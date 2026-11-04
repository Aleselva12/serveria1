import { useRef, useState, type PointerEvent, type WheelEvent } from "react";
import type { Node } from "./model";

export type TreePoint = {node: Node; x: number; y: number; kind: "area"|"branch"|"star"};
export type TreeEdge = {from: string; to: string; kind: "child"|"flow"};
export const trunkLayout: Record<string,[number,number]> = {
  T1:[900,417], T2:[660,456], T8:[1120,464], T9:[994,520],
  T12:[724,558], T6:[571,614], T7:[647,692], T4:[1130,587],
  T5:[887,633], T13:[1205,694], T10:[736,760], T11:[1021,763], T3:[900,856],
};
/** These are design-level links, never runtime-certified dependencies. */
export const trunkFlows: Record<string,string[]> = {
  T1:["T2","T8","T9"], T9:["T4"], T4:["T5"], T13:["T4"],
  T6:["T7"], T10:["T11"], T3:["T5","T11"],
};
const groupCode = (n:Node) => n.code || (n.id==="programmi"?"D":n.id==="macchine"?"F":n.id);
const byCode = (a:Node,b:Node) => groupCode(a).localeCompare(groupCode(b),"it",{numeric:true});
/** Horizontal canopies above, broad roots below, a free constellation as the trunk. */
export function layout(nodes:Node[]) {
  const points:TreePoint[]=[], edges:TreeEdge[]=[];
  const append=(node:Node,x:number,y:number,kind:TreePoint["kind"])=>points.push({node,x,y,kind});
  const trunk=nodes.filter(n=>n.parent==="tronco").sort(byCode);
  for(const n of trunk){const [x,y]=trunkLayout[n.id]||[900,630];append(n,x,y,"star");}
  const branchGroups=nodes.filter(n=>n.role==="ramo").sort(byCode);
  branchGroups.forEach((group,i)=>{
    const x=115+i*262, y=292+Math.abs(i-3)*8;
    append(group,x,y,"branch");
    nodes.filter(n=>n.parent===group.id && n.classification==="star").sort(byCode).forEach((n,j)=>{
      const col=j%2===0?-53:53;
      const ny=106+Math.floor(j/2)*80+(j%2)*13;
      append(n,x+col,ny,"star");edges.push({from:group.id,to:n.id,kind:"child"});
    });
  });
  const rootGroups=nodes.filter(n=>n.parent==="radici").sort(byCode);
  rootGroups.forEach((group,i)=>{
    const x=164+i*293,y=1121-Math.abs(i-2.5)*7;
    append(group,x,y,"area");
    nodes.filter(n=>n.parent===group.id && n.classification==="star").sort(byCode).forEach((n,j)=>{
      append(n,x+(j%2===0?-57:57),1230+Math.floor(j/2)*91+(j%2)*14,"star");
      edges.push({from:group.id,to:n.id,kind:"child"});
    });
  });
  for(const n of trunk)for(const target of trunkFlows[n.id]||[])if(trunk.some(t=>t.id===target))edges.push({from:n.id,to:target,kind:"flow"});
  return {points,edges};
}
type Props = {
  nodes:Node[]; selected:string; onSelect:(id:string)=>void;
  priority:(n:Node)=>string; visible:(n:Node)=>boolean; related?:{from:string;to:string}[];
};
const WIDTH=1800,HEIGHT=1450;
export default function Constellation({nodes,selected,onSelect,priority,visible,related=[]}:Props){
  const [zoom,setZoom]=useState(1),[pan,setPan]=useState({x:0,y:0});
  const drag=useRef<{x:number;y:number;px:number;py:number}|null>(null);
  const {points,edges}=layout(nodes);
  const byId=new Map(points.map(p=>[p.node.id,p]));
  const selectedPoint=byId.get(selected);
  const reset=()=>{setZoom(1);setPan({x:0,y:0});};
  const onDown=(e:PointerEvent<SVGSVGElement>)=>{
    if((e.target as Element).closest("[data-node]"))return;
    drag.current={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y};
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove=(e:PointerEvent<SVGSVGElement>)=>{
    if(!drag.current)return;
    const rect=e.currentTarget.getBoundingClientRect();
    setPan({x:drag.current.px+(e.clientX-drag.current.x)*WIDTH/rect.width,
      y:drag.current.py+(e.clientY-drag.current.y)*HEIGHT/rect.height});
  };
  const onWheel=(e:WheelEvent<SVGSVGElement>)=>{
    e.preventDefault();
    setZoom(v=>Math.max(.75,Math.min(3.6,v*(e.deltaY>0?.92:1.08))));
  };
  const labels=(p:TreePoint)=>{
    const raw=p.node.title.replace(/^[A-Z][\d.]* · /,"");
    const cap=p.kind!=="star"?26:24;
    const words=raw.split(" "),lines:string[]=[];
    for(const word of words){
      const i=lines.length-1;
      if(i<0||lines[i].length+word.length+1>cap)lines.push(word);
      else lines[i]+=" "+word;
    }
    return lines.slice(0,3);
  };
  return <section className="rm2-space" aria-label="Costellazione architetturale Cora">
    <div className="rm2-spacebar">
      <span><i className="rm2-live"/> RADICI <b>→</b> TRONCO <b>→</b> RAMI</span>
      <div>
        <button type="button" onClick={()=>setZoom(z=>Math.min(3.6,z*1.2))} aria-label="Ingrandisci">+</button>
        <button type="button" onClick={()=>setZoom(z=>Math.max(.75,z/1.2))} aria-label="Riduci">−</button>
        <button type="button" onClick={reset} aria-label="Ripristina inquadratura">Ripristina</button>
      </div>
    </div>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label="Albero di Cora: stelle del tronco libere, radici e rami distinti" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onWheel={onWheel}>
      <defs>
        <radialGradient id="rm2-spaceglow"><stop stopColor="#1e625c" stopOpacity=".28"/><stop offset="1" stopColor="#07121b" stopOpacity="0"/></radialGradient>
        <filter id="rm2-halo" x="-250%" y="-250%" width="600%" height="600%"><feGaussianBlur stdDeviation="8"/></filter>
      </defs>
      <ellipse cx="900" cy="680" rx="740" ry="630" fill="url(#rm2-spaceglow)"/>
      <g transform={`translate(${pan.x+900*(1-zoom)} ${pan.y+720*(1-zoom)}) scale(${zoom})`}>
        <path className="rm2-spine" d="M900 340 C875 485 920 590 895 750 S900 972 900 1020"/>
        {points.filter(p=>p.kind==="branch").map(p=><path key={"b"+p.node.id} className="rm2-struct" d={`M900 344 Q${(900+p.x)/2} 283 ${p.x} ${p.y}`}/>)}
        {points.filter(p=>p.kind==="area").map(p=><path key={"a"+p.node.id} className="rm2-struct" d={`M900 1028 Q${(900+p.x)/2} 1088 ${p.x} ${p.y}`}/>)}
        {edges.map(e=>{
          const a=byId.get(e.from),b=byId.get(e.to);if(!a||!b)return null;
          return <path key={e.from+"|"+e.to} className={e.kind==="flow"?"rm2-flow":"rm2-struct"} d={e.kind==="child"?`M${a.x} ${a.y} Q${(a.x+b.x)/2} ${(a.y+b.y)/2} ${b.x} ${b.y}`:`M${a.x} ${a.y} L${b.x} ${b.y}`}/>;
        })}
        {related.map((e,i)=>{
          const a=byId.get(e.from),b=byId.get(e.to);
          if(!a||!b||e.from===e.to)return null;
          return <path key={"relation"+i} className="rm2-related" d={`M${a.x} ${a.y} L${b.x} ${b.y}`}/>;
        })}
        {selectedPoint&&<circle cx={selectedPoint.x} cy={selectedPoint.y} r="32" className="rm2-selection-ring"/>}
        {points.map(p=>{
          const tone=priority(p.node),found=visible(p.node),active=selected===p.node.id;
          const label=labels(p);
          return <g key={p.node.id} data-node={p.node.id} className={`rm2-point tone-${tone} ${active?"is-active":""} ${!found?"is-muted":""}`}
            role="button" tabIndex={0} aria-label={p.node.title} aria-pressed={active}
            onClick={()=>onSelect(p.node.id)}
            onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(p.node.id);}}}>
            <title>{p.node.title}</title>
            <circle cx={p.x} cy={p.y} r="30" fill="transparent"/>
            <circle className="rm2-halo" cx={p.x} cy={p.y} r={p.kind==="star"?17:23} filter="url(#rm2-halo)"/>
            <circle className="rm2-core" cx={p.x} cy={p.y} r={p.kind==="star"?7:12}/>
            <text x={p.x} y={p.y+(p.kind==="star"?32:39)} textAnchor="middle">
              {p.node.code&&<tspan x={p.x} className="rm2-code">{p.node.code}</tspan>}
              {label.map((part,i)=><tspan key={i} x={p.x} dy={i===0?(p.node.code?19:0):17}>{part}</tspan>)}
            </text>
          </g>;
        })}
      </g>
    </svg>
    <div className="rm2-space-foot"><span>{zoom.toFixed(1)}× · trascina per muoverti</span><span>{points.length} punti principali · pianeti e lune nella scheda</span></div>
  </section>;
}
