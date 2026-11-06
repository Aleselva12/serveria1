import {useEffect,useMemo,useState,useRef} from "react";
import {BrainCircuit,AlertTriangle,CheckCircle2,RefreshCcw,Target,ExternalLink} from "lucide-react";
import {apiBaseUrl} from "../services/api";
import {authenticatedFetch} from "../services/transport";
import {priorityApi,type PriorityEvaluation} from "../services/priorityApi";
import type {Node} from "./model";

type Status={model:string;installed:boolean;available:boolean;detail:string};
type Preview=PriorityEvaluation;
const INITIAL=["T1","R5.2","G1","E1","E2","F2","R1.4","T9"];
const MAX_ITEMS=8;
const STRATEGY=["importance","urgency","blockers","impact","effort","risk"] as const;
const LABELS:Record<typeof STRATEGY[number],string>={
 importance:"Importanza",urgency:"Urgenza",blockers:"Dipendenze",impact:"Impatto",
 effort:"Sforzo",risk:"Rischio",
};
type Props={stars:Node[];onOpen:(id:string)=>void};
export default function RoadmapPriorities({stars,onOpen}:Props){
 const [selected,setSelected]=useState<string[]>(INITIAL);
 const [status,setStatus]=useState<Status|null>(null);
 const [checking,setChecking]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [context,setContext]=useState("");
 const [preview,setPreview]=useState<Preview|null>(null);
 const interactions=useRef(0),evaluationPending=useRef(false);
 const byId=useMemo(()=>new Map(stars.map(x=>[x.id,x])),[stars]);
 const eligible=selected.filter(id=>byId.has(id)).slice(0,MAX_ITEMS);
 const refresh=async()=>{
  setChecking(true);
  try{
   const response=await authenticatedFetch(apiBaseUrl+"/api/v1/roadmap/classifier/status");
   if(!response.ok)throw Error("Servizio classificatore non ancora disponibile sul backend.");
   setStatus(await response.json() as Status);
  }catch{setStatus(null);}finally{setChecking(false);}
 };
 useEffect(()=>{
  let active=true;const startedAt=interactions.current;
  void refresh();
  void priorityApi.latest().then(data=>{
   if(active&&interactions.current===startedAt&&data.evaluation){setPreview(data.evaluation);setSelected(data.evaluation.ratings.map(r=>r.id).filter(id=>byId.has(id)).slice(0,MAX_ITEMS));}
  }).catch(()=>undefined);
  return()=>{active=false;};
 },[]);
 const toggle=(id:string)=>{
  if(evaluationPending.current)return;
  interactions.current++;
  setPreview(null);setError("");
  setSelected(old=>old.includes(id)?old.filter(x=>x!==id):old.length<MAX_ITEMS?[...old,id]:old);
 };
 const evaluate=async()=>{
  if(!eligible.length||evaluationPending.current)return;
  evaluationPending.current=true;interactions.current++;
  setBusy(true);setError("");setPreview(null);
  const objectives=eligible.map(id=>{
   const n=byId.get(id)!;
   return {id:n.id,title:n.title.slice(0,130),
    summary:(n.note||"").slice(0,420),
    implementation:n.status||"unverified",
    problems:(n.knownIssues||[]).slice(0,3).map(x=>x.slice(0,180)),
    goals:(n.timeline?.future||[]).slice(0,3).map(x=>x.slice(0,180))};
  });
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),450000);
  try{
   const response=await authenticatedFetch(apiBaseUrl+"/api/v1/roadmap/classifier/preview",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({objectives,additional_context:context}),signal:controller.signal,
   });
   const body=await response.json() as Preview&{detail?:string};
   if(!response.ok)throw Error(body.detail||"Classificazione non disponibile.");
   if(!Array.isArray(body.ratings))throw Error("Il modello non ha restituito dati validi.");
   setPreview(body);
   if(body.persisted)window.dispatchEvent(new Event("cora:priorities-updated"));
  }catch(e){setError(e instanceof Error&&e.name==="AbortError"?"Tempo massimo di attesa superato (7 minuti e 30 secondi). Controlla il run in Attività e la disponibilità di Ollama.":e instanceof Error?e.message:"Impossibile effettuare la classificazione.");}
  finally{evaluationPending.current=false;clearTimeout(timeout);setBusy(false);}
 };
 const display=(id:string)=>byId.get(id)?.title.replace(/^[A-Z][\d.]* · /,"")||id;
 return <section id="roadmap-priorities" className="rm2-priorities" aria-label="Classificatore locale degli obiettivi">
  <div className="rm2-priorities-heading"><div><small>MODULO SPERIMENTALE · SOLO LOCALE</small>
   <h2><BrainCircuit size={20}/> Analisi dei prossimi passi</h2>
   <p>Confronta alcuni obiettivi della mappa con un modello Ollama. Le valutazioni sono consigli,
      non nuovi test e non modificano le stelle.</p></div>
   <button type="button" onClick={()=>void refresh()} disabled={checking} aria-label="Ricontrolla modello"><RefreshCcw size={15}/></button>
  </div>
  <div className="rm2-priorities-status">
   <span><i className={"rm2-dot "+(status?.installed?"tone-ok":"tone-unknown")}/> {status?.model||"Modello locale non verificato"}</span>
   <span>{status?.detail||"Controllo Ollama non disponibile. Il backend deve essere aggiornato."}</span>
  </div>
  <details className="rm2-priorities-targets">
   <summary>Seleziona obiettivi da confrontare ({eligible.length}/{MAX_ITEMS})</summary>
   <div>{stars.map(star=><label key={star.id}>
      <input type="checkbox" checked={selected.includes(star.id)} onChange={()=>toggle(star.id)}
       disabled={busy||!selected.includes(star.id)&&selected.length>=MAX_ITEMS}/>
      <span>{star.code||star.id} · {display(star.id)}</span>
    </label>)}</div>
  </details>
  <label className="rm2-priorities-context">Ulteriori obiettivi o criteri (facoltativo)
   <textarea disabled={busy} value={context} onChange={e=>{interactions.current++;setContext(e.target.value);setPreview(null);}} maxLength={500}
    rows={2} placeholder="Esempio: privilegia la stabilità dei servizi rispetto alle funzioni nuove…"/>
  </label>
  <div className="rm2-priorities-actions">
   <button type="button" disabled={busy||!status?.installed||!eligible.length}
    onClick={()=>void evaluate()}><Target size={15}/>{busy?"Classificazione locale in corso…":"Valuta priorità"}</button>
   <span>Non esegue test, non installa modelli e non modifica la mappa.</span>
  </div>
  {error&&<p className="rm2-priorities-error" role="alert"><AlertTriangle size={15}/>{error}</p>}
  {preview&&<>
   <div className="rm2-priorities-result"><CheckCircle2 size={15}/> Proposta del modello {preview.model}.
      Punteggi 0–100 indicativi · {preview.evaluated_at?new Date(preview.evaluated_at).toLocaleString("it-IT"):"Data non disponibile"}.
      {preview.model_verified?" Modello effettivo confermato: "+preview.reported_model:" Modello effettivo non confermato dal provider."}</div>
   {preview.persistence_detail&&<p role={preview.persisted===false?"alert":"status"}>{preview.persistence_detail}</p>}
   <div className="rm2-priorities-ratings">
    {preview.ratings.map((r,i)=><div className="rm2-priority-card" key={r.id}>
     <div><span className="rm2-priority-position">{i+1}</span><strong>{display(r.id)}</strong>
      <b>{r.score}/100</b></div>
     <p>{r.explanation}</p><small>Confidenza dichiarata dal modello: {r.confidence==="high"?"alta":r.confidence==="medium"?"media":"bassa"}</small>
     <div className="rm2-priority-dimensions">{STRATEGY.map(k=><span key={k}>{LABELS[k]} <b>{r[k]}/5</b></span>)}</div>
     <button type="button" onClick={()=>onOpen(r.id)}>Apri stella <ExternalLink size={12}/></button>
    </div>)}
   </div>
   <p className="rm2-priorities-caution">{preview.warning}</p>
  </>}
 </section>;
}
