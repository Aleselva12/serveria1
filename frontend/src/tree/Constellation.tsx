import {useState,useRef} from 'react';
import type {Node} from './model';
type Point={node:Node;x:number;y:number;kind:string};
export function layout(nodes:Node[]){
 const points:Point[]=[],edges:{from:string;to:string}[]=[];
 const add=(node:Node,x:number,y:number,kind:string)=>points.push({node,x,y,kind});
 const trunk=nodes.filter(n=>n.parent==='tronco');trunk.forEach((n,i)=>{add(n,900,560+i*24,'star');if(i)edges.push({from:trunk[i-1].id,to:n.id})});
 const branches=nodes.filter(n=>n.role==='ramo').sort((a,b)=>a.title.localeCompare(b.title));
 branches.forEach((g,i)=>{
 const x=130+i*255,y=470+Math.abs(i-3)*18;add(g,x,y,'branch');edges.push({from:trunk[0].id,to:g.id});
 const stars=nodes.filter(n=>n.parent===g.id);
 stars.forEach((n,j)=>{add(n,x+(j%2?18:-18),90+j*72,'star');edges.push({from:g.id,to:n.id})});
 });
 const roots=nodes.filter(n=>n.parent==='radici');
 roots.forEach((g,i)=>{const x=170+i*290;add(g,x,1010,'area');edges.push({from:trunk[trunk.length-1].id,to:g.id});
 const stars=nodes.filter(n=>n.parent===g.id);stars.forEach((n,j)=>{add(n,x+(j%2?25:-25),1100+j*78,'star');edges.push({from:g.id,to:n.id})});
 });return {points,edges};
}
export default function Constellation({nodes,selected,onSelect,priority,visible}:{nodes:Node[];selected:string;onSelect:(id:string)=>void;priority:(n:Node)=>string;visible:(n:Node)=>boolean}){
 const [focus,setFocus]=useState<string|null>(null),[zoom,setZoom]=useState(1),[pan,setPan]=useState({x:0,y:0});
 const drag=useRef<{x:number;y:number;px:number;py:number}|null>(null);
 const base=layout(nodes);
 let points=base.points,edges=base.edges;
 if(focus){const n=nodes.find(n=>n.id===focus)!;points=[{node:n,x:900,y:680,kind:'star'}];edges=[];
 const kids=nodes.filter(c=>c.parent===focus);
 kids.forEach((p,i)=>{const a=-Math.PI+(i+.5)*Math.PI*2/kids.length,x=900+420*Math.cos(a),y=670+370*Math.sin(a);points.push({node:p,x,y,kind:'planet'});edges.push({from:focus,to:p.id});
 const moons=nodes.filter(m=>m.parent===p.id);moons.forEach((m,j)=>{const ma=a+(j-(moons.length-1)/2)*.42;points.push({node:m,x:x+150*Math.cos(ma),y:y+140*Math.sin(ma),kind:'moon'});edges.push({from:p.id,to:m.id})});
 });}
 const byId=new Map(points.map(p=>[p.node.id,p]));
 function choose(p:Point){onSelect(p.node.id);if(p.kind==='star'){setFocus(p.node.id);setPan({x:0,y:0});setZoom(1)}}
 return <div className="constellation"><nav aria-label="Controlli mappa"><button onClick={()=>{setFocus(null);setZoom(1);setPan({x:0,y:0})}}>Albero completo</button><button aria-label="Ingrandisci" onClick={()=>setZoom(z=>Math.min(4,z*1.25))}>＋</button><button aria-label="Riduci" onClick={()=>setZoom(z=>Math.max(.6,z/1.25))}>−</button><button onClick={e=>{const host=e.currentTarget.closest('.constellation');if(document.fullscreenElement)void document.exitFullscreen();else void host?.requestFullscreen()}}>Pieno schermo</button><span>{focus?'Stella → pianeti → lune':'Radici → tronco → rami'} · trascina per esplorare</span></nav>
 <svg viewBox="0 0 1800 1450" aria-label={focus?'Sistema della stella selezionata':'Albero connesso di Cora'} role="group"
 onPointerDown={e=>{if((e.target as Element).closest('[data-node]'))return;drag.current={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y};e.currentTarget.setPointerCapture(e.pointerId)}}
 onPointerMove={e=>{if(drag.current){const k=1800/e.currentTarget.getBoundingClientRect().width;setPan({x:drag.current.px+(e.clientX-drag.current.x)*k,y:drag.current.py+(e.clientY-drag.current.y)*k})}}}
 onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}}>
 <defs><filter id="star-glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="4"/></filter><radialGradient id="nebula"><stop stopColor="#196f75" stopOpacity=".2"/><stop offset="1" stopColor="#07101d" stopOpacity="0"/></radialGradient></defs>
 <ellipse cx="450" cy="630" rx="650" ry="600" fill="url(#nebula)"/>
 <g transform={`translate(${pan.x+900*(1-zoom)} ${pan.y+660*(1-zoom)}) scale(${zoom})`}>
 {edges.map(e=>{const a=byId.get(e.from)!,b=byId.get(e.to)!;return <path key={e.from+e.to} className="tree-connection" d={`M${a.x},${a.y} C${a.x},${(a.y+b.y)/2} ${b.x},${(a.y+b.y)/2} ${b.x},${b.y}`}/>})}
 {points.map(p=>{const active=visible(p.node),color=priority(p.node),r=p.kind==='star'?7:p.kind==='moon'?3:5;const short=p.node.title.replace(/^[A-Z][\d.]* · /,'');return <g key={p.node.id} data-node={p.node.id} className={'constellation-node '+color} opacity={active?1:.18} role="button" tabIndex={0} aria-label={p.node.title} aria-pressed={selected===p.node.id} onClick={()=>choose(p)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(p)}}}>
 <title>{p.node.title}</title><circle cx={p.x} cy={p.y} r="22" fill="transparent"/><circle className="node-halo" cx={p.x} cy={p.y} r={r*2} filter="url(#star-glow)"/><circle className="node-core" cx={p.x} cy={p.y} r={r}/>{selected===p.node.id&&<circle cx={p.x} cy={p.y} r={r+7} fill="none" stroke="#fff"/>}
 <text x={p.x+(p.x===900?20:0)} y={p.y+(p.x===900?5:24)} textAnchor={p.x===900?'start':'middle'}>{(p.x===900?[short]:short.split(' ').reduce<string[]>((lines,w)=>{if(!lines.length||lines[lines.length-1].length+w.length>22)lines.push(w);else lines[lines.length-1]+=' '+w;return lines},[])).map((line,i)=><tspan key={i} x={p.x+(p.x===900?20:0)} dy={i?17:0}>{line}</tspan>)}</text></g>})}
 </g></svg></div>
}
