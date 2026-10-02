import { useState } from "react";
import { Plus, Save, RefreshCw } from "lucide-react";
import ToolFlowCanvas from "./ToolFlowCanvas";
import { toolsApi } from "../services/toolsApi";
import type { AutomationDraft, DraftSummary, FlowNode, ToolEntry } from "../types/contracts";

const uid = () => crypto.randomUUID();
function initialDraft(): AutomationDraft {
  const input = uid(), output = uid();
  return { title: "Nuova automazione", description: "", status: "draft", nodes: [
    { id: input, kind: "trigger", label: "Avvio manuale", x: 70, y: 150, config: { trigger: "manual" } },
    { id: output, kind: "output", label: "Risultato", x: 650, y: 150, config: {} },
  ], edges: [] };
}
export default function AutomationEditor({ entries }: { entries: ToolEntry[] }) {
  const [draft, setDraft] = useState<AutomationDraft>(initialDraft);
  const [selectedId, setSelectedId] = useState("");
  const [pending, setPending] = useState<{ source: string; label: string } | null>(null);
  const [token, setToken] = useState("");
  const [summaries, setSummaries] = useState<DraftSummary[]>([]);
  const [draftId, setDraftId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(true);
  const [configText, setConfigText] = useState("{}");
  const [configError, setConfigError] = useState("");
  const selected = draft.nodes.find(n => n.id === selectedId);
  const available = entries.filter(e => e.kind !== "planned");
  function update(fn: (d: AutomationDraft) => AutomationDraft) { setDraft(d => ({ ...fn(d), warnings: [] })); setDirty(true); setNotice(""); }
  function select(id: string) {
    if (configError) return;
    setSelectedId(id); setConfigError("");
    setConfigText(JSON.stringify(draft.nodes.find(n => n.id === id)?.config || {}, null, 2));
  }
  function updateNode(fields: Partial<FlowNode>) { update(d => ({ ...d, nodes: d.nodes.map(n => n.id === selectedId ? { ...n, ...fields } : n) })); }
  function add(kind: FlowNode["kind"]) {
    if (configError) return;
    const node: FlowNode = { id: uid(), kind, label: { trigger: "Avvio manuale", tool: "Scegli un tool", condition: "Condizione", output: "Risultato" }[kind],
      x: 360 + (draft.nodes.length % 3) * 260, y: 60 + Math.floor(draft.nodes.length / 3) * 160, config: kind === "trigger" ? { trigger: "manual" } : {} };
    update(d => ({ ...d, nodes: [...d.nodes, node] })); setSelectedId(node.id); setConfigText(JSON.stringify(node.config, null, 2));
  }
  function connect(id: string, direction: "in" | "out", label = "successo") {
    if (direction === "out") { setPending({ source: id, label }); setError(""); return; }
    if (!pending) { setError("Scegli prima una porta di uscita."); return; }
    if (pending.source === id) { setError("Un nodo non può essere collegato a se stesso."); return; }
    if (draft.edges.some(e => e.source === pending.source && e.target === id && e.label === pending.label)) { setError("Questo collegamento esiste già."); return; }
    const edge = { id: uid(), source: pending.source, target: id, label: pending.label };
    update(d => ({ ...d, edges: [...d.edges, edge] })); setPending(null); setError("");
  }
  function configure(value: string) {
    setConfigText(value);
    setDirty(true); setNotice("");
    try {
      const config: unknown = JSON.parse(value);
      if (!config || typeof config !== "object" || Array.isArray(config)) throw Error("Usa un oggetto JSON, ad esempio {}.");
      updateNode({ config: config as Record<string, unknown> }); setConfigError("");
    } catch (e) { setConfigError(e instanceof Error ? e.message : "JSON non valido."); }
  }
  async function save() {
    if (busy || configError) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await toolsApi.saveDraft(draft, token);
      setDraft(saved); setDraftId(saved.id || ""); setDirty(false);
      setSummaries(rows => [{ id: saved.id!, title: saved.title, version: saved.version!, updated_at: saved.updated_at!, status: "draft" }, ...rows.filter(r => r.id !== saved.id)]);
      setNotice("Bozza salvata sul server. Non è attiva e non esegue operazioni.");
    } catch (e) { setError(e instanceof Error ? e.message : "Salvataggio non riuscito."); }
    finally { setBusy(false); }
  }
  async function refresh() {
    if (busy) return; setBusy(true); setError("");
    try { setSummaries(await toolsApi.listDrafts(token)); }
    catch (e) { setError(e instanceof Error ? e.message : "Elenco non disponibile."); }
    finally { setBusy(false); }
  }
  async function load() {
    if (busy || !draftId || dirty && !window.confirm("Le modifiche non salvate verranno sostituite. Aprire la bozza scelta?")) return;
    setBusy(true); setError("");
    try {
      const loaded = await toolsApi.loadDraft(draftId, token);
      setDraft(loaded); setSelectedId(""); setPending(null); setConfigError(""); setNotice(""); setDirty(false);
    } catch (e) { setError(e instanceof Error ? e.message : "Bozza non disponibile."); }
    finally { setBusy(false); }
  }
  function reset() {
    if (dirty && !window.confirm("Le modifiche non salvate verranno sostituite. Creare una nuova bozza?")) return;
    setDraft(initialDraft()); setSelectedId(""); setPending(null); setDirty(true); setConfigError(""); setError(""); setNotice(""); setDraftId("");
  }
  return <section className="automation-editor"><div className="draft-heading"><div><span className="tools-badge planned">Bozza · non eseguibile</span>
    <p>Costruisci i passaggi e i collegamenti. Salva la bozza per riprenderla; l’attivazione dei flussi verrà collegata successivamente.</p></div>
    <button className="file-tool" onClick={reset} disabled={busy}>Nuova bozza</button></div>
    <div className="draft-meta"><label>Nome automazione<input aria-label="Nome automazione" maxLength={120} value={draft.title} disabled={busy} onChange={e => update(d => ({ ...d, title: e.target.value }))} /></label>
    <label>Descrizione<input aria-label="Descrizione automazione" maxLength={4000} value={draft.description} disabled={busy} onChange={e => update(d => ({ ...d, description: e.target.value }))} /></label></div>
    <div className="draft-toolbar">{(["trigger", "tool", "condition", "output"] as const).map(kind => <button className="file-tool" disabled={busy || !!configError || draft.nodes.length >= 80} key={kind} onClick={() => add(kind)}><Plus size={14} />{{ trigger: "Ingresso", tool: "Tool", condition: "Condizione", output: "Uscita" }[kind]}</button>)}
      {pending && <button className="file-tool" onClick={() => setPending(null)}>Annulla collegamento</button>}
      <button className="upload-button" disabled={busy || !!configError || !draft.title.trim()} onClick={() => void save()}><Save size={14} />{busy ? "Attendi…" : "Salva bozza"}</button><small>{dirty ? "Modifiche non salvate" : `Salvata · versione ${draft.version}`}</small></div>
    {error && <div className="connection-error" role="alert">{error}</div>}{notice && <div className="file-notice" role="status">{notice}</div>}
    {draft.warnings?.length ? <div className="draft-warnings"><strong>Passaggi da completare nella bozza</strong><ul>{draft.warnings.map(w => <li key={w}>{w}</li>)}</ul></div> : null}
    <div className="tools-workspace"><ToolFlowCanvas flow={draft} selected={selectedId} onSelect={select} editable={!busy} pending={pending}
      onMove={(id, x, y) => update(d => ({ ...d, nodes: d.nodes.map(n => n.id === id ? { ...n, x, y } : n) }))}
      onConnect={connect} onRemoveEdge={id => update(d => ({ ...d, edges: d.edges.filter(e => e.id !== id) }))} />
      <aside className="tools-detail"><div className="eyebrow">CONFIGURA IL PASSAGGIO</div>{selected ? <><label>Nome nodo<input aria-label="Nome nodo" maxLength={160} disabled={busy} value={selected.label} onChange={e => updateNode({ label: e.target.value })} /></label>
        {selected.kind === "tool" && <><label>Tool o operazione backend<select aria-label="Tool del nodo" disabled={busy} value={selected.tool_id || ""} onChange={e => { const entry = entries.find(t => t.id === e.target.value); updateNode({ tool_id: entry?.id || null, label: entry?.name || "Scegli un tool", config: {} }); setConfigText("{}"); setConfigError(""); }}>
          <option value="">Scegli un tool…</option>{available.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><p>{entries.find(e => e.id === selected.tool_id)?.description}</p>
          <small>Parametri: {entries.find(e => e.id === selected.tool_id)?.parameters.join(", ") || "Consulta la definizione del tool"}</small></>}
        <label>{selected.kind === "condition" ? "Regola della condizione (JSON)" : "Configurazione del passaggio (JSON)"}<textarea aria-label="Configurazione nodo" rows={8} disabled={busy} value={configText} onChange={e => configure(e.target.value)} /></label>
        {configError && <p role="alert" className="draft-config-error">JSON non valido: {configError}. Correggilo prima di cambiare passaggio o salvare.</p>}
        <p>{selected.kind === "condition" ? "Usa le due porte di uscita per i rami sì e no. La regola verrà interpretata quando sarà implementato l’esecutore." : "Questa configurazione viene conservata nella bozza; non viene eseguita."}</p>
        <button className="text-button" disabled={busy} onClick={() => { update(d => ({ ...d, nodes: d.nodes.filter(n => n.id !== selectedId), edges: d.edges.filter(e => e.source !== selectedId && e.target !== selectedId) })); setSelectedId(""); setConfigError(""); setPending(null); }}>Rimuovi passaggio</button>
      </> : <p>Seleziona un nodo nel flusso per configurarlo.</p>}</aside></div>
    <details className="draft-access"><summary>Bozze salvate e accesso al server</summary><p>Da remoto si usa il token proprietario CORA_FILES_TOKEN, mantenuto solo in memoria durante questa pagina.</p>
      <label>Token proprietario<input aria-label="Token bozze" type="password" value={token} autoComplete="off" onChange={e => setToken(e.target.value)} /></label>
      <div className="draft-toolbar"><button className="file-tool" disabled={busy} onClick={() => void refresh()}><RefreshCw size={14} />Aggiorna bozze</button>
        <select aria-label="Bozza da aprire" value={draftId} onChange={e => setDraftId(e.target.value)}><option value="">Seleziona una bozza…</option>{summaries.map(s => <option key={s.id} value={s.id}>{s.title} · v{s.version}</option>)}</select>
        <button className="file-tool" disabled={busy || !draftId} onClick={() => void load()}>Apri bozza</button></div></details>
  </section>;
}
