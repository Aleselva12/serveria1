import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

type Failing = { checkId: string; title: string; since: string; failures: number; notified: boolean };
type Transition = { id: string; at: string; kind: string; title: string; detail: string; checkId: string | null; commit: string };
type Timeline = { failing: Failing[]; history: Transition[] };
const REFRESH_MS = 60000;

function when(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

export function isTimeline(value: unknown): value is Timeline {
  const data = value as Timeline;
  return !!data && Array.isArray(data.failing) && Array.isArray(data.history) &&
    data.history.every(t => typeof t.id === "string" && typeof t.title === "string" && typeof t.at === "string");
}

/** OK → error → restored: what is failing now and the recent transitions. */
export default function HealthTimeline() {
  const [data, setData] = useState<Timeline | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/health-transitions", { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error();
        const value = await response.json();
        if (!isTimeline(value)) throw new Error();
        if (active) { setData(value); setError(""); }
      } catch { if (active) setError("Cronologia dei controlli non disponibile."); }
    };
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return <section className="rm2-verification" aria-label="Cronologia dei controlli">
    <h2>Cronologia dei controlli</h2>
    <p>Passaggi OK → errore → ripristinato rilevati dai controlli automatici e dai collaudi sul server. I controlli periodici devono fallire due volte di fila prima di contare.</p>
    {error && <p role="alert">{error}</p>}
    {data && (data.failing.length
      ? <><h3>Ora in errore</h3><ul>{data.failing.map(f => <li key={f.checkId} className="rm2-verification-result result-fail">
          <strong>{f.title}</strong>
          <span>dal {when(f.since)}{f.failures > 1 ? " · " + f.failures + " fallimenti di fila" : ""}{f.notified ? "" : " · avviso non ripetuto (già inviato nelle ultime 6 ore)"}</span>
        </li>)}</ul></>
      : <p role="status">Nessun controllo in errore in questo momento.</p>)}
    {data && <details open={data.history.length > 0 && data.history.length <= 10}>
      <summary>Ultimi passaggi ({data.history.length})</summary>
      {data.history.length === 0 ? <p>Nessun passaggio registrato finora.</p> :
        <ul>{data.history.map(t => <li key={t.id} className={"rm2-verification-result result-" + (t.kind === "failure" ? "fail" : "pass")}>
          <strong>{when(t.at)} · {t.title}</strong>
          <span>{t.detail}</span>
        </li>)}</ul>}
    </details>}
  </section>;
}
