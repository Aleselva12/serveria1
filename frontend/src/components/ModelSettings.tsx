import { useEffect, useState } from "react";
import { authenticatedFetch } from "../services/transport";
import { apiBaseUrl } from "../services/api";

type ModelInfo = { name: string; size: number; running: boolean };
type ModelPayload = { active: string; models: ModelInfo[] };

export default function ModelSettings({ onChanged }: { onChanged: () => void }) {
  const [data, setData] = useState<ModelPayload | null>(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/runtime/models");
      if (!response.ok) throw new Error("Impossibile leggere i modelli installati.");
      const payload = await response.json() as ModelPayload;
      setData(payload); setSelected(payload.active); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Modelli non disponibili."); }
  }
  useEffect(() => { void load(); }, []);

  async function save() {
    if (!selected || selected === data?.active) return;
    setSaving(true); setError("");
    try {
      const response = await authenticatedFetch(apiBaseUrl + "/runtime/model", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: selected }),
      });
      if (!response.ok) throw new Error("Cambio modello non riuscito.");
      const payload = await response.json() as ModelPayload;
      setData(payload); setSelected(payload.active); onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : "Cambio modello non riuscito."); }
    finally { setSaving(false); }
  }

  return <div className="settings-model">
    <div>
      <strong>Modello locale</strong>
      <p>Elenco letto direttamente dai modelli installati in Ollama su questa macchina.</p>
    </div>
    {error && <div className="connection-error">{error}</div>}
    <div className="settings-model-controls">
      <select value={selected} disabled={!data || saving} onChange={e => setSelected(e.target.value)}>
        {!data && <option>Caricamento…</option>}
        {data?.models.map(model => <option key={model.name} value={model.name}>
          {model.running ? "● " : "○ "}{model.name} · {(model.size / 1024 / 1024 / 1024).toFixed(1)} GB
        </option>)}
      </select>
      <button className="solid-button" disabled={!data || saving || selected === data.active} onClick={() => void save()}>
        {saving ? "Cambio…" : "Usa modello"}
      </button>
    </div>
    {data && <small>● caricato in memoria · ○ installato ma spento &nbsp; | &nbsp; Selezionato: {data.active}</small>}
  </div>;
}
