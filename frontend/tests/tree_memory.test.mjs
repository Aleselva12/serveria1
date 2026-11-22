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
 assert.equal(byId.get('T7.p3.m2').status,'partial');
 assert.deepEqual(checks['T7.p3.m2'],['memory_evidence_regression']);
 assert.equal(byId.get('T7.p4').status,'partial');
 for(const id of ['T7.p1','T7.p2','T7.p3.m1','T7.p4.m1','T7.p4.m2'])
  assert.equal(developmentIndicator(byId.get(id)).label,'Implementato (dichiarato)');
});

test('memory planets require attributed evidence and preserve future scope',()=>{
 const library=nodes.filter(n=>/^T7\.p(?:[6-9]|10)(?:\.|$)/.test(n.id));
 assert.equal(library.length,17);
 const sha='a'.repeat(40);
 const ids=['memory_evidence_regression','memory_library_e2e'];
 const projectHealth={catalog:ids.map(id=>({id,kind:'e2e',releaseScoped:true})),latest:
  Object.fromEntries(ids.map(id=>[id,{status:'pass',at:new Date().toISOString(),commit:sha,environment:'debian-verifier'}]))};
 for(const node of library){
  assert.ok(!node.observations.some(o=>o.type==='manual_pass'),node.id);
  assert.ok(['partial','idea'].includes(node.status),node.id);
  assert.notEqual(starTone(node,projectHealth,'b'.repeat(40),checks,nodes),'ok',node.id);
 }
 for(const planet of [5,6,7,8,9,10]){
  const node=byId.get(`T7.p${planet}`);
  assert.ok(checks[node.id].length);
  assert.equal(starTone(node,projectHealth,sha,checks,nodes),'ok',node.id);
 }
 assert.equal(starTone(byId.get('T7.p8.m3'),projectHealth,sha,checks,nodes),'unknown');
 assert.equal(byId.get('T7.p5.m2').status,'planned');
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
