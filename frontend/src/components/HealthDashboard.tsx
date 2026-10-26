import {useEffect, useState} from "react";
import {api, type HealthDashboardData, type HealthCheckDefinition, type HealthResult} from "../services/api";
import {serviceStatusLabels} from "../services/homeStatus";
import {homeRoadmap} from "../services/connections";

const goalIds:Record<string,string[]> = {
  cora:["RUNTIME-MEMORY","AUTO-QUALITY"], files:["FILES-PHOTOS"],
  audio:["AUDIO-WORD"], calendar:["CALENDAR-MAIL"],
  worker:["MODELS-WORKER"], backups:["BACKUP-UPDATE"],
  immich:["FILES-PHOTOS"], nextcloud:["FILES-PHOTOS"],
  magazzino_tele:["WORK-APPS"], preventivi:["WORK-APPS"],
};

import type {ServiceStatus} from "../types/contracts";

const time = (value?:string) => value ? new Date(value).toLocaleString("it-IT") : "Mai";
function statusOf(definition:HealthCheckDefinition, evidence?:HealthResult) {
  if (!evidence) return {label:"Da verificare",tone:"unknown"};
  if (definition.automated && Date.now() - Date.parse(evidence.at) > 10 * 60 * 1000)
    return {label:"Scaduto",tone:"unknown"};
  if (evidence.status === "pass") return {label:definition.kind === "preflight" ? "Prerequisito OK" : definition.kind === "contract" ? "Contratto OK" : "Test OK",tone:"success"};
  if (evidence.status === "fail") return {label:"Errore",tone:"error"};
  return {label:"Non verificato",tone:"unknown"};
}

export default function HealthDashboard({
  services = [], servicesError = "", showServices = false,
  componentFilter, compact = false,
}: {
  services?: ServiceStatus[]; servicesError?:string; showServices?:boolean;
  componentFilter?:string[]; compact?:boolean;
}) {
  const [data,setData] = useState<HealthDashboardData|null>(null);
  const [error,setError] = useState("");
  const [history,setHistory] = useState(false);
  useEffect(() => {
    let active = true, pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const value = await api.healthDashboard();
        if (active) {setData(value);setError("");}
      } catch {
        if (active) {setData(null);setError("Registro dei controlli non raggiungibile.");}
      } finally {pending = false;}
    }
    void refresh();
    const timer = setInterval(() => void refresh(),30000);
    return () => {active = false;clearInterval(timer);};
  }, []);
  const filtered = data?.catalog.filter(c => !componentFilter || componentFilter.includes(c.component)) || [];
  const groups = Object.entries(data?.components || {}).filter(([key]) => filtered.some(c => c.component === key));
  const failures = filtered.filter(c => statusOf(c,data?.latest[c.id]).tone === "error").length;
  const notTested = filtered.filter(c => !data?.latest[c.id]).length;
  return <section id={!componentFilter ? "system-health" : undefined} className={"home-health-dashboard" + (compact ? " compact" : "")}
    aria-label="Salute del sistema e collaudi">
    <div className="metric-head">
      <div><h2>{compact ? "Verifiche e collaudi" : "Salute del sistema e collaudi"}</h2>
        <small>Controlli condivisi · contratti software · prove funzionali</small></div>
      {data && <span className="pill">{failures ? failures+" errori" : notTested ? notTested+" da provare" : "Risultati disponibili"}</span>}
    </div>
    {showServices && <>
      <h3>Disponibilità dei servizi</h3>
      {servicesError && <p role="alert">{servicesError}</p>}
      {services.length ? services.map(item => <div key={item.id} className="mobile-service-row health-service-row">
        <span>{item.browserUrl && /^https?:\/\/[^\s]+$/i.test(item.browserUrl)
          ? <a href={item.browserUrl} target="_blank" rel="noopener noreferrer">{item.label}</a>
          : item.label}</span>
        <span>
          {(item.id==="immich" || item.id==="nextcloud") &&
            <small title="Servizio host di aggiornamento esterno ancora da implementare">Aggiornamento: lavoro 2</small>}
          <strong>{serviceStatusLabels[item.status]}</strong>
        </span>
      </div>) : <p>Elenco servizi non disponibile; questo non certifica un guasto di ogni servizio.</p>}
    </>}
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p>Caricamento del catalogo di collaudo…</p>}
    {data && <>
      <p className="home-health-info">I controlli periodici non eseguono lavori degli utenti. I test end-to-end non automatizzati
        restano «Da verificare» finché non hanno un esito registrato.</p>
      <p className="home-health-info">
        Storico: {data.historyStore === "postgresql" ? "PostgreSQL" : "non disponibile; eventuali risultati temporanei non sono prove persistenti"}.
      </p>
      {groups.map(([id,name]) => {
        const list=filtered.filter(c => c.component === id);
        const bad=list.filter(c => statusOf(c,data.latest[c.id]).tone === "error").length;
        const goals=homeRoadmap.goals.filter(g => (goalIds[id]||[]).includes(g.id));
        return <details key={id} className="home-health-component">
          <summary><strong>{name}</strong><span>{bad ? bad+" errori" : list.length+" verifiche"}</span></summary>
          {goals.map(goal => <div key={goal.id} className="home-health-development">
            <strong>Stato sviluppo: {"development" in goal && goal.development || goal.state}</strong>
            {"observations" in goal && Array.isArray(goal.observations) && goal.observations.length>0 &&
              <small>Verifiche riferite dall'utente: {goal.observations.join(" · ")} (non attestate automaticamente sul commit installato)</small>}
            {"issues" in goal && Array.isArray(goal.issues) && goal.issues.length>0 &&
              <small>Da risolvere: {goal.issues.join(" · ")}</small>}
            {"verification" in goal && Array.isArray(goal.verification) && goal.verification.length>0 &&
              <small>Da collaudare: {goal.verification.join(" · ")}</small>}
          </div>)}
          <div className="home-health-check-list">
          {list.map(item => {
            const last=data.latest[item.id];
            const result=statusOf(item,last);
            return <div key={item.id} className="home-health-check">
              <div className="home-health-check-heading">
                <strong>{item.title}</strong><span className={"pill "+result.tone}>{result.label}</span>
              </div>
              <small>{item.stage} · {item.automated ? "ogni 5 minuti" : "collaudo previsto: "+item.frequency}</small>
              {item.description && <small>{item.description}</small>}
              {item.dependsOn.length > 0 && <small>Dipende da: {item.dependsOn.join(", ")}</small>}
              <small>Ultimo esito: {time(last?.at)} · {last?.environment || "nessuno"}{last?.commit ? " · "+last.commit.slice(0,10):""}</small>
              {last?.detail && <small className={result.tone==="error"?"health-error-detail":""}>{last.detail}</small>}
            </div>;
          })}
          </div>
        </details>;
      })}
      {!componentFilter && <details className="home-health-component" open={history}>
        <summary onClick={event=>{event.preventDefault();setHistory(v=>!v);}}>Ultimi risultati registrati ({data.history.length})</summary>
        {history && <div className="home-health-history">
          {data.history.slice(0,20).map((row,i) => <p key={row.id+row.at+i}>
            <strong>{row.id}</strong> · {row.status} · {time(row.at)} · {row.environment}
            {row.detail ? " · "+row.detail : ""}
          </p>)}
        </div>}
      </details>}
    </>}
  </section>;
}
