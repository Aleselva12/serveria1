import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { architectureApi, type AgentCard, type AgentCatalog, type ModelTarget, type TargetModels } from '../services/architectureApi';
import type { BackendHealth, ServiceStatus } from '../types/contracts';
import './architecture-overview.css';

const labels: Record<string, string> = { supervisor: 'Cora centrale', structure_agent: 'Struttura', programmer_agent: 'Programmatore', local_research_agent: 'Documenti', audio_agent: 'Audio', email_quotes_agent: 'Mail e preventivi' };
const states: Record<string, string> = { ready: 'Disponibile', busy: 'In esecuzione', degraded: 'Da verificare', offline: 'Offline', error: 'Errore', unknown: 'Non verificato' };
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
  useEffect(() => {
    let active = true;
    setCatalog(null); setError('');
    if (machine === 'inherit') return;
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
      setMessage(`Assegnazione salvata e riletta: ${current?.model || model} su ${current?.machine_name || machine}. Attiva dalla prossima chiamata; nessun riavvio richiesto.`);
    }
    catch (e) { setError((stored ? 'Salvataggio confermato, ma verifica di rilettura non riuscita: ' : '') + (e instanceof Error ? e.message : 'Salvataggio non riuscito.')); }
    finally { setSaving(false); }
  }
  return <section className="agent-detail" aria-label={`Dettaglio ${labels[agent.id] || agent.name}`}>
    <div className="catalog-heading"><div><small>SCHEDA AGENTE</small><h2>{labels[agent.id] || agent.name}</h2></div><button disabled={saving} onClick={onClose}>Chiudi scheda</button></div>
    <p>{agent.description}</p>
    <div className="agent-detail-columns"><div>
      <dl><dt>Nome nel sistema</dt><dd>{agent.name}</dd><dt>Stato runtime</dt><dd>{states[agent.runtime.status] || 'Non verificato'}</dd><dt>Modulo</dt><dd>{agent.available ? 'Presente' : 'Dipendenze mancanti'}</dd><dt>LLM configurato</dt><dd>{agent.model}</dd><dt>Esecuzione inferenza</dt><dd>{agent.machine_name}</dd><dt>Origine scelta</dt><dd>{({agent_assignment: 'Assegnazione di questo agente', global_selection: 'Modello generale ereditato', role_environment: 'Variabile del ruolo', default: 'Configurazione predefinita'} as Record<string,string>)[agent.configuration?.source || ''] || 'Configurazione ereditata'}</dd><dt>Ingresso</dt><dd>{agent.entrypoint || (agent.id === 'supervisor' ? 'Chat principale' : 'Delega da Cora')}</dd><dt>Codice</dt><dd>{agent.module || agent.id}</dd></dl>
      <div className="model-proof"><h3>Ultimo modello che ha risposto</h3>{agent.last_inference ? <><p>{agent.last_inference.reported_model || 'Nome non riportato dal provider'} · {new Date(agent.last_inference.observed_at).toLocaleString('it-IT')}</p><p>{agent.last_inference.configuration_id === agent.configuration?.configuration_id ? 'Chiamata con la configurazione attuale.' : 'Riscontro storico: la configurazione è cambiata. Esegui una nuova verifica.'}</p>{agent.last_inference.matches_requested === false && <p role="alert">Il modello riportato dal provider è diverso da quello richiesto.</p>}</> : <p>Nessuna risposta ancora osservata. La configurazione, da sola, non conferma un’inferenza.</p>}</div>
      {agent.transcription && <section className="model-proof"><h3>Trascrizione audio · separata dal LLM</h3><dl><dt>Motore</dt><dd>{agent.transcription.engine}</dd><dt>Modello Whisper</dt><dd>{agent.transcription.model_label}</dd><dt>Dispositivo configurato</dt><dd>{agent.transcription.device} · {agent.transcription.compute_type}</dd><dt>Stato</dt><dd>{agent.transcription.ready ? 'Pronto' : 'Da configurare'}</dd><dt>In memoria</dt><dd>{agent.transcription.loaded ? `${agent.transcription.loaded.model} · ${agent.transcription.loaded.device} · ${agent.transcription.loaded.compute_type}` : 'Non ancora caricato'}</dd></dl>{agent.transcription.loaded && (agent.transcription.loaded.model !== agent.transcription.model || agent.transcription.loaded.device !== agent.transcription.device || agent.transcription.loaded.compute_type !== agent.transcription.compute_type) && <p role="status">Whisper in memoria usa una configurazione precedente. Ricarica il motore prima della prossima trascrizione.</p>}<p>La scelta del LLM riguarda l’analisi del testo. Non cambia Whisper né trasferisce la trascrizione al desktop.</p><button type="button" disabled={saving || verifying} onClick={() => void reloadWhisper()}>Ricarica motore Whisper</button></section>}
      <h3>Tool disponibili · {agent.tools.length}</h3>
      <div className="agent-tools">{agent.tools.map(t => <details key={t.id}><summary>{t.name}</summary><p>{t.description}</p>{t.parameters.length > 0 && <small>Parametri: {t.parameters.join(', ')}</small>}</details>)}</div>
      {!agent.tools.length && <p>Nessun tool collegato rilevato.</p>}
      <details className="agent-checks"><summary>Controlli e capacità</summary><pre>{JSON.stringify(agent.runtime.checks, null, 2)}</pre><ul>{agent.capabilities.map(c => <li key={c.id}>{c.description}</li>)}</ul></details>
    </div><form onSubmit={e => { e.preventDefault(); void save(); }}>
      <h3>LLM di questo agente</h3><p>{agent.id === 'supervisor' ? 'Questo è il modello della chat principale.' : 'Questa scelta riguarda solo questo agente. Per cambiare la chat principale, modifica Cora centrale.'}</p>
      <label>Macchina<select aria-label="Macchina" value={machine} disabled={saving} onChange={e => setMachine(e.target.value)}><option value="inherit">Usa il modello predefinito di Cora</option>{targets.map(t => <option key={t.id} value={t.id}>{t.name}{!t.enabled ? ' · OFF' : ''}</option>)}{machine !== 'inherit' && !targets.some(t => t.id === machine) && <option value={machine}>Macchina non disponibile</option>}</select></label>
      {machine === 'inherit' ? <p>Rimuove l’assegnazione specifica e ripristina la configurazione generale.</p> : <>
        <label>Modello installato<select aria-label="Modello installato" disabled={saving || loading || !catalog} value={model} onChange={e => setModel(e.target.value)}>{!catalog?.models.length && <option value="">{loading ? 'Caricamento…' : 'Nessun modello disponibile'}</option>}{catalog?.models.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}</select></label>
        <button type="button" disabled={loading || saving} onClick={() => setReload(n => n + 1)}>Ricarica modelli</button>
        {machine !== 'local' && <p>Il worker usa soltanto il modello selezionato da te in Macchine. ON/OFF e scelta restano manuali: se cambi modello, aggiorna anche l’assegnazione di questo agente.</p>}
        {catalog && !catalog.enabled && <p role="status">Worker OFF: abilitalo dalla pagina Macchine.</p>}
        {catalog && !catalog.agent_chat && <p role="status">Aggiorna il container worker sul desktop per abilitare le conversazioni degli agenti.</p>}
      </>}
      {error && <p role="alert" className="catalog-error">{error}</p>}{message && <p role="status">{message}</p>}
      <button className="catalog-save" disabled={saving || verifying || (machine !== 'inherit' && (loading || !catalog?.enabled || !catalog?.agent_chat || !model))}>{saving ? 'Salvataggio…' : 'Salva assegnazione'}</button>
      <button type="button" disabled={saving || verifying || dirty} onClick={() => void verify()}>{verifying ? 'Verifica in corso…' : 'Verifica modello con una chiamata'}</button><p className="catalog-fineprint">Invia una breve richiesta al modello salvato, senza usare tool.{dirty ? ' Salva le modifiche prima della verifica.' : ''}</p>{verificationMessage && <p role="status">{verificationMessage}</p>}
      <p className="catalog-fineprint">Gli strumenti continuano a essere eseguiti da Cora. La macchina selezionata esegue l’inferenza del modello.</p>
    </form></div>
  </section>;
}

export default function ArchitectureOverview({ selectedNode, onSelect }: { health: BackendHealth | null; selectedNode: string; onSelect: (id: string) => void }) {
  const [data, setData] = useState<AgentCatalog | null>(null);
  const [targets, setTargets] = useState<ModelTarget[]>([]);
  const [services, setServices] = useState<ServiceStatus[]>([]);
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
    ]);
    setLoading(false);
    setRefreshMessage('Configurazione riletta dal backend. Le assegnazioni salvate qui valgono dalla prossima chiamata, senza riavvio. Per codice e variabili Docker serve invece l’aggiornamento di Cora.');
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('cora:model-config-changed'));
  }
  useEffect(() => { void refresh(); }, []);
  const selected = data?.agents.find(a => a.id === selectedNode);
  const selectedProgram = services.find(s => s.id === program);
  return <div className="agent-catalog">
    <div className="catalog-heading"><div><small>SERVER / AGENTI</small><h2>Agenti<span>.</span></h2><p>Apri una scheda per vedere strumenti, stato e modello.</p></div><button disabled={loading} onClick={() => void refresh()}>{loading ? 'Caricamento…' : 'Ricarica configurazione e stato'}</button></div>
    {refreshMessage && !error && <p role="status">{refreshMessage}</p>}
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {data && <><div className="agent-card-grid">{data.agents.map(a => <button className={`agent-card ${opened && selectedNode === a.id ? 'selected' : ''}`} key={a.id} aria-expanded={opened && selectedNode === a.id} onClick={() => { onSelect(a.id); setOpened(true); requestAnimationFrame(() => detailRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })); }}>
      <span className="agent-card-heading"><span className="catalog-monogram">{initials(labels[a.id] || a.name)}</span><strong>{labels[a.id] || a.name}</strong><span aria-hidden="true">↗</span></span><span className="agent-card-description">{a.description}</span><span className="agent-card-info"><span><small>TOOL COLLEGATI</small><b>{a.tools.length}</b></span><span><small>LLM CONFIGURATO</small><b>{a.model}</b></span></span><span className="agent-card-footer"><span data-state={a.runtime.status}>● {states[a.runtime.status] || 'Non verificato'}</span><span>{a.machine_name}</span></span>
    </button>)}</div>
      <div ref={detailRef}>{opened && selected && <><div className="catalog-errors">{targetError && <p role="alert">Elenco macchine: {targetError}</p>}</div><AgentDetails key={`${selected.id}:${reloadEpoch}`} agent={selected} targets={targets} onSaved={reloadAgents} onClose={() => setOpened(false)} /></>}</div>
      {data.inventory_errors.map((e, i) => <p className="catalog-error" key={i}>Inventario tool: {e}</p>)}
    </>}
    <div className="catalog-heading programs-heading"><div><small>SERVER / PROGRAMMI E SERVIZI</small><h2>Altri programmi<span>.</span></h2></div></div>
    {serviceError && <p role="alert" className="catalog-error">{serviceError}</p>}
    <div className="agent-card-grid program-card-grid">{services.map(s => <button className={`program-card ${program === s.id ? 'selected' : ''}`} key={s.id} aria-expanded={program === s.id} onClick={() => setProgram(p => p === s.id ? '' : s.id)}><span className="agent-card-heading"><span className="catalog-monogram">{initials(s.label)}</span><strong>{s.label}</strong></span><span data-state={s.status}>● {states[s.status] || 'Non verificato'}</span><small>{s.detail || 'Nessun dettaglio disponibile'}</small></button>)}</div>
    {selectedProgram && <section className="agent-detail"><h3>{selectedProgram.label}</h3><p>{selectedProgram.detail}</p><p>Ultimo controllo: {new Date(selectedProgram.checkedAt).toLocaleString('it-IT')}</p>{selectedProgram.browserUrl && /^https?:\/\//.test(selectedProgram.browserUrl) && <a href={selectedProgram.browserUrl} target="_blank" rel="noreferrer">Apri programma ↗</a>}</section>}
    <p className="catalog-fineprint">Servizi configurati e container rilevati dal backend. “Non verificato” non conferma che un programma sia installato.</p>
    {data && <details className="catalog-support"><summary>Componenti interni di Cora · {data.components.length}</summary>{data.components.map(c => <div key={c.id}><strong>{c.name}</strong><p>{c.description}</p></div>)}</details>}
  </div>;
}
