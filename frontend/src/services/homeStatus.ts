import type { ServiceStatus } from "../types/contracts";

export const serviceStatusLabels: Record<ServiceStatus["status"], string> = {
  ready: "Raggiungibile", busy: "Occupato", offline: "Non raggiungibile", error: "Errore", unknown: "Non verificato",
};

/** Probes prove reachability, never an end-to-end functional test. */
export function serviceSummary(services: ServiceStatus[], error: string) {
  if (error) return "Stato dei servizi non disponibile";
  if (!services.length) return "Controllo dei servizi in attesa";
  const ready = services.filter(service => service.status === "ready").length;
  const issues = services.filter(service => service.status === "offline" || service.status === "error").length;
  const unknown = services.filter(service => service.status === "unknown").length;
  return [`${ready}/${services.length} servizi raggiungibili`,
    ...(issues ? [`${issues} da controllare`] : []),
    ...(unknown ? [`${unknown} non verificati`] : []),
  ].join(" · ");
}
