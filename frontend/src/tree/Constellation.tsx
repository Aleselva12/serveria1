import {useEffect,useRef,useState,type PointerEvent,type WheelEvent} from "react";
import {toneLabels} from "./roadmapEvidence";
import type {Node} from "./model";

export type TreePoint={node:Node;x:number;y:number;kind:"area"|"branch"|"star"|"planet"|"moon"};
export type TreeEdge={from:string;to:string;kind:"child"|"flow"};
export const trunkLayout:Record<string,[number,number]>={
 T1:[900,417],T2:[660,456],T8:[1120,464],T9:[994,520],
 T12:[724,558],T6:[571,614],T7:[647,692],T4:[1130,587],
 T5:[887,633],T13:[1205,694],T10:[736,760],T11:[1021,763],T3:[900,856],
};
/** Graphic connections only, not proven runtime calls. */
export const trunkFlows:Record<string,string[]>={
 T1:["T2","T8","T9"],T9:["T4"],T4:["T5"],T13:["T4"],
 T6:["T7"],T10:["T11"],T3:["T5","T11"],
};
const byCode=(a:Node,b:Node)=>(a.code||a.id).localeCompare(b.code||b.id,"it",{numeric:true});
/** A complete tree of responsibilities; trunk stars are free, not a dependency chain. */
export function layout(nodes:Node[]){
 const points:TreePoint[]=[],edges:TreeEdge[]=[];
 const add=(node:Node,x:number,y:number,kind:TreePoint["kind"])=>points.push({node,x,y,kind});
 const trunk=nodes.filter(n=>n.parent==="tronco").sort(byCode);
 for(const n of trunk){const [x,y]=trunkLayout[n.id]||[900,630];add(n,x,y,"star");}
 const branches=nodes.filter(n=>n.role==="ramo").sort(byCode);
 branches.forEach((g,i)=>{
  const x=115+i*262,y=292+Math.abs(i-3)*8;
  add(g,x,y,"branch");
  nodes.filter(n=>n.parent===g.id&&n.classification==="star").sort(byCode).forEach((n,j)=>{
   add(n,x+(j%2===0?-53:53),106+Math.floor(j/2)*80+(j%2)*13,"star");
   edges.push({from:g.id,to:n.id,kind:"child"});
  });
 });
 const roots=nodes.filter(n=>n.parent==="radici").sort(byCode);
 roots.forEach((g,i)=>{
  const x=164+i*293,y=1121-Math.abs(i-2.5)*7;
  add(g,x,y,"area");
  nodes.filter(n=>n.parent===g.id&&n.classification==="star").sort(byCode).forEach((n,j)=>{
   add(n,x+(j%2===0?-57:57),1230+Math.floor(j/2)*91+(j%2)*14,"star");
   edges.push({from:g.id,to:n.id,kind:"child"});
  });
 });
 for(const n of trunk)for(const id of trunkFlows[n.id]||[])if(trunk.some(t=>t.id===id))edges.push({from:n.id,to:id,kind:"flow"});
 return {points,edges};
}
/** A star-only view: no other stars, with all planets and their moons in a 2D orbit. */
export function focusLayout(nodes:Node[],id:string){
 const star=nodes.find(n=>n.id===id&&n.classification==="star");
 if(!star)return {points:[] as TreePoint[],edges:[] as TreeEdge[]};
 const points:TreePoint[]=[{node:star,x:900,y:720,kind:"star"}],edges:TreeEdge[]=[];
 const planets=nodes.filter(n=>n.parent===id&&n.classification==="planet");
 planets.forEach((p,i)=>{
  // Wide open, deterministic spacing; no random positions and no hidden objective planets.
  const a=-Math.PI/2+i*2*Math.PI/Math.max(1,planets.length);
  const x=900+490*Math.cos(a),y=720+405*Math.sin(a);
  points.push({node:p,x,y,kind:"planet"});edges.push({from:id,to:p.id,kind:"child"});
  const moons=nodes.filter(n=>n.parent===p.id&&n.classification==="moon");
  moons.forEach((m,j)=>{
   const spread=(j-(moons.length-1)/2)*.25,angle=a+spread;
   const mx=x+139*Math.cos(angle),my=y+127*Math.sin(angle);
   points.push({node:m,x:mx,y:my,kind:"moon"});edges.push({from:p.id,to:m.id,kind:"child"});
  });
 });
 return {points,edges};
}
type Props={
 nodes:Node[];selected:string;focusId?:string|null;onFocusChange?:(id:string|null)=>void;
 onSelect:(id:string)=>void;priority:(n:Node)=>string;visible:(n:Node)=>boolean;
 related?:{from:string;to:string}[];
};
const WIDTH=1800,HEIGHT=1450, CX=900,CY=725;
function pointAt(e:{clientX:number;clientY:number;currentTarget:SVGSVGElement}){
 const ctm=e.currentTarget.getScreenCTM();
 if(ctm){const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(ctm.inverse());return {x:p.x,y:p.y};}
 return {x:CX,y:CY};
}
const titleOf=(n:Node)=>n.title.replace(/^[A-Z][\d.]* · /,"");
export default function Constellation({nodes,selected,focusId=null,onFocusChange,onSelect,priority,visible,related=[]}:Props){
 const [zoom,setZoom]=useState(1),[pan,setPan]=useState({x:0,y:0});
 const pointers=useRef(new Map<number,{x:number;y:number}>());
 const drag=useRef<{x:number;y:number;px:number;py:number}|null>(null);
 const pinch=useRef<{distance:number;zoom:number}|null>(null);
 useEffect(()=>{setPan({x:0,y:0});setZoom(1);drag.current=null;pinch.current=null;pointers.current.clear();},[focusId]);
 const {points,edges}=focusId?focusLayout(nodes,focusId):layout(nodes);
 const byId=new Map(points.map(p=>[p.node.id,p])), selectedPoint=byId.get(selected);
 const reset=()=>{setZoom(1);setPan({x:0,y:0});};
 const applyZoom=(factor:number,anchor={x:CX,y:CY})=>{
  const z=Math.max(.58,Math.min(4.5,zoom*factor));
  // Keep the pointer's world position under the pointer rather than zooming only at the center.
  const world={x:(anchor.x-pan.x-CX*(1-zoom))/zoom,y:(anchor.y-pan.y-CY*(1-zoom))/zoom};
  setPan({x:anchor.x-CX*(1-z)-z*world.x,y:anchor.y-CY*(1-z)-z*world.y});
  setZoom(z);
 };
 const onDown=(e:PointerEvent<SVGSVGElement>)=>{
  if((e.target as Element).closest("[data-node]"))return;
  pointers.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
  e.currentTarget.setPointerCapture(e.pointerId);
  if(pointers.current.size===1)drag.current={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y};
  else if(pointers.current.size===2){
   const [a,b]=[...pointers.current.values()];
   pinch.current={distance:Math.hypot(a.x-b.x,a.y-b.y),zoom};
   drag.current=null;
  }
 };
 const onMove=(e:PointerEvent<SVGSVGElement>)=>{
  if(!pointers.current.has(e.pointerId))return;
  pointers.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.current.size===2&&pinch.current){
   const [a,b]=[...pointers.current.values()];
   const ratio=Math.hypot(a.x-b.x,a.y-b.y)/Math.max(1,pinch.current.distance);
   const z=Math.max(.58,Math.min(4.5,pinch.current.zoom*ratio));
   setZoom(z);return;
  }
  if(drag.current){
   const rect=e.currentTarget.getBoundingClientRect();
   const scale=Math.min(rect.width/WIDTH,rect.height/HEIGHT);
   setPan({x:drag.current.px+(e.clientX-drag.current.x)/scale,y:drag.current.py+(e.clientY-drag.current.y)/scale});
  }
 };
 const onUp=(e:PointerEvent<SVGSVGElement>)=>{
  pointers.current.delete(e.pointerId);drag.current=null;pinch.current=null;
  if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
 };
 const onWheel=(e:WheelEvent<SVGSVGElement>)=>{
  e.preventDefault();applyZoom(e.deltaY>0?.90:1.11,pointAt(e));
 };
 const labels=(n:Node,kind:TreePoint["kind"])=>{
  const cap=kind==="moon"?20:kind==="star"?23:25;const lines:string[]=[];
  for(const w of titleOf(n).split(" ")){const i=lines.length-1;
   if(i<0||lines[i].length+w.length+1>cap)lines.push(w);else lines[i]+=" "+w;
  }
  return lines.slice(0,kind==="moon"?2:3);
 };
 const draw=(p:TreePoint)=>{
  const active=selected===p.node.id,objective=p.node.status==="planned"||p.node.status==="idea";
  const tone=priority(p.node),label=labels(p.node,p.kind);
  const radius=p.kind==="star"?(focusId?20:10):p.kind==="planet"?12:p.kind==="moon"?6:15;
  const highlight=visible(p.node);
  return <g key={p.node.id} data-node={p.node.id}
   className={`rm2-point tone-${tone} ${objective?"is-objective":""} ${active?"is-active":""} ${!highlight?"is-muted":""} ${p.kind==="moon"?"is-moon":""}`}
   role="button" tabIndex={0} aria-pressed={active} aria-label={p.node.title+" · "+toneLabels[tone]}
   onClick={()=>onSelect(p.node.id)}
   onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(p.node.id);}}}>
   <title>{p.node.title+" · "+toneLabels[tone]}{objective?" · obiettivo non ancora implementato":""}</title>
   <circle cx={p.x} cy={p.y} r="35" fill="transparent"/>
   <circle className="rm2-halo" cx={p.x} cy={p.y} r={radius*2.5} filter="url(#rm2-halo)"/>
   {objective&&<circle className="rm2-objective-ring" cx={p.x} cy={p.y} r={radius+9}/>}
   <circle className="rm2-core" cx={p.x} cy={p.y} r={radius}/>
   <text x={p.x} y={p.y+(p.kind==="moon"?25:p.kind==="star"?(focusId?47:32):37)} textAnchor="middle">
    {p.node.code&&<tspan className="rm2-code" x={p.x}>{p.node.code}</tspan>}
    {label.map((part,i)=><tspan key={i} x={p.x} dy={i===0&&p.node.code?19:i===0?0:17}>{part}</tspan>)}
    {objective&&p.kind==="star"&&<tspan className="rm2-objective-label" x={p.x} dy="17">◇ OBIETTIVO</tspan>}
   </text>
  </g>;
 };
 return <section className={"rm2-space "+(focusId?"rm2-focused":"")} aria-label="Costellazione architetturale Cora">
  <div className="rm2-spacebar">
   <span><i className="rm2-live"/>{focusId?"STELLA · PIANETI · LUNE":"RADICI → TRONCO → RAMI"}</span>
   <div>
    {focusId&&<button type="button" onClick={()=>onFocusChange?.(null)} aria-label="Torna all'albero completo">← Tutta la mappa</button>}
    <button type="button" onClick={()=>applyZoom(1.2)} aria-label="Ingrandisci">+</button>
    <button type="button" onClick={()=>applyZoom(1/1.2)} aria-label="Riduci">−</button>
    <button type="button" onClick={reset} aria-label="Centra la vista">Centra</button>
   </div>
  </div>
  <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group"
   aria-label={focusId?"Vista isolata della stella e dei suoi pianeti e lune":"Albero Cora con stelle obiettivo evidenziate"}
   onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onWheel={onWheel}
   onDoubleClick={e=>{if(!(e.target as Element).closest("[data-node]"))reset();}}>
   <defs>
    <radialGradient id="rm2-spaceglow"><stop stopColor="#1e625c" stopOpacity=".28"/><stop offset="1" stopColor="#07121b" stopOpacity="0"/></radialGradient>
    <filter id="rm2-halo" x="-250%" y="-250%" width="600%" height="600%"><feGaussianBlur stdDeviation="8"/></filter>
   </defs>
   <ellipse cx="900" cy="680" rx="740" ry="630" fill="url(#rm2-spaceglow)"/>
   <g className="rm2-scene" key={focusId||"overview"} transform={`translate(${pan.x+CX*(1-zoom)} ${pan.y+CY*(1-zoom)}) scale(${zoom})`}>
    {!focusId&&<>
     <path className="rm2-spine" d="M900 340 C875 485 920 590 895 750 S900 972 900 1020"/>
     {points.filter(p=>p.kind==="branch").map(p=><path key={"b"+p.node.id} className="rm2-struct" d={`M900 344 Q${(900+p.x)/2} 283 ${p.x} ${p.y}`}/>)}
     {points.filter(p=>p.kind==="area").map(p=><path key={"a"+p.node.id} className="rm2-struct" d={`M900 1028 Q${(900+p.x)/2} 1088 ${p.x} ${p.y}`}/>)}
    </>}
    {edges.map(e=>{const a=byId.get(e.from),b=byId.get(e.to);if(!a||!b)return null;
     return <path key={e.from+"|"+e.to} className={e.kind==="flow"?"rm2-flow":"rm2-struct"}
      d={focusId?`M${a.x} ${a.y} L${b.x} ${b.y}`:e.kind==="child"?`M${a.x} ${a.y} Q${(a.x+b.x)/2} ${(a.y+b.y)/2} ${b.x} ${b.y}`:`M${a.x} ${a.y} L${b.x} ${b.y}`}/>;
    })}
    {!focusId&&related.map((e,i)=>{const a=byId.get(e.from),b=byId.get(e.to);
     return a&&b&&e.from!==e.to?<path key={"relation"+i} className="rm2-related" d={`M${a.x} ${a.y} L${b.x} ${b.y}`}/>:null;
    })}
    {selectedPoint&&<circle className="rm2-selection-ring" cx={selectedPoint.x} cy={selectedPoint.y} r={focusId?42:26}/>}
    {points.map(draw)}
   </g>
  </svg>
  <div className="rm2-space-foot"><span>{zoom.toFixed(1)}× · trascina / rotella / due dita</span><span>{focusId?`${points.length-1} pianeti e lune · nessun'altra stella`:`${points.length} punti · apri una stella`}</span></div>
 </section>;
}
