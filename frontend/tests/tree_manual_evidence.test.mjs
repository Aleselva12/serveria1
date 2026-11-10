import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";
import {readFileSync} from "node:fs";

const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const nodes=JSON.parse(read("../src/tree/cora-plan.snapshot.json")).nodes;
const byId=new Map(nodes.map(n=>[n.id,n]));
const source=read("../src/tree/roadmapEvidence.ts");
const transpiled=ts.transpileModule(source,{compilerOptions:{
  target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,
}}).outputText;
const {starTone,manualEvidence,verificationSummary}=await import("data:text/javascript;base64,"+Buffer.from(transpiled).toString("base64"));
const greenIds=["T1.p1.m1","T8.p2.m1","T8.p3.m1","T8.p3.m2",
  "R3.1.p1.m2","R1.2.p2.m2","R1.2.p3.m1","R1.2.p3.m2",
  "assegnare.m1","assegnare.m2","installare.m2","T10.p1.m1","T10.p3.m1","T6.p1.m2"];
const yellowIds=["worker.p4.m2","T8.p2.m2","R3.2.p2.m1","T1.p1.m2","T6.p2.m1"];

test("every 8-Nov owner observation has a date, exact known node and an explicit narrow scope",()=>{
 assert.equal(new Set(nodes.map(n=>n.id)).size,nodes.length);
 for(const id of greenIds){
  assert.ok(byId.has(id));
  const record=manualEvidence(byId.get(id));
  assert.equal(record?.kind,"ok",id);
  assert.equal(record?.date,"2026-11-08",id);
  assert.ok(record.text.length>35,id);
  assert.equal(starTone(byId.get(id),null,null,{},nodes),id==="T1.p1.m1"?"minor":"ok",id);
 }
 for(const id of yellowIds){
  const record=manualEvidence(byId.get(id));
  assert.equal(record?.kind,"plan",id);
  assert.equal(record?.date,"2026-11-08",id);
  assert.equal(starTone(byId.get(id),null,null,{},nodes),"plan",id);
 }
});
test("manual evidence does not falsely promote an entire partial star",()=>{
 for(const id of ["T1","T6","T8","T10","worker","R1.2"]){
  const star=byId.get(id);
  assert.equal(star.status,"partial");
  assert.notEqual(starTone(star,null,null,{},nodes),"ok",id);
  assert.equal(star.timeline?.present?.runtimeVerified,false);
 }
 assert.ok(byId.get("T1.p1.m1").knownIssues.some(x=>x.includes("lento")));
 assert.equal(byId.get("T1").knownIssues?.length||0,0,"Latency belongs to its exact owner, not a duplicate star issue");
 assert.equal((byId.get("worker").knownIssues||[]).length,0);
 assert.equal((byId.get("T8").knownIssues||[]).length,0);
});
test("manual check does not override an actual failing check attributed to installed Debian commit",()=>{
 const n=byId.get("T8.p3.m1");
 const sha="a".repeat(40);
 const health={
  catalog:[{id:"specific",kind:"e2e",frequency:"manual",automated:false,maxAgeSeconds:86400}],
  latest:{specific:{id:"specific",status:"fail",at:new Date().toISOString(),commit:sha,environment:"debian-api"}},
 };
 assert.equal(starTone(n,health,sha,{"T8.p3.m1":["specific"]},nodes),"problem");
});
test("outstanding GPU proof, offline HTTP 502 and hardware upgrades are not mislabelled as runtime failures",()=>{
 assert.ok(manualEvidence(byId.get("worker.p4.m2")).text.includes("HTTP 502"));
 assert.ok(manualEvidence(byId.get("worker.p4.m2")).text.includes("fallback locale"));
 assert.ok(byId.get("R1.2").timeline.future.some(s=>s.includes("GPU")));
 assert.ok(byId.get("R1.1").timeline.future.some(s=>s.includes("hardware")));
 assert.equal(starTone(byId.get("R1.1.p2"),null,null,{},nodes),"plan");
});
test("untested is neutral gray, not red; manual success has a clear limited label",()=>{
 const ui=read("../src/tree/TreeHome.tsx");
 const css=read("../src/tree/tree.css");
 assert.match(source,/unverified: "Grigio · non collaudato"/);
 assert.match(css,/\.tone-unverified,.rm2-point.tone-unverified\{--rm2-tone:var\(--rm2-unknown\)\}/);
 assert.match(ui,/Verde · verificato manualmente/);
 assert.match(ui,/Non sostituisce i test del catalogo/);
 assert.match(verificationSummary(byId.get("T8.p3.m1"),null,null,{},nodes),/manuale circoscritta/);
 assert.equal(manualEvidence(byId.get("T1.p1.m1")).kind,"ok","Historical success stays recorded");
 assert.match(verificationSummary(byId.get("T1.p1.m1"),null,null,{},nodes),/Attenzione/,"Open latency issue must remain visible despite historical success");
 assert.match(verificationSummary(byId.get("worker.p4.m2"),null,null,{},nodes),/Rifinitura da eseguire/);
});
