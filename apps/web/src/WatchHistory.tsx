import {useEffect,useState} from 'react';
import {api} from './types';
import {timeLabel,type Snapshot} from './watch-types';
const labels=['Routine','Watch','Elevated','High review priority'];
const colors=['#3d7867','#8a651a','#a04c16','#a02f2d'];
export default function WatchHistory({id,updated}:{id:string;updated:string}){
 const [history,setHistory]=useState<Snapshot[]>([]);
 useEffect(()=>{let stopped=false;api<Snapshot[]>(`/watch/areas/${id}/history`).then(data=>{if(!stopped){const unique=new Map(data.map(row=>[row.created_at,row]));setHistory([...unique.values()].slice(-30))}}).catch(()=>{if(!stopped)setHistory([])});return()=>{stopped=true}},[id,updated]);
 return <section className="watch-history"><h2>Review priority through time</h2>{history.length?<><svg viewBox="0 0 330 70" role="img" aria-label={`${history.length} saved checks. These are review levels, not hazard probabilities.`}>{history.map((s,i)=>{const width=310/Math.max(8,history.length),height=s.level<0?6:12+s.level*13;return <rect key={s.created_at} x={10+i*(310/Math.max(8,history.length))} y={62-height} width={Math.max(3,width-4)} height={height} rx="2" fill={s.level<0?'#93a6b1':colors[s.level]}><title>{timeLabel(s.created_at)}: {s.level<0?'Unknown':labels[s.level]}</title></rect>})}</svg><p className="watch-small">{history.length} saved evidence checks · unknown stays separate from routine.</p></>:<p className="watch-small">The first saved check will start this history.</p>}</section>
}
