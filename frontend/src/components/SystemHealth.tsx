import HealthDashboard from "./HealthDashboard";
import ServerTelemetry from "./ServerTelemetry";
import { useHomeMonitoring } from "../services/useHomeMonitoring";

/** Sistema › Salute: server measurements, every automatic check and the state of each service. */
export default function SystemHealth() {
  const { telemetry, telemetryError, services, servicesError } = useHomeMonitoring();
  return <div className="system-health">
    <ServerTelemetry telemetry={telemetry} error={telemetryError} />
    <div className="system-card"><HealthDashboard showServices services={services} servicesError={servicesError} /></div>
  </div>;
}
