import { useEffect, useState } from "react";
import App from "../App";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

export default function AuthGate() {
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
  if (authenticated || offline) return <App />;
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
