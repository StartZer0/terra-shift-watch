"""Dated contextual layers. These are not independent validation labels."""
import math
import numpy as np
import rasterio
import httpx
import planetary_computer
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
from .config import STAC_URL
from .science import selection_mask, coverage_pct, geographic_image

GFC='https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12'

def forest_context(grid,first_year,last_year,decline,check,common_valid=None,output_path=None):
    if first_year<2000 or last_year>2024:
        return {'state':'unavailable','reason':'The pinned forest reference covers 2000–2024. This comparison extends beyond it.'},None
    mosaic={k:np.full((grid.size,grid.size),255,dtype='uint8') for k in ('treecover2000','lossyear','datamask')}
    tiles=set()
    for west,south,east,north in grid.search_boxes:
        for x in range(math.floor(west/10)*10,math.ceil(east/10)*10,10):
            for y in range(math.floor(south/10)*10+10,math.ceil(north/10)*10+1,10):
                if -50<=y<=80: tiles.add((x,y))
    if len(tiles)>16: return {'state':'unavailable','reason':'Reference selection exceeds the local tile budget.'},None
    completed=[]
    for x,y in sorted(tiles):
        tile=f'{abs(y):02d}{"N" if y>=0 else "S"}_{abs(x):03d}{"E" if x>=0 else "W"}'
        for layer in mosaic:
            check();url=f'{GFC}/Hansen_GFC-2024-v1.12_{layer}_{tile}.tif'
            with rasterio.open(url) as src:
                with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.size,height=grid.size,src_nodata=255,nodata=255,dtype='uint8',resampling=Resampling.nearest,warp_mem_limit=64) as vrt:
                    for row in range(0,grid.size,512):
                        for col in range(0,grid.size,512):
                            check();h=min(512,grid.size-row);w=min(512,grid.size-col)
                            data=vrt.read(1,window=Window(col,row,w,h))
                            dest=mosaic[layer][row:row+h,col:col+w]; np.copyto(dest,data,where=data!=255)
        completed.append(tile)
    tree=mosaic['treecover2000'];loss=mosaic['lossyear'];valid=(mosaic['datamask']==1)&(tree!=255)&(loss!=255)&selection_mask(grid)
    # Excludes mapped loss before the starting year; cannot reconstruct later regrowth.
    baseline=(tree>=30)&valid&((loss==0)|(loss>first_year-2000))
    candidate=baseline&decline
    mapped_loss=baseline&(loss>first_year-2000)&(loss<=last_year-2000)
    context={'state':'ready','dataset':'Hansen Global Forest Change 2000–2024 v1.12','baseline_year':2000,'canopy_threshold_pct':30,'reference_coverage_pct':coverage_pct(valid,selection_mask(grid)),'mapped_baseline_ha':float(baseline.sum()*grid.resolution**2/10000),'vegetation_decline_within_baseline_ha':float(candidate.sum()*grid.resolution**2/10000),'mapped_loss_pixels_ha':float(mapped_loss.sum()*grid.resolution**2/10000),'tiles':completed,'url':GFC+'/download.html','attribution':'Hansen/UMD/Google/USGS/NASA, CC BY 4.0; reprojected and thresholded by Terra Shift','limitations':['Mapped pixel areas are descriptive map summaries, not statistically unbiased estimates of forest loss.','Tree-cover loss includes harvest, fire and other disturbance; permanent deforestation is not established.','This reference uses Landsat too and is not independent validation of the satellite pipeline.','Loss dates are annual and do not establish timing within the endpoint acquisition windows. Regrowth after the baseline is not reconstructed.']}
    context['comparable_baseline_ha']=float((baseline&common_valid).sum()*grid.resolution**2/10000) if common_valid is not None else None
    context['annual_loss']=[{'year':year,'loss_ha':float((mapped_loss&(loss==year-2000)).sum()*grid.resolution**2/10000)} for year in range(first_year,last_year+1)]
    if output_path is not None:
        image=np.zeros((*baseline.shape,4),dtype='uint8')
        image[baseline]=[48,128,76,210];image[mapped_loss]=[196,69,38,240]
        yy,xx=np.indices(baseline.shape);unknown=selection_mask(grid)&(mosaic['datamask']==255)
        image[unknown]=[54,68,77,150];image[unknown&((xx+yy)%12<3)]=[170,181,190,180]
        np.savez_compressed(output_path/'forest-baseline.npz',baseline=baseline)
        context['image']='forest-reference.png';geographic_image(image,grid,output_path/context['image'])
    return context,candidate

def terrain_context(grid,exposed,check):
    items={}
    with httpx.Client(timeout=40) as client:
        for bbox in grid.search_boxes:
            r=client.post(STAC_URL+'/search',json={'collections':['cop-dem-glo-30'],'bbox':bbox,'limit':100});r.raise_for_status()
            for item in r.json().get('features',[]): items[item['id']]=item
    if len(items)>36: return {'state':'unavailable','reason':'Terrain reference exceeds the local 36-tile budget.'}
    heights=np.full((grid.size,grid.size),np.nan,dtype='float32')
    for item in items.values():
        check();signed=planetary_computer.sign(item)
        key=next((k for k,v in signed['assets'].items() if 'data' in v.get('roles',[])),None)
        if not key: continue
        with rasterio.open(signed['assets'][key]['href']) as src:
            with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.size,height=grid.size,dtype='float32',nodata=np.nan,resampling=Resampling.bilinear,warp_mem_limit=64) as vrt:
                for row in range(0,grid.size,512):
                    for col in range(0,grid.size,512):
                        check();h=min(512,grid.size-row);w=min(512,grid.size-col)
                        data=vrt.read(1,window=Window(col,row,w,h));dest=heights[row:row+h,col:col+w];np.copyto(dest,data,where=np.isfinite(data))
    valid=np.isfinite(heights)&selection_mask(grid)
    if not valid.any(): return {'state':'unavailable','reason':'No usable terrain reference in this selection.'}
    gy,gx=np.gradient(heights,grid.resolution)
    slope=np.degrees(np.arctan(np.sqrt(gx*gx+gy*gy)))
    support=exposed&np.isfinite(slope)
    return {'state':'ready','dataset':'Copernicus DEM GLO-30','reference_type':'static digital surface model, approximately 30 m source cells','valid_pct':coverage_pct(valid,selection_mask(grid)),'minimum_elevation_m':float(np.min(heights[valid])),'maximum_elevation_m':float(np.max(heights[valid])),'mean_slope_degrees_in_exposed_change':float(np.mean(slope[support])) if support.any() else None,'attribution':'Copernicus DEM, European Union / ESA; reprojected by Terra Shift','limitation':'Terrain provides static context. Slope is sensitive to analysis resolution and surface objects; it does not establish erosion, elevation change or soil loss.'}
