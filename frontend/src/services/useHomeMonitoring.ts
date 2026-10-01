import { useEffect, useState } from "react";
import { api } from "./api";
import type { ServerTelemetry, ServiceStatus } from "../types/contracts";

export function useHomeMonitoring() {
  const [telemetry, setTelemetry] = useState<ServerTelemetry | null>(null);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [telemetryError, setTelemetryError] = useState("");
  const [servicesError, setServicesError] = useState("");
  useEffect(() => {
    let live = true;
    let metricsPending = false;
    let servicesPending = false;
    async function metrics() {
      if (metricsPending) return;
      metricsPending = true;
      try {
        const data = await api.telemetry();
        if (live) {
          setTelemetry(data);
          setTelemetryError("");
        }
      } catch (error) {
        if (live) {
          setTelemetry(null);
          setTelemetryError(
            error instanceof Error
              ? error.message
              : "Monitoraggio non disponibile",
          );
        }
      } finally {
        metricsPending = false;
      }
    }
    async function status() {
      if (servicesPending) return;
      servicesPending = true;
      try {
        const data = await api.services();
        if (live) {
          setServices(data.services);
          setServicesError("");
        }
      } catch (error) {
        if (live) {
          setServices([]);
          setServicesError(
            error instanceof Error
              ? error.message
              : "Stato servizi non disponibile",
          );
        }
      } finally {
        servicesPending = false;
      }
    }
    void metrics();
    void status();
    const metricTimer = window.setInterval(() => void metrics(), 5000);
    const serviceTimer = window.setInterval(() => void status(), 15000);
    return () => {
      live = false;
      clearInterval(metricTimer);
      clearInterval(serviceTimer);
    };
  }, []);
  return { telemetry, services, telemetryError, servicesError };
}
