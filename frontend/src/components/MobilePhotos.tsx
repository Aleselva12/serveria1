import { ExternalLink, Images, RefreshCw, Upload } from "lucide-react";
import { useHomeMonitoring } from "../services/useHomeMonitoring";

function immichUrl() {
  const configured = (import.meta.env.VITE_IMMICH_URL || "").trim();
  if (configured) return configured.replace(/\/$/, "");
  return `${window.location.protocol}//${window.location.hostname}:2283`;
}

export default function MobilePhotos() {
  const { services, servicesError } = useHomeMonitoring();
  const immich = services.find((service) => service.id === "immich");
  const url = immichUrl();
  return (
    <section className="mobile-feature-page mobile-photos">
      <div className="mobile-feature-hero">
        <div className="mobile-feature-icon"><Images size={30} /></div>
        <div>
          <span className="mobile-kicker">FOTO</span>
          <h1>Immich</h1>
          <p>La tua libreria fotografica privata sul server.</p>
        </div>
      </div>

      <div className="mobile-status-card">
        <div className="mobile-section-title">
          <div>
            <span className="mobile-kicker">SERVIZIO</span>
            <h2>{immich?.status === "ready" ? "Immich online" : immich ? "Immich da controllare" : "Stato Immich"}</h2>
          </div>
          <i className={"mobile-large-dot " + (immich?.status === "ready" ? "ok" : "unknown")} />
        </div>
        <p className="mobile-card-copy">
          {immich?.detail || servicesError || "Il backend non ha ancora restituito lo stato del servizio."}
        </p>
        <a className="mobile-primary-button" href={url} target="_blank" rel="noreferrer">
          <Images size={18} /> Apri raccolta foto <ExternalLink size={15} />
        </a>
        <a className="mobile-secondary-button as-link" href={url} target="_blank" rel="noreferrer">
          <Upload size={18} /> Carica foto in Immich
        </a>
      </div>

      <div className="mobile-status-card mobile-info-card">
        <RefreshCw size={19} />
        <div>
          <strong>Prima versione</strong>
          <p>La PWA apre l'interfaccia Immich reale, senza duplicarne galleria, ricerca e backup. In seguito possiamo integrare album recenti e upload rapido direttamente qui tramite API Immich.</p>
        </div>
      </div>
    </section>
  );
}
