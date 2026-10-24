import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";
import { Cpu, Monitor, RefreshCw, Server, Trash2, Plus, Network } from "lucide-react";

type Profile = "heavy" | "medium" | "light";
type WorkerConfig = {
  enabled: boolean;
  selected_model: string;
  active_profile: Profile;
  profiles: Record<Profile, string>;
};
type Machine = {
  id: string;
  name: string;
  fqdn: string;
  type: "coordinator" | "worker" | "tailnet_device";
  online: boolean | null;
  worker_ready: boolean;
  capabilities: string[];
  registered: boolean;
} & Partial<WorkerConfig>;
type Inventory = {
  machines: Machine[];
  tailscale_discovery_configured: boolean;
  tailscale_error: string | null;
  execution_enabled: boolean;
};
type InstalledModel = { name: string; size_bytes: number };
type ModelsResponse = {
  models: InstalledModel[];
  reachable: boolean;
  settings: WorkerConfig;
};

async function jsonRequest<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await authenticatedFetch(apiBaseUrl + path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      // The API returns specific, safe diagnostic messages. Do not hide
      // missing backend token behind the generic "Ollama offline" message.
      const failure = await response.json().catch(() => null) as { detail?: unknown } | null;
      const detail = typeof failure?.detail === "string" ? failure.detail.slice(0, 250) : "";
      if (detail) throw new Error(detail);
      throw new Error("Richiesta non riuscita (HTTP " + response.status + ").");
    }
    return await response.json() as T;
  } finally {
    window.clearTimeout(timer);
  }
}

function WorkerPanel({ machine, onRemove }: { machine: Machine; onRemove: (m: Machine) => void }) {
  const [installed, setInstalled] = useState<InstalledModel[]>([]);
  const [config, setConfig] = useState<WorkerConfig>({
    enabled: machine.enabled ?? false,
    selected_model: machine.selected_model ?? "",
    active_profile: machine.active_profile ?? "heavy",
    profiles: machine.profiles ?? {
      heavy: "gpt-oss:20b", medium: "qwen3:8b-q8_0", light: "qwen3:4b-q8_0",
    },
  });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [message, setMessage] = useState("");
  const [test, setTest] = useState("");
  const route = "/api/v1/machines/" + encodeURIComponent(machine.id);
  async function load() {
    setLoading(true); setMessage(""); setFetched(false);
    try {
      const response = await jsonRequest<ModelsResponse>(route + "/models");
      if (!response.reachable || !Array.isArray(response.models)) throw new Error("Ollama Windows non disponibile.");
      setInstalled(response.models);
      setConfig(response.settings);
      setFetched(true);
    } catch (e) {
      setInstalled([]);
      setMessage(e instanceof Error ? e.message : "Elenco modelli non disponibile.");
    } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [machine.id]);
  async function save(next: WorkerConfig, success: string) {
    setBusy(true); setMessage(""); setTest("");
    try {
      const saved = await jsonRequest<WorkerConfig>(route + "/settings", {
        method: "PUT", body: JSON.stringify(next),
      });
      setConfig(saved);
      setMessage(success);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Impostazioni non salvate.");
    } finally { setBusy(false); }
  }
  async function runTest() {
    setBusy(true); setTest(""); setMessage("");
    try {
      const result = await jsonRequest<{ response: string; model: string }>(
        route + "/test", { method: "POST" }, 330000,
      );
      setTest(result.model + ": " + (result.response || "(nessuna risposta)"));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Test non riuscito.");
    } finally { setBusy(false); }
  }
  const names = new Set(installed.map(m => m.name));
  const canRun = fetched && names.has(config.selected_model) && machine.worker_ready;
  return <div style={{marginTop:14,display:"grid",gap:12}}>
    <div style={{display:"flex",gap:10,alignItems:"center",justifyContent:"space-between",flexWrap:"wrap"}}>
      <label style={{display:"flex",gap:8,alignItems:"center"}}>
        <input aria-label={"Abilita worker " + machine.name} type="checkbox"
          checked={config.enabled} disabled={busy}
          onChange={event => void save({...config, enabled:event.target.checked},
            event.target.checked ? "Worker abilitato manualmente." : "Worker disattivato.")} />
        <strong>{config.enabled ? "Worker ON" : "Worker OFF"}</strong>
      </label>
      <button type="button" className="text-button" disabled={busy || loading} onClick={() => void load()}>
        <RefreshCw size={15} /> {loading ? "Caricamento…" : "Ricarica modelli"}
      </button>
    </div>
    <p className="muted">
      Il modello viene scelto solo da te. L'elenco viene letto da Ollama Windows:
      selezionare un modello non lo scarica e non lo carica immediatamente in VRAM.
      L'interruttore ON/OFF è indipendente dalla connessione: ON senza un modello disponibile
      non avvia alcuna inferenza.
    </p>
    <label style={{display:"grid",gap:6}}>
      <strong>Modello attivo del desktop</strong>
      <select aria-label="Modello attivo del desktop" disabled={busy || loading || !fetched || installed.length === 0}
        value={config.selected_model}
        onChange={event => void save({...config, selected_model:event.target.value},
          "Modello selezionato. Le assegnazioni degli agenti a modelli precedenti vanno aggiornate in Architettura.")}>
        {!config.selected_model && <option value="">Scegli un modello installato</option>}
        {config.selected_model && !names.has(config.selected_model) &&
          <option value={config.selected_model}>{config.selected_model} · non installato</option>}
        {installed.map(model => <option key={model.name} value={model.name}>
          {model.name + " · " + (model.size_bytes / 1e9).toFixed(1) + " GB su disco"}
        </option>)}
      </select>
    </label>
    <div>
      <strong>Modelli installati sul PC{fetched ? " · " + installed.length : ""}</strong>
      {fetched && installed.length === 0 && <p className="muted">Nessun modello installato su Ollama Windows.</p>}
      {fetched && installed.length > 0 && <div style={{display:"grid",gap:6,marginTop:8}}>
        {installed.map(model => <label key={model.name} style={{display:"flex",alignItems:"center",gap:9,
          padding:9,borderRadius:7,background:config.selected_model === model.name ? "var(--surface-secondary, rgba(120,120,120,.12))" : "transparent",
          border:"1px solid var(--border-subtle, rgba(120,120,120,.22))"}}>
          <input type="radio" name={"worker-model-"+machine.id}
            checked={config.selected_model === model.name} disabled={busy || loading}
            onChange={() => void save({...config, selected_model:model.name},
              "Modello selezionato. Se un agente usava il precedente, aggiorna la sua assegnazione in Architettura.")}/>
          <span style={{flex:1,overflowWrap:"anywhere"}}>{model.name}</span>
          <small className="muted">{(model.size_bytes / 1e9).toFixed(1)} GB</small>
        </label>)}
      </div>}
    </div>
    <p className="muted">
      {config.selected_model ? "Selezionato: " + config.selected_model : "Nessun modello selezionato."}
      {" "}Le dimensioni indicate riguardano i pesi su disco, non la VRAM effettivamente utilizzata.
    </p>
    <div style={{display:"flex",gap:12,alignItems:"center",flexWrap:"wrap"}}>
      <button type="button" disabled={busy || !config.enabled || !canRun} onClick={() => void runTest()}>
        Prova inferenza
      </button>
      <button type="button" className="text-button" disabled={busy} onClick={() => onRemove(machine)}>
        <Trash2 size={15}/> Rimuovi dalla pagina
      </button>
    </div>
    {message && <p role="status">{message}</p>}
    {test && <p role="status" style={{overflowWrap:"anywhere"}}>{test}</p>}
  </div>;
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
    try { setInventory(await jsonRequest<Inventory>("/api/v1/machines", undefined, 25000)); }
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
    } catch (e) { setError(e instanceof Error ? e.message : "Registrazione non riuscita."); }
    finally { setBusy(false); }
  }

  async function remove(machine: Machine) {
    if (busy || !machine.registered || machine.type !== "worker") return;
    if (!window.confirm("Rimuovere " + machine.name + " dall'inventario? Il PC e Docker non saranno modificati.")) return;
    setBusy(true); setError("");
    try {
      await jsonRequest("/api/v1/machines/" + encodeURIComponent(machine.id), {method:"DELETE"});
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Rimozione non riuscita."); }
    finally { setBusy(false); }
  }

  return <section className="content-page">
    <div className="page-heading">
      <div><div className="eyebrow">INFRASTRUTTURA DISTRIBUITA</div><h1>Macchine</h1>
        <p>Server Debian, desktop e futuri laptop. Elenco completo dei modelli installati con selezione manuale per macchina.</p>
      </div>
      <button className="text-button" disabled={loading} onClick={() => void refresh()}>
        <RefreshCw size={16} /> {loading ? "Aggiornamento…" : "Aggiorna"}
      </button>
    </div>
    {error && <div className="connection-error" role="alert">{error}</div>}
    <div className="section-card" style={{marginBottom:16}}>
      <h2><Network size={18}/> Rete privata</h2>
      <p>{inventory?.tailscale_discovery_configured
        ? (inventory.tailscale_error || "Inventario Tailscale collegato in sola lettura.")
        : "Inventario automatico non configurato. Registra manualmente il nome MagicDNS del dispositivo; l'API Tailscale resta facoltativa."}</p>
      <p className="muted">Tailscale non assegna permessi di calcolo. Il worker nasce OFF e il modello si sceglie manualmente: gli agenti non possono modificarlo.</p>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(310px,1fr))",gap:14}}>
      {(inventory?.machines || []).map(m => <article className="section-card" key={m.id} style={{margin:0}}>
        <div style={{display:"flex",gap:10,alignItems:"center",justifyContent:"space-between"}}>
          <div style={{display:"flex",gap:10,alignItems:"center"}}>
            {m.type === "coordinator" ? <Server size={22}/> : m.type === "worker" ? <Cpu size={22}/> : <Monitor size={22}/>}
            <strong>{m.name}</strong>
          </div>
          <span className="pill">{m.type === "coordinator" ? "Server" : m.type === "worker" ? "Worker" : "Tailscale"}</span>
        </div>
        <p className="muted" style={{overflowWrap:"anywhere"}}>{m.fqdn || "Debian / API Cora"}</p>
        <p>{m.type === "coordinator" ? "● API raggiungibile" : m.worker_ready ? "● Connessione HTTP al worker OK (modelli da verificare)" :
          m.online === false ? "● Tailscale offline" : m.type === "worker" ? "● Worker non raggiungibile" :
          m.online ? "● Connesso a Tailscale" : "● Stato non verificato"}</p>
        {m.type === "worker" && <details style={{marginTop:10}}>
          <summary style={{cursor:"pointer",fontWeight:600}}>Gestisci modelli e risorse del desktop</summary>
          <WorkerPanel machine={m} onRemove={machine => void remove(machine)}/>
        </details>}
        {!m.registered && m.fqdn.endsWith(".ts.net") &&
          <button type="button" className="text-button" disabled={busy} onClick={() => void add(m.name,m.fqdn)}>
            <Plus size={15}/> Registra worker
          </button>}
      </article>)}
    </div>
    <div className="section-card" style={{marginTop:16}}>
      <h2>Aggiungi un worker</h2>
      <p className="muted">Avvia il container Windows con Tailscale Serve. La registrazione non installa software, non scarica modelli e non dà accesso al Docker Engine.</p>
      <form onSubmit={event => {event.preventDefault(); void add();}} style={{display:"flex",flexWrap:"wrap",gap:10,alignItems:"end"}}>
        <label style={{display:"grid",gap:6,flex:"1 1 180px"}}>Nome
          <input required maxLength={80} value={name} onChange={event => setName(event.target.value)} placeholder="Desktop"/>
        </label>
        <label style={{display:"grid",gap:6,flex:"2 1 280px"}}>Nome Tailscale completo
          <input required maxLength={253} value={fqdn} onChange={event => setFqdn(event.target.value)} placeholder="desktop.tailnet.ts.net"/>
        </label>
        <button type="submit" disabled={busy || !name.trim() || !fqdn.trim()}><Plus size={16}/> Registra</button>
      </form>
    </div>
  </section>;
}
