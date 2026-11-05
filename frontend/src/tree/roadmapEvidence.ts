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

export function starTone(
  node: Node,
  health: HealthDashboardData | null,
  activeCommit: string | null,
  mapping: CheckMapping,
): string {
  if (!["star", "planet", "moon"].includes(node.classification || "")) return "unknown";
  const ids = mapping[node.id] || [];
  const evidence = ids.map(id => ({
    def: health?.catalog.find(c => c.id === id),
    result: health?.latest[id],
  }));
  const live = (e: typeof evidence[number]) => /^debian(?:$|[-_:])/i.test(e.result?.environment || "");
  if (evidence.some(e => live(e) && checkState(e.def, e.result, activeCommit) === "fail")) return "problem";
  // Planned stars remain grey placeholders even when a related prerequisite passes.
  if (node.status === "planned" || node.status === "idea") return "unknown";
  if (ids.length && evidence.every(e => live(e) && checkState(e.def, e.result, activeCommit) === "pass")) return "ok";
  if (node.knownIssues?.length) return "minor";
  if (node.timeline?.future?.length) return "plan";
  return "unknown";
}

export const toneLabels: Record<string, string> = {
  ok: "Verde · controlli superati", problem: "Rosso · test fallito",
  minor: "Arancione · attenzione", plan: "Giallo · lavoro previsto",
  unknown: "Grigio · non verificato",
};
