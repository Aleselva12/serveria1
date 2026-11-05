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
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let starts=0,payload=null,offline=false,callbacks=0;
const machine='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const empty=()=>({run:null,availableChecks:[{id:'memory_e2e',title:'Memoria'}],unavailableChecks:[{id:'backup_restore',title:'Backup'}]});
let state=empty(),timers=[];
globalThis.__nodeSchedule=fn=>{timers.push(fn);return timers.length;};
globalThis.__nodeCancel=()=>{};
globalThis.__nodeFetch=async(url,init={})=>{
 if(url.endsWith('/machines'))return {ok:true,json:async()=>({machines:[{id:machine,name:'PC ufficio',registered:true,type:'worker'}]})};
 if(offline)return {ok:false,json:async()=>({detail:'Server non disponibile'})};
 if(init.method==='POST'){
  starts++;payload=JSON.parse(init.body);
  state={...state,run:{id:'job1',status:'running',total:1,completed:0,currentCheck:'memory_e2e',results:[],detail:'Avviati'}};
  return {ok:true,json:async()=>state.run};
 }
 return {ok:true,json:async()=>state};
};
let code=ts.transpileModule(readFileSync(new URL('../src/tree/NodeVerificationPanel.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from ["']react\/jsx-runtime["']/g,'from '+external('react/jsx-runtime'))
 .replace(/from ["']react["']/g,'from '+external('react'))
 .replace(/import \{ apiBaseUrl \} from .*?;/,"const apiBaseUrl='';")
 .replace(/import \{ authenticatedFetch \} from .*?;/,'const authenticatedFetch=globalThis.__nodeFetch;')
 .replace(/\bsetTimeout\(/g,'globalThis.__nodeSchedule(')
 .replace(/\bclearTimeout\(/g,'globalThis.__nodeCancel(');
const Panel=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=r=>r.root.findAllByType('button').find(b=>b.props.onClick&&String(b.children).toLowerCase().includes('collaudi'));
const render=async()=>{let r;await act(async()=>{r=create(React.createElement(Panel,{onResults:()=>callbacks++}));});return r;};

test('one explicit click starts once, sends selected registered machine and records progress',async()=>{
 starts=0;state=empty();offline=false;timers=[];callbacks=0;let r;
 try{
  r=await render();assert.equal(starts,0);assert.equal(button(r).props.disabled,false);
  await act(async()=>r.root.findAllByType('select')[0].props.onChange({target:{value:machine}}));
  const click=button(r).props.onClick;
  await act(async()=>{click();click();});
  assert.equal(starts,1);assert.equal(payload.desktopMachineId,machine);
  assert.equal(button(r).props.disabled,true);
  state={...state,run:{...state.run,status:'completed',completed:1,currentCheck:null,detail:'Terminati',results:[{id:'memory_e2e',status:'pass',detail:'Rilettura riuscita'}]}};
  await act(async()=>{await timers.at(-1)();});
  assert.equal(r.root.findByType('progress').props.value,1);
  assert.match(JSON.stringify(r.toJSON()),/Rilettura riuscita/);
  assert.equal(button(r).props.disabled,false);assert.ok(callbacks>=2);
 }finally{if(r)await act(async()=>r.unmount());}
});
test('reopening the page reconnects to running checks without a second POST',async()=>{
 starts=0;offline=false;state={...empty(),run:{id:'old',status:'running',total:2,completed:1,currentCheck:'memory_e2e',results:[],detail:'In corso'}};let r;
 try{r=await render();assert.equal(starts,0);assert.equal(button(r).props.disabled,true);assert.equal(r.root.findByType('progress').props.value,1);}
 finally{if(r)await act(async()=>r.unmount());}
});
test('unavailable backend explains the problem and does not trigger a test',async()=>{
 starts=0;offline=true;state=empty();let r;
 try{r=await render();assert.equal(starts,0);assert.match(JSON.stringify(r.root.findByProps({role:'alert'}).children.map(x=>typeof x==='string'?x:'')),/Server non disponibile/);assert.equal(button(r).props.disabled,true);}
 finally{if(r)await act(async()=>r.unmount());offline=false;}
});
