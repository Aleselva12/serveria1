import { apiBaseUrl } from "../services/api";

export default function SharedFile({ path }: { path: string }) {
  return <main className="auth-page"><section className="section-card auth-card">
    <h1>File condiviso</h1>
    <p>Accesso confermato. Il collegamento resta privato e può essere scaduto o revocato.</p>
    <a className="file-tool" href={apiBaseUrl + path} referrerPolicy="no-referrer">Scarica il file</a>
    <a href="/">Torna a Cora</a>
  </section></main>;
}
