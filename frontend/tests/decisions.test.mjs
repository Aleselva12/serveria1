import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { create, act } from 'react-test-renderer';

const require = createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const listeners = {};
globalThis.window = {addEventListener: (name, fn) => listeners[name] = fn, removeEventListener: name => delete listeners[name]};

let state, calls;
const reset = () => {
  calls = [];
  state = {
    approvals: [{id: 'g1', kind: 'generic', actor: 'supervisor', action: 'library.write', payload: {path: 'a.docx'}, status: 'pending', contract_version: 1},
                {id: 'c1', kind: 'calendar', actor: 'calendar', action: 'create_event', payload: {title: 'Visita'}, status: 'pending'}],
    uncertain: [{id: 'op1', capability_id: 'supervisor.write', run_id: 'old', payload: {file: 'x'}, status: 'uncertain', error_type: 'ProcessInterrupted'}],
    word: [{id: 'w1', audioId: 'a1', title: 'Visita cliente', createdAt: '2026-11-18T09:00:00Z', expiresAt: '2026-11-25T09:00:00Z'}],
    results: [],
  };
};
const changed = () => listeners['cora:decisions-changed']?.();
globalThis.__decisionsApi = {
  DECISIONS_CHANGED: 'cora:decisions-changed',
  loadDecisions: async () => ({decisions: {...state, pending: state.approvals.length + state.uncertain.length + state.word.length}, errors: []}),
  resolveApproval: async (a, approve) => { calls.push(['resolve', a.kind, a.id, approve]); state.approvals = state.approvals.filter(x => x.id !== a.id); changed(); return {status: 'queued'}; },
  reviewOperation: async (id, outcome, note) => { calls.push(['review', id, outcome, note]); state.uncertain = []; changed(); return {status: 'uncertain'}; },
};
const source = (await readFile(new URL('../src/components/Decisions.tsx', import.meta.url), 'utf8'))
  .replace(/import \{ DECISIONS_CHANGED[^;]*;/, 'const {DECISIONS_CHANGED,loadDecisions,resolveApproval,reviewOperation}=globalThis.__decisionsApi;');
const compiled = ts.transpileModule('import React from "react";\n' + source, {compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}})
  .outputText.replaceAll('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href));
const {default: DecisionsPanel} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const textOf = node => typeof node === 'string' || typeof node === 'number' ? String(node)
  : Array.isArray(node) ? node.map(textOf).join('') : node?.props ? textOf(node.props.children) : '';
const text = view => JSON.stringify(view.toJSON());
const buttons = (view, label) => view.root.findAll(n => n.type === 'button' && textOf(n.props.children).includes(label));

test('approvals from agents and calendar are decided here, one at a time', async () => {
  reset();
  let view;
  await act(async () => { view = create(React.createElement(DecisionsPanel)); });
  assert.match(text(view), /Azioni da approvare/);
  assert.match(text(view), /"Calendario"," · ","create_event"/);
  await act(async () => buttons(view, 'Approva questa azione')[1].props.onClick());
  await act(async () => buttons(view, 'Rifiuta')[0].props.onClick());
  assert.deepEqual(calls, [['resolve', 'calendar', 'c1', true], ['resolve', 'generic', 'g1', false]]);
  assert.doesNotMatch(text(view), /Azioni da approvare/);
  await act(async () => view.unmount());
});

test('uncertain effects need a written verification and the review never replays the operation', async () => {
  reset();
  let view;
  await act(async () => { view = create(React.createElement(DecisionsPanel)); });
  assert.equal(buttons(view, 'Effetto verificato')[0].props.disabled, true);
  await act(async () => view.root.findAll(n => n.type === 'textarea' && n.props['aria-label'] === 'Verifica op1')[0]
    .props.onChange({target: {value: 'Controllato il file sul server'}}));
  await act(async () => buttons(view, 'Effetto verificato')[0].props.onClick());
  assert.deepEqual(calls, [['review', 'op1', 'effect_verified', 'Controllato il file sul server']]);
  assert.doesNotMatch(text(view), /Effetti da verificare/);
  await act(async () => view.unmount());
});

test('Word notes are only listed: approval happens in Audio next to the transcript', async () => {
  reset();
  let opened = 0, view;
  await act(async () => { view = create(React.createElement(DecisionsPanel, {onOpenAudio: () => opened++})); });
  assert.match(text(view), /Note Word da approvare/);
  assert.match(text(view), /Visita cliente/);
  await act(async () => buttons(view, 'Apri Audio')[0].props.onClick());
  assert.equal(opened, 1);
  assert.equal(calls.length, 0);
  state = {approvals: [], uncertain: [], word: [], results: []};
  await act(async () => changed());
  assert.match(text(view), /Niente da decidere/);
  await act(async () => view.unmount());
});
