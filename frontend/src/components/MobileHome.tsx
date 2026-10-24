import { useEffect, useState } from "react";
import {
  Activity,
  CalendarDays,
  FileAudio,
  Files,
  Images,
  MessageCircle,
  RefreshCw,
  Settings,
  Server,
} from "lucide-react";
import ProjectRoadmap from "./ProjectRoadmap";
import { serviceStatusLabels, serviceSummary } from "../services/homeStatus";
import type { BackendHealth } from "../types/contracts";
import { useHomeMonitoring } from "../services/useHomeMonitoring";
import {
  currentPushState,
  disablePushNotifications,
  enablePushNotifications,
  sendTestPush,
  type PushState,
} from "../services/pushNotifications";

type MobilePage = "photos" | "files" | "audio" | "calendar" | "chat" | "activity" | "settings";

const bytes = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) return "0 GiB";
  return (value / 1024 ** 3).toFixed(value >= 100 * 1024 ** 3 ? 0 : 1) + " GiB";
};

export default function MobileHome({
  health,
  checking,
  onRefresh,
  onNavigate,
}: {
  health: BackendHealth | null;
  checking: boolean;
  onRefresh: () => void;
  onNavigate: (page: MobilePage) => void;
}) {
  const { telemetry, services, telemetryError, servicesError, refresh } = useHomeMonitoring();
  const [pushState, setPushState] = useState<PushState>({
    supported: false,
    permission: typeof Notification === "undefined" ? "unsupported" : Notification.permission,
    subscribed: false,
  });
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMessage, setPushMessage] = useState("");
  const disks = telemetry?.disks ?? [];
  const disk = disks[0];
  const coreOk = Boolean(health);
  const displayedServices = [...services];
  if (!services.some(service => service.id === "fastapi")) displayedServices.unshift({
    id: "fastapi", label: "Cora / FastAPI", status: coreOk ? "ready" : "unknown", checkedAt: "",
  });
  if (!services.some(service => service.id === "ollama")) displayedServices.push({
    id: "ollama", label: "Ollama locale", status: health ? health.ollama_online ? "ready" : "offline" : "unknown", checkedAt: "",
  });

  useEffect(() => {
    let live = true;
    void currentPushState().then((state) => {
      if (live) setPushState(state);
    }).catch(() => undefined);
    return () => { live = false; };
  }, []);

  async function pushAction(action: () => Promise<PushState | void>, success: string) {
    if (pushBusy) return;
    setPushBusy(true);
    setPushMessage("");
    try {
      const state = await action();
      if (state) setPushState(state);
      setPushMessage(success);
    } catch (error) {
      setPushMessage(error instanceof Error ? error.message : "Operazione notifiche non riuscita.");
    } finally {
      setPushBusy(false);
    }
  }

  return (
    <section className="mobile-home">
      <div className="mobile-hero">
        <div>
          <span className="mobile-kicker">CORA MOBILE</span>
          <h1>{coreOk ? "Cora raggiungibile" : checking ? "Controllo server…" : "Server non raggiungibile"}</h1>
          <p>
            {coreOk
              ? serviceSummary(services, servicesError)
              : checking ? "Verifica della connessione in corso…" : "Verifica Tailscale, rete e servizi del server."}
          </p>
        </div>
        <button className="mobile-icon-button" onClick={() => { onRefresh(); refresh(); }} disabled={checking} aria-label="Aggiorna stato server">
          <RefreshCw size={19} className={checking ? "spin" : ""} />
        </button>
      </div>

      <div className="mobile-primary-grid">
        <button onClick={() => onNavigate("photos")}><Images /><strong>Foto</strong><span>Collegamento al servizio foto</span></button>
        <button onClick={() => onNavigate("files")}><Files /><strong>File</strong><span>Drive del server</span></button>
        <button onClick={() => onNavigate("audio")}><FileAudio /><strong>Audio</strong><span>Carica e trascrivi</span></button>
        <button onClick={() => onNavigate("calendar")}><CalendarDays /><strong>Agenda</strong><span>Impegni e appuntamenti</span></button>
      </div>

      <div className="mobile-status-card">
        <div className="mobile-section-title">
          <div><span className="mobile-kicker">STATO</span><h2>Misurazioni di Cora</h2></div>
          <Server size={20} />
        </div>
        <div className="mobile-metrics">
          <div><span>CPU</span><strong>{telemetry?.cpu.percent == null ? "—" : Math.round(telemetry.cpu.percent) + "%"}</strong></div>
          <div><span>RAM</span><strong>{telemetry?.ram.percent == null ? "—" : Math.round(telemetry.ram.percent) + "%"}</strong></div>
          <div><span>Disco</span><strong>{disk ? bytes(disk.totalBytes - disk.usedBytes) : "—"}</strong><small>{disk ? "liberi" : ""}</small></div>
        </div>
        {(telemetryError || servicesError) && <p className="mobile-inline-error">{telemetryError || servicesError}</p>}
        <div className="mobile-service-list">
          {displayedServices.map((service) => (
            <div className="mobile-service-row" key={service.id}>
              <span><i className={service.status === "ready" ? "ok" : service.status === "unknown" ? "unknown" : "down"} />{service.label}</span>
              <strong>{serviceStatusLabels[service.status]}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="mobile-status-card">
        <div className="mobile-section-title">
          <div><span className="mobile-kicker">TELEFONO</span><h2>Notifiche</h2></div>
        </div>
        <p className="mobile-card-copy">
          {!pushState.supported
            ? "Web Push richiede la PWA installata e aperta tramite HTTPS."
            : pushState.subscribed
              ? "Questo dispositivo è registrato. Gli appuntamenti con promemoria possono arrivare anche quando Cora non è aperta."
              : pushState.permission === "denied"
                ? "Notifiche bloccate nelle impostazioni del telefono."
                : "Registra questo dispositivo per ricevere i promemoria del calendario."}
        </p>
        {pushMessage && <p className="mobile-inline-status" role="status">{pushMessage}</p>}
        <div className="mobile-push-actions">
          {!pushState.subscribed ? (
            <button
              className="mobile-secondary-button"
              disabled={pushBusy || !pushState.supported || pushState.permission === "denied"}
              onClick={() => void pushAction(() => enablePushNotifications("Dispositivo mobile"), "Notifiche calendario attivate su questo dispositivo.")}
            >
              {pushBusy ? "Attivazione…" : "Attiva notifiche calendario"}
            </button>
          ) : (
            <>
              <button
                className="mobile-secondary-button"
                disabled={pushBusy}
                onClick={() => void pushAction(async () => { await sendTestPush(); }, "Notifica di prova inviata.")}
              >
                Invia notifica di prova
              </button>
              <button
                className="mobile-text-button"
                disabled={pushBusy}
                onClick={() => void pushAction(() => disablePushNotifications(), "Notifiche disattivate su questo dispositivo.")}
              >
                Disattiva su questo dispositivo
              </button>
            </>
          )}
        </div>
      </div>

      <ProjectRoadmap />

      <div className="mobile-secondary-links">
        <button onClick={() => onNavigate("chat")}><MessageCircle size={18} /><span>Chat Cora</span></button>
        <button onClick={() => onNavigate("activity")}><Activity size={18} /><span>Attività</span></button>
        <button onClick={() => onNavigate("settings")}><Settings size={18} /><span>Impostazioni</span></button>
      </div>
    </section>
  );
}
