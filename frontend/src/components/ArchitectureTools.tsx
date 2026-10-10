import { useEffect, useRef, useState } from "react";
import { Search, RefreshCw, Wrench } from "lucide-react";
import { api } from "../services/api";
import { toolsApi } from "../services/toolsApi";
import type { ToolDefinition, ToolInventory, ToolEntry } from "../types/contracts";
import ToolFlowCanvas from "./ToolFlowCanvas";
import AutomationEditor from "./AutomationEditor";
import "./architecture-tools.css";
import "./tool-flow.css";

const states = { connected: "Collegato agli agenti", unconnected: "Tool da collegare", integration_needed: "API da integrare con gli agenti", direct: "API diretta · interfaccia e servizi", planned: "Da implementare" };
export default function ArchitectureTools() {
  const [data, setData] = useState<ToolInventory | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [group, setGroup] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const [definition, setDefinition] = useState<ToolDefinition | null>(null);
  const [definitionLoading, setDefinitionLoading] = useState(false);
  const [definitionError, setDefinitionError] = useState("");
  const [stepId, setStepId] = useState("");
  const [mode, setMode] = useState<"inspect" | "draft">("inspect");
  const viewer = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(""); setData(null);
    api.toolInventory().then(result => { if (!cancelled) setData(result); })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Inventario non disponibile."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [revision]);
  useEffect(() => {
    let cancelled = false;
    setDefinition(null); setDefinitionError(""); setStepId("");
    if (!selectedId) { setDefinitionLoading(false); return; }
    setDefinitionLoading(true);
    toolsApi.definition(selectedId).then(result => { if (!cancelled) { setDefinition(result); setStepId(result.flow.nodes[0]?.id || ""); } })
      .catch(e => { if (!cancelled) setDefinitionError(e instanceof Error ? e.message : "Definizione non disponibile."); })
      .finally(() => { if (!cancelled) setDefinitionLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId, revision]);
  const entries = data?.entries || [];
  const groups = [...new Set(entries.map(e => e.group))];
  const filtered = entries.filter(e => (status === "all" || e.status === status) &&
    (group === "all" || e.group === group) &&
    `${e.name} ${e.description} ${e.agents.join(" ")} ${e.group}`.toLocaleLowerCase("it").includes(query.toLocaleLowerCase("it")));
  const selected = entries.find(e => e.id === selectedId);
  const step = definition?.flow.nodes.find(n => n.id === stepId);
  function select(entry: ToolEntry) { setSelectedId(entry.id); setMode("inspect"); viewer.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }); }
  return <div className="architecture-tools">
    <div className="tools-intro"><div><h2>Tools e automatizzazioni</h2><p>Seleziona un tool dall’elenco per esplorarne il funzionamento, oppure costruisci una nuova bozza.</p></div>
      <button className="file-tool" disabled={loading} onClick={() => setRevision(r => r + 1)}><RefreshCw size={14} /> Aggiorna</button></div>
    <nav className="flow-view-tabs" aria-label="Modalità tools">
      <button aria-pressed={mode === "inspect"} onClick={() => setMode("inspect")}>Tool selezionato</button>
      <button aria-pressed={mode === "draft"} onClick={() => setMode("draft")}>Costruisci automazione</button>
    </nav>
    <div ref={viewer} className="tool-viewer" hidden={mode !== "inspect"}>
      <div className="tools-intro"><h3>{selected?.name || "Visualizzatore del tool"}</h3><span>Schema e caratteristiche</span></div>
      {definitionError && <div className="connection-error" role="alert">{definitionError}<button onClick={() => setRevision(r => r + 1)}>Riprova</button></div>}
      <div className="tools-workspace">
        {definition ? <ToolFlowCanvas flow={definition.flow} selected={stepId} onSelect={setStepId} /> :
          <div className="tool-flow-empty">{definitionLoading ? <p role="status">Lettura della definizione…</p> :
            <><Wrench size={32} /><h3>{selected ? "Flusso non disponibile" : "Scegli un tool dall’elenco"}</h3><p>Qui vedrai soltanto il suo flusso: ingresso, controlli, operazione e risultato.</p></>}</div>}
        <aside className="tools-detail" aria-live="polite"><div><div className="eyebrow">PASSAGGIO SELEZIONATO</div>
          {step ? <><h3>{step.label}</h3><p className="flow-step-detail">{step.detail}</p></> : <p>Seleziona un passaggio del flusso per i dettagli.</p>}
          </div><div className="tool-attributes">{selected && <><div className="eyebrow">CARATTERISTICHE DEL TOOL</div><span className={`tools-badge ${selected.status}`}>{states[selected.status]}</span>
            <p>{selected.description}</p><p>{selected.detail}</p><dl><dt>Funzione</dt><dd>{selected.group}</dd><dt>Agenti collegati</dt><dd>{selected.agents.join(", ") || (selected.status === "direct" ? "Non richiesti per questa API" : "Nessuno")}</dd><dt>Origine</dt><dd>{selected.source}</dd><dt>Output dichiarato</dt><dd>{definition?.output_type || "Non disponibile"}</dd></dl></>}
          </div></aside>
      </div>
      {definition && <><p className="tools-scope">{definition.note}</p>
        {definition.entry.capabilities?.length ? <section className="section-card"><h3>Contratti eseguibili</h3><p>Gli stessi contratti sono usati dagli agenti e dal servizio di esecuzione. Il diagramma illustra il funzionamento; le automazioni restano bozze separate.</p>
          {definition.entry.capabilities.map(c=><article key={c.id} className="capability-contract"><h4>{c.actor} · versione {c.version}</h4><p><code>{c.id}</code></p>
            <dl><dt>Operazione</dt><dd>{{read:"Lettura",compute:"Calcolo",write:"Scrittura",delegate:"Delega"}[c.effect]}</dd><dt>Ripetizione</dt><dd>{c.retry === "safe" ? "Dichiarata sicura · nessun ritentativo automatico" : "Non ripetere automaticamente"}</dd><dt>Approvazione</dt><dd>{c.permissions.some(p => p.policy === "confirm") ? (c.approval === "calendar" ? "Proposta calendario da confermare" : "Conferma solo per le azioni indicate") : c.permissions.some(p => p.policy === "blocked") ? "Contiene azioni bloccate dalla policy" : "Automatica · nessuna conferma utente"}</dd></dl>
            <table><thead><tr><th>Permesso</th><th>Quando</th><th>Policy</th></tr></thead><tbody>{c.permissions.map(p=><tr key={p.action}><td>{p.action}</td><td>{c.conditional_actions.includes(p.action) ? "Solo nel ramo che lo richiede" : "Prima dell’esecuzione"}</td><td>{p.policy === "auto" ? "Automatico" : p.policy === "confirm" ? "Conferma" : "Bloccato"}</td></tr>)}</tbody></table>
            <details><summary>Schemi input, risultato e revisione</summary><pre>{JSON.stringify({input:c.input_schema,result:c.output_schema,native_output:c.native_output_schema,contract_digest:c.contract_digest,implementation_revision:c.implementation_revision},null,2)}</pre></details>
          </article>)}
        </section> : null}

        <div className="tool-signature"><h3>Ingressi e parametri</h3>{definition.parameters.length ? <div className="tool-parameter-table"><table><thead><tr><th>Parametro</th><th>Tipo</th><th>Obbligatorio</th><th>Valore iniziale</th></tr></thead><tbody>
          {definition.parameters.map(p => <tr key={p.name}><td>{p.name}</td><td>{p.type}</td><td>{p.required ? "Sì" : "No"}</td><td>{p.default ?? "—"}</td></tr>)}
        </tbody></table></div> : <p>Nessun parametro dichiarato.</p>}</div>
        <details className="tool-source-details"><summary>Operazioni chiamate e controlli interni</summary><div><h4>Operazioni nel codice</h4>{definition.operations.length ? <ul>{definition.operations.map(c => <li key={c}>{c}</li>)}</ul> : <p>Nessuna chiamata diretta rilevata.</p>}
          <h4>Controlli espliciti</h4><ul>{[...definition.checks, ...definition.conditions].map((c, i) => <li key={i}>{c}</li>)}</ul></div></details></>}
    </div>
    <p className="panel-note">Automazioni grafiche: solo bozze. Salvataggio e modifica sono disponibili; esecuzione, pianificazione e collegamento agli agenti sono da implementare.</p>
    <div hidden={mode !== "draft"}><AutomationEditor entries={entries} /></div>
    {error && <div className="connection-error" role="alert">{error}</div>}
    {data?.errors.length ? <div className="connection-error" role="alert">Inventario parziale: {data.errors.join("; ")}</div> : null}
    <div className="tools-catalog"><div className="tools-intro"><h2>Elenco per funzione</h2><span>{filtered.length} elementi · clicca per aprire il flusso</span></div>
      <div className="tools-counts">{Object.entries(states).map(([key, label]) =>
        <button key={key} className={`tools-state ${key}`} aria-pressed={status === key} onClick={() => setStatus(status === key ? "all" : key)}><strong>{entries.filter(e => e.status === key).length}</strong> {label}</button>)}</div>
      <div className="tools-filters"><label className="tools-search"><Search size={16} /><input aria-label="Cerca tools" placeholder="Cerca nome, funzione o agente…" value={query} onChange={e => setQuery(e.target.value)} /></label>
        <select aria-label="Filtra per funzione" value={group} onChange={e => setGroup(e.target.value)}><option value="all">Tutte le funzioni</option>{groups.map(g => <option key={g}>{g}</option>)}</select>
        <select aria-label="Filtra per stato" value={status} onChange={e => setStatus(e.target.value)}><option value="all">Tutti gli stati</option>{Object.entries(states).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
      {loading && <p className="tools-empty" role="status">Caricamento dell’inventario…</p>}
      {!loading && !error && !filtered.length && <p className="tools-empty">Nessuno strumento corrisponde ai filtri.</p>}
      {[{id:"agent",title:"Tool, integrazioni e promemoria"},{id:"direct",title:"API dirette dell’interfaccia e dei servizi · nessun collegamento agenti richiesto"}].map(section => <div key={section.id} className="tools-catalog-section"><h3>{section.title}</h3>
      {groups.filter(g => filtered.some(e => e.group === g && (e.status === "direct") === (section.id === "direct"))).map(g => <section className="tools-function" key={g}><h4>{g}<span>{filtered.filter(e => e.group === g && (e.status === "direct") === (section.id === "direct")).length}</span></h4>
        {filtered.filter(e => e.group === g && (e.status === "direct") === (section.id === "direct")).map(e => <button key={e.id} className={`tools-list-row ${selectedId === e.id ? "selected" : ""}`} onClick={() => select(e)} aria-pressed={selectedId === e.id}>
          <Wrench size={16} /><div><strong>{e.name}</strong><p>{e.description}</p><small>{e.agents.join(", ") || (e.kind === "api" ? "Operazione backend / frontend" : "Nessun agente collegato")}</small></div><span className={`tools-badge ${e.status}`}>{states[e.status]}</span></button>)}
      </section>)}</div>)}
    </div><p className="tools-scope">{data?.scope}</p>
  </div>;
}
