import { useCallback, useEffect, useState } from "react";
import App from "../App";
import SharedFile from "./SharedFile";
import { sharedDownloadPath } from "../services/sharedFiles";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

// Access is automatic (Tailscale on the server, loopback with AVVIO.cmd on Windows).
// There is no password form: when the backend does not answer, for example while
// it restarts after an update, the page waits and asks again on its own.
const RETRY_MS = 5000;

type Status = "checking" | "ready" | "denied" | "unreachable";

export default function AuthGate() {
  const [mode, setMode] = useState("");
  const [status, setStatus] = useState<Status>("checking");
  const [offline, setOffline] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/auth/status");
      if (!response.ok) throw new Error("Backend non disponibile.");
      const data = await response.json();
      setMode(data.mode || "");
      setStatus(data.authenticated === true ? "ready" : "denied");
    } catch { setStatus(current => current === "ready" ? current : "unreachable"); }
  }, []);
  useEffect(() => {
    void refresh();
    // A 401 elsewhere is re-checked, never turned into a login prompt by itself.
    const recheck = () => { setOffline(false); void refresh(); };
    window.addEventListener("cora:unauthorized", recheck);
    return () => window.removeEventListener("cora:unauthorized", recheck);
  }, [refresh]);
  useEffect(() => {
    if (status !== "unreachable" || offline) return;
    const timer = setTimeout(() => void refresh(), RETRY_MS);
    return () => clearTimeout(timer);
  }, [status, offline, refresh]);
  const sharedPath = sharedDownloadPath(window.location.hash);
  if (status === "ready") return sharedPath ? <SharedFile path={sharedPath} /> : <App authMode={mode} />;
  if (offline && !sharedPath) return <App authMode={mode} />;
  const retry = <button className="file-tool" type="button" onClick={() => void refresh()}>Riprova ora</button>;
  if (status === "checking") return <main className="auth-page"><section className="section-card auth-card" aria-live="polite"><div className="eyebrow">CORA</div><h1>Verifica accesso…</h1></section></main>;
  if (status === "unreachable") return <main className="auth-page"><section className="section-card auth-card" aria-live="polite">
    <div className="eyebrow">CORA</div><h1>Cora non risponde</h1>
    <p>Il server si sta avviando (per esempio dopo un aggiornamento) oppure non è raggiungibile. Riprovo da solo ogni pochi secondi.</p>
    {retry}
    {!sharedPath && <button className="text-button" type="button" onClick={() => setOffline(true)}>Visualizza interfaccia offline</button>}
  </section></main>;
  if (mode === "desktop") return <main className="auth-page"><section className="section-card auth-card">
    <h1>Accesso locale a Cora</h1><p>Apri http://127.0.0.1:5173 sul computer che esegue AVVIO.cmd.</p>
    <p role="alert">Accesso locale non disponibile. Riavvia Cora con AVVIO.cmd.</p>{retry}
  </section></main>;
  if (mode === "tailscale") return <main className="auth-page"><section className="section-card auth-card">
    <div className="eyebrow">CORA · TAILSCALE</div><h1>Collega il tuo dispositivo</h1>
    <p>Attiva Tailscale con l’account autorizzato e apri l’indirizzo HTTPS privato del server. L’accesso a Cora è automatico.</p>
    <p role="alert">Identità Tailscale assente o non autorizzata.</p>{retry}
  </section></main>;
  return <main className="auth-page"><section className="section-card auth-card">
    <div className="eyebrow">CORA</div><h1>Accesso non configurato</h1>
    <p>L’accesso con password non è più disponibile. Configura l’accesso Tailscale sul server con <code>deploy/tailscale_login.py</code>.</p>{retry}
  </section></main>;
}
