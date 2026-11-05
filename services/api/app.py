from . import config
import asyncio
import csv
import io
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from .contracts import AnalysisRequest, RefineRequest
from .science import make_grid, selection_mask
from .meta import cost_total
from .exports import evidence_layers
from .timeline import timeline_observations
from .watch_api import router as watch_router,shutdown as watch_shutdown
from .watch_engine import scheduler as watch_scheduler
from . import watch_engine

jobs={}; lock=asyncio.Lock()

def terminate(job):
    for key in ('process','export_process'):
        proc=job.get(key)
        if proc and proc.poll() is None:
            try: os.killpg(proc.pid,signal.SIGTERM); proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL); proc.wait(timeout=3)
            except ProcessLookupError: pass

def purge(identifier):
    job=jobs.get(identifier)
    if not job: return
    folder=config.JOBS/identifier
    if folder.exists(): (folder/'cancel').touch()
    terminate(job)
    shutil.rmtree(folder,ignore_errors=True)
    jobs.pop(identifier,None)

async def janitor():
    while True:
        await asyncio.sleep(15)
        async with lock:
            now=time.time()
            for identifier,job in list(jobs.items()):
                if now-job['access']>config.IDLE_TTL or now-job['created']>config.HARD_TTL:
                    await asyncio.to_thread(purge,identifier); continue
                proc=job.get('process')
                if proc and proc.poll() is None:
                    try:
                        rss=psutil.Process(proc.pid).memory_info().rss
                        if rss>int(os.getenv('WORKER_RSS_CEILING_MIB','1024'))*1024**2:
                            await asyncio.to_thread(terminate,job)
                            (config.JOBS/identifier/'status.json').write_text(json.dumps({'state':'failed','stage':'Worker memory ceiling reached. Increase cell size or reduce selection.','progress':0}))
                    except psutil.NoSuchProcess: pass

@asynccontextmanager
async def lifespan(app):
    config.JOBS.mkdir(parents=True,exist_ok=True)
    # This app owns only its dedicated temporary jobs directory.
    for path in config.JOBS.iterdir():
        if path.is_dir(): shutil.rmtree(path)
    watch_engine.historical_busy=lambda:any(j['process'].poll() is None or j.get('exporting') for j in jobs.values())
    task=asyncio.create_task(janitor())
    watch_task=asyncio.create_task(watch_scheduler())
    yield
    task.cancel()
    watch_task.cancel()
    await asyncio.gather(watch_task,return_exceptions=True)
    await watch_shutdown()
    for identifier in list(jobs): purge(identifier)

app=FastAPI(title='Terra Shift',lifespan=lifespan)
app.include_router(watch_router)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def local_security(request,call_next):
    # Same-origin application. Never allow arbitrary websites to spend local API credits.
    origin=request.headers.get('origin')
    dev_origins={'http://127.0.0.1:5174','http://localhost:5174','http://127.0.0.1:8018','http://localhost:8018'}
    if origin and origin not in dev_origins and urlparse(origin).netloc!=request.headers.get('host'):
        return JSONResponse({'detail':'Cross-origin requests are not allowed.'},status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    return response

def owner(request,response=None):
    token=request.cookies.get('terra_watch_session')
    if not token and response is not None:
        token=secrets.token_urlsafe(32)
        response.set_cookie('terra_watch_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=config.HARD_TTL)
    return token

def get_job(identifier,request):
    job=jobs.get(identifier)
    if not job or not secrets.compare_digest(job['owner'],owner(request) or ''): raise HTTPException(404,'Analysis expired or was deleted. Run it again to retrieve new imagery.')
    job['access']=time.time()
    return job,config.JOBS/identifier

@app.get('/api/health')
def health():
    return {'status':'ok','model':config.MODEL,'segmentation_model':config.SAM_MODEL,'meta_configured':bool(os.getenv('MODEL_API_KEY')),'cesium_configured':bool(os.getenv('VITE_CESIUM_ION_TOKEN')),'hosting':'local','spent_or_reserved_usd':cost_total(),'budget_usd':config.BUDGET}

@app.get('/api/capabilities')
def capabilities():
    return {'sources':[{'id':k,**v,'status':'implemented; independent validation pending'} for k,v in config.SOURCES.items()],'max_grid_edge':2048,'max_concurrent_jobs':1,'ffmpeg':bool(shutil.which('ffmpeg')),'default_reasoning_model':config.MODEL,'sam_model':config.SAM_MODEL}

@app.get('/api/places')
async def places(q:str):
    if not 2<=len(q)<=160: raise HTTPException(422,'Enter a place name or coordinates.')
    try:
        lat,lon=map(float,q.replace(',',' ').split())
        if not -90<=lat<=90 or not -180<=lon<=180: raise ValueError()
        return [{'label':f'{lat:.4f}, {lon:.4f}','latitude':lat,'longitude':lon}]
    except ValueError: pass
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':q,'count':6,'language':'en','format':'json'})
        if r.status_code!=200: raise HTTPException(502,'Place search is unavailable. Enter latitude, longitude instead.')
        return [{'label':', '.join(filter(None,[p['name'],p.get('admin1'),p.get('country')])),'latitude':p['latitude'],'longitude':p['longitude']} for p in r.json().get('results',[])]

@app.post('/api/estimate')
def estimate(req:AnalysisRequest):
    try: grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    except ValueError as error: raise HTTPException(422,str(error)) from None
    count=req.to_year-req.from_year+1 if req.mode=='history' else 2
    return {'request':req.model_dump(mode='json'),'selection_area_km2':float(selection_mask(grid).sum()*grid.resolution**2/1e6),'periods':count,'pixels_per_period':grid.size**2,'resolution_m':grid.resolution,'polygon':grid.polygon,'bounds':grid.bounds,'message':f'{count} observation windows; up to {req.max_scenes if req.mode=="history" else 1} usable scenes per window. Actual availability is checked during retrieval.'}

@app.get('/api/session')
def session(request:Request,response:Response):
    token=owner(request,response)
    match=next((k for k,j in jobs.items() if j['owner']==token),None)
    return {'job_id':match}

@app.post('/api/jobs')
async def create_job(req:AnalysisRequest,request:Request,response:Response):
    async with lock:
        token=owner(request,response)
        if watch_engine.satellite_area:raise HTTPException(409,'Wait for the Watch satellite inspection to finish.')
        if jobs: raise HTTPException(409,'Delete the current analysis before starting another. The local worker supports one active session.')
        identifier=secrets.token_hex(16); path=config.JOBS/identifier; path.mkdir()
        (path/'request.json').write_text(req.model_dump_json())
        (path/'status.json').write_text(json.dumps({'state':'running','stage':'Preparing analysis','progress':1}))
        proc=subprocess.Popen([sys.executable,'-m','services.api.worker',str(path)],cwd=config.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        jobs[identifier]={'owner':token,'created':time.time(),'access':time.time(),'process':proc}
        return {'id':identifier,'request':req.model_dump(mode='json')}

@app.get('/api/jobs/{identifier}')
def status(identifier:str,request:Request):
    job,path=get_job(identifier,request)
    info=json.loads((path/'status.json').read_text())
    if job['process'].poll() is not None and info['state']=='running': info.update(state='failed',stage='Worker stopped before completion. Retry with a smaller selection.')
    if (path/'result.json').exists(): info['result']=json.loads((path/'result.json').read_text())
    if info['state']=='failed' and not (path/'result.json').exists():
        # Failed computations cannot retain imagery indefinitely. Keep only diagnostic metadata.
        for f in path.iterdir():
            if f.name not in ('status.json','request.json') and f.is_file(): f.unlink(missing_ok=True)
    return info

@app.delete('/api/jobs/{identifier}')
async def delete(identifier:str,request:Request):
    async with lock:
        get_job(identifier,request)
        await asyncio.to_thread(purge,identifier)
    return {'deleted':True}

@app.get('/api/jobs/{identifier}/assets/{name}')
def asset(identifier:str,name:str,request:Request):
    _,path=get_job(identifier,request)
    if Path(name).name!=name or not name.endswith('.png'): raise HTTPException(404)
    target=path/name
    if not target.is_file(): raise HTTPException(404)
    return FileResponse(target,media_type='image/png')

@app.post('/api/jobs/{identifier}/refine')
async def refine(identifier:str,body:RefineRequest,request:Request):
    async with lock:
        job,path=get_job(identifier,request)
        if job['process'].poll() is None or job.get('exporting'): raise HTTPException(409,'Wait for the current operation to finish.')
        if not (path/'result.json').exists(): raise HTTPException(409,'Complete an analysis first.')
        req=AnalysisRequest.model_validate_json((path/'request.json').read_text())
        if req.source=='sentinel1': raise HTTPException(422,'Point segmentation requires optical imagery.')
        (path/'status.json').write_text(json.dumps({'state':'running','stage':'SAM · inspecting selected object','progress':96}))
        proc=subprocess.Popen([sys.executable,'-m','services.api.worker',str(path),str(body.index),str(body.x),str(body.y)],cwd=config.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        job['process']=proc
    return {'started':True}

def make_export(job,path,kind):
    result=json.loads((path/'result.json').read_text())
    if kind=='report':
        output=path/'terra-shift-evidence.zip'
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(path/'result.json','evidence.json')
            z.writestr('selection.geojson',json.dumps({'type':'Feature','properties':{'method':result['method_status']},'geometry':result['grid']['polygon']}))
            csv_file=io.StringIO(); writer=csv.writer(csv_file); writer.writerow(['metric','value'])
            for k,v in result['metrics'].items(): writer.writerow([k,v])
            z.writestr('measurements.csv',csv_file.getvalue())
            timeline_csv=io.StringIO();timeline_writer=csv.writer(timeline_csv)
            timeline_writer.writerow(['frame','requested_period','state','actual_date'])
            for i,obs in enumerate(timeline_observations(result)):
                timeline_writer.writerow([i,obs['label'],obs['state'],obs.get('date','')])
            z.writestr('timeline.csv',timeline_csv.getvalue())
            evidence_layers(path,result,z)
            for p in path.glob('*.png'):
                if not p.name.startswith('source-'): z.write(p,p.name)
        return output
    if not shutil.which('ffmpeg'): raise ValueError('FFmpeg is not installed.')
    frames=path/'export-frames'; frames.mkdir(exist_ok=True)
    # Include a labeled gap frame instead of silently bridging missing years.
    observations=timeline_observations(result)
    for i,obs in enumerate(observations):
        canvas=Image.new('RGB',(960,768),'#07131e')
        if obs['state']=='ready':
            with Image.open(path/obs['image']) as original:
                img=original.convert('RGBA'); img.thumbnail((960,700)); canvas.paste(img,((960-img.width)//2,(700-img.height)//2),img)
        draw=ImageDraw.Draw(canvas)
        draw.text((24,706),f'{obs["label"]}  |  '+(obs.get('date','')[:10] if obs['state']=='ready' else 'No usable observation')+f'  |  {i+1}/{len(observations)}',fill='white',font=ImageFont.load_default(size=24))
        draw.text((24,744),'Terra Shift · Actual observations; no generated intermediate frames. USGS / NASA / Copernicus',fill='#a9bfcd',font=ImageFont.load_default(size=12))
        canvas.save(frames/f'{i:04}.png')
    output=path/f'terra-shift-timeline.{kind}'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','1','-filter_threads','1','-framerate','1','-i',str(frames/'%04d.png')]
    if kind=='mp4': cmd+=['-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-r','24','-movflags','+faststart']
    else: cmd+=['-vf','scale=640:-1:flags=lanczos','-loop','0']
    job['export_process']=subprocess.Popen(cmd+[str(output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        code=job['export_process'].wait(timeout=180)
        if code: raise ValueError('Video encoder did not complete.')
        return output
    finally:
        if job['export_process'].poll() is None: terminate(job)
        shutil.rmtree(frames,ignore_errors=True)

@app.get('/api/jobs/{identifier}/export/{kind}')
async def export(identifier:str,kind:str,request:Request):
    if kind not in ('report','mp4','gif'): raise HTTPException(404)
    async with lock:
        job,path=get_job(identifier,request)
        if job['process'].poll() is None or job.get('exporting'): raise HTTPException(409,'Wait for the active operation to finish.')
        if not (path/'result.json').exists(): raise HTTPException(409,'No completed results to export.')
        job['exporting']=True
    try:
        output=await asyncio.to_thread(make_export,job,path,kind)
        return FileResponse(output,filename=output.name)
    except Exception: raise HTTPException(422,'Export stopped. The analysis may have expired or the encoder is unavailable.') from None
    finally: job['exporting']=False
