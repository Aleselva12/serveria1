import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const url=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const service=url('export const runtimeRequest=(...args)=>globalThis.__consultationRequest(...args);');
let source=await readFile(new URL('../src/components/ThinkingPanel.tsx',import.meta.url),'utf8');
source=source.replace('"../services/runtimeApi"',JSON.stringify(service));
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
code=code.replaceAll('"react"',JSON.stringify(pathToFileURL(require.resolve('react')).href)).replaceAll('"react/jsx-runtime"',JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href));
const {default:Panel}=await import(url(code));
const item=(id,name)=>({id,name,kind:'file',status:'read',run_id:'run-example',created_at:'2026-10-18T12:00:00Z'});
const empty={items:[],next_before:null,write_failures_since_restart:0};
const props={value:{text:'',truncated:false},threadId:'conversation-a'};

test('persisted evidence is visible without model thinking and loads older pages',async()=>{
 const requests=[];
 globalThis.__consultationRequest=async path=>{requests.push(path);return requests.length===1?{...empty,items:[item(3,'new.txt')],next_before:3}:{...empty,items:[item(2,'old.txt')]};};
 let r;
 await act(async()=>{r=create(React.createElement(Panel,props));});
 assert.ok(JSON.stringify(r.toJSON()).includes('new.txt'));
 await act(async()=>r.root.findByType('button').props.onClick());
 assert.ok(requests[1].endsWith('?before=3'));
 assert.ok(JSON.stringify(r.toJSON()).includes('old.txt'));
 assert.ok(JSON.stringify(r.toJSON()).includes('new.txt'));
 await act(async()=>r.unmount());
});

test('late response from another conversation cannot expose its file names',async()=>{
 let resolveOld;
 globalThis.__consultationRequest=path=>path.endsWith('conversation-a')?new Promise(resolve=>{resolveOld=resolve;}):Promise.resolve({...empty,items:[item(5,'current.txt')]});
 let r;
 await act(async()=>{r=create(React.createElement(Panel,props));});
 await act(async()=>r.update(React.createElement(Panel,{...props,threadId:'conversation-b'})));
 await act(async()=>resolveOld({...empty,items:[item(4,'other-private.txt')]}));
 assert.ok(JSON.stringify(r.toJSON()).includes('current.txt'));
 assert.ok(!JSON.stringify(r.toJSON()).includes('other-private.txt'));
 await act(async()=>r.unmount());
});

test('history failure is explicit and model output remains separate',async()=>{
 globalThis.__consultationRequest=async()=>{throw Error('offline');};
 let r;
 await act(async()=>{r=create(React.createElement(Panel,{...props,value:{text:'model text',truncated:false}}));});
 assert.equal(r.root.findByProps({role:'alert'}).children[0],'Storico consultazioni non disponibile.');
 assert.ok(JSON.stringify(r.toJSON()).includes('model text'));
 await act(async()=>r.unmount());
});
