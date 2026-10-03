import { useEffect, useRef, useState } from "react";
import { api } from "./api";

export function usePermanentContext(connected: boolean) {
  const [content, setContent] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dirty = useRef(false);
  const current = useRef("");
  const savePending = useRef(false);
  useEffect(() => {
    if (!connected) return;
    let cancelled = false;
    void api.systemContext().then(context => {
      if (cancelled || dirty.current) return;
      current.current = context.content;
      setContent(context.content); setUpdatedAt(context.updated_at); setVersion(context.version); setError("");
    }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Contesto non disponibile."); });
    return () => { cancelled = true; };
  }, [connected]);
  function edit(value: string) { dirty.current = true; current.current = value; setContent(value); }
  async function save() {
    if (savePending.current) return;
    savePending.current = true; setSaving(true); setError("");
    const submitted = current.current;
    try {
      const saved = await api.saveSystemContext(submitted);
      if (current.current === submitted) {
        dirty.current = false; current.current = saved.content; setContent(saved.content);
      }
      setUpdatedAt(saved.updated_at); setVersion(saved.version);
    } catch(e) { setError(e instanceof Error ? e.message : "Salvataggio non riuscito."); }
    finally { savePending.current = false; setSaving(false); }
  }
  return { content, updatedAt, version, saving, error, edit, save };
}
