import PriorityAssessment from "./PriorityAssessment";
import HealthDashboard from "./HealthDashboard";
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
  onOpenUpdates,
}: {
  health: BackendHealth | null;
  checking: boolean;
  onRefresh: () => void;
  onNavigate: (page: MobilePage) => void;
  onOpenUpdates: () => void;
}) {
  const { telemetry, services, telemetryError, servicesError, refresh } = useHomeMonitoring();
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

      <button type="button" className="mobile-primary-button mobile-update-button" onClick={onOpenUpdates}>
        <RefreshCw size={18} aria-hidden="true" /> Aggiorna Cora
      </button>
      <p className="mobile-update-help">Apre gli aggiornamenti per controllare versione, log e confermare il deploy.</p>

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
              <span><i className={service.status === "ready" ? "ok" : service.status === "unknown" ? "unknown" : "down"} />
                {service.browserUrl && /^https?:\/\/[^\s]+$/i.test(service.browserUrl)
                  ? <a href={service.browserUrl} target="_blank" rel="noopener noreferrer">{service.label}</a>
                  : service.label}
              </span>
              <strong>{serviceStatusLabels[service.status]}</strong>
            </div>
          ))}
        </div>
        <HealthDashboard compact />
      </div>

      <PriorityAssessment />
      <ProjectRoadmap />

      <div className="mobile-secondary-links">
        <button onClick={() => onNavigate("chat")}><MessageCircle size={18} /><span>Chat Cora</span></button>
        <button onClick={() => onNavigate("activity")}><Activity size={18} /><span>Attività</span></button>
        <button onClick={() => onNavigate("settings")}><Settings size={18} /><span>Impostazioni e notifiche push</span></button>
      </div>
    </section>
  );
}
