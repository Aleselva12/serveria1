import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

type Update = { platform: string; status: string; url?: string; directory?: string; commit?: string; phase?: string };

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
    if (!open || state?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [open, state?.status]);
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
      </> : state?.url ? <>
        <p>Server Debian: apri il servizio aggiornamenti del server. Controlla l’esito del job prima di considerare completato l’aggiornamento.</p>
        <a className="home-update-link" href={state.url} target="_blank" rel="noopener noreferrer">Apri aggiornamenti Debian</a>
      </> : state && <p>Servizio aggiornamenti Debian non configurato. Imposta CORA_UPDATE_URL con l’indirizzo HTTPS della pagina host e segui updater/README.md. Il servizio richiede configurazione separata dall’app.</p>}
    </section>}
  </div>;
}
