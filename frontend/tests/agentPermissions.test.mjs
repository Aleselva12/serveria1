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
let policy, calls, failPermissions;
globalThis.__permRequest = async (path, init = {}) => {
  calls.push([path, init.method || 'GET', init.body ? JSON.parse(init.body) : null]);
  if (path === '/permissions') {
    if (failPermissions) throw Error('Permessi non disponibili');
    return {rules: [{actor: 'supervisor', action: 'library.write', policy, scope: 'Libreria IA'}]};
  }
  if (path === '/runtime/policies') { policy = JSON.parse(init.body).policy; return {saved: true}; }
  throw Error('Unexpected ' + path);
};
const source = (await readFile(new URL('../src/components/AgentPermissions.tsx', import.meta.url), 'utf8'))
  .replace('import { runtimeRequest } from "../services/runtimeApi";', 'const runtimeRequest=globalThis.__permRequest;');
const compiled = ts.transpileModule('import React from "react";\n' + source, {compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}})
  .outputText.replaceAll('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href));
const {default: AgentPermissions} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const select = view => view.root.findAllByType('select')[0];

test('agent permissions are loaded once and a change is saved, then reloaded', async () => {
  policy = 'auto'; calls = []; failPermissions = false;
  let view;
  await act(async () => { view = create(React.createElement(AgentPermissions)); });
  assert.equal(select(view).props['aria-label'], 'supervisor library.write');
  assert.equal(select(view).props.value, 'auto');
  await act(async () => select(view).props.onChange({target: {value: 'confirm'}}));
  assert.deepEqual(calls[1], ['/runtime/policies', 'PUT', {actor: 'supervisor', action: 'library.write', policy: 'confirm'}]);
  assert.equal(calls.filter(c => c[0] === '/permissions').length, 2);
  assert.equal(select(view).props.value, 'confirm');
  assert.match(JSON.stringify(view.toJSON()), /Notifiche › Da decidere/);
  await act(async () => view.unmount());
});

test('a failed load is shown instead of an empty list', async () => {
  calls = []; failPermissions = true;
  let view;
  await act(async () => { view = create(React.createElement(AgentPermissions)); });
  assert.match(JSON.stringify(view.toJSON()), /Permessi non disponibili/);
  assert.equal(view.root.findAllByType('select').length, 0);
  await act(async () => view.unmount());
});
