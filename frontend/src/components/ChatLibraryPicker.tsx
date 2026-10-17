import { useEffect, useState } from "react";
import { filesApi } from "../services/filesApi";
import type { BrowserNode } from "../types/contracts";

const supported = /\.(txt|md|csv|tsv|json|pdf|docx|py|ts|tsx|js|css|yaml|yml|toml|log)$/i;

export default function ChatLibraryPicker({
  disabled, onClose, onPick,
}: {
  disabled: boolean;
  onClose: () => void;
  onPick: (relativePath: string) => Promise<void>;
}) {
  const [folder, setFolder] = useState("");
  const [items, setItems] = useState<BrowserNode[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    void filesApi.children("library", "", "library", folder, "", page * 100, false)
      .then(result => {
        if (!live) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch(err => {
        if (live) setError(err instanceof Error ? err.message : "Libreria non disponibile.");
      })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [folder, page]);
  const enter = (path: string) => { setFolder(path); setPage(0); };
  async function pick(path: string) {
    setSelecting(true); setError("");
    try { await onPick(path); onClose(); }
    catch (err) { setError(err instanceof Error ? err.message : "Impossibile allegare il documento."); }
    finally { setSelecting(false); }
  }
  return <div className="file-modal-shade">
    <section className="file-modal" role="dialog" aria-modal="true" aria-labelledby="library-picker-title">
      <header>
        <h2 id="library-picker-title">Seleziona dalla Libreria IA</h2>
        <button type="button" disabled={selecting} onClick={onClose} aria-label="Chiudi selezione">×</button>
      </header>
      <p>Il documento viene allegato come copia alla conversazione: nessuna modifica all'originale.</p>
      <div className="settings-row">
        <strong>/{folder || "Libreria IA"}</strong>
        <button type="button" disabled={!folder || loading || selecting} onClick={() => enter(folder.split("/").slice(0, -1).join("/"))}>Cartella superiore</button>
      </div>
      {error && <p role="alert" className="connection-error">{error}</p>}
      {loading ? <p>Caricamento documenti…</p> : items.length === 0 ? <p>Cartella vuota.</p> :
        <div className="file-table-wrap"><table className="file-table"><thead><tr><th>Nome</th><th>Tipo</th><th>Azione</th></tr></thead>
          <tbody>{items.map(item => <tr key={item.path}>
            <td>{item.name}</td><td>{item.kind === "folder" ? "Cartella" : item.kind === "file" ? "Documento" : "Non selezionabile"}</td>
            <td>{item.kind === "folder"
              ? <button type="button" disabled={loading || selecting} onClick={() => enter(item.path)}>Apri</button>
              : item.kind === "file" && supported.test(item.name)
                ? <button type="button" disabled={disabled || selecting || item.sizeBytes == null || item.sizeBytes > 5_000_000} onClick={() => void pick(item.path)}>Allega</button>
                : <span>Formato non supportato</span>}
            </td>
          </tr>)}</tbody>
        </table></div>}
      {total > 100 && <div className="settings-row">
        <button type="button" disabled={page === 0 || loading} onClick={() => setPage(n => n - 1)}>Indietro</button>
        <span>{page * 100 + 1}–{Math.min((page + 1) * 100, total)} di {total}</span>
        <button type="button" disabled={(page + 1) * 100 >= total || loading} onClick={() => setPage(n => n + 1)}>Avanti</button>
      </div>}
    </section>
  </div>;
}
