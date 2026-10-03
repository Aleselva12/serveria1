import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url);
const external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let calls=[],policy='auto';
globalThis.__panelRequest=async(path,init={})=>{
 calls.push(path);
 if(path==='/runtime')return {runs:[],pool:{}};
 if(path==='/approvals')return {generic:[],calendar:[],history:[]};
 if(path==='/permissions')return {rules:[{actor:'supervisor',action:'calculate',policy,scope:'local'}]};
 if(path==='/runtime/policies'){policy=JSON.parse(init.body).policy;return {saved:true};}
 throw Error('Unexpected path '+path);
};
let s=await readFile(new URL('../src/components/RuntimePanel.tsx',import.meta.url),'utf8');
let c=ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react')).replace('import { runtimeRequest } from "../services/runtimeApi";','const runtimeRequest=globalThis.__panelRequest;');
const Panel=(await import('data:text/javascript;base64,'+Buffer.from(c).toString('base64'))).default;
test('polling loads lightweight permissions once, skips hidden tabs and reloads after policy changes',async()=>{
 const original=globalThis.setInterval,clear=globalThis.clearInterval,doc=globalThis.document;let tick,r;
 globalThis.setInterval=f=>{tick=f;return 42;};globalThis.clearInterval=()=>{};globalThis.document={hidden:false};
 try {
  await act(async()=>{r=create(React.createElement(Panel));});
  await act(async()=>tick());
  assert.equal(calls.filter(p=>p==='/permissions').length,1);assert.ok(!calls.includes('/runtime/registry'));
  globalThis.document.hidden=true;const count=calls.length;await act(async()=>tick());assert.equal(calls.length,count);
  globalThis.document.hidden=false;
  await act(async()=>r.root.findByType('select').props.onChange({target:{value:'confirm'}}));
  assert.equal(calls.filter(p=>p==='/permissions').length,2);assert.equal(r.root.findByType('select').props.value,'confirm');
 } finally {if(r)await act(async()=>r.unmount());globalThis.setInterval=original;globalThis.clearInterval=clear;globalThis.document=doc;}
});
