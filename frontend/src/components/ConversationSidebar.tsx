import { useMemo, useState } from "react";
import {
  Folder,
  FolderPlus,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
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
  onDelete: (id: string) => Promise<void>;
  onMove: (id: string, projectId: string | null) => Promise<void>;
  onCreateProject: (name: string) => Promise<void>;
  onEditProject: (
    id: string,
    patch: { name?: string; shared_context?: string },
  ) => Promise<void>;
  onDeleteProject: (id: string) => Promise<void>;
};

export default function ConversationSidebar(props: Props) {
  const [openChat, setOpenChat] = useState("");
  const [openProject, setOpenProject] = useState("");
  const [search, setSearch] = useState("");
  const [renamingId, setRenamingId] = useState("");
  const [renameDraft, setRenameDraft] = useState("");
  const [projectMemory, setProjectMemory] =
    useState<ConversationProject | null>(null);
  const [projectMemoryDraft, setProjectMemoryDraft] = useState("");
  const [savingProjectMemory, setSavingProjectMemory] = useState(false);

  const visibleChats = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return props.chats;
    return props.chats.filter((chat) =>
      chat.title.toLowerCase().includes(query),
    );
  }, [props.chats, search]);

  const ungrouped = visibleChats.filter((chat) => !chat.projectId);

  function beginRename(chat: Chat) {
    setRenameDraft(chat.title);
    setRenamingId(chat.id);
    setOpenChat("");
  }

  async function commitRename(chat: Chat) {
    const title = renameDraft.trim();
    setRenamingId("");
    if (!title || title === chat.title) return;
    await props.onRename(chat.id, title);
  }

  async function remove(chat: Chat) {
    if (
      !window.confirm(
        `Eliminare definitivamente “${chat.title}”? Questa operazione non è reversibile.`,
      )
    )
      return;
    await props.onDelete(chat.id);
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

  function openProjectMemory(project: ConversationProject) {
    setProjectMemory(project);
    setProjectMemoryDraft(project.shared_context || "");
    setOpenProject("");
  }

  async function saveProjectMemory() {
    if (!projectMemory || savingProjectMemory) return;
    setSavingProjectMemory(true);
    try {
      await props.onEditProject(projectMemory.id, {
        shared_context: projectMemoryDraft,
      });
      setProjectMemory(null);
    } finally {
      setSavingProjectMemory(false);
    }
  }

  async function removeProject(project: ConversationProject) {
    if (
      !window.confirm(
        `Eliminare il progetto “${project.name}”? Le chat resteranno nello storico senza progetto.`,
      )
    )
      return;
    await props.onDeleteProject(project.id);
    setOpenProject("");
  }

  function row(chat: Chat) {
    return (
      <div
        className={"conversation-row " + (chat.id === props.currentId ? "active" : "")}
        key={chat.id}
        draggable={!props.disabled}
        onDragStart={(event) => {
          event.dataTransfer.setData("text/cora-chat-id", chat.id);
          event.dataTransfer.effectAllowed = "move";
        }}
      >
        {renamingId === chat.id ? (
          <input
            className="conversation-rename-input"
            autoFocus
            value={renameDraft}
            onChange={(event) => setRenameDraft(event.target.value)}
            onBlur={() => void commitRename(chat)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void commitRename(chat);
              if (event.key === "Escape") setRenamingId("");
            }}
          />
        ) : (
          <button
            className="conversation-open"
            disabled={props.disabled}
            onClick={() => props.onSelect(chat.id)}
            title={chat.title}
          >
            <span className="conversation-dot" />
            <span>{chat.title}</span>
          </button>
        )}

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
              <button onClick={() => beginRename(chat)}>
                <Pencil size={14} /> Rinomina
              </button>

              <div className="conversation-menu-subtitle">Sposta nel progetto</div>
              {props.projects.map((project) => (
                <button
                  key={project.id}
                  onClick={() =>
                    void props
                      .onMove(chat.id, project.id)
                      .then(() => setOpenChat(""))
                  }
                >
                  <Folder size={14} /> {project.name}
                </button>
              ))}

              {chat.projectId && (
                <button
                  onClick={() =>
                    void props.onMove(chat.id, null).then(() => setOpenChat(""))
                  }
                >
                  <Folder size={14} /> Rimuovi dal progetto
                </button>
              )}

              <button className="danger" onClick={() => void remove(chat)}>
                <Trash2 size={14} /> Elimina
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="conversation-sidebar-content">
        <button
          className="sidebar-new modern"
          disabled={props.disabled}
          onClick={() => props.onNew(null)}
        >
          <Plus size={16} /> Nuova chat
        </button>

        <label className="conversation-search">
          <Search size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Cerca chat"
          />
        </label>

        <div className="conversation-sidebar-toolbar">
          <span>Progetti</span>
          <div>
            <button title="Nuovo progetto" onClick={() => void createProject()}>
              <FolderPlus size={15} />
            </button>
            <button
              title="Aggiorna"
              disabled={props.loading}
              onClick={props.onRefresh}
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {props.error && (
          <div className="sidebar-history-error">{props.error}</div>
        )}

        {props.projects.map((project) => (
          <section
            className="conversation-project"
            key={project.id}
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
            }}
            onDrop={(event) => {
              event.preventDefault();
              const chatId = event.dataTransfer.getData("text/cora-chat-id");
              if (chatId) void props.onMove(chatId, project.id);
            }}
          >
            <div className="conversation-project-head">
              <button
                className="project-title"
                onClick={() => props.onNew(project.id)}
                title={"Nuova chat in " + project.name}
              >
                <Folder size={14} />
                <span>{project.name}</span>
                <small>{project.conversation_count}</small>
              </button>

              <div className="conversation-more-wrap">
                <button
                  className="conversation-more"
                  onClick={() =>
                    setOpenProject(openProject === project.id ? "" : project.id)
                  }
                  aria-label={"Azioni progetto " + project.name}
                >
                  <MoreHorizontal size={15} />
                </button>

                {openProject === project.id && (
                  <div className="conversation-menu project-menu">
                    <button onClick={() => void editProject(project)}>
                      <Pencil size={14} /> Rinomina progetto
                    </button>
                    <button onClick={() => openProjectMemory(project)}>
                      <Folder size={14} /> Memoria condivisa
                    </button>
                    <button
                      className="danger"
                      onClick={() => void removeProject(project)}
                    >
                      <Trash2 size={14} /> Elimina progetto
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="conversation-project-list">
              {visibleChats
                .filter((chat) => chat.projectId === project.id)
                .map(row)}
            </div>
          </section>
        ))}

        <div className="conversation-section-label">Chat</div>
        <div
          className="conversation-list"
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
          }}
          onDrop={(event) => {
            event.preventDefault();
            const chatId = event.dataTransfer.getData("text/cora-chat-id");
            if (chatId) void props.onMove(chatId, null);
          }}
        >
          {ungrouped.map(row)}
        </div>
      </div>

      {projectMemory && (
        <div className="conversation-modal-shade" onMouseDown={() => setProjectMemory(null)}>
          <div
            className="conversation-modal"
            role="dialog"
            aria-modal="true"
            aria-label={"Memoria condivisa di " + projectMemory.name}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <small>PROGETTO</small>
                <h3>{projectMemory.name}</h3>
              </div>
              <button onClick={() => setProjectMemory(null)} aria-label="Chiudi">
                <X size={17} />
              </button>
            </header>

            <p>
              Questo contesto viene condiviso soltanto dalle conversazioni del
              progetto. Non modifica la memoria globale di Cora.
            </p>

            <textarea
              rows={10}
              value={projectMemoryDraft}
              onChange={(event) => setProjectMemoryDraft(event.target.value)}
              placeholder="Scrivi qui informazioni, regole e contesto condivisi dal progetto…"
            />

            <footer>
              <button onClick={() => setProjectMemory(null)}>Annulla</button>
              <button
                className="solid-button"
                disabled={savingProjectMemory}
                onClick={() => void saveProjectMemory()}
              >
                {savingProjectMemory ? "Salvataggio…" : "Salva memoria progetto"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
