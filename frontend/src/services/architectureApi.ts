import { authenticatedFetch } from './transport';
import type { BackendComponent, ToolEntry } from '../types/contracts';
export type AgentCard = BackendComponent & {
  role: string; model: string; machine_name: string;
  assignment: { machine_id: string; model: string } | null;
  runtime: { status: string; checks: Record<string, unknown> };
  tools: ToolEntry[];
};
export type AgentCatalog = { agents: AgentCard[]; components: BackendComponent[]; inventory_errors: string[] };
export type ModelTarget = { id: string; name: string; enabled: boolean; active_model: string | null };
export type TargetModels = { models: { name: string }[]; enabled: boolean; active_model: string | null; agent_chat: boolean };
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
  async agents() {
    const data = await call<AgentCatalog>('/agents');
    if (!data || !Array.isArray(data.agents) || !Array.isArray(data.components) || !Array.isArray(data.inventory_errors) || !data.agents.every(a => a && typeof a.id === 'string' && typeof a.name === 'string' && typeof a.description === 'string' && typeof a.model === 'string' && typeof a.machine_name === 'string' && a.runtime && typeof a.runtime.status === 'string' && Array.isArray(a.tools) && a.tools.every(t => typeof t.name === 'string' && typeof t.description === 'string' && Array.isArray(t.parameters)))) throw Error('Catalogo agenti non valido.');
    return data;
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
    return call('/agents/' + encodeURIComponent(agentId) + '/model', { method: 'PUT', body: JSON.stringify({ machine_id: machineId, model }) });
  },
};
