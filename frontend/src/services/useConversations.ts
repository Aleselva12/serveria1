import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "../types/contracts";
import { api } from "./api";

export type Chat = {
  id: string;
  threadId: string;
  title: string;
  messages: (Message & { failed?: boolean })[];
  persisted: boolean;
};
function makeChat(): Chat {
  const id = crypto.randomUUID();
  return { id, threadId: id, title: "Nuova chat", messages: [], persisted: false };
}
const errorText = (error: unknown) => error instanceof Error ? error.message : "Storico non disponibile.";

export function useConversations(connected: boolean, sending: boolean) {
  const [chats, setChats] = useState<Chat[]>(() => [makeChat()]);
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
  const currentChat = chats.find(c => c.id === activeChat) || chats[0];

  const refreshHistory = useCallback(async () => {
    const request = ++listRequest.current;
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const saved = await api.conversations();
      if (!live.current || request !== listRequest.current) return;
      setChats(previous => {
        const ids = new Set(saved.map(c => c.id));
        // Keep unsent drafts, and preserve any in-flight optimistic messages.
        const drafts = previous.filter(c => !c.persisted && !ids.has(c.id));
        const rows = saved.map(c => ({
          id: c.id, threadId: c.id, title: c.title, persisted: true,
          messages: previous.find(p => p.id === c.id)?.messages || [],
        }));
        const merged = [...(touched.current || !rows.length ? drafts : drafts.filter(c => c.messages.length)), ...rows];
        return merged.length ? merged : [makeChat()];
      });
      if (!touched.current && saved.length) setActiveChat(saved[0].id);
      setMessageRevision(v => v + 1);
    } catch (error) {
      if (live.current && request === listRequest.current) setHistoryError(errorText(error));
    } finally {
      if (live.current && request === listRequest.current) setHistoryLoading(false);
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
    void api.conversationMessages(selectedId).then(rows => {
      if (!live.current || request !== messageRequest.current) return;
      setChats(previous => previous.map(c => c.id === selectedId ? {
        ...c,
        messages: rows.map(m => ({
          id: m.id, conversationId: m.conversation_id, role: m.role,
          content: m.content, createdAt: m.created_at, attachments: m.metadata?.attachments,
        })),
      } : c));
    }).catch(error => {
      if (live.current && request === messageRequest.current) setMessagesError(errorText(error));
    }).finally(() => {
      if (live.current && request === messageRequest.current) setMessagesLoading(false);
    });
    return () => { ++messageRequest.current; };
  }, [selectedId, persisted, connected, sending, messageRevision]);

  function selectChat(id: string) {
    touched.current = true;
    // Invalidate immediately, before the effect for the new selection runs.
    ++messageRequest.current;
    setActiveChat(id);
    setMessageRevision(v => v + 1);
    setMessagesError("");
    setMessagesLoading(chats.find(c => c.id === id)?.persisted || false);
  }
  function newChat() {
    touched.current = true;
    ++messageRequest.current;
    const chat = makeChat();
    setChats(previous => [chat, ...previous]);
    setActiveChat(chat.id);
    setMessagesLoading(false);
    setMessagesError("");
  }
  const updateChats: typeof setChats = action => { touched.current = true; setChats(action); };
  return { chats, setChats: updateChats, currentChat, selectChat, newChat, refreshHistory,
    historyLoading, historyError, messagesLoading, messagesError };
}

