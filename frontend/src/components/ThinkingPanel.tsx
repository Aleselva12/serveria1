import { useEffect, useState } from "react";
import { runtimeRequest } from "../services/runtimeApi";

export type ThinkingState = { text: string; truncated: boolean };
type Evidence = {id:number; run_id:string; created_at:string; kind:string; name:string; status:string};
type EvidencePage = {items:Evidence[];next_before:number|null;write_failures_since_restart:number};
export default function ThinkingPanel({ value, threadId, running = false }: { value: ThinkingState; threadId?:string; running?:boolean }) {
  const [history,setHistory] = useState<EvidencePage>({items:[],next_before:null,write_failures_since_restart:0});
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  useEffect(()=>{
    let disposed=false;
    setHistory({items:[],next_before:null,write_failures_since_restart:0}); setError("");setLoading(false);
    async function refresh() {
      if (!threadId) return;
      try {
        const page=await runtimeRequest<EvidencePage>("/chat/consultations/"+encodeURIComponent(threadId));
        if (!disposed) {setHistory(page);setError("");}
      } catch {if (!disposed) setError("Storico consultazioni non disponibile.");}
    }
    void refresh(); const timer=running ? setInterval(()=>void refresh(),5000) : undefined;
    return ()=>{disposed=true;if(timer) clearInterval(timer);};
  },[threadId,running]);
  async function older() {
    if (!threadId||!history.next_before||loading) return;
    const selectedThread=threadId;
    setLoading(true);
    try {
      const page=await runtimeRequest<EvidencePage>("/chat/consultations/"+encodeURIComponent(selectedThread)+"?before="+history.next_before);
      setHistory(previous=>({...page,items:[...previous.items,...page.items.filter(item=>!previous.items.some(old=>old.id===item.id))]}));setError("");
    } catch {setError("Impossibile caricare i passaggi precedenti.");}
    finally {setLoading(false);}
  }
  return <details className="thinking-panel"><summary>Ragionamento e consultazioni</summary>
    <p>Storico privato della conversazione, dal momento dell’aggiornamento. Ultimi passaggi prima; nessuna ricostruzione retroattiva.</p>
    {error&&<p role="alert">{error}</p>}
    {history.write_failures_since_restart>0&&<p>Alcuni passaggi potrebbero mancare: errori di registrazione dall’avvio del servizio.</p>}
    <ul>{history.items.map(item=><li key={item.id}>{new Date(item.created_at).toLocaleString()} · {item.kind} · {item.name} · {item.status} · esecuzione {item.run_id.slice(0,8)}</li>)}</ul>
    {!history.items.length&&!error&&<p>Nessun passaggio registrato. Non prova l’assenza di operazioni.</p>}
    {history.next_before&&<button disabled={loading} onClick={()=>void older()}>Passaggi precedenti</button>}
    {value.text&&<>
    <p>Testo emesso dal modello; non certifica operazioni eseguite. Ultima chiamata, disponibile nella vista corrente.</p>
    {value.truncated && <p>Mostrata soltanto la parte più recente; la generazione prosegue senza tagli.</p>}
    <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: "18rem", overflow: "auto"}}>{value.text}</pre>
    </>}
  </details>;
}
