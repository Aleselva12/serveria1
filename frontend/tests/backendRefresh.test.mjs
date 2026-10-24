import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url), external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const windowMock=new EventTarget(); windowMock.setInterval=()=>0; globalThis.window=windowMock;
let resolveFirst,calls=0;
globalThis.__backendApi={health:()=>{calls++;return calls===1?new Promise(resolve=>{resolveFirst=resolve;}):Promise.resolve({model:'new-model'});},registry:async()=>({components:[]})};
const source=await readFile(new URL('../src/services/useBackend.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from "react"/g,'from '+external('react')).replace('import { api } from "./api";','const api=globalThis.__backendApi;');
const {useBackend}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
let state;function Driver(){state=useBackend();return React.createElement('p',null,state.health?.model||'loading');}
test('configuration change queues a fresh health read even during a pending request',async()=>{
 let r;await act(async()=>{r=create(React.createElement(Driver));});
 await act(async()=>windowMock.dispatchEvent(new Event('cora:model-config-changed')));
 assert.equal(calls,1);
 await act(async()=>{resolveFirst({model:'old-model'});await new Promise(resolve=>setImmediate(resolve));});
 assert.equal(calls,2);assert.equal(state.health.model,'new-model');
 await act(async()=>r.unmount());
});
