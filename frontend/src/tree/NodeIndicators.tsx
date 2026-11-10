import type {NodeIndicator} from "./roadmapEvidence";
export type IndicatorPair={development:NodeIndicator;verification:NodeIndicator};
export default function NodeIndicators({development,verification}:IndicatorPair){
 return <span className="rm2-node-indicators">{[["Sviluppo",development],["Collaudi",verification]].map(([name,value])=>{
  const indicator=value as NodeIndicator;
  return <span key={name as string} title={name+": "+indicator.label}><i aria-hidden="true" style={{background:indicator.color}}/>{name as string} · {indicator.label}</span>;
 })}</span>;
}
export function IndicatorLegend(){
 return <details className="rm2-indicator-legend"><summary>Legenda · Sviluppo e collaudi</summary>
  <p>I due punti accanto a ogni stella, pianeta e luna indicano, da sinistra, sviluppo (S) e collaudi (C). Descrivono solo quel nodo: non ereditano gli esiti dei figli. Il colore centrale mantiene la logica storica della mappa.</p>
  <p><b>Sviluppo:</b> grigio = non implementato o da valutare; blu = parziale; verde = implementato secondo il progetto, senza certificare il funzionamento.</p>
  <p><b>Collaudi:</b> grigio = nessun esito reale valido; giallo = verifica parziale o rifinitura; arancione = criticità; rosso = collaudo fallito; verde = collaudo reale superato oppure osservazione manuale circoscritta e datata.</p>
  <p>Test assenti, scaduti, di altre versioni o eseguiti solo in CI non sono fallimenti sul server. Un controllo simulato non basta per il verde.</p>
 </details>;
}
