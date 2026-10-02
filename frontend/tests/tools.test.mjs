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
const definition = id => ({
  entry: fixture.entries.find(e => e.id === id), parameters: [{name:'value',type:'str',required:true,default:null}],
  output_type: 'str', operations: ['calculate'], checks: [], conditions: [], note: 'Static summary',
  flow: { nodes: [
    {id:'input',kind:'trigger',label:'Ingresso '+id,x:50,y:120,config:{},detail:'input'},
    {id:'operation',kind:'tool',label:'Operazione '+id,x:330,y:120,config:{},detail:'operation'},
    {id:'output',kind:'output',label:'Risultato '+id,x:610,y:120,config:{},detail:'output'},
  ], edges: [{id:'e',source:'input',target:'operation',label:'input'}] },
});
let response = async () => fixture, detail = async id => definition(id), saved, stored;
globalThis.__inventoryApi = { toolInventory: () => response() };
globalThis.__toolsApi = {
  definition: id => detail(id),
  saveDraft: async (draft, token) => { saved = {draft,token}; stored = {...draft,id:'saved',version:1,updated_at:'2026-10-02T20:00:00Z',warnings:[]}; return stored; },
  listDrafts: async () => stored ? [{id:stored.id,title:stored.title,version:stored.version,updated_at:stored.updated_at,status:'draft'}] : [],
  loadDraft: async () => stored,
};
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
  ['import ArchitectureOverview from "./ArchitectureOverview";', 'const ArchitectureOverview = () => null;'],
  ['import ArchitectureTools from "./ArchitectureTools";', 'const ArchitectureTools = globalThis.__Tools;'],
  ['import ConnectionNotice from "./ConnectionNotice";', 'const ConnectionNotice = () => null;'],
]);
async function mount(Component, props={}) { let r; await act(async()=>{r=create(React.createElement(Component,props));});return r; }
async function click(r,label) {await act(async()=>r.root.findAllByType('button').find(b=>b.children.includes(label)).props.onClick());}
const rows = r => r.root.findAll(n=>n.type==='button' && n.props.className?.startsWith('tools-list-row'));
async function choose(r,index) { await act(async()=>rows(r)[index].props.onClick()); }
async function unmount(r){await act(async()=>r.unmount());}

test('Tools remains reachable without registry and starts with an empty viewer',async()=>{
  const r=await mount(Architecture,{registry:null,health:null,selectedNode:'',onSelect:()=>{}});
  await click(r,'Tools');
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
