import { useEffect, useMemo, useState } from 'react';
import type { RunSnapshot, CapabilityOperation } from '../services/runtimeApi';
import { buildEvidence, terminalRun, friendlyName, stepExplanation, layoutEvidence, type TraceEvent, type EvidenceStep } from './activityEvidence';
import './activity-explorer.css';

type Props = {runs:RunSnapshot[]; selected?:RunSnapshot; selectedId:string; events:TraceEvent[]; operations:CapabilityOperation[]; onSelect:(id:string)=>void; loading:boolean; error:string; older:boolean; onOlder:()=>void; live:boolean; onLive:(value:boolean)=>void; onRefresh:()=>void};
const stateNames:Record<string,string>={completed:'Concluso',running:'In corso',queued:'In coda',failed:'Fallito',error:'Errore',uncertain:'Esito incerto',interrupted:'Interrotto',awaiting_approval:'Attende approvazione',cancelled:'Annullato',timed_out:'Tempo scaduto',succeeded:'Riuscito',observed:'Osservato'};
const label=(s:string)=>stateNames[s] || s;
const tone=(s:string)=>['failed','error','uncertain','divergente'].includes(s)?'issue':['running','queued'].includes(s)?'active':'neutral';
const json=(value:unknown)=>JSON.stringify(value,null,2);
const short=(s:string,n=24)=>s.length>n?s.slice(0,n-1)+'…':s;
const record=(v:unknown):Record<string,unknown>=>v && typeof v==='object' && !Array.isArray(v)?v as Record<string,unknown>:{};
const ms=(v:unknown)=>typeof v==='number'?v>=1000?(v/1000).toFixed(2)+' s':Math.round(v)+' ms':'Non registrata';
const kindLabel=(s:EvidenceStep)=>s.origin==='Operazione persistente'?'OPERAZIONE':s.kind==='modello osservato'?'PROVIDER':s.kind==='model'?'MODELLO':s.kind==='tool'?'STRUMENTO':s.kind==='node'?'AGENTE / NODO':s.origin==='Evento persistente'?'FATTO SALVATO':'EVENTO';

function DeviceIcon({kind}:{kind:string}) {
  return <g className="ae-device" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
    {kind==='tool' || kind==='read' || kind==='write' ? <><path d="M-23 -9 L0 -22 L23 -9 L0 4Z" fill="#e9efff"/><path d="M-23 -9 V14 L0 28 V4Z" fill="#c4d3f4"/><path d="M0 4 L23 -9 V14 L0 28Z" fill="#f4f6ff"/><path d="M-16 -2 L-7 3 M7 8 L17 2 M7 15 L17 9"/></> : kind==='model' || kind==='modello osservato' ? <><path d="M-25 -18 L9 -28 L26 -17 L-8 -7Z" fill="#f3f6ff"/><path d="M-25 -18 V-3 L-8 8 V-7Z M-25 1 V16 L-8 27 V12Z" fill="#b8caed"/><path d="M-8 -7 L26 -17 V-2 L-8 8Z M-8 12 L26 2 V17 L-8 27Z" fill="#e3eaff"/><path d="M-25 1 L9 -9 L26 2 L-8 12Z" fill="#f4f7ff"/><path d="M0 -1 L18 -6 M0 18 L18 13"/><circle cx="-17" cy="-9" r="1.5" fill="currentColor"/><circle cx="-17" cy="10" r="1.5" fill="currentColor"/></> : <><path d="M-24 -21 L17 -29 L17 3 L-24 12Z" fill="#c5d7f8"/><path d="M-19 -17 L12 -23 V-1 L-19 6Z" fill="#f5f8ff"/><path d="M-24 12 L17 3 L31 14 L-10 25Z" fill="#e4ecff"/><path d="M-24 12 V16 L-10 29 L31 18 V14 M-10 25 V29 M-13 14 L13 8 M-8 18 L19 12"/></>}
  </g>;
}

export default function ActivityExplorer(props:Props) {
  const {runs,selected,selectedId,events,operations,onSelect}=props;
  const [mode,setMode]=useState<'map'|'sequence'>('map');
  const [filter,setFilter]=useState('');
  const [category,setCategory]=useState('all');
  const [stepId,setStepId]=useState('');
  const [eventId,setEventId]=useState('');
  const [cursor,setCursor]=useState<number|null>(null);
  const [playing,setPlaying]=useState(false);
  const [speed,setSpeed]=useState(1);
  const timed=useMemo(()=>[...events].sort((a,b)=>a.timestamp.localeCompare(b.timestamp)||a.id.localeCompare(b.id)),[events]);
  const {steps,warnings}=useMemo(()=>buildEvidence(cursor===null?selected:undefined,cursor===null?events:timed.slice(0,cursor+1),cursor===null?operations:[]),[selected,events,operations,timed,cursor]);
  const visible=steps.filter(s=>category==='all' || (category==='tools'?s.kind==='tool'||s.origin==='Operazione persistente':category==='models'?['model','modello osservato'].includes(s.kind):s.kind==='evento'));
  const step=steps.find(s=>s.id===stepId) || (!stepId?visible[0]:undefined);
  const selectedEvent=timed.find(e=>e.id===eventId);
  const networkSteps=visible.some(s=>s.id.startsWith("span:"))?visible.filter(s=>s.id.startsWith("span:")):visible;
  const {nodes:graph,positions,height}=layoutEvidence(networkSteps);
  const completed=steps.filter(s=>['completed','succeeded'].includes(s.status)).length;
  const issues=warnings.length+(props.error?1:0);
  const currentEvents=cursor===null?timed:timed.slice(0,cursor+1);
  const baseTime=timed.length?Date.parse(timed[0].timestamp):NaN;
  const timings=selected?.timings || {};
  useEffect(()=>{setStepId('');setEventId('');setCursor(null);setPlaying(false);},[selectedId]);
  useEffect(()=>{
    if(!playing) return;
    const timer=setInterval(()=>setCursor(old=>{const next=(old ?? -1)+1;if(next>=timed.length-1)setPlaying(false);return Math.min(next,timed.length-1);}),1000/speed);
    return ()=>clearInterval(timer);
  },[playing,timed.length,speed]);
  const pick=(s:EvidenceStep)=>{setStepId(s.id);setEventId('');};
  function pickEvent(e:TraceEvent){setEventId(e.id);setStepId(e.span_id?'span:'+e.span_id:'event:'+e.id);}
  const activeStep=step?steps.indexOf(step)+1:0;
  return <section className="activity-explorer" aria-label="Esplora esecuzioni">
    <header className="ae-header">
      <div className="ae-brand"><span className="ae-logo">◇</span><div><h2>CORA EXPLORER</h2><span>IL PERCORSO DELLE TUE RICHIESTE</span></div></div>
      <div className="ae-now"><small>ESECUZIONE SELEZIONATA</small><strong>{selected?friendlyName(selected.target || 'Richiesta'): 'Seleziona una richiesta'}</strong><span>{selectedId?selectedId.slice(0,12):'IN ATTESA'} · {selected?label(selected.status):'Nessun run'}</span></div>
      <div className="ae-progress"><small>EVIDENZE CARICATE</small><div className="ae-progress-blocks">{Array.from({length:14},(_,i)=><i key={i} className={i<Math.round(14*completed/Math.max(1,steps.length))?'filled':''}/>)}</div><span>{completed} / {steps.length} passaggi conclusi · {issues} segnali da verificare</span></div>
      <div className="ae-controls"><button aria-pressed={props.live} onClick={()=>props.onLive(!props.live)}>{props.live?'● Live':'Live in pausa'}</button><button title="Aggiorna dati" onClick={props.onRefresh} disabled={props.loading}>↻</button></div>
    </header>
    <div className="ae-layout">
      <aside className="ae-history" aria-label="Storico esecuzioni"><div className="ae-panel-heading"><h3>RICHIESTE E PASSAGGI</h3><span>•••</span></div><label className="ae-search"><span className="sr-only">Cerca per ID, destinazione o stato</span><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Cerca un’esecuzione…"/></label>
        <div className="ae-categories" role="group" aria-label="Filtra passaggi">{[['all','Tutti'],['models','Modelli'],['tools','Strumenti'],['events','Eventi']].map(([id,name])=><button key={id} aria-pressed={category===id} onClick={()=>setCategory(id)}>{name}</button>)}</div>
        <div className="ae-run-list">{runs.filter(r=>(r.id+' '+r.target+' '+r.status+' '+label(r.status)).toLowerCase().includes(filter.toLowerCase())).map(r=><div key={r.id}><button className={'ae-run '+(selectedId===r.id?'selected':'')} aria-pressed={selectedId===r.id} onClick={()=>onSelect(r.id)}><span className={'ae-dot '+tone(r.status)}/><div><strong>{friendlyName(r.target || 'Richiesta')}</strong><small>{r.created_at?new Date(r.created_at).toLocaleString('it-IT'):r.id.slice(0,8)} · {label(r.status)}</small></div><span>{selectedId===r.id?'⌄':'›'}</span></button>
        {selectedId===r.id && <ol className="ae-step-list">{visible.map((s,i)=><li key={s.id}><button aria-pressed={step?.id===s.id} onClick={()=>pick(s)}><span className={'ae-step-number '+tone(s.status)}>{i+1}</span><span><strong>{friendlyName(s.name)}</strong><small>{kindLabel(s)} · {label(s.status)}</small></span></button></li>)}</ol>}</div>)}</div>
        {!runs.length && <p className="ae-empty">Invia una richiesta dalla Chat per osservarne il percorso.</p>}<p className="ae-muted ae-history-note">Ultimi 30 run persistenti e run attivi. I numeri seguono il campione caricato; non rappresentano una catena obbligatoria.</p>
      </aside>
      <main className="ae-center">
        <div className="ae-toolbar"><div role="group" aria-label="Visualizzazione"><button aria-pressed={mode==='map'} onClick={()=>setMode('map')}>◈ RETE</button><button aria-pressed={mode==='sequence'} onClick={()=>setMode('sequence')}>☷ SEQUENZA</button></div><span className="ae-map-caption">{cursor===null?'EVIDENZE ATTUALI':`LETTURA · EVENTO ${cursor+1}/${timed.length}`}</span></div>
        {props.loading && <p role="status">Caricamento delle prove…</p>}
        {props.error && <p className="ae-warning" role="alert">{props.error}</p>}
        {!selectedId ? <div className="ae-empty">Seleziona un’esecuzione per esplorare il percorso.</div> : mode==='map' ? <div className="ae-map"><svg viewBox={`0 0 780 ${height}`} role="group" aria-label="Mappa dei passaggi osservati"><defs><marker id="ae-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/></marker></defs>
          {graph.map(s=>{const a=s.parent?positions.get(s.parent):undefined,b=positions.get(s.id)!;return a && <path className={'ae-edge '+(step?.id===s.id?'highlight':'')} key={'edge:'+s.id} d={`M ${a.x+48} ${a.y} C ${a.x+130} ${a.y},${b.x-130} ${b.y},${b.x-48} ${b.y}`} markerEnd="url(#ae-arrow)"/>;})}
          {graph.map(s=>{const p=positions.get(s.id)!;return <g key={s.id} transform={`translate(${p.x} ${p.y})`} className={'ae-node '+tone(s.status)+(step?.id===s.id?' selected':'')} role="button" tabIndex={0} aria-label={s.name+': '+label(s.status)} aria-pressed={step?.id===s.id} onClick={()=>pick(s)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(s);}}}><title>{friendlyName(s.name)+' · '+s.origin+' · '+label(s.status)}</title><rect className="ae-node-halo" x="-77" y="-44" width="154" height="125" rx="3"/><DeviceIcon kind={s.kind}/><circle cx="36" cy="-25" r="10" className="ae-node-badge"/><text x="36" y="-22" textAnchor="middle" className="ae-node-number">{steps.indexOf(s)+1}</text><text y="48" textAnchor="middle">{short(friendlyName(s.name),23)}</text><text y="64" textAnchor="middle" className="ae-node-state">{cursor===null && terminalRun(selected?.status || '') && s.status==='running'?'Finale non osservato':label(s.status)}</text><text y="79" textAnchor="middle" className="ae-node-kind">{kindLabel(s)}</text></g>;})}
        </svg>{!graph.length && <p className="ae-empty">Nessuna prova disponibile per questo filtro.</p>}{networkSteps.length>40 && <p>40 nodi nella rete. Tutti i {visible.length} passaggi sono consultabili in Sequenza.</p>}</div> : <ol className="ae-sequence">{visible.map((s,i)=><li key={s.id}><button className={step?.id===s.id?'selected':''} onClick={()=>pick(s)}><span className={'ae-step-number '+tone(s.status)}>{i+1}</span><div><strong>{friendlyName(s.name)}</strong><small>{s.time?new Date(s.time).toLocaleTimeString('it-IT'):'Ordine temporale non disponibile'} · {s.origin} · {label(s.status)}</small></div><span>{ms(s.duration)}</span></button></li>)}</ol>}
        <div className="ae-map-legend"><span>── Relazione registrata</span><span>◇ Nodo / agente</span><span>▱ Strumento</span><span className="issue">● Da verificare</span></div><p className="ae-caption">La rete mostra i legami padre/figlio delle chiamate. Operazioni, eventi e prove del provider sono consultabili nell’elenco a sinistra; senza correlazione non diventano frecce nella rete. I tempi sovrapposti non vanno sommati.</p>
        <div className="ae-summary"><span><strong>{operations.length}</strong>operazioni salvate</span><span><strong>{steps.filter(s=>s.kind==='tool').length}</strong>chiamate tool tracciate</span><span><strong>{Array.isArray(timings.selected_tools)?timings.selected_tools.length:'—'}</strong>tool esposti</span><span><strong>{ms(selected?.elapsed_ms)}</strong>durata run</span></div>
      </main>
      <aside className="ae-inspector" aria-label="Dettaglio del passaggio"><div className="ae-panel-heading"><h3>DETTAGLIO PASSAGGIO</h3><span>↗</span></div>{step ? <><div className="ae-inspector-content"><span className="ae-eyebrow">PASSAGGIO {activeStep} DI {steps.length} · {kindLabel(step)}</span><h2>{friendlyName(step.name)}</h2><span className={'ae-status '+tone(step.status)}>{label(step.status)}</span><p>{stepExplanation(step)}</p><StepDetails step={step}/>{selectedEvent && <div className="ae-event-focus"><strong>Evento selezionato</strong><p>{selectedEvent.type} · {String(selectedEvent.payload.status || 'registrato')}</p><small>{selectedEvent.timestamp}</small></div>}<details><summary>Dati tecnici e identificativi</summary><pre>{json(selectedEvent || step.data)}</pre></details></div></> : <p className="ae-empty">Seleziona un passaggio per vedere cosa è accaduto e quali prove lo sostengono.</p>}</aside>
      <section className="ae-flow" aria-label="Flusso degli eventi"><div className="ae-flow-header"><h3>FLUSSO DEGLI EVENTI</h3><div className="ae-flow-key"><span>● Modello</span><span>● Strumento</span><span>● Fatto persistente</span></div><div className="ae-replay"><button title="Velocità di lettura" onClick={()=>setSpeed(s=>s===1?2:s===2?0.5:1)}>{speed}×</button><button disabled={!timed.length} onClick={()=>{props.onLive(false);setPlaying(false);setCursor(c=>Math.max(0,(c??timed.length)-1));}}>‹</button><button disabled={!timed.length} className="ae-play" onClick={()=>{props.onLive(false);if(!playing)setCursor(c=>c===null || c>=timed.length-1?0:c);setPlaying(!playing);}}>{playing?'Pausa lettura':'Riproduci tracce'}</button><button disabled={!timed.length} onClick={()=>{props.onLive(false);setPlaying(false);setCursor(c=>Math.min((c??-1)+1,timed.length-1));}}>Passo</button><button title="Mostra tutte le prove" onClick={()=>{setCursor(null);setPlaying(false);}}>↺</button></div></div>
        {timed.length>0 && <label className="ae-scrubber">LETTURA EVENTI<input aria-label="Posizione nella lettura degli eventi" type="range" min="0" max={Math.max(0,timed.length-1)} value={cursor??timed.length-1} onChange={e=>{props.onLive(false);setPlaying(false);setCursor(Number(e.target.value));}}/><span>{cursor===null?'Tutte le prove':`${cursor+1} / ${timed.length}`}</span></label>}
        <div className="ae-table-scroll"><table><thead><tr><th>N.</th><th>TEMPO</th><th>ORIGINE</th><th>DESTINAZIONE / OGGETTO</th><th>EVENTO</th><th>ESITO</th><th>DURATA</th></tr></thead><tbody>{currentEvents.map((e,i)=>{const offset=Date.parse(e.timestamp)-baseTime;const destination=e.payload.name || e.payload.capability_id || e.payload.target || '—';return <tr key={e.id} className={eventId===e.id?'selected':''} onClick={()=>pickEvent(e)}><td><button aria-label={'Esamina evento '+(i+1)} onClick={ev=>{ev.stopPropagation();pickEvent(e);}}>{String(i+1).padStart(2,'0')}</button></td><td>{Number.isFinite(offset)?'+'+(offset/1000).toFixed(3)+' s':'—'}</td><td>{friendlyName(e.source)}</td><td>{String(destination)}</td><td>{e.type}</td><td><span className={'ae-status '+tone(String(e.payload.status))}>{label(String(e.payload.status || 'registrato'))}</span></td><td>{ms(e.payload.duration_ms)}</td></tr>;})}</tbody></table>{!currentEvents.length && <p className="ae-empty">Nessun evento caricato. Le operazioni persistenti possono comunque essere consultate nei passaggi.</p>}</div><div className="ae-flow-footer"><span>{currentEvents.length} eventi nel campione · lettura locale, nessuna azione ripetuta. L’esito del run in alto è quello attuale.</span>{props.older && <button onClick={props.onOlder}>Carica diagnostica precedente</button>}</div>
      </section>
      <section className="ae-audit"><div className="ae-audit-head"><div><span className="ae-eyebrow">VERIFICA IL PERCORSO, POI IL RISULTATO</span><h3>Il successo tecnico corrisponde alla tua richiesta?</h3></div><span className={'ae-status '+(issues?'issue':'neutral')}>{issues?issues+' segnali da verificare':'Nessuna anomalia rilevata nel campione'}</span></div><div className="ae-audit-columns"><div className="ae-evidence">{warnings.map(w=><p className="ae-warning" key={w}>{w}</p>)}<p>“Concluso” è lo stato del run, non una certificazione della risposta. Tool esposto ≠ tool invocato. Diagnostica a campione: le prove mancanti non dimostrano l’assenza di un’azione.</p><dl className="ae-context"><dt>Instradamento registrato</dt><dd>{String(timings.primary_route || 'Non disponibile')}</dd><dt>Pagine di contesto</dt><dd>{Array.isArray(timings.context_pages)?timings.context_pages.join(', ') || 'Nessuna dichiarata':'Non disponibili'}</dd><dt>Strumenti esposti</dt><dd>{Array.isArray(timings.selected_tools)?timings.selected_tools.join(', ') || 'Nessuno dichiarato':'Non disponibili'}</dd></dl></div><Review key={selectedId} run={selected}/></div></section>
    </div>
  </section>;
}

function StepDetails({step}:{step:EvidenceStep}) {
  const d=record(step.data),p=record(d.payload),model=step.kind==='modello osservato';
  const fields:[string,unknown][]=[['Fonte della prova',step.origin],['Stato registrato',label(step.status)],['Durata',ms(step.duration)],['Ora osservata',step.time?new Date(step.time).toLocaleTimeString('it-IT'):'Non registrata']];
  if(model) fields.push(['Modello richiesto',d.requested_model],['Modello riportato',d.reported_model],['Macchina registrata',d.machine_id],['Corrispondenza',d.matches_requested===true?'Sì':d.matches_requested===false?'NO · modello divergente':'Non verificabile']);
  else if(step.origin==='Operazione persistente') fields.push(['Capability',d.capability_id],['Tipo di effetto',d.effect],['Verifica effetto',d.review_outcome || 'Non registrata'],['Nota verifica',d.review_note],['Errore',d.error_type]);
  else fields.push(['Componente',d.source],['Relazione padre',step.parent || 'Non registrata'],['Errore',p.error_type],['Dettaglio errore',p.error_detail]);
  return <><dl className="ae-detail-fields">{fields.filter(([,v])=>v!==null && v!==undefined && v!=='').map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>{step.origin==='Operazione persistente' && <><details open><summary>Parametri dell’operazione</summary><pre>{json(d.payload)}</pre></details><details open><summary>Risultato dell’operazione</summary><pre>{json(d.result) || 'Non disponibile'}</pre></details></>}</>;
}

function Review({run}:{run?:RunSnapshot}) {
  const [expectation,setExpectation]=useState('');
  const [verdict,setVerdict]=useState('pending');
  return <details open className="ae-review"><summary>Confronta richiesta e risultato</summary><p>Apri la conversazione originale per confrontare ciò che hai chiesto. I metadati non consentono di dedurre automaticamente la tua intenzione.</p><label>Cosa doveva accadere?<textarea value={expectation} onChange={e=>setExpectation(e.target.value)} placeholder="Esempio: leggere il documento e usare il modello scelto sul desktop"/></label><label>Valutazione manuale<select value={verdict} onChange={e=>setVerdict(e.target.value)}><option value="pending">Da verificare</option><option value="match">Corrisponde a ciò che ho chiesto</option><option value="mismatch">Non corrisponde / possibile falso positivo</option><option value="insufficient">Prove insufficienti</option></select></label><p>Annotazioni temporanee di questa vista: non certificano il run e non vengono salvate sul server.</p><h4>Risposta registrata</h4><pre>{run?.result?.response || run?.output || 'Risposta non disponibile in questo snapshot. Consulta la Chat.'}</pre><p className="ae-muted">Le verifiche degli effetti incerti e le approvazioni restano nei controlli operativi sottostanti.</p></details>;
}
