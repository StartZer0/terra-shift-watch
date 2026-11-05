import calendar
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import httpx
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
import planetary_computer
from .config import STAC_URL, SOURCES
from .science import qa_mask

def windows(req):
    if req.mode=='event':
        return [(str(d),d-timedelta(days=req.window_days),min(date.today(),d+timedelta(days=req.window_days))) for d in (req.before_date,req.after_date)]
    return [(str(y),date(y,req.start_month,1),min(date.today(),date(y,req.end_month,calendar.monthrange(y,req.end_month)[1]))) for y in range(req.from_year,req.to_year+1)]

def search(req,grid,start,end):
    if start>end: return []
    found={}
    for bbox in grid.search_boxes:
        body={'collections':[SOURCES[req.source]['collection']], 'bbox':bbox,'datetime':f'{start}T00:00:00Z/{end}T23:59:59Z','limit':100}
        if req.source not in ('sentinel1','modis'): body['query']={'eo:cloud_cover':{'lt':70}}
        with httpx.Client(timeout=45) as client:
            r=client.post(f'{STAC_URL}/search',json=body); r.raise_for_status()
            for item in r.json().get('features',[]): found[item['id']]=item
    items=list(found.values())
    if req.source=='modis':
        # Keep one platform throughout the time series; no silent Terra/Aqua mixing.
        items=[i for i in items if str(i['properties'].get('platform','')).lower()=='terra']
    def rank(item):
        props=item['properties'];score=props.get('eo:cloud_cover',100)
        if props.get('platform')=='landsat-7' and (acquisition(item) or '')>='2003-06': score+=20
        return score
    return sorted(items,key=rank)

def acquisition(item):
    props=item['properties']
    return props.get('datetime') or props.get('start_datetime')

def sentinel_calibration(item):
    """Read actual product offsets, including reprocessed older acquisitions."""
    asset=item['assets'].get('product-metadata')
    if not asset: raise ValueError('Sentinel product calibration metadata is unavailable.')
    with httpx.Client(timeout=40) as client:
        r=client.get(asset['href']); r.raise_for_status()
        if len(r.content)>10_000_000: raise ValueError('Unexpectedly large calibration metadata.')
    root=ET.fromstring(r.content)
    quant=None; offsets={}
    for node in root.iter():
        tag=node.tag.split('}')[-1]
        if tag=='BOA_QUANTIFICATION_VALUE': quant=float(node.text)
        if tag=='BOA_ADD_OFFSET': offsets[int(node.attrib['band_id'])]=float(node.text)
    if not quant or quant<=0: raise ValueError('Sentinel reflectance quantification value is missing.')
    baseline=float(item['properties'].get('s2:processing_baseline','nan'))
    if not offsets and (not np.isfinite(baseline) or baseline>=4): raise ValueError('Sentinel baseline needs explicit offsets, but none were supplied.')
    band_ids={'B02':1,'B03':2,'B04':3,'B8A':8,'B11':11}
    return {key:(1/quant,offsets.get(index,0)/quant) for key,index in band_ids.items()}

def asset_keys(item,source):
    available=item['assets']
    if source=='landsat': keys={'blue':'blue','green':'green','red':'red','nir':'nir08','swir':'swir16','qa':'qa_pixel','saturation':'qa_radsat'}
    elif source=='sentinel2': keys={'blue':'B02','green':'B03','red':'B04','nir':'B8A','swir':'B11','qa':'SCL'}
    elif source=='hls_l30': keys={'blue':'B02','green':'B03','red':'B04','nir':'B05','swir':'B06','qa':'Fmask'}
    elif source=='hls_s30': keys={'blue':'B02','green':'B03','red':'B04','nir':'B8A','swir':'B11','qa':'Fmask'}
    elif source=='modis': keys={'blue':'sur_refl_b03','green':'sur_refl_b04','red':'sur_refl_b01','nir':'sur_refl_b02','swir':'sur_refl_b06','qa':'sur_refl_state_500m','saturation':'sur_refl_qc_500m'}
    else: keys={'vv':'vv','vh':'vh'}
    # Collection versions sometimes expose capitalization differences; never guess different bands.
    lower={k.lower():k for k in available}
    for name,key in list(keys.items()):
        if key not in available and key.lower() in lower: keys[name]=lower[key.lower()]
        elif key not in available: raise ValueError(f'Missing required {name} band in {source} item.')
    return keys

def read_scene(item,source,grid,check):
    keys=asset_keys(item,source); bands={}; provenance={}
    signed=planetary_computer.sign(item)
    s2_calibration=sentinel_calibration(signed) if source=='sentinel2' else None
    for name,key in keys.items():
        check()
        asset=signed['assets'][key]
        is_qa=name in ('qa','saturation')
        with rasterio.open(asset['href']) as src:
            metadata=item['assets'][key].get('raster:bands',[{}])[0]
            scale=metadata.get('scale'); offset=metadata.get('offset')
            if scale is None and src.scales[0]!=1: scale=src.scales[0]
            if offset is None and src.offsets[0]!=0: offset=src.offsets[0]
            if not is_qa and source!='sentinel1':
                if scale is None:
                    # Published collection calibration only; S2 shifted baselines must come from metadata.
                    if source=='landsat': scale,offset=.0000275,-.2
                    elif source.startswith('hls') or source=='modis': scale,offset=.0001,0
                    else: scale,offset=s2_calibration[key]
                if offset is None: offset=0
            dtype='float64' if is_qa else 'float32'
            with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.size,height=grid.size,resampling=Resampling.nearest if is_qa else Resampling.bilinear,dtype=dtype,nodata=np.nan,warp_mem_limit=64) as vrt:
                data=np.empty((grid.size,grid.size),dtype=dtype)
                for y in range(0,grid.size,512):
                    for x in range(0,grid.size,512):
                        check(); h=min(512,grid.size-y); w=min(512,grid.size-x)
                        data[y:y+h,x:x+w]=vrt.read(1,window=Window(x,y,w,h))
            if not is_qa and source!='sentinel1': data=data*scale+offset
            bands[name]=data
            provenance[name]={'asset':key,'scale':scale,'offset':offset,'nodata':str(src.nodata)}
    if source=='sentinel1':
        valid=np.isfinite(bands['vv'])&np.isfinite(bands['vh'])&(bands['vv']>0)&(bands['vh']>0)
    else:
        finite=np.ones((grid.size,grid.size),dtype=bool)
        for band in bands.values(): finite &= np.isfinite(band)
        qa=np.nan_to_num(bands['qa'],nan=65535)
        saturation=bands.get('saturation')
        valid=finite&qa_mask(source,qa,saturation)
        if source=='modis' and saturation is not None:
            q=np.nan_to_num(saturation,nan=4294967295).astype('uint32')
            valid &= (q & 3)==0
            for band in (1,2,3,4,6): valid &= ((q >> (2+4*(band-1))) & 15)==0
        for key in ('red','blue','green','nir','swir'): valid &= (bands[key]>-.1)&(bands[key]<=1.2)
    return bands,valid,provenance
