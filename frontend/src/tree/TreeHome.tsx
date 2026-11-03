import {useEffect,useState} from 'react';
import plan from './cora-plan.snapshot.json';
import {api,type HealthDashboardData} from '../services/api';
import {severity,checks,type Node} from './model';
import './tree.css';
import {closure} from './closure';
import atlasEvidence from './atlas-evidence.json';
const nodes:Node[]=plan.nodes;
const byId=new Map(nodes.map(n=>[n.id,n]));
const children=(id:string)=>nodes.filter(n=>n.parent===id);
const groups=nodes.filter(n=>n.parent==='radici'||n.role==='tronco'||n.role==='ramo');
const legend:Record<string,string>=plan.legend, states:Record<string,string>=plan.stateLegend;
function star(n:Node):Node {return n.classification==='star'||!n.parent?n:star(byId.get(n.parent)!)}
export default function TreeHome(){
 const [id,select]=useState('T1'),[query,search]=useState(''),[mode,filter]=useState('all');
 const [health,setHealth]=useState<HealthDashboardData|null>(null),[error,err]=useState('');
 useEffect(()=>{let live=true, pending=false;async function refresh(){if(pending)return;pending=true;try{const d=await api.healthDashboard();if(live){setHealth(d);err('')}}catch{if(live){setHealth(null);err('Registro dei controlli non raggiungibile')}}finally{pending=false}} void refresh();const t=setInterval(refresh,30000);return()=>{live=false;clearInterval(t)}},[]);
 const failures=new Set(Object.keys(checks).filter(k=>checks[k].some(c=>health?.latest[c]?.status==='fail')));
 const priority=(n:Node)=>severity(n,nodes,failures);
 const selected=byId.get(id)!,root=star(selected);
 const path=(n:Node):string=>n.parent?path(byId.get(n.parent)!)+' › '+n.title:n.title;
 const related=plan.relations.filter(r=>r.from===id||r.to===id);
 const link=(n:Node)=><button key={n.id} onClick={()=>select(n.id)} className={'tree-item '+priority(n)}>{n.title}</button>;
 const match=(n:Node):boolean=>n.title.toLowerCase().includes(query.trim().toLowerCase())||children(n.id).some(match);
 const future=(n:Node):boolean=>['idea','planned'].includes(n.status||'')||n.priority==='plan';
 const goals=nodes.filter(n=>star(n).id===root.id&&future(n));
 return <section className="tree-page"><header><a href="#home">← Home</a><small>DIREZIONE CORA · V2</small><h1>Schema albero</h1><p>Seleziona una stella per esplorare pianeti, lune e verifiche.</p></header>
 <div className="tree-controls"><input aria-label="Cerca nella mappa" placeholder="Cerca anche nei pianeti e nelle lune…" value={query} onChange={e=>search(e.target.value)}/><select aria-label="Vista" value={mode} onChange={e=>filter(e.target.value)}><option value="all">Tutte le stelle</option><option value="future">Obiettivi e stelle grigie</option><option value="issues">Problemi</option></select></div>
 <div className="tree-layout"><div className="tree-space">{groups.map(g=>{const stars=children(g.id).filter(n=>match(n)&&(mode==='all'||(mode==='issues'?['problem','minor'].includes(priority(n)):priority(n)==='unknown'||nodes.some(d=>star(d).id===n.id&&future(d)))));return stars.length>0&&<section key={g.id}><small>{g.parent==='radici'?'RADICI':g.role==='ramo'?'RAMO':'TRONCO'}</small><h2>{g.title}</h2><div className="orbit" style={{height:Math.max(1,Math.ceil(stars.length/2))*58+20}}>
 <svg viewBox={`0 0 100 ${Math.ceil(stars.length/2)*58+20}`} preserveAspectRatio="none" aria-hidden="true">
 {stars.map((n,i)=>{const y=28+Math.floor(i/2)*58;return <path key={n.id} d={`M2 2 V${y-12} Q2 ${y} 7 ${y} H${i%2?54:8}`} fill="none" stroke="#586a83" strokeWidth="1" vectorEffect="non-scaling-stroke"/>})}</svg>
 {stars.map((n,i)=><button style={{left:i%2?'54%':'8%',top:10+Math.floor(i/2)*58}} className={'sky-star '+priority(n)} aria-pressed={root.id===n.id} key={n.id} onClick={()=>select(n.id)}><i/> {n.title}</button>)}</div></section>})}
 {query&&<section><h2>Risultati nei dettagli</h2>{nodes.filter(n=>n.parent&&n.title.toLowerCase().includes(query.toLowerCase())).map(link)}</section>}
 {mode==='issues'&&!nodes.some(n=>['minor','problem'].includes(priority(n)))&&<p>Nessun problema segnalato nelle evidenze disponibili.</p>}</div>
 <aside aria-live="polite"><div className="tree-legend">{Object.entries(legend).map(([k,v])=><span key={k} className={'tree-item '+k}>{v}</span>)}</div><small>{path(selected)}</small><h2>{selected.title}</h2><strong>{legend[priority(root)]} · stato della stella</strong><p>{states[selected.status||'unverified']}</p><p>{selected.note}</p>
 {selected.parent&&<button onClick={()=>select(selected.parent!)}>↑ {byId.get(selected.parent)?.title}</button>}
 <h3>{selected.classification==='star'?'Pianeti':selected.classification==='planet'?'Lune':'Elementi'}</h3>{children(id).map(link)}
 <h3>Origine dei problemi</h3>{nodes.some(n=>star(n).id===root.id&&(failures.has(n.id)||['minor','problem'].includes(n.priority||'')))?nodes.filter(n=>star(n).id===root.id&&(failures.has(n.id)||['minor','problem'].includes(n.priority||''))).map(link):<p>Nessuna anomalia segnalata.</p>}
 <h3>Cosa serve per chiudere questo punto</h3>
 <p>{closure[id]||'Criterio specifico da definire: quale risultato osservabile confermerà che questo punto è completo?'}</p>
 {!closure[id]&&id!==root.id&&closure[root.id]&&<small>Traguardo della stella: {closure[root.id]}</small>}
 <h3>Verifiche</h3>{root.id==='D5'&&<details><summary>Test Atlas · profili e associazioni delle prove</summary><p>{atlasEvidence.environment} · {atlasEvidence.at} · <a href={'https://github.com/'+atlasEvidence.repo+'/blob/'+atlasEvidence.commit+'/'+atlasEvidence.file}>sorgente {atlasEvidence.commit.slice(0,8)}</a></p>{atlasEvidence.cases.map(c=><p key={c.name}>{c.status} · {c.name}</p>)}<small>Questi casi verificano Atlas, non il server Debian.</small></details>}{error&&<p>{error}</p>}{(checks[id]||[]).map(c=>{const v=health?.latest[c];return <p key={c}><b>{health?.catalog.find(d=>d.id===c)?.title||c}</b><br/>{v?`${v.status} · ${v.detail} · ${v.environment} · ${v.commit||'commit non disponibile'} · ${v.at}`:'Nessun esito disponibile'}</p>})}{!checks[id]?.length&&<p>Collaudo da associare o aggiungere.</p>}
 <h3>Passato</h3><p>{selected.earlierNote||'Nessuna nota storica associata.'}</p><h3>Obiettivi della stella</h3>{goals.length?goals.map(link):<p>Nessun obiettivo futuro esplicito nei nodi.</p>}
 <h3>Collegamenti proposti</h3>{[...new Set([...(selected.trunkLinks||[]),...related.map(r=>r.from===id?r.to:r.from)])].map(k=>byId.has(k)&&link(byId.get(k)!))}
 </aside></div><details><summary>Prossimi lavori concordati</summary>{plan.nextWork.map((w,i)=><p key={w}><button onClick={()=>select(['T1','R5.2','G1'][i])}>{w} →</button></p>)}</details></section>
}
