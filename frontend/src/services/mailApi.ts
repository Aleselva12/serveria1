import { authenticatedFetch } from "./transport";
import { apiBaseUrl } from "./api";
export type Selection = "a" | "b" | "all";
export type Scope = "inbox" | "unread" | "yesterday";
export type Message = { account: string; id: string; email: string; subject: string; sender: string; to: string; cc: string; date: string; timestamp: number; snippet: string; body: string; unread: boolean };
export type Listing = { messages: Message[]; errors: Record<string, string>; next: Record<string, string> };
export async function mailRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1/mail" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(45000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Mail non disponibile");
  return data;
}
