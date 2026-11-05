"""One bounded satellite inspection process. Raw arrays die with this process."""
from . import config
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlparse
import json,math,os,sys,time
import numpy as np
import psutil
import rasterio
import httpx
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from PIL import Image
from .science import make_grid,selection_mask,coverage_pct,geographic_image
from .watch_providers import discover,now_iso

ALLOWED_HOSTS={'archive.podaac.earthdata.nasa.gov','data.podaac.earthdatacloud.nasa.gov','data.lpdaac.earthdatacloud.nasa.gov'}

def read_classification(url,grid,check):
    if urlparse(url).hostname not in ALLOWED_HOSTS or urlparse(url).scheme!='https':raise ValueError('Untrusted NASA asset host.')
    token=os.getenv('EARTHDATA_TOKEN')
    if not token:raise ValueError('NASA Earthdata token is not configured.')
    check()
    # Earthdata returns signed CloudFront assets. Resolve with an authenticated
    # byte-range GET, then never forward the Earthdata bearer to the CDN.
    headers={'Authorization':f'Bearer {token}','Range':'bytes=0-0'}
    with httpx.Client(timeout=25,follow_redirects=False) as client:
        with client.stream('GET',url,headers=headers) as response:
            if response.status_code in (302,303,307,308):
                asset_url=response.headers.get('location','')
                parsed=urlparse(asset_url)
                if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.cloudfront.net'):raise ValueError('Unexpected NASA download redirect.')
                raster_headers=''
            else:
                response.raise_for_status();asset_url=url;raster_headers=f'Authorization: Bearer {token}'
    with rasterio.Env(GDAL_HTTP_HEADERS=raster_headers,GDAL_HTTP_TIMEOUT=25,GDAL_HTTP_MAX_RETRY=0,GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_USE_HEAD='NO',CPL_LOG=os.devnull):
        with rasterio.open(asset_url) as src:
            with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.size,height=grid.size,src_nodata=255,nodata=255,resampling=Resampling.nearest,warp_mem_limit=32) as vrt:
                values=vrt.read(1)
    check();return values

def inspect_satellite(settings,path,include_sam):
    path=Path(path);path.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    def check():
        if time.monotonic()-started>420:raise TimeoutError('Satellite inspection exceeded its time budget.')
        if psutil.Process().memory_info().rss>768*1024**2:raise MemoryError('Satellite inspection memory ceiling reached.')
    resolution=max(60,math.ceil(settings['side_km']*1000/512))
    grid=make_grid(settings['longitude'],settings['latitude'],settings['side_km'],resolution,settings.get('aoi_polygon'));selected=selection_mask(grid)
    catalog=discover(settings)
    result={'state':'ready','checked_at':now_iso(),'observed_at':None,'resolution_m':grid.resolution,'bounds':grid.bounds,'catalog':catalog,'notes':[],'sam':[],'sam_summary':{},'traces':[]}
    dates=[];confirmed=None
    for product,layer in [('water','water'),('disturbance','vegetation'),('disturbance','ground')]:
        provider=next((p for p in catalog if p['id']=='opera_'+product),{})
        granules=[g for g in provider.get('granules',[]) if layer in g.get('assets',{})]
        if not granules:
            result[layer]={'state':'unavailable','reason':'No matching recent OPERA raster was discovered.'};continue
        latest=granules[0]
        try:
            valid=None;attempted=0
            # A catalog intersection may be all clouds/nodata. Try a bounded
            # set of dated acquisitions rather than interpreting that as absence.
            for candidate in granules[:3]:
                attempted+=1
                candidate_data=read_classification(candidate['assets'][layer],grid,check)
                candidate_valid=selected&np.isin(candidate_data,[0,1,2] if layer=='water' else list(range(9)))
                if coverage_pct(candidate_valid,selected)>=5:
                    latest=candidate;data=candidate_data;valid=candidate_valid;break
            if valid is None:
                result[layer]={'state':'unavailable','reason':'The bounded recent tile sample has insufficient valid classified coverage (cloud, shadow, or no-data). This is not absence of the feature.'};continue
            mask=valid&np.isin(data,[1,2] if layer=='water' else [3,6])
            evidence={'state':'ready','date':latest['date'],'granule_id':latest['id'],'coverage_pct':coverage_pct(valid,selected),'mapped_ha':float(mask.sum()*grid.resolution**2/10000),'confirmed_pct':float(mask.sum()/valid.sum()*100),'candidates_read':attempted,'note':'One sampled OPERA tile, clipped to the boundary. Coverage may be partial.'}
            dates.append(latest['date']);image=np.zeros((*mask.shape,4),dtype='uint8');image[mask]=[51,178,204,220] if layer=='water' else [224,142,62,225]
            geographic_image(image,grid,path/f'opera-{layer}.png');evidence['image']=f'opera-{layer}.png'
            if layer=='vegetation':confirmed=(mask,valid)
            if layer=='water':
                tile=latest['title'].split('_')[3]
                prior=next((g for g in reversed(granules) if g['title'].split('_')[3]==tile and g['date'][:10]<latest['date'][:10]),None)
                if prior:
                    try:
                        before=read_classification(prior['assets'][layer],grid,check);common=valid&np.isin(before,[0,1,2]);a=np.isin(before,[1,2])&common;b=mask&common
                        if common.any():
                            evidence['change']={'before_date':prior['date'],'after_date':latest['date'],'common_valid_pct':coverage_pct(common,selected),'before_ha':float(a.sum()*grid.resolution**2/10000),'after_ha':float(b.sum()*grid.resolution**2/10000),'net_ha':float((b.sum()-a.sum())*grid.resolution**2/10000)}
                            days=(datetime.fromisoformat(latest['date'].replace('Z','+00:00'))-datetime.fromisoformat(prior['date'].replace('Z','+00:00'))).total_seconds()/86400
                            if days>0:evidence['change']['rate_ha_per_day']=evidence['change']['net_ha']/days
                    except Exception:evidence['change_note']='A comparable earlier classified raster was unavailable; no change was calculated.'
            result[layer]=evidence
        except Exception as error:
            result[layer]={'state':'unavailable','reason':f'NASA raster could not be measured ({type(error).__name__}). Verify Earthdata application authorization and product access; catalog discovery alone is not measurement.'}
    if confirmed is not None and 'forest' in settings['features']:
        try:
            from .references import forest_context
            forest,mask=forest_context(grid,2024,2024,confirmed[0],check,confirmed[1],path)
            result['forest']={'state':forest['state'],'disturbance_ha':forest['vegetation_decline_within_baseline_ha'],'reference_coverage_pct':forest['reference_coverage_pct'],'comparable_baseline_ha':forest['comparable_baseline_ha'],'observation_coverage_pct':coverage_pct(confirmed[1],selected),'baseline_year':2024,'note':'Dated 2000 tree-cover reference, excluding mapped loss through 2024; later regrowth and loss are not reconstructed.'}
        except Exception as error:result['forest']={'state':'unavailable','reason':f'Tree-cover reference unavailable ({type(error).__name__}).'}
    result['observed_at']=min(dates) if dates else None
    if include_sam:
        try:result.update(inspect_optical(settings,grid,path,check))
        except Exception as error:result['notes'].append(f'Optical/SAM inspection unavailable ({type(error).__name__}); NASA evidence remains separate.')
    # Only active preview PNGs and this compact summary survive. Raw arrays are never archived.
    for entry in result['sam']:entry.pop('mask',None)
    for raw in path.glob('*.npz'):raw.unlink(missing_ok=True)
    for raw in path.glob('source-*.png'):raw.unlink(missing_ok=True)
    (path/'summary.json').write_text(json.dumps(result,allow_nan=False))
    return result

def inspect_optical(settings,grid,path,check):
    from .contracts import AnalysisRequest
    from .catalog import search,read_scene,acquisition
    from .science import indices,rgb_preview,display_preview
    from .segmentation import run_history,summarize
    today=date.today();before=today-timedelta(days=35);after=today-timedelta(days=5)
    themes=[t for t in settings['features'] if t!='forest'] or ['vegetation']
    req=AnalysisRequest(longitude=settings['longitude'],latitude=settings['latitude'],side_km=settings['side_km'],aoi_polygon=settings.get('aoi_polygon'),source='sentinel2',mode='event',before_date=before,after_date=after,window_days=10,resolution=max(60,int(math.ceil(grid.resolution))),themes=themes,use_reasoning=False)
    observations=[]
    for index,target in enumerate((before,after)):
        candidates=search(req,grid,target-timedelta(days=10),min(today,target+timedelta(days=10)))
        for item in candidates[:3]:
            check();bands,valid,_=read_scene(item,'sentinel2',grid,check);valid&=selection_mask(grid)
            if coverage_pct(valid,selection_mask(grid))<20:continue
            values=indices(bands,valid);rgb=rgb_preview(bands,valid)
            np.savez_compressed(path/f'observation-{index}.npz',values=values)
            Image.fromarray(rgb).save(path/f'source-{index}.png')
            geographic_image(display_preview(rgb,selection_mask(grid)),grid,path/f'optical-{index}.png')
            observations.append({'index':index,'label':acquisition(item)[:10],'date':acquisition(item),'state':'ready','source_image':f'source-{index}.png','image':f'optical-{index}.png','valid_pct':coverage_pct(valid,selection_mask(grid))});break
    if not observations:raise ValueError('No usable recent optical scene.')
    entries,traces=run_history(req,observations,grid,path,check)
    container={'request':req.model_dump(mode='json'),'observations':observations,'sam':entries,'metrics':{}}
    summarize(container,grid,path,check)
    return {'sam':entries,'sam_summary':container['sam_summary'],'optical_observations':observations,'traces':traces,'sam_note':'Actual SAM masks on the available dated optical acquisitions; their dates may be older than the OPERA observation or forecast. A single usable acquisition does not establish change. Guided results are not independent validation.'}

if __name__=='__main__':
    try:inspect_satellite(json.loads(Path(sys.argv[1]).read_text()),Path(sys.argv[2]),sys.argv[3]=='sam')
    except Exception as error:
        Path(sys.argv[2]).mkdir(parents=True,exist_ok=True)
        (Path(sys.argv[2])/'summary.json').write_text(json.dumps({'state':'unavailable','checked_at':now_iso(),'notes':[f'Satellite inspection stopped ({type(error).__name__}).'],'sam':[],'sam_summary':{}}))
