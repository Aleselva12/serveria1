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
const external = name => JSON.stringify(pathToFileURL(require.resolve(name)).href);
async function compile(file, replacements = []) {
  let code = ts.transpileModule(await readFile(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText.replace(/from "react\/jsx-runtime"/g, 'from ' + external('react/jsx-runtime'))
    .replace(/from "react"/g, 'from ' + external('react'))
    .replace(/from "lucide-react"/g, 'from ' + external('lucide-react'));
  for (const [from, to] of replacements) code = code.replace(from, to);
  return (await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))).default;
}
const entry = (id, status, group) => ({ id, name: id, status, group, kind: status === 'planned' ? 'planned' : 'tool', description: id + ' description', agents: status === 'connected' ? ['Cora'] : [], source: 'test', parameters: [], detail: 'structural' });
const fixture = { entries: [entry('calculator', 'connected', 'Sistema'), entry('upload', 'unconnected', 'File'), entry('calendar', 'planned', 'Calendario')], errors: [], scope: 'Test inventory' };
let response = async () => fixture;
globalThis.__toolsApi = { toolInventory: () => response() };
const Tools = await compile('../src/components/ArchitectureTools.tsx', [
  ['import { api } from "../services/api";', 'const api = globalThis.__toolsApi;'],
  ['import "./architecture-tools.css";', ''],
]);
globalThis.__Tools = Tools;
const Architecture = await compile('../src/components/Architecture.tsx', [
  ['import ArchitectureRuntime from "./ArchitectureRuntime";', 'const ArchitectureRuntime = () => null;'],
  ['import ArchitectureTools from "./ArchitectureTools";', 'const ArchitectureTools = globalThis.__Tools;'],
  ['import ConnectionNotice from "./ConnectionNotice";', 'const ConnectionNotice = () => null;'],
]);

test('Tools subpage remains reachable without the agents registry', async () => {
  let r;
  await act(async () => { r = create(React.createElement(Architecture, { registry: null, health: null, selectedNode: '', onSelect: () => {} })); });
  const tabs = r.root.findAllByType('button');
  await act(async () => tabs.find(b => b.children.includes('Tools')).props.onClick());
  assert.equal(r.root.findAllByProps({className: 'tool-node connected selected'}).length, 1);
  await act(async () => r.unmount());
});
test('search and status filters update nodes and function list together', async () => {
  let r;
  await act(async () => { r = create(React.createElement(Tools)); });
  assert.equal(r.root.findAllByProps({className: 'tools-list-row '}).length + r.root.findAllByProps({className: 'tools-list-row selected'}).length, 3);
  await act(async () => r.root.findByProps({'aria-label': 'Filtra per stato'}).props.onChange({target: {value: 'planned'}}));
  assert.equal(r.root.findAllByProps({className: 'tool-node planned selected'}).length, 1);
  assert.equal(r.root.findAllByProps({className: 'tools-list-row selected'}).length, 1);
  await act(async () => r.root.findByProps({'aria-label': 'Cerca tools'}).props.onChange({target: {value: 'absent'}}));
  assert.equal(r.root.findAllByProps({className: 'tool-node planned selected'}).length, 0);
  assert.ok(JSON.stringify(r.toJSON()).includes('Nessuno strumento corrisponde'));
  await act(async () => r.unmount());
});
test('inventory failure stays explicit and refresh can recover', async () => {
  response = async () => { throw new Error('Backend offline'); };
  let r;
  await act(async () => { r = create(React.createElement(Tools)); });
  assert.equal(r.root.findByProps({role: 'alert'}).children[0], 'Backend offline');
  response = async () => fixture;
  await act(async () => r.root.findAllByType('button').find(b => b.children.includes(' Aggiorna')).props.onClick());
  assert.equal(r.root.findAllByProps({role: 'alert'}).length, 0);
  await act(async () => r.unmount());
});
