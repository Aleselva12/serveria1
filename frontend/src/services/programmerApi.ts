import { runtimeRequest, streamRun, type RunSnapshot } from "./runtimeApi";
export type Workspace = {
  id: string;
  title: string;
  created_at: string;
  source_digest: string;
  file_count: number;
  status: string;
};
export type CodeFile = {
  path: string;
  content: string;
  sha256: string;
  start_line: number;
  total_lines: number;
  truncated: boolean;
};
export type CodeDiff = {
  changes: { path: string; kind: string; patch: string; truncated: boolean }[];
  total_changes: number;
  truncated: boolean;
};
export type GraphStatus = {
  available: boolean;
  stale?: boolean;
  nodes?: number;
  edges?: number;
  reason?: string;
};
export const programmerApi = {
  status: () =>
    runtimeRequest<{
      model: string;
      skills: Record<string, string>;
      checks: { docker_cli: boolean };
    }>("/programmer/status"),
  workspaces: () => runtimeRequest<Workspace[]>("/programmer/workspaces"),
  create: (title: string) =>
    runtimeRequest<Workspace>("/programmer/workspaces", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  files: (id: string) =>
    runtimeRequest<{ files: string[] }>(
      "/programmer/workspaces/" + id + "/files",
    ),
  file: (id: string, path: string, start = 1) =>
    runtimeRequest<CodeFile>(
      "/programmer/workspaces/" +
        id +
        "/file?" +
        new URLSearchParams({ path, start_line: String(start) }),
    ),
  diff: (id: string) =>
    runtimeRequest<CodeDiff>("/programmer/workspaces/" + id + "/diff"),
  graph: (id: string) =>
    runtimeRequest<GraphStatus>("/programmer/workspaces/" + id + "/graph"),
  importGraph: (id: string, graph: unknown, source_digest: string) =>
    runtimeRequest<GraphStatus>("/programmer/workspaces/" + id + "/graph", {
      method: "POST",
      body: JSON.stringify({ graph, source_digest }),
    }),
  importDraft: (id: string, path: string) =>
    runtimeRequest<{ id: string; status: string }>(
      "/programmer/workspaces/" + id + "/drafts",
      { method: "POST", body: JSON.stringify({ path }) },
    ),
  async run(
    id: string,
    message: string,
    onRun: (id: string) => void,
    onText: (text: string) => void,
    onState: (state: string) => void,
    signal?: AbortSignal,
  ) {
    const run = await runtimeRequest<RunSnapshot>("/programmer/runs", {
      method: "POST",
      body: JSON.stringify({ workspace_id: id, message }),
    });
    onRun(run.id);
    onState(run.status);
    return streamRun(run, onText, onState, signal);
  },
  async buildGraph(
    id: string,
    onRun: (id: string) => void,
    onState: (state: string) => void,
    signal?: AbortSignal,
  ) {
    const run = await runtimeRequest<RunSnapshot>(
      "/programmer/workspaces/" + id + "/graph/build",
      { method: "POST" },
    );
    onRun(run.id);
    onState(run.status);
    return streamRun(run, () => {}, onState, signal);
  },
  async check(
    id: string,
    profile: string,
    onRun: (id: string) => void,
    onState: (state: string) => void,
    signal?: AbortSignal,
  ) {
    const run = await runtimeRequest<RunSnapshot>(
      "/programmer/workspaces/" + id + "/checks",
      { method: "POST", body: JSON.stringify({ profile }) },
    );
    onRun(run.id);
    onState(run.status);
    return streamRun(run, () => {}, onState, signal);
  },
};

export type ComponentRecord = {
  id: string;
  title: string;
  kind: string;
  version: number;
  files: string[];
  dependencies: string[];
  integration: string;
  status: string;
  recorded_status: string;
  stale: boolean;
  missing_checks: string[];
  workspace_digest: string;
};
export type GraphNode = {
  id: string | number;
  label?: string;
  name?: string;
  unresolved?: boolean;
  [key: string]: unknown;
};
export type GraphEdge = {
  source: string | number;
  target: string | number;
  relation?: string;
  confidence?: string;
  [key: string]: unknown;
};
export type GraphView = {
  status: GraphStatus;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_matches: number;
  truncated: boolean;
};
export const programmerArtifactsApi = {
  components: (id: string) =>
    runtimeRequest<{ components: ComponentRecord[] }>(
      `/programmer/workspaces/${id}/components`,
    ),
  register: (
    id: string,
    data: {
      title: string;
      kind: string;
      files: string[];
      dependencies: string[];
      integration: string;
      component_id: string;
    },
  ) =>
    runtimeRequest<ComponentRecord>(`/programmer/workspaces/${id}/components`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  transition: (
    id: string,
    component: ComponentRecord,
    status: string,
    note: string,
  ) =>
    runtimeRequest<ComponentRecord>(
      `/programmer/workspaces/${id}/components/${component.id}/status`,
      {
        method: "POST",
        body: JSON.stringify({
          status,
          note,
          expected_version: component.version,
          expected_digest: component.workspace_digest,
        }),
      },
    ),
  deliver: (id: string, component: string) =>
    runtimeRequest<{ id: string; sha256: string; missing_checks: string[] }>(
      `/programmer/workspaces/${id}/components/${component}/deliveries`,
      { method: "POST" },
    ),
  checks: (id: string) =>
    runtimeRequest<{
      checks: {
        profile: string;
        passed: boolean;
        checked_at: string;
        workspace_digest: string;
        scope?: string;
      }[];
    }>(`/programmer/workspaces/${id}/checks`),
  graph: (id: string, query: string, nodeId: string) =>
    runtimeRequest<GraphView>(
      `/programmer/workspaces/${id}/graph/view?` +
        new URLSearchParams({ query, node_id: nodeId }),
    ),
};
