"""Bounded public forecasts and OPERA discovery; secrets never enter response payloads."""
from datetime import datetime,timedelta,timezone
import math
import os
import httpx

CMR='https://cmr.earthdata.nasa.gov/search/granules.json'
COLLECTIONS={'water':'C2617126679-POCLOUD','disturbance':'C2746980408-LPCLOUD'}

def now_iso():return datetime.now(timezone.utc).isoformat()

def haversine(lat,lon,other_lat,other_lon):
    a,b=map(math.radians,(lat,other_lat));dlat=b-a;dlon=math.radians(other_lon-lon)
    return 6371*2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(a)*math.cos(b)*math.sin(dlon/2)**2)))

def source_result(name,url,params,config):
    fetched=now_iso()
    try:
        with httpx.Client(timeout=httpx.Timeout(35,connect=10)) as client:
            r=client.get(url,params=params);r.raise_for_status();data=r.json()
        if data.get('error'):raise ValueError('Provider returned an error.')
        distance=haversine(config['latitude'],config['longitude'],data.get('latitude',config['latitude']),data.get('longitude',config['longitude']))
        return {'id':name,'state':'ready','fetched_at':fetched,'url':url,'grid_distance_km':round(distance,2),'grid_point':{'latitude':data.get('latitude'),'longitude':data.get('longitude')},'data':data}
    except Exception as error:
        return {'id':name,'state':'unavailable','fetched_at':fetched,'url':url,'reason':f'{name} request unavailable ({type(error).__name__}); no risk was inferred from the missing response.'}

def weather(config):
    return source_result('weather','https://api.open-meteo.com/v1/forecast',{'latitude':config['latitude'],'longitude':config['longitude'],'daily':'precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max,wind_gusts_10m_max','hourly':'soil_moisture_0_to_7cm','past_days':7,'forecast_days':7,'timezone':'UTC'},config)

def river(config):
    return source_result('river','https://flood-api.open-meteo.com/v1/flood',{'latitude':config['latitude'],'longitude':config['longitude'],'daily':'river_discharge','past_days':90,'forecast_days':7},config)

def marine(config):
    return source_result('marine','https://marine-api.open-meteo.com/v1/marine',{'latitude':config['latitude'],'longitude':config['longitude'],'daily':'wave_height_max,wave_period_max','hourly':'sea_level_height_msl','past_days':3,'forecast_days':7,'timezone':'UTC','cell_selection':'sea'},config)

def discover(config):
    from .science import make_grid
    grid=make_grid(config['longitude'],config['latitude'],config['side_km'],max(60,config['side_km']*1000/512),config.get('aoi_polygon'))
    end=datetime.now(timezone.utc);start=end-timedelta(days=45);out=[]
    for concept,collection in COLLECTIONS.items():
        entries={}
        try:
            with httpx.Client(timeout=35) as client:
                for box in grid.search_boxes:
                    r=client.get(CMR,params={'collection_concept_id':collection,'bounding_box':','.join(map(str,box)),'temporal':start.isoformat()+','+end.isoformat(),'page_size':8,'sort_key':'-start_date'})
                    r.raise_for_status()
                    for e in r.json().get('feed',{}).get('entry',[]):entries[e['id']]=e
            granules=[]
            for e in sorted(entries.values(),key=lambda x:x.get('time_start',''),reverse=True)[:8]:
                assets={}
                for link in e.get('links',[]):
                    url=link.get('href','')
                    if not url.startswith('https://') or not url.endswith('.tif'):continue
                    for name,suffix in {'water':'_B01_WTR.tif','vegetation':'_VEG-DIST-STATUS.tif','ground':'_GEN-DIST-STATUS.tif'}.items():
                        if url.endswith(suffix):assets[name]=url
                granules.append({'id':e['id'],'title':e.get('title'),'date':e.get('time_start'),'assets':assets})
            out.append({'id':'opera_'+concept,'state':'ready' if granules else 'no_observations','fetched_at':now_iso(),'url':'https://search.earthdata.nasa.gov/search/granules?p='+collection,'granules':granules,'search_window_days':45,'sample_limit':8})
        except Exception as error:
            out.append({'id':'opera_'+concept,'state':'unavailable','fetched_at':now_iso(),'url':CMR,'reason':f'NASA catalog unavailable ({type(error).__name__}).','granules':[]})
    return out

def provider_configuration():
    return [
        {'id':'weather','name':'Weather outlook','configured':True,'detail':'Open-Meteo forecast; 7 days, representative model grid point.'},
        {'id':'river','name':'GloFAS river outlook','configured':True,'detail':'GloFAS via Open-Meteo; discharge forecast, not a local inundation forecast.'},
        {'id':'earthdata','name':'NASA OPERA','configured':bool(os.getenv('EARTHDATA_TOKEN')),'detail':'Public catalog discovery; authenticated water/disturbance raster reads are checked on demand.'},
        {'id':'ewds','name':'Copernicus EWDS','configured':bool(os.getenv('EWDS_API_KEY')),'detail':'Direct forecast retrieval requires the CEMS-FLOODS dataset licence; queued access is not time-critical.'},
        {'id':'copernicus_marine','name':'Copernicus Marine','configured':bool(os.getenv('COPERNICUSMARINE_SERVICE_USERNAME') and os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD')),'detail':'Direct point wave outlook; coastal inundation needs local terrain and protection data.'},
        {'id':'meta','name':'Meta SAM 3.1 + Muse Wonder','configured':bool(os.getenv('MODEL_API_KEY')),'detail':'SAM in satellite comparisons; Muse explains measured Watch evidence on request.'},
    ]
