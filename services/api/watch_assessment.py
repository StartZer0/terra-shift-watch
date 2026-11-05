"""Versioned, inspectable review rules. Levels are not calibrated hazard probabilities."""
from datetime import datetime,timezone
import math
import numpy as np

RULE_VERSION='watch-evidence-v1'
LEVELS={-1:'Unknown',0:'Routine',1:'Watch',2:'Elevated',3:'High review priority'}

def valid(value):return isinstance(value,(int,float)) and math.isfinite(value)

def rows(provider,key):
    if not provider or provider.get('state')!='ready':return []
    daily=provider.get('data',{}).get('daily',{})
    return [{'date':d,'value':float(v)} for d,v in zip(daily.get('time',[]),daily.get(key,[])) if valid(v)]

def assess(config,providers,satellite=None,today=None):
    now=datetime.fromisoformat(today+'T12:00:00+00:00') if today else datetime.now(timezone.utc)
    today=today or now.date().isoformat()
    providers=[dict(p) for p in providers]
    for provider in providers:
        if provider['id'] not in ('weather','river','marine') or provider.get('state')!='ready':continue
        try:age=(now-datetime.fromisoformat(provider['fetched_at'].replace('Z','+00:00'))).total_seconds()/3600
        except (ValueError,KeyError):age=999
        if age>18 or age<-.1:provider.update(state='outdated',reason='Forecast retrieval is too old for a current review. Refresh this watch; no current priority was inferred from stale forecasts.')
    sources={p['id']:p for p in providers}; evidence={};cards=[]
    def put(key,value,unit,source,detail):
        if valid(value):evidence[key]={'value':round(float(value),4),'unit':unit,'source':source,'detail':detail}
        return key
    def add(feature,title,level,summary,keys,series,unit,recommendation,limits):
        cards.append({'feature':feature,'title':title,'level':level,'level_label':LEVELS[level],'summary':summary,'evidence_ids':[k for k in keys if k in evidence],'series':series,'unit':unit,'recommendation':recommendation,'limitations':limits})
    rain=rows(sources.get('weather'),'precipitation_sum');et=rows(sources.get('weather'),'et0_fao_evapotranspiration')
    rain_f=[p for p in rain if p['date']>=today];et_f=[p for p in et if p['date']>=today]
    # Never silently compute a seven-day total from an incomplete response.
    rain_total=sum(p['value'] for p in rain_f[:7]) if len(rain_f)>=7 else None
    et_total=sum(p['value'] for p in et_f[:7]) if len(et_f)>=7 else None
    rain_max=max((p['value'] for p in rain_f),default=None)
    balance=rain_total-et_total if rain_total is not None and et_total is not None else None
    put('rain_7d',rain_total,'mm','weather','Seven-day forecast precipitation at the representative weather grid point.')
    put('rain_daily_max',rain_max,'mm/day','weather','Highest forecast daily precipitation.')
    put('water_balance_7d',balance,'mm','weather','Forecast precipitation minus reference evapotranspiration; not measured soil-water storage.')
    pressure=2 if balance is not None and balance<=-30 else 1 if balance is not None and balance<=-15 else 0 if balance is not None else -1
    sat=satellite or {};age=None
    if sat.get('observed_at'):
        age=(datetime.fromisoformat(today).date()-datetime.fromisoformat(sat['observed_at'].replace('Z','+00:00')).date()).days
    fresh=age is not None and 0<=age<=14
    if age is not None:put('satellite_age_days',age,'days','satellite','Age of the dated satellite observation; a catalog hit is not a pixel measurement.')
    spatial='Forecasts sample a representative model grid point, not every pixel in the selected boundary.'
    limits=['Priorities use application thresholds; they are not official warnings or calibrated event probabilities.',spatial]
    if 'water' in config['features']:
        flow=rows(sources.get('river'),'river_discharge');past=[p['value'] for p in flow if p['date']<today];future=[p for p in flow if p['date']>=today]
        provider=sources.get('river',{});usable=len(past)>=30 and len(future)>=3 and provider.get('grid_distance_km',999)<=30
        q95=float(np.percentile(past,95)) if usable else None;peak=max((p['value'] for p in future),default=None) if usable else None
        delta=(peak-past[-1]) if usable else None
        put('flow_recent_p95',q95,'m³/s','river','95th percentile of up to 90 recent modeled days; not a return-period flood threshold.')
        put('flow_forecast_peak',peak,'m³/s','river','Largest available forecast discharge over the next seven days.')
        put('flow_change_from_latest',delta,'m³/s','river','Forecast peak minus latest past modeled discharge; not a gauge observation.')
        observed=(sat.get('water') or {}).get('change') or {}
        if fresh and observed.get('common_valid_pct',0)>=20:
            put('observed_water_rate',observed.get('rate_ha_per_day'),'ha/day','satellite','Mapped change between two actual OPERA acquisitions on common valid pixels. This measured interval rate is not a prediction.')
        if usable:
            high=peak>max(q95*1.5,q95+2);elevated=peak>q95+max(1,q95*.05)
            level=3 if high else 2 if elevated else 1 if rain_max is not None and rain_max>=50 else 0
            summary='Forecast river flow is above its recent modeled range.' if elevated else 'No discharge trigger in this forecast; local flooding can still occur.'
        else:
            level=1 if rain_max is not None and rain_max>=50 else -1
            summary='Heavy-rain outlook warrants review; river evidence is unavailable.' if level==1 else 'River evidence is insufficient for a flood-related assessment.'
        add('water','River & heavy-rain outlook',level,summary,['flow_forecast_peak','flow_recent_p95','flow_change_from_latest','rain_daily_max','observed_water_rate'],flow,'m³/s','Check local flood bulletins, gauges, drainage, and exposure before taking action.',limits+['GloFAS is river-scale modeled discharge. This does not predict street flooding, flood depth, or the exact area inundated.','The recent percentile is season-dependent and is not a 2-, 5-, or 20-year flood threshold.'])
    if 'vegetation' in config['features']:
        dist=sat.get('vegetation',{});pct=dist.get('confirmed_pct') if fresh else None
        put('vegetation_disturbed_pct',pct,'%','satellite','Ongoing confirmed OPERA vegetation disturbance within valid sampled pixels; not forest-specific.')
        level=max(pressure,2 if pct is not None and pct>=5 else 1 if pct is not None and pct>0 else -1)
        add('vegetation','Vegetation stress outlook',level,'Drying weather pressure and dated vegetation-disturbance evidence are reviewed separately.', ['water_balance_7d','rain_7d','vegetation_disturbed_pct'],rain,'mm/day','Review recent imagery and local vegetation conditions; compare season-matched observations.',limits+['Reference ET₀ is atmospheric demand, not actual plant water loss. A seven-day deficit is not a drought or desertification diagnosis.'])
    if 'forest' in config['features']:
        forest=sat.get('forest',{});supported=fresh and forest.get('state')=='ready' and forest.get('observation_coverage_pct',0)>=20 and forest.get('reference_coverage_pct',0)>=20 and (forest.get('comparable_baseline_ha') or 0)>0
        area=forest.get('disturbance_ha') if supported else None
        put('forest_disturbance_ha',area,'ha','satellite','OPERA ongoing disturbance intersecting the dated available tree-cover reference.')
        level=2 if area is not None and area>1 else 1 if area is not None and area>0 else 0 if area is not None else -1
        add('forest','Forest disturbance review',level,'Dated disturbance is checked against an available tree-cover baseline.' if area is not None else 'Forest attribution awaits recent raster evidence and a tree-cover baseline.', ['forest_disturbance_ha','water_balance_7d'],[], 'ha','Inspect the disturbance footprint and verify harvest, fire, storm, or other causes with local evidence.',limits+['Disturbance is an observation, not a forecast of deforestation. Tree-cover reference age and coverage limit attribution.','Weather pressure alone does not establish that a forest exists or that tree loss will occur.'])
    if 'ground' in config['features']:
        ground=sat.get('ground',{});pct=ground.get('confirmed_pct') if fresh else None
        put('surface_disturbed_pct',pct,'%','satellite','OPERA ongoing confirmed generic surface disturbance; not a bare-soil or erosion measurement.')
        level=2 if pct is not None and pct>5 and rain_max is not None and rain_max>=30 else 1 if rain_max is not None and rain_max>=50 else 1 if pressure>=1 else 0 if rain_max is not None else -1
        add('ground','Ground & runoff pressure',level,'Rainfall and drying-pressure triggers identify places needing a ground-condition review.', ['rain_daily_max','water_balance_7d','surface_disturbed_pct'],rain,'mm/day','Check exposed ground, slope, soil type, drainage, and recent land disturbance before assessing erosion.',limits+['No soil-loss rate, landslide probability, or desert-expansion rate is inferred. Those need additional terrain, soil, land-use, and validated hazard models.'])
    if 'coast' in config['features']:
        marine=sources.get('marine',{});waves=rows(marine,'wave_height_max');future=[p for p in waves if p['date']>=today]
        usable=len(future)>=3 and marine.get('grid_distance_km',999)<=50
        peak=max((p['value'] for p in future),default=None) if usable else None
        put('wave_forecast_peak',peak,'m','marine','Forecast maximum significant wave height near the representative sea grid point.')
        level=3 if peak is not None and peak>=5 else 2 if peak is not None and peak>=3 else 1 if peak is not None and peak>=2 else 0 if peak is not None else -1
        add('coast','Coastal wave exposure',level,'Review the wave outlook alongside local shoreline exposure.' if usable else 'No suitable nearby marine forecast cell; coastal exposure is not assessed.', ['wave_forecast_peak'],waves if usable else [],'m','Consult local coastal forecasts, tides, terrain, and protective infrastructure.',limits+['Significant wave height is not storm-surge depth, inland flood depth, or predicted shoreline retreat.'])
    assessed=[c['level'] for c in cards if c['level']>=0];level=max(assessed) if assessed else -1
    return {'rule_version':RULE_VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'forecast_start':today,'level':level,'level_label':LEVELS[level],'cards':cards,'evidence':evidence,'sources':providers,'satellite':satellite,'coverage':{'assessed_features':len(assessed),'requested_features':len(cards),'scope':'Representative model grid points; satellite rasters, when read, are clipped to the selected boundary.'},'disclaimer':'Research and review support. Use official local warnings and professional judgment for safety decisions.'}
