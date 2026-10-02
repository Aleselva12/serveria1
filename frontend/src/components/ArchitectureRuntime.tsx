import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ArchitectureGraph, ExecutionRun } from "../types/contracts";
import "./architecture-runtime.css";

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
  useEffect(() => { let active = true; const update = () => { if (active) void refresh(); }; update(); const timer = setInterval(update, 10000); return () => { active = false; clearInterval(timer); }; }, [showGraph, showTraces]);
  const run = runs.find(r => r.id === selected) || runs[0];
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
      <div className="section-card"><h3>Deleghe disponibili</h3>{graph.delegations.map(d => <p key={d.tool}><strong>{d.source} → {d.target}</strong> · <code>{d.tool}</code></p>)}<p>Questi collegamenti sono strumenti disponibili; l’elenco seguente mostra quelli effettivamente eseguiti.</p></div>
      {graph.errors.map(e => <p role="alert" key={e.component}>Grafo non disponibile: {e.component} · {e.error_type}</p>)}
      </>}
    </>}
    {showTraces && <div className="section-card"><div className="runtime-toolbar"><h2>Tracce di esecuzione</h2><button className="chip" disabled={loading} onClick={() => void refresh()}>Aggiorna</button></div><p>Ultime 50 richieste chat · aggiornamento ogni 10 secondi · conservate dopo il riavvio.</p>
      {runError && <p role="alert">{runError}</p>}
      {!loading && !runError && !runs.length && <p>Nessuna esecuzione registrata. Invia un messaggio a Cora per generare la prima traccia.</p>}
      {runs.length > 0 && <><label>Esecuzione <select value={run?.id || ""} onChange={e => setSelected(e.target.value)}>{runs.map(r => <option value={r.id} key={r.id}>{new Date(r.started_at).toLocaleString("it-IT")} · {r.status} · {r.id.slice(0, 8)}</option>)}</select></label>
      {run && <><p>Chat: <code>{run.thread_id}</code> · Grafo: <code>{run.graph_version}</code> · Errori registrati: {run.error_count}</p>{run.note && <p>{run.note}</p>}<div className="trace-table"><table><thead><tr><th>Ora</th><th>Passaggio</th><th>Stato</th><th>Durata</th><th>Relazione</th></tr></thead><tbody>{run.events.map((e, i) => <tr key={i}><td>{new Date(e.timestamp).toLocaleTimeString("it-IT")}</td><td>{e.kind} · {e.name}</td><td>{e.status}{e.error_type && ` · ${e.error_type}`}</td><td>{e.duration_ms === null ? "—" : `${e.duration_ms} ms`}</td><td title={e.parent_id || ""}>{e.span_id?.slice(0, 8) || "richiesta"}{e.parent_id && ` ← ${e.parent_id.slice(0, 8)}`}</td></tr>)}</tbody></table></div></>}
      </>}
    </div>}
  </div>;
}
