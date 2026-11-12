import type { HealthCheckDefinition, HealthDashboardData, HealthResult } from "../services/api";
import type { Node } from "./model";

export type CheckState = "pass" | "warn" | "fail" | "unknown" | "stale" | "outdated" | "unattributed" | "planned";
export type CheckMapping = Readonly<Record<string, readonly string[]>>;
const fullSha = /^[0-9a-f]{40}$/i;

/** Only the host updater's active release is an authoritative installed revision.
 * A result from CI, an older commit, or with no release provenance cannot
 * certify the currently running Debian deployment.
 */
export function checkState(
  definition: HealthCheckDefinition | undefined,
  result: HealthResult | undefined,
  activeCommit: string | null,
): CheckState {
  if (!definition) return "unknown";
  if (definition.frequency === "to_implement") return "planned";
  if (!result || !Number.isFinite(Date.parse(result.at))) return "unknown";
  if (Date.parse(result.at) > Date.now() + 60_000) return "unknown";
  const maxAge = definition.maxAgeSeconds ?? (definition.automated ? 600 : 86400);
  // Release-scoped checks run after each install: the commit match below bounds them.
  if (!definition.releaseScoped && Date.now() - Date.parse(result.at) > maxAge * 1000) return "stale";
  if (result.status !== "pass" && result.status !== "warn" && result.status !== "fail") return "unknown";
  const release = activeCommit?.trim().toLowerCase() || "";
  const tested = result.commit?.trim().toLowerCase() || "";
  if (!fullSha.test(release) || !fullSha.test(tested)) return "unattributed";
  if (release !== tested) return "outdated";
  return result.status;
}

/** A "warn" result works but reports an advisory: it counts as proof, coloured yellow.
 * Green requires a successful E2E tied to both the installed SHA and the
 * Debian environment. A CI-only E2E or an API preflight does not qualify.
 */
export function verifiedLiveE2E(
  definition: HealthCheckDefinition | undefined,
  result: HealthResult | undefined,
  activeCommit: string | null,
): boolean {
  return definition?.kind === "e2e" &&
    ["pass", "warn"].includes(checkState(definition, result, activeCommit)) &&
    /^debian(?:$|[-_:])/i.test(result?.environment || "");
}

/** Owner-witnessed manual evidence from the map's versioned notes.
 * This records a narrow observation, not a health-check pass, an installed SHA,
 * or a proof that a whole parent/star and all its children are operational.
 */
export function manualEvidence(node: Node): {kind:"ok"|"plan";date:string;text:string}|null {
  const records = (node.observations||[]).filter(o=>
    (o.type==="manual_pass"||o.type==="manual_followup") &&
    /^\d{4}-\d{2}-\d{2}$/.test(o.observedAt||"") && !!o.text
  );
  if(!records.length)return null;
  const latest=[...records].sort((a,b)=>(b.observedAt||"").localeCompare(a.observedAt||""))[0];
  return {kind:latest.type==="manual_pass"?"ok":"plan",date:latest.observedAt!,text:latest.text};
}

/** Future scope is absent, not an untested implementation. */
export const isFuture = (node: Node): boolean => node.status === "planned" || node.status === "idea";

/** Owner scale: green works, yellow works with something to improve, orange
 * problems to check, red does not work, grey not verified (solid) or not yet
 * present (dashed, future). Evidence counts only from the Debian deployment on
 * the active commit; any check kind (e2e, synthetic, contract, preflight) does.
 */
export function starTone(
  node: Node,
  health: HealthDashboardData | null,
  activeCommit: string | null,
  mapping: CheckMapping,
  nodes: readonly Node[] = [],
): string {
  const children = nodes.filter(child => child.parent === node.id);
  const childTones = children.map(child => starTone(child, health, activeCommit, mapping, nodes));
  const aggregate = node.classification === "area" || node.role === "ramo" ||
    ["radici", "tronco", "rami"].includes(node.id);
  if (aggregate) {
    const active = childTones.filter(t => t !== "unknown");
    if (!active.length) return "unknown";
    if (active.every(t => t === "problem")) return "problem";
    if (active.some(t => ["problem", "minor"].includes(t))) return "minor";
    return fromChildren(active);
  }
  if (!["star", "planet", "moon"].includes(node.classification || "")) return "unknown";
  if (isFuture(node)) return "unknown";
  const evidence = (mapping[node.id] || []).map(id => ({def: health?.catalog.find(c => c.id === id), result: health?.latest[id]}));
  const live = (e: typeof evidence[number]) => /^debian(?:$|[-_:])/i.test(e.result?.environment || "");
  const state = (e: typeof evidence[number]) => live(e) ? checkState(e.def, e.result, activeCommit) : "unknown";
  const failed = evidence.filter(e => state(e) === "fail");
  // A failed real E2E means the function does not work; other failures need checking.
  if (failed.some(e => e.def?.kind === "e2e")) return "problem";
  if (failed.length) return "minor";
  if (childTones.some(t => ["problem", "minor"].includes(t))) return "minor";
  if (node.knownIssues?.length) return "minor";
  const manual = manualEvidence(node);
  if (manual?.kind === "plan") return "plan";
  const valid = evidence.filter(e => ["pass", "warn"].includes(state(e)));
  if (valid.some(e => state(e) === "warn")) return "plan";
  if (evidence.length && valid.length === evidence.length) return "ok";
  // Some checks proven, others missing or expired: it works, the proof is incomplete.
  if (valid.length) return "plan";
  if (manual?.kind === "ok") return "ok";
  // No own proof: the element is proven through its planets/moons, like a container.
  return fromChildren(childTones.filter(t => t !== "unknown"));
}
/** Proof through children: green only when every present child works. */
function fromChildren(tones: string[]): string {
  if (tones.length && tones.every(t => t === "ok")) return "ok";
  if (tones.some(t => t === "ok" || t === "plan")) return "plan";
  return "unverified";
}

export const toneLabels: Record<string, string> = {
  ok: "Verde · funziona", problem: "Rosso · non funziona",
  minor: "Arancione · problemi da controllare", plan: "Giallo · funziona, da migliorare",
  unknown: "Grigio tratteggiato · non ancora presente", unverified: "Grigio · non verificato",
};

/** Runtime text shares the same decision as the map, never the static project status. */
export function verificationSummary(node: Node, health: HealthDashboardData | null,
  activeCommit: string | null, mapping: CheckMapping, nodes: readonly Node[] = []): string {
  const tone = starTone(node, health, activeCommit, mapping, nodes);
  const container = node.classification === "area" || node.role === "ramo" || ["radici", "tronco", "rami"].includes(node.id);
  const ids = mapping[node.id] || [];
  const latest = (id: string) => health?.latest[id];
  const state = (id: string) => /^debian(?:$|[-_:])/i.test(latest(id)?.environment || "")
    ? checkState(health?.catalog.find(c => c.id === id), latest(id), activeCommit) : "unknown";
  const manual = manualEvidence(node);
  if (tone === "unknown") return "Non ancora presente: obiettivo futuro, escluso dalla verifica del genitore.";
  if (container) return {
    ok: "Funziona: tutti i sottoelementi presenti sono verificati.",
    plan: "Funziona in parte: alcuni sottoelementi sono da migliorare o non ancora verificati.",
    minor: "Problemi da controllare in uno o più sottoelementi.",
    problem: "Non funziona: tutti i sottoelementi verificati hanno collaudi falliti.",
  }[tone] || "Non verificato: nessun sottoelemento ha prove valide sulla versione attiva.";
  if (tone === "problem") return "Non funziona: collaudo reale fallito sulla versione attiva. Consultare gli esiti collegati.";
  if (tone === "minor") {
    if (ids.some(id => state(id) === "fail")) return "Problemi da controllare: un controllo collegato è fallito sulla versione attiva.";
    if (node.knownIssues?.length) return "Problemi da controllare: criticità documentate su questo elemento.";
    return "Problemi da controllare in un sottoelemento.";
  }
  if (tone === "ok") return manual?.kind === "ok" && !ids.length
    ? "Funziona: verifica manuale circoscritta del "+manual.date+": "+manual.text
    : ids.length ? "Funziona: tutti i controlli collegati superati sulla versione attiva."
    : "Funziona: verificato tramite i sottoelementi.";
  if (tone === "plan") {
    const warns = ids.filter(id => state(id) === "warn").map(id => latest(id)!.detail);
    if (warns.length) return "Funziona, con avvisi da risolvere: "+warns.join(" · ");
    if (manual?.kind === "plan") return "Funziona. Rifinitura da eseguire (osservazione manuale del "+manual.date+"): "+manual.text;
    if (!ids.length) return "Funziona in parte: alcuni sottoelementi sono da migliorare o non ancora verificati.";
    return "Funziona, ma non tutti i controlli collegati hanno un esito valido sulla versione attiva.";
  }
  if (!health || health.historyStore === "unavailable") return "Non verificato: registro dei collaudi non disponibile. Non indica un guasto.";
  if (!activeCommit) return "Non verificato: versione attiva non verificabile. Non indica un guasto.";
  if (!ids.length) return "Non verificato: nessun controllo collegato a questo elemento.";
  const states = ids.map(state);
  if (states.includes("outdated")) return "Non verificato: esiti riferiti a un’altra versione; ripetere il collaudo.";
  if (states.includes("stale")) return "Non verificato: esiti scaduti; ripetere il collaudo.";
  if (states.includes("unattributed")) return "Non verificato: commit del collaudo non verificabile.";
  return "Non verificato: nessun esito valido sul Debian per la versione attiva.";
}


export type NodeIndicator = {label:string;color:string};
export const indicatorColors = {gray:"#8994a5",blue:"#60a5fa",green:"#34d399",yellow:"#facc15",orange:"#fb923c",red:"#f87171"};
/** Declared implementation only: tests and descendants cannot change it. */
export function developmentIndicator(node:Node):NodeIndicator {
  if(isFuture(node))return {label:"Non implementato",color:indicatorColors.gray};
  if(node.status==="partial")return {label:"Sviluppo parziale",color:indicatorColors.blue};
  if(node.status==="present")return {label:"Implementato (dichiarato)",color:indicatorColors.green};
  return {label:"Sviluppo da valutare",color:indicatorColors.gray};
}
/** Exact-node evidence only. Legacy map aggregation remains in starTone. */
export function verificationIndicator(node:Node,health:HealthDashboardData|null,
  activeCommit:string|null,mapping:CheckMapping):NodeIndicator {
  const evidence=(mapping[node.id]||[]).map(id=>({
    def:health?.catalog.find(c=>c.id===id),result:health?.latest[id]
  }));
  const live=(e:typeof evidence[number])=>/^debian(?:$|[-_:])/i.test(e.result?.environment||"");
  const failed=(e:typeof evidence[number])=>live(e)&&checkState(e.def,e.result,activeCommit)==="fail";
  if(evidence.some(failed))return evidence.every(e=>e.def?.kind==="e2e"&&failed(e))
    ?{label:"Collaudo fallito",color:indicatorColors.red}
    :{label:"Verifiche con criticità",color:indicatorColors.orange};
  if(node.knownIssues?.length)return {label:"Criticità documentate",color:indicatorColors.orange};
  const manual=manualEvidence(node);
  if(manual?.kind==="plan")return {label:"Rifinitura aperta · osservazione manuale del "+manual.date,color:indicatorColors.yellow};
  if(manual?.kind==="ok")return {label:"Verifica manuale circoscritta del "+manual.date,color:indicatorColors.green};
  const valid=evidence.filter(e=>live(e)&&["pass","warn"].includes(checkState(e.def,e.result,activeCommit)));
  if(evidence.length&&valid.length===evidence.length)
    return valid.some(e=>checkState(e.def,e.result,activeCommit)==="warn")
      ?{label:"Funziona · avvisi da risolvere",color:indicatorColors.yellow}
      :{label:"Controlli superati sulla versione attiva",color:indicatorColors.green};
  if(valid.length)return {label:"Controlli superati in parte · altri da ripetere",color:indicatorColors.yellow};
  return {label:evidence.length?"Non verificato · nessun esito reale valido":"Non verificato · nessun controllo associato",color:indicatorColors.gray};
}
