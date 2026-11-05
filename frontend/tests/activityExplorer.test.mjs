import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {create,act} from 'react-test-renderer';
import {evidenceUrl,explorerUrl} from './activityLoader.mjs';
const {buildEvidence,layoutEvidence}=await import(evidenceUrl);
const Explorer=(await import(explorerUrl)).default;
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const event=(id,status,time,parent=null)=>({id,sequence:1,type:'trace.span',timestamp:time,source:'tracing',component_run_id:'r',span_id:'s',parent_span_id:parent,payload:{kind:'tool',name:'library_read',status}});
const start=event('start','running','2026-11-05T10:00:00Z','missing');
const end=event('end','completed','2026-11-05T10:00:01Z','missing');
const run={id:'r',status:'completed',target:'supervisor',elapsed_ms:1200,agents:{},timings:{selected_tools:['library_read','library_write'],inference_observations:[{role:'supervisor',requested_model:'A',reported_model:'B',matches_requested:false,machine_id:'desktop'}]}};

test('global completion never certifies uncertain effects or a mismatched model',()=>{
 const result=buildEvidence(run,[start],[{id:'o',capability_id:'write',effect:'write',status:'uncertain'}]);
 assert.ok(result.warnings.some(w=>w.includes('successo globale')));
 assert.ok(result.warnings.some(w=>w.includes('differisce')));
 assert.ok(result.warnings.some(w=>w.includes('evento finale')));
 assert.ok(result.warnings.some(w=>w.includes('genitore assente')));
 assert.equal(result.steps.filter(s=>s.kind==='tool').length,1);
 assert.ok(!result.steps.some(s=>s.name==='library_write'));
});

test('missing evidence stays unknown and span completion survives delayed starts',()=>{
 const empty=buildEvidence(run,[],[]);
 assert.ok(empty.warnings.some(w=>w.includes('Nessun percorso')));
 assert.equal(empty.steps.filter(s=>s.kind==='tool').length,0);
 const late={...start,id:'late',timestamp:'2026-11-05T10:00:02Z'};
 assert.equal(buildEvidence(run,[end,late],[]).steps.find(s=>s.id==='span:s').status,'completed');
});

test('transactional facts retain their origin and disconnected proofs gain no invented parent',()=>{
 const fact={...end,id:'fact',type:'operation.committed',span_id:null,payload:{status:'succeeded',operation_id:'o'}};
 const result=buildEvidence(run,[fact],[{id:'o',capability_id:'read',effect:'read',status:'succeeded'}]);
 assert.equal(result.steps.find(s=>s.id==='event:fact').origin,'Evento persistente');
 assert.equal(result.steps.find(s=>s.id==='operation:o').parent,undefined);
 const cyclic=[{id:'a',parent:'b'},{id:'b',parent:'a'}];
 const layout=layoutEvidence(cyclic);
 assert.equal(layout.positions.size,2);
 assert.ok([...layout.positions.values()].every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
});

test('a failed trace remains visible despite global completion',()=>{
 const result=buildEvidence(run,[{...end,payload:{...end.payload,status:'error',error_type:'ToolError'}}],[]);
 assert.ok(result.warnings.some(w=>w.includes('chiamata tracciata è fallita')));
});

test('non-span events with a span reference open their own recorded detail',async()=>{
 let root;
 const finished={...end,id:'finished',type:'tool.finished',payload:{status:'completed',operation_id:'operation-proof'}};
 try {
  await act(async()=>{root=create(React.createElement(Explorer,{runs:[run],selected:run,selectedId:'r',events:[finished],operations:[],onSelect:()=>{},loading:false,error:'',older:false,onOlder:()=>{},live:false,onLive:()=>{},onRefresh:()=>{}}));});
  await act(async()=>root.root.findAllByType('button').find(b=>b.props['aria-label']==='Esamina evento 1').props.onClick({stopPropagation(){}}));
  const inspector=root.root.findByProps({'aria-label':'Dettaglio del passaggio'});
  assert.ok(inspector.findAllByType('pre').some(n=>n.children.join('').includes('operation-proof')));
 } finally {if(root)await act(async()=>root.unmount());}
});

test('replay reveals historical state, not future completion, and cannot invoke tools',async()=>{
 let root,liveChanges=[];
 try {
  await act(async()=>{root=create(React.createElement(Explorer,{runs:[run],selected:run,selectedId:'r',events:[start,end],operations:[],onSelect:()=>{},loading:false,error:'',older:false,onOlder:()=>{},live:true,onLive:v=>liveChanges.push(v),onRefresh:()=>{}}));});
  const button=name=>root.root.findAllByType('button').find(b=>b.children.includes(name));
  await act(async()=>button('Passo').props.onClick());
  assert.deepEqual(liveChanges,[false]);
  let node=root.root.findAll(n=>n.type==='g' && n.props.role==='button')[0];
  assert.match(node.props['aria-label'],/In corso/);
  await act(async()=>button('Passo').props.onClick());
  node=root.root.findAll(n=>n.type==='g' && n.props.role==='button')[0];
  assert.match(node.props['aria-label'],/Concluso/);
  await act(async()=>node.props.onKeyDown({key:'Enter',preventDefault(){}}));
  assert.ok(JSON.stringify(root.toJSON()).includes('Traccia diagnostica'));
 } finally {if(root)await act(async()=>root.unmount());}
});
