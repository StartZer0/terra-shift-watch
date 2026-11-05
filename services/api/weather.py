import calendar
from datetime import date
import httpx
import numpy as np

def weather_context(req,check):
    start=req.from_year if req.mode=='history' else req.before_date.year
    end=req.to_year if req.mode=='history' else req.after_date.year
    first=min(start,1991); last=max(end,2020)
    params={'latitude':req.latitude,'longitude':req.longitude,'start_date':f'{first}-01-01','end_date':str(min(date.today(),date(last,12,31))),'daily':'temperature_2m_mean,precipitation_sum','models':'era5','timezone':'UTC'}
    check()
    with httpx.Client(timeout=60) as c:
        r=c.get('https://archive-api.open-meteo.com/v1/archive',params=params); r.raise_for_status(); data=r.json()
    d=data['daily']; groups={}
    for day,t,p in zip(d['time'],d['temperature_2m_mean'],d['precipitation_sum']):
        y,m,_=map(int,day.split('-'))
        if req.start_month<=m<=req.end_month: groups.setdefault(y,[]).append((t,p))
    annual=[]
    for y,values in groups.items():
        expected=sum(calendar.monthrange(y,m)[1] for m in range(req.start_month,req.end_month+1))
        complete=sum(t is not None and p is not None for t,p in values)==expected
        if complete: annual.append({'year':y,'temperature_c':float(np.mean([v[0] for v in values])),'precipitation_mm':float(sum(v[1] for v in values))})
    baseline=[v for v in annual if 1991<=v['year']<=2020]
    if len(baseline)!=30: raise ValueError('Weather climatology incomplete.')
    mean_p=float(np.mean([v['precipitation_mm'] for v in baseline])); mean_t=float(np.mean([v['temperature_c'] for v in baseline]))
    out=[]
    for v in annual:
        if start<=v['year']<=end: out.append({**v,'precipitation_anomaly_mm':v['precipitation_mm']-mean_p,'temperature_anomaly_c':v['temperature_c']-mean_t})
    return {'dataset':'ERA5','resolution':'0.25° reanalysis; representative cell, not a local weather station','baseline':'1991–2020, same seasonal months','latitude':data.get('latitude'),'longitude':data.get('longitude'),'season_months':[req.start_month,req.end_month],'annual':out,'attribution':'Weather data by Open-Meteo / Copernicus Climate Change Service (CC BY 4.0)','limitation':'Temporal association does not establish causation. Event mode weather is seasonal context, not an event rainfall reconstruction.'}
