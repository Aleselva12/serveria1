import { useEffect, useState } from "react";
import { homeRoadmap } from "../services/connections";
import { api, type ProjectPreflight } from "../services/api";

type Goal = {
  id: string;
  category: string;
  label: string;
  state: string;
  detail: string;
  development?: string;
  verification?: string[];
  issues?: string[];
  checks?: string[];
};

function technicalStatus(goal: Goal, result: ProjectPreflight | null) {
  if (!goal.checks?.length) return "Non configurati";
  if (!result?.checkedAt || Date.now() - Date.parse(result.checkedAt) > result.intervalSeconds * 2000)
    return "Da controllare";
  const selected = goal.checks.map(id => result.checks.find(c => c.id === id));
  if (selected.some(item => !item)) return "Verifiche incomplete";
  if (selected.some(item => item?.status === "fail")) return "Prerequisiti mancanti";
  if (selected.some(item => item?.status === "unknown")) return "Prerequisiti ignoti";
  return "Prerequisiti presenti";
}

export default function ProjectRoadmap() {
  const [preflight, setPreflight] = useState<ProjectPreflight | null>(null);
  const [preflightError, setPreflightError] = useState("");

  useEffect(() => {
    let active = true, pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const result = await api.projectChecks();
        if (active) { setPreflight(result); setPreflightError(""); }
      } catch {
        if (active) {
          setPreflight(null);
          setPreflightError("Controlli automatici non disponibili. Nessun esito precedente viene considerato confermato.");
        }
      } finally { pending = false; }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const fresh = Boolean(preflight?.checkedAt &&
    Date.now() - Date.parse(preflight.checkedAt) <= preflight.intervalSeconds * 2000);

  return (
    <section className="system-card home-backlog" aria-labelledby="project-goals-title">
      <div className="metric-head">
        <div><span>STATO DEL PROGETTO</span><h2 id="project-goals-title">Obiettivi aperti</h2></div>
        <span className="pill">{homeRoadmap.goals.length} obiettivi · {homeRoadmap.categories.length} macroclassi</span>
      </div>
      <p className="home-backlog-intro">Revisione del {homeRoadmap.updatedAt}. {homeRoadmap.basis}</p>
      <div className="home-goal-groups">
        {homeRoadmap.categories.map(category => (
          <details className="home-goal-group" key={category.id}>
            <summary>
              <span><strong>{category.id} · {category.label}</strong><small>{category.detail}</small></span>
              <span className="pill">{category.goals.length}</span>
            </summary>

            {category.id === "M1" && <div className="home-architecture-nodes" aria-label="Nodi previsti nell'architettura">
              {homeRoadmap.nodes.map(node => <div key={node.id} className="home-architecture-node">
                <div><strong>{node.name}</strong><span className="pill">{node.phase === "presente" ? "Nodo presente" : "Nodo futuro"}</span></div>
                <p>{node.role}</p>
              </div>)}
            </div>}

            {category.id === "M2" && <div className="home-preflight" aria-label="Monitoraggio tecnico ripetuto">
              <strong>Controlli automatici dei prerequisiti</strong>
              <p>Il backend esegue controlli non distruttivi circa ogni 5 minuti, anche senza questa pagina aperta. Non sostituiscono i test delle funzioni.</p>
              {preflightError && <p role="status">{preflightError}</p>}
              {!fresh && !preflightError && <p>In attesa di un risultato recente dal backend.</p>}
              {fresh && preflight && <>
                <small>Ultimo ciclo: {new Date(preflight.checkedAt!).toLocaleString("it-IT")} · Dati temporanei, azzerati al riavvio.</small>
                <div className="home-preflight-list">
                  {preflight.checks.map(item => (
                    <div key={item.id} title={item.detail}>
                      <span>{item.label}</span>
                      <strong>{item.status === "pass" ? "Presente" : item.status === "fail" ? "Non pronto" : "Non verificato"}</strong>
                    </div>
                  ))}
                </div>
              </>}
            </div>}

            {(category.goals as Goal[]).map(goal => (
              <div className="settings-row home-goal" key={goal.id}>
                <div className="home-goal-body">
                  <strong>{goal.label}</strong><p>{goal.detail}</p>
                  {category.id === "M2" && <>
                    <div className="home-goal-status-line">
                      <span>Funzionamento: <strong>Da verificare</strong></span>
                      <span>Sviluppo: <strong>{goal.development || "Da valutare"}</strong></span>
                      <span>Ambiente: <strong>{technicalStatus(goal, preflight)}</strong></span>
                    </div>
                    <details className="home-goal-evidence">
                      <summary>Verifiche e problemi aperti</summary>
                      <div>
                        <strong>Da provare</strong>
                        <ul>{(goal.verification || []).map(step => <li key={step}>{step}</li>)}</ul>
                        {(goal.issues?.length || 0) > 0 && <>
                          <strong>Mancanze o problemi noti</strong>
                          <ul>{goal.issues!.map(issue => <li key={issue}>{issue}</li>)}</ul>
                        </>}
                        <small>I controlli tecnici sono distinti dalla prova funzionale su Debian.</small>
                      </div>
                    </details>
                  </>}
                </div>
                <span className={"pill " + (goal.state.includes("hardware") ? "" : "pending")}>{goal.state}</span>
              </div>
            ))}
          </details>
        ))}
      </div>
      <details className="home-evidence-note">
        <summary>Come leggere questo quadro</summary>
        {homeRoadmap.limits.map(note => <p key={note}>{note}</p>)}
      </details>
    </section>
  );
}
