import { contractsValid } from "./capabilityContracts";
import { authenticatedFetch } from "./transport";
import { apiBaseUrl, ApiError } from "./api";
import type { AutomationDraft, AutomationRun, DraftSummary, RunSummary, ToolDefinition, ToolFlow } from "../types/contracts";

/** A run the server refused to start, with every reason for the owner. */
export class RunRejectedError extends ApiError {
  constructor(message: string, public readonly problems: string[]) { super(message, "http", 422); }
}
const runStatuses = ["queued", "running", "waiting_approval", "succeeded", "failed", "rejected", "cancelled", "interrupted"];
function runSummaryValid(r: RunSummary) {
  return r && typeof r.id === "string" && typeof r.draft_id === "string" && Number.isInteger(r.draft_version) &&
    (r.mode === "dry_run" || r.mode === "live") && runStatuses.includes(r.status) && typeof r.created_at === "string";
}
function runValid(r: AutomationRun) {
  return runSummaryValid(r) && r.nodes && typeof r.nodes === "object" &&
    Object.values(r.nodes).every(n => n && typeof n.status === "string" && typeof n.label === "string");
}

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
    const response = await authenticatedFetch(apiBaseUrl + path, { ...init, headers, signal: controller.signal });
    if (!response.ok) {
      let detail = response.status === 401 || response.status === 403
        ? "Accesso alle bozze negato. Inserisci il token proprietario configurato in CORA_FILES_TOKEN."
        : "Operazione non riuscita (HTTP " + response.status + ").";
      let problems: string[] | null = null;
      try {
        const body = await response.json();
        if (typeof body.detail === "string") detail = body.detail;
        else if (body.detail && typeof body.detail.message === "string" && Array.isArray(body.detail.problems)) {
          detail = body.detail.message; problems = body.detail.problems.filter((p: unknown) => typeof p === "string");
        }
      } catch { /* proxy error */ }
      if (problems) throw new RunRejectedError(detail, problems);
      throw new ApiError(detail, "http", response.status);
    }
    if (response.status === 204) return null;
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
    if (!d || d.entry?.id !== id || !contractsValid(d.entry.capabilities) || !Array.isArray(d.parameters) || !flowValid(d.flow) ||
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
  async validateDraft(draft: AutomationDraft): Promise<string[]> {
    const d = await request("/tools/drafts/validate", "", {
      method: "POST",
      body: JSON.stringify({ title: draft.title, description: draft.description, nodes: draft.nodes, edges: draft.edges }),
    });
    if (!d || !Array.isArray(d.warnings) || !d.warnings.every((w: unknown) => typeof w === "string"))
      throw new ApiError("Risposta di verifica non valida.", "invalid");
    return d.warnings;
  },
  async deleteDraft(id: string, version: number): Promise<void> {
    await request("/tools/drafts/" + encodeURIComponent(id) + "?version=" + version, "", { method: "DELETE" });
  },
  async duplicateDraft(id: string): Promise<AutomationDraft> {
    const d = await request("/tools/drafts/" + encodeURIComponent(id) + "/duplicate", "", { method: "POST" });
    if (!flowValid(d) || typeof d.id !== "string" || d.status !== "draft" || d.version !== 1 || typeof d.title !== "string" || typeof d.updated_at !== "string")
      throw new ApiError("Risposta duplicazione non valida: ricarica le bozze.", "invalid");
    return d;
  },
  async startRun(draftId: string, version: number, mode: "dry_run" | "live", input: Record<string, unknown>): Promise<AutomationRun> {
    const d = await request("/tools/drafts/" + encodeURIComponent(draftId) + "/runs", "", { method: "POST", body: JSON.stringify({ version, mode, input }) });
    if (!runValid(d)) throw new ApiError("Risposta di avvio non valida: controlla le esecuzioni prima di ritentare.", "invalid");
    return d;
  },
  async listRuns(draftId: string): Promise<RunSummary[]> {
    const d = await request("/tools/drafts/" + encodeURIComponent(draftId) + "/runs");
    if (!Array.isArray(d) || !d.every(runSummaryValid)) throw new ApiError("Elenco esecuzioni non valido.", "invalid");
    return d;
  },
  async getRun(runId: string): Promise<AutomationRun> {
    const d = await request("/tools/runs/" + encodeURIComponent(runId));
    if (!runValid(d) || d.id !== runId) throw new ApiError("Esecuzione non valida.", "invalid");
    return d;
  },
  async cancelRun(runId: string): Promise<AutomationRun> {
    const d = await request("/tools/runs/" + encodeURIComponent(runId) + "/cancel", "", { method: "POST" });
    if (!runValid(d)) throw new ApiError("Risposta di annullamento non valida.", "invalid");
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
