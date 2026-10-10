import { usePermanentContext } from "./services/usePermanentContext";
import { streamChat, runtimeRequest } from "./services/runtimeApi";
import { authenticatedFetch } from "./services/transport";
import RuntimePanel from "./components/RuntimePanel";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ChevronDown,
  FileText,
  Menu,
  Paperclip,
  RefreshCw,
  Send,
  Settings,
  Save,
} from "lucide-react";
import Audio from "./components/Audio";
import ChatToolPicker from "./components/ChatToolPicker";
import { uploadAttachment, type Attachment } from "./services/mediaApi";
import Home from "./components/Home";
import Programmer from "./components/Programmer";
import Calendar from "./components/Calendar";
import FileManager from "./components/FileManager";
import Architecture from "./components/Architecture";
import ArchitectureRuntime from "./components/ArchitectureRuntime";
import MemoryManagement from "./components/MemoryManagement";
import ModelSettings from "./components/ModelSettings";
import { apiBaseUrl } from "./services/api";
import { useBackend } from "./services/useBackend";
import { useConversations } from "./services/useConversations";

type Page =
  | "home"
  | "chat"
  | "architecture"
  | "code"
  | "calendar"
  | "files"
  | "audio"
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
  { id: "audio", label: "Audio", icon: FileText },
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
  audio: "Audio",
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
  const [liveText, setLiveText] = useState("");
  const [runState, setRunState] = useState("");
  const [activeRun, setActiveRun] = useState("");
  const [chatError, setChatError] = useState("");
  const sendLock = useRef(false);
  const attachmentInput = useRef<HTMLInputElement>(null);
  const [attachmentDrafts,setAttachmentDrafts] = useState<Record<string,Attachment[]>>({});
  const [toolDrafts,setToolDrafts] = useState<Record<string,string[]|null>>({});
  const [attachmentBusy,setAttachmentBusy] = useState(false);
  const attachmentLock = useRef(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const [activity, setActivity] = useState<RequestActivity[]>([]);
  const [selectedNode, setSelectedNode] = useState("supervisor");
  const backend = useBackend();
  const { content: permanentContext, updatedAt: contextUpdatedAt, version: contextVersion, saving: contextSaving, error: contextError, edit: setPermanentContext, save: savePermanentContext, reload:reloadPermanentContext } = usePermanentContext(Boolean(backend.health));
  const history = useConversations(Boolean(backend.health), sending);
  const { chats, setChats, currentChat } = history;
  useEffect(() => {
    if (page === "chat" && !history.messagesLoading)
      messagesEnd.current?.scrollIntoView({ block: "end" });
  }, [page, currentChat.id, currentChat.messages.length, history.messagesLoading, sending]);

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
  async function attach(files:File[]) {
    if(attachmentLock.current||sendLock.current)return;
    const id=currentChat.threadId, existing=attachmentDrafts[id]||[];
    if(existing.length+files.length>6){setChatError("Massimo sei allegati per richiesta.");return;}
    attachmentLock.current=true;setAttachmentBusy(true);setChatError("");
    try{for(const file of files){const item=await uploadAttachment(id,file);setAttachmentDrafts(prev=>({...prev,[id]:[...(prev[id]||[]),item]}));}}
    catch(e){setChatError(e instanceof Error?e.message:"Allegato non caricato.");}
    finally{attachmentLock.current=false;setAttachmentBusy(false);}
  }
  async function send() {
    const manualTools = toolDrafts[currentChat.threadId] ?? null;
    const attachments = attachmentDrafts[currentChat.threadId]||[];
    const content = draft.trim() || (attachments.length ? "Analizza i file allegati." : "");
    if (!content || attachmentLock.current || sendLock.current || history.messagesLoading || history.historyLoading || history.messagesError || !backend.health?.ollama_online) return;
    sendLock.current = true;
    setSending(true);
    setLiveText("");
    setActiveRun("");
    setRunState("queued");
    setChatError("");
    setDraft("");
    setAttachmentDrafts(prev=>({...prev,[currentChat.threadId]:[]}));
    setToolDrafts(prev=>({...prev,[currentChat.threadId]:null}));
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
                  attachments,
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
      const result = await streamChat(content, threadId, setActiveRun, setLiveText, setRunState, attachments.map(a=>a.id), manualTools);
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
      setAttachmentDrafts(prev=>({...prev,[threadId]:[...attachments,...(prev[threadId]||[])]}));
      setToolDrafts(prev=>({...prev,[threadId]:manualTools}));
    } finally {
      sendLock.current = false;
      setSending(false);
      setLiveText("");
      setActiveRun("");
      void history.refreshHistory();
    }
  }
  const withSidebar = !["home", "files", "audio", "architecture", "code", "calendar"].includes(page);
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
                      {m.attachments?.map(a=><a className="attachment-chip" href={apiBaseUrl+a.downloadUrl} key={a.id}>{a.name}{a.truncated?" · estratto limitato":""}</a>)}
                      {m.failed && (
                        <small className="message-failed">
                          Esito della richiesta non confermato
                        </small>
                      )}
                    </div>
                  </div>
                ))}
                {sending && <div className="message assistant"><div className="message-body"><p>{liveText || (runState === "queued" ? "In coda…" : runState === "cancelling" ? "Annullamento in corso…" : runState.startsWith("Agente:") ? runState : "Cora sta lavorando…")}</p>{activeRun && <button className="text-button" disabled={runState === "cancelling"} onClick={() => void runtimeRequest("/runtime/runs/" + activeRun + "/cancel", { method: "POST" }).then(() => setRunState("cancelling")).catch(e => setChatError(e.message))}>Annulla esecuzione</button>}</div></div>}
                <div ref={messagesEnd} />
              </div>
              <div className="chat-bottom">
                {chatError && (
                  <div className="connection-error" role="alert">
                    {chatError}
                  </div>
                )}
                {attachmentBusy&&<p role="status">Caricamento degli allegati…</p>}
                <ChatToolPicker key={currentChat.threadId} selection={toolDrafts[currentChat.threadId]??null} onChange={names=>setToolDrafts(prev=>({...prev,[currentChat.threadId]:names}))} disabled={sending||attachmentBusy} available={Boolean(backend.health)} />
                <div className="attachment-drafts">{(attachmentDrafts[currentChat.threadId]||[]).map(a=><span className="attachment-chip" key={a.id}>{a.name}{a.truncated?" · estratto limitato":""}<button disabled={sending||attachmentBusy} aria-label={"Rimuovi allegato "+a.name} onClick={()=>setAttachmentDrafts(prev=>({...prev,[currentChat.threadId]:(prev[currentChat.threadId]||[]).filter(x=>x.id!==a.id)}))}>×</button></span>)}</div>
                <div className="composer">
                  <input ref={attachmentInput} type="file" multiple hidden accept=".txt,.md,.csv,.tsv,.json,.pdf,.docx,.py,.ts,.tsx,.js,.css,.yaml,.yml,.toml,.log" onChange={e=>{const files=Array.from(e.target.files||[]);e.target.value="";void attach(files);}}/>
                  <button disabled={sending||attachmentBusy||!backend.health} title="Allega documenti alla richiesta" aria-label="Allega file" onClick={()=>attachmentInput.current?.click()}>
                    <Paperclip size={19} /><span>Allega</span>
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
                    className="send-button"
                    disabled={
                      sending || attachmentBusy || history.messagesLoading || history.historyLoading || Boolean(history.messagesError) || !backend.health?.ollama_online || (!draft.trim() && !(attachmentDrafts[currentChat.threadId]||[]).length)
                    }
                    title="Invia messaggio"
                    aria-label="Invia messaggio"
                    onClick={() => void send()}
                  >
                    <Send size={17} />
                  </button>
                </div>
                <small>Allegati: testo, PDF e Word · massimo 6 file da 5 MB. Per le registrazioni usa la pagina Audio. Gli estratti limitati sono segnalati.</small>
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
                  <span>Allegati: massimo 6 documenti, 5 MB ciascuno · estratti limitati</span>
                  <button className="text-button" onClick={()=>navigate("audio")}>Registrazioni e trascrizioni → Audio</button>
                  <span>Risposta progressiva attiva</span>
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
          {page === "code" && <Programmer />}
          {page === "calendar" && <Calendar />}
          {page === "files" && <FileManager />}
          {page === "audio" && <Audio />}
          {page === "activity" && (
            <section className="content-page activity-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">TRASPARENZA</div>
                  <h1>Attività</h1>
                  <p>
                    Attività recenti della sessione e tracce tecniche persistenti
                    delle esecuzioni di Cora.
                  </p>
                </div>
                <span className="pill">Runtime · Sola lettura</span>
              </div>
              <div className="activity-layout">
                <div className="section-card activity-session-card">
                  <h2>Richieste della sessione</h2>
                  <p className="muted">
                    Vista immediata delle richieste inviate da questa interfaccia.
                  </p>
                  {activity.length === 0 ? (
                    <p className="muted">
                      Nessuna richiesta inviata in questa sessione.
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
                            "pill " +
                            (a.status === "completed"
                              ? "success"
                              : a.status === "failed"
                                ? "pending"
                                : "")
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
                </div>
                <RuntimePanel />
                <ArchitectureRuntime showGraph={false} showTraces />
              </div>
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
                  <button className="text-button" onClick={async () => { const r = await authenticatedFetch(apiBaseUrl + "/auth/logout", { method: "POST" }); if (r.ok) window.dispatchEvent(new Event("cora:unauthorized")); }}>Esci</button>
                  <button className="text-button" onClick={async () => { const r = await authenticatedFetch(apiBaseUrl + "/auth/logout?all_sessions=true", { method: "POST" }); if (r.ok) window.dispatchEvent(new Event("cora:unauthorized")); }}>Disconnetti tutti i dispositivi</button>
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
                <ModelSettings onChanged={() => void backend.refresh()} />
                <div className="settings-row">
                  <div>
                    <strong>Modalità runtime</strong>
                    <p>{backend.health?.runtime_mode === "server" ? "Istanza server ufficiale" : "PC di prova · risorse server bloccate"}</p>
                  </div>
                  <span className={"pill " + (backend.health?.runtime_mode === "server" ? "success" : "pending")}>
                    {backend.health?.runtime_mode === "server" ? "SERVER" : "DEV / ISOLATED"}
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
                    <div className="connection-error">{contextError} <button className="text-button" disabled={contextSaving} onClick={()=>void reloadPermanentContext()}>Carica la versione salvata (sostituisce la bozza)</button></div>
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

