import { homeRoadmap } from "../services/connections";

export default function ProjectRoadmap() {
  return <section className="system-card home-backlog" aria-labelledby="project-goals-title">
    <div className="metric-head">
      <div><span>ROADMAP</span><h2 id="project-goals-title">Obiettivi aperti</h2></div>
      <span className="pill">{homeRoadmap.goals.length} traguardi · {homeRoadmap.categories.length} macroclassi</span>
    </div>
    <p className="home-backlog-intro">Revisione del {homeRoadmap.updatedAt}. {homeRoadmap.basis}</p>
    <div className="home-goal-groups">
      {homeRoadmap.categories.map(category => <details className="home-goal-group" key={category.id}>
        <summary><span><strong>{category.id} · {category.label}</strong><small>{category.detail}</small></span>
          <span className="pill">{category.id==="M1" ? homeRoadmap.architecture.open.length+" aperte" : category.goals.length}</span>
        </summary>
        {category.id === "M1" && <div className="home-architecture-decisions">
          {([
            ["confirmed","Decisioni già prese","Scelte architetturali attuali, non tutte già implementate."],
            ["open","Ancora da decidere","Alternative e specifiche da definire prima di considerare definitiva la struttura."],
            ["missing","Componenti mancanti","Parti da costruire dopo le decisioni, senza presentarle come installate."],
          ] as const).map(([key,title,note]) =>
            <div key={key} className={"home-architecture-decision "+key}>
              <h3>{title}</h3><p>{note}</p>
              {homeRoadmap.architecture[key].map(item => <div key={item.title} className="home-architecture-entry">
                <strong>{item.title}</strong><small>{item.detail}</small>
              </div>)}
            </div>
          )}
          <h3>Nodi attuali e futuri</h3>
          <div className="home-architecture-nodes" aria-label="Nodi previsti nell'architettura">
            {homeRoadmap.nodes.map(node => <div key={node.id} className="home-architecture-node">
              <div><strong>{node.name}</strong><span className="pill">{node.phase === "presente" ? "Nodo presente" : "Nodo futuro"}</span></div>
              <p>{node.role}</p>
            </div>)}
          </div>
        </div>}
        {category.id === "M2" && <div className="home-m2-summary">
          <p><strong>La situazione reale è nel riquadro «Salute del sistema e collaudi».</strong> Un solo registro contiene
          controlli, problemi e storico. Un test del collegamento software non attesta la riuscita di un lavoro reale.</p>
          <button type="button" className="text-button" onClick={() =>
            document.getElementById("system-health")?.scrollIntoView({behavior:"smooth",block:"start"})
          }>Vai alla dashboard dei controlli</button>
          <details className="home-m2-goals">
            <summary>Traguardi di affidabilità ancora aperti ({category.goals.length})</summary>
            {category.goals.map(goal => <div key={goal.id} className="settings-row home-goal">
              <div><strong>{goal.label}</strong><p>{goal.detail}</p>
                {"issues" in goal && Array.isArray(goal.issues) && goal.issues.length>0 &&
                  <small>Problemi aperti: {goal.issues.join(" · ")}</small>}
              </div><span className="pill">{goal.state}</span>
            </div>)}
          </details>
        </div>}
        {(category.id==="M3" || category.id==="M4") && category.goals.map(goal =>
          <div className="settings-row home-goal" key={goal.id}>
            <div><strong>{goal.label}</strong><p>{goal.detail}</p></div>
            <span className="pill">{goal.state}</span>
          </div>
        )}
      </details>)}
    </div>
    <details className="home-evidence-note">
      <summary>Come leggere questo quadro</summary>
      {homeRoadmap.limits.map(note=><p key={note}>{note}</p>)}
    </details>
  </section>;
}
