import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const model=readFileSync(new URL('../src/tree/model.ts',import.meta.url),'utf8');
const source=readFileSync(new URL('../src/tree/Constellation.tsx',import.meta.url),'utf8');
const snapshot=JSON.parse(readFileSync(new URL('../src/tree/cora-plan.snapshot.json',import.meta.url),'utf8'));
const {nodes,relations}=snapshot;
const mod=code=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64');
const {severity,checks}=await import(mod(model));
const first=source.indexOf('export type TreePoint');
const last=source.indexOf('type Props=');
assert.ok(first>=0&&last>first);
const {layout,trunkLayout,trunkFlows}=await import(mod(source.slice(first,last)));

test('all canonical 45 stars, 151 planets and 304 moons survive in ServerIA',()=>{
 const ids=new Set(nodes.map(n=>n.id));
 assert.equal(ids.size,nodes.length);
 assert.equal(nodes.length,515);
 assert.equal(nodes.filter(n=>n.classification==='star').length,45);
 assert.equal(nodes.filter(n=>n.classification==='planet').length,151);
 assert.equal(nodes.filter(n=>n.classification==='moon').length,304);
 assert.equal(relations.length,37);
 for(const id of [...Object.keys(checks),...nodes.map(n=>n.parent).filter(Boolean),...relations.flatMap(r=>[r.from,r.to])])
   assert.ok(ids.has(id),'Missing id '+id);
 for(const id of ['immich','nextcloud','magazzino','worker','installare','assegnare','C1a','C1b','C1c','C1d','C1e'])
   assert.ok(ids.has(id),'Lost historical ID '+id);
});
test('V2 notes preserve actual issues, future ideas and provenance without inventing green health',()=>{
 const byId=new Map(nodes.map(n=>[n.id,n]));
 assert.ok(byId.get('T1').knownIssues.length>0);
 assert.ok(byId.get('F2').timeline.future.some(t=>t.includes('SQL')));
 assert.equal(byId.get('C1d').status,'idea');
 assert.equal(byId.get('C1e').status,'idea');
 for(const n of nodes.filter(n=>n.classification==='star')){
   assert.equal(n.priority,'unknown');
   assert.equal(n.timeline.present.runtimeVerified,false);
   assert.ok(Array.isArray(n.timeline.past));
   assert.ok(Array.isArray(n.knownIssues));
 }
});
test('old severity helper does not propagate problems across unrelated branches',()=>{
 const a={id:'A',priority:'ok'},b={id:'B',priority:'unknown'},p={id:'p',parent:'A'},m={id:'m',parent:'p',priority:'minor'},all=[a,b,p,m];
 assert.equal(severity(a,all,new Set()),'minor');
 assert.equal(severity(a,all,new Set(['m'])),'problem');
 assert.equal(severity(b,all,new Set(['m'])),'unknown');
});
test('constellation keeps free trunk stars rather than connecting them in a fake chain',()=>{
 const {points,edges}=layout(nodes);
 assert.equal(points.length,58); // 45 stars, 6 roots, 7 branches
 assert.equal(points.filter(p=>p.kind==='star').length,45);
 const trunks=points.filter(p=>p.node.parent==='tronco');
 assert.equal(trunks.length,13);
 assert.ok(new Set(trunks.map(p=>p.x)).size>=7);
 assert.ok(new Set(trunks.map(p=>p.y)).size>=7);
 assert.ok(trunks.every(p=>p.y>350&&p.y<900));
 assert.ok(points.filter(p=>p.kind==='branch').every(p=>p.y<350));
 assert.ok(points.filter(p=>p.kind==='area').every(p=>p.y>1000));
 assert.ok(!edges.some(e=>e.kind==='child'&&e.from.startsWith('T')&&e.to.startsWith('T')));
 for(const e of edges.filter(e=>e.kind==='flow'))assert.ok(trunkFlows[e.from]?.includes(e.to));
 for(const star of nodes.filter(n=>n.classification==='star'&&n.parent!=='tronco'))
   assert.ok(edges.some(e=>e.kind==='child'&&e.from===star.parent&&e.to===star.id),'Unconnected star '+star.id);
 assert.deepEqual(trunkLayout.T6,[571,614]);
});
test('frontend V2 inspector shows structured work, problems, tests and time without duplicate test runners',()=>{
 const ui=readFileSync(new URL('../src/tree/TreeHome.tsx',import.meta.url),'utf8');
 for(const q of ['Copia schema','Presente','Problemi','Futuro','Storia','PIANETI','TEST COLLEGATI','RELAZIONI','W1 → W2 → W3','api.healthDashboard()'])
   assert.ok(ui.includes(q),'Missing panel section '+q);
 assert.ok(!ui.includes('api.runTests('),'Roadmap must not trigger duplicated test execution');
 assert.ok(ui.includes('knownIssues')&&ui.includes('timeline.future'));
 assert.ok(ui.includes('evidenceStatus')&&ui.includes('commit'));
});
