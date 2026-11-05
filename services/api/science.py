"""Deterministic measurements. No model output participates in these calculations."""
import math
from dataclasses import dataclass
import numpy as np
from pyproj import CRS, Transformer
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from PIL import Image
from rasterio.features import geometry_mask
from shapely.geometry import Polygon, mapping

@dataclass
class Grid:
    crs: CRS
    transform: object
    size: int
    resolution: float
    polygon: dict
    search_boxes: list
    bounds: list
    area_mask: object = None

def make_grid(lon, lat, side_km, resolution, aoi_polygon=None):
    crs = CRS.from_proj4(f'+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs')
    reverse = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
    half = side_km * 500
    n = math.ceil(side_km * 1000 / resolution)
    actual = side_km * 1000 / n
    corners = [(-half,-half),(half,-half),(half,half),(-half,half),(-half,-half)]
    ring = [list(reverse.transform(x,y)) for x,y in corners]
    # Sample curved edges for a conservative catalog search and preview footprint.
    edge = []
    for a,b in zip(corners,corners[1:]):
        for t in np.linspace(0,1,33):
            edge.append(reverse.transform(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    xs,ys = zip(*edge)
    west,east,south,north = min(xs),max(xs),min(ys),max(ys)
    forward=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    pole_x,pole_y=forward.transform(lon,90 if lat>=0 else -90)
    contains_pole=abs(pole_x)<=half and abs(pole_y)<=half
    if contains_pole:
        west,east=-180,180
        if lat>=0:north=90
        else:south=-90
        boxes=[[west,south,east,north]]
    elif east-west > 180:
        west=min(x for x in xs if x>=0); east=max(x for x in xs if x<0)
        boxes=[[west,south,180,north],[-180,south,east,north]]
    else:
        boxes=[[west,south,east,north]]
    transform = from_origin(-half,half,actual,actual)
    mask = None
    if aoi_polygon is not None:
        local = Polygon([forward.transform(*point) for point in aoi_polygon])
        mask = geometry_mask([mapping(local)],out_shape=(n,n),transform=transform,invert=True)
        if not mask.any(): raise ValueError('The boundary contains no analysis-cell centers. Draw a larger area.')
        ring = aoi_polygon
    return Grid(crs, transform, n, actual, {'type':'Polygon','coordinates':[ring]}, boxes, [west,south,east,north], mask)

def selection_mask(grid):
    return grid.area_mask if grid.area_mask is not None else np.ones((grid.size,grid.size),dtype=bool)

def coverage_pct(valid, selected):
    return float((valid & selected).sum() / selected.sum() * 100) if selected.any() else 0.

def ratio(a,b):
    out=np.full(a.shape,np.nan,dtype='float32')
    np.divide(a-b,a+b,out=out,where=np.isfinite(a)&np.isfinite(b)&(np.abs(a+b)>1e-6))
    return out

def indices(bands,valid):
    ndvi=ratio(bands['nir'],bands['red'])
    water=ratio(bands['green'],bands['swir'])
    ground=ratio(bands['swir']+bands['red'],bands['nir']+bands['blue'])
    result=np.stack([ndvi,water,ground])
    result[:,~valid]=np.nan
    return result

def qa_mask(source, qa, saturation=None):
    q=qa.astype('uint32')
    if source=='landsat':
        valid=(q & 0b111111)==0  # fill, dilated cloud, cirrus, cloud, shadow, snow
        if saturation is not None: valid &= saturation==0
    elif source=='sentinel2': valid=np.isin(q,[4,5,6])
    elif source.startswith('hls'): valid=((q & 0b11111)==0)&(q!=255)  # cirrus/cloud/adjacent/shadow/snow
    elif source=='modis': valid=((q & 3)==0)&((q & (1<<2))==0)&((q & (3<<8))==0)&((q & (1<<10))==0)&((q & (1<<12))==0)&((q & (1<<13))==0)&((q & (1<<15))==0)
    else: valid=np.isfinite(qa)
    return valid

def compare(before,after,cell_m,water_threshold=0,support=None):
    valid=np.isfinite(before).all(axis=0)&np.isfinite(after).all(axis=0)
    selected=np.ones(valid.shape,dtype=bool) if support is None else support
    valid &= selected
    hectares=cell_m**2/10000
    w0=(before[1]>water_threshold)&valid; w1=(after[1]>water_threshold)&valid
    gain=w1&~w0; loss=w0&~w1
    d=after[0]-before[0]
    vegetation_valid=valid&~w0&~w1
    green=(d>=.1)&vegetation_valid; brown=(d<=-.1)&vegetation_valid
    bare=((after[2]-before[2])>=.1)&vegetation_valid
    a0=float(w0.sum()*hectares); a1=float(w1.sum()*hectares)
    metrics={'before_water_ha':a0,'after_water_ha':a1,'water_gain_ha':float(gain.sum()*hectares),'water_loss_ha':float(loss.sum()*hectares),'net_water_ha':a1-a0,'relative_water_pct':(a1-a0)/a0*100 if a0 else None,'greening_ha':float(green.sum()*hectares),'browning_ha':float(brown.sum()*hectares),'exposed_ground_increase_ha':float(bare.sum()*hectares),'common_valid_ha':float(valid.sum()*hectares),'common_valid_pct':coverage_pct(valid,selected),'mean_ndvi_change':float(np.mean(d[vegetation_valid])) if vegetation_valid.any() else None}
    if not valid.any():
        for key in metrics:
            if key not in ('common_valid_ha','common_valid_pct'):metrics[key]=None
    return metrics, {'water_gain':gain,'water_loss':loss,'greening':green,'browning':brown,'ground':bare,'valid':valid}

def rgb_preview(bands,valid):
    rgb=np.stack([bands['red'],bands['green'],bands['blue']],axis=-1)
    rgb=np.nan_to_num(np.clip((rgb-.015)/.3,0,1))**(1/1.6)
    return np.dstack([(rgb*255).astype('uint8'), valid.astype('uint8')*255])

def display_preview(rgba,support=None):
    """Never reveal an undated basemap through missing scientific pixels."""
    result=rgba.copy();invalid=rgba[:,:,3]==0
    yy,xx=np.indices(invalid.shape)
    result[invalid]=[49,65,74,255]
    result[invalid&((xx+yy)%12<3)]=[120,139,150,255]
    if support is not None: result[~support]=0
    return result

def geographic_image(rgba,grid,path,max_edge=1400):
    west,south,east,north=grid.bounds
    if east<west: east+=360
    aspect=max(.1,min(10,(east-west)*math.cos(math.radians((north+south)/2))/(north-south)))
    w=int(min(max_edge,max_edge*aspect)); h=int(min(max_edge,max_edge/aspect))
    w=max(w,2); h=max(h,2)
    dst=np.zeros((4,h,w),dtype='uint8')
    dst_transform=from_origin(west,north,(east-west)/w,(north-south)/h)
    for i in range(4):
        reproject(rgba[:,:,i],dst[i],src_transform=grid.transform,src_crs=grid.crs,dst_transform=dst_transform,dst_crs='EPSG:4326',resampling=Resampling.nearest,num_threads=1,warp_mem_limit=64)
    Image.fromarray(np.moveaxis(dst,0,-1)).save(path)

def change_rgba(masks,theme):
    shape=masks['valid'].shape
    out=np.zeros((*shape,4),dtype='uint8')
    if theme in ('water','coast'):
        out[masks['water_gain']]=[41,166,212,220]; out[masks['water_loss']]=[228,139,67,220]
    elif theme=='forest' and 'forest_decline' in masks:
        out[masks['forest_decline']]=[228,139,67,220]
    elif theme in ('vegetation','forest'):
        out[masks['greening']]=[63,173,111,220]; out[masks['browning']]=[228,139,67,220]
    else: out[masks['ground']]=[228,139,67,220]
    yy,xx=np.indices(shape)
    out[(~masks['valid'])&((xx+yy)%12<3)]=[170,181,190,110]
    if 'selected' in masks: out[~masks['selected']]=0
    return out

def theil_sen(years,values):
    if len(years)<5: return None
    return float(np.median([(values[j]-values[i])/(years[j]-years[i]) for i in range(len(years)) for j in range(i+1,len(years)) if years[j]!=years[i]]))
