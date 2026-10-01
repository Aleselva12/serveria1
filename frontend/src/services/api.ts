import type {
  BackendChatResponse,
  BackendHealth,
  BackendRegistry,
  ServerTelemetry,
  ServiceStatus,
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
    const response = await fetch(apiBaseUrl + path, {
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
