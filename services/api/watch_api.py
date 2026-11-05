import asyncio,json,shutil,time,subprocess,sys,tempfile,os
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse,Response
from . import config,watch_store as store,watch_engine as engine
from .watch_models import WatchArea,WatchSwitch,SatelliteOptions
from .watch_providers import provider_configuration
from .science import make_grid,selection_mask

router=APIRouter(prefix='/api/watch',tags=['Watch'])
tasks=set();satellite_task=None;direct_task=None;direct_process=None;direct_area=None

def launch(coroutine):
    task=asyncio.create_task(coroutine);tasks.add(task);task.add_done_callback(tasks.discard);return task

def require(identifier):
    area=store.get_area(identifier)
    if not area:raise HTTPException(404,'Watch area not found.')
    return area

@router.post('/geometry')
def geometry(body:WatchArea):
    grid=make_grid(body.longitude,body.latitude,body.side_km,max(60,body.side_km*1000/512),body.aoi_polygon)
    return {'polygon':grid.polygon['coordinates'][0],'area_km2':float(selection_mask(grid).sum()*grid.resolution**2/1e6),'longitude':body.longitude,'latitude':body.latitude,'side_km':body.side_km}

@router.get('')
def overview():
    engine.expire_assets()
    return {'areas':store.list_areas(),'providers':provider_configuration(),'scheduler':'Checks run while the local backend is running. Overdue enabled areas resume after restart.','max_areas':int(os.getenv('WATCH_MAX_AREAS','12')),'satellite_busy':engine.satellite_area,'checking':list(engine.busy)}

@router.post('/areas',status_code=201)
def create(body:WatchArea):
    try:identifier=store.create(body.model_dump())
    except ValueError as error:raise HTTPException(409,str(error)) from None
    return require(identifier)

@router.post('/areas/{identifier}/refresh',status_code=202)
async def refresh(identifier:str):
    require(identifier)
    if identifier in engine.busy:raise HTTPException(409,'This area is already being checked.')
    # Only one refresh is admitted at a time; no unbounded cross-provider workload.
    if engine.busy:raise HTTPException(409,'Another area is being checked. Retry after it completes.')
    launch(engine.refresh(identifier));return {'queued':True}

@router.patch('/areas/{identifier}')
def toggle(identifier:str,body:WatchSwitch):
    require(identifier);store.set_enabled(identifier,body.enabled,body.auto_satellite);return require(identifier)

@router.delete('/areas/{identifier}')
async def remove(identifier:str):
    require(identifier);await asyncio.to_thread(engine.stop_satellite,identifier)
    if direct_area==identifier and direct_process and direct_process.poll() is None:
        direct_process.kill();await asyncio.to_thread(direct_process.wait,5)
    store.remove(identifier)
    shutil.rmtree(config.RUNTIME/'watch-assets'/identifier,ignore_errors=True)
    return {'deleted':True}

@router.get('/areas/{identifier}/history')
def history(identifier:str):require(identifier);return store.history(identifier)

@router.get('/areas/{identifier}/evidence')
def evidence(identifier:str):
    area=require(identifier)
    payload={'application':'Terra Shift Watch','area':area,'history':store.history(identifier),'interpretation':'Review priorities are heuristic, not official warnings or calibrated disaster probabilities.'}
    return Response(json.dumps(payload,indent=2,allow_nan=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="terra-shift-watch-evidence.json"'})

@router.post('/areas/{identifier}/direct/{provider}',status_code=202)
async def direct(identifier:str,provider:str):
    global direct_task
    area=require(identifier)
    if provider not in ('marine','ewds'):raise HTTPException(404)
    if direct_task is not None and not direct_task.done():raise HTTPException(409,'Another direct provider read is running.')
    store.save_direct(identifier,provider,{'state':'running'})
    def work():
        global direct_process,direct_area
        try:
            with tempfile.TemporaryDirectory(prefix='terra-watch-direct-') as tmp:
                request=Path(tmp)/'request.json';output=Path(tmp)/'result.json';request.write_text(json.dumps(area['config']))
                direct_area=identifier
                direct_process=subprocess.Popen([sys.executable,'-m','services.api.watch_direct',provider,str(request),str(output)],cwd=config.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:direct_process.wait(timeout=300 if provider=='ewds' else 100)
                except subprocess.TimeoutExpired:direct_process.kill();direct_process.wait(timeout=5)
                result=json.loads(output.read_text()) if output.exists() else {'state':'unavailable','reason':'Direct read exceeded its time budget. Fast forecast evidence remains available.'}
                store.save_direct(identifier,provider,result)
        finally:direct_process=None;direct_area=None
    direct_task=launch(asyncio.to_thread(work));return {'queued':True}

@router.post('/areas/{identifier}/explain',status_code=202)
async def explain(identifier:str):
    area=require(identifier)
    if not area.get('latest') or not area['latest'].get('evidence'):raise HTTPException(409,'Complete a check with usable evidence first.')
    if identifier in engine.busy:raise HTTPException(409,'Wait for the active check.')
    async def work():
        engine.busy.add(identifier)
        try:
            brief=await asyncio.to_thread(engine.muse_brief,area['latest'],lambda:engine.check_exists(identifier))
            # Do not overwrite a newer forecast with an older brief.
            current=store.get_area(identifier)
            if current and current.get('latest',{}).get('created_at')==area['latest']['created_at']:
                payload=area['latest'];payload['brief']=brief;store.save_snapshot(identifier,payload,reschedule=False)
        except Exception:
            current=store.get_area(identifier)
            if current and current.get('latest',{}).get('created_at')==area['latest']['created_at']:
                payload=area['latest'];payload['brief']={'state':'unavailable','reason':'Muse explanation did not complete; measured findings remain available.'};store.save_snapshot(identifier,payload,reschedule=False)
        finally:engine.busy.discard(identifier)
    launch(work());return {'queued':True}

@router.post('/areas/{identifier}/satellite',status_code=202)
async def satellite(identifier:str,body:SatelliteOptions):
    global satellite_task
    require(identifier)
    if engine.satellite_process is not None or satellite_task is not None and not satellite_task.done():raise HTTPException(409,'A satellite inspection is already running.')
    if engine.historical_busy():raise HTTPException(409,'Wait for the historical raster operation to finish.')
    # The satellite subprocess has its own bounded time, grid, and memory budget.
    satellite_task=launch(asyncio.to_thread(engine.satellite,identifier,body.include_sam))
    return {'queued':True,'note':'Reads recent NASA products and, if selected, actual optical imagery for SAM. Temporary previews expire after one day.'}

@router.get('/areas/{identifier}/assets/{name}')
def asset(identifier:str,name:str):
    require(identifier)
    if Path(name).name!=name or not name.endswith('.png'):raise HTTPException(404)
    path=config.RUNTIME/'watch-assets'/identifier/name
    if not path.is_file() or time.time()-path.stat().st_mtime>86400:raise HTTPException(404,'Preview expired; inspect fresh imagery.')
    return FileResponse(path,media_type='image/png')

async def shutdown():
    await asyncio.to_thread(engine.stop_satellite)
    if direct_process and direct_process.poll() is None:direct_process.kill()
    for task in list(tasks):task.cancel()
    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
