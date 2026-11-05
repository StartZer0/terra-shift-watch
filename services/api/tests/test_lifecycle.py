from pathlib import Path
from fastapi.testclient import TestClient
from services.api import app as module

class FinishedProcess:
    def poll(self): return 0

def test_session_isolation_and_explicit_delete(tmp_path,monkeypatch):
    monkeypatch.setattr(module.config,'JOBS',tmp_path/'jobs')
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**k:FinishedProcess())
    module.jobs.clear()
    with TestClient(module.app) as first:
        body={'longitude':0,'latitude':0,'from_year':2020,'to_year':2021}
        identifier=first.post('/api/jobs',json=body).json()['id']
        folder=tmp_path/'jobs'/identifier
        (folder/'frame-0.png').write_bytes(b'test-only artifact')
        # A second client cannot view or purge another session's imagery.
        other=TestClient(module.app)
        assert other.get(f'/api/jobs/{identifier}').status_code==404
        assert other.get(f'/api/jobs/{identifier}/assets/frame-0.png').status_code==404
        assert other.delete(f'/api/jobs/{identifier}').status_code==404
        assert first.post('/api/jobs',json=body).status_code==409
        assert first.delete(f'/api/jobs/{identifier}').status_code==200
        assert not folder.exists()
        assert first.get(f'/api/jobs/{identifier}/assets/frame-0.png').status_code==404
        replacement=first.post('/api/jobs',json=body)
        assert replacement.status_code==200
        assert replacement.json()['id']!=identifier
    assert not list((tmp_path/'jobs').iterdir())

def test_local_origin_protection(tmp_path,monkeypatch):
    monkeypatch.setattr(module.config,'JOBS',tmp_path/'jobs')
    with TestClient(module.app) as client:
        body={'longitude':0,'latitude':0}
        assert client.post('/api/estimate',json=body,headers={'Origin':'https://unrelated.example'}).status_code==403
        assert client.post('/api/estimate',json=body,headers={'Origin':'http://127.0.0.1:5174'}).status_code==200
        assert client.get('/api/health',headers={'Host':'untrusted.example'}).status_code==400
