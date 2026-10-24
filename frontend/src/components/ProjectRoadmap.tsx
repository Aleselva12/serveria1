import { homeRoadmap } from "../services/connections";

export default function ProjectRoadmap() {
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
            {category.goals.map(goal => (
              <div className="settings-row home-goal" key={goal.id}>
                <div><strong>{goal.label}</strong><p>{goal.detail}</p></div>
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
