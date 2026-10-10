import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
const compile = s => ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const url = s => 'data:text/javascript;base64,'+Buffer.from(compile(s)).toString('base64');
const transportUrl=url(await readFile(new URL('../src/services/transport.ts',import.meta.url),'utf8'));
const source=(await readFile(new URL('../src/services/runtimeApi.ts',import.meta.url),'utf8')).replace('import { apiBaseUrl } from "./api";','const apiBaseUrl="/backend";').replace('"./transport"',JSON.stringify(transportUrl));
const {streamChat,runtimeRequest}=await import(url(source));
const original=globalThis.fetch;
afterEach(()=>globalThis.fetch=original);
const json=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
test('manual tools and attachments travel together; explicit empty never becomes automatic',async()=>{
 for(const manual of [['calculator_tool'],[]]){
  let calls=0;globalThis.fetch=async(url,init)=>{
   if(++calls===1){assert.deepEqual(JSON.parse(init.body),{message:'Leggi',thread_id:'thread',attachment_ids:['attachment-id'],manual_tools:manual});return json({id:'run',status:'queued'});}
   return stream('event: result\ndata: '+JSON.stringify({status:'completed',result:{response:'done',thread_id:'thread'}})+'\n\n');
  };
  await streamChat('Leggi','thread',()=>{},()=>{},()=>{},['attachment-id'],manual);assert.equal(calls,2);
 }
});
function stream(frames) {
  const bytes=new TextEncoder().encode(frames);
  return new Response(new ReadableStream({start(c){ for(let i=0;i<bytes.length;i+=7)c.enqueue(bytes.slice(i,i+7));c.close(); }}),{headers:{'Content-Type':'text/event-stream'}});
}
test('streaming handles split UTF-8, provisional text and canonical final result',async()=>{
  let calls=0;const texts=[],states=[],ids=[];
  globalThis.fetch=async(path,init)=>{
    calls++;assert.equal(init.credentials,'include');
    if(calls===1){assert.equal(path,'/backend/api/v1/chat/runs');assert.equal(init.headers.get('X-Cora-Client'),'ui');return json({id:'run',status:'queued'});}
    return stream('data: '+JSON.stringify({type:'chat.delta',payload:{text:'Caffè ☕'}})+'\n\n'+'data: '+JSON.stringify({type:'run.state',payload:{status:'running'}})+'\n\n'+'event: result\ndata: '+JSON.stringify({status:'completed',result:{response:'Risposta salvata',thread_id:'thread'}})+'\n\n');
  };
  const result=await streamChat('test','thread',id=>ids.push(id),text=>texts.push(text),state=>states.push(state));
  assert.deepEqual(ids,['run']);assert.deepEqual(texts,['Caffè ☕']);assert.deepEqual(states,['queued','running']);assert.equal(result.response,'Risposta salvata');assert.equal(calls,2);
});
test('cancelled runs never become successful answers and are not resubmitted',async()=>{
  let calls=0;globalThis.fetch=async()=>++calls===1?json({id:'run',status:'queued'}):stream('event: result\ndata: '+JSON.stringify({status:'cancelled',result:null})+'\n\n');
  await assert.rejects(streamChat('test','thread',()=>{},()=>{},()=>{}),/cancelled/);assert.equal(calls,2);
});
test('resync replaces text instead of appending and mutations use the global session',async()=>{
  let calls=0;const texts=[];
  globalThis.fetch=async()=>++calls===1?json({id:'run',status:'queued'}):stream('data: '+JSON.stringify({type:'chat.delta',payload:{text:'old'}})+'\n\nevent: resync\ndata: '+JSON.stringify({output:'recovered',status:'running'})+'\n\nevent: result\ndata: '+JSON.stringify({status:'completed',result:{response:'done',thread_id:'thread'}})+'\n\n');
  await streamChat('test','thread',()=>{},t=>texts.push(t),()=>{});assert.deepEqual(texts,['old','recovered']);
  globalThis.fetch=async(path,init)=>{assert.equal(path,'/backend/api/v1/runtime/runs/run/cancel');assert.equal(init.headers.get('X-Cora-Client'),'ui');assert.equal(init.credentials,'include');return json({status:'cancelling'});};
  assert.equal((await runtimeRequest('/runtime/runs/run/cancel',{method:'POST'})).status,'cancelling');
});

test('specialist state and reset are visible without replacing canonical final result',async()=>{
 let calls=0;const texts=[],states=[];
 globalThis.fetch=async()=>++calls===1?json({id:'run',status:'queued'}):stream(
 'data: '+JSON.stringify({type:'chat.delta',payload:{text:'Supervisor'}})+'\n\n'+
 'data: '+JSON.stringify({type:'agent.state',source:'research',payload:{status:'running'}})+'\n\n'+
 'data: '+JSON.stringify({type:'chat.reset'})+'\n\n'+
 'data: '+JSON.stringify({type:'chat.delta',payload:{text:'Specialist'}})+'\n\n'+
 'event: result\ndata: '+JSON.stringify({status:'completed',result:{response:'Canonical',thread_id:'thread'}})+'\n\n');
 const result=await streamChat('query','thread',()=>{},t=>texts.push(t),s=>states.push(s));
 assert.deepEqual(texts,['Supervisor','','Specialist']);assert.ok(states.includes('Agente: research'));assert.equal(result.response,'Canonical');assert.equal(calls,2);
});


test('chat attachments are sent with the request and streaming never resubmits them',async()=>{
 let calls=0;globalThis.fetch=async(url,init)=>{
  if(++calls===1){assert.deepEqual(JSON.parse(init.body),{message:'Leggi',thread_id:'thread',attachment_ids:['attachment-id']});return json({id:'run',status:'queued'});}
  return stream('event: result\ndata: '+JSON.stringify({status:'completed',result:{response:'Letto',thread_id:'thread'}})+'\n\n');
 };
 await streamChat('Leggi','thread',()=>{},()=>{},()=>{},['attachment-id']);assert.equal(calls,2);
});
