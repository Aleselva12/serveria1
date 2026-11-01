/* No third-party scripts: authorization codes never enter analytics or storage. */
(async () => {
  const params = new URLSearchParams(window.location.search);
  window.history.replaceState(null, "", window.location.pathname);
  const output = document.getElementById("result");
  const state = params.get("state") || "";
  const storageKey = "cora:calendar-oauth:" + state;
  let completionKey;
  try {
    completionKey = sessionStorage.getItem(storageKey);
    sessionStorage.removeItem(storageKey);
  } catch { /* Cookies/storage may be blocked. */ }
  if (!completionKey) {
    output.textContent = "Sessione Google non riconosciuta. Torna al Calendario e premi Ricollega Google nella stessa scheda.";
    return;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch("/backend/api/v1/calendar/google/auth/finish", {
      method: "POST", credentials: "include", signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-Cora-Client": "ui" },
      body: JSON.stringify({ state, completion_key: completionKey,
        code: params.get("code") || "", error: params.get("error") || "" }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Collegamento non completato. Torna al Calendario e riprova.");
    output.textContent = data.connected ? "Google Calendar collegato. Il rinnovo ordinario avviene automaticamente." : "Autorizzazione annullata: il collegamento precedente è stato conservato.";
  } catch (error) {
    output.textContent = controller.signal.aborted
      ? "Esito non confermato. Torna al Calendario e verifica il collegamento prima di riprovare."
      : error instanceof Error ? error.message : "Collegamento non completato.";
  } finally { clearTimeout(timeout); }
})();
