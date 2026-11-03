import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/tree/model.ts',import.meta.url),'utf8');
const {severity,checks}=await import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64'));
const {nodes,relations}=JSON.parse(readFileSync(new URL('../src/tree/cora-plan.snapshot.json',import.meta.url)));
test('every imported relation, parent and check resolves; all 45 stars retained',()=>{
 const ids=new Set(nodes.map(n=>n.id));assert.equal(ids.size,nodes.length);
 assert.equal(nodes.filter(n=>n.classification==='star').length,45);
 for(const id of [...Object.keys(checks),...nodes.map(n=>n.parent).filter(Boolean),...relations.flatMap(r=>[r.from,r.to])])assert.ok(ids.has(id),id);
});
test('minor and major moon problems propagate to their star without coloring unrelated stars',()=>{
 const a={id:'A',priority:'ok'},b={id:'B',priority:'unknown'},p={id:'p',parent:'A'},m={id:'m',parent:'p',priority:'minor'}, all=[a,b,p,m];
 assert.equal(severity(a,all,new Set()),'minor');assert.equal(severity(a,all,new Set(['m'])),'problem');assert.equal(severity(b,all,new Set(['m'])),'unknown');
});
