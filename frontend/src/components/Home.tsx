import PriorityAssessment from "./PriorityAssessment";
import { ArrowRight, ShieldCheck, Wifi } from "lucide-react";
import CurrentCommit from "./CurrentCommit";
import type { BackendHealth } from "../types/contracts";
import { useHomeMonitoring } from "../services/useHomeMonitoring";
import { serviceSummary } from "../services/homeStatus";
import ProjectRoadmap from "./ProjectRoadmap";

/** Programs the owner opens often, as quick links. Technical services stay in Sistema › Salute. */
const quickServices = new Set(["immich", "nextcloud", "magazzino_tele", "preventivi", "n8n"]);
const safeUrl = (value?: string) => value && /^https?:\/\/[^\s]+$/i.test(value) ? value : null;

export default function Home({
  health,
  checking,
  onOpenUpdates,
  onOpenHealth,
}: {
  health: BackendHealth | null;
  checking: boolean;
  checkedAt: string;
  onOpenUpdates: () => void;
  onOpenHealth: () => void;
}) {
  const { services, servicesError } = useHomeMonitoring();
  const links = services.filter(s => quickServices.has(s.id) && safeUrl(s.browserUrl));
  return (
    <section className="home-page">
      <div className="home-hero system-card">
        <h1>Il tuo server</h1>
        <p className={"home-connection " + (health ? "is-connected" : "is-unknown")}>
          {health ? <ShieldCheck size={16} /> : <Wifi size={16} />}
          {health
            ? "Cora è raggiungibile · " + serviceSummary(services, servicesError)
            : checking
              ? "Verifica della connessione a Cora…"
              : "Il backend non è raggiungibile. Avvia Cora sul computer o sul server."}
        </p>
        {links.length > 0 && <div className="home-quick-services" aria-label="Apri un programma">
          {links.map(s => <a key={s.id} href={safeUrl(s.browserUrl)!} target="_blank" rel="noopener noreferrer"
            className={"home-quick-service " + s.status}>{s.label}<span aria-hidden="true"> ↗</span></a>)}
        </div>}
        <div className="home-update-actions">
          <button className="file-tool" onClick={onOpenHealth}>Salute del server <ArrowRight size={14} /></button>
          <button className="file-tool" onClick={onOpenUpdates}>Aggiornamenti <ArrowRight size={14} /></button>
        </div>
        <small><CurrentCommit /></small>
      </div>
      <PriorityAssessment />
      <ProjectRoadmap />
    </section>
  );
}
