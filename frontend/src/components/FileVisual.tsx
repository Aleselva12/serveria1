import { useEffect, useRef, useState } from "react";
import {
  File,
  FileText,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileArchive,
  FileAudio,
  FileVideo,
  Folder,
  Link,
  Loader2,
} from "lucide-react";
import type { BrowserNode, FileArea } from "../types/contracts";
import { filesApi } from "../services/filesApi";

export function fileStyle(item: BrowserNode) {
  const extension = item.name.split(".").pop()?.toLowerCase() || "";
  if (item.kind === "folder")
    return { Icon: Folder, tone: "folder", label: "Cartella" };
  if (item.kind === "link")
    return { Icon: Link, tone: "other", label: "Collegamento" };
  if (item.kind === "special")
    return { Icon: File, tone: "other", label: "File speciale" };
  if (extension === "pdf") return { Icon: FileText, tone: "pdf", label: "PDF" };
  if (["png", "jpg", "jpeg", "gif", "webp", "heic", "svg"].includes(extension))
    return { Icon: FileImage, tone: "image", label: "Immagine" };
  if (["csv", "tsv", "xls", "xlsx", "ods"].includes(extension))
    return { Icon: FileSpreadsheet, tone: "sheet", label: "Foglio di calcolo" };
  if (["mp4", "webm", "mov", "avi"].includes(extension))
    return { Icon: FileVideo, tone: "video", label: "Video" };
  if (["mp3", "wav", "m4a", "ogg", "flac"].includes(extension))
    return { Icon: FileAudio, tone: "audio", label: "Audio" };
  if (["zip", "gz", "tar", "7z", "rar"].includes(extension))
    return { Icon: FileArchive, tone: "archive", label: "Archivio" };
  if (
    [
      "py",
      "ts",
      "tsx",
      "js",
      "jsx",
      "html",
      "css",
      "json",
      "yml",
      "yaml",
      "toml",
      "sh",
      "sql",
    ].includes(extension)
  )
    return { Icon: FileCode2, tone: "code", label: "Codice" };
  if (["txt", "md", "docx", "doc", "odt", "log", "xml"].includes(extension))
    return { Icon: FileText, tone: "document", label: "Documento" };
  return {
    Icon: File,
    tone: "other",
    label: extension ? extension.toUpperCase() : "File",
  };
}
export function FileTypeIcon({
  item,
  size = 20,
}: {
  item: BrowserNode;
  size?: number;
}) {
  const { Icon, tone } = fileStyle(item);
  return (
    <span className={"drive-file-icon tone-" + tone}>
      <Icon size={size} />
    </span>
  );
}

// Never turn a folder of previews into hundreds of simultaneous requests.
let active = 0;
const waiting: Array<() => void> = [];
async function slot() {
  if (active >= 3) await new Promise<void>((resolve) => waiting.push(resolve));
  else active++;
  return () => {
    const next = waiting.shift();
    if (next) next();
    else active--;
  };
}
const smallPreviewExtensions = new Set([
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "pdf",
  "txt",
  "md",
  "json",
  "csv",
  "tsv",
  "py",
  "ts",
  "tsx",
  "js",
  "css",
  "yaml",
  "yml",
  "toml",
  "log",
  "xml",
  "docx",
]);
export function canShowThumbnail(item: BrowserNode) {
  return (
    item.kind === "file" &&
    item.sizeBytes != null &&
    item.sizeBytes <= 2 * 1024 * 1024 &&
    smallPreviewExtensions.has(item.name.split(".").pop()?.toLowerCase() || "")
  );
}
export default function FileThumbnail({
  area,
  rootId,
  token,
  item,
  enabled,
}: {
  area: FileArea;
  rootId: string;
  token: string;
  item: BrowserNode;
  enabled: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof filesApi.preview>
  > | null>(null);
  const [loading, setLoading] = useState(false);
  const { label, tone } = fileStyle(item);
  useEffect(() => {
    if (!enabled || !canShowThumbnail(item)) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px" },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [enabled, item.path]);
  useEffect(() => {
    let live = true,
      url = "";
    setPreview(null);
    setLoading(false);
    if (!enabled || !visible || !canShowThumbnail(item)) return;
    setLoading(true);
    void (async () => {
      const release = await slot();
      try {
        if (!live) return;
        const data = await filesApi.preview(area, token, rootId, item);
        url = data.url;
        if (live) setPreview(data);
        else if (url) URL.revokeObjectURL(url);
      } catch {
        /* The full preview/download remains available through the file menu. */
      } finally {
        release();
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [
    area,
    rootId,
    token,
    item.path,
    item.modifiedAt,
    item.sizeBytes,
    visible,
    enabled,
  ]);
  return (
    <div
      className={"drive-thumbnail tone-" + tone}
      ref={ref}
      aria-hidden="true"
    >
      {preview?.kind === "text" ? (
        <div className="drive-document-preview">
          <pre>{preview.text.slice(0, 1800)}</pre>
        </div>
      ) : preview?.mime.startsWith("image/") ? (
        <img src={preview.url} alt="" loading="lazy" />
      ) : preview?.mime === "application/pdf" ? (
        <iframe
          title={"Anteprima PDF " + item.name}
          src={preview.url + "#page=1&view=FitH&toolbar=0&navpanes=0"}
          sandbox="allow-same-origin"
          tabIndex={-1}
        />
      ) : (
        <div className="drive-format-preview">
          <FileTypeIcon item={item} size={48} />
          <span>{label}</span>
        </div>
      )}
      {loading && (
        <span className="drive-thumbnail-loading">
          <Loader2 size={18} />
        </span>
      )}
    </div>
  );
}
