import { useEffect, useState } from "react";
import { mediaRequest, type AudioRecord } from "../services/mediaApi";
import { runtimeRequest } from "../services/runtimeApi";

type Match = {
  path: string; heading: string; start: number; stop: number; sha256: string;
  identityLines: string[];
};
type Proposal = {
  id: string; documentPath: string; customer: string; date: string; note: string;
  status: string; expiresAt: string; errorCode?: string | null;
};
type AnalysisRun = {
  id: string; status: string; result?: {
    analysis?: { customerQuery: string; note: string }; audio_version?: number;
  } | null;
};
const terminal = new Set(["completed", "failed", "cancelled", "timed_out", "interrupted"]);
const nowRome = () => new Date().toLocaleDateString("it-IT", {timeZone: "Europe/Rome"});
function dateFor(recordedAt: string) {
  const date = recordedAt?.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(date || "")
    ? (date!.slice(8, 10) + "/" + date!.slice(5, 7) + "/" + date!.slice(0, 4))
    : nowRome();
}
const errorText = (e: unknown) => e instanceof Error ? e.message : "Operazione non riuscita.";

export default function CommercialNotes({ record, disabled }: {record: AudioRecord; disabled: boolean}) {
  const [query, setQuery] = useState("");
  const [note, setNote] = useState("");
  const [date, setDate] = useState(() => dateFor(record.recordedAt));
  const [matches, setMatches] = useState<Match[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [analysisId, setAnalysisId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function reload() {
    const data = await mediaRequest<Proposal[]>("/api/v1/audio/" + record.id + "/commercial/proposals");
    setProposals(data);
  }
  useEffect(() => {
    setQuery(""); setNote(""); setDate(dateFor(record.recordedAt));
    setMatches([]); setSelected(null); setAnalysisId(""); setError(""); setNotice("");
    void reload().catch(e => setError(errorText(e)));
  }, [record.id, record.version]);

  useEffect(() => {
    if (!analysisId) return;
    let live = true;
    let active = false;
    const refresh = async () => {
      if (active) return;
      active = true;
      try {
        const run = await runtimeRequest<AnalysisRun>("/runtime/runs/" + analysisId);
        if (!live) return;
        if (run.status === "completed" && run.result?.analysis) {
          if (run.result.audio_version !== record.version) {
            setError("Trascrizione cambiata: richiedi una nuova analisi.");
          } else {
            setNote(run.result.analysis.note);
            setQuery(run.result.analysis.customerQuery);
            setMatches([]); setSelected(null);
            setNotice("Analisi disponibile: controlla cliente e appunto prima di proporre.");
          }
          setAnalysisId("");
        } else if (terminal.has(run.status)) {
          setError("Analisi non completata. Verifica Attività o scrivi l'appunto manualmente.");
          setAnalysisId("");
        }
      } catch(e) {
        if (live) { setError(errorText(e)); setAnalysisId(""); }
      } finally { active = false; }
    };
    void refresh();
    const timer = setInterval(() => void refresh(), 2000);
    return () => { live = false; clearInterval(timer); };
  }, [analysisId, record.version]);

  async function action(work: () => Promise<void>) {
    if (busy || disabled || analysisId) return;
    setBusy(true); setError(""); setNotice("");
    try { await work(); }
    catch(e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  async function analyze() {
    await action(async () => {
      const run = await mediaRequest<AnalysisRun>(
        "/api/v1/audio/" + record.id + "/commercial/analyze?expected_version=" + record.version,
        {method: "POST"});
      setAnalysisId(run.id);
      setNotice("Analisi locale avviata; nessun Word sarà modificato.");
    });
  }
  async function search() {
    await action(async () => {
      const result = await mediaRequest<{matches: Match[]; scanned: number; skipped: number}>(
        "/api/v1/audio/" + record.id + "/commercial/customers?query=" + encodeURIComponent(query));
      setMatches(result.matches); setSelected(null);
      setNotice(result.matches.length
        ? "Trovati " + result.matches.length + " blocchi cliente. Seleziona quello corretto."
        : "Nessun cliente trovato: controlla il nome o i file presenti in Libreria IA.");
    });
  }
  async function propose() {
    await action(async () => {
      if (selected === null || !matches[selected]) throw new Error("Seleziona il cliente preciso.");
      await mediaRequest("/api/v1/audio/" + record.id + "/commercial/proposals", {
        method: "POST",
        body: JSON.stringify({
          expected_audio_version: record.version,
          selected: matches[selected], date, note,
        }),
      });
      setNotice("Proposta salvata per 24 ore. Nessun documento modificato.");
      await reload();
    });
  }
  async function resolve(id: string, approve: boolean) {
    await action(async () => {
      try {
        const result = await mediaRequest<{status:string}>(
          "/api/v1/audio/" + record.id + "/commercial/proposals/" + id + "/resolve",
          {method: "POST", body: JSON.stringify({approve})});
        setNotice(approve && result.status === "approved"
          ? "Aggiunta approvata nel Word della Libreria IA, backup conservato."
          : "Proposta " + result.status + ".");
      } finally {
        // Even if the external write failed, never retry it automatically.
        await reload();
      }
    });
  }
  return <section className="system-card commercial-notes">
    <h3>Telefonata → appunti Word</h3>
    <p>La ricerca usa i Word già nella Libreria IA. Nessuna modifica viene fatta prima della tua approvazione. Solo aggiunte, mai cancellazioni o sostituzioni.</p>
    {error && <p role="alert" className="connection-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="media-actions">
      <button disabled={disabled || busy || !!analysisId} onClick={() => void analyze()}>
        {analysisId ? "Analisi in corso…" : "Analizza conversazione con Cora"}
      </button>
    </div>
    <label>Nome cliente da cercare
      <input value={query} maxLength={200} disabled={busy || !!analysisId}
        onChange={e => { setQuery(e.target.value); setMatches([]); setSelected(null); }} />
    </label>
    <button disabled={disabled || busy || !!analysisId || query.trim().length < 2} onClick={() => void search()}>
      Cerca nei Word della Libreria IA
    </button>
    {matches.length > 0 && <fieldset><legend>Seleziona il blocco cliente corretto</legend>
      {matches.map((m, i) => <label key={m.path + ":" + m.start} style={{display:"block",marginBottom:8}}>
        <input type="radio" name={"commercial-customer-" + record.id} checked={selected === i}
          disabled={busy} onChange={() => setSelected(i)} />
        <strong>{m.heading}</strong> — {m.path}
        {m.identityLines.length > 0 && <small> · {m.identityLines.join(" · ").slice(0,300)}</small>}
      </label>)}
    </fieldset>}
    <label>Data della conversazione (GG/MM/AAAA)
      <input value={date} maxLength={10} disabled={busy} onChange={e => setDate(e.target.value)} />
    </label>
    <label>Testo esatto da aggiungere sotto il cliente scelto
      <textarea className="transcript-editor" value={note} maxLength={5000}
        disabled={busy} onChange={e => setNote(e.target.value)} />
    </label>
    <button className="upload-button" disabled={busy || disabled || !!analysisId || selected === null || !note.trim()}
      onClick={() => void propose()}>Prepara proposta append-only (24 ore)</button>
    <h4>Proposte di questa registrazione</h4>
    {proposals.length === 0 && <p>Nessuna proposta.</p>}
    {proposals.map(p => <article key={p.id} className="calendar-proposal">
      <strong>{p.customer}</strong><small> · {p.documentPath} · {p.date}</small>
      <p style={{whiteSpace:"pre-wrap"}}>{p.note}</p>
      <small>Stato: {p.status} · Scadenza: {new Date(p.expiresAt).toLocaleString("it-IT")}</small>
      {p.status === "pending" && <div className="media-actions">
        <button className="upload-button" disabled={busy || disabled} onClick={() => {
          if (window.confirm("Confermi la sola aggiunta al Word indicato?")) void resolve(p.id, true);
        }}>Approva aggiunta</button>
        <button disabled={busy || disabled} onClick={() => void resolve(p.id, false)}>Rifiuta</button>
      </div>}
      {p.status === "uncertain" && <p role="alert">Esito non verificato: non ripetere. Controlla Word e backup.</p>}
    </article>)}
  </section>;
}
