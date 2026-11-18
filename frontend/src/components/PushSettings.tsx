import { useEffect, useState } from "react";
import {
  currentPushState,
  disablePushNotifications,
  enablePushNotifications,
  sendTestPush,
  type PushState,
} from "../services/pushNotifications";

/** Push on this device: calendar reminders and Cora's alerts. Lives in Impostazioni › Notifiche. */
export default function PushSettings({ deviceLabel = "Dispositivo" }: { deviceLabel?: string }) {
  const [state, setState] = useState<PushState>({
    supported: false,
    permission: typeof Notification === "undefined" ? "unsupported" : Notification.permission,
    subscribed: false,
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let live = true;
    void currentPushState().then(next => { if (live) setState(next); }).catch(() => undefined);
    return () => { live = false; };
  }, []);

  async function act(action: () => Promise<PushState | void>, success: string) {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      const next = await action();
      if (next) setState(next);
      setMessage(success);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Operazione notifiche non riuscita.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="push-settings">
    <p>
      {!state.supported
        ? "Le notifiche push richiedono l'app installata (PWA) e aperta tramite HTTPS."
        : state.subscribed
          ? "Questo dispositivo è registrato: riceve i promemoria del calendario e gli avvisi di Cora anche quando Cora non è aperta. Dalle 23 alle 7 gli avvisi arrivano in un unico riepilogo del mattino."
          : state.permission === "denied"
            ? "Notifiche bloccate nelle impostazioni del dispositivo o del browser."
            : "Registra questo dispositivo per ricevere i promemoria del calendario e gli avvisi di Cora."}
    </p>
    {message && <p role="status">{message}</p>}
    <div className="push-settings-actions">
      {!state.subscribed ? (
        <button className="solid-button" disabled={busy || !state.supported || state.permission === "denied"}
          onClick={() => void act(() => enablePushNotifications(deviceLabel), "Notifiche attivate su questo dispositivo.")}>
          {busy ? "Attivazione…" : "Attiva notifiche su questo dispositivo"}
        </button>
      ) : (
        <>
          <button className="solid-button" disabled={busy} onClick={() => void act(async () => { await sendTestPush(); }, "Notifica di prova inviata.")}>
            Invia notifica di prova
          </button>
          <button className="text-button" disabled={busy} onClick={() => void act(() => disablePushNotifications(), "Notifiche disattivate su questo dispositivo.")}>
            Disattiva su questo dispositivo
          </button>
        </>
      )}
    </div>
  </div>;
}
