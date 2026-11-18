import { useCallback, useEffect, useState } from "react";
import { Bell, Check, X } from "lucide-react";
import { INBOX_CHANGED, loadInbox, markAllSeen, markSeen, type Inbox, type InboxItem } from "../services/inboxApi";
import DecisionsPanel, { useDecisions } from "./Decisions";
import "./notifications.css";

const REFRESH_MS = 60000;
const tone: Record<InboxItem["severity"], string> = { error: "error", warning: "pending", success: "success", info: "unknown" };
const label: Record<InboxItem["severity"], string> = { error: "Errore", warning: "Avviso", success: "Ripristinato", info: "Info" };

function when(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

/** Inbox kept fresh: periodic reload plus any change made elsewhere in the page. */
export function useInbox(includeSeen = false) {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try { setInbox(await loadInbox(includeSeen)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Notifiche non disponibili."); }
  }, [includeSeen]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    const changed = () => void refresh();
    window.addEventListener(INBOX_CHANGED, changed);
    return () => { clearInterval(timer); window.removeEventListener(INBOX_CHANGED, changed); };
  }, [refresh]);
  return { inbox, error, refresh };
}

function Item({ item, compact = false }: { item: InboxItem; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  return <li className={"inbox-item" + (item.seenAt ? " seen" : "")}>
    <div className="inbox-item-heading">
      <span className={"pill " + tone[item.severity]}>{label[item.severity]}</span>
      <strong>{item.title}</strong>
    </div>
    {item.body && <p>{item.body}</p>}
    <div className="inbox-item-footer">
      <small>{when(item.createdAt)}</small>
      {!item.seenAt && <button className="text-button" disabled={busy} aria-label={"Segna come vista: " + item.title}
        onClick={async () => { setBusy(true); try { await markSeen(item.id); } finally { setBusy(false); } }}>
        <Check size={14} /> {compact ? "Vista" : "Segna come vista"}
      </button>}
    </div>
  </li>;
}

/** Small window on the Home: unseen notifications and pending decisions, until handled. */
export function HomeNotifications({ onOpenAll, onOpenDecisions }: { onOpenAll: () => void; onOpenDecisions?: () => void }) {
  const { inbox } = useInbox(false);
  const { decisions } = useDecisions();
  const [closed, setClosed] = useState(false);
  const unseen = inbox?.unseen ?? 0;
  const pending = decisions?.pending ?? 0;
  if (closed || (unseen === 0 && pending === 0)) return null;
  return <aside className="home-notifications section-card" aria-label="Notifiche non viste">
    <div className="home-notifications-heading">
      <Bell size={16} /><strong>Notifiche</strong>{unseen > 0 && <span className="pill error">{unseen}</span>}
      <button className="text-button" aria-label="Chiudi per ora" onClick={() => setClosed(true)}><X size={16} /></button>
    </div>
    {pending > 0 && <button className="home-decisions-link text-button" onClick={onOpenDecisions ?? onOpenAll}>
      <span className="pill pending">{pending}</span> {pending === 1 ? "decisione in attesa" : "decisioni in attesa"}: approvazioni o verifiche
    </button>}
    {unseen > 0 && inbox && <ul>{inbox.items.slice(0, 3).map(item => <Item key={item.id} item={item} compact />)}</ul>}
    <div className="home-notifications-actions">
      <button className="text-button" onClick={onOpenAll}>Tutte le notifiche{unseen > 3 ? " (" + unseen + ")" : ""}</button>
      {unseen > 0 && <button className="text-button" onClick={() => void markAllSeen()}>Segna tutte viste</button>}
    </div>
  </aside>;
}

export type NotificationsTab = "alerts" | "decisions";

/** Menu page: alerts from the automatic checks and everything that waits for a decision. */
export default function NotificationsPage({ initialTab = "alerts", onOpenSettings, onOpenAudio }:
  { initialTab?: NotificationsTab; onOpenSettings?: () => void; onOpenAudio?: () => void }) {
  const [tab, setTab] = useState<NotificationsTab>(initialTab);
  const [showSeen, setShowSeen] = useState(false);
  const { inbox, error, refresh } = useInbox(showSeen);
  const { decisions } = useDecisions();
  const pending = decisions?.pending ?? 0;
  return <section className="content-page narrow notifications-page">
    <div className="section-title">
      <h1>Notifiche</h1>
      {inbox && <span className={"pill " + (inbox.unseen ? "error" : "success")}>{inbox.unseen ? inbox.unseen + " da vedere" : "Tutto visto"}</span>}
    </div>
    <div className="notifications-tabs" role="tablist" aria-label="Sezioni Notifiche">
      <button role="tab" aria-selected={tab === "alerts"} onClick={() => setTab("alerts")}>Avvisi{inbox?.unseen ? " (" + inbox.unseen + ")" : ""}</button>
      <button role="tab" aria-selected={tab === "decisions"} onClick={() => setTab("decisions")}>Da decidere{pending ? " (" + pending + ")" : ""}</button>
    </div>
    {tab === "alerts" ? <>
      <p>Avvisi dei controlli automatici: un servizio che smette di funzionare e quando torna a posto. Arrivano anche su telefono o PC se le notifiche push sono attive{onOpenSettings ? <> nelle <button className="text-button inline" onClick={onOpenSettings}>Impostazioni › Notifiche</button></> : " nelle Impostazioni"}.</p>
      <div className="notifications-toolbar">
        <label><input type="checkbox" checked={showSeen} onChange={e => setShowSeen(e.target.checked)} /> Mostra anche quelle già viste</label>
        <button className="text-button" onClick={() => void refresh()}>Aggiorna</button>
        {!!inbox?.unseen && <button className="text-button" onClick={() => void markAllSeen()}>Segna tutte viste</button>}
      </div>
      {error && <p role="alert">{error}</p>}
      {inbox && inbox.items.length === 0 && <p className="muted">Nessuna notifica{showSeen ? "." : " da vedere."}</p>}
      {inbox && <ul className="inbox-list">{inbox.items.map(item => <Item key={item.id} item={item} />)}</ul>}
    </> : <>
      <p>Tutto ciò che aspetta un tuo sì o no: azioni proposte dagli agenti, appuntamenti, note Word e operazioni dall'esito incerto.</p>
      <DecisionsPanel onOpenAudio={onOpenAudio} />
    </>}
  </section>;
}
