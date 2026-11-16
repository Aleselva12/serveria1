import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { create, act } from 'react-test-renderer';

const require = createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window = { confirm: () => true };
const external = name => JSON.stringify(pathToFileURL(require.resolve(name)).href);
async function compile(file, replacements = []) {
  let code = ts.transpileModule(await readFile(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText.replaceAll('from "react/jsx-runtime"', 'from ' + external('react/jsx-runtime'))
    .replace(/from "react"/g, 'from ' + external('react'))
    .replace(/from "lucide-react"/g, 'from ' + external('lucide-react'));
  for (const [from, to] of replacements) code = code.replace(from, to);
  return (await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))).default;
}
const entry = (id, status, group) => ({ id, name: id, status, group, kind: status === 'planned' ? 'planned' : 'tool', description: id + ' description', agents: status === 'connected' ? ['Cora'] : [], source: 'test', parameters: ['value'], detail: 'structural' });
const fixture = { entries: [entry('calculator', 'connected', 'Sistema'), entry('upload', 'unconnected', 'File'), entry('calendar', 'planned', 'Calendario')], errors: [], scope: 'Test inventory' };
fixture.entries[0].capabilities = [{id:'supervisor.calculator',version:3,actor:'supervisor',effect:'compute',retry:'safe',approval:'generic',connected:true,
  required_actions:['calculate'],conditional_actions:['inspect_runtime'],permissions:[{action:'calculate',policy:'auto'},{action:'inspect_runtime',policy:'blocked'}],
  input_schema:{type:'object'},output_schema:{type:'object'},native_output_schema:{type:'string'},contract_digest:'digest',implementation_revision:'revision'}];
const definition = id => ({
  entry: fixture.entries.find(e => e.id === id), parameters: [{name:'value',type:'str',required:true,default:null}],
  output_type: 'str', operations: ['calculate'], checks: [], conditions: [], note: 'Static summary',
  flow: { nodes: [
    {id:'input',kind:'trigger',label:'Ingresso '+id,x:50,y:120,config:{},detail:'input'},
    {id:'operation',kind:'tool',label:'Operazione '+id,x:330,y:120,config:{},detail:'operation'},
    {id:'output',kind:'output',label:'Risultato '+id,x:610,y:120,config:{},detail:'output'},
  ], edges: [{id:'e',source:'input',target:'operation',label:'input'}] },
});
let response = async () => fixture, detail = async id => definition(id), saved, stored, duplicated, deleted;
let validation = async () => [];
globalThis.__inventoryApi = { toolInventory: () => response() };
globalThis.__toolsApi = {
  definition: id => detail(id),
  saveDraft: async (draft, token) => { saved = {draft,token}; stored = {...draft,id:'saved',version:1,updated_at:'2026-10-02T20:00:00Z',warnings:[]}; return stored; },
  listDrafts: async () => stored ? [{id:stored.id,title:stored.title,version:stored.version,updated_at:stored.updated_at,status:'draft'}] : [],
  loadDraft: async () => stored,
  validateDraft: async () => validation(),
  duplicateDraft: async id => { duplicated = id; return {...stored,id:'copy',title:'Copia di '+stored.title,version:1,updated_at:'2026-10-03T20:00:00Z'}; },
  deleteDraft: async (id, version) => { deleted = {id,version}; stored = null; },
  listRuns: async () => runHistory,
  startRun: async (...args) => { started = args; return startResult(...args); },
  getRun: async id => runById(id),
  cancelRun: async id => ({...runById(id),status:'cancelled'}),
};
let runHistory = [], started, startResult = () => { throw Error('not configured'); }, runById = () => { throw Error('missing'); };
globalThis.__Canvas = await compile('../src/components/ToolFlowCanvas.tsx');
const Editor = await compile('../src/components/AutomationEditor.tsx', [
  ['import ToolFlowCanvas from "./ToolFlowCanvas";','const ToolFlowCanvas=globalThis.__Canvas;'],
  ['import { toolsApi } from "../services/toolsApi";','const toolsApi=globalThis.__toolsApi;'],
]);
globalThis.__Editor = Editor;
const Tools = await compile('../src/components/ArchitectureTools.tsx', [
  ['import { api } from "../services/api";','const api=globalThis.__inventoryApi;'],
  ['import { toolsApi } from "../services/toolsApi";','const toolsApi=globalThis.__toolsApi;'],
  ['import ToolFlowCanvas from "./ToolFlowCanvas";','const ToolFlowCanvas=globalThis.__Canvas;'],
  ['import AutomationEditor from "./AutomationEditor";','const AutomationEditor=globalThis.__Editor;'],
  ['import "./architecture-tools.css";',''],['import "./tool-flow.css";',''],
]);
globalThis.__Tools = Tools;
const Architecture = await compile('../src/components/Architecture.tsx', [
  ['import PriorityAssessment from "./PriorityAssessment";', 'const PriorityAssessment = () => null;'],
  ['import ArchitectureOverview from "./ArchitectureOverview";', 'const ArchitectureOverview = () => null;'],
  ['import ArchitectureTools from "./ArchitectureTools";', 'const ArchitectureTools = globalThis.__Tools;'],
  ['import ConnectionNotice from "./ConnectionNotice";', 'const ConnectionNotice = () => null;'],
]);
async function mount(Component, props={}) { let r; await act(async()=>{r=create(React.createElement(Component,props));});return r; }
async function click(r,label) {await act(async()=>r.root.findAllByType('button').find(b=>b.children.includes(label)).props.onClick());}
const rows = r => r.root.findAll(n=>n.type==='button' && n.props.className?.startsWith('tools-list-row'));
async function choose(r,index) { await act(async()=>rows(r)[index].props.onClick()); }
async function unmount(r){await act(async()=>r.unmount());}

test('direct interface APIs are separate and integration gaps remain actionable',async()=>{
 const previous=response;
 response=async()=>({...fixture,entries:[...fixture.entries,{id:'direct-api',name:'GET /auth/session',group:'Accesso',kind:'api',status:'direct',description:'Sessione',detail:'API diretta',agents:[],parameters:[],source:'API'},{id:'missing-api',name:'GET /api/v1/server/files/children',group:'File server',kind:'api',status:'integration_needed',description:'Cartelle',detail:'Manca server_list_files',agents:[],parameters:[],source:'API'}]});
 const r=await mount(Tools);
 const sections=r.root.findAllByProps({className:'tools-catalog-section'});
 assert.equal(sections.length,2);
 assert.equal(sections[1].findAllByType('strong').filter(n=>n.children.includes('GET /auth/session')).length,1);
 assert.equal(sections[0].findAllByType('strong').filter(n=>n.children.includes('GET /auth/session')).length,0);
 assert.equal(sections[0].findAllByType('strong').filter(n=>n.children.includes('GET /api/v1/server/files/children')).length,1);
 assert.ok(JSON.stringify(r.toJSON()).includes('eseguibili solo a mano'));
 await unmount(r);response=previous;
});

test('Tools remains reachable without registry and starts with an empty viewer',async()=>{
  const r=await mount(Architecture,{registry:null,health:null,selectedNode:'',onSelect:()=>{}});
  await click(r,'Tool e automazioni');
  assert.ok(JSON.stringify(r.toJSON()).includes('Scegli un tool dall’elenco'));
  assert.equal(rows(r).length,3);
  assert.equal(r.root.findAllByProps({className:'tools-node-grid'}).length,0);
  await unmount(r);
});
test('clicking a catalogue item shows only its flow and characteristics',async()=>{
  const r=await mount(Tools);await choose(r,0);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione calculator'}).length,1);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione upload'}).length,0);
  assert.ok(JSON.stringify(r.toJSON()).includes('Ingressi e parametri'));
  await choose(r,1);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione calculator'}).length,0);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione upload'}).length,1);
  await unmount(r);
});
test('filtering the list does not replace the selected tool flow',async()=>{
  const r=await mount(Tools);await choose(r,0);
  await act(async()=>r.root.findByProps({'aria-label':'Filtra per stato'}).props.onChange({target:{value:'planned'}}));
  assert.equal(rows(r).length,1);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione calculator'}).length,1);
  await act(async()=>r.root.findByProps({'aria-label':'Cerca tools'}).props.onChange({target:{value:'absent'}}));
  assert.equal(rows(r).length,0);
  assert.ok(JSON.stringify(r.toJSON()).includes('Nessuno strumento corrisponde'));
  await unmount(r);
});
test('late definition responses cannot overwrite a newer selection',async()=>{
  let resolve;
  detail=id=>id==='calculator'?new Promise(r=>{resolve=r;}):Promise.resolve(definition(id));
  const r=await mount(Tools);await choose(r,0);await choose(r,1);
  await act(async()=>resolve(definition('calculator')));
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione upload'}).length,1);
  assert.equal(r.root.findAllByProps({'aria-label':'Passaggio: Operazione calculator'}).length,0);
  detail=async id=>definition(id);await unmount(r);
});
test('inventory failure is explicit and refresh can recover',async()=>{
  response=async()=>{throw Error('Backend offline');};
  const r=await mount(Tools);
  assert.equal(r.root.findByProps({role:'alert'}).children[0],'Backend offline');
  response=async()=>fixture;await click(r,' Aggiorna');
  assert.equal(r.root.findAllByProps({role:'alert'}).length,0);await unmount(r);
});
test('graph editor adds and connects a tool, moves it and persists its configuration',async()=>{
  const r=await mount(Editor,{entries:fixture.entries});await click(r,'Tool');
  await act(async()=>r.root.findByProps({'aria-label':'Tool del nodo'}).props.onChange({target:{value:'calculator'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Configurazione nodo'}).props.onChange({target:{value:'{"value":"2+2"}'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Collega in uscita: Avvio manuale'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Collega in ingresso: calculator'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Collega in uscita: calculator'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Collega in ingresso: Risultato'}).props.onClick());
  const step=r.root.findByProps({'aria-label':'Passaggio: calculator'});
  await act(async()=>step.props.onKeyDown({key:'ArrowRight',preventDefault(){}}));
  await click(r,'Salva bozza');
  assert.equal(saved.draft.edges.length,2);
  const node=saved.draft.nodes.find(n=>n.tool_id==='calculator');
  assert.deepEqual(node.config,{value:'2+2'});assert.equal(node.x,900);
  assert.equal(saved.draft.status,'draft');
  assert.ok(JSON.stringify(r.toJSON()).includes('Bozza salvata sul server'));
  await unmount(r);
});
test('invalid JSON prevents saving and removing a node removes its connections',async()=>{
  const r=await mount(Editor,{entries:fixture.entries});await click(r,'Tool');
  await act(async()=>r.root.findByProps({'aria-label':'Configurazione nodo'}).props.onChange({target:{value:'{bad'}}));
  const save=r.root.findAllByType('button').find(b=>b.children.includes('Salva bozza'));
  assert.equal(save.props.disabled,true);
  await act(async()=>r.root.findByProps({'aria-label':'Configurazione nodo'}).props.onChange({target:{value:'{}'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Collega in uscita: Avvio manuale'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Collega in ingresso: Scegli un tool'}).props.onClick());
  await click(r,'Rimuovi passaggio');
  assert.equal(r.root.findAllByProps({className:'flow-connections'}).length,0);
  await unmount(r);
});

test('catalog shows versioned execution contracts and conditional permissions without execution buttons',async()=>{
  const r=await mount(Tools);await choose(r,0);
  const text=JSON.stringify(r.toJSON());
  for(const value of ['Contratti eseguibili','supervisor.calculator','versione ','Solo nel ramo che lo richiede','nessun ritentativo automatico']) assert.ok(text.includes(value),value);
  // The catalog viewer never runs a tool directly; only the automation editor has run buttons.
  const viewer=r.root.findByProps({className:'tool-viewer'});
  assert.equal(viewer.findAllByType('button').filter(b=>b.children.includes('Esegui')).length,0);
  await unmount(r);
});

const wait = ms => act(async()=>{await new Promise(r=>setTimeout(r,ms));});
const text = r => JSON.stringify(r.toJSON());
test('saved drafts load on open and can be duplicated and deleted',async()=>{
  stored={...fixtureDraft(),id:'saved',version:2,updated_at:'2026-10-02T20:00:00Z',warnings:[]};
  const r=await mount(Editor,{entries:fixture.entries});
  assert.ok(text(r).includes('Bozza esistente'));
  await act(async()=>r.root.findByProps({'aria-label':'Duplica Bozza esistente'}).props.onClick());
  assert.equal(duplicated,'saved');
  assert.ok(text(r).includes('Copia di Bozza esistente'));
  await act(async()=>r.root.findByProps({'aria-label':'Apri Bozza esistente'}).props.onClick());
  assert.equal(r.root.findByProps({'aria-label':'Nome automazione'}).props.value,'Bozza esistente');
  await act(async()=>r.root.findByProps({'aria-label':'Elimina Bozza esistente'}).props.onClick());
  assert.deepEqual(deleted,{id:'saved',version:2});
  assert.equal(r.root.findAllByProps({'aria-label':'Apri Bozza esistente'}).length,0);
  assert.ok(text(r).includes('resta nell’editor come nuova bozza'));
  await unmount(r);
});
function fixtureDraft(){return {title:'Bozza esistente',description:'',status:'draft',nodes:[{id:'in',kind:'trigger',label:'Avvio',x:10,y:10,config:{}}],edges:[]};}

test('live validation shows warnings, structure errors and blocks saving on errors',async()=>{
  stored=null;validation=async()=>['Risultato: non raggiungibile da un ingresso.'];
  const r=await mount(Editor,{entries:fixture.entries});await wait(700);
  assert.ok(text(r).includes('non raggiungibile'));
  validation=async()=>{throw Object.assign(Error('I cicli non sono supportati.'),{status:400});};
  await act(async()=>r.root.findByProps({'aria-label':'Descrizione automazione'}).props.onChange({target:{value:'x'}}));await wait(700);
  assert.ok(text(r).includes('Struttura non valida'));
  assert.equal(r.root.findAllByType('button').find(b=>b.children.includes('Salva bozza')).props.disabled,true);
  validation=async()=>[];
  await act(async()=>r.root.findByProps({'aria-label':'Descrizione automazione'}).props.onChange({target:{value:'xy'}}));await wait(700);
  assert.ok(text(r).includes('Flusso completo'));
  await unmount(r);
});

test('tool parameters render as a form from the contract schema and show permissions',async()=>{
  const entries=structuredClone(fixture.entries);
  entries[0].capabilities[0].input_schema={type:'object',required:['expression'],properties:{
    expression:{type:'string',title:'Espressione',description:'Formula da calcolare'},
    precision:{anyOf:[{type:'integer'},{type:'null'}],default:2},
    mode:{enum:['fast','exact']},strict:{type:'boolean'}}};
  const r=await mount(Editor,{entries});await click(r,'Tool');
  await act(async()=>r.root.findByProps({'aria-label':'Tool del nodo'}).props.onChange({target:{value:'calculator'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Parametro expression'}).props.onChange({target:{value:'2+2'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Parametro precision'}).props.onChange({target:{value:'3'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Parametro mode'}).props.onChange({target:{value:'exact'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Parametro strict'}).props.onChange({target:{value:'false'}}));
  assert.deepEqual(JSON.parse(r.root.findByProps({'aria-label':'Configurazione nodo'}).props.value),{expression:'2+2',precision:3,mode:'exact',strict:false});
  await act(async()=>r.root.findByProps({'aria-label':'Parametro expression'}).props.onChange({target:{value:''}}));
  assert.deepEqual(JSON.parse(r.root.findByProps({'aria-label':'Configurazione nodo'}).props.value),{precision:3,mode:'exact',strict:false});
  const out=text(r);
  for(const value of ['EFFETTO E PERMESSI','Calcolo','Automatico','Bloccato','solo nel ramo che lo richiede','Espressione']) assert.ok(out.includes(value),value);
  await act(async()=>r.root.findByProps({'aria-label':'Tool del nodo'}).props.onChange({target:{value:'upload'}}));
  assert.ok(text(r).includes('Nessun contratto eseguibile'));
  await unmount(r);
});

const savedFlow = () => ({id:'saved',version:4,updated_at:'2026-10-02T20:00:00Z',warnings:[],title:'Flusso',description:'',status:'draft',
  nodes:[{id:'in',kind:'trigger',label:'Avvio',x:10,y:10,config:{}},
         {id:'calc',kind:'tool',label:'Calcola',x:200,y:10,tool_id:'calculator',config:{value:'{{input.numero}}'}},
         {id:'check',kind:'condition',label:'Grande?',x:400,y:10,config:{left:'{{calc.total}}',op:'gt',right:'10'}},
         {id:'out',kind:'output',label:'Fine',x:600,y:10,config:{}}],
  edges:[{id:'a',source:'in',target:'calc',label:'successo'},{id:'b',source:'calc',target:'check',label:'successo'},
         {id:'c',source:'check',target:'out',label:'sì'},{id:'d',source:'check',target:'out',label:'no'}]});
const runOf = (status, nodes={}) => ({id:'run1',draft_id:'saved',draft_version:4,title:'Flusso',mode:'dry_run',status,created_at:'2026-10-03T10:00:00Z',
  started_at:null,finished_at:null,error:null,input:{numero:5},nodes:{in:{status:'done',kind:'trigger',label:'Avvio'},calc:{status:'pending',kind:'tool',label:'Calcola'},
  check:{status:'pending',kind:'condition',label:'Grande?'},out:{status:'pending',kind:'output',label:'Fine'},...nodes}});

test('a saved draft runs as dry run with launch inputs and shows node progress',async()=>{
  stored=savedFlow();runHistory=[];validation=async()=>[];
  let current=runOf('running');
  startResult=()=>current;runById=()=>current;
  const r=await mount(Editor,{entries:fixture.entries});
  await act(async()=>r.root.findByProps({'aria-label':'Apri Flusso'}).props.onClick());
  const dry=()=>r.root.findAllByType('button').find(b=>b.children.includes('Prova a vuoto'));
  assert.equal(dry().props.disabled,false);
  await act(async()=>r.root.findByProps({'aria-label':'Valore di avvio numero'}).props.onChange({target:{value:'5'}}));
  await act(async()=>dry().props.onClick());
  assert.deepEqual(started,['saved',4,'dry_run',{numero:5}]);
  assert.ok(text(r).includes('In esecuzione'));
  assert.equal(dry().props.disabled,true);
  current=runOf('succeeded',{calc:{status:'done',kind:'tool',label:'Calcola',result:{total:42},input:{value:5},duration_ms:12},
    check:{status:'done',kind:'condition',label:'Grande?',outcome:'sì'},out:{status:'done',kind:'output',label:'Fine'}});
  await wait(1700);
  assert.ok(text(r).includes('Completata'));
  const step=r.root.findAll(n=>typeof n.props.className==='string'&&n.props.className.includes('flow-step')&&n.props.className.includes('run-done'));
  assert.ok(step.length>=3);
  await act(async()=>r.root.findByProps({'aria-label':'Passaggio: Calcola'}).props.onClick());
  assert.ok(text(r).includes('ULTIMA ESECUZIONE'));
  assert.ok(text(r).includes('42'));
  await unmount(r);
});

test('run rejection lists problems and live run asks confirmation; unsaved drafts cannot run',async()=>{
  stored=savedFlow();runHistory=[{...runOf('failed'),error:'Calcola: errore'}];
  startResult=()=>{throw Object.assign(Error('Il flusso non può essere eseguito.'),{problems:['Manca il valore di avvio «numero».']});};
  let asked='';globalThis.window.confirm=m=>{asked=m;return true;};
  const r=await mount(Editor,{entries:fixture.entries});
  const run=()=>r.root.findAllByType('button').find(b=>b.children.includes('Esegui'));
  assert.equal(run().props.disabled,true);
  await act(async()=>r.root.findByProps({'aria-label':'Apri Flusso'}).props.onClick());
  assert.ok(text(r).includes('Esecuzioni precedenti'));
  await act(async()=>run().props.onClick());
  assert.ok(asked.includes('Eseguire davvero'));
  assert.ok(text(r).includes('Manca il valore di avvio «numero».'));
  await act(async()=>r.root.findByProps({'aria-label':'Descrizione automazione'}).props.onChange({target:{value:'cambiata'}}));
  assert.equal(run().props.disabled,true);
  globalThis.window.confirm=()=>true;
  await unmount(r);
});

test('condition form and reference picker write references into the configuration',async()=>{
  stored=savedFlow();runHistory=[];
  const r=await mount(Editor,{entries:fixture.entries});
  await act(async()=>r.root.findByProps({'aria-label':'Apri Flusso'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Passaggio: Grande?'}).props.onClick());
  await act(async()=>r.root.findByProps({'aria-label':'Condizione: confronto'}).props.onChange({target:{value:'empty'}}));
  assert.deepEqual(JSON.parse(r.root.findByProps({'aria-label':'Configurazione nodo'}).props.value),{left:'{{calc.total}}',op:'empty'});
  assert.equal(r.root.findAllByProps({'aria-label':'Condizione: termine'}).length,0);
  const picker=r.root.findByProps({'aria-label':'Riferimento per il valore'});
  const values=picker.findAllByType('option').map(o=>o.props.value);
  assert.ok(values.includes('{{calc}}'));assert.ok(values.includes('{{input.numero}}'));
  assert.ok(!values.includes('{{out}}'));
  await act(async()=>picker.props.onChange({target:{value:'{{input.numero}}'}}));
  assert.equal(JSON.parse(r.root.findByProps({'aria-label':'Configurazione nodo'}).props.value).left,'{{input.numero}}');
  await unmount(r);
});
