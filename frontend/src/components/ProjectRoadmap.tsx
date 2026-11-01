import { homeRoadmap } from "../services/connections";

export default function ProjectRoadmap() {
  return <section className="system-card home-backlog" aria-labelledby="project-goals-title">
    <div className="metric-head">
      <div><span>ROADMAP</span><h2 id="project-goals-title">Obiettivi aperti</h2></div>
      <span className="pill">{homeRoadmap.goals.length} traguardi · {homeRoadmap.categories.length} macroclassi</span>
    </div>
    <p className="home-backlog-intro">Revisione del {homeRoadmap.updatedAt}. {homeRoadmap.basis}</p>
    <section className="home-next-work" aria-label="Prossimi tre lavori">
      <h3>Prossimi tre lavori</h3>
      <div className="home-next-work-list">
        {homeRoadmap.nextWork.map(work => <article id={"work-"+work.id} key={work.id} className="home-next-work-card">
          <div className="home-next-work-heading">
            <span className="home-next-work-number">{work.order}</span>
            <div><strong>{work.title}</strong><small>{work.status}</small></div>
          </div>
          <p>{work.description}</p>
          {work.id==="W1" && <details>
            <summary>Idee già raccolte</summary>
            <ul>{work.notes.map(note=><li key={note}>{note}</li>)}</ul>
          </details>}
          {work.id==="W2" && <small>Gli aggiornamenti di Immich e Nextcloud non sono ancora abilitati dalla Home.</small>}
          {work.id==="W3" && <a href="#programmer-next">Apri pagina segnaposto (vuota)</a>}
        </article>)}
      </div>
    </section>
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
            <div className="home-goal-body">
              <strong>{goal.label}</strong><p>{goal.detail}</p>
              {"nextSteps" in goal && Array.isArray(goal.nextSteps) && goal.nextSteps.length > 0 &&
                <details className="home-goal-evidence">
                  <summary>Passi previsti e risultato atteso</summary>
                  <ol>{goal.nextSteps.map(step => <li key={step}>{step}</li>)}</ol>
                  {"doneWhen" in goal && typeof goal.doneWhen === "string" &&
                    <p><strong>Traguardo verificabile:</strong> {goal.doneWhen}</p>}
                </details>}
            </div>
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
