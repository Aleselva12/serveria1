import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { create, act } from 'react-test-renderer';

const require = createRequire(import.meta.url);
const external = name => JSON.stringify(pathToFileURL(require.resolve(name)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const data = JSON.parse(await readFile(new URL('../src/project-status.generated.json', import.meta.url), 'utf8'));
globalThis.__homeRoadmap = { ...data, categories: data.categories.map(c => ({ ...c, goals: data.goals.filter(g => g.category === c.id) })) };
function url(code) { return 'data:text/javascript;base64,' + Buffer.from(code).toString('base64'); }
async function compile(path, replacements = []) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  let code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  code = code.replace(/from ["']react\/jsx-runtime["']/g, 'from ' + external('react/jsx-runtime')).replace(/from ["']react["']/g, 'from ' + external('react'));
  for (const [from, to] of replacements) code = code.replace(from, to);
  return import(url(code));
}
const status = await compile('../src/services/homeStatus.ts');
globalThis.__homeStatus = status;
globalThis.__projectApi = { projectChecks: async () => ({
  checkedAt: new Date().toISOString(), intervalSeconds: 300, scope: "preflight_only",
  checks: ["database", "library", "audio", "ollama", "word_sample"].map(id => ({
    id, label: id, status: "pass", detail: "Prerequisito di prova", checkedAt: new Date().toISOString(),
  })),
}) };
const { default: ProjectRoadmap } = await compile('../src/components/ProjectRoadmap.tsx', [
  [/import \{ homeRoadmap \} from .*?;/, 'const homeRoadmap = globalThis.__homeRoadmap;'],
  [/import \{ api \} from .*?;/, 'const api = globalThis.__projectApi;'],
]);
globalThis.__ProjectRoadmap = ProjectRoadmap;
let monitoring, refreshes, backendRefreshes, updateOpens;
const reset = () => { refreshes = 0; backendRefreshes = 0; updateOpens = 0; monitoring = { telemetry: null, services: [], telemetryError: '', servicesError: '', refresh: () => refreshes++ }; };
reset();
globalThis.__useHomeMonitoring = () => monitoring;
globalThis.__push = { currentPushState: async () => ({ supported: false, permission: 'unsupported', subscribed: false }) };
const { default: MobileHome } = await compile('../src/components/MobileHome.tsx', [
  [/import \{[^}]+\} from "lucide-react";/, 'const Activity=()=>null, CalendarDays=Activity, FileAudio=Activity, Files=Activity, Images=Activity, MessageCircle=Activity, RefreshCw=Activity, Settings=Activity, Server=Activity;'],
  [/import ProjectRoadmap from .*?;/, 'const ProjectRoadmap=globalThis.__ProjectRoadmap;'],
  [/import \{ serviceStatusLabels, serviceSummary \} from .*?;/, 'const { serviceStatusLabels, serviceSummary }=globalThis.__homeStatus;'],
  [/import \{ useHomeMonitoring \} from .*?;/, 'const useHomeMonitoring=globalThis.__useHomeMonitoring;'],
  [/import \{[^}]+\} from "\.\.\/services\/pushNotifications";/, 'const {currentPushState}=globalThis.__push;'],
]);
const text = renderer => JSON.stringify(renderer.toJSON());
const props = health => ({ health, checking: false, onRefresh: () => backendRefreshes++, onNavigate: () => {}, onOpenUpdates: () => updateOpens++ });

test('project goals have four groups and each open goal appears once without claimed server evidence', async () => {
  let r; await act(async () => { r = create(React.createElement(ProjectRoadmap)); });
  assert.equal(r.root.findAllByProps({ className: 'home-goal-group' }).length, 4);
  assert.equal(r.root.findAllByProps({ className: 'settings-row home-goal' }).length, data.goals.length);
  assert.equal(data.goals.length, 19);
  assert.equal(data.nodes.length, 4);
  assert.equal(r.root.findAllByProps({ className: 'home-architecture-node' }).length, 4);
  assert.ok(text(r).includes('Sviluppo:'));
  assert.ok(text(r).includes('Funzionamento:'));
  assert.ok(!text(r).includes('Funzionamento: Funziona'));
  assert.ok(text(r).includes('Prerequisiti presenti'));
  assert.ok(!text(r).includes('Riscontrato'));
  assert.ok(!text(r).includes('Chiuso: causa utente'));
  await act(async () => r.unmount());
});

test('mobile Home has a dedicated Update Cora button, independent from server-state refresh', async () => {
  reset();
  let r;
  await act(async () => { r = create(React.createElement(MobileHome, props(null))); });
  const update = r.root.findByProps({className: 'mobile-primary-button mobile-update-button'});
  assert.ok(update.children.some(child => typeof child === 'string' && child.includes('Aggiorna Cora')));
  assert.ok(text(r).includes('Apre gli aggiornamenti'));
  await act(async () => update.props.onClick());
  assert.equal(updateOpens, 1);
  assert.equal(backendRefreshes, 0);
  assert.equal(refreshes, 0);
  await act(async () => r.unmount());
});

test('mobile with no backend preserves unknown Ollama and absent measurements', async () => {
  reset(); let r; await act(async () => { r = create(React.createElement(MobileHome, props(null))); });
  const rows = r.root.findAllByProps({ className: 'mobile-service-row' });
  assert.equal(rows.length, 2);
  assert.ok(rows.every(row => row.findByType('strong').children.join('') === 'Non verificato'));
  assert.ok(!text(r).includes('servizi operativi'));
  assert.ok(!text(r).includes('Offline'));
  assert.ok(!text(r).includes('0%'));
  assert.equal(r.root.findAllByProps({ className: 'home-goal-group' }).length, 4);
  await act(async () => r.unmount());
});

test('mobile does not duplicate returned service rows and refresh updates both health and monitoring', async () => {
  reset(); monitoring.services = [
    { id: 'fastapi', label: 'FastAPI', status: 'ready', checkedAt: '' },
    { id: 'ollama', label: 'Ollama', status: 'offline', checkedAt: '' },
    { id: 'immich', label: 'Immich', status: 'unknown', checkedAt: '' },
  ];
  let r; await act(async () => { r = create(React.createElement(MobileHome, props({ ollama_online: false }))); });
  assert.equal(r.root.findAllByProps({ className: 'mobile-service-row' }).length, 3);
  assert.ok(text(r).includes('1/3 servizi raggiungibili'));
  assert.ok(text(r).includes('1 non verificati'));
  await act(async () => r.root.findByProps({ 'aria-label': 'Aggiorna stato server' }).props.onClick());
  assert.equal(refreshes, 1); assert.equal(backendRefreshes, 1);
  await act(async () => r.unmount());
});

test('service lookup failure is never summarized as all services operational', () => {
  assert.equal(status.serviceSummary([], 'offline'), 'Stato dei servizi non disponibile');
  assert.equal(status.serviceStatusLabels.unknown, 'Non verificato');
});


test('manual monitoring refresh refetches both sources, clears failed metrics and stops after unmount', async () => {
  let metricCalls = 0, serviceCalls = 0, fail = false;
  globalThis.window = { setInterval: () => 0 };
  globalThis.__monitorApi = {
    telemetry: async () => { metricCalls++; if (fail) throw Error('Metrics unavailable'); return { sampledAt: 'test' }; },
    services: async () => { serviceCalls++; return { services: [{ id: 'api', status: 'ready' }] }; },
  };
  const { useHomeMonitoring } = await compile('../src/services/useHomeMonitoring.ts', [[/import \{ api \} from .*?;/, 'const api=globalThis.__monitorApi;']]);
  let state;
  function Driver() { state = useHomeMonitoring(); return null; }
  let r; await act(async () => { r = create(React.createElement(Driver)); });
  assert.equal(metricCalls, 1); assert.equal(serviceCalls, 1);
  fail = true;
  await act(async () => state.refresh());
  assert.equal(metricCalls, 2); assert.equal(serviceCalls, 2);
  assert.equal(state.telemetry, null);
  assert.equal(state.services.length, 1);
  assert.equal(state.telemetryError, 'Metrics unavailable');
  const refresh = state.refresh;
  await act(async () => r.unmount());
  refresh();
  assert.equal(metricCalls, 2); assert.equal(serviceCalls, 2);
});
