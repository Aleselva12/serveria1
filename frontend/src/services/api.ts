import { contractsValid } from "./capabilityContracts";
import { authenticatedFetch } from "./transport";
import type {
  ArchitectureGraph,
  ArchitectureOverview,
  ExecutionRun,
  ToolInventory,
  SavedConversation,
  SavedMessage,
  BackendChatResponse,
  BackendHealth,
  BackendRegistry,
  MemoryEpisode,
  PersistentMemory,
  ServerTelemetry,
  ServiceStatus,
  SystemContext,
  WorkingMemoryState,
} from "../types/contracts";

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || "/backend"
).replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly kind: "offline" | "http" | "missing" | "invalid",
    public readonly status?: number,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 10000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await authenticatedFetch(apiBaseUrl + path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
    if (!response.ok) {
      if (
        response.status === 502 ||
        response.status === 503 ||
        response.status === 504
      ) {
        throw new ApiError(
          "Collegamento non riuscito: backend non raggiungibile dal proxy.",
          "offline",
          response.status,
        );
      }
      const kind =
        response.status === 404 || response.status === 501 ? "missing" : "http";
      throw new ApiError(
        kind === "missing"
          ? "Collegamento da realizzare: funzione non esposta dal backend."
          : "Il backend ha restituito un errore (HTTP " +
              response.status +
              ").",
        kind,
        response.status,
      );
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError(
        "La risposta non è JSON. Controlla l’indirizzo del backend.",
        "invalid",
      );
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted)
      throw new ApiError(
        "Tempo di attesa scaduto. Non ho conferma dell’esito della richiesta.",
        "offline",
      );
    if (error instanceof SyntaxError)
      throw new ApiError("Risposta del backend non valida.", "invalid");
    throw new ApiError(
      "Collegamento non riuscito: backend non raggiungibile. Verifica AVVIO e la configurazione della connessione.",
      "offline",
    );
  } finally {
    clearTimeout(timer);
  }
}

function metricValid(metric: ServerTelemetry["cpu"]) {
  return (
    metric &&
    typeof metric.label === "string" &&
    (metric.percent === null ||
      (Number.isFinite(metric.percent) &&
        metric.percent >= 0 &&
        metric.percent <= 100))
  );
}
const nonnegative = (value: number) => Number.isFinite(value) && value >= 0;

export const api = {
  async architectureOverview(): Promise<ArchitectureOverview> {
    const data = await request<ArchitectureOverview>("/api/v1/architecture/overview");
    if (!data || typeof data.version !== "string" || typeof data.framework !== "string" ||
        !Array.isArray(data.nodes) || !data.nodes.every(n => n && typeof n.id === "string" && typeof n.name === "string" && typeof n.available === "boolean" && Array.isArray(n.capabilities) && (n.model === null || typeof n.model === "string")) ||
        !Array.isArray(data.edges) || !data.edges.every(e => e && typeof e.source === "string" && typeof e.target === "string" && typeof e.label === "string" && ["request", "delegation"].includes(e.kind) && data.nodes.some(n => n.id === e.source) && data.nodes.some(n => n.id === e.target)) ||
        !Array.isArray(data.components) || !data.components.every(c => c && typeof c.id === "string" && typeof c.name === "string" && typeof c.description === "string" && typeof c.available === "boolean" && Array.isArray(c.capabilities)) ||
        !Array.isArray(data.direct_paths) || !data.direct_paths.every(p => p && typeof p.id === "string" && typeof p.name === "string" && typeof p.trigger === "string" && typeof p.description === "string" && Array.isArray(p.routes) && p.routes.every(r => typeof r === "string")) ||
        !Array.isArray(data.automations) || !data.automations.every(a => a && typeof a.id === "string" && typeof a.name === "string" && typeof a.trigger === "string" && typeof a.description === "string"))
      throw new ApiError("Panoramica dell’architettura non valida.", "invalid");
    return data;
  },
  async architectureGraph(): Promise<ArchitectureGraph> {
    const data = await request<ArchitectureGraph>("/api/v1/architecture/graph");
    if (!data || typeof data.version !== "string" || !Array.isArray(data.graphs) || !Array.isArray(data.delegations) || !Array.isArray(data.errors) || !data.graphs.every(g => typeof g.id === "string" && Array.isArray(g.nodes) && Array.isArray(g.edges) && g.nodes.every(n => typeof n.id === "string" && typeof n.name === "string") && g.edges.every(e => typeof e.source === "string" && typeof e.target === "string" && typeof e.conditional === "boolean"))) throw new ApiError("Grafo non valido.", "invalid");
    return data;
  },
  async executionRuns(): Promise<ExecutionRun[]> {
    const data = await request<ExecutionRun[]>("/api/v1/runs?limit=50");
    if (!Array.isArray(data) || !data.every(r => typeof r.id === "string" && typeof r.thread_id === "string" && Number.isFinite(Date.parse(r.started_at)) && Array.isArray(r.events) && r.events.every(e => typeof e.name === "string" && typeof e.kind === "string" && Number.isFinite(Date.parse(e.timestamp))))) throw new ApiError("Tracce non valide.", "invalid");
    return data;
  },
  async executionRun(id:string): Promise<ExecutionRun> {
    return request<ExecutionRun>("/api/v1/runs/"+encodeURIComponent(id));
  },
  async toolInventory(): Promise<ToolInventory> {
    const data = await request<ToolInventory>("/tools/inventory");
    if (!data || !Array.isArray(data.entries) || !Array.isArray(data.errors) ||
        !data.errors.every(e => typeof e === "string") || typeof data.scope !== "string" ||
        !data.entries.every(e => e && typeof e.id === "string" && typeof e.name === "string" &&
          typeof e.description === "string" && typeof e.group === "string" && typeof e.source === "string" &&
          typeof e.detail === "string" && contractsValid(e.capabilities) && ["tool", "api", "planned"].includes(e.kind) &&
          ["connected", "unconnected", "planned"].includes(e.status) &&
          Array.isArray(e.agents) && e.agents.every(a => typeof a === "string") &&
          Array.isArray(e.parameters) && e.parameters.every(p => typeof p === "string")))
      throw new ApiError("Inventario tools non valido.", "invalid");
    return data;
  },
  async conversations(): Promise<SavedConversation[]> {
    const data = await request<SavedConversation[]>("/conversations?limit=500");
    if (!Array.isArray(data) || !data.every(c => c &&
      typeof c.id === "string" && typeof c.title === "string" &&
      Number.isFinite(Date.parse(c.created_at)) && Number.isFinite(Date.parse(c.updated_at)) &&
      typeof c.archived === "boolean"))
      throw new ApiError("Elenco conversazioni non valido.", "invalid");
    return data;
  },
  async conversationMessages(id: string): Promise<SavedMessage[]> {
    const data = await request<SavedMessage[]>(
      "/conversations/" + encodeURIComponent(id) + "/messages?limit=2000",
    );
    if (!Array.isArray(data) || !data.every(m => m &&
      typeof m.id === "string" && m.conversation_id === id &&
      ["user", "assistant", "system"].includes(m.role) && typeof m.content === "string" &&
      Number.isFinite(Date.parse(m.created_at))))
      throw new ApiError("Messaggi della conversazione non validi.", "invalid");
    return data;
  },

  async telemetry(): Promise<ServerTelemetry> {
    const data = await request<ServerTelemetry>("/api/v1/server/telemetry");
    if (
      !data ||
      !Number.isFinite(Date.parse(data.sampledAt)) ||
      !metricValid(data.cpu) ||
      !metricValid(data.ram) ||
      (data.gpu && !metricValid(data.gpu)) ||
      !Array.isArray(data.disks) ||
      !data.disks.every(
        (d) =>
          d &&
          typeof d.id === "string" &&
          typeof d.label === "string" &&
          nonnegative(d.usedBytes) &&
          nonnegative(d.totalBytes) &&
          d.usedBytes <= d.totalBytes,
      ) ||
      (data.network &&
        (!nonnegative(data.network.receiveBitsPerSecond) ||
          !nonnegative(data.network.transmitBitsPerSecond))) ||
      (data.cpuHistory &&
        (!Array.isArray(data.cpuHistory) ||
          !data.cpuHistory.every(
            (p) =>
              p &&
              Number.isFinite(Date.parse(p.at)) &&
              nonnegative(p.percent) &&
              p.percent <= 100,
          ))) ||
      (data.power &&
        !["mains", "ups", "battery", "unknown"].includes(data.power.kind))
    )
      throw new ApiError("Misurazioni del server non valide.", "invalid");
    return data;
  },
  async services(): Promise<{ checkedAt: string; services: ServiceStatus[] }> {
    const data = await request<{
      checkedAt: string;
      services: ServiceStatus[];
    }>("/api/v1/system/status");
    if (
      !data ||
      !Number.isFinite(Date.parse(data.checkedAt)) ||
      !Array.isArray(data.services) ||
      !data.services.every(
        (s) =>
          s &&
          typeof s.id === "string" &&
          typeof s.label === "string" &&
          ["ready", "busy", "offline", "error", "unknown"].includes(s.status) &&
          Number.isFinite(Date.parse(s.checkedAt)),
      )
    )
      throw new ApiError("Stato dei servizi non valido.", "invalid");
    return data;
  },
  async health(): Promise<BackendHealth> {
    const data = await request<BackendHealth>("/health");
    if (
      !data ||
      data.status !== "ok" ||
      typeof data.ollama_online !== "boolean" ||
      typeof data.model !== "string" ||
      !Array.isArray(data.agents)
    )
      throw new ApiError(
        "Questo indirizzo non restituisce lo stato atteso di Cora.",
        "invalid",
      );
    return data;
  },
  async registry(): Promise<BackendRegistry> {
    const data = await request<BackendRegistry>("/capabilities");
    if (
      !data ||
      !Array.isArray(data.components) ||
      !data.components.every(
        (c) =>
          c &&
          typeof c.id === "string" &&
          typeof c.name === "string" &&
          typeof c.available === "boolean" &&
          Array.isArray(c.capabilities) &&
          c.capabilities.every(
            (cap) =>
              cap &&
              typeof cap.id === "string" &&
              typeof cap.description === "string",
          ),
      )
    )
      throw new ApiError("Registro dei componenti non valido.", "invalid");
    return data;
  },
  async systemContext(): Promise<SystemContext> {
    return request<SystemContext>("/memory/context");
  },
  async saveSystemContext(content: string, expectedVersion: number): Promise<SystemContext> {
    return request<SystemContext>("/memory/context", {
      method: "PUT",
      body: JSON.stringify({ content, expected_version:expectedVersion }),
    });
  },
  async memories(query = "", memoryType = "", limit = 100, includeExpired = false): Promise<PersistentMemory[]> {
    const params = new URLSearchParams({
      query,
      memory_type: memoryType,
      limit: String(limit),
      include_expired:String(includeExpired),
    });
    return request<PersistentMemory[]>("/memory?" + params.toString());
  },
  async saveMemory(input: {
    memory_type: string;
    key: string;
    content: string;
    source?: string;
    importance?: number;
    assertion?: PersistentMemory["assertion"];
    confidence?: number | null;
    expires_at?: string | null;
    expected_version?: number;
    expected_memory_id?: string;
  }): Promise<PersistentMemory> {
    return request<PersistentMemory>("/memory", {
      method: "POST",
      body: JSON.stringify({
        source: "user_explicit",
        importance: 4,
        ...input,
      }),
    });
  },
  async memoryHistory(id: string): Promise<{version:number; snapshot:PersistentMemory; editor:string; created_at:string}[]> {
    return request("/memory/"+encodeURIComponent(id)+"/history");
  },
  async deleteMemory(id: string): Promise<{ deleted: boolean }> {
    return request<{ deleted: boolean }>("/memory/" + encodeURIComponent(id), {
      method: "DELETE",
    });
  },
  async episodes(limit = 50): Promise<MemoryEpisode[]> {
    return request<MemoryEpisode[]>("/memory/episodes?limit=" + limit);
  },
  async workingMemory(): Promise<WorkingMemoryState[]> {
    return request<WorkingMemoryState[]>("/memory/working");
  },
  async clearWorkingMemory(agentId: string, threadId: string): Promise<{ deleted: boolean }> {
    return request<{ deleted: boolean }>(
      "/memory/working/" +
        encodeURIComponent(agentId) +
        "/" +
        encodeURIComponent(threadId),
      { method: "DELETE" },
    );
  },
  async chat(message: string, threadId: string): Promise<BackendChatResponse> {
    const data = await request<BackendChatResponse>(
      "/chat",
      {
        method: "POST",
        body: JSON.stringify({ message, thread_id: threadId }),
      },
      300000,
    );
    if (
      !data ||
      typeof data.response !== "string" ||
      typeof data.thread_id !== "string"
    )
      throw new ApiError("Risposta chat non valida.", "invalid");
    return data;
  },
};
