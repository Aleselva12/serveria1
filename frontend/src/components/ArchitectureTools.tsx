import { useEffect, useState } from "react";
import { Search, RefreshCw, Wrench, Workflow, ZoomIn, ZoomOut } from "lucide-react";
import { api } from "../services/api";
import type { ToolInventory, ToolEntry } from "../types/contracts";
import "./architecture-tools.css";

const states = { connected: "Collegato agli agenti", unconnected: "Implementato · non collegato", planned: "Predisposto · da implementare" };

export default function ArchitectureTools() {
  const [data, setData] = useState<ToolInventory | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [group, setGroup] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(""); setData(null);
    api.toolInventory().then(result => { if (!cancelled) setData(result); })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Inventario non disponibile."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [revision]);
  const entries = data?.entries || [];
  const groups = [...new Set(entries.map(e => e.group))];
  const filtered = entries.filter(e => (status === "all" || e.status === status) &&
    (group === "all" || e.group === group) &&
    `${e.name} ${e.description} ${e.agents.join(" ")} ${e.group}`.toLocaleLowerCase("it").includes(query.toLocaleLowerCase("it")));
  const selected = filtered.find(e => e.id === selectedId) || filtered[0];
  function select(entry: ToolEntry) { setSelectedId(entry.id); }
  return <div className="architecture-tools">
    <div className="tools-intro"><div><h2>Tools e automatizzazioni</h2><p>Esplora ogni strumento, la sua funzione e il collegamento agli agenti.</p></div>
      <button className="file-tool" disabled={loading} onClick={() => setRevision(r => r + 1)}><RefreshCw size={14} /> Aggiorna</button></div>
    <div className="tools-counts">{Object.entries(states).map(([key, label]) =>
      <button key={key} className={`tools-state ${key}`} aria-pressed={status === key} onClick={() => setStatus(status === key ? "all" : key)}>
        <strong>{entries.filter(e => e.status === key).length}</strong> {label}</button>)}</div>
    <div className="tools-filters"><label className="tools-search"><Search size={16} /><input aria-label="Cerca tools" placeholder="Cerca nome, funzione o agente…" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <select aria-label="Filtra per funzione" value={group} onChange={e => setGroup(e.target.value)}><option value="all">Tutte le funzioni</option>{groups.map(g => <option key={g}>{g}</option>)}</select>
      <select aria-label="Filtra per stato" value={status} onChange={e => setStatus(e.target.value)}><option value="all">Tutti gli stati</option>{Object.entries(states).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
    {error && <div className="connection-error" role="alert">{error}</div>}
    {data?.errors.length ? <div className="connection-error" role="alert">Inventario parziale: {data.errors.join("; ")}</div> : null}
    <div className="tools-workspace">
      <div className="tools-canvas"><header><span><Workflow size={15} /> STRUMENTI · {filtered.length} NODI</span><div>
        <button aria-label="Riduci nodi" disabled={zoom <= .75} onClick={() => setZoom(z => Math.max(.75, z - .25))}><ZoomOut size={16} /></button>
        <button onClick={() => setZoom(1)} aria-label="Ripristina dimensioni">{Math.round(zoom * 100)}%</button>
        <button aria-label="Ingrandisci nodi" disabled={zoom >= 1.5} onClick={() => setZoom(z => Math.min(1.5, z + .25))}><ZoomIn size={16} /></button></div></header>
        <div className="tools-canvas-scroll"><div className="tools-node-grid" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${180 * zoom}px, 1fr))` }}>
          {filtered.map(e => <button key={e.id} className={`tool-node ${e.status} ${selected?.id === e.id ? "selected" : ""}`} aria-pressed={selected?.id === e.id} onClick={() => select(e)}>
            <span className="tool-port left" /><span className="tool-node-icon"><Wrench size={19} /></span><small>{e.group} · {e.kind === "api" ? "API" : e.kind === "planned" ? "Predisposizione" : "Tool"}</small>
            <strong>{e.name}</strong><span className={`tools-badge ${e.status}`}>{states[e.status]}</span><span className="tool-port right" /></button>)}
        </div>{loading && <p className="tools-empty" role="status">Caricamento dell’inventario…</p>}{!loading && !error && !filtered.length && <p className="tools-empty">Nessuno strumento corrisponde ai filtri.</p>}</div>
        <footer>Nodi singoli in sola lettura · seleziona uno strumento per i dettagli</footer>
      </div>
      <aside className="tools-detail" aria-live="polite"><div className="eyebrow">STRUMENTO SELEZIONATO</div>{selected ? <>
        <h3>{selected.name}</h3><span className={`tools-badge ${selected.status}`}>{states[selected.status]}</span><p>{selected.description}</p>
        <dl><dt>Funzione</dt><dd>{selected.group}</dd><dt>Agenti collegati</dt><dd>{selected.agents.join(", ") || "Nessuno"}</dd><dt>Origine</dt><dd>{selected.source}</dd>
        <dt>Parametri del tool</dt><dd>{selected.kind === "api" ? "Definiti dal contratto API" : selected.parameters.join(", ") || "Nessuno dichiarato"}</dd></dl>
        <div className="panel-note">{selected.detail}</div></> : <p>Seleziona un nodo dopo il caricamento dell’inventario.</p>}</aside>
    </div>
    <div className="tools-catalog"><div className="tools-intro"><h2>Elenco per funzione</h2><span>{filtered.length} elementi</span></div>
      {groups.filter(g => filtered.some(e => e.group === g)).map(g => <section className="tools-function" key={g}><h3>{g}<span>{filtered.filter(e => e.group === g).length}</span></h3>
        {filtered.filter(e => e.group === g).map(e => <button key={e.id} className={`tools-list-row ${selected?.id === e.id ? "selected" : ""}`} onClick={() => select(e)} aria-pressed={selected?.id === e.id}>
          <Wrench size={16} /><div><strong>{e.name}</strong><p>{e.description}</p><small>{e.agents.join(", ") || (e.kind === "api" ? "Operazione backend / frontend" : "Nessun agente collegato")}</small></div><span className={`tools-badge ${e.status}`}>{states[e.status]}</span></button>)}
      </section>)}
    </div>
    <p className="tools-scope">{data?.scope} Le predisposizioni non vengono conteggiate come strumenti implementati.</p>
  </div>;
}
