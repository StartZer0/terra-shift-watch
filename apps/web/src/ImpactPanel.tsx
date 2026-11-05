import type {CSSProperties} from 'react';
import type {Assessment,Theme,FeatureFinding,Narrative} from './types';

const colors:Record<Theme,string>={water:'#167d9f',coast:'#167d9f',vegetation:'#387b51',forest:'#9d4939',ground:'#ac641f'};

export default function ImpactPanel({assessment,active,onSelect}:{assessment:Assessment;active:Theme;onSelect:(theme:Theme)=>void}){
 const t=assessment.temporal;
 return <section className="impact-summary" aria-label="Key findings">
  <div className="impact-period"><span>{t.mode==='history'?`${t.span_years}-year change · ${t.available_periods}/${t.requested_periods} yearly periods`:'Actual acquisition interval'}</span><small>{t.mode==='history'?`${t.season} each year · seasonal measurements`:'Single-acquisition measurements'}</small>{t.requested!==t.observed&&<small>Requested: {t.requested}</small>}</div>
  <h3>What changed</h3>
  {assessment.cards.filter(card=>card.theme===active).map(card=><button key={card.theme} className="impact-card active" style={{'--impact-color':colors[card.theme]} as CSSProperties} onClick={()=>onSelect(card.theme)} aria-label={`Inspect ${card.title}`} aria-pressed={true}>
   <span className="impact-card-heading"><strong>{card.title}</strong><span className={`extent-badge ${card.extent_pct===0?'no-change':''}`}>{card.extent_label}</span></span>
   <span className="impact-value">{card.value}<small>{card.unit}</small></span>
   <span className="impact-detail">{card.detail}</span>
   {card.extent_pct!==null&&<><span className="extent-track" role="meter" aria-label={`${card.title}: affected share`} aria-valuenow={Math.min(100,card.extent_pct)} aria-valuemin={0} aria-valuemax={100}><i style={{width:`${Math.max(0,Math.min(100,card.extent_pct))}%`}}/></span><span className="extent-caption"><strong>{card.extent_pct.toFixed(1)}%</strong> {card.scope} changed</span></>}
  </button>)}
  <details className="impact-method"><summary>How change levels are defined</summary><p>{assessment.level_method}</p><p>For vegetation and ground maps, darker colours mean a larger index shift. These thresholds describe the measurement, rather than validated disaster damage.</p></details>
 </section>;
}

export function FeatureDetails({feature}:{feature:FeatureFinding}){
 return <section className="feature-details" aria-label="Selected feature measurements"><div className="feature-metrics">{feature.metrics.map(metric=><div key={metric.label}><span>{metric.label}</span><strong>{metric.value}<small>{metric.unit}</small></strong></div>)}</div>{feature.chart&&<FeatureChart chart={feature.chart}/>}</section>;
}

export function FeatureChart({chart}:{chart:NonNullable<FeatureFinding['chart']>}){
 const values=chart.points.flatMap(point=>point.value===null?[]:[point.value]);
 if(!values.length)return <p className="subtle">No comparable measurements are available for this chart.</p>;
 const min=Math.min(...values),max=Math.max(...values);const format=(value:number)=>value.toLocaleString(undefined,{maximumFractionDigits:chart.unit==='ha'?2:3});
 if(chart.type==='bars')return <div className="feature-chart"><h3>{chart.title}</h3>{chart.points.map(point=><div className="feature-bar" key={point.label}><span>{point.label}</span><div><i style={{width:`${point.value!==null&&max>0?point.value/max*100:0}%`,background:chart.color}}/></div><strong>{point.value===null?'—':format(point.value)} {chart.unit}</strong></div>)}<p className="subtle">{chart.note}</p></div>;
 const x=(index:number)=>12+index*272/Math.max(1,chart.periods-1),y=(value:number)=>72-(value-min)/(max-min||1)*48;
 const path=chart.points.map((point,index)=>point.value===null?'':`${index>0&&chart.points[index-1].index===point.index-1&&chart.points[index-1].value!==null?'L':'M'} ${x(point.index)},${y(point.value)}`).join(' ');
 return <div className="feature-chart"><h3>{chart.title}</h3><svg viewBox="0 0 296 94" role="img" aria-label={chart.title}><text x="12" y="13" fill="#617584" fontSize="10">{format(max)} {chart.unit}</text><line x1="12" y1="76" x2="284" y2="76" stroke="#d9e1e6"/><path d={path} fill="none" stroke={chart.color} strokeWidth="2.5" strokeLinejoin="round"/>{chart.points.filter(point=>point.value!==null).map(point=><circle key={point.index} cx={x(point.index)} cy={y(point.value!)} r="3" fill={chart.color}><title>{point.label}: {format(point.value!)} {chart.unit}</title></circle>)}<text x="12" y="91" fill="#617584" fontSize="10">{format(min)} {chart.unit}</text></svg><div className="chart-labels"><span>{chart.points[0]?.label}</span><span>{chart.points.at(-1)?.label}</span></div><p className="subtle">{chart.note}</p></div>;
}

export function FeatureInterpretation({feature,narrative,label}:{feature?:FeatureFinding;narrative?:Narrative;label:string}){
 return <section className="interpretation" aria-label={`${label} analysis`}><div className="section-label">{label} analysis <span>{narrative?'Muse Wonder':'Measured evidence'}</span></div><p>{narrative?.summary||feature?.explanation||'A feature-specific interpretation is unavailable for this older report. Run a new analysis to populate this feature.'}</p>{narrative&&<details><summary>Read the {label.toLowerCase()} interpretation</summary>{narrative.observations.map((observation,index)=><p className="plain-finding" key={index}>{observation.text}</p>)}{narrative.limitations.map((limitation,index)=><p className="subtle" key={index}>{limitation}</p>)}</details>}{feature&&<p className="subtle feature-scope">{feature.limitation}</p>}</section>;
}

export function RainfallPanel({rainfall}:{rainfall:NonNullable<Assessment['rainfall']>}){
 const rows=rainfall.annual.filter(row=>row.precipitation_anomaly_pct!==null);
 if(!rows.length)return null;
 const last=rows.at(-1)!;
 return <section className="rainfall-panel" aria-label="Rainfall context">
  <h3>Rainfall context</h3><p><strong>{last.year}: {last.precipitation_anomaly_pct!>0?'+':''}{last.precipitation_anomaly_pct!.toFixed(1)}%</strong> seasonal rainfall anomaly.</p>
  <p className="subtle">Baseline: {rainfall.baseline}.</p><div className="rainfall-bars" role="img" aria-label="Annual precipitation anomalies relative to the seasonal baseline">{rows.map(row=><div key={row.year} title={`${row.year}: ${row.precipitation_anomaly_pct!.toFixed(1)}%`} className="rainfall-column"><div><i className={row.precipitation_anomaly_pct!<0?'dry':'wet'} style={{height:`${Math.max(2,Math.min(40,Math.abs(row.precipitation_anomaly_pct!)*.4))}px`}}/></div><small>{rows.length<=5||row.year===rows[0].year||row.year===last.year?row.year:''}</small></div>)}</div>
  <p className="subtle">Orange: drier; blue: wetter. Bars cap at ±100%; hover for exact values.</p><details><summary>Does this establish drought severity?</summary><p className="subtle">{rainfall.note}</p><a href={rainfall.reference} target="_blank" rel="noreferrer">Drought indicator methods ↗</a></details>
 </section>;
}
