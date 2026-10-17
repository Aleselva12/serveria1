import { useEffect, useState } from "react";
import { libraryMonitorApi, type MonitorStatus } from "../services/libraryMonitorApi";

export default function LibraryMonitorFeed({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<MonitorStatus | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const refresh = () => libraryMonitorApi.status()
      .then(result => { if (active) {setData(result);setError("");} })
      .catch(() => {if (active) setError("Monitor Libreria non disponibile.");});
    void refresh();
    const interval = setInterval(() => void refresh(), 60000);
    return () => { active=false; clearInterval(interval); };
  }, []);
  const events = data?.events ?? [];
  const significant = events.filter(event => event.type === "added" || event.type === "removed_or_unwatched");
  const shown = compact ? significant.slice(-5).reverse() : events.slice(-30).reverse();
  return <div className={compact ? "system-card secondary-card" : "section-card"}>
    <h2>{compact ? "Novità Libreria IA" : "Library Monitor · Registro variazioni"}</h2>
    <p className="muted">{compact
      ? "Nuovi file e file non più rilevati nelle cartelle monitorate. Le modifiche ordinarie sono in Attività."
      : "Cronologia delle scansioni del filesystem. Le variazioni non sono ancora analisi semantiche."}</p>
    {!data ? <p>{error || "Caricamento monitor…"}</p> : <>
      <p>{data.folders.length} cartelle abilitate · {data.indexed_files} file rilevati
        {data.last_scan ? " · Scansione " + new Date(data.last_scan).toLocaleString("it-IT") : " · Prima scansione non eseguita"}</p>
      {shown.length === 0 ? <p>Nessuna novità {compact ? "significativa" : "registrata"}.</p> :
        <ul>{shown.map((event,index) => <li key={index}>
          <strong>{event.type === "added" ? "Nuovo file" : event.type === "changed" ? "File modificato" : "File non più rilevato"}</strong>
          {" · "}{event.path}{" · "}{new Date(event.at).toLocaleString("it-IT")}
        </li>)}</ul>}
      {!compact && <small>Il monitor non sposta, modifica né elimina file. Un file non rilevato può essere stato spostato o reso inaccessibile.</small>}
    </>}
  </div>;
}
