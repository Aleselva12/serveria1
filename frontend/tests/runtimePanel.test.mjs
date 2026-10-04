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
let calls=[],policy='auto',unknownEffects=[],history=[],reviewCalls=[],telemetry=null;
globalThis.__panelRequest=async(path,init={})=>{
 calls.push(path);
 if(path.startsWith('/runtime/runs?'))return history;
 if(path.startsWith('/runtime/operations?'))return unknownEffects;
 if(path.endsWith('/review')){const decision=JSON.parse(init.body);reviewCalls.push(decision);unknownEffects=[];return {status:'uncertain',review_outcome:decision.outcome};}
 if(path==='/runtime')return {runs:[],pool:{},traces:{write_error:null,diagnostics:telemetry}};
 if(path.startsWith('/runtime/domain-events?'))return {events:[{id:'event1',sequence:1,type:'run.committed',source:'supervisor',component_run_id:'root',payload:{status:'completed'}}],next_cursor:1};
 if(path.startsWith('/runtime/diagnostics?'))return {events:[],next_before:null};
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

test('diagnostic losses are visible without turning canonical success into failure',async()=>{
 telemetry={pending:3,dropped:2,last_error:'OSError',retention_days:30,worker_alive:true};
 history=[{id:'root',status:'completed',target:'supervisor',approval_ids:[]}];
 let r;
 try {
  await act(async()=>{r=create(React.createElement(Panel));});
  assert.ok(JSON.stringify(r.toJSON()).includes('Diagnostica incompleta'));
  await act(async()=>r.root.findAllByType('button').find(b=>b.children.includes('Vedi operazioni')).props.onClick());
  assert.ok(JSON.stringify(r.toJSON()).includes('run.committed'));
  const before=calls.filter(p=>p.includes('/runtime/domain-events?')).length;
  await act(async()=>r.root.findAllByType('button').find(b=>b.children.includes('Carica eventi successivi')).props.onClick());
  assert.equal(calls.filter(p=>p.includes('/runtime/domain-events?')).length,before+1);
  assert.equal(JSON.stringify(r.toJSON()).match(/run.committed/g).length,1);
 } finally {if(r)await act(async()=>r.unmount());telemetry=null;history=[];}
});

test('uncertain effects require a recorded verification and review never replays an operation',async()=>{
 calls=[];reviewCalls=[];
 unknownEffects=[{id:'uncertain-op',capability_id:'supervisor.write',run_id:'old-run',payload:{file:'note.docx'},status:'uncertain',effect:'write',contract_version:1,error_type:'ProcessInterrupted',review_outcome:null}];
 history=[{id:'old-run',status:'interrupted',target:'supervisor',approval_ids:[]}];
 let r;
 try {
  await act(async()=>{r=create(React.createElement(Panel));});
  let button=r.root.findAllByType('button').find(b=>b.children.includes('Effetto verificato'));
  assert.equal(button.props.disabled,true);
  assert.ok(JSON.stringify(r.toJSON()).includes('esito incerto'));
  await act(async()=>r.root.findByType('textarea').props.onChange({target:{value:'Ho verificato il file sul server'}}));
  button=r.root.findAllByType('button').find(b=>b.children.includes('Effetto verificato'));
  assert.equal(button.props.disabled,false);
  await act(async()=>button.props.onClick());
  assert.deepEqual(reviewCalls,[{outcome:'effect_verified',note:'Ho verificato il file sul server'}]);
  assert.ok(!calls.some(p=>p.includes('/resolve') || p.includes('/chat')));
  assert.ok(JSON.stringify(r.toJSON()).includes('Nessun effetto da verificare'));
 } finally {if(r)await act(async()=>r.unmount());unknownEffects=[];history=[];}
});
