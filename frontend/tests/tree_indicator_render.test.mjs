import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url);
const url=code=>'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
const compile=path=>ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from "(react(?:\/jsx-runtime)?)"/g,(_,name)=>'from '+JSON.stringify(pathToFileURL(require.resolve(name)).href));
const evidence=url(compile('../src/tree/roadmapEvidence.ts'));
const {default:Constellation}=await import(url(compile('../src/tree/Constellation.tsx').replace(/from "\.\/roadmapEvidence"/g,'from '+JSON.stringify(evidence))));
const {developmentIndicator,verificationIndicator}=await import(evidence);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
test('focused SVG gives each star, planet and moon two accessible scoped indicators',async()=>{
 const nodes=[{id:'s',title:'Stella',classification:'star',status:'present'},{id:'p',parent:'s',title:'Pianeta',classification:'planet',status:'partial'},{id:'m',parent:'p',title:'Luna',classification:'moon',status:'planned'}];
 let r;
 try{
  await act(async()=>{r=create(React.createElement(Constellation,{nodes,selected:'s',focusId:'s',onSelect:()=>{},priority:()=> 'unverified',visible:()=>true,indicators:n=>({development:developmentIndicator(n),verification:verificationIndicator(n,null,null,{})})}));});
  const points=r.root.findAll(n=>Boolean(n.props['data-node']));
  assert.equal(points.length,3);
  for(const point of points){
   assert.match(point.props['aria-label'],/Sviluppo:.*Collaudi:/);
   assert.equal(point.findByProps({className:'rm2-svg-indicators'}).findAllByType('circle').length,2);
  }
  assert.match(points.find(p=>p.props['data-node']==='p').props['aria-label'],/Sviluppo parziale/);
  assert.match(points.find(p=>p.props['data-node']==='m').props['aria-label'],/Non implementato/);
 }finally{if(r)await act(async()=>r.unmount());}
});
