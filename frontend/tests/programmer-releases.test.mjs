import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url),external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const calls=[];const release={id:'release',workspace_id:'work',kind:'prepare',status:'ready',phase:'ready',commit:'b'.repeat(40),base_commit:'a'.repeat(40)};
let jobs=[release];
globalThis.__releasesApi={status:async()=>({available:true,active_commit:'a'.repeat(40),jobs}),commit:async(id,message)=>{calls.push(['commit',id,message]);return {commit:release.commit};},prepare:async(id,commit)=>{calls.push(['prepare',id,commit]);return release;},apply:async(id,job,operation)=>{calls.push(['apply',id,job,operation]);const result={...job,id:'apply',kind:'apply',status:'queued'};jobs=[result,release];return result;}};
let source=await readFile(new URL('../src/components/ProgrammerReleases.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react'))
 .replace(/import \{[^}]*\} from "\.\.\/services\/programmerApi";/,'const programmerReleaseApi=globalThis.__releasesApi;');
const Component=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=(r,text)=>r.root.findAllByType('button').find(b=>b.children.includes(text));
test('release application requires owner selection and sends the exact ready commit',async()=>{
 calls.length=0;jobs=[release];let r;
 try {await act(async()=>{r=create(React.createElement(Component,{workspaceId:'work',gitWorkspace:true,disabled:false,onRefresh:()=>{}}));});
 await act(async()=>r.root.findByProps({'aria-label':'Rilascio selezionato'}).props.onChange({target:{value:'release'}}));
 assert.equal(button(r,'Applica e riavvia Cora').props.disabled,true);
 await act(async()=>r.root.findByProps({'aria-label':'Conferma operazione sul rilascio'}).props.onChange({target:{checked:true}}));
 await act(async()=>button(r,'Applica e riavvia Cora').props.onClick());
 const call=calls.find(c=>c[0]==='apply');assert.equal(call[1],'work');assert.equal(call[2].commit,release.commit);assert.equal(call[3],'apply');
 assert.ok(JSON.stringify(r.toJSON()).includes('queued'));
 }finally{if(r)await act(async()=>r.unmount());}
});
test('snapshot workspace cannot commit or prepare a release',async()=>{
 jobs=[];let r;
 try{await act(async()=>{r=create(React.createElement(Component,{workspaceId:'snapshot',gitWorkspace:false,disabled:false,onRefresh:()=>{}}));});
 assert.equal(button(r,'Salva commit Git').props.disabled,true);assert.equal(button(r,'Prepara rilascio').props.disabled,true);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('GitHub publication sends the verified release without applying it',async()=>{
 calls.length=0;jobs=[release];let r;
 try {await act(async()=>{r=create(React.createElement(Component,{workspaceId:'work',gitWorkspace:true,disabled:false,onRefresh:()=>{}}));});
 await act(async()=>r.root.findByProps({'aria-label':'Rilascio selezionato'}).props.onChange({target:{value:'release'}}));
 await act(async()=>button(r,'Pubblica branch su GitHub').props.onClick());
 const call=calls.find(c=>c[0]==='apply');assert.equal(call[1],'work');assert.equal(call[2].commit,release.commit);assert.equal(call[3],'publish');
 }finally{if(r)await act(async()=>r.unmount());}
});
