import { useCallback, useEffect, useState } from "react";
import { DECISIONS_CHANGED, loadDecisions, resolveApproval, reviewOperation, type Approval, type Decisions } from "../services/decisionsApi";

const REFRESH_MS = 60000;

function when(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

/** Pending decisions kept fresh: periodic reload plus any decision taken elsewhere in the page. */
export function useDecisions() {
  const [decisions, setDecisions] = useState<Decisions | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const { decisions: next, errors } = await loadDecisions();
      setDecisions(next);
      setError(errors.length ? "Non disponibili ora: " + errors.join(", ") + "." : "");
    } catch (e) { setError(e instanceof Error ? e.message : "Decisioni non disponibili."); }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    const changed = () => void refresh();
    window.addEventListener(DECISIONS_CHANGED, changed);
    return () => { clearInterval(timer); window.removeEventListener(DECISIONS_CHANGED, changed); };
  }, [refresh]);
  return { decisions, error, refresh };
}

/** "Da decidere": agent proposals, uncertain effects and Word notes, moved here from Attività. */
export default function DecisionsPanel({ onOpenAudio }: { onOpenAudio?: () => void }) {
  const { decisions, error } = useDecisions();
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  async function run(action: () => Promise<{ status?: string; error_type?: string } | void>) {
    setBusy(true); setMessage("");
    try {
      const result = await action();
      if (result && result.status === "failed") setMessage("Azione non completata: " + result.error_type + ". Controlla il risultato prima di riprovare.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Operazione non riuscita."); }
    finally { setBusy(false); }
  }
  const decide = (a: Approval, approve: boolean) => run(() => resolveApproval(a, approve));

  return <div className="decisions">
    {error && <p role="alert">{error}</p>}
    {message && <p role="alert">{message}</p>}
    {decisions && decisions.pending === 0 && <p className="muted">Niente da decidere: nessuna proposta o verifica in attesa.</p>}

    {!!decisions?.approvals.length && <article className="section-card">
      <h2>Azioni da approvare</h2>
      <p>La conferma riguarda esclusivamente l'azione e i parametri mostrati. Per la Libreria IA controlla percorso e contenuto prima/dopo: un file cambiato dopo la lettura richiede una nuova proposta. Il cestino conserva il file ed è ripristinabile dalla pagina File.</p>
      {decisions.approvals.map(a => <div className="decision-item" key={a.kind + a.id}>
        <strong>{a.kind === "calendar" ? "Calendario" : a.actor} · {a.action}</strong>
        {a.actions && <p>Permessi richiesti: {a.actions.join(", ")}</p>}
        <pre>{JSON.stringify(a.payload, null, 2)}</pre>
        {a.kind === "generic" && a.contract_version === null && <p>Proposta precedente ai contratti: chiedi all’agente una nuova proposta per confermarla.</p>}
        <div className="decision-actions">
          <button className="solid-button" disabled={busy || (a.kind === "generic" && a.contract_version === null)} onClick={() => void decide(a, true)}>Approva questa azione</button>
          <button className="text-button" disabled={busy} onClick={() => void decide(a, false)}>Rifiuta</button>
        </div>
      </div>)}
    </article>}

    {!!decisions?.word.length && <article className="section-card">
      <h2>Note Word da approvare</h2>
      <p>Si approvano nella pagina Audio, accanto alla trascrizione da cui nascono, così vedi il testo prima di scriverlo nel documento del cliente.</p>
      {decisions.word.map(w => <div className="decision-item" key={w.id}>
        <strong>{w.title}</strong>
        <small>Proposta il {when(w.createdAt)} · scade il {when(w.expiresAt)}</small>
      </div>)}
      {onOpenAudio && <button className="text-button" onClick={onOpenAudio}>Apri Audio</button>}
    </article>}

    {!!decisions?.uncertain.length && <article className="section-card">
      <h2>Effetti da verificare</h2>
      <p>Un esito incerto può includere effetti già prodotti. Verifica il servizio o il file interessato prima di ripetere l’operazione. Registrare la verifica non esegue né ripete azioni.</p>
      {decisions.uncertain.map(o => <div className="decision-item" key={o.id}>
        <strong>{o.capability_id} · esito incerto</strong>
        <p>Operazione {o.id} · run {o.run_id || "senza run"}</p>
        <pre>{JSON.stringify(o.payload, null, 2)}</pre>
        {o.error_type && <p>{o.error_type}</p>}
        <label>Verifica effettuata<textarea aria-label={"Verifica " + o.id} maxLength={2000} value={notes[o.id] || ""} onChange={e => setNotes(n => ({ ...n, [o.id]: e.target.value }))} /></label>
        <div className="decision-actions">
          <button disabled={busy || !notes[o.id]?.trim()} onClick={() => void run(() => reviewOperation(o.id, "effect_verified", notes[o.id]))}>Effetto verificato</button>
          <button disabled={busy || !notes[o.id]?.trim()} onClick={() => void run(() => reviewOperation(o.id, "no_effect_verified", notes[o.id]))}>Nessun effetto verificato</button>
        </div>
      </div>)}
    </article>}

    {!!decisions?.results.length && <article className="section-card"><details><summary>Esiti delle proposte</summary>
      {decisions.results.map(a => <div className="decision-item" key={a.id}>
        <strong>{a.actor} · {a.action} · {a.status}</strong>
        {["executing", "uncertain"].includes(a.status) && <p>Non ripetere la proposta: controlla le operazioni e l’effetto nel servizio interessato.</p>}
        {a.error_type && <p>{a.error_type}</p>}
        <pre>{typeof a.result === "string" ? a.result : JSON.stringify(a.result, null, 2)}</pre>
      </div>)}
    </details></article>}
  </div>;
}
