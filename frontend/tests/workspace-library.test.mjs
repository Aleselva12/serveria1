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
const calls=[];
globalThis.__workspaceLibraryApi={organize:async(id,changes)=>{calls.push([id,changes]);return {...rows.find(r=>r.id===id),...changes};}};
const rows=[{id:'work',title:'My work',created_at:'2026-11-04T12:00:00Z',mode:'git'},
 {id:'update',title:'Aggiornamento Cora dal branch main',created_at:'2026-11-04T13:00:00Z',mode:'git'},
 {id:'old',title:'Old experiment',created_at:'2026-11-03T12:00:00Z',archived:true}];
let source=await readFile(new URL('../src/components/WorkspaceLibrary.tsx',import.meta.url),'utf8');
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react'))
 .replace(/from "lucide-react"/g,'from '+external('lucide-react'))
 .replace(/import \{[^}]*\} from "\.\.\/services\/programmerApi";/,'const programmerApi=globalThis.__workspaceLibraryApi;');
const Library=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=(r,text)=>r.root.findAllByType('button').find(b=>b.children.includes(text));
test('updates and archived work stay separate, with search and explicit workspace selection',async()=>{
 let r;const selected=[];
 try{await act(async()=>{r=create(React.createElement(Library,{rows,selected:'work',disabled:false,onSelect:id=>selected.push(id),onUpdate:()=>{}}));});
 const visibleTitles=()=>r.root.findAllByProps({className:'workspace-row'}).map(b=>b.findByType('strong').children[0]);
 assert.deepEqual(visibleTitles(),['My work']);
 await act(async()=>button(r,'Aggiornamenti').props.onClick());
 assert.deepEqual(visibleTitles(),['Aggiornamento Cora dal branch main']);
 await act(async()=>r.root.findByProps({className:'workspace-row'}).props.onClick());
 assert.deepEqual(selected,['update']);
 await act(async()=>button(r,'Archivio').props.onClick());assert.deepEqual(visibleTitles(),['Old experiment']);
 await act(async()=>r.root.findByProps({'aria-label':'Cerca workspace'}).props.onChange({target:{value:'missing'}}));
 assert.deepEqual(visibleTitles(),[]);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('archive and rename persist through the API and failures stay visible',async()=>{
 let r;const updated=[];calls.length=0;
 try{await act(async()=>{r=create(React.createElement(Library,{rows,selected:'work',disabled:false,onSelect:()=>{},onUpdate:row=>updated.push(row)}));});
 await act(async()=>r.root.findByProps({'aria-label':'Rinomina workspace'}).props.onChange({target:{value:'New name'}}));
 await act(async()=>button(r,'Salva nome').props.onClick());
 assert.deepEqual(calls[0],['work',{title:'New name'}]);
 await act(async()=>button(r,'Archivia lavoro').props.onClick());
 assert.deepEqual(calls[1],['work',{archived:true}]);
 assert.equal(updated[1].archived,true);
 const original=globalThis.__workspaceLibraryApi.organize;
 try{globalThis.__workspaceLibraryApi.organize=async()=>{throw new Error('Connection interrupted');};
 await act(async()=>button(r,'Archivia lavoro').props.onClick());
 assert.ok(JSON.stringify(r.root.findByProps({role:'alert'}).children).includes('Connection interrupted'));
 }finally{globalThis.__workspaceLibraryApi.organize=original;}
 }finally{if(r)await act(async()=>r.unmount());}
});
