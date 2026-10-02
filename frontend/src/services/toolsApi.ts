import { apiBaseUrl, ApiError } from "./api";
import type { AutomationDraft, DraftSummary, ToolDefinition, ToolFlow } from "../types/contracts";

const kinds = ["trigger", "tool", "condition", "output"];
function flowValid(data: ToolFlow) {
  return data && Array.isArray(data.nodes) && Array.isArray(data.edges) &&
    data.nodes.every(n => n && typeof n.id === "string" && kinds.includes(n.kind) &&
      typeof n.label === "string" && Number.isFinite(n.x) && Number.isFinite(n.y) &&
      n.config && typeof n.config === "object" && !Array.isArray(n.config)) &&
    data.edges.every(e => e && typeof e.id === "string" && typeof e.source === "string" &&
      typeof e.target === "string" && typeof e.label === "string");
}
async function request(path: string, token = "", init: RequestInit = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (token) headers.set("Authorization", "Bearer " + token);
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBaseUrl + path, { ...init, headers, signal: controller.signal });
    if (!response.ok) {
      let detail = response.status === 401 || response.status === 403
        ? "Accesso alle bozze negato. Inserisci il token proprietario configurato in CORA_FILES_TOKEN."
        : "Operazione non riuscita (HTTP " + response.status + ").";
      try { const body = await response.json(); if (typeof body.detail === "string") detail = body.detail; } catch { /* proxy error */ }
      throw new ApiError(detail, "http", response.status);
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError("Risposta tools non valida.", "invalid");
    return await response.json();
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(controller.signal.aborted ? "Tempo scaduto: esito non confermato. Ricarica le bozze prima di ritentare." : "Backend non raggiungibile.", "offline");
  } finally { clearTimeout(timer); }
}
export const toolsApi = {
  async definition(id: string): Promise<ToolDefinition> {
    const d = await request("/tools/definition?tool_id=" + encodeURIComponent(id));
    if (!d || d.entry?.id !== id || !Array.isArray(d.parameters) || !flowValid(d.flow) ||
        typeof d.note !== "string" || typeof d.output_type !== "string" ||
        ![d.operations, d.checks, d.conditions].every(a => Array.isArray(a) && a.every(x => typeof x === "string")) ||
        !d.parameters.every((p: ToolDefinition["parameters"][number]) => p && typeof p.name === "string" && typeof p.type === "string" && typeof p.required === "boolean" && (p.default === null || typeof p.default === "string")))
      throw new ApiError("Definizione tool non valida.", "invalid");
    return d;
  },
  async listDrafts(token = ""): Promise<DraftSummary[]> {
    const d = await request("/tools/drafts", token);
    if (!Array.isArray(d) || !d.every(e => e && typeof e.id === "string" && typeof e.title === "string" &&
        Number.isInteger(e.version) && e.version > 0 && typeof e.updated_at === "string" && e.status === "draft"))
      throw new ApiError("Elenco bozze non valido.", "invalid");
    return d;
  },
  async loadDraft(id: string, token = ""): Promise<AutomationDraft> {
    const d = await request("/tools/drafts/" + encodeURIComponent(id), token);
    if (!flowValid(d) || d.id !== id || d.status !== "draft" || typeof d.title !== "string" || typeof d.description !== "string" || !Number.isInteger(d.version))
      throw new ApiError("Bozza non valida.", "invalid");
    return d;
  },
  async saveDraft(draft: AutomationDraft, token = ""): Promise<AutomationDraft> {
    const d = await request("/tools/drafts" + (draft.id ? "/" + encodeURIComponent(draft.id) : ""), token, {
      method: draft.id ? "PUT" : "POST",
      body: JSON.stringify({ title: draft.title, description: draft.description, nodes: draft.nodes, edges: draft.edges, version: draft.version }),
    });
    if (!flowValid(d) || typeof d.id !== "string" || d.status !== "draft" || !Number.isInteger(d.version) ||
        typeof d.title !== "string" || typeof d.description !== "string" || !Array.isArray(d.warnings) || !d.warnings.every((w: unknown) => typeof w === "string"))
      throw new ApiError("Risposta salvataggio non valida: esito non confermato, ricarica le bozze.", "invalid");
    return d;
  },
};
