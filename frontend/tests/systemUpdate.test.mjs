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
  assert.match(text(r.toJSON()),/preparata, non ancora installata/);
  assert.match(text(r.toJSON()),/backup dei dati/);
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
 const release={id:'12345678-1234-1234-1234-123456789abc',kind:'prepare',status:'ready',phase:'ready',commit:'a'.repeat(40),base_commit:'b'.repeat(40)};
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

test('status lost during deployment is shown as stale, never as a live pending phase', async()=>{
 let calls=0,r;
 globalThis.__updateFetch=async()=>{
   calls++;
   if(calls>1) throw Error('proxy offline');
   return {ok:true,json:async()=>({platform:'server',available:true,active_commit:'b'.repeat(40),
      jobs:[{id:'a',kind:'apply',status:'queued',phase:'queued',commit:'a'.repeat(40)}]})};
 };
 try {
   await act(async()=>{r=create(React.createElement(Panel));});
   await act(async()=>button(r,'Aggiorna Cora').props.onClick());
   assert.match(text(r.toJSON()),/In attesa/);
   await act(async()=>button(r,'Verifica stato').props.onClick());
   assert.match(text(r.toJSON()),/Ultimo stato noto/);
   assert.match(text(r.toJSON()),/Backend temporaneamente non raggiungibile/);
   assert.equal(button(r,'Prepara aggiornamento da GitHub').props.disabled,true);
 } finally {if(r)await act(async()=>r.unmount());}
});

test('dedicated Updates page starts open and keeps old release un-installable', async()=>{
 let r;
 const old={id:'old',kind:'prepare',status:'ready',phase:'ready',commit:'a'.repeat(40),base_commit:'c'.repeat(40)};
 globalThis.__updateFetch=async()=>({ok:true,json:async()=>({
   platform:'server',available:true,active_commit:'b'.repeat(40),jobs:[old]
 })});
 try {
   await act(async()=>{r=create(React.createElement(Panel,{standalone:true}));});
   assert.match(text(r.toJSON()),/Aggiornamenti Cora/);
   assert.equal(Boolean(button(r,'Installa versione verificata')),false);
 }finally{if(r)await act(async()=>r.unmount());}
});

const serverFetch=(github,calls=[],jobs=[])=>async(path,init={})=>{
 calls.push([path,init.method||'GET',init.body]);
 if(path.endsWith('/server/github'))return {ok:true,json:async()=>github};
 return {ok:true,json:async()=>({platform:'server',available:true,active_commit:'b'.repeat(40),jobs})};
};

test('update page separates overview, installation and GitHub publication',async()=>{
 let r;
 globalThis.__updateFetch=serverFetch({available:true,configured:true,branch:'main',active_commit:'b'.repeat(40),
   github_commit:'c'.repeat(40),ahead:0,behind:3,state:'behind',pending:[]});
 try{
  await act(async()=>{r=create(React.createElement(Panel,{standalone:true}));});
  const all=text(r.toJSON());
  assert.match(all,/Panoramica/);assert.match(all,/Preparazione e installazione/);
  assert.match(all,/Invia modifiche a GitHub/);
  assert.match(all,/bbbbbbbbbbbb/);assert.match(all,/cccccccccccc/);
  assert.match(all,/indietro di 3 commit/);
  assert.match(all,/Nessuna modifica del server da inviare/);
  assert.equal(button(r,'Prepara aggiornamento da GitHub').props.disabled,false);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('divergence blocks the update with a clear message',async()=>{
 let r;
 globalThis.__updateFetch=serverFetch({available:true,configured:true,github_commit:'c'.repeat(40),ahead:1,behind:2,state:'diverged',pending:[]});
 try{
  await act(async()=>{r=create(React.createElement(Panel,{standalone:true}));});
  assert.match(text(r.toJSON()),/divergono/);
  assert.match(text(r.toJSON()),/finché la pull request/);
  assert.equal(button(r,'Prepara aggiornamento da GitHub').props.disabled,true);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('server commits are published only after confirmation and then offer the compare link',async()=>{
 const oldWindow=globalThis.window;let r,calls=[],answer=false;
 globalThis.window={confirm:()=>answer};
 const item={release_id:'12345678-1234-1234-1234-123456789abc',workspace_id:'w1',commit:'d'.repeat(40),status:'applied',active:true,published:null};
 let github={available:true,configured:true,github_commit:'c'.repeat(40),ahead:1,behind:0,state:'ahead',pending:[item]};
 globalThis.__updateFetch=async(...args)=>serverFetch(github,calls)(...args);
 try{
  await act(async()=>{r=create(React.createElement(Panel,{standalone:true}));});
  assert.match(text(r.toJSON()),/avanti di 1 commit/);
  assert.equal(r.root.findAllByType('a').length,0);
  await act(async()=>button(r,'Invia a GitHub').props.onClick());
  assert.equal(calls.filter(c=>c[1]==='POST').length,0);
  answer=true;
  await act(async()=>button(r,'Invia a GitHub').props.onClick());
  const post=calls.filter(c=>c[1]==='POST');
  assert.equal(post.length,1);assert.equal(post[0][0],'/backend/api/v1/system/update/server/publish');
  assert.deepEqual(JSON.parse(post[0][2]),{release_id:item.release_id,expected_commit:item.commit});
  github={...github,pending:[{...item,published:{branch:'cora/w1',compare_url:'https://github.com/o/r/compare/main...cora%2Fw1?expand=1'}}]};
  await act(async()=>button(r,'Controlla GitHub').props.onClick());
  const link=r.root.findAllByType('a').find(a=>text(a).includes('Apri PR su GitHub'));
  assert.equal(link.props.href,'https://github.com/o/r/compare/main...cora%2Fw1?expand=1');
  assert.equal(link.props.rel,'noopener noreferrer');
 }finally{globalThis.window=oldWindow;if(r)await act(async()=>r.unmount());}
});

test('shows real dependency transitions and archives a topic through the updater API', async () => {
  const active = "a".repeat(40);
  const upstream = "b".repeat(40);
  const dependency = {ecosystem: 'npm', name: 'library', installed: '1.8.0', available: '2.0.0', change: 'major'};
  const topic = {...dependency, id: 'topic-id', discussed: false};
  let r, archived = false;
  const calls = [];
  globalThis.__updateFetch = async (path, init = {}) => {
    calls.push([path, init.method]);
    let data;
    if (path.endsWith('/server/github')) data = {state: 'behind', behind: 1, github_commit: upstream};
    else if (path.includes('/server/dependencies')) data = {
      installed_commit: active, available_commit: path.includes('?commit=') ? upstream : null, dependencies: [dependency],
    };
    else if (path.endsWith('/dependency-topics/topic-id')) {
      archived = true;
      data = {...topic, discussed: true};
    } else if (path.endsWith('/dependency-topics')) data = {topics: [{...topic, discussed: archived}]};
    else data = {platform: 'server', available: true, active_commit: active,
      components: {commit: active, aligned: true, components: []}, jobs: []};
    return {ok: true, json: async () => data};
  };
  try {
    await act(async () => { r = create(React.createElement(Panel, {standalone: true})); });
    assert.match(text(r.toJSON()), /Componenti allineati al commit installato/);
    assert.match(text(r.toJSON()), /Major · verifica compatibilità/);
    assert.match(text(r.toJSON()), /Topic da discutere \(1\)/);
    assert.ok(calls.some(([path]) => path.endsWith('/dependencies?commit=' + upstream)));
    await act(async () => button(r, 'Segna come discusso').props.onClick());
    assert.ok(calls.some(([path, method]) => path.endsWith('/dependency-topics/topic-id') && method === 'POST'));
    assert.match(text(r.toJSON()), /Topic da discutere \(0\)/);
    assert.equal(button(r, 'Segna come discusso'), undefined);
  } finally {
    if (r) await act(async () => r.unmount());
  }
});
