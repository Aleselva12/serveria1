import { useEffect, useMemo, useState } from "react";
import {
  Bot,
  FileSearch,
  Mail,
  Mic2,
  Plus,
  Send,
  Server,
} from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

function StatusPill({ health }) {
  const online = health?.status === "ok";
  const ollama = health?.ollama_online;

  return (
    <div className="status-pill">
      <span className={online && ollama ? "status-dot online" : "status-dot"} />
      <span>
        {!online ? "Cora non raggiungibile" : ollama ? "Cora attiva" : "Cora attiva · Ollama offline"}
      </span>
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Ciao. Sono Cora. Dimmi cosa vuoi fare.",
    },
  ]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState(false);

  const agents = useMemo(
    () => [
      { icon: FileSearch, name: "Documenti", detail: "Ricerca e analisi locale" },
      { icon: Mic2, name: "Audio", detail: "Trascrizioni e conversazioni" },
      { icon: Mail, name: "Mail", detail: "Archivio, digest e preventivi" },
      { icon: Server, name: "Struttura", detail: "Architettura, stato e diagnosi" },
    ],
    []
  );

  useEffect(() => {
    let mounted = true;

    const loadHealth = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (!response.ok) throw new Error("health");
        const data = await response.json();
        if (mounted) setHealth(data);
      } catch {
        if (mounted) setHealth(null);
      }
    };

    loadHealth();
    const timer = setInterval(loadHealth, 5000);

    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const newChat = () => {
    setThreadId(crypto.randomUUID());
    setMessages([
      {
        role: "assistant",
        content: "Nuova conversazione. Come posso aiutarti?",
      },
    ]);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", content: text }]);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          thread_id: threadId,
        }),
      });

      if (!response.ok) throw new Error("Errore API");

      const data = await response.json();
      setThreadId(data.thread_id);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: data.response },
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "Non riesco a raggiungere il backend di Cora. Prova a riaprire AVVIO.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand">
            <div className="brand-mark">
              <Bot size={22} />
            </div>
            <div>
              <strong>Cora</strong>
              <span>local workspace</span>
            </div>
          </div>

          <button className="new-chat" onClick={newChat}>
            <Plus size={17} />
            Nuova chat
          </button>

          <div className="section-label">Agenti</div>
          <div className="agent-list">
            {agents.map(({ icon: Icon, name, detail }) => (
              <div className="agent-card" key={name}>
                <Icon size={18} />
                <div>
                  <strong>{name}</strong>
                  <span>{detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-footer">
          <StatusPill health={health} />
          <div className="model-line">
            <Server size={14} />
            {health?.model || "modello locale"}
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <h1>Cora</h1>
            <p>Un'unica interfaccia per i tuoi agenti locali.</p>
          </div>
        </header>

        <section className="conversation">
          <div className="messages">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message-row ${message.role === "user" ? "user" : "assistant"}`}
              >
                <div className="message-bubble">{message.content}</div>
              </div>
            ))}
            {busy && (
              <div className="message-row assistant">
                <div className="message-bubble thinking">Cora sta pensando…</div>
              </div>
            )}
          </div>

          <div className="composer-wrap">
            <div className="composer">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                placeholder="Scrivi a Cora..."
                rows={1}
              />
              <button onClick={send} disabled={busy || !input.trim()} aria-label="Invia">
                <Send size={18} />
              </button>
            </div>
            <span className="hint">Invio per mandare · Shift+Invio per andare a capo</span>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
