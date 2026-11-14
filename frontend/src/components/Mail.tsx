import { useEffect, useRef, useState } from "react";
import { mailRequest, type Listing, type Message, type Scope, type Selection } from "../services/mailApi";
import "./Mail.css";
type Accounts = { accounts: { id: string; email: string; connected: boolean }[]; webAuth: { available: boolean } };
export default function Mail() {
 const [selection, setSelection] = useState<Selection>("all");
 const [scope, setScope] = useState<Scope>("inbox");
 const [accounts, setAccounts] = useState<Accounts | null>(null);
 const [listing, setListing] = useState<Listing | null>(null);
 const [detail, setDetail] = useState<Message | null>(null);
 const [summary, setSummary] = useState("");
 const [error, setError] = useState("");
 const [busy, setBusy] = useState(false);
 const generation = useRef(0), detailGeneration = useRef(0);
 const showError = (e: unknown) => setError(e instanceof Error ? e.message : "Operazione non disponibile");
 useEffect(() => {
  const id = ++generation.current; ++detailGeneration.current;
  setListing(null); setDetail(null); setSummary(""); setError(""); setBusy(true);
  Promise.all([mailRequest<Accounts>("/accounts"), mailRequest<Listing>(`/messages?selection=${selection}&scope=${scope}`)])
   .then(([a,l]) => { if(id === generation.current){setAccounts(a);setListing(l);} })
   .catch(e => {if(id === generation.current) showError(e);})
   .finally(() => {if(id === generation.current) setBusy(false);});
  return () => {++generation.current; ++detailGeneration.current;};
 }, [selection,scope]);
 async function connect(account: string){
  setBusy(true);setError("");
  try {const r = await mailRequest<{state:string;completion_key:string;url:string}>(`/accounts/${account}/auth/start`,{});
   sessionStorage.setItem("cora:mail-oauth:"+r.state,r.completion_key);window.location.assign(r.url);
  }catch(e){showError(e);setBusy(false);}
 }
 async function open(m: Message){
  const id=++detailGeneration.current;setDetail(null);setError("");
  try{const r=await mailRequest<Message>(`/accounts/${m.account}/messages/${encodeURIComponent(m.id)}`);if(id===detailGeneration.current)setDetail(r);}
  catch(e){if(id===detailGeneration.current)showError(e);}
 }
 async function more(){
  if(!listing)return;const id=generation.current;setBusy(true);
  const cursors=Object.fromEntries((selection==="all"?["a","b"]:[selection]).map(a=>[a,listing.next[a]||"-"]));
  try{const r=await mailRequest<Listing>(`/messages?selection=${selection}&scope=${scope}&cursors=${encodeURIComponent(JSON.stringify(cursors))}`);
   if(id===generation.current)setListing({...r,errors:{...listing.errors,...r.errors},messages:[...new Map([...listing.messages,...r.messages].map(m=>[m.account+m.id,m])).values()].sort((a,b)=>b.timestamp-a.timestamp)});
  }catch(e){if(id===generation.current)showError(e);}finally{if(id===generation.current)setBusy(false);}
 }
 async function summarize(){
  const id=generation.current;setBusy(true);setSummary("");setError("");
  try{const r=await mailRequest<Listing & {status:string;summary:string|null;notice?:string;coverage?:string}>("/summary",{selection,scope});
   if(id===generation.current)setSummary([r.summary||r.notice||(r.status==="empty"?"Nessuna email nell’ambito selezionato.":"Nessuna email disponibile: verifica i collegamenti."),r.status==="partial"?"Riepilogo parziale: alcuni account o messaggi non sono inclusi.":"",r.coverage||""].filter(Boolean).join("\n\n"));
  }catch(e){if(id===generation.current)showError(e);}finally{if(id===generation.current)setBusy(false);}
 }
 async function template(){
  try{const r=await mailRequest<unknown>(`/automation-template?selection=${selection}`);
   const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:"application/json"}));
   const link=document.createElement("a");link.href=url;link.download="mail-automazione-bozza.json";link.click();URL.revokeObjectURL(url);
  }catch(e){showError(e);}
 }
 return <section className="mail-page"><h1>Mail</h1><p>Consulta separatamente i tuoi account o riuniscili in una sola vista.</p>
  <div className="mail-toolbar"><label>Account <select value={selection} onChange={e=>setSelection(e.target.value as Selection)}>
   <option value="a">Account A · aletessituraselva@gmail.com</option><option value="b">Account B · aleselva97@gmail.com</option><option value="all">Tutti</option></select></label>
   <label>Ambito <select value={scope} onChange={e=>setScope(e.target.value as Scope)}><option value="inbox">Posta in arrivo</option><option value="unread">Non lette</option><option value="yesterday">Ricevute ieri · Europe/Rome</option></select></label>
   <button disabled={busy} onClick={summarize}>Riepilogo IA dell’ambito</button></div>
  <div className="mail-toolbar">{accounts?.accounts.map(a=><div key={a.id}><span>{a.email} · {a.connected?"Autorizzazione salvata":"Da collegare"} </span><button disabled={busy||!accounts.webAuth.available} onClick={()=>connect(a.id)}>{a.connected?"Ricollega":"Collega"}</button></div>)}</div>
  {accounts&&!accounts.webAuth.available&&<p>Configura OAuth Google sul server prima di collegare gli account.</p>}
  <p role="status">{busy?"Operazione in corso…":""}</p>{error&&<p role="alert">{error}</p>}
  {Object.entries(listing?.errors||{}).map(([a,e])=><p role="alert" key={a}>Account {a.toUpperCase()}: {e}</p>)}
  {summary&&<article className="mail-summary"><h2>Riepilogo IA</h2><p>{summary}</p></article>}
  <div className="mail-columns"><div><h2>Messaggi</h2>{listing&&!listing.messages.length&&<p>Nessun messaggio disponibile nell’ambito selezionato.</p>}
   <ul className="mail-list">{listing?.messages.map(m=><li key={m.account+m.id}><button onClick={()=>open(m)} aria-pressed={detail?.id===m.id&&detail?.account===m.account}><small>{m.email} · {new Date(m.timestamp).toLocaleString("it-IT",{timeZone:"Europe/Rome"})}</small><strong>{m.unread?"• ":""}{m.subject}</strong><span>{m.sender}</span><span>{m.snippet}</span></button></li>)}</ul>
   {listing&&Object.keys(listing.next).length>0&&<button disabled={busy} onClick={more}>Carica altri messaggi</button>}</div>
   <article aria-label="Dettaglio messaggio">{detail?<><h2>{detail.subject}</h2><p>Account: {detail.email}</p><p>Da: {detail.sender}</p><p>A: {detail.to}</p>{detail.cc&&<p>Cc: {detail.cc}</p>}<p>{detail.date}</p><pre>{detail.body||detail.snippet||"Contenuto testuale non disponibile."}</pre><p>HTML e allegati sono consultabili in Gmail.</p></>:<p>Seleziona un messaggio per leggerne i dettagli.</p>}</article></div>
  <aside><h2>Futura automazione</h2><p>Riepilogo delle email ricevute il giorno precedente, alle 08:00 Europe/Rome, per l’account selezionato o aggregato. Nessuna automazione attiva e nessun invio configurato.</p><button onClick={template}>Scarica bozza per Automazioni</button></aside>
 </section>;
}
