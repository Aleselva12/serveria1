import type { BackendHealth, BackendRegistry } from "../types/contracts";
import ConnectionNotice from "./ConnectionNotice";

export default function Architecture({
  registry,
  health,
  selectedNode,
  onSelect,
}: {
  registry: BackendRegistry | null;
  health: BackendHealth | null;
  selectedNode: string;
  onSelect: (id: string) => void;
}) {
  if (!registry)
    return (
      <section className="content-page">
        <div className="page-heading">
          <div>
            <h1>Architettura</h1>
            <p>
              Registro dei componenti non disponibile. Verifica la connessione
              al backend.
            </p>
          </div>
        </div>
      </section>
    );
  const supervisor = registry.components.find((c) => c.id === "supervisor");
  const agents = registry.components.filter((c) => c.kind === "agent");
  const selected =
    registry.components.find((c) => c.id === selectedNode) || supervisor;
  return (
    <section className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">OSSERVA IL SISTEMA</div>
          <h1>Architettura</h1>
          <p>
            Componenti letti dal backend. I collegamenti illustrano la delega
            possibile, non un’esecuzione.
          </p>
        </div>
        <span className="pill">Registro reale · Sola lettura</span>
      </div>
      <div className="arch-layout">
        <div className="arch-canvas">
          <div className="canvas-label">
            MAPPA DEI COMPONENTI <span>{registry.project}</span>
          </div>
          <div className="graph-area">
            <svg
              viewBox="0 0 820 440"
              className="graph-lines"
              aria-hidden="true"
            >
              {agents.map((a, i) => (
                <path
                  key={a.id}
                  d={
                    "M 410 104 C 410 150 " +
                    ((i + 0.5) * 820) / agents.length +
                    " 145 " +
                    ((i + 0.5) * 820) / agents.length +
                    " 211"
                  }
                />
              ))}
              <path d="M 410 104 C 410 270 410 295 410 343" />
            </svg>
            {supervisor && (
              <button
                className={
                  "graph-node central " +
                  (selected?.id === "supervisor" ? "selected" : "")
                }
                onClick={() => onSelect("supervisor")}
              >
                <span>✦</span>
                <strong>Supervisore</strong>
                <small>Orchestrazione</small>
              </button>
            )}
            {agents.map((a, i) => (
              <button
                key={a.id}
                style={{ left: ((i + 0.5) * 100) / agents.length + "%" }}
                className={
                  "graph-node leaf " + (selected?.id === a.id ? "selected" : "")
                }
                onClick={() => onSelect(a.id)}
              >
                <span
                  className={"node-dot " + (a.available ? "" : "unavailable")}
                />
                <strong>
                  {a.name
                    .replace("Local Research Agent", "Documenti")
                    .replace("Email & Quotes Agent", "Mail e preventivi")
                    .replace(" Agent", "")}
                </strong>
                <small>
                  {a.available ? "Modulo presente" : "Dipendenze mancanti"}
                </small>
              </button>
            ))}
            <div className="graph-node model">
              <span
                className={
                  "node-dot " + (health?.ollama_online ? "" : "unavailable")
                }
              />
              <strong>Ollama</strong>
              <small>
                {health
                  ? health.ollama_online
                    ? "Raggiungibile"
                    : "Offline"
                  : "Non verificato"}
              </small>
            </div>
          </div>
        </div>
        <aside className="side-panel">
          <div className="eyebrow">COMPONENTE SELEZIONATO</div>
          <h2>{selected?.name || "Seleziona un componente"}</h2>
          <p>{selected?.description}</p>
          <div className="field-line">
            <span>Disponibilità strutturale</span>
            <strong>
              {selected?.available ? "Modulo presente" : "Non disponibile"}
            </strong>
          </div>
          <div className="eyebrow spaced">CAPACITÀ DICHIARATE</div>
          <div className="chip-row">
            {selected?.capabilities.map((c) => (
              <span className="chip" key={c.id} title={c.description}>
                {c.id}
              </span>
            ))}
          </div>
          <div className="panel-note">
            Il registro verifica moduli e dipendenze. Non certifica credenziali,
            permessi o disponibilità operativa di ogni agente.
          </div>
        </aside>
      </div>
      <div className="section-card">
        <h2>Componenti di supporto</h2>
        <div className="chip-row">
          {registry.components
            .filter((c) => c.kind !== "agent" && c.id !== "supervisor")
            .map((c) => (
              <button
                className="chip"
                key={c.id}
                title={c.description}
                onClick={() => onSelect(c.id)}
              >
                {c.name}
              </button>
            ))}
        </div>
      </div>
      <ConnectionNotice feature="graph" />
      <ConnectionNotice feature="runs" />
      <ConnectionNotice feature="graphEdit" compact />
    </section>
  );
}
