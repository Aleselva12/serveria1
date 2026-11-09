import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const model=readFileSync(new URL('../src/tree/model.ts',import.meta.url),'utf8');
const source=readFileSync(new URL('../src/tree/Constellation.tsx',import.meta.url),'utf8');
const snapshot=JSON.parse(readFileSync(new URL('../src/tree/cora-plan.snapshot.json',import.meta.url),'utf8'));
const projectStatus=JSON.parse(readFileSync(new URL('../src/project-status.generated.json',import.meta.url),'utf8'));
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
 assert.ok(relations.length>=37,'Baseline conceptual relations must survive');
 assert.equal(new Set(relations.map(r=>[r.from,r.to,r.kind].join('|'))).size,relations.length,'Duplicate semantic relations');
 for(const id of [...Object.keys(checks),...nodes.map(n=>n.parent).filter(Boolean),...relations.flatMap(r=>[r.from,r.to])])
   assert.ok(ids.has(id),'Missing id '+id);
 for(const id of ['immich','nextcloud','magazzino','worker','installare','assegnare','C1a','C1b','C1c','C1d','C1e'])
   assert.ok(ids.has(id),'Lost historical ID '+id);
});
test('V2 notes preserve actual issues, future ideas and provenance without inventing green health',()=>{
 const byId=new Map(nodes.map(n=>[n.id,n]));
 assert.ok(byId.get('T1.p1.m1').knownIssues.some(t=>t.includes('qwen3')));
 assert.ok(byId.get('F2').timeline.future.some(t=>t.includes('SQL')));
 assert.equal(byId.get('C1d').status,'idea');
 assert.equal(byId.get('C1e').status,'idea');
 for(const n of nodes.filter(n=>n.classification==='star')){
   assert.equal(n.priority,'unknown');
   assert.equal(n.timeline.present.runtimeVerified,false);
   assert.ok(Array.isArray(n.timeline.past));
   assert.ok(n.knownIssues===undefined||Array.isArray(n.knownIssues));
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
test('frontend V2 inspector shows structured work, live project status and evidence without duplicate test runners',()=>{
 const ui=readFileSync(new URL('../src/tree/TreeHome.tsx',import.meta.url),'utf8');
 for(const q of ['Copia schema','Presente','Problemi','Futuro','Storia','PIANETI','TEST COLLEGATI','RELAZIONI','SEQUENZA OPERATIVA · AUTO','api.healthDashboard()','homeRoadmap.nextWork','Stato progetto'])
   assert.ok(ui.includes(q),'Missing panel section '+q);
 assert.ok(!ui.includes('api.runTests('),'Roadmap must not trigger duplicated test execution');
 assert.ok(!ui.includes('source.nextWork'),'Current work sequence must come from project-status, not the qwe snapshot');
 assert.ok(ui.includes('knownIssues')&&ui.includes('timeline.future'));
 const evidence=readFileSync(new URL('../src/tree/roadmapEvidence.ts',import.meta.url),'utf8');
 assert.ok(ui.includes('checkState')&&ui.includes('activeRelease')&&evidence.includes('verifiedLiveE2E')&&evidence.includes('activeCommit'));
});

test('roadmap references current Home goals and shares orchestrator structural evidence',()=>{
 const goalIds=new Set(projectStatus.goals.map(g=>g.id));
 for(const node of nodes)
   for(const ref of node.roadmapRefs||[]) assert.ok(goalIds.has(ref),'Unknown roadmapRef '+node.id+' → '+ref);
 const ordered=[...projectStatus.nextWork].sort((a,b)=>a.order-b.order);
 assert.equal(new Set(ordered.map(w=>w.id)).size,ordered.length);
 assert.deepEqual(ordered.map(w=>w.id),projectStatus.nextWork.map(w=>w.id));
 assert.equal(projectStatus.nextWork.find(w=>w.id==='W1').status,'COMPLETATO · 04/11/2026');
 assert.equal(projectStatus.nextWork.find(w=>w.id==='W2').status,'PROSSIMO LAVORO');
 for(const id of ['T1','T2','T3','T4','T5','T6','T10','T11'])
   assert.ok(checks[id]?.includes('orchestrator_v1_contract'),'Missing W1 structural evidence on '+id);
});

test('documented issues have one owner and star-level views can find descendant issues',()=>{
 const byId=new Map(nodes.map(n=>[n.id,n]));
 const issues=nodes.flatMap(n=>(n.knownIssues||[]).map(text=>({id:n.id,text})));
 assert.equal(issues.length,19,'Do not lose or duplicate the original 19 documented issues');
 assert.equal(new Set(issues.map(x=>x.text)).size,issues.length);
 assert.equal(nodes.filter(n=>n.classification==='star'&&n.knownIssues?.length).length,2);
 for(const [id,owner] of [['C1b.m2','C1'],['R5.2.p3.m1','R5.2'],['B3.p1.m2','B3']]){
  assert.ok(byId.get(id)?.knownIssues?.length,'Missing scoped issue '+id);
  let current=byId.get(id);
  while(current&&current.id!==owner)current=byId.get(current.parent);
  assert.equal(current?.id,owner,'Issue no longer belongs to original star');
 }
 const ui=readFileSync(new URL('../src/tree/TreeHome.tsx',import.meta.url),'utf8');
 assert.ok(ui.includes('scopedIssues(n.id).length'),'Issue filter must include descendant problems');
 assert.ok(ui.includes('const issues=scopedIssues(root.id)'),'Inspector must include scoped problems');
});

test('semantic cross-node relations retain identity and do not imply independent test success',()=>{
 const allowed=new Set(['uses','depends_on','communicates_with','produces_for','verified_by','shares_evidence_with']);
 const ids=new Set(nodes.map(n=>n.id));
 for(const relation of relations){
  assert.ok(allowed.has(relation.kind),'Unexpected relation type '+relation.kind);
  assert.ok(ids.has(relation.from)&&ids.has(relation.to));
  assert.notEqual(relation.from,relation.to);
  assert.ok(relation.note);
 }
 assert.ok(relations.some(r=>r.kind==='shares_evidence_with'));
 assert.ok(relations.some(r=>r.kind==='verified_by'));
});

test('planner code review updates only the documented plan schema, not scheduling or runtime certification',()=>{
 const byId=new Map(nodes.map(n=>[n.id,n]));
 for(const id of ['T9','T9.p1','T9.p1.m1']){
  const n=byId.get(id);
  assert.equal(n.status,'partial',id+' must reflect the existing plan schema');
  assert.ok(n.observations?.some(o=>o.type==='code_review'&&o.text.includes('core/plans.py')));
 }
 for(const id of ['T9.p1.m2','T9.p2','T9.p3'])assert.equal(byId.get(id).status,'planned',id+' must not claim implemented scheduling');
 assert.equal(byId.get('T9').timeline.present.runtimeVerified,false);
});

test('V3 schema preserves 515 canonical nodes and 19 uniquely owned legacy issues',async()=>{
 const {legacyIssues,validateAtlasOverlay}=await import(mod(model));
 const issues=legacyIssues(nodes);
 assert.equal(snapshot.v3.schemaVersion,3);
 assert.equal(nodes.length,515);
 assert.equal(issues.length,19);
 assert.deepEqual(snapshot.v3.issues,issues);
 assert.equal(new Set(issues.map(i=>i.id)).size,19);
 assert.ok(issues.every(i=>i.kind==='unclassified'&&i.state==='open'&&i.source==='legacy'));
 assert.equal(snapshot.v3.migration.nodeHierarchy,'unchanged');
 assert.equal(snapshot.v3.migration.relations.startsWith('top-level'),true);
 const overlay={...snapshot.v3,relations};
 assert.deepEqual(validateAtlasOverlay(overlay,nodes),[]);
});

test('V3 issue ownership and evidence validation rejects unknown references and duplicates',async()=>{
 const {validateAtlasOverlay}=await import(mod(model));
 const overlay={schemaVersion:3,nodeResponsibilities:{},issues:[
  {id:'i',ownerNodeId:'not-a-node',title:'Example',kind:'bug',state:'open',affectedNodeIds:['also-unknown'],evidenceIds:['missing']},
  {id:'i',ownerNodeId:'A1',title:'Example again',kind:'bug',state:'open'}
 ],evidence:[],relations:[]};
 const errors=validateAtlasOverlay(overlay,nodes).join(' | ');
 for(const phrase of ['Duplicate issue','Unknown issue owner','Unknown affected node','Unknown evidence'])
  assert.ok(errors.includes(phrase),phrase);
});
