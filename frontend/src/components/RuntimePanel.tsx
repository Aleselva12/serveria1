import { useEffect, useRef, useState } from "react";
import { runtimeRequest, type RunSnapshot, type CapabilityOperation } from "../services/runtimeApi";
type Approval = { contract_version?:number|null; capability_id?:string|null; id:string; actor:string; action:string; payload:unknown; actions?:string[]; status:string; result?:unknown; error_type?:string };
type Rule = { actor:string; action:string; policy:string; scope:string };
export default function RuntimePanel() {
  const [runs,setRuns] = useState<RunSnapshot[]>([]);
  const [history,setHistory] = useState<RunSnapshot[]>([]);
  const [uncertain,setUncertain] = useState<CapabilityOperation[]>([]);
  const [operations,setOperations] = useState<CapabilityOperation[]>([]);
  const [selectedRun,setSelectedRun] = useState("");
  const [notes,setNotes] = useState<Record<string,string>>({});
  const [traceError,setTraceError] = useState<string|null>(null);
  const [accepting,setAccepting] = useState(true);
  const detailRevision = useRef(0);
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
      const [runtime,approvals,registry,runHistory,unknownEffects] = await Promise.all([
        runtimeRequest<{runs:RunSnapshot[];pool:Record<string,unknown>;accepting_runs?:boolean;traces?:{write_error:string|null}}>("/runtime"),
        runtimeRequest<{generic:Approval[];calendar:Approval[];history:Approval[]}>("/approvals"),
        rulesLoaded.current ? Promise.resolve(null) : runtimeRequest<{rules:Rule[]}>("/permissions"),
        runtimeRequest<RunSnapshot[]>("/runtime/runs?limit=30"),
        runtimeRequest<CapabilityOperation[]>("/runtime/operations?unresolved=true&limit=50"),
      ]);
      setHistory(runHistory); setUncertain(unknownEffects); setAccepting(runtime.accepting_runs !== false); setTraceError(runtime.traces?.write_error || null);
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
  async function inspectRun(id:string) {
    const revision = ++detailRevision.current;
    setSelectedRun(id); setOperations([]);
    try {
      const entries = await runtimeRequest<CapabilityOperation[]>("/runtime/operations?run_id="+encodeURIComponent(id)+"&limit=100");
      if (revision === detailRevision.current) setOperations(entries);
    } catch(e) { if (revision === detailRevision.current) setError(e instanceof Error ? e.message : "Operazioni non disponibili."); }
  }
  return <div className="runtime-panel">
    {error && <p role="alert">{error}</p>}
    {traceError && <p role="status">Tracce tecniche non aggiornate: {traceError}. Gli esiti persistenti sono nella sezione Run.</p>}
    {!accepting && <p role="alert">Il runtime non accetta nuove esecuzioni. Verifica gli esiti e riavvia il backend dopo aver ripristinato il database.</p>}
    <article className="section-card"><h2>Esecuzioni attive</h2><p>Un modello alla volta · coda limitata · annullamento cooperativo</p><p>Annullare ferma l’intera catena ai confini sicuri. Gli effetti già prodotti non vengono annullati e le proposte già create restano da gestire; una chiamata in corso conserva il proprio posto fino al ritorno.</p>
      {!runs.length && <p>Nessuna esecuzione attiva.</p>}
      {runs.map(r => <div key={r.id}><strong>{r.status}</strong> · {r.id.slice(0,8)} · {Math.round(r.elapsed_ms/1000)} s{r.persistence_error && <p>Stato persistente non confermato: {r.persistence_error}</p>}<p>{Object.entries(r.agents).map(([a,s])=>a+": "+s).join(" · ")}</p><button disabled={busy || ["cancelling","interrupted"].includes(r.status)} onClick={() => void act("/runtime/runs/"+r.id+"/cancel")}>Annulla</button></div>)}
      <details><summary>Pool PostgreSQL</summary><pre>{JSON.stringify(pool,null,2)}</pre></details>
    </article>
    <article className="section-card"><h2>Effetti da verificare</h2><p>Un esito incerto può includere effetti già prodotti. Verifica il servizio o il file interessato prima di ripetere l’operazione. Registrare la verifica non esegue né ripete azioni.</p>
      {!uncertain.length && <p>Nessun effetto da verificare.</p>}
      {uncertain.map(o=><div key={o.id}><strong>{o.capability_id} · esito incerto</strong><p>Operazione {o.id} · run {o.run_id || "senza run"}</p><pre>{JSON.stringify(o.payload,null,2)}</pre>{o.error_type && <p>{o.error_type}</p>}
        <label>Verifica effettuata<textarea aria-label={"Verifica " + o.id} maxLength={2000} value={notes[o.id] || ""} onChange={e=>setNotes(n=>({...n,[o.id]:e.target.value}))}/></label>
        <button disabled={busy || !notes[o.id]?.trim()} onClick={()=>void act("/runtime/operations/"+o.id+"/review","POST",{outcome:"effect_verified",note:notes[o.id]})}>Effetto verificato</button>
        <button disabled={busy || !notes[o.id]?.trim()} onClick={()=>void act("/runtime/operations/"+o.id+"/review","POST",{outcome:"no_effect_verified",note:notes[o.id]})}>Nessun effetto verificato</button>
      </div>)}
    </article>
    <article className="section-card"><h2>Run persistenti recenti</h2><p>Ultimi 30 run. Lo stato del run e l’esito delle singole operazioni sono distinti.</p>
      {history.map(r=><div key={r.id}><strong>{r.status}</strong> · {r.target} · {r.id.slice(0,8)} <button onClick={()=>void inspectRun(r.id)}>Vedi operazioni</button>{r.approval_ids?.length ? <p>Proposte: {r.approval_ids.join(", ")}</p> : null}</div>)}
      {selectedRun && <details open><summary>Operazioni del run {selectedRun.slice(0,8)}</summary>{!operations.length && <p>Nessuna operazione registrata in questa vista.</p>}{operations.map(o=><div key={o.id}><strong>{o.capability_id} · {o.status}</strong><p>{o.effect} · versione {o.contract_version}</p>{o.review_outcome && <p>Verifica: {o.review_outcome === "effect_verified" ? "effetto riscontrato" : "assenza di effetto riscontrata"} · {o.reviewed_by} · {o.review_note}</p>}<pre>{JSON.stringify({parametri:o.payload,risultato:o.result},null,2)}</pre></div>)}</details>}
    </article>
    <article className="section-card"><h2>Azioni da approvare</h2><p>La conferma riguarda esclusivamente l'azione e i parametri mostrati.</p>
      {!generic.length && !calendar.length && <p>Nessuna proposta in attesa.</p>}
      {[...generic.map(a=>({...a,kind:"generic"})),...calendar.map(a=>({...a,kind:"calendar"}))].map(a=><div key={a.kind+a.id}><strong>{a.actor} · {a.action}</strong>{a.actions && <p>Permessi richiesti: {a.actions.join(", ")}</p>}<pre>{JSON.stringify(a.payload,null,2)}</pre>{a.kind === "generic" && a.contract_version === null && <p>Proposta precedente ai contratti: chiedi all’agente una nuova proposta per confermarla.</p>}<button disabled={busy || (a.kind === "generic" && a.contract_version === null)} onClick={()=>void act("/approvals/"+(a.kind==="calendar" ? "calendar/" : "")+a.id+"/resolve","POST",{approve:true})}>Approva questa azione</button><button disabled={busy} onClick={()=>void act("/approvals/"+(a.kind==="calendar" ? "calendar/" : "")+a.id+"/resolve","POST",{approve:false})}>Rifiuta</button></div>)}
    </article>
    {results.length > 0 && <article className="section-card"><details><summary>Esiti delle proposte</summary>{results.map(a=><div key={a.id}><strong>{a.actor} · {a.action} · {a.status}</strong>{["executing","uncertain"].includes(a.status) && <p>Non ripetere la proposta: controlla le operazioni e l’effetto nel servizio interessato.</p>}{a.error_type && <p>{a.error_type}</p>}<pre>{typeof a.result === "string" ? a.result : JSON.stringify(a.result,null,2)}</pre></div>)}</details></article>}
    <article className="section-card"><details><summary>Permessi degli agenti per azione</summary><p>Automatico, richiedi conferma o bloccato. Le capability prive di un percorso verificato restano bloccate.</p>{rules.map(r=><label className="settings-row" key={r.actor+r.action}><span>{r.actor} · {r.action}<small>{r.scope}</small></span><select aria-label={r.actor+" "+r.action} disabled={busy} value={r.policy} onChange={e=>void act("/runtime/policies","PUT",{actor:r.actor,action:r.action,policy:e.target.value})}><option value="auto">Automatico</option><option value="confirm">Richiedi conferma</option><option value="blocked">Bloccato</option></select></label>)}</details></article>
  </div>;
}
