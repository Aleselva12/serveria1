import { authenticatedFetch } from "./transport";
import { apiBaseUrl } from "./api";

export type MonitorEvent = { at: string; type: "added" | "changed" | "removed_or_unwatched"; path: string };
export type MonitorStatus = { folders: string[]; last_scan: string | null; indexed_files: number; events: MonitorEvent[] };
const endpoint = apiBaseUrl + "/api/v1/library/files/monitor";

async function request(route = "", options: RequestInit = {}): Promise<MonitorStatus> {
  const response = await authenticatedFetch(endpoint + route, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const json = await response.json().catch(() => ({}));
    throw new Error(typeof json.detail === "string" ? json.detail : "Monitor Libreria non disponibile.");
  }
  return response.json() as Promise<MonitorStatus>;
}

export const libraryMonitorApi = {
  status: () => request(),
  setFolder: (folder: string, enabled: boolean) => request("/folder", { method: "PUT", body: JSON.stringify({ folder, enabled }) }),
  scan: () => request("/scan", { method: "POST" }),
};
