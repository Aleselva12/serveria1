import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import ts from "typescript";

const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const source=read("../src/tree/roadmapEvidence.ts");
const compiled=ts.transpileModule(source,{compilerOptions:{
  target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,
}}).outputText;
const {checkState,verifiedLiveE2E,starTone}=await import("data:text/javascript;base64,"+Buffer.from(compiled).toString("base64"));

const sha="a".repeat(40),old="b".repeat(40);
const now=()=>new Date().toISOString();
const definition=(id,kind="e2e",frequency="on_release")=>({
  id,title:id,component:"cora",kind,stage:"Unit test",frequency,
  dependsOn:[],description:"",automated:frequency==="5m"
});
const result=(id,commit=sha,environment="debian-api",status="pass",at=now())=>({
  id,status,detail:"",source:"test",environment,commit,durationMs:1,at
});
const dashboard=(entries=[])=>({
  catalog:entries.map(e=>e[0]),components:{cora:"Cora"},latest:Object.fromEntries(entries.map(e=>[e[0].id,e[1]])),
  history:[],historyStore:"postgresql",updatedAt:now()
});
const node={id:"A1",classification:"star",status:"partial",priority:"unknown",timeline:{future:[]}};
const mapping={A1:["chat_contract","chat_e2e"]};

test("a passing old SHA is labelled outdated, never a passing current release",()=>{
  const d=definition("chat_e2e"),r=result("chat_e2e",old);
  assert.equal(checkState(d,r,sha),"outdated");
  assert.equal(verifiedLiveE2E(d,r,sha),false);
});
test("commit unknown and results with missing SHA cannot certify live Debian",()=>{
  const d=definition("chat_e2e");
  assert.equal(checkState(d,result(d.id),null),"unattributed");
  assert.equal(checkState(d,result(d.id,null),sha),"unattributed");
  assert.equal(checkState(d,result(d.id,"a".repeat(8)),sha),"unattributed");
});
test("a CI-only E2E never certifies live Debian even for identical SHA",()=>{
  const d=definition("chat_e2e"),r=result(d.id,sha,"ci-synthetic");
  assert.equal(checkState(d,r,sha),"pass");
  assert.equal(verifiedLiveE2E(d,r,sha),false);
  assert.equal(verifiedLiveE2E(d,result(d.id,sha,"debian-api"),sha),true);
});
test("only fully checked current-commit results with matching Debian E2E can color green",()=>{
  const contract=definition("chat_contract","contract","5m"),e2e=definition("chat_e2e");
  const positive=dashboard([[contract,result(contract.id)],[e2e,result(e2e.id)]]);
  assert.equal(starTone(node,positive,sha,mapping),"ok");
  assert.equal(starTone(node,positive,old,mapping),"unknown");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id)]]),sha,mapping),"unknown");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id)],[e2e,result(e2e.id,sha,"ci")]]),sha,mapping),"unknown");
});
test("old failures are historical, current failures are red; known issues remain orange",()=>{
  const contract=definition("chat_contract","contract","5m"),e2e=definition("chat_e2e");
  const oldFailure=dashboard([[contract,result(contract.id,old,"debian-api","fail")],[e2e,result(e2e.id,old)]]);
  assert.equal(starTone(node,oldFailure,sha,mapping),"unknown");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id,sha,"debian-api","fail")]]),sha,mapping),"problem");
  assert.equal(starTone({...node,knownIssues:["Problema da verificare"]},oldFailure,sha,mapping),"minor");
});
test("old automatic checks expire and cannot be considered current",()=>{
  const contract=definition("chat_contract","contract","5m");
  const past=new Date(Date.now()-11*60*1000).toISOString();
  assert.equal(checkState(contract,result(contract.id,sha,"debian-api","pass",past),sha),"stale");
});
test("future Gmail entries have no test runner and never show a fabricated pass",()=>{
  const catalog=read("../../core/health_catalog.py");
  for(const id of ["gmail_contract","gmail_e2e"]){
    assert.match(catalog,new RegExp('entry\\("'+id+'"[\\s\\S]*?"to_implement"'));
    const def=definition(id,id.endsWith("_e2e")?"e2e":"contract","to_implement");
    assert.equal(checkState(def,result(id),sha),"planned");
    assert.equal(verifiedLiveE2E(def,result(id),sha),false);
  }
  assert.match(catalog,/"gmail": "Email e Gmail"/);
  const runner=read("../../core/project_checks.py");
  assert.match(runner,/if item\["automated"\]/);
  assert.ok(!runner.includes('def _gmail('));
});
test("the roadmap uses active release and shared checks without a second test runner",()=>{
  const view=read("../src/tree/TreeHome.tsx");
  assert.ok(view.includes('api.healthDashboard()'));
  assert.ok(view.includes('"/api/v1/system/update"'));
  assert.ok(view.includes("verifiedLiveE2E"));
  assert.ok(!view.includes("api.runTests("));
  assert.ok(view.includes("Commit installato"));
});
