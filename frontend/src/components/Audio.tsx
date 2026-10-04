import {useEffect,useRef,useState} from 'react';
import {mediaRequest,downloadMedia,type AudioRecord} from '../services/mediaApi';
import {apiBaseUrl} from '../services/api';
import {runtimeRequest} from '../services/runtimeApi';

const terminal = new Set(['completed','failed','cancelled','timed_out','interrupted','awaiting_approval']);
const statuses:Record<string,string> = {queued:'In coda',running:'Trascrizione in corso',cancelling:'Annullamento in corso',completed:'Completata',failed:'Fallita',cancelled:'Annullata',timed_out:'Tempo scaduto',interrupted:'Interrotta al riavvio'};
export default function Audio() {
  const [items,setItems]=useState<AudioRecord[]>([]), [selected,setSelected]=useState('');
  const [record,setRecord]=useState<AudioRecord|null>(null), [text,setText]=useState('');
  const [dirty,setDirty]=useState(false), [busy,setBusy]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('');
  const [title,setTitle]=useState(''), [date,setDate]=useState(''), [one,setOne]=useState(''), [two,setTwo]=useState('');
  const [readiness,setReadiness]=useState<{ready:boolean;engineInstalled:boolean;localModelReady:boolean;diarizationReady:boolean}|null>(null);
  const [language,setLanguage]=useState('it'), [diarize,setDiarize]=useState(false);
  const input=useRef<HTMLInputElement>(null), live=useRef(true), revision=useRef(0), lock=useRef(false);
  async function refresh() { const status=await mediaRequest<NonNullable<typeof readiness>>('/api/v1/audio/status');if(live.current)setReadiness(status);const data=await mediaRequest<{items:AudioRecord[]}>('/api/v1/audio'); if(live.current) setItems(data.items); }
  useEffect(()=>{live.current=true; void refresh().catch(e=>setError(e.message));return()=>{live.current=false;revision.current++;};},[]);
  useEffect(()=>{
    const request=++revision.current; setRecord(null);setText('');setDirty(false);setError('');
    if(selected) void mediaRequest<AudioRecord>('/api/v1/audio/'+selected).then(r=>{if(live.current&&request===revision.current){setRecord(r);setText(r.transcript??'');}}).catch(e=>{if(live.current&&request===revision.current)setError(e.message);});
  },[selected]);
  useEffect(()=>{
    if(!record?.run || terminal.has(record.run.status))return;
    const id=record.id, request=revision.current;
    const timer=setInterval(()=>{if(document.hidden)return;void mediaRequest<AudioRecord>('/api/v1/audio/'+id).then(r=>{if(live.current&&request===revision.current){setRecord(r);if(!dirty)setText(r.transcript??'');if(r.run&&terminal.has(r.run.status))void refresh();}}).catch(e=>{if(live.current&&request===revision.current)setError(e.message);});},2000);
    return()=>clearInterval(timer);
  },[record?.id,record?.run?.status,dirty]);
  async function action(fn:()=>Promise<void>) {
    if(lock.current)return;lock.current=true;setBusy(true);setError('');setNotice('');
    try{await fn();}catch(e){setError(e instanceof Error?e.message:'Operazione non riuscita.');}finally{lock.current=false;setBusy(false);}
  }
  async function upload(file:File) {
    await action(async()=>{const form=new FormData();form.set('file',file);form.set('title',title);form.set('recorded_at',date);form.set('speaker_one',one);form.set('speaker_two',two);
      const r=await mediaRequest<AudioRecord>('/api/v1/audio',{method:'POST',body:form});await refresh();setSelected(r.id);setNotice('Registrazione salvata. Avvia la trascrizione quando vuoi.');});
  }
  const working=Boolean(record?.run&&!terminal.has(record.run.status));
  return <section className="media-page">
    <div className="page-heading"><h1>Audio</h1><p>Registrazioni già salvate di telefonate e conversazioni. Trascrizione locale, senza microfono.</p></div>
    {readiness&&!readiness.ready&&<p className="connection-notice">{!readiness.engineInstalled?"Dipendenze Audio non installate: avvia AVVIO.cmd -ConAudio sul PC oppure usa il profilo Docker Audio.":"Modello Whisper locale non pronto. Prepara il modello prima della trascrizione."} Puoi comunque caricare le registrazioni.</p>}
    {error&&<div className="connection-error" role="alert">{error}</div>}{notice&&<p role="status">{notice}</p>}
    <div className="system-card audio-upload"><h2>Carica una registrazione</h2>
      <label>Titolo<input value={title} maxLength={200} onChange={e=>setTitle(e.target.value)} disabled={busy}/></label>
      <label>Data della conversazione<input type="datetime-local" value={date} onChange={e=>setDate(e.target.value)} disabled={busy}/></label>
      <label>Interlocutore 1<input value={one} maxLength={200} onChange={e=>setOne(e.target.value)} disabled={busy}/></label>
      <label>Interlocutore 2<input value={two} maxLength={200} onChange={e=>setTwo(e.target.value)} disabled={busy}/></label>
      <button className="upload-button" disabled={busy} onClick={()=>input.current?.click()}>{busy?'Operazione in corso…':'Seleziona file audio'}</button>
      <input ref={input} hidden type="file" accept=".wav,.mp3,.m4a,.mp4,.aac,.flac,.ogg,.opus,.webm" onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void upload(file);}}/>
    </div>
    <div className="audio-workspace"><aside className="system-card"><h2>Registrazioni</h2><button disabled={busy} onClick={()=>void action(refresh)}>Aggiorna elenco</button>
      {!items.length&&<p>Nessuna registrazione caricata.</p>}{items.map(r=><button className={'audio-item '+(selected===r.id?'selected':'')} key={r.id} disabled={busy||dirty} onClick={()=>setSelected(r.id)}><strong>{r.title}</strong><small>{r.recordedAt||new Date(r.createdAt).toLocaleString('it-IT')} · {r.run?statuses[r.run.status]||r.run.status:'Da trascrivere'}</small></button>)}
    </aside><div className="system-card audio-detail">{!record?<p>Seleziona una registrazione per vedere i dettagli.</p>:<>
      <h2>{record.title}</h2><p>{record.name} · {record.recordedAt||'Data non indicata'}</p>
      {record.speakerNames.some(Boolean)&&<p>Interlocutori: {record.speakerNames.filter(Boolean).join(', ')}. Le etichette automatiche vanno verificate: non identificano le persone con certezza.</p>}
      <audio controls preload="none" src={apiBaseUrl+"/api/v1/audio/"+record.id+"/source"}/>
      <div className="media-actions"><button disabled={busy} onClick={()=>void action(()=>downloadMedia('/api/v1/audio/'+record.id+'/source',record.name))}>Scarica audio originale</button>
        <label>Lingua<select value={language} onChange={e=>setLanguage(e.target.value)} disabled={working||busy}><option value="it">Italiano</option><option value="en">Inglese</option><option value="">Rilevamento automatico</option></select></label>
        <label><input type="checkbox" checked={diarize} onChange={e=>setDiarize(e.target.checked)} disabled={working||busy}/>Distingui due interlocutori (modello locale opzionale)</label>
        <button className="upload-button" disabled={busy||working||record.transcript!==null||!readiness?.ready} onClick={()=>void action(async()=>{const run=await mediaRequest<AudioRecord['run']>('/api/v1/audio/'+record.id+'/transcribe',{method:'POST',body:JSON.stringify({language,diarize,expected_speakers:2,expected_version:record.version})});setRecord({...record,run});})}>Avvia trascrizione</button>
        {working&&record.run&&<button disabled={busy||record.run.status==='cancelling'} onClick={()=>void action(async()=>{await runtimeRequest('/runtime/runs/'+record.run!.id+'/cancel',{method:'POST'});setRecord({...record,run:{...record.run!,status:'cancelling'}});})}>Annulla trascrizione</button>}
      </div>
      {record.run&&<p role="status">{statuses[record.run.status]||record.run.status}{['failed','timed_out','interrupted'].includes(record.run.status)&&' · Consulta Attività per i dettagli; puoi avviare un nuovo tentativo esplicito.'}</p>}
      {record.result?.diarization_warning&&<p className="connection-notice">{record.result.diarization_warning}</p>}
      {record.transcript!==null&&<><h3>Trascrizione</h3><small>{record.result?.detected_language} · {record.result?.duration_seconds} secondi · versione {record.version}</small>
        <textarea className="transcript-editor" aria-label="Trascrizione modificabile" value={text} disabled={busy} onChange={e=>{setText(e.target.value);setDirty(true);}}/>
        <div className="media-actions"><button disabled={busy||!dirty} onClick={()=>void action(async()=>{const r=await mediaRequest<AudioRecord>('/api/v1/audio/'+record.id+'/transcript',{method:'PUT',body:JSON.stringify({transcript:text,expected_version:record.version})});setRecord(r);setText(r.transcript??'');setDirty(false);setNotice('Correzioni salvate.');})}>Salva correzioni</button>
        <button disabled={busy||!dirty} onClick={()=>{setText(record.transcript??'');setDirty(false);}}>Scarta correzioni</button>
        <button disabled={busy||dirty} onClick={()=>void action(()=>downloadMedia('/api/v1/audio/'+record.id+'/transcript/download','trascrizione.txt'))}>Scarica testo</button>
        <button disabled={busy||dirty} onClick={()=>void action(async()=>{await mediaRequest('/api/v1/audio/'+record.id+'/library',{method:'POST'});setNotice('Copia della trascrizione aggiunta alla Libreria IA; originale conservato.');})}>Copia in Libreria IA</button></div>
        <p>Puoi allegare il testo scaricato a una richiesta nella chat.</p>
      </>}
    </>}</div></div>
  </section>;
}
