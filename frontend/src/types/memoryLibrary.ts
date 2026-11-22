export type CardState = "draft" | "approved" | "archived";

export type MemoryDocument = {
  title: string;
  description: string;
  content: string;
  kind: "note" | "entity" | "fact" | "decision" | "brief";
  assertion: "user_statement" | "observation" | "inference";
  state: CardState;
  source_runs: string[];
  relations: {
    target_id: string;
    kind: "relates_to" | "depends_on" | "contradicts" | "supersedes";
  }[];
  valid_from: string | null;
  valid_until: string | null;
};

type Identity = { id: string; scope: string; slug: string; version: number; created_at: string };
export type MemoryCard = Identity & { document: MemoryDocument };
export type MemoryCardSummary = Identity & Pick<MemoryDocument, "title" | "description" | "kind" | "state">;

export type EvidenceRun = {
  id: string; target: string; kind: string; status: string; created_at: string;
};
export type RunEvidence = {
  run_id: string;
  report: Omit<EvidenceRun, "id"> & {
    finished_at: string | null;
    error_type: string | null;
    episode: { id: string; title: string; summary: string } | null;
  };
  messages: { id: string; role: string; content: string; created_at: string }[];
  events: { id: string; type: string; source: string; timestamp: string; payload: Record<string, unknown> }[];
  next_cursor: number;
};
export type MemoryExport = {
  format: "serveria-memory-library-v1";
  scope: string;
  cards: MemoryCard[];
  next_cursor: string | null;
};
