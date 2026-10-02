export type AgentStatus = "ready" | "busy" | "offline" | "error" | "unknown";
export type ToolEntry = {
  id: string; name: string; description: string; group: string;
  kind: "tool" | "api" | "planned";
  status: "connected" | "unconnected" | "planned";
  agents: string[]; source: string; parameters: string[]; detail: string;
};
export type ToolInventory = { entries: ToolEntry[]; errors: string[]; scope: string };
export type FlowNode = {
  id: string; kind: "trigger" | "tool" | "condition" | "output";
  label: string; x: number; y: number; config: Record<string, unknown>;
  tool_id?: string | null; detail?: string;
};
export type FlowEdge = { id: string; source: string; target: string; label: string; dashed?: boolean };
export type ToolFlow = { nodes: FlowNode[]; edges: FlowEdge[] };
export type ToolDefinition = {
  entry: ToolEntry; parameters: { name: string; type: string; required: boolean; default: string | null }[];
  output_type: string; operations: string[]; checks: string[]; conditions: string[];
  flow: ToolFlow; note: string;
};
export type AutomationDraft = ToolFlow & {
  id?: string; title: string; description: string; version?: number;
  updated_at?: string; status: "draft"; warnings?: string[];
};
export type DraftSummary = { id: string; title: string; version: number; updated_at: string; status: "draft" };
export type ServiceStatus = {
  id: string;
  label: string;
  status: AgentStatus;
  detail?: string;
  checkedAt: string;
};
export type Conversation = { id: string; title: string; updatedAt: string };
export type Message = {
  id: string;
  conversationId: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
  attachments?: { id: string; name: string }[];
  runId?: string;
};
export type Agent = {
  id: string;
  label: string;
  kind: string;
  status: AgentStatus;
  capabilities: string[];
};
export type ArchitectureEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
};
export type RunStep = {
  id: string;
  runId: string;
  nodeId: string;
  status: "pending" | "running" | "completed" | "failed" | "waiting_approval";
  startedAt?: string;
  finishedAt?: string;
  summary: string;
  parentStepId?: string;
};
export type Run = {
  id: string;
  conversationId?: string;
  status: RunStep["status"];
  startedAt: string;
  steps: RunStep[];
};
export type Workspace = {
  id: string;
  label: string;
  kind: "cora" | "project";
  rootLabel: string;
  writable: boolean;
  executable: boolean;
};
export type WorkspaceFile = {
  id: string;
  workspaceId: string;
  path: string;
  language: string;
  content: string;
  revision: string;
};
export type CalendarInput = {
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  notes: string;
};
export type CalendarEvent = CalendarInput & {
  id: string;
  version: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};
export type CalendarHistory = {
  id: string;
  action: string;
  actor: string;
  changed_at: string;
  snapshot: Record<string, unknown>;
};
export type CalendarProposal = {
  id: string;
  actor: string;
  action: "create" | "update" | "delete";
  event_id: string | null;
  expected_version: number | null;
  payload: Partial<CalendarInput>;
  previous: Partial<CalendarEvent>;
  reason: string;
  created_at: string;
  status: string;
};
export type FileItem = {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  createdAt: string;
  source: "upload" | "generated";
  status: "ready" | "processing" | "error";
};
export type ActionApproval = {
  id: string;
  runId: string;
  capability: string;
  description: string;
  status: "pending" | "approved" | "rejected";
};

/** Live server dashboard contract. */
export type ServerMetric = {
  percent: number | null;
  label: string;
  detail?: string;
  temperatureC?: number | null;
};
export type ServerDisk = {
  id: string;
  label: string;
  usedBytes: number;
  totalBytes: number;
};
export type ServerTelemetry = {
  sampledAt: string;
  cpu: ServerMetric;
  ram: ServerMetric;
  gpu?: ServerMetric | null;
  disks: ServerDisk[];
  network?: {
    receiveBitsPerSecond: number;
    transmitBitsPerSecond: number;
    interfaceName?: string;
  } | null;
  power?: { kind: "mains" | "ups" | "battery" | "unknown"; detail?: string };
  cpuHistory?: { at: string; percent: number }[];
};
export type ServerFileNode = {
  id: string;
  parentId: string | null;
  name: string;
  kind: "file" | "folder";
  pathLabel: string;
  mimeType?: string;
  sizeBytes?: number;
  modifiedAt?: string;
  capabilities: Array<"read" | "download" | "upload" | "share" | "delete">;
};
export type ServerStorage = {
  usedBytes: number;
  totalBytes: number;
  sampledAt: string;
};

/** Contracts actually exposed by serveria1, without the proposed /api/v1 prefix. */
export type BackendHealth = {
  status: string;
  ollama_online: boolean;
  model: string;
  agents: string[];
  memory?: {
    total: number;
    by_type: Record<string, number>;
    available?: boolean;
    embedded?: number;
    backend?: string;
    embedding_model?: string;
  };
};
export type BackendComponent = {
  id: string;
  name: string;
  kind: string;
  description: string;
  available: boolean;
  module_available: boolean;
  dependency_status: Record<string, boolean | null>;
  capabilities: { id: string; description: string }[];
};
export type BackendRegistry = {
  project: string;
  component_count: number;
  components: BackendComponent[];
};
export type BackendChatResponse = { response: string; thread_id: string; run_id?: string | null };

export type FileArea = "server" | "library";
export type BrowserNode = {
  path: string;
  name: string;
  kind: "file" | "folder" | "link" | "special";
  sizeBytes: number | null;
  modifiedAt: string;
  mimeType: string;
  capabilities: string[];
};
export type BrowserRoot = {
  id: string;
  label: string;
  path: string;
  writable: boolean;
  available: boolean;
  storage: { usedBytes: number; totalBytes: number; freeBytes: number } | null;
};
export type BrowserListing = {
  rootId: string;
  path: string;
  parentPath: string | null;
  writable: boolean;
  total: number;
  items: BrowserNode[];
};
export type TrashItem = { id: string; path: string; deletedAt: string };

export type SystemContext = {
  id: number;
  content: string;
  version: number;
  updated_at: string | null;
  metadata: Record<string, unknown>;
};

export type PersistentMemory = {
  id: string;
  memory_type: string;
  key: string;
  content: string;
  source: string;
  importance: number;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
  metadata: Record<string, unknown>;
  search_score?: number;
};

export type MemoryEpisode = {
  id: string;
  conversation_id?: string | null;
  title: string;
  summary: string;
  episode_type: string;
  created_at: string;
  agent_id?: string | null;
  importance: number;
  metadata: Record<string, unknown>;
};

export type WorkingMemoryState = {
  agent_id: string;
  thread_id: string;
  state: Record<string, unknown>;
  updated_at: string;
  expires_at?: string | null;
};

/** Rows returned by the PostgreSQL conversation APIs. */
export type SavedConversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  archived: boolean;
};
export type SavedMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

export interface ArchitectureGraph {
  version: string;
  graphs: { id: string; nodes: { id: string; name: string }[]; edges: { source: string; target: string; conditional: boolean; label: string }[] }[];
  delegations: { source: string; target: string; tool: string }[];
  errors: { component: string; error_type: string }[];
}
export interface ExecutionRun {
  id: string; thread_id: string; graph_version: string; status: string;
  started_at: string; duration_ms: number | null; error_count: number; note: string | null;
  metrics?: Record<string, unknown>;
  events: { timestamp: string; kind: string; name: string; status: string; span_id: string | null; parent_id: string | null; duration_ms: number | null; error_type: string | null }[];
}

export interface ArchitectureOverview {
  version: string;
  framework: string;
  nodes: (BackendComponent & { model: string | null })[];
  edges: { source: string; target: string; label: string; kind: "request" | "delegation" }[];
  components: BackendComponent[];
  direct_paths: { id: string; name: string; trigger: string; description: string; routes: string[]; source: string }[];
  automations: { id: string; name: string; trigger: string; description: string; source: string }[];
}
