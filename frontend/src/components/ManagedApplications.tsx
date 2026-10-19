import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";
type App = { id:string; name:string; repository:string; installed:boolean; url?:string|null; job?:{status:string;action?:string} };
type Catalog = { available:boolean; apps:App[] };
export default function ManagedApplications() {
 const [open,setOpen]=useState(false);
 const [data,setData]=useState<Catalog|null>(null);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 async function refresh(){
  try {const r=await authenticatedFetch(apiBaseUrl+"/api/v1/system/apps");
   if(!r.ok) throw Error("Stato applicazioni non disponibile");
   setData(await r.json());setError("");
  }catch(e){setError(String(e))}
 }
 useEffect(()=>{if(open) void refresh()},[open]);
 useEffect(()=>{if(!open||!data?.apps.some(x=>x.job?.status==="running"))return;
 const timer=setInterval(()=>void refresh(),3000);return ()=>clearInterval(timer)},[open,data]);
 async function action(app:App){
  const operation=app.installed?"update":"install";
  if(!window.confirm((app.installed?"Aggiornare ":"Installare ")+app.name+" sul Debian?"))return;
  setBusy(true);
  try{const r=await authenticatedFetch(apiBaseUrl+"/api/v1/system/apps/"+app.id+"/"+operation,{method:"POST"});
   if(!r.ok)throw Error("Operazione non accettata: verificare il servizio host");
   await refresh();
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 return <div className="home-update-actions"><button className="file-tool" onClick={()=>setOpen(x=>!x)}>Gestisci applicazioni</button>
 {open&&<section aria-label="Applicazioni esterne" aria-live="polite">
 <p>Applicazioni autonome: nessun collegamento con gli agenti di Cora.</p>
 <button className="text-button" onClick={()=>void refresh()}>Verifica stato</button>
 {error&&<p role="alert">{error}</p>}
 {!data?.available&&<p>Servizio host per le applicazioni esterne non abilitato. L'installazione richiede configurazione del Debian.</p>}
 {data?.apps.map(app=><div key={app.id}><strong>{app.name}</strong> — {app.installed?"Sorgenti installati":"Da installare"}
 <p>{app.repository}</p><p>{app.job?.status==="running"?"Operazione in corso":app.job?.status==="needs_configuration"?"Configura schema e segreti sul Debian":app.job?.status==="failed"?"Operazione fallita: controlla il servizio host":""}</p>
 <button className="file-tool" disabled={!data.available||busy||app.job?.status==="running"} onClick={()=>void action(app)}>{app.installed?"Aggiorna":"Installa"}</button>
 {app.url&&<a href={app.url} target="_blank" rel="noopener noreferrer">Apri gestionale</a>}</div>)}
 </section>}</div>;
}
