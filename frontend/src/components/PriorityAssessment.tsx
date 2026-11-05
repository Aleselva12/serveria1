import {useEffect,useState} from "react";
import {priorityApi,type PriorityEvaluation,type PriorityStatus,type PriorityRating} from "../services/priorityApi";
import "./priority-assessment.css";

const dimensions:Record<string,string>={importance:"Importanza",urgency:"Urgenza",blockers:"Dipendenze",impact:"Impatto",effort:"Sforzo",risk:"Rischio"};
const date=(value?:string)=>value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString("it-IT"):"Data non disponibile";

export default function PriorityAssessment({mode="list"}:{mode?:"list"|"model"}){
  const [evaluation,setEvaluation]=useState<PriorityEvaluation|null>(null);
  const [status,setStatus]=useState<PriorityStatus|null>(null);
  const [busy,setBusy]=useState(true),[error,setError]=useState("");
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    let active=true;
    setBusy(true);setError("");
    async function load(){
      try{
        if(mode==="model"){
          const data=await priorityApi.status();if(active)setStatus(data);
        }else{
          const data=await priorityApi.latest();
          if(active){setEvaluation(data.evaluation);if(!data.available)setError("Storico delle priorità non disponibile. Verifica il database e l'aggiornamento del server.");}
        }
      }catch(e){if(active)setError(e instanceof Error?e.message:"Priorità non disponibili.");}
      finally{if(active)setBusy(false);}
    }
    const updated=()=>setRevision(v=>v+1);
    window.addEventListener("cora:priorities-updated",updated);
    void load();
    return()=>{active=false;window.removeEventListener("cora:priorities-updated",updated);};
  },[mode,revision]);
  const rating=(row:PriorityRating)=><li key={row.id}>
    <div><strong><span className="priority-code">{row.id}</span> {row.title?.replace(/^[A-Z][\d.]* · /,"")||row.id}</strong><b>{row.score}/100</b></div>
    <p>{row.explanation}</p><small>Confidenza: {row.confidence==="high"?"alta":row.confidence==="medium"?"media":"bassa"}</small>
  </li>;
  return <section className="system-card priority-assessment" aria-label={mode==="model"?"Modello valutazione priorità":"Priorità valutate"}>
    <header><div><h2>{mode==="model"?"Modello per le priorità":"Priorità valutate"}</h2>
      <p>{mode==="model"?"Valutatore dedicato, separato dal modello del Supervisor.":"Ultima valutazione salvata: primi cinque punti in evidenza."}</p></div>
      <button type="button" disabled={busy} onClick={()=>setRevision(v=>v+1)}>{busy?"Caricamento…":"Aggiorna"}</button></header>
    {error&&<p role="alert">{error}</p>}
    {mode==="model"&&status&&<>
      <dl className="priority-model-info">
        <div><dt>Modello configurato</dt><dd>{status.model}</dd></div>
        <div><dt>Motore</dt><dd>{status.provider||"Ollama"} · endpoint configurato</dd></div>
        <div><dt>Configurazione</dt><dd>{status.configuration_source==="default"?"Valore predefinito":status.configuration_source==="CORA_ROADMAP_CLASSIFIER_MODEL"?"Configurazione dedicata del server":"Origine non disponibile"}</dd></div>
        <div><dt>Disponibilità</dt><dd>{status.detail}</dd></div>
        <div><dt>Ultima valutazione</dt><dd>{status.last_evaluation?date(status.last_evaluation.evaluated_at):"Nessuna valutazione salvata"}</dd></div>
        {status.last_evaluation&&<><div><dt>Modello richiesto allora</dt><dd>{status.last_evaluation.model}</dd></div>
          <div><dt>Modello restituito da Ollama</dt><dd>{status.last_evaluation.reported_model||"Non dichiarato"}{status.last_evaluation.model_verified?" · confermato":" · non confermato"}</dd></div></>}
      </dl>
      <p>Il modello assegna i valori ai criteri; il server calcola il punteggio e l'ordine con pesi fissi.</p>
      {status.weights&&<div className="priority-weights">{Object.entries(status.weights).map(([key,value])=><span key={key}>{dimensions[key]||key} × {value}</span>)}</div>}
      <p>Ogni valutazione confronta fino a {status.max_objectives||8} obiettivi selezionati, senza valutare automaticamente tutta la mappa.</p>
      {status.history_available===false&&<p role="status">Storico non disponibile: i modelli dell'ultima valutazione non sono verificabili.</p>}
    </>}
    {mode==="list"&&evaluation&&<>
      <p className="priority-provenance">{date(evaluation.evaluated_at)} · Modello richiesto: <strong>{evaluation.model}</strong>
        {evaluation.reported_model?" · Restituito: "+evaluation.reported_model:" · Modello effettivo non dichiarato"}
        {evaluation.model_verified?" · confermato":" · non confermato"}</p>
      <p>{evaluation.objective_count||evaluation.ratings.length} obiettivi confrontati. Il punteggio riguarda questa selezione.</p>
      <ol className="priority-ranking priority-top-five">{evaluation.ratings.slice(0,5).map(rating)}</ol>
      {evaluation.ratings.length>5&&<details className="priority-more"><summary>Altri punti ({evaluation.ratings.length-5})</summary>
        <ol className="priority-ranking" start={6}>{evaluation.ratings.slice(5).map(rating)}</ol></details>}
      <small>{evaluation.warning}</small>
    </>}
    {mode==="list"&&!evaluation&&!busy&&!error&&<p>Nessuna valutazione salvata. Avvia “Valuta priorità” nella mappa per creare l'elenco.</p>}
    <footer><a href="#homepage-schema-albero">Apri mappa e valuta priorità</a>{mode==="list"&&<a href="#architecture">Vedi modello e criteri in Architettura</a>}</footer>
  </section>;
}
