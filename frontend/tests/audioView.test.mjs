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
const service=url('export const mediaRequest=(...args)=>globalThis.__audioTest.request(...args); export const downloadMedia=()=>Promise.resolve();');
const runtime=url('export const runtimeRequest=()=>Promise.resolve();');
const base=url('export const apiBaseUrl="/backend";');
const compile = source => ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replaceAll('"react"',JSON.stringify(pathToFileURL(require.resolve('react')).href))
 .replaceAll('"react/jsx-runtime"',JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href));
let commercial = await readFile(new URL('../src/components/CommercialNotes.tsx',import.meta.url),'utf8');
commercial = commercial.replace('"../services/mediaApi"',JSON.stringify(service)).replace('"../services/runtimeApi"',JSON.stringify(runtime));
const commercialURL = url(compile(commercial));
let source=await readFile(new URL('../src/components/Audio.tsx',import.meta.url),'utf8');
source=source.replace('"./CommercialNotes"',JSON.stringify(commercialURL));
source=source.replace("'../services/mediaApi'",JSON.stringify(service)).replace("'../services/runtimeApi'",JSON.stringify(runtime)).replace("'../services/api'",JSON.stringify(base));
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
code=code.replaceAll('"react"',JSON.stringify(pathToFileURL(require.resolve('react')).href)).replaceAll("'react'",JSON.stringify(pathToFileURL(require.resolve('react')).href)).replaceAll('"react/jsx-runtime"',JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href));
const {default:Audio}=await import(url(code));
const flush=()=>new Promise(r=>setImmediate(r));
function text(node){if(typeof node==='string')return node;if(!node)return '';return (node.children||[]).map(text).join(' ');}
function button(root,label){return root.findAllByType('button').find(b=>text(b).includes(label));}
const row={id:'record',title:'Telefonata',name:'call.wav',recordedAt:'2026-10-04T19:30',speakerNames:['Ale','Cliente'],createdAt:'2026-10-04T19:00:00Z',version:2,transcript:'testo originale',result:{duration_seconds:10,detected_language:'it'},run:{id:'run',status:'completed'}};
test('saved recordings show readiness and never offer microphone capture',async()=>{
 globalThis.__audioTest={request:async route=>route.endsWith('/status')?{ready:false,engineInstalled:false,localModelReady:false}:route==='/api/v1/audio'?{items:[]}:assert.fail(route)};
 let tree;await act(async()=>{tree=create(React.createElement(Audio));await flush();});
 assert.match(text(tree.toJSON()),/Dipendenze Audio assenti/);
 assert.match(text(tree.toJSON()),/senza microfono/);
 assert.equal(tree.root.findAllByType('input').filter(n=>n.props.type==='file')[0].props.accept.includes('.m4a'),true);
 await act(async()=>tree.unmount());
});
test('transcript corrections use displayed version; conflicts preserve the draft and disable export',async()=>{
 let savedBody;
 globalThis.__audioTest={request:async(route,init)=>{
  if(route.endsWith('/status'))return {ready:true,engineInstalled:true,localModelReady:true};
  if(route==='/api/v1/audio')return {items:[row]};
  if(route==='/api/v1/audio/record')return row;
  if(route.endsWith('/commercial/proposals'))return [];
  if(route.endsWith('/transcript')){savedBody=JSON.parse(init.body);throw new Error('Versione cambiata');}
  assert.fail(route);
 }};
 let tree;await act(async()=>{tree=create(React.createElement(Audio));await flush();});
 await act(async()=>{button(tree.root,'Telefonata').props.onClick();await flush();});
 await act(async()=>tree.root.findAllByType('textarea')[0].props.onChange({target:{value:'mia correzione'}}));
 assert.equal(button(tree.root,'Scarica testo').props.disabled,true);
 assert.equal(button(tree.root,'Copia in Libreria IA').props.disabled,true);
 await act(async()=>{button(tree.root,'Salva correzioni').props.onClick();await flush();});
 assert.deepEqual(savedBody,{transcript:'mia correzione',expected_version:2});
 assert.equal(tree.root.findAllByType('textarea')[0].props.value,'mia correzione');assert.match(text(tree.toJSON()),/Versione cambiata/);
 await act(async()=>tree.unmount());
});


test('commercial note requires exact selection and explicit approval before publication',async t=>{
 const {default:CommercialNotes}=await import(commercialURL);
 let proposals=[], writes=0, draft;
 const match={path:'synthetic.docx',heading:'CLIENTE TEST',start:0,stop:4,sha256:'a'.repeat(64),identityLines:[]};
 globalThis.window={confirm:()=>true};
 globalThis.__audioTest={request:async(route,init={})=>{
  if(route.includes('/customers?'))return {matches:[match],scanned:1,skipped:0};
  if(route.endsWith('/resolve')){writes++;proposals=[{...proposals[0],status:'approved'}];return {status:'approved'};}
  if(route.endsWith('/proposals')&&init.method==='POST'){
   draft=JSON.parse(init.body); proposals=[{id:'p',documentPath:match.path,customer:match.heading,date:draft.date,note:draft.note,status:'pending',expiresAt:'2026-10-25T12:00:00Z'}];return proposals[0];
  }
  if(route.endsWith('/proposals'))return proposals;
  assert.fail(route);
 }};
 let tree;await act(async()=>{tree=create(React.createElement(CommercialNotes,{record:row,disabled:false}));await flush();});
 t.after(async()=>{await act(async()=>tree.unmount());});
 await act(async()=>tree.root.findAllByType('input')[0].props.onChange({target:{value:'CLIENTE'}}));
 await act(async()=>{button(tree.root,'Cerca nei Word').props.onClick();await flush();});
 await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'Appunto verificato'}}));
 assert.equal(button(tree.root,'Prepara proposta').props.disabled,true);
 await act(async()=>tree.root.findAllByType('input').find(i=>i.props.type==='radio').props.onChange());
 await act(async()=>{button(tree.root,'Prepara proposta').props.onClick();await flush();});
 assert.equal(draft.expected_audio_version,2);assert.deepEqual(draft.selected,match);assert.equal(writes,0);
 await act(async()=>{button(tree.root,'Approva aggiunta').props.onClick();await flush();});
 assert.equal(writes,1);assert.equal(button(tree.root,'Approva aggiunta'),undefined);
});
