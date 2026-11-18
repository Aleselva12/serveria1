import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/systemTabs.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}}).outputText;
const tabs = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('Sistema groups health, updates, machines and technical activity', () => {
  assert.deepEqual(tabs.SYSTEM_TABS.map(t => t.label), ['Salute', 'Aggiornamenti', 'Macchine', 'Attività tecnica']);
});

test('#system/<id> opens the tab and unknown ids fall back to Salute', () => {
  assert.equal(tabs.systemTabFor('system', 'macchine'), 'macchine');
  assert.equal(tabs.systemTabFor('system', undefined), 'salute');
  assert.equal(tabs.systemTabFor('system', 'boh'), 'salute');
});

test('old addresses keep working and land on the matching Sistema tab', () => {
  assert.equal(tabs.systemTabFor('updates', undefined), 'aggiornamenti');
  assert.equal(tabs.systemTabFor('machines', undefined), 'macchine');
  assert.equal(tabs.systemTabFor('activity', 'generale'), 'attivita');
  assert.equal(tabs.systemTabFor('settings', 'notifiche'), null);
  assert.equal(tabs.systemTabFor('home', undefined), null);
});
