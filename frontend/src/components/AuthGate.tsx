import { useEffect, useState } from "react";
import App from "../App";
import SharedFile from "./SharedFile";
import { sharedDownloadPath } from "../services/sharedFiles";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

export default function AuthGate() {
  const [mode, setMode] = useState("password");
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setChecking(true);
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/auth/status");
      if (!response.ok) throw new Error("Backend non disponibile.");
      const data = await response.json();
      setMode(data.mode || "password");
      setAuthenticated(data.authenticated === true);
      setError("");
    } catch { setError("Collegamento non riuscito. Avvia il backend e riprova."); }
    finally { setChecking(false); }
  }
  useEffect(() => {
    void refresh();
    const expire = () => { setAuthenticated(false); setOffline(false); };
    window.addEventListener("cora:unauthorized", expire);
    return () => window.removeEventListener("cora:unauthorized", expire);
  }, []);
  const sharedPath = sharedDownloadPath(window.location.hash);
  if (authenticated) return sharedPath ? <SharedFile path={sharedPath} /> : <App authMode={mode} />;
  if (offline && !sharedPath) return <App authMode={mode} />;
  if (checking) return <main className="auth-page"><section className="section-card auth-card" aria-live="polite"><div className="eyebrow">CORA</div><h1>Verifica accesso…</h1></section></main>;
  if (mode === "desktop") return <main className="auth-page"><section className="section-card auth-card">
    <h1>Accesso locale a Cora</h1><p>Apri http://127.0.0.1:5173 sul computer che esegue AVVIO.cmd.</p>
    <p role="alert">{error || "Accesso locale non disponibile. Riavvia Cora con AVVIO.cmd."}</p>
    <button onClick={() => void refresh()}>Riprova accesso</button>
  </section></main>;
  if (mode === "tailscale") return <main className="auth-page"><section className="section-card auth-card">
    <div className="eyebrow">CORA · TAILSCALE</div><h1>Collega il tuo dispositivo</h1>
    <p>Attiva Tailscale con l’account autorizzato e apri l’indirizzo HTTPS privato del server. L’accesso a Cora è automatico.</p>
    {error ? <p role="alert">{error}</p> : <p role="alert">Identità Tailscale assente o non autorizzata.</p>}
    <button className="file-tool" type="button" onClick={() => void refresh()}>Riprova accesso</button>
  </section></main>;
  return <main className="auth-page"><form className="section-card auth-card" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Accesso non riuscito.");
      setPassword(""); setAuthenticated(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Accesso non riuscito."); }
    finally { setBusy(false); }
  }}><div className="eyebrow">CORA</div><h1>Accedi al tuo server</h1><p>La sessione dura sette giorni. Puoi revocarla dalle Impostazioni.</p>
    <label>Nome utente<input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} /></label>
    <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label>
    {error && <p role="alert">{error}</p>}<button className="file-tool" disabled={busy || checking}>{busy ? "Accesso…" : "Accedi"}</button>
    <button className="text-button" type="button" disabled={checking} onClick={() => void refresh()}>Verifica connessione</button>
    {error && <button className="text-button" type="button" onClick={() => setOffline(true)}>Visualizza interfaccia offline</button>}
  </form></main>;
}
