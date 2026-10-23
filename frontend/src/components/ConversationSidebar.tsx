import { useState } from "react";
import {
  Archive,
  Folder,
  FolderPlus,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import type { ConversationProject } from "../types/contracts";
import type { Chat } from "../services/useConversations";

type Props = {
  chats: Chat[];
  projects: ConversationProject[];
  currentId: string;
  disabled: boolean;
  loading: boolean;
  error: string;
  onNew: (projectId?: string | null) => void;
  onRefresh: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onArchive: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onMove: (id: string, projectId: string | null) => Promise<void>;
  onCreateProject: (name: string) => Promise<void>;
  onEditProject: (id: string, patch: { name?: string; shared_context?: string }) => Promise<void>;
  onDeleteProject: (id: string) => Promise<void>;
};

export default function ConversationSidebar(props: Props) {
  const [openChat, setOpenChat] = useState("");
  const [openProject, setOpenProject] = useState("");
  const ungrouped = props.chats.filter((chat) => !chat.projectId);

  async function rename(chat: Chat) {
    const title = window.prompt("Nuovo nome della conversazione", chat.title)?.trim();
    if (title) await props.onRename(chat.id, title);
    setOpenChat("");
  }

  async function remove(chat: Chat) {
    if (!window.confirm(`Eliminare definitivamente “${chat.title}”? Questa operazione non è reversibile.`)) return;
    await props.onDelete(chat.id);
    setOpenChat("");
  }

  async function archive(chat: Chat) {
    await props.onArchive(chat.id);
    setOpenChat("");
  }

  async function createProject() {
    const name = window.prompt("Nome del nuovo progetto")?.trim();
    if (name) await props.onCreateProject(name);
  }

  async function editProject(project: ConversationProject) {
    const name = window.prompt("Nome del progetto", project.name)?.trim();
    if (name) await props.onEditProject(project.id, { name });
    setOpenProject("");
  }

  async function editProjectMemory(project: ConversationProject) {
    const shared = window.prompt(
      "Contesto / memoria condivisa del progetto",
      project.shared_context || "",
    );
    if (shared !== null)
      await props.onEditProject(project.id, { shared_context: shared });
    setOpenProject("");
  }

  async function removeProject(project: ConversationProject) {
    if (!window.confirm(`Eliminare il progetto “${project.name}”? Le chat resteranno nello storico senza progetto.`)) return;
    await props.onDeleteProject(project.id);
    setOpenProject("");
  }

  function row(chat: Chat) {
    return (
      <div className={"conversation-row " + (chat.id === props.currentId ? "active" : "")} key={chat.id}>
        <button
          className="conversation-open"
          disabled={props.disabled}
          onClick={() => props.onSelect(chat.id)}
          title={chat.title}
        >
          <span className="conversation-dot" />
          <span>{chat.title}</span>
        </button>
        <div className="conversation-more-wrap">
          <button
            className="conversation-more"
            aria-label={"Azioni per " + chat.title}
            onClick={() => setOpenChat(openChat === chat.id ? "" : chat.id)}
          >
            <MoreHorizontal size={15} />
          </button>
          {openChat === chat.id && (
            <div className="conversation-menu">
              <button onClick={() => void rename(chat)}><Pencil size={14} /> Rinomina</button>
              <div className="conversation-menu-subtitle">Sposta nel progetto</div>
              {props.projects.map((project) => (
                <button key={project.id} onClick={() => void props.onMove(chat.id, project.id).then(() => setOpenChat(""))}>
                  <Folder size={14} /> {project.name}
                </button>
              ))}
              {chat.projectId && (
                <button onClick={() => void props.onMove(chat.id, null).then(() => setOpenChat(""))}>
                  <Folder size={14} /> Rimuovi dal progetto
                </button>
              )}
              <button onClick={() => void archive(chat)}><Archive size={14} /> Archivia</button>
              <button className="danger" onClick={() => void remove(chat)}><Trash2 size={14} /> Elimina</button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="conversation-sidebar-content">
      <button className="sidebar-new modern" disabled={props.disabled} onClick={() => props.onNew(null)}>
        <Plus size={16} /> Nuova chat
      </button>

      <div className="conversation-sidebar-toolbar">
        <span>Conversazioni</span>
        <div>
          <button title="Nuovo progetto" onClick={() => void createProject()}><FolderPlus size={15} /></button>
          <button title="Aggiorna" disabled={props.loading} onClick={props.onRefresh}><RefreshCw size={14} /></button>
        </div>
      </div>

      {props.error && <div className="sidebar-history-error">{props.error}</div>}

      {props.projects.map((project) => (
        <section className="conversation-project" key={project.id}>
          <div className="conversation-project-head">
            <button className="project-title" onClick={() => props.onNew(project.id)}>
              <Folder size={14} />
              <span>{project.name}</span>
              <small>{project.conversation_count}</small>
            </button>
            <div className="conversation-more-wrap">
              <button className="conversation-more" onClick={() => setOpenProject(openProject === project.id ? "" : project.id)}>
                <MoreHorizontal size={15} />
              </button>
              {openProject === project.id && (
                <div className="conversation-menu project-menu">
                  <button onClick={() => void editProject(project)}><Pencil size={14} /> Rinomina progetto</button>
                  <button onClick={() => void editProjectMemory(project)}><Folder size={14} /> Memoria condivisa</button>
                  <button className="danger" onClick={() => void removeProject(project)}><Trash2 size={14} /> Elimina progetto</button>
                </div>
              )}
            </div>
          </div>
          <div className="conversation-project-list">
            {props.chats.filter((chat) => chat.projectId === project.id).map(row)}
          </div>
        </section>
      ))}

      <div className="conversation-section-label">Chat</div>
      <div className="conversation-list">
        {ungrouped.map(row)}
      </div>
    </div>
  );
}
