import ChatLibraryPicker from "./components/ChatLibraryPicker";
import LibraryMonitorFeed from "./components/LibraryMonitorFeed";
import LibraryMonitorSettings from "./components/LibraryMonitorSettings";
import ThinkingPanel, { type ThinkingState } from "./components/ThinkingPanel";
import { LengthChoice, RunTimer, type ResponseLength } from "./components/RunControls";
import { usePermanentContext } from "./services/usePermanentContext";
import { streamChat, runtimeRequest, type LibraryActivity } from "./services/runtimeApi";
import { authenticatedFetch } from "./services/transport";
import RuntimePanel from "./components/RuntimePanel";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  CalendarDays,
  ChevronDown,
  FileAudio,
  Files,
  House,
  Images,
  FileText,
  Menu,
  MoreHorizontal,
  Paperclip,
  RefreshCw,
  Send,
  Settings,
  Save,
  Server,
} from "lucide-react";
import Audio from "./components/Audio";
import ChatToolPicker from "./components/ChatToolPicker";
import ConversationSidebar from "./components/ConversationSidebar";
import { uploadAttachment, attachLibraryFile, type Attachment } from "./services/mediaApi";
import Home from "./components/Home";
import SystemUpdate from "./components/SystemUpdate";
import MobileHome from "./components/MobileHome";
import MobilePhotos from "./components/MobilePhotos";
import Programmer from "./components/Programmer";
import Calendar from "./components/Calendar";
import FileManager from "./components/FileManager";
import Architecture from "./components/Architecture";
import Machines from "./components/Machines";
import ArchitectureRuntime from "./components/ArchitectureRuntime";
import MemoryManagement from "./components/MemoryManagement";
import ModelSettings from "./components/ModelSettings";
import { api, apiBaseUrl } from "./services/api";
import { useBackend } from "./services/useBackend";
import { useConversations } from "./services/useConversations";

type Page =
  | "home"
  | "chat"
  | "photos"
  | "architecture"
  | "machines"
  | "code"
  | "calendar"
  | "files"
  | "audio"
  | "activity"
  | "updates"
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
  { id: "machines", label: "Macchine" },
  { id: "code", label: "Programma" },
  { id: "calendar", label: "Calendario" },
];
const secondary: { id: Page; label: string; icon: typeof FileText }[] = [
  { id: "audio", label: "Audio", icon: FileText },
  { id: "activity", label: "Attività", icon: Activity },
  { id: "updates", label: "Aggiornamenti", icon: RefreshCw },
  { id: "settings", label: "Impostazioni", icon: Settings },
];
const mobilePrimary: { id: Page; label: string; icon: typeof House }[] = [
  { id: "home", label: "Home", icon: House },
  { id: "photos", label: "Foto", icon: Images },
  { id: "files", label: "File", icon: Files },
  { id: "audio", label: "Audio", icon: FileAudio },
  { id: "calendar", label: "Agenda", icon: CalendarDays },
];
const uid = () => crypto.randomUUID();
export default function App({ authMode = "password" }: { authMode?: string } = {}) {
  const [page, setPage] = useState<Page>(() => {
    const requested = window.location.hash.replace(/^#/, "");
    return ["home", "photos", "files", "audio", "calendar", "chat", "activity", "updates", "settings", "machines"].includes(requested) ? requested as Page : "home";
  });
  const [menu, setMenu] = useState(false);
  const [mobileUi, setMobileUi] = useState(() => window.matchMedia("(max-width: 620px)").matches);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [responseLength, setResponseLength] = useState<ResponseLength>("medium");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [finishedAt, setFinishedAt] = useState<number | null>(null);
  const [liveText, setLiveText] = useState("");
  const [thinking, setThinking] = useState<ThinkingState>({text: "", truncated: false});
  const [libraryActivity, setLibraryActivity] = useState<{threadId:string; items:LibraryActivity[]}>({threadId:"", items:[]});
  const [runState, setRunState] = useState("");
  const [activeRun, setActiveRun] = useState("");
  const [chatError, setChatError] = useState("");
  const sendLock = useRef(false);
  const attachmentInput = useRef<HTMLInputElement>(null);
  const [attachmentDrafts,setAttachmentDrafts] = useState<Record<string,Attachment[]>>({});
  const [toolDrafts,setToolDrafts] = useState<Record<string,string[]|null>>({});
  const [attachmentBusy,setAttachmentBusy] = useState(false);
  const [attachmentMenu,setAttachmentMenu] = useState(false);
  const [libraryPicker,setLibraryPicker] = useState(false);
  const attachmentLock = useRef(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const [activity, setActivity] = useState<RequestActivity[]>([]);
  const [selectedNode, setSelectedNode] = useState("supervisor");
  const backend = useBackend();
  const { content: permanentContext, updatedAt: contextUpdatedAt, version: contextVersion, saving: contextSaving, error: contextError, edit: setPermanentContext, save: savePermanentContext, reload:reloadPermanentContext } = usePermanentContext(Boolean(backend.health));
  const history = useConversations(Boolean(backend.health), sending);
  const { chats, setChats, currentChat } = history;
  useEffect(() => setThinking({text: "", truncated: false}), [currentChat.id]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 620px)");
    const sync = () => setMobileUi(media.matches);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    const syncHash = () => {
      const requested = window.location.hash.replace(/^#/, "");
      if (["home", "photos", "files", "audio", "calendar", "chat", "activity", "settings", "machines"].includes(requested)) setPage(requested as Page);
    };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);
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
    const url = next === "home"
      ? window.location.pathname + window.location.search
      : "#" + next;
    window.history.replaceState(null, "", url);
  }
  function newChat(projectId: string | null = null) {
    if (sendLock.current) return;
    history.newChat(projectId);
    setAttachmentMenu(false);
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
  async function attachFromLibrary(path: string) {
    if (attachmentLock.current || sendLock.current) throw new Error("Attendi la fine dell'operazione corrente.");
    const id = currentChat.threadId;
    if ((attachmentDrafts[id] || []).length >= 6) throw new Error("Massimo sei allegati.");
    attachmentLock.current = true;
    setAttachmentBusy(true);
    try {
      const item = await attachLibraryFile(id, path);
      setAttachmentDrafts(prev => ({...prev,[id]:[...(prev[id] || []),item]}));
    } finally {
      attachmentLock.current = false;
      setAttachmentBusy(false);
    }
  }
  async function send() {
    const manualTools = toolDrafts[currentChat.threadId] ?? null;
    const attachments = attachmentDrafts[currentChat.threadId]||[];
    const content = draft.trim() || (attachments.length ? "Analizza i file allegati." : "");
    if (!content || attachmentLock.current || sendLock.current || history.messagesLoading || history.historyLoading || history.messagesError || !backend.health?.ollama_online) return;
    sendLock.current = true;
    setSending(true);
    setThinking({text: "", truncated: false});
    setStartedAt(Date.now()); setFinishedAt(null);
    setLiveText("");
    setActiveRun("");
    setRunState("queued");
    setChatError("");
    setAttachmentMenu(false);
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
      if (!currentChat.persisted) {
        await api.createConversation(threadId, currentChat.projectId);
      }
      setLibraryActivity({threadId, items:[]});
      const result = await streamChat(content, threadId, setActiveRun, setLiveText, setRunState, attachments.map(a=>a.id), manualTools, item => setLibraryActivity(previous => ({threadId, items:[...previous.items.slice(-199), item]})), responseLength, setThinking);
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
      setFinishedAt(Date.now());
      setLiveText("");
      setActiveRun("");
      void history.refreshHistory();
    }
  }
  const withSidebar = !["home", "photos", "files", "audio", "architecture", "code", "calendar", "machines"].includes(page);
  return (
    <div
      className={"app app-" + page + " " + (withSidebar ? "has-sidebar" : "")}
    >
      {withSidebar && (
        <aside className="global-sidebar">
          <div className="sidebar-top">
            <ConversationSidebar
              chats={chats}
              projects={history.projects}
              currentId={currentChat.id}
              disabled={sending}
              loading={history.historyLoading}
              error={history.historyError}
              onNew={(projectId) => newChat(projectId ?? null)}
              onRefresh={() => void history.refreshHistory()}
              onSelect={(id) => {
                history.selectChat(id);
                setAttachmentMenu(false);
                setDraft("");
                setChatError("");
                navigate("chat");
              }}
              onRename={history.renameChat}
              onDelete={history.deleteChat}
              onMove={history.moveChat}
              onCreateProject={history.createProject}
              onEditProject={history.updateProject}
              onDeleteProject={history.deleteProject}
            />
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
            <div className="mobile-more-wrap">
              <button className="mobile-more-button" onClick={() => setMenu(!menu)} aria-expanded={menu} aria-label="Altre funzioni">
                <MoreHorizontal size={21} />
              </button>
              {menu && (
                <div className="dropdown mobile-dropdown">
                  <button onClick={() => navigate("chat")}><span>✦</span> Chat Cora</button>
                  <button onClick={() => navigate("activity")}><Activity size={17} /> Attività</button>
                  <button onClick={() => navigate("machines")}><Server size={17} /> Macchine</button>
                  <button onClick={() => navigate("settings")}><Settings size={17} /> Impostazioni</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className={"main " + (page === "chat" ? "chat-main" : "")}>
          {backend.error && page !== "updates" && (
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
            mobileUi ? (
              <div className="mobile-home-slot">
                <MobileHome
                  health={backend.health}
                  checking={backend.checking}
                  onRefresh={() => void backend.refresh()}
                  onNavigate={(next) => navigate(next)}
                />
              </div>
            ) : (
              <Home
                health={backend.health}
                checking={backend.checking}
                checkedAt={backend.checkedAt}
                onOpenUpdates={() => navigate("updates")}
              />
            )
          )}
          {page === "updates" && (
            <section className="content-page narrow">
              <SystemUpdate standalone />
            </section>
          )}
          {page === "photos" && <MobilePhotos />}
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
                {libraryActivity.threadId === currentChat.threadId && libraryActivity.items.length > 0 && <details className="message assistant" open><summary>Consultazione Libreria IA · ultima richiesta</summary><div className="message-body"><small>Attività della sessione corrente, fino a 200 passaggi. Non conservata dopo il ricaricamento.</small><ul>{libraryActivity.items.map((item, index) => <li key={index}>{item.action === "search" ? `Ricerca «${item.query}»` : item.action === "list" ? "Elenco documenti" : "Lettura"} · {item.path === "." ? "Libreria IA" : item.path}</li>)}</ul></div></details>}
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
                {libraryPicker && <ChatLibraryPicker disabled={sending||attachmentBusy} onClose={()=>setLibraryPicker(false)} onPick={attachFromLibrary} />}
                <div className="attachment-drafts">{(attachmentDrafts[currentChat.threadId]||[]).map(a=><span className="attachment-chip" key={a.id}>{a.name}{a.truncated?" · estratto limitato":""}<button disabled={sending||attachmentBusy} aria-label={"Rimuovi allegato "+a.name} onClick={()=>setAttachmentDrafts(prev=>({...prev,[currentChat.threadId]:(prev[currentChat.threadId]||[]).filter(x=>x.id!==a.id)}))}>×</button></span>)}</div>
                <ThinkingPanel key={currentChat.threadId} value={thinking} threadId={currentChat.threadId} running={sending} />
                <RunTimer started={startedAt} finished={finishedAt} />
                <LengthChoice value={responseLength} onChange={setResponseLength} disabled={sending} />
                <div className="composer">
                  <input ref={attachmentInput} type="file" multiple hidden accept=".txt,.md,.csv,.tsv,.json,.pdf,.docx,.py,.ts,.tsx,.js,.css,.yaml,.yml,.toml,.log" onChange={e=>{const files=Array.from(e.target.files||[]);e.target.value="";void attach(files);}}/>
                  <div className="attachment-choice">
                    <button disabled={sending||attachmentBusy||!backend.health} title="Scegli la provenienza del documento" aria-label="Allega file" aria-expanded={attachmentMenu} onClick={()=>setAttachmentMenu(open=>!open)}>
                      <Paperclip size={19} /><span>Allega</span>
                    </button>
                    {attachmentMenu && <div className="attachment-choice-menu composer-tools-menu">
                      <div className="composer-menu-section">
                        <strong>Allega</strong>
                        <button type="button" onClick={()=>{setAttachmentMenu(false);attachmentInput.current?.click();}}>Carica dal dispositivo</button>
                        <button type="button" onClick={()=>{setAttachmentMenu(false);setLibraryPicker(true);}}>Scegli dalla Libreria IA</button>
                      </div>
                      <div className="composer-menu-divider" />
                      <div className="composer-menu-section">
                        <strong>Strumenti</strong>
                        <ChatToolPicker
                          embedded
                          key={currentChat.threadId}
                          selection={toolDrafts[currentChat.threadId]??null}
                          onChange={names=>setToolDrafts(prev=>({...prev,[currentChat.threadId]:names}))}
                          disabled={sending||attachmentBusy}
                          available={Boolean(backend.health)}
                        />
                      </div>
                    </div>}
                  </div>
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
          {page === "machines" && <Machines />}
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
              <LibraryMonitorFeed />
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
                  {authMode === "desktop" ? <p>Accesso locale automatico. Cora accetta richieste soltanto dal computer che la esegue.</p> : authMode === "tailscale" ? <p>Accesso automatico tramite Tailscale. Per interromperlo su questo dispositivo, disconnetti Tailscale; per revocarlo, rimuovi il dispositivo dalla console Tailscale.</p> : <>
                  <button className="text-button" onClick={async () => { const r = await authenticatedFetch(apiBaseUrl + "/auth/logout", { method: "POST" }); if (r.ok) window.dispatchEvent(new Event("cora:unauthorized")); }}>Esci</button>
                  <button className="text-button" onClick={async () => { const r = await authenticatedFetch(apiBaseUrl + "/auth/logout?all_sessions=true", { method: "POST" }); if (r.ok) window.dispatchEvent(new Event("cora:unauthorized")); }}>Disconnetti tutti i dispositivi</button>
                  </>}
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
                <LibraryMonitorSettings />
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
                        Informazioni sul proprietario che Cora può consultare quando
                        servono alla richiesta. Non vengono inserite in ogni turno
                        né modificate automaticamente.
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
      <nav className="mobile-nav" aria-label="Navigazione mobile">
        {mobilePrimary.map((item) => (
          <button
            key={item.id}
            className={page === item.id ? "active" : ""}
            onClick={() => navigate(item.id)}
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

