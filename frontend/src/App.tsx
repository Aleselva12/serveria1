import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  CalendarDays,
  ChevronDown,
  Code2,
  FileText,
  Folder,
  Menu,
  Mic,
  Paperclip,
  Plus,
  RefreshCw,
  Send,
  Settings,
  Save,
} from "lucide-react";
import Home from "./components/Home";
import FileManager from "./components/FileManager";
import Architecture from "./components/Architecture";
import ConnectionNotice from "./components/ConnectionNotice";
import MemoryManagement from "./components/MemoryManagement";
import { api, apiBaseUrl } from "./services/api";
import { useBackend } from "./services/useBackend";
import { useConversations } from "./services/useConversations";

type Page =
  | "home"
  | "chat"
  | "architecture"
  | "code"
  | "calendar"
  | "files"
  | "activity"
  | "settings"
  | "memory-management";
type RequestActivity = {
  id: string;
  title: string;
  startedAt: string;
  status: "running" | "completed" | "failed";
};
const primary: { id: Page; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "chat", label: "Chat" },
  { id: "architecture", label: "Architettura" },
  { id: "code", label: "Programma" },
  { id: "calendar", label: "Calendario" },
];
const secondary: { id: Page; label: string; icon: typeof FileText }[] = [
  { id: "activity", label: "Attività", icon: Activity },
  { id: "settings", label: "Impostazioni", icon: Settings },
];
const labels: Record<Page, string> = {
  home: "Home",
  chat: "Chat",
  architecture: "Architettura",
  code: "Programma",
  calendar: "Calendario",
  files: "File",
  activity: "Attività",
  settings: "Impostazioni",
  "memory-management": "Gestione Memoria",
};
const uid = () => crypto.randomUUID();
export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [menu, setMenu] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const sendLock = useRef(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const [activity, setActivity] = useState<RequestActivity[]>([]);
  const [selectedNode, setSelectedNode] = useState("supervisor");
  const [permanentContext, setPermanentContext] = useState("");
  const [contextUpdatedAt, setContextUpdatedAt] = useState<string | null>(null);
  const [contextVersion, setContextVersion] = useState<number | null>(null);
  const [contextSaving, setContextSaving] = useState(false);
  const [contextError, setContextError] = useState("");
  const [selectedMonth, setSelectedMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const backend = useBackend();
  const history = useConversations(Boolean(backend.health), sending);
  const { chats, setChats, currentChat } = history;
  useEffect(() => {
    if (page === "chat" && !history.messagesLoading)
      messagesEnd.current?.scrollIntoView({ block: "end" });
  }, [page, currentChat.id, currentChat.messages.length, history.messagesLoading, sending]);

  useEffect(() => {
    if (!backend.health) return;
    let cancelled = false;
    void api
      .systemContext()
      .then((context) => {
        if (cancelled) return;
        setPermanentContext(context.content);
        setContextUpdatedAt(context.updated_at);
        setContextVersion(context.version);
        setContextError("");
      })
      .catch((error) => {
        if (!cancelled)
          setContextError(
            error instanceof Error ? error.message : "Contesto non disponibile.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [backend.health]);

  async function savePermanentContext() {
    if (contextSaving) return;
    setContextSaving(true);
    setContextError("");
    try {
      const saved = await api.saveSystemContext(permanentContext);
      setPermanentContext(saved.content);
      setContextUpdatedAt(saved.updated_at);
      setContextVersion(saved.version);
    } catch (error) {
      setContextError(
        error instanceof Error ? error.message : "Salvataggio non riuscito.",
      );
    } finally {
      setContextSaving(false);
    }
  }

  const statusLabel = backend.health
    ? "Backend collegato"
    : backend.checking
      ? "Connessione…"
      : "Collegamento non riuscito";
  function navigate(next: Page) {
    setPage(next);
    setMenu(false);
  }
  function newChat() {
    if (sendLock.current) return;
    history.newChat();
    setDraft("");
    setChatError("");
    navigate("chat");
  }
  async function send() {
    const content = draft.trim();
    if (!content || sendLock.current || history.messagesLoading || history.historyLoading || history.messagesError || !backend.health?.ollama_online) return;
    sendLock.current = true;
    setSending(true);
    setChatError("");
    setDraft("");
    const conversationId = currentChat.id,
      threadId = currentChat.threadId,
      requestId = uid(),
      userId = uid(),
      createdAt = new Date().toISOString();
    setChats((prev) =>
      prev.map((c) =>
        c.id === conversationId
          ? {
              ...c,
              title: c.messages.length ? c.title : content.slice(0, 55),
              messages: [
                ...c.messages,
                {
                  id: userId,
                  conversationId,
                  role: "user",
                  content,
                  createdAt,
                },
              ],
            }
          : c,
      ),
    );
    setActivity((prev) => [
      {
        id: requestId,
        title: content.slice(0, 80),
        startedAt: createdAt,
        status: "running",
      },
      ...prev,
    ]);
    try {
      const result = await api.chat(content, threadId);
      setChats((prev) =>
        prev.map((c) =>
          c.id === conversationId
            ? {
                ...c,
                threadId: result.thread_id,
                persisted: true,
                messages: [
                  ...c.messages,
                  {
                    id: uid(),
                    conversationId,
                    role: "assistant",
                    content: result.response,
                    createdAt: new Date().toISOString(),
                  },
                ],
              }
            : c,
        ),
      );
      setActivity((prev) =>
        prev.map((a) =>
          a.id === requestId ? { ...a, status: "completed" } : a,
        ),
      );
    } catch (error) {
      setChatError(
        error instanceof Error ? error.message : "Collegamento non riuscito.",
      );
      setChats((prev) =>
        prev.map((c) =>
          c.id === conversationId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === userId ? { ...m, failed: true } : m,
                ),
              }
            : c,
        ),
      );
      setActivity((prev) =>
        prev.map((a) => (a.id === requestId ? { ...a, status: "failed" } : a)),
      );
      setDraft((prev) => prev || content);
    } finally {
      sendLock.current = false;
      setSending(false);
      void history.refreshHistory();
    }
  }
  const withSidebar = page !== "home" && page !== "files";
  const monthTitle = new Intl.DateTimeFormat("it-IT", {
    month: "long",
    year: "numeric",
  }).format(selectedMonth);
  return (
    <div
      className={"app app-" + page + " " + (withSidebar ? "has-sidebar" : "")}
    >
      {withSidebar && (
        <aside className="global-sidebar">
          <div className="sidebar-top">
            <button
              className="sidebar-new"
              disabled={sending}
              onClick={newChat}
            >
              <span>✧</span> Nuova chat
            </button>
            <div className="sidebar-caption">
              CONVERSAZIONI · STORICO
            </div>
            <button className="sidebar-history" disabled={sending || history.historyLoading}
              onClick={() => void history.refreshHistory()}>
              <RefreshCw size={14} /> {history.historyLoading ? "Caricamento…" : "Aggiorna storico"}
            </button>
            {history.historyError && <div className="sidebar-history-error" role="alert">{history.historyError}</div>}
            {chats.filter(c => !c.persisted).length > 0 && <small className="sidebar-history-note">Le nuove chat vengono salvate al primo messaggio.</small>}
            {chats.map((chat) => (
              <button
                key={chat.id}
                disabled={sending}
                className={
                  "sidebar-history " +
                  (chat.id === currentChat.id ? "active" : "")
                }
                onClick={() => {
                  history.selectChat(chat.id);
                  setDraft("");
                  setChatError("");
                  navigate("chat");
                }}
              >
                ◯ &nbsp; {chat.title}
              </button>
            ))}
          </div>
          <div className="sidebar-bottom">
            <div className="sidebar-server">
              ✧{" "}
              <span>
                Console del server<small>{statusLabel}</small>
              </span>
            </div>
            <button onClick={() => navigate("settings")}>
              <span className="sidebar-avatar">AS</span> Alessandro{" "}
              <Settings size={16} />
            </button>
          </div>
        </aside>
      )}
      <div className="app-shell">
        <header className="topbar">
          <nav className="primary-nav" aria-label="Navigazione principale">
            {primary.map((item) => (
              <button
                key={item.id}
                onClick={() => navigate(item.id)}
                className={page === item.id ? "active" : ""}
              >
                {item.label}
              </button>
            ))}
            <button
              onClick={() => navigate("files")}
              className={page === "files" ? "active" : ""}
            >
              File
            </button>
          </nav>
          <div className="header-right">
            <span
              className={
                "connection-tag " + (backend.health ? "online" : "offline")
              }
            >
              ● {statusLabel}
            </span>
            <div className="more-wrap">
              <button
                className={
                  "more-button " +
                  (secondary.some((x) => x.id === page) ? "active" : "")
                }
                onClick={() => setMenu(!menu)}
                aria-expanded={menu}
              >
                <Menu size={18} />
                <span>Altro</span>
                <ChevronDown size={14} />
              </button>
              {menu && (
                <div className="dropdown">
                  {secondary.map((item) => (
                    <button key={item.id} onClick={() => navigate(item.id)}>
                      <item.icon size={17} />
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </header>
        <main className={"main " + (page === "chat" ? "chat-main" : "")}>
          {backend.error && (
            <div className="connection-error" role="alert">
              <span>{backend.error}</span>
              <button
                disabled={backend.checking}
                onClick={() => void backend.refresh()}
              >
                <RefreshCw size={14} /> Riprova
              </button>
            </div>
          )}
          {page === "home" && (
            <Home
              health={backend.health}
              checking={backend.checking}
              checkedAt={backend.checkedAt}
            />
          )}
          {page === "chat" && (
            <section className="chat-page">
              <div className="messages" aria-live="polite">
                {history.messagesLoading && <p role="status">Caricamento dei messaggi…</p>}
                {history.messagesError && <div className="connection-error" role="alert">
                  {history.messagesError}
                  <button disabled={history.messagesLoading} onClick={() => history.selectChat(currentChat.id)}>Riprova</button>
                </div>}
                {!history.messagesLoading && !history.messagesError && currentChat.messages.length === 0 && (
                  <div className="chat-welcome">
                    <h1>Una conversazione con Cora.</h1>
                    <p>Scrivi una richiesta all’agente centrale di Cora.</p>
                  </div>
                )}
                {currentChat.messages.map((m) => (
                  <div key={m.id} className={"message " + m.role}>
                    <div className="message-avatar">
                      {m.role === "assistant" ? "✦" : m.role === "system" ? "S" : "A"}
                    </div>
                    <div className="message-content">
                      {m.content}
                      {m.failed && (
                        <small className="message-failed">
                          Esito della richiesta non confermato
                        </small>
                      )}
                    </div>
                  </div>
                ))}
                {sending && (
                  <div className="message assistant">
                    <div className="message-avatar">✦</div>
                    <div className="message-content" role="status">
                      Cora sta elaborando la richiesta…
                    </div>
                  </div>
                )}
                <div ref={messagesEnd} />
              </div>
              <div className="chat-bottom">
                {chatError && (
                  <div className="connection-error" role="alert">
                    {chatError}
                  </div>
                )}
                <div className="composer">
                  <button
                    disabled
                    title="Allegati: collegamento da realizzare"
                    aria-label="Allega file · da collegare"
                  >
                    <Paperclip size={19} />
                  </button>
                  <textarea
                    disabled={history.historyLoading || history.messagesLoading}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        void send();
                      }
                    }}
                    placeholder="Scrivi a Cora…"
                    aria-label="Messaggio a Cora"
                    rows={1}
                  />
                  <button
                    disabled
                    title="Microfono: collegamento da realizzare"
                    aria-label="Microfono · da collegare"
                  >
                    <Mic size={18} />
                  </button>
                  <button
                    className="send-button"
                    disabled={
                      sending || history.messagesLoading || history.historyLoading || Boolean(history.messagesError) || !backend.health?.ollama_online || !draft.trim()
                    }
                    title="Invia messaggio"
                    aria-label="Invia messaggio"
                    onClick={() => void send()}
                  >
                    <Send size={17} />
                  </button>
                </div>
                <p>
                  {backend.health
                    ? backend.health.ollama_online
                      ? "Chat collegata all’agente centrale · Orchestratore provvisorio · Modello " +
                        backend.health.model
                      : "Ollama offline: avvia il modello locale per inviare messaggi."
                    : "Backend non collegato"}
                </p>
                <p>Storico salvato sul server · ultime 500 conversazioni, fino a 2.000 messaggi per chat.</p>
                <div className="composer-notes">
                  <span>Allegati · da collegare</span>
                  <span>Microfono · da collegare</span>
                  <span>Risposta progressiva · da collegare</span>
                </div>
              </div>
            </section>
          )}
          {page === "architecture" && (
            <>
              <Architecture
                registry={backend.registry}
                health={backend.health}
                selectedNode={selectedNode}
                onSelect={setSelectedNode}
              />
              {backend.registryError && (
                <div className="connection-error" role="alert">
                  {backend.registryError}
                </div>
              )}
            </>
          )}
          {page === "code" && (
            <section className="content-page code-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">SPAZIO DI CODING</div>
                  <h1>Programma</h1>
                  <p>Codice di Cora e progetti separati.</p>
                </div>
                <span className="pill pending">Da collegare</span>
              </div>
              <ConnectionNotice feature="code" />
              <div className="editor-shell">
                <aside className="editor-sidebar">
                  <div className="editor-side-title">
                    <Folder size={17} /> ESPLORA
                  </div>
                  <label className="select-label">
                    AREA DI LAVORO
                    <select disabled>
                      <option>Workspace da collegare</option>
                    </select>
                  </label>
                  <div className="folder-row">
                    <Folder size={17} /> Nessun file caricato
                  </div>
                </aside>
                <div className="editor-main">
                  <div className="editor-tabs">
                    <span>
                      <Code2 size={15} /> Editor da collegare
                    </span>
                    <button disabled>Salva · da collegare</button>
                  </div>
                  <div className="code-surface">
                    <p className="empty-files">
                      Il contenuto apparirà dopo il collegamento ai workspace
                      autorizzati.
                    </p>
                  </div>
                  <div className="editor-terminal">
                    <div className="terminal-title">OUTPUT</div>
                    <p>Esecuzione da collegare.</p>
                    <button className="solid-button" disabled>
                      Esegui · da collegare
                    </button>
                  </div>
                </div>
              </div>
            </section>
          )}
          {page === "calendar" && (
            <section className="content-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ORGANIZZA IL TEMPO</div>
                  <h1>Calendario</h1>
                  <p>Spazio personale gestito dall’utente.</p>
                </div>
                <span className="pill pending">Da collegare</span>
              </div>
              <ConnectionNotice feature="calendar" />
              <div className="calendar-layout">
                <div className="section-card calendar-card">
                  <div className="calendar-toolbar">
                    <button
                      aria-label="Mese precedente"
                      onClick={() =>
                        setSelectedMonth(
                          new Date(
                            selectedMonth.getFullYear(),
                            selectedMonth.getMonth() - 1,
                            1,
                          ),
                        )
                      }
                    >
                      ←
                    </button>
                    <h2>{monthTitle}</h2>
                    <button
                      aria-label="Mese successivo"
                      onClick={() =>
                        setSelectedMonth(
                          new Date(
                            selectedMonth.getFullYear(),
                            selectedMonth.getMonth() + 1,
                            1,
                          ),
                        )
                      }
                    >
                      →
                    </button>
                  </div>
                  <div className="calendar-grid">
                    {["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"].map(
                      (d) => (
                        <strong key={d}>{d}</strong>
                      ),
                    )}
                    {Array.from(
                      {
                        length:
                          (new Date(
                            selectedMonth.getFullYear(),
                            selectedMonth.getMonth(),
                            1,
                          ).getDay() +
                            6) %
                          7,
                      },
                      (_, i) => (
                        <span key={"empty-" + i} className="empty" />
                      ),
                    )}
                    {Array.from(
                      {
                        length: new Date(
                          selectedMonth.getFullYear(),
                          selectedMonth.getMonth() + 1,
                          0,
                        ).getDate(),
                      },
                      (_, i) => (
                        <div className="calendar-day" key={i}>
                          <span>{i + 1}</span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
                <aside className="side-panel calendar-side">
                  <div className="eyebrow">NUOVO EVENTO · DA COLLEGARE</div>
                  <label>
                    Titolo
                    <input disabled placeholder="Collegamento da realizzare" />
                  </label>
                  <label>
                    Data e ora
                    <input disabled type="datetime-local" />
                  </label>
                  <button className="solid-button" disabled>
                    <Plus size={16} /> Aggiungi evento
                  </button>
                  <div className="panel-note">
                    <CalendarDays size={17} />
                    Gli eventi del server non sono ancora disponibili.
                  </div>
                </aside>
              </div>
            </section>
          )}
          {page === "files" && <FileManager />}
          {page === "activity" && (
            <section className="content-page narrow">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">TRASPARENZA</div>
                  <h1>Attività</h1>
                  <p>Richieste inviate dalla chat in questa sessione.</p>
                </div>
              </div>
              <div className="section-card">
                <h2>Richieste della sessione</h2>
                {activity.length === 0 ? (
                  <p className="muted">
                    Nessuna richiesta inviata da questa pagina.
                  </p>
                ) : (
                  activity.map((a) => (
                    <div className="settings-row" key={a.id}>
                      <div>
                        <strong>{a.title}</strong>
                        <p>{new Date(a.startedAt).toLocaleString("it-IT")}</p>
                      </div>
                      <span
                        className={
                          "pill " + (a.status === "completed" ? "success" : "")
                        }
                      >
                        {a.status === "completed"
                          ? "Risposta ricevuta"
                          : a.status === "running"
                            ? "In corso"
                            : "Esito non confermato"}
                      </span>
                    </div>
                  ))
                )}
                <button
                  className="text-button"
                  onClick={() => navigate("architecture")}
                >
                  Apri la mappa <ArrowRight size={16} />
                </button>
              </div>
              <ConnectionNotice feature="runs" />
            </section>
          )}
          {page === "memory-management" && (
            <MemoryManagement
              registry={backend.registry}
              onBack={() => navigate("settings")}
            />
          )}
          {page === "settings" && (
            <section className="content-page narrow">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">PREFERENZE</div>
                  <h1>Impostazioni</h1>
                  <p>Connessione e parametri reali del sistema.</p>
                </div>
                <button
                  className="solid-button"
                  disabled={backend.checking}
                  onClick={() => void backend.refresh()}
                >
                  <RefreshCw size={15} /> Aggiorna stato
                </button>
              </div>
              <div className="section-card">
                <h2>Connessione reale</h2>
                <div className="settings-row">
                  <div>
                    <strong>Backend Cora</strong>
                    <p>
                      {apiBaseUrl === "/backend"
                        ? "Proxy locale verso FastAPI"
                        : apiBaseUrl}
                    </p>
                  </div>
                  <span className={"pill " + (backend.health ? "success" : "")}>
                    {statusLabel}
                  </span>
                </div>
                <div className="settings-row">
                  <div>
                    <strong>Modello dell’agente centrale</strong>
                    <p>{backend.health?.model || "Non disponibile"}</p>
                  </div>
                  <span className="pill">
                    {backend.health
                      ? backend.health.ollama_online
                        ? "Ollama raggiungibile"
                        : "Ollama offline"
                      : "Non verificato"}
                  </span>
                </div>
                <div className="settings-row">
                  <div>
                    <strong>Registro dei componenti</strong>
                    <p>
                      {backend.registry
                        ? backend.registry.component_count +
                          " componenti dichiarati dal backend"
                        : backend.registryError || "In attesa di connessione"}
                    </p>
                  </div>
                </div>
                <div className="settings-memory-context">
                  <div className="settings-memory-head">
                    <div>
                      <strong>Contesto permanente di Cora</strong>
                      <p>
                        Informazioni fondamentali che Cora riceverà all’inizio di
                        ogni conversazione e che non verranno modificate
                        automaticamente.
                      </p>
                    </div>
                    <span className={"pill " + (contextUpdatedAt ? "success" : "pending")}>
                      {contextUpdatedAt ? "Collegato" : "Non caricato"}
                    </span>
                  </div>
                  <textarea
                    value={permanentContext}
                    onChange={(event) => setPermanentContext(event.target.value)}
                    rows={7}
                    placeholder="Scrivi poche frasi base comuni a Cora e agli agenti…"
                  />
                  {contextError && (
                    <div className="connection-error">{contextError}</div>
                  )}
                  <div className="settings-memory-actions">
                    <small>
                      {contextUpdatedAt
                        ? "Ultima modifica: " +
                          new Date(contextUpdatedAt).toLocaleString("it-IT") +
                          (contextVersion ? " · versione " + contextVersion : "")
                        : "Contesto non ancora caricato"}
                    </small>
                    <button
                      className="solid-button"
                      disabled={!backend.health || contextSaving}
                      onClick={() => void savePermanentContext()}
                    >
                      <Save size={15} />{" "}
                      {contextSaving ? "Salvataggio…" : "Salva modifiche"}
                    </button>
                  </div>
                </div>

                <div className="settings-memory-summary">
                  <div className="eyebrow">MEMORIA</div>
                  <div className="settings-row compact">
                    <span>Memorie persistenti</span>
                    <strong>{backend.health?.memory?.total ?? 0}</strong>
                  </div>
                  <div className="settings-row compact">
                    <span>Contesto permanente</span>
                    <strong>{permanentContext.trim() ? "Configurato" : "Vuoto"}</strong>
                  </div>
                  <div className="settings-row compact">
                    <span>Motore di recupero</span>
                    <strong>
                      {backend.health?.memory?.available === false
                        ? "Non disponibile"
                        : "PostgreSQL + pgvector"}
                    </strong>
                  </div>
                </div>
                <div className="settings-row">
                  <div>
                    <strong>Gestione Memoria</strong>
                    <p>
                      Organizzazione, consultazione e gestione della memoria di Cora.
                    </p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => navigate("memory-management")}
                  >
                    Apri <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            </section>
          )}
        </main>
      </div>
      <div className="mobile-nav">
        {[...primary, { id: "files" as Page, label: "File" }, ...secondary].map(
          (item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => navigate(item.id)}
            >
              {labels[item.id]}
            </button>
          ),
        )}
      </div>
    </div>
  );
}

