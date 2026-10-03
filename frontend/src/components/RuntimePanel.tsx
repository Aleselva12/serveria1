import { useEffect, useRef, useState } from "react";
import { runtimeRequest, type RunSnapshot } from "../services/runtimeApi";
type Approval = { id:string; actor:string; action:string; payload:unknown; actions?:string[]; status:string; result?:unknown; error_type?:string };
type Rule = { actor:string; action:string; policy:string; scope:string };
export default function RuntimePanel() {
  const [runs,setRuns] = useState<RunSnapshot[]>([]);
  const [pool,setPool] = useState<Record<string,unknown>>({});
  const [generic,setGeneric] = useState<Approval[]>([]);
  const [results,setResults] = useState<Approval[]>([]);
  const [calendar,setCalendar] = useState<Approval[]>([]);
  const [rules,setRules] = useState<Rule[]>([]);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const refreshing = useRef(false);
  const rulesLoaded = useRef(false);
  const rulesRevision = useRef(0);
  const refreshQueued = useRef(false);
  async function refresh(force = false) {
    if (refreshing.current) { if (force) refreshQueued.current = true; return; }
    const revision = rulesRevision.current;
    refreshing.current = true;
    try {
      const [runtime,approvals,registry] = await Promise.all([
        runtimeRequest<{runs:RunSnapshot[];pool:Record<string,unknown>}>("/runtime"),
        runtimeRequest<{generic:Approval[];calendar:Approval[];history:Approval[]}>("/approvals"),
        rulesLoaded.current ? Promise.resolve(null) : runtimeRequest<{rules:Rule[]}>("/permissions"),
      ]);
      setRuns(runtime.runs); setPool(runtime.pool); setGeneric(approvals.generic); setCalendar(approvals.calendar); setResults(approvals.history); if (registry && revision === rulesRevision.current) { setRules(registry.rules); rulesLoaded.current = true; } setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Runtime non disponibile."); }
    finally { refreshing.current = false; if (refreshQueued.current) { refreshQueued.current = false; void refresh(); } }
  }
  useEffect(() => { void refresh(); const timer = setInterval(() => { if ((typeof document === "undefined" || !document.hidden)) void refresh(); },5000); return () => clearInterval(timer); },[]);
  async function act(path:string, method="POST", body?:object) {
    setBusy(true);
    try {
      const result = await runtimeRequest<{status?:string;error_type?:string}>(path,{method,body:body ? JSON.stringify(body) : undefined});
      if (method === "PUT") { rulesLoaded.current = false; rulesRevision.current++; }
      await refresh(true);
      if (result.status === "failed") setError("Azione non completata: " + result.error_type + ". Controlla il risultato prima di riprovare.");
    } catch(e) { setError(e instanceof Error ? e.message : "Operazione non riuscita."); }
    finally { setBusy(false); }
  }
  return <div className="runtime-panel">
    {error && <p role="alert">{error}</p>}
    <article className="section-card"><h2>Esecuzioni attive</h2><p>Un modello alla volta · coda limitata · annullamento cooperativo</p>
      {!runs.length && <p>Nessuna esecuzione attiva.</p>}
      {runs.map(r => <div key={r.id}><strong>{r.status}</strong> · {r.id.slice(0,8)} · {Math.round(r.elapsed_ms/1000)} s<p>{Object.entries(r.agents).map(([a,s])=>a+": "+s).join(" · ")}</p><button disabled={busy || r.status === "cancelling"} onClick={() => void act("/runtime/runs/"+r.id+"/cancel")}>Annulla</button></div>)}
      <details><summary>Pool PostgreSQL</summary><pre>{JSON.stringify(pool,null,2)}</pre></details>
    </article>
    <article className="section-card"><h2>Azioni da approvare</h2><p>La conferma riguarda esclusivamente l'azione e i parametri mostrati.</p>
      {!generic.length && !calendar.length && <p>Nessuna proposta in attesa.</p>}
      {[...generic.map(a=>({...a,kind:"generic"})),...calendar.map(a=>({...a,kind:"calendar"}))].map(a=><div key={a.kind+a.id}><strong>{a.actor} · {a.action}</strong>{a.actions && <p>Permessi richiesti: {a.actions.join(", ")}</p>}<pre>{JSON.stringify(a.payload,null,2)}</pre><button disabled={busy} onClick={()=>void act("/approvals/"+(a.kind==="calendar" ? "calendar/" : "")+a.id+"/resolve","POST",{approve:true})}>Approva questa azione</button><button disabled={busy} onClick={()=>void act("/approvals/"+(a.kind==="calendar" ? "calendar/" : "")+a.id+"/resolve","POST",{approve:false})}>Rifiuta</button></div>)}
    </article>
    {results.length > 0 && <article className="section-card"><details><summary>Esiti delle proposte</summary>{results.map(a=><div key={a.id}><strong>{a.actor} · {a.action} · {a.status}</strong>{a.error_type && <p>{a.error_type}</p>}<pre>{typeof a.result === "string" ? a.result : JSON.stringify(a.result,null,2)}</pre></div>)}</details></article>}
    <article className="section-card"><details><summary>Permessi degli agenti per azione</summary><p>Automatico, richiedi conferma o bloccato. Le capability prive di un percorso verificato restano bloccate.</p>{rules.map(r=><label className="settings-row" key={r.actor+r.action}><span>{r.actor} · {r.action}<small>{r.scope}</small></span><select aria-label={r.actor+" "+r.action} disabled={busy} value={r.policy} onChange={e=>void act("/runtime/policies","PUT",{actor:r.actor,action:r.action,policy:e.target.value})}><option value="auto">Automatico</option><option value="confirm">Richiedi conferma</option><option value="blocked">Bloccato</option></select></label>)}</details></article>
  </div>;
}
