import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, ChevronRight,
  CircleHelp, Clock3, Copy, Download, GitBranch, Layers3, Orbit, Search, Target,
} from "lucide-react";
import planSource from "./cora-plan.snapshot.json";
import { api, type HealthDashboardData, type HealthCheckDefinition, type HealthResult } from "../services/api";
import { homeRoadmap } from "../services/connections";
import { checks, type Node } from "./model";
import { closure } from "./closure";
import atlasEvidence from "./atlas-evidence.json";
import Constellation from "./Constellation";
import "./tree.css";

type Relation = {from:string;to:string;kind:string;note:string;status?:string};
type Source = {nodes:Node[];relations:Relation[];revision:string;nextWork:string[]};
const source=planSource as Source;
const nodes:Node[]=source.nodes;
const byId=new Map(nodes.map(n=>[n.id,n]));
const childIndex=new Map<string,Node[]>();
for (const n of nodes) if(n.parent) childIndex.set(n.parent,[...(childIndex.get(n.parent)||[]),n]);
const children=(id:string)=>childIndex.get(id)||[];
const stars=nodes.filter(n=>n.classification==="star");
const rootFor=(n:Node):Node=>{
  let current=n;
  while(current.parent&&current.classification!=="star") current=byId.get(current.parent)||current;
  return current;
};
const ancestry=(n:Node):Node[]=>{
  const result:Node[]=[];let current:Node|undefined=n;
  while(current){result.unshift(current);current=current.parent?byId.get(current.parent):undefined;}
  return result;
};
const hasAncestor=(n:Node,id:string)=>ancestry(n).some(a=>a.id===id);
const implementation:Record<string,string>={
  present:"Presente nel codice",partial:"Parziale / da collaudare",
  planned:"Da realizzare",idea:"Idea da valutare",unverified:"Da verificare",
};
const tones:Record<string,string>={
  unknown:"Da valutare",ok:"Funzione collaudata",plan:"Lavoro previsto",
  minor:"Attenzione",problem:"Test fallito",
};
const relNames:Record<string,string>={
  uses:"Utilizza",depends_on:"Dipende da",
  communicates_with:"Comunica con",produces_for:"Produce dati per",
};
const formatDate=(s?:string|null)=>{
  if(!s||Number.isNaN(Date.parse(s)))return "Data non disponibile";
  return new Date(s).toLocaleString("it-IT");
};
function evidenceStatus(def:HealthCheckDefinition|undefined,result:HealthResult|undefined){
  if(!def||!result||!Number.isFinite(Date.parse(result.at)))return "unknown";
  if(def.automated&&Date.now()-Date.parse(result.at)>10*60*1000)return "stale";
  if(result.status==="fail")return "fail";
  if(result.status==="pass")return "pass";
  return "unknown";
}
/** A red star requires actual check failure; orange notes are issues to investigate, not proven outages.
 * A green star requires an up-to-date functional E2E run with commit+environment, and no missing mapped checks.
 */
export function starTone(n:Node,health:HealthDashboardData|null):string{
  if(n.priority&&n.priority!=="unknown")return n.priority;
  if(n.classification!=="star")return "unknown";
  const ids=checks[n.id]||[];
  const evidence=ids.map(id=>({def:health?.catalog.find(c=>c.id===id),result:health?.latest[id]}));
  if(evidence.some(e=>evidenceStatus(e.def,e.result)==="fail"))return "problem";
  if(n.knownIssues?.length)return "minor";
  if(n.status==="planned"||n.status==="idea")return "unknown";
  if(ids.length&&evidence.every(e=>evidenceStatus(e.def,e.result)==="pass")&&
    evidence.some(e=>e.def?.kind==="e2e"&&e.result?.commit&&e.result?.environment))return "ok";
  if(n.timeline?.future?.length)return "plan";
  return "unknown";
}
export default function TreeHome(){
  const [selectedId,setSelected]=useState("T1");
  const [tab,setTab]=useState<"present"|"issues"|"future"|"past">("present");
  const [openPlanet,setOpenPlanet]=useState<string|null>(null);
  const [query,setQuery]=useState("");
  const [group,setGroup]=useState("all");
  const [mode,setMode]=useState<"all"|"issues"|"future">("all");
  const [view,setView]=useState<"map"|"list">("map");
  const [health,setHealth]=useState<HealthDashboardData|null>(null);
  const [healthError,setHealthError]=useState("");
  const [copied,setCopied]=useState(false);
  useEffect(()=>{
    let active=true,pending=false;
    async function refresh(){
      if(pending)return;pending=true;
      try {
        const response=await api.healthDashboard();
        if(active){setHealth(response);setHealthError("");}
      }catch {
        if(active){setHealth(null);setHealthError("Registro dei controlli non raggiungibile; non è un esito negativo dei singoli servizi.");}
      }finally{pending=false;}
    }
    void refresh();const timer=window.setInterval(()=>void refresh(),30000);
    return()=>{active=false;clearInterval(timer);};
  },[]);
  const selected=byId.get(selectedId)||byId.get("T1")!;
  const root=rootFor(selected);
  const tone=(n:Node)=>starTone(n,health);
  const selectedTone=tone(root);
  const relationRows=source.relations.filter(r=>r.from===root.id||r.to===root.id);
  const mappedChecks=checks[root.id]||[];
  const healthCatalog=health?.catalog||[];
  const matching=useMemo(()=>{
    const q=query.trim().toLocaleLowerCase("it");
    const descendants=(n:Node):string=>{
      const values=[n.id,n.title,n.note||"",...(n.knownIssues||[]),...(n.timeline?.future||[])];
      const walk=(id:string):void=>{for(const c of children(id)){values.push(c.title,c.note||"");walk(c.id);}};
      walk(n.id);return values.join(" ").toLocaleLowerCase("it");
    };
    return stars.filter(n=>
      (group==="all"||group==="T"&&n.parent==="tronco"||group!=="T"&&hasAncestor(n,group))&&
      (!q||descendants(n).includes(q))&&
      (mode==="all"||mode==="issues"&&(n.knownIssues?.length||tone(n)==="problem")||
       mode==="future"&&(n.status==="planned"||n.status==="idea"||Boolean(n.timeline?.future?.length)))
    );
  // Health changes are reflected when the response refreshes; no separate test execution.
  },[query,group,mode,health]);
  const found=new Set(matching.map(n=>n.id));
  const visible=(n:Node)=>n.classification!=="star"||found.has(n.id);
  const choose=(id:string)=>{
    if(!byId.has(id))return;setSelected(id);setOpenPlanet(null);setTab("present");
  };
  const jump=(id:string)=>{
    setGroup("all");setMode("all");setQuery("");choose(id);
  };
  const exportData=()=>{
    const json=JSON.stringify({schema:source.revision,source:"ServerIA frontend snapshot",nodes:source.nodes,relations:source.relations},null,2);
    const url=URL.createObjectURL(new Blob([json],{type:"application/json"}));
    const anchor=document.createElement("a");anchor.href=url;anchor.download="cora-roadmap-v2.json";anchor.click();
    URL.revokeObjectURL(url);
  };
  const copyOutline=async()=>{
    const lines=stars.map(s=>`${s.code||s.id} — ${s.title} · ${implementation[s.status||"unverified"]||"Da verificare"}\n${(s.knownIssues||[]).map(v=>"  Problema: "+v).join("\n")}\n${(s.timeline?.future||[]).map(v=>"  Obiettivo: "+v).join("\n")}`);
    try{await navigator.clipboard.writeText(lines.join("\n\n"));setCopied(true);}catch{setCopied(false);}
  };
  const goalRefs=root.roadmapRefs||[];
  const goals=homeRoadmap.goals.filter(g=>goalRefs.includes(g.id));
  const issues=root.knownIssues||[];
  const otherIssues=mappedChecks.filter(id=>{
    const def=healthCatalog.find(c=>c.id===id);
    return evidenceStatus(def,health?.latest[id])==="fail";
  });
  const relations=relationRows.map(r=>{
    const otherId=r.from===root.id?r.to:r.from;
    return {link:r,other:byId.get(otherId),outgoing:r.from===root.id};
  }).filter(r=>r.other);
  const scope=ancestry(root).map(n=>n.code||n.title).join(" / ");
  const areaGroups=[...nodes.filter(n=>n.parent==="radici"),...nodes.filter(n=>n.role==="ramo")];
  const leftGroups=[
    {id:"all",label:"Tutta la costellazione"},
    {id:"T",label:"T · Tronco condiviso"},
    ...areaGroups.map(n=>({id:n.id,label:(n.code||n.id)+" · "+n.title.replace(/^[A-Z][\d.]* · /,"")})),
  ];
  const firstStar=(id:string)=>stars.find(s=>hasAncestor(s,id))?.id;
  const verified=evidenceStatus;
  return <section className="rm2-page" aria-label="Direzione Cora - Roadmap V2">
    <header className="rm2-header">
      <a href="#home" className="rm2-brand"><ArrowLeft size={17}/> SERVERIA <span>· DIREZIONE</span></a>
      <div className="rm2-intro"><small>EVOLUTION / PROJECT ATLAS</small><h1>Roadmap<span>.</span></h1>
        <p>Radici → tronco → rami. Una mappa per capire dove intervenire, cosa manca e quali risultati sono verificati.</p>
      </div>
      <div className="rm2-header-actions">
        <button onClick={()=>void copyOutline()} type="button"><Copy size={15}/>{copied?"Copiato":"Copia schema"}</button>
        <button onClick={exportData} type="button"><Download size={15}/>Esporta JSON</button>
      </div>
    </header>
    <div className="rm2-metrics">
      <span><b>6</b> RADICI / 14 STELLE</span><span><b>13</b> TRONCO</span>
      <span><b>7</b> RAMI / 18 STELLE</span><span><b>151</b> PIANETI · <b>304</b> LUNE</span>
    </div>
    <div className="rm2-top-controls">
      <div className="rm2-view-switch"><button type="button" aria-pressed={view==="map"} onClick={()=>setView("map")}><Orbit size={15}/>Costellazione</button><button type="button" aria-pressed={view==="list"} onClick={()=>setView("list")}><Layers3 size={15}/>Elenco</button></div>
      <div className="rm2-status-filter" role="group" aria-label="Filtro lavoro">
        <button aria-pressed={mode==="all"} onClick={()=>setMode("all")}>Tutti</button>
        <button aria-pressed={mode==="issues"} onClick={()=>setMode("issues")}>Problemi e attenzioni</button>
        <button aria-pressed={mode==="future"} onClick={()=>setMode("future")}>Da fare / futuri</button>
      </div>
      <p>Realizzazione ≠ salute. Colori riferiti alle prove disponibili o alle attenzioni documentate.</p>
    </div>
    <div className="rm2-workspace">
      <aside className="rm2-sidebar">
        <label className="rm2-search"><Search size={16}/><input aria-label="Cerca stella, pianeta, problema o obiettivo" placeholder="Cerca stelle, problemi, obiettivi…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <div className="rm2-side-label"><GitBranch size={14}/> MAPPA E AREE</div>
        <nav className="rm2-group-nav" aria-label="Aree dell'albero">
          {leftGroups.map(g=><button type="button" aria-pressed={group===g.id} key={g.id} onClick={()=>setGroup(g.id)}>{g.label}<span>{g.id==="all"?45:stars.filter(s=>g.id==="T"?s.parent==="tronco":hasAncestor(s,g.id)).length}</span></button>)}
        </nav>
        <div className="rm2-side-label">STELLE <span>{matching.length} / 45</span></div>
        <div className="rm2-star-index">
          {matching.map(n=><button type="button" key={n.id} onClick={()=>choose(n.id)} aria-pressed={root.id===n.id}>
            <i className={"rm2-dot tone-"+tone(n)}/><span><b>{n.code||n.id}</b> · {n.title.replace(/^[A-Z][\d.]* · /,"")}</span><ChevronRight size={13}/>
          </button>)}
          {!matching.length&&<p>Nessuna stella corrispondente. Azzera i filtri.</p>}
        </div>
      </aside>
      <div className="rm2-center">
        {view==="map"?<Constellation nodes={nodes} selected={root.id} onSelect={choose} priority={tone} visible={visible} related={source.relations.filter(r=>r.from===root.id||r.to===root.id)}/>:
          <div className="rm2-list"><h2>Componenti e responsabilità</h2><p>Vista alternativa della stessa mappa: non una seconda roadmap.</p>
            {["radici","tronco","rami"].map(level=><section key={level}><h3>{level.toUpperCase()}</h3><div>{matching.filter(n=>level==="tronco"?n.parent==="tronco":level==="radici"?hasAncestor(n,"radici"):!hasAncestor(n,"radici")&&n.parent!=="tronco").map(n=><button type="button" key={n.id} onClick={()=>choose(n.id)}><i className={"rm2-dot tone-"+tone(n)}/><span>{n.code} · {n.title.replace(/^[A-Z][\d.]* · /,"")}</span><ArrowRight size={14}/></button>)}</div></section>)}
          </div>}
      </div>
      <aside className="rm2-inspector" aria-label="Scheda della stella">
        <small className="rm2-inspect-path">{scope}</small>
        <div className="rm2-inspect-code">{root.code||root.id} · STELLA</div>
        <h2>{root.title.replace(/^[A-Z][\d.]* · /,"")}</h2>
        <div className="rm2-badges">
          <span className="rm2-impl">{implementation[root.status||"unverified"]||"Da verificare"}</span>
          <span className={"rm2-attention tone-"+selectedTone}><i className="rm2-dot"/>{tones[selectedTone]||"Da valutare"}</span>
        </div>
        <p className="rm2-caveat">I colori indicano l'attenzione richiesta. Una funzione nel codice non è necessariamente collaudata sul Debian.</p>
        <div className="rm2-tabs" role="tablist" aria-label="Tempo e problemi">
          {([
            ["present","Presente"],["issues","Problemi"],["future","Futuro"],["past","Storia"],
          ] as const).map(([key,label])=><button role="tab" type="button" key={key} aria-selected={tab===key} onClick={()=>setTab(key)}>{label}{key==="issues"&&issues.length>0?" · "+issues.length:""}</button>)}
        </div>
        <div className="rm2-tab-body">
          {tab==="present"&&<>
            <p>{root.note||"Descrizione operativa da verificare."}</p>
            {root.observations?.map((o,i)=><div className="rm2-observation" key={i}><CheckCircle2 size={15}/><div>{o.text}<small>Confermato dall'utente; non prova il commit installato.</small></div></div>)}
            <div className="rm2-section-head"><Orbit size={14}/> PIANETI <span>{children(root.id).length}</span></div>
            <div className="rm2-planets">{children(root.id).map(pl=><div key={pl.id} className="rm2-planet">
              <button type="button" aria-expanded={openPlanet===pl.id} onClick={()=>setOpenPlanet(openPlanet===pl.id?null:pl.id)}><Orbit size={14}/><span>{pl.title}</span>{openPlanet===pl.id?<ChevronDown size={14}/>:<ChevronRight size={14}/>}</button>
              {openPlanet===pl.id&&<div className="rm2-moonlist">{children(pl.id).map(m=><p key={m.id}><i className="rm2-moon"/>{m.title}</p>)}{!children(pl.id).length&&<p>Nessuna luna per questo pianeta.</p>}</div>}
            </div>)}</div>
          </>}
          {tab==="issues"&&<>
            {issues.length?<ul className="rm2-item-list">{issues.map(issue=><li key={issue}><AlertCircle size={15}/>{issue}</li>)}</ul>:<p>Nessun problema documentato. Non significa che tutti i test siano superati.</p>}
            {otherIssues.length>0&&<p className="rm2-test-fail">{otherIssues.length} test collegati segnalano un errore nel registro condiviso.</p>}
          </>}
          {tab==="future"&&<>
            {root.timeline?.future?.length?<ul className="rm2-item-list">{root.timeline.future.map(future=><li key={future}><Target size={15}/>{future}</li>)}</ul>:<p>Nessun obiettivo futuro documentato per questa stella.</p>}
            {goals.map(g=><div key={g.id} className="rm2-goal"><b>{g.id}</b><span>{g.label}</span><small>{g.state}</small></div>)}
            <div className="rm2-closure"><strong>Risultato verificabile richiesto</strong><p>{closure[root.id]||"Criterio puntuale ancora da definire; non segnare il punto come completato."}</p></div>
          </>}
          {tab==="past"&&<>
            {root.timeline?.past?.length?<ul className="rm2-item-list">{root.timeline.past.map((entry,i)=><li key={i}><Clock3 size={15}/>{entry.text||entry.commit||"Evento storico"} · {formatDate(entry.at)}</li>)}</ul>:<p>Nessun commit storico associato con evidenza verificabile. Non vengono inventate date o versioni.</p>}
            {root.earlierNote&&<div className="rm2-goal"><b>Nota precedente · data non nota</b><span>{root.earlierNote}</span></div>}
            {root.id==="D5"&&<div className="rm2-goal"><b>Prove CodeAtlas — ambiente separato</b><span>{atlasEvidence.environment}, commit {atlasEvidence.commit.slice(0,8)} · {atlasEvidence.cases.length} casi registrati</span><small>Non attestano il funzionamento del server Debian.</small></div>}
          </>}
        </div>
        <div className="rm2-inspect-bottom">
          <div className="rm2-section-head"><CheckCircle2 size={14}/> TEST COLLEGATI <span>{mappedChecks.length}</span></div>
          {healthError&&<p className="rm2-test-note">{healthError}</p>}
          {!health&&!healthError&&<p className="rm2-test-note">Caricamento registro condiviso…</p>}
          {mappedChecks.map(cid=>{
            const def=healthCatalog.find(c=>c.id===cid),result=health?.latest[cid],st=verified(def,result);
            return <div key={cid} className="rm2-check">
              <div><strong>{def?.title||cid}</strong><span className={"rm2-check-state "+st}>{st==="pass"?"Superato":st==="fail"?"Fallito":st==="stale"?"Scaduto":"Da verificare"}</span></div>
              <small>{def?def.kind+" · "+(def.automated?"automatico":"a richiesta"):"Controllo non esposto dal catalogo"}</small>
              <small>{result?formatDate(result.at)+" · "+(result.environment||"ambiente ignoto")+(result.commit?" · "+result.commit.slice(0,10):" · commit non disponibile"):"Nessun esito disponibile"}</small>
              {result?.detail&&<small>{result.detail}</small>}
            </div>;
          })}
          {!mappedChecks.length&&<p className="rm2-test-note">Nessun controllo associato a questa stella. Da progettare; non significa “tutto ok”.</p>}
          <div className="rm2-section-head"><GitBranch size={14}/> RELAZIONI <span>{relations.length}</span></div>
          {relations.map(({link,other,outgoing},i)=>other&&<button type="button" className="rm2-relation" key={i} onClick={()=>jump(other.id)}>
            <span>{outgoing?relNames[link.kind]||link.kind:"È collegato da"} {outgoing?"→":"←"}</span>
            <strong>{other.code||other.id} · {other.title.replace(/^[A-Z][\d.]* · /,"")}</strong>
            <small>{link.note}</small>
          </button>)}
          {!relations.length&&<p className="rm2-test-note">Nessuna relazione concettuale proposta.</p>}
          <small className="rm2-rel-caveat">Le relazioni sono ipotesi architetturali, non chiamate a runtime già provate.</small>
        </div>
      </aside>
    </div>
    <section className="rm2-footer-work"><div><small>PROSSIME PRIORITÀ</small><h2>W1 → W2 → W3</h2><p>La sequenza di lavoro già concordata, senza creare altre stelle.</p></div>
      <div>{source.nextWork.slice(0,3).map((w,i)=><button type="button" key={w} onClick={()=>jump(["T1","R5.2","G1"][i])}><b>W{i+1}</b><span>{w.replace(/^W\d\s*/,"")}</span><ArrowRight size={16}/></button>)}</div>
    </section>
    <footer className="rm2-footer"><CircleHelp size={14}/>{source.revision} · piano concettuale da qwe · risultati dei test letti dal registro unico, senza eseguirli due volte. <a href="#home">Torna alla Home</a></footer>
  </section>;
}
