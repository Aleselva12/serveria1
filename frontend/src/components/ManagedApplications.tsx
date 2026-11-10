import HealthDashboard from "./HealthDashboard";
import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";
type App = { id:string; name:string; repository:string; recoveryUrl?:string; installed:boolean; configured?:boolean; running?:boolean; commit?:string|null; url?:string|null; job?:{status:string;action?:string;phase?:string;message?:string} };
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
 async function action(app:App, acknowledge=false){
  const operation=acknowledge?"acknowledge":app.installed?"update":"install";
  if(!window.confirm(acknowledge?"Confermi di aver verificato nel pannello AIO il completamento o il ripristino? Questa azione sblocca i nuovi lavori senza ripetere il precedente.":app.id==="nextcloud-aio"?"Creare un backup e aggiornare Nextcloud tramite AIO? Il servizio sarà temporaneamente indisponibile.":(app.installed?"Aggiornare ":"Installare ")+app.name+" sul Debian?"))return;
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
 <HealthDashboard componentFilter={["magazzino_tele","preventivi"]} compact />
 {data?.apps.map(app=><div key={app.id}><strong>{app.name}</strong> — {app.running?"Online":app.installed?"Installata, servizio non attivo":"Da installare"}
 <p>{app.repository}</p>{app.commit&&<p>Versione: <code>{app.commit}</code></p>}{app.installed&&!app.configured&&<p>{app.id==="nextcloud-aio"?"Configurare ed eseguire il primo backup nel pannello AIO.":"Configurazione privata e schema necessari."}</p>}<p>{app.job?.status==="running"?(app.job.message||"Operazione in corso"):app.job?.status==="needs_configuration"?"Configura schema e segreti sul Debian":app.job?.status==="failed"?(app.job.message||"Operazione fallita: controlla il servizio host"):(app.job?.message||"")}</p>
 <button className="file-tool" disabled={!data.available||busy||app.job?.status==="running"||app.job?.status==="recovery_required"||(app.id==="nextcloud-aio"&&!app.configured)} onClick={()=>void action(app)}>{app.id==="nextcloud-aio"?"Backup e aggiorna Nextcloud":app.installed?"Aggiorna e verifica":"Installa"}</button>
 {app.id==="nextcloud-aio"&&app.job?.status==="recovery_required"&&<button disabled={busy} onClick={()=>void action(app,true)}>Conferma recupero verificato</button>}
 {app.recoveryUrl&&<a href={app.recoveryUrl} target="_blank" rel="noopener noreferrer">Pannello AIO e ripristino</a>}
 {app.url&&<a href={app.url} target="_blank" rel="noopener noreferrer">Apri gestionale</a>}</div>)}
 </section>}</div>;
}
