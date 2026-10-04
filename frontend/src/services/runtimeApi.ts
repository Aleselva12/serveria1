import { apiBaseUrl } from "./api";
import { authenticatedFetch } from "./transport";
export type RunSnapshot = { cancel_requested?:boolean; stop_reason?:string|null; persistence_error?:string|null; created_at?:string; finished_at?:string|null; target?:string; parent_run_id?:string|null; approval_ids?:string[]; id: string; thread_id: string; status: string; output: string; elapsed_ms: number; error_type: string | null; result: { response: string; thread_id: string } | null; agents: Record<string,string>; timings: Record<string,unknown> };
export async function runtimeRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1" + path, { ...init, headers: { "Content-Type": "application/json", ...init.headers }, signal: init.signal ?? AbortSignal.timeout(15000) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Operazione non riuscita.");
  return data as T;
}
export async function streamChat(message: string, threadId: string, onRun: (id:string)=>void, onText: (text:string)=>void, onState:(state:string)=>void) {
  const run = await runtimeRequest<RunSnapshot>("/chat/runs", { method: "POST", body: JSON.stringify({ message, thread_id: threadId }) });
  onRun(run.id); onState(run.status);
  return streamRun(run, onText, onState);
}
export async function streamRun(run: RunSnapshot, onText: (text:string)=>void, onState:(state:string)=>void, signal?: AbortSignal) {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1/runtime/runs/" + run.id + "/events", { signal });
  if (!response.ok || !response.body) throw new Error("Streaming non disponibile. Consulta Attività per l'esito.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "", text = "", final: RunSnapshot | null = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = pending.indexOf("\n\n")) >= 0) {
        const frame = pending.slice(0, boundary); pending = pending.slice(boundary + 2);
        const line = frame.split("\n").find(l => l.startsWith("data: "));
        if (!line) continue;
        const event = JSON.parse(line.slice(6));
        if (frame.includes("event: result")) final = event as RunSnapshot;
        else if (frame.includes("event: resync")) { text = event.output || ""; onText(text); onState(event.status); }
        else if (event.type === "chat.reset") { text = ""; onText(text); }
        else if (event.type === "chat.delta") { text += event.payload.text; onText(text); }
        else if (event.type === "run.state") onState(event.payload.status);
        else if (event.type === "agent.state" && event.payload.status === "running") onState("Agente: " + event.source);
      }
    }
  } finally { reader.releaseLock(); }
  if (!final) final = await runtimeRequest<RunSnapshot>("/runtime/runs/" + run.id);
  if (!["completed", "awaiting_approval"].includes(final.status) || !final.result) throw new Error("Esecuzione " + final.status + ". Consulta Attività; la richiesta non viene ripetuta automaticamente.");
  return final.result;
}

export type CapabilityOperation = {
  id:string; run_id:string|null; root_run_id:string|null; approval_id:string|null;
  capability_id:string; contract_version:number; effect:string; retry:string;
  status:string; payload:unknown; result:unknown; error_type:string|null;
  review_outcome:string|null; review_note:string|null; reviewed_by:string|null;
};
