import HealthDashboard from "./HealthDashboard";
import ThinkingPanel, { type ThinkingState } from "./ThinkingPanel";
import { LengthChoice, RunTimer, type ResponseLength } from "./RunControls";
import { useEffect, useRef, useState } from "react";
import { Code2, Folder, Send, RefreshCw } from "lucide-react";
import {
  programmerApi,
  type Workspace,
  type CodeFile,
  type CodeDiff,
  type GraphStatus,
} from "../services/programmerApi";
import { api } from "../services/api";
import { runtimeRequest } from "../services/runtimeApi";

import ProgrammerArtifacts from "./ProgrammerArtifacts";
import ProgrammerReleases from "./ProgrammerReleases";
import WorkspaceEditor from "./WorkspaceEditor";
import PersonalTerminal from "./PersonalTerminal";
import WorkspaceLibrary from "./WorkspaceLibrary";
import "./programmer-v2.css";

export default function Programmer() {
  const [section, setSection] = useState("work");
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [selected, setSelected] = useState("");
  const [files, setFiles] = useState<string[]>([]),
    [file, setFile] = useState<CodeFile | null>(null);
  const [diff, setDiff] = useState<CodeDiff | null>(null),
    [graph, setGraph] = useState<GraphStatus | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>(
      [],
    ),
    [draft, setDraft] = useState("");
  const [title, setTitle] = useState("Nuovo lavoro su CORA"),
    [filter, setFilter] = useState("");
  const [model, setModel] = useState(""),
    [online, setOnline] = useState(false),
    [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false),
    [importing, setImporting] = useState(false);
  const [runId, setRunId] = useState(""),
    [state, setState] = useState(""),
    [live, setLive] = useState("");
  const [report, setReport] = useState(""),
    [error, setError] = useState(""),
    [viewDiff, setViewDiff] = useState(false);
  const [revision, setRevision] = useState(0);
  const [thinking, setThinking] = useState<ThinkingState>({text: "", truncated: false});
  const [responseLength, setResponseLength] = useState<ResponseLength>("medium");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [finishedAt, setFinishedAt] = useState<number | null>(null);
  const [graphifyAvailable, setGraphifyAvailable] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null),
    selection = useRef(""),
    mounted = useRef(true),
    fileRequest = useRef(0);

  async function connect() {
    try {
      const [status, rows] = await Promise.all([
        programmerApi.status(),
        programmerApi.workspaces(),
      ]);
      if (!mounted.current) return;
      setOnline(true);
      setModel(status.model);
      setGraphifyAvailable(status.checks.graphify_cli === true);
      setWorkspaces(rows);
      if (!selection.current) {
        let remembered = "";
        try { remembered = window.localStorage.getItem("cora.programmer.workspace") || ""; } catch { /* Storage is optional. */ }
        if (rows.some(row => row.id === remembered && !row.archived)) { setSelected(remembered); setLibraryOpen(false); }
      }
      setError("");
    } catch (e) {
      if (mounted.current) {
        setOnline(false);
        setError(String(e));
      }
    }
  }
  useEffect(() => {
    mounted.current = true;
    void connect();
    return () => {
      mounted.current = false;
      abort.current?.abort();
    };
  }, []);
  async function refresh(id: string) {
    const [listing, changes, mapping] = await Promise.all([
      programmerApi.files(id),
      programmerApi.diff(id),
      programmerApi.graph(id),
    ]);
    if (!mounted.current || selection.current !== id) return;
    setFiles(listing.files);
    setDiff(changes);
    setGraph(mapping);
    setRevision((prev) => prev + 1);
  }
  useEffect(() => {
    selection.current = selected;
    if (selected) { try { window.localStorage.setItem("cora.programmer.workspace", selected); } catch { /* Storage is optional. */ } }
    setThinking({text: "", truncated: false});
    fileRequest.current++;
    setFile(null);
    setFiles([]);
    setDiff(null);
    setGraph(null);
    setMessages([]);
    setReport("");
    setViewDiff(false);
    if (!selected) return;
    void refresh(selected).catch((e) => {
      if (selection.current === selected) setError(String(e));
    });
    void api
      .conversationMessages(selected)
      .then((rows) => {
        if (mounted.current && selection.current === selected)
          setMessages(rows.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch(() => {});
  }, [selected]);
  async function create(git = false) {
    if (creating || busy || editing !== null || !title.trim()) return;
    setCreating(true);
    setError("");
    try {
      const row = await (git
        ? programmerApi.createGit(title)
        : programmerApi.create(title));
      if (mounted.current) {
        setWorkspaces((prev) => [row, ...prev]);
        setSelected(row.id);
        setLibraryOpen(false);
      }
    } catch (e) {
      if (mounted.current) setError(String(e));
    } finally {
      if (mounted.current) setCreating(false);
    }
  }
  async function read(path: string, start = 1) {
    const id = selected,
      sequence = ++fileRequest.current;
    try {
      const value = await programmerApi.file(id, path, start);
      if (
        mounted.current &&
        selection.current === id &&
        sequence === fileRequest.current
      ) {
        setFile(value);
        setViewDiff(false);
      }
    } catch (e) {
      if (mounted.current && selection.current === id) setError(String(e));
    }
  }
  async function execute(profile?: string) {
    if (!online || busy || editing !== null || !selected || (!profile && !draft.trim())) return;
    const id = selected,
      message = draft.trim();
    setBusy(true);
    setThinking({text: "", truncated: false});
    setStartedAt(Date.now()); setFinishedAt(null);
    setError("");
    setLive("");
    setRunId("");
    setState("queued");
    abort.current = new AbortController();
    if (!profile) {
      setReport("");
      setDraft("");
      setMessages((prev) => [...prev, { role: "user", content: message }]);
    }
    try {
      const result =
        profile === "graph"
          ? await programmerApi.buildGraph(
              id,
              setRunId,
              setState,
              abort.current.signal,
            )
          : profile
            ? await programmerApi.check(
                id,
                profile,
                setRunId,
                setState,
                abort.current.signal,
              )
            : await programmerApi.run(
                id,
                message,
                setRunId,
                setLive,
                setState,
                abort.current.signal,
                responseLength,
                setThinking,
              );
      if (!mounted.current) return;
      if (profile) setReport(result.response);
      else
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: result.response },
        ]);
      setState("Terminato");
      setLive("");
      await refresh(id);
      if (file) await read(file.path, file.start_line);
    } catch (e) {
      if (mounted.current) {
        setError(String(e));
        setState("Esito da verificare in Attività");
        if (!profile) setDraft((current) => current || message);
      }
    } finally {
      if (mounted.current) setBusy(false);
      setFinishedAt(Date.now());
    }
  }
  async function stop() {
    try {
      await runtimeRequest("/runtime/runs/" + runId + "/cancel", {
        method: "POST",
      });
      setState("Arresto richiesto");
    } catch (e) {
      setError(String(e));
    }
  }
  async function importGraph(upload: File) {
    const id = selected,
      row = workspaces.find((w) => w.id === id);
    if (!row) return;
    setImporting(true);
    setError("");
    try {
      if (upload.size > 8000000) throw new Error("Grafo oltre 8 MB.");
      await programmerApi.importGraph(
        id,
        JSON.parse(await upload.text()),
        row.source_digest,
      );
      if (mounted.current && selection.current === id) await refresh(id);
    } catch (e) {
      if (mounted.current) setError(String(e));
    } finally {
      if (mounted.current) setImporting(false);
    }
  }
  async function importDraft() {
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const result = await programmerApi.importDraft(selected, file.path);
      setReport(
        "Bozza importata nella pagina Architettura → Tools. ID: " +
          result.id +
          ". Nessuna azione eseguita.",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setImporting(false);
    }
  }
  const current = workspaces.find((w) => w.id === selected);
  const hasPythonTests = files.some((path) => path.startsWith("tests/test") && path.endsWith(".py"));
  const hasFrontend = files.includes("frontend/tsconfig.json");
  const sendBlocked = !online
    ? "Backend non disponibile. Puoi preparare il messaggio; ricollega il Programmatore per inviarlo."
    : !selected
      ? "Seleziona un workspace per inviare il messaggio."
      : busy
        ? "Esecuzione in corso. Puoi preparare il prossimo messaggio."
        : editing !== null
          ? "Salva o chiudi l’editor del file prima di inviare."
          : "";
  return (
    <section className="content-page code-page programmer-v2">
      <div className="page-heading">
        <div>
          <div className="eyebrow">CORA · PROGRAMMA 2.0</div>
          <h1>Il tuo laboratorio di sviluppo</h1>
          <p>Esplora il codice, lavora con il programmatore e verifica le modifiche.</p>
        </div>
        <span className={"pill " + (online ? "" : "pending")}>
          {online ? "Backend collegato" : "Backend non disponibile"}
        </span>
      </div>
      <nav className="programmer-nav" aria-label="Sezioni Programma">
        {[['work', 'Lavoro e codice'], ['terminal', 'Terminale del server'], ['releases', 'Rilasci'], ['health', 'Diagnostica']].map(([id, label]) =>
          <button key={id} aria-pressed={section === id} disabled={editing !== null && section !== id}
            onClick={() => setSection(id)}>{label}</button>)}
      </nav>
      {section === 'terminal' && <><p className="programmer-section-note">Terminale personale. Il programmatore non può ancora utilizzare questa shell.</p><PersonalTerminal /></>}
      {error && (
        <p className="programmer-error" role="alert">
          {error}
        </p>
      )}
      <div hidden={section !== 'work'}>
      <details className="programmer-workspace-picker" open={libraryOpen} onToggle={e => setLibraryOpen(e.currentTarget.open)}>
      <summary>Libreria dei lavori <span>{workspaces.length} aree · lavori, aggiornamenti e archivio</span></summary>
      <WorkspaceLibrary rows={workspaces} selected={selected} disabled={busy || creating || importing || editing !== null}
        onSelect={id => { setSelected(id); setLibraryOpen(false); }} onUpdate={row => setWorkspaces(previous => previous.map(item => item.id === row.id ? row : item))} />
      </details>
      <details className="programmer-new-work">
      <summary>Nuovo lavoro</summary>
      <p>Git: per modificare CORA e preparare un rilascio. Snapshot: per esperimenti separati.</p>
      <div className="programmer-actions">
        <input
          aria-label="Titolo nuovo workspace"
          value={title}
          maxLength={120}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy || creating}
        />
        <button
          className="solid-button"
          disabled={!online || busy || creating || editing !== null || !title.trim()}
          onClick={() => void create()}
        >
          {creating ? "Preparazione…" : "Crea workspace"}
        </button>
        <button
          disabled={!online || busy || creating || editing !== null || !title.trim()}
          onClick={() => void create(true)}
        >
          Crea workspace Git
        </button>
        <button
          disabled={busy || creating}
          onClick={() => void connect()}
          aria-label="Ricollega programmatore"
        >
          <RefreshCw size={16} />
        </button>
      </div>
      </details>
      <div className="programmer-current" aria-live="polite">
        <div><span className="eyebrow">LAVORO IN USO</span><strong>{current?.title || 'Seleziona un lavoro o creane uno nuovo'}</strong>
          {current && <small>{current.mode === 'git' ? 'Workspace Git' : 'Snapshot'} · {current.file_count} file{current.base_commit ? ` · base ${current.base_commit.slice(0, 8)}` : ''}{current.archived ? ' · archiviato' : ''}</small>}</div>
        <span>{model || 'Modello non disponibile'}</span>
      </div>
      <div className="program-workspace">
        <div className="editor-shell">
          <aside className="editor-sidebar">
            <div className="editor-side-title">
              <Folder size={17} /> ESPLORA
            </div>
            <label className="select-label">
              AREA DI LAVORO
              <select
                aria-label="Workspace programmatore"
                value={selected}
                disabled={busy || creating || importing || editing !== null}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">Seleziona un workspace</option>
                {workspaces.filter(w => w.id === selected || (!w.archived && w.purpose !== 'update' && w.title !== 'Aggiornamento Cora dal branch main')).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.title}
                  </option>
                ))}
              </select>
            </label>
            <input
              aria-label="Filtra file"
              placeholder="Cerca un file…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            <div className="programmer-file-list">
              {files
                .filter((p) => p.toLowerCase().includes(filter.toLowerCase()))
                .map((path) => (
                  <button
                    key={path}
                    className={file?.path === path ? "selected" : ""}
                    disabled={editing !== null}
                    onClick={() => void read(path)}
                  >
                    {path}
                  </button>
                ))}
            </div>
            {current && <small>Workspace: {current.id}</small>}
          </aside>
          <div className="editor-main">
            <div className="editor-tabs">
              <button disabled={!selected || busy || importing || editing !== null} onClick={() => setEditing("")}>Nuovo file</button>
              <button disabled={!file || busy || importing || editing !== null} onClick={() => setEditing(file!.path)}>Modifica file</button>
              <span>
                <Code2 size={15} />
                {viewDiff
                  ? "Modifiche"
                  : file?.path || "Sorgente dello snapshot"}
              </span>
              <button
                disabled={!selected || editing !== null}
                onClick={() => setViewDiff(!viewDiff)}
              >
                {diff?.total_changes || 0} modifiche
              </button>
            </div>
            <div className="code-surface programmer-code">
              {editing !== null ? <WorkspaceEditor workspace={selected} path={editing} onClose={() => setEditing(null)} onSaved={async path => { await refresh(selected); await read(path); }} /> : viewDiff ? (
                <>
                  {diff?.changes.length ? (
                    diff.changes.map((c) => (
                      <div key={c.path}>
                        <strong>
                          {c.kind} · {c.path}
                        </strong>
                        <pre>{c.patch}</pre>
                        {c.truncated && <small>Diff abbreviato.</small>}
                      </div>
                    ))
                  ) : (
                    <p>Nessuna modifica rispetto allo snapshot.</p>
                  )}
                </>
              ) : file ? (
                <>
                  <pre>{file.content}</pre>
                  <div className="programmer-pagination">
                    <button
                      disabled={file.start_line === 1}
                      onClick={() =>
                        void read(file.path, Math.max(1, file.start_line - 120))
                      }
                    >
                      Precedenti
                    </button>
                    <small>
                      Da riga {file.start_line} · {file.total_lines} righe
                      totali
                    </small>
                    <button
                      disabled={file.start_line + 120 > file.total_lines}
                      onClick={() =>
                        void read(file.path, file.start_line + 120)
                      }
                    >
                      Successive
                    </button>
                  </div>
                </>
              ) : (
                <p className="empty-files">
                  {selected ? 'Apri un file dall’elenco per esplorare il codice del lavoro in uso.' : 'Crea o seleziona un lavoro e apri un file. Il programmatore lavorerà sulla sua copia.'}
                </p>
              )}
            </div>
            <details className="editor-terminal">
              <summary className="terminal-title">Verifiche e mappa del codice</summary>
              <div className="programmer-actions">
                <button
                  disabled={!selected || busy || importing || editing !== null}
                  onClick={() => void execute("syntax")}
                >
                  Verifica sintassi
                </button>
                <button
                  disabled={!selected || busy || importing || editing !== null}
                  onClick={() => void execute("contracts")}
                >
                  Verifica contratti
                </button>
                <button
                  disabled={!selected || busy || importing || editing !== null || !hasFrontend}
                  title={hasFrontend ? undefined : "Richiede frontend/tsconfig.json nel workspace."}
                  onClick={() => void execute("typescript")}
                >
                  Verifica TypeScript
                </button>
                <button
                  disabled={!selected || busy || importing || editing !== null || !hasFrontend}
                  title={hasFrontend ? undefined : "Richiede frontend/tsconfig.json nel workspace."}
                  onClick={() => void execute("frontend_build")}
                >
                  Build frontend Docker
                </button>
                <button
                  disabled={!selected || busy || importing || editing !== null || !hasPythonTests}
                  title={hasPythonTests ? undefined : "Richiede almeno un file tests/test*.py nel workspace."}
                  onClick={() => void execute("python_tests")}
                >
                  Test Docker
                </button>
                {file?.path.endsWith(".json") && (
                  <button
                    disabled={busy || importing || editing !== null}
                    onClick={() => void importDraft()}
                  >
                    Importa bozza in Tools
                  </button>
                )}
              </div>
              {selected && !hasPythonTests && <p>I test Docker richiedono almeno un file <code>tests/test*.py</code>. Il solo <code>tests/__init__.py</code> non contiene test eseguibili.</p>}
              {selected && !hasFrontend && <p>Le verifiche frontend non si applicano a questa bozza: manca <code>frontend/tsconfig.json</code>.</p>}
              <button
                disabled={!selected || busy || importing || editing !== null || !graphifyAvailable}
                onClick={() => void execute("graph")}
              >
                Costruisci mappa Graphify
              </button>
              {!graphifyAvailable && <p>Graphify non risulta installato nel backend. La mappa non è necessaria per creare la funzione e provarne i test.</p>}
              <p>
                Graphify:{" "}
                {graph?.available
                  ? `${graph.nodes} nodi · ${graph.edges} collegamenti${graph.stale ? " · mappa dello snapshot, codice modificato" : ""}`
                  : "grafo non importato"}
              </p>
              <label className="programmer-upload">
                Importa graph.json dello snapshot
                <input
                  type="file"
                  accept=".json"
                  disabled={!selected || busy || importing || editing !== null}
                  onChange={(e) => {
                    const upload = e.target.files?.[0];
                    if (upload) void importGraph(upload);
                    e.target.value = "";
                  }}
                />
              </label>
              {report && <pre className="programmer-report">{report}</pre>}
            </details>
          </div>
        </div>
        <aside className="copilot-panel" aria-label="Copilot">
          <div className="copilot-head">
            <div>
              <div className="eyebrow">COPILOT</div>
              <h2>Agente programmatore</h2>
            </div>
            <span className="pill">{busy ? state : "Bozze"}</span>
          </div>
          <div className="copilot-body" aria-live="polite">
            {!messages.length && (
              <div className="copilot-empty">
                <div className="message-avatar">✦</div>
                <strong>Da cosa iniziamo?</strong>
                <p>
                  Chiedimi di esplorare il codice, analizzare un problema o preparare una modifica nel lavoro selezionato.
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={"programmer-message " + m.role}>
                <strong>{m.role === "user" ? "Tu" : "Programmatore"}</strong>
                <p>{m.content}</p>
              </div>
            ))}
            {busy && (
              <div className="programmer-message">
                <strong>{state}</strong>
                <p>{live || "Lavoro in corso…"}</p>
              </div>
            )}
          </div>
          <ThinkingPanel value={thinking} />
          <RunTimer started={startedAt} finished={finishedAt} />
                <LengthChoice value={responseLength} onChange={setResponseLength} disabled={busy} />
                <div className="copilot-composer">
            <textarea
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Cosa vuoi capire, correggere o costruire?"
              aria-label="Messaggio al Copilot"
              aria-describedby={sendBlocked ? "copilot-send-status" : undefined}
            />
            <button
              disabled={!online || !selected || busy || editing !== null || !draft.trim()}
              onClick={() => void execute()}
              aria-label="Invia messaggio al Copilot"
              title={sendBlocked || "Invia messaggio al Copilot"}
            >
              <Send size={16} />
            </button>
          </div>
          {sendBlocked && <small id="copilot-send-status">{sendBlocked}</small>}
          {runId && <small>ID esecuzione: <code>{runId}</code></small>}
          {busy && runId && (
            <button disabled={state === "Arresto richiesto"} onClick={() => void stop()}>Annulla esecuzione</button>
          )}
          <small>
            {model || "Modello locale"} · skill e strumenti Cora · nessuna
            attivazione automatica
          </small>
        </aside>
      </div>
      <details className="programmer-context-help"><summary>Workspace e contesto: cosa vede il programmatore?</summary>
        <p>Ogni lavoro contiene una copia del codice e una propria conversazione. Gli altri workspace non vengono caricati automaticamente nel contesto.
          Continuare nello stesso lavoro conserva la sua chat. Dopo un aggiornamento di CORA, crea un nuovo workspace Git per lavorare sulla nuova base.
          Archiviare riordina l’elenco senza cancellare nulla e non svuota la memoria della conversazione.</p>
      </details>
      <details className="programmer-deliveries"><summary>Componenti, consegne e grafo</summary>
      <ProgrammerArtifacts workspaceId={selected} revision={revision} disabled={busy || importing || creating || editing !== null} />
      </details>
      </div>
      <div hidden={section !== 'releases'}>
      <p className="programmer-section-note">Rilasci del lavoro selezionato: <strong>{current?.title || 'nessun lavoro selezionato'}</strong>. La cronologia delle copie automatiche è in Lavoro e codice → Aggiornamenti.</p>
      <ProgrammerReleases
        workspaceId={selected}
        gitWorkspace={current?.mode === "git"}
        disabled={busy || creating || importing || editing !== null}
        onRefresh={() => {
          void connect();
          if (selected)
            void refresh(selected).catch((e) => setError(String(e)));
        }}
      />
      </div>
      {section === 'health' && <HealthDashboard componentFilter={["cora","worker"]} compact />}
    </section>
  );
}
