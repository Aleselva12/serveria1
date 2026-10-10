import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const source = (await readFile(new URL('../src/services/runtimeApi.ts', import.meta.url), 'utf8'))
  .replace('import { apiBaseUrl } from "./api";', 'const apiBaseUrl = "/backend";')
  .replace('import { authenticatedFetch } from "./transport";', 'const authenticatedFetch = (...args) => globalThis.fetch(...args);');
const compiled = ts.transpileModule(source, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {streamRun} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('library progress is delivered separately from answer text', async () => {
  const original = globalThis.fetch;
  const activity = {action:'search',path:'clienti',query:'Rossi'};
  const frames = [
    'data: ' + JSON.stringify({type:'library.activity',payload:activity}),
    'data: ' + JSON.stringify({type:'chat.delta',payload:{text:'Risultato'}}),
    'event: result\ndata: ' + JSON.stringify({status:'completed',result:{response:'Risultato',thread_id:'t'}}),
  ].join('\n\n') + '\n\n';
  globalThis.fetch = async () => new Response(frames);
  try {
    const activities = [], texts = [];
    const result = await streamRun({id:'run'}, text => texts.push(text), () => {}, undefined, item => activities.push(item));
    assert.deepEqual(activities, [activity]);
    assert.deepEqual(texts, ['Risultato']);
    assert.equal(result.response, 'Risultato');
  } finally { globalThis.fetch = original; }
});
