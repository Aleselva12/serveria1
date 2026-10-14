export type ThinkingState = { text: string; truncated: boolean };
export default function ThinkingPanel({ value }: { value: ThinkingState }) {
  if (!value.text) return null;
  return <details className="thinking-panel"><summary>Elaborazione del modello</summary>
    <p>Testo emesso dal modello; non certifica operazioni eseguite. Ultima chiamata, disponibile nella vista corrente.</p>
    {value.truncated && <p>Mostrata soltanto la parte più recente; la generazione prosegue senza tagli.</p>}
    <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: "18rem", overflow: "auto"}}>{value.text}</pre>
  </details>;
}
