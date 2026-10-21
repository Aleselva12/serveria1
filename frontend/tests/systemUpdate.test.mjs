import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url);
const external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let s=await readFile(new URL('../src/components/SystemUpdate.tsx',import.meta.url),'utf8');
let c=ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime'))
 .replace(/from "react"/g,'from '+external('react'))
 .replace('import { apiBaseUrl } from "../services/api";','const apiBaseUrl="/backend";')
 .replace('import { authenticatedFetch } from "../services/transport";','const authenticatedFetch=(...args)=>globalThis.__updateFetch(...args);');
const Panel=(await import('data:text/javascript;base64,'+Buffer.from(c).toString('base64'))).default;
const text=n=>typeof n==='string'?n:(n?.children||[]).map(text).join(' ');
const button=(r,label)=>r.root.findAllByType('button').find(b=>text(b).includes(label));

test('Windows preparation is explicit and ready never means installed',async()=>{
 let calls=[],status='idle',r;
 globalThis.__updateFetch=async(path,init={})=>{
  calls.push([path,init.method||'GET']);
  if(init.method==='POST')status='ready';
  return {ok:true,json:async()=>({platform:'windows',status,commit:'abc',directory:'C:/candidate'})};
 };
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  assert.equal(calls.length,0);
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  assert.equal(calls.length,1); assert.equal(r.root.findAllByType('a').length,0);
  await act(async()=>button(r,'Prepara aggiornamento Windows').props.onClick());
  assert.equal(calls.filter(c=>c[1]==='POST').length,1);
  assert.match(text(r.toJSON()),/preparato, non installato/);
  assert.match(text(r.toJSON()),/backup PostgreSQL/);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('Debian shows availability and requires explicit installation',async()=>{
 let r;
 globalThis.__updateFetch=async(path,init={})=>({
   ok:true,
   json:async()=>({platform:'server',available:false,reason:'Updater non configurato',jobs:[]})
 });
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  assert.equal(Boolean(button(r,'Prepara aggiornamento Windows')),false);
  assert.equal(Boolean(button(r,'Prepara aggiornamento da GitHub')),false);
  assert.equal(r.root.findAllByType('a').length,0);
  assert.match(text(r.toJSON()),/Updater non configurato/);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('Debian prepares from GitHub only on click and installs only a verified job with confirmation',async()=>{
 const oldConfirm=globalThis.window;
 let r, calls=[];
 globalThis.window={confirm:()=>false};
 const release={id:'12345678-1234-1234-1234-123456789abc',kind:'prepare',status:'ready',phase:'ready',commit:'a'.repeat(40)};
 globalThis.__updateFetch=async(path,init={})=>{
   calls.push([path,init.method||'GET']);
   return {ok:true,json:async()=>({platform:'server',available:true,active_commit:'b'.repeat(40),jobs:[release]})};
 };
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  assert.equal(calls.length,0);
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  assert.equal(calls.filter(x=>x[1]==='POST').length,0);
  assert.ok(button(r,'Prepara aggiornamento da GitHub'));
  assert.ok(button(r,'Installa versione verificata'));
  await act(async()=>button(r,'Installa versione verificata').props.onClick());
  assert.equal(calls.filter(x=>x[1]==='POST').length,0);
  await act(async()=>button(r,'Prepara aggiornamento da GitHub').props.onClick());
  assert.equal(calls.filter(x=>x[1]==='POST').length,1);
  assert.equal(calls.find(x=>x[1]==='POST')[0],'/backend/api/v1/system/update/server/prepare');
 }finally{globalThis.window=oldConfirm;if(r)await act(async()=>r.unmount());}
});

test('an uncertain POST is never repeated automatically and remains visible',async()=>{
 let posts=0,r;
 globalThis.__updateFetch=async(path,init={})=>{
  if(init.method==='POST'){posts++;throw Error('offline');}
  return {ok:true,json:async()=>({platform:'windows',status:'idle'})};
 };
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  await act(async()=>button(r,'Prepara aggiornamento Windows').props.onClick());
  assert.equal(posts,1);assert.match(text(r.toJSON()),/offline/);
 }finally{if(r)await act(async()=>r.unmount());}
});
