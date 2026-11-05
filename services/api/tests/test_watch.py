from datetime import date,timedelta
import json,time
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from services.api.watch_models import WatchArea
from services.api.watch_assessment import assess
from services.api import watch_store as store,watch_engine as engine,meta

TODAY='2026-11-05'

def area(**values):return WatchArea(label='Test watch',latitude=30,longitude=70,**values).model_dump()

def source(name,variable,values,dates=None,distance=0):
    dates=dates or [(date.fromisoformat(TODAY)+timedelta(days=i)).isoformat() for i in range(len(values))]
    return {'id':name,'state':'ready','grid_distance_km':distance,'fetched_at':TODAY+'T00:00:00+00:00','url':'https://example.org/data','data':{'daily':{'time':dates,variable:values}}}

def weather(rain=1,et=4):
    p=source('weather','precipitation_sum',[rain]*7);p['data']['daily']['et0_fao_evapotranspiration']=[et]*7
    return p

def river(future=20,distance=0):
    start=date.fromisoformat(TODAY)-timedelta(days=90)
    dates=[(start+timedelta(days=i)).isoformat() for i in range(97)]
    return source('river','river_discharge',[10]*90+[future]*7,dates,distance)

def test_missing_inputs_remain_unknown():
    result=assess(area(),[],today=TODAY)
    assert result['level']==-1
    assert all(c['level']==-1 for c in result['cards'])
    assert not result['evidence']

def test_forecast_does_not_leak_into_recent_percentile():
    result=assess(area(features=['water']),[weather(),river(1000)],today=TODAY)
    assert result['evidence']['flow_recent_p95']['value']==10
    assert result['evidence']['flow_forecast_peak']['value']==1000
    assert result['level']==3

def test_distant_river_cell_is_not_assessed_as_local_flood():
    result=assess(area(features=['water']),[weather(),river(1000,80)],today=TODAY)
    assert result['level']==-1
    assert 'flow_forecast_peak' not in result['evidence']

def test_partial_week_does_not_create_complete_water_balance():
    p=weather();p['data']['daily']['precipitation_sum']=[1,1]
    result=assess(area(features=['vegetation']),[p],today=TODAY)
    assert 'rain_7d' not in result['evidence'] and 'water_balance_7d' not in result['evidence']
    assert result['level']==-1

def test_weather_pressure_never_predicts_forest_loss():
    result=assess(area(features=['vegetation','forest']),[weather(0,8)],today=TODAY)
    assert result['cards'][0]['level']==2
    assert result['cards'][1]['level']==-1
    assert 'forest_disturbance_ha' not in result['evidence']

def test_stale_satellite_measurements_do_not_trigger_current_forest_level():
    sat={'observed_at':'2026-09-01T00:00:00Z','forest':{'disturbance_ha':100}}
    result=assess(area(features=['forest']),[],sat,today=TODAY)
    assert result['level']==-1
    assert 'forest_disturbance_ha' not in result['evidence']

def test_coast_needs_valid_nearby_sea_data():
    far=source('marine','wave_height_max',[8]*7,distance=200)
    assert assess(area(features=['coast']),[far],today=TODAY)['level']==-1
    near=source('marine','wave_height_max',[8]*7,distance=5)
    assert assess(area(features=['coast']),[near],today=TODAY)['level']==3

def test_stale_forecasts_do_not_support_current_priorities():
    p=river(1000);p['fetched_at']='2026-11-02T00:00:00+00:00'
    result=assess(area(features=['water']),[p],today=TODAY)
    assert result['level']==-1 and result['sources'][0]['state']=='outdated'

def test_empty_forest_baseline_is_not_a_zero_loss_finding():
    sat={'observed_at':TODAY+'T00:00:00Z','forest':{'state':'ready','disturbance_ha':0,'comparable_baseline_ha':0,'reference_coverage_pct':100,'observation_coverage_pct':100}}
    assert assess(area(features=['forest']),[],sat,today=TODAY)['level']==-1

def test_single_sam_acquisition_cannot_establish_change(tmp_path):
    import numpy as np
    from services.api.science import make_grid
    from services.api.segmentation import summarize
    grid=make_grid(0,0,1,100);shape=(grid.size,grid.size)
    np.savez_compressed(tmp_path/'observation-0.npz',values=np.ones((3,*shape)))
    np.savez_compressed(tmp_path/'mask.npz',mask=np.ones(shape,dtype=bool))
    obs={'index':0,'date':TODAY+'T00:00:00Z','state':'ready','label':TODAY}
    result={'request':{'themes':['water']},'observations':[obs],'sam':[{'index':0,'themes':['water'],'concept':'water','state':'ready','mask':'mask.npz'}]}
    summary=summarize(result,grid,tmp_path,lambda:None)['water']
    assert summary['successful']==1 and summary['change'] is None

def test_satellite_daily_cadence_is_bounded():
    assert engine.satellite_due({'satellite':None})
    assert not engine.satellite_due({'satellite':{'checked_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}})

def test_missing_optical_acquisitions_remain_unknown(tmp_path):
    from services.api.science import make_grid
    from services.api.segmentation import summarize
    result={'request':{'themes':['water']},'observations':[],'sam':[]}
    summary=summarize(result,make_grid(0,0,1,100),tmp_path,lambda:None)['water']
    assert summary['change'] is None and summary['successful']==0

def test_watch_limits_and_polygon_validation():
    with pytest.raises(ValidationError):WatchArea(label=' ',latitude=30,longitude=70)
    with pytest.raises(ValidationError):WatchArea(label='Test',latitude=30,longitude=70,features=[])
    with pytest.raises(ValidationError):WatchArea(label='Test',latitude=30,longitude=70,interval_hours=0)
    polygon=[[70,30],[70.1,30],[70.1,30.1],[70,30.1]]
    obj=WatchArea(label='Drawn',latitude=0,longitude=0,aoi_polygon=polygon)
    assert obj.aoi_polygon[0]==obj.aoi_polygon[-1] and 29<obj.latitude<31

def test_store_persists_pause_and_bounds_history(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'RUNTIME',tmp_path)
    identifier=store.create(area());store.set_enabled(identifier,False)
    for i in range(95):store.save_snapshot(identifier,{'created_at':str(i),'level':i%4})
    assert len(store.history(identifier))==90
    assert store.get_area(identifier)['config']['enabled'] is False
    assert store.get_area(identifier)['state']=='paused'
    assert store.remove(identifier)
    assert not store.save_snapshot(identifier,{'level':0})
    assert not store.list_areas() and not store.history(identifier)

def test_derived_brief_does_not_delay_forecast_schedule(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'RUNTIME',tmp_path)
    identifier=store.create(area());store.save_snapshot(identifier,{'level':0})
    before=store.get_area(identifier)['next_due']
    store.save_snapshot(identifier,{'level':0,'brief':{'summary':'Context'}},reschedule=False)
    assert store.get_area(identifier)['next_due']==before

def test_failed_check_has_retry_backoff(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'RUNTIME',tmp_path)
    identifier=store.create(area());store.state(identifier,'failed','Unavailable')
    assert store.get_area(identifier)['next_due']>time.time()+1000

def test_muse_rejects_unrecognized_evidence_and_numbers(monkeypatch):
    calls=[]
    def invalid(payload,check,reservation):
        calls.append(payload)
        return json.dumps({'summary':'There is a 99% disaster risk.','evidence_ids':['invented'],'next_steps':['Act now.']}),{}
    monkeypatch.setattr(meta,'request',invalid)
    with pytest.raises(meta.ProviderError):engine.muse_brief(assess(area(),[weather(),river()],today=TODAY))
    assert len(calls)==2

def test_watch_api_has_no_credential_values_and_preserves_exact_polygon(tmp_path,monkeypatch):
    from services.api.app import app
    from services.api import config
    monkeypatch.setattr(store,'RUNTIME',tmp_path)
    monkeypatch.setattr(config,'JOBS',tmp_path/'jobs')
    monkeypatch.setenv('EARTHDATA_TOKEN','PRIVATE_NASA_VALUE')
    with TestClient(app) as client:
        result=client.get('/api/watch')
        assert result.status_code==200 and 'PRIVATE_NASA_VALUE' not in result.text
        request=area(enabled=False,aoi_polygon=[[70,30],[70.1,30],[70.1,30.1],[70,30.1]])
        created=client.post('/api/watch/areas',json=request)
        assert created.status_code==201
        identifier=created.json()['id']
        geometry=client.post('/api/watch/geometry',json=request).json()
        assert geometry['polygon'][0]==geometry['polygon'][-1]
        assert geometry['area_km2']>0
        assert client.get(f'/api/watch/areas/{identifier}/assets/not-a-file.png').status_code==404
        assert client.get(f'/api/watch/areas/{identifier}/evidence').status_code==200
        assert client.delete(f'/api/watch/areas/{identifier}').status_code==200
        assert client.get(f'/api/watch/areas/{identifier}/history').status_code==404
