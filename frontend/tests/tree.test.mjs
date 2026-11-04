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
test('constellation connects all 45 stars through their actual branch, roots and trunk',async()=>{
 const code=readFileSync(new URL('../src/tree/Constellation.tsx',import.meta.url),'utf8');
 const output=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React}}).outputText.replace(/^import .*from 'react';/m,'');
 const {layout}=await import('data:text/javascript;base64,'+Buffer.from(output).toString('base64'));
 const {points,edges}=layout(nodes);
 assert.equal(points.filter(p=>p.kind==='star').length,45);
 assert.equal(edges.length,points.length-1);
 const reached=new Set([points[0].node.id]);
 for(let i=0;i<points.length;i++)for(const e of edges)if(reached.has(e.from)||reached.has(e.to)){reached.add(e.from);reached.add(e.to)}
 assert.equal(reached.size,points.length);
 for(const n of nodes.filter(n=>n.classification==='star'&&n.parent!=='tronco'))assert.ok(edges.some(e=>e.from===n.parent&&e.to===n.id));
});
