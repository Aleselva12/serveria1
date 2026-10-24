import { useEffect, useState } from 'react';
import { Cpu, SlidersHorizontal, Sparkles } from 'lucide-react';
import { runtimeRequest } from '../services/runtimeApi';

type Profile = {model:string;machine_id:string;verified:boolean;tools:boolean|null;thinking_values:(boolean|string)[];context_tokens:number;context_max:number|null;transport:string;configuration_id:string};
export default function ChatModelBar({revision,onSettings}: {revision?:string;onSettings:()=>void}) {
  const [profile,setProfile]=useState<Profile|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    let live=true;setProfile(null);setError('');
    runtimeRequest<Profile>('/chat/model-profile').then(p=>{if(live)setProfile(p);}).catch(()=>{if(live)setError('Profilo modello non disponibile.');});
    return ()=>{live=false;};
  },[revision]);
  return <details className="chat-model-profile"><summary><Cpu size={15}/><span>{profile?.model || 'Modello di Cora'}</span><SlidersHorizontal size={14}/></summary>
    <div className="chat-profile-popover">
      <strong>Il modello di questa chat</strong>
      {error && <p role="status">{error}</p>}
      {profile && <><dl>
        <div><dt>Macchina</dt><dd>{profile.machine_id==='local'?'Server Cora':profile.machine_id}</dd></div>
        <div><dt>Contesto configurato</dt><dd>{profile.context_tokens.toLocaleString('it-IT')} token{!profile.context_max?' · massimo non verificato':''}</dd></div>
        <div><dt>Strumenti</dt><dd>{profile.tools===null?'Non verificati':profile.tools?'Supportati':'Non supportati · scegli Nessuno'}</dd></div>
        <div><dt>Thinking</dt><dd>{profile.thinking_values.length===0?'Gestito dal modello · non verificato':profile.thinking_values.every(v=>v===false)?'Non supportato':'Predefinito del modello'}</dd></div>
        <div><dt>Risposta</dt><dd>{profile.transport==='buffered'?'Ricevuta al termine dal desktop':'Progressiva'}</dd></div>
      </dl><small>Capacità dichiarate dal provider, non un collaudo del modello. Nessun cambio automatico.</small></>}
      <button onClick={onSettings}><Sparkles size={14}/> Modello e macchina → Architettura</button>
    </div>
  </details>;
}
