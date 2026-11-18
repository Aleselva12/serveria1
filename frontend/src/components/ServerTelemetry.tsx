import { Activity, HardDrive, PlugZap, Wifi } from "lucide-react";
import type { ServerTelemetry as Telemetry } from "../types/contracts";

const bytes = (value: number) =>
  (value / 1024 ** 3).toLocaleString("it-IT", { maximumFractionDigits: 1 }) +
  " GiB";
const rate = (value: number) =>
  (value / 1e6).toLocaleString("it-IT", { maximumFractionDigits: 2 }) +
  " Mbit/s";

/** CPU, RAM, GPU, disks, network, power and CPU history. Lives in Sistema › Salute. */
export default function ServerTelemetry({ telemetry, error }: { telemetry: Telemetry | null; error: string }) {
  const history = telemetry?.cpuHistory ?? [];
  const first = history.length ? Date.parse(history[0].at) : 0;
  const last = history.length
    ? Date.parse(history[history.length - 1].at)
    : first;
  const points = history
    .map(
      (p) =>
        `${last > first ? ((Date.parse(p.at) - first) / (last - first)) * 600 : 0},${100 - p.percent}`,
    )
    .join(" ");
  return (
    <div className="server-telemetry">
      <small className="muted">
        {telemetry
          ? "Misurazioni visibili al processo Cora · " + new Date(telemetry.sampledAt).toLocaleTimeString("it-IT")
          : "In attesa delle misurazioni del server"}
      </small>
      {error && (
        <div className="connection-notice" role="alert">
          {error}
        </div>
      )}
      <div className="home-metrics">
        {(["cpu", "ram", "gpu"] as const).map((key) => {
          const metric = telemetry?.[key];
          const value = metric?.percent;
          const known = value != null;
          return (
            <div className="system-card metric-card" key={key}>
              <div className="metric-head">
                <span>{key.toUpperCase()}</span>
                <span className="metric-tag">
                  {known
                    ? "Rilevato"
                    : telemetry
                      ? key === "cpu"
                        ? "Primo campione"
                        : "Non disponibile"
                      : "In attesa"}
                </span>
              </div>
              <div className="metric-content">
                <div
                  className={"gauge" + (known ? "" : " unknown")}
                  style={
                    known
                      ? {
                          background: `conic-gradient(#10b981 ${value * 3.6}deg, #eeeeee 0deg)`,
                        }
                      : undefined
                  }
                >
                  <span>
                    {known
                      ? value.toLocaleString("it-IT", {
                          maximumFractionDigits: 1,
                        }) + "%"
                      : "—"}
                  </span>
                </div>
                <strong>{metric?.label ?? key.toUpperCase()}</strong>
                <small>
                  {metric?.detail ?? "Misurazione non disponibile"}
                  {metric?.temperatureC != null &&
                    ` · ${metric.temperatureC} °C`}
                </small>
              </div>
            </div>
          );
        })}
      </div>
      <div className="home-secondary">
        <div className="system-card secondary-card">
          <h2>ARCHIVIAZIONE DISCO</h2>
          {telemetry?.disks.length ? (
            telemetry.disks.map((disk) => (
              <div className="disk-line" key={disk.id}>
                <div>
                  <strong>{disk.label}</strong>
                  <span>
                    {bytes(disk.usedBytes)} / {bytes(disk.totalBytes)}
                  </span>
                </div>
                <div className="progress">
                  <i
                    style={{
                      width: `${disk.totalBytes ? (disk.usedBytes / disk.totalBytes) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            ))
          ) : (
            <div className="empty-metric">
              <HardDrive size={25} />
              <p>Spazio disco non disponibile</p>
            </div>
          )}
        </div>
        <div className="system-card secondary-card">
          <h2>RETE</h2>
          <div className="empty-metric">
            <Wifi size={25} />
            {telemetry?.network ? (
              <>
                <strong>
                  ↓ {rate(telemetry.network.receiveBitsPerSecond)}
                </strong>
                <strong>
                  ↑ {rate(telemetry.network.transmitBitsPerSecond)}
                </strong>
                <p>{telemetry.network.interfaceName}</p>
              </>
            ) : (
              <p>
                {telemetry
                  ? "In attesa di due campioni delle interfacce attive"
                  : "Traffico non disponibile"}
              </p>
            )}
          </div>
        </div>
        <div className="system-card secondary-card">
          <h2>ALIMENTAZIONE</h2>
          <div className="power-row">
            <span className="power-icon">
              <PlugZap size={21} />
            </span>
            <div>
              <strong>
                {
                  {
                    mains: "Collegata alla rete",
                    ups: "UPS",
                    battery: "A batteria",
                    unknown: "Non rilevabile",
                  }[telemetry?.power?.kind ?? "unknown"]
                }
              </strong>
              <p>{telemetry?.power?.detail ?? "In attesa dei sensori"}</p>
            </div>
          </div>
        </div>
      </div>
      <div className="home-bottom">
        <div className="system-card activity-card">
          <div className="metric-head">
            <h2>Attività CPU nel tempo</h2>
            <span className="pill">{history.length} campioni</span>
          </div>
          {history.length > 1 ? (
            <>
              <div className="home-cpu-chart">
                <span>100%</span>
                <svg
                  viewBox="0 0 600 100"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="Utilizzo CPU da zero a cento percento"
                >
                  <polyline
                    points={points}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
                <span>0%</span>
              </div>
              <div className="home-chart-time">
                <small>{new Date(first).toLocaleTimeString("it-IT")}</small>
                <small>{new Date(last).toLocaleTimeString("it-IT")}</small>
              </div>
              <small>
                Ultimi 120 campioni · cronologia azzerata al riavvio del backend
              </small>
            </>
          ) : (
            <div className="empty-metric">
              <Activity size={26} />
              <p>In attesa di campioni CPU reali</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
