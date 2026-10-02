import type { CalendarEvent } from "../types/contracts";
export const CALENDAR_ZONE = "Europe/Rome";
const parts = (value: Date) =>
  Object.fromEntries(
    new Intl.DateTimeFormat("sv-SE", {
      timeZone: CALENDAR_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(value)
      .map((p) => [p.type, p.value]),
  );
export function romeLocal(value: string | Date) {
  const p = parts(new Date(value));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export const romeToday = () => romeLocal(new Date()).slice(0, 10);
export function shiftDay(day: string, amount: number) {
  const d = new Date(day + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + amount);
  return d.toISOString().slice(0, 10);
}
export function shiftMonth(day: string, amount: number) {
  const d = new Date(day.slice(0, 7) + "-01T12:00:00Z");
  d.setUTCMonth(d.getUTCMonth() + amount);
  return d.toISOString().slice(0, 10);
}
/** Interpret inputs as Italian wall time, independent of the device timezone.
 * Reject nonexistent DST times; the repeated autumn hour uses the first occurrence.
 */
export function romeISO(local: string) {
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(local))
    throw new Error("Inserisci data e ora valide.");
  const wall = Date.parse(local + ":00Z");
  for (const offset of [120, 60]) {
    const candidate = new Date(wall - offset * 60000);
    if (Number.isFinite(candidate.getTime()) && romeLocal(candidate) === local)
      return candidate.toISOString();
  }
  throw new Error(
    "Questo orario non esiste in Italia durante il cambio all'ora legale. Scegli un altro orario.",
  );
}
export const dayStart = (day: string) => romeISO(day + "T00:00");
export const clock = (iso: string) => romeLocal(iso).slice(11);
export const dayLabel = (day: string) =>
  new Intl.DateTimeFormat("it-IT", {
    timeZone: CALENDAR_ZONE,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(day + "T12:00:00Z"));
export function eventsOnDay(events: CalendarEvent[], day: string) {
  const start = Date.parse(dayStart(day)),
    end = Date.parse(dayStart(shiftDay(day, 1)));
  return events.filter(
    (e) => Date.parse(e.start) < end && Date.parse(e.end) > start,
  );
}
export function layoutDay(events: CalendarEvent[], day: string) {
  const minutes = (iso: string) => {
    const time = clock(iso).split(":").map(Number);
    return time[0] * 60 + time[1];
  };
  const items = eventsOnDay(events, day)
    .filter((e) => !e.all_day)
    .map((event) => {
      const start =
        romeLocal(event.start).slice(0, 10) < day ? 0 : minutes(event.start);
      const end =
        romeLocal(event.end).slice(0, 10) > day ? 1440 : minutes(event.end);
      return {
        event,
        start,
        end: Math.min(1440, Math.max(start + 24, end)),
        lane: 0,
        lanes: 1,
      };
    })
    .sort((a, b) => a.start - b.start || b.end - a.end);
  let group: typeof items = [],
    groupEnd = -1;
  const assign = () => {
    const laneEnds: number[] = [];
    for (const item of group) {
      let lane = laneEnds.findIndex((end) => end <= item.start);
      if (lane === -1) lane = laneEnds.length;
      laneEnds[lane] = item.end;
      item.lane = lane;
    }
    for (const item of group) item.lanes = laneEnds.length;
  };
  for (const item of items) {
    if (item.start >= groupEnd) {
      assign();
      group = [];
      groupEnd = -1;
    }
    group.push(item);
    groupEnd = Math.max(groupEnd, item.end);
  }
  assign();
  return items;
}
