import { useEffect, useRef, useState } from "react";
import {
  programmerArtifactsApi,
  type ComponentRecord,
  type GraphView,
} from "../services/programmerApi";
import { authenticatedFetch } from "../services/transport";
import { apiBaseUrl } from "../services/api";

const labels: Record<string, string> = {
  draft: "Bozza",
  verified: "Verificato",
  reviewed: "Revisionato",
  integrated: "Integrazione dichiarata",
  active: "Attivazione dichiarata",
};
export default function ProgrammerArtifacts({
  workspaceId,
  revision,
  disabled,
}: {
  workspaceId: string;
  revision: number;
  disabled: boolean;
}) {
  const [rows, setRows] = useState<ComponentRecord[]>([]),
    [selected, setSelected] = useState("");
  const [title, setTitle] = useState(""),
    [kind, setKind] = useState("tool"),
    [files, setFiles] = useState("");
  const [dependencies, setDependencies] = useState(""),
    [integration, setIntegration] = useState(""),
    [note, setNote] = useState("");
  const [checks, setChecks] = useState<
    {
      profile: string;
      passed: boolean;
      checked_at: string;
      workspace_digest: string;
    }[]
  >([]);
  const [graph, setGraph] = useState<GraphView | null>(null),
    [query, setQuery] = useState(""),
    [nodeId, setNodeId] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [delivery, setDelivery] = useState<{ id: string; sha256: string } | null>(
      null,
    );
  const currentWorkspace = useRef(workspaceId),
    graphRequest = useRef(0);
  const loadedWorkspace = useRef("");
  currentWorkspace.current = workspaceId;
  const component = rows.find((row) => row.id === selected);
  async function refresh(id: string) {
    const [records, history] = await Promise.all([
      programmerArtifactsApi.components(id),
      programmerArtifactsApi.checks(id),
    ]);
    if (currentWorkspace.current === id) {
      setRows(records.components);
      setChecks(history.checks);
    }
  }
  async function loadGraph(id: string, search: string, center: string) {
    const sequence = ++graphRequest.current;
    try {
      const result = await programmerArtifactsApi.graph(id, search, center);
      if (currentWorkspace.current === id && sequence === graphRequest.current)
        setGraph(result);
    } catch (e) {
      if (currentWorkspace.current === id && sequence === graphRequest.current)
        setError(String(e));
    }
  }
  useEffect(() => {
    currentWorkspace.current = workspaceId;
    setRows([]);
    setSelected("");
    setTitle("");
    setFiles("");
    setIntegration("");
    setDependencies("");
    setNote("");
    setDelivery(null);
    setChecks([]);
    setGraph(null);
    setQuery("");
    setNodeId("");
    setError("");
    graphRequest.current++;
    return () => {
      currentWorkspace.current = "";
      graphRequest.current++;
    };
  }, [workspaceId]);
  useEffect(() => {
    if (!workspaceId) return;
    void refresh(workspaceId).catch((e) => {
      if (currentWorkspace.current === workspaceId) setError(String(e));
    });
    const changed = loadedWorkspace.current !== workspaceId;
    loadedWorkspace.current = workspaceId;
    void loadGraph(workspaceId, changed ? "" : query, changed ? "" : nodeId);
  }, [workspaceId, revision]);
  function choose(id: string) {
    setSelected(id);
    setDelivery(null);
    setNote("");
    const row = rows.find((r) => r.id === id);
    setTitle(row?.title || "");
    setKind(row?.kind || "tool");
    setFiles(row?.files.join("\n") || "");
    setDependencies(row?.dependencies.join("\n") || "");
    setIntegration(row?.integration || "");
  }
  async function action(operation: () => Promise<unknown>) {
    if (busy || disabled || !workspaceId) return;
    const id = workspaceId;
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh(id);
    } catch (e) {
      if (currentWorkspace.current === id) setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    const id = workspaceId;
    await action(async () => {
      const row = await programmerArtifactsApi.register(id, {
        title,
        kind,
        files: files
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        dependencies: dependencies
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        integration,
        component_id: selected,
      });
      if (currentWorkspace.current === id) {
        setSelected(row.id);
        setDelivery(null);
      }
    });
  }
  async function exportPackage() {
    const id = workspaceId;
    if (!component) return;
    await action(async () => {
      const result = await programmerArtifactsApi.deliver(id, component.id);
      if (currentWorkspace.current === id) setDelivery(result);
    });
  }
  async function download() {
    if (!delivery) return;
    await action(async () => {
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/v1/programmer/workspaces/${workspaceId}/deliveries/${delivery.id}`,
      );
      if (!response.ok)
        throw new Error("Download della consegna non riuscito.");
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `cora-component-${delivery.id}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  const locked = disabled || busy || !workspaceId;
  const next = component
    ? (
        {
          verified: "reviewed",
          reviewed: "integrated",
          integrated: "active",
        } as Record<string, string>
      )[component.status]
    : undefined;
  const nodes = graph?.nodes || [],
    edges = graph?.edges || [];
  const positions = new Map(
    nodes.map((n, index) => {
      const center = String(n.id) === nodeId;
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
      const radius = index % 2 ? 245 : 155;
      return [
        String(n.id),
        {
          x: center ? 450 : 450 + Math.cos(angle) * radius * 1.35,
          y: center ? 320 : 320 + Math.sin(angle) * radius,
        },
      ];
    }),
  );
  return (
    <div className="programmer-artifacts">
      <section className="programmer-registry" aria-label="Registro componenti">
        <h2>Componenti e consegne</h2>
        <p>Versioni, verifiche e passaggio alla revisione.</p>
        {error && (
          <p role="alert" className="programmer-error">
            {error}
          </p>
        )}
        <label>
          Componente
          <select
            aria-label="Componente registrato"
            disabled={locked}
            value={selected}
            onChange={(e) => choose(e.target.value)}
          >
            <option value="">Nuovo componente</option>
            {rows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.title} · v{row.version} · {labels[row.status]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Titolo
          <input
            aria-label="Titolo componente"
            value={title}
            disabled={locked}
            maxLength={120}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Tipo
          <select
            aria-label="Tipo componente"
            value={kind}
            disabled={locked}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="tool">Tool Python</option>
            <option value="automation">Automazione</option>
            <option value="frontend">Frontend</option>
            <option value="other">Altro</option>
          </select>
        </label>
        <label>
          File e test, un percorso per riga
          <textarea
            aria-label="File componente"
            rows={3}
            value={files}
            disabled={locked}
            onChange={(e) => setFiles(e.target.value)}
          />
        </label>
        <label>
          Dipendenze, una per riga
          <textarea
            aria-label="Dipendenze componente"
            rows={2}
            value={dependencies}
            disabled={locked}
            onChange={(e) => setDependencies(e.target.value)}
          />
        </label>
        <label>
          Istruzioni di integrazione
          <textarea
            aria-label="Istruzioni integrazione"
            rows={3}
            value={integration}
            disabled={locked}
            maxLength={12000}
            onChange={(e) => setIntegration(e.target.value)}
          />
        </label>
        <button
          disabled={
            locked || !title.trim() || !files.trim() || !integration.trim()
          }
          onClick={() => void save()}
        >
          {selected ? "Registra nuova revisione" : "Registra componente"}
        </button>
        {component && (
          <div className="programmer-component-detail">
            <p>
              <strong>
                {labels[component.status]} · v{component.version}
              </strong>
              {component.stale
                ? " · codice cambiato: registra una nuova revisione"
                : ""}
            </p>
            <p>
              Verifiche mancanti:{" "}
              {component.missing_checks.join(", ") ||
                "nessuna per i profili previsti"}
            </p>
            <button
              disabled={locked || component.stale}
              onClick={() => void exportPackage()}
            >
              Prepara consegna
            </button>
            {delivery && (
              <div>
                <button disabled={locked} onClick={() => void download()}>
                  Scarica ZIP
                </button>
                <small>SHA256: {delivery.sha256}</small>
              </div>
            )}
            {next && (
              <>
                <label>
                  Nota ed evidenza della revisione/integrazione
                  <textarea
                    aria-label="Nota stato componente"
                    rows={2}
                    value={note}
                    disabled={locked}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </label>
                <button
                  disabled={locked || component.stale || !note.trim()}
                  onClick={() =>
                    void action(async () => {
                      await programmerArtifactsApi.transition(
                        workspaceId,
                        component,
                        next,
                        note,
                      );
                      setNote("");
                    })
                  }
                >
                  {next === "reviewed"
                    ? "Conferma revisione"
                    : next === "integrated"
                      ? "Registra integrazione avvenuta"
                      : "Registra attivazione avvenuta"}
                </button>
              </>
            )}
            <small>
              Gli stati di integrazione e attivazione sono dichiarazioni
              manuali: questi pulsanti aggiornano il registro.
            </small>
          </div>
        )}
        <h3>Ultime verifiche</h3>
        {checks.length ? (
          <ul>
            {checks
              .slice(-8)
              .reverse()
              .map((check, index) => (
                <li key={index}>
                  {check.profile} · {check.passed ? "superata" : "non superata"}{" "}
                  · {new Date(check.checked_at).toLocaleString()}
                  {component &&
                  check.workspace_digest !== component.workspace_digest
                    ? " · altra versione del codice"
                    : ""}
                </li>
              ))}
          </ul>
        ) : (
          <p>Nessuna verifica registrata.</p>
        )}
      </section>
      <section className="programmer-graph" aria-label="Mappa Graphify">
        <h2>Mappa del codice</h2>
        <p>Seleziona un simbolo per esplorarne i collegamenti.</p>
        <div className="programmer-actions">
          <input
            aria-label="Ricerca mappa Graphify"
            value={query}
            maxLength={200}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Modulo, funzione o percorso…"
          />
          <button
            disabled={!workspaceId}
            onClick={() => {
              setNodeId("");
              void loadGraph(workspaceId, query, "");
            }}
          >
            Cerca nella mappa
          </button>
          {nodeId && (
            <button
              onClick={() => {
                setNodeId("");
                void loadGraph(workspaceId, query, "");
              }}
            >
              Torna ai risultati
            </button>
          )}
        </div>
        {!graph?.status.available ? (
          <p>Costruisci o importa la mappa Graphify dal workspace.</p>
        ) : (
          <>
            <p>
              {graph.status.stale
                ? "Mappa del baseline: il workspace è stato modificato. "
                : ""}
              {graph.total_matches} corrispondenze · {nodes.length} nodi
              visibili{graph.truncated ? " · vista parziale" : ""}
            </p>
            <svg
              viewBox="0 0 900 640"
              role="img"
              aria-label="Collegamenti del codice"
            >
              <defs>
                <marker
                  id="programmer-arrow"
                  viewBox="0 0 10 10"
                  refX="29"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
                </marker>
              </defs>
              {edges.map((edge, index) => {
                const a = positions.get(String(edge.source)),
                  b = positions.get(String(edge.target));
                return a && b ? (
                  <line
                    key={index}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    markerEnd="url(#programmer-arrow)"
                    className={edge.confidence === "INFERRED" ? "inferred" : ""}
                  >
                    <title>
                      {String(edge.source)} → {String(edge.target)} ·{" "}
                      {edge.relation || "collegamento"} ·{" "}
                      {edge.confidence || "origine non indicata"}
                    </title>
                  </line>
                ) : null;
              })}
              {nodes.map((node) => {
                const id = String(node.id),
                  position = positions.get(id)!;
                return (
                  <g
                    key={id}
                    role="button"
                    tabIndex={0}
                    aria-label={"Esplora simbolo " + id}
                    transform={`translate(${position.x},${position.y})`}
                    className={
                      node.unresolved
                        ? "unresolved"
                        : id === nodeId
                          ? "focused"
                          : ""
                    }
                    onClick={() => {
                      setNodeId(id);
                      void loadGraph(workspaceId, "", id);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setNodeId(id);
                        void loadGraph(workspaceId, "", id);
                      }
                    }}
                  >
                    <title>
                      {id}
                      {node.unresolved ? " · riferimento non risolto" : ""}
                    </title>
                    <circle r="28" />
                    <text y="43" textAnchor="middle">
                      {String(node.label || node.name || id).slice(0, 24)}
                    </text>
                  </g>
                );
              })}
            </svg>
            {nodeId && (
              <pre className="programmer-report">
                {JSON.stringify(
                  nodes.find((n) => String(n.id) === nodeId),
                  null,
                  2,
                )?.slice(0, 3000)}
              </pre>
            )}
            <small>
              Frecce: relazioni estratte. Tratteggio: relazioni inferite. Nodi
              tratteggiati: riferimenti non risolti. La mappa non mostra
              l’esecuzione del programma.
            </small>
          </>
        )}
      </section>
    </div>
  );
}
