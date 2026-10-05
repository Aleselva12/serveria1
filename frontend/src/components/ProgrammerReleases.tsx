import { useEffect, useRef, useState } from "react";
import {
  programmerReleaseApi,
  type ReleaseJob,
} from "../services/programmerApi";
export default function ProgrammerReleases({
  workspaceId,
  gitWorkspace,
  disabled,
  onRefresh,
}: {
  workspaceId: string;
  gitWorkspace: boolean;
  disabled: boolean;
  onRefresh: () => void;
}) {
  const [available, setAvailable] = useState(false),
    [active, setActive] = useState(""),
    [jobs, setJobs] = useState<ReleaseJob[]>([]);
  const [selected, setSelected] = useState(""),
    [commit, setCommit] = useState(""),
    [message, setMessage] = useState("Modifica richiesta dall’utente");
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const mounted = useRef(true),
    current = useRef(workspaceId);
  current.current = workspaceId;
  async function refresh() {
    try {
      const value = await programmerReleaseApi.status();
      if (!mounted.current) return;
      setAvailable(value.available);
      setActive(value.active_commit || "");
      setJobs(value.jobs);
      if (value.reason) setNotice(value.reason);
      else setNotice("");
      setError("");
    } catch (e) {
      if (mounted.current)
        setError(
          "Aggiornamenti non raggiungibili. Se Cora si sta riavviando, lo stato verrà recuperato automaticamente. " +
            String(e),
        );
    }
  }
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    setSelected("");
    setCommit("");
    setConfirmed(false);
  }, [workspaceId]);
  const rows = jobs.filter((job) => job.workspace_id === workspaceId),
    release = rows.find((job) => job.id === selected);
  const running = jobs.some((job) =>
    ["queued", "running", "recovery_required"].includes(job.status),
  );
  async function action(operation: () => Promise<unknown>) {
    if (busy || disabled || running) return;
    const id = workspaceId;
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh();
      if (current.current === id) onRefresh();
    } catch (e) {
      if (mounted.current) setError(String(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  const locked =
    disabled || busy || running || !available || !workspaceId || !gitWorkspace;
  return (
    <section
      className="system-card programmer-release-panel"
      aria-label="Aggiornamenti richiesti"
    >
      <h2>Aggiornamento di Cora</h2>
      <p>
        Salva un commit, prepara e verifica le immagini, poi richiedi
        l’applicazione.
      </p>
      {notice && <p>{notice}</p>}
      {error && (
        <p role="alert" className="programmer-error">
          {error}
        </p>
      )}
      {active && (
        <p>
          Versione attiva: <code>{active}</code>
        </p>
      )}
      {!gitWorkspace && (
        <p>
          Per aggiornare il programma crea un workspace Git dal pulsante in
          alto. Gli snapshot restano utilizzabili per le bozze.
        </p>
      )}
      <div className="programmer-actions">
        <input
          aria-label="Messaggio commit Git"
          maxLength={200}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={locked}
        />
        <button
          disabled={locked || !message.trim()}
          onClick={() =>
            void action(async () => {
              const result = await programmerReleaseApi.commit(
                workspaceId,
                message,
              );
              if (current.current === workspaceId) setCommit(result.commit);
            })
          }
        >
          Salva commit Git
        </button>
        <button
          disabled={locked || !commit}
          onClick={() =>
            void action(async () => {
              const row = await programmerReleaseApi.prepare(
                workspaceId,
                commit,
              );
              if (current.current === workspaceId) {
                setSelected(row.id);
                setConfirmed(false);
              }
            })
          }
        >
          Prepara rilascio
        </button>
      </div>
      {commit && (
        <p>
          Commit selezionato: <code>{commit}</code>
        </p>
      )}
      <label>
        Rilascio
        <select
          aria-label="Rilascio selezionato"
          value={selected}
          disabled={busy}
          onChange={(e) => {
            setSelected(e.target.value);
            setConfirmed(false);
          }}
        >
          <option value="">Seleziona un job</option>
          {rows.map((job) => (
            <option key={job.id} value={job.id}>
              {job.kind} · {job.commit.slice(0, 8)} · {job.status}
            </option>
          ))}
        </select>
      </label>
      {release && (
        <div>
          <p>
            <strong>
              {release.status} · {release.phase}
            </strong>
          </p>
          <p>
            Commit: <code>{release.commit}</code>
          </p>
          {release.error && <p role="alert">{release.error}</p>}
          {release.compare_url && <p><a href={release.compare_url} target="_blank" rel="noreferrer">Apri confronto e crea PR su GitHub</a></p>}
          {release.kind === "prepare" && ["ready", "applied", "rolled_back"].includes(release.status) && (
            <button disabled={locked} onClick={() => void action(async () => {
              const result = await programmerReleaseApi.apply(workspaceId, release, "publish");
              setSelected(result.id); setConfirmed(false);
            })}>Pubblica branch su GitHub</button>
          )}
          {release.rollback && <p>Recupero: {release.rollback}</p>}
          {release.kind === "prepare" &&
            ["ready", "applied"].includes(release.status) && (
              <>
                <label className="programmer-release-confirm">
                  <input
                    type="checkbox"
                    aria-label="Conferma operazione sul rilascio"
                    checked={confirmed}
                    disabled={locked}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  {release.status === "ready"
                    ? "Richiedo l’applicazione di questo commit e il riavvio di Cora."
                    : "Richiedo il ripristino di codice e dati al backup precedente. Le modifiche successive saranno conservate in un backup separato."}
                </label>
                <button
                  disabled={locked || !confirmed}
                  onClick={() =>
                    void action(async () => {
                      const result = await programmerReleaseApi.apply(
                        workspaceId,
                        release,
                        release.status === "ready" ? "apply" : "rollback",
                      );
                      setSelected(result.id);
                      setConfirmed(false);
                    })
                  }
                >
                  {release.status === "ready"
                    ? "Applica e riavvia Cora"
                    : "Ripristina versione e dati precedenti"}
                </button>
              </>
            )}
        </div>
      )}
      {rows.length > 0 && (
        <ul>
          {rows.slice(0, 8).map((job) => (
            <li key={job.id}>
              {job.kind} · {job.status} · {job.phase} · {job.commit.slice(0, 8)}
            </li>
          ))}
        </ul>
      )}
      <small>
        Il lavoro prosegue sul server anche se chiudi questa pagina. Durante il
        riavvio la connessione può interrompersi; al ritorno viene recuperato lo
        stato. Dopo un aggiornamento frontend ricarica la pagina.
      </small>
    </section>
  );
}
