import { apiBaseUrl } from "./api";
import type {
  CalendarEvent,
  CalendarInput,
  CalendarProposal,
  CalendarHistory,
} from "../types/contracts";

export async function calendarRequest<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(apiBaseUrl + "/api/v1/calendar" + path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : response.status === 422
            ? "Controlla titolo, date e orari dell'evento."
            : "Calendario non disponibile (HTTP " + response.status + ").",
      );
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new Error(
        "Risposta calendario non valida: il backend non restituisce JSON.",
      );
    const data: unknown = await response.json();
    const record = (value: unknown): value is Record<string, unknown> =>
      Boolean(value && typeof value === "object" && !Array.isArray(value));
    const date = (value: unknown) =>
      typeof value === "string" && Number.isFinite(Date.parse(value));
    const event = (value: unknown) =>
      record(value) &&
      typeof value.id === "string" &&
      typeof value.title === "string" &&
      typeof value.notes === "string" &&
      date(value.start) &&
      date(value.end) &&
      typeof value.all_day === "boolean" &&
      Number.isInteger(value.version) &&
      Number(value.version) >= 1 &&
      typeof value.created_by === "string" &&
      typeof value.updated_by === "string";
    let valid = false;
    if (path.endsWith("/resolve"))
      valid = record(data) && (data.event === null || event(data.event));
    else if (path === "/proposals")
      valid =
        Array.isArray(data) &&
        data.every(
          (p) =>
            record(p) &&
            typeof p.id === "string" &&
            typeof p.actor === "string" &&
            ["create", "update", "delete"].includes(String(p.action)) &&
            record(p.payload) &&
            record(p.previous) &&
            typeof p.reason === "string" &&
            date(p.created_at),
        );
    else if (path.endsWith("/history"))
      valid =
        Array.isArray(data) &&
        data.every(
          (h) =>
            record(h) &&
            typeof h.id === "string" &&
            typeof h.actor === "string" &&
            ["create", "update", "delete", "restore"].includes(
              String(h.action),
            ) &&
            record(h.snapshot) &&
            date(h.changed_at),
        );
    else if (path.startsWith("/events?"))
      valid = Array.isArray(data) && data.every(event);
    else valid = event(data);
    if (!valid)
      throw new Error("Dati calendario non validi ricevuti dal backend.");
    return data as T;
  } catch (e) {
    if (controller.signal.aborted)
      throw new Error(
        "Tempo di attesa scaduto: esito non confermato. Aggiorna prima di riprovare.",
      );
    throw e instanceof Error ? e : new Error("Calendario non raggiungibile.");
  } finally {
    clearTimeout(timeout);
  }
}
export const calendarApi = {
  get: (id: string, token: string) =>
    calendarRequest<CalendarEvent>(`/events/${id}`, token),
  list: (start: string, end: string, token: string, deleted = false) =>
    calendarRequest<CalendarEvent[]>(
      "/events?" +
        new URLSearchParams({ start, end, deleted: String(deleted) }),
      token,
    ),
  save: (data: CalendarInput, token: string, event?: CalendarEvent) =>
    calendarRequest<CalendarEvent>(
      "/events" + (event ? "/" + event.id : ""),
      token,
      {
        method: event ? "PATCH" : "POST",
        body: JSON.stringify({
          ...data,
          ...(event ? { version: event.version } : {}),
        }),
      },
    ),
  remove: (event: CalendarEvent, token: string) =>
    calendarRequest<CalendarEvent>(
      `/events/${event.id}?version=${event.version}`,
      token,
      { method: "DELETE" },
    ),
  restore: (event: CalendarEvent, token: string) =>
    calendarRequest<CalendarEvent>(
      `/events/${event.id}/restore?version=${event.version}`,
      token,
      { method: "POST" },
    ),
  history: (id: string, token: string) =>
    calendarRequest<CalendarHistory[]>(`/events/${id}/history`, token),
  proposals: (token: string) =>
    calendarRequest<CalendarProposal[]>("/proposals", token),
  resolve: (id: string, approve: boolean, token: string) =>
    calendarRequest<{ event: CalendarEvent | null }>(
      `/proposals/${id}/resolve`,
      token,
      { method: "POST", body: JSON.stringify({ approve }) },
    ),
};
