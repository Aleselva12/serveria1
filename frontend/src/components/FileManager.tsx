import { useState } from "react";
import {
  CloudUpload,
  Folder,
  Grid2X2,
  List,
  Search,
  Upload,
} from "lucide-react";
import ConnectionNotice from "./ConnectionNotice";

export default function FileManager() {
  const [view, setView] = useState<"list" | "grid">("list");
  return (
    <section className="file-manager">
      <div className="file-toolbar">
        <div className="file-toolbar-left">
          <div className="breadcrumbs">Server</div>
          <label className="file-search">
            <Search size={15} />
            <input
              disabled
              placeholder="Ricerca da collegare"
              aria-label="Ricerca file non disponibile"
            />
          </label>
        </div>
        <div className="file-toolbar-actions">
          <div className="view-switch">
            <button
              className={view === "list" ? "selected" : ""}
              onClick={() => setView("list")}
              title="Vista elenco"
            >
              <List size={16} />
            </button>
            <button
              className={view === "grid" ? "selected" : ""}
              onClick={() => setView("grid")}
              title="Vista griglia"
            >
              <Grid2X2 size={15} />
            </button>
          </div>
          <button
            className="upload-button"
            disabled
            title="Collegamento da realizzare"
          >
            <Upload size={15} /> Carica file · da collegare
          </button>
        </div>
      </div>
      <div className="file-workspace">
        <aside className="folder-pane">
          <div className="folder-heading">RISORSE DI SISTEMA</div>
          <div className="tree-item">
            <Folder size={16} />
            <span>Cartelle da collegare</span>
          </div>
          <div className="storage-box">
            <div>
              <strong>Archiviazione</strong>
              <span>—</span>
            </div>
            <small>Spazio del NAS non disponibile.</small>
          </div>
        </aside>
        <div className="file-content">
          <ConnectionNotice feature="files" />
          {view === "list" ? (
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
                  <tr>
                    <td colSpan={5} className="empty-files">
                      Il contenuto del server non è ancora collegato.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div className="file-grid">
              <p className="empty-files">In attesa dei file del server.</p>
            </div>
          )}
          <div
            className="file-dropzone unavailable"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => e.preventDefault()}
          >
            <CloudUpload size={27} />
            <strong>Caricamento da collegare</strong>
            <small>
              Nessun file viene accettato finché l’upload sul server non sarà
              disponibile.
            </small>
          </div>
        </div>
      </div>
    </section>
  );
}
