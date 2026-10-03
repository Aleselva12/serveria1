import { useCallback, useEffect, useRef, useState } from "react";
import type { BackendHealth, BackendRegistry } from "../types/contracts";
import { api } from "./api";

export function useBackend() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [registry, setRegistry] = useState<BackendRegistry | null>(null);
  const [error, setError] = useState("");
  const [registryError, setRegistryError] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [checking, setChecking] = useState(true);
  const live = useRef(false);
  const pending = useRef(false);
  const registryLoaded = useRef(false);
  const refresh = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    if (live.current) setChecking(true);
    const [status, capabilities] = await Promise.allSettled([
      api.health(),
      registryLoaded.current ? Promise.resolve(null) : api.registry(),
    ]);
    pending.current = false;
    if (!live.current) return;
    setChecking(false);
    setCheckedAt(new Date().toISOString());
    if (status.status === "fulfilled") {
      setHealth(status.value);
      setError("");
    } else {
      setHealth(null);
      setError(
        status.reason instanceof Error
          ? status.reason.message
          : "Collegamento non riuscito.",
      );
    }
    if (capabilities.status === "fulfilled" && capabilities.value) {
      registryLoaded.current = true;
      setRegistry(capabilities.value);
      setRegistryError("");
    } else if (capabilities.status === "rejected") {
      setRegistry(null);
      setRegistryError(
        capabilities.reason instanceof Error
          ? capabilities.reason.message
          : "Registro non disponibile.",
      );
    }
  }, []);
  useEffect(() => {
    live.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      if ((typeof document === "undefined" || !document.hidden)) void refresh();
    }, 15000);
    return () => {
      live.current = false;
      clearInterval(timer);
    };
  }, [refresh]);
  return {
    health,
    registry,
    error,
    registryError,
    checkedAt,
    checking,
    refresh,
  };
}
