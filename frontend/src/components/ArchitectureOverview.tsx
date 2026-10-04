import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ArchitectureOverview as Overview, BackendHealth } from "../types/contracts";
import "./architecture-overview.css";

const label = (id: string, name: string) => ({
  react_ui: "Interfaccia", fastapi_backend: "API · FastAPI", supervisor: "Cora · Agente centrale",
  structure_agent: "Struttura", local_research_agent: "Documenti", audio_agent: "Audio",
  email_quotes_agent: "Mail e preventivi", programmer_agent: "Programmatore",
}[id] || name);

export default function ArchitectureOverview({ health, selectedNode, onSelect }: {
  health: BackendHealth | null; selectedNode: string; onSelect: (id: string) => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    api.architectureOverview().then(data => { if (active) { setOverview(data); setError(""); } })
      .catch(e => { if (active) { setOverview(null); setError(e.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  const agents = overview?.nodes.filter(n => n.kind === "agent" && n.id !== "supervisor") || [];
  const positions: Record<string, {x: number; y: number}> = {
    react_ui: {x: 250, y: 65}, fastapi_backend: {x: 690, y: 65}, supervisor: {x: 470, y: 215},
  };
  agents.forEach((a, i) => { positions[a.id] = {x: (i + .5) * 940 / agents.length, y: 390}; });
  const selected = overview && [...overview.nodes, ...overview.components].find(n => n.id === selectedNode)
    || overview?.nodes.find(n => n.id === "supervisor");
  const selectedModel = overview?.nodes.find(n => n.id === selected?.id)?.model;
  return <>
    <div className="overview-toolbar"><div><h2>Framework generale</h2><p>Agenti separati e collegamenti di delega effettivamente disponibili.</p></div><button className="chip" disabled={loading} onClick={() => setRevision(v => v + 1)}>Aggiorna</button></div>
    {loading && !overview && <p>Caricamento architettura…</p>}
    {error && <p role="alert">{error}</p>}
    {overview && <>
      <div className="arch-layout overview-layout">
        <div className="overview-canvas">
          <div className="canvas-label">MAPPA DEL SISTEMA <span>{overview.framework}</span></div>
          <div className="overview-scroll"><div className="overview-map">
            <svg viewBox="0 0 940 455" className="overview-lines" role="img" aria-label="Collegamenti del framework agentico">
              <defs><marker id="overview-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" /></marker></defs>
              {overview.edges.map((edge, i) => {
                const a = positions[edge.source], b = positions[edge.target]; if (!a || !b) return null;
                const d = a.y === b.y ? `M${a.x + 97} ${a.y} L${b.x - 99} ${b.y}`
                  : `M${a.x} ${a.y + 42} C${a.x} ${(a.y + b.y) / 2} ${b.x} ${(a.y + b.y) / 2} ${b.x} ${b.y - 44}`;
                return <path key={i} d={d} className={edge.kind} markerEnd="url(#overview-arrow)"><title>{label(edge.source, edge.source)} → {label(edge.target, edge.target)} · {edge.label}</title></path>;
              })}
              <text x="470" y="58" textAnchor="middle">Richiesta</text>
              <text x="545" y="145">/chat</text>
              <text x="470" y="303" textAnchor="middle">Delega agli agenti</text>
            </svg>
            {overview.nodes.map(node => { const p = positions[node.id]; if (!p) return null;
              return <button key={node.id} className={`overview-node ${node.id === "supervisor" ? "central" : node.kind} ${selected?.id === node.id ? "selected" : ""}`} style={{ left: `${p.x / 940 * 100}%`, top: `${p.y / 455 * 100}%` }} aria-pressed={selected?.id === node.id} onClick={() => onSelect(node.id)}>
                <span className="overview-node-kind">{node.id === "supervisor" ? "SUPERVISORE" : node.kind === "agent" ? "AGENTE" : "INTERFACCIA"}</span>
                <strong>{label(node.id, node.name)}</strong>
                <small><span className={`node-dot ${node.available ? "" : "unavailable"}`} />{node.available ? "Modulo presente" : "Non disponibile"}</small>
              </button>;
            })}
          </div></div>
          <div className="overview-legend"><span>→ Richiesta e delega</span><span>Un nodo = un agente o un’interfaccia</span><span>Sola lettura</span></div>
        </div>
        <aside className="side-panel overview-details">
          <div className="eyebrow">COMPONENTE SELEZIONATO</div><h2>{selected?.name}</h2><p>{selected?.description}</p>
          <div className="field-line"><span>Disponibilità strutturale</span><strong>{selected?.available ? "Modulo presente" : "Non disponibile"}</strong></div>
          {selectedModel && <div className="overview-model"><span>Modello configurato</span><strong>{selectedModel}</strong></div>}
          <div className="eyebrow spaced">CAPACITÀ DICHIARATE</div><div className="chip-row">{selected?.capabilities.map(c => <span className="chip" key={c.id} title={c.description}>{c.id}</span>)}</div>
          <p className="panel-note">La disponibilità dei moduli non certifica credenziali o operatività. Le esecuzioni si consultano in Attività.</p>
        </aside>
      </div>
      <div className="section-card overview-support"><div className="overview-section-heading"><h2>Componenti di supporto</h2><span className="pill">Servizi e codice condiviso</span></div>
        <div className="overview-components"><div className="overview-service"><strong>Ollama</strong><small>{!health ? "Non verificato" : health.ollama_online ? "Raggiungibile" : "Offline"}</small></div>
        {overview.components.map(c => <button className={`overview-component ${selected?.id === c.id ? "selected" : ""}`} aria-pressed={selected?.id === c.id} key={c.id} title={c.description} onClick={() => onSelect(c.id)}><strong>{c.name}</strong><small>{c.available ? "Modulo presente" : "Non disponibile"}</small></button>)}</div>
      </div>
      <div className="section-card overview-direct"><div className="overview-section-heading"><h2>Percorsi diretti · senza agenti</h2><span className="pill">Codice deterministico</span></div>
        <p>Queste funzioni passano dalle API ai servizi, senza delega a un agente.</p><div className="overview-paths">{overview.direct_paths.map(p => <div className="overview-path" key={p.id}><strong>{p.name}</strong><small>{p.trigger}</small><p>{p.description}</p></div>)}</div>
        <div className="overview-automations">{overview.automations.map(a => <div key={a.id}><strong>Automatico · {a.name}</strong><span>{a.trigger}</span><p>{a.description}</p></div>)}</div>
      </div>
      <p className="overview-version">Panoramica letta dal backend · versione {overview.version}</p>
    </>}
  </>;
}
