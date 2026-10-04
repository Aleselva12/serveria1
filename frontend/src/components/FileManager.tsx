import { useEffect, useRef, useState } from "react";
import {
  CloudUpload,
  Copy,
  Download,
  FileText,
  Folder,
  Grid2X2,
  List,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  Undo2,
  X,
} from "lucide-react";
import FilePreview from "./FilePreview";
import { apiBaseUrl } from "../services/api";
import { filesApi } from "../services/filesApi";
import type {
  BrowserListing,
  BrowserNode,
  BrowserRoot,
  FileArea,
  TrashItem,
} from "../types/contracts";

const bytes = (value: number | null | undefined) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(
        value /
          (value >= 1073741824
            ? 1073741824
            : value >= 1048576
              ? 1048576
              : value >= 1024
                ? 1024
                : 1),
      ) +
      (value >= 1073741824
        ? " GB"
        : value >= 1048576
          ? " MB"
          : value >= 1024
            ? " KB"
            : " B");
const join = (path: string, name: string) =>
  [path, name].filter(Boolean).join("/");
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Operazione non riuscita.";

function Breadcrumbs({
  label,
  path,
  disabled,
  navigate,
}: {
  label: string;
  path: string;
  disabled: boolean;
  navigate: (path: string) => void;
}) {
  const segments = path.split("/").filter(Boolean);
  return (
    <nav className="breadcrumbs" aria-label="Percorso cartella">
      <button disabled={disabled} onClick={() => navigate("")}>
        {label}
      </button>
      {segments.map((name, index) => (
        <span key={index}>
          {" "}
          /{" "}
          <button
            disabled={disabled}
            onClick={() => navigate(segments.slice(0, index + 1).join("/"))}
          >
            {name}
          </button>
        </span>
      ))}
    </nav>
  );
}

function ServerPicker({
  token,
  destination,
  onClose,
  onCopied,
}: {
  token: string;
  destination: string;
  onClose: () => void;
  onCopied: () => void;
}) {
  const [roots, setRoots] = useState<BrowserRoot[]>([]);
  const [rootId, setRootId] = useState("");
  const [path, setPath] = useState("");
  const [offset, setOffset] = useState(0);
  const [listing, setListing] = useState<BrowserListing | null>(null);
  const [selected, setSelected] = useState<BrowserNode | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  useEffect(() => {
    let live = true;
    void filesApi
      .roots("server", token)
      .then((data) => {
        if (live) {
          setRoots(data);
          setRootId(data.find((r) => r.available)?.id || "");
          setLoading(false);
        }
      })
      .catch((e) => {
        if (live) {
          setError(message(e));
          setLoading(false);
        }
      });
    return () => {
      live = false;
    };
  }, [token]);
  useEffect(() => {
    if (!rootId) return;
    let live = true;
    setListing(null);
    setSelected(null);
    setLoading(true);
    setError("");
    void filesApi
      .children("server", token, rootId, path, "", offset)
      .then((data) => {
        if (live) setListing(data);
      })
      .catch((e) => {
        if (live) setError(message(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [rootId, path, offset, token]);
  async function submit() {
    if (!selected || !name.trim() || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await filesApi.mutate("library", token, "/import", {
        source_root_id: rootId,
        source_path: selected.path,
        destination: join(destination, name.trim()),
      });
      onCopied();
    } catch (e) {
      setError(message(e));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <div className="file-modal-shade">
      <section
        className="file-modal file-picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="picker-title"
      >
        <header>
          <h2 id="picker-title">Copia dal server</h2>
          <button
            disabled={busy}
            onClick={onClose}
            aria-label="Chiudi selezione"
          >
            <X size={18} />
          </button>
        </header>
        <p>
          L’originale rimarrà nella sua cartella. Scegli il file da copiare.
        </p>
        <label>
          Risorsa
          <select
            disabled={busy}
            value={rootId}
            onChange={(e) => {
              setRootId(e.target.value);
              setPath("");
              setOffset(0);
            }}
          >
            {roots.map((r) => (
              <option key={r.id} value={r.id} disabled={!r.available}>
                {r.label}
                {!r.available ? " · non disponibile" : ""}
              </option>
            ))}
          </select>
        </label>
        <Breadcrumbs
          label="Radice"
          path={path}
          disabled={busy}
          navigate={(next) => {
            setPath(next);
            setOffset(0);
          }}
        />
        {error && (
          <div className="connection-error" role="alert">
            {error}
          </div>
        )}
        <div className="picker-files">
          {loading ? (
            <p role="status">Caricamento…</p>
          ) : (
            listing?.items.map((item) => (
              <button
                disabled={busy || !["file", "folder"].includes(item.kind)}
                key={item.path}
                className={selected?.path === item.path ? "selected" : ""}
                onClick={() => {
                  if (item.kind === "folder") {
                    setPath(item.path);
                    setOffset(0);
                  } else {
                    setSelected(item);
                    setName(item.name);
                  }
                }}
              >
                {item.kind === "folder" ? (
                  <Folder size={17} />
                ) : (
                  <FileText size={17} />
                )}
                <span>{item.name}</span>
                {item.kind === "file" && <small>{bytes(item.sizeBytes)}</small>}
              </button>
            ))
          )}
          {!loading && listing?.total === 0 && <p>Cartella vuota.</p>}
        </div>
        <div className="file-pagination">
          <button
            disabled={busy || offset === 0}
            onClick={() => setOffset((n) => Math.max(0, n - 100))}
          >
            Precedenti
          </button>
          <button
            disabled={busy || !listing || offset + 100 >= listing.total}
            onClick={() => setOffset((n) => n + 100)}
          >
            Successivi
          </button>
        </div>
        <label>
          Nome della copia
          <input
            value={name}
            disabled={busy || !selected}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <small>Destinazione: Libreria IA / {destination || "radice"}</small>
        <footer>
          <button disabled={busy} onClick={onClose}>
            Annulla
          </button>
          <button
            className="upload-button"
            disabled={
              busy ||
              !selected ||
              !name.trim() ||
              name.includes("/") ||
              name.includes("\\")
            }
            onClick={() => void submit()}
          >
            {busy ? "Copia in corso…" : "Copia nella libreria"}
          </button>
        </footer>
      </section>
    </div>
  );
}

type EditAction = {
  kind: "folder" | "rename" | "move" | "copy" | "library";
  item?: BrowserNode;
};
const actionLabels = {
  folder: "Nuova cartella",
  rename: "Rinomina",
  move: "Sposta",
  copy: "Copia",
  library: "Copia nella Libreria IA",
};
function FileBrowser({ area, token }: { area: FileArea; token: string }) {
  const [roots, setRoots] = useState<BrowserRoot[]>([]);
  const [rootId, setRootId] = useState("");
  const [path, setPath] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [listing, setListing] = useState<BrowserListing | null>(null);
  const [trash, setTrash] = useState<TrashItem[]>([]);
  const [recursive,setRecursive] = useState(false);
  const [preview,setPreview] = useState<BrowserNode|null>(null);
  const [shareList,setShareList] = useState<{id:string;path:string;expiresAt:string;revoked:boolean}[]|null>(null);
  const [shareLink,setShareLink] = useState("");
  const [uploadProgress,setUploadProgress] = useState("");
  const [inTrash, setInTrash] = useState(false);
  const [view, setView] = useState<"list" | "grid">("list");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [action, setAction] = useState<EditAction | null>(null);
  const [value, setValue] = useState("");
  const [picker, setPicker] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const mutationLock = useRef(false);
  const root = roots.find((r) => r.id === rootId);
  const writable = Boolean(
    root?.available &&
    root?.writable &&
    listing?.writable &&
    !inTrash &&
    !loading,
  );
  const isLibrary = area === "library";
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    let live = true;
    void filesApi
      .roots(area, token)
      .then((data) => {
        if (!live) return;
        setRoots(data);
        setRootId((current) =>
          data.some((r) => r.id === current)
            ? current
            : data.find((r) => r.available)?.id || data[0]?.id || "",
        );
      })
      .catch((e) => {
        if (live) {
          setRoots([]);
          setRootId("");
          setListing(null);
          setLoading(false);
          setError(message(e));
        }
      });
    return () => {
      live = false;
    };
  }, [area, token, reload]);
  useEffect(() => {
    if (!rootId) return;
    let live = true;
    setLoading(true);
    setListing(null);
    setTrash([]);
    const load = async () => {
      try {
        if (inTrash) {
          const items = await filesApi.trashList(area, token, rootId);
          if (live) setTrash(items);
        } else {
          const data = await filesApi.children(
            area,
            token,
            rootId,
            path,
            search,
            offset,
            recursive,
          );
          if (live) setListing(data);
        }
      } catch (e) {
        if (live) setError(message(e));
      } finally {
        if (live) setLoading(false);
      }
    };
    void load();
    return () => {
      live = false;
    };
  }, [area, token, rootId, path, search, offset, recursive, inTrash, reload]);
  function navigate(next: string) {
    setError("");
    setPreview(null);setShareList(null);setShareLink("");
    setPath(next);
    setOffset(0);
    setQuery("");
    setSearch("");
    setInTrash(false);
    setListing(null);
  }
  async function run(operation: () => Promise<unknown>, success: string) {
    if (mutationLock.current) return;
    mutationLock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await operation();
      setNotice(success);
      setAction(null);
      setOffset(0);
      setReload((n) => n + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      mutationLock.current = false;
      setBusy(false);
    }
  }
  async function uploadFiles(files: File[]) {
    if (!files.length || !writable || mutationLock.current) return;
    let completed = 0;
    setUploadProgress("");
    await run(
      async () => {
        for (const file of files) {
          try {
            await filesApi.resumableUpload(area, rootId, path, file, setUploadProgress);
            completed++;
          } catch (e) {
            setReload((n) => n + 1);
            throw new Error(
              `${completed} di ${files.length} file confermati. ${file.name}: ${message(e)} Gli altri file non sono stati inviati.`,
            );
          }
        }
      },
      isLibrary
        ? `${files.length} copie aggiunte. Originali conservati in File server → Originali Libreria IA.`
        : `${files.length} file caricati.`,
    );
  }
  function edit(kind: EditAction["kind"], item?: BrowserNode) {
    setAction({ kind, item });
    setValue(
      kind === "rename"
        ? item!.name
        : kind === "folder"
          ? ""
          : kind === "library"
            ? item!.name
            : item!.path,
    );
  }
  async function submitAction() {
    if (!action || !value.trim()) return;
    const text = value.trim();
    if (
      (action.kind === "rename" || action.kind === "folder") &&
      (text.includes("/") || text.includes("\\"))
    ) {
      setError("Inserisci un nome, senza separatori di percorso.");
      return;
    }
    if (action.kind === "library")
      await run(
        () =>
          filesApi.mutate("library", token, "/import", {
            source_root_id: rootId,
            source_path: action.item!.path,
            destination: text,
          }),
        "Copia aggiunta alla Libreria IA. Originale conservato sul server.",
      );
    else if (action.kind === "folder")
      await run(
        () =>
          filesApi.mutate(area, token, "/folders", {
            root_id: rootId,
            path: join(path, text),
          }),
        "Cartella creata.",
      );
    else
      await run(
        () =>
          filesApi.mutate(area, token, "/transfer", {
            root_id: rootId,
            path: action.item!.path,
            destination: action.kind === "rename" ? join(path, text) : text,
            mode: action.kind === "copy" ? "copy" : "move",
          }),
        "Operazione completata.",
      );
  }
  async function showShares() {
    await run(async()=>{const data=await filesApi.shares(area,rootId);setShareList(data.items);}, "Condivisioni caricate.");
  }
  function actions(item: BrowserNode) {
    return (
      <div className="file-actions">
        {item.kind==="file"&&<><button disabled={busy} title="Anteprima" aria-label={"Anteprima "+item.name} onClick={()=>setPreview(item)}>Anteprima</button>
        <button disabled={busy} title="Condividi per 24 ore (richiede accesso)" onClick={()=>void run(async()=>{const share=await filesApi.share(area,rootId,item.path);setShareLink(new URL(apiBaseUrl+share.url,window.location.origin).href);},"Collegamento creato: valido 24 ore, richiede accesso al server.")}>Condividi</button></>}

        {item.capabilities.includes("download") && (
          <button
            disabled={busy}
            title="Scarica"
            aria-label={"Scarica " + item.name}
            onClick={() =>
              void run(
                () => filesApi.download(area, token, rootId, item),
                "Download preparato.",
              )
            }
          >
            <Download size={15} />
          </button>
        )}
        {!isLibrary && item.kind === "file" && (
          <button
            disabled={busy}
            title="Copia nella Libreria IA"
            aria-label={"Copia nella Libreria IA " + item.name}
            onClick={() => edit("library", item)}
          >
            <Copy size={15} />
            <span>IA</span>
          </button>
        )}
        {item.capabilities.includes("rename") && (
          <button
            disabled={busy}
            title="Rinomina"
            aria-label={"Rinomina " + item.name}
            onClick={() => edit("rename", item)}
          >
            <Pencil size={15} />
          </button>
        )}
        {item.capabilities.includes("copy") && (
          <button
            disabled={busy}
            title="Copia"
            aria-label={"Copia " + item.name}
            onClick={() => edit("copy", item)}
          >
            <Copy size={15} />
          </button>
        )}
        {item.capabilities.includes("move") && (
          <button
            disabled={busy}
            title="Sposta"
            aria-label={"Sposta " + item.name}
            onClick={() => edit("move", item)}
          >
            Sposta
          </button>
        )}
        {item.capabilities.includes("trash") && (
          <button
            className="danger"
            disabled={busy}
            title="Sposta nel cestino"
            aria-label={"Cestina " + item.name}
            onClick={() =>
              void run(
                () =>
                  filesApi.mutate(area, token, "/trash", {
                    root_id: rootId,
                    path: item.path,
                  }),
                isLibrary
                  ? "Copia spostata nel cestino. Originale sul server invariato."
                  : "Elemento spostato nel cestino.",
              )
            }
          >
            <Trash2 size={15} />
          </button>
        )}
      </div>
    );
  }
  function nameButton(item: BrowserNode) {
    return (
      <button
        className="file-name"
        disabled={busy || !["folder","file"].includes(item.kind)}
        onClick={() => item.kind==="folder" ? navigate(item.path) : setPreview(item)}
      >
        {item.kind === "folder" ? <Folder size={18} /> : <FileText size={18} />}
        <span>{item.name}</span>
      </button>
    );
  }
  return (
    <>
      <div className="file-subpage-caption">
        <p>
          {isLibrary
            ? "Copie di lavoro disponibili all’IA. Gli originali restano sul server."
            : "Esplora e gestisci i file presenti sul server."}
        </p>
        {busy && <span role="status">Operazione in corso…</span>}
      </div>
      <div className="file-toolbar">
        <div className="file-toolbar-left">
          <Breadcrumbs
            label={root?.label || "Server"}
            path={inTrash ? "" : path}
            disabled={busy}
            navigate={navigate}
          />
          {inTrash && <strong>Cestino</strong>}
          <label className="file-search">
            <Search size={15} />
            <input
              disabled={busy || inTrash}
              placeholder={recursive?"Cerca anche nelle sottocartelle":"Cerca in questa cartella"}
              aria-label="Cerca per nome"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label><input type="checkbox" checked={recursive} disabled={busy||inTrash} onChange={e=>{setRecursive(e.target.checked);setOffset(0);}}/>Sottocartelle</label>
        </div>
        <div className="file-toolbar-actions">
          <button
            className="file-tool"
            disabled={busy || loading}
            title="Aggiorna elenco"
            aria-label="Aggiorna elenco"
            onClick={() => {
              setError("");
              setReload((n) => n + 1);
            }}
          >
            <RefreshCw size={16} />
          </button>
          <button className="file-tool" disabled={busy||!rootId} onClick={()=>void showShares()}>Condivisioni</button>
          <button className="file-tool" disabled={busy||!writable} onClick={()=>void run(()=>filesApi.cancelPendingUploads(area,rootId,path),"Upload in sospeso annullati per questa cartella.")}>Annulla upload sospesi</button>
          <div className="view-switch">
            <button
              className={view === "list" ? "selected" : ""}
              aria-label="Vista elenco"
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              <List size={16} />
            </button>
            <button
              className={view === "grid" ? "selected" : ""}
              aria-label="Vista griglia"
              aria-pressed={view === "grid"}
              onClick={() => setView("grid")}
            >
              <Grid2X2 size={15} />
            </button>
          </div>
          <button
            className="file-tool"
            disabled={busy || !writable}
            onClick={() => edit("folder")}
          >
            <Folder size={15} /> Nuova cartella
          </button>
          {isLibrary && (
            <button
              className="file-tool"
              disabled={busy || !writable}
              onClick={() => setPicker(true)}
            >
              <Copy size={15} /> Copia dal server
            </button>
          )}
          <button
            className="upload-button"
            disabled={busy || !writable}
            onClick={() => input.current?.click()}
          >
            <Upload size={15} />
            {isLibrary ? "Carica copie" : "Carica file"}
          </button>
          <input
            type="file"
            multiple
            hidden
            ref={input}
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              e.target.value = "";
              void uploadFiles(files);
            }}
          />
        </div>
      </div>
      {busy&&uploadProgress&&<p role="status">{uploadProgress}</p>}
      {!busy&&uploadProgress&&error&&<p>Per riprendere un upload interrotto, seleziona nuovamente lo stesso file entro 24 ore.</p>}
      {shareLink&&<div className="file-notice"><label>Collegamento privato (richiede login)<input readOnly value={shareLink} onFocus={e=>e.target.select()}/></label></div>}
      {listing&&(listing as BrowserListing & {truncated?:boolean}).truncated&&<p className="connection-notice">Ricerca limitata a 10.000 elementi o 30 livelli. Cerca in una sottocartella per continuare.</p>}
      {shareList&&<div className="system-card"><div className="metric-head"><h3>Condivisioni della risorsa</h3><button onClick={()=>setShareList(null)}>Chiudi</button></div>{!shareList.length&&<p>Nessun collegamento creato.</p>}{shareList.map(item=><div className="settings-row" key={item.id}><div><strong>{item.path}</strong><small>Scadenza: {new Date(item.expiresAt).toLocaleString("it-IT")} · {item.revoked?"Revocato":""}</small></div><button disabled={busy||item.revoked} onClick={()=>void run(async()=>{await filesApi.revokeShare(area,item.id);setShareList(prev=>prev?.map(s=>s.id===item.id?{...s,revoked:true}:s)||null);},"Collegamento revocato.")}>Revoca</button></div>)}</div>}
      {preview&&<FilePreview area={area} rootId={rootId} token={token} item={preview} close={()=>setPreview(null)}/>}
      {error && (
        <div className="connection-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="file-notice" role="status">
          {notice}
        </div>
      )}
      <div className="file-workspace">
        <aside className="folder-pane">
          <div className="folder-heading">
            {isLibrary ? "LIBRERIA IA" : "RISORSE DEL SERVER"}
          </div>
          {roots.map((r) => (
            <button
              className={
                "tree-item " + (r.id === rootId && !inTrash ? "selected" : "")
              }
              key={r.id}
              disabled={busy}
              title={r.path}
              onClick={() => {
                setRootId(r.id);
                navigate("");
              }}
            >
              <Folder size={16} />
              <span>
                {r.label}
                {!r.available
                  ? " · non disponibile"
                  : !r.writable
                    ? " · sola lettura"
                    : ""}
              </span>
            </button>
          ))}
          <button
            className={"tree-item " + (inTrash ? "selected" : "")}
            disabled={busy || !root?.available}
            onClick={() => {
              setInTrash(true);
              setOffset(0);
            }}
          >
            <Trash2 size={16} /> Cestino
          </button>
          <div className="storage-box">
            <div>
              <strong>Spazio sul disco</strong>
            </div>
            {root?.storage ? (
              <>
                <p>
                  {bytes(root.storage.freeBytes)} liberi di{" "}
                  {bytes(root.storage.totalBytes)}
                </p>
                <small>Filesystem della cartella selezionata.</small>
              </>
            ) : (
              <small>Spazio non disponibile.</small>
            )}
          </div>
        </aside>
        <div className="file-content" aria-busy={loading || busy}>
          {loading ? (
            <p className="empty-files" role="status">
              Caricamento…
            </p>
          ) : inTrash ? (
            <div className="trash-list">
              {trash.length ? (
                trash.map((item) => (
                  <div className="trash-row" key={item.id}>
                    <div>
                      <strong>{item.path}</strong>
                      <small>
                        {new Date(item.deletedAt).toLocaleString("it-IT")}
                      </small>
                    </div>
                    <button
                      className="file-tool"
                      disabled={busy || !root?.writable}
                      onClick={() =>
                        void run(
                          () =>
                            filesApi.mutate(area, token, "/restore", {
                              root_id: rootId,
                              id: item.id,
                            }),
                          "Elemento ripristinato.",
                        )
                      }
                    >
                      <Undo2 size={15} /> Ripristina
                    </button>
                  </div>
                ))
              ) : (
                <p className="empty-files">
                  {error ? "Cestino non disponibile." : "Cestino vuoto."}
                </p>
              )}
            </div>
          ) : !listing ? (
            <p className="empty-files">
              Elenco non disponibile. Verifica la connessione e aggiorna.
            </p>
          ) : view === "list" ? (
            <div className="file-table-wrap">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Tipo</th>
                    <th>Dimensione</th>
                    <th>Ultima modifica</th>
                    <th>Azioni</th>
                  </tr>
                </thead>
                <tbody>
                  {listing.items.map((item) => (
                    <tr key={item.path}>
                      <td>{nameButton(item)}</td>
                      <td>
                        {item.kind === "folder"
                          ? "Cartella"
                          : item.kind === "link"
                            ? "Collegamento"
                            : item.kind === "special"
                              ? "File speciale"
                              : isLibrary
                                ? "Copia"
                                : "File"}
                      </td>
                      <td>{bytes(item.sizeBytes)}</td>
                      <td>
                        {new Date(item.modifiedAt).toLocaleString("it-IT")}
                      </td>
                      <td>{actions(item)}</td>
                    </tr>
                  ))}
                  {listing.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="empty-files">
                        {search
                          ? "Nessun nome corrisponde alla ricerca."
                          : "Cartella vuota."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="file-grid">
              {listing.items.map((item) => (
                <div className="file-tile" key={item.path}>
                  {nameButton(item)}
                  <small>
                    {item.kind === "folder"
                      ? "Cartella"
                      : bytes(item.sizeBytes)}
                    {isLibrary && item.kind === "file" ? " · Copia IA" : ""}
                  </small>
                  {actions(item)}
                </div>
              ))}
              {listing.items.length === 0 && (
                <p className="empty-files">
                  {search ? "Nessun risultato." : "Cartella vuota."}
                </p>
              )}
            </div>
          )}
          {listing && !inTrash && (
            <div className="file-pagination">
              <span>
                {listing.total
                  ? `${offset + 1}–${Math.min(offset + 100, listing.total)} di ${listing.total}`
                  : "0 elementi"}
              </span>
              <button
                disabled={busy || offset === 0}
                onClick={() => setOffset((n) => Math.max(0, n - 100))}
              >
                Precedenti
              </button>
              <button
                disabled={busy || offset + 100 >= listing.total}
                onClick={() => setOffset((n) => n + 100)}
              >
                Successivi
              </button>
            </div>
          )}
          {!inTrash && (
            <div
              className={
                "file-dropzone " +
                (!writable || busy ? "unavailable" : dragging ? "dragging" : "")
              }
              onDragOver={(e) => {
                e.preventDefault();
                if (writable && !busy) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                void uploadFiles(Array.from(e.dataTransfer.files));
              }}
            >
              <CloudUpload size={27} />
              <strong>
                {writable
                  ? "Trascina qui i file"
                  : "Caricamento non disponibile"}
              </strong>
              <small>
                {isLibrary
                  ? "Ogni upload conserva anche un originale in File server → Originali Libreria IA."
                  : root?.writable === false
                    ? "Questa risorsa è in sola lettura."
                    : "I file saranno caricati nella cartella aperta."}
              </small>
            </div>
          )}
        </div>
      </div>
      {action && (
        <div className="file-modal-shade">
          <form
            className="file-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="file-action-title"
            onSubmit={(e) => {
              e.preventDefault();
              void submitAction();
            }}
          >
            <header>
              <h2 id="file-action-title">{actionLabels[action.kind]}</h2>
              <button
                type="button"
                disabled={busy}
                aria-label="Chiudi operazione"
                onClick={() => setAction(null)}
              >
                <X size={18} />
              </button>
            </header>
            <label>
              {action.kind === "folder" || action.kind === "rename"
                ? "Nome"
                : "Percorso di destinazione dalla radice"}
              <input
                autoFocus
                disabled={busy}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
            {action.kind === "library" && (
              <p>
                Verrà creata una copia indipendente. Il file originale rimarrà
                sul server.
              </p>
            )}
            {["copy", "move", "library"].includes(action.kind) && (
              <small>La cartella di destinazione deve già esistere.</small>
            )}
            {error && (
              <div className="connection-error" role="alert">
                {error}
              </div>
            )}
            <footer>
              <button
                type="button"
                disabled={busy}
                onClick={() => setAction(null)}
              >
                Annulla
              </button>
              <button
                className="upload-button"
                disabled={busy || !value.trim()}
              >
                {busy ? "Operazione in corso…" : "Conferma"}
              </button>
            </footer>
          </form>
        </div>
      )}
      {picker && (
        <ServerPicker
          token={token}
          destination={path}
          onClose={() => setPicker(false)}
          onCopied={() => {
            setPicker(false);
            setNotice("Copia aggiunta. Originale conservato sul server.");
            setReload((n) => n + 1);
          }}
        />
      )}
    </>
  );
}

export default function FileManager() {
  const [area, setArea] = useState<FileArea>("server");
  const token = "";
  return (
    <section className="file-manager">
      <div className="file-page-heading">
        <h1>File</h1>

      </div>
      <div className="file-subnav" role="tablist" aria-label="Sezioni File">
        <button
          role="tab"
          id="server-tab"
          aria-selected={area === "server"}
          aria-controls="file-panel"
          onClick={() => setArea("server")}
        >
          File server
        </button>
        <button
          role="tab"
          id="library-tab"
          aria-selected={area === "library"}
          aria-controls="file-panel"
          onClick={() => setArea("library")}
        >
          Libreria IA
        </button>
      </div>

      <div
        id="file-panel"
        role="tabpanel"
        aria-labelledby={area === "server" ? "server-tab" : "library-tab"}
      >
        <FileBrowser key={area + ":" + token} area={area} token={token} />
      </div>
    </section>
  );
}

