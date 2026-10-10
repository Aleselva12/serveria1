import { apiBaseUrl } from "./api";
import { authenticatedFetch } from "./transport";

export type ChatTool = { name:string; description:string; group:string; permissions:{action:string;policy:"auto"|"confirm"|"blocked"}[] };
export async function chatTools():Promise<ChatTool[]> {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1/chat/tools", {signal:AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Tools chat non disponibili.");
  if (!data || !Array.isArray(data.tools) || !data.tools.every((t:ChatTool)=>t && typeof t.name === "string" && typeof t.description === "string" && typeof t.group === "string" && Array.isArray(t.permissions) && t.permissions.every(p=>p && typeof p.action === "string" && ["auto","confirm","blocked"].includes(p.policy))))
    throw new Error("Elenco tools chat non valido.");
  return data.tools;
}
