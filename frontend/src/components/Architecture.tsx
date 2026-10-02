import type { BackendHealth, BackendRegistry } from "../types/contracts";
import ConnectionNotice from "./ConnectionNotice";
import { useState } from "react";
import ArchitectureRuntime from "./ArchitectureRuntime";
import ArchitectureTools from "./ArchitectureTools";

export default function Architecture({
  registry,
  selectedNode,
  onSelect,
}: {
  registry: BackendRegistry | null;
  health: BackendHealth | null;
  selectedNode: string;
  onSelect: (id: string) => void;
}) {
  const [view, setView] = useState<"architecture" | "tools">("architecture");
  const navigation = <nav className="file-subnav" aria-label="Sezioni Architettura">
    <button aria-current={view === "architecture" ? "page" : undefined} aria-selected={view === "architecture"} onClick={() => setView("architecture")}>Architettura</button>
    <button aria-current={view === "tools" ? "page" : undefined} aria-selected={view === "tools"} onClick={() => setView("tools")}>Tools</button>
  </nav>;
  if (view === "tools") return <section className="content-page"><div className="page-heading"><div><div className="eyebrow">OSSERVA IL SISTEMA</div><h1>Architettura</h1></div><span className="pill">Inventario · Sola lettura</span></div>{navigation}<ArchitectureTools /></section>;
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
        {navigation}
        <ArchitectureRuntime showTraces={false} />
      </section>
    );
  const supervisor = registry.components.find((c) => c.id === "supervisor");

  const selected =
    registry.components.find((c) => c.id === selectedNode) || supervisor;
  return (
    <section className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">OSSERVA IL SISTEMA</div>
          <h1>Architettura</h1>
          <p>
            Grafo e componenti letti dal backend. Le tracce delle esecuzioni sono state spostate nella pagina Attività.
          </p>
        </div>
        <span className="pill">Registro reale · Sola lettura</span>
      </div>
      {navigation}
      <div className="arch-layout">
        <ArchitectureRuntime showTraces={false} />
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
        <h2>Agenti e componenti</h2>
        <div className="chip-row">
          {registry.components
            
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
      <ConnectionNotice feature="graphEdit" compact />
    </section>
  );
}
