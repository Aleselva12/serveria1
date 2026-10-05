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
 try {await act(async()=>{r=create(React.createElement(Programmer));});assert.equal(button(r,'Crea workspace').props.disabled,true);assert.ok(JSON.stringify(r.toJSON()).includes('Backend offline'));}
 finally {if(r)await act(async()=>r.unmount());globalThis.__programmerApi.status=original;}
});
