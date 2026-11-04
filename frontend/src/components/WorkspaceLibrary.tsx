import { useEffect, useState } from "react";
import { Archive, ArchiveRestore, FolderGit2, Search } from "lucide-react";
import { programmerApi, type Workspace } from "../services/programmerApi";

export default function WorkspaceLibrary({ rows, selected, disabled, onSelect, onUpdate }: {
  rows: Workspace[]; selected: string; disabled: boolean;
  onSelect: (id: string) => void; onUpdate: (row: Workspace) => void;
}) {
  const [scope, setScope] = useState("work"), [query, setQuery] = useState("");
  const [name, setName] = useState(""), [saving, setSaving] = useState(false), [error, setError] = useState("");
  const current = rows.find(row => row.id === selected);
  useEffect(() => { setName(current?.title || ""); setError(""); }, [selected, current?.title]);
  const purpose = (row: Workspace) => row.purpose || (row.title === "Aggiornamento Cora dal branch main" ? "update" : "work");
  const groups = [
    { id: "work", label: "I miei lavori", count: rows.filter(r => !r.archived && purpose(r) === "work").length },
    { id: "update", label: "Aggiornamenti", count: rows.filter(r => !r.archived && purpose(r) === "update").length },
    { id: "archive", label: "Archivio", count: rows.filter(r => r.archived).length },
  ];
  const visible = rows.filter(row => (scope === "archive" ? row.archived : !row.archived && purpose(row) === scope)
    && `${row.title} ${row.id} ${row.base_commit || ""}`.toLowerCase().includes(query.toLowerCase()));
  async function update(changes: { title?: string; archived?: boolean }) {
    if (!current || disabled || saving) return;
    setSaving(true); setError("");
    try { onUpdate(await programmerApi.organize(current.id, changes)); }
    catch (e) { setError(String(e)); }
    finally { setSaving(false); }
  }
  return <section className="workspace-library" aria-label="Libreria workspace">
    <div className="workspace-library-head">
      <div><span className="eyebrow">PROGETTO CORA</span><h2>Le tue aree di lavoro</h2></div>
      <label className="workspace-search"><Search size={16} aria-hidden="true" />
        <input aria-label="Cerca workspace" placeholder="Cerca titolo o versione…" value={query} onChange={e => setQuery(e.target.value)} />
      </label>
    </div>
    <div className="workspace-scopes" role="group" aria-label="Categorie workspace">
      {groups.map(group => <button key={group.id} aria-pressed={scope === group.id}
        onClick={() => setScope(group.id)}>{group.label} <span>{group.count}</span></button>)}
    </div>
    <div className="workspace-library-list">
      {visible.map(row => <button key={row.id} className="workspace-row" aria-pressed={selected === row.id}
        disabled={disabled || saving} onClick={() => onSelect(row.id)}>
        <FolderGit2 size={18} aria-hidden="true" />
        <span><strong>{row.title}</strong><small>{row.mode === "git" ? "Git" : "Snapshot"} · {row.created_at ? new Date(row.created_at).toLocaleString("it-IT", {dateStyle: "short", timeStyle: "short"}) : ""}
          {row.base_commit && ` · base ${row.base_commit.slice(0, 8)}`}</small></span>
        <span className="workspace-row-kind">{row.id === selected ? "In uso" : row.archived ? "Archiviato" : "Apri"}</span>
      </button>)}
      {!visible.length && <p className="workspace-empty">{query ? "Nessun workspace corrisponde alla ricerca." : scope === "archive"
        ? "L’archivio è vuoto. I lavori archiviati si possono sempre riaprire."
        : scope === "update" ? "Qui trovi le copie create per aggiornare CORA." : "Crea un lavoro per iniziare. Gli aggiornamenti hanno un elenco separato."}</p>}
    </div>
    {current && <div className="workspace-organize">
      <label>Nome del lavoro in uso<input aria-label="Rinomina workspace" value={name} maxLength={120}
        disabled={disabled || saving} onChange={e => setName(e.target.value)} /></label>
      <button disabled={disabled || saving || !name.trim() || name.trim() === current.title}
        onClick={() => void update({title: name.trim()})}>Salva nome</button>
      <button disabled={disabled || saving} onClick={() => void update({archived: !current.archived})}>
        {current.archived ? <ArchiveRestore size={16} /> : <Archive size={16} />}
        {current.archived ? "Ripristina dall’archivio" : "Archivia lavoro"}</button>
      <small>L’archivio conserva codice, chat e riferimenti ai rilasci. Non libera spazio su disco.</small>
    </div>}
    {error && <p role="alert" className="programmer-error">{error}</p>}
  </section>;
}
