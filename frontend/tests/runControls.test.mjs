import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {act,create} from 'react-test-renderer';
const require=createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;

let now = 1000, tick, cleared = 0;
const originalNow = Date.now;
Date.now = () => now;
globalThis.window = {setInterval: fn => {tick=fn;return 1;}, clearInterval: () => cleared++};
const src=await readFile(new URL('../src/components/RunControls.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(src,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from "react\/jsx-runtime"/g,'from '+JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href)).replace(/from "react"/g,'from '+JSON.stringify(pathToFileURL(require.resolve('react')).href));
const {RunTimer,LengthChoice}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('elapsed time advances while waiting and stops at completion; a new run resets',async()=>{
 let r;
 try {
  await act(async()=>{r=create(React.createElement(RunTimer,{started:1000,finished:null}));});
  now=66000;await act(async()=>tick());
  assert.ok(JSON.stringify(r.toJSON()).includes('65')===false);
  assert.deepEqual(r.root.findByProps({role:'timer'}).children,['Tempo trascorso',': ','1',':','05']);
  await act(async()=>r.update(React.createElement(RunTimer,{started:1000,finished:66000})));
  assert.ok(cleared>0);
  now=100000;await act(async()=>r.update(React.createElement(RunTimer,{started:100000,finished:null})));
  assert.deepEqual(r.root.findByProps({role:'timer'}).children,['Tempo trascorso',': ','0',':','00']);
 } finally {await act(async()=>r?.unmount());Date.now=originalNow;}
});
test('length choice passes a style and locks during an active request',async()=>{
 let r,chosen;
 await act(async()=>{r=create(React.createElement(LengthChoice,{value:'medium',disabled:false,onChange:v=>chosen=v}));});
 await act(async()=>r.root.findByType('select').props.onChange({target:{value:'long'}}));
 assert.equal(chosen,'long');
 await act(async()=>r.update(React.createElement(LengthChoice,{value:'long',disabled:true,onChange:()=>{}})));
 assert.equal(r.root.findByType('select').props.disabled,true);
 await act(async()=>r.unmount());
});
