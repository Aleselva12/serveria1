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
const source = await readFile(new URL('../src/services/useConversations.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
  .replace('from "react"', 'from ' + JSON.stringify(pathToFileURL(require.resolve('react')).href))
  .replace('import { api } from "./api";', 'const api=globalThis.__conversationTestApi;');
let list, messages, state;
globalThis.__conversationTestApi = {
  conversations: () => list(), conversationMessages: id => messages(id),
};
const { useConversations } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const conversation = id => ({ id, title: 'Saved ' + id });
const message = (id, content) => ({
  id: content, conversation_id: id, role: 'user', content, created_at: '2026-10-02T12:00:00Z',
});
function View({ connected = true, sending = false }) {
  state = useConversations(connected, sending);
  return null;
}
async function mount() {
  let renderer;
  await act(async () => { renderer = create(React.createElement(View)); });
  return renderer;
}
async function unmount(renderer) { await act(async () => renderer.unmount()); }

test('empty database leaves one usable unsaved chat', async () => {
  list = async () => []; messages = async () => [];
  const r = await mount();
  assert.equal(state.chats.length, 1);
  assert.equal(state.currentChat.persisted, false);
  assert.equal(state.messagesLoading, false);
  await unmount(r);
});
test('restart restores sidebar, canonical messages and the same thread', async () => {
  list = async () => [conversation('A'), conversation('B')];
  messages = async id => [message(id, 'from ' + id)];
  let r = await mount();
  assert.equal(state.currentChat.threadId, 'A');
  assert.equal(state.currentChat.messages[0].conversationId, 'A');
  await act(async () => state.selectChat('B'));
  assert.equal(state.currentChat.messages[0].content, 'from B');
  await unmount(r); r = await mount();
  assert.equal(state.chats.length, 2);
  assert.equal(state.currentChat.messages[0].content, 'from A');
  await unmount(r);
});
test('late messages from an earlier selection cannot replace the selected chat', async () => {
  list = async () => [conversation('A'), conversation('B')];
  messages = async id => [message(id, 'initial')];
  const r = await mount();
  let finishA, finishB;
  messages = id => new Promise(resolve => { if (id === 'A') finishA = resolve; else finishB = resolve; });
  await act(async () => state.selectChat('A'));
  await act(async () => state.selectChat('B'));
  await act(async () => finishA([message('A', 'stale')]));
  assert.equal(state.currentChat.id, 'B');
  assert.equal(state.messagesLoading, true);
  await act(async () => finishB([message('B', 'selected')]));
  assert.equal(state.currentChat.messages[0].content, 'selected');
  await unmount(r);
});
test('a new unsent chat survives history refresh and remains selected', async () => {
  list = async () => [conversation('A')]; messages = async () => [];
  const r = await mount();
  await act(async () => state.newChat());
  const draft = state.currentChat.id;
  await act(async () => state.refreshHistory());
  assert.equal(state.currentChat.id, draft);
  assert.equal(state.currentChat.persisted, false);
  assert.equal(state.chats.length, 2);
  await unmount(r);
});
test('read errors stay visible and retry reloads the same conversation', async () => {
  list = async () => [conversation('A')];
  let calls = 0;
  messages = async () => { ++calls; throw new Error('DB offline'); };
  const r = await mount();
  assert.equal(state.messagesError, 'DB offline');
  assert.equal(calls, 1);
  messages = async id => [message(id, 'recovered')];
  await act(async () => state.selectChat('A'));
  assert.equal(state.messagesError, '');
  assert.equal(state.currentChat.messages[0].content, 'recovered');
  await unmount(r);
});
test('list failure preserves previously loaded chats', async () => {
  list = async () => [conversation('A')]; messages = async () => [];
  const r = await mount();
  list = async () => { throw new Error('History offline'); };
  await act(async () => state.refreshHistory());
  assert.equal(state.historyError, 'History offline');
  assert.equal(state.currentChat.id, 'A');
  assert.equal(state.historyLoading, false);
  await unmount(r);
});
test('after a send, refresh reconciles a persisted draft without duplicating messages', async () => {
  list = async () => []; messages = async () => [];
  const r = await mount();
  const id = state.currentChat.id;
  await act(async () => r.update(React.createElement(View, { sending: true })));
  await act(async () => state.setChats(chats => chats.map(c => ({ ...c,
    messages: [{ id: 'optimistic', conversationId: id, role: 'user', content: 'hello', createdAt: '2026-10-02T12:00:00Z' }],
  }))));
  list = async () => [{ ...conversation(id), title: 'hello' }];
  messages = async () => [message(id, 'hello'), { ...message(id, 'reply'), role: 'assistant' }];
  await act(async () => {
    r.update(React.createElement(View, { sending: false }));
    await state.refreshHistory();
  });
  assert.equal(state.chats.length, 1);
  assert.equal(state.currentChat.title, 'hello');
  assert.equal(state.currentChat.threadId, id);
  assert.equal(state.currentChat.persisted, true);
  assert.deepEqual(state.currentChat.messages.map(m => m.content), ['hello', 'reply']);
  await unmount(r);
});
