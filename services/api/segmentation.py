"""SAM measurements on every dated image; guided results retain their provenance."""
import heapq
import numpy as np
from rasterio.features import shapes,sieve,rasterize
from shapely.geometry import shape
from meta_sam_parser import PromptObject,FramePrompt,PromptPoint,PromptBox
from . import meta
from .science import selection_mask,coverage_pct,geographic_image


def concepts(themes):
    groups={}
    for theme in themes:
        concept='water' if theme in ('water','coast') else 'vegetation' if theme in ('vegetation','forest') else 'bare ground'
        groups.setdefault(concept,[]).append(theme)
    return groups


def interior_point(mask):
    current=mask.copy()
    for _ in range(16):
        smaller=np.zeros_like(current)
        smaller[1:-1,1:-1]=current[1:-1,1:-1]&current[:-2,1:-1]&current[2:,1:-1]&current[1:-1,:-2]&current[1:-1,2:]
        if not smaller.any():break
        current=smaller
    rows,cols=np.nonzero(current)
    if not len(rows):return None
    nearest=np.argmin((rows-rows.mean())**2+(cols-cols.mean())**2)
    return int(cols[nearest]),int(rows[nearest])


def guidance(values,concept,valid):
    band=values[1] if concept=='water' else values[0] if concept=='vegetation' else values[2]
    threshold=.2 if concept in ('water','bare ground') else .5
    candidate=(band>threshold)&valid
    if candidate.sum()<16:return [],{'rule':f'{concept}: index > {threshold}','objects':[]}
    clean=sieve(candidate.astype('uint8'),size=16,connectivity=8)
    regions=((shape(geometry).area,geometry) for geometry,value in shapes(clean,mask=clean.astype(bool),connectivity=8) if value==1)
    largest=heapq.nlargest(4,regions,key=lambda region:region[0])
    negative=interior_point(valid&(band<(-.1 if concept=='water' else .1)))
    objects=[];seeds=[];height,width=valid.shape
    for index,(_,geometry) in enumerate(largest,1):
        component=rasterize([(geometry,1)],out_shape=valid.shape).astype(bool)&candidate
        point=interior_point(component)
        if point is None:continue
        bounds=shape(geometry).bounds
        box=PromptBox(max(0,int(bounds[0])-8),max(0,int(bounds[1])-8),min(width,int(bounds[2])+8),min(height,int(bounds[3])+8))
        points=[PromptPoint(*point)]
        if negative is not None:points.append(PromptPoint(*negative,label='negative'))
        objects.append(PromptObject(id=index,prompts=[FramePrompt(frame=0,box=box,points=points)]))
        seeds.append({'id':index,'positive':point,'negative':negative,'box':[box.left,box.top,box.right,box.bottom]})
    return objects,{'rule':f'{concept}: index > {threshold}; components ≥16 pixels; at most four objects; eight-pixel box margin','objects':seeds,'independent_of_spectral':False}


def segment_observation(path,obs,grid,concept,themes,check):
    with np.load(path/f'observation-{obs["index"]}.npz') as archive:values=archive['values']
    valid=np.isfinite(values).all(axis=0)&selection_mask(grid)
    spectral=((values[1]>0) if concept=='water' else (values[0]>.3) if concept=='vegetation' else (values[2]>.1))&valid
    entry={'index':obs['index'],'themes':themes,'concept':concept,'date':obs['date'],'state':'unavailable','area_ha':None,'spectral_iou':None,'objects':0,'attempts':[],'reason':None}
    traces=[];mask=None;mode='concept'
    try:
        mask,trace=meta.segment(path/obs['source_image'],check,concept);traces.append(trace)
        entry['attempts'].append({'mode':'concept','objects':trace['objects'],'request_id':trace.get('request_id'),'output_characters':trace.get('output_characters')})
        if not trace['objects']:
            objects,seed=guidance(values,concept,valid)
            if objects:
                mask,trace=meta.segment(path/obs['source_image'],check,concept,objects=objects);traces.append(trace);mode='spectral-guided'
                entry['guidance']=seed
                entry['attempts'].append({'mode':mode,'objects':trace['objects'],'request_id':trace.get('request_id'),'output_characters':trace.get('output_characters')})
        mask &=valid;entry['objects']=trace['objects'];entry['prompt_mode']=mode;entry['object_details']=trace.get('object_details',[])
        if not trace['objects'] or not mask.any():
            entry['state']='empty';entry['reason']='No usable mask was returned. This is unknown evidence, not proof that the feature is absent.'
            for suffix in ('.png','.npz'):(path/f'sam-{themes[0]}-{obs["index"]}{suffix}').unlink(missing_ok=True)
            return entry,traces
        entry['state']='guided' if mode=='spectral-guided' else 'ready'
        entry['area_ha']=float(mask.sum()*grid.resolution**2/10000)
        union=mask|spectral;entry['spectral_iou']=float((mask&spectral).sum()/union.sum()) if union.any() else None
        name=f'sam-{themes[0]}-{obs["index"]}';entry['image']=name+'.png';entry['mask']=name+'.npz'
        image=np.zeros((*mask.shape,4),dtype='uint8');image[mask]=[157,134,231,185]
        geographic_image(image,grid,path/entry['image']);np.savez_compressed(path/entry['mask'],mask=mask)
        return entry,traces
    except meta.ProviderError as error:
        entry['reason']=str(error);traces.extend(error.traces)
        for suffix in ('.png','.npz'):(path/f'sam-{themes[0]}-{obs["index"]}{suffix}').unlink(missing_ok=True)
        return entry,traces


def summarize(result,grid,path,check):
    selected=selection_mask(grid);common=selected.copy()
    observations=[obs for obs in result['observations'] if obs['state']=='ready']
    for obs in observations:
        check()
        with np.load(path/f'observation-{obs["index"]}.npz') as archive:common &= np.isfinite(archive['values']).all(axis=0)
    summaries={};cell=grid.resolution**2/10000
    for theme in result['request'].get('themes') or [result['request']['theme']]:
        metrics=result.setdefault('metrics',{})
        for key in list(metrics):
            if key.startswith(f'sam_{theme}_'):del metrics[key]
        entries=[entry for entry in result['sam'] if theme in entry.get('themes',[])]
        support=common.copy();scope='fixed common pixels on dated representative images'
        if theme=='forest':
            baseline=path/'forest-baseline.npz'
            if baseline.exists():
                with np.load(baseline) as archive:support &=archive['baseline']
                scope='dated tree-cover baseline on fixed common pixels'
            else:support[:]=False;scope='no dated tree-cover mask available'
        points=[];usable={}
        for obs in observations:
            entry=next((entry for entry in entries if entry['index']==obs['index']),None);value=None
            if entry and entry['state'] in ('ready','guided') and support.any():
                with np.load(path/entry['mask']) as archive:mask=archive['mask']&support
                value=float(mask.sum()*cell);usable[obs['index']]=entry
            points.append({'index':obs['index'],'label':obs['label'],'value':value})
        summary={'concept':entries[0]['concept'] if entries else None,'successful':len(usable),'attempted':len(entries),'guided':sum(entry['state']=='guided' for entry in entries),'empty':sum(entry['state']=='empty' for entry in entries),'failed':sum(entry['state']=='unavailable' for entry in entries),'common_valid_pct':coverage_pct(common,selected),'scope':scope,'support_ha':float(support.sum()*cell),'points':points,'periods':len(result['observations']),'change':None,
            'note':'SAM areas use one actual source image per period, not seasonal medians. Guided labels are spectral hypotheses; recovery targets at most four regions and may miss other objects. This is not independent validation. Missing masks remain gaps; model confidence is not calibrated accuracy.'}
        first,last=(observations[0],observations[-1]) if observations else (None,None)
        if len(observations)>1 and first['date']!=last['date'] and first['index'] in usable and last['index'] in usable:
            with np.load(path/usable[first['index']]['mask']) as archive:before=archive['mask']&support
            with np.load(path/usable[last['index']]['mask']) as archive:after=archive['mask']&support
            gain=after&~before;loss=before&~after
            summary['change']={'before_ha':float(before.sum()*cell),'after_ha':float(after.sum()*cell),'gain_ha':float(gain.sum()*cell),'loss_ha':float(loss.sum()*cell),'net_ha':float((after.sum()-before.sum())*cell),'image':f'sam-change-{theme}.png'}
            image=np.zeros((*support.shape,4),dtype='uint8');image[gain]=[41,166,212,225];image[loss]=[228,139,67,225]
            yy,xx=np.indices(support.shape);missing=selected&~common
            image[missing]=[54,68,77,150];image[missing&((xx+yy)%12<3)]=[170,181,190,180]
            geographic_image(image,grid,path/summary['change']['image'])
        else:(path/f'sam-change-{theme}.png').unlink(missing_ok=True)
        summaries[theme]=summary
        for key in ('successful','attempted','guided','empty','failed','common_valid_pct'):metrics[f'sam_{theme}_{key}']=summary[key]
        if summary['change']:
            for key,value in summary['change'].items():
                if key!='image':metrics[f'sam_{theme}_{key}']=value
    result['sam_summary']=summaries
    return summaries


def run_history(req,observations,grid,path,check,progress=lambda stage,pct:None):
    entries=[];traces=[];ready=[obs for obs in observations if obs['state']=='ready'];groups=concepts(req.themes)
    if not req.use_sam or req.source=='sentinel1':return entries,traces
    total=len(ready)*len(groups);done=0
    for concept,themes in groups.items():
        for obs in ready:
            check();progress(f'SAM 3.1 · {concept} · {obs["label"]} ({done+1}/{total})',72+13*done/max(total,1))
            entry,attempts=segment_observation(path,obs,grid,concept,themes,check);entries.append(entry);traces.extend(attempts);done+=1
    return entries,traces
