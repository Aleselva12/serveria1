import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

type UpdateJob = {
  id: string; kind: string; status: string; phase?: string; commit?: string;
  base_commit?: string; error?: string; error_stage?: string; error_detail?: string;
  cleanup_error?: string; updated_at?: string;
};
type Update = {
  platform: string; status?: string; directory?: string; commit?: string;
  phase?: string; available?: boolean; reason?: string; active_commit?: string;
  jobs?: UpdateJob[];
};
const working = (job: UpdateJob) => ["queued", "running"].includes(job.status);
const phaseNames: Record<string, string> = {
  queued: "In attesa", building: "Compilazione delle immagini", testing: "Esecuzione dei test",
  ready: "Verifiche completate", stopping: "Arresto controllato dei servizi",
  backing_up: "Backup dei dati", backup_complete: "Backup completato",
  migration_trial: "Prova delle migrazioni su una copia dei dati",
  candidate_starting: "Avvio della versione candidata",
  restoring: "Ripristino della versione precedente", completed: "Completato",
};
const describe = (job: UpdateJob) => phaseNames[job.phase || ""] || job.phase || job.status;
const role = (job: UpdateJob) => job.kind === "prepare" ? "Preparazione" : job.kind === "apply" ? "Installazione" : "Operazione";
const short = (hash?: string) => hash?.slice(0, 12) || "non disponibile";

export default function SystemUpdate({ standalone = false }: { standalone?: boolean } = {}) {
  const [expanded, setExpanded] = useState(false);
  const open = standalone || expanded;
  const [state, setState] = useState<Update | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [statusError, setStatusError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionNote, setActionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  async function refresh() {
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update");
      if (!response.ok) throw Error("HTTP " + response.status);
      const data: Update = await response.json();
      setState(data); setConnected(true); setStatusError("");
    } catch {
      // Never display an old queued job as current when the API cannot be reached.
      setConnected(false);
      setStatusError("Backend temporaneamente non raggiungibile. Durante l'installazione Cora può riavviarsi: l'updater sul Debian continua indipendentemente. Non ripetere la richiesta; la pagina riproverà automaticamente.");
    }
  }

  useEffect(() => {
    if (!open) return;
    void refresh();
    // Poll even while disconnected or when no job has been returned yet.
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [open]);

  async function invoke(route: string, body?: object) {
    setBusy(true); setActionError(""); setActionNote("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + route, {
        method: "POST", ...(body ? {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}),
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw Error(typeof errorBody.detail === "string" ? errorBody.detail : "Operazione non accettata (HTTP " + response.status + ").");
      }
      setActionNote("Richiesta accettata. Attendo le verifiche del servizio updater.");
      await refresh();
    } catch (error) {
      // If the response was lost, the daemon may have accepted the request.
      // In particular, never automatically repeat an uncertain POST.
      setActionError((error instanceof Error ? error.message : String(error)) + ". Esito non confermato: controlla lo stato prima di riprovare.");
    } finally { setBusy(false); }
  }

  const jobs = state?.jobs || [];
  const running = jobs.find(working);
  const ready = jobs.find(job => job.kind === "prepare" && job.status === "ready" &&
    !!job.base_commit && job.base_commit === state?.active_commit);
  const recent = jobs[0];
  const shown = running || ready || recent;
  const canAct = connected === true && state?.available === true && !busy && !running;

  return <div className={standalone ? "system-card" : "home-update-actions"}>
    {standalone ? <>
      <h1>Aggiornamenti Cora</h1>
      <p>Il servizio di aggiornamento gira sul Debian e prosegue anche durante il riavvio di Cora.</p>
    </> : <button className="file-tool" onClick={() => setExpanded(v => !v)}>Aggiorna Cora</button>}
    {open && <section aria-label="Aggiornamento di Cora" aria-live="polite">
      {connected === false && <p role="status" style={{ color: "#965a14" }}>{statusError}</p>}
      {actionError && <p role="alert" style={{color:"#b42318",fontWeight:600}}>{actionError}</p>}
      {actionNote && !actionError && <p role="status">{actionNote}</p>}
      <button className="text-button" onClick={() => void refresh()}>Verifica stato</button>
      {state?.platform === "windows" ? <>
        <p>Desktop Windows: prepara una copia separata del codice, esegue test e build, senza installarla automaticamente.</p>
        <button className="file-tool" disabled={connected !== true || busy || state.status === "running"}
          onClick={() => void invoke("/api/v1/system/update/prepare")}>Prepara aggiornamento Windows</button>
        {state.status === "failed" && <p role="alert" style={{color:"#b42318"}}>Preparazione fallita nella fase {state.phase}. La versione installata non è cambiata.</p>}
        {state.status === "ready" && <>
          <p>Versione {short(state.commit)} verificata e preparata, non ancora installata.</p>
          <p>Per attivare il candidato, esegui il backup dei dati e segui le istruzioni della cartella preparata.</p>
          <code>{state.directory}</code>
        </>}
      </> : state?.platform === "server" ? <>
        {state.available === false && connected === true &&
          <p role="alert" style={{color:"#b42318"}}>{state.reason || "Servizio updater non disponibile."}</p>}
        <p>Commit installato: <code>{short(state.active_commit)}</code></p>
        {state.available !== false && <button className="file-tool" disabled={!canAct}
          onClick={() => void invoke("/api/v1/system/update/server/prepare")}>
          Prepara aggiornamento da GitHub
        </button>}
        {connected === false && shown &&
          <p>Ultimo stato noto (non confermato): {role(shown)} · {describe(shown)}. Non è un'indicazione dello stato attuale.</p>}
        {connected === true && shown && <div className="settings-row">
          <div>
            <strong>{running ? role(shown) + ": " + describe(shown) :
              ready && shown.id === ready.id ? "Versione pronta per l'installazione" :
              "Ultimo risultato: " + role(shown) + " · " + describe(shown)}</strong>
            {running && <p role="status">L'updater è al lavoro sul server. La fase viene aggiornata automaticamente.</p>}
            {shown.status === "failed" && <>
              <p role="alert" style={{color:"#b42318",fontWeight:600}}>
                Aggiornamento non riuscito. Motivo: {shown.error || "Controlla il log privato del servizio updater sul Debian."}
              </p>
              {(shown.error_stage || shown.error_detail || shown.cleanup_error) && <details className="updater-diagnostic">
                <summary>Mostra dettagli tecnici</summary>
                {shown.error_stage && <p><strong>Passaggio:</strong> {shown.error_stage}</p>}
                {shown.error_detail && <pre>{shown.error_detail}</pre>}
                {shown.cleanup_error && <p><strong>Pulizia ambiente:</strong> {shown.cleanup_error}</p>}
              </details>}
            </>}
            {shown.status === "recovery_required" && <p role="alert" style={{color:"#b42318",fontWeight:600}}>
              È necessario un intervento sul server prima di tentare nuovi aggiornamenti.
            </p>}
          </div>
          {ready && !running && shown.id === ready.id &&
            <button className="file-tool" disabled={!canAct} onClick={() => {
              if (!window.confirm("Installare il commit " + short(ready.commit) + "? Cora verrà riavviata dopo backup e test.")) return;
              void invoke("/api/v1/system/update/server/apply", {
                release_id: ready.id, expected_commit: ready.commit,
              });
            }}>Installa versione verificata</button>}
        </div>}
        {!!jobs.length && <button className="text-button" onClick={() => setShowHistory(v => !v)}>
          {showHistory ? "Nascondi cronologia aggiornamenti" : "Mostra cronologia aggiornamenti"}
        </button>}
        {showHistory && jobs.slice(0, 15).map(job => <div key={job.id} className="settings-row">
          <span>{role(job)} · {job.status} · {describe(job)} · {short(job.commit)}</span>
          {job.status === "failed" && <div className="update-history-error" role="alert">
            <span style={{color:"#b42318"}}>{job.error || "Dettagli non disponibili"}</span>
            {(job.error_stage || job.error_detail || job.cleanup_error) && <details className="updater-diagnostic compact">
              <summary>Dettagli</summary>
              {job.error_stage && <p><strong>Passaggio:</strong> {job.error_stage}</p>}
              {job.error_detail && <pre>{job.error_detail}</pre>}
              {job.cleanup_error && <p><strong>Pulizia ambiente:</strong> {job.cleanup_error}</p>}
            </details>}
          </div>}
        </div>)}
      </> : connected === null ? <p>Caricamento stato aggiornamenti…</p> : null}
    </section>}
  </div>;
}
