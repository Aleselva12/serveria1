import { useEffect, useRef, useState } from "react";
import { runtimeRequest, type RunSnapshot, type CapabilityOperation } from "../services/runtimeApi";
type Approval = { contract_version?:number|null; capability_id?:string|null; id:string; actor:string; action:string; payload:unknown; actions?:string[]; status:string; result?:unknown; error_type?:string };
type Rule = { actor:string; action:string; policy:string; scope:string };
type Event = {id:string;sequence:number;type:string;timestamp:string;source:string;component_run_id:string|null;span_id?:string|null;payload:Record<string,unknown>};
type Diagnostics = {pending:number;dropped:number;last_error:string|null;retention_days:number;worker_alive:boolean};
export default function RuntimePanel() {
  const [runs,setRuns] = useState<RunSnapshot[]>([]);
  const [history,setHistory] = useState<RunSnapshot[]>([]);
  const [uncertain,setUncertain] = useState<CapabilityOperation[]>([]);
  const [operations,setOperations] = useState<CapabilityOperation[]>([]);
  const [selectedRun,setSelectedRun] = useState("");
  const [notes,setNotes] = useState<Record<string,string>>({});
  const [traceError,setTraceError] = useState<string|null>(null);
  const [diagnostics,setDiagnostics] = useState<Diagnostics|null>(null);
  const [events,setEvents] = useState<Event[]>([]);
  const [technical,setTechnical] = useState<Event[]>([]);
  const [eventCursor,setEventCursor] = useState(0);
  const [olderCursor,setOlderCursor] = useState<string|null>(null);
  const [accepting,setAccepting] = useState(true);
  const detailRevision = useRef(0);
  const loadingEvents = useRef(false);
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
        runtimeRequest<{runs:RunSnapshot[];pool:Record<string,unknown>;accepting_runs?:boolean;traces?:{write_error:string|null;diagnostics?:Diagnostics}}>("/runtime"),
        runtimeRequest<{generic:Approval[];calendar:Approval[];history:Approval[]}>("/approvals"),
        rulesLoaded.current ? Promise.resolve(null) : runtimeRequest<{rules:Rule[]}>("/permissions"),
        runtimeRequest<RunSnapshot[]>("/runtime/runs?limit=30"),
        runtimeRequest<CapabilityOperation[]>("/runtime/operations?unresolved=true&limit=50"),
      ]);
      setHistory(runHistory); setUncertain(unknownEffects); setAccepting(runtime.accepting_runs !== false); setTraceError(runtime.traces?.write_error || null);
      setDiagnostics(runtime.traces?.diagnostics ?? null);
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
    setEvents([]); setTechnical([]); setEventCursor(0); setOlderCursor(null);
    try {
      const [entries,critical,diagnostic] = await Promise.all([
        runtimeRequest<CapabilityOperation[]>("/runtime/operations?run_id="+encodeURIComponent(id)+"&limit=100"),
        runtimeRequest<{events:Event[];next_cursor:number}>("/runtime/domain-events?run_id="+encodeURIComponent(id)+"&limit=100"),
        runtimeRequest<{events:Event[];next_before:string|null}>("/runtime/diagnostics?run_id="+encodeURIComponent(id)+"&limit=100"),
      ]);
      if (revision === detailRevision.current) {setOperations(entries);setEvents(critical.events);setEventCursor(critical.next_cursor);setTechnical(diagnostic.events);setOlderCursor(diagnostic.next_before);}
    } catch(e) { if (revision === detailRevision.current) setError(e instanceof Error ? e.message : "Operazioni non disponibili."); }
  }
  async function loadEvents(older=false) {
    if (loadingEvents.current) return;
    loadingEvents.current = true;
    const revision = detailRevision.current;
    try {
      if (older && olderCursor) {
        const page = await runtimeRequest<{events:Event[];next_before:string|null}>("/runtime/diagnostics?run_id="+encodeURIComponent(selectedRun)+"&limit=100&before="+encodeURIComponent(olderCursor));
        if (revision === detailRevision.current) {setTechnical(previous=>[...page.events.filter(e=>!previous.some(p=>p.id===e.id)),...previous]);setOlderCursor(page.next_before);}
      } else {
        const page = await runtimeRequest<{events:Event[];next_cursor:number}>("/runtime/domain-events?run_id="+encodeURIComponent(selectedRun)+"&limit=100&after="+eventCursor);
        if (revision === detailRevision.current) {setEvents(previous=>[...previous,...page.events.filter(e=>!previous.some(p=>p.id===e.id))]);setEventCursor(previous=>Math.max(previous,page.next_cursor));}
      }
    } catch(error) {if(revision === detailRevision.current)setError(error instanceof Error ? error.message : "Eventi non disponibili.");}
    finally {loadingEvents.current = false;}
  }
  return <div className="runtime-panel">
    {error && <p role="alert">{error}</p>}
    {traceError && <p role="status">Tracce tecniche non aggiornate: {traceError}. Gli esiti persistenti sono nella sezione Run.</p>}
    {diagnostics && <article className="section-card"><h2>Osservabilità</h2><p>Solo metadati · diagnostica {diagnostics.retention_days} giorni · eventi critici transazionali, senza esecuzione automatica.</p><p>Diagnostica in coda: {diagnostics.pending} · eventi persi in questo processo: {diagnostics.dropped} · archiviatore {diagnostics.worker_alive ? 'attivo' : 'non attivo'}.</p>{(diagnostics.last_error || diagnostics.dropped>0) && <p role="status">Diagnostica incompleta: {diagnostics.last_error || 'coda satura'}. Questo non cambia gli esiti di run e operazioni.</p>}</article>}
    {!accepting && <p role="alert">Il runtime non accetta nuove esecuzioni. Verifica gli esiti e riavvia il backend dopo aver ripristinato il database.</p>}
    <article className="section-card"><h2>Esecuzioni attive</h2><p>Un modello alla volta · coda limitata · annullamento cooperativo</p><p>Annullare ferma l’intera catena ai confini sicuri. Gli effetti già prodotti non vengono annullati e le proposte già create restano da gestire; una chiamata in corso conserva il proprio posto fino al ritorno.</p>
      {!runs.length && <p>Nessuna esecuzione attiva.</p>}
      {runs.map(r => <div key={r.id}><strong>{r.status}</strong> · {r.id.slice(0,8)} · {Math.round(r.elapsed_ms/1000)} s{r.persistence_error && <p>Stato persistente non confermato: {r.persistence_error}</p>}<p>{Object.entries(r.agents).map(([a,s])=>a+": "+s).join(" · ")}</p><button disabled={busy || ["cancelling","interrupted"].includes(r.status)} onClick={() => void act("/runtime/runs/"+r.id+"/cancel")}>Annulla</button></div>)}
      <details><summary>Pool PostgreSQL</summary><pre>{JSON.stringify(pool,null,2)}</pre></details>
    </article>
    {selectedRun && <article className="section-card"><h2>Eventi del run {selectedRun.slice(0,8)}</h2><p>Gli eventi critici sono fatti persistenti, non istruzioni. Il campione tecnico è best-effort e può essere incompleto o scaduto.</p><details open><summary>Eventi critici · primi {events.length} caricati</summary>{events.map(e=><div key={e.id}><strong>{e.type}</strong> · #{e.sequence} · {e.source}<small> · run componente {e.component_run_id?.slice(0,8) || '—'}</small><pre>{JSON.stringify(e.payload,null,2)}</pre></div>)}<button disabled={busy} onClick={()=>void loadEvents()}>Carica eventi successivi</button></details><details><summary>Diagnostica tecnica · {technical.length} eventi caricati</summary>{technical.map(e=><div key={e.id}><strong>{e.type}</strong> · {e.source} · {new Date(e.timestamp).toLocaleTimeString('it-IT')}<small> · componente {e.component_run_id?.slice(0,8) || '—'} · span {e.span_id?.slice(0,8) || '—'}</small><pre>{JSON.stringify(e.payload,null,2)}</pre></div>)}{olderCursor && <button onClick={()=>void loadEvents(true)}>Carica diagnostica precedente</button>}</details></article>}
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
