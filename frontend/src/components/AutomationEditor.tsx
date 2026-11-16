import { useEffect, useState } from "react";
import { Plus, Save, RefreshCw, Copy, Trash2, FolderOpen, CheckCircle2, Play, FlaskConical, Square } from "lucide-react";
import ToolFlowCanvas from "./ToolFlowCanvas";
import { toolsApi } from "../services/toolsApi";
import type { AutomationDraft, AutomationRun, DraftSummary, FlowEdge, FlowNode, RunSummary, ToolEntry } from "../types/contracts";

const uid = () => crypto.randomUUID();
const kindLabels = { trigger: "Ingresso", tool: "Tool", condition: "Condizione", output: "Uscita" } as const;
const effectLabels = { read: "Lettura", compute: "Calcolo", write: "Scrittura", delegate: "Delega" } as const;
const policyLabels: Record<string, string> = { auto: "Automatico", confirm: "Richiede conferma", blocked: "Bloccato" };
const runStatusLabels: Record<string, string> = { queued: "In coda", running: "In esecuzione", waiting_approval: "In attesa di conferma",
  succeeded: "Completata", failed: "Non riuscita", rejected: "Rifiutata", cancelled: "Annullata", interrupted: "Interrotta" };
const nodeStatusLabels: Record<string, string> = { pending: "Non ancora eseguito", done: "Eseguito", skipped: "Saltato: ramo non scelto",
  simulated: "Simulato: non eseguito", waiting_approval: "In attesa di conferma in Attività", failed: "Errore", rejected: "Rifiutato", cancelled: "Annullato" };
const operators: [string, string][] = [["eq", "è uguale a"], ["ne", "è diverso da"], ["gt", "è maggiore di"], ["gte", "è maggiore o uguale a"],
  ["lt", "è minore di"], ["lte", "è minore o uguale a"], ["contains", "contiene"], ["not_contains", "non contiene"], ["empty", "è vuoto"], ["not_empty", "non è vuoto"]];
const ACTIVE_RUN = ["queued", "running", "waiting_approval"];
const REF = /\{\{\s*([A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*)\s*\}\}/g;
const isRef = (value: unknown) => typeof value === "string" && value.includes("{{");
type RefOption = { value: string; label: string };

function inputNames(nodes: FlowNode[]) {
  const names: string[] = [];
  for (const node of nodes) for (const match of JSON.stringify(node.config).matchAll(REF)) {
    const [root, name] = match[1].split(".");
    if (root === "input" && name && !names.includes(name)) names.push(name);
  }
  return names;
}
function ancestorsOf(id: string, edges: FlowEdge[]) {
  const seen = new Set<string>(), stack = [id];
  while (stack.length) { const current = stack.pop()!; for (const e of edges) if (e.target === current && !seen.has(e.source)) { seen.add(e.source); stack.push(e.source); } }
  return seen;
}
/** Values a node may reference: launch inputs and the results of the steps before it. */
function referenceOptions(node: FlowNode, draft: AutomationDraft, entries: ToolEntry[]): RefOption[] {
  const options: RefOption[] = inputNames(draft.nodes).map(name => ({ value: `{{input.${name}}}`, label: `Valore di avvio: ${name}` }));
  const before = ancestorsOf(node.id, draft.edges);
  for (const other of draft.nodes) {
    if (!before.has(other.id) || other.kind === "trigger" || other.kind === "output") continue;
    if (other.kind === "condition") { options.push({ value: `{{${other.id}.outcome}}`, label: `${other.label} → esito (sì/no)` }); continue; }
    options.push({ value: `{{${other.id}}}`, label: `${other.label} → risultato intero` });
    const output = entries.find(e => e.id === other.tool_id)?.capabilities?.[0]?.output_schema as JsonSchema | undefined;
    for (const name of Object.keys(output?.properties || {})) options.push({ value: `{{${other.id}.${name}}}`, label: `${other.label} → ${name}` });
  }
  return options;
}
function parseInput(value: string): unknown {
  try { return JSON.parse(value); } catch { return value; }
}
function RefPicker({ options, onPick, label }: { options: RefOption[]; onPick: (value: string) => void; label: string }) {
  return <select className="ref-picker" aria-label={label} value="" onChange={e => {
    if (e.target.value === "__new") { const name = window.prompt("Nome del valore da chiedere all’avvio (lettere, numeri, _):")?.trim(); if (name && /^[A-Za-z0-9_-]+$/.test(name)) onPick(`{{input.${name}}}`); return; }
    if (e.target.value) onPick(e.target.value);
  }}><option value="">↳ usa un valore da…</option>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}<option value="__new">Nuovo valore di avvio…</option></select>;
}
const preview = (value: unknown) => { const text = JSON.stringify(value, null, 2) ?? "—"; return text.length > 4000 ? text.slice(0, 4000) + "\n…" : text; };

function initialDraft(): AutomationDraft {
  const input = uid(), output = uid();
  return { title: "Nuova automazione", description: "", status: "draft", nodes: [
    { id: input, kind: "trigger", label: "Avvio manuale", x: 70, y: 150, config: { trigger: "manual" } },
    { id: output, kind: "output", label: "Risultato", x: 650, y: 150, config: {} },
  ], edges: [] };
}
const errorText = (e: unknown, fallback: string) => e instanceof Error ? e.message : fallback;
const statusOf = (e: unknown) => (e as { status?: number } | null)?.status;
function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

/* ---- Parameter form generated from the tool's input schema ---- */
type JsonSchema = {
  type?: string | string[]; title?: string; description?: string; enum?: unknown[];
  anyOf?: JsonSchema[]; default?: unknown; properties?: Record<string, JsonSchema>; required?: string[];
};
// Pydantic renders optional fields as anyOf [T, null]: edit them as T, keeping the outer title and default.
function resolve(schema: JsonSchema): JsonSchema {
  const option = schema.anyOf?.find(o => o.type !== "null");
  return option ? { ...resolve(option), title: schema.title, description: schema.description, default: schema.default } : schema;
}
function fieldType(schema: JsonSchema) {
  if (schema.enum) return "enum";
  const type = Array.isArray(schema.type) ? schema.type.find(t => t !== "null") : schema.type;
  return type === "string" || type === "integer" || type === "number" || type === "boolean" ? type : "complex";
}
function ParamForm({ schema, config, disabled, onChange, refs }: {
  schema: JsonSchema; config: Record<string, unknown>; disabled: boolean; onChange: (config: Record<string, unknown>) => void; refs: RefOption[];
}) {
  const properties = Object.entries(schema.properties || {});
  function set(name: string, value: unknown) {
    const next = { ...config };
    if (value === undefined) delete next[name]; else next[name] = value;
    onChange(next);
  }
  return <fieldset className="param-form" disabled={disabled}><legend>Parametri del tool</legend>
    {properties.map(([name, raw]) => {
      const field = resolve(raw), type = fieldType(field), value = config[name];
      const required = schema.required?.includes(name);
      const placeholder = field.default === undefined || field.default === null ? "" : String(field.default);
      const label = <span>{field.title || name}{required && <b aria-label="obbligatorio"> *</b>}</span>;
      const aria = "Parametro " + name;
      let input;
      if (isRef(value)) input = <input aria-label={aria} className="ref-value" value={value as string} onChange={e => set(name, e.target.value === "" ? undefined : e.target.value)} />;
      else if (type === "enum") input = <select aria-label={aria} value={value === undefined ? "" : String(value)}
        onChange={e => set(name, e.target.value === "" ? undefined : field.enum!.find(o => String(o) === e.target.value))}>
        <option value="">— non impostato —</option>{field.enum!.map(o => <option key={String(o)} value={String(o)}>{String(o)}</option>)}</select>;
      else if (type === "boolean") input = <select aria-label={aria} value={value === undefined ? "" : String(value)}
        onChange={e => set(name, e.target.value === "" ? undefined : e.target.value === "true")}>
        <option value="">— non impostato —</option><option value="true">Sì</option><option value="false">No</option></select>;
      else if (type === "integer" || type === "number") input = <input aria-label={aria} type="number" step={type === "integer" ? 1 : "any"}
        placeholder={placeholder} value={typeof value === "number" ? value : ""}
        onChange={e => set(name, e.target.value === "" ? undefined : Number(e.target.value))} />;
      else if (type === "string") input = <input aria-label={aria} placeholder={placeholder} value={typeof value === "string" ? value : ""}
        onChange={e => set(name, e.target.value === "" ? undefined : e.target.value)} />;
      else input = <code className="param-complex">{value === undefined ? "Valore strutturato: impostalo nel JSON avanzato." : JSON.stringify(value)}</code>;
      return <label key={name}>{label}{input}<RefPicker label={"Riferimento per " + name} options={refs} onPick={ref => set(name, ref)} />{field.description && <small>{field.description}</small>}</label>;
    })}
  </fieldset>;
}

/* ---- Effect and permission policy of the selected tool ---- */
function ContractSummary({ entry }: { entry?: ToolEntry }) {
  if (!entry) return null;
  const contract = entry.capabilities?.[0];
  if (!contract) return <p className="node-contract none">Nessun contratto eseguibile: il passaggio resta descrittivo e non potrà essere eseguito dal motore delle automazioni.</p>;
  return <div className="node-contract"><div className="eyebrow">EFFETTO E PERMESSI</div>
    <p><strong>{effectLabels[contract.effect]}</strong> · {contract.retry === "safe" ? "ripetibile" : "da non ripetere automaticamente"} · <code>{contract.id}</code></p>
    {contract.permissions.length ? <ul>{contract.permissions.map(p => <li key={p.action} className={"policy-" + p.policy}>
      <span>{p.action}{contract.conditional_actions.includes(p.action) ? " (solo nel ramo che lo richiede)" : ""}</span>
      <em>{policyLabels[p.policy] || p.policy}</em></li>)}</ul> : <p>Nessun permesso richiesto.</p>}
  </div>;
}

function ConditionForm({ config, disabled, onChange, refs }: {
  config: Record<string, unknown>; disabled: boolean; onChange: (config: Record<string, unknown>) => void; refs: RefOption[];
}) {
  const op = typeof config.op === "string" ? config.op : "eq";
  const unary = op === "empty" || op === "not_empty";
  const text = (value: unknown) => value === undefined ? "" : typeof value === "string" ? value : JSON.stringify(value);
  function set(fields: Record<string, unknown>) {
    const next = { left: config.left ?? "", op, ...(unary ? {} : { right: config.right ?? "" }), ...fields };
    if (next.op === "empty" || next.op === "not_empty") delete (next as Record<string, unknown>).right;
    onChange(next);
  }
  return <fieldset className="param-form" disabled={disabled}><legend>Regola della condizione</legend>
    <label>Valore da controllare<input aria-label="Condizione: valore" placeholder="es. {{…}}" value={text(config.left)} onChange={e => set({ left: e.target.value })} />
      <RefPicker label="Riferimento per il valore" options={refs} onPick={ref => set({ left: ref })} /></label>
    <label>Confronto<select aria-label="Condizione: confronto" value={op} onChange={e => set({ op: e.target.value })}>{operators.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
    {!unary && <label>Termine di confronto<input aria-label="Condizione: termine" value={text(config.right)} onChange={e => set({ right: e.target.value })} />
      <RefPicker label="Riferimento per il termine" options={refs} onPick={ref => set({ right: ref })} /></label>}
    <small>Se la regola è vera si segue il ramo «sì», altrimenti il ramo «no». I numeri scritti come testo vengono confrontati come numeri.</small>
  </fieldset>;
}

export default function AutomationEditor({ entries }: { entries: ToolEntry[] }) {
  const [draft, setDraft] = useState<AutomationDraft>(initialDraft);
  const [selectedId, setSelectedId] = useState("");
  const [pending, setPending] = useState<{ source: string; label: string } | null>(null);
  const [summaries, setSummaries] = useState<DraftSummary[]>([]);
  const [listLoaded, setListLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(true);
  const [configText, setConfigText] = useState("{}");
  const [configError, setConfigError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [structureError, setStructureError] = useState("");
  const [checkState, setCheckState] = useState<"idle" | "checking" | "done" | "offline">("idle");
  const [run, setRun] = useState<AutomationRun | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runInputs, setRunInputs] = useState<Record<string, string>>({});
  const [runError, setRunError] = useState("");
  const [runProblems, setRunProblems] = useState<string[]>([]);
  const selected = draft.nodes.find(n => n.id === selectedId);
  const selectedEntry = entries.find(e => e.id === selected?.tool_id);
  const schema = selectedEntry?.capabilities?.[0]?.input_schema as JsonSchema | undefined;
  const hasForm = !!schema?.properties && Object.keys(schema.properties).length > 0;
  const available = entries.filter(e => e.kind !== "planned");
  const groups = [...new Set(available.map(e => e.group))];
  const refs = selected ? referenceOptions(selected, draft, entries) : [];
  const launchInputs = inputNames(draft.nodes);
  const runnable = !!draft.id && !dirty && !structureError && !configError && !busy;
  const runActive = !!run && ACTIVE_RUN.includes(run.status);
  const shownRun = run && run.draft_id === draft.id ? run : null;
  const statuses = shownRun ? Object.fromEntries(Object.entries(shownRun.nodes).map(([id, state]) => [id, state.status])) : undefined;
  const selectedRunState = shownRun && selected ? shownRun.nodes[selected.id] : undefined;
  const writers = draft.nodes.filter(n => n.kind === "tool" && ["write", "delegate"].includes(entries.find(e => e.id === n.tool_id)?.capabilities?.[0]?.effect || ""));

  // Server-side check while drawing: same rules as saving, nothing is stored.
  const graphKey = JSON.stringify([draft.title, draft.description, draft.nodes, draft.edges]);
  useEffect(() => {
    if (configError || !draft.title.trim()) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      setCheckState("checking");
      toolsApi.validateDraft(draft).then(result => { if (!cancelled) { setWarnings(result); setStructureError(""); setCheckState("done"); } })
        .catch(e => {
          if (cancelled) return;
          if (statusOf(e) === 400) { setStructureError(errorText(e, "Struttura non valida.")); setCheckState("done"); }
          else setCheckState("offline");
        });
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [graphKey, configError]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setRunProblems([]); setRunError("");
    if (!draft.id) { setRuns([]); return; }
    let cancelled = false;
    toolsApi.listRuns(draft.id).then(rows => { if (!cancelled) setRuns(rows); }).catch(() => { if (!cancelled) setRuns([]); });
    return () => { cancelled = true; };
  }, [draft.id]);

  // Follow an active run: quickly while it executes, slowly while it waits for a confirmation.
  useEffect(() => {
    if (!run || !ACTIVE_RUN.includes(run.status)) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      toolsApi.getRun(run.id).then(next => {
        if (cancelled) return;
        setRun(next);
        if (!ACTIVE_RUN.includes(next.status)) setRuns(rows => rows.map(r => r.id === next.id ? { ...r, status: next.status, finished_at: next.finished_at, error: next.error } : r));
      }).catch(e => { if (!cancelled) setRunError(errorText(e, "Stato dell’esecuzione non disponibile.")); });
    }, run.status === "waiting_approval" ? 5000 : 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [run]);

  function update(fn: (d: AutomationDraft) => AutomationDraft) { setDraft(d => fn(d)); setDirty(true); setNotice(""); }
  function select(id: string) {
    if (configError) return;
    setSelectedId(id); setConfigError("");
    setConfigText(JSON.stringify(draft.nodes.find(n => n.id === id)?.config || {}, null, 2));
  }
  function updateNode(fields: Partial<FlowNode>) { update(d => ({ ...d, nodes: d.nodes.map(n => n.id === selectedId ? { ...n, ...fields } : n) })); }
  function setConfig(config: Record<string, unknown>) { updateNode({ config }); setConfigText(JSON.stringify(config, null, 2)); setConfigError(""); }
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
    } catch (e) { setConfigError(errorText(e, "JSON non valido.")); }
  }
  function confirmDiscard(action: string) { return !dirty || window.confirm("Le modifiche non salvate verranno perse. " + action); }
  function open(loaded: AutomationDraft) {
    setDraft(loaded); setSelectedId(""); setPending(null); setConfigError(""); setDirty(false);
    setWarnings(loaded.warnings || []); setStructureError("");
  }

  async function save() {
    if (busy || configError || structureError) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await toolsApi.saveDraft(draft);
      open(saved);
      setSummaries(rows => [{ id: saved.id!, title: saved.title, version: saved.version!, updated_at: saved.updated_at!, status: "draft" }, ...rows.filter(r => r.id !== saved.id)]);
      setNotice("Bozza salvata sul server. Non parte da sola: puoi provarla a vuoto o eseguirla a mano.");
    } catch (e) { setError(errorText(e, "Salvataggio non riuscito.")); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError("");
    try { setSummaries(await toolsApi.listDrafts()); setListLoaded(true); }
    catch (e) { setError(errorText(e, "Elenco non disponibile.")); }
    finally { setBusy(false); }
  }
  async function load(id: string) {
    if (busy || !confirmDiscard("Aprire la bozza scelta?")) return;
    setBusy(true); setError(""); setNotice("");
    try { open(await toolsApi.loadDraft(id)); }
    catch (e) { setError(errorText(e, "Bozza non disponibile.")); }
    finally { setBusy(false); }
  }
  async function duplicate(row: DraftSummary) {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const clone = await toolsApi.duplicateDraft(row.id);
      setSummaries(rows => [{ id: clone.id!, title: clone.title, version: clone.version!, updated_at: clone.updated_at!, status: "draft" }, ...rows]);
      setNotice(`Creata «${clone.title}». Aprila dall’elenco per modificarla.`);
    } catch (e) { setError(errorText(e, "Duplicazione non riuscita.")); }
    finally { setBusy(false); }
  }
  async function remove(row: DraftSummary) {
    if (busy || !window.confirm(`Eliminare definitivamente «${row.title}»? L’operazione non si può annullare.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await toolsApi.deleteDraft(row.id, row.version);
      setSummaries(rows => rows.filter(r => r.id !== row.id));
      if (draft.id === row.id) { setDraft(d => ({ ...d, id: undefined, version: undefined })); setDirty(true); }
      setNotice(draft.id === row.id ? "Bozza eliminata. Il flusso resta nell’editor come nuova bozza non salvata." : "Bozza eliminata.");
    } catch (e) {
      setError(errorText(e, "Eliminazione non riuscita."));
      if (statusOf(e) === 409 || statusOf(e) === 404) void refresh();
    } finally { setBusy(false); }
  }
  async function startRun(mode: "dry_run" | "live") {
    if (!runnable || runActive || !draft.id || !draft.version) return;
    if (mode === "live" && !window.confirm(writers.length
      ? `Eseguire davvero l’automazione? Questi passaggi modificano dati: ${writers.map(w => w.label).join(", ")}. Le azioni con conferma verranno chieste in Attività.`
      : "Eseguire davvero l’automazione? Nessun passaggio dichiara modifiche ai dati.")) return;
    setRunError(""); setRunProblems([]);
    try {
      const input = Object.fromEntries(launchInputs.map(name => [name, parseInput(runInputs[name] ?? "")]));
      const started = await toolsApi.startRun(draft.id, draft.version, mode, input);
      setRun(started);
      setRuns(rows => [started, ...rows]);
    } catch (e) {
      setRunError(errorText(e, "Avvio non riuscito."));
      setRunProblems((e as { problems?: string[] }).problems || []);
    }
  }
  async function cancelRun() {
    if (!run) return;
    try { setRun(await toolsApi.cancelRun(run.id)); }
    catch (e) { setRunError(errorText(e, "Annullamento non riuscito.")); }
  }
  async function showRun(id: string) {
    setRunError("");
    try { setRun(await toolsApi.getRun(id)); }
    catch (e) { setRunError(errorText(e, "Esecuzione non disponibile.")); }
  }
  function reset() {
    if (!confirmDiscard("Creare una nuova bozza?")) return;
    open(initialDraft()); setDirty(true); setError(""); setNotice("");
  }

  return <section className="automation-editor"><div className="draft-heading"><div><span className="tools-badge planned">Bozza · esecuzione manuale</span>
    <p>Costruisci i passaggi e i collegamenti. Il flusso viene verificato mentre lo disegni; salvalo, provalo a vuoto ed eseguilo a mano. Avvio automatico e pianificazione arriveranno in seguito.</p></div>
    <button className="file-tool" onClick={reset} disabled={busy}>Nuova bozza</button></div>

    <section className="draft-library" aria-label="Bozze salvate"><div className="draft-library-head"><h3>Bozze salvate</h3>
      <button className="file-tool" disabled={busy} onClick={() => void refresh()}><RefreshCw size={14} />Aggiorna</button></div>
      {summaries.length ? <ul>{summaries.map(s => <li key={s.id} className={s.id === draft.id ? "current" : undefined}>
        <div><strong>{s.title}</strong><small>v{s.version} · {formatDate(s.updated_at)}{s.id === draft.id ? " · aperta" : ""}</small></div>
        <div className="draft-library-actions">
          <button className="file-tool" disabled={busy} aria-label={"Apri " + s.title} onClick={() => void load(s.id)}><FolderOpen size={14} />Apri</button>
          <button className="file-tool" disabled={busy} aria-label={"Duplica " + s.title} onClick={() => void duplicate(s)}><Copy size={14} />Duplica</button>
          <button className="file-tool danger" disabled={busy} aria-label={"Elimina " + s.title} onClick={() => void remove(s)}><Trash2 size={14} />Elimina</button>
        </div></li>)}</ul> : <p>{listLoaded ? "Nessuna bozza salvata." : "Caricamento delle bozze…"}</p>}
    </section>

    <div className="draft-meta"><label>Nome automazione<input aria-label="Nome automazione" maxLength={120} value={draft.title} disabled={busy} onChange={e => update(d => ({ ...d, title: e.target.value }))} /></label>
    <label>Descrizione<input aria-label="Descrizione automazione" maxLength={4000} value={draft.description} disabled={busy} onChange={e => update(d => ({ ...d, description: e.target.value }))} /></label></div>
    <div className="draft-toolbar">{(["trigger", "tool", "condition", "output"] as const).map(kind => <button className="file-tool" disabled={busy || !!configError || draft.nodes.length >= 80} key={kind} onClick={() => add(kind)}><Plus size={14} />{kindLabels[kind]}</button>)}
      {pending && <button className="file-tool" onClick={() => setPending(null)}>Annulla collegamento</button>}
      <button className="upload-button" disabled={busy || !!configError || !!structureError || !draft.title.trim()} onClick={() => void save()}><Save size={14} />{busy ? "Attendi…" : "Salva bozza"}</button><small>{dirty ? "Modifiche non salvate" : `Salvata · versione ${draft.version}`}</small></div>
    {error && <div className="connection-error" role="alert">{error}</div>}{notice && <div className="file-notice" role="status">{notice}</div>}

    <div className="draft-check" aria-live="polite">
      {structureError ? <div className="draft-structure-error" role="alert"><strong>Struttura non valida</strong> {structureError} Correggila prima di salvare.</div>
        : warnings.length ? <div className="draft-warnings"><strong>Passaggi da completare nella bozza</strong><ul>{warnings.map(w => <li key={w}>{w}</li>)}</ul></div>
        : checkState === "done" ? <div className="draft-complete"><CheckCircle2 size={14} />Flusso completo: nessun passaggio da completare.</div> : null}
      {checkState === "checking" && <small>Verifica del flusso…</small>}
      {checkState === "offline" && <small>Verifica automatica non disponibile; il controllo verrà ripetuto al salvataggio.</small>}
    </div>

    <section className="run-panel" aria-label="Esecuzione">
      <div className="run-panel-head"><div><h3>Esecuzione manuale</h3>
        <p>{runnable ? "La prova a vuoto esegue solo i passaggi che leggono o calcolano; quelli che modificano dati vengono mostrati senza eseguirli." : "Salva la bozza senza errori per poterla eseguire."}</p></div>
        <div className="run-actions">
          <button className="file-tool" disabled={!runnable || runActive} onClick={() => void startRun("dry_run")}><FlaskConical size={14} />Prova a vuoto</button>
          <button className="upload-button" disabled={!runnable || runActive} onClick={() => void startRun("live")}><Play size={14} />Esegui</button>
          {runActive && <button className="file-tool danger" onClick={() => void cancelRun()}><Square size={14} />Annulla</button>}
        </div></div>
      {launchInputs.length > 0 && <div className="run-inputs"><strong>Valori di avvio</strong>{launchInputs.map(name => <label key={name}>{name}
        <input aria-label={"Valore di avvio " + name} value={runInputs[name] ?? ""} disabled={runActive} onChange={e => setRunInputs(v => ({ ...v, [name]: e.target.value }))} /></label>)}
        <small>Numeri, true/false e JSON vengono interpretati; il resto resta testo.</small></div>}
      {runError && <div className="connection-error" role="alert">{runError}{runProblems.length > 0 && <ul>{runProblems.map(p => <li key={p}>{p}</li>)}</ul>}</div>}
      {shownRun && <div className={"run-status run-" + shownRun.status} role="status">
        <strong>{shownRun.mode === "dry_run" ? "Prova a vuoto" : "Esecuzione"} · {runStatusLabels[shownRun.status]}</strong>
        {shownRun.status === "waiting_approval" && <span> Un passaggio attende la tua conferma nella pagina Attività; l’esecuzione riprende da sola.</span>}
        {shownRun.error && <span> {shownRun.error}</span>}
        {shownRun.draft_version !== draft.version && <span> Riguarda la versione {shownRun.draft_version} della bozza.</span>}
      </div>}
      {runs.length > 0 && <details className="run-history"><summary>Esecuzioni precedenti ({runs.length})</summary><ul>{runs.map(r => <li key={r.id} className={r.id === run?.id ? "current" : undefined}>
        <span>{formatDate(r.created_at)} · {r.mode === "dry_run" ? "prova" : "reale"} · v{r.draft_version}</span><em className={"run-" + r.status}>{runStatusLabels[r.status]}</em>
        <button className="text-button" aria-label={"Mostra esecuzione " + formatDate(r.created_at)} onClick={() => void showRun(r.id)}>Mostra</button></li>)}</ul></details>}
    </section>

    <div className="tools-workspace"><ToolFlowCanvas flow={draft} selected={selectedId} onSelect={select} editable={!busy} pending={pending} statuses={statuses}
      onMove={(id, x, y) => update(d => ({ ...d, nodes: d.nodes.map(n => n.id === id ? { ...n, x, y } : n) }))}
      onConnect={connect} onRemoveEdge={id => update(d => ({ ...d, edges: d.edges.filter(e => e.id !== id) }))} />
      <aside className="tools-detail"><div className="eyebrow">CONFIGURA IL PASSAGGIO</div>{selected ? <><label>Nome nodo<input aria-label="Nome nodo" maxLength={160} disabled={busy} value={selected.label} onChange={e => updateNode({ label: e.target.value })} /></label>
        {selected.kind === "tool" && <><label>Tool o operazione backend<select aria-label="Tool del nodo" disabled={busy} value={selected.tool_id || ""} onChange={e => { const entry = entries.find(t => t.id === e.target.value); updateNode({ tool_id: entry?.id || null, label: entry?.name || "Scegli un tool", config: {} }); setConfigText("{}"); setConfigError(""); }}>
          <option value="">Scegli un tool…</option>{groups.map(g => <optgroup key={g} label={g}>{available.filter(e => e.group === g).map(e => <option key={e.id} value={e.id}>{e.name}{e.capabilities?.length ? "" : " · senza contratto"}</option>)}</optgroup>)}</select></label>
          {selectedEntry && <p>{selectedEntry.description}</p>}
          <ContractSummary entry={selectedEntry} />
          {hasForm && <ParamForm schema={schema!} config={selected.config} disabled={busy || !!configError} onChange={setConfig} refs={refs} />}
          {selectedEntry && !hasForm && <small>Parametri: {selectedEntry.parameters.join(", ") || "nessuno dichiarato"}</small>}</>}
        {selected.kind === "condition" && <ConditionForm config={selected.config} disabled={busy || !!configError} onChange={setConfig} refs={refs} />}
        <details className="draft-advanced" open={(!hasForm && selected.kind !== "condition") || !!configError}><summary>{hasForm || selected.kind === "condition" ? "Configurazione avanzata (JSON)" : "Configurazione del passaggio (JSON)"}</summary>
          <textarea aria-label="Configurazione nodo" rows={8} disabled={busy} value={configText} onChange={e => configure(e.target.value)} /></details>
        {configError && <p role="alert" className="draft-config-error">JSON non valido: {configError}. Correggilo prima di cambiare passaggio o salvare.</p>}
        <p>{selected.kind === "condition" ? "Usa le due porte di uscita per i rami sì e no." : "I valori fra {{ }} vengono sostituiti al momento dell’esecuzione con i dati indicati."}</p>
        {selectedRunState && <div className={"node-run run-" + selectedRunState.status}><div className="eyebrow">ULTIMA ESECUZIONE</div>
          <p><strong>{nodeStatusLabels[selectedRunState.status] || selectedRunState.status}</strong>{selectedRunState.duration_ms !== undefined && ` · ${Math.round(selectedRunState.duration_ms)} ms`}{selectedRunState.outcome && ` · ramo «${selectedRunState.outcome}»`}</p>
          {selectedRunState.note && <p>{selectedRunState.note}</p>}{selectedRunState.error && <p className="draft-config-error">{selectedRunState.error}</p>}
          {selectedRunState.input !== undefined && <details><summary>Dati in ingresso</summary><pre>{preview(selectedRunState.input)}</pre></details>}
          {selectedRunState.result !== undefined && <details open><summary>Risultato</summary><pre>{preview(selectedRunState.result)}</pre></details>}
        </div>}
        <button className="text-button" disabled={busy} onClick={() => { update(d => ({ ...d, nodes: d.nodes.filter(n => n.id !== selectedId), edges: d.edges.filter(e => e.source !== selectedId && e.target !== selectedId) })); setSelectedId(""); setConfigError(""); setPending(null); }}>Rimuovi passaggio</button>
      </> : <p>Seleziona un nodo nel flusso per configurarlo.</p>}</aside></div>
  </section>;
}
