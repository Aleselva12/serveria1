import { apiBaseUrl } from "./api";
import { authenticatedFetch } from "./transport";

export type InboxItem = {
  id: string;
  createdAt: string;
  source: string;
  kind: string;
  severity: "info" | "warning" | "error" | "success";
  title: string;
  body: string;
  url: string | null;
  ref: string | null;
  commit: string;
  seenAt: string | null;
};
export type Inbox = { items: InboxItem[]; unseen: number };

const BASE = "/api/v1/notifications/inbox";
// Lets the Home window, the menu badge and the page stay in step after a change.
export const INBOX_CHANGED = "cora:inbox-changed";

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(apiBaseUrl + BASE + path, { ...init, headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(response.status === 503 ? "Notifiche non disponibili." : "Operazione non riuscita (HTTP " + response.status + ").");
  return response.json() as Promise<T>;
}

export function isInbox(value: unknown): value is Inbox {
  const data = value as Inbox;
  return !!data && Array.isArray(data.items) && typeof data.unseen === "number" &&
    data.items.every(item => typeof item.id === "string" && typeof item.title === "string" && typeof item.createdAt === "string");
}

export async function loadInbox(includeSeen = false): Promise<Inbox> {
  const data = await call<unknown>(includeSeen ? "?include_seen=true&limit=200" : "?limit=50");
  if (!isInbox(data)) throw new Error("Risposta notifiche non valida.");
  return data;
}

export async function markSeen(id: string) {
  await call(`/${encodeURIComponent(id)}/seen`, { method: "POST" });
  window.dispatchEvent(new Event(INBOX_CHANGED));
}

export async function markAllSeen() {
  await call("/seen", { method: "POST" });
  window.dispatchEvent(new Event(INBOX_CHANGED));
}
