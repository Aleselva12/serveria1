import { useEffect, useState } from "react";
import { apiBaseUrl } from "../services/api";
import { authenticatedFetch } from "../services/transport";

/** Display the active installed commit, not the checkout HEAD or a prepared candidate. */
export default function CurrentCommit() {
  const [commit, setCommit] = useState("");
  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const response = await authenticatedFetch(apiBaseUrl + "/api/v1/system/update");
        if (!response.ok) return;
        const data = await response.json();
        if (live && data.platform === "server" && /^[a-f0-9]{40}$/.test(data.active_commit || ""))
          setCommit(data.active_commit);
      } catch { /* Monitoring is informational and must never block Home. */ }
    }
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => { live = false; window.clearInterval(timer); };
  }, []);
  return <span> · Commit attivo: {commit ? <code title={commit}>{commit.slice(0, 12)}</code> : "non disponibile"}</span>;
}
