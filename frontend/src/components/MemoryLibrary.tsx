import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, api } from "../services/api";
import type {
  EvidenceRun, MemoryCard, MemoryCardSummary, MemoryDocument, RunEvidence,
} from "../types/memoryLibrary";

const emptyDocument: MemoryDocument = {
  title: "", description: "", content: "", kind: "note", assertion: "user_statement",
  state: "draft", source_runs: [], relations: [], valid_from: null, valid_until: null,
};

const kinds = { note: "Nota", entity: "Entità", fact: "Fatto", decision: "Decisione", brief: "Memoria breve" };
const states = { draft: "Bozza", approved: "Approvata", archived: "Archiviata" };
const assertions = { user_statement: "Dichiarazione", observation: "Osservazione", inference: "Deduzione" };
const relationKinds = {
  relates_to: "Collegata a", depends_on: "Dipende da",
  contradicts: "Contraddice", supersedes: "Sostituisce",
};
type RelationKind = keyof typeof relationKinds;

function dateInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export default function MemoryLibrary() {
  const [scopes, setScopes] = useState<string[]>([]);
  const [scope, setScope] = useState("global");
  const [query, setQuery] = useState("");
  const [cards, setCards] = useState<MemoryCardSummary[]>([]);
  const [search, setSearch] = useState({ scope: "global", query: "" });
  const [moreCards, setMoreCards] = useState(false);
  const [card, setCard] = useState<MemoryCard | null>(null);
  const [revision, setRevision] = useState<MemoryCard | null>(null);
  const [document, setDocument] = useState<MemoryDocument | null>(null);
  const [slug, setSlug] = useState("");
  const [draftScope, setDraftScope] = useState("global");
  const [runs, setRuns] = useState<EvidenceRun[]>([]);
  const [runId, setRunId] = useState("");
  const [evidence, setEvidence] = useState<RunEvidence | null>(null);
  const [moreEvents, setMoreEvents] = useState(false);
  const [relationKind, setRelationKind] = useState<RelationKind>("relates_to");
  const [relationTarget, setRelationTarget] = useState("");
  const [sourceRun, setSourceRun] = useState("");
  const [starterFile, setStarterFile] = useState<File | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409
        ? "Scheda già esistente o versione superata. Riapri la scheda e verifica la versione corrente."
        : err instanceof Error ? err.message : "Operazione non riuscita.");
    } finally {
      setBusy(false);
    }
  }

  async function loadCards(selectedScope: string, text: string, after = "") {
    const found = await api.memoryLibrary(selectedScope, text, after);
    setCards(previous => after ? [...previous, ...found] : found);
    setMoreCards(found.length === 50);
    setSearch({ scope: selectedScope, query: text });
  }

  useEffect(() => {
    void perform(async () => {
      const [knownScopes, recent] = await Promise.all([
        api.memoryLibraryScopes(), api.memoryEvidenceRuns(),
      ]);
      setScopes(knownScopes);
      setRuns(recent);
      await loadCards("global", "");
    });
  }, []);

  async function openCard(id: string) {
    setCard(await api.memoryLibraryCard(id));
    setRevision(null);
    setDocument(null);
  }

  async function showEvidence(id: string, after = 0) {
    const page = await api.memoryEvidence(id, after);
    setEvidence(previous => ({
      ...page,
      events: after && previous?.run_id === page.run_id ? [...previous.events, ...page.events] : page.events,
    }));
    setRunId(id);
    setMoreEvents(page.events.length === 100);
  }

  function startDraft(source?: string) {
    setCard(null);
    setRevision(null);
    setSlug("");
    setDraftScope(search.scope);
    setDocument({ ...emptyDocument, source_runs: source ? [source] : [] });
  }

  async function saveCard(event: FormEvent) {
    event.preventDefault();
    if (!document) return;
    await perform(async () => {
      const saved = await api.saveMemoryLibraryCard(document, card
        ? { id: card.id, version: card.version }
        : { scope: draftScope, slug: slug.trim() });
      setCard(saved);
      setDocument(null);
      setScopes(await api.memoryLibraryScopes());
      setScope(saved.scope);
      setQuery("");
      await loadCards(saved.scope, "");
      setNotice("Scheda salvata.");
    });
  }

  async function downloadScope() {
    const allCards: MemoryCard[] = [];
    let after = "";
    do {
      const page = await api.exportMemoryLibrary(search.scope, after);
      allCards.push(...page.cards);
      after = page.next_cursor ?? "";
    } while (after);
    const body = JSON.stringify({
      format: "serveria-memory-library-v1", scope: search.scope, cards: allCards,
    }, null, 2);
    const url = URL.createObjectURL(new Blob([body], { type: "application/json" }));
    const link = window.document.createElement("a");
    link.href = url;
    link.download = "serveria-memoria-" + search.scope.replaceAll("/", "-") + ".json";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function importStarter(file: File) {
    if (file.size > 1_000_000) throw new Error("Il file delle bozze supera 1 MB.");
    const imported = await api.importMemoryDrafts(JSON.parse(await file.text()));
    const firstScope = imported[0].scope;
    setStarterFile(null);
    setScopes(await api.memoryLibraryScopes());
    setScope(firstScope);
    setQuery("");
    await loadCards(firstScope, "");
    setNotice(`Importate ${imported.length} bozze da rivedere.`);
  }

  const shown = revision ?? card;

  return (
    <section className="memory-card memory-library" aria-busy={busy}>
      <h2>Biblioteca e registro delle esecuzioni</h2>
      {error && <div role="alert" className="connection-error">{error}</div>}
      {notice && <p role="status">{notice}</p>}
      <fieldset disabled={busy}>
        <legend>Biblioteca</legend>
        <form onSubmit={event => { event.preventDefault(); void perform(() => loadCards(scope, query)); }}>
          <label>Ambito <input value={scope} onChange={event => setScope(event.target.value)}
            list="memory-library-scopes" placeholder="azienda/progetto/attivita" required /></label>
          <datalist id="memory-library-scopes">
            {[...new Set(["global", ...scopes])].map(value => <option key={value} value={value} />)}
          </datalist>
          <label>Cerca <input value={query} onChange={event => setQuery(event.target.value)} maxLength={200} /></label>
          <button type="submit">Cerca schede</button>
        </form>
        <details>
          <summary>Ambiti disponibili</summary>
          <ul>{[...new Set(["global", ...scopes])].map(value => <li key={value}>
            <button onClick={() => void perform(async () => {
              setScope(value);
              setQuery("");
              await loadCards(value, "");
            })}>{value}</button>
          </li>)}</ul>
          {scopes.length >= 50 && <button onClick={() => void perform(async () => {
            const page = await api.memoryLibraryScopes(scopes.at(-1));
            setScopes(previous => [...previous, ...page]);
            if (!page.length) setNotice("Tutti gli ambiti sono già visibili.");
          })}>Altri ambiti</button>}
        </details>
        <p>Ambito consultato: {search.scope}</p>
        <button onClick={() => startDraft()}>Nuova scheda</button>
        <button onClick={() => void perform(downloadScope)}>Esporta schede approvate</button>
        <details>
          <summary>Importa bozze</summary>
          <label>File JSON <input type="file" accept=".json,application/json"
            onChange={event => setStarterFile(event.target.files?.[0] ?? null)} /></label>
          <button disabled={!starterFile} onClick={() => {
            if (starterFile) void perform(() => importStarter(starterFile));
          }}>Importa</button>
        </details>
        {cards.length ? <ul>{cards.map(item => (
          <li key={item.id}>
            <button onClick={() => void perform(() => openCard(item.id))}>{item.title}</button>
            {" · "}{states[item.state]} · {item.description}
          </li>
        ))}</ul> : <p>Nessuna scheda trovata.</p>}
        {moreCards && <button onClick={() => void perform(() =>
          loadCards(search.scope, search.query, cards.at(-1)?.slug))}>Altre schede</button>}

        {shown && <article>
          <h3>{shown.document.title}</h3>
          <p>{shown.scope} · {states[shown.document.state]} · {assertions[shown.document.assertion]} · v{shown.version}</p>
          <p>{shown.document.description}</p>
          <p>ID scheda <code>{shown.id}</code></p>
          <p style={{ whiteSpace: "pre-wrap" }}>{shown.document.content}</p>
          {shown.document.valid_from && <p>Valida dal {new Date(shown.document.valid_from).toLocaleString("it-IT")}</p>}
          {shown.document.valid_until && <p>Valida fino al {new Date(shown.document.valid_until).toLocaleString("it-IT")}</p>}
          {shown.document.source_runs.map(id => <button key={id}
            onClick={() => void perform(() => showEvidence(id))}>Fonte {id}</button>)}
          {shown.document.relations.map(item => <button key={item.kind + item.target_id}
            onClick={() => void perform(() => openCard(item.target_id))}>
            {relationKinds[item.kind]} {item.target_id}
          </button>)}
          {!revision && <button onClick={() => setDocument(shown.document)}>Modifica o revisiona</button>}
          {revision && <button onClick={() => setRevision(null)}>Versione corrente</button>}
          {shown.version > 1 && <button onClick={() => void perform(async () => {
            setRevision(await api.memoryLibraryCard(shown.id, shown.version - 1));
            setDocument(null);
          })}>Revisione precedente</button>}
        </article>}

        {document && <form onSubmit={saveCard}>
          <h3>{card ? "Revisione della scheda" : "Nuova scheda"}</h3>
          {!card && <>
            <label>Ambito <input value={draftScope} onChange={event => setDraftScope(event.target.value)} required /></label>
            <label>Chiave <input value={slug} onChange={event => setSlug(event.target.value)}
              placeholder="serveria2-decisione" pattern="[a-z0-9][a-z0-9_\\-]{0,59}" required /></label>
          </>}
          <label>Titolo <input value={document.title} maxLength={200}
            onChange={event => setDocument({ ...document, title: event.target.value })} required /></label>
          <label>Descrizione <input value={document.description} maxLength={500}
            onChange={event => setDocument({ ...document, description: event.target.value })} required /></label>
          <label>Contenuto <textarea value={document.content} maxLength={12_000}
            onChange={event => setDocument({ ...document, content: event.target.value })} required /></label>
          <label>Tipo <select value={document.kind}
            onChange={event => setDocument({ ...document, kind: event.target.value as MemoryDocument["kind"] })}>
            {Object.entries(kinds).map(([value, text]) => <option value={value} key={value}>{text}</option>)}
          </select></label>
          <label>Classificazione <select value={document.assertion}
            onChange={event => setDocument({ ...document, assertion: event.target.value as MemoryDocument["assertion"] })}>
            {Object.entries(assertions).map(([value, text]) => <option value={value} key={value}>{text}</option>)}
          </select></label>
          <label>Stato <select value={document.state}
            onChange={event => setDocument({ ...document, state: event.target.value as MemoryDocument["state"] })}>
            {Object.entries(states).map(([value, text]) => <option value={value} key={value}>{text}</option>)}
          </select></label>
          <label>Valida dal <input type="datetime-local" value={dateInput(document.valid_from)}
            onChange={event => setDocument({ ...document, valid_from: event.target.value ? new Date(event.target.value).toISOString() : null })} /></label>
          <label>Valida fino al <input type="datetime-local" value={dateInput(document.valid_until)}
            onChange={event => setDocument({ ...document, valid_until: event.target.value ? new Date(event.target.value).toISOString() : null })} /></label>
          <label>ID esecuzione <input value={sourceRun} onChange={event => setSourceRun(event.target.value)} /></label>
          <button type="button" disabled={!sourceRun.trim()} onClick={() => {
            setDocument({ ...document, source_runs: [...new Set([...document.source_runs, sourceRun.trim()])] });
            setSourceRun("");
          }}>Aggiungi fonte</button>
          {document.source_runs.map(id => <button key={id} type="button" onClick={() =>
            setDocument({ ...document, source_runs: document.source_runs.filter(item => item !== id) })
          }>Rimuovi fonte {id}</button>)}
          <label>Relazione <select value={relationKind} onChange={event => setRelationKind(event.target.value as RelationKind)}>
            {Object.entries(relationKinds).map(([value, text]) => <option value={value} key={value}>{text}</option>)}
          </select></label>
          <label>ID scheda collegata <input value={relationTarget} onChange={event => setRelationTarget(event.target.value)} /></label>
          <button type="button" disabled={!relationTarget.trim()} onClick={() => {
            setDocument({ ...document, relations: [...document.relations, { kind: relationKind, target_id: relationTarget.trim() }] });
            setRelationTarget("");
          }}>Aggiungi relazione</button>
          {document.relations.map((item, index) => <button key={index} type="button" onClick={() =>
            setDocument({ ...document, relations: document.relations.filter((_, position) => position !== index) })
          }>Rimuovi relazione {item.target_id}</button>)}
          <button type="submit">Salva scheda</button>
          <button type="button" onClick={() => setDocument(null)}>Annulla</button>
        </form>}
      </fieldset>

      <fieldset disabled={busy}>
        <legend>Registro delle esecuzioni</legend>
        <form onSubmit={event => { event.preventDefault(); void perform(() => showEvidence(runId.trim())); }}>
          <label>ID esecuzione <input value={runId} onChange={event => setRunId(event.target.value)} required /></label>
          <button type="submit">Apri esecuzione</button>
        </form>
        <details>
          <summary>Esecuzioni recenti</summary>
          {runs.length ? <ul>{runs.map(run => <li key={run.id}>
            <button onClick={() => void perform(() => showEvidence(run.id))}>
              {new Date(run.created_at).toLocaleString("it-IT")} · {run.target} · {run.status}
            </button>
          </li>)}</ul> : <p>Nessuna esecuzione recente.</p>}
        </details>
        {evidence && <article>
          <h3>Resoconto {evidence.report.kind} · {evidence.report.target}</h3>
          <p>Stato registrato: {evidence.report.status}
            {evidence.report.error_type ? " · " + evidence.report.error_type : ""}</p>
          <p>{new Date(evidence.report.created_at).toLocaleString("it-IT")}
            {evidence.report.finished_at && " → " + new Date(evidence.report.finished_at).toLocaleString("it-IT")}</p>
          {evidence.report.episode && <details>
            <summary>Episodio · {evidence.report.episode.title}</summary>
            <p style={{ whiteSpace: "pre-wrap" }}>{evidence.report.episode.summary}</p>
          </details>}
          <button onClick={() => startDraft(evidence.run_id)}>Crea una scheda da questa fonte</button>
          <h4>Messaggi dell’esecuzione</h4>
          {evidence.messages.map(message => <details key={message.id}>
            <summary>{message.role === "user" ? "Richiesta" : "Risposta"} · {new Date(message.created_at).toLocaleString("it-IT")}</summary>
            <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
          </details>)}
          {!evidence.messages.length && <p>Nessun messaggio attribuito a questa esecuzione.</p>}
          <h4>Eventi del run radice</h4>
          {evidence.events.map(item => <details key={item.id}>
            <summary>{item.type} · {item.source} · {new Date(item.timestamp).toLocaleString("it-IT")}</summary>
            <pre>{JSON.stringify(item.payload, null, 2)}</pre>
          </details>)}
          {moreEvents && <button onClick={() => void perform(() =>
            showEvidence(evidence.run_id, evidence.next_cursor))}>Altri eventi</button>}
        </article>}
      </fieldset>
    </section>
  );
}
