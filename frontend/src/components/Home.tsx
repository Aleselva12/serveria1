import { Activity, HardDrive, PlugZap, ShieldCheck, Wifi } from "lucide-react";
import type { BackendHealth } from "../types/contracts";
import ConnectionNotice from "./ConnectionNotice";

export default function Home({
  health,
  checking,
  checkedAt,
}: {
  health: BackendHealth | null;
  checking: boolean;
  checkedAt: string;
}) {
  return (
    <section className="home-page">
      <div className="home-hero system-card">
        <h1>Ciao, Alessandro</h1>
        <p>
          <ShieldCheck size={16} />
          {health
            ? "Cora è collegata al backend. La chat è disponibile; il monitoraggio delle prestazioni è da collegare."
            : checking
              ? "Verifica della connessione a Cora…"
              : "Il backend non è raggiungibile. Avvia Cora per usare la chat."}
        </p>
      </div>
      <div className="home-metrics">
        {["CPU", "RAM", "GPU"].map((label) => (
          <div className="system-card metric-card" key={label}>
            <div className="metric-head">
              <span>{label}</span>
              <span className="metric-tag pending">Da collegare</span>
            </div>
            <div className="metric-content">
              <div className="gauge unknown">
                <span>—</span>
              </div>
              <strong>Misurazione non disponibile</strong>
              <small>
                {label === "GPU"
                  ? "Presenza e carico da verificare"
                  : "In attesa del monitoraggio backend"}
              </small>
            </div>
          </div>
        ))}
      </div>
      <ConnectionNotice feature="telemetry" />
      <div className="home-secondary">
        <div className="system-card secondary-card">
          <h2>ARCHIVIAZIONE DISCO</h2>
          <div className="empty-metric">
            <HardDrive size={25} />
            <strong>—</strong>
            <p>Capacità e spazio utilizzato da collegare.</p>
          </div>
        </div>
        <div className="system-card secondary-card">
          <h2>RETE</h2>
          <div className="empty-metric">
            <Wifi size={25} />
            <strong>—</strong>
            <p>Traffico e interfacce da collegare.</p>
          </div>
        </div>
        <div className="system-card secondary-card">
          <h2>ALIMENTAZIONE</h2>
          <div className="power-row">
            <span className="power-icon">
              <PlugZap size={21} />
            </span>
            <div>
              <strong>Non verificata</strong>
              <p>Sensori e presenza UPS da collegare.</p>
            </div>
          </div>
        </div>
      </div>
      <div className="home-bottom">
        <div className="system-card activity-card">
          <div className="metric-head">
            <h2>Attività CPU nel tempo</h2>
            <span className="pill pending">Da collegare</span>
          </div>
          <div className="empty-metric">
            <Activity size={26} />
            <p>
              Il grafico comparirà quando saranno disponibili campioni reali.
            </p>
          </div>
        </div>
        <div className="system-card home-placeholder">
          <h2>Stato dei servizi</h2>
          <div className="settings-row">
            <strong>FastAPI</strong>
            <span className={"pill " + (health ? "success" : "")}>
              {health
                ? "Collegato"
                : checking
                  ? "Verifica…"
                  : "Non raggiungibile"}
            </span>
          </div>
          <div className="settings-row">
            <strong>Ollama</strong>
            <span
              className={"pill " + (health?.ollama_online ? "success" : "")}
            >
              {health
                ? health.ollama_online
                  ? "Raggiungibile"
                  : "Offline"
                : "Non verificato"}
            </span>
          </div>
          <small>
            {checkedAt &&
              "Ultimo controllo: " +
                new Date(checkedAt).toLocaleTimeString("it-IT")}
          </small>
          <ConnectionNotice feature="services" compact />
        </div>
      </div>
    </section>
  );
}
