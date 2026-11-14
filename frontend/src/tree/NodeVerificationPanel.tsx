import {useEffect, useRef, useState} from "react";
import {apiBaseUrl, type HealthResult} from "../services/api";
import {authenticatedFetch} from "../services/transport";

type Run = {
  id:string; status:"running"|"completed"|"failed"|"interrupted";
  total:number; completed:number; currentCheck:string|null; updatedAt:string;
  detail:string; results:HealthResult[];
  hostMaintenance?:{status:string;rollbackAvailable?:boolean};
  targets?:{desktopMachineId:string|null;laptopMachineId:string|null};
};
type Check = {id:string;title:string};
type State = {run:Run|null;availableChecks:Check[];unavailableChecks:Check[]};
type Machine = {id:string;name:string;registered:boolean;type:string};
const endpoint=apiBaseUrl+"/api/v1/system/node-verification";
const resultLabels:Record<string,string>={pass:"Superato",fail:"Fallito",unknown:"Non verificato",skipped:"Saltato"};

async function read<T>(response:Response):Promise<T>{
  if(!response.ok){
    let detail="Servizio collaudi non disponibile. Verifica che il server sia aggiornato.";
    try{const data=await response.json();if(typeof data.detail==="string")detail=data.detail;}catch{/* keep the actionable fallback */}
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export default function NodeVerificationPanel({onResults}:{onResults:()=>void}){
  const [state,setState]=useState<State|null>(null);
  const [error,setError]=useState("");
  const [starting,setStarting]=useState(false);
  const [refreshKey,setRefreshKey]=useState(0);
  const [machines,setMachines]=useState<Machine[]>([]);
  const [desktop,setDesktop]=useState("");
  const [laptop,setLaptop]=useState("");
  const callback=useRef(onResults),observed=useRef("");
  const mounted=useRef(true),launchPending=useRef(false),targetsRestored=useRef(false);
  callback.current=onResults;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    let active=true;
    void authenticatedFetch(apiBaseUrl+"/api/v1/machines").then(r=>read<{machines:Machine[]}>(r)).then(data=>{
      if(active)setMachines((data.machines||[]).filter(m=>m.registered&&m.type==="worker"));
    }).catch(()=>{/* Optional destinations; checks explain missing prerequisites. */});
    return()=>{active=false;};
  },[]);
  useEffect(()=>{
    let active=true,timer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    async function refresh(){
      let running=false;
      try{
        const data=await read<State>(await authenticatedFetch(endpoint,{signal:controller.signal}));
        if(!active)return;
        if(!Array.isArray(data.availableChecks)||!Array.isArray(data.unavailableChecks)||
           (data.run&&!Array.isArray(data.run.results)))throw new Error("Formato dello stato non disponibile. Verifica l'aggiornamento del server.");
        setState(data);setError("");running=data.run?.status==="running";
        if(!targetsRestored.current){
          targetsRestored.current=true;
          if(data.run?.targets){setDesktop(data.run.targets.desktopMachineId||"");setLaptop(data.run.targets.laptopMachineId||"");}
        }
        const revision=data.run?data.run.id+":"+data.run.completed+":"+data.run.status:"";
        if(revision!==observed.current){observed.current=revision;callback.current();}
      }catch(e){if(active)setError(e instanceof Error?e.message:"Stato collaudi non disponibile.");}
      if(active)timer=setTimeout(()=>void refresh(),running?2000:15000);
    }
    void refresh();
    return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[refreshKey]);
  const job=state?.run,running=job?.status==="running";
  async function start(){
    if(launchPending.current||running)return;
    launchPending.current=true;
    setStarting(true);setError("");
    try{
      const job=await read<Run>(await authenticatedFetch(endpoint,{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({desktopMachineId:desktop||null,laptopMachineId:laptop||null})}));
      if(mounted.current)setState(old=>old?{...old,run:job}:null);
    }catch(e){if(mounted.current)setError(e instanceof Error?e.message:"Avvio non riuscito.");}
    finally{launchPending.current=false;if(mounted.current){setStarting(false);setRefreshKey(v=>v+1);}}
  }
  const title=(id:string)=>state?.availableChecks.find(c=>c.id===id)?.title||id;
  const failed=job?.results.filter(r=>r.status==="fail").length||0;
  const passed=job?.results.filter(r=>r.status==="pass").length||0;
  const unknown=job?.results.filter(r=>r.status!=="pass"&&r.status!=="fail").length||0;
  return <section className="rm2-verification" aria-label="Collaudo manuale dal sito">
    <div className="rm2-verification-heading"><div><h2>Collaudi della mappa</h2>
      <p>Un clic avvia una sola esecuzione sul server. La mappa si aggiorna anche dopo operazioni reali confermate su Calendar e worker; qui rimane lo storico dell’ultima suite.</p></div>
      <button type="button" onClick={()=>void start()} disabled={starting||running||!state||Boolean(error)}>
        {starting?"Avvio…":running?"Collaudi in corso…":"Avvia collaudi una tantum"}
      </button></div>
    {machines.length>0&&<details><summary>Destinazioni dei test di inferenza (facoltative)</summary>
      {([['Desktop',desktop,setDesktop],['Laptop',laptop,setLaptop]] as const).map(([name,value,set])=><label key={name}>{name}
        <select value={value} disabled={starting||running} onChange={e=>set(e.target.value)}><option value="">Usa configurazione del server</option>
          {machines.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>)}
      <p>I test usano il modello già selezionato in Macchine. Per spostare la chat principale sul desktop, assegna quel worker al Supervisor in Architettura.</p>
    </details>}
    {error&&<p role="alert">{error} <button type="button" onClick={()=>setRefreshKey(v=>v+1)}>Riprova stato</button></p>}
    {!state&&!error&&<p role="status">Caricamento collaudi disponibili…</p>}
    {job&&<><p role="status" aria-live="polite">{running?"In esecuzione":job.status==="interrupted"?"Interrotto":job.status==="failed"?"Terminato con errori":"Terminato"} · {job.completed}/{job.total}
      {running&&job.currentCheck?" · "+title(job.currentCheck):""}</p>
      <progress max={job.total||1} value={job.completed} aria-label="Avanzamento dei collaudi"/>
      <p>{passed} superati · {failed} falliti · {unknown} non verificati o saltati. {job.detail}</p>
      {job.hostMaintenance?.status==="updated"&&<p>Aggiornamento prerequisito updater eseguito automaticamente. Copia precedente conservata per il ripristino.</p>}
      <details open={!running}><summary>Esiti dell'ultima esecuzione</summary>
        <ul>{job.results.map(r=><li key={r.id} className={"rm2-verification-result result-"+r.status}>
          <strong>{title(r.id)} · {resultLabels[r.status]}</strong><span>{r.detail}</span></li>)}</ul>
      </details></>}
    {state&&<p>{state.availableChecks.length} controlli eseguibili. {state.unavailableChecks.length} ancora senza un collaudo eseguibile.</p>}
    {Boolean(state?.unavailableChecks.length)&&<details><summary>Controlli ancora da implementare</summary><ul>{state!.unavailableChecks.map(c=><li key={c.id}>{c.title}</li>)}</ul></details>}
  </section>;
}
