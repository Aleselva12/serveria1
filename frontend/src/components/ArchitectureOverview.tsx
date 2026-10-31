import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { architectureApi, type AgentCard, type AgentCatalog, type ModelTarget, type TargetModels, type ShadowRouterStatus, type DefaultModelsStatus } from '../services/architectureApi';
import type { BackendHealth, ServiceStatus } from '../types/contracts';
import './architecture-overview.css';

const labels: Record<string, string> = { supervisor: 'Cora centrale', structure_agent: 'Struttura', programmer_agent: 'Programmatore', local_research_agent: 'Documenti', audio_agent: 'Audio', email_quotes_agent: 'Mail e preventivi' };
const states: Record<string, string> = { ready: 'Disponibile', busy: 'In esecuzione', degraded: 'Da verificare', offline: 'Offline', error: 'Errore', unknown: 'Non verificato' };
const programUrl = (value?: string) => {
  if (!value) return null;
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
};
const initials = (name: string) => name.slice(0, 2).toUpperCase();

function AgentDetails({ agent, targets, onSaved, onClose }: { agent: AgentCard; targets: ModelTarget[]; onSaved: () => Promise<AgentCatalog>; onClose: () => void }) {
  const [machine, setMachine] = useState(agent.assignment?.machine_id || 'inherit');
  const [model, setModel] = useState(agent.model);
  const [catalog, setCatalog] = useState<TargetModels | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [reload, setReload] = useState(0);
  const [verifying, setVerifying] = useState(false);
  const [verificationId, setVerificationId] = useState('');
  const [verificationMessage, setVerificationMessage] = useState('');
  const [downloading, setDownloading] = useState(false);
  const baselineMachine = agent.assignment?.machine_id || 'inherit';
  useEffect(() => { setMachine(baselineMachine); setModel(agent.model); }, [agent.id, agent.model, baselineMachine, agent.configuration?.configuration_id]);
  useEffect(() => {
    if (!verificationId) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const state = await architectureApi.verification(verificationId);
        if (!active) return;
        if (state.status === 'completed') {
          const result = state.result;
          setVerificationMessage(result?.matches_requested === false ? `Modello diverso: richiesto ${result.configuration.model}, provider ${result.reported_model}.` : result?.reported_model ? `Risposta ricevuta da ${result.reported_model} · ${result.configuration.machine_id === 'local' ? 'Ollama di Cora' : agent.machine_name} · ${Math.round(result.duration_ms)} ms` : 'Risposta ricevuta, ma il provider non ha indicato il nome del modello.');
          setVerificationId(''); setVerifying(false); await onSaved();
        } else if (['failed', 'cancelled', 'timed_out', 'interrupted'].includes(state.status)) {
          setVerificationMessage(`Verifica ${state.status}: ${state.error_type || 'consulta Attività'}. Nessun risultato confermato.`);
          setVerificationId(''); setVerifying(false);
        } else { setVerificationMessage(`Verifica ${state.status === 'queued' ? 'in coda' : 'in corso'}…`); timer = setTimeout(poll, 1000); }
      } catch (e) { if (active) { setVerificationMessage(e instanceof Error ? e.message : 'Verifica non leggibile. Consulta Attività.'); setVerificationId(''); setVerifying(false); } }
    };
    void poll(); return () => { active = false; clearTimeout(timer); };
  }, [verificationId]);
  const dirty = machine !== baselineMachine || (machine !== 'inherit' && model !== agent.model);
  async function verify() {
    setVerifying(true); setVerificationMessage('Avvio verifica…');
    try { const result = await architectureApi.verify(agent.id); setVerificationId(result.run_id); }
    catch (e) { setVerifying(false); setVerificationMessage(e instanceof Error ? e.message : 'Verifica non avviata.'); }
  }
  async function reloadWhisper() {
    try { const result = await architectureApi.reloadTranscription(); setMessage(result.note); await onSaved(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Ricarica non riuscita.'); }
  }
  async function downloadWorker() {
    setDownloading(true); setError('');
    try { await architectureApi.downloadWorkerUpdate(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Download non riuscito.'); }
    finally { setDownloading(false); }
  }
  useEffect(() => {
    let active = true;
    setCatalog(null); setError('');
    if (machine === 'inherit') { setLoading(false); return; }
    setLoading(true);
    architectureApi.models(machine).then(data => {
      if (!active) return;
      setCatalog(data);
      setModel(old => data.models.some(m => m.name === old) ? old : data.models[0]?.name || '');
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [machine, reload]);
  async function save() {
    setSaving(true); setError(''); setMessage('');
    let stored = false;
    try {
      const saved = await architectureApi.save(agent.id, machine, machine === 'inherit' ? '' : model);
      stored = true;
      const readback = await onSaved();
      const current = readback.agents.find(a => a.id === agent.id);
      if (saved.configuration && current?.configuration?.configuration_id !== saved.configuration.configuration_id) throw Error('Configurazione salvata ma riletta diversa. Ricarica prima di avviare una chat.');
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('cora:model-config-changed'));
      const needsUpdate = machine !== 'inherit' && machine !== 'local' && !catalog?.agent_chat;
      setMessage(`Assegnazione salvata e riletta: ${current?.model || model} su ${current?.machine_name || machine}. ${needsUpdate ? 'Serve aggiornare il worker desktop prima di usarla. La chat non userà un altro modello al suo posto.' : 'Attiva dalla prossima chiamata; nessun riavvio di Cora richiesto.'}`);
    }
    catch (e) { setError((stored ? 'Salvataggio confermato, ma verifica di rilettura non riuscita: ' : '') + (e instanceof Error ? e.message : 'Salvataggio non riuscito.')); }
    finally { setSaving(false); }
  }
  return <section className="agent-detail" aria-label={`Dettaglio ${labels[agent.id] || agent.name}`}>
    <div className="catalog-heading"><div><small>SCHEDA AGENTE</small><h2>{labels[agent.id] || agent.name}</h2></div><button disabled={saving || verifying} onClick={onClose}>Chiudi scheda</button></div>
    <p>{agent.description}</p>
    <div className="agent-detail-columns"><div>
      <dl><dt>Stato runtime</dt><dd>{states[agent.runtime.status] || 'Non verificato'}</dd><dt>LLM configurato</dt><dd>{agent.model}</dd><dt>Esecuzione inferenza</dt><dd>{agent.machine_name}</dd><dt>Origine scelta</dt><dd>{({agent_assignment: 'Assegnazione di questo agente', global_selection: 'Modello generale ereditato', role_environment: 'Variabile del ruolo', default: 'Configurazione predefinita'} as Record<string,string>)[agent.configuration?.source || ''] || 'Configurazione ereditata'}</dd><dt>Ingresso</dt><dd>{agent.entrypoint || (agent.id === 'supervisor' ? 'Chat principale' : 'Delega da Cora')}</dd></dl>
      <div className="model-proof"><h3>Ultimo modello che ha risposto</h3>{agent.last_inference ? <><p>{agent.last_inference.reported_model || 'Nome non riportato dal provider'} · {new Date(agent.last_inference.observed_at).toLocaleString('it-IT')}</p><p>{agent.last_inference.configuration_id === agent.configuration?.configuration_id ? 'Chiamata con la configurazione attuale.' : 'Riscontro storico: la configurazione è cambiata. Esegui una nuova verifica.'}</p>{agent.last_inference.matches_requested === false && <p role="alert">Il modello riportato dal provider è diverso da quello richiesto.</p>}</> : <p>Nessuna risposta ancora osservata. La configurazione, da sola, non conferma un’inferenza.</p>}</div>
      {agent.transcription && <details className="model-proof"><summary>Trascrizione audio · separata dal LLM</summary><dl><dt>Motore</dt><dd>{agent.transcription.engine}</dd><dt>Modello Whisper</dt><dd>{agent.transcription.model_label}</dd><dt>Dispositivo configurato</dt><dd>{agent.transcription.device} · {agent.transcription.compute_type}</dd><dt>Stato</dt><dd>{agent.transcription.ready ? 'Pronto' : 'Da configurare'}</dd><dt>In memoria</dt><dd>{agent.transcription.loaded ? `${agent.transcription.loaded.model} · ${agent.transcription.loaded.device} · ${agent.transcription.loaded.compute_type}` : 'Non ancora caricato'}</dd></dl>{agent.transcription.loaded && (agent.transcription.loaded.model !== agent.transcription.model || agent.transcription.loaded.device !== agent.transcription.device || agent.transcription.loaded.compute_type !== agent.transcription.compute_type) && <p role="status">Whisper in memoria usa una configurazione precedente. Ricarica il motore prima della prossima trascrizione.</p>}<p>La scelta del LLM riguarda l’analisi del testo. Non cambia Whisper né trasferisce la trascrizione al desktop.</p><button type="button" disabled={saving || verifying} onClick={() => void reloadWhisper()}>Ricarica motore Whisper</button></details>}
      <details className="agent-tool-list"><summary>Tool disponibili · {agent.tools.length}</summary>
      <div className="agent-tools">{agent.tools.map(t => <details key={t.id}><summary>{t.name}</summary><p>{t.description}</p>{t.parameters.length > 0 && <small>Parametri: {t.parameters.join(', ')}</small>}</details>)}</div>
      {!agent.tools.length && <p>Nessun tool collegato rilevato.</p>}</details>
      <details className="agent-checks"><summary>Dettagli tecnici e capacità</summary><p>{agent.name} · {agent.module || agent.id} · {agent.available ? 'Modulo presente' : 'Dipendenze mancanti'}</p><pre>{JSON.stringify(agent.runtime.checks, null, 2)}</pre><ul>{agent.capabilities.map(c => <li key={c.id}>{c.description}</li>)}</ul></details>
    </div><form onSubmit={e => { e.preventDefault(); void save(); }}>
      <h3>LLM di questo agente</h3><p>{agent.id === 'supervisor' ? 'Questo è il modello della chat principale.' : 'Questa scelta riguarda solo questo agente. Per cambiare la chat principale, modifica Cora centrale.'}</p>
      <label>Macchina<select aria-label="Macchina" value={machine} disabled={saving || verifying} onChange={e => setMachine(e.target.value)}><option value="inherit">Usa il modello predefinito di Cora</option>{targets.map(t => <option key={t.id} value={t.id}>{t.name}{!t.enabled ? ' · OFF' : ''}</option>)}{machine !== 'inherit' && !targets.some(t => t.id === machine) && <option value={machine}>Macchina non disponibile</option>}</select></label>
      {machine === 'inherit' ? <p>Rimuove l’assegnazione specifica e ripristina la configurazione generale.</p> : <>
        <label>Modello installato<select aria-label="Modello installato" disabled={saving || verifying || loading || !catalog} value={model} onChange={e => setModel(e.target.value)}>{!catalog?.models.length && <option value="">{loading ? 'Caricamento…' : 'Nessun modello disponibile'}</option>}{catalog?.models.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}</select></label>
        <button type="button" disabled={loading || saving} onClick={() => setReload(n => n + 1)}>Ricarica modelli</button>
        {machine !== 'local' && <p>Il worker usa soltanto il modello selezionato da te in Macchine. ON/OFF e scelta restano manuali: se cambi modello, aggiorna anche l’assegnazione di questo agente.</p>}
        {catalog && !catalog.enabled && <p role="status">Worker OFF: abilitalo dalla pagina Macchine.</p>}
        {catalog && !catalog.agent_chat && <div className="model-proof" role="status"><h3>Worker da aggiornare per la chat</h3><p>Puoi salvare questa assegnazione. Per usarla serve aggiornare il container sul desktop: il test positivo in Macchine prova solo l’inferenza /generate, mentre gli agenti usano /chat con messaggi e tool.</p><button type="button" disabled={downloading} onClick={() => void downloadWorker()}>{downloading ? 'Download…' : 'Scarica aggiornamento worker'}</button><ol><li>Sul desktop estrai lo ZIP nella cartella worker esistente. Conserva il file .env con il token e le eventuali personalizzazioni di Compose. Leggi UPDATE.md incluso.</li><li>Da PowerShell, nella cartella worker, esegui:<pre>docker compose up -d --build --force-recreate worker</pre></li><li>Premi Ricarica modelli qui, poi Verifica modello con una chiamata.</li></ol><p>L’aggiornamento va eseguito sul desktop; ricaricare la pagina o riavviare solo Cora non aggiorna quel container.</p></div>}
      </>}
      {error && <p role="alert" className="catalog-error">{error}</p>}{message && <p role="status">{message}</p>}
      <button className="catalog-save" disabled={saving || verifying || (machine !== 'inherit' && (loading || !catalog?.enabled || !model))}>{saving ? 'Salvataggio…' : 'Salva assegnazione'}</button>
      <button type="button" disabled={saving || verifying || dirty} onClick={() => void verify()}>{verifying ? 'Verifica in corso…' : 'Verifica modello con una chiamata'}</button><p className="catalog-fineprint">Invia una breve richiesta al modello salvato, senza usare tool.{dirty ? ' Salva le modifiche prima della verifica.' : ''}</p>{verificationMessage && <p role="status">{verificationMessage}</p>}
      <p className="catalog-fineprint">Gli strumenti continuano a essere eseguiti da Cora. La macchina selezionata esegue l’inferenza del modello.</p>
    </form></div>
  </section>;
}

export default function ArchitectureOverview({ selectedNode, onSelect }: { health: BackendHealth | null; selectedNode: string; onSelect: (id: string) => void }) {
  const [data, setData] = useState<AgentCatalog | null>(null);
  const [targets, setTargets] = useState<ModelTarget[]>([]);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [shadowError, setShadowError] = useState('');
  const [pendingPack, setPendingPack] = useState('');
  const [shadowRouter, setShadowRouter] = useState<ShadowRouterStatus | null>(null);
  const [defaultModels, setDefaultModels] = useState<DefaultModelsStatus | null>(null);
  const [defaultModelsError, setDefaultModelsError] = useState('');
  const [error, setError] = useState('');
  const [targetError, setTargetError] = useState('');
  const [serviceError, setServiceError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshMessage, setRefreshMessage] = useState('');
  const [opened, setOpened] = useState(false);
  const [reloadEpoch, setReloadEpoch] = useState(0);
  const [program, setProgram] = useState('');
  const detailRef = useRef<HTMLDivElement>(null);
  async function reloadAgents() { const next = await architectureApi.agents(); setData(next); setError(''); return next; }
  async function refresh() {
    setLoading(true);
    setReloadEpoch(n => n + 1);
    await Promise.all([
      reloadAgents().catch(e => { setData(null); setError(e.message); }),
      architectureApi.targets().then(t => { setTargets(t); setTargetError(''); }).catch(e => { setTargets([]); setTargetError(e.message); }),
      api.services().then(s => { setServices(s.services.filter(p => !['fastapi', 'cora'].includes(p.id))); setServiceError(''); }).catch(e => { setServices([]); setServiceError(e.message); }),
      architectureApi.shadowRouter().then(r => { setShadowRouter(r); setShadowError(''); }).catch(e => { setShadowRouter(null); setShadowError(e.message); }),
      architectureApi.defaultModels().then(m => { setDefaultModels(m); setDefaultModelsError(''); }).catch(e => { setDefaultModels(null); setDefaultModelsError(e.message); }),
    ]);
    setLoading(false);
    setRefreshMessage('Aggiornato alle ' + new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }));
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('cora:model-config-changed'));
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!defaultModels?.running) return;
    const timer = setInterval(() => {
      architectureApi.defaultModels().then(m => { setDefaultModels(m); setDefaultModelsError(''); }).catch(e => setDefaultModelsError(e.message));
    }, 2000);
    return () => clearInterval(timer);
  }, [defaultModels?.running]);
  async function downloadDefaults(pack: 'base' | 'now' | 'future') {
    setDefaultModelsError(''); setPendingPack(pack);
    try { setDefaultModels(await architectureApi.downloadDefaultModels(pack)); }
    catch (e) { setDefaultModelsError(e instanceof Error ? e.message : 'Download non avviato.'); }
    finally { setPendingPack(''); }
  }
  const selected = data?.agents.find(a => a.id === selectedNode);
  const selectedProgram = services.find(s => s.id === program);
  return <div className="agent-catalog" aria-busy={loading}>
    <div className="catalog-heading"><div><h2>Agenti <span className="catalog-count">{data?.agents.length ?? '—'}</span></h2><p>Seleziona un agente per configurare modello, macchina e strumenti.</p></div><div className="catalog-refresh">{refreshMessage && !error && <small role="status">{refreshMessage}</small>}<button disabled={loading} onClick={() => void refresh()}>{loading ? 'Caricamento…' : 'Ricarica configurazione e stato'}</button></div></div>
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {!data && loading && <p>Caricamento agenti…</p>}
    {data && <><div className="agent-card-grid">{data.agents.map(a => <button className={`agent-card ${opened && selectedNode === a.id ? 'selected' : ''}`} key={a.id} aria-expanded={opened && selectedNode === a.id} onClick={() => { onSelect(a.id); setOpened(true); requestAnimationFrame(() => detailRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })); }}>
      <span className="agent-card-heading"><span className="catalog-monogram" aria-hidden="true">{initials(labels[a.id] || a.name)}</span><strong>{labels[a.id] || a.name}</strong><span aria-hidden="true">›</span></span>
      <span className="agent-card-model"><small>LLM configurato</small><b>{a.model}</b><span>{a.machine_name}</span></span>
      <span className="agent-card-footer"><span data-state={a.runtime.status}>● {states[a.runtime.status] || 'Non verificato'}</span><span>{a.tools.length} tool</span></span>
    </button>)}</div>
      {!data.agents.length && <p>Nessun agente rilevato dal backend.</p>}
      <div ref={detailRef}>{opened && selected && <><div className="catalog-errors">{targetError && <p role="alert">Elenco macchine: {targetError}</p>}</div><AgentDetails key={`${selected.id}:${reloadEpoch}`} agent={selected} targets={targets} onSaved={reloadAgents} onClose={() => setOpened(false)} /></>}</div>
      {data.inventory_errors.map((e, i) => <p role="alert" className="catalog-error" key={i}>Inventario tool: {e}</p>)}
    </>}
    <section className="catalog-section" aria-label="Programmi e servizi">
      <div className="catalog-heading"><div><h2>Programmi e servizi</h2><p>Clicca sull’icona o sul nome per aprire il programma in una nuova scheda.</p></div></div>
      {serviceError && <p role="alert" className="catalog-error">{serviceError}</p>}
      <div className="program-card-grid">{services.map(s => {
        const href = programUrl(s.browserUrl);
        const title = <><span className="catalog-monogram" aria-hidden="true">{initials(s.label)}</span><strong>{s.label}</strong>{href && <span aria-hidden="true">↗</span>}</>;
        return <article className={`program-card ${program === s.id ? 'selected' : ''}`} key={s.id}>
          {href ? <a className="program-launch" href={href} target="_blank" rel="noopener noreferrer" aria-label={`Apri ${s.label} (nuova scheda)`}>{title}</a> : <div className="program-launch">{title}</div>}
          <span data-state={s.status}>● {states[s.status] || 'Non verificato'}</span>
          <div className="program-actions"><small>{href ? 'Collegamento configurato' : 'Link non configurato'}</small><button type="button" aria-label={`Dettagli ${s.label}`} aria-expanded={program === s.id} onClick={() => setProgram(p => p === s.id ? '' : s.id)}>Dettagli</button></div>
        </article>;
      })}</div>
      {!serviceError && !loading && !services.length && <p>Nessun programma rilevato.</p>}
      {selectedProgram && <section className="program-detail" aria-label={`Stato ${selectedProgram.label}`}><div className="catalog-heading"><h3>{selectedProgram.label}</h3><button onClick={() => setProgram('')}>Chiudi dettagli</button></div><p>{selectedProgram.detail || 'Nessun dettaglio disponibile.'}</p><small>Ultimo controllo: {new Date(selectedProgram.checkedAt).toLocaleString('it-IT')}</small>{!programUrl(selectedProgram.browserUrl) && <p>Per abilitare l’icona, configura l’indirizzo browser del servizio nelle impostazioni di distribuzione di Cora. Deve essere raggiungibile dal dispositivo da cui apri la pagina.</p>}</section>}
      <p className="catalog-fineprint">Lo stato misura il controllo del backend; il collegamento usa l’indirizzo browser configurato. “Non verificato” non conferma che il servizio sia installato.</p>
    </section>
    <details className="catalog-disclosure" aria-label="Orchestrazione e router shadow">
      <summary><span>Orchestrazione <small>{shadowError ? 'Stato non disponibile' : 'Principale e router shadow'}</small></span></summary>
      {shadowError && <p role="alert">Stato orchestrazione non disponibile: {shadowError}</p>}
      {shadowRouter && <><div className="routing-rows"><div><strong>Orchestratore principale</strong><span>{shadowRouter.principal.model}</span><small>Decide il percorso operativo</small></div><div><strong>Router specializzato</strong><span>{shadowRouter.shadow.model}</span><small>Shadow · non controlla il routing</small></div></div><dl className="routing-metrics"><dt>Esempi raccolti</dt><dd>{shadowRouter.progress.examples}</dd><dt>{shadowRouter.progress.metric_label}</dt><dd>{shadowRouter.progress.agreement_percent == null ? 'Non disponibile' : shadowRouter.progress.agreement_percent + '%'}</dd></dl><p>{shadowRouter.note}</p>{(!shadowRouter.database_ready || shadowRouter.error) && <p role="alert">{shadowRouter.error || 'Dati del router non disponibili: verifica la migrazione 0008.'}</p>}</>}
    </details>
    <details className="catalog-disclosure" aria-label="Catalogo modelli locali di Cora">
      <summary><span>Modelli locali <small>{defaultModels?.running ? `Download in corso · ${defaultModels.current_model || 'preparazione'}` : 'Pacchetti e download su Ollama di Cora'}</small></span></summary>
      <p>Scarica solo i modelli mancanti. I pacchetti aggiuntivi non cambiano le assegnazioni degli agenti.</p>
      {defaultModels && (['base','now','future'] as const).map(pack => {
        const titles = { base: 'Base', now: 'Utili ora', future: 'Futuri' };
        const actions = { base: 'Scarica modelli default', now: 'Scarica modelli utili ora', future: 'Scarica modelli futuri' };
        const rows = defaultModels.packs[pack] || [];
        const missing = defaultModels.missing[pack] || [];
        return <details className="model-pack" key={pack}><summary>{titles[pack]} <small>{rows.length - missing.length}/{rows.length} presenti</small></summary>
          <ul className="model-pack-list">{rows.map(m => <li key={m.name}><div><strong>{m.name}</strong><small>{m.role}</small></div><span data-state={m.installed ? 'ready' : 'unknown'}>{m.installed ? 'Installato' : defaultModels.current_model === m.name ? 'Download…' : 'Mancante'}</span></li>)}</ul>
          <button type="button" disabled={Boolean(pendingPack) || defaultModels.running || missing.length === 0} onClick={() => void downloadDefaults(pack)}>{pendingPack === pack || (defaultModels.running && defaultModels.pack === pack) ? 'Download in corso…' : missing.length === 0 ? 'Già presenti' : actions[pack]}</button>
        </details>;
      })}
      {defaultModels && <p className="catalog-fineprint">{defaultModels.note}</p>}
    </details>
    {defaultModelsError && <p role="alert">Modelli locali: {defaultModelsError}</p>}
    {defaultModels?.running && <p role="status">Download in corso: {defaultModels.current_model || 'preparazione…'}</p>}
    {!!defaultModels?.failed.length && <p role="alert">Download fallito: {defaultModels.failed.join(', ')}{defaultModels.last_error ? ' · ' + defaultModels.last_error : ''}</p>}
    {data && <details className="catalog-disclosure"><summary>Componenti interni <small>{data.components.length}</small></summary>{data.components.map(c => <div className="component-row" key={c.id}><strong>{c.name}</strong><p>{c.description}</p></div>)}</details>}
  </div>;
}
