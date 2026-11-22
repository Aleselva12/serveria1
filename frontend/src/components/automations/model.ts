// Pure helpers of the Automazioni page: tool catalog, canvas <-> draft conversion,
// run overlay, schedules and recipes. No React and no I/O, so tests can import it.
import type { AutomationRun, FlowEdge, FlowNode, RunNodeState, ToolEntry } from "../../types/contracts";

export type Effect = "read" | "compute" | "write" | "delegate" | "none";
export type Kind = FlowNode["kind"];
export type CatalogTool = {
  id: string; name: string; description: string; group: string; effect: Effect;
  executable: boolean; connected: boolean; required: string[];
  properties: Record<string, { type?: string; description?: string; enum?: unknown[]; default?: unknown }>;
};
export type NodeStatus = RunNodeState["status"] | "running";
export type CanvasData = {
  label: string; kind: Kind; toolId: string | null; config: Record<string, unknown>;
  effect: Effect; subtitle: string; status?: NodeStatus; [key: string]: unknown;
};
export type CanvasNode = { id: string; type?: string; position: { x: number; y: number }; data: CanvasData };
export type CanvasEdge = { id: string; source: string; target: string; label?: unknown; type?: string; animated?: boolean; className?: string };
export type Schedule = { enabled: boolean; time: string; days: number[]; mode: "dry_run" | "live" };

export const EFFECTS: Record<Effect, { label: string; hint: string }> = {
  read: { label: "Legge", hint: "Consulta dati senza modificarli: sicuro da provare." },
  compute: { label: "Calcola", hint: "Elabora i dati ricevuti, non modifica nulla." },
  write: { label: "Scrive", hint: "Modifica dati: nella prova a vuoto non parte, dal vivo chiede conferma se previsto." },
  delegate: { label: "Delega", hint: "Affida il compito a un agente specializzato: nella prova a vuoto non parte." },
  none: { label: "Base", hint: "Blocco di struttura del flusso." },
};
export const KIND_LABEL: Record<Kind, string> = { trigger: "Avvio", tool: "Tool", condition: "Condizione", output: "Risultato" };
export const OPERATORS: { id: string; label: string; unary?: boolean }[] = [
  { id: "eq", label: "è uguale a" }, { id: "ne", label: "è diverso da" },
  { id: "gt", label: "è maggiore di" }, { id: "gte", label: "è almeno" },
  { id: "lt", label: "è minore di" }, { id: "lte", label: "è al massimo" },
  { id: "contains", label: "contiene" }, { id: "not_contains", label: "non contiene" },
  { id: "empty", label: "è vuoto", unary: true }, { id: "not_empty", label: "non è vuoto", unary: true },
];
export const DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
export const STATUS_LABEL: Record<NodeStatus, string> = {
  pending: "In attesa", running: "In corso", done: "Completato", skipped: "Saltato", simulated: "Simulato",
  waiting_approval: "Attende conferma", failed: "Non riuscito", rejected: "Rifiutato", cancelled: "Annullato",
};

/** Tools a draft may reference: the server rejects planned entries in drafts. */
export function catalogFrom(entries: ToolEntry[]): CatalogTool[] {
  return entries.filter(e => e.kind !== "planned").map((e): CatalogTool => {
    const contract = e.capabilities?.[0];
    const schema = (contract?.input_schema ?? {}) as { required?: unknown; properties?: unknown };
    return {
      id: e.id, name: e.name, description: e.description || e.detail || "", group: e.group || "Altro",
      effect: contract ? contract.effect : "none" as Effect, executable: !!contract, connected: e.status === "connected" || e.status === "direct",
      required: Array.isArray(schema.required) ? schema.required.filter((r): r is string => typeof r === "string") : [],
      properties: schema.properties && typeof schema.properties === "object" ? schema.properties as CatalogTool["properties"] : {},
    };
  }).sort((a, b) => a.group.localeCompare(b.group, "it") || a.name.localeCompare(b.name, "it"));
}

export function prettyName(name: string) {
  const plain = name.replace(/_tool$/, "").replace(/_/g, " ").trim();
  return plain ? plain[0].toUpperCase() + plain.slice(1) : name;
}

function subtitleFor(kind: Kind, tool: CatalogTool | undefined, config: Record<string, unknown>) {
  if (kind === "trigger") {
    const schedule = scheduleOf(config);
    return schedule?.enabled ? describeSchedule(schedule) : "Avvio manuale";
  }
  if (kind === "condition") {
    const op = OPERATORS.find(o => o.id === config.op);
    return op ? `${String(config.left ?? "?")} ${op.label}${op.unary ? "" : " " + String(config.right ?? "?")}` : "Regola da completare";
  }
  if (kind === "output") return "Raccoglie i risultati";
  if (!tool) return "Scegli un tool";
  return tool.group + " · " + EFFECTS[tool.effect].label;
}

export function nodeData(node: Pick<FlowNode, "kind" | "label" | "config" | "tool_id">, catalog: CatalogTool[]): CanvasData {
  const tool = node.tool_id ? catalog.find(t => t.id === node.tool_id) : undefined;
  return {
    label: node.label, kind: node.kind, toolId: node.tool_id ?? null, config: node.config ?? {},
    effect: node.kind === "tool" ? tool?.effect ?? "none" : "none", subtitle: subtitleFor(node.kind, tool, node.config ?? {}),
  };
}

export function toCanvas(draft: { nodes: FlowNode[]; edges: FlowEdge[] }, catalog: CatalogTool[]) {
  const nodes = draft.nodes.map(n => ({ id: n.id, type: "cora", position: { x: n.x, y: n.y }, data: nodeData(n, catalog) }));
  const edges = draft.edges.map(e => ({ id: e.id, source: e.source, target: e.target, label: e.label || undefined, type: "smoothstep" }));
  return { nodes, edges };
}

/** Canvas state back to the draft shape. Positions are shifted into the 0..10000 range the server accepts. */
export function fromCanvas(nodes: CanvasNode[], edges: CanvasEdge[]): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const minX = Math.min(0, ...nodes.map(n => n.position.x)), minY = Math.min(0, ...nodes.map(n => n.position.y));
  const clamp = (v: number) => Math.max(0, Math.min(10000, Math.round(v)));
  return {
    nodes: nodes.map(n => ({
      id: n.id, kind: n.data.kind, label: n.data.label.trim() || KIND_LABEL[n.data.kind],
      x: clamp(n.position.x - minX + (minX < 0 ? 20 : 0)), y: clamp(n.position.y - minY + (minY < 0 ? 20 : 0)),
      config: n.data.config ?? {}, tool_id: n.data.kind === "tool" ? n.data.toolId : null,
    })),
    edges: edges.map(e => ({ id: e.id, source: e.source, target: e.target, label: typeof e.label === "string" ? e.label : "" })),
  };
}

export function uniqueId(prefix: string, taken: Iterable<string>) {
  const used = new Set(taken);
  for (let i = 1; ; i++) if (!used.has(`${prefix}-${i}`)) return `${prefix}-${i}`;
}

/** Edge label the engine needs: a condition's branches are "sì" then "no". */
export function edgeLabelFor(sourceKind: Kind | undefined, existing: CanvasEdge[], source: string) {
  if (sourceKind !== "condition") return undefined;
  const used = new Set(existing.filter(e => e.source === source).map(e => e.label));
  return used.has("sì") ? (used.has("no") ? undefined : "no") : "sì";
}

/** Node state while a run is executing: a pending node that has started is shown as running. */
export function statusOf(state: RunNodeState | undefined): NodeStatus | undefined {
  if (!state) return undefined;
  return state.status === "pending" && state.started_at ? "running" : state.status;
}

export function overlayRun<T extends CanvasNode>(nodes: T[], run: AutomationRun | null): T[] {
  return nodes.map(n => {
    const status = run ? statusOf(run.nodes[n.id]) : undefined;
    return n.data.status === status ? n : { ...n, data: { ...n.data, status } };
  });
}

/** Edges whose source handed data on: animated while a run is shown. */
export function carriedEdges<T extends CanvasEdge>(edges: T[], run: AutomationRun | null): T[] {
  return edges.map(e => {
    const source = run?.nodes[e.source];
    const flowing = !!source && (source.status === "done" || source.status === "simulated") &&
      !(source.kind === "condition" && source.outcome && (e.label ?? "") !== source.outcome);
    const muted = !!source && source.kind === "condition" && !!source.outcome && (e.label ?? "") !== source.outcome;
    const className = flowing ? "flowing" : muted ? "muted" : undefined;
    return e.animated === flowing && e.className === className ? e : { ...e, animated: flowing, className };
  });
}

/** Run nodes in the order the engine settled them, for the trace panel. */
export function traceOf(run: AutomationRun | null) {
  if (!run) return [];
  return Object.entries(run.nodes)
    .filter(([, s]) => s.status !== "pending" || s.started_at)
    .sort(([, a], [, b]) => { const x = a.started_at ?? "~", y = b.started_at ?? "~"; return x < y ? -1 : x > y ? 1 : 0; })
    .map(([id, s]) => ({ id, label: s.label, status: statusOf(s)!, note: s.error ?? s.note ?? (s.outcome ? "Ramo «" + s.outcome + "»" : ""), duration: s.duration_ms }));
}

export function scheduleOf(config: Record<string, unknown> | undefined): Schedule | null {
  const raw = config?.schedule as Partial<Schedule> | undefined;
  if (!raw || typeof raw !== "object") return null;
  const time = typeof raw.time === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(raw.time) ? raw.time : "08:00";
  const days = Array.isArray(raw.days) ? [...new Set(raw.days.filter(d => Number.isInteger(d) && d >= 0 && d <= 6))].sort() : [0, 1, 2, 3, 4, 5, 6];
  return { enabled: raw.enabled === true, time, days: days.length ? days : [0, 1, 2, 3, 4, 5, 6], mode: raw.mode === "live" ? "live" : "dry_run" };
}

export function describeSchedule(s: Schedule) {
  const when = s.days.length === 7 ? "Ogni giorno" : s.days.join() === "0,1,2,3,4" ? "Giorni feriali" : s.days.map(d => DAYS[d]).join(", ");
  return `${when} alle ${s.time}`;
}

/** Next local start time of an enabled schedule; days count from Monday = 0. */
export function nextRun(s: Schedule | null, now = new Date()): Date | null {
  if (!s?.enabled) return null;
  const [h, m] = s.time.split(":").map(Number);
  for (let offset = 0; offset < 8; offset++) {
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset, h, m, 0, 0);
    if (s.days.includes((day.getDay() + 6) % 7) && day > now) return day;
  }
  return null;
}

/** Every {{input.name}} the flow expects at start, as the engine computes it. */
export function inputNames(nodes: { data: { config: Record<string, unknown> } }[]) {
  const names: string[] = [];
  const scan = (value: unknown) => {
    if (typeof value === "string") {
      for (const m of value.matchAll(/\{\{\s*input\.([A-Za-z0-9_-]+)/g)) if (!names.includes(m[1])) names.push(m[1]);
    } else if (value && typeof value === "object") Object.values(value).forEach(scan);
  };
  nodes.forEach(n => scan(n.data.config));
  return names;
}

export type Recipe = {
  id: string; name: string; description: string; category: string;
  steps: { id: string; kind: Kind; label: string; tool?: string; config?: Record<string, unknown> }[];
  links: [string, string, string?][];
};

// Recipes use only tools the server declares; a missing tool leaves its step to be chosen.
export const RECIPES: Recipe[] = [
  {
    id: "salute", name: "Salute del server", description: "Lo stato di Cora in un colpo d'occhio.", category: "SISTEMA",
    steps: [
      { id: "avvio", kind: "trigger", label: "Ogni mattina", config: { schedule: { enabled: false, time: "07:30", days: [0, 1, 2, 3, 4, 5, 6], mode: "dry_run" } } },
      { id: "stato", kind: "tool", label: "Stato del sistema", tool: "tools.py:system_status_tool" },
      { id: "eventi", kind: "tool", label: "Eventi recenti", tool: "tools.py:recent_system_events_tool" },
      { id: "fine", kind: "output", label: "Rapporto" },
    ],
    links: [["avvio", "stato"], ["avvio", "eventi"], ["stato", "fine"], ["eventi", "fine"]],
  },
  {
    id: "mail", name: "Mail del giorno", description: "Se ci sono mail, l'agente email le riassume.", category: "COMUNICAZIONE",
    steps: [
      { id: "avvio", kind: "trigger", label: "Avvio" },
      { id: "mail", kind: "tool", label: "Mail di oggi", tool: "email_agent/email_tools.py:get_daily_emails" },
      { id: "check", kind: "condition", label: "Ci sono mail?", config: { left: "{{mail}}", op: "not_empty" } },
      { id: "riassunto", kind: "tool", label: "Riassunto", tool: "tools.py:email_agent_tool", config: { query: "Riassumi in breve queste email: {{mail}}" } },
      { id: "fine", kind: "output", label: "Risultato" },
    ],
    links: [["avvio", "mail"], ["mail", "check"], ["check", "riassunto", "sì"], ["check", "fine", "no"], ["riassunto", "fine"]],
  },
  {
    id: "agenda", name: "Agenda del periodo", description: "Gli appuntamenti fra due date.", category: "CALENDARIO",
    steps: [
      { id: "avvio", kind: "trigger", label: "Avvio", config: { input: { inizio: "", fine: "" } } },
      { id: "eventi", kind: "tool", label: "Appuntamenti", tool: "core/calendar_tools.py:calendar_list_events", config: { start: "{{input.inizio}}", end: "{{input.fine}}" } },
      { id: "fine", kind: "output", label: "Agenda" },
    ],
    links: [["avvio", "eventi"], ["eventi", "fine"]],
  },
  {
    id: "documenti", name: "Domanda ai documenti", description: "Cerca nella libreria e nei documenti locali.", category: "CONOSCENZA",
    steps: [
      { id: "avvio", kind: "trigger", label: "Avvio", config: { input: { domanda: "" } } },
      { id: "libreria", kind: "tool", label: "Libreria IA", tool: "tools.py:library_search", config: { query: "{{input.domanda}}" } },
      { id: "locali", kind: "tool", label: "Documenti locali", tool: "search_agent/search_tools.py:search_local_documents", config: { query: "{{input.domanda}}" } },
      { id: "fine", kind: "output", label: "Fonti trovate" },
    ],
    links: [["avvio", "libreria"], ["avvio", "locali"], ["libreria", "fine"], ["locali", "fine"]],
  },
  {
    id: "calcolo", name: "Gioco dei numeri", description: "Calcola e decide: il modo più semplice per capire i rami.", category: "PALESTRA",
    steps: [
      { id: "avvio", kind: "trigger", label: "Avvio", config: { input: { espressione: "6*7" } } },
      { id: "conto", kind: "tool", label: "Calcolatrice", tool: "tools.py:calculator_tool", config: { expression: "{{input.espressione}}" } },
      { id: "check", kind: "condition", label: "Più di 40?", config: { left: "{{conto}}", op: "gt", right: "40" } },
      { id: "grande", kind: "output", label: "Numero grande" },
      { id: "piccolo", kind: "output", label: "Numero piccolo" },
    ],
    links: [["avvio", "conto"], ["conto", "check"], ["check", "grande", "sì"], ["check", "piccolo", "no"]],
  },
];

/** Lay a recipe out left to right by depth; tools missing from the catalog stay unselected. */
export function recipeDraft(recipe: Recipe, catalog: CatalogTool[]): { title: string; description: string; nodes: FlowNode[]; edges: FlowEdge[]; missing: string[] } {
  const depth: Record<string, number> = {};
  const visit = (id: string, d: number) => {
    if ((depth[id] ?? -1) >= d) return;
    depth[id] = d;
    recipe.links.filter(([a]) => a === id).forEach(([, b]) => visit(b, d + 1));
  };
  recipe.steps.filter(s => s.kind === "trigger").forEach(s => visit(s.id, 0));
  const rows: Record<number, number> = {};
  const missing: string[] = [];
  const nodes = recipe.steps.map(s => {
    const d = depth[s.id] ?? 0, row = rows[d] = (rows[d] ?? -1) + 1;
    const known = s.tool && catalog.some(t => t.id === s.tool);
    if (s.tool && !known) missing.push(s.label);
    return { id: s.id, kind: s.kind, label: s.label, x: 40 + d * 240, y: 60 + row * 190, config: structuredClone(s.config ?? {}), tool_id: known ? s.tool! : null };
  });
  const edges = recipe.links.map(([a, b, label], i) => ({ id: `e${i + 1}-${a}-${b}`, source: a, target: b, label: label ?? "" }));
  return { title: recipe.name, description: recipe.description, nodes, edges, missing };
}

export function emptyDraft() {
  return {
    title: "Nuovo flusso", description: "",
    nodes: [
      { id: "avvio", kind: "trigger" as const, label: "Avvio", x: 40, y: 120, config: {}, tool_id: null },
      { id: "fine", kind: "output" as const, label: "Risultato", x: 520, y: 120, config: {}, tool_id: null },
    ],
    edges: [] as FlowEdge[],
  };
}
