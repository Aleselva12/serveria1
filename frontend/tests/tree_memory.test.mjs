import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const read=p=>readFileSync(new URL(p,import.meta.url),'utf8');
const snapshot=JSON.parse(read('../src/tree/cora-plan.snapshot.json'));
const nodes=snapshot.nodes;
const byId=new Map(nodes.map(n=>[n.id,n]));
const load=async source=>import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{
 compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022},
}).outputText).toString('base64'));
const {checks}=await load(read('../src/tree/model.ts'));
const {starTone,developmentIndicator}=await load(read('../src/tree/roadmapEvidence.ts'));

test('memory archives have scoped checks and do not certify unbuilt integrations',()=>{
 for(const [planet,check] of [[1,'owner'],[2,'semantic'],[3,'episodes'],[4,'working']]){
  assert.ok(checks[`T7.p${planet}`].includes(`memory_${check}_regression`));
 }
 assert.ok(checks['T7.p2.m1'].includes('memory_e2e'));
 assert.ok(!checks['T7.p3']?.includes('memory_e2e'));
 assert.equal(byId.get('T7.p3.m2').status,'planned');
 assert.equal(checks['T7.p3.m2'],undefined);
 assert.equal(byId.get('T7.p4').status,'partial');
 for(const id of ['T7.p1','T7.p2','T7.p3.m1','T7.p4.m1','T7.p4.m2'])
  assert.equal(developmentIndicator(byId.get(id)).label,'Implementato (dichiarato)');
});

test('the agreed library and registers remain future even with passing parent evidence',()=>{
 const future=nodes.filter(n=>/^T7\.p(?:[6-9]|10)(?:\.|$)/.test(n.id));
 assert.equal(future.length,17);
 const sha='a'.repeat(40);
 const health={catalog:[{id:'memory_e2e',kind:'e2e',releaseScoped:true}],latest:{memory_e2e:{
  status:'pass',at:new Date().toISOString(),commit:sha,environment:'debian-api',
 }}};
 for(const node of future){
  assert.ok(['planned','idea'].includes(node.status),node.id);
  assert.equal(checks[node.id],undefined,node.id);
  assert.equal(starTone(node,health,sha,checks,nodes),'unknown',node.id);
  assert.ok(!node.observations.some(o=>o.type==='manual_pass'),node.id);
 }
 assert.equal(byId.get('T7.p8.m3').status,'idea');
 assert.equal(byId.get('T7').timeline.present.runtimeVerified,false);
 assert.ok(snapshot.relations.some(r=>r.from==='T6'&&r.to==='T7.p9'));
});

test('focused memory map retains all ten planets, moons and exact parent edges',async()=>{
 const source=read('../src/tree/Constellation.tsx');
 const {focusLayout}=await load(source.slice(source.indexOf('export type TreePoint'),source.indexOf('type Props=')));
 const result=focusLayout(nodes,'T7');
 assert.equal(result.points.filter(p=>p.kind==='planet').length,10);
 const expected=nodes.filter(n=>n.id==='T7'||n.parent==='T7'||byId.get(n.parent)?.parent==='T7');
 assert.deepEqual(new Set(result.points.map(p=>p.node.id)),new Set(expected.map(n=>n.id)));
 for(const p of result.points)assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
 for(const edge of result.edges)assert.equal(byId.get(edge.to).parent,edge.from);
});
