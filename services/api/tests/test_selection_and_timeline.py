import json
import numpy as np
import pytest
from pydantic import ValidationError
from services.api.contracts import AnalysisRequest
from services.api.science import make_grid, selection_mask, compare, display_preview, change_rgba
from services.api.timeline import timeline_observations


def test_polygon_excludes_pixels_and_uses_selected_area_for_coverage():
    req=AnalysisRequest(longitude=0,latitude=0,aoi_polygon=[[0,0],[.06,0],[0,.06]],themes=['water','vegetation','ground'])
    grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    support=selection_mask(grid)
    assert 0<support.sum()<grid.size**2
    before=np.zeros((3,grid.size,grid.size),dtype='float32');after=before.copy()
    before[1]=-.5;after[1]=.5
    metrics,masks=compare(before,after,grid.resolution,support=support)
    assert metrics['common_valid_pct']==100
    assert metrics['water_gain_ha']==pytest.approx(support.sum()*grid.resolution**2/10000)
    assert not masks['water_gain'][~support].any()
    masks['selected']=support
    assert not change_rgba(masks,'water')[~support].any()
    rgba=np.ones((*support.shape,4),dtype='uint8')*255
    assert not display_preview(rgba,support)[~support].any()


def test_polygon_validation_and_idempotent_normalization():
    with pytest.raises(ValidationError):
        AnalysisRequest(longitude=0,latitude=0,aoi_polygon=[[0,0],[.02,.02],[0,.02],[.02,0]])
    with pytest.raises(ValidationError):
        AnalysisRequest(longitude=0,latitude=0,themes=[])
    req=AnalysisRequest(longitude=0,latitude=0,aoi_polygon=[[179.98,.01],[-179.98,.01],[180,.04]],themes=['water','coast','water'])
    assert req.themes==['water','coast']
    restored=AnalysisRequest.model_validate_json(req.model_dump_json())
    assert restored.side_km==pytest.approx(req.side_km)
    grid=make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon)
    assert len(grid.search_boxes)==2


def test_legacy_theme_and_all_theme_selection():
    assert AnalysisRequest(longitude=0,latitude=0,theme='ground').themes==['ground']
    assert len(AnalysisRequest(longitude=0,latitude=0,themes=['water','vegetation','forest','ground','coast']).themes)==5


def test_timeline_keeps_every_requested_year_and_explicit_gap():
    result={'request':{'mode':'history','from_year':2000,'to_year':2020},'observations':[
        {'index':20,'label':'2020','state':'ready'}, {'index':0,'label':'2000','state':'ready'}]}
    plan=timeline_observations(result)
    assert [o['label'] for o in plan]==[str(year) for year in range(2000,2021)]
    assert len(plan)==21 and plan[1]['state']=='missing'
    assert plan[0]['state']==plan[-1]['state']=='ready'


def test_multi_theme_worker_shares_scene_reads_and_writes_each_layer(tmp_path,monkeypatch):
    from services.api import worker
    req=AnalysisRequest(longitude=0,latitude=0,side_km=1,from_year=2020,to_year=2022,
        themes=['water','vegetation','forest','ground','coast'],aoi_polygon=[[0,0],[.004,0],[0,.004]],use_sam=True,use_reasoning=False,use_weather=False,max_scenes=1)
    (tmp_path/'request.json').write_text(req.model_dump_json())
    reads=[];segments=[]
    def search(request,grid,start,end):
        return [{'id':str(start.year),'properties':{'datetime':f'{start.year}-07-01T00:00:00Z','platform':'test-only'}}]
    def scene(item,source,grid,check):
        reads.append(item['id']);check()
        bands={k:np.full((grid.size,grid.size),v,dtype='float32') for k,v in {'red':.1,'blue':.1,'green':.3,'nir':.5,'swir':.1}.items()}
        return bands,np.ones((grid.size,grid.size),dtype=bool),{}
    monkeypatch.setattr(worker,'search',search);monkeypatch.setattr(worker,'read_scene',scene)
    monkeypatch.setattr(worker,'terrain_context',lambda *args:{'state':'unavailable','reason':'test-only'})
    def forest(grid,*args):
        return {'state':'ready','vegetation_decline_within_baseline_ha':0,'limitations':[]},np.zeros((grid.size,grid.size),dtype=bool)
    def segment(path,check,concept):
        from PIL import Image
        segments.append(concept)
        with Image.open(path) as image:mask=np.ones((image.height,image.width),dtype=bool)
        return mask,{'objects':1,'model':'test-only','request_id':'test-only','estimated_usd':0,'seconds':0}
    monkeypatch.setattr(worker,'forest_context',forest);monkeypatch.setattr('services.api.segmentation.meta.segment',segment)
    worker.run(tmp_path)
    result=json.loads((tmp_path/'result.json').read_text())
    assert reads==['2020','2021','2022']
    assert set(result['theme_results'])=={'water','vegetation','forest','ground','coast'}
    assert segments==['water']*3+['vegetation']*3+['bare ground']*3
    support=selection_mask(make_grid(req.longitude,req.latitude,req.side_km,req.resolution,req.aoi_polygon))
    with np.load(tmp_path/'indices-0.npz') as data:assert np.isnan(data['values'][:,~support]).all()
    assert all(item['area_ha']==pytest.approx(result['selection_area_km2']*100) for item in result['sam'])
    assert all((tmp_path/v['change_image']).is_file() for v in result['theme_results'].values())
