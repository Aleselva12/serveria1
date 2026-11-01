import { useEffect, useState } from "react";
import {
  ChevronRight,
  Folder,
  FolderOpen,
  HardDrive,
  Library,
  LockKeyhole,
  Files,
  Trash2,
} from "lucide-react";
import { filesApi } from "../services/filesApi";
import type { BrowserNode, BrowserRoot, FileArea } from "../types/contracts";

type Selection = { area: FileArea; rootId: string; path: string };
type TreeProps = {
  area: FileArea;
  token: string;
  root: BrowserRoot;
  folder: string;
  label: string;
  selection: Selection;
  disabled: boolean;
  inTrash: boolean;
  reload: number;
  depth?: number;
  select: (area: FileArea, rootId: string, path: string) => void;
};
function FolderTree({
  area,
  token,
  root,
  folder,
  label,
  selection,
  disabled,
  inTrash,
  reload,
  depth = 0,
  select,
}: TreeProps) {
  const onBranch =
    selection.area === area &&
    selection.rootId === root.id &&
    (selection.path === folder ||
      !folder ||
      selection.path.startsWith(folder + "/"));
  const [expanded, setExpanded] = useState(false);
  const [items, setItems] = useState<BrowserNode[]>([]);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (onBranch && selection.path !== folder) setExpanded(true);
  }, [selection.path, onBranch, folder]);
  useEffect(() => {
    setPage(0);
    setItems([]);
  }, [reload]);
  useEffect(() => {
    if (!expanded || !root.available) return;
    let live = true;
    setLoading(true);
    setError("");
    void filesApi
      .children(area, token, root.id, folder, "", page)
      .then((data) => {
        if (live) {
          setItems((previous) =>
            page
              ? [
                  ...previous,
                  ...data.items.filter((item) => item.kind === "folder"),
                ]
              : data.items.filter((item) => item.kind === "folder"),
          );
          setTotal(data.total);
        }
      })
      .catch((e) => {
        if (live)
          setError(
            e instanceof Error ? e.message : "Cartelle non disponibili.",
          );
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [
    area,
    token,
    root.id,
    root.available,
    folder,
    expanded,
    page,
    reload,
    retry,
  ]);
  const selected = !inTrash && onBranch && selection.path === folder;
  return (
    <div className="drive-tree-branch">
      <div className={"drive-tree-row " + (selected ? "is-current" : "")}>
        <button
          className="drive-tree-toggle"
          aria-label={(expanded ? "Comprimi " : "Espandi ") + label}
          aria-expanded={expanded}
          disabled={disabled || !root.available || depth >= 20}
          onClick={() => setExpanded((value) => !value)}
        >
          <ChevronRight size={14} />
        </button>
        <button
          className="drive-tree-link"
          title={label + (!root.writable ? " · Sola lettura" : "")}
          disabled={disabled || !root.available}
          aria-current={selected ? "location" : undefined}
          onClick={() => select(area, root.id, folder)}
        >
          {!folder ? (
            <HardDrive size={17} />
          ) : expanded ? (
            <FolderOpen size={17} />
          ) : (
            <Folder size={17} />
          )}
          <span>
            {label}
            {!root.available && <small>Non disponibile</small>}
          </span>
          {!folder && !root.writable && (
            <LockKeyhole className="drive-tree-lock" size={12} />
          )}
        </button>
      </div>
      {expanded && (
        <div className="drive-tree-children">
          {items.map((item) => (
            <FolderTree
              key={item.path}
              {...{
                area,
                token,
                root,
                selection,
                disabled,
                inTrash,
                reload,
                select,
              }}
              folder={item.path}
              label={item.name}
              depth={depth + 1}
            />
          ))}
          {loading && (
            <small className="drive-tree-feedback" role="status">
              Caricamento…
            </small>
          )}
          {error && (
            <div className="drive-tree-feedback">
              <small>{error}</small>
              <button onClick={() => setRetry((value) => value + 1)}>
                Riprova
              </button>
            </div>
          )}
          {!loading && !error && !items.length && (
            <small className="drive-tree-feedback">Nessuna sottocartella</small>
          )}
          {!loading && !error && page + 100 < total && (
            <button
              className="drive-tree-more"
              onClick={() => setPage((value) => value + 100)}
            >
              Altre cartelle…
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function FileSidebar({
  area,
  token,
  roots,
  rootId,
  path,
  inTrash,
  busy,
  reload,
  select,
  showTrash,
  storage,
}: {
  area: FileArea;
  token: string;
  roots: BrowserRoot[];
  rootId: string;
  path: string;
  inTrash: boolean;
  busy: boolean;
  reload: number;
  select: (area: FileArea, rootId: string, path: string) => void;
  showTrash: () => void;
  storage: { freeBytes: number; totalBytes: number } | null | undefined;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [otherRoots, setOtherRoots] = useState<BrowserRoot[]>([]);
  const [error, setError] = useState("");
  const other: FileArea = area === "server" ? "library" : "server";
  useEffect(() => {
    let live = true;
    setOtherRoots([]);
    setError("");
    void filesApi
      .roots(other, token)
      .then((data) => {
        if (live) setOtherRoots(data);
      })
      .catch(() => {
        if (live) setError("Risorse non disponibili");
      });
    return () => {
      live = false;
    };
  }, [other, token, reload]);
  const chooseResource = (
    nextArea: FileArea,
    nextRoot: string,
    nextPath: string,
  ) => {
    select(nextArea, nextRoot, nextPath);
    setMobileOpen(false);
  };
  const format = (value: number) =>
    new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(
      value / 1073741824,
    ) + " GB";
  return (
    <aside
      className={"drive-sidebar " + (mobileOpen ? "is-expanded" : "")}
      aria-label="Librerie e cartelle"
    >
      <div className="drive-brand">
        <span>
          <Files size={23} />
        </span>
        <div>
          <h1>File</h1>
          <small>Il tuo spazio, su Cora</small>
        </div>
        <button
          className="drive-mobile-toggle"
          aria-label="Mostra librerie e cartelle"
          aria-expanded={mobileOpen}
          aria-controls="drive-sidebar-body"
          onClick={() => setMobileOpen((value) => !value)}
        >
          <ChevronRight size={16} />
          Librerie
        </button>
      </div>
      <div className="drive-sidebar-body" id="drive-sidebar-body">
        {(["server", "library"] as FileArea[]).map((group) => {
          const list = area === group ? roots : otherRoots;
          return (
            <div className="drive-library-group" key={group}>
              <button
                className={
                  "drive-library-title " + (area === group ? "is-active" : "")
                }
                onClick={() =>
                  chooseResource(
                    group,
                    list.find((r) => r.available)?.id || "",
                    "",
                  )
                }
                disabled={busy}
              >
                {group === "server" ? (
                  <HardDrive size={18} />
                ) : (
                  <Library size={18} />
                )}
                <span>
                  {group === "server" ? "File server" : "Libreria IA"}
                </span>
              </button>
              <div className="drive-library-roots">
                {list.map((root) => (
                  <FolderTree
                    key={root.id}
                    area={group}
                    token={token}
                    root={root}
                    folder=""
                    label={root.label}
                    selection={{ area, rootId, path }}
                    disabled={busy}
                    inTrash={inTrash}
                    reload={reload}
                    select={chooseResource}
                  />
                ))}
                {area !== group && error && (
                  <small className="drive-tree-feedback">{error}</small>
                )}
              </div>
            </div>
          );
        })}
        <button
          className={"drive-trash-link " + (inTrash ? "is-current" : "")}
          disabled={busy || !rootId}
          onClick={() => {
            showTrash();
            setMobileOpen(false);
          }}
        >
          <Trash2 size={18} />
          <span>
            Cestino<small>Della risorsa selezionata</small>
          </span>
        </button>
        <div className="drive-storage">
          <div>
            <HardDrive size={16} />
            <strong>Spazio di archiviazione</strong>
          </div>
          {storage ? (
            <>
              <progress
                value={Math.max(0, storage.totalBytes - storage.freeBytes)}
                max={storage.totalBytes || 1}
                aria-label="Spazio utilizzato"
              />
              <p>
                {format(storage.freeBytes)} liberi di{" "}
                {format(storage.totalBytes)}
              </p>
            </>
          ) : (
            <p>Spazio non disponibile</p>
          )}
          <small>Disco della risorsa selezionata</small>
        </div>
      </div>
    </aside>
  );
}
