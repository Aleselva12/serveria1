import HealthDashboard from "./HealthDashboard";
import { useHomeMonitoring } from "../services/useHomeMonitoring";

/** Sistema › Salute: every automatic check and the state of each service. */
export default function SystemHealth() {
  const { services, servicesError } = useHomeMonitoring();
  return <div className="system-card"><HealthDashboard showServices services={services} servicesError={servicesError} /></div>;
}
