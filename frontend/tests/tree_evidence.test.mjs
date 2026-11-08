import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import ts from "typescript";

const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const source=read("../src/tree/roadmapEvidence.ts");
const compiled=ts.transpileModule(source,{compilerOptions:{
  target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,
}}).outputText;
const {checkState,verifiedLiveE2E,starTone,verificationSummary}=await import("data:text/javascript;base64,"+Buffer.from(compiled).toString("base64"));

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
  assert.equal(starTone(node,positive,old,mapping),"unverified");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id)]]),sha,mapping),"unverified");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id)],[e2e,result(e2e.id,sha,"ci")]]),sha,mapping),"unverified");
});
test("old failures are historical, partial failures are orange; known issues remain orange",()=>{
  const contract=definition("chat_contract","contract","5m"),e2e=definition("chat_e2e");
  const oldFailure=dashboard([[contract,result(contract.id,old,"debian-api","fail")],[e2e,result(e2e.id,old)]]);
  assert.equal(starTone(node,oldFailure,sha,mapping),"unverified");
  assert.equal(starTone(node,dashboard([[contract,result(contract.id,sha,"debian-api","fail")]]),sha,mapping),"minor");
  assert.equal(starTone({...node,knownIssues:["Problema da verificare"]},oldFailure,sha,mapping),"minor");
});
test("old automatic checks expire and cannot be considered current",()=>{
  const contract=definition("chat_contract","contract","5m");
  const past=new Date(Date.now()-11*60*1000).toISOString();
  assert.equal(checkState(contract,result(contract.id,sha,"debian-api","pass",past),sha),"stale");
});
test("Gmail runnable scope is explicit and simulated drafts never claim a live account",()=>{
  const catalog=read("../../core/health_catalog.py");
  assert.match(catalog,/"Gmail: bozza MIME con trasporto simulato"/);
  const def=definition("gmail_e2e","synthetic");
  assert.equal(verifiedLiveE2E(def,result(def.id),sha),false);
});

test("the roadmap uses active release and shared checks without a second test runner",()=>{
  const view=read("../src/tree/TreeHome.tsx");
  assert.ok(view.includes('api.healthDashboard()'));
  assert.ok(view.includes('"/api/v1/system/update"'));
  assert.ok(view.includes('"runtimeCommit" in health'));
  assert.ok(view.includes('health.runtimeCommit.toLowerCase()===activeCommit.toLowerCase()'));
  assert.ok(view.includes("verifiedLiveE2E"));
  assert.ok(!view.includes("api.runTests("));
  assert.ok(view.includes("Commit installato"));
});


test("manual priorities never hide live failures or fabricate green",()=>{
  const d=definition("chat_e2e");
  for(const priority of ["ok","minor","plan","problem"]){
    const n={...node,priority};
    assert.equal(starTone(n,dashboard([[d,result(d.id,sha,"debian-api","fail")]]),sha,{A1:[d.id]}),"problem");
    assert.equal(starTone(n,null,sha,{A1:[d.id]}),"unverified");
  }
});
test("CI failures are not live failures; missing live proof is explicitly unverified",()=>{
  const d=definition("chat_e2e");
  assert.equal(starTone(node,dashboard([[d,result(d.id,sha,"ci","fail")]]),sha,{A1:[d.id]}),"unverified");
  assert.equal(checkState(d,result(d.id,sha,"debian-api","pass",new Date(Date.now()+3600000).toISOString()),sha),"unknown");
});
test("functional evidence expires too",()=>{
  const d=definition("chat_e2e");
  assert.equal(checkState(d,result(d.id,sha,"debian-api","pass",new Date(Date.now()-25*3600000).toISOString()),sha),"stale");
});

test("contract checks never certify functionality or hide known issues",()=>{
 const d=definition("orchestrator_v1_contract","contract","5m");
 const n={...node,knownIssues:["Sviluppo futuro ancora documentato"]};
 assert.equal(starTone(n,dashboard([[d,result(d.id)]]),sha,{A1:[d.id]}),"minor");
 assert.equal(verifiedLiveE2E(d,result(d.id),sha),false);
 assert.equal(starTone(n,dashboard([[d,result(d.id,sha,"debian-api","fail")]]),sha,{A1:[d.id]}),"minor");
});

test("focused worker nodes update only covered scopes; GPU is not certified by inference",async()=>{
 const {checks}=await import("data:text/javascript;base64,"+Buffer.from(ts.transpileModule(read("../src/tree/model.ts"),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText).toString("base64"));
 const d=definition("desktop_e2e");
 const health=dashboard([[d,result(d.id)]]);
 const moon={classification:"moon",status:"partial"};
 assert.equal(starTone({...moon,id:"R1.2.p3.m1"},health,sha,checks),"ok");
 assert.notEqual(starTone({...moon,id:"R1.2.p1.m1"},health,sha,checks),"ok");
});

 test("synthetic and HTTP successes stay unverified; child risk propagates without certifying siblings",()=>{
  for(const kind of ["synthetic","preflight","contract"]){
   const d=definition("limited",kind);
   assert.equal(starTone(node,dashboard([[d,result(d.id)]]),sha,{A1:[d.id]}),"plan");
  }
  const d=definition("real"),h=dashboard([[d,result(d.id)]]);
  const children=[node,{id:"p",parent:"A1",classification:"planet",status:"partial",knownIssues:["Rischio"]}];
  assert.equal(starTone(node,h,sha,{A1:[d.id]},children),"minor");
  assert.equal(starTone({...children[1],knownIssues:[]},h,sha,{A1:[d.id]},children),"plan");
 });

test("future scope does not block a valid live E2E; partial children remain yellow",()=>{
 const d=definition("real"),h=dashboard([[d,result(d.id)]]),m={A1:[d.id]};
 const future={id:"future",parent:"A1",classification:"planet",status:"planned"};
 const partial={id:"partial",parent:"A1",classification:"planet",status:"partial"};
 const all=[node,future,partial];
 assert.equal(starTone(future,h,sha,m,all),"unknown");
 assert.equal(starTone(partial,h,sha,m,all),"plan");
 assert.equal(starTone({...node,timeline:{future:["An optional upgrade"]}},h,sha,m,all),"ok");
 const present={...future,status:"present"};
 assert.equal(starTone(present,h,sha,m,[node,present]),"unverified");
 assert.equal(starTone(node,h,sha,m,[node,present]),"plan");
});

test("a mapped E2E without valid proof remains neutral and unverified",()=>{
 const d=definition("real"),h=dashboard([[d,undefined]]),m={A1:[d.id]};
 assert.equal(starTone(node,h,sha,m),"unverified");
 assert.match(verificationSummary(node,h,sha,m),/Non provato/);
 assert.equal(starTone(node,dashboard([[d,result(d.id)]]),sha,m),"ok");
 assert.match(verificationSummary(node,dashboard([[d,result(d.id)]]),sha,m),/Collaudo reale superato/);
});

test("root areas and branches aggregate actual children without claiming their own E2E",()=>{
 for(const group of [{id:"group",classification:"area"},{id:"group",role:"ramo"}]){
  const future={id:"future",parent:"group",classification:"star",status:"planned"};
  const partial={id:"partial",parent:"group",classification:"star",status:"partial"};
  const present={id:"present",parent:"group",classification:"star",status:"present"};
  const d=definition("real"),m={present:[d.id]};
  const all=[group,future,partial,present];
  const h=dashboard([[d,result(d.id)]]);
  assert.equal(starTone(group,h,sha,m,all),"plan");
  assert.equal(starTone(group,h,sha,m,[group,partial]),"plan");
  assert.match(verificationSummary(group,h,sha,m,all),/Presente parzialmente/);
  const failed=dashboard([[d,result(d.id,sha,"debian-api","fail")]]);
  assert.equal(starTone(group,failed,sha,m,all),"minor");
  assert.equal(starTone(group,failed,sha,m,[group,present]),"problem");
  assert.equal(starTone(group,dashboard(),sha,m,[group,present]),"unverified");
  assert.equal(starTone(group,h,sha,m,[group,future]),"unknown");
 }
});

test("runtime descriptions distinguish expired, old and missing proof from a failed test",()=>{
 const d=definition("real"),m={A1:[d.id]};
 assert.match(verificationSummary(node,dashboard([[d,result(d.id,old)]]),sha,m),/un’altra versione/);
 const expired=new Date(Date.now()-25*3600000).toISOString();
 assert.match(verificationSummary(node,dashboard([[d,result(d.id,sha,"debian-api","pass",expired)]]),sha,m),/scaduti/);
 assert.match(verificationSummary(node,dashboard([[d,result(d.id,sha,"debian-api","fail")]]),sha,m),/Collaudo fallito/);
});
