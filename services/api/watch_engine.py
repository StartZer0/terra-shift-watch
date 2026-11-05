"""Persistent schedule, bounded providers, and optional evidence-linked Muse briefs."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json,os,re,shutil,signal,subprocess,sys,time,threading
from pathlib import Path
from . import config,watch_store as store
from .watch_providers import weather,river,marine,discover
from .watch_assessment import assess
from .watch_models import Brief

busy=set(); satellite_process=None;satellite_area=None
refresh_lock=asyncio.Lock()
satellite_lock=threading.Lock()

def muse_brief(payload,check=lambda:None):
    from .meta import request,ProviderError
    evidence={'created_at':payload['created_at'],'evidence':payload['evidence'],'cards':[{k:c[k] for k in ('feature','title','level_label','summary','evidence_ids','limitations','recommendation')} for c in payload['cards']]}
    instructions=('Return only JSON with summary (string), evidence_ids (array of exact supplied evidence keys), next_steps (1-5 strings). '
        'Explain this environmental watch assessment for a human. Reference only the supplied evidence. '
        'Use no numerical literals in summary or next_steps; exact values are rendered separately from the evidence. '
        'Do not assign probabilities, confirm disasters, imply official warnings, predict deforestation or desertification, or claim unknown data is safe. '
        'Distinguish forecast conditions from satellite observations. Recommendations must support evidence review and checking local official sources. '
        'Do not change rule levels. Missing evidence and dated-reference limitations matter.')
    for attempt in range(2):
        raw,trace=request({'model':config.MODEL,'reasoning':{'effort':'max'},'max_output_tokens':8192,'instructions':instructions,'input':json.dumps(evidence,allow_nan=False)},check,1)
        try:
            clean=raw.strip();clean=re.sub(r'^```(?:json)?\s*|\s*```$','',clean)
            brief=Brief.model_validate_json(clean)
            assert set(brief.evidence_ids)<=set(payload['evidence'])
            assert not re.search(r'\d',brief.summary+' '.join(brief.next_steps))
            return {**brief.model_dump(),'trace':trace,'validated':True}
        except (ValueError,AssertionError):
            instructions+=' Previous output failed the evidence contract. Use only allowed keys and no numerical literals.'
    raise ProviderError('Muse brief did not pass evidence validation; measured evidence remains available.')

def collect(identifier):
    area=store.get_area(identifier)
    if not area:return
    store.state(identifier,'checking');settings=area['config']
    try:
        functions=[weather,river]+([marine] if 'coast' in settings['features'] else [])
        with ThreadPoolExecutor(max_workers=3) as executor:providers=list(executor.map(lambda f:f(settings),functions))
        providers+=discover(settings)
        current=store.get_area(identifier)
        if not current:return
        payload=assess(settings,providers,current.get('satellite'))
        previous=area.get('latest');payload['escalated']=previous is not None and payload['level']>previous.get('level',-1)
        if settings.get('use_muse') and payload['evidence']:
            try:payload['brief']=muse_brief(payload,lambda:check_exists(identifier))
            except Exception as error:payload['brief']={'state':'unavailable','reason':f'Muse interpretation unavailable ({type(error).__name__}); rule-based evidence is retained.'}
        store.save_snapshot(identifier,payload)
    except Exception as error:
        if store.get_area(identifier):store.state(identifier,'failed',f'Check failed ({type(error).__name__}); no low-risk status was inferred.')

def check_exists(identifier):
    if not store.get_area(identifier):raise InterruptedError('Watch area deleted.')

async def refresh(identifier):
    if identifier in busy:return
    busy.add(identifier)
    try:
        async with refresh_lock:await asyncio.to_thread(collect,identifier)
    finally:busy.discard(identifier)

async def scheduler():
    store.recover()
    while True:
        try:
            due=next((a for a in store.list_areas() if a['config']['enabled'] and a['next_due']<=time.time() and a['id'] not in busy),None) if not busy else None
            if due:await refresh(due['id'])
            elif satellite_process is None and not historical_busy():
                candidate=next((a for a in store.list_areas() if a['config']['enabled'] and a['config'].get('auto_satellite',False) and satellite_due(a)),None)
                if candidate:await asyncio.to_thread(satellite,candidate['id'],True)
        except asyncio.CancelledError:raise
        except Exception:pass
        await asyncio.sleep(15)

historical_busy=lambda:False

def satellite_due(area):
    from datetime import datetime
    checked=(area.get('satellite') or {}).get('checked_at')
    try:return not checked or time.time()-datetime.fromisoformat(checked.replace('Z','+00:00')).timestamp()>=86400
    except ValueError:return True

def satellite(identifier,include_sam):
    if not satellite_lock.acquire(blocking=False):return
    try:_satellite_work(identifier,include_sam)
    finally:satellite_lock.release()

def _satellite_work(identifier,include_sam):
    global satellite_process,satellite_area
    area=store.get_area(identifier)
    if not area:return
    folder=config.RUNTIME/'watch-assets'/identifier
    shutil.rmtree(folder,ignore_errors=True);folder.mkdir(parents=True)
    request=folder/'request.json';request.write_text(json.dumps(area['config']))
    satellite_area=identifier
    satellite_process=subprocess.Popen([sys.executable,'-m','services.api.watch_satellite',str(request),str(folder),'sam' if include_sam else 'no-sam'],cwd=config.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        code=satellite_process.wait(timeout=450)
        if not store.get_area(identifier):return
        summary=folder/'summary.json'
        if summary.exists():store.save_satellite(identifier,json.loads(summary.read_text()))
        else:store.save_satellite(identifier,{'state':'unavailable','notes':['Satellite worker stopped without usable evidence.']})
        # Refresh card interpretation from existing forecasts without downloading them again.
        current=store.get_area(identifier)
        if current and current.get('latest'):
            payload=assess(current['config'],current['latest']['sources'],current.get('satellite'))
            store.save_snapshot(identifier,payload,reschedule=False)
    except subprocess.TimeoutExpired:
        stop_satellite(identifier)
        store.save_satellite(identifier,{'state':'unavailable','notes':['Satellite inspection reached its bounded time limit.']})
    finally:
        request.unlink(missing_ok=True)
        # Remove partial raw derivatives even after cancellation or a failed process.
        for pattern in ('*.npz','source-*.png'):
            for item in folder.glob(pattern):item.unlink(missing_ok=True)
        satellite_process=None;satellite_area=None

def stop_satellite(identifier=None):
    if identifier is not None and satellite_area!=identifier:return
    proc=satellite_process
    if proc and proc.poll() is None:
        try:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        except ProcessLookupError:pass

def expire_assets():
    root=config.RUNTIME/'watch-assets'
    if root.exists():
        for path in root.iterdir():
            if path.is_dir() and path.name!=satellite_area and time.time()-path.stat().st_mtime>86400:shutil.rmtree(path,ignore_errors=True)
