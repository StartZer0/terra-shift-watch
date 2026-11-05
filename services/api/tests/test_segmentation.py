import json
import numpy as np
import pytest
from PIL import Image
from services.api import meta
from services.api.segmentation import guidance,segment_observation,summarize
from services.api.science import make_grid


def test_decode_real_wire_format_inclusive_bounds_and_empty_vs_invalid(tmp_path,monkeypatch):
    path=tmp_path/'input.png';Image.new('RGB',(8,8)).save(path)
    trace={'model':'test-only','request_id':'test-only','estimated_usd':0,'seconds':0}
    raw='<0f>0<|box;x1=1;y1=1;x2=5;y2=5;w=8;h=8;c=0.75|><|mask;x=0;y=0;c=0.75;data=5,5,!!!!!(QO(0lu8?|>'
    monkeypatch.setattr(meta,'request',lambda *args:(raw,trace))
    mask,info=meta.segment(path,lambda:None)
    assert mask.shape==(8,8) and mask.any() and not mask[0].any() and not mask[:,6:].any()
    assert info['object_details'][0]['bounds']==[1,1,6,6] and info['object_details'][0]['confidence']==.75
    monkeypatch.setattr(meta,'request',lambda *args:('',trace))
    assert meta.segment(path,lambda:None)[1]['objects']==0
    for invalid in ['No objects found','<0f>',raw.replace('x2=5','x2=9').replace('w=8','w=10')]:
        monkeypatch.setattr(meta,'request',lambda *args:(invalid,trace))
        with pytest.raises(meta.ProviderError) as error:meta.segment(path,lambda:None)
        assert error.value.traces==[trace]


def test_guidance_seed_provenance_and_bounded_empty_recovery(tmp_path,monkeypatch):
    grid=make_grid(0,0,1,50);values=np.zeros((3,grid.size,grid.size),dtype='float32');values[1]=-.5;values[1,8:18,8:18]=.5
    valid=np.ones(values.shape[1:],dtype=bool);valid[:4]=False
    objects,seed=guidance(values,'water',valid)
    assert len(objects)==1 and seed['independent_of_spectral'] is False
    positive=objects[0].prompts[0].points[0]
    assert valid[positive.y,positive.x] and values[1,positive.y,positive.x]>.2
    calls=[]
    def fake(path,check,prompt,objects=None):
        calls.append(objects);mask=np.zeros(valid.shape,dtype=bool)
        if objects is not None:mask[8:18,8:18]=True
        return mask,{'model':'test-only','request_id':str(len(calls)),'estimated_usd':0,'seconds':0,'objects':int(objects is not None)}
    monkeypatch.setattr(meta,'segment',fake)
    values[:,~valid]=np.nan;np.savez_compressed(tmp_path/'observation-0.npz',values=values)
    obs={'index':0,'source_image':'input.png','date':'2020-07-01'}
    entry,traces=segment_observation(tmp_path,obs,grid,'water',['water','coast'],lambda:None)
    assert len(calls)==2 and entry['state']=='guided' and len(traces)==2
    assert len(entry['attempts'])==2 and entry['spectral_iou']==1
    assert entry['guidance']['objects'][0]['positive']==(positive.x,positive.y)
    # An empty scene has no spectral guidance; do not invent a zero-area measurement.
    values[1]=-.5;np.savez_compressed(tmp_path/'observation-0.npz',values=values);calls.clear()
    entry,_=segment_observation(tmp_path,obs,grid,'water',['water'],lambda:None)
    assert len(calls)==1 and entry['state']=='empty' and entry['area_ha'] is None
    assert not (tmp_path/'sam-water-0.png').exists() and not (tmp_path/'sam-water-0.npz').exists()


def test_sam_change_uses_own_masks_fixed_support_and_keeps_missing_year(tmp_path):
    grid=make_grid(0,0,1,100);shape=(grid.size,grid.size)
    before=np.zeros(shape,dtype=bool);before[:,:4]=True;after=np.zeros(shape,dtype=bool);after[:,:2]=True
    observations=[{'index':i,'state':'ready','label':str(2000+i),'date':f'{2000+i}-07-01'} for i in range(3)]
    for obs in observations:np.savez_compressed(tmp_path/f'observation-{obs["index"]}.npz',values=np.zeros((3,*shape)))
    np.savez_compressed(tmp_path/'sam-0.npz',mask=before);np.savez_compressed(tmp_path/'sam-2.npz',mask=after)
    entries=[{'index':i,'themes':['water','coast'],'concept':'water','state':'empty' if i==1 else 'guided' if i==2 else 'ready','mask':f'sam-{i}.npz'} for i in range(3)]
    result={'request':{'themes':['water','coast']},'observations':observations,'sam':entries}
    summaries=summarize(result,grid,tmp_path,lambda:None)
    assert [p['value'] for p in summaries['water']['points']]==[40,None,20]
    assert summaries['water']['guided']==1 and summaries['water']['successful']==2
    assert summaries['water']['change']['net_ha']==-20 and summaries['water']['change']['loss_ha']==20
    assert (tmp_path/summaries['water']['change']['image']).exists()
    entries[2]['state']='empty'
    assert summarize(result,grid,tmp_path,lambda:None)['water']['change'] is None
    assert not (tmp_path/'sam-change-water.png').exists()


def test_completed_text_is_not_lost_when_no_deltas(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','test-only');monkeypatch.setattr(meta,'reserve',lambda _:1);monkeypatch.setattr(meta,'settle',lambda *args:None)
    events=[{'type':'response.completed','response':{'id':'test-only','usage':{'images_processed':1},'output':[{'content':[{'type':'output_text','text':'actual output'}]}]}}]
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_lines(self):return iter('data: '+json.dumps(event) for event in events)
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,*args,**kwargs):return Response()
    monkeypatch.setattr(meta.httpx,'Client',Client)
    output,trace=meta.request({'model':meta.SAM_MODEL},lambda:None,.01)
    assert output=='actual output' and trace['output_source']=='completed' and trace['delta_events']==0


def test_provider_failure_stays_unavailable_and_is_not_retried_as_empty(tmp_path,monkeypatch):
    grid=make_grid(0,0,1,100);values=np.ones((3,grid.size,grid.size),dtype='float32')
    np.savez_compressed(tmp_path/'observation-0.npz',values=values)
    calls=[];trace={'request_id':'test-only','estimated_usd':.01}
    def failed(*args,**kwargs):
        calls.append(1);raise meta.ProviderError('Test-only API failure',[trace])
    monkeypatch.setattr(meta,'segment',failed)
    entry,traces=segment_observation(tmp_path,{'index':0,'date':'2020-07-01','source_image':'input.png'},grid,'water',['water'],lambda:None)
    assert len(calls)==1 and entry['state']=='unavailable' and entry['area_ha'] is None and traces==[trace]
