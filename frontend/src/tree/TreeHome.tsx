import { useEffect, useMemo, useState, useCallback } from "react";
import {
  AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, ChevronRight,
  CircleHelp, Clock3, Copy, Download, GitBranch, Layers3, Orbit, Search, Target,
} from "lucide-react";
import planSource from "./cora-plan.snapshot.json";
import { api, apiBaseUrl, type HealthDashboardData } from "../services/api";
import { authenticatedFetch } from "../services/transport";
import { checkState, starTone, verifiedLiveE2E, toneLabels } from "./roadmapEvidence";
import { homeRoadmap } from "../services/connections";
import { checks, type Node } from "./model";
import { closure } from "./closure";
import atlasEvidence from "./atlas-evidence.json";
import NodeVerificationPanel from "./NodeVerificationPanel";
import Constellation from "./Constellation";
import RoadmapPriorities from "./RoadmapPriorities";
import {codeLinks,pageLinks,sourceUrl} from "./codeLinks";
import "./tree.css";

type Relation = {from:string;to:string;kind:string;note:string;status?:string};
type Source = {nodes:Node[];relations:Relation[];revision:string;nextWork:string[]};
const source=planSource as Source;
const workTargets:Record<string,string>={W1:"T1",W2:"R5.2",W3:"G1"};
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
/** Same installed-commit endpoint used by the Home; read-only, no additional test runner. */
async function activeRelease():Promise<string|null>{
  const response=await authenticatedFetch(apiBaseUrl+"/api/v1/system/update");
  if(!response.ok)return null;
  const data=await response.json() as {platform?:string;active_commit?:string};
  return data.platform==="server"&&/^[a-f0-9]{40}$/i.test(data.active_commit||"")
    ? data.active_commit!.toLowerCase():null;
}
export default function TreeHome(){
  const [selectedId,setSelected]=useState("T1");
  const [focusId,setFocusId]=useState<string|null>(null);
  const [tab,setTab]=useState<"present"|"issues"|"future"|"past">("present");
  const [openPlanet,setOpenPlanet]=useState<string|null>(null);
  const [query,setQuery]=useState("");
  const [group,setGroup]=useState("all");
  const [mode,setMode]=useState<"all"|"issues"|"future">("all");
  const [healthFilter,setHealthFilter]=useState("all");
  const [view,setView]=useState<"map"|"list">("map");
  const [health,setHealth]=useState<HealthDashboardData|null>(null);
  const [healthError,setHealthError]=useState("");
  const [activeCommit,setActiveCommit]=useState<string|null>(null);
  const [copied,setCopied]=useState(false);
  const [verificationRevision,setVerificationRevision]=useState(0);
  const refreshVerification=useCallback(()=>setVerificationRevision(v=>v+1),[]);
  useEffect(()=>{
    let active=true,pending=false;
    async function refresh(){
      if(pending)return;pending=true;
      try {
        const [dashboard,release]=await Promise.allSettled([api.healthDashboard(),activeRelease()]);
        if(active){
          if(dashboard.status==="fulfilled"){
            setHealth(dashboard.value);setHealthError("");
          }else{
            setHealth(null);
            setHealthError("Registro dei controlli non raggiungibile; non è un esito negativo dei singoli servizi.");
          }
          setActiveCommit(release.status==="fulfilled"?release.value:null);
        }
      }finally{pending=false;}
    }
    void refresh();const timer=window.setInterval(()=>void refresh(),30000);
    return()=>{active=false;clearInterval(timer);};
  },[verificationRevision]);
  const selected=byId.get(selectedId)||byId.get("T1")!;
  const root=rootFor(selected);
  const tone=(n:Node)=>starTone(n,health,activeCommit,checks,nodes);
  const selectedTone=tone(root);
  const counts=Object.fromEntries(Object.keys(toneLabels).map(key=>[key,stars.filter(n=>tone(n)===key).length]));
  const relationRows=source.relations.filter(r=>r.from===root.id||r.to===root.id);
  // The inspector reuses check IDs from the canonical registry; it never runs tests.
  const mappedChecks=[...new Set([...(checks[root.id]||[]),...(checks[selected.id]||[])])];
  const selectedEvidence=checks[selected.id]||[];
  const newlyObserved=selectedEvidence.some(cid=>{
    const def=health?.catalog.find(d=>d.id===cid),result=health?.latest[cid];
    return verifiedLiveE2E(def,result,activeCommit);
  });
  const healthCatalog=health?.catalog||[];
  const matching=useMemo(()=>{
    const q=query.trim().toLocaleLowerCase("it");
    const descendants=(n:Node):string=>{
      const values=[n.id,n.title,n.note||"",...(n.knownIssues||[]),...(n.timeline?.future||[])];
      const walk=(id:string):void=>{for(const c of children(id)){values.push(c.title,c.note||"");walk(c.id);}};
      walk(n.id);return values.join(" ").toLocaleLowerCase("it");
    };
    return stars.filter(n=>
      (healthFilter==="all"||tone(n)===healthFilter)&&
      (group==="all"||group==="T"&&n.parent==="tronco"||group!=="T"&&hasAncestor(n,group))&&
      (!q||descendants(n).includes(q))&&
      (mode==="all"||mode==="issues"&&(n.knownIssues?.length||tone(n)==="problem")||
       mode==="future"&&(n.status==="planned"||n.status==="idea"||Boolean(n.timeline?.future?.length)))
    );
  // Health changes are reflected when the response refreshes; no separate test execution.
  },[query,group,mode,health,activeCommit,healthFilter]);
  const found=new Set(matching.map(n=>n.id));
  const visible=(n:Node)=>n.classification!=="star"||found.has(n.id);
  const choose=(id:string)=>{
    let node=byId.get(id);
    if(!node)return;
    if(node.classification==="area"||node.role==="ramo"){
      node=stars.find(s=>hasAncestor(s,node!.id));
      if(!node)return;
    }
    const parent=rootFor(node);
    setSelected(node.id);
    setOpenPlanet(node.classification==="planet"?node.id:node.classification==="moon"?node.parent||null:null);
    setTab("present");
    if(parent.classification==="star")setFocusId(parent.id);
  };
  const showAll=()=>{
    setFocusId(null);setSelected(root.id);setOpenPlanet(null);
  };
  const jump=(id:string)=>{
    setGroup("all");setMode("all");setHealthFilter("all");setQuery("");choose(id);
  };
  const exportData=()=>{
    const json=JSON.stringify({
      schema:source.revision,
      source:"ServerIA frontend snapshot",
      projectStatus:{updatedAt:homeRoadmap.updatedAt,nextWork:homeRoadmap.nextWork},
      verification:{activeCommit,updatedAt:health?.updatedAt,stars:stars.map(n=>({id:n.id,tone:tone(n),checks:checks[n.id]||[]})),latest:health?.latest},
      nodes:source.nodes,
      relations:source.relations,
    },null,2);
    const url=URL.createObjectURL(new Blob([json],{type:"application/json"}));
    const anchor=document.createElement("a");anchor.href=url;anchor.download="cora-roadmap-v2.json";anchor.click();
    URL.revokeObjectURL(url);
  };
  const copyOutline=async()=>{
    const lines=stars.map(s=>`${s.code||s.id} — ${s.title} · ${implementation[s.status||"unverified"]||"Da verificare"}\n${(s.knownIssues||[]).map(v=>"  Problema: "+v).join("\n")}\n${(s.timeline?.future||[]).map(v=>"  Obiettivo: "+v).join("\n")}`);
    try{await navigator.clipboard.writeText(lines.join("\n\n"));setCopied(true);}catch{setCopied(false);}
  };
  const links=codeLinks[root.id]||[];
  const pageLink=pageLinks[root.id];
  const goalStars=stars.filter(n=>n.status==="planned"||n.status==="idea");
  const goalRefs=root.roadmapRefs||[];
  const goals=homeRoadmap.goals.filter(g=>goalRefs.includes(g.id));
  const workItems=[...homeRoadmap.nextWork].sort((a,b)=>a.order-b.order);
  const currentWork=workItems.find(w=>/PROSSIMO LAVORO/i.test(w.status))||
    workItems.find(w=>!/COMPLETATO/i.test(w.status));
  const issues=root.knownIssues||[];
  const otherIssues=mappedChecks.filter(id=>{
    const def=healthCatalog.find(c=>c.id===id);
    return checkState(def,health?.latest[id],activeCommit)==="fail";
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
  const verified=checkState;
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
      <p>Realizzazione ≠ salute. Grigio = obiettivo futuro o non verificato; test e problemi non modificano la struttura.</p>
    </div>
    <NodeVerificationPanel onResults={refreshVerification}/>
    <div className="rm2-health-summary" role="group" aria-label="Filtra stelle per esito dei test">
      <button type="button" aria-pressed={healthFilter==="all"} onClick={()=>setHealthFilter("all")}>Tutte · {stars.length}</button>
      {Object.entries(toneLabels).map(([key,label])=><button type="button" key={key} className={"tone-"+key} aria-pressed={healthFilter===key} onClick={()=>setHealthFilter(key)}><i className="rm2-dot"/>{label} · {counts[key]}</button>)}
      <p>Esiti sulla versione attiva del Debian. Verde: collaudo reale superato, controlli e sottoelementi verificati. Giallo: miglioramenti previsti. Arancione: problema o rischio. Rosso: blocco o guasto totale. Nessun test disponibile non significa superato.</p>
      {healthError&&<p role="status">{healthError}</p>}
    </div>
    <div className="rm2-goal-strip" aria-label="Stelle obiettivo da realizzare">
      <div className="rm2-goal-strip-title"><Target size={14}/> STELLE OBIETTIVO <span>{goalStars.length} ancora da realizzare</span></div>
      <div>{goalStars.map(n=><button type="button" key={n.id} onClick={()=>jump(n.id)}>
        <span className="rm2-goal-glyph">◇</span><b>{n.code||n.id}</b>{n.title.replace(/^[A-Z][\d.]* · /,"")}
      </button>)}</div>
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
            <i title={toneLabels[tone(n)]} aria-label={toneLabels[tone(n)]} className={"rm2-dot tone-"+tone(n)}/><span><b>{n.code||n.id}</b> · {n.title.replace(/^[A-Z][\d.]* · /,"")}</span><ChevronRight size={13}/>
          </button>)}
          {!matching.length&&<p>Nessuna stella corrispondente. Azzera i filtri.</p>}
        </div>
      </aside>
      <div className="rm2-center">
        {view==="map"?<Constellation nodes={nodes} selected={selected.id} focusId={focusId} onFocusChange={id=>id===null?showAll():setFocusId(id)} onSelect={choose} priority={tone} visible={visible} related={source.relations.filter(r=>r.from===root.id||r.to===root.id)}/>:
          <div className="rm2-list"><h2>Componenti e responsabilità</h2><p>Vista alternativa della stessa mappa: non una seconda roadmap.</p>
            {["radici","tronco","rami"].map(level=><section key={level}><h3>{level.toUpperCase()}</h3><div>{matching.filter(n=>level==="tronco"?n.parent==="tronco":level==="radici"?hasAncestor(n,"radici"):!hasAncestor(n,"radici")&&n.parent!=="tronco").map(n=><button type="button" key={n.id} onClick={()=>choose(n.id)}><i title={toneLabels[tone(n)]} aria-label={toneLabels[tone(n)]} className={"rm2-dot tone-"+tone(n)}/><span>{n.code} · {n.title.replace(/^[A-Z][\d.]* · /,"")}</span><ArrowRight size={14}/></button>)}</div></section>)}
          </div>}
      </div>
      <aside className="rm2-inspector" aria-label="Scheda della stella">
        <small className="rm2-inspect-path">{scope}</small>
        <div className="rm2-inspect-code">{root.code||root.id} · STELLA</div>
        <h2>{root.title.replace(/^[A-Z][\d.]* · /,"")}</h2>
        {focusId&&<button type="button" className="rm2-overview-link" onClick={showAll}>← Torna alla panoramica delle stelle</button>}
        <div className="rm2-badges">
          <span className="rm2-impl">{selectedTone==="ok"?"Controlli superati · stato di progetto separato":implementation[root.status||"unverified"]||"Da verificare"}</span>
          <span className={"rm2-attention tone-"+selectedTone}><i className="rm2-dot"/>{toneLabels[selectedTone]||tones[selectedTone]||"Da valutare"}</span>
        </div>
        {goals.length>0&&<div className="rm2-project-state">
          <strong>Stato progetto · aggiornato {homeRoadmap.updatedAt}</strong>
          {goals.map(g=><div key={g.id}><b>{g.id}</b><span>{g.state}</span><small>{g.detail}</small></div>)}
        </div>}
        {selected.id!==root.id&&<div className="rm2-current-part">
          <strong>{selected.classification==="planet"?"Pianeta":selected.classification==="moon"?"Luna":"Elemento"} selezionato</strong>
          <span>{selected.title} · {implementation[selected.status||"unverified"]||"Da verificare"}</span>
        </div>}
        {newlyObserved&&<div className="rm2-observation"><CheckCircle2 size={15}/><div>Collaudo E2E attribuibile al commit attivo del Debian.
          <small>Ambiente Debian e versione corrispondente; la struttura della mappa non viene modificata.</small>
        </div></div>}
        <p className="rm2-caveat">Verde = collaudo reale sulla versione attiva. Simulazioni, contratti e check HTTP non certificano una funzionalità. Problemi e miglioramenti si propagano dai sottoelementi.</p>
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
              <button type="button" aria-expanded={openPlanet===pl.id} onClick={()=>setOpenPlanet(openPlanet===pl.id?null:pl.id)}><i title={toneLabels[tone(pl)]} className={"rm2-dot tone-"+tone(pl)}/><span>{pl.title}</span>{openPlanet===pl.id?<ChevronDown size={14}/>:<ChevronRight size={14}/>}</button>
              {openPlanet===pl.id&&<div className="rm2-moonlist">{children(pl.id).map(m=><p key={m.id}><i title={toneLabels[tone(m)]} className={"rm2-dot tone-"+tone(m)}/>{m.title}</p>)}{!children(pl.id).length&&<p>Nessuna luna per questo pianeta.</p>}</div>}
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
          <p className="rm2-test-note">Commit installato: {activeCommit?<code>{activeCommit.slice(0,12)}</code>:"non disponibile. Nessun risultato può confermare il verde sulla versione corrente."}</p>
          {healthError&&<p className="rm2-test-note">{healthError}</p>}
          {activeCommit&&mappedChecks.some(cid=>health?.latest[cid]&&!health.latest[cid].commit)&&<p className="rm2-test-note">Il sito conosce il commit installato, ma uno o più collaudi non riportano lo SHA del codice testato. Questi risultati non possono certificare la versione corrente: verificare che il container API sia stato costruito dall’updater con CORA_GIT_COMMIT e ripetere i controlli dopo il rilascio.</p>}
          {!health&&!healthError&&<p className="rm2-test-note">Caricamento registro condiviso…</p>}
          {mappedChecks.map(cid=>{
            const def=healthCatalog.find(c=>c.id===cid),result=health?.latest[cid],st=verified(def,result,activeCommit);
            return <div key={cid} className="rm2-check">
              <div><strong>{def?.title||cid}</strong><span className={"rm2-check-state "+st}>{st==="pass"?"Superato sul commit attivo":st==="fail"?"Fallito sul commit attivo":st==="stale"?"Scaduto":st==="outdated"?"Altra versione":st==="unattributed"?"Versione non verificata":st==="planned"?"Da implementare":"Da verificare"}</span></div>
              <small>{def?def.kind+" · "+(def.frequency==="to_implement"?"non implementato, nessun runner":def.automated?"automatico":"a richiesta"):"Controllo non ancora registrato nel catalogo"}</small>
              <small>{def?.frequency==="to_implement"?"Controllo proposto: nessuna esecuzione automatica.":result?formatDate(result.at)+" · "+(result.environment||"ambiente ignoto")+(result.commit?" · "+result.commit.slice(0,10):" · commit non disponibile"):"Nessun esito disponibile"}</small>
              {result?.detail&&<small>{result.detail}</small>}
            </div>;
          })}
          {!mappedChecks.length&&<p className="rm2-test-note">Nessun controllo associato a questa stella. Da progettare; non significa “tutto ok”.</p>}
          <div className="rm2-section-head"><GitBranch size={14}/> CODICE E PAGINE <span>{links.length}</span></div>
          {pageLink&&<a className="rm2-code-link" href={pageLink.hash}><strong>{pageLink.label}</strong><small>Pagina esistente di ServerIA</small></a>}
          {links.map((link,i)=><a key={i} className="rm2-code-link" href={sourceUrl(link)} target="_blank" rel="noopener noreferrer">
            <strong>{link.label} ↗</strong><small>{link.repo||"Aleselva12/serveria1"} / {link.path}</small>
          </a>)}
          {!links.length&&!pageLink&&<p className="rm2-test-note">Nessun collegamento al codice verificato per questa stella: la capacità potrebbe essere futura o da censire.</p>}
          <small className="rm2-rel-caveat">Collegamenti selezionati e verificati nella repository; non rappresentano da soli una prova end-to-end.</small>
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
    <RoadmapPriorities stars={stars} onOpen={jump}/>
    <section className="rm2-footer-work"><div><small>SEQUENZA OPERATIVA · AUTO</small><h2>{workItems.slice(0,3).map(w=>w.id).join(" → ")}</h2><p>Stato letto dalla roadmap Home aggiornata il {homeRoadmap.updatedAt}.{currentWork?" Prossimo: "+currentWork.id+" · "+currentWork.title:""}</p></div>
      <div>{workItems.slice(0,3).map(w=><button type="button" key={w.id} onClick={()=>jump(workTargets[w.id]||"T1")}><b>{w.id}</b><span>{w.title}<small>{w.status}</small></span><ArrowRight size={16}/></button>)}</div>
    </section>
    <footer className="rm2-footer"><CircleHelp size={14}/>{source.revision} · struttura da qwe · stato lavori da project-status · risultati test dal registro unico, senza eseguirli due volte. <a href="#home">Torna alla Home</a></footer>
  </section>;
}
