"""Read-only provider checks. Never prints credentials or signed asset URLs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.api import config
import os
import httpx

def main():
    with httpx.Client(timeout=30) as client:
        key=os.getenv('MODEL_API_KEY')
        if key:
            r=client.get(config.META_URL+'/models',headers={'Authorization':'Bearer '+key})
            print('Meta model catalog HTTP:',r.status_code)
            if r.status_code==200:
                names=[x.get('id') for x in r.json().get('data',[])]
                for model in (config.MODEL,config.SAM_MODEL): print(model+': '+('listed' if model in names else 'not listed; verify account entitlement'))
        else: print('Meta key: missing')
        r=client.get(config.STAC_URL+'/collections/landsat-c2-l2'); print('Satellite catalog HTTP:',r.status_code)
        token=os.getenv('VITE_CESIUM_ION_TOKEN')
        if token:
            r=client.get('https://api.cesium.com/v1/assets/2/endpoint',params={'access_token':token})
            print('Cesium world imagery endpoint HTTP:',r.status_code)
        else: print('Cesium token: missing')

if __name__=='__main__':
    try: main()
    except Exception as e: print('Access check stopped:',type(e).__name__); sys.exit(1)
