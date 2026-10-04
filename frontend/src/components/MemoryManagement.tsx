import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Brain,
  Clock3,
  Database,
  Layers3,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { api } from "../services/api";
import type {
  BackendRegistry,
  MemoryEpisode,
  PersistentMemory,
  WorkingMemoryState,
} from "../types/contracts";

type Props = {
  registry?: BackendRegistry | null;
  onBack: () => void;
};

export default function MemoryManagement({ registry, onBack }: Props) {
  const [semanticMemories, setSemanticMemories] = useState<PersistentMemory[]>([]);
  const [recentMemories, setRecentMemories] = useState<MemoryEpisode[]>([]);
  const [workingMemory, setWorkingMemory] = useState<WorkingMemoryState[]>([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryType, setMemoryType] = useState("note");
  const [assertion, setAssertion] = useState<PersistentMemory["assertion"]>("user_statement");
  const [confidence, setConfidence] = useState("");
  const [expiry, setExpiry] = useState("");
  const [editing, setEditing] = useState<PersistentMemory | null>(null);
  const [history, setHistory] = useState<{id:string; rows:{version:number; snapshot:PersistentMemory; editor:string; created_at:string}[]} | null>(null);
  const [search, setSearch] = useState("");
  const [includeExpired,setIncludeExpired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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

  async function refreshAll(query = search) {
    setLoading(true);
    setError("");
    try {
      const [memories, episodes, working] = await Promise.all([
        api.memories(query, "", 100,includeExpired),
        api.episodes(50),
        api.workingMemory(),
      ]);
      setSemanticMemories(memories);
      setRecentMemories(episodes);
      setWorkingMemory(working);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Memoria non raggiungibile.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll("");
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void api
        .memories(search, "", 100,includeExpired)
        .then(setSemanticMemories)
        .catch((err) =>
          setError(
            err instanceof Error ? err.message : "Ricerca memoria non riuscita.",
          ),
        );
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search,includeExpired]);

  async function addSemanticMemory() {
    const content = memoryDraft.trim();
    const title = memoryTitle.trim();
    if (!content || saving) return;
    setSaving(true);
    setError("");
    try {
      await api.saveMemory({
        memory_type: memoryType,
        key: title || "manual-" + crypto.randomUUID(),
        content,
        source: "user_explicit",
        importance: 4,
        assertion,
        confidence:confidence === "" ? null : Number(confidence),
        expires_at:expiry ? new Date(expiry).toISOString() : null,
        expected_version:editing?.version ?? 0,
      });
      setMemoryDraft("");
      setMemoryTitle("");
      setEditing(null); setConfidence(""); setExpiry("");
      await refreshAll(search);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Salvataggio non riuscito.");
    } finally {
      setSaving(false);
    }
  }

  function editMemory(memory:PersistentMemory) {
    setEditing(memory); setMemoryTitle(memory.key); setMemoryDraft(memory.content);
    setMemoryType(memory.memory_type); setAssertion(memory.assertion);
    setConfidence(memory.confidence === null ? "" : String(memory.confidence));
    setExpiry(memory.expires_at ? new Date(new Date(memory.expires_at).getTime()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16) : "");
  }

  async function showHistory(memory:PersistentMemory) {
    try { setHistory({id:memory.id, rows:await api.memoryHistory(memory.id)}); }
    catch(err) { setError(err instanceof Error ? err.message : "Storico non disponibile."); }
  }

  async function removeMemory(id: string) {
    setError("");
    try {
      await api.deleteMemory(id);
      await refreshAll(search);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eliminazione non riuscita.");
    }
  }

  async function clearAgentWorkingMemory(agentId: string, threadId: string) {
    setError("");
    try {
      await api.clearWorkingMemory(agentId, threadId);
      setWorkingMemory(await api.workingMemory());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pulizia memoria non riuscita.");
    }
  }

  return (
    <section className="memory-page">
      <div className="page-heading memory-heading">
        <div>
          <div className="eyebrow">REGISTRO MEMORIA</div>
          <h1>Gestione Memoria</h1>
          <p>
            Memoria semantica, memoria episodica, provenienza e memoria di
            lavoro degli agenti.
          </p>
        </div>
        <button className="text-button" onClick={onBack}>
          <ArrowLeft size={16} /> Torna alle impostazioni
        </button>
      </div>

      <div className="memory-backend-note connected">
        <Database size={16} />
        <div>
          <strong>PostgreSQL + pgvector</strong>
          <span>
            Le memorie mostrate in questa pagina provengono dal backend reale di Cora.
          </span>
        </div>
        <button
          className="text-button"
          disabled={loading}
          onClick={() => void refreshAll()}
        >
          <RefreshCw size={14} /> Aggiorna
        </button>
      </div>

      {error && <div className="connection-error">{error}</div>}

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
                Conoscenze persistenti recuperabili semanticamente e modificabili
                dall’utente.
              </p>
            </div>
          </div>

          <div className="memory-toolbar">
            <label><input type="checkbox" checked={includeExpired} onChange={event=>setIncludeExpired(event.target.checked)} /> Mostra anche le scadute</label>
            <label className="memory-search">
              <Search size={15} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Ricerca semantica nelle memorie…"
              />
            </label>
          </div>

          <div className="manual-memory-form">
            <div className="manual-memory-row">
              <input
                value={memoryTitle}
                onChange={(event) => setMemoryTitle(event.target.value)}
                placeholder="Chiave / titolo breve"
                disabled={!!editing}
              />
              <select
                value={memoryType}
                onChange={(event) => setMemoryType(event.target.value)}
                disabled={!!editing}
              >
                <option value="fact">Fatto</option>
                <option value="preference">Preferenza</option>
                <option value="person">Persona</option>
                <option value="project">Progetto</option>
                <option value="decision">Decisione</option>
                <option value="note">Nota</option>
                <option value="task_context">Contesto task</option>
              </select>
            </div>
            <div className="manual-memory-row">
              <select aria-label="Natura della memoria" value={assertion} onChange={event=>setAssertion(event.target.value as PersistentMemory["assertion"])}>
                <option value="user_statement">Affermazione dell'utente</option>
                <option value="observation">Osservazione</option>
                <option value="inference">Deduzione / ipotesi</option>
                <option value="unclassified">Non classificata</option>
              </select>
              <input aria-label="Confidenza da 0 a 1" type="number" min="0" max="1" step="0.05" placeholder="Confidenza (0–1), facoltativa" value={confidence} onChange={event=>setConfidence(event.target.value)} />
            </div>
            <label>Scadenza facoltativa <input type="datetime-local" value={expiry} onChange={event=>setExpiry(event.target.value)} /></label>
            <textarea
              value={memoryDraft}
              onChange={(event) => setMemoryDraft(event.target.value)}
              rows={3}
              placeholder="Aggiungi manualmente una memoria importante…"
            />
            <button
              className="memory-add-button"
              onClick={() => void addSemanticMemory()}
              disabled={!memoryDraft.trim() || saving}
            >
              <Plus size={15} /> {saving ? "Salvataggio…" : editing ? `Salva versione ${editing.version+1}` : "Aggiungi memoria"}
            </button>
            {editing && <button className="text-button" onClick={()=>{setEditing(null);setMemoryTitle("");setMemoryDraft("");setConfidence("");setExpiry("");}}>Annulla modifica</button>}
            <small>La confidenza è dichiarata dall'autore, non una probabilità verificata. Le deduzioni restano ipotesi.</small>
          </div>

          <div className="memory-list">
            {loading && semanticMemories.length === 0 ? (
              <p className="muted">Caricamento memorie…</p>
            ) : semanticMemories.length === 0 ? (
              <p className="muted">Nessuna memoria trovata.</p>
            ) : (
              semanticMemories.map((memory) => (
                <article className="memory-entry" key={memory.id}>
                  <div className="memory-entry-top">
                    <strong>{memory.key}</strong>
                    <div className="memory-entry-actions">
                      <span>{memory.memory_type}</span>
                      <button onClick={()=>editMemory(memory)}>Modifica</button>
                      <button onClick={()=>void showHistory(memory)}>Versioni</button>
                      <button
                        aria-label="Elimina memoria"
                        title="Elimina memoria"
                        onClick={() => void removeMemory(memory.id)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                  <p>{memory.content}</p>
                  <small>
                    {memory.assertion === 'inference' ? 'Ipotesi' : memory.assertion === 'observation' ? 'Osservazione' : memory.assertion === 'user_statement' ? "Affermazione utente" : 'Non classificata'} · v{memory.version} · {memory.source} · confidenza {memory.confidence ?? 'non indicata'} · importanza {memory.importance} ·{" "}
                    {new Date(memory.updated_at).toLocaleString("it-IT")}
                  </small>
                  {!!memory.metadata.source_ref && <small>Riferimento: {String(memory.metadata.source_ref)}</small>}
                  {memory.expires_at && <small>Scade: {new Date(memory.expires_at).toLocaleString('it-IT')}</small>}
                  {history?.id === memory.id && <div>
                    <button className="text-button" onClick={()=>setHistory(null)}>Chiudi storico</button>
                    {history.rows.map(row=><div key={row.version}><small>v{row.version} · {row.editor} · {new Date(row.created_at).toLocaleString('it-IT')}</small><p>{row.snapshot.content}</p><small>{row.snapshot.assertion} · confidenza {row.snapshot.confidence ?? 'non indicata'}</small></div>)}
                  </div>}
                </article>
              ))
            )}
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
                Brevi resoconti append-only degli ultimi avvenimenti significativi.
              </p>
            </div>
          </div>

          <div className="episodic-timeline">
            {recentMemories.length === 0 ? (
              <p className="muted">Nessun episodio registrato.</p>
            ) : (
              recentMemories.map((memory) => (
                <article className="episodic-entry" key={memory.id}>
                  <div className="episodic-marker" />
                  <div>
                    <div className="episodic-title">
                      <strong>{memory.title}</strong>
                      <span>
                        {new Date(memory.created_at).toLocaleString("it-IT")}
                      </span>
                    </div>
                    <p>{memory.summary}</p>
                    <small>{memory.episode_type}</small>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="memory-system-note">
            <Clock3 size={15} />
            <span>
              I turni chat completati generano automaticamente un breve episodio.
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
              Stato temporaneo per agente. Scade automaticamente e non viene
              trattato come conoscenza permanente.
            </p>
          </div>
          <span className="memory-scope">Per agente</span>
        </div>

        <div className="working-agent-grid">
          {agents.map((agent) => {
            const states = workingMemory.filter(
              (item) => item.agent_id === agent.id,
            );
            const latest = states[0];
            return (
              <article className="working-agent-card" key={agent.id}>
                <div className="working-agent-top">
                  <span className="agent-memory-dot" />
                  <strong>{agent.name}</strong>
                  <span className="working-agent-status">
                    {latest ? "Memoria attiva" : "Vuota"}
                  </span>
                </div>
                <div className="working-memory-placeholder">
                  {latest ? (
                    <>
                      <span>Thread {latest.thread_id}</span>
                      <strong>
                        {String(latest.state.status || "Contesto disponibile")}
                      </strong>
                      <small>
                        {String(
                          latest.state.current_request ||
                            latest.state.last_response ||
                            "Stato operativo disponibile.",
                        ).slice(0, 260)}
                      </small>
                      <small>
                        Aggiornata:{" "}
                        {new Date(latest.updated_at).toLocaleString("it-IT")}
                      </small>
                      <button
                        className="text-button working-clear"
                        onClick={() =>
                          void clearAgentWorkingMemory(
                            latest.agent_id,
                            latest.thread_id,
                          )
                        }
                      >
                        Azzera memoria di lavoro
                      </button>
                    </>
                  ) : (
                    <>
                      <span>Memoria di lavoro</span>
                      <strong>Nessun contesto attivo</strong>
                      <small>
                        Verrà popolata durante l’esecuzione dell’agente.
                      </small>
                    </>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </section>
  );
}
