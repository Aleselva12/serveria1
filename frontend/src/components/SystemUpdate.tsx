import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

type UpdateJob = { id: string; kind: string; status: string; phase?: string; commit?: string };
type Update = { platform: string; status?: string; directory?: string; commit?: string; phase?: string; available?: boolean; reason?: string; active_commit?: string; jobs?: UpdateJob[] };

export default function SystemUpdate() {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<Update | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update");
      if (!response.ok) throw Error("Stato aggiornamenti non disponibile.");
      setState(await response.json()); setError("");
    } catch (e) { setError(String(e)); }
  }
  useEffect(() => { if (open) void refresh(); }, [open]);
  useEffect(() => {
    if (!open || (state?.status !== "running" && !state?.jobs?.some(j => ["queued", "running"].includes(j.status)))) return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [open, state?.status, state?.jobs]);
  async function prepareServer() {
    setBusy(true); setError("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update/server/prepare", { method: "POST" });
      if (!response.ok) throw Error(await response.text());
      await refresh();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  async function applyServer(job: UpdateJob) {
    if (!job.commit || !window.confirm("Installare il rilascio " + job.commit.slice(0, 12) + "? Cora si riavvierà. Il servizio host eseguirà backup e controlli prima di confermare il risultato.")) return;
    setBusy(true); setError("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update/server/apply", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ release_id: job.id, expected_commit: job.commit }),
      });
      if (!response.ok) throw Error(await response.text());
      await refresh();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  async function prepare() {
    setBusy(true); setError("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update/prepare", { method: "POST" });
      if (!response.ok) throw Error("Preparazione non confermata: verifica lo stato prima di riprovare.");
      await refresh();
    } catch (e) { await refresh(); setError(String(e)); }
    finally { setBusy(false); }
  }
  return <div className="home-update-actions">
    <button className="file-tool" onClick={() => setOpen(v => !v)}>Aggiorna Cora</button>
    {open && <section aria-label="Aggiornamento di Cora" aria-live="polite">
      {error && <p role="alert">{error}</p>}
      <button className="text-button" onClick={() => void refresh()}>Verifica stato</button>
      {state?.platform === "windows" ? <>
        <p>Desktop Windows: prepara una nuova copia da GitHub ed esegue test e build. La copia attuale resta attiva.</p>
        <button className="file-tool" disabled={busy || state.status === "running"} onClick={() => void prepare()}>
          {busy || state.status === "running" ? "Preparazione in corso…" : "Prepara aggiornamento Windows"}
        </button>
        {state.status === "failed" && <p role="alert">Preparazione fallita nella fase {state.phase}. Aggiornamento non installato. Controlla le dipendenze e i test del candidato in {state.directory}.</p>}
        {state.status === "ready" && <>
          <p>Suite di regressione Windows, test frontend e build riusciti per il commit {state.commit}. Aggiornamento preparato, non installato. I test server completi sono eseguiti nella CI Linux.</p>
          <p>Prima di attivare: salva un backup PostgreSQL e della cartella data, chiudi i servizi Cora attuali, poi esegui ATTIVA.ps1 nella cartella indicata. Configurazione e dati restano quelli locali. Per tornare al codice precedente serve anche un backup compatibile del database.</p>
          <code>{state.directory}</code>
        </>}
      </> : state?.platform === "server" ? <>
        <p>Aggiornamenti integrati: GitHub main → verifiche → backup → installazione. Cora rimane il punto di controllo; il servizio host continua anche durante il riavvio.</p>
        {!state.available ? <p role="alert">{state.reason || "Updater non configurato: installazione iniziale tramite updater/README.md sul Debian."}</p> : <>
          <p>Versione installata: <code>{state.active_commit?.slice(0, 12) || "sconosciuta"}</code></p>
          <button className="file-tool" disabled={busy || state.jobs?.some(j => ["queued", "running"].includes(j.status))} onClick={() => void prepareServer()}>Prepara aggiornamento da GitHub</button>
          {state.jobs?.filter(j => j.kind === "prepare").slice(0, 5).map(job =>
            <div className="settings-row" key={job.id}>
              <div><strong>{job.status}</strong> · {job.phase || "In attesa"} · <code>{job.commit?.slice(0, 12)}</code></div>
              {job.status === "ready" && <button className="file-tool" disabled={busy} onClick={() => void applyServer(job)}>Installa versione verificata</button>}
            </div>
          )}
          {state.jobs?.filter(j => j.kind === "apply").slice(0, 3).map(job => <p key={job.id}>Installazione: {job.status} · {job.phase || ""}</p>)}
        </>}
      </> : null}
    </section>}
  </div>;
}
