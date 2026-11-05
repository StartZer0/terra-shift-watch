"""Refresh one active report from its temporary indices, without fetching satellite data."""
import argparse
import json
import re
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from services.api import config
from services.api.worker import Job,write_json
from services.api.science import make_grid
from services.api.assessment import annual_history,build_assessment,explanation_evidence
from services.api.meta import explain,ProviderError
from services.api.references import forest_context
from services.api.segmentation import summarize as summarize_sam


def refresh(identifier,reasoning=True):
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('Invalid active analysis ID.')
    path=config.JOBS/identifier;job=Job(path);job.check();started=time.time()
    result=json.loads((path/'result.json').read_text());req=job.req
    grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    before=np.load(path/f'indices-{result["comparison"]["before_index"]}.npz')['values']
    after=np.load(path/f'indices-{result["comparison"]["after_index"]}.npz')['values']
    with np.load(path/'change.npz') as archive:masks={key:archive[key] for key in archive.files}
    ready=[o for o in result['observations'] if o['state']=='ready']
    if 'forest' in req.themes and req.source!='sentinel1' and not (result.get('forest_reference') or {}).get('annual_loss'):
        try:
            forest,candidate=forest_context(grid,ready[0]['year'],ready[-1]['year'],masks['browning'],job.check,masks['valid'],path)
            result['forest_reference']=forest
            if candidate is not None:
                masks['forest_decline']=candidate
                result['metrics']['vegetation_decline_in_forest_baseline_ha']=forest['vegetation_decline_within_baseline_ha']
                np.savez_compressed(path/'change.npz',**masks)
        except (InterruptedError,MemoryError):raise
        except Exception as error:result['notes'].append(f'Tree-cover reference refresh unavailable ({type(error).__name__}); earlier reference retained.')
    result['annual'],history=annual_history(path,ready,grid,req.source,job.check);result['metrics'].update(history)
    if result.get('sam_summary'):summarize_sam(result,grid,path,job.check)
    result['assessment']=build_assessment(result,before,after,masks,grid,path,job.check)
    if reasoning and req.use_reasoning:
        try:
            result['narrative'],trace=explain(explanation_evidence(result),job.check);result['traces'].append(trace)
        except ProviderError as error:
            result['narrative']=None;result['notes'].append(str(error));result['traces'].extend(error.traces)
    else:result['narrative']=None
    result['version']='terra-shift-0.3' if result.get('sam_summary') else 'terra-shift-0.2'
    result.setdefault('performance',{})['report_refresh_seconds']=round(time.time()-started,2)
    job.check();write_json(path/'result.json',result)
    return {'id':identifier,'period':result['assessment']['temporal']['observed'],'themes':list(result['assessment']['maps']),
        'narrative_valid':bool(result['narrative']),'seconds':result['performance']['report_refresh_seconds']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('identifier');parser.add_argument('--skip-reasoning',action='store_true')
    args=parser.parse_args();print(json.dumps(refresh(args.identifier,not args.skip_reasoning)))
