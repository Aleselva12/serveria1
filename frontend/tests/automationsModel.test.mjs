import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/automations/model.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const m = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

const contract = (effect, required = []) => ({ id: 'x.y', effect, input_schema: { required, properties: Object.fromEntries(required.map(r => [r, { type: 'string' }])) } });
const entries = [
  { id: 'tools.py:calculator_tool', name: 'calculator_tool', description: 'Calcola', group: 'Sistema', kind: 'tool', status: 'connected', capabilities: [contract('compute', ['expression'])] },
  { id: 'tools.py:remember_tool', name: 'remember_tool', description: '', group: 'Memoria', kind: 'tool', status: 'connected', capabilities: [contract('write')] },
  { id: 'api:x', name: 'GET /x', description: '', group: 'API', kind: 'api', status: 'direct' },
  { id: 'planned:y', name: 'y', description: '', group: 'Futuro', kind: 'planned', status: 'planned' },
];

test('catalog keeps draftable tools with their effect and drops planned ones', () => {
  const c = m.catalogFrom(entries);
  assert.deepEqual(c.map(t => t.id).sort(), ['api:x', 'tools.py:calculator_tool', 'tools.py:remember_tool']);
  const calc = c.find(t => t.id === 'tools.py:calculator_tool');
  assert.equal(calc.effect, 'compute'); assert.equal(calc.executable, true); assert.deepEqual(calc.required, ['expression']);
  const api = c.find(t => t.id === 'api:x');
  assert.equal(api.effect, 'none'); assert.equal(api.executable, false);
});

test('canvas round trip keeps ids, config, tool and branch labels; positions stay in range', () => {
  const catalog = m.catalogFrom(entries);
  const draft = m.recipeDraft(m.RECIPES.find(r => r.id === 'calcolo'), catalog);
  assert.deepEqual(draft.missing, []);
  const canvas = m.toCanvas(draft, catalog);
  canvas.nodes[0].position = { x: -150, y: -40 };
  const back = m.fromCanvas(canvas.nodes, canvas.edges);
  assert.deepEqual(back.nodes.map(n => n.id), draft.nodes.map(n => n.id));
  assert.ok(back.nodes.every(n => n.x >= 0 && n.x <= 10000 && n.y >= 0 && n.y <= 10000));
  assert.equal(back.nodes.find(n => n.id === 'conto').tool_id, 'tools.py:calculator_tool');
  assert.deepEqual(back.nodes.find(n => n.id === 'check').config, { left: '{{conto}}', op: 'gt', right: '40' });
  assert.deepEqual(back.edges.filter(e => e.label).map(e => e.label).sort(), ['no', 'sì']);
  assert.equal(back.nodes.find(n => n.kind === 'output').tool_id, null);
});

test('recipes report tools the server does not declare instead of inventing them', () => {
  const draft = m.recipeDraft(m.RECIPES.find(r => r.id === 'salute'), []);
  assert.equal(draft.missing.length, 2);
  assert.ok(draft.nodes.filter(n => n.kind === 'tool').every(n => n.tool_id === null));
});

test('condition edges get sì first, then no, then nothing', () => {
  assert.equal(m.edgeLabelFor('condition', [], 'c'), 'sì');
  assert.equal(m.edgeLabelFor('condition', [{ source: 'c', label: 'sì' }], 'c'), 'no');
  assert.equal(m.edgeLabelFor('condition', [{ source: 'c', label: 'sì' }, { source: 'c', label: 'no' }], 'c'), undefined);
  assert.equal(m.edgeLabelFor('tool', [], 'c'), undefined);
});

test('run overlay marks running nodes and animates only the branch taken', () => {
  const run = { nodes: {
    a: { status: 'done', kind: 'trigger', label: 'A' },
    c: { status: 'done', kind: 'condition', label: 'C', outcome: 'sì', started_at: '2' },
    t: { status: 'pending', kind: 'tool', label: 'T', started_at: '3' },
  } };
  const nodes = m.overlayRun([{ id: 't', position: { x: 0, y: 0 }, data: { kind: 'tool' } }], run);
  assert.equal(nodes[0].data.status, 'running');
  const edges = m.carriedEdges([
    { id: '1', source: 'a', target: 'c' }, { id: '2', source: 'c', target: 't', label: 'sì' }, { id: '3', source: 'c', target: 'x', label: 'no' },
  ], run);
  assert.deepEqual(edges.map(e => e.className), ['flowing', 'flowing', 'muted']);
  // Nodes without a start time (never the case for the engine) go last.
  assert.deepEqual(m.traceOf(run).map(s => s.id), ['c', 't', 'a']);
});

test('schedules: sane defaults, description and next start on the chosen days', () => {
  assert.equal(m.scheduleOf({}), null);
  const s = m.scheduleOf({ schedule: { enabled: true, time: '25:99', days: [9, 0, 0, 4] } });
  assert.deepEqual(s, { enabled: true, time: '08:00', days: [0, 4], mode: 'dry_run' });
  assert.equal(m.describeSchedule(s), 'Lun, Ven alle 08:00');
  assert.equal(m.describeSchedule({ ...s, days: [0, 1, 2, 3, 4, 5, 6] }), 'Ogni giorno alle 08:00');
  const wednesday = new Date(2026, 10, 18, 9, 0); // Wed 18 Nov 2026
  const next = m.nextRun(s, wednesday);
  assert.equal(next.getDay(), 5); assert.equal(next.getHours(), 8);
  assert.equal(m.nextRun({ ...s, enabled: false }, wednesday), null);
});

test('input names are collected like the engine does', () => {
  assert.deepEqual(m.inputNames([{ data: { config: { a: '{{input.x}} e {{ input.y }}', b: { c: ['{{input.x}}', '{{nodo.campo}}'] } } } }]), ['x', 'y']);
});
