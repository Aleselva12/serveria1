import { authenticatedFetch } from './transport';
import type { BackendComponent, ToolEntry } from '../types/contracts';
export type ModelConfiguration = { role: string; model: string; machine_id: string; source: string; configuration_id: string };
export type ModelObservation = { reported_model: string | null; requested_model: string; machine_id: string; configuration_id: string; observed_at: string; matches_requested: boolean | null };
export type Verification = { id: string; status: string; error_type?: string; result?: { configuration: ModelConfiguration; reported_model: string | null; matches_requested?: boolean | null; provider_reported: boolean; duration_ms: number } };
export type AgentCard = BackendComponent & {
  role: string; model: string; machine_name: string;
  configuration?: ModelConfiguration; last_inference?: ModelObservation | null; entrypoint?: string; module?: string;
  transcription?: { engine: string; model_label: string; model: string; device: string; compute_type: string; ready: boolean; loaded: {model: string; device: string; compute_type: string} | null; diarization_model: string | null };
  assignment: { machine_id: string; model: string } | null;
  runtime: { status: string; checks: Record<string, unknown> };
  tools: ToolEntry[];
};
export type AgentCatalog = { agents: AgentCard[]; components: BackendComponent[]; inventory_errors: string[] };
export type ModelTarget = { id: string; name: string; enabled: boolean; active_model: string | null };
export type TargetModels = { models: { name: string }[]; enabled: boolean; active_model: string | null; agent_chat: boolean };
export type DefaultModelsStatus = {
  running: boolean;
  current_model: string | null;
  completed: string[];
  failed: string[];
  last_error: string | null;
  models: { name: string; role: string; installed: boolean }[];
  missing: string[];
  note: string;
};
export type ShadowRouterStatus = {
  principal: ModelConfiguration;
  shadow: ModelConfiguration;
  progress: { examples: number; evaluated: number; matched: number; agreement_percent: number | null; last_example: string | null; model: string; active_for_routing: boolean; metric_label: string };
  database_ready: boolean;
  error: string | null;
  note: string;
};
const base = (import.meta.env.VITE_API_BASE_URL || '/backend').replace(/\/$/, '');
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await authenticatedFetch(base + '/api/v1/architecture' + path, {
      ...init, signal: controller.signal,
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
    });
    if (!response.headers.get('content-type')?.includes('application/json')) throw Error('Risposta non valida dal backend.');
    const result = await response.json();
    if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : `Richiesta non riuscita (HTTP ${response.status}).`);
    return result as T;
  } catch (e) {
    if (controller.signal.aborted) throw Error('Tempo di attesa scaduto. Ricarica per verificare lo stato prima di riprovare.');
    throw e;
  } finally { clearTimeout(timer); }
}
export const architectureApi = {
  async downloadWorkerUpdate() {
    const response = await authenticatedFetch(base + '/api/v1/architecture/worker-update', { signal: AbortSignal.timeout(30000) });
    if (!response.ok || !response.headers.get('content-type')?.includes('application/zip')) throw Error('Download aggiornamento worker non riuscito. Aggiorna Cora e riprova.');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = 'cora-worker-update.zip'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  verify(agentId: string) { return call<{run_id: string}>('/agents/' + encodeURIComponent(agentId) + '/verify', { method: 'POST' }); },
  async verification(id: string): Promise<Verification> {
    const response = await authenticatedFetch(base + '/api/v1/runtime/runs/' + encodeURIComponent(id), { signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw Error('Impossibile leggere la verifica. Consulta Attività.');
    return response.json();
  },
  async reloadTranscription() {
    const response = await authenticatedFetch(base + '/api/v1/audio/engine/reload', { method: 'POST', signal: AbortSignal.timeout(10000) });
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Ricarica Whisper non riuscita.');
    return data as {note: string};
  },
  async agents() {
    const data = await call<AgentCatalog>('/agents');
    if (!data || !Array.isArray(data.agents) || !Array.isArray(data.components) || !Array.isArray(data.inventory_errors) || !data.agents.every(a => a && typeof a.id === 'string' && typeof a.name === 'string' && typeof a.description === 'string' && typeof a.model === 'string' && typeof a.machine_name === 'string' && a.runtime && typeof a.runtime.status === 'string' && Array.isArray(a.tools) && a.tools.every(t => typeof t.name === 'string' && typeof t.description === 'string' && Array.isArray(t.parameters)))) throw Error('Catalogo agenti non valido.');
    return data;
  },
  async shadowRouter() {
    return call<ShadowRouterStatus>('/shadow-router');
  },
  async defaultModels() {
    return call<DefaultModelsStatus>('/default-models');
  },
  async downloadDefaultModels() {
    return call<DefaultModelsStatus>('/default-models/download', { method: 'POST' });
  },
  async targets() {
    const data = await call<{ targets: ModelTarget[] }>('/model-targets');
    if (!Array.isArray(data?.targets) || !data.targets.every(t => typeof t.id === 'string' && typeof t.name === 'string' && typeof t.enabled === 'boolean')) throw Error('Elenco macchine non valido.');
    return data.targets;
  },
  async models(id: string) {
    const data = await call<TargetModels>('/model-targets/' + encodeURIComponent(id));
    if (!data || !Array.isArray(data.models) || !data.models.every(m => typeof m.name === 'string') || typeof data.enabled !== 'boolean' || typeof data.agent_chat !== 'boolean') throw Error('Elenco modelli non valido.');
    return data;
  },
  save(agentId: string, machineId: string, model: string) {
    return call<{ assignment: AgentCard['assignment']; configuration: ModelConfiguration; requires_restart: boolean }>('/agents/' + encodeURIComponent(agentId) + '/model', { method: 'PUT', body: JSON.stringify({ machine_id: machineId, model }) });
  },
};
