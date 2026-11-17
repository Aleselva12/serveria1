import { useCallback, useEffect, useState } from "react";
import { Bell, Check, X } from "lucide-react";
import { INBOX_CHANGED, loadInbox, markAllSeen, markSeen, type Inbox, type InboxItem } from "../services/inboxApi";
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

/** Small window on the Home: unseen notifications, until marked as seen. */
export function HomeNotifications({ onOpenAll }: { onOpenAll: () => void }) {
  const { inbox } = useInbox(false);
  const [closed, setClosed] = useState(false);
  if (closed || !inbox || inbox.unseen === 0) return null;
  return <aside className="home-notifications section-card" aria-label="Notifiche non viste">
    <div className="home-notifications-heading">
      <Bell size={16} /><strong>Notifiche</strong><span className="pill error">{inbox.unseen}</span>
      <button className="text-button" aria-label="Chiudi per ora" onClick={() => setClosed(true)}><X size={16} /></button>
    </div>
    <ul>{inbox.items.slice(0, 3).map(item => <Item key={item.id} item={item} compact />)}</ul>
    <div className="home-notifications-actions">
      <button className="text-button" onClick={onOpenAll}>Tutte le notifiche{inbox.unseen > 3 ? " (" + inbox.unseen + ")" : ""}</button>
      <button className="text-button" onClick={() => void markAllSeen()}>Segna tutte viste</button>
    </div>
  </aside>;
}

/** Menu page with every notification; seen ones stay listed, greyed out. */
export default function NotificationsPage() {
  const [showSeen, setShowSeen] = useState(false);
  const { inbox, error, refresh } = useInbox(showSeen);
  return <section className="content-page narrow notifications-page">
    <div className="section-title">
      <h1>Notifiche</h1>
      {inbox && <span className={"pill " + (inbox.unseen ? "error" : "success")}>{inbox.unseen ? inbox.unseen + " da vedere" : "Tutto visto"}</span>}
    </div>
    <p>Avvisi dei controlli automatici: un servizio che smette di funzionare e quando torna a posto. Arrivano anche su telefono o PC se le notifiche push sono attive nelle Impostazioni.</p>
    <div className="notifications-toolbar">
      <label><input type="checkbox" checked={showSeen} onChange={e => setShowSeen(e.target.checked)} /> Mostra anche quelle già viste</label>
      <button className="text-button" onClick={() => void refresh()}>Aggiorna</button>
      {!!inbox?.unseen && <button className="text-button" onClick={() => void markAllSeen()}>Segna tutte viste</button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {inbox && inbox.items.length === 0 && <p className="muted">Nessuna notifica{showSeen ? "." : " da vedere."}</p>}
    {inbox && <ul className="inbox-list">{inbox.items.map(item => <Item key={item.id} item={item} />)}</ul>}
  </section>;
}
