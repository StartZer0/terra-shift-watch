"""Re-run SAM on an active run's temporary imagery; never refetch satellite history."""
import sys,json,re,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from services.api import config
from services.api.worker import Job,write_json
from services.api.science import make_grid
from services.api.segmentation import run_history,summarize
from services.api.references import forest_context
from services.api.assessment import build_assessment,explanation_evidence
from services.api.meta import explain,ProviderError


def refresh(identifier):
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('Invalid active analysis ID.')
    path=config.JOBS/identifier;job=Job(path);job.check();start=time.time()
    result=json.loads((path/'result.json').read_text());req=job.req
    grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    ready=[o for o in result['observations'] if o['state']=='ready']
    with np.load(path/'change.npz') as archive:masks={key:archive[key] for key in archive.files}
    if 'forest' in req.themes and not (path/'forest-baseline.npz').exists():
        forest,candidate=forest_context(grid,ready[0]['year'],ready[-1]['year'],masks['browning'],job.check,masks['valid'],path)
        result['forest_reference']=forest
    result['sam'],traces=run_history(req,result['observations'],grid,path,job.check,lambda stage,pct:print(stage,flush=True))
    result['traces'].extend(traces);summarize(result,grid,path,job.check)
    with np.load(path/f'indices-{ready[0]["index"]}.npz') as archive:before=archive['values']
    with np.load(path/f'indices-{ready[-1]["index"]}.npz') as archive:after=archive['values']
    result['assessment']=build_assessment(result,before,after,masks,grid,path,job.check)
    if req.use_reasoning:
        try:
            result['narrative'],trace=explain(explanation_evidence(result),job.check);result['traces'].append(trace)
        except ProviderError as error:
            result['narrative']=None;result['notes'].append(str(error));result['traces'].extend(error.traces)
    result['version']='terra-shift-0.3';result['performance']['sam_refresh_seconds']=round(time.time()-start,2)
    job.check();write_json(path/'result.json',result)
    print(json.dumps({'seconds':result['performance']['sam_refresh_seconds'],'themes':{k:{key:v[key] for key in ('successful','attempted','guided','empty','failed','change')} for k,v in result['sam_summary'].items()},'narrative_valid':bool(result['narrative'])}),flush=True)

if __name__=='__main__':refresh(sys.argv[1])
