import json
import numpy as np
import pytest
from PIL import Image
from services.api.assessment import extent_level,period_context,build_assessment,explanation_evidence,annual_history,rainfall_context
from services.api.science import make_grid,compare
from services.api.meta import validate_explanation


def test_verified_years_allowed_but_unmeasured_amounts_stay_blocked():
    data={'summary':'Between 2000 and 2020, water extent decreased.','observations':[{'text':'Water loss exceeded gain.','metric_keys':['water_loss_ha']}],'limitations':[]}
    assert validate_explanation(json.dumps(data),{'water_loss_ha'},['2000','2020'])==data
    for summary in ['Between 2000 and 2030, water decreased.','Water lost 20%.','Water decreased by 2000 ha.']:
        with pytest.raises(ValueError):validate_explanation(json.dumps({**data,'summary':summary}),{'water_loss_ha'},['2000','2020'])


def test_descriptive_extent_cutoffs_and_unknown_are_explicit():
    assert [extent_level(v) for v in [None,0,4.9,5,19.9,20,49.9,50]]==['Not assessable','None detected','Localized','Distributed','Distributed','Widespread','Widespread','Extensive']


def test_persistence_map_and_selected_theme_evidence(tmp_path):
    grid=make_grid(0,0,1,100);shape=(grid.size,grid.size)
    before=np.zeros((3,*shape),dtype='float32');before[1]=-.5;before[1,:,:5]=.5
    after=before.copy();after[1,:,2:5]=-.5
    metrics,masks=compare(before,after,grid.resolution)
    observations=[{'index':y-2000,'year':y,'label':str(y),'state':'ready' if y in (2000,2018,2019,2020) else 'missing','date':f'{y}-07-01T00:00:00Z'} for y in range(2000,2021)]
    for obs in observations:
        if obs['state']!='ready':continue
        values=after.copy() if obs['year']!=2000 else before.copy()
        if obs['year']==2018:values[1,:,3:5]=.5
        if obs['year']==2019:values[1,:,4]=.5
        np.savez_compressed(tmp_path/f'indices-{obs["index"]}.npz',values=values)
    result={'request':{'mode':'history','from_year':2000,'to_year':2020,'start_month':6,'end_month':8,'source':'landsat','theme':'water','themes':['water']},'observations':observations,'metrics':metrics,'sam':[],'quality':'adequate coverage','annual':[{'year':2000,'index':0,'label':'2000','water_ha':50,'ndvi':.3}],'limitations':[]}
    assessment=build_assessment(result,before,after,masks,grid,tmp_path,lambda:None)
    result['assessment']=assessment
    assert assessment['temporal']['observed']=='2000–2020'
    assert assessment['temporal']['span_years']==20
    assert assessment['cards'][0]['extent_pct']==pytest.approx(30)
    assert assessment['cards'][0]['extent_label']=='Widespread'
    assert result['metrics']['persistent_recent_water_loss_ha']==pytest.approx(10)
    with Image.open(tmp_path/'impact-water.png') as image:
        pixels=np.asarray(image)
        for color in [(253,201,158),(232,115,49),(164,35,31)]:assert np.all(pixels[:,:,:3]==color,axis=2).any()
    evidence=explanation_evidence(result)
    assert 'greening_ha' not in evidence['metrics'] and 'ndvi' not in evidence['annual'][0]
    assert len(evidence['annual'])==1 and evidence['time_context']['first_year']==2000
    observations[19]['state']='missing'
    assert 'water' not in build_assessment(result,before,after,masks,grid,tmp_path,lambda:None)['maps']
    result['request']['themes']=['forest'];result['forest_reference']={'mapped_baseline_ha':0}
    result['metrics']['vegetation_decline_in_forest_baseline_ha']=0
    masks['forest_decline']=np.zeros(shape,dtype=bool)
    unknown=build_assessment(result,before,after,masks,grid,tmp_path,lambda:None)
    assert unknown['cards'][0]['value']=='—' and unknown['cards'][0]['extent_label']=='Not assessable'
    assert 'forest' not in unknown['maps']


def test_land_history_excludes_water_to_land_conversion(tmp_path):
    grid=make_grid(0,0,1,100);a=np.zeros((3,grid.size,grid.size),dtype='float32');a[0]=.4;a[1]=-.5;a[1,:,0]=.5
    b=a.copy();b[1,:,0]=-.5;b[0,:,0]=.9
    np.savez_compressed(tmp_path/'indices-0.npz',values=a);np.savez_compressed(tmp_path/'indices-1.npz',values=b)
    ready=[{'index':0,'label':'2000','year':2000},{'index':1,'label':'2020','year':2020}]
    rows,metrics=annual_history(tmp_path,ready,grid,'landsat',lambda:None)
    assert rows[0]['ndvi']==pytest.approx(rows[1]['ndvi'])
    assert metrics['history_land_valid_pct']==90


def test_rainfall_is_percentage_context_without_invented_drought_category():
    context=rainfall_context({'annual':[{'year':2020,'precipitation_mm':50,'precipitation_anomaly_mm':-50,'temperature_anomaly_c':1}], 'baseline':'1991–2020'})
    assert context['annual'][0]['precipitation_anomaly_pct']==-50
    assert 'not a validated drought-severity' in context['note']


def test_each_selected_feature_has_its_own_metrics_chart_and_scope():
    from services.api.assessment import feature_findings
    result={'request':{'mode':'history','from_year':2000,'to_year':2002,'start_month':6,'end_month':8},
        'observations':[{'index':i,'year':2000+i,'label':str(2000+i),'state':'ready','date':f'{2000+i}-07-01'} for i in range(3)],
        'metrics':{'net_water_ha':-20,'before_water_ha':50,'after_water_ha':30,'water_gain_ha':0,'water_loss_ha':20,'greening_ha':3,'browning_ha':2,'mean_ndvi_change':.025,'history_common_valid_pct':90,'history_land_valid_pct':70,'exposed_ground_increase_ha':4},
        'annual':[{'index':i,'year':2000+i,'label':str(2000+i),'water_ha':50-10*i,'ndvi':.3+i*.01,'bsi':.1+i*.02} for i in range(3)],
        'forest_reference':{'state':'ready','mapped_baseline_ha':10,'comparable_baseline_ha':8,'mapped_loss_pixels_ha':3,'reference_coverage_pct':80,'annual_loss':[{'year':2000,'loss_ha':0},{'year':2001,'loss_ha':1},{'year':2002,'loss_ha':2}]}}
    result['request']['source']='landsat'
    cards=[{'theme':theme,'detail':f'{theme} only'} for theme in ('water','coast','forest','vegetation','ground')]
    findings=feature_findings(result,cards)
    assert len({f['explanation'] for f in findings.values()})==5
    assert len({f['chart']['title'] for f in findings.values()})==5
    assert [p['value'] for p in findings['water']['chart']['points']]==[50,40,30]
    assert [p['value'] for p in findings['coast']['chart']['points']]==[0,10,20]
    assert [p['value'] for p in findings['forest']['chart']['points']]==[0,1,3]
    assert findings['forest']['metrics'][0]['label']=='Dated tree-cover baseline'
    assert 'land-to-water' not in findings['forest']['explanation'] and 'water area' not in findings['forest']['chart']['title'].lower()
    assert findings['vegetation']['metrics'][2]['value']=='+0.025'
    del result['forest_reference']['annual_loss']
    assert feature_findings(result,cards)['forest']['chart']['type']=='bars'
