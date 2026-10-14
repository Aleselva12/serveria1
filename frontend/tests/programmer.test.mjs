import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url),external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const calls=[];let writes=false;
const workspace={id:'workspace',title:'Nuovo tool',source_digest:'a'.repeat(64),file_count:1,status:'draft'};
globalThis.__programmerApi={
 status:async()=>({model:'local-coder',checks:{docker_cli:false}}),workspaces:async()=>[],
 create:async(title)=>{calls.push(['create',title]);return workspace;},files:async()=>({files:['sample.py']}),
 diff:async()=>({changes:writes?[{path:'sample.py',kind:'modified',patch:'+value = 42',truncated:false}]:[],total_changes:writes?1:0,truncated:false}),graph:async()=>({available:false}),
 file:async()=>({path:'sample.py',content:'value = 42',sha256:'hash',start_line:1,total_lines:1,truncated:false}),
 run:async(id,message,onRun,onText,onState)=>{calls.push(['run',id,message]);onRun('run-id');onText('Provvisorio');onState('running');writes=true;return {response:'Bozza creata e verificata',thread_id:id};},
};
globalThis.__programmerHistory=async id=>{calls.push(['history',id]);return [];};
globalThis.__programmerRuntime=async(path,init)=>{calls.push(['runtime',path,init]);return {};};
let source=await readFile(new URL('../src/components/Programmer.tsx',import.meta.url),'utf8');
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react')).replace(/from "lucide-react"/g,'from '+external('lucide-react'))
 .replace(/import \{[^}]*\} from "\.\.\/services\/programmerApi";/,'const programmerApi=globalThis.__programmerApi;')
 .replace(/import \{[^}]*\} from "\.\/RunControls";/, "const LengthChoice=()=>null, RunTimer=()=>null;")
 .replace(/import ThinkingPanel from "\.\/ThinkingPanel";/, "const ThinkingPanel=()=>null;")
 .replace(/import ProgrammerReleases from "\.\/ProgrammerReleases";/, "const ProgrammerReleases=()=>null;")
 .replace(/import ProgrammerArtifacts from "\.\/ProgrammerArtifacts";/, "const ProgrammerArtifacts=()=>null;")
 .replace(/import WorkspaceEditor from "\.\/WorkspaceEditor";/, "const WorkspaceEditor=()=>null;")
 .replace(/import \{ api \} from "\.\.\/services\/api";/,'const api={conversationMessages:id=>globalThis.__programmerHistory(id)};')
 .replace(/import \{ runtimeRequest \} from "\.\.\/services\/runtimeApi";/,'const runtimeRequest=(...args)=>globalThis.__programmerRuntime(...args);');
const Programmer=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=(r,text)=>r.root.findAllByType('button').find(b=>b.children.includes(text));
test('programmer creates workspace, sends to its agent and displays real changes',async()=>{
 calls.length=0;writes=false;let r;
 try {
  await act(async()=>{r=create(React.createElement(Programmer));});
  assert.equal(r.root.findByProps({'aria-label':'Invia messaggio al Copilot'}).props.disabled,true);
  await act(async()=>button(r,'Crea workspace').props.onClick());
  assert.ok(calls.some(c=>c[0]==='history'&&c[1]==='workspace'));
  await act(async()=>r.root.findByProps({'aria-label':'Messaggio al Copilot'}).props.onChange({target:{value:'Crea un tool'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Invia messaggio al Copilot'}).props.onClick());
  assert.deepEqual(calls.find(c=>c[0]==='run'),['run','workspace','Crea un tool']);
  assert.ok(JSON.stringify(r.toJSON()).includes('Bozza creata e verificata'));
  const changes=r.root.findAllByType('button').find(b=>b.children.includes(' modifiche'));
  await act(async()=>changes.props.onClick());assert.ok(JSON.stringify(r.toJSON()).includes('+value = 42'));
 } finally {if(r)await act(async()=>r.unmount());}
});
test('offline programmer reports unavailable backend and disables creation',async()=>{
 const original=globalThis.__programmerApi.status;let r;globalThis.__programmerApi.status=async()=>{throw new Error('Backend offline');};
 try {await act(async()=>{r=create(React.createElement(Programmer));});assert.equal(button(r,'Crea workspace').props.disabled,true);assert.ok(JSON.stringify(r.toJSON()).includes('Backend offline'));
  const composer=r.root.findByProps({'aria-label':'Messaggio al Copilot'});
  assert.notEqual(composer.props.disabled,true);
  await act(async()=>composer.props.onChange({target:{value:'Bozza da inviare dopo la riconnessione'}}));
  assert.equal(r.root.findByProps({'aria-label':'Messaggio al Copilot'}).props.value,'Bozza da inviare dopo la riconnessione');
  assert.equal(r.root.findByProps({'aria-label':'Invia messaggio al Copilot'}).props.disabled,true);
 }
 finally {if(r)await act(async()=>r.unmount());globalThis.__programmerApi.status=original;}
});
test('failed run keeps the prompt editable and exposes its ID without retrying',async()=>{
 const original=globalThis.__programmerApi.run;let r;calls.length=0;
 globalThis.__programmerApi.run=async(id,message,onRun)=>{calls.push(['run',id,message]);onRun('failed-run-id');throw new Error('Esecuzione failed');};
 try {
  await act(async()=>{r=create(React.createElement(Programmer));});
  await act(async()=>button(r,'Crea workspace').props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Messaggio al Copilot'}).props.onChange({target:{value:'Crea la somma'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Invia messaggio al Copilot'}).props.onClick());
  const composer=r.root.findByProps({'aria-label':'Messaggio al Copilot'});
  assert.notEqual(composer.props.disabled,true);
  assert.equal(composer.props.value,'Crea la somma');
  assert.ok(JSON.stringify(r.toJSON()).includes('failed-run-id'));
  assert.equal(calls.filter(c=>c[0]==='run').length,1);
 } finally {if(r)await act(async()=>r.unmount());globalThis.__programmerApi.run=original;}
});
test('minimal workspace cannot start inapplicable checks; generated tests enable Python checks',async()=>{
 const originalFiles=globalThis.__programmerApi.files,originalRun=globalThis.__programmerApi.run;
 let paths=['README.md','tests/__init__.py'],r;
 globalThis.__programmerApi.files=async()=>({files:paths});
 globalThis.__programmerApi.run=async()=>{paths=[...paths,'sum_numbers.py','tests/test_sum_numbers.py'];return {response:'File creati'};};
 try {
  await act(async()=>{r=create(React.createElement(Programmer));});
  await act(async()=>button(r,'Crea workspace').props.onClick());
  for(const name of ['Test Docker','Verifica TypeScript','Build frontend Docker','Costruisci mappa Graphify'])
   assert.equal(button(r,name).props.disabled,true,name);
  assert.equal(button(r,'Verifica sintassi').props.disabled,false);
  assert.ok(JSON.stringify(r.toJSON()).includes('non contiene test eseguibili'));
  await act(async()=>r.root.findByProps({'aria-label':'Messaggio al Copilot'}).props.onChange({target:{value:'Crea funzione e test'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Invia messaggio al Copilot'}).props.onClick());
  assert.equal(button(r,'Test Docker').props.disabled,false);
  assert.equal(button(r,'Build frontend Docker').props.disabled,true);
 } finally {
  if(r)await act(async()=>r.unmount());
  globalThis.__programmerApi.files=originalFiles;globalThis.__programmerApi.run=originalRun;
 }
});
