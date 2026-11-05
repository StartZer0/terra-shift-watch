"""One isolated, cancellable raster worker. All imagery belongs to one temporary run."""
from . import config  # establish GDAL and BLAS limits before importing NumPy
import gc
import json
import os
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image
import psutil
from .contracts import AnalysisRequest
from .catalog import windows, search, read_scene, acquisition
from .science import make_grid, indices, rgb_preview, display_preview, geographic_image, compare, change_rgba, theil_sen, selection_mask, coverage_pct
from .meta import segment, explain, ProviderError
from .weather import weather_context
from .references import forest_context, terrain_context
from .assessment import annual_history, build_assessment, explanation_evidence
from .segmentation import run_history, summarize as summarize_sam

def write_json(path,data):
    temp=path.with_suffix('.partial'); temp.write_text(json.dumps(data,allow_nan=False)); temp.replace(path)

class Job:
    def __init__(self,path):
        self.path=Path(path); self.started=time.time(); self.last_check=0
        self.peak_rss=0
        self.req=AnalysisRequest.model_validate_json((self.path/'request.json').read_text())
    def check(self):
        if not self.path.exists() or (self.path/'cancel').exists(): raise InterruptedError('Analysis cancelled.')
        now=time.time()
        if now-self.last_check>3:
            self.last_check=now
            rss=psutil.Process().memory_info().rss;self.peak_rss=max(self.peak_rss,rss)
            if rss>int(os.getenv('WORKER_RSS_CEILING_MIB','1024'))*1024**2: raise MemoryError('Worker memory limit reached. Choose a coarser analysis cell size.')
            total=sum(p.stat().st_size for p in self.path.rglob('*') if p.is_file())
            if total>int(os.getenv('TEMP_JOB_QUOTA_MIB','2048'))*1024**2: raise MemoryError('Temporary storage limit reached.')
            if psutil.disk_usage(self.path).free<int(os.getenv('HOST_FREE_DISK_RESERVE_MIB','2048'))*1024**2: raise MemoryError('Not enough free disk space for this analysis.')
    def progress(self,stage,pct,**extra):
        self.check(); write_json(self.path/'status.json',{'state':'running','stage':stage,'progress':pct,'elapsed_seconds':round(time.time()-self.started),**extra})

def run(path):
    job=Job(path); req=job.req; grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    support=selection_mask(grid)
    observations=[]; notes=[]; traces=[]; orbit=None
    periods=windows(req)
    for index,(label,start,end) in enumerate(periods):
        job.progress(f'Finding observations for {label}',5+55*index/len(periods))
        entry={'index':index,'label':label,'year':start.year,'window':[str(start),str(end)],'state':'missing','scenes':[]}
        try: items=search(req,grid,start,end)
        except Exception as e:
            entry['reason']=f'Catalog request failed ({type(e).__name__}).'; observations.append(entry); continue
        if req.source=='sentinel1':
            if orbit is None and items:
                props=items[0]['properties']; orbit=(props.get('sat:relative_orbit'),props.get('sat:orbit_state'))
            items=[i for i in items if (i['properties'].get('sat:relative_orbit'),i['properties'].get('sat:orbit_state'))==orbit and orbit[0] is not None]
        limit=1 if req.mode=='event' else req.max_scenes
        # Bound the cloud-ranked scene sample; per-pixel QA is checked after retrieval.
        items=items[:max(limit*3,limit)]
        if req.mode=='event': items.sort(key=lambda i:abs((datetime.fromisoformat(acquisition(i).replace('Z','+00:00')).date()- (req.before_date if index==0 else req.after_date)).days))
        arrays=[]; best_valid=-1; best_rgb=None; best_indices=None; best_item=None
        for item in items:
            if req.mode=='history' and len(arrays)>=limit: break
            job.progress(f'Reading {label} · observation {len(arrays)+1}/{limit}',7+55*index/len(periods))
            try:
                bands,valid,calibration=read_scene(item,req.source,grid,job.check)
                valid &= support
                if coverage_pct(valid,support)<5: continue
                if req.source=='sentinel1':
                    vv=np.full(valid.shape,np.nan,dtype='float32'); vv[valid]=10*np.log10(bands['vv'][valid])
                    vh=np.full(valid.shape,np.nan,dtype='float32'); vh[valid]=10*np.log10(bands['vh'][valid])
                    data=np.stack([vv,vh,np.zeros_like(vv)])
                    gray=np.nan_to_num(np.clip((vv+25)/25,0,1)*255).astype('uint8')
                    rgb=np.dstack([gray,gray,gray,valid.astype('uint8')*255])
                else: data=indices(bands,valid); rgb=rgb_preview(bands,valid)
                if req.mode=='history': arrays.append(data)
                entry['scenes'].append({'id':item['id'],'date':acquisition(item),'end_date':item['properties'].get('end_datetime'),'platform':item['properties'].get('platform'),'valid_pct':round(coverage_pct(valid,support),2),'calibration':calibration})
                if coverage_pct(valid,support)>best_valid:
                    best_valid=coverage_pct(valid,support); best_rgb=rgb; best_indices=data; best_item=entry['scenes'][-1]
                if req.mode=='event': arrays=[best_indices]
                del bands; gc.collect()
                if req.mode=='event' and best_valid>=98: break
            except (InterruptedError,MemoryError): raise
            except Exception as e:
                notes.append(f'{label}: a scene could not be read ({type(e).__name__}).')
        if arrays:
            if req.mode=='event': entry['scenes']=[best_item]
            job.check()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning); composite=np.nanmedian(np.stack(arrays),axis=0)
            valid=np.isfinite(composite).all(axis=0)
            np.savez_compressed(job.path/f'indices-{index}.npz',values=composite)
            np.savez_compressed(job.path/f'observation-{index}.npz',values=best_indices)
            Image.fromarray(best_rgb).save(job.path/f'source-{index}.png')
            geographic_image(display_preview(best_rgb,support),grid,job.path/f'frame-{index}.png')
            entry.update(state='ready',date=best_item['date'],representative_scene=best_item['id'],valid_pct=round(coverage_pct(valid,support),2),image=f'frame-{index}.png',source_image=f'source-{index}.png',summary='seasonal sample median' if req.mode=='history' else 'single acquisition',scene_count=len(arrays))
            del composite,arrays,best_indices,best_rgb; gc.collect()
        else: entry['reason']='No usable observations in this window; no data were interpolated.'
        observations.append(entry)
        write_json(job.path/'observations.json',observations)
    ready=[o for o in observations if o['state']=='ready']
    if len(ready)<2: raise ValueError('Fewer than two usable periods. Widen the seasonal window or choose another source/area.')
    job.progress('Measuring change on common valid pixels',65)
    first,last=ready[0],ready[-1]
    a=np.load(job.path/f'indices-{first["index"]}.npz')['values']; b=np.load(job.path/f'indices-{last["index"]}.npz')['values']
    limitation=[
        'Exploratory measurements within the selected boundary; not a validated global disaster diagnosis.',
        'Same-season sampling reduces seasonal effects but does not remove phenology, atmospheric or sensor differences.',
        'Water threshold and vegetation change thresholds are development heuristics; boundaries may be affected by registration and mixed pixels.',
        'Displayed optical images are real representative observations. Seasonal measurements may use additional observations listed in evidence; MODIS source products are already temporal composites.',
    ]
    if req.source=='landsat': limitation.append('Landsat instruments differ; no learned cross-sensor harmonization has been applied. Landsat 7 scan-line gaps remain nodata unless another sampled observation covers them.')
    if req.source=='sentinel1':
        common=np.isfinite(a).all(axis=0)&np.isfinite(b).all(axis=0)
        delta=b[0]-a[0]; increase=(delta>=3)&common; decrease=(delta<=-3)&common
        metrics={'common_valid_pct':coverage_pct(common,support),'common_valid_ha':float(common.sum()*grid.resolution**2/10000),'backscatter_increase_ha':float(increase.sum()*grid.resolution**2/10000),'backscatter_decrease_ha':float(decrease.sum()*grid.resolution**2/10000),'mean_vv_change_db':float(np.mean(delta[common])) if common.any() else None}
        masks={'valid':common,'water_gain':decrease,'water_loss':increase,'greening':increase,'browning':decrease,'ground':increase}
        limitation.append('SAR output measures backscatter change, not confirmed water. Matched relative orbit and direction; residual incidence, speckle, layover and vegetation effects remain. SAM optical segmentation is not applied to radar.')
        effective_theme='water'
    else:
        metrics,masks=compare(a,b,grid.resolution,support=support)
        lo,_=compare(a,b,grid.resolution,-.05,support=support); hi,_=compare(a,b,grid.resolution,.05,support=support)
        metrics['water_threshold_sensitivity_net_ha']=[lo['net_water_ha'],hi['net_water_ha']]
        effective_theme=req.theme
    if 'forest' in req.themes: limitation.append('Forest attribution requires a dated tree-cover baseline and persistent loss evidence. Current vegetation measurements do not establish deforestation.')
    if 'ground' in req.themes: limitation.append('Exposed-ground change can include rock, construction and agricultural activity; desertification and soil loss are not established.')
    if 'coast' in req.themes: limitation.append('Waterline evidence is not tide-normalized; no coastal erosion distance or sediment volume is inferred.')
    if req.mode=='event':
        days=(datetime.fromisoformat(last['date'].replace('Z','+00:00'))-datetime.fromisoformat(first['date'].replace('Z','+00:00'))).total_seconds()/86400
        metrics['actual_interval_days']=days
        if metrics.get('net_water_ha') is not None and days>0: metrics['net_water_ha_per_day']=metrics['net_water_ha']/days
    else:
        elapsed=last['year']-first['year']
        if metrics.get('net_water_ha') is not None and elapsed: metrics['net_water_ha_per_year']=metrics['net_water_ha']/elapsed
    forest=None
    if 'forest' in req.themes and req.source!='sentinel1':
        job.progress('Checking dated tree-cover evidence',70)
        try:
            forest,candidate=forest_context(grid,first['year'],last['year'],masks['browning'],job.check,masks['valid'],job.path)
            if candidate is not None:
                metrics['vegetation_decline_in_forest_baseline_ha']=forest['vegetation_decline_within_baseline_ha']
                masks['forest_decline']=candidate
                overlay=np.zeros((*candidate.shape,4),dtype='uint8');overlay[candidate]=[228,139,67,220]
                geographic_image(overlay,grid,job.path/'forest.png')
                limitation.extend(forest['limitations'])
        except (InterruptedError,MemoryError): raise
        except Exception as e: forest={'state':'unavailable','reason':f'Forest reference could not be read ({type(e).__name__}). General vegetation change is still available.'}
    masks['selected']=support
    theme_results={}
    for theme in req.themes:
        image=f'change-{theme}.png'
        geographic_image(change_rgba(masks,'water' if req.source=='sentinel1' else theme),grid,job.path/image)
        theme_results[theme]={'change_image':image}
    geographic_image(change_rgba(masks,effective_theme),grid,job.path/'change.png')
    np.savez_compressed(job.path/'change.npz',**masks)
    annual,history_metrics=annual_history(job.path,ready,grid,req.source,job.check)
    metrics.update(history_metrics);cohort_pct=metrics['history_common_valid_pct']
    trend=None
    if req.mode=='history' and req.source!='sentinel1' and cohort_pct>=80:
        trend=theil_sen([r['year'] for r in annual],[r['water_ha'] for r in annual])
    if trend is not None: metrics['water_trend_ha_per_year']=trend
    sam,sam_traces=run_history(req,observations,grid,job.path,job.check,job.progress)
    traces.extend(sam_traces)
    weather=None
    if req.use_weather:
        job.progress('Adding historical weather context',86)
        try: weather=weather_context(req,job.check)
        except (InterruptedError,MemoryError): raise
        except Exception as e: notes.append(f'Weather context unavailable ({type(e).__name__}); satellite measurements are unaffected.')
    result={'version':'terra-shift-0.3','request':req.model_dump(mode='json'),'grid':{'resolution_m':grid.resolution,'size':grid.size,'crs':grid.crs.to_string(),'transform':list(grid.transform)[:6],'bounds':grid.bounds,'polygon':grid.polygon},'observations':observations,'comparison':{'before_index':first['index'],'after_index':last['index'],'before_label':first['label'],'after_label':last['label']},'metrics':metrics,'annual':annual,'sam':sam,'weather':weather,'limitations':limitation,'notes':list(dict.fromkeys(notes)),'traces':traces,'narrative':None,'quality':'partial' if metrics['common_valid_pct']<80 else 'adequate coverage','change_image':'change.png','method_status':'exploratory; not independently validated','attribution':'Landsat: USGS / NASA. Sentinel: modified Copernicus data. HLS: NASA. MODIS: NASA LP DAAC. Catalog: Microsoft Planetary Computer.'}
    result['theme_results']=theme_results
    result['selection_area_km2']=float(support.sum()*grid.resolution**2/1e6)
    result['forest_reference']=forest
    result['terrain_reference']=None
    if 'ground' in req.themes:
        job.progress('Adding terrain context',90)
        try: result['terrain_reference']=terrain_context(grid,masks['ground'],job.check)
        except (InterruptedError,MemoryError): raise
        except Exception as e: result['terrain_reference']={'state':'unavailable','reason':f'Terrain reference unavailable ({type(e).__name__}).'}
    if req.source=='modis': result['limitations'].append('MODIS frames are 8-day composites. Displayed dates are composite-window starts, not single acquisition dates; different pixels may come from different days.')
    if sam:summarize_sam(result,grid,job.path,job.check)
    result['assessment']=build_assessment(result,a,b,masks,grid,job.path,job.check)
    if req.use_reasoning:
        job.progress('Muse Wonder · interpreting measured evidence',92)
        try:
            explanation,trace=explain(explanation_evidence(result),job.check)
            result['narrative']=explanation; result['traces'].append(trace)
        except ProviderError as e:
            result['notes'].append(str(e));result['traces'].extend(e.traces)
    job.check();result['performance']={'elapsed_seconds':round(time.time()-job.started,2),'sampled_peak_worker_rss_mib':round(job.peak_rss/1024**2,1),'max_concurrent_jobs':1,'grid_pixels':grid.size**2}
    write_json(job.path/'result.json',result)
    write_json(job.path/'status.json',{'state':'complete','stage':'Analysis ready','progress':100,'elapsed_seconds':round(time.time()-job.started)})

def refine(path,index,x,y):
    job=Job(path); result=json.loads((job.path/'result.json').read_text()); req=job.req
    obs=next(o for o in result['observations'] if o['index']==index and o['state']=='ready')
    grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    mask,trace=segment(job.path/obs['source_image'],job.check,point=(x,y))
    raw=np.load(job.path/f'observation-{index}.npz')['values']; mask &= np.isfinite(raw).all(axis=0)
    overlay=np.zeros((*mask.shape,4),dtype='uint8'); overlay[mask]=[157,134,231,190]
    geographic_image(overlay,grid,job.path/f'selected-{index}.png')
    result['selection']={'index':index,'image':f'selected-{index}.png','area_ha':float(mask.sum()*grid.resolution**2/10000),'prompt':'user point','objects':trace['objects']}
    result['traces'].append(trace); job.check(); write_json(job.path/'result.json',result)
    write_json(job.path/'status.json',{'state':'complete','stage':'Object selection ready','progress':100})

if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:
        if len(sys.argv)>2: refine(folder,int(sys.argv[2]),float(sys.argv[3]),float(sys.argv[4]))
        else: run(folder)
    except InterruptedError: pass
    except Exception as e:
        if folder.exists() and not (folder/'cancel').exists():
            safe=str(e) if isinstance(e,(ValueError,MemoryError,ProviderError)) else f'Analysis stopped ({type(e).__name__}). Check provider access and retry.'
            write_json(folder/'status.json',{'state':'failed','stage':safe,'progress':0})
        sys.exit(1)
