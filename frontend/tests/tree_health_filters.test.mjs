import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {pathToFileURL} from "node:url";
import ts from "typescript";
import React from "react";
import {create,act} from "react-test-renderer";
const require=createRequire(import.meta.url);
const external=name=>JSON.stringify(pathToFileURL(require.resolve(name)).href);
const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const compile=source=>ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const url=code=>"data:text/javascript;base64,"+Buffer.from(code).toString("base64");
const evidenceUrl=url(compile(read("../src/tree/roadmapEvidence.ts")));
const sha="a".repeat(40),at=new Date().toISOString();
const definition=id=>({id,title:id,component:"cora",kind:"e2e",frequency:"on_release",automated:false});
let reads=0;
globalThis.__treeHealth={catalog:[definition("good"),definition("bad")],latest:{good:{status:"pass",commit:sha,environment:"debian-api",at},bad:{status:"fail",commit:sha,environment:"debian-api",at}}};
globalThis.__treePlan={revision:"test",relations:[],nodes:[{id:"tronco",title:"Tronco"},...[["T1","Supervisore"],["A1","Chat"]].map(([id,title])=>({id,title,parent:"tronco",classification:"star",priority:"minor",status:"partial",knownIssues:[],timeline:{future:[]}}))]};
globalThis.__treeApi={healthDashboard:async()=>{reads++;return globalThis.__treeHealth;}};
globalThis.__treeTransport=async()=>({ok:true,json:async()=>({platform:"server",active_commit:sha})});
globalThis.window={setInterval:()=>1};
globalThis.clearInterval=()=>{};
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let code=compile(read("../src/tree/TreeHome.tsx"))
 .replace(/from ["']react\/jsx-runtime["']/g,"from "+external("react/jsx-runtime"))
 .replace(/from ["']react["']/g,"from "+external("react"))
 .replace(/import \{([^}]+)\} from "lucide-react";/,(_,names)=>"const "+names.split(",").map(x=>x.trim()).filter(Boolean).map(x=>x+"=()=>null").join(",")+";")
 .replace(/import planSource from .*?;/,"const planSource=globalThis.__treePlan;")
 .replace(/import \{[^}]+\} from "\.\.\/services\/api";/,"const api=globalThis.__treeApi,apiBaseUrl='';")
 .replace(/import \{ authenticatedFetch \} from .*?;/,"const authenticatedFetch=globalThis.__treeTransport;")
 .replace(/from "\.\/roadmapEvidence"/g,"from "+JSON.stringify(evidenceUrl))
 .replace(/import \{ homeRoadmap \} from .*?;/,"const homeRoadmap={goals:[],nextWork:[]};")
 .replace(/import \{ checks \} from .*?;/,"const checks={T1:['good'],A1:['bad']};")
 .replace(/import \{ closure \} from .*?;/,"const closure={};")
 .replace(/import atlasEvidence from .*?;/,"const atlasEvidence={};")
 .replace(/import NodeVerificationPanel from .*?;/,"const NodeVerificationPanel=props=>{globalThis.__verificationOnResults=props.onResults;return null;};")
 .replace(/import Constellation from .*?;/,"const Constellation=()=>null;")
 .replace(/import RoadmapPriorities from .*?;/,"const RoadmapPriorities=()=>null;")
 .replace(/import \{[^}]+\} from "\.\/codeLinks";/,"const codeLinks={},pageLinks={},sourceUrl=()=>'';")
 .replace(/import "\.\/tree.css";/,"");
const TreeHome=(await import(url(code))).default;

test("visible green/red counts and filters use live evidence and never run probes",async()=>{
 let r;
 try{
  await act(async()=>{r=create(React.createElement(TreeHome));});
  const summary=r.root.findByProps({className:"rm2-health-summary"});
  const buttons=summary.findAllByType("button");
  const text=b=>b.children.filter(x=>typeof x==="string"||typeof x==="number").join("");
  assert.match(text(buttons[1]),/Verde.*1/);
  assert.match(text(buttons[2]),/Rosso.*1/);
  const content=n=>typeof n==="string"?n:n.children?.map(content).join("")||"";
  const index=()=>r.root.findByProps({className:"rm2-star-index"}).findAllByType("button");
  assert.equal(index().length,2);
  await act(async()=>buttons[2].props.onClick());
  assert.equal(index().length,1);
  assert.match(content(index()[0]),/Chat/);
  await act(async()=>buttons[1].props.onClick());
  assert.equal(index().length,1);
  assert.match(content(index()[0]),/Supervisore/);
  assert.equal(reads,1);
 }finally{if(r)await act(async()=>r.unmount());}
});

test("refresh updates the rendered verification text and colors from the shared registry",async()=>{
 let r;
 const text=n=>typeof n==="string"?n:n.children?.map(text).join("")||"";
 const original=globalThis.__treeHealth;
 try{
  globalThis.__treeHealth={...original,latest:{...original.latest,good:{...original.latest.good,status:"fail"}}};
  await act(async()=>{r=create(React.createElement(TreeHome));});
  assert.match(text(r.root.findByProps({className:"rm2-badges"})),/Collaudo fallito/);
  globalThis.__treeHealth=original;
  const refresh=r.root.findAllByType("button").find(b=>text(b)==="Aggiorna albero");
  await act(async()=>refresh.props.onClick());
  assert.match(text(r.root.findByProps({className:"rm2-badges"})),/Collaudo reale superato/);
  globalThis.__treeHealth={...original,latest:{...original.latest,good:{...original.latest.good,status:"fail"}}};
  await act(async()=>globalThis.__verificationOnResults());
  assert.match(text(r.root.findByProps({className:"rm2-badges"})),/Collaudo fallito/);
  const page=r.root.findByProps({className:"rm2-page"});
  const sections=page.children.filter(c=>typeof c!=="string");
  const sequence=sections.findIndex(c=>c.props.className==="rm2-footer-work");
  const tree=sections.findIndex(c=>c.props.className==="rm2-workspace");
  const analysis=sections.findIndex(c=>c.type.name==="RoadmapPriorities");
  const verification=sections.findIndex(c=>c.type.name==="NodeVerificationPanel");
  const refreshIndex=sections.findIndex(c=>c.type==="button"&&text(c)==="Aggiorna albero");
  assert.ok(sequence<tree&&tree<analysis&&analysis<verification&&verification<refreshIndex);
 }finally{
  globalThis.__treeHealth=original;
  if(r)await act(async()=>r.unmount());
 }
});
