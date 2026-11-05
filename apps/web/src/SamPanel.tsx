import type {Result,Theme} from './types';
import {FeatureChart} from './ImpactPanel';
const number=(value:number)=>value.toLocaleString(undefined,{maximumFractionDigits:2});

export default function SamPanel({result,theme,frame,showMasks,onFrame,onPlay,onChange,onToggle}:{result:Result;theme:Theme;frame:number;showMasks:boolean;onFrame:(index:number)=>void;onPlay:()=>void;onChange:()=>void;onToggle:(value:boolean)=>void}){
 const entries=result.sam.filter(entry=>!entry.themes||entry.themes.includes(theme));const summary=result.sam_summary?.[theme];
 if(!entries.length)return null;
 const concept=summary?.concept||entries[0].concept||'selected concept';
 const change=summary?.change;
 return <section className="sam-analysis" aria-label="SAM 3.1 analysis"><div className="section-label">SAM 3.1 · {concept}<span>Actual model masks</span></div>
  {summary?<><div className="sam-status"><strong>{summary.successful}/{summary.attempted}</strong><span>periods with usable scoped masks</span></div><div className="sam-counts"><span>{summary.guided} guided</span><span>{summary.empty} empty</span><span>{summary.failed} failed</span></div>
   {change&&<div className="feature-metrics"><div><span>SAM starting area</span><strong>{number(change.before_ha)}<small>ha</small></strong></div><div><span>SAM ending area</span><strong>{number(change.after_ha)}<small>ha</small></strong></div><div><span>SAM gained</span><strong>{number(change.gain_ha)}<small>ha</small></strong></div><div><span>SAM lost</span><strong>{number(change.loss_ha)}<small>ha</small></strong></div></div>}
   <p className="subtle">Scope: {summary.scope} ({number(summary.support_ha)} ha). Comparable image coverage: {number(summary.common_valid_pct)}%.</p>
   {summary.successful>=2?<FeatureChart chart={{title:theme==='forest'?'SAM vegetation in tree-cover baseline':`SAM ${concept} area through time`,unit:'ha',color:'#8567b1',note:'Each point is a real SAM segmentation on a dated acquisition. Missing masks remain gaps.',points:summary.points,periods:summary.periods}}/>:<p className="sam-no-data">No defensible SAM trend is available for this feature. Empty outputs remain unknown, rather than zero area.</p>}
   <div className="sam-actions"><button className="secondary" disabled={!change} onClick={onChange}>View SAM change</button><button className="secondary" disabled={!summary.successful} onClick={onPlay}>Play SAM history</button></div><p className="subtle">{summary.note}</p>
  </>:<p className="subtle">This older report contains endpoint masks only. New analyses segment every available yearly image.</p>}
  <label className="check-label"><input type="checkbox" checked={showMasks} onChange={event=>onToggle(event.target.checked)}/>Show SAM mask on current year</label>
  <details><summary>Inspect yearly masks and model evidence</summary><div className="sam-year-list">{entries.map(entry=>{
   const observation=result.observations.find(obs=>obs.index===entry.index);const scores=entry.object_details?.flatMap(object=>object.confidence===null?[]:[object.confidence]);
   const status=entry.state==='guided'?'Guided mask':entry.state==='ready'?'Concept mask':entry.state==='empty'||entry.state==='no_detection'?'Empty · unknown':'Unavailable';
   return <button key={entry.index} className={frame===entry.index?'selected':''} onClick={()=>onFrame(entry.index)} title={entry.reason}><strong>{observation?.label}</strong><span>{status}</span><small>{typeof entry.area_ha==='number'&&['ready','guided'].includes(entry.state)?`${number(entry.area_ha)} ha · whole-image concept`:entry.reason||'No usable mask'}</small>{scores&&scores.length>0&&<small>Model score {Math.min(...scores).toFixed(2)}–{Math.max(...scores).toFixed(2)} · uncalibrated</small>}{entry.prompt_mode==='spectral-guided'&&<small>Text prompt was empty; spectral boxes and points located the objects.</small>}{entry.spectral_iou!==null&&entry.spectral_iou!==undefined&&<small>Spectral agreement {number(entry.spectral_iou*100)}%{entry.state==='guided'?' · guided, not independent':''}</small>}</button>
  })}</div><p className="subtle">Table areas describe the whole-image concept. Charts and change metrics use the stated common support and, for Forests, the dated baseline. Neither model scores nor spectral agreement establish ground-truth accuracy.</p></details>
 </section>;
}
