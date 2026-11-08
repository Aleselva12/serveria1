import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const src=readFileSync(new URL('../src/tree/roadmapEvidence.ts',import.meta.url),'utf8');
const js=ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {developmentIndicator:dev,verificationIndicator:verify,indicatorColors:c,starTone}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const sha='a'.repeat(40),node={id:'n',classification:'star',status:'partial'};
const def={id:'test',kind:'e2e',frequency:'manual',maxAgeSeconds:86400};
const result={id:'test',status:'pass',at:new Date().toISOString(),commit:sha,environment:'debian-api'};
const health=(r=result,d=def)=>({catalog:[d],latest:{test:r}});
const mapping={n:['test']};
test('development is declared independently for every node kind',()=>{
 for(const classification of ['star','planet','moon'])for(const [status,color] of [['planned',c.gray],['idea',c.gray],['partial',c.blue],['present',c.green],['other',c.gray]])
 assert.equal(dev({...node,classification,status}).color,color);
});
test('missing, old, expired, future, unassigned and CI evidence is not a failed test',()=>{
 for(const r of [undefined,{...result,commit:'b'.repeat(40)},{...result,commit:null},{...result,environment:'ci',status:'fail'},{...result,at:new Date(Date.now()-90000000).toISOString()},{...result,at:new Date(Date.now()+3600000).toISOString()}]){
  const h={catalog:[def],latest:{test:r}};
  assert.equal(verify(node,h,sha,mapping).color,c.gray);
 }
 assert.equal(verify(node,null,null,{}).color,c.gray);
 assert.equal(verify(node,health(),null,mapping).color,c.gray);
 assert.equal(verify(node,health(),sha,{}).color,c.gray);
});
test('real failure, partial proof and live success are distinct',()=>{
 assert.equal(verify(node,health({...result,status:'fail'}),sha,mapping).color,c.red);
 assert.equal(verify(node,health(result,{...def,kind:'synthetic'}),sha,mapping).color,c.yellow);
 assert.equal(verify(node,health({...result,status:'fail'},{...def,kind:'synthetic'}),sha,mapping).color,c.orange);
 assert.equal(verify(node,health(),sha,mapping).color,c.green);
 assert.equal(verify(node,health(),sha,{n:['test','missing']}).color,c.yellow);
});
test('manual green is scoped, dated and overridden by a current failure',()=>{
 const n={...node,observations:[{type:'manual_pass',observedAt:'2026-11-08',text:'Percorso provato'}]};
 assert.match(verify(n,null,null,{}).label,/manuale circoscritta del 2026-11-08/);
 assert.equal(verify(n,health({...result,status:'fail'}),sha,mapping).color,c.red);
 assert.equal(verify({...n,observations:[{...n.observations[0],type:'manual_followup'}]},null,null,{}).color,c.yellow);
});
test('a failing moon cannot change the independent parent indicators or sibling',()=>{
 const parent={...node,status:'present'},moon={id:'moon',parent:'n',classification:'moon',status:'partial'};
 const m={moon:['test']},h=health({...result,status:'fail'});
 assert.equal(starTone(parent,h,sha,m,[parent,moon]),'minor');
 assert.equal(verify(parent,h,sha,m).color,c.gray);
 assert.equal(dev(parent).color,c.green);
 assert.equal(verify(moon,h,sha,m).color,c.red);
 assert.equal(verify({...moon,id:'sibling'},h,sha,m).color,c.gray);
});
