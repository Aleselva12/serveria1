import { useEffect, useRef, useState } from "react";
import { mailRequest, type Listing, type Message, type Scope, type Selection } from "../services/mailApi";
import "./Mail.css";
type SummaryJob = { status: string; selection: Selection; scope: Scope; trigger: string; summary: string | null; notice?: string; coverage?: string; queued_at?: string; started_at?: string; finished_at?: string | null };
type SummaryState = { accepted?: boolean; job: SummaryJob | null; pending: SummaryJob | null; nightly: { time: string; timezone: string } };
const scopeLabel: Record<string,string> = { inbox: "Posta in arrivo", unread: "Non lette", yesterday: "Ricevute ieri" };
const selectionLabel: Record<string,string> = { a: "Account A", b: "Account B", all: "Tutti gli account" };
const when = (iso?: string | null) => iso ? new Date(iso).toLocaleString("it-IT", { timeZone: "Europe/Rome" }) : "";
function summaryText(job: SummaryJob): string {
 if (job.status === "running") return "Riepilogo in corso sul server dalle " + when(job.started_at) + ". Può richiedere molti minuti: puoi chiudere la pagina.";
 const main = job.summary || job.notice || (job.status === "empty" ? "Nessuna email nell’ambito selezionato." : "Nessuna email disponibile: verifica i collegamenti.");
 return [main, job.status === "partial" ? "Riepilogo parziale: alcuni account o messaggi non sono inclusi." : "", job.coverage || ""].filter(Boolean).join("\n\n");
}
type Accounts = { accounts: { id: string; email: string; connected: boolean }[]; webAuth: { available: boolean } };
export default function Mail() {
 const [selection, setSelection] = useState<Selection>("all");
 const [scope, setScope] = useState<Scope>("inbox");
 const [accounts, setAccounts] = useState<Accounts | null>(null);
 const [listing, setListing] = useState<Listing | null>(null);
 const [detail, setDetail] = useState<Message | null>(null);
 const [summary, setSummary] = useState<SummaryState | null>(null);
 const [error, setError] = useState("");
 const [busy, setBusy] = useState(false);
 const generation = useRef(0), detailGeneration = useRef(0);
 const showError = (e: unknown) => setError(e instanceof Error ? e.message : "Operazione non disponibile");
 useEffect(() => {
  const id = ++generation.current; ++detailGeneration.current;
  setListing(null); setDetail(null); setError(""); setBusy(true);
  Promise.all([mailRequest<Accounts>("/accounts"), mailRequest<Listing>(`/messages?selection=${selection}&scope=${scope}`)])
   .then(([a,l]) => { if(id === generation.current){setAccounts(a);setListing(l);} })
   .catch(e => {if(id === generation.current) showError(e);})
   .finally(() => {if(id === generation.current) setBusy(false);});
  return () => {++generation.current; ++detailGeneration.current;};
 }, [selection,scope]);
 useEffect(() => {
  let alive = true, timer: ReturnType<typeof setTimeout> | undefined;
  const load = () => mailRequest<SummaryState>("/summary/latest").then(r => {
   if (!alive) return; setSummary(r);
   if (r.pending || r.job?.status === "running") timer = setTimeout(load, 20000);
  }).catch(() => {});
  load();
  return () => { alive = false; if (timer) clearTimeout(timer); };
 }, [summary?.pending?.queued_at, summary?.job?.started_at]);
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
  setError("");
  try{setSummary(await mailRequest<SummaryState>("/summary",{selection,scope}));}catch(e){showError(e);}
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
   <button disabled={busy||!!summary?.pending||summary?.job?.status==="running"} onClick={summarize}>Riepilogo IA dell’ambito</button></div>
  <div className="mail-toolbar">{accounts?.accounts.map(a=><div key={a.id}><span>{a.email} · {a.connected?"Autorizzazione salvata":"Da collegare"} </span><button disabled={busy||!accounts.webAuth.available} onClick={()=>connect(a.id)}>{a.connected?"Ricollega":"Collega"}</button></div>)}</div>
  {accounts&&!accounts.webAuth.available&&<p>Configura OAuth Google sul server prima di collegare gli account.</p>}
  <p role="status">{busy?"Operazione in corso…":""}</p>{error&&<p role="alert">{error}</p>}
  {Object.entries(listing?.errors||{}).map(([a,e])=><p role="alert" key={a}>Account {a.toUpperCase()}: {e}</p>)}
  {summary&&(summary.job||summary.pending)&&<article className="mail-summary"><h2>Riepilogo IA</h2>
   {summary.job&&<><p><small>{selectionLabel[summary.job.selection]||summary.job.selection} · {scopeLabel[summary.job.scope]||summary.job.scope} · {summary.job.trigger==="nightly"?"notturno":"manuale"}{summary.job.finished_at?" · completato "+when(summary.job.finished_at):""}</small></p><p>{summaryText(summary.job)}</p></>}
   {summary.pending&&<p>In coda: {selectionLabel[summary.pending.selection]} · {scopeLabel[summary.pending.scope]}. Parte appena il server è libero.</p>}</article>}
  <div className="mail-columns"><div><h2>Messaggi</h2>{listing&&!listing.messages.length&&<p>Nessun messaggio disponibile nell’ambito selezionato.</p>}
   <ul className="mail-list">{listing?.messages.map(m=><li key={m.account+m.id}><button onClick={()=>open(m)} aria-pressed={detail?.id===m.id&&detail?.account===m.account}><small>{m.email} · {new Date(m.timestamp).toLocaleString("it-IT",{timeZone:"Europe/Rome"})}</small><strong>{m.unread?"• ":""}{m.subject}</strong><span>{m.sender}</span><span>{m.snippet}</span></button></li>)}</ul>
   {listing&&Object.keys(listing.next).length>0&&<button disabled={busy} onClick={more}>Carica altri messaggi</button>}</div>
   <article aria-label="Dettaglio messaggio">{detail?<><h2>{detail.subject}</h2><p>Account: {detail.email}</p><p>Da: {detail.sender}</p><p>A: {detail.to}</p>{detail.cc&&<p>Cc: {detail.cc}</p>}<p>{detail.date}</p><pre>{detail.body||detail.snippet||"Contenuto testuale non disponibile."}</pre><p>HTML e allegati sono consultabili in Gmail.</p></>:<p>Seleziona un messaggio per leggerne i dettagli.</p>}</article></div>
  <aside><h2>Riepilogo notturno</h2><p>Ogni notte alle {summary?.nightly.time||"03:00"} (Europe/Rome) il server riassume le email ricevute il giorno prima su tutti gli account. Il risultato compare qui e, se le notifiche sono attive, ricevi un avviso. Nessuna email viene inviata o modificata.</p><button onClick={template}>Scarica bozza per Automazioni</button></aside>
 </section>;
}
