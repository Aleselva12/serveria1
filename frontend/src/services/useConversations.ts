import { useCallback, useEffect, useRef, useState } from "react";
import type { ConversationProject, Message } from "../types/contracts";
import { api } from "./api";

export type Chat = {
  id: string;
  threadId: string;
  title: string;
  projectId: string | null;
  messages: (Message & { failed?: boolean })[];
  persisted: boolean;
};

function makeChat(projectId: string | null = null): Chat {
  const id = crypto.randomUUID();
  return {
    id,
    threadId: id,
    title: "Nuova chat",
    projectId,
    messages: [],
    persisted: false,
  };
}

const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Storico non disponibile.";

export function useConversations(connected: boolean, sending: boolean) {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat()]);
  const [projects, setProjects] = useState<ConversationProject[]>([]);
  const [activeChat, setActiveChat] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState("");
  const [messageRevision, setMessageRevision] = useState(0);
  const touched = useRef(false);
  const live = useRef(false);
  const listRequest = useRef(0);
  const messageRequest = useRef(0);

  const currentChat = chats.find((c) => c.id === activeChat) || chats[0];

  const refreshHistory = useCallback(async () => {
    const request = ++listRequest.current;
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const saved = await api.conversations();
      if (!live.current || request !== listRequest.current) return;

      // Projects enrich the sidebar but must never make canonical chat history fail.
      // This also keeps the history compatible while backend/frontend versions
      // briefly differ during an update.
      if (typeof api.conversationProjects === "function") {
        void api
          .conversationProjects()
          .then((savedProjects) => {
            if (live.current && request === listRequest.current)
              setProjects(savedProjects);
          })
          .catch(() => {
            // Conversation history remains usable if project metadata is unavailable.
          });
      }
      setChats((previous) => {
        const ids = new Set(saved.map((c) => c.id));
        const drafts = previous.filter((c) => !c.persisted && !ids.has(c.id));
        const rows = saved.map((c) => ({
          id: c.id,
          threadId: c.id,
          title: c.title,
          projectId: c.project_id || null,
          persisted: true,
          messages: previous.find((p) => p.id === c.id)?.messages || [],
        }));
        const merged = [
          ...(touched.current || !rows.length
            ? drafts
            : drafts.filter((c) => c.messages.length)),
          ...rows,
        ];
        return merged.length ? merged : [makeChat()];
      });

      if (!touched.current && saved.length) setActiveChat(saved[0].id);
      setMessageRevision((v) => v + 1);
    } catch (error) {
      if (live.current && request === listRequest.current)
        setHistoryError(errorText(error));
    } finally {
      if (live.current && request === listRequest.current)
        setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      ++listRequest.current;
      ++messageRequest.current;
    };
  }, []);

  useEffect(() => {
    if (connected) void refreshHistory();
  }, [connected, refreshHistory]);

  const selectedId = currentChat.id;
  const persisted = currentChat.persisted;

  useEffect(() => {
    const request = ++messageRequest.current;
    setMessagesError("");
    if (!persisted || !connected || sending) {
      setMessagesLoading(false);
      return;
    }
    setMessagesLoading(true);
    void api
      .conversationMessages(selectedId)
      .then((rows) => {
        if (!live.current || request !== messageRequest.current) return;
        setChats((previous) =>
          previous.map((c) =>
            c.id === selectedId
              ? {
                  ...c,
                  messages: rows.map((m) => ({
                    id: m.id,
                    conversationId: m.conversation_id,
                    role: m.role,
                    content: m.content,
                    createdAt: m.created_at,
                    attachments: m.metadata?.attachments,
                  })),
                }
              : c,
          ),
        );
      })
      .catch((error) => {
        if (live.current && request === messageRequest.current)
          setMessagesError(errorText(error));
      })
      .finally(() => {
        if (live.current && request === messageRequest.current)
          setMessagesLoading(false);
      });

    return () => {
      ++messageRequest.current;
    };
  }, [selectedId, persisted, connected, sending, messageRevision]);

  function selectChat(id: string) {
    touched.current = true;
    ++messageRequest.current;
    setActiveChat(id);
    setMessageRevision((v) => v + 1);
    setMessagesError("");
    setMessagesLoading(chats.find((c) => c.id === id)?.persisted || false);
  }

  function newChat(projectId: string | null = null) {
    touched.current = true;
    ++messageRequest.current;
    const chat = makeChat(projectId);
    setChats((previous) => [chat, ...previous]);
    setActiveChat(chat.id);
    setMessagesLoading(false);
    setMessagesError("");
  }

  async function renameChat(id: string, title: string) {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    if (!chat.persisted) {
      setChats((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
      return;
    }
    const updated = await api.updateConversation(id, { title });
    setChats((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, title: updated.title } : c,
      ),
    );
  }

  async function archiveChat(id: string) {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    if (!chat.persisted) {
      setChats((prev) => prev.filter((c) => c.id !== id));
    } else {
      await api.updateConversation(id, { archived: true });
      setChats((prev) => prev.filter((c) => c.id !== id));
    }
    if (currentChat.id === id) {
      const next = chats.find((c) => c.id !== id);
      if (next) setActiveChat(next.id);
      else newChat();
    }
  }

  async function deleteChat(id: string) {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    if (chat.persisted) await api.deleteConversation(id);
    setChats((prev) => prev.filter((c) => c.id !== id));
    if (currentChat.id === id) {
      const next = chats.find((c) => c.id !== id);
      if (next) setActiveChat(next.id);
      else newChat();
    }
  }

  async function moveChat(id: string, projectId: string | null) {
    const chat = chats.find((c) => c.id === id);
    if (!chat) return;
    if (!chat.persisted) {
      setChats((prev) =>
        prev.map((c) => (c.id === id ? { ...c, projectId } : c)),
      );
      return;
    }
    const updated = await api.updateConversation(
      id,
      projectId ? { project_id: projectId } : { clear_project: true },
    );
    setChats((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, projectId: updated.project_id || null } : c,
      ),
    );
    void refreshHistory();
  }

  async function createProject(name: string, sharedContext = "") {
    await api.createConversationProject(name, sharedContext);
    await refreshHistory();
  }

  async function updateProject(
    id: string,
    patch: { name?: string; shared_context?: string },
  ) {
    await api.updateConversationProject(id, patch);
    await refreshHistory();
  }

  async function deleteProject(id: string) {
    await api.deleteConversationProject(id);
    await refreshHistory();
  }

  const updateChats: typeof setChats = (action) => {
    touched.current = true;
    setChats(action);
  };

  return {
    chats,
    projects,
    setChats: updateChats,
    currentChat,
    selectChat,
    newChat,
    refreshHistory,
    renameChat,
    archiveChat,
    deleteChat,
    moveChat,
    createProject,
    updateProject,
    deleteProject,
    historyLoading,
    historyError,
    messagesLoading,
    messagesError,
  };
}
