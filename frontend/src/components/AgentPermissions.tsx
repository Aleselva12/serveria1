import { useEffect, useRef, useState } from "react";
import { runtimeRequest } from "../services/runtimeApi";

type Rule = { actor: string; action: string; policy: string; scope: string };

/** What each agent may do on its own. Lives in Impostazioni › Accesso e permessi. */
export default function AgentPermissions() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const live = useRef(true);

  async function load() {
    try {
      const data = await runtimeRequest<{ rules: Rule[] }>("/permissions");
      if (live.current) { setRules(data.rules); setError(""); }
    } catch (e) {
      if (live.current) setError(e instanceof Error ? e.message : "Permessi non disponibili.");
    }
  }
  useEffect(() => { live.current = true; void load(); return () => { live.current = false; }; }, []);

  async function change(rule: Rule, policy: string) {
    if (busy) return;
    setBusy(true);
    try {
      await runtimeRequest("/runtime/policies", { method: "PUT", body: JSON.stringify({ actor: rule.actor, action: rule.action, policy }) });
      await load();
    } catch (e) {
      if (live.current) setError(e instanceof Error ? e.message : "Permesso non salvato.");
    } finally {
      if (live.current) setBusy(false);
    }
  }

  return <div className="agent-permissions">
    <p>Per ogni azione: automatica, con richiesta di conferma (arriva in Notifiche › Da decidere) o bloccata. Le azioni senza un percorso verificato restano bloccate.</p>
    {error && <p role="alert">{error}</p>}
    {!rules && !error && <p>Caricamento permessi…</p>}
    {rules?.length === 0 && <p>Nessuna regola configurata.</p>}
    {rules?.map(r => <label className="settings-row" key={r.actor + r.action}>
      <span>{r.actor} · {r.action}<small>{r.scope}</small></span>
      <select aria-label={r.actor + " " + r.action} disabled={busy} value={r.policy} onChange={e => void change(r, e.target.value)}>
        <option value="auto">Automatico</option>
        <option value="confirm">Richiedi conferma</option>
        <option value="blocked">Bloccato</option>
      </select>
    </label>)}
  </div>;
}
