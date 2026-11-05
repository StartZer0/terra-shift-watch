import json
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from shapely.geometry import shape,mapping
from affine import Affine

def evidence_layers(path,result,archive):
    transform=Affine(*result['grid']['transform']);crs=result['grid']['crs']
    features=[];truncated=False
    with np.load(path/'change.npz') as masks:
        themes=result['request'].get('themes') or [result['request']['theme']]
        selected={}
        for theme in themes:
            classes=['water_gain','water_loss'] if theme in ('water','coast') else ['forest_decline'] if theme=='forest' and 'forest_decline' in masks else ['ground'] if theme=='ground' else ['greening','browning']
            for name in classes:selected.setdefault(name,[]).append(theme)
        for name,related_themes in selected.items():
            mask=masks[name].astype('uint8')
            for geometry,value in shapes(mask,mask=mask.astype(bool),transform=transform):
                local=shape(geometry);area=local.area
                if area<4*result['grid']['resolution_m']**2: continue
                geo=transform_geom(crs,'EPSG:4326',mapping(local.simplify(result['grid']['resolution_m']/2,preserve_topology=True)),precision=7)
                label={'water_gain':'backscatter_decrease','water_loss':'backscatter_increase'}.get(name,name) if result['request']['source']=='sentinel1' else name
                features.append({'type':'Feature','geometry':geo,'properties':{'class':label,'themes':related_themes,'mapped_area_ha':area/10000}})
                if len(features)>=2500: truncated=True;break
            if truncated:break
    archive.writestr('change-regions.geojson',json.dumps({'type':'FeatureCollection','features':features,'export_policy':{'minimum_component_pixels':4,'simplification_m':result['grid']['resolution_m']/2,'feature_limit':2500,'truncated':truncated,'note':'Vector display generalization does not change raster-derived measurements. Classes are observations, not confirmed causes.'}}))
    # Export derived science, never raw provider files. These paths expire with the active run.
    for role,index in [('before',result['comparison']['before_index']),('after',result['comparison']['after_index'])]:
        data=np.load(path/f'indices-{index}.npz')['values']
        target=path/f'{role}-indices.tif'
        with rasterio.open(target,'w',driver='GTiff',height=data.shape[1],width=data.shape[2],count=3,dtype='float32',crs=crs,transform=transform,nodata=np.nan,compress='deflate',tiled=True) as dst:
            dst.write(data)
            names=('VV dB','VH dB','unused') if result['request']['source']=='sentinel1' else ('NDVI','MNDWI','BSI')
            for band,name in enumerate(names,1):dst.set_band_description(band,name)
        archive.write(target,target.name)
        target.unlink(missing_ok=True)
