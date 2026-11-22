import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Handle, Position, ReactFlow, ReactFlowProvider, addEdge, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node, type NodeChange, type EdgeChange, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "@fontsource/work-sans/400.css";
import "@fontsource/work-sans/500.css";
import "@fontsource/work-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "./automations.css";
import {
  Activity, AlertTriangle, ArrowLeft, Ban, BookOpen, Bot, Calculator, CheckCircle2, CircleDot, Copy, Download,
  Eye, FilePlus2, Flag, GitBranch, Layers, Loader2, Maximize, Orbit, PenLine, Play, Plus, Radar, Save, Search, Settings2,
  ShieldCheck, Sparkles, Square, Trash2, Workflow, X, Zap, ZoomIn, ZoomOut,
} from "lucide-react";
import { api } from "../../services/api";
import { RunRejectedError, toolsApi } from "../../services/toolsApi";
import type { AutomationRun, DraftSummary, RunSummary, ToolEntry } from "../../types/contracts";
import {
  DAYS, EFFECTS, KIND_LABEL, OPERATORS, RECIPES, STATUS_LABEL, carriedEdges, catalogFrom, describeSchedule, edgeLabelFor,
  emptyDraft, explainRefs, fromCanvas, inputNames, nextRun, nodeData, overlayRun, recipeDraft, scheduleOf, toCanvas, traceOf,
  uniqueId, type CanvasData, type CatalogTool, type Effect, type Kind, type Schedule,
} from "./model";
import LiveServer from "./LiveServer";
import { AREAS, paramLabel, type Area } from "./toolGuide";

type FlowNodeT = Node<CanvasData, "cora">;
type Tab = "editor" | "runs" | "tools" | "live";
type Current = { id?: string; version?: number; title: string; description: string };
const ACTIVE = new Set(["queued", "running", "waiting_approval"]);

const kindIcon: Record<Kind, typeof Zap> = { trigger: Zap, tool: Workflow, condition: GitBranch, output: Flag };
const effectIcon: Record<Effect, typeof Zap> = { read: Eye, compute: Calculator, write: PenLine, delegate: Bot, none: CircleDot };
function iconFor(data: Pick<CanvasData, "kind" | "effect">) {
  return data.kind === "tool" ? effectIcon[data.effect] : kindIcon[data.kind];
}
const statusIcon = (status: string) =>
  status === "done" || status === "succeeded" ? CheckCircle2 : status === "failed" || status === "rejected" ? AlertTriangle :
  status === "cancelled" || status === "interrupted" || status === "skipped" ? Ban : status === "waiting_approval" ? ShieldCheck :
  status === "simulated" ? Sparkles : status === "running" || status === "queued" ? Loader2 : CircleDot;
const runLabel: Record<string, string> = {
  queued: "In coda", running: "In corso", waiting_approval: "Attende conferma in Attività", succeeded: "Completata",
  failed: "Non riuscita", rejected: "Rifiutata", cancelled: "Annullata", interrupted: "Interrotta",
};

function CoraNode({ data, selected }: NodeProps<FlowNodeT>) {
  const Icon = iconFor(data);
  const StatusIcon = data.status ? statusIcon(data.status) : null;
  const tag = data.kind === "tool" ? EFFECTS[data.effect].label : KIND_LABEL[data.kind];
  return (
    <div className={`auto-node kind-${data.kind} effect-${data.effect} ${selected ? "selected" : ""} ${data.status ? "status-" + data.status : ""}`}>
      {data.kind !== "trigger" && <Handle type="target" position={Position.Left} />}
      <div className="auto-node-top">
        <span><Icon size={22} /></span>
        <small>{StatusIcon ? <><StatusIcon size={11} className={data.status === "running" ? "spin" : ""} />{STATUS_LABEL[data.status!]}</> : tag}</small>
      </div>
      <strong>{data.label}</strong>
      <small>{data.subtitle}</small>
      {data.kind !== "output" && <Handle type="source" position={Position.Right} />}
    </div>
  );
}
const nodeTypes = { cora: CoraNode };

function Editor() {
  const flow = useReactFlow<FlowNodeT, Edge>();
  const [nodes, setNodes, onNodesChangeBase] = useNodesState<FlowNodeT>([]);
  const [edges, setEdges, onEdgesChangeBase] = useEdgesState<Edge>([]);
  const [catalog, setCatalog] = useState<CatalogTool[]>([]);
  const [planned, setPlanned] = useState<ToolEntry[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [current, setCurrent] = useState<Current>({ title: "Nuovo flusso", description: "" });
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState<Tab>("editor");
  const [selected, setSelected] = useState("");
  const [nodeTab, setNodeTab] = useState<"Parametri" | "Input" | "Output">("Parametri");
  const [search, setSearch] = useState("");
  const [area, setArea] = useState<"Essenziali" | Area>("Essenziali");
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [problems, setProblems] = useState<string[]>([]);
  const [run, setRun] = useState<AutomationRun | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [input, setInput] = useState<Record<string, string>>({});
  const [confirmLive, setConfirmLive] = useState(false);
  const [lastField, setLastField] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);

  const node = nodes.find(n => n.id === selected);
  const trigger = nodes.find(n => n.data.kind === "trigger");
  const schedule = scheduleOf(trigger?.data.config);
  const names = useMemo(() => inputNames(nodes), [nodes]);
  const running = !!run && ACTIVE.has(run.status);

  const onNodesChange = useCallback((changes: NodeChange<FlowNodeT>[]) => {
    if (changes.some(c => c.type !== "select" && c.type !== "dimensions")) setDirty(true);
    onNodesChangeBase(changes);
  }, [onNodesChangeBase]);
  const onEdgesChange = useCallback((changes: EdgeChange<Edge>[]) => {
    if (changes.some(c => c.type !== "select")) setDirty(true);
    onEdgesChangeBase(changes);
  }, [onEdgesChangeBase]);

  // Keep the test input in step with the {{input.x}} names the flow uses.
  useEffect(() => {
    setInput(value => {
      const defaults = (trigger?.data.config.input ?? {}) as Record<string, unknown>;
      return Object.fromEntries(names.map(n => [n, value[n] ?? String(defaults[n] ?? "")]));
    });
  }, [names.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  function show(graph: { nodes: Parameters<typeof toCanvas>[0]["nodes"]; edges: Parameters<typeof toCanvas>[0]["edges"] }, tools = catalog) {
    const canvas = toCanvas(graph, tools);
    setNodes(canvas.nodes as FlowNodeT[]);
    setEdges(canvas.edges);
    setSelected(canvas.nodes.find(n => n.data.kind === "tool")?.id ?? canvas.nodes[0]?.id ?? "");
    setRun(null); setProblems([]);
    setTimeout(() => void flow.fitView({ padding: .22 }), 60);
  }

  async function refreshDrafts() {
    const list = await toolsApi.listDrafts();
    setDrafts(list);
    return list;
  }

  async function openDraft(id: string, tools = catalog, force = false) {
    if (dirty && !force && !window.confirm("Ci sono modifiche non salvate. Aprire comunque un altro flusso?")) return;
    try {
      const d = await toolsApi.loadDraft(id);
      setCurrent({ id: d.id, version: d.version, title: d.title, description: d.description });
      show(d, tools); setDirty(false); setWarnings(d.warnings ?? []); setTab("editor");
      setRuns(await toolsApi.listRuns(id).catch(() => []));
      setNotice("Flusso «" + d.title + "» aperto");
    } catch (e) { setNotice((e as Error).message); }
  }

  function openRecipe(index: number, tools = catalog) {
    if (dirty && !window.confirm("Ci sono modifiche non salvate. Caricare comunque la ricetta?")) return;
    const recipe = RECIPES[index];
    const draft = recipeDraft(recipe, tools);
    setCurrent({ title: draft.title, description: draft.description });
    show(draft, tools); setDirty(true); setRuns([]); setWarnings([]); setTab("editor");
    setNotice(draft.missing.length ? "Ricetta caricata: scegli il tool per " + draft.missing.join(", ") : "Ricetta caricata · salvala per provarla");
  }

  function newFlow() {
    if (dirty && !window.confirm("Ci sono modifiche non salvate. Iniziare comunque un nuovo flusso?")) return;
    setCurrent({ title: "Nuovo flusso", description: "" });
    show(emptyDraft()); setDirty(true); setRuns([]); setWarnings([]); setTab("editor");
    setNotice("Nuovo flusso: aggiungi i tool dalla libreria e collegali");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let tools: CatalogTool[] = [];
      try {
        const inventory = await api.toolInventory();
        tools = catalogFrom(inventory.entries);
        if (cancelled) return;
        setCatalog(tools); setPlanned(inventory.entries.filter(e => e.kind === "planned"));
      } catch (e) { setNotice("Catalogo tool non disponibile: " + (e as Error).message); }
      try {
        const list = await refreshDrafts();
        if (cancelled) return;
        if (list.length) await openDraft(list[0].id, tools); else openRecipe(0, tools);
      } catch (e) {
        if (!cancelled) { openRecipe(0, tools); setNotice("Bozze non disponibili: " + (e as Error).message); }
      }
      if (!cancelled) setLoaded(true);
    })();
    return () => { cancelled = true; if (poll.current) clearTimeout(poll.current); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run overlay: node states and flowing edges follow the run on screen.
  useEffect(() => {
    setNodes(ns => overlayRun(ns, run));
    setEdges(es => carriedEdges(es, run));
  }, [run, setNodes, setEdges]);

  function watch(runId: string) {
    if (poll.current) clearTimeout(poll.current);
    const tick = async () => {
      try {
        const fresh = await toolsApi.getRun(runId);
        setRun(fresh);
        if (ACTIVE.has(fresh.status)) { poll.current = setTimeout(tick, fresh.status === "waiting_approval" ? 4000 : 900); return; }
        setNotice("Esecuzione " + runLabel[fresh.status].toLowerCase() + (fresh.error ? ": " + fresh.error : ""));
        if (current.id || fresh.draft_id) setRuns(await toolsApi.listRuns(fresh.draft_id).catch(() => []));
      } catch (e) { setNotice((e as Error).message); poll.current = setTimeout(tick, 4000); }
    };
    void tick();
  }

  function updateNode(id: string, patch: Partial<CanvasData>) {
    setNodes(ns => ns.map(n => {
      if (n.id !== id) return n;
      const merged = { ...n.data, ...patch };
      const fresh = nodeData({ kind: merged.kind, label: merged.label, config: merged.config, tool_id: merged.toolId }, catalog);
      return { ...n, data: { ...merged, effect: fresh.effect, subtitle: fresh.subtitle } };
    }));
    setDirty(true);
  }
  const setConfig = (id: string, config: Record<string, unknown>) => updateNode(id, { config });

  function addNode(kind: Kind, tool?: CatalogTool) {
    const id = uniqueId(tool ? tool.name.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 30) || "tool" : kind, nodes.map(n => n.id));
    const right = Math.max(40, ...nodes.map(n => n.position.x));
    const data = nodeData({ kind, label: tool ? tool.title : KIND_LABEL[kind], config: kind === "condition" ? { left: "", op: "not_empty" } : {}, tool_id: tool?.id ?? null }, catalog);
    setNodes(ns => [...ns.map(n => ({ ...n, selected: false })), { id, type: "cora", position: { x: right + 60, y: 300 + (ns.length % 3) * 40 }, data, selected: true }]);
    setSelected(id); setCatalogOpen(false); setTab("editor"); setDirty(true); setNodeTab("Parametri");
    setNotice("«" + (tool ? tool.title : KIND_LABEL[kind]) + "» aggiunto: collegalo trascinando dal pallino a destra di un altro blocco al suo pallino a sinistra");
    setTimeout(() => void flow.fitView({ padding: .22 }), 60);
  }

  const onConnect = useCallback((c: Connection) => {
    setEdges(es => {
      const sourceKind = nodes.find(n => n.id === c.source)?.data.kind;
      const label = edgeLabelFor(sourceKind, es, c.source ?? "");
      return addEdge({ ...c, id: uniqueId("e", es.map(e => e.id)), type: "smoothstep", label }, es);
    });
    setDirty(true);
  }, [nodes, setEdges]);

  async function save(): Promise<Current | null> {
    setBusy(true);
    try {
      const graph = fromCanvas(nodes, edges);
      const saved = await toolsApi.saveDraft({ ...current, ...graph, status: "draft" });
      const next = { id: saved.id, version: saved.version, title: saved.title, description: saved.description };
      setCurrent(next); setDirty(false); setWarnings(saved.warnings ?? []);
      await refreshDrafts().catch(() => undefined);
      setNotice("Salvato · versione " + saved.version + (saved.warnings?.length ? " · " + saved.warnings.length + " avvisi" : ""));
      return next;
    } catch (e) { setNotice((e as Error).message); return null; }
    finally { setBusy(false); }
  }

  async function execute(mode: "dry_run" | "live") {
    setConfirmLive(false);
    const values = input;
    const target = dirty || !current.id ? await save() : current;
    if (!target?.id || !target.version) return;
    setBusy(true); setProblems([]);
    try {
      const started = await toolsApi.startRun(target.id, target.version, mode, values);
      setRun(started); setTab("editor");
      setNotice(mode === "dry_run" ? "Prova avviata · i blocchi che modificano dati non partono" : "Esecuzione vera avviata");
      watch(started.id);
    } catch (e) {
      if (e instanceof RunRejectedError) { setProblems(e.problems); setNotice(e.message + " Vedi la traccia."); }
      else setNotice((e as Error).message);
    } finally { setBusy(false); }
  }

  async function stop() {
    if (!run) return;
    try { setRun(await toolsApi.cancelRun(run.id)); setNotice("Annullamento richiesto: il passaggio in corso termina prima di fermarsi"); }
    catch (e) { setNotice((e as Error).message); }
  }

  async function openRun(id: string) {
    try { const r = await toolsApi.getRun(id); setRun(r); setTab("editor"); if (ACTIVE.has(r.status)) watch(r.id); }
    catch (e) { setNotice((e as Error).message); }
  }

  async function duplicate() {
    if (!current.id) return;
    try { const copy = await toolsApi.duplicateDraft(current.id); await refreshDrafts(); if (copy.id) await openDraft(copy.id, catalog, true); }
    catch (e) { setNotice((e as Error).message); }
  }

  async function remove() {
    if (!current.id || !current.version || !window.confirm("Eliminare definitivamente «" + current.title + "»?")) return;
    try {
      await toolsApi.deleteDraft(current.id, current.version);
      const list = await refreshDrafts();
      if (list.length) await openDraft(list[0].id, catalog, true); else { setDirty(false); setCurrent({ title: "Nuovo flusso", description: "" }); show(emptyDraft()); }
      setNotice("Flusso eliminato");
    } catch (e) { setNotice((e as Error).message); }
  }

  function exportFlow() {
    const blob = new Blob([JSON.stringify({ ...current, ...fromCanvas(nodes, edges) }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = (current.title || "flusso").replace(/[^\w-]+/g, "-") + ".json"; a.click();
    URL.revokeObjectURL(url);
    setNotice("Flusso esportato in JSON");
  }

  function toggleSchedule() {
    if (!trigger) { setNotice("Aggiungi un nodo di avvio per pianificare il flusso"); return; }
    const s: Schedule = schedule ?? { enabled: false, time: "08:00", days: [0, 1, 2, 3, 4, 5, 6], mode: "dry_run" };
    setConfig(trigger.id, { ...trigger.data.config, schedule: { ...s, enabled: !s.enabled } });
    setSelected(trigger.id);
    setNotice(!s.enabled ? "Pianificazione attivata: salva per renderla effettiva" : "Pianificazione disattivata: salva per confermare");
  }

  function insertRef(ref: string) {
    if (!node || !lastField) { void navigator.clipboard?.writeText(ref); setNotice(ref + " copiato: incollalo in un parametro"); return; }
    setConfig(node.id, { ...node.data.config, [lastField]: String(node.data.config[lastField] ?? "") + ref });
  }

  const q = search.trim().toLowerCase();
  const visibleTools = q
    ? catalog.filter(t => `${t.title} ${t.hint} ${t.area} ${t.name}`.toLowerCase().includes(q))
    : catalog.filter(t => area === "Essenziali" ? t.essential : t.area === area);
  const areaCount = (a: Area) => catalog.filter(t => t.area === a).length;
  const runNode = node && run ? run.nodes[node.id] : undefined;
  const trace = traceOf(run);
  const upstream = useMemo(() => {
    if (!node) return [];
    const seen = new Set<string>(), stack = [node.id];
    while (stack.length) {
      const id = stack.pop()!;
      edges.filter(e => e.target === id).forEach(e => { if (!seen.has(e.source)) { seen.add(e.source); stack.push(e.source); } });
    }
    return nodes.filter(n => seen.has(n.id) && n.data.kind !== "trigger" && n.data.kind !== "output");
  }, [node, nodes, edges]);

  const library = <>
    <div className="auto-search"><Search size={15} /><input aria-label="Cerca un blocco" placeholder="Cerca: mail, calendario, documenti…" value={search} onChange={e => setSearch(e.target.value)} /></div>
    {!q && <div className="auto-areas" role="tablist" aria-label="Aree">
      {(["Essenziali", ...AREAS.filter(a => a !== "Strumenti tecnici" && areaCount(a))] as ("Essenziali" | Area)[]).map(a =>
        <button key={a} role="tab" aria-selected={area === a} className={`source-button ${area === a ? "on" : ""}`} onClick={() => setArea(a)}>{a}</button>)}
    </div>}
    <div className="auto-base-blocks">
      {(["trigger", "condition", "output"] as Kind[]).map(k => { const I = kindIcon[k]; return <button className="source-button" key={k} onClick={() => addNode(k)}><I size={14} />{KIND_LABEL[k]}</button>; })}
    </div>
    <div className="auto-tool-list">
      {visibleTools.map(t => { const I = effectIcon[t.effect]; return (
        <button className={`source-button effect-${t.effect}`} key={t.id} onClick={() => addNode("tool", t)} title={EFFECTS[t.effect].hint}>
          <I size={16} /><span><strong>{t.title}</strong><small>{t.hint}</small></span><Plus size={13} />
        </button>); })}
      {!visibleTools.length && <p className="auto-empty">{catalog.length ? "Nessun blocco trovato." : "Blocchi non disponibili: il server non risponde."}</p>}
    </div>
    {!q && areaCount("Strumenti tecnici") > 0 && <button className={`source-button auto-tech-link ${area === "Strumenti tecnici" ? "on" : ""}`}
      onClick={() => setArea(area === "Strumenti tecnici" ? "Essenziali" : "Strumenti tecnici")}>
      {area === "Strumenti tecnici" ? "← Torna agli essenziali" : `Strumenti tecnici (${areaCount("Strumenti tecnici")}) per programmazione e diagnosi`}</button>}
  </>;

  const counts = { read: 0, compute: 0, write: 0, delegate: 0, none: 0 } as Record<Effect, number>;
  catalog.forEach(t => counts[t.effect]++);

  return <div className="auto-workspace">
    <aside className="auto-sidebar">
      <div className="auto-sidebar-title"><Workflow size={17} /><strong>Automazioni</strong></div>
      <div className="auto-side-label">I MIEI FLUSSI <span>{String(drafts.length).padStart(2, "0")}</span></div>
      {drafts.map(d => <button className={`source-button auto-flow-item ${current.id === d.id ? "selected" : ""}`} key={d.id} disabled={running} onClick={() => void openDraft(d.id)}>
        <Workflow size={15} /><span>{d.title}<small>V{d.version} · {new Date(d.updated_at).toLocaleDateString("it-IT")}</small></span>
      </button>)}
      {!drafts.length && <p className="auto-empty">Nessun flusso salvato: parti da un esempio qui sotto.</p>}
      <button className="source-button auto-flow-item auto-new" disabled={running} onClick={newFlow}><FilePlus2 size={15} /><span>Nuovo flusso</span></button>
      <div className="auto-side-label">ESEMPI DA CUI PARTIRE <span>{String(RECIPES.length).padStart(2, "0")}</span></div>
      {RECIPES.map((r, i) => <button className="source-button auto-flow-item" key={r.id} disabled={running} onClick={() => openRecipe(i)} title={r.description}>
        <BookOpen size={15} /><span>{r.name}<small>{r.category}</small></span>
      </button>)}
      <div className="auto-side-label">BLOCCHI DA AGGIUNGERE</div>
      {library}
      <div className="auto-sidebar-foot"><ShieldCheck size={16} /><span>Provare è sicuro<small>«Prova» non modifica nulla. Solo «Esegui davvero» agisce, e chiede conferma per le modifiche.</small></span></div>
    </aside>

    <main className="auto-main">
      <div className="auto-titlebar">
        <div><h1>Automazioni<span>.</span></h1><p className="auto-lead">Metti in fila dei blocchi: un <b>avvio</b>, una o più <b>azioni</b>, un <b>risultato</b>. Premi <b>Prova</b> per vedere cosa succederebbe, senza toccare nulla.</p></div>
        <div className="auto-effect-legend">{(["read", "compute", "write", "delegate"] as Effect[]).map(e => { const I = effectIcon[e]; return <span key={e} className={`effect-${e}`} title={EFFECTS[e].hint}><I size={12} />{EFFECTS[e].label}</span>; })}</div>
      </div>

      <div className="auto-flowbar">
        <div>
          <input aria-label="Nome del flusso" value={current.title} maxLength={120} onChange={e => { setCurrent(c => ({ ...c, title: e.target.value })); setDirty(true); }} />
          <small><span className={`ops-live-dot ${dirty ? "warn" : ""}`} />{dirty ? "MODIFICHE NON SALVATE" : current.version ? "SALVATO" : "NUOVO"}<span> · {nodes.length} blocchi{warnings.length ? ` · ${warnings.length} cose da sistemare` : ""}</span></small>
        </div>
        <div className="auto-actions">
          <button className="source-button" title="Esporta JSON" aria-label="Esporta JSON" onClick={exportFlow}><Download size={16} /></button>
          <button className="source-button" title="Duplica flusso" aria-label="Duplica flusso" disabled={!current.id || busy} onClick={() => void duplicate()}><Copy size={16} /></button>
          <button className="source-button" title="Elimina flusso" aria-label="Elimina flusso" disabled={!current.id || busy || running} onClick={() => void remove()}><Trash2 size={16} /></button>
          <button className="source-button" title="Salva" aria-label="Salva" disabled={busy} onClick={() => void save()}><Save size={16} /></button>
          <button className={`source-button auto-switch ${schedule?.enabled ? "on" : ""}`} role="switch" aria-checked={!!schedule?.enabled} aria-label="Pianificazione" onClick={toggleSchedule}><i /></button>
          <span>{schedule?.enabled ? "Parte da solo: " + describeSchedule(schedule).toLowerCase() : "Parte solo a mano"}</span>
        </div>
      </div>

      <div className="auto-tabs" role="tablist" aria-label="Viste automazioni">
        {([["editor", "Flusso", Workflow], ["runs", "Storico", Activity], ["tools", "Tutti i blocchi", Layers], ["live", "Server vivo", Orbit]] as const).map(([id, label, I]) =>
          <button className="source-button" key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}><I size={14} />{label}{id === "runs" && <small>{runs.length}</small>}</button>)}
        <span>{running ? "IN CORSO…" : schedule?.enabled ? "PROSSIMO AVVIO: " + (nextRun(schedule)?.toLocaleString("it-IT", { weekday: "short", hour: "2-digit", minute: "2-digit" }) ?? "—") : "AVVIO MANUALE"}</span>
      </div>

      {tab === "editor" && <>
        <div className="auto-editor">
          <div className="auto-canvas">
            <div className="auto-canvas-label"><span>IL FLUSSO · TRASCINA PER SPOSTARE, COLLEGA I PALLINI</span><span>{run ? (run.mode === "live" ? "ESECUZIONE VERA · " : "PROVA · ") + runLabel[run.status].toUpperCase() : ""}</span></div>
            {!loaded && <div className="auto-loading"><Loader2 className="spin" /> Caricamento…</div>}
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onNodeClick={(_, n) => { setSelected(n.id); setLastField(null); }} onPaneClick={() => setSelected("")}
              fitView fitViewOptions={{ padding: .22 }} minZoom={.25} maxZoom={1.8} deleteKeyCode={["Backspace", "Delete"]}
              nodesDraggable={!running} nodesConnectable={!running} proOptions={{ hideAttribution: true }} aria-label="Mappa del flusso di automazione">
              <Background gap={22} size={1} />
            </ReactFlow>
            <div className="auto-canvas-tools">
              <button className="source-button" title="Aggiungi nodo" aria-label="Aggiungi nodo" onClick={() => setCatalogOpen(true)}><Plus size={17} /></button>
              <button className="source-button" title="Ingrandisci" aria-label="Ingrandisci" onClick={() => void flow.zoomIn()}><ZoomIn size={16} /></button>
              <button className="source-button" title="Riduci" aria-label="Riduci" onClick={() => void flow.zoomOut()}><ZoomOut size={16} /></button>
              <button className="source-button" title="Adatta mappa" aria-label="Adatta mappa" onClick={() => void flow.fitView({ padding: .2 })}><Maximize size={16} /></button>
              {run && !running && <button className="source-button" title="Pulisci risultati" aria-label="Pulisci risultati" onClick={() => setRun(null)}><X size={16} /></button>}
            </div>
            <div className="auto-run-buttons">
              {running
                ? <button className="source-button auto-execute" onClick={() => void stop()}><Square size={15} />Ferma</button>
                : <>
                  <button className="source-button auto-live-run" disabled={busy} onClick={() => setConfirmLive(true)} title="Esegue davvero le azioni"><Zap size={14} />Esegui davvero</button>
                  <button className="source-button auto-execute" disabled={busy} onClick={() => void execute("dry_run")}>{busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />}Prova</button>
                </>}
            </div>
          </div>

          <aside className="auto-inspector">
            <div className="auto-side-label">BLOCCO SELEZIONATO <Settings2 size={13} /></div>
            {node ? <>
              <div className={`auto-inspector-icon effect-${node.data.effect}`}>{(() => { const I = iconFor(node.data); return <I size={22} />; })()}</div>
              <input className="auto-node-name" aria-label="Nome nodo" value={node.data.label} maxLength={160} onChange={e => updateNode(node.id, { label: e.target.value })} />
              <p>{node.data.kind === "tool" ? (node.data.toolId ? EFFECTS[node.data.effect].hint : "Scegli qui sotto cosa deve fare questo blocco.") : KIND_LABEL[node.data.kind] + " · " + node.data.subtitle}</p>
              <div className="auto-node-tabs">{(["Parametri", "Input", "Output"] as const).map(t => <button className={`source-button ${nodeTab === t ? "selected" : ""}`} onClick={() => setNodeTab(t)} key={t}>{t === "Parametri" ? "Impostazioni" : t === "Input" ? "Cosa entra" : "Cosa esce"}</button>)}</div>
              {nodeTab === "Parametri" ? <Inspector node={node} catalog={catalog} names={names} upstream={upstream} labels={Object.fromEntries(nodes.map(n => [n.id, n.data.label]))}
                onConfig={c => setConfig(node.id, c)} onTool={id => {
                  const tool = catalog.find(t => t.id === id);
                  updateNode(node.id, { toolId: id || null, label: tool && (node.data.label === KIND_LABEL.tool || !node.data.toolId) ? tool.title : node.data.label });
                }} onField={setLastField} onRef={insertRef} />
                : <pre className="auto-json">{runNode
                  ? JSON.stringify(nodeTab === "Input" ? runNode.input ?? (node.data.kind === "trigger" ? run?.input : null) ?? null : runNode.result ?? runNode.error ?? runNode.note ?? null, null, 2)
                  : "Ancora niente da mostrare.\nPremi «Prova» per vedere cosa entra\ne cosa esce da questo blocco."}</pre>}
              <div className="auto-node-actions">
                <button className="source-button" disabled={running} onClick={() => {
                  const id = uniqueId(node.id.replace(/-\d+$/, ""), nodes.map(n => n.id));
                  setNodes(ns => [...ns, { ...node, id, selected: false, position: { x: node.position.x + 40, y: node.position.y + 170 }, data: { ...node.data, status: undefined, config: structuredClone(node.data.config) } }]);
                  setSelected(id); setDirty(true);
                }}><Copy size={14} />Duplica</button>
                <button className="source-button" title="Elimina nodo" aria-label="Elimina nodo" disabled={running} onClick={() => {
                  setNodes(ns => ns.filter(n => n.id !== node.id)); setEdges(es => es.filter(e => e.source !== node.id && e.target !== node.id)); setSelected(""); setDirty(true);
                }}><Trash2 size={14} /></button>
              </div>
            </> : <div className="auto-empty auto-hint">
              <p>Clicca un blocco del flusso per vederlo e cambiarlo.</p>
              <ol className="auto-steps"><li>Scegli un <b>esempio</b> o aggiungi <b>blocchi</b> dalla colonna a sinistra.</li><li><b>Collega</b> i blocchi trascinando dal pallino a destra a quello a sinistra.</li><li>Premi <b>Prova</b>: vedrai ogni passaggio illuminarsi.</li></ol>
              {warnings.length > 0 && <ul className="auto-warnings">{warnings.map(w => <li key={w}><AlertTriangle size={12} />{w}</li>)}</ul>}
            </div>}
          </aside>
        </div>

        <div className="auto-bottom">
          <section>
            <div className="auto-side-label">VALORI PER LA PROVA</div>
            {names.length ? <div className="auto-inputs">{names.map(n => <label key={n}>{paramLabel(n)}
              <input value={input[n] ?? ""} onChange={e => setInput(v => ({ ...v, [n]: e.target.value }))} placeholder={"valore di «" + n + "»"} /></label>)}</div>
              : <p className="auto-note">Questo flusso non ha bisogno di valori iniziali: premi <b>Prova</b>.</p>}
          </section>
          <section>
            <div className="auto-side-label">COSA È SUCCESSO <span>{problems.length ? problems.length + " DA SISTEMARE" : trace.length ? trace.length + " PASSAGGI" : ""}</span></div>
            <div className="auto-log-list">
              {problems.length > 0 ? problems.map(p => <div key={p} className="status-failed"><AlertTriangle size={13} /><strong>{p}</strong></div>)
                : trace.length ? trace.map((l, i) => { const I = statusIcon(l.status); return (
                  <div key={l.id} className={"status-" + l.status} onClick={() => { setSelected(l.id); setNodeTab("Output"); }}>
                    <I size={13} className={l.status === "running" ? "spin" : ""} /><span>{String(i + 1).padStart(2, "0")}</span><strong>{l.label}</strong>
                    <small>{STATUS_LABEL[l.status]}{l.duration ? ` · ${Math.round(l.duration)} ms` : ""}{l.note ? " · " + l.note : ""}</small>
                  </div>); })
                : <div className="auto-log-empty"><Activity size={23} /><span>Ancora nessuna prova</span><small>Qui comparirà ogni passaggio, con il suo esito</small></div>}
            </div>
          </section>
        </div>
      </>}

      {tab === "runs" && <section className="auto-content">
        <div className="auto-content-head"><h2>Storico</h2><span>{current.id ? "LE ULTIME VOLTE CHE QUESTO FLUSSO È PARTITO" : "SALVA IL FLUSSO PER PROVARLO"}</span></div>
        {runs.length ? <div className="auto-run-table">{runs.map(r => { const I = statusIcon(r.status); return (
          <article key={r.id} className={"status-" + r.status} onClick={() => void openRun(r.id)}>
            <I size={18} /><strong>{runLabel[r.status]}</strong><span>{r.mode === "live" ? "Esecuzione vera" : "Prova"}{(r as { origin?: string }).origin === "schedule" ? " · partita da sola" : ""}</span>
            <time>{new Date(r.created_at).toLocaleString("it-IT")}</time><small>{r.error ?? "Apri sulla mappa"}</small>
          </article>); })}</div>
          : <div className="auto-empty-state"><Activity size={36} /><h3>Questo flusso non è ancora partito.</h3><button className="source-button" onClick={() => setTab("editor")}><ArrowLeft size={14} />Torna al flusso</button></div>}
      </section>}

      {tab === "tools" && <section className="auto-content">
        <div className="auto-content-head"><h2>Tutti i blocchi</h2><span>{catalog.length} AZIONI CHE CORA SA FARE</span></div>
        {AREAS.filter(a => a !== "Strumenti tecnici" && areaCount(a)).map(a => <div key={a} className="auto-catalog-group">
          <div className="auto-side-label">{a.toUpperCase()} <span>{areaCount(a)}</span></div>
          <div className="auto-block-grid">{catalog.filter(t => t.area === a).map(t => <BlockCard key={t.id} tool={t} onAdd={() => addNode("tool", t)} />)}</div>
        </div>)}
        {areaCount("Strumenti tecnici") > 0 && <details className="auto-catalog-group auto-tech">
          <summary>Strumenti tecnici ({areaCount("Strumenti tecnici")}) · programmazione, struttura e diagnosi</summary>
          <div className="auto-block-grid">{catalog.filter(t => t.area === "Strumenti tecnici").map(t => <BlockCard key={t.id} tool={t} onAdd={() => addNode("tool", t)} />)}</div>
        </details>}
        {planned.length > 0 && <p className="auto-note">In arrivo: {planned.map(p => p.name.replace(/_/g, " ")).join(" · ")}</p>}
      </section>}

      {tab === "live" && <LiveServer catalog={catalog} usedTools={nodes.filter(n => n.data.toolId).map(n => n.data.toolId!)} run={run}
        drafts={drafts.length} onAdd={t => addNode("tool", t)} />}

      <div className="auto-status" role="status"><span className={`ops-live-dot ${running ? "pulse" : ""}`} />{notice || "Pronto · «Prova» non modifica nulla"}</div>
    </main>

    {catalogOpen && <div className="ops-modal-backdrop" onClick={() => setCatalogOpen(false)}>
      <section className="ops-modal auto-catalog-modal" role="dialog" aria-modal="true" aria-label="Aggiungi un nodo" onClick={e => e.stopPropagation()}>
        <div className="auto-content-head"><h2>Aggiungi un nodo</h2><button className="source-button" autoFocus aria-label="Chiudi catalogo" onClick={() => setCatalogOpen(false)}><X size={18} /></button></div>
        {library}
      </section>
    </div>}

    {confirmLive && <div className="ops-modal-backdrop" onClick={() => setConfirmLive(false)}>
      <section className="ops-modal" role="dialog" aria-modal="true" aria-label="Esecuzione vera" onClick={e => e.stopPropagation()}>
        <Zap size={22} /><h2>Eseguire davvero?</h2>
        <p>Questa volta le azioni partono sul serio. Quelle che modificano qualcosa e chiedono conferma si fermano in <b>Notifiche › Da decidere</b> finché non approvi.</p>
        {nodes.filter(n => n.data.kind === "tool" && (n.data.effect === "write" || n.data.effect === "delegate")).map(n =>
          <div className="ops-modal-item" key={n.id}><PenLine size={15} />{n.data.label}<small>{EFFECTS[n.data.effect].label}</small></div>)}
        <div className="auto-modal-actions">
          <button className="source-button" onClick={() => setConfirmLive(false)}>Annulla</button>
          <button className="source-button auto-execute static" onClick={() => void execute("live")}><Radar size={15} />Sì, esegui</button>
        </div>
      </section>
    </div>}
  </div>;
}

function Inspector({ node, catalog, names, upstream, labels, onConfig, onTool, onField, onRef }: {
  node: FlowNodeT; catalog: CatalogTool[]; names: string[]; upstream: FlowNodeT[]; labels: Record<string, string>;
  onConfig: (c: Record<string, unknown>) => void; onTool: (id: string) => void; onField: (f: string | null) => void; onRef: (r: string) => void;
}) {
  const config = node.data.config;
  const refs = <div className="auto-refs">
    <small>Usa il risultato di un blocco precedente</small>
    <div>{upstream.map(u => <button className="source-button" key={u.id} onClick={() => onRef(`{{${u.id}}}`)} title={"Risultato di " + u.data.label}>{u.data.label}</button>)}
      {names.map(n => <button className="source-button input" key={n} onClick={() => onRef(`{{input.${n}}}`)} title="Valore che inserisci alla partenza">{paramLabel(n)}</button>)}
      <button className="source-button input" onClick={() => onRef("{{input.nuovo}}")} title="Un valore da chiedere alla partenza: rinomina «nuovo» come preferisci">+ valore da chiedere</button></div>
  </div>;

  if (node.data.kind === "trigger") {
    const s = scheduleOf(config) ?? { enabled: false, time: "08:00", days: [0, 1, 2, 3, 4, 5, 6], mode: "dry_run" as const };
    const set = (patch: Partial<Schedule>) => onConfig({ ...config, schedule: { ...s, ...patch } });
    const defaults = (config.input ?? {}) as Record<string, unknown>;
    const next = nextRun(s);
    return <>
      <label className="auto-check"><input type="checkbox" checked={s.enabled} onChange={e => set({ enabled: e.target.checked })} />Avvia da solo a un orario</label>
      <div className={s.enabled ? "" : "auto-dim"}>
        <label>Orario<input type="time" value={s.time} onChange={e => set({ time: e.target.value })} /></label>
        <div className="auto-days">{DAYS.map((d, i) => <button key={d} className={`source-button ${s.days.includes(i) ? "on" : ""}`} onClick={() => set({ days: s.days.includes(i) ? s.days.filter(x => x !== i) : [...s.days, i] })}>{d}</button>)}</div>
        <label>Modalità<select value={s.mode} onChange={e => set({ mode: e.target.value as Schedule["mode"] })}><option value="dry_run">Prova a vuoto (sicura)</option><option value="live">Dal vivo</option></select></label>
        <p className="auto-note">{s.enabled && next ? "Prossimo avvio: " + next.toLocaleString("it-IT", { weekday: "long", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Senza pianificazione si avvia solo a mano."}</p>
      </div>
      {names.length > 0 && <>
        <div className="auto-side-label sub">VALORI QUANDO PARTE DA SOLO</div>
        {names.map(n => <label key={n}>{paramLabel(n)}<input value={String(defaults[n] ?? "")} onChange={e => onConfig({ ...config, input: { ...defaults, [n]: e.target.value } })} /></label>)}
      </>}
    </>;
  }

  if (node.data.kind === "condition") {
    const op = OPERATORS.find(o => o.id === config.op);
    return <>
      <label>Cosa controllare<input value={String(config.left ?? "")} placeholder="clicca un blocco qui sotto" onFocus={() => onField("left")} onChange={e => onConfig({ ...config, left: e.target.value })} />
        {explainRefs(config.left, labels) && <small className="auto-ref-explain">{explainRefs(config.left, labels)}</small>}</label>
      <label>Regola<select value={String(config.op ?? "")} onChange={e => onConfig({ ...config, op: e.target.value })}>{OPERATORS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
      {!op?.unary && <label>Confronta con<input value={String(config.right ?? "")} onFocus={() => onField("right")} onChange={e => onConfig({ ...config, right: e.target.value })} /></label>}
      <p className="auto-note">Collega due uscite: la prima diventa il ramo <b>sì</b>, la seconda il ramo <b>no</b>.</p>
      {refs}
    </>;
  }

  if (node.data.kind === "output") return <p className="auto-note">Raccoglie i risultati dei passaggi collegati. In un flusso possono esserci più risultati, uno per ramo.</p>;

  const tool = catalog.find(t => t.id === node.data.toolId);
  const fields = tool ? [...new Set([...Object.keys(tool.properties), ...Object.keys(config)])] : Object.keys(config);
  // Fixed split: a field never moves while the owner types in it.
  const main = fields.filter(f => !tool || tool.required.includes(f) || !(f in tool.properties));
  const extra = fields.filter(f => !main.includes(f));
  const setField = (name: string, raw: string | boolean) => {
    const type = tool?.properties[name]?.type;
    let value: unknown = raw;
    if (typeof raw === "string" && (type === "integer" || type === "number") && raw.trim() !== "" && !raw.includes("{{") && !Number.isNaN(Number(raw))) value = Number(raw);
    const next = { ...config };
    if (raw === "" && !tool?.required.includes(name)) delete next[name]; else next[name] = value;
    onConfig(next);
  };
  return <>
    <label>Cosa fa<select value={node.data.toolId ?? ""} onChange={e => onTool(e.target.value)}>
      <option value="">— scegli un'azione —</option>
      {AREAS.map(a => { const list = catalog.filter(t => t.area === a); return list.length ? <optgroup key={a} label={a}>{list.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</optgroup> : null; })}
    </select></label>
    {tool && <p className={`auto-effect-badge effect-${tool.effect}`}><b>{EFFECTS[tool.effect].label}</b> · {tool.hint}</p>}
    {main.map(field)}
    {extra.length > 0 && <details className="auto-extra" open={extra.some(f => config[f] !== undefined) || undefined}><summary>Altre opzioni ({extra.length})</summary>{extra.map(field)}</details>}
    {tool && !fields.length && <p className="auto-note">Questa azione non ha bisogno di impostazioni.</p>}
    {tool && refs}
  </>;
  function field(name: string) {
      const prop = tool?.properties[name] ?? {};
      const required = tool?.required.includes(name);
      const value = config[name];
      if (prop.type === "boolean") return <label className="auto-check" key={name}><input type="checkbox" checked={value === true} onChange={e => setField(name, e.target.checked)} />{paramLabel(name)}</label>;
      if (Array.isArray(prop.enum)) return <label key={name}>{paramLabel(name)}{required && " *"}<select value={String(value ?? "")} onChange={e => setField(name, e.target.value)}><option value="">—</option>{prop.enum.map(v => <option key={String(v)}>{String(v)}</option>)}</select></label>;
      const text = typeof value === "string" || typeof value === "number" ? String(value) : value === undefined ? "" : JSON.stringify(value);
      return <label key={name} title={prop.description}>{paramLabel(name)}{required && " *"}
        <input value={text} placeholder={prop.description ?? ""} onFocus={() => onField(name)} onChange={e => setField(name, e.target.value)} />
        {explainRefs(value, labels) && <small className="auto-ref-explain">{explainRefs(value, labels)}</small>}</label>;
  }
}

function BlockCard({ tool, onAdd }: { tool: CatalogTool; onAdd: () => void }) {
  const I = effectIcon[tool.effect];
  return <button className={`source-button auto-block effect-${tool.effect}`} onClick={onAdd} title="Aggiungi al flusso">
    <I size={18} /><span><strong>{tool.title}</strong><small>{tool.hint}</small><em>{EFFECTS[tool.effect].label}{tool.connected ? "" : " · non collegato"}</em></span><Plus size={15} />
  </button>;
}

export default function Automations() {
  return <div className="ops-page auto-page"><ReactFlowProvider><Editor /></ReactFlowProvider></div>;
}
