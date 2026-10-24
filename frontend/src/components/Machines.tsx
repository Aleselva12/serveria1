import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";
import { Cpu, Monitor, RefreshCw, Server, Trash2, Plus, Network } from "lucide-react";

type Machine = {
  id: string; name: string; fqdn: string;
  type: "coordinator" | "worker" | "tailnet_device";
  online: boolean | null; worker_ready: boolean;
  capabilities: string[]; registered: boolean;
};
type Inventory = {
  machines: Machine[];
  tailscale_discovery_configured: boolean;
  tailscale_error: string | null;
  execution_enabled: boolean;
};

async function jsonRequest(path: string, init?: RequestInit) {
  const response = await authenticatedFetch(apiBaseUrl + path, {
    ...init,
    headers: { "Accept": "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers },
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error("La macchina è già registrata oppure il limite è stato raggiunto.");
    throw new Error("Richiesta non riuscita (HTTP " + response.status + ").");
  }
  return response.json();
}

export default function Machines() {
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [fqdn, setFqdn] = useState("");

  async function refresh() {
    setLoading(true); setError("");
    try { setInventory(await jsonRequest("/api/v1/machines") as Inventory); }
    catch (e) { setError(e instanceof Error ? e.message : "Inventario non disponibile."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);

  async function add(n = name, h = fqdn) {
    if (busy || !n.trim() || !h.trim()) return;
    setBusy(true); setError("");
    try {
      await jsonRequest("/api/v1/machines", {
        method: "POST", body: JSON.stringify({name:n.trim(), fqdn:h.trim()}),
      });
      setName(""); setFqdn("");
      await refresh();
    } catch(e) { setError(e instanceof Error ? e.message : "Registrazione non riuscita."); }
    finally { setBusy(false); }
  }

  async function remove(machine: Machine) {
    if (busy || !machine.registered || machine.type === "coordinator") return;
    if (!window.confirm("Rimuovere " + machine.name + " dall'inventario Cora? Il PC e Docker non saranno modificati.")) return;
    setBusy(true); setError("");
    try {
      await jsonRequest("/api/v1/machines/" + encodeURIComponent(machine.id), {method: "DELETE"});
      await refresh();
    } catch(e) { setError(e instanceof Error ? e.message : "Rimozione non riuscita."); }
    finally { setBusy(false); }
  }

  return <section className="content-page">
    <div className="page-heading">
      <div><div className="eyebrow">INFRASTRUTTURA DISTRIBUITA</div>
        <h1>Macchine</h1>
        <p>Server centrale e dispositivi Tailscale. Un worker registrato è raggiungibile, ma non esegue lavori finché non gli assegneremo capacità autorizzate.</p>
      </div>
      <button className="text-button" disabled={loading} onClick={() => void refresh()}><RefreshCw size={16}/> {loading ? "Aggiornamento…" : "Aggiorna"}</button>
    </div>
    {error && <div className="connection-error" role="alert">{error}</div>}
    <div className="section-card" style={{marginBottom:16}}>
      <h2><Network size={18}/> Rete privata</h2>
      {inventory?.tailscale_discovery_configured
        ? <p>{inventory.tailscale_error || "Inventario Tailscale collegato in sola lettura."}</p>
        : <p>La scoperta automatica non è ancora configurata. Puoi registrare le macchine manualmente con il loro nome MagicDNS; successivamente potremo usare l'API Tailscale con permessi di sola lettura.</p>}
      <p className="muted">Una macchina presente nella tailnet non è automaticamente un worker. Nessuna macchina può ancora eseguire comandi remoti da questa pagina.</p>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:14}}>
      {(inventory?.machines || []).map(m => <article className="section-card" key={m.id} style={{margin:0}}>
        <div style={{display:"flex",gap:10,alignItems:"center",justifyContent:"space-between"}}>
          <div style={{display:"flex",gap:10,alignItems:"center"}}>
            {m.type === "coordinator" ? <Server size={22}/> : m.type === "worker" ? <Cpu size={22}/> : <Monitor size={22}/>}
            <strong>{m.name}</strong>
          </div>
          <span className="pill">{m.type === "coordinator" ? "Server" : m.type === "worker" ? "Worker" : "Tailscale"}</span>
        </div>
        <p className="muted" style={{wordBreak:"break-all"}}>{m.fqdn || "Debian / API Cora"}</p>
        <p>{m.type === "coordinator" ? "● API raggiungibile" : m.worker_ready ? "● Worker raggiungibile" : m.online === false ? "● Tailscale offline" : m.type === "worker" ? "● Worker non raggiungibile" : m.online ? "● Connesso a Tailscale" : "● Stato non verificato"}</p>
        {m.type === "worker" && <p className="muted">{m.capabilities.length ? m.capabilities.join(", ") : "Nessuna capacità definita · nessuna esecuzione abilitata"}</p>}
        {!m.registered && m.fqdn.endsWith(".ts.net") && <button className="text-button" disabled={busy} onClick={() => void add(m.name, m.fqdn)}><Plus size={15}/> Registra worker</button>}
        {m.type === "worker" && <button className="text-button" disabled={busy} onClick={() => void remove(m)}><Trash2 size={15}/> Scollega dalla pagina</button>}
      </article>)}
    </div>
    <div className="section-card" style={{marginTop:16}}>
      <h2>Aggiungi un worker</h2>
      <p className="muted">Prima avvia il container cora-desktop-worker sul PC e condividi la porta locale con Tailscale Serve (non Funnel). La registrazione non installa software sul PC.</p>
      <form onSubmit={e => {e.preventDefault(); void add();}} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"end"}}>
        <label style={{display:"grid",gap:6,flex:"1 1 180px"}}>Nome
          <input aria-label="Nome macchina" required maxLength={80} value={name} onChange={e=>setName(e.target.value)} placeholder="Desktop" />
        </label>
        <label style={{display:"grid",gap:6,flex:"2 1 280px"}}>Nome Tailscale completo
          <input aria-label="Nome Tailscale" required maxLength={253} value={fqdn} onChange={e=>setFqdn(e.target.value)} placeholder="desktop.tailnet.ts.net" />
        </label>
        <button type="submit" disabled={busy || !name.trim() || !fqdn.trim()}><Plus size={16}/> Registra</button>
      </form>
    </div>
  </section>;
}
