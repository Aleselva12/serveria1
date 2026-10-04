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
let source=await readFile(new URL('../src/components/Audio.tsx',import.meta.url),'utf8');
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
 assert.match(text(tree.toJSON()),/Dipendenze Audio non installate/);
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
  if(route.endsWith('/transcript')){savedBody=JSON.parse(init.body);throw new Error('Versione cambiata');}
  assert.fail(route);
 }};
 let tree;await act(async()=>{tree=create(React.createElement(Audio));await flush();});
 await act(async()=>{button(tree.root,'Telefonata').props.onClick();await flush();});
 await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'mia correzione'}}));
 assert.equal(button(tree.root,'Scarica testo').props.disabled,true);
 assert.equal(button(tree.root,'Copia in Libreria IA').props.disabled,true);
 await act(async()=>{button(tree.root,'Salva correzioni').props.onClick();await flush();});
 assert.deepEqual(savedBody,{transcript:'mia correzione',expected_version:2});
 assert.equal(tree.root.findByType('textarea').props.value,'mia correzione');assert.match(text(tree.toJSON()),/Versione cambiata/);
 await act(async()=>tree.unmount());
});
