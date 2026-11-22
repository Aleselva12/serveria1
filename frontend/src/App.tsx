import "./tree/preview.css";
import ChatMessage from "./components/ChatMessage";
import ChatModelBar from "./components/ChatModelBar";
import "./chat.css";
import ChatLibraryPicker from "./components/ChatLibraryPicker";
import LibraryMonitorFeed from "./components/LibraryMonitorFeed";
import LibraryMonitorSettings from "./components/LibraryMonitorSettings";
import ThinkingPanel, { type ThinkingState } from "./components/ThinkingPanel";
import { LengthChoice, RunTimer, type ResponseLength } from "./components/RunControls";
import { usePermanentContext } from "./services/usePermanentContext";
import { streamChat, runtimeRequest, type LibraryActivity } from "./services/runtimeApi";
import RuntimePanel from "./components/RuntimePanel";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bell,
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
import NotificationsPage, { HomeNotifications, useInbox, type NotificationsTab } from "./components/Notifications";
import { useDecisions } from "./components/Decisions";
import PushSettings from "./components/PushSettings";
import SystemUpdate from "./components/SystemUpdate";
import SystemHealth from "./components/SystemHealth";
import ManagedApplications from "./components/ManagedApplications";
import { SYSTEM_TABS, systemTabFor, type SystemTab } from "./components/systemTabs";
import MobileHome from "./components/MobileHome";
import MobilePhotos from "./components/MobilePhotos";
import Programmer from "./components/Programmer";
import Mail from "./components/Mail";
import Calendar from "./components/Calendar";
import FileManager from "./components/FileManager";
import Architecture from "./components/Architecture";
import Machines from "./components/Machines";
import ArchitectureRuntime from "./components/ArchitectureRuntime";
import MemoryManagement from "./components/MemoryManagement";
import ModelSettings from "./components/ModelSettings";
import RuntimeSettingsOverview from "./components/RuntimeSettingsOverview";
import AgentPermissions from "./components/AgentPermissions";
import AccountsSettings from "./components/AccountsSettings";
import { SETTINGS_TABS, isSettingsTab, splitHash, type SettingsTab } from "./components/settingsTabs";
import { api, apiBaseUrl } from "./services/api";
import { useBackend } from "./services/useBackend";
import { useConversations } from "./services/useConversations";

import {lazy, Suspense} from "react";
const TreeHome=lazy(()=>import("./tree/TreeHome"));
// React Flow and its fonts load only when the page is opened.
const Automations=lazy(()=>import("./components/automations/Automations"));

type Page =
  | "homepage-schema-albero"
  | "home"
  | "chat"
  | "photos"
  | "architecture"
  | "automations"
  | "machines"
  | "code"
  | "mail"
  | "calendar"
  | "files"
  | "audio"
  | "activity"
  | "updates"
  | "settings"
  | "system"
  | "notifications"
  | "memory-management";
const validPages: ReadonlySet<Page> = new Set([
  "home", "chat", "photos", "architecture", "automations", "machines", "code", "calendar", "mail",
  "files", "audio", "activity", "updates", "settings", "memory-management", "homepage-schema-albero",
  "notifications", "system",
]);
function isPage(value: string): value is Page {
  return validPages.has(value as Page);
}
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
  { id: "automations", label: "Automazioni" },
  { id: "code", label: "Programma" },
  { id: "calendar", label: "Calendario" },
  { id: "mail", label: "Mail" },
  { id: "files", label: "File" },
  { id: "audio", label: "Audio" },
];
const secondary: { id: Page; label: string; icon: typeof FileText }[] = [
  { id: "notifications", label: "Notifiche", icon: Bell },
  { id: "system", label: "Sistema", icon: Server },
  { id: "settings", label: "Impostazioni", icon: Settings },
];
const mobilePrimary: { id: Page; label: string; icon: typeof House }[] = [
  { id: "home", label: "Home", icon: House },
  { id: "photos", label: "Foto", icon: Images },
  { id: "files", label: "File", icon: Files },
  { id: "audio", label: "Audio", icon: FileAudio },
  { id: "calendar", label: "Agenda", icon: CalendarDays },
  { id: "mail", label: "Mail", icon: FileText },
];
const uid = () => crypto.randomUUID();
export default function App({ authMode = "tailscale" }: { authMode?: string } = {}) {
  const [page, setPage] = useState<Page>(() => {
    const [requested, sub] = splitHash(window.location.hash);
    if (systemTabFor(requested, sub)) return "system";
    return isPage(requested) ? requested : "home";
  });
  const [systemTab, setSystemTab] = useState<SystemTab>(() => {
    const [requested, sub] = splitHash(window.location.hash);
    return systemTabFor(requested, sub) ?? "salute";
  });
  const [settingsTab, setSettingsTab] = useState<SettingsTab>(() => {
    const [requested, sub] = splitHash(window.location.hash);
    return requested === "settings" && isSettingsTab(sub) ? sub : "generale";
  });
  const [menu, setMenu] = useState(false);
  // Menu badge: unseen alerts plus decisions waiting for the owner.
  const unseen = (useInbox(false).inbox?.unseen ?? 0) + (useDecisions().decisions?.pending ?? 0);
  const [notificationsTab, setNotificationsTab] = useState<NotificationsTab>("alerts");
  const [inspector, setInspector] = useState(false);
  const [connections, setConnections] = useState(false);
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
      const [requested, sub] = splitHash(window.location.hash);
      const system = systemTabFor(requested, sub);
      if (system) { setPage("system"); setSystemTab(system); return; }
      if (isPage(requested)) setPage(requested);
      if (requested === "settings") setSettingsTab(isSettingsTab(sub) ? sub : "generale");
    };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);
  useEffect(() => {
    if (page === "chat" && !history.messagesLoading && (currentChat.messages.length > 0 || sending))
      messagesEnd.current?.scrollIntoView({ block: "end" });
  }, [page, currentChat.id, currentChat.messages.length, history.messagesLoading, sending]);

  const statusLabel = backend.health
    ? "Backend collegato"
    : backend.checking
      ? "Connessione…"
      : "Collegamento non riuscito";
  // Updates, machines and activity are Sistema tabs: their old ids still navigate there.
  function navigate(next: Page, sub?: string) {
    const system = systemTabFor(next, sub);
    const target: Page = system ? "system" : next;
    let suffix = "";
    setPage(target);
    setMenu(false);
    if (target === "settings") {
      const tab: SettingsTab = isSettingsTab(sub) ? sub : "generale";
      setSettingsTab(tab);
      if (tab !== "generale") suffix = "/" + tab;
    }
    if (system) {
      setSystemTab(system);
      if (system !== "salute") suffix = "/" + system;
    }
    const url = target === "home"
      ? window.location.pathname + window.location.search
      : "#" + target + suffix;
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
  const withSidebar = page === "chat";
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
                      {item.id === "notifications" && unseen > 0 && <span className="pill error">{unseen}</span>}
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
                  <button onClick={() => navigate("notifications")}><Bell size={17} /> Notifiche{unseen ? " (" + unseen + ")" : ""}</button>
                  <button onClick={() => navigate("system")}><Server size={17} /> Sistema</button>
                  <button onClick={() => navigate("settings")}><Settings size={17} /> Impostazioni</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className={"main " + (page === "chat" ? "chat-main" : "")}>
          {backend.error && !(page === "system" && systemTab === "aggiornamenti") && (
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
                  onNavigate={(next) => navigate(next, next === "settings" ? "notifiche" : "generale")}
                  onOpenUpdates={() => navigate("updates")}
                />
              </div>
            ) : (
              <Home
                health={backend.health}
                checking={backend.checking}
                checkedAt={backend.checkedAt}
                onOpenUpdates={() => navigate("updates")}
                onOpenHealth={() => navigate("system", "salute")}
              />
            )
          )}
          {page === "home" && <HomeNotifications onOpenAll={() => { setNotificationsTab("alerts"); navigate("notifications"); }} onOpenDecisions={() => { setNotificationsTab("decisions"); navigate("notifications"); }} />}
          {page === "notifications" && <NotificationsPage key={notificationsTab} initialTab={notificationsTab} onOpenSettings={() => navigate("settings", "notifiche")} onOpenAudio={() => navigate("audio")} />}
          {page === "system" && (
            <nav className="settings-tabs system-tabs" role="tablist" aria-label="Sezioni di Sistema">
              {SYSTEM_TABS.map(t => <button key={t.id} role="tab" aria-selected={systemTab === t.id}
                className={systemTab === t.id ? "active" : ""} onClick={() => navigate("system", t.id)}>{t.label}</button>)}
            </nav>
          )}
          {page === "system" && systemTab === "salute" && (
            <section className="content-page">
              <div className="page-heading"><div><div className="eyebrow">SISTEMA</div><h1>Salute</h1><p>Controlli automatici e stato di ogni servizio del server.</p></div></div>
              <SystemHealth />
            </section>
          )}
          {page === "system" && systemTab === "aggiornamenti" && (
            <section className="content-page narrow">
              <SystemUpdate standalone />
              <div className="system-card system-apps">
                <h2>Applicazioni gestite</h2>
                <ManagedApplications defaultOpen />
              </div>
            </section>
          )}
          {page === "photos" && <MobilePhotos />}
          {page === "chat" && (
            <section className="chat-page">
              <header className="chat-workspace-header">
                <div><span className="chat-eyebrow">SERVERIA · SPAZIO PERSONALE</span><strong>Cora <span>Una conversazione, tante possibilità.</span></strong></div>
                <div className="chat-header-actions">
                  <ChatModelBar revision={backend.health?.model_configuration_id} onSettings={()=>navigate('architecture')}/>
                  <button className={inspector?'active':''} aria-expanded={inspector} aria-controls="chat-inspector" onClick={()=>setInspector(v=>!v)}>Attività e fonti</button>
                </div>
              </header>
              {inspector && <aside className="chat-inspector" id="chat-inspector" aria-label="Attività e fonti della chat"><button onClick={()=>setInspector(false)} aria-label="Chiudi attività">×</button><h2>Attività e fonti</h2><p>Operazioni registrate da Cora, distinte dal testo del modello.</p><ThinkingPanel key={currentChat.threadId} value={thinking} threadId={currentChat.threadId} running={sending} /></aside>}
              <div className="messages" aria-live="polite">
                {history.messagesLoading && <p role="status">Caricamento dei messaggi…</p>}
                {history.messagesError && <div className="connection-error" role="alert">
                  {history.messagesError}
                  <button disabled={history.messagesLoading} onClick={() => history.selectChat(currentChat.id)}>Riprova</button>
                </div>}
                {!history.messagesLoading && !history.messagesError && currentChat.messages.length === 0 && (
                  <div className="chat-welcome">
                    <span className="chat-welcome-mark">✦</span><span className="chat-eyebrow">IL TUO SPAZIO, CON CORA</span>
                    <h1>Da dove cominciamo?</h1>
                    <p>Un’idea, un documento, qualcosa da organizzare.<br/>Portalo qui, facciamogli spazio.</p>
                    <div className="chat-starters">
                      <button onClick={()=>setDraft('Cerca nella Libreria IA ')}><Files size={18}/><strong>Ritrova un’informazione</strong><span>Cerca tra i tuoi documenti</span></button>
                      <button onClick={()=>setDraft('Aiutami a organizzare ')}><CalendarDays size={18}/><strong>Metti ordine alle idee</strong><span>Ragioniamo sul prossimo passo</span></button>
                      <button onClick={()=>setDraft('Aiutami a scrivere ')}><FileText size={18}/><strong>Comincia una bozza</strong><span>Un testo da costruire insieme</span></button>
                    </div>
                  </div>
                )}
                {currentChat.messages.map((m) => (
                  <div key={m.id} className={"message " + m.role}>
                    <div className="message-avatar">
                      {m.role === "assistant" ? "✦" : m.role === "system" ? "S" : "A"}
                    </div>
                    <div className="message-content">
                      <ChatMessage content={m.content} assistant={m.role==='assistant'}/>
                      {m.attachments?.map(a=><a className="attachment-chip" href={apiBaseUrl+a.downloadUrl} key={a.id}>{a.name}{a.truncated?" · estratto limitato":""}</a>)}
                      {m.failed && (
                        <small className="message-failed">
                          Esito della richiesta non confermato
                        </small>
                      )}
                    </div>
                  </div>
                ))}
                {libraryActivity.threadId === currentChat.threadId && libraryActivity.items.length > 0 && <details className="chat-library-sources"><summary>Fonti consultate · ultima richiesta</summary><div className="message-body"><small>Attività della sessione corrente, fino a 200 passaggi. Non conservata dopo il ricaricamento.</small><ul>{libraryActivity.items.map((item, index) => <li key={index}>{item.action === "search" ? `Ricerca «${item.query}»` : item.action === "list" ? "Elenco documenti" : "Lettura"} · {item.path === "." ? "Libreria IA" : item.path}</li>)}</ul></div></details>}
                {sending && <div className="message assistant"><div className="message-body">{liveText ? <ChatMessage content={liveText} assistant/> : <p role="status">{(runState === "queued" ? "In coda…" : runState === "cancelling" ? "Annullamento in corso…" : runState.startsWith("Agente:") ? runState : "Cora sta lavorando…")}</p>}{activeRun && <button className="text-button" disabled={runState === "cancelling"} onClick={() => void runtimeRequest("/runtime/runs/" + activeRun + "/cancel", { method: "POST" }).then(() => setRunState("cancelling")).catch(e => setChatError(e.message))}>Annulla esecuzione</button>}</div></div>}
                <div ref={messagesEnd} />
              </div>
              <div className="chat-bottom">
                {chatError && (
                  <div className="connection-error" role="alert">
                    {chatError}<button className="text-button" onClick={()=>navigate('activity')}>Apri Attività</button>
                  </div>
                )}
                {attachmentBusy&&<p role="status">Caricamento degli allegati…</p>}
                {libraryPicker && <ChatLibraryPicker disabled={sending||attachmentBusy} onClose={()=>setLibraryPicker(false)} onPick={attachFromLibrary} />}
                <div className="attachment-drafts">{(attachmentDrafts[currentChat.threadId]||[]).map(a=><span className="attachment-chip" key={a.id}>{a.name}{a.truncated?" · estratto limitato":""}<button disabled={sending||attachmentBusy} aria-label={"Rimuovi allegato "+a.name} onClick={()=>setAttachmentDrafts(prev=>({...prev,[currentChat.threadId]:(prev[currentChat.threadId]||[]).filter(x=>x.id!==a.id)}))}>×</button></span>)}</div>
                <div className="chat-composer-toolbar"><button aria-expanded={connections} onClick={()=>setConnections(v=>!v)}>＋ Spazi collegati</button>
                <LengthChoice value={responseLength} onChange={setResponseLength} disabled={sending} /></div>
                {connections && <nav className="chat-connections" aria-label="Spazi collegati">
                  <button onClick={()=>navigate('files')}><Files size={16}/> File e Libreria IA</button>
                  <button onClick={()=>navigate('calendar')}><CalendarDays size={16}/> Calendario</button>
                  <button onClick={()=>navigate('audio')}><FileAudio size={16}/> Audio → Word</button>
                  <button onClick={()=>navigate('code')}><FileText size={16}/> Programmatore</button>
                  <button onClick={()=>navigate('home')}><House size={16}/> Home e programmi</button>
                </nav>}
                <RunTimer started={startedAt} finished={finishedAt} />
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
                    onChange={(e) => {setDraft(e.target.value);e.target.style.height='auto';e.target.style.height=Math.min(e.target.scrollHeight,144)+'px';}}
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
                <div className="chat-footer"><span>Cora può sbagliare. Controlla le fonti e approva le modifiche.</span><button onClick={()=>setInspector(true)}>Dettagli della conversazione</button></div>
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
          {page === "system" && systemTab === "macchine" && <Machines />}
          {page === "automations" && <Suspense fallback={<p>Apertura automazioni…</p>}><Automations /></Suspense>}
          {page === "code" && <Programmer />}
          {page === "homepage-schema-albero" && <Suspense fallback={<p>Apertura schema…</p>}><TreeHome /></Suspense>}
          {page === "calendar" && <Calendar />}
          {page === "mail" && <Mail />}
          {page === "files" && <FileManager />}
          {page === "audio" && <Audio />}
          {page === "system" && systemTab === "attivita" && (
            <section className="content-page activity-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">TRASPARENZA</div>
                  <h1>Attività tecnica</h1>
                  <p>
                    Attività recenti della sessione e tracce tecniche persistenti
                    delle esecuzioni di Cora.
                  </p>
                </div>
                <span className="pill">Percorsi e prove di esecuzione</span>
              </div>
              <div className="activity-layout">
                <RuntimePanel />
                <details className="activity-secondary"><summary>Registro Libreria e richieste della sessione</summary>
                <LibraryMonitorFeed />
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
                </details>
                <details className="activity-secondary"><summary>Archivio tecnico delle tracce</summary><ArchitectureRuntime showGraph={false} showTraces /></details>
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
            <section className="content-page settings-page">
              <div className="settings-hero">
                <div>
                  <div className="eyebrow">CONFIGURAZIONE</div>
                  <h1>Impostazioni</h1>
                  <p>Come si comporta Cora. Stato e manutenzione del server sono in Sistema.</p>
                </div>
                <button className="solid-button" disabled={backend.checking} onClick={() => void backend.refresh()}>
                  <RefreshCw size={15}/> Aggiorna stato
                </button>
              </div>

              <nav className="settings-tabs" role="tablist" aria-label="Sezioni delle impostazioni">
                {SETTINGS_TABS.map(t => <button key={t.id} role="tab" aria-selected={settingsTab === t.id}
                  className={settingsTab === t.id ? "active" : ""} onClick={() => navigate("settings", t.id)}>{t.label}</button>)}
              </nav>

              {settingsTab === "generale" && <>
                <div className="settings-status-strip">
                  <div><span>Backend</span><strong>{statusLabel}</strong></div>
                  <div><span>Runtime</span><strong>{backend.health?.runtime_mode === "server" ? "Server" : "Dev / isolato"}</strong></div>
                  <div><span>Modello centrale</span><strong>{backend.health?.model || "Non disponibile"}</strong></div>
                  <div><span>Macchina</span><strong>{backend.health?.model_machine || "Non verificata"}</strong></div>
                </div>
                <section className="section-card settings-panel settings-wide">
                  <div className="settings-section-head">
                    <div>
                      <span className="settings-kicker">ISTANZA</span>
                      <h2>Istanza Cora</h2>
                      <p>Connessione e modalità di esecuzione.</p>
                    </div>
                  </div>
                  <div className="settings-row">
                    <div><strong>Backend Cora</strong><p>{apiBaseUrl === "/backend" ? "Proxy locale verso FastAPI" : apiBaseUrl}</p></div>
                    <span className={"pill "+(backend.health?"success":"")}>{statusLabel}</span>
                  </div>
                  <div className="settings-row">
                    <div><strong>Modalità runtime</strong><p>{backend.health?.runtime_mode === "server" ? "Istanza server ufficiale" : "PC di prova con risorse server isolate"}</p></div>
                    <span className={"pill "+(backend.health?.runtime_mode==="server"?"success":"pending")}>{backend.health?.runtime_mode==="server"?"SERVER":"DEV"}</span>
                  </div>
                </section>
                <section className="section-card settings-panel settings-wide">
                  <RuntimeSettingsOverview />
                </section>
                <section className="section-card settings-panel settings-wide">
                  <div className="settings-section-head">
                    <div>
                      <span className="settings-kicker">SISTEMA</span>
                      <h2>Stato e manutenzione</h2>
                      <p>Non sono impostazioni: qui si controlla e si aggiorna il server.</p>
                    </div>
                  </div>
                  <div className="settings-link-grid">
                    <button onClick={()=>navigate("system", "aggiornamenti")}><strong>Sistema › Aggiornamenti</strong><span>Versione, updater e applicazioni gestite</span><ArrowRight size={16}/></button>
                    <button onClick={()=>navigate("system", "attivita")}><strong>Sistema › Attività tecnica</strong><span>Run, errori e tracce tecniche</span><ArrowRight size={16}/></button>
                  </div>
                </section>
              </>}

              {settingsTab === "modelli" && <section className="section-card settings-panel settings-wide">
                <div className="settings-section-head">
                  <div>
                    <span className="settings-kicker">IA</span>
                    <h2>Modello generale</h2>
                    <p>Fallback globale per gli agenti senza assegnazione specifica.</p>
                  </div>
                  <span className={"pill "+(backend.health?.ollama_online?"success":"pending")}>{backend.health?.ollama_online?"Provider raggiungibile":"Provider offline"}</span>
                </div>
                <ModelSettings onChanged={() => void backend.refresh()} />
                <div className="settings-link-grid">
                  <button onClick={()=>navigate("architecture")}><strong>Architettura</strong><span>Modelli e configurazione dei singoli agenti</span><ArrowRight size={16}/></button>
                  <button onClick={()=>navigate("system", "macchine")}><strong>Sistema › Macchine</strong><span>Worker, modelli installati e instradamento</span><ArrowRight size={16}/></button>
                </div>
              </section>}

              {settingsTab === "memoria" && <section className="section-card settings-panel settings-wide">
                <div className="settings-section-head">
                  <div>
                    <span className="settings-kicker">MEMORIA</span>
                    <h2>Contesto permanente</h2>
                    <p>Informazioni sul proprietario consultabili da Cora quando servono. Non vengono inserite automaticamente in ogni turno.</p>
                  </div>
                  <span className={"pill "+(contextUpdatedAt?"success":"pending")}>{contextUpdatedAt?"Salvato":"Non caricato"}</span>
                </div>
                <textarea className="settings-context-textarea" value={permanentContext} onChange={e=>setPermanentContext(e.target.value)} rows={6} placeholder="Poche frasi base comuni a Cora e agli agenti…"/>
                {contextError&&<div className="connection-error">{contextError}<button className="text-button" disabled={contextSaving} onClick={()=>void reloadPermanentContext()}>Ricarica salvato</button></div>}
                <div className="settings-memory-actions">
                  <small>{contextUpdatedAt?"Ultima modifica: "+new Date(contextUpdatedAt).toLocaleString("it-IT")+(contextVersion?" · v"+contextVersion:""):"Contesto non ancora caricato"}</small>
                  <button className="solid-button" disabled={!backend.health||contextSaving} onClick={()=>void savePermanentContext()}><Save size={15}/>{contextSaving?"Salvataggio…":"Salva"}</button>
                </div>
                <div className="settings-mini-stats">
                  <div><span>Memorie persistenti</span><strong>{backend.health?.memory?.total??0}</strong></div>
                  <div><span>Motore</span><strong>{backend.health?.memory?.available===false?"Non disponibile":"PostgreSQL + pgvector"}</strong></div>
                </div>
                <button className="settings-open-link" onClick={()=>navigate("memory-management")}><span><strong>Gestione Memoria</strong><small>Organizzazione, consultazione e manutenzione</small></span><ArrowRight size={17}/></button>
              </section>}

              {settingsTab === "account" && <section className="section-card settings-panel settings-wide">
                <div className="settings-section-head">
                  <div>
                    <span className="settings-kicker">ACCOUNT</span>
                    <h2>Account collegati</h2>
                    <p>Servizi esterni che Cora usa per conto tuo.</p>
                  </div>
                </div>
                <AccountsSettings onOpenMail={() => navigate("mail")} onOpenCalendar={() => navigate("calendar")} />
              </section>}

              {settingsTab === "notifiche" && <section className="section-card settings-panel settings-wide" id="settings-notifications">
                <div className="settings-section-head">
                  <div>
                    <span className="settings-kicker">NOTIFICHE</span>
                    <h2>Notifiche push</h2>
                    <p>Promemoria del calendario e avvisi di Cora su questo telefono o PC. Ogni dispositivo si attiva da sé.</p>
                  </div>
                </div>
                <PushSettings deviceLabel={mobileUi ? "Dispositivo mobile" : "Computer"} />
                <button className="settings-open-link" onClick={()=>navigate("notifications")}><span><strong>Notifiche</strong><small>Avvisi e decisioni in attesa</small></span><ArrowRight size={17}/></button>
              </section>}

              {settingsTab === "permessi" && <>
                <section className="section-card settings-panel settings-wide">
                  <div className="settings-section-head">
                    <div>
                      <span className="settings-kicker">ACCESSO</span>
                      <h2>Chi può aprire Cora</h2>
                    </div>
                  </div>
                  {authMode === "desktop" ? <p>Accesso locale automatico: richieste accettate soltanto dal computer che esegue Cora.</p> :
                   <p>Accesso automatico tramite Tailscale, senza password. Per togliere l'accesso a un dispositivo lo si revoca da Tailscale.</p>}
                </section>
                <section className="section-card settings-panel settings-wide">
                  <div className="settings-section-head">
                    <div>
                      <span className="settings-kicker">PERMESSI</span>
                      <h2>Permessi degli agenti per azione</h2>
                    </div>
                  </div>
                  <AgentPermissions />
                </section>
              </>}

              {settingsTab === "libreria" && <section className="section-card settings-panel settings-wide">
                <LibraryMonitorSettings />
                <button className="settings-open-link" onClick={()=>navigate("files")}><span><strong>File › Libreria IA</strong><small>Scegli le cartelle da tenere sotto controllo</small></span><ArrowRight size={17}/></button>
              </section>}
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

