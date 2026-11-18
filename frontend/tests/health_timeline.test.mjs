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
const source = (await readFile(new URL('../src/tree/HealthTimeline.tsx', import.meta.url), 'utf8'))
  .replace('import { apiBaseUrl } from "../services/api";', 'const apiBaseUrl="";')
  .replace('import { authenticatedFetch } from "../services/transport";', 'const authenticatedFetch=(...a)=>globalThis.__timelineFetch(...a);');
const compiled = ts.transpileModule('import React from "react";\n' + source, {compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}})
  .outputText.replaceAll('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href));
const {default: HealthTimeline, isTimeline} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

async function render(response) {
  const urls = [];
  globalThis.__timelineFetch = async url => { urls.push(url); return response; };
  let view;
  await act(async () => { view = create(React.createElement(HealthTimeline)); });
  const text = JSON.stringify(view.toJSON());
  await act(async () => view.unmount());
  return {text, urls};
}

test('shows what is failing now and the recent transitions', async () => {
  const data = {
    failing: [{checkId: 'nextcloud_e2e', title: 'Nextcloud: raggiungibilità HTTP', since: '2026-11-17T04:10:00Z', failures: 3, notified: false}],
    history: [{id: '1', at: '2026-11-17T04:10:00Z', kind: 'failure', title: 'Errore: Nextcloud', detail: 'non raggiungibile · versione 80950be', checkId: 'nextcloud_e2e', commit: '80950be'}],
  };
  const {text, urls} = await render({ok: true, json: async () => data});
  assert.deepEqual(urls, ['/api/v1/system/health-transitions']);
  assert.match(text, /Ora in errore/);
  assert.match(text, /3 fallimenti di fila/);
  assert.match(text, /avviso non ripetuto/);
  assert.match(text, /Errore: Nextcloud/);
  assert.match(text, /versione 80950be/);
});

test('says when nothing is failing and handles an unavailable service', async () => {
  assert.match((await render({ok: true, json: async () => ({failing: [], history: []})})).text, /Nessun controllo in errore/);
  assert.match((await render({ok: false, json: async () => ({})})).text, /non disponibile/);
  assert.equal(isTimeline({failing: [], history: [{id: 1}]}), false);
});
