import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync,existsSync} from "node:fs";
import ts from "typescript";
import {fileURLToPath} from "node:url";
const read=(path)=>readFileSync(new URL(path,import.meta.url),"utf8");
const dataUrl=(code)=>"data:text/javascript;base64,"+Buffer.from(ts.transpileModule(code,{
 compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}
}).outputText).toString("base64");
const snap=JSON.parse(read("../src/tree/cora-plan.snapshot.json")),nodes=snap.nodes;
const svgSource=read("../src/tree/Constellation.tsx");
const part=svgSource.slice(svgSource.indexOf("export type TreePoint"),svgSource.indexOf("type Props="));
const {layout,focusLayout}=await import(dataUrl(part));
const {codeLinks,pageLinks,sourceUrl}=await import(dataUrl(read("../src/tree/codeLinks.ts")));
const byId=new Map(nodes.map(n=>[n.id,n]));

test("clicking any star has a dedicated 2D scene with ONLY its planets and moons",()=>{
 for(const star of nodes.filter(n=>n.classification==="star")){
  const {points,edges}=focusLayout(nodes,star.id);
  const starPoints=points.filter(p=>p.kind==="star");
  assert.deepEqual(starPoints.map(p=>p.node.id),[star.id],"Extra stars in "+star.id);
  const descendants=nodes.filter(n=>n.parent===star.id);
  assert.equal(points.filter(p=>p.kind==="planet").length,descendants.length);
  for(const planet of descendants){
    assert.ok(points.some(p=>p.node.id===planet.id&&p.kind==="planet"));
    const moonCount=nodes.filter(n=>n.parent===planet.id).length;
    assert.equal(points.filter(p=>p.node.parent===planet.id&&p.kind==="moon").length,moonCount);
    assert.ok(edges.some(e=>e.from===star.id&&e.to===planet.id));
  }
 }
});
test("the full tree has all 46 canonical stars and no fabricated trunk chain",()=>{
 const {points,edges}=layout(nodes);
 assert.equal(points.filter(p=>p.kind==="star").length,46);
 assert.deepEqual(new Set(points.filter(p=>p.kind==="star").map(p=>p.node.id)),new Set(nodes.filter(n=>n.classification==="star").map(n=>n.id)));
 assert.equal(points.filter(p=>p.kind==="branch").length,7);
 assert.equal(points.filter(p=>p.kind==="area").length,6);
 assert.ok(!edges.some(e=>e.kind==="child"&&e.from.startsWith("T")&&e.to.startsWith("T")));
});
test("C1 and F1 orbit preserve historical ideas and exact check boundaries",()=>{
 const calendar=focusLayout(nodes,"C1").points.map(p=>p.node.id);
 for(const id of ["C1a","C1b","C1c","C1d","C1e"])assert.ok(calendar.includes(id));
 const worker=focusLayout(nodes,"worker").points.map(p=>p.node.id);
 for(const id of ["installare","assegnare"])assert.ok(worker.includes(id));
 assert.equal(byId.get("C1e").status,"idea");
});
test("planned objectives are grey and visible as labelled map stars, not hidden future categories",()=>{
 const goals=nodes.filter(n=>n.classification==="star"&&["planned","idea"].includes(n.status));
 assert.equal(goals.length,5);
 assert.deepEqual(goals.map(n=>n.id).sort(),["E1","E2","F2","R1.4","T14"].sort());
 const css=read("../src/tree/tree.css");
 const ui=read("../src/tree/TreeHome.tsx");
 assert.ok(css.includes(".rm2-point.tone-problem")&&css.includes(".rm2-point.tone-ok"));
 assert.ok(css.includes(".rm2-point.is-objective .rm2-core"));
 assert.ok(css.includes(".rm2-point.tone-unknown"));
 assert.ok(svgSource.includes("◇ OBIETTIVO"));
 assert.ok(ui.includes("STELLE OBIETTIVO")&&ui.includes('setFocusId(parent.id)'));
 assert.ok(ui.includes('onFocusChange'));
 assert.ok(svgSource.includes("onPointerDown")&&svgSource.includes("onWheel"));
});
test("reviewed source links exist in the serveria1 repository; no source URLs are invented",()=>{
 let validated=0;
 for(const [nodeId,links] of Object.entries(codeLinks)){
  assert.ok(byId.has(nodeId),"Wrong node in source registry: "+nodeId);
  for(const link of links){
    assert.match(sourceUrl(link),/^https:\/\/github\.com\/Aleselva12\//);
    if(link.repo)continue;
    const file=fileURLToPath(new URL("../../"+link.path,import.meta.url));
    assert.ok(existsSync(file),"Broken source link "+nodeId+" → "+link.path);
    validated++;
  }
 }
 assert.ok(validated>=40);
 for(const [nodeId,page] of Object.entries(pageLinks)){
  assert.ok(byId.has(nodeId));
  assert.match(page.hash,/^#[a-z][a-z-]*$/);
 }
});
test("no new check runner or autonomous structural mutations were added to the map",()=>{
 const ui=read("../src/tree/TreeHome.tsx");
 assert.ok(ui.includes("api.healthDashboard()"));
 assert.ok(!ui.includes("api.runTests("));
 assert.ok(!ui.includes("updateRoadmap("));
 assert.ok(ui.includes("knownIssues")&&ui.includes("timeline.future"));
 assert.ok(ui.includes("selectedEvidence"));
});
