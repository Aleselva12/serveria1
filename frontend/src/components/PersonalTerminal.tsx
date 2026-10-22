import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./personal-terminal.css";

type Config = { username: string; idle_seconds: number; max_seconds: number };

export default function PersonalTerminal() {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [password, setPassword] = useState("");
  const [state, setState] = useState("disconnected");
  const [error, setError] = useState("");
  const host = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    if (window.location.protocol !== "https:") {
      setError("Apri Cora dal tuo indirizzo Tailscale HTTPS per usare il terminale.");
      return;
    }
    void fetch("/terminal/status", { credentials: "same-origin", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 403
          ? "Accesso consentito soltanto al proprietario tramite Tailscale."
          : "Terminale non attivo. Completa la configurazione iniziale sul server (deploy/terminal_setup.py).");
        const data = await response.json() as Config;
        if (!controller.signal.aborted) setConfig(data);
      }).catch(e => { if (!controller.signal.aborted) setError(String(e.message || e)); });
    return () => controller.abort();
  }, [open]);

  useEffect(() => {
    if (!open || !config || !host.current) return;
    const term = new Terminal({ cursorBlink: true, fontSize: 14, scrollback: 1000,
      disableStdin: true, theme: { background: "#10151f", foreground: "#e5eaf3" } });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host.current);
    terminal.current = term;
    fit.fit();
    const observer = new ResizeObserver(() => fit.fit());
    observer.observe(host.current);
    const input = term.onData(data => {
      const ws = socket.current;
      if (ws?.readyState !== WebSocket.OPEN) return;
      if (ws.bufferedAmount > 131072) { ws.close(); return; }
      const chars = Array.from(data);
      for (let start = 0; start < chars.length; start += 1024)
        ws.send(JSON.stringify({ type: "input", data: chars.slice(start, start + 1024).join("") }));
    });
    const resize = term.onResize(({ cols, rows }) => {
      if (socket.current?.readyState === WebSocket.OPEN)
        socket.current.send(JSON.stringify({ type: "resize", cols: Math.max(20, Math.min(400, cols)), rows: Math.max(5, Math.min(150, rows)) }));
    });
    return () => {
      generation.current++;
      socket.current?.close(); socket.current = null;
      observer.disconnect(); input.dispose(); resize.dispose(); term.dispose(); terminal.current = null;
    };
  }, [open, config]);

  function disconnect() {
    generation.current++;
    socket.current?.close(); socket.current = null;
    if (terminal.current) terminal.current.options.disableStdin = true;
    setState("disconnected"); setPassword("");
  }

  function connect(event: React.FormEvent) {
    event.preventDefault();
    if (!config || !password || !terminal.current || state !== "disconnected") return;
    setError(""); setState("connecting");
    terminal.current.reset();
    const current = ++generation.current;
    let credential = password;
    setPassword("");
    const ws = new WebSocket(`wss://${window.location.host}/terminal/connect`);
    socket.current = ws;
    ws.onopen = () => {
      if (generation.current !== current) { credential = ""; ws.close(); return; }
      ws.send(JSON.stringify({ type: "auth", password: credential,
        cols: Math.max(20, Math.min(400, terminal.current?.cols || 80)),
        rows: Math.max(5, Math.min(150, terminal.current?.rows || 24)) }));
      credential = "";
    };
    ws.onmessage = event => {
      if (generation.current !== current) return;
      try {
        const message = JSON.parse(event.data);
        if (message.type === "ready") {
          setState("connected");
          if (terminal.current) { terminal.current.options.disableStdin = false; terminal.current.focus(); }
        } else if (message.type === "output" && typeof message.data === "string") terminal.current?.write(message.data);
        else if (message.type === "error") setError(message.message);
      } catch { setError("Risposta del terminale non valida."); ws.close(); }
    };
    ws.onerror = () => {
      if (generation.current === current) setError("Connessione non riuscita. Verifica Tailscale; dopo troppi tentativi attendi cinque minuti.");
    };
    ws.onclose = event => {
      credential = "";
      if (generation.current !== current) return;
      socket.current = null;
      setState("disconnected");
      if (terminal.current) terminal.current.options.disableStdin = true;
      if (event.reason) setError(event.reason);
    };
  }

  function key(data: string) {
    if (state === "connected") socket.current?.send(JSON.stringify({ type: "input", data }));
    terminal.current?.focus();
  }

  return <div className="personal-terminal">
    <button className="outline-button" aria-expanded={open} onClick={() => {
      disconnect(); setConfig(null); setError(""); setOpen(!open);
    }}>{open ? "Chiudi terminale" : "Terminale del server"}</button>
    {open && <section className="terminal-panel" aria-label="Terminale personale del server">
      <div className="terminal-heading"><h2>Terminale del server</h2>
        <span role="status">{state === "connected" ? "Connesso" : state === "connecting" ? "Connessione…" : "Disconnesso"}</span></div>
      <p>Accesso personale a Debian. Inserisci la password dell’utente del server; per i comandi amministrativi usa sudo.</p>
      {error && <p role="alert" className="programmer-error">{error}</p>}
      {!config && !error && <p>Verifica accesso…</p>}
      {config && <>
        <form onSubmit={connect} className="terminal-login">
          <span>Utente: <strong>{config.username}</strong></span>
          <input aria-label="Password Debian" type="password" autoComplete="off" maxLength={1024}
            placeholder="Password Debian" value={password} disabled={state !== "disconnected"}
            onChange={event => setPassword(event.target.value)} />
          <button type="submit" disabled={!password || state !== "disconnected"}>Connetti</button>
          <button type="button" disabled={state === "disconnected"} onClick={disconnect}>Disconnetti</button>
        </form>
        <p className="terminal-note">La password non viene salvata. Chiusura dopo {config.idle_seconds / 60} minuti senza input o {config.max_seconds / 60} minuti di sessione. La chiusura interrompe la connessione: usa tmux per lavori da mantenere attivi.</p>
        <div className="terminal-keys" aria-label="Tasti terminale">
          {([["Ctrl+C", "\u0003"], ["Tab", "\t"], ["Esc", "\u001b"], ["↑", "\u001b[A"], ["↓", "\u001b[B"], ["←", "\u001b[D"], ["→", "\u001b[C"], ["Invio", "\r"]] as const).map(([label, value]) =>
            <button key={label} disabled={state !== "connected"} onClick={() => key(value)}>{label}</button>)}
        </div>
        <div ref={host} className="terminal-screen" aria-label="Console Debian" />
      </>}
    </section>}
  </div>;
}
