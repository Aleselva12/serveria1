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
const source = (await readFile(new URL('../src/components/Notifications.tsx', import.meta.url), 'utf8'))
  .replace('import { Bell, Check, X } from "lucide-react";', 'const Bell=()=>null, Check=()=>null, X=()=>null;')
  .replace(/import \{ INBOX_CHANGED[^;]*;/, 'const {INBOX_CHANGED,loadInbox,markAllSeen,markSeen}=globalThis.__inbox;')
  .replace('import "./notifications.css";', '');
const compiled = ts.transpileModule('import React from "react";\n' + source, {compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}})
  .outputText.replaceAll('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href));

const item = (id, seenAt = null) => ({id, createdAt: '2026-11-17T04:10:00Z', source: 'health', kind: 'failure', severity: 'error',
  title: 'Errore: ' + id, body: 'dettaglio', url: '/#notifications', ref: id, commit: 'abc', seenAt});
let store;
const listeners = {};
globalThis.window = {addEventListener: (name, fn) => listeners[name] = fn, removeEventListener: name => delete listeners[name],
  dispatchEvent: event => listeners[event.type]?.()};
globalThis.__inbox = {
  INBOX_CHANGED: 'cora:inbox-changed',
  loadInbox: async includeSeen => ({items: store.filter(i => includeSeen || !i.seenAt), unseen: store.filter(i => !i.seenAt).length}),
  markSeen: async id => { store = store.map(i => i.id === id ? {...i, seenAt: 'now'} : i); listeners['cora:inbox-changed']?.(); },
  markAllSeen: async () => { store = store.map(i => ({...i, seenAt: 'now'})); listeners['cora:inbox-changed']?.(); },
};
const {default: NotificationsPage, HomeNotifications} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const text = view => JSON.stringify(view.toJSON());
const textOf = node => typeof node === 'string' || typeof node === 'number' ? String(node)
  : Array.isArray(node) ? node.map(textOf).join('') : node?.props ? textOf(node.props.children) : '';
const button = (view, label) => view.root.findAll(n => n.type === 'button' && textOf(n.props.children).includes(label))[0];

test('Home window shows unseen notifications until they are marked as seen', async () => {
  store = [item('a'), item('b'), item('c'), item('d')];
  let opened = 0, view;
  await act(async () => { view = create(React.createElement(HomeNotifications, {onOpenAll: () => opened++})); });
  assert.match(text(view), /Errore: a/);
  assert.doesNotMatch(text(view), /Errore: d/);  // at most three in the small window
  assert.match(text(view), /Tutte le notifiche/);
  await act(async () => button(view, 'Tutte le notifiche').props.onClick());
  assert.equal(opened, 1);
  await act(async () => view.root.findAll(n => n.type === 'button' && n.props['aria-label'] === 'Segna come vista: Errore: a')[0].props.onClick());
  assert.doesNotMatch(text(view), /Errore: a/);
  await act(async () => button(view, 'Segna tutte viste').props.onClick());
  assert.equal(view.toJSON(), null);
  await act(async () => view.unmount());
});

test('closing the Home window hides it without marking anything as seen', async () => {
  store = [item('a')];
  let view;
  await act(async () => { view = create(React.createElement(HomeNotifications, {onOpenAll() {}})); });
  await act(async () => view.root.findAll(n => n.props['aria-label'] === 'Chiudi per ora')[0].props.onClick());
  assert.equal(view.toJSON(), null);
  assert.equal(store[0].seenAt, null);
  await act(async () => view.unmount());
});

test('Notifiche page lists unseen ones and can include the seen history', async () => {
  store = [item('a'), item('old', '2026-11-16T10:00:00Z')];
  let view;
  await act(async () => { view = create(React.createElement(NotificationsPage)); });
  assert.match(text(view), /1 da vedere/);
  assert.doesNotMatch(text(view), /Errore: old/);
  await act(async () => view.root.findByType('input').props.onChange({target: {checked: true}}));
  assert.match(text(view), /Errore: old/);
  await act(async () => button(view, 'Segna tutte viste').props.onClick());
  assert.match(text(view), /Tutto visto/);
  await act(async () => view.unmount());
});
