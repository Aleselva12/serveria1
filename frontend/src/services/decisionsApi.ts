import { apiBaseUrl } from "./api";
import { authenticatedFetch } from "./transport";
import { runtimeRequest, type CapabilityOperation } from "./runtimeApi";

/** Something an agent proposed and that waits for the owner's yes or no. */
export type Approval = {
  id: string; actor: string; action: string; payload: unknown; status: string;
  contract_version?: number | null; capability_id?: string | null; actions?: string[];
  result?: unknown; error_type?: string; kind?: "generic" | "calendar";
};
/** Word note proposed from a recording: decided on the Audio page, next to its transcript. */
export type WordProposal = { id: string; audioId: string; title: string; createdAt: string; expiresAt: string };
export type Decisions = {
  approvals: Approval[];          // generic and calendar, approved or rejected here
  uncertain: CapabilityOperation[]; // effects to verify by hand
  word: WordProposal[];
  results: Approval[];            // recent outcomes, for reference
  pending: number;
};

// Lets the Home window, the menu badge and the page stay in step after a decision.
export const DECISIONS_CHANGED = "cora:decisions-changed";

async function wordProposals(): Promise<WordProposal[]> {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1/audio/commercial/pending", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Note Word non disponibili.");
  const data = await response.json() as { items?: WordProposal[] };
  return Array.isArray(data.items) ? data.items : [];
}

/** One area that fails does not hide the others: its list stays empty and the error is reported. */
export async function loadDecisions(): Promise<{ decisions: Decisions; errors: string[] }> {
  const [approvals, uncertain, word] = await Promise.allSettled([
    runtimeRequest<{ generic: Approval[]; calendar: Approval[]; history: Approval[] }>("/approvals"),
    runtimeRequest<CapabilityOperation[]>("/runtime/operations?unresolved=true&limit=50"),
    wordProposals(),
  ]);
  const errors: string[] = [];
  const value = <T,>(result: PromiseSettledResult<T>, fallback: T, label: string) => {
    if (result.status === "fulfilled") return result.value;
    errors.push(label);
    return fallback;
  };
  const a = value(approvals, { generic: [], calendar: [], history: [] }, "approvazioni");
  const list = [...a.generic.map(x => ({ ...x, kind: "generic" as const })), ...a.calendar.map(x => ({ ...x, kind: "calendar" as const }))];
  const effects = value(uncertain, [], "effetti da verificare");
  const notes = value(word, [], "note Word");
  return { decisions: { approvals: list, uncertain: effects, word: notes, results: a.history, pending: list.length + effects.length + notes.length }, errors };
}

function changed() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(DECISIONS_CHANGED));
}

export async function resolveApproval(approval: Approval, approve: boolean) {
  const path = "/approvals/" + (approval.kind === "calendar" ? "calendar/" : "") + approval.id + "/resolve";
  try {
    return await runtimeRequest<{ status?: string; error_type?: string }>(path, { method: "POST", body: JSON.stringify({ approve }) });
  } finally { changed(); }
}

export async function reviewOperation(id: string, outcome: "effect_verified" | "no_effect_verified", note: string) {
  try {
    return await runtimeRequest<{ status?: string }>("/runtime/operations/" + id + "/review", { method: "POST", body: JSON.stringify({ outcome, note }) });
  } finally { changed(); }
}
