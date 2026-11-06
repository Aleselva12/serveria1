import type { RunSnapshot, CapabilityOperation } from '../services/runtimeApi';

export type TraceEvent = {id:string; sequence:number; type:string; timestamp:string; source:string; component_run_id:string|null; span_id?:string|null; parent_span_id?:string|null; operation_id?:string|null; payload:Record<string,unknown>};
export type EvidenceStep = {id:string; name:string; kind:string; status:string; origin:string; parent?:string; time?:string; duration?:number; data:unknown};
export const terminalRun = (status:string) => ['completed','failed','interrupted','cancelled','timed_out','awaiting_approval'].includes(status);
export function buildEvidence(run:RunSnapshot|undefined, events:TraceEvent[], operations:CapabilityOperation[]) {
  const steps:EvidenceStep[] = [];
  const spans = new Map<string, EvidenceStep>();
  const sorted = [...events].sort((a,b)=>a.timestamp.localeCompare(b.timestamp) || a.id.localeCompare(b.id));
  for (const e of sorted) {
    const p=e.payload;
    if (e.type === 'trace.span' && e.span_id) {
      const id='span:'+e.span_id;
      const previous=spans.get(id);
      // A delayed start must never erase a terminal event for the same span.
      if (previous && previous.status !== 'running' && p.status === 'running') continue;
      spans.set(id,{id, name:String(p.name || e.source), kind:String(p.kind || 'passaggio'), status:String(p.status || 'unknown'), origin:'Traccia diagnostica', parent:e.parent_span_id ? 'span:'+e.parent_span_id : undefined, time:previous?.time || e.timestamp, duration:typeof p.duration_ms==='number' ? p.duration_ms : undefined, data:e});
    } else steps.push({id:'event:'+e.id,name:e.type,kind:'evento',status:String(p.status || 'registrato'),origin:['run.committed','run.stop_requested','operation.committed','operation.reviewed'].includes(e.type)?'Evento persistente':'Traccia diagnostica',time:e.timestamp,data:e});
  }
  steps.push(...spans.values());
  for (const o of operations) steps.push({id:'operation:'+o.id,name:o.capability_id,kind:o.effect,status:o.status,origin:'Operazione persistente',data:o});
  const observations = Array.isArray(run?.timings?.inference_observations) ? run.timings.inference_observations as Record<string,unknown>[] : [];
  observations.filter(o=>o && typeof o==='object').forEach((o,i)=>steps.push({id:'model:'+i,name:String(o.role || 'Modello'),kind:'modello osservato',status:o.matches_requested===false?'divergente':o.reported_model?'osservato':'non verificabile',origin:'Risposta del provider',data:o}));
  steps.sort((a,b)=>(a.time || 'z').localeCompare(b.time || 'z') || a.id.localeCompare(b.id));
  const warnings:string[]=[];
  if (!spans.size) warnings.push('Nessun percorso diagnostico disponibile: non è possibile ricostruire i passaggi interni.');
  if ([...spans.values()].some(s=>s.parent && !spans.has(s.parent))) warnings.push('Alcuni passaggi hanno un genitore assente dal campione. I collegamenti mancanti non vengono ricostruiti.');
  if (run && terminalRun(run.status) && [...spans.values()].some(s=>s.status==='running')) warnings.push('Il run è terminato, ma alcune tracce non hanno un evento finale: stato del passaggio non confermato.');
  if (observations.some(o=>o?.matches_requested===false)) warnings.push('Un modello riportato dal provider differisce da quello richiesto.');
  if (!observations.some(o=>o?.reported_model)) warnings.push('Identità del modello non confermata da una risposta del provider.');
  if (operations.some(o=>o.status==='uncertain')) warnings.push('Ci sono effetti incerti: verificare il risultato prima di ripetere azioni.');
  if (run?.status==='completed' && operations.some(o=>['failed','uncertain'].includes(o.status))) warnings.push('Run concluso con operazioni fallite o incerte: il successo globale non certifica ogni effetto.');
  if ([...spans.values()].some(s=>['failed','error'].includes(s.status))) warnings.push('Una chiamata tracciata è fallita: controlla errore e risultato anche se il run è concluso.');
  if (run && ['failed','interrupted','cancelled','timed_out'].includes(run.status)) warnings.push('Il run non si è concluso regolarmente: verifica l’esito e gli eventuali effetti già prodotti.');
  return {steps,warnings};
}

export const friendlyName=(name:string)=>({roadmap_classifier:'Valutazione priorità',supervisor:'Cora centrale',documents:'Agente Documenti',research:'Agente Ricerca',programmer:'Agente Programmatore',audio:'Agente Audio',mail:'Agente Mail',library_read:'Lettura documento',library_search:'Ricerca in Libreria',library_list:'Elenco documenti','run.committed':'Stato del run salvato','operation.committed':'Esito operazione salvato','context.selected':'Preparazione contesto','memory.selected':'Selezione memoria','tool.finished':'Strumento terminato','component.request':'Richiesta a un componente','component.finished':'Risposta del componente'}[name] || name);
export function stepExplanation(step:EvidenceStep) {
  if(step.origin==='Operazione persistente') return 'Il registro conserva l’invocazione e il suo esito. Confronta parametri, risultato ed eventuale verifica dell’effetto.';
  if(step.kind==='modello osservato') return 'Questi dati confrontano il modello richiesto con quello riportato dal provider. La macchina è quella registrata dall’applicazione.';
  if(step.kind==='tool') return 'Una chiamata a uno strumento è stata osservata. La sua conclusione tecnica va confrontata con il risultato dell’operazione.';
  if(step.kind==='model') return 'Il modello ha elaborato un turno. Può produrre una risposta oppure richiedere strumenti; il solo completamento non dimostra che li abbia usati.';
  if(step.origin==='Evento persistente') return 'Questo fatto è stato salvato insieme allo stato del run o dell’operazione. Non è un comando da eseguire.';
  return 'Passaggio osservato nell’esecuzione. Le frecce rappresentano esclusivamente relazioni padre/figlio presenti nelle tracce.';
}

// Bounded, cycle-safe topology layout. Disconnected evidence has no invented edge.
export function layoutEvidence(steps:EvidenceStep[]) {
  const nodes=steps.slice(0,40), byId=new Map(nodes.map(s=>[s.id,s]));
  function depth(s:EvidenceStep,seen=new Set<string>()):number {
    if(!s.parent || !byId.has(s.parent) || seen.has(s.id)) return 0;
    return Math.min(2,1+depth(byId.get(s.parent)!,new Set([...seen,s.id])));
  }
  const rows=[0,0,0];
  const positions=new Map(nodes.map(s=>{const column=depth(s);return [s.id,{x:100+column*245,y:70+rows[column]++*155}];}));
  return {nodes,positions,height:Math.max(420,Math.max(...rows)*155+85)};
}
