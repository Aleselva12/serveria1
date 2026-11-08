import type { HealthCheckDefinition, HealthDashboardData, HealthResult } from "../services/api";
import type { Node } from "./model";

export type CheckState = "pass" | "fail" | "unknown" | "stale" | "outdated" | "unattributed" | "planned";
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
  if (Date.now() - Date.parse(result.at) > maxAge * 1000) return "stale";
  if (result.status !== "pass" && result.status !== "fail") return "unknown";
  const release = activeCommit?.trim().toLowerCase() || "";
  const tested = result.commit?.trim().toLowerCase() || "";
  if (!fullSha.test(release) || !fullSha.test(tested)) return "unattributed";
  if (release !== tested) return "outdated";
  return result.status;
}

/** Green requires a successful E2E tied to both the installed SHA and the
 * Debian environment. A CI-only E2E or an API preflight does not qualify.
 */
export function verifiedLiveE2E(
  definition: HealthCheckDefinition | undefined,
  result: HealthResult | undefined,
  activeCommit: string | null,
): boolean {
  return definition?.kind === "e2e" &&
    checkState(definition, result, activeCommit) === "pass" &&
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
    if (active.every(t => t === "unverified")) return "unverified";
    if (active.some(t => t === "unverified" || t === "plan")) return "plan";
    return "ok"; // Only all verified children justify a green aggregate.
  }
  if (!["star", "planet", "moon"].includes(node.classification || "")) return "unknown";
  const ids = mapping[node.id] || [];
  const evidence = ids.map(id => ({def: health?.catalog.find(c => c.id === id), result: health?.latest[id]}));
  const live = (e: typeof evidence[number]) => /^debian(?:$|[-_:])/i.test(e.result?.environment || "");
  const failed = (e: typeof evidence[number]) => live(e) && checkState(e.def, e.result, activeCommit) === "fail";
  if (evidence.some(failed)) return evidence.every(e => e.def?.kind === "e2e" && failed(e)) ? "problem" : "minor";
  if (childTones.some(t => ["problem", "minor"].includes(t))) return "minor";
  if (node.knownIssues?.length) return "minor";
  if (isFuture(node)) return "unknown";
  // Manual checks are scoped to exact moons/planets and must not override real failures.
  // No inference about other environments or commits is made from a manual check.
  const manual=manualEvidence(node);
  if (manual?.kind==="plan") return "plan";
  if (manual?.kind==="ok" && !childTones.some(t => t==="unverified" || t==="plan")) return "ok";
  if (childTones.some(t => t==="unverified")) return "plan";
  if (evidence.some(e => verifiedLiveE2E(e.def, e.result, activeCommit)) &&
      evidence.every(e => live(e) && checkState(e.def, e.result, activeCommit) === "pass")) return "ok";
  // A mapped functional check must be proved, even for a partial implementation.
  if (evidence.some(e => !e.def || e.def.kind === "e2e")) return "unverified";
  return node.status === "partial" ? "plan" : "unverified";
}

export const toneLabels: Record<string, string> = {
  ok: "Verde · funzionante e collaudato", problem: "Rosso · collaudo fallito",
  minor: "Arancione · attenzione", plan: "Giallo · presente parzialmente",
  unknown: "Grigio · non ancora presente", unverified: "Grigio · non collaudato",
};

/** Runtime text shares the same decision as the map, never the static project status. */
export function verificationSummary(node: Node, health: HealthDashboardData | null,
  activeCommit: string | null, mapping: CheckMapping, nodes: readonly Node[] = []): string {
  const tone = starTone(node, health, activeCommit, mapping, nodes);
  const container = node.classification === "area" || node.role === "ramo" || ["radici", "tronco", "rami"].includes(node.id);
  if (container && tone === "ok") return "Riepilogo positivo dei sottoelementi: verdi o parziali gialli; obiettivi non presenti esclusi. Non è un collaudo autonomo del contenitore.";
  const manual=manualEvidence(node);
  if (tone === "ok" && manual?.kind === "ok")
    return "Verifica manuale circoscritta del "+manual.date+": "+manual.text+
      " Non è un collaudo automatico né una certificazione del commit attuale.";
  if (tone === "ok") return "Collaudo reale superato sulla versione attiva. Elementi futuri e parziali non bloccano questo esito.";
  if (tone === "problem") return "Collaudo fallito sulla versione attiva. Consultare gli esiti collegati.";
  if (tone === "minor") return "Attenzione: problemi documentati, controlli falliti o sottoelementi presenti non provati. Consultare problemi e test collegati.";
  if (tone === "unknown") return "Obiettivo non ancora presente: escluso dalla verifica del genitore.";
  if (tone === "plan" && manual?.kind === "plan")
    return "Rifinitura da eseguire (osservazione manuale del "+manual.date+"): "+manual.text;
  if (tone === "plan") return "Presente parzialmente: completamento e collaudi restano da eseguire; non blocca il verde del genitore.";
  const ids = mapping[node.id] || [];
  if (!health || health.historyStore === "unavailable") return "Non provato: registro dei collaudi non disponibile. Non indica un guasto accertato.";
  if (!activeCommit) return "Non provato: versione attiva non verificabile. Non indica un collaudo fallito.";
  if (!ids.length) return "Non provato: nessun controllo associato a questo elemento presente.";
  const states = ids.map(id => checkState(health.catalog.find(c => c.id === id), health.latest[id], activeCommit));
  if (states.includes("outdated")) return "Non provato sulla versione attiva: esiti riferiti a un’altra versione.";
  if (states.includes("unattributed")) return "Non provato sulla versione attiva: commit del collaudo non verificabile.";
  if (states.includes("stale")) return "Non provato: collaudi scaduti, da ripetere.";
  return "Non provato: manca un collaudo reale valido sul Debian per questa versione. Controlli parziali o simulati non bastano.";
}
