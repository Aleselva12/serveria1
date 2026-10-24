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
globalThis.requestAnimationFrame=fn=>fn();
const tool={id:'read',name:'read_document',description:'Reads an authorized document',parameters:['path']};
const agent=id=>({id,name:id,description:'Description '+id,role:id,available:true,capabilities:[],configuration:{role:id,model:'local-model',machine_id:'local',source:'global_selection',configuration_id:'base-'+id},model:'local-model',machine_name:'Ollama di Cora',assignment:null,runtime:{status:'ready',checks:{}},tools:[tool]});
let fixture,offline=false,failSave=false,saved=[];
const reset=()=>{fixture={agents:[agent('supervisor'),agent('local_research_agent')],components:[],inventory_errors:[]};offline=false;failSave=false;saved=[];};reset();
globalThis.__overviewApi={
 verify:async id=>({run_id:'verify-'+id}),
 verification:async()=>({id:'verify-supervisor',status:'completed',result:{reported_model:'provider-model',configuration:fixture.agents[0].configuration,duration_ms:10}}),
 reloadTranscription:async()=>({note:'Cache Whisper ricaricata'}),
 agents:async()=>{if(offline)throw Error('Offline');return {...fixture,agents:[...fixture.agents]};},
 targets:async()=>[{id:'local',name:'Ollama di Cora',enabled:true},{id:'pc',name:'Desktop',enabled:true}],
 models:async id=>({models:[{name:id==='pc'?'desktop-model':'local-model'}],enabled:true,agent_chat:true,active_model:id==='pc'?'desktop-model':null}),
 save:async(id,machine,model)=>{if(failSave)throw Error('Worker OFF');saved.push({id,machine,model});fixture.agents=fixture.agents.map(a=>a.id===id?{...a,assignment:{machine_id:machine,model},configuration:{role:a.role,model,machine_id:machine,source:'agent_assignment',configuration_id:'saved-'+id},model,machine_name:'Desktop'}:a);return {configuration:fixture.agents.find(a=>a.id===id).configuration,requires_restart:false};},
};
globalThis.__servicesApi={services:async()=>({services:[{id:'immich',label:'Immich',status:'unknown',detail:'Non configurato',checkedAt:'2026-10-24T18:00:00Z'}]})};
const source=await readFile(new URL('../src/components/ArchitectureOverview.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from ["']react\/jsx-runtime["']/g,'from '+external('react/jsx-runtime')).replace(/from ["']react["']/g,'from '+external('react')).replace(/import \{ api \} from ['"]\.\.\/services\/api['"];?/,'const api=globalThis.__servicesApi;').replace(/import \{ architectureApi \} from ['"]\.\.\/services\/architectureApi['"];?/,'const architectureApi=globalThis.__overviewApi;').replace(/import ['"]\.\/architecture-overview.css['"];?/,'');
const Overview=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const App=()=>{const[id,setId]=React.useState('supervisor');return React.createElement(Overview,{health:null,selectedNode:id,onSelect:setId});};
const card=r=>r.root.findAllByType('button').filter(b=>b.props.className?.startsWith('agent-card '));
const button=(r,text)=>r.root.findAllByType('button').find(b=>b.children.includes(text));
test('large agent buttons open real tools and details; programs are separate; no graph',async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 assert.equal(r.root.findAllByType('svg').length,0);assert.equal(card(r).length,2);
 await act(async()=>card(r)[1].props.onClick());
 assert.ok(JSON.stringify(r.toJSON()).includes('Description local_research_agent'));
 assert.ok(JSON.stringify(r.toJSON()).includes('read_document'));
 assert.equal(r.root.findAllByProps({className:'program-card '}).length,1);
 await act(async()=>r.unmount());
});
test('owner assigns desktop model to one agent and refreshes persistent state',async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 await act(async()=>card(r)[0].props.onClick());
 await act(async()=>r.root.findAllByType('select')[0].props.onChange({target:{value:'pc'}}));
 assert.equal(r.root.findAllByType('select')[1].props.value,'desktop-model');
 await act(async()=>button(r,'Salva assegnazione').props.onClick?.());
 // Saving is a form submit, not a card action.
 await act(async()=>r.root.findByType('form').props.onSubmit({preventDefault(){}}));
 assert.deepEqual(saved,[{id:'supervisor',machine:'pc',model:'desktop-model'}]);
 assert.equal(fixture.agents[1].model,'local-model');
 assert.ok(JSON.stringify(r.toJSON()).includes('Assegnazione salvata'));
 await act(async()=>r.unmount());
});
test('failed save retains selection and shows backend reason',async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 await act(async()=>card(r)[0].props.onClick());
 await act(async()=>r.root.findAllByType('select')[0].props.onChange({target:{value:'pc'}}));failSave=true;
 await act(async()=>r.root.findByType('form').props.onSubmit({preventDefault(){}}));
 assert.equal(saved.length,0);assert.equal(r.root.findAllByType('select')[0].props.value,'pc');
 assert.ok(JSON.stringify(r.toJSON()).includes('Worker OFF'));
 await act(async()=>r.unmount());
});
test('agent endpoint failure does not hide independently loaded programs',async()=>{
 reset();offline=true;let r;await act(async()=>{r=create(React.createElement(App));});
 assert.equal(card(r).length,0);assert.equal(r.root.findAllByProps({className:'program-card '}).length,1);
 assert.ok(JSON.stringify(r.toJSON()).includes('Offline'));
 await act(async()=>r.unmount());
});

test('model verification shows provider reply and no tools are invoked', async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 await act(async()=>card(r)[0].props.onClick());
 await act(async()=>button(r,'Verifica modello con una chiamata').props.onClick());
 assert.ok(JSON.stringify(r.toJSON()).includes('provider-model'));
 assert.equal(saved.length,0);
 await act(async()=>r.unmount());
});
test('manual reload resets an unsaved form to the stored assignment', async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 await act(async()=>card(r)[0].props.onClick());
 await act(async()=>r.root.findAllByType('select')[0].props.onChange({target:{value:'pc'}}));
 await act(async()=>button(r,'Ricarica configurazione e stato').props.onClick());
 assert.equal(r.root.findAllByType('select')[0].props.value,'inherit');
 assert.equal(saved.length,0);
 await act(async()=>r.unmount());
});
test('Audio distinguishes the LLM from the Whisper transcription engine', async()=>{
 reset();fixture.agents[1]={...fixture.agents[1],id:'audio_agent',transcription:{engine:'Faster-Whisper',model:'small',model_label:'small',device:'cpu',compute_type:'int8',ready:true,loaded:null}};
 let r;await act(async()=>{r=create(React.createElement(App));});await act(async()=>card(r)[1].props.onClick());
 const text=JSON.stringify(r.toJSON());assert.ok(text.includes('Faster-Whisper'));assert.ok(text.includes('small'));assert.ok(text.includes('Non ancora caricato'));assert.ok(text.toLowerCase().includes('non cambia whisper'));
 await act(async()=>r.unmount());
});
