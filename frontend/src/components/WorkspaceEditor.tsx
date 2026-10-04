import { useEffect, useState } from "react";
import { programmerApi } from "../services/programmerApi";

export default function WorkspaceEditor({ workspace, path, onClose, onSaved }: {
  workspace: string; path: string; onClose: () => void;
  onSaved: (path: string) => Promise<void>;
}) {
  const [name, setName] = useState(path), [content, setContent] = useState("");
  const [hash, setHash] = useState(""), [initial, setInitial] = useState("");
  const [loading, setLoading] = useState(!!path), [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (path) void programmerApi.fullFile(workspace, path).then(file => {
      if (!active) return;
      if (file.truncated) throw new Error("File incompleto: modifica non consentita.");
      setContent(file.content); setInitial(file.content); setHash(file.sha256); setLoading(false);
    }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [workspace, path]);
  async function save() {
    if (loading || saving || !name.trim()) return;
    setSaving(true); setError("");
    try {
      const saved = await programmerApi.saveFile(workspace, name.trim(), content, hash);
      // Saving succeeded even if refreshing the surrounding panels fails.
      setInitial(content); setHash(saved.sha256);
      await onSaved(name.trim()); onClose();
    } catch (e) { setError(String(e)); }
    finally { setSaving(false); }
  }
  function close() {
    if (content !== initial && !window.confirm("Scartare le modifiche non salvate?")) return;
    onClose();
  }
  return <div className="workspace-editor">
    <p>Modifica soltanto la copia del workspace. Nessuna applicazione al codice attivo.</p>
    {!path && <input aria-label="Percorso nuovo file" value={name} onChange={e => setName(e.target.value)} placeholder="tools/nuovo_tool.py" disabled={saving} />}
    {error && <p role="alert">{error} La bozza resta qui; in caso di conflitto copiala prima di annullare e rileggere il file.</p>}
    <textarea aria-label="Modifica sorgente" value={content} onChange={e => setContent(e.target.value)} disabled={loading || saving} spellCheck={false} rows={22} />
    <div className="programmer-actions">
      <button disabled={loading || saving || !name.trim()} onClick={() => void save()}>{saving ? "Salvataggio…" : "Salva nel workspace"}</button>
      <button disabled={saving} onClick={close}>Annulla modifica</button>
    </div>
  </div>;
}
