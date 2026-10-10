import { useEffect, useState } from "react";
import { chatTools, type ChatTool } from "../services/chatToolsApi";

const labels:Record<string,string> = {audio_agent_tool:"Agente Audio",email_agent_tool:"Agente Mail e preventivi",search_agent_tool:"Agente Documenti",structure_agent_tool:"Agente Struttura",programmer_agent_tool:"Agente Programmatore"};
export default function ChatToolPicker({selection,onChange,disabled,available}:{selection:string[]|null;onChange:(names:string[]|null)=>void;disabled:boolean;available:boolean}) {
  const [open,setOpen] = useState(false);
  const [tools,setTools] = useState<ChatTool[]>([]);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  const [revision,setRevision] = useState(0);
  useEffect(()=>{
    if (!open || !available) return;
    let active=true;setLoading(true);setError("");
    chatTools().then(t=>{if(active)setTools(t);}).catch(e=>{if(active){setTools([]);setError(e.message);}}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[open,available,revision]);
  const groups=[...new Set(tools.map(t=>t.group))];
  return <div className="chat-tool-picker">
    <button className="chip" type="button" disabled={disabled} aria-expanded={open} onClick={()=>setOpen(v=>!v)}>Tools · {selection === null ? "Automatici" : selection.length + " selezionati"}</button>
    {open && <div className="chat-tool-panel">
      <div className="chip-row"><button type="button" className="chip" disabled={disabled} aria-pressed={selection===null} onClick={()=>onChange(null)}>Automatici</button>
        <button type="button" className="chip" disabled={disabled||!available} aria-pressed={selection!==null} onClick={()=>onChange(selection??[])}>Scelta manuale</button></div>
      <p>La scelta manuale rende disponibili solo i tool selezionati per questa richiesta. Gli agenti specializzati usano i propri strumenti. La selezione non esegue azioni da sola.</p>
      <p>Le operazioni automatiche non chiedono conferma. Le azioni con policy di conferma restano approvabili in Attività o Calendario.</p>
      {!available && <p>Collega il backend per caricare i tool disponibili.</p>}
      {loading && <p role="status">Caricamento tools…</p>}
      {error && <p role="alert">{error} <button type="button" onClick={()=>setRevision(v=>v+1)}>Riprova</button></p>}
      {selection!==null && !loading && !error && groups.map(g=><fieldset key={g} disabled={disabled}><legend>{g}</legend>{tools.filter(t=>t.group===g).map(t=><label className="chat-tool-option" key={t.name}>
        <input type="checkbox" checked={selection.includes(t.name)} onChange={e=>onChange(e.target.checked?[...selection,t.name]:selection.filter(n=>n!==t.name))}/>
        <span><strong>{labels[t.name]||t.name}</strong><small>{t.description}</small><small>{t.group === "Agenti specializzati" ? "Delega · l’agente mantiene le policy dei propri tool" : t.permissions.some(p=>p.policy==="confirm")?"Conferma prevista per alcune azioni":t.permissions.some(p=>p.policy==="blocked")?"Contiene azioni bloccate":"Automatico · nessuna conferma"}</small></span>
      </label>)}</fieldset>)}
      {selection!==null && !selection.length && <p>Nessun tool abilitato per questa richiesta.</p>}
    </div>}
  </div>;
}
