import { useEffect, useId, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { ArrowRight, GitBranch, Play, Wrench, ZoomIn, ZoomOut } from "lucide-react";
import type { FlowNode, ToolFlow } from "../types/contracts";

const icons = { trigger: Play, condition: GitBranch, tool: Wrench, output: ArrowRight };
const labels = { trigger: "Ingresso", condition: "Condizione", tool: "Operazione", output: "Uscita" };
export default function ToolFlowCanvas({ flow, selected, onSelect, editable = false, onMove, onConnect, pending, onRemoveEdge }: {
  flow: ToolFlow; selected: string; onSelect: (id: string) => void; editable?: boolean;
  onMove?: (id: string, x: number, y: number) => void;
  onConnect?: (id: string, direction: "in" | "out", label?: string) => void;
  pending?: { source: string; label: string } | null;
  onRemoveEdge?: (id: string) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const arrowId = useId().replaceAll(":", "");
  const drag = useRef<{ id: string; clientX: number; clientY: number; x: number; y: number } | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const width = Math.max(1000, ...flow.nodes.map(n => n.x + 280));
  const height = Math.max(450, ...flow.nodes.map(n => n.y + 170));
  useEffect(() => {
    const fit = () => { const available = scroll.current?.clientWidth || 0; if (available) setZoom(Math.max(.4, Math.min(1, (available - 40) / width))); };
    fit();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(fit) : null;
    if (scroll.current) observer?.observe(scroll.current);
    return () => observer?.disconnect();
    // Refitting on added/removed nodes keeps drag and manual zoom stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow.nodes.length, editable ? null : width]);
  useEffect(() => { if (!editable) drag.current = null; }, [editable]);
  function start(e: PointerEvent<HTMLButtonElement>, n: FlowNode) {
    onSelect(n.id);
    if (!editable || e.button !== 0) return;
    drag.current = { id: n.id, clientX: e.clientX, clientY: e.clientY, x: n.x, y: n.y };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }
  function move(e: PointerEvent<HTMLButtonElement>) {
    if (!drag.current) return;
    const d = drag.current;
    onMove?.(d.id, Math.min(10000, Math.max(0, d.x + (e.clientX - d.clientX) / zoom)), Math.min(10000, Math.max(0, d.y + (e.clientY - d.clientY) / zoom)));
  }
  return <div className="tool-flow-canvas"><div className="tool-flow-controls"><span>{editable ? "BOZZA GRAFICA" : "FLUSSO DEL TOOL SELEZIONATO"}</span><div>
    <button aria-label="Riduci flusso" disabled={zoom <= .4} onClick={() => setZoom(z => Math.max(.4, z - .2))}><ZoomOut size={15} /></button>
    <button onClick={() => setZoom(Math.min(1, 950 / width))}>Adatta</button><button onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
    <button aria-label="Ingrandisci flusso" disabled={zoom >= 1.6} onClick={() => setZoom(z => Math.min(1.6, z + .2))}><ZoomIn size={15} /></button></div></div>
    {pending && <div className="flow-pending" role="status">Collegamento “{pending.label}”: scegli la porta di ingresso del nodo di destinazione.</div>}
    <div ref={scroll} className="tool-flow-scroll"><div style={{ width: width * zoom, height: height * zoom }}><div className="tool-flow-plane" style={{ width, height, transform: `scale(${zoom})`, transformOrigin: "top left" }}>
      <svg width={width} height={height} className="tool-flow-edges" aria-hidden="true"><defs><marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8b83ad" /></marker></defs>
        {flow.edges.map(e => { const a = flow.nodes.find(n => n.id === e.source), b = flow.nodes.find(n => n.id === e.target); if (!a || !b) return null;
          const ax = a.x + 220, ay = a.y + (a.kind === "condition" && e.label === "no" ? 88 : 55), bx = b.x, by = b.y + 55;
          const span = Math.max(60, Math.abs(bx - ax) / 2);
          return <g key={e.id}><path d={`M ${ax} ${ay} C ${ax + span} ${ay} ${bx - span} ${by} ${bx} ${by}`} strokeDasharray={e.dashed ? "6 5" : undefined} markerEnd={`url(#${arrowId})`} /><text x={(ax + bx) / 2} y={(ay + by) / 2 - 10} textAnchor="middle">{e.label}</text></g>;
        })}</svg>
      {flow.nodes.map(n => { const Icon = icons[n.kind]; return <div key={n.id} className={`flow-step ${n.kind} ${selected === n.id ? "selected" : ""}`} style={{ left: n.x, top: n.y }}>
        {n.kind !== "trigger" && <button className="flow-port input" aria-label={`Collega in ingresso: ${n.label}`} disabled={!editable} onClick={() => onConnect?.(n.id, "in")} />}
        <button className="flow-step-body" aria-pressed={selected === n.id} aria-label={`Passaggio: ${n.label}`} onClick={() => onSelect(n.id)} onPointerDown={e => start(e, n)} onPointerMove={move}
          onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}
          onKeyDown={e => { const offsets: Record<string, [number, number]> = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] }; const d = offsets[e.key]; if (editable && d) { e.preventDefault(); onMove?.(n.id, Math.min(10000, Math.max(0, n.x + d[0])), Math.min(10000, Math.max(0, n.y + d[1]))); } }}>
          <span className="flow-step-icon"><Icon size={24} /></span><span><small>{labels[n.kind]}</small><strong>{n.label}</strong></span></button>
        {n.kind !== "output" && <button className="flow-port output" aria-label={`Collega in uscita: ${n.label}`} disabled={!editable} onClick={() => onConnect?.(n.id, "out", n.kind === "condition" ? "sì" : "successo")} />}
        {n.kind === "condition" && editable && <button className="flow-port output branch-no" aria-label={`Collega ramo no: ${n.label}`} onClick={() => onConnect?.(n.id, "out", "no")} />}
      </div>; })}
    </div></div></div>
    <div className="flow-caption">{editable ? "Trascina i nodi oppure usa le frecce della tastiera. Collega una porta di uscita a una di ingresso." : "Seleziona un passaggio per vedere le sue caratteristiche."}</div>
    {editable && flow.edges.length > 0 && <div className="flow-connections">{flow.edges.map(e => <div key={e.id}><span>{flow.nodes.find(n => n.id === e.source)?.label} → {flow.nodes.find(n => n.id === e.target)?.label} · {e.label}</span><button aria-label={`Rimuovi collegamento ${e.id}`} onClick={() => onRemoveEdge?.(e.id)}>Rimuovi</button></div>)}</div>}
  </div>;
}
