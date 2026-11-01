import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Search,
  Plus,
  Save,
  X,
  Pencil,
  Download,
  ChevronDown,
} from "lucide-react";
import type { BrowserNode, FileArea } from "../types/contracts";
import {
  filesApi,
  type WordDocument as WordData,
  type WordBlock,
  type WordParagraph,
} from "../services/filesApi";
import "./word-document.css";

export default function WordDocument({
  area,
  token,
  rootId,
  item,
  editable,
  startEditing = false,
  close,
  saved,
}: {
  area: FileArea;
  token: string;
  rootId: string;
  item: BrowserNode;
  editable: boolean;
  startEditing?: boolean;
  close: () => void;
  saved: () => void;
}) {
  const [document, setDocument] = useState<WordData | null>(null);
  const [editing, setEditing] = useState(startEditing);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<{ after: string; text: string }[]>([]);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [match, setMatch] = useState(0);
  const [error, setError] = useState("");
  const [backup, setBackup] = useState("");
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);
  const nodes = useRef<Record<string, HTMLDivElement | null>>({});
  const dirty =
    Object.keys(edits).length > 0 || notes.some((note) => note.text.trim());
  const canEdit = editable && Boolean(document?.editable);
  const paragraphs = new Map(document?.paragraphs.map((p) => [p.id, p]));
  const matches =
    document?.paragraphs.filter(
      (p) =>
        query.trim() &&
        (edits[p.id] ?? p.text)
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase()),
    ) || [];
  useEffect(() => {
    let live = true;
    void filesApi
      .word(area, token, rootId, item.path)
      .then((value) => {
        if (live) setDocument(value);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [area, token, rootId, item.path]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const onClose = () => {
    if (
      !busy &&
      (!dirty || window.confirm("Scartare gli appunti non salvati?"))
    )
      close();
  };
  async function save() {
    if (!document || !canEdit || saving.current) return;
    saving.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await filesApi.saveWord(
        area,
        token,
        rootId,
        item.path,
        document.revision,
        edits,
        notes.filter((note) => note.text.trim()),
      );
      setDocument(result);
      setEdits({});
      setNotes([]);
      setSelected("");
      setBackup(result.backupPath);
      saved();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Salvataggio Word non riuscito.",
      );
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  function findNext() {
    if (!matches.length) return;
    const index = match % matches.length;
    nodes.current[matches[index].id]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
    setMatch(index + 1);
  }
  function renderNote(note: { after: string; text: string }, index: number) {
    return (
      <div className="word-new-note" key={index}>
        <label>
          Nuovo appunto
          <textarea
            autoFocus
            aria-label={"Nuovo appunto " + (index + 1)}
            placeholder="Data, conversazione, prossimi passi…"
            value={note.text}
            disabled={busy}
            onChange={(e) =>
              setNotes((previous) =>
                previous.map((n, i) =>
                  i === index ? { ...n, text: e.target.value } : n,
                ),
              )
            }
          />
        </label>
        <button
          disabled={busy}
          aria-label={"Rimuovi nuovo appunto " + (index + 1)}
          onClick={() =>
            setNotes((previous) => previous.filter((_, i) => i !== index))
          }
        >
          <X size={15} />
        </button>
      </div>
    );
  }
  function renderParagraph(p: WordParagraph) {
    const changed = edits[p.id] !== undefined;
    const value = edits[p.id] ?? p.text;
    return (
      <div
        className={
          "word-paragraph " +
          (p.heading ? "word-heading h" + p.heading : "") +
          (p.list ? " word-list-item" : "") +
          (query.trim() &&
          value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
            ? " word-match"
            : "")
        }
        ref={(element) => {
          nodes.current[p.id] = element;
        }}
        key={p.id}
      >
        {editing && canEdit && p.editable && selected === p.id ? (
          <textarea
            autoFocus
            aria-label={"Modifica paragrafo " + p.id}
            value={value}
            disabled={busy}
            onChange={(e) => {
              const text = e.target.value;
              setEdits((previous) => {
                const next = { ...previous };
                if (text === p.text) delete next[p.id];
                else next[p.id] = text;
                return next;
              });
            }}
          />
        ) : (
          <div className="word-paragraph-text">
            {changed
              ? value
              : p.runs.map((run, i) => (
                  <span
                    key={i}
                    style={{
                      fontWeight: run.bold ? 700 : undefined,
                      fontStyle: run.italic ? "italic" : undefined,
                      textDecoration: run.underline ? "underline" : undefined,
                      color: run.color || undefined,
                    }}
                  >
                    {run.text}
                  </span>
                ))}
            {!value && (
              <span className="word-empty-line">
                {editing ? "Paragrafo vuoto" : "\u00a0"}
              </span>
            )}
          </div>
        )}
        {editing && canEdit && p.editable && (
          <div className="word-paragraph-tools">
            <button
              disabled={busy}
              title="Modifica questo paragrafo"
              aria-label={"Modifica paragrafo " + p.id}
              onClick={() => setSelected(p.id)}
            >
              <Pencil size={13} />
            </button>
            <button
              disabled={busy}
              title="Aggiungi appunto subito dopo"
              aria-label={"Aggiungi appunto dopo " + p.id}
              onClick={() =>
                setNotes((previous) => [...previous, { after: p.id, text: "" }])
              }
            >
              <Plus size={14} />
            </button>
          </div>
        )}
        {editing && !p.editable && (
          <small className="word-locked-note">
            Elemento avanzato: modifica dal programma Word.
          </small>
        )}
        {notes.map(
          (note, index) => note.after === p.id && renderNote(note, index),
        )}
      </div>
    );
  }
  function renderBlocks(blocks: WordBlock[]): React.ReactNode {
    return blocks.map((block, i) =>
      block.kind === "paragraph" ? (
        paragraphs.has(block.id) && renderParagraph(paragraphs.get(block.id)!)
      ) : block.kind === "table" ? (
        <div className="word-table-wrap" key={"table" + i}>
          <table className="word-table">
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.cells.map((cell, c) => (
                    <td colSpan={cell.colSpan} key={c}>
                      {renderBlocks(cell.blocks)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="word-locked-note" key={"notice" + i}>
          {block.text}
        </p>
      ),
    );
  }
  return (
    <div className="file-modal-shade word-document-shade">
      <section
        className="word-document-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="word-document-title"
      >
        <header className="word-header">
          <div>
            <FileText size={23} />
            <div>
              <h2 id="word-document-title">{item.name}</h2>
              <small>
                {editing && canEdit
                  ? "Modifica degli appunti"
                  : "Documento Word"}
                {!canEdit && document ? " · Sola lettura" : ""}
              </small>
            </div>
          </div>
          <button
            aria-label="Chiudi documento Word"
            disabled={busy}
            onClick={onClose}
          >
            <X size={21} />
          </button>
        </header>
        <div className="word-toolbar">
          <label>
            <Search size={16} />
            <input
              aria-label="Trova cliente o testo"
              placeholder="Trova cliente o testo…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setMatch(0);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") findNext();
              }}
            />
          </label>
          {query && <small>{matches.length} risultati</small>}
          <button
            disabled={!matches.length}
            onClick={findNext}
            aria-label="Risultato successivo"
          >
            <ChevronDown size={16} />
          </button>
          <span className="word-toolbar-spacer" />
          <button
            disabled={busy}
            onClick={() =>
              void filesApi
                .download(area, token, rootId, item)
                .catch((e) => setError(e.message))
            }
          >
            <Download size={15} />
            Scarica
          </button>
          {canEdit && !editing && (
            <button onClick={() => setEditing(true)}>
              <Pencil size={15} />
              Modifica documento
            </button>
          )}
          {canEdit && editing && (
            <button
              disabled={busy}
              title="Aggiungi in fondo al documento"
              onClick={() =>
                setNotes((previous) => [
                  ...previous,
                  { after: "end", text: "" },
                ])
              }
            >
              <Plus size={15} />
              Aggiungi appunto
            </button>
          )}
          {canEdit && editing && (
            <button
              className="word-save"
              disabled={busy || !dirty}
              onClick={() => void save()}
            >
              <Save size={15} />
              {busy ? "Salvataggio…" : "Salva con backup"}
            </button>
          )}
        </div>
        {error && (
          <p className="word-error" role="alert">
            {error}
          </p>
        )}
        {backup && (
          <p className="word-saved" role="status">
            Salvato sul server. Backup precedente: {backup}
          </p>
        )}
        {!document && !error && (
          <p className="word-loading" role="status">
            Apertura documento Word…
          </p>
        )}
        {document && (
          <>
            <div className="word-document-scroll">
              <article className="word-paper">
                {renderBlocks(document.blocks)}
                {notes.map(
                  (note, index) =>
                    note.after === "end" && renderNote(note, index),
                )}
              </article>
            </div>
            <footer className="word-footer">
              <span>{dirty ? "Appunti non salvati" : document.note}</span>
              {editing && canEdit && (
                <small>
                  Matita: modifica testo · +: aggiungi un appunto in quel punto
                </small>
              )}
            </footer>
          </>
        )}
      </section>
    </div>
  );
}
