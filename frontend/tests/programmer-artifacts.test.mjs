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
const calls=[];let rows=[];
const row={id:'component-1',title:'Example',kind:'tool',files:['generated_tools/example.py','tests/test_example.py'],dependencies:[],integration:'Review permissions',version:1,status:'draft',recorded_status:'draft',stale:false,missing_checks:['python_tests'],workspace_digest:'a'.repeat(64)};
globalThis.__artifactApi={
 components:async()=>({components:rows}),checks:async()=>({checks:[]}),
 graph:async(id,query,nodeId)=>{calls.push(['graph',id,query,nodeId]);return {status:{available:true,stale:true},nodes:[{id:'sample',label:'sample'},{id:'os',label:'os',unresolved:true}],edges:[{source:'sample',target:'os',relation:'imports',confidence:'EXTRACTED'}],total_matches:2,truncated:false};},
 register:async(id,data)=>{calls.push(['register',id,data]);rows=[{...row,...data,id:row.id}];return rows[0];},
 deliver:async(id,component)=>{calls.push(['deliver',id,component]);return {id:'delivery-1',sha256:'b'.repeat(64),missing_checks:['python_tests']};},
 transition:async(id,component,status,note)=>{calls.push(['transition',id,component,status,note]);rows=[{...component,status}];return rows[0];},
};
let source=await readFile(new URL('../src/components/ProgrammerArtifacts.tsx',import.meta.url),'utf8');
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react'))
 .replace(/import \{[^}]*\} from "\.\.\/services\/programmerApi";/,'const programmerArtifactsApi=globalThis.__artifactApi;')
 .replace(/import \{ authenticatedFetch \} from "\.\.\/services\/transport";/,'const authenticatedFetch=()=>{throw new Error("unexpected download")};')
 .replace(/import \{ apiBaseUrl \} from "\.\.\/services\/api";/,'const apiBaseUrl="";');
const Component=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=(r,text)=>r.root.findAllByType('button').find(b=>b.children.includes(text));
const set=(r,label,value)=>r.root.findByProps({'aria-label':label}).props.onChange({target:{value}});
test('component registration and delivery use selected workspace and preserve missing evidence',async()=>{
 calls.length=0;rows=[];let r;
 try{await act(async()=>{r=create(React.createElement(Component,{workspaceId:'work-1',revision:0,disabled:false}));});
 assert.equal(button(r,'Registra componente').props.disabled,true);
 await act(async()=>{set(r,'Titolo componente','Example');set(r,'File componente','generated_tools/example.py\ntests/test_example.py');set(r,'Istruzioni integrazione','Review permissions');});
 await act(async()=>button(r,'Registra componente').props.onClick());
 assert.equal(calls.find(c=>c[0]==='register')[1],'work-1');
 assert.deepEqual(calls.find(c=>c[0]==='register')[2].files,row.files);
 await act(async()=>button(r,'Prepara consegna').props.onClick());
 assert.deepEqual(calls.find(c=>c[0]==='deliver'),['deliver','work-1','component-1']);
 assert.ok(JSON.stringify(r.toJSON()).includes('python_tests'));
 assert.ok(button(r,'Scarica ZIP'));
 assert.equal(button(r,'Conferma revisione'),undefined);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('review requires a note and graph navigation keeps workspace and selected symbol',async()=>{
 calls.length=0;rows=[{...row,status:'verified',missing_checks:[]}];let r;
 try{await act(async()=>{r=create(React.createElement(Component,{workspaceId:'work-2',revision:0,disabled:false}));});
 await act(async()=>set(r,'Componente registrato','component-1'));
 assert.equal(button(r,'Conferma revisione').props.disabled,true);
 await act(async()=>set(r,'Nota stato componente','Reviewed code and test evidence'));
 await act(async()=>button(r,'Conferma revisione').props.onClick());
 const call=calls.find(c=>c[0]==='transition');assert.equal(call[1],'work-2');assert.equal(call[3],'reviewed');assert.equal(call[2].workspace_digest,row.workspace_digest);
 await act(async()=>r.root.findByProps({'aria-label':'Esplora simbolo os'}).props.onClick());
 assert.ok(calls.some(c=>c[0]==='graph'&&c[1]==='work-2'&&c[3]==='os'));
 assert.ok(JSON.stringify(r.toJSON()).includes('Mappa del baseline'));
 await act(async()=>r.update(React.createElement(Component,{workspaceId:'work-3',revision:1,disabled:false})));
 assert.equal(r.root.findByProps({'aria-label':'Titolo componente'}).props.value,'');
 assert.ok(calls.some(c=>c[0]==='graph'&&c[1]==='work-3'&&c[2]===''&&c[3]===''));
 }finally{if(r)await act(async()=>r.unmount());}
});
