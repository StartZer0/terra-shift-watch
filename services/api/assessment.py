"""Readable findings and explicitly descriptive change levels, independent of an LLM."""
import calendar
import numpy as np
from .science import geographic_image, selection_mask, coverage_pct


def extent_level(percent):
    if percent is None: return 'Not assessable'
    if percent <= 0: return 'None detected'
    if percent < 5: return 'Localized'
    if percent < 20: return 'Distributed'
    if percent < 50: return 'Widespread'
    return 'Extensive'


def period_context(result):
    req=result['request']; ready=[o for o in result['observations'] if o['state']=='ready']
    first,last=ready[0],ready[-1]
    history=req['mode']=='history'
    observed=f'{first["year"]}–{last["year"]}' if history else f'{first["date"][:10]} → {last["date"][:10]}'
    return {'mode':req['mode'],'requested':f'{req["from_year"]}–{req["to_year"]}' if history else f'{req["before_date"]} → {req["after_date"]}',
        'observed':observed,'first_year':first['year'],'last_year':last['year'],
        'span_years':last['year']-first['year'],'available_periods':len(ready),'requested_periods':len(result['observations']),
        'season':f'{calendar.month_abbr[req["start_month"]]}–{calendar.month_abbr[req["end_month"]]}',
        'measurement_basis':'Same-season annual sample medians; displayed image dates are representative acquisitions, not the measurement windows.' if history else 'Single acquisitions on the actual observed dates.',
        'before_image_date':first['date'][:10],'after_image_date':last['date'][:10]}


def _number(value):
    return f'{value:,.1f}' if value is not None else 'unknown'


def rainfall_context(weather):
    if not weather: return None
    annual=[]
    for row in weather.get('annual',[]):
        baseline=row['precipitation_mm']-row['precipitation_anomaly_mm']
        annual.append({**row,'precipitation_anomaly_pct':100*row['precipitation_anomaly_mm']/baseline if baseline>=1 else None})
    return {'annual':annual,'baseline':weather.get('baseline','1991–2020'),
        'note':'Regional seasonal rainfall anomaly, not a validated drought-severity index or proof of local drought. A drought category requires an appropriate calibrated indicator such as SPI or SPEI.',
        'reference':'https://www.drought.gov/topics/global-drought-indices'}


def annual_history(path,ready,grid,source,check):
    selected=selection_mask(grid);cohort=selected.copy();land=selected.copy()
    for obs in ready:
        check()
        with np.load(path/f'indices-{obs["index"]}.npz') as archive:
            values=archive['values'];finite=np.isfinite(values).all(axis=0);cohort &= finite
            if source!='sentinel1':land &= finite&(values[1]<=0)
    rows=[]
    for obs in ready:
        check();row={key:obs[key] for key in ('year','index','label')}
        with np.load(path/f'indices-{obs["index"]}.npz') as archive:
            values=archive['values']
            if source=='sentinel1':row['mean_vv_db']=float(np.mean(values[0][cohort])) if cohort.any() else None
            else:
                row['water_ha']=float(((values[1]>0)&cohort).sum()*grid.resolution**2/10000) if cohort.any() else None
                row['ndvi']=float(np.mean(values[0][land])) if land.any() else None
                row['bsi']=float(np.mean(values[2][land])) if land.any() else None
        rows.append(row)
    return rows,{'history_common_valid_pct':coverage_pct(cohort,selected),'history_land_valid_pct':coverage_pct(land,selected) if source!='sentinel1' else None}


def _paint(levels, positive, negative, valid, selected, palette_up, palette_down):
    image=np.zeros((*selected.shape,4),dtype='uint8')
    for index in range(1,4):
        image[(levels==index)&positive&valid]=[*palette_up[index-1],230]
        image[(levels==index)&negative&valid]=[*palette_down[index-1],230]
    yy,xx=np.indices(selected.shape)
    image[selected&~valid]=[54,68,77,150]
    image[selected&~valid&((xx+yy)%12<3)]=[170,181,190,180]
    return image


def build_assessment(result,before,after,masks,grid,path,check):
    selected=selection_mask(grid);valid=masks['valid'];area=result['metrics'].get('common_valid_ha')
    metrics=result['metrics'];req=result['request'];themes=req.get('themes') or [req['theme']]
    forest=result.get('forest_reference') or {}
    if 'forest' in themes and forest.get('state')=='ready':
        for label,key in [('baseline_ha','mapped_baseline_ha'),('comparable_ha','comparable_baseline_ha'),('loss_ha','mapped_loss_pixels_ha'),('coverage_pct','reference_coverage_pct')]:metrics[f'forest_reference_{label}']=forest.get(key)
    temporal=period_context(result);cards=[];maps={};cell_ha=grid.resolution**2/10000
    for theme in themes:
        check();baseline=area;scope='of comparable region';detail='';value='Unknown';unit='';affected=None
        if req['source']=='sentinel1':
            affected=metrics.get('backscatter_decrease_ha',0)+metrics.get('backscatter_increase_ha',0) if area else None
            value=_number(affected);unit='ha changed';detail='Radar backscatter changed; this does not establish flooding.'
            title='Radar change'
        elif theme in ('water','coast'):
            title='Water extent' if theme=='water' else 'Land / water transitions'
            gain=metrics.get('water_gain_ha');loss=metrics.get('water_loss_ha');net=metrics.get('net_water_ha')
            affected=gain+loss if gain is not None and loss is not None else None
            relative=metrics.get('relative_water_pct')
            value=f'{relative:+.1f}%' if relative is not None else _number(net)
            unit='starting water area' if relative is not None else 'ha net change'
            detail=f'{_number(metrics.get("before_water_ha"))} → {_number(metrics.get("after_water_ha"))} ha of water. Net {net:+,.1f} ha.' if net is not None else 'No comparable endpoint water measurement.'
            if theme=='coast':
                value=_number(affected);unit='ha switched between land and water'
                detail=f'{_number(gain)} ha land → water; {_number(loss)} ha water → land. This uses the same water masks, viewed as boundary transitions.'
        elif theme=='vegetation':
            title='Vegetation change';gain=metrics.get('greening_ha');loss=metrics.get('browning_ha')
            affected=gain+loss if gain is not None and loss is not None else None
            delta=metrics.get('mean_ndvi_change');value=f'{delta:+.3f}' if delta is not None else 'Unknown';unit='mean NDVI change'
            detail=f'{_number(gain)} ha greener; {_number(loss)} ha declined, excluding endpoint water.'
        elif theme=='forest':
            title='Tree-cover decline';forest=result.get('forest_reference') or {}
            affected=metrics.get('vegetation_decline_in_forest_baseline_ha')
            baseline=forest.get('comparable_baseline_ha')
            if baseline is None and metrics.get('common_valid_pct')==100:baseline=forest.get('mapped_baseline_ha')
            scope='of comparable tree-cover baseline';value=_number(affected);unit='ha of vegetation decline'
            detail=f'Compared against {_number(baseline)} ha of dated tree-cover baseline. This does not confirm permanent deforestation.' if baseline else 'No adequate comparable tree-cover baseline. General vegetation change cannot establish deforestation.'
            if not baseline:affected=None;value='—';unit='no comparable baseline'
        else:
            title='Exposed-ground increase';affected=metrics.get('exposed_ground_increase_ha')
            value=_number(affected);unit='ha mapped';detail='Increase in the bare-soil index, excluding endpoint water. Soil loss and desertification are not established.'
        percent=100*affected/baseline if affected is not None and baseline and baseline>0 else None
        cards.append({'theme':theme,'title':title,'value':value,'unit':unit,'detail':detail,'affected_ha':affected,
            'extent_pct':percent,'extent_label':extent_level(percent),'scope':scope,'coverage_pct':metrics.get('common_valid_pct')})

    if req['source']!='sentinel1':
        # The last three requested years must all exist; do not bridge missing years.
        end=req['to_year'];years=list(range(end-2,end+1))
        recent={o['year']:o for o in result['observations'] if o['state']=='ready' and o['year'] in years}
        if req['mode']=='history' and req['to_year']-req['from_year']>=2 and len(recent)==3:
            recent_valid=valid.copy();wet_count=np.zeros(selected.shape,dtype='uint8')
            for year in years:
                check()
                with np.load(path/f'indices-{recent[year]["index"]}.npz') as data:
                    values=data['values'];recent_valid &= np.isfinite(values).all(axis=0);wet_count += (values[1]>0)
            up=[(171,222,241),(64,162,204),(0,91,153)];down=[(253,201,158),(232,115,49),(164,35,31)]
            levels=np.where(masks['water_loss'],3-wet_count,wet_count)
            image=_paint(levels,masks['water_gain'],masks['water_loss'],recent_valid,selected,up,down)
            name='impact-water.png';geographic_image(image,grid,path/name)
            legend=[{'label':f'{direction} · {n}/3 years','color':'#%02x%02x%02x'%color} for direction,colors in [('Gain',up),('Loss',down)] for n,color in enumerate(colors,1)]
            for theme in ('water','coast'):
                if theme in themes:maps[theme]={'image':name,'title':'Recent persistence','legend':legend,
                    'note':f'Darker areas show the changed water state in more of {years[0]}, {years[1]}, {years[2]}. This measures repeated observations, not flood depth or drought severity.'}
            metrics['persistent_recent_water_loss_ha']=float((masks['water_loss']&recent_valid&(wet_count==0)).sum()*cell_ha)
            metrics['persistent_recent_water_gain_ha']=float((masks['water_gain']&recent_valid&(wet_count==3)).sum()*cell_ha)
        for theme in themes:
            if theme not in ('vegetation','forest','ground'):continue
            if theme=='forest' and ('forest_decline' not in masks or next(c for c in cards if c['theme']=='forest')['extent_pct'] is None):continue
            delta=after[2]-before[2] if theme=='ground' else after[0]-before[0]
            levels=np.where(np.abs(delta)>=.35,3,np.where(np.abs(delta)>=.2,2,np.where(np.abs(delta)>=.1,1,0))).astype('uint8')
            positive=masks['ground'] if theme=='ground' else masks['greening'] if theme=='vegetation' else np.zeros(selected.shape,dtype=bool)
            negative=masks['forest_decline'] if theme=='forest' else masks['browning'] if theme=='vegetation' else np.zeros(selected.shape,dtype=bool)
            up=[(185,227,187),(80,171,113),(10,104,67)] if theme!='ground' else [(253,213,164),(235,142,53),(164,66,23)]
            down=[(253,202,175),(232,114,74),(166,36,40)]
            name=f'impact-{theme}.png';geographic_image(_paint(levels,positive,negative,valid,selected,up,down),grid,path/name)
            labels=['0.10–0.20','0.20–0.35','≥0.35'];directions=[('Increase',up)] if theme=='ground' else [('Decline',down)] if theme=='forest' else [('Greener',up),('Decline',down)]
            maps[theme]={'image':name,'title':'Index-change intensity','legend':[{'label':f'{direction} · {label}','color':'#%02x%02x%02x'%color} for direction,colors in directions for label,color in zip(labels,colors)],
                'note':f'Absolute change in {"BSI" if theme=="ground" else "NDVI"}. These are descriptive app bins, not calibrated damage, drought or deforestation severity classes.'}
        forest=result.get('forest_reference') or {}
        if 'forest' in themes and forest.get('image') and (path/forest['image']).exists():
            maps['forest']={'image':forest['image'],'title':'Dated tree-cover reference','kind':'reference',
                'legend':[{'label':'Tree-cover baseline','color':'#30804c'},{'label':'Mapped tree-cover loss','color':'#c44526'}],
                'note':f'Dated tree-cover reference for {temporal["observed"]}. Green shows the starting baseline; orange shows mapped loss within it. Loss can include fire or harvest and does not establish permanent deforestation. This is a reference layer, not the endpoint NDVI-change mask.'}
        if 'coast' in maps:
            maps['coast']={**maps['coast'],'legend':[{**item,'label':item['label'].replace('Gain','Land → water').replace('Loss','Water → land')} for item in maps['coast']['legend']]}
    return {'temporal':temporal,'cards':cards,'features':feature_findings(result,cards),'maps':maps,'rainfall':rainfall_context(result.get('weather')),
        'level_method':'Spatial reach = affected mapped area ÷ comparable area. Localized: <5%; distributed: 5–<20%; widespread: 20–<50%; extensive: ≥50%. These descriptive app bands are not hazard-severity or confidence scores.'}


def feature_findings(result,cards):
    metrics=result['metrics'];forest=result.get('forest_reference') or {};annual=result.get('annual',[])
    findings={};period=period_context(result)['observed']
    for card in cards:
        theme=card['theme'];rows=[];chart=None
        def metric(label,value,unit='ha'):
            rows.append({'label':label,'value':f'{value:+.3f}' if value is not None and unit in ('NDVI','BSI') else _number(value) if value is not None else '—','unit':unit})
        def history(title,key,unit,color,note,transform=lambda value:value):
            return {'title':title,'unit':unit,'color':color,'note':note,'points':[{'index':row['index'],'label':row['label'],'value':transform(row[key]) if row.get(key) is not None else None} for row in annual],'periods':len(result['observations'])}
        if result['request']['source']=='sentinel1':
            metric('Backscatter decreased',metrics.get('backscatter_decrease_ha'));metric('Backscatter increased',metrics.get('backscatter_increase_ha'))
            chart=history('Radar backscatter','mean_vv_db','dB','#167d9f','Matched-orbit radar observations on common valid pixels.')
            text='Radar backscatter changed between the observed periods. Water, tree-cover and shoreline attribution cannot be established from this radar comparison.'
            limit='This is a radar measurement, not an optical land-cover classification.'
        elif theme=='water':
            for label,key in [('Starting water area','before_water_ha'),('Ending water area','after_water_ha'),('Water gained','water_gain_ha'),('Water lost','water_loss_ha')]:metric(label,metrics.get(key))
            chart=history('Water area through time','water_ha','ha','#167d9f',f'{_number(metrics.get("history_common_valid_pct"))}% fixed common support; missing years are gaps.')
            net=metrics.get('net_water_ha') or 0;direction='decreased' if net<0 else 'increased' if net>0 else 'had no net change'
            text=f'Between {period}, mapped water {direction}. {card["detail"]}'
            limit='Water extent does not measure flood depth, water volume or drought severity.'
        elif theme=='coast':
            gain=metrics.get('water_gain_ha');loss=metrics.get('water_loss_ha')
            metric('Land → water',gain);metric('Water → land',loss);metric('Net mapped land gain',-metrics['net_water_ha'] if metrics.get('net_water_ha') is not None else None)
            base=next((row.get('water_ha') for row in annual if row.get('water_ha') is not None),None)
            chart=history('Net land change relative to start','water_ha','ha','#b36b32','Positive = less water / more mapped land. Same water masks as Water, on fixed common support.',lambda value:base-value if base is not None else None)
            text=f'Between {period}, the waterline changed within the selected boundary. {card["detail"]} Positive net land gain means water retreat; it does not establish sediment accumulation.'
            limit='Applies to inland waterlines too. No tide correction, shoreline retreat distance or erosion rate is available.'
        elif theme=='forest':
            metric('Dated tree-cover baseline',forest.get('mapped_baseline_ha'))
            metric('Comparable baseline',forest.get('comparable_baseline_ha'))
            metric('Mapped tree-cover loss · reference',forest.get('mapped_loss_pixels_ha'))
            metric('Reference land coverage',forest.get('reference_coverage_pct'),'%')
            loss_by_year=forest.get('annual_loss')
            if loss_by_year:
                cumulative=0;points=[];first=period_context(result)['first_year']
                for row in loss_by_year:
                    cumulative+=row['loss_ha'];points.append({'index':row['year']-first,'label':str(row['year']),'value':cumulative})
                chart={'title':'Cumulative mapped tree-cover loss','unit':'ha','color':'#ae4b31','note':'Dated reference loss within the starting tree-cover baseline, not a general NDVI chart. No regrowth reconstruction.','points':points,'periods':len(points)}
            elif forest.get('state')=='ready':
                chart={'title':'Dated tree-cover evidence','unit':'ha','color':'#387b51','type':'bars','note':'Starting baseline and mapped reference loss are different measures; these bars are not an annual history or endpoint NDVI comparison.','points':[{'index':0,'label':'Tree-cover baseline','value':forest.get('mapped_baseline_ha')},{'index':1,'label':'Mapped reference loss','value':forest.get('mapped_loss_pixels_ha')}],'periods':2}
            text=f'Tree-cover evidence for {period}: {card["detail"]} The reference separately maps {_number(forest.get("mapped_loss_pixels_ha"))} ha of tree-cover loss.' if forest.get('state')=='ready' else forest.get('reason','No dated tree-cover reference is available for this comparison.')
            limit='Reference loss can include harvest, fire and other disturbance. It is not proof of permanent deforestation; regrowth is not reconstructed.'
        elif theme=='vegetation':
            metric('Greener land',metrics.get('greening_ha'));metric('Vegetation decline',metrics.get('browning_ha'))
            metric('Mean NDVI change',metrics.get('mean_ndvi_change'),'NDVI')
            chart=history('Vegetation greenness through time','ndvi','NDVI','#387b51',f'{_number(metrics.get("history_land_valid_pct"))}% stable non-water support across sampled years.')
            text=f'Vegetation observations for {period}: {card["detail"]} The annual curve measures greenness on land that remained non-water.'
            limit='Greenness change can reflect seasons, crops or disturbance. It does not by itself measure forest loss.'
        else:
            metric('Exposed-ground increase',metrics.get('exposed_ground_increase_ha'))
            chart=history('Bare-soil index through time','bsi','BSI','#ac641f',f'{_number(metrics.get("history_land_valid_pct"))}% stable non-water support across sampled years.')
            text=f'Ground observations for {period}: {card["detail"]} The annual curve tracks the bare-soil index on stable non-water pixels.'
            limit='Rock, construction and agricultural activity can also raise this index. This is not confirmed soil erosion or desertification.'
        findings[theme]={'metrics':rows,'chart':chart,'explanation':text,'limitation':limit}
    return findings


def explanation_evidence(result):
    req=result['request'];themes=req.get('themes') or [req['theme']]
    prefixes={'water':('water_','before_water_','after_water_','net_water_','relative_water_','persistent_recent_water_'),
        'coast':('water_','before_water_','after_water_','net_water_','relative_water_','persistent_recent_water_'),
        'vegetation':('greening_','browning_','mean_ndvi_'),'forest':('vegetation_decline_in_forest_','forest_reference_'),'ground':('exposed_ground_',)}
    prefixes={theme:prefixes[theme]+(f'sam_{theme}_',) for theme in themes}
    allowed=('common_valid_','history_','actual_interval_','backscatter_','mean_vv_')+tuple(p for theme in themes for p in prefixes[theme])
    metrics={key:value for key,value in result['metrics'].items() if key.startswith(allowed)}
    theme_metric_keys={theme:[key for key in metrics if key.startswith(('common_valid_','history_','actual_interval_','backscatter_','mean_vv_')+prefixes[theme])] for theme in themes}
    annual=[{k:v for k,v in row.items() if k in ('year','index','label') or k=='water_ha' and any(t in themes for t in ('water','coast')) or k=='ndvi' and 'vegetation' in themes or k=='bsi' and 'ground' in themes} for row in result['annual']]
    return {'mode':req['mode'],'time_context':period_context(result),'annual':annual,'metrics':metrics,'themes':themes,'theme_metric_keys':theme_metric_keys,
        'key_findings':(result.get('assessment') or {}).get('cards',[]),'feature_findings':(result.get('assessment') or {}).get('features',{}),'quality':result['quality'],
        'forest_reference':result.get('forest_reference') if 'forest' in themes else None,
        'terrain_reference':result.get('terrain_reference') if 'ground' in themes else None,
        'sam':result.get('sam_summary',result['sam']),'weather':result.get('weather'),'limitations':result['limitations']}
