import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { mailRequest } from "../services/mailApi";
import { calendarApi, type CalendarProviderStatus } from "../services/calendarApi";

type MailAccounts = { accounts: { id: string; email: string; connected: boolean }[]; webAuth: { available: boolean } };

/** Read-only overview of the external accounts Cora uses. Connecting stays where the account is used. */
export default function AccountsSettings({ onOpenMail, onOpenCalendar }: { onOpenMail: () => void; onOpenCalendar: () => void }) {
  const [mail, setMail] = useState<MailAccounts | null>(null);
  const [mailError, setMailError] = useState("");
  const [calendar, setCalendar] = useState<CalendarProviderStatus | null>(null);
  const [calendarError, setCalendarError] = useState("");

  useEffect(() => {
    let live = true;
    void mailRequest<MailAccounts>("/accounts")
      .then(r => { if (live) setMail(r); })
      .catch(e => { if (live) setMailError(e instanceof Error ? e.message : "Stato Gmail non disponibile."); });
    void calendarApi.provider("")
      .then(r => { if (live) setCalendar(r); })
      .catch(e => { if (live) setCalendarError(e instanceof Error ? e.message : "Stato Google Calendar non disponibile."); });
    return () => { live = false; };
  }, []);

  const calendarState = !calendar ? "" : calendar.provider !== "google" ? "Calendario locale"
    : calendar.reauthorizationRequired ? "Autorizzazione da rinnovare"
      : calendar.connected ? (calendar.reachable === false ? "Collegato, non raggiungibile" : "Collegato") : "Da collegare";
  const calendarOk = calendar?.provider === "google" && calendar.connected && !calendar.reauthorizationRequired && calendar.reachable !== false;

  return <div className="accounts-settings">
    <div className="settings-row">
      <div><strong>Gmail</strong>
        {mailError ? <p role="alert">{mailError}</p> : !mail ? <p>Caricamento…</p>
          : mail.accounts.length === 0 ? <p>Nessun account configurato.</p>
            : mail.accounts.map(a => <p key={a.id}>{a.email} · {a.connected ? "Autorizzazione salvata" : "Da collegare"}</p>)}
        {mail && !mail.webAuth.available && <p>OAuth Google non configurato sul server.</p>}
      </div>
      <span className={"pill " + (mail && mail.accounts.length > 0 && mail.accounts.every(a => a.connected) ? "success" : "pending")}>
        {mail ? mail.accounts.filter(a => a.connected).length + "/" + mail.accounts.length : "—"}
      </span>
    </div>
    <div className="settings-row">
      <div><strong>Google Calendar</strong>
        {calendarError ? <p role="alert">{calendarError}</p> : !calendar ? <p>Caricamento…</p> : <p>{calendarState}</p>}
      </div>
      <span className={"pill " + (calendarOk ? "success" : "pending")}>{calendar ? (calendarOk ? "OK" : "Da controllare") : "—"}</span>
    </div>
    <p className="muted">Collegare o ricollegare un account si fa dove lo usi: la pagina apre la finestra di Google e torna a Cora.</p>
    <div className="settings-link-grid">
      <button onClick={onOpenMail}><strong>Mail</strong><span>Collega o ricollega gli account Gmail</span><ArrowRight size={16} /></button>
      <button onClick={onOpenCalendar}><strong>Calendario</strong><span>Collega o ricollega Google Calendar</span><ArrowRight size={16} /></button>
    </div>
  </div>;
}
