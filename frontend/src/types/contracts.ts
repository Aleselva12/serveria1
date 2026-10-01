export type AgentStatus = "ready" | "busy" | "offline" | "error" | "unknown";
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
export type ArchitectureGraph = {
  version: string;
  nodes: Agent[];
  edges: ArchitectureEdge[];
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
export type CalendarEvent = {
  id: string;
  title: string;
  start: string;
  end: string;
  notes?: string;
  source: "user";
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
  memory?: { total: number; by_type: Record<string, number> };
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
export type BackendChatResponse = { response: string; thread_id: string };

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
