import numpy as np
import pytest
from pydantic import ValidationError
from services.api.contracts import AnalysisRequest
from services.api.science import make_grid,compare,qa_mask,ratio,theil_sen

def test_water_accounting_and_common_support():
    before=np.zeros((3,2,3),dtype='float32'); after=before.copy()
    before[1]=[[.5,-.5,.5],[-.5,.5,-.5]]
    after[1]=[[-.5,.5,.5],[-.5,.5,.5]]
    after[:,1,2]=np.nan  # unknown must not be counted as gain
    m,_=compare(before,after,100)
    assert m['water_gain_ha']==1
    assert m['water_loss_ha']==1
    assert m['net_water_ha']==0
    assert m['before_water_ha']==m['after_water_ha']==3
    assert m['common_valid_ha']==5

def test_zero_baseline_and_identical_observations():
    a=np.zeros((3,3,3),dtype='float32');a[1]=-.5
    m,_=compare(a,a,30)
    assert m['relative_water_pct'] is None
    assert m['water_gain_ha']==m['water_loss_ha']==m['greening_ha']==m['browning_ha']==0

def test_quality_cloud_shadow_snow_saturation():
    q=np.array([0,1,2,4,8,16,32,64,128],dtype='uint16')
    assert qa_mask('landsat',q).tolist()==[True,False,False,False,False,False,False,True,True]
    assert not qa_mask('landsat',np.array([0]),np.array([1]))[0]
    assert qa_mask('sentinel2',np.arange(12)).tolist()==[False,False,False,False,True,True,True,False,False,False,False,False]

def test_ratio_invalid_denominator():
    result=ratio(np.array([.4,0,np.nan]),np.array([.1,0,.3]))
    assert result[0]==pytest.approx(.6)
    assert np.isnan(result[1:]).all()

def test_square_area_and_dateline():
    grid=make_grid(179.99,0,20,30)
    assert len(grid.search_boxes)==2
    assert grid.resolution**2*grid.size**2==pytest.approx(400_000_000)
    assert grid.search_boxes[0][0]<180 and grid.search_boxes[1][2]>-180

def test_date_source_and_resource_contracts():
    with pytest.raises(ValidationError): AnalysisRequest(longitude=0,latitude=0,source='sentinel2',from_year=2000)
    with pytest.raises(ValidationError): AnalysisRequest(longitude=0,latitude=0,side_km=100,resolution=30)
    with pytest.raises(ValidationError): AnalysisRequest(longitude=0,latitude=0,mode='event',before_date='2020-01-01',after_date='2020-01-10')
    req=AnalysisRequest(longitude=0,latitude=0,from_year=2000,to_year=2020)
    from services.api.catalog import windows
    assert len(windows(req))==21

def test_trend_requires_five_observations():
    assert theil_sen([2000,2001],[5,6]) is None
    assert theil_sen([2000,2001,2002,2003,2004],[5,7,9,11,13])==2

def test_pole_containing_selection_searches_all_longitudes():
    grid=make_grid(15,89,300,500)
    assert grid.search_boxes[0][0]==-180
    assert grid.search_boxes[0][2]==180
    assert grid.search_boxes[0][3]==90

def test_missing_display_pixels_are_explicit():
    from services.api.science import display_preview
    source=np.array([[[1,2,3,255],[8,9,10,0]]],dtype='uint8')
    view=display_preview(source)
    assert view[0,0].tolist()==[1,2,3,255]
    assert view[0,1,3]==255
    assert source[0,1,3]==0  # never modify the model's source input

def test_no_overlap_is_unknown_not_zero_change():
    a=np.zeros((3,2,2),dtype='float32');b=a.copy();a[:,:,0]=np.nan;b[:,:,1]=np.nan
    metrics,_=compare(a,b,30)
    assert metrics['common_valid_pct']==0
    assert metrics['net_water_ha'] is None
    assert metrics['before_water_ha'] is None
