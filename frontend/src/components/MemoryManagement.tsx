import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Brain,
  Clock3,
  Database,
  Layers3,
  Plus,
  Save,
  Search,
  Sparkles,
} from "lucide-react";
import type { BackendRegistry } from "../types/contracts";

type Props = {
  registry?: BackendRegistry | null;
  onBack: () => void;
};

type SemanticMemory = {
  id: string;
  title: string;
  content: string;
  type: string;
  source: string;
};

type RecentMemory = {
  id: string;
  title: string;
  summary: string;
  time: string;
};

const initialSemantic: SemanticMemory[] = [
  {
    id: "sem-1",
    title: "Preferenza architetturale",
    content:
      "Per compiti semplici e ripetitivi preferire strumenti deterministici o modelli specialistici agli LLM generalisti.",
    type: "Preferenza",
    source: "Esempio frontend",
  },
  {
    id: "sem-2",
    title: "Architettura chat",
    content:
      "La chat entra dall’agente centrale di Cora, che per ora svolge anche il ruolo di orchestratore.",
    type: "Decisione",
    source: "Esempio frontend",
  },
];

const initialRecent: RecentMemory[] = [
  {
    id: "recent-1",
    title: "Ultima sessione",
    summary:
      "Definita la persistenza con PostgreSQL + pgvector, transcript Markdown, log e metadata.",
    time: "Resoconto di esempio",
  },
  {
    id: "recent-2",
    title: "Sessione precedente",
    summary:
      "La chat è stata collegata all’agente centrale di Cora e separata concettualmente dal futuro orchestratore.",
    time: "Resoconto di esempio",
  },
];

export default function MemoryManagement({ registry, onBack }: Props) {
  const [persistentContext, setPersistentContext] = useState(
    "Sei Cora, assistente locale del server.\nPreferisci dati verificabili e descrivi chiaramente cosa hai realmente fatto.\nUsa strumenti locali quando sono sufficienti e non inventare risultati.",
  );
  const [semanticMemories, setSemanticMemories] =
    useState<SemanticMemory[]>(initialSemantic);
  const [recentMemories] = useState<RecentMemory[]>(initialRecent);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [search, setSearch] = useState("");

  const agents = useMemo(() => {
    const fromRegistry =
      registry?.components
        .filter(
          (component) =>
            component.kind === "agent" || component.id === "supervisor",
        )
        .map((component) => ({
          id: component.id,
          name: component.name,
          available: component.available,
        })) || [];

    if (fromRegistry.length) return fromRegistry;

    return [
      { id: "supervisor", name: "Cora · Agente centrale", available: false },
      { id: "local_research_agent", name: "Local Research Agent", available: false },
      { id: "audio_agent", name: "Audio Agent", available: false },
      { id: "email_quotes_agent", name: "Email & Quotes Agent", available: false },
      { id: "structure_agent", name: "Structure Agent", available: false },
    ];
  }, [registry]);

  const visibleSemantic = semanticMemories.filter((memory) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return (
      memory.title.toLowerCase().includes(query) ||
      memory.content.toLowerCase().includes(query) ||
      memory.type.toLowerCase().includes(query)
    );
  });

  function addSemanticMemory() {
    const content = memoryDraft.trim();
    const title = memoryTitle.trim();
    if (!content) return;
    setSemanticMemories((current) => [
      {
        id: crypto.randomUUID(),
        title: title || "Memoria inserita manualmente",
        content,
        type: "Manuale",
        source: "Utente · solo frontend",
      },
      ...current,
    ]);
    setMemoryDraft("");
    setMemoryTitle("");
  }

  return (
    <section className="memory-page">
      <div className="page-heading memory-heading">
        <div>
          <div className="eyebrow">REGISTRO MEMORIA</div>
          <h1>Gestione Memoria</h1>
          <p>
            Contesto comune, memoria semantica, memoria episodica e memoria di
            lavoro degli agenti.
          </p>
        </div>
        <button className="text-button" onClick={onBack}>
          <ArrowLeft size={16} /> Torna alle impostazioni
        </button>
      </div>

      <div className="memory-backend-note">
        <Database size={16} />
        <div>
          <strong>Interfaccia pronta · backend da collegare</strong>
          <span>
            I dati modificati in questa pagina restano locali alla sessione del
            frontend finché non collegheremo PostgreSQL + pgvector.
          </span>
        </div>
      </div>

      <section className="memory-card memory-context-card">
        <div className="memory-card-head">
          <div className="memory-card-icon">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="memory-kicker">BASE COMUNE</div>
            <h2>Contesto persistente</h2>
            <p>
              Poche frasi fondamentali caricate come contesto di base e comuni a
              tutti i modelli.
            </p>
          </div>
          <span className="memory-scope">Tutti i modelli</span>
        </div>
        <textarea
          className="persistent-context-input"
          value={persistentContext}
          onChange={(event) => setPersistentContext(event.target.value)}
          rows={6}
          placeholder="Scrivi qui le frasi base comuni a Cora e agli agenti…"
        />
        <div className="memory-card-footer">
          <span>{persistentContext.trim().split(/\n+/).filter(Boolean).length} frasi</span>
          <button className="solid-button" disabled>
            <Save size={15} /> Salva nel backend
          </button>
        </div>
      </section>

      <div className="memory-grid">
        <section className="memory-card semantic-memory-card">
          <div className="memory-card-head compact">
            <div className="memory-card-icon">
              <Brain size={18} />
            </div>
            <div>
              <div className="memory-kicker">MEMORIA SEMANTICA</div>
              <h2>Memorie importanti</h2>
              <p>
                Informazioni utili e durevoli selezionate dall’IA o inserite
                manualmente dall’utente.
              </p>
            </div>
          </div>

          <div className="memory-toolbar">
            <label className="memory-search">
              <Search size={15} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Cerca nelle memorie…"
              />
            </label>
          </div>

          <div className="manual-memory-form">
            <input
              value={memoryTitle}
              onChange={(event) => setMemoryTitle(event.target.value)}
              placeholder="Titolo breve"
            />
            <textarea
              value={memoryDraft}
              onChange={(event) => setMemoryDraft(event.target.value)}
              rows={3}
              placeholder="Aggiungi manualmente una memoria importante…"
            />
            <button
              className="memory-add-button"
              onClick={addSemanticMemory}
              disabled={!memoryDraft.trim()}
            >
              <Plus size={15} /> Aggiungi memoria
            </button>
          </div>

          <div className="memory-list">
            {visibleSemantic.map((memory) => (
              <article className="memory-entry" key={memory.id}>
                <div className="memory-entry-top">
                  <strong>{memory.title}</strong>
                  <span>{memory.type}</span>
                </div>
                <p>{memory.content}</p>
                <small>{memory.source}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="memory-card recent-memory-card">
          <div className="memory-card-head compact">
            <div className="memory-card-icon">
              <Clock3 size={18} />
            </div>
            <div>
              <div className="memory-kicker">MEMORIA EPISODICA</div>
              <h2>Memorie recenti</h2>
              <p>
                Brevi resoconti di ciò che è successo, salvati dal sistema come
                piccoli commit della continuità operativa.
              </p>
            </div>
          </div>

          <div className="episodic-timeline">
            {recentMemories.map((memory) => (
              <article className="episodic-entry" key={memory.id}>
                <div className="episodic-marker" />
                <div>
                  <div className="episodic-title">
                    <strong>{memory.title}</strong>
                    <span>{memory.time}</span>
                  </div>
                  <p>{memory.summary}</p>
                </div>
              </article>
            ))}
          </div>

          <div className="memory-system-note">
            <Clock3 size={15} />
            <span>
              Questa sezione sarà alimentata automaticamente dal sistema.
            </span>
          </div>
        </section>
      </div>

      <section className="memory-card working-memory-card">
        <div className="memory-card-head">
          <div className="memory-card-icon">
            <Layers3 size={18} />
          </div>
          <div>
            <div className="memory-kicker">CONTESTO OPERATIVO</div>
            <h2>Memoria di lavoro</h2>
            <p>
              Ogni agente dispone di uno spazio temporaneo per obiettivi,
              contesto corrente, risultati intermedi e passaggi di consegne.
            </p>
          </div>
          <span className="memory-scope">Per agente</span>
        </div>

        <div className="working-agent-grid">
          {agents.map((agent) => (
            <article className="working-agent-card" key={agent.id}>
              <div className="working-agent-top">
                <span className="agent-memory-dot" />
                <strong>{agent.name}</strong>
                <span className="working-agent-status">
                  {agent.available ? "Disponibile" : "Da collegare"}
                </span>
              </div>
              <div className="working-memory-placeholder">
                <span>Memoria di lavoro</span>
                <strong>Contesto corrente non disponibile</strong>
                <small>
                  Qui vedremo task attivo, ultimi risultati, handoff e riferimenti
                  alle memorie persistenti.
                </small>
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
