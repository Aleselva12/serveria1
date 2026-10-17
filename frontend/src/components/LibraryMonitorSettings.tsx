import { useEffect, useState } from "react";
import { libraryMonitorApi, type MonitorStatus } from "../services/libraryMonitorApi";

export default function LibraryMonitorSettings() {
  const [monitor, setMonitor] = useState<MonitorStatus|null>(null);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const refresh = () => libraryMonitorApi.status().then(setMonitor).catch(e => setError(String(e)));
  useEffect(() => { void refresh(); }, []);
  const deactivate = async (folder: string) => {
    setBusy(true); setError("");
    try { setMonitor(await libraryMonitorApi.setFolder(folder,false)); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  return <div className="section-card">
    <h2>Monitor proattivo · Libreria IA</h2>
    <p>Attiva le cartelle dalla pagina File → Libreria IA. Cora può consultare gli altri documenti su richiesta; la scansione in background controlla solo le cartelle selezionate.</p>
    {!monitor && !error && <p>Caricamento stato del monitor…</p>}
    {error && <p role="alert">{error}</p>}
    {monitor && <>
      <div className="settings-row">
        <div><strong>Ultima scansione</strong>
          <p>{monitor.last_scan ? new Date(monitor.last_scan).toLocaleString("it-IT") : "Non ancora eseguita"} · {monitor.indexed_files} file rilevati</p></div>
        <button disabled={busy} onClick={async () => {setBusy(true);setError("");try {setMonitor(await libraryMonitorApi.scan());}catch(e){setError(String(e));}finally{setBusy(false);}}}>Scansiona ora</button>
      </div>
      {monitor.folders.length === 0 ? <p>Nessuna cartella autorizzata all'analisi proattiva.</p> :
        monitor.folders.map(folder => <div key={folder} className="settings-row">
          <div><strong>{folder}</strong><p>Include tutte le sottocartelle</p></div>
          <button disabled={busy} onClick={() => void deactivate(folder)}>Disattiva</button>
        </div>)}
      <details><summary>Ultimi cambiamenti rilevati ({monitor.events.length})</summary>
        {monitor.events.length === 0 ? <p>Nessuna variazione registrata.</p> :
          <ul>{monitor.events.slice().reverse().map((event,index) =>
            <li key={index}>{event.type === "added" ? "Nuovo" : event.type === "changed" ? "Modificato" : "Rimosso o fuori monitoraggio"} · {event.path} · {new Date(event.at).toLocaleString("it-IT")}</li>)}</ul>}
      </details>
    </>}
  </div>;
}
