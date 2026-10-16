import {useEffect, useState} from 'react';
import type {BrowserNode, FileArea} from '../types/contracts';
import {filesApi} from '../services/filesApi';

export default function FileEditor({area, rootId, item, token, close, saved}: {
  area: FileArea; rootId: string; item: BrowserNode; token: string;
  close: () => void; saved: () => void;
}) {
  const [text, setText] = useState('');
  const [original, setOriginal] = useState('');
  const [revision, setRevision] = useState('');
  const [error, setError] = useState('');
  const [backup, setBackup] = useState('');
  const [busy, setBusy] = useState(false);
  const dirty = text !== original;
  useEffect(() => {
    let live = true;
    void filesApi.text(area, token, rootId, item.path).then(data => {
      if (live) { setText(data.text); setOriginal(data.text); setRevision(data.revision); }
    }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [area, token, rootId, item.path]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  async function save() {
    setBusy(true); setError('');
    try {
      const content = original.includes("\r\n") && !original.replaceAll("\r\n", "").includes("\n")
        ? text.replace(/\r?\n/g, "\r\n") : text;
      const result = await filesApi.saveText(area, token, rootId, item.path, content, revision);
      setText(content); setRevision(result.revision); setOriginal(content); setBackup(result.backupPath); saved();
    } catch (e) { setError(e instanceof Error ? e.message : 'Salvataggio non riuscito.'); }
    finally { setBusy(false); }
  }
  return <div className="file-modal-shade"><section className="file-modal file-editor" role="dialog" aria-modal="true" aria-labelledby="file-editor-title">
    <header><h2 id="file-editor-title">Modifica {item.name}</h2><button disabled={busy} aria-label="Chiudi editor" onClick={() => { if (!dirty || window.confirm('Scartare le modifiche non salvate?')) close(); }}>×</button></header>
    <small>{item.path} · Testo UTF-8, massimo 1 MiB. Ogni salvataggio conserva un backup nella stessa cartella.</small>
    {!revision && !error && <p role="status">Apertura file…</p>}
    {error && <p className="connection-error" role="alert">{error}</p>}
    {revision && <textarea aria-label="Contenuto del file" spellCheck={false} disabled={busy} value={text} onChange={e => setText(e.target.value)}/>}
    {backup && <p role="status">Salvato. Backup: {backup}</p>}
    <p>Le modifiche al codice richiedono la ricostruzione dei container per essere eseguite. Il prossimo aggiornamento da GitHub potrebbe sostituirle: salvale anche in Git.</p>
    <footer><span>{dirty ? 'Modifiche non salvate' : 'Nessuna modifica in sospeso'}</span><button className="upload-button" disabled={busy || !revision || !dirty} onClick={() => void save()}>{busy ? 'Salvataggio…' : 'Salva con backup'}</button></footer>
  </section></div>;
}
