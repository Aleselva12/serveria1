import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ArchitectureGraph, ExecutionRun } from "../types/contracts";
import "./architecture-runtime.css";

export function performanceRows(metrics: Record<string, unknown>, duration: number | null) {
  const rows: [string,string][] = [];
  const ms = (label:string, value:unknown) => { if (typeof value === "number" && Number.isFinite(value) && value >= 0) rows.push([label, (value/1000).toLocaleString("it-IT",{maximumFractionDigits:2}) + " s"]); };
  ms("Tempo totale",duration);
  ms("Attesa in coda",metrics.queue_ms);
  ms("Primo testo visibile",metrics.first_token_ms);
  ms("Preparazione contesto",metrics.context_ms);
  ms("Preparazione prompt",metrics.prompt_ms);
  ms("Ricerca memoria",metrics.memory_ms);
  ms("Chiamate ai modelli",metrics.model_ms);
  ms("Esecuzione tool",metrics.tool_ms);
  ms("Salvataggio risposta",metrics.result_save_ms);
  const config = metrics.configuration && typeof metrics.configuration === "object" ? metrics.configuration as Record<string,unknown> : null;
  const host = metrics.host && typeof metrics.host === "object" ? metrics.host as Record<string,unknown> : null;
  if (config) {
    if (typeof config.profile === "string") rows.push(["Profilo",config.profile]);
    if (typeof config.model === "string") rows.push(["Modello",config.model]);
    if (typeof config.keep_alive === "string") rows.push(["Keep-alive",config.keep_alive]);
    if (typeof config.context_tokens === "number") rows.push(["Context configurato",String(config.context_tokens)]);
    if (typeof config.output_tokens === "number") rows.push(["Output massimo",String(config.output_tokens)]);
    if (typeof config.hardware_label === "string" && config.hardware_label) rows.push(["Hardware",config.hardware_label]);
    if (typeof config.gpu_label === "string" && config.gpu_label) rows.push(["GPU",config.gpu_label]);
  }
  if (host) {
    if (typeof host.logical_cpu_count === "number") rows.push(["CPU logiche",String(host.logical_cpu_count)]);
    if (typeof host.ram_total_gib === "number") rows.push(["RAM installata",String(host.ram_total_gib) + " GiB"]);
  }
  const models = Array.isArray(metrics.models) ? metrics.models.filter((m):m is Record<string,unknown> => Boolean(m) && typeof m === "object") : [];
  const sum = (key:string) => models.reduce((total,m) => total + (typeof m[key] === "number" && Number.isFinite(m[key]) && m[key] >= 0 ? m[key] : 0),0);
  if (models.length) {
    rows.push(["Chiamate modello",String(models.length)]);
    const ttft = models.filter(m=>typeof m.first_token_ms === 'number' && Number.isFinite(m.first_token_ms));
    if (ttft.length) ms("Primo token per chiamata (medio)",ttft.reduce((sum,m)=>sum+(m.first_token_ms as number),0)/ttft.length);
    if (models.some(m=>typeof m.load_duration === "number")) ms("Caricamento modelli",sum("load_duration")/1e6);
    if (models.some(m=>typeof m.prompt_eval_count === "number")) rows.push(["Token input elaborati",String(sum("prompt_eval_count"))]);
    if (models.some(m=>typeof m.eval_count === "number")) rows.push(["Token generati",String(sum("eval_count"))]);
    const seconds = sum("eval_duration")/1e9;
    if (seconds > 0) rows.push(["Velocità di generazione",(sum("eval_count")/seconds).toLocaleString("it-IT",{maximumFractionDigits:1}) + " token/s"]);
  }
  if (typeof metrics.context_estimated_tokens === 'number') rows.push(["Token contesto stimati",String(metrics.context_estimated_tokens)]);
  if (typeof metrics.context_input_budget === 'number') rows.push(["Budget input",String(metrics.context_input_budget)]);
  if (typeof metrics.context_dropped_turns === 'number') rows.push(["Turni esclusi",String(metrics.context_dropped_turns)]);
  return rows;
}

export default function ArchitectureRuntime({
  showGraph = true,
  showTraces = true,
}: {
  showGraph?: boolean;
  showTraces?: boolean;
}) {
  const [graph, setGraph] = useState<ArchitectureGraph | null>(null);
  const [runs, setRuns] = useState<ExecutionRun[]>([]);
  const [selected, setSelected] = useState("");
  const [detail,setDetail] = useState<ExecutionRun|null>(null);
  const [graphError, setGraphError] = useState("");
  const [runError, setRunError] = useState("");
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true);
    await Promise.all([
      showGraph
        ? api.architectureGraph().then(g => { setGraph(g); setGraphError(""); }).catch(e => { setGraph(null); setGraphError(e.message); })
        : Promise.resolve(),
      showTraces
        ? api.executionRuns().then(r => { setRuns(r); setRunError(""); }).catch(e => { setRuns([]); setRunError(e.message); })
        : Promise.resolve(),
    ]);
    setLoading(false);
  }
  useEffect(() => { let active = true; const update = () => { if (active && (typeof document === "undefined" || !document.hidden)) void refresh(); }; update(); const timer = setInterval(update, 10000); return () => { active = false; clearInterval(timer); }; }, [showGraph, showTraces]);
  const summary = runs.find(r => r.id === selected) || runs[0];
  useEffect(()=>{
    if (!showTraces || !summary) return;
    let active = true;
    void api.executionRun(summary.id).then(value=>{if(active)setDetail(value);}).catch(error=>{if(active)setRunError(error.message);});
    return ()=>{active=false;};
  },[selected,runs,showTraces]);
  const run = detail?.id === summary?.id ? detail : summary;
  return <div className="runtime-architecture">
    {showGraph && <>
      <div className="runtime-toolbar"><h2>Grafo eseguibile</h2><button className="chip" disabled={loading} onClick={() => void refresh()}>Aggiorna</button></div>
      {graphError && <p role="alert">{graphError}</p>}
      {loading && !graph && !graphError && <p>Caricamento grafo…</p>}
      {graph && <>
      <p>Topologia LangGraph · versione <code>{graph.version}</code>. Le frecce tratteggiate indicano una scelta condizionale.</p>
      <div className="runtime-graphs">{graph.graphs.map(g => {
        const positions = Object.fromEntries(g.nodes.map((n, i) => [n.id, { x: 100 + (i % 2) * 200, y: 48 + Math.floor(i / 2) * 105 }]));
        return <article className="section-card" key={g.id}><h3>{g.id}</h3><svg viewBox={`0 0 400 ${Math.ceil(g.nodes.length / 2) * 105 + 30}`} role="img" aria-label={`Grafo eseguibile ${g.id}`}>
          <defs><marker id={`arrow-${g.id}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="currentColor" /></marker></defs>
          {g.edges.map((e, i) => { const a = positions[e.source], b = positions[e.target]; if (!a || !b) return null; return <g key={i}><path className="runtime-edge" strokeDasharray={e.conditional ? "5 5" : undefined} markerEnd={`url(#arrow-${g.id})`} d={`M${a.x} ${a.y + 20} Q${(a.x + b.x) / 2 + (i % 2 ? 45 : -45)} ${(a.y + b.y) / 2} ${b.x} ${b.y - 23}`} /><title>{e.source} → {e.target}{e.label ? ` · ${e.label}` : ""}</title></g>; })}
          {g.nodes.map(n => <g key={n.id}><rect className="runtime-node" x={positions[n.id].x - 85} y={positions[n.id].y - 20} width="170" height="40" rx="10"/><text x={positions[n.id].x} y={positions[n.id].y + 5} textAnchor="middle">{n.name}</text></g>)}
        </svg></article>;
      })}</div>
      <div className="section-card"><h3>Deleghe disponibili</h3>{graph.delegations.map(d => <p key={d.tool}><strong>{d.source} → {d.target}</strong> · <code>{d.tool}</code></p>)}<p>Questi collegamenti sono strumenti disponibili. Le esecuzioni effettive sono consultabili nella pagina Attività.</p></div>
      {graph.errors.map(e => <p role="alert" key={e.component}>Grafo non disponibile: {e.component} · {e.error_type}</p>)}
      </>}
    </>}
    {showTraces && <div className="section-card"><div className="runtime-toolbar"><h2>Tracce di esecuzione</h2><button className="chip" disabled={loading} onClick={() => void refresh()}>Aggiorna</button></div><p>Ultimi 50 run radice · stati persistenti · diagnostica dettagliata per 30 giorni predefiniti. Solo il dettaglio selezionato viene caricato.</p>
      {runError && <p role="alert">{runError}</p>}
      {!loading && !runError && !runs.length && <p>Nessuna esecuzione registrata. Invia un messaggio a Cora per generare la prima traccia.</p>}
      {runs.length > 0 && <><label>Esecuzione <select value={run?.id || ""} onChange={e => setSelected(e.target.value)}>{runs.map(r => <option value={r.id} key={r.id}>{new Date(r.started_at).toLocaleString("it-IT")} · {r.status} · {r.id.slice(0, 8)}</option>)}</select></label>
      {run && <><p>Chat: <code>{run.thread_id}</code> · Grafo: <code>{run.graph_version}</code> · Errori nel campione: {run.error_count}</p>{run.note && <p>{run.note}</p>}{run.metrics && <details><summary>Profilazione prestazioni</summary><table><tbody>{performanceRows(run.metrics,run.duration_ms).map(([label,value])=><tr key={label}><th>{label}</th><td>{value}</td></tr>)}</tbody></table><p>Le durate di contesto, modelli e tool possono sovrapporsi: non vanno sommate. Il primo testo può essere provvisorio.</p><details><summary>Dati tecnici</summary><pre>{JSON.stringify(run.metrics,null,2)}</pre></details></details>}<div className="trace-table"><table><thead><tr><th>Ora</th><th>Passaggio</th><th>Stato</th><th>Durata</th><th>Relazione</th></tr></thead><tbody>{run.events.map((e, i) => <tr key={i}><td>{new Date(e.timestamp).toLocaleTimeString("it-IT")}</td><td>{e.kind} · {e.name}</td><td>{e.status}{e.error_type && ` · ${e.error_type}`}</td><td>{e.duration_ms === null ? "—" : `${e.duration_ms} ms`}</td><td title={e.parent_id || ""}>{e.span_id?.slice(0, 8) || "richiesta"}{e.parent_id && ` ← ${e.parent_id.slice(0, 8)}`}</td></tr>)}</tbody></table></div></>}
      </>}
    </div>}
  </div>;
}
