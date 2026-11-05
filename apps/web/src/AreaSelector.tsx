import {Crosshair, Pentagon, Square} from 'lucide-react';
import type {Settings} from './types';

interface Props {
 settings:Settings;area:number|null;picking:boolean;drawing:boolean;
 onChange:(patch:Partial<Settings>)=>void;onPick:()=>void;onDraw:()=>void;
}

export default function AreaSelector({settings:s,area,picking,drawing,onChange,onPick,onDraw}:Props){
 const custom=!!s.aoi_polygon;
 const vertices=custom?s.aoi_polygon!.slice(0,-1):[];
 function edit(index:number,axis:number,value:number){
  const next=vertices.map((p,i)=>i===index?p.map((v,a)=>a===axis?value:v):p);
  onChange({aoi_polygon:[...next,next[0]]});
 }
 return <section className="setup-section area-selector">
  <div className="section-label"><span>Study area</span>{custom?<Pentagon size={15}/>:<Square size={15}/>}</div>
  <h2 className="place-title">{s.label}</h2>
  <div className="segmented" aria-label="Boundary shape">
   <button type="button" aria-pressed={!custom&&!drawing} className={!custom&&!drawing?'selected':''} onClick={()=>onChange({aoi_polygon:null})}><Square size={14}/>Square</button>
   <button type="button" aria-pressed={custom||drawing} className={custom||drawing?'selected':''} onClick={onDraw}><Pentagon size={14}/>{custom?'Redraw boundary':'Draw boundary'}</button>
  </div>
  {!custom&&<><div className="coordinate-row"><label>Latitude<input type="number" step="0.00001" min="-89" max="89" value={s.latitude} onChange={e=>onChange({latitude:Number(e.target.value),label:'Selected location'})}/></label><label>Longitude<input type="number" step="0.00001" min="-180" max="180" value={s.longitude} onChange={e=>onChange({longitude:Number(e.target.value),label:'Selected location'})}/></label></div>
   <div className="square-row"><label>Square width <span><input aria-label="Square width km" type="number" min="1" max="500" step="0.1" value={s.side_km} onChange={e=>onChange({side_km:Number(e.target.value)})}/> km</span></label><button type="button" className={`pick-button ${picking?'active':''}`} onClick={onPick}><Crosshair size={16}/>{picking?'Click Earth':'Pick on Earth'}</button></div></>}
  {custom&&<><p className="subtle">{vertices.length} corners. Drag a corner on the map to refine the boundary.</p><details className="boundary-coordinates"><summary>Edit exact coordinates</summary>{vertices.map((point,i)=><div className="coordinate-row" key={i}><label>Corner {i+1} latitude<input aria-label={`Corner ${i+1} latitude`} type="number" step="0.00001" value={point[1]} onChange={e=>edit(i,1,Number(e.target.value))}/></label><label>Longitude<input aria-label={`Corner ${i+1} longitude`} type="number" step="0.00001" value={point[0]} onChange={e=>edit(i,0,Number(e.target.value))}/></label></div>)}</details></>}
  <p className="subtle">{(area??s.side_km**2).toLocaleString(undefined,{maximumFractionDigits:2})} km² selected · only this boundary is analyzed</p>
  <p className="subtle">Boundary precision follows the {s.resolution} m analysis cells. Missing pixels stay unknown.</p>
 </section>;
}
