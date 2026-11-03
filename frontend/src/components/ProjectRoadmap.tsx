export default function ProjectRoadmap() {
  return <a className="tree-preview" href="#homepage-schema-albero">
    <svg viewBox="0 0 160 74" width="142" aria-hidden="true"><path d="M9 51L46 37L79 48L109 18L148 11M46 37L59 10M79 48L129 62" fill="none" stroke="#8293a6"/>{[[9,51],[46,37],[79,48],[109,18],[148,11],[59,10],[129,62]].map(([x,y])=><circle key={x} cx={x} cy={y} r={x===79?5:3} fill="#d7e5f3"/>)}</svg>
    <div><small>DIREZIONE PROGETTO</small><h2>Schema albero</h2><p>Esplora le stelle di Cora, le verifiche e i prossimi obiettivi.</p></div><b aria-hidden="true">↗</b>
  </a>
}
