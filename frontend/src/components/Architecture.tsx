import type { BackendHealth, BackendRegistry } from "../types/contracts";
import { useState } from "react";
import ArchitectureOverview from "./ArchitectureOverview";
import ArchitectureTools from "./ArchitectureTools";

export default function Architecture({ health, selectedNode, onSelect }: {
  registry: BackendRegistry | null;
  health: BackendHealth | null;
  selectedNode: string;
  onSelect: (id: string) => void;
}) {
  const [view, setView] = useState<"architecture" | "tools">("architecture");
  return <section className="content-page">
    <div className="page-heading"><div><div className="eyebrow">OSSERVA IL SISTEMA</div><h1>Architettura</h1><p>{view === "tools" ? "Esplora i tool e costruisci bozze grafiche di automazioni." : "Agenti, modelli e programmi del server. Apri una scheda per vedere i dettagli."}</p></div><span className="pill">{view === "tools" ? "Tools e bozze grafiche" : "Configurazione agenti"}</span></div>
    <nav className="file-subnav" aria-label="Sezioni Architettura">
      <button aria-current={view === "architecture" ? "page" : undefined} aria-selected={view === "architecture"} onClick={() => setView("architecture")}>Architettura</button>
      <button aria-current={view === "tools" ? "page" : undefined} aria-selected={view === "tools"} onClick={() => setView("tools")}>Tools</button>
    </nav>
    {view === "tools" ? <ArchitectureTools /> : <><ArchitectureOverview health={health} selectedNode={selectedNode} onSelect={onSelect} /></>}
  </section>;
}
