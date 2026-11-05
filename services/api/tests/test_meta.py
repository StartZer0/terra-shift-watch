import json
import pytest
from PIL import Image
from services.api import meta


def test_narrative_rejects_unmeasured_numbers_and_unknown_metrics():
    valid={'summary':'Water declined within the selected square.','observations':[{'text':'Measured retreat exceeds gain.','metric_keys':['water_loss_ha']}],'limitations':['This does not establish cause.']}
    assert meta.validate_explanation(json.dumps(valid),{'water_loss_ha'})==valid
    invalid={**valid,'summary':'There was a 98% accurate flood detection.'}
    with pytest.raises(ValueError):meta.validate_explanation(json.dumps(invalid),{'water_loss_ha'})
    with pytest.raises(ValueError):meta.validate_explanation(json.dumps(valid),{'invented_metric'})


def test_invalid_narrative_retries_once_and_preserves_cost(monkeypatch):
    outputs=iter(['{"summary":"invalid"}',json.dumps({'summary':'Water declined.','observations':[{'text':'Retreat was observed.','metric_keys':['loss']}],'limitations':[]})])
    calls=[]
    def request(payload,check,reservation):
        calls.append(payload)
        return next(outputs),{'model':'test-only','request_id':str(len(calls)),'estimated_usd':.1,'seconds':1}
    monkeypatch.setattr(meta,'request',request)
    data,trace=meta.explain({'metrics':{'loss':3}},lambda:None)
    assert data['summary']=='Water declined.'
    assert len(calls)==2 and len(trace['attempts'])==2
    assert trace['estimated_usd']==pytest.approx(.2)


def test_point_prompt_accepts_fractional_user_coordinates(tmp_path,monkeypatch):
    image=tmp_path/'test-only.png';Image.new('RGB',(334,334)).save(image)
    class ReachedAPI(Exception):pass
    def request(payload,*args):
        assert payload['model']==meta.SAM_MODEL
        raise ReachedAPI()
    monkeypatch.setattr(meta,'request',request)
    # The official prompt builder rejects floats; reaching request verifies valid integer pixels.
    with pytest.raises(ReachedAPI):meta.segment(image,lambda:None,point=(.217,.797))


def test_theme_explanations_require_distinct_summaries_and_scoped_metrics():
    evidence={'mode':'history','themes':['water','forest'],'time_context':{'first_year':2000,'last_year':2020},'theme_metric_keys':{'water':['water_loss_ha'],'forest':['vegetation_decline_in_forest_baseline_ha']}}
    water={'summary':'Between 2000 and 2020, water declined.','observations':[{'text':'Water retreat exceeded gain.','metric_keys':['water_loss_ha']}],'limitations':[]}
    forest={'summary':'Between 2000 and 2020, tree-cover evidence was limited.','observations':[{'text':'Decline was assessed within the baseline.','metric_keys':['vegetation_decline_in_forest_baseline_ha']}],'limitations':[]}
    data={'by_theme':{'water':water,'forest':forest}}
    meta.validate_theme_explanations(data,evidence,['2000','2020'])
    with pytest.raises(ValueError):meta.validate_theme_explanations({'by_theme':{'water':water}},evidence,['2000','2020'])
    with pytest.raises(ValueError):meta.validate_theme_explanations({'by_theme':{'water':water,'forest':water}},evidence,['2000','2020'])
    with pytest.raises(ValueError):meta.validate_theme_explanations({'by_theme':{'water':water,'forest':{**forest,'summary':water['summary']}}},evidence,['2000','2020'])
