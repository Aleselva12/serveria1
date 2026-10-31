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
let serviceRows;
let fixture,offline=false,failSave=false,legacy=false,downloads=0,saved=[];
const reset=()=>{serviceRows=[{id:'immich',label:'Immich',status:'unknown',detail:'Non configurato',checkedAt:'2026-10-24T18:00:00Z'}];fixture={agents:[agent('supervisor'),agent('local_research_agent')],components:[],inventory_errors:[]};offline=false;failSave=false;legacy=false;downloads=0;saved=[];};reset();
globalThis.__overviewApi={
 shadowRouter:async()=>({principal:{model:'main-model'},shadow:{model:'router-model'},progress:{examples:4,agreement_percent:75,metric_label:'Accordo osservato'},database_ready:true,error:null,note:'Solo osservazione'}),
 defaultModels:async()=>({packs:{base:[{name:'base-model',role:'Base',installed:false}],now:[],future:[]},missing:{base:['base-model'],now:[],future:[]},running:false,pack:null,current_model:null,failed:[],note:'Nessuna assegnazione automatica'}),

 downloadWorkerUpdate:async()=>{downloads++;},
 verify:async id=>({run_id:'verify-'+id}),
 verification:async()=>({id:'verify-supervisor',status:'completed',result:{reported_model:'provider-model',configuration:fixture.agents[0].configuration,duration_ms:10}}),
 reloadTranscription:async()=>({note:'Cache Whisper ricaricata'}),
 agents:async()=>{if(offline)throw Error('Offline');return {...fixture,agents:[...fixture.agents]};},
 targets:async()=>[{id:'local',name:'Ollama di Cora',enabled:true},{id:'pc',name:'Desktop',enabled:true}],
 models:async id=>({models:[{name:id==='pc'?'desktop-model':'local-model'}],enabled:true,agent_chat:!legacy,active_model:id==='pc'?'desktop-model':null}),
 save:async(id,machine,model)=>{if(failSave)throw Error('Worker OFF');saved.push({id,machine,model});fixture.agents=fixture.agents.map(a=>a.id===id?{...a,assignment:{machine_id:machine,model},configuration:{role:a.role,model,machine_id:machine,source:'agent_assignment',configuration_id:'saved-'+id},model,machine_name:'Desktop'}:a);return {configuration:fixture.agents.find(a=>a.id===id).configuration,requires_restart:false};},
};
globalThis.__servicesApi={services:async()=>({services:serviceRows})};
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

test('legacy worker can save the desktop choice and offers concrete update instructions', async()=>{
 reset();legacy=true;let r;await act(async()=>{r=create(React.createElement(App));});
 await act(async()=>card(r)[0].props.onClick());
 await act(async()=>r.root.findAllByType('select')[0].props.onChange({target:{value:'pc'}}));
 assert.equal(button(r,'Salva assegnazione').props.disabled,false);
 assert.ok(JSON.stringify(r.toJSON()).includes('/generate'));
 await act(async()=>button(r,'Scarica aggiornamento worker').props.onClick());
 assert.equal(downloads,1);
 await act(async()=>r.root.findByType('form').props.onSubmit({preventDefault(){}}));
 assert.deepEqual(saved,[{id:'supervisor',machine:'pc',model:'desktop-model'}]);
 assert.ok(JSON.stringify(r.toJSON()).includes('Serve aggiornare il worker desktop'));
 assert.ok(!JSON.stringify(r.toJSON()).includes('Attiva dalla prossima chiamata'));
 legacy=false;
 await act(async()=>button(r,'Ricarica modelli').props.onClick());
 assert.equal(button(r,'Scarica aggiornamento worker'),undefined);
 assert.equal(r.root.findAllByType('select')[0].props.value,'pc');
 await act(async()=>r.unmount());
});

test('program icon opens only a configured HTTP URL; details remain an independent action',async()=>{
 reset();serviceRows=[
 {id:'immich',label:'Immich',status:'ready',browserUrl:'https://photos.example.test:8443',checkedAt:'2026-11-01T00:00:00Z'},
 {id:'nextcloud',label:'Nextcloud',status:'unknown',browserUrl:'javascript:alert(1)',checkedAt:'2026-11-01T00:00:00Z'},
 {id:'unsafe',label:'Private URL',status:'unknown',browserUrl:'https://user:secret@example.test',checkedAt:'2026-11-01T00:00:00Z'}];
 let r;await act(async()=>{r=create(React.createElement(App));});
 const links=r.root.findAllByType('a');assert.equal(links.length,1);
 assert.equal(links[0].props.href,'https://photos.example.test:8443/');
 assert.equal(links[0].props.target,'_blank');assert.ok(links[0].props.rel.includes('noopener'));
 assert.equal(links[0].findAllByProps({className:'catalog-monogram'}).length,1);
 await act(async()=>r.root.findByProps({'aria-label':'Dettagli Nextcloud'}).props.onClick());
 assert.ok(JSON.stringify(r.toJSON()).includes('Per abilitare l’icona'));
 await act(async()=>r.unmount());
});
test('models and shadow routing are collapsed after the agents and programs',async()=>{
 reset();let r;await act(async()=>{r=create(React.createElement(App));});
 const packs=r.root.findByProps({'aria-label':'Catalogo modelli locali di Cora'});
 const shadow=r.root.findByProps({'aria-label':'Orchestrazione e router shadow'});
 assert.equal(packs.type,'details');assert.equal(packs.props.open,undefined);
 assert.equal(shadow.type,'details');assert.equal(shadow.props.open,undefined);
 const html=JSON.stringify(r.toJSON());assert.ok(html.indexOf('Programmi e servizi')<html.indexOf('Pacchetti e download'));
 await act(async()=>r.unmount());
});
