import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

type UpdateJob = {
  id: string; kind: string; status: string; phase?: string; commit?: string;
  base_commit?: string; error?: string; error_stage?: string; error_detail?: string;
  cleanup_error?: string; updated_at?: string; branch?: string; compare_url?: string;
};
type Pending = {
  release_id: string; workspace_id: string; commit: string; status: string; active: boolean;
  created_at?: string; published?: { branch?: string; compare_url: string } | null;
};
type GitHubState = {
  available?: boolean; reason?: string; configured?: boolean; repository?: string; branch?: string;
  active_commit?: string; github_commit?: string; ahead?: number; behind?: number;
  state?: "aligned" | "ahead" | "behind" | "diverged"; pending?: Pending[];
};
type Component = {
  id: string; label: string; status: string; installed: string; expected: string; note: string;
};
type Components = { commit: string; aligned: boolean; components: Component[] };
type Update = {
  platform: string; status?: string; directory?: string; commit?: string;
  phase?: string; available?: boolean; reason?: string; active_commit?: string;
  jobs?: UpdateJob[]; components?: Components | null;
};
const componentStatus: Record<string, [string, string]> = {
  ok: ["Aggiornato", "#1f7a4d"], outdated: ["Non aggiornato", "#b42318"],
  untracked: ["Fuori dai rilasci", "#b42318"], stopped: ["Fermo", "#b42318"],
  missing: ["Non installato", "#b42318"], updating: ["In aggiornamento", "#965a14"],
  unknown: ["Non verificabile", "#965a14"],
};
const working = (job: UpdateJob) => ["queued", "running"].includes(job.status);
const phaseNames: Record<string, string> = {
  queued: "In attesa", awaiting_updater: "Aggiornamento dell'updater prima dell'installazione", building: "Compilazione delle immagini", testing: "Esecuzione dei test",
  ready: "Verifiche completate", stopping: "Arresto controllato dei servizi",
  backing_up: "Backup dei dati", backup_complete: "Backup completato",
  migration_trial: "Prova delle migrazioni su una copia dei dati",
  candidate_starting: "Avvio della versione candidata", publishing: "Invio del ramo a GitHub",
  restoring: "Ripristino della versione precedente", completed: "Completato",
};
const describe = (job: UpdateJob) => phaseNames[job.phase || ""] || job.phase || job.status;
const role = (job: UpdateJob) => job.kind === "prepare" ? "Preparazione" : job.kind === "apply" ? "Installazione" :
  job.kind === "publish" ? "Invio a GitHub" : "Operazione";
const plural = (n: number, one: string, many: string) => n + " " + (n === 1 ? one : many);
function compareText(github: GitHubState) {
  const ahead = github.ahead || 0, behind = github.behind || 0;
  if (github.state === "aligned") return "Cora è all'ultimo commit di GitHub.";
  if (github.state === "behind") return "Cora è indietro di " + plural(behind, "commit", "commit") + " rispetto a GitHub: puoi aggiornare.";
  if (github.state === "ahead") return "Il server è avanti di " + plural(ahead, "commit", "commit") + " non ancora su GitHub: inviali con la sezione qui sotto.";
  if (github.state === "diverged") return "Server e GitHub divergono: " + plural(ahead, "commit", "commit") + " solo sul server, " + plural(behind, "commit", "commit") + " solo su GitHub.";
  return "";
}
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
  const [github, setGithub] = useState<GitHubState | null>(null);
  const [githubBusy, setGithubBusy] = useState(false);

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

  async function refreshGithub() {
    setGithubBusy(true);
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update/server/github");
      if (!response.ok) throw Error("HTTP " + response.status);
      setGithub(await response.json());
    } catch {
      setGithub({ available: false, reason: "Confronto con GitHub non riuscito. Riprova con \"Controlla GitHub\"." });
    } finally { setGithubBusy(false); }
  }

  const platform = state?.platform;
  useEffect(() => {
    // The comparison fetches from GitHub: only on opening, on request and after a job ends.
    if (open && platform === "server") void refreshGithub();
  }, [open, platform]);

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
  const updateJobs = jobs.filter(job => job.kind !== "publish");
  const lastPublish = jobs.find(job => job.kind === "publish");
  const ready = jobs.find(job => job.kind === "prepare" && job.status === "ready" &&
    !!job.base_commit && job.base_commit === state?.active_commit);
  const recent = updateJobs[0];
  const shown = (running?.kind === "publish" ? undefined : running) || ready || recent;
  const canAct = connected === true && state?.available === true && !busy && !running;
  const runningId = running?.id;
  const [lastRunning, setLastRunning] = useState<string | undefined>();
  useEffect(() => {
    if (lastRunning && !runningId && platform === "server") void refreshGithub();
    setLastRunning(runningId);
  }, [runningId]);
  const diverged = github?.available !== false && github?.state === "diverged";
  const pending = github?.pending || [];

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
        <section className="update-section" aria-label="Aggiorna Cora">
          <h2>Aggiorna Cora</h2>
          <p className="update-hint">Installa sul server l'ultimo commit del ramo {github?.branch || "main"} su GitHub, dopo build, test e backup.</p>
          <div className="update-compare">
            <span>Commit attivo sul server</span><code>{short(state.active_commit)}</code>
            <span>Ultimo commit su GitHub</span><code>{github?.available === false ? "non verificato" : github?.configured === false ? "repository non configurata" : short(github?.github_commit)}</code>
          </div>
          {github?.available === false && <p role="status" style={{color:"#965a14"}}>{github.reason}</p>}
          {github?.state && <p role="status" style={{color: diverged ? "#b42318" : github.state === "ahead" ? "#965a14" : "#1f7a4d", fontWeight: 600}}>
            {compareText(github)}
          </p>}
          {diverged && <p role="alert" style={{color:"#b42318"}}>
            Aggiornamento bloccato finché la pull request con le modifiche del server non è unita su GitHub.
            Usa "Create a merge commit" (non squash o rebase), poi premi "Controlla GitHub".
          </p>}
          {state.available !== false && <button className="text-button" disabled={githubBusy} onClick={() => void refreshGithub()}>
            {githubBusy ? "Controllo GitHub…" : "Controlla GitHub"}
          </button>}
          {connected === true && state.available !== false && <ComponentVersions value={state.components} />}
          {state.available !== false && <button className="file-tool" disabled={!canAct || diverged}
            onClick={() => void invoke("/api/v1/system/update/server/prepare")}>
            Prepara aggiornamento da GitHub
          </button>}
          {connected === false && shown &&
            <p>Ultimo stato noto (non confermato): {role(shown)} · {describe(shown)}. Non è un'indicazione dello stato attuale.</p>}
          {connected === true && shown && <div className="settings-row">
            <div>
              <strong>{working(shown) ? role(shown) + ": " + describe(shown) :
                ready && shown.id === ready.id ? "Versione pronta per l'installazione" :
                "Ultimo risultato: " + role(shown) + " · " + describe(shown)}</strong>
              {working(shown) && <p role="status">L'updater è al lavoro sul server. La fase viene aggiornata automaticamente.</p>}
              {shown.status === "failed" && <>
                <p role="alert" style={{color:"#b42318",fontWeight:600}}>
                  Operazione non riuscita. Motivo: {shown.error || "Controlla il log privato del servizio updater sul Debian."}
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
        </section>
        {state.available !== false && <section className="update-section" aria-label="Invia modifiche a GitHub">
          <h2>Invia modifiche a GitHub</h2>
          {connected === true && lastPublish && working(lastPublish) && <p role="status">Invio a GitHub in corso…</p>}
          {connected === true && lastPublish?.status === "failed" && <p role="alert" style={{color:"#b42318"}}>
            Ultimo invio non riuscito: {lastPublish.error || "controlla il log del servizio updater."}
          </p>}
          <p className="update-hint">
            Pubblica i commit verificati sul server (per esempio dal Programmatore) su un ramo <code>cora/…</code>, senza force push e
            senza toccare {github?.branch || "main"}. La pull request la apri e la unisci tu su GitHub.
          </p>
          {github?.available === false ? <p role="status" style={{color:"#965a14"}}>{github.reason}</p> :
           github?.configured === false ? <p role="status">Repository GitHub non configurata nell'updater: la pubblicazione non è disponibile.</p> :
           !github ? <p>Controllo GitHub in corso…</p> :
           !pending.length ? <p role="status">
             {github.state === "ahead" || github.state === "diverged"
               ? "Il server ha commit non su GitHub ma nessun rilascio verificato da inviare: preparali dal Programmatore."
               : "Nessuna modifica del server da inviare: tutto è già su GitHub."}
           </p> :
           pending.map(item => <div key={item.release_id} className="settings-row">
             <div>
               <strong>Commit <code>{short(item.commit)}</code>{item.active ? " · versione attiva" : " · verificato, non installato"}</strong>
               {item.published ? <p role="status">
                 Ramo <code>{item.published.branch || "cora/" + item.workspace_id}</code> inviato. Apri la pull request, uniscila con
                 un merge commit e poi aggiorna Cora dalla sezione sopra.
               </p> : <p>Non ancora inviato a GitHub.</p>}
             </div>
             <div>
               {item.published && <a className="file-tool" href={item.published.compare_url} target="_blank" rel="noopener noreferrer">
                 Apri PR su GitHub
               </a>}
               <button className="file-tool" disabled={!canAct} onClick={() => {
                 if (!window.confirm("Inviare il commit " + short(item.commit) + " a GitHub sul ramo cora/" + item.workspace_id + "? Nessun force push: se il ramo su GitHub è cambiato l'invio fallisce.")) return;
                 void invoke("/api/v1/system/update/server/publish", {
                   release_id: item.release_id, expected_commit: item.commit,
                 });
               }}>{item.published ? "Invia di nuovo" : "Invia a GitHub"}</button>
             </div>
           </div>)}
        </section>}
      </> : connected === null ? <p>Caricamento stato aggiornamenti…</p> : null}
    </section>}
  </div>;
}

function ComponentVersions({ value }: { value?: Components | null }) {
  if (value === undefined) return null;
  if (value === null) return <p role="alert" style={{color:"#965a14"}}>
    Versioni dei componenti non disponibili: l'updater host è di una versione precedente e si allineerà al prossimo aggiornamento.
  </p>;
  const stale = value.components.filter(item => item.status !== "ok");
  return <details className="updater-diagnostic" open={stale.length > 0}>
    <summary style={{color: value.aligned ? "#1f7a4d" : "#b42318", fontWeight: 600}}>
      {value.aligned ? "Tutti i componenti sono aggiornati" : stale.length + " componenti non allineati al commit installato"}
    </summary>
    {value.components.map(item => {
      const [text, color] = componentStatus[item.status] || [item.status, "#965a14"];
      return <div key={item.id} className="settings-row">
        <span>{item.label}</span>
        <span style={{color, fontWeight: 600}}>{text}</span>
        {item.status !== "ok" && <p>{item.note}{item.installed && <> Installato: <code>{short(item.installed.replace("sha256:", ""))}</code></>}{item.expected && <> · atteso: <code>{short(item.expected.replace("sha256:", ""))}</code></>}</p>}
      </div>;
    })}
  </details>;
}
