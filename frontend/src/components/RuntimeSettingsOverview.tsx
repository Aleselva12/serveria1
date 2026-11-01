import { useEffect, useState } from "react";
import { Gauge, Layers3, Timer, Workflow } from "lucide-react";
import { authenticatedFetch } from "../services/transport";
import { apiBaseUrl } from "../services/api";

type RuntimeConfiguration = {
  profile: string;
  model: string;
  inference_machine: string;
  inference_transport: string;
  keep_alive: string;
  context_tokens: number;
  output_tokens: number;
  model_timeout_seconds: number | null;
  run_timeout_seconds: number | null;
  queue_size: number;
  db_pool_size: number;
};

export default function RuntimeSettingsOverview() {
  const [data,setData]=useState<RuntimeConfiguration|null>(null);
  const [error,setError]=useState("");
  async function load(){
    setError("");
    try{
      const response=await authenticatedFetch(apiBaseUrl+"/runtime/configuration");
      if(!response.ok) throw new Error("Configurazione runtime non disponibile.");
      setData(await response.json() as RuntimeConfiguration);
    }catch(e){
      setError(e instanceof Error?e.message:"Configurazione runtime non disponibile.");
    }
  }
  useEffect(()=>{void load();},[]);
  return <div className="settings-runtime-overview">
    <div className="settings-section-head">
      <div>
        <span className="settings-kicker">RUNTIME E PRESTAZIONI</span>
        <h2>Parametri effettivi</h2>
        <p>Valori realmente usati dal processo Cora. Quelli legati al deploy restano in sola lettura perché richiedono riavvio o configurazione host.</p>
      </div>
      <button className="text-button" onClick={()=>void load()}>Aggiorna</button>
    </div>
    {error&&<div className="connection-error">{error}</div>}
    {data&&<div className="settings-runtime-grid">
      <div className="settings-stat"><Gauge size={17}/><span>Profilo</span><strong>{data.profile||"default"}</strong></div>
      <div className="settings-stat"><Layers3 size={17}/><span>Contesto</span><strong>{data.context_tokens.toLocaleString("it-IT")} token</strong></div>
      <div className="settings-stat"><Workflow size={17}/><span>Coda run</span><strong>{data.queue_size}</strong></div>
      <div className="settings-stat"><Timer size={17}/><span>Keep-alive</span><strong>{data.keep_alive}</strong></div>
      <div className="settings-stat"><span>Output</span><strong>{data.output_tokens<0?"Senza tetto prefissato":data.output_tokens+" token"}</strong></div>
      <div className="settings-stat"><span>Timeout modello</span><strong>{data.model_timeout_seconds==null?"Disattivato":data.model_timeout_seconds+" s"}</strong></div>
      <div className="settings-stat"><span>Timeout run</span><strong>{data.run_timeout_seconds==null?"Disattivato":data.run_timeout_seconds+" s"}</strong></div>
      <div className="settings-stat"><span>DB pool</span><strong>{data.db_pool_size}</strong></div>
    </div>}
  </div>;
}
