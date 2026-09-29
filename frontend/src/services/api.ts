import type {
  BackendChatResponse,
  BackendHealth,
  BackendRegistry,
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

export const api = {
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
