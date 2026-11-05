"""Optional direct Copernicus reads, isolated from the fast monitoring loop."""
from . import config
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,logging,math,os,sys,tempfile,time
logging.disable(logging.CRITICAL)

def marine(settings):
    import copernicusmarine
    from .watch_providers import haversine
    now=datetime.now(timezone.utc);lat=settings['latitude'];lon=settings['longitude']
    dataset=os.getenv('CMEMS_WAVE_DATASET','cmems_mod_glo_wav_anfc_0.083deg_PT3H-i')
    ds=copernicusmarine.open_dataset(dataset_id=dataset,username=os.getenv('COPERNICUSMARINE_SERVICE_USERNAME'),password=os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD'),variables=['VHM0'],minimum_latitude=lat,maximum_latitude=lat,minimum_longitude=lon,maximum_longitude=lon,start_datetime=now.date().isoformat(),end_datetime=(now+timedelta(days=7)).date().isoformat(),coordinates_selection_method='nearest',chunk_size_limit=10)
    try:
        assert ds['VHM0'].size<=1000,'Requested marine subset is too large.'
        series=ds['VHM0'].mean(dim=[d for d in ds['VHM0'].dims if d!='time']).load()
        days={}
        for t,v in zip(series.time.values,series.values):
            if math.isfinite(float(v)):days[str(t)[:10]]=max(days.get(str(t)[:10],0),float(v))
        if not days:return {'id':'copernicus_marine_direct','state':'no_data','fetched_at':now.isoformat(),'note':'No valid sea values at this point. Choose a coastal/ocean location; this does not indicate a credential failure.'}
        actual_lat=float(ds.latitude.values.flatten()[0]);actual_lon=float(ds.longitude.values.flatten()[0])
        return {'id':'copernicus_marine_direct','state':'ready','fetched_at':now.isoformat(),'url':'https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_WAV_001_027/description','dataset':dataset,'grid_distance_km':haversine(lat,lon,actual_lat,actual_lon),'data':{'daily':{'time':list(days),'wave_height_max':list(days.values())}},'note':'Direct authenticated Copernicus Marine subset; significant wave height, not local storm-surge or inundation depth.'}
    finally:ds.close()

def ewds(settings):
    from ecmwf.datastores import Client
    from .science import make_grid
    now=datetime.now(timezone.utc);run=now-timedelta(days=1)
    grid=make_grid(settings['longitude'],settings['latitude'],settings['side_km'],max(1000,settings['side_km']*1000/128),settings.get('aoi_polygon'))
    if len(grid.search_boxes)!=1:raise ValueError('Direct EWDS subset currently needs a boundary not crossing the date line.')
    west,south,east,north=grid.search_boxes[0]
    request={'system_version':['operational'],'hydrological_model':['lisflood'],'product_type':['control_forecast'],'variable':'river_discharge_in_the_last_24_hours','year':[str(run.year)],'month':[f'{run.month:02d}'],'day':[f'{run.day:02d}'],'leadtime_hour':[str(24*i) for i in range(1,8)],'data_format':'netcdf','download_format':'unarchived','area':[north,west,south,east]}
    client=Client(url=os.getenv('EWDS_API_URL','https://ewds.climate.copernicus.eu/api'),key=os.environ['EWDS_API_KEY'],timeout=20,maximum_tries=1,retry_after=1,sleep_max=2,progress=False,log_callback=lambda *args,**kwargs:None)
    remote=client.submit('cems-glofas-forecast',request)
    started=time.monotonic()
    while not remote.results_ready:
        if time.monotonic()-started>240:return {'id':'ewds_direct','state':'queued','fetched_at':now.isoformat(),'request_id':remote.request_id,'url':'https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast','note':'EWDS processing remains queued. Use the fast river feed for the current review; the direct store is not time-critical.'}
        time.sleep(4)
    result=client.get_results(remote.request_id)
    if result.content_length>25*1024**2:raise ValueError('EWDS subset exceeds the 25 MiB download budget.')
    with tempfile.TemporaryDirectory(prefix='terra-ewds-') as tmp:
        target=Path(tmp)/'forecast.nc';result.download(str(target))
        import xarray as xr
        with xr.open_dataset(target,engine='h5netcdf') as ds:
            key=next((v for v in ds.data_vars if 'dis' in v.lower()),next(iter(ds.data_vars)))
            data=ds[key]
            if data.size>1_000_000:raise ValueError('EWDS subset exceeds the bounded sample size.')
            lat_name=next((n for n in ('latitude','lat') if n in data.coords),None);lon_name=next((n for n in ('longitude','lon') if n in data.coords),None)
            if lat_name:data=data.sel({lat_name:settings['latitude']},method='nearest')
            if lon_name:data=data.sel({lon_name:settings['longitude']},method='nearest')
            values=[float(v) for v in data.values.flatten() if math.isfinite(float(v))]
            if not values:return {'id':'ewds_direct','state':'no_data','fetched_at':now.isoformat(),'request_id':remote.request_id,'run_date':run.date().isoformat(),'note':'The direct subset returned no valid modeled river-discharge values at the nearest point. Choose a modeled river location; this does not indicate a credential failure.'}
    return {'id':'ewds_direct','state':'ready','fetched_at':now.isoformat(),'request_id':remote.request_id,'url':'https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast','run_date':run.date().isoformat(),'lead_hours':request['leadtime_hour'],'control_discharge_m3s':values,'note':'Direct GloFAS control forecast at the nearest requested river grid point. A control forecast is not an ensemble probability; this is shown separately from the fast-feed recent-percentile rule.'}

if __name__=='__main__':
    operation,request_file,output=sys.argv[1:4]
    try:payload=(marine if operation=='marine' else ewds)(json.loads(Path(request_file).read_text()))
    except Exception as error:payload={'id':'copernicus_marine_direct' if operation=='marine' else 'ewds_direct','state':'unavailable','reason':f'Direct provider access unavailable ({type(error).__name__}). Check credentials, product coverage, and accepted dataset terms.','fetched_at':datetime.now(timezone.utc).isoformat()}
    Path(output).write_text(json.dumps(payload,allow_nan=False))
