import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url);
const external=name=>JSON.stringify(pathToFileURL(require.resolve(name)).href);
const read=path=>readFileSync(new URL(path,import.meta.url),'utf8');
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
globalThis.window=new EventTarget();
let count=8,offline=false,available=true,reads=0,modelReads=0;
const evaluation=()=>({model:'requested-model',reported_model:'reported-model',model_verified:true,evaluated_at:'2026-11-06T00:00:00+00:00',objective_count:count,warning:'Indicativo',ratings:Array.from({length:count},(_,i)=>({id:'T'+(i+1),title:'Obiettivo '+(i+1),score:95-i,explanation:'Spiegazione del punto '+(i+1),confidence:'medium'}))});
globalThis.__priorityApi={
 latest:async()=>{reads++;if(offline)throw Error('Offline');return {evaluation:count?evaluation():null,available};},
 status:async()=>{modelReads++;return {model:'configured-now',provider:'Ollama',installed:true,available:true,detail:'Pronto',configuration_source:'default',weights:{importance:4,risk:-1},max_objectives:8,history_available:true,last_evaluation:{model:'requested-before',reported_model:'actual-before',model_verified:true,evaluated_at:'2026-11-06T00:00:00+00:00'}};},
};
let code=ts.transpileModule(read('../src/components/PriorityAssessment.tsx'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from ["']react\/jsx-runtime["']/g,'from '+external('react/jsx-runtime'))
 .replace(/from ["']react["']/g,'from '+external('react'))
 .replace(/import \{ priorityApi \} from .*?;/,'const priorityApi=globalThis.__priorityApi;')
 .replace(/import "\.\/priority-assessment.css";/,'');
const Panel=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
async function mount(mode='list'){let r;await act(async()=>{r=create(React.createElement(Panel,{mode}));});return r;}

test('Home always displays five ranked points and keeps the rest in a collapsed list',async()=>{
 count=8;offline=false;available=true;reads=0;modelReads=0;let r;
 try{
  r=await mount();
  assert.equal(r.root.findByProps({className:'priority-ranking priority-top-five'}).findAllByType('li').length,5);
  const more=r.root.findByProps({className:'priority-more'});
  assert.notEqual(more.props.open,true);
  assert.equal(more.findAllByType('li').length,3);
  assert.equal(more.findByType('ol').props.start,6);
  assert.match(JSON.stringify(r.toJSON()),/Obiettivo 1/);
  assert.equal(reads,1);assert.equal(modelReads,0);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('a shorter list does not show an empty dropdown and saved updates refresh on notification',async()=>{
 count=3;let r;
 try{
  r=await mount();
  assert.equal(r.root.findAllByType('details').length,0);
  count=8;
  await act(async()=>window.dispatchEvent(new Event('cora:priorities-updated')));
  assert.equal(r.root.findByProps({className:'priority-more'}).findAllByType('li').length,3);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('Architecture shows configured and previously observed models without presenting them as identical',async()=>{
 let r;
 try{
  r=await mount('model');const text=JSON.stringify(r.toJSON());
  for(const label of ['configured-now','actual-before','requested-before','Importanza','Rischio','separato','pesi fissi'])assert.ok(text.includes(label),label);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('empty history and unavailable storage remain distinguishable',async()=>{
 count=0;offline=false;available=true;let r;
 try{r=await mount();assert.match(JSON.stringify(r.toJSON()),/Nessuna valutazione salvata/);}
 finally{if(r)await act(async()=>r.unmount());}
 available=false;
 try{r=await mount();assert.ok(r.root.findByProps({role:'alert'}));}
 finally{if(r)await act(async()=>r.unmount());available=true;}
});
test('desktop Home, mobile Home and Architecture share the same assessment component',()=>{
 for(const name of ['Home','MobileHome'])assert.ok(read('../src/components/'+name+'.tsx').includes('<PriorityAssessment />'));
 assert.ok(read('../src/components/Architecture.tsx').includes('<PriorityAssessment mode="model"/>'));
});

test('a late saved result cannot undo a new selection and double clicks start one evaluation',async()=>{
 const previousLatest=globalThis.__priorityApi.latest;
 let resolveHistory,posts=0;
 globalThis.__priorityApi.latest=()=>new Promise(resolve=>{resolveHistory=resolve;});
 globalThis.__priorityTransport=async(url,init={})=>{
  if(init.method==='POST'){posts++;return {ok:true,json:async()=>({...evaluation(),ratings:[{id:'E1',score:80,explanation:'Priorita motivata',confidence:'medium'}],persisted:true,persistence_detail:'Salvata'})};}
  return {ok:true,json:async()=>({model:'configured',installed:true,available:true,detail:'Pronto'})};
 };
 let roadmap=ts.transpileModule(read('../src/tree/RoadmapPriorities.tsx'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText
  .replace(/from ["']react\/jsx-runtime["']/g,'from '+external('react/jsx-runtime'))
  .replace(/from ["']react["']/g,'from '+external('react'))
  .replace(/import \{([^}]+)\} from "lucide-react";/,(_,names)=>'const '+names.split(',').map(n=>n.trim()).filter(Boolean).map(n=>n+'=()=>null').join(',')+';')
  .replace(/import \{ apiBaseUrl \} from .*?;/,"const apiBaseUrl='';")
  .replace(/import \{ authenticatedFetch \} from .*?;/,'const authenticatedFetch=globalThis.__priorityTransport;')
  .replace(/import \{ priorityApi \} from .*?;/,'const priorityApi=globalThis.__priorityApi;');
 const Roadmap=(await import('data:text/javascript;base64,'+Buffer.from(roadmap).toString('base64'))).default;
 let r;
 try{
  await act(async()=>{r=create(React.createElement(Roadmap,{stars:[{id:'T1',title:'Supervisor'},{id:'E1',title:'Clienti CRM'}],onOpen:()=>{}}));});
  await act(async()=>r.root.findAllByType('input')[0].props.onChange());
  await act(async()=>resolveHistory({available:true,evaluation:{...evaluation(),ratings:[{id:'T1',score:99,explanation:'Old',confidence:'low'}]}}));
  assert.equal(r.root.findAllByType('input')[0].props.checked,false);
  const evaluate=r.root.findAllByType('button').find(b=>b.children.includes('Valuta priorità')).props.onClick;
  await act(async()=>{evaluate();evaluate();});
  assert.equal(posts,1);
 }finally{
  if(r)await act(async()=>r.unmount());
  globalThis.__priorityApi.latest=previousLatest;
 }
});
