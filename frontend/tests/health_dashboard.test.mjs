import assert from "node:assert/strict";
import {test} from "node:test";
import {readFile} from "node:fs/promises";
import {createRequire} from "node:module";
import {pathToFileURL} from "node:url";
import ts from "typescript";
import React from "react";
import {create, act} from "react-test-renderer";
const require=createRequire(import.meta.url);
const external=name=>JSON.stringify(pathToFileURL(require.resolve(name)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let requests=0;
const at=new Date().toISOString();
let response={
  catalog:[
    {id:"chat_contract", title:"Chat → orchestratore → agenti (contratti)",
     component:"cora",kind:"contract",stage:"Chat API → grafo → delega",frequency:"5m",
     dependsOn:[],description:"",automated:true},
    {id:"chat_e2e", title:"Chat: risposta integrale e persistenza",
     component:"cora",kind:"e2e",stage:"Chat → modello → DB",frequency:"on_release",
     dependsOn:["chat_contract"],description:"Solo in test",automated:false},
  ],
  components:{cora:"Cora e memoria"},
  latest:{chat_contract:{id:"chat_contract",status:"pass",detail:"Contratto presente",
    source:"periodic",environment:"ci-synthetic",commit:null,durationMs:20,at}},
  history:[],historyStore:"postgresql",updatedAt:at,
};
globalThis.__healthApi={
  healthDashboard:async()=>{requests++;return response;},
};
globalThis.__serviceLabels={ready:"Raggiungibile",busy:"Occupato",offline:"Non raggiungibile",
  error:"Errore",unknown:"Non verificato"};
globalThis.__roadmap={goals:[{
  id:"RUNTIME-MEMORY",state:"Da collaudare",development:"In costruzione",
  issues:["Verificare ripristino chat"],verification:["Risposta agente dopo riavvio"]
}]};
let source=await readFile(new URL("../src/components/HealthDashboard.tsx",import.meta.url),"utf8");
let code=ts.transpileModule(source,{compilerOptions:{
  target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX
}}).outputText
 .replace(/from ["']react\/jsx-runtime["']/g,"from "+external("react/jsx-runtime"))
 .replace(/from ["']react["']/g,"from "+external("react"))
 .replace(/import \{ api \} from .*?;/,"const api=globalThis.__healthApi;")
 .replace(/import \{\s*serviceStatusLabels\s*\} from .*?;/,"const serviceStatusLabels=globalThis.__serviceLabels;")
 .replace(/import \{\s*homeRoadmap\s*\} from .*?;/,"const homeRoadmap=globalThis.__roadmap;");
const HealthDashboard=(await import("data:text/javascript;base64,"+Buffer.from(code).toString("base64"))).default;
const rendered=r=>JSON.stringify(r.toJSON());

test("Health panel distinguishes contract checks from untested full workflows",async()=>{
  requests=0;
  let r;
  try {
    await act(async()=>{r=create(React.createElement(HealthDashboard,{}));});
    assert.ok(rendered(r).includes("Contratto OK"));
    assert.ok(rendered(r).includes("Da verificare"));
    assert.ok(rendered(r).includes("Stato sviluppo: In costruzione"));
    assert.ok(rendered(r).includes("Verificare ripristino chat"));
    assert.equal(requests,1,"UI should query existing results, never run probes");
  } finally {if(r)await act(async()=>r.unmount());}
});

test("Health panel reports boundary failures without marking other untested flows as passing",async()=>{
  const old=response;
  response={...response,latest:{chat_contract:{...old.latest.chat_contract,
    status:"fail",detail:"Collegamento assente: grafo → tools"}}};
  let r;
  try{
    await act(async()=>{r=create(React.createElement(HealthDashboard,{componentFilter:["cora"]}));});
    assert.ok(rendered(r).includes("Collegamento assente"));
    assert.ok(rendered(r).includes("Errore"));
    assert.ok(rendered(r).includes("Da verificare"));
  } finally{
    if(r)await act(async()=>r.unmount());
    response=old;
  }
});
