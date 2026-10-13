import { useEffect, useState } from "react";
export type ResponseLength = "short" | "medium" | "long";
export function LengthChoice({ value, onChange, disabled }: { value: ResponseLength; onChange: (value: ResponseLength) => void; disabled: boolean }) {
  return <label>Lunghezza della risposta <select value={value} disabled={disabled} onChange={e => onChange(e.target.value as ResponseLength)}><option value="short">Corta</option><option value="medium">Media</option><option value="long">Lunga</option></select></label>;
}
export function RunTimer({ started, finished }: { started: number | null; finished: number | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    setNow(Date.now());
    if (started === null || finished !== null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [started, finished]);
  if (started === null) return null;
  const seconds = Math.max(0, Math.floor(((finished ?? now) - started) / 1000));
  return <p role="timer" aria-live="off">{finished === null ? "Tempo trascorso" : "Durata richiesta"}: {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</p>;
}
