import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';
import React from 'react';
import { act, create } from 'react-test-renderer';
import ts from 'typescript';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const reactUrl = pathToFileURL(createRequire(import.meta.url).resolve('react')).href;
const source = await readFile(new URL('../src/components/MemoryLibrary.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React },
}).outputText
  .replace('from "react"', 'from ' + JSON.stringify(reactUrl))
  .replace('import { ApiError, api } from "../services/api";', 'const api=globalThis.libraryApi; class ApiError extends Error {}');


const text = node => node.children.map(child => typeof child === 'string' ? child : text(child)).join('');
const stamp = '2026-11-22T12:00:00Z';
const runId = '8598810d-8de6-4a82-8a9f-98f75bd1cbad';

test('a recorded failure can be opened and turned into a draft with its original source', async () => {
  let saved;
  globalThis.libraryApi = {
    memoryLibraryScopes: async () => ['global'],
    memoryLibrary: async () => [],
    memoryEvidenceRuns: async () => [{ id: runId, target: 'supervisor', status: 'failed', created_at: stamp }],
    memoryEvidence: async id => {
      assert.equal(id, runId);
      return {
        run_id: id,
        report: { kind: 'chat', target: 'supervisor', status: 'failed', created_at: stamp, error_type: 'TimeoutError' },
        messages: [{ id: 'message-1', role: 'user', content: 'Richiesta originale', created_at: stamp }],
        events: [],
      };
    },
    saveMemoryLibraryCard: async (document, identity) => {
      saved = { document, identity };
      return { id: 'card-1', ...identity, version: 1, document };
    },
  };
  const { default: MemoryLibrary } = await import(
    'data:text/javascript;base64,' + Buffer.from(`import React from "${reactUrl}";\n` + compiled).toString('base64')
  );
  let view;
  await act(async () => { view = create(React.createElement(MemoryLibrary)); });
  try {
    const field = name => view.root.findAllByType('label').find(node => text(node).startsWith(name));
    const change = (name, value, type = 'input') => act(async () =>
      field(name).findByType(type).props.onChange({ target: { value } }));
    const click = label => act(async () => view.root.findAllByType('button')
      .find(node => text(node) === label).props.onClick());
    const submit = label => act(async () => view.root.findAllByType('form')
      .find(form => form.findAllByType('button').some(node => text(node) === label))
      .props.onSubmit({ preventDefault() {} }));

    await change('ID esecuzione', runId);
    await submit('Apri esecuzione');
    assert.match(view.root.findAllByType('p').map(text).join('\n'), /failed · TimeoutError/, view.root.findAllByProps({role:'alert'}).map(text).join(' '));
    assert.ok(view.root.findAllByType('p').some(node => text(node) === 'Richiesta originale'));

    await click('Crea una scheda da questa fonte');
    await change('Chiave', 'collaudo');
    await change('Titolo', 'Collaudo');
    await change('Descrizione', 'Decisione da rivedere');
    await change('Contenuto', 'La prova è fallita per timeout.', 'textarea');
    await submit('Salva scheda');
    assert.equal(saved.document.state, 'draft');
    assert.deepEqual(saved.document.source_runs, [runId]);
    assert.deepEqual(saved.identity, { scope: 'global', slug: 'collaudo' });
  } finally {
    await act(async () => view.unmount());
  }
});
