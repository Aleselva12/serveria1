import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
const contractSource = await readFile(new URL("../src/services/capabilityContracts.ts", import.meta.url), "utf8");
const contractUrl = "data:text/javascript;base64," + Buffer.from(ts.transpileModule(contractSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText).toString("base64");
const transportSource = await readFile(new URL("../src/services/transport.ts", import.meta.url), "utf8");
const transportUrl = "data:text/javascript;base64," + Buffer.from(ts.transpileModule(transportSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText).toString("base64");

class ApiError extends Error { constructor(message, kind, status) { super(message); this.kind=kind; this.status=status; } }
globalThis.__toolsApiError=ApiError;
const source = (await readFile(new URL('../src/services/toolsApi.ts',import.meta.url),'utf8')).replace('import { apiBaseUrl, ApiError } from "./api";', 'const apiBaseUrl="/backend";const ApiError=globalThis.__toolsApiError;');
const compiled=ts.transpileModule(source.replaceAll('"./transport"', JSON.stringify(transportUrl)).replaceAll('"./capabilityContracts"', JSON.stringify(contractUrl)),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {toolsApi}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const original=globalThis.fetch;
afterEach(()=>globalThis.fetch=original);
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
const draft={title:'Test',description:'',status:'draft',nodes:[{id:'input',kind:'trigger',label:'Input',x:30,y:30,config:{}}],edges:[]};
test('draft save sends owner token in headers only and persists draft graph',async()=>{
  globalThis.fetch=async(url,init)=>{
    assert.equal(url,'/backend/tools/drafts');assert.equal(init.method,'POST');
    assert.equal(init.headers.get('Authorization'),'Bearer owner-secret');
    assert.ok(!init.body.includes('owner-secret'));
    assert.deepEqual(JSON.parse(init.body).nodes,draft.nodes);
    return response({...draft,id:'saved',version:1,warnings:[]});
  };
  assert.equal((await toolsApi.saveDraft(draft,'owner-secret')).status,'draft');
});
test('version conflicts surface without retry or invented success',async()=>{
  let calls=0;
  globalThis.fetch=async()=>{calls++;return response({detail:'Bozza cambiata'},409);};
  await assert.rejects(toolsApi.saveDraft({...draft,id:'saved',version:1}),e=>e.status===409);
  assert.equal(calls,1);
});
test('malformed definitions and another tool identity are rejected',async()=>{
  globalThis.fetch=async()=>response({entry:{id:'other'},flow:draft,parameters:[],operations:[],checks:[],conditions:[],note:'test',output_type:'str'});
  await assert.rejects(toolsApi.definition('selected'),e=>e.kind==='invalid');
  globalThis.fetch=async()=>response({...draft,id:'saved',version:1,warnings:[],status:'active'});
  await assert.rejects(toolsApi.saveDraft(draft),e=>e.kind==='invalid');
});

test('draft delete sends the seen version, accepts 204 and validate reads warnings',async()=>{
  globalThis.fetch=async(url,init)=>{
    assert.equal(url,'/backend/tools/drafts/abc?version=3');assert.equal(init.method,'DELETE');
    return new Response(null,{status:204});
  };
  assert.equal(await toolsApi.deleteDraft('abc',3),undefined);
  globalThis.fetch=async(url,init)=>{assert.equal(url,'/backend/tools/drafts/validate');assert.equal(init.method,'POST');return response({warnings:['manca uscita']});};
  assert.deepEqual(await toolsApi.validateDraft(draft),['manca uscita']);
  globalThis.fetch=async()=>response({warnings:'no'});
  await assert.rejects(toolsApi.validateDraft(draft),e=>e.kind==='invalid');
});

test('run rejection keeps every problem and run responses are validated',async()=>{
  globalThis.fetch=async()=>response({detail:{message:'Il flusso non può essere eseguito.',problems:['A: scegli un tool.','Manca «x».']}},422);
  await assert.rejects(toolsApi.startRun('d',1,'dry_run',{}),e=>e.status===422&&e.problems.length===2&&e.message.includes('non può'));
  globalThis.fetch=async(url,init)=>{assert.equal(url,'/backend/tools/drafts/d/runs');assert.deepEqual(JSON.parse(init.body),{version:1,mode:'live',input:{a:1}});
    return response({id:'r',draft_id:'d',draft_version:1,mode:'live',status:'queued',created_at:'x',nodes:{n:{status:'pending',label:'N',kind:'trigger'}}},201);};
  assert.equal((await toolsApi.startRun('d',1,'live',{a:1})).status,'queued');
  globalThis.fetch=async()=>response({id:'r',draft_id:'d',draft_version:1,mode:'live',status:'exploded',created_at:'x',nodes:{}});
  await assert.rejects(toolsApi.getRun('r'),e=>e.kind==='invalid');
});
