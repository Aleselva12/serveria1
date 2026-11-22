import { useMemo, useState } from "react";
import { Bot, Calculator, Eye, PenLine, Plus } from "lucide-react";
import type { AutomationRun } from "../../types/contracts";
import { EFFECTS, prettyName, type CatalogTool, type Effect } from "./model";

const W = 1000, H = 640, CX = W / 2, CY = H / 2, HUB = 165, RING = 275;
const effectIcon: Record<Effect, typeof Eye> = { read: Eye, compute: Calculator, write: PenLine, delegate: Bot, none: Eye };

/** Constellation of the server's tools: Cora at the centre, one hub per group, tools on the outer ring. */
export default function LiveServer({ catalog, usedTools, run, drafts, scheduled, onAdd }: {
  catalog: CatalogTool[]; usedTools: string[]; run: AutomationRun | null; drafts: number; scheduled: number;
  onAdd: (tool: CatalogTool) => void;
}) {
  const [focus, setFocus] = useState<CatalogTool | null>(null);
  const [hover, setHover] = useState<CatalogTool | null>(null);
  const used = useMemo(() => new Set(usedTools), [usedTools]);
  const ran = useMemo(() => {
    const ids = new Set<string>();
    if (!run) return ids;
    for (const [id, state] of Object.entries(run.nodes)) {
      const tool = (run as AutomationRun & { graph?: { nodes: { id: string; tool_id?: string | null }[] } }).graph?.nodes.find(n => n.id === id)?.tool_id;
      if (tool && (state.status === "done" || state.status === "simulated")) ids.add(tool);
    }
    return ids;
  }, [run]);

  const layout = useMemo(() => {
    const groups = [...new Set(catalog.map(t => t.group))];
    const n = Math.max(catalog.length, 1);
    const tools = catalog.map((t, i) => {
      const a = (i / n) * Math.PI * 2 - Math.PI / 2;
      return { tool: t, a, x: CX + Math.cos(a) * RING, y: CY + Math.sin(a) * RING * .82 };
    });
    const hubs = groups.map(g => {
      const mine = tools.filter(t => t.tool.group === g);
      const a = Math.atan2(mine.reduce((s, t) => s + Math.sin(t.a), 0), mine.reduce((s, t) => s + Math.cos(t.a), 0));
      return { group: g, a, x: CX + Math.cos(a) * HUB, y: CY + Math.sin(a) * HUB * .82, tools: mine };
    });
    return { tools, hubs };
  }, [catalog]);

  const counts = { read: 0, compute: 0, write: 0, delegate: 0, none: 0 } as Record<Effect, number>;
  catalog.forEach(t => counts[t.effect]++);
  const shown = hover ?? focus;

  return <section className="auto-content auto-live">
    <div className="auto-content-head"><h2>Server vivo.</h2><span>{catalog.length} TOOL · {layout.hubs.length} AREE · {catalog.filter(t => t.connected).length} COLLEGATI</span></div>
    <div className="auto-live-grid">
      <svg viewBox={`0 0 ${W} ${H}`} className="auto-live-map" role="img" aria-label="Mappa dei tool del server">
        <defs>
          <radialGradient id="live-core"><stop offset="0" stopColor="var(--ops-accent)" stopOpacity=".55" /><stop offset="1" stopColor="var(--ops-accent)" stopOpacity="0" /></radialGradient>
        </defs>
        <ellipse cx={CX} cy={CY} rx={RING} ry={RING * .82} className="live-orbit" />
        <ellipse cx={CX} cy={CY} rx={HUB} ry={HUB * .82} className="live-orbit" />
        {layout.hubs.map(h => {
          const hot = h.tools.some(t => used.has(t.tool.id) || ran.has(t.tool.id));
          return <g key={h.group}>
            <line x1={CX} y1={CY} x2={h.x} y2={h.y} className={`live-link ${hot ? "hot" : ""}`} />
            {h.tools.map(t => <line key={t.tool.id} x1={h.x} y1={h.y} x2={t.x} y2={t.y}
              className={`live-spoke effect-${t.tool.effect} ${used.has(t.tool.id) || ran.has(t.tool.id) ? "hot" : ""} ${shown?.id === t.tool.id ? "focus" : ""}`} />)}
          </g>;
        })}
        <circle cx={CX} cy={CY} r={70} fill="url(#live-core)" className="live-core-glow" />
        <circle cx={CX} cy={CY} r={30} className="live-core" />
        <text x={CX} y={CY + 4} className="live-core-label">CORA</text>
        {layout.hubs.map(h => <g key={h.group} className="live-hub">
          <circle cx={h.x} cy={h.y} r={9} />
          <text x={h.x + (Math.cos(h.a) >= 0 ? 14 : -14)} y={h.y + 3} textAnchor={Math.cos(h.a) >= 0 ? "start" : "end"}>{h.group.toUpperCase()} · {h.tools.length}</text>
        </g>)}
        {layout.tools.map(t => <circle key={t.tool.id} cx={t.x} cy={t.y} r={shown?.id === t.tool.id ? 9 : 6}
          className={`live-tool effect-${t.tool.effect} ${t.tool.connected ? "" : "off"} ${used.has(t.tool.id) ? "used" : ""} ${ran.has(t.tool.id) ? "ran" : ""}`}
          tabIndex={0} role="button" aria-label={prettyName(t.tool.name)}
          onMouseEnter={() => setHover(t.tool)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(t.tool)} onBlur={() => setHover(null)}
          onClick={() => setFocus(t.tool)} onKeyDown={e => { if (e.key === "Enter") setFocus(t.tool); }}>
          <title>{prettyName(t.tool.name)} · {EFFECTS[t.tool.effect].label}</title>
        </circle>)}
      </svg>
      <aside className="auto-live-side">
        <div className="auto-live-stats">
          {(["read", "compute", "write", "delegate"] as Effect[]).map(e => { const I = effectIcon[e]; return (
            <div key={e} className={`effect-${e}`}><I size={15} /><b>{counts[e]}</b><span>{EFFECTS[e].label}</span></div>); })}
          <div><b>{drafts}</b><span>Flussi salvati</span></div>
          <div><b>{scheduled}</b><span>Pianificato (questo)</span></div>
        </div>
        {shown ? <div className={`auto-live-card effect-${shown.effect}`}>
          <span className="ops-overline">{shown.group.toUpperCase()} · {EFFECTS[shown.effect].label.toUpperCase()}</span>
          <h3>{prettyName(shown.name)}</h3>
          <p>{shown.description || "Nessuna descrizione."}</p>
          <p className="auto-note">{EFFECTS[shown.effect].hint}</p>
          {shown.required.length > 0 && <p className="auto-note">Parametri: {shown.required.join(", ")}</p>}
          <button className="source-button auto-execute static" onClick={() => onAdd(shown)}><Plus size={14} />Aggiungi al flusso</button>
        </div> : <div className="auto-live-card"><h3>Esplora</h3><p>Ogni punto è un tool che Cora sa usare, raggruppato per area. Passa sopra per leggerlo, clicca per aggiungerlo al flusso.</p>
          <p className="auto-note">Anello acceso = usato nel flusso aperto. Punto pieno = eseguito nell'ultima prova. Punto spento = non collegato.</p></div>}
      </aside>
    </div>
  </section>;
}
