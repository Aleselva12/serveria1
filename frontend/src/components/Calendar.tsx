import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, RefreshCw } from "lucide-react";
import type {
  CalendarEvent,
  CalendarHistory,
  CalendarProposal,
} from "../types/contracts";
import { calendarApi } from "../services/calendarApi";
import {
  clock,
  dayLabel,
  dayStart,
  eventsOnDay,
  layoutDay,
  romeISO,
  romeLocal,
  romeToday,
  shiftDay,
  shiftMonth,
} from "../services/calendarTime";
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Operazione non riuscita.";
const actions: Record<string, string> = {
  create: "Creazione",
  update: "Modifica",
  delete: "Eliminazione",
  restore: "Ripristino",
};
const initialForm = (day: string, hour = 9) => ({
  title: "",
  start: `${day}T${String(hour).padStart(2, "0")}:00`,
  end: `${day}T${String(hour).padStart(2, "0")}:30`,
  all_day: false,
  notes: "",
});
export default function Calendar() {
  const [day, setDay] = useState(romeToday),
    [view, setView] = useState<"month" | "day">("month");
  const [events, setEvents] = useState<CalendarEvent[]>([]),
    [trash, setTrash] = useState<CalendarEvent[]>([]);
  const [proposals, setProposals] = useState<CalendarProposal[]>([]),
    [token] = useState("");
  const [editing, setEditing] = useState<CalendarEvent>(),
    [form, setForm] = useState(() => initialForm(romeToday()));
  const [history, setHistory] = useState<CalendarHistory[]>([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [connected, setConnected] = useState(false);
  const lock = useRef(false),
    generation = useRef(0),
    historyGeneration = useRef(0);
  const month = day.slice(0, 7) + "-01",
    rangeStart = view === "month" ? month : day;
  const rangeEnd = view === "month" ? shiftMonth(month, 1) : shiftDay(day, 1);
  const refresh = useCallback(
    async (quiet = false) => {
      const current = ++generation.current;
      if (!quiet) setLoading(true);
      try {
        const [saved, deleted, pending] = await Promise.all([
          calendarApi.list(dayStart(rangeStart), dayStart(rangeEnd), token),
          calendarApi.list(
            dayStart(rangeStart),
            dayStart(rangeEnd),
            token,
            true,
          ),
          calendarApi.proposals(token),
        ]);
        if (current !== generation.current) return;
        setEvents(saved);
        setTrash(deleted);
        setProposals(pending);
        setConnected(true);
      } catch (e) {
        if (current !== generation.current) return;
        setError(errorText(e));
        setConnected(false);
        setEvents([]);
        setTrash([]);
        setProposals([]);
      } finally {
        if (current === generation.current) setLoading(false);
      }
    },
    [rangeStart, rangeEnd, token],
  );
  useEffect(() => {
    setError("");
    setEvents([]);
    setTrash([]);
    void refresh();
    const timer = setInterval(() => {
      if (!lock.current) void refresh(true);
    }, 30000);
    const onFocus = () => {
      if (!lock.current) void refresh(true);
    };
    window.addEventListener("focus", onFocus);
    return () => {
      ++generation.current;
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);
  function newEvent(date = day, hour = 9) {
    ++historyGeneration.current;
    setEditing(undefined);
    setHistory([]);
    setForm(initialForm(date, hour));
  }
  async function select(event: CalendarEvent) {
    const current = ++historyGeneration.current;
    setEditing(event);
    setHistory([]);
    setForm({
      title: event.title,
      start: romeLocal(event.start),
      end: event.all_day
        ? shiftDay(romeLocal(event.end).slice(0, 10), -1) + "T00:00"
        : romeLocal(event.end),
      all_day: event.all_day,
      notes: event.notes,
    });
    try {
      const result = await calendarApi.history(event.id, token);
      if (current === historyGeneration.current) setHistory(result);
    } catch (e) {
      if (current === historyGeneration.current) setError(errorText(e));
    }
  }
  async function mutate(
    operation: () => Promise<unknown>,
    message: string,
    reset = false,
  ) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await operation();
      setNotice(message);
      if (reset) newEvent();
      await refresh(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function save() {
    let start: string, end: string;
    try {
      start = romeISO(
        form.all_day ? form.start.slice(0, 10) + "T00:00" : form.start,
      );
      end = romeISO(
        form.all_day ? shiftDay(form.end.slice(0, 10), 1) + "T00:00" : form.end,
      );
      // Preserve the second occurrence of the repeated autumn hour when unchanged.
      if (editing && !form.all_day && !editing.all_day) {
        if (form.start === romeLocal(editing.start)) start = editing.start;
        if (form.end === romeLocal(editing.end)) end = editing.end;
        if (Date.parse(end) <= Date.parse(start)) {
          throw new Error("La fine deve essere successiva all'inizio.");
        }
      }
      if (!form.title.trim()) throw new Error("Inserisci un titolo.");
      if (Date.parse(end) <= Date.parse(start))
        throw new Error("La fine deve essere successiva all'inizio.");
    } catch (e) {
      setError(errorText(e));
      return;
    }
    const overlaps = events.some(
      (e) =>
        e.id !== editing?.id &&
        Date.parse(e.start) < Date.parse(end) &&
        Date.parse(e.end) > Date.parse(start),
    );
    await mutate(
      async () => {
        const saved = await calendarApi.save(
          {
            title: form.title.trim(),
            start,
            end,
            all_day: form.all_day,
            notes: form.notes,
          },
          token,
          editing,
        );
        await select(saved);
      },
      overlaps
        ? "Evento salvato. Si sovrappone ad altri impegni."
        : "Evento salvato nel calendario.",
    );
  }
  const daysInMonth = Number(shiftDay(shiftMonth(month, 1), -1).slice(8));
  const offset = (new Date(month + "T12:00:00Z").getUTCDay() + 6) % 7;
  const title =
    view === "day"
      ? dayLabel(day)
      : new Intl.DateTimeFormat("it-IT", {
          timeZone: "Europe/Rome",
          month: "long",
          year: "numeric",
        }).format(new Date(month + "T12:00:00Z"));
  const daily = eventsOnDay(events, day);
  async function openProposalEvent(p: CalendarProposal) {
    if (!p.event_id) return;
    try {
      const event = await calendarApi.get(p.event_id, token);
      setDay(romeLocal(event.start).slice(0, 10));
      setView("day");
      await select(event);
    } catch (e) {
      setError(errorText(e));
    }
  }
  return (
    <section className="content-page calendar-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ORGANIZZA IL TEMPO</div>
          <h1>Calendario</h1>
          <p>Impegni personali · orario italiano (Europe/Rome)</p>
        </div>
        <span className={"pill " + (connected ? "" : "pending")}>
          {loading
            ? "Caricamento…"
            : connected
              ? "Collegato"
              : "Non disponibile"}
        </span>
      </div>

      {error && (
        <p role="alert" className="calendar-error">
          {error}{" "}
          <button
            onClick={() => {
              setError("");
              void refresh();
            }}
          >
            Ricarica
          </button>
        </p>
      )}
      {notice && (
        <p role="status" className="calendar-notice">
          {notice}
        </p>
      )}
      <div className="calendar-layout">
        <div className="section-card calendar-card">
          <div className="calendar-controls">
            <div
              className="calendar-switch"
              role="group"
              aria-label="Vista calendario"
            >
              <button
                className={view === "month" ? "active" : ""}
                disabled={busy} onClick={() => setView("month")}
              >
                Mese
              </button>
              <button
                className={view === "day" ? "active" : ""}
                disabled={busy} onClick={() => setView("day")}
              >
                Giorno
              </button>
            </div>
            <button disabled={busy} onClick={() => setDay(romeToday())}>Oggi</button>
            <button
              aria-label="Aggiorna calendario"
              disabled={busy || loading}
              onClick={() => {
                setError("");
                void refresh();
              }}
            >
              <RefreshCw size={16} />
            </button>
            <button
              className="solid-button"
              disabled={busy}
              onClick={() => newEvent()}
            >
              <Plus size={16} />
              Nuovo impegno
            </button>
          </div>
          <div className="calendar-toolbar">
            <button
              disabled={busy} aria-label="Periodo precedente"
              onClick={() =>
                setDay(
                  view === "month" ? shiftMonth(day, -1) : shiftDay(day, -1),
                )
              }
            >
              <ChevronLeft size={18} />
            </button>
            <h2>{title}</h2>
            <button
              disabled={busy} aria-label="Periodo successivo"
              onClick={() =>
                setDay(view === "month" ? shiftMonth(day, 1) : shiftDay(day, 1))
              }
            >
              <ChevronRight size={18} />
            </button>
          </div>
          {view === "month" ? (
            <div className="calendar-grid">
              {["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"].map((d) => (
                <strong key={d}>{d}</strong>
              ))}
              {Array.from({ length: offset }, (_, i) => (
                <span className="empty" key={"empty" + i} />
              ))}
              {Array.from({ length: daysInMonth }, (_, i) => {
                const date = month.slice(0, 8) + String(i + 1).padStart(2, "0");
                return (
                  <div
                    className={
                      "calendar-day " + (date === romeToday() ? "is-today" : "")
                    }
                    key={date}
                  >
                    <button
                      disabled={busy} className="calendar-date"
                      aria-label={"Apri " + dayLabel(date)}
                      onClick={() => {
                        setDay(date);
                        setView("day");
                      }}
                    >
                      {i + 1}
                    </button>
                    <button
                      className="calendar-add"
                      disabled={busy}
                      aria-label={"Nuovo impegno " + date}
                      onClick={() => newEvent(date)}
                    >
                      <Plus size={12} />
                    </button>
                    {eventsOnDay(events, date).map((event) => (
                      <button
                        className="calendar-event"
                        key={event.id}
                        disabled={busy}
                        onClick={() => void select(event)}
                        title={event.title}
                      >
                        {event.all_day ? "Tutto il giorno" : clock(event.start)}{" "}
                        · {event.title}
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          ) : (
            <>
              <div className="calendar-all-day">
                <strong>Tutto il giorno</strong>
                {daily
                  .filter((e) => e.all_day)
                  .map((e) => (
                    <button
                      className="calendar-event"
                      key={e.id}
                      disabled={busy}
                      onClick={() => void select(e)}
                    >
                      {e.title}
                    </button>
                  ))}
                {!daily.some((e) => e.all_day) && <span>Nessun impegno</span>}
              </div>
              <div className="calendar-timeline-scroll">
                <div className="calendar-timeline">
                  {Array.from({ length: 24 }, (_, hour) => (
                    <div
                      className="calendar-hour"
                      key={hour}
                      style={{ top: hour * 60 }}
                    >
                      <span>{String(hour).padStart(2, "0")}:00</span>
                      <button
                        aria-label={"Aggiungi impegno alle " + hour}
                        disabled={busy}
                        onClick={() => newEvent(day, hour)}
                      />
                    </div>
                  ))}
                  <div className="calendar-timed-events">
                    {layoutDay(events, day).map((item) => (
                      <button
                        key={item.event.id}
                        className="calendar-timed-event"
                        disabled={busy}
                        style={{
                          top: item.start,
                          height: Math.max(24, item.end - item.start),
                          left: `${(item.lane / item.lanes) * 100}%`,
                          width: `calc(${100 / item.lanes}% - 4px)`,
                        }}
                        onClick={() => void select(item.event)}
                        title={
                          item.event.title +
                          " · " +
                          clock(item.event.start) +
                          "–" +
                          clock(item.event.end)
                        }
                      >
                        <strong>{item.event.title}</strong>
                        <span>
                          {clock(item.event.start)}–{clock(item.event.end)}
                        </span>
                        {item.lanes > 1 && <small>Sovrapposto</small>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <p className="panel-note">
                Clicca su un orario per inserire un impegno.
              </p>
            </>
          )}
          {!loading && connected && !events.length && (
            <p className="panel-note">Nessun impegno in questo periodo.</p>
          )}
        </div>
        <aside className="side-panel calendar-side">
          <div className="eyebrow">
            {editing ? "MODIFICA IMPEGNO" : "NUOVO IMPEGNO"}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <label>
              Titolo
              <input
                required
                maxLength={200}
                disabled={busy}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="calendar-checkbox">
              <input
                type="checkbox"
                disabled={busy}
                checked={form.all_day}
                onChange={(e) =>
                  setForm({ ...form, all_day: e.target.checked })
                }
              />
              Tutto il giorno
            </label>
            <label>
              Inizio
              <input
                required
                type={form.all_day ? "date" : "datetime-local"}
                disabled={busy}
                value={form.all_day ? form.start.slice(0, 10) : form.start}
                onChange={(e) =>
                  setForm({
                    ...form,
                    start: form.all_day
                      ? e.target.value + "T00:00"
                      : e.target.value,
                  })
                }
              />
            </label>
            <label>
              {form.all_day ? "Ultimo giorno incluso" : "Fine"}
              <input
                required
                type={form.all_day ? "date" : "datetime-local"}
                disabled={busy}
                value={form.all_day ? form.end.slice(0, 10) : form.end}
                onChange={(e) =>
                  setForm({
                    ...form,
                    end: form.all_day
                      ? e.target.value + "T00:00"
                      : e.target.value,
                  })
                }
              />
            </label>
            <label>
              Note
              <textarea
                maxLength={10000}
                rows={4}
                disabled={busy}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </label>
            <button className="solid-button" disabled={busy || !connected}>
              {busy
                ? "Operazione…"
                : editing
                  ? "Salva modifiche"
                  : "Aggiungi impegno"}
            </button>
          </form>
          {editing && (
            <>
              <p className="panel-note">
                Creato da {editing.created_by} · versione {editing.version}
              </p>
              <div className="calendar-actions">
                <button disabled={busy} onClick={() => newEvent()}>
                  Chiudi modifica
                </button>
                <button
                  disabled={busy || !connected}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Eliminare questo impegno? Potrai recuperarlo dagli eliminati.",
                      )
                    )
                      void mutate(
                        () => calendarApi.remove(editing, token),
                        "Evento eliminato e recuperabile.",
                        true,
                      );
                  }}
                >
                  Elimina
                </button>
              </div>
              <details className="calendar-history">
                <summary>Storico modifiche ({history.length})</summary>
                {history.map((h) => (
                  <div key={h.id}>
                    <strong>
                      {actions[h.action]} · {h.actor}
                    </strong>
                    <small>{romeLocal(h.changed_at).replace("T", " ")}</small>
                    <span>{String(h.snapshot.title ?? "")}</span>
                  </div>
                ))}
              </details>
            </>
          )}
        </aside>
      </div>
      <div className="calendar-bottom">
        <section className="section-card">
          <h2>Proposte degli agenti</h2>
          <p>Le proposte diventano effettive solo dopo la tua approvazione.</p>
          {!proposals.length && (
            <p className="panel-note">Nessuna proposta in attesa.</p>
          )}
          {proposals.map((p) => (
            <article className="calendar-proposal" key={p.id}>
              <strong>
                {actions[p.action]} ·{" "}
                {p.payload.title ||
                  p.previous.title ||
                  events.find((e) => e.id === p.event_id)?.title ||
                  p.event_id}
              </strong>
              <small>Proposta da {p.actor}</small>
              {p.payload.start && (
                <p>
                  {romeLocal(p.payload.start).replace("T", " ")} →{" "}
                  {p.payload.end && romeLocal(p.payload.end).replace("T", " ")}
                  {p.payload.all_day && " · Tutto il giorno (fine esclusa)"}
                </p>
              )}
              {p.payload.notes && <p>{p.payload.notes}</p>}
              {p.reason && <p>{p.reason}</p>}
              {p.previous.start && (
                <details>
                  <summary>Evento prima della modifica</summary>
                  <p>
                    {p.previous.title} ·{" "}
                    {romeLocal(p.previous.start).replace("T", " ")} →{" "}
                    {p.previous.end &&
                      romeLocal(p.previous.end).replace("T", " ")}
                  </p>
                  <p>{p.previous.notes}</p>
                </details>
              )}
              {p.action !== "create" && (
                <p className="panel-note">
                  Versione di partenza: {p.expected_version}.{" "}
                  <button
                    disabled={busy}
                    onClick={() => void openProposalEvent(p)}
                  >
                    Apri evento
                  </button>
                </p>
              )}
              <div className="calendar-actions">
                <button
                  className="solid-button"
                  disabled={busy || !connected}
                  onClick={() =>
                    void mutate(
                      () => calendarApi.resolve(p.id, true, token),
                      "Proposta approvata: calendario aggiornato.",
                      true,
                    )
                  }
                >
                  Approva
                </button>
                <button
                  disabled={busy || !connected}
                  onClick={() =>
                    void mutate(
                      () => calendarApi.resolve(p.id, false, token),
                      "Proposta rifiutata.",
                    )
                  }
                >
                  Rifiuta
                </button>
              </div>
            </article>
          ))}
        </section>
        <section className="section-card">
          <h2>Eliminati nel periodo</h2>
          <p>Gli eventi eliminati conservano lo storico.</p>
          {!trash.length && (
            <p className="panel-note">Nessun evento eliminato.</p>
          )}
          {trash.map((e) => (
            <article className="calendar-proposal" key={e.id}>
              <strong>{e.title}</strong>
              <small>{romeLocal(e.start).replace("T", " ")}</small>
              <button
                disabled={busy || !connected}
                onClick={() =>
                  void mutate(
                    () => calendarApi.restore(e, token),
                    "Evento ripristinato.",
                  )
                }
              >
                Ripristina
              </button>
            </article>
          ))}
        </section>
      </div>
    </section>
  );
}
