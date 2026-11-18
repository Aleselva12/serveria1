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
const load = async (file, replacements = []) => {
  let source = await readFile(new URL('../src/components/' + file, import.meta.url), 'utf8');
  for (const [a, b] of replacements) source = source.replace(a, b);
  const out = ts.transpileModule('import React from "react";\n' + source, {compilerOptions: {jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}})
    .outputText.replaceAll('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href));
  return import('data:text/javascript;base64,' + Buffer.from(out).toString('base64'));
};

const tabs = await load('settingsTabs.ts');

test('settings sub-pages are addressed as #settings/<id> and unknown ids fall back', () => {
  assert.deepEqual(tabs.splitHash('#settings/permessi'), ['settings', 'permessi']);
  assert.deepEqual(tabs.splitHash('#settings'), ['settings', undefined]);
  assert.deepEqual(tabs.splitHash(''), ['', undefined]);
  assert.equal(tabs.isSettingsTab('notifiche'), true);
  assert.equal(tabs.isSettingsTab('nope'), false);
  assert.equal(tabs.isSettingsTab(undefined), false);
  assert.deepEqual(tabs.SETTINGS_TABS.map(t => t.label),
    ['Generale', 'Modelli IA', 'Memoria', 'Account collegati', 'Notifiche', 'Accesso e permessi', 'Libreria IA']);
});

let mail, calendar;
globalThis.__accounts = {
  mailRequest: async path => { assert.equal(path, '/accounts'); if (mail instanceof Error) throw mail; return mail; },
  calendarApi: {provider: async token => { assert.equal(token, ''); if (calendar instanceof Error) throw calendar; return calendar; }},
};
const {default: AccountsSettings} = await load('AccountsSettings.tsx', [
  ['import { ArrowRight } from "lucide-react";', 'const ArrowRight=()=>null;'],
  ['import { mailRequest } from "../services/mailApi";', 'const {mailRequest}=globalThis.__accounts;'],
  ['import { calendarApi, type CalendarProviderStatus } from "../services/calendarApi";', 'const {calendarApi}=globalThis.__accounts;'],
]);

test('linked accounts show Gmail and Google Calendar state and send reconnection to their pages', async () => {
  mail = {accounts: [{id: 'a', email: 'uno@example.com', connected: true}, {id: 'b', email: 'due@example.com', connected: false}], webAuth: {available: true}};
  calendar = {connected: true, provider: 'google', reauthorizationRequired: true};
  let opened = [], view;
  await act(async () => { view = create(React.createElement(AccountsSettings, {onOpenMail: () => opened.push('mail'), onOpenCalendar: () => opened.push('calendar')})); });
  const text = JSON.stringify(view.toJSON());
  assert.match(text, /uno@example.com/);
  assert.match(text, /due@example.com"," · ","Da collegare/);
  assert.match(text, /"1\/2"|1\/2/);
  assert.match(text, /Autorizzazione da rinnovare/);
  assert.match(text, /Da controllare/);
  for (const b of view.root.findAllByType('button')) await act(async () => b.props.onClick());
  assert.deepEqual(opened, ['mail', 'calendar']);
  await act(async () => view.unmount());
});

test('one failing service does not hide the other', async () => {
  mail = new Error('Mail non disponibile');
  calendar = {connected: true, provider: 'google', reachable: true};
  let view;
  await act(async () => { view = create(React.createElement(AccountsSettings, {onOpenMail() {}, onOpenCalendar() {}})); });
  const text = JSON.stringify(view.toJSON());
  assert.match(text, /Mail non disponibile/);
  assert.match(text, /"Collegato"/);
  assert.match(text, /"OK"/);
  await act(async () => view.unmount());
});
