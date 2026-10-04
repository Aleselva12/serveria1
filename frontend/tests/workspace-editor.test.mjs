import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {create,act} from 'react-test-renderer';
const require=createRequire(import.meta.url),ext=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let saved=[],conflict=false;
globalThis.__editorApi={fullFile:async()=>({content:'line\n'.repeat(300)+'tail',sha256:'original',truncated:false}),saveFile:async(...args)=>{saved.push(args);if(conflict)throw new Error('409 conflitto');return {saved:true,sha256:'new'};}};
const source=await readFile(new URL('../src/components/WorkspaceEditor.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from "react\/jsx-runtime"/g,'from '+ext('react/jsx-runtime')).replace(/from "react"/g,'from '+ext('react')).replace(/import \{ programmerApi \} from "\.\.\/services\/programmerApi";/,'const programmerApi=globalThis.__editorApi;');
const Editor=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
test('editor saves complete content with CAS hash and retains draft on conflict',async()=>{
 let r,closed=0,refreshed=0;saved=[];conflict=true;
 try{
  await act(async()=>{r=create(React.createElement(Editor,{workspace:'ws',path:'long.py',onClose:()=>closed++,onSaved:async()=>refreshed++}));});
  const area=()=>r.root.findByProps({'aria-label':'Modifica sorgente'});
  assert.equal(area().props.value,'line\n'.repeat(300)+'tail');
  await act(async()=>area().props.onChange({target:{value:'my draft'}}));
  const save=()=>r.root.findAllByType('button').find(b=>b.children.includes('Salva nel workspace'));
  await act(async()=>save().props.onClick());
  assert.deepEqual(saved[0],['ws','long.py','my draft','original']);
  assert.equal(area().props.value,'my draft');assert.equal(closed,0);
  assert.match(r.root.findByProps({role:'alert'}).children.join(''),/409/);
  conflict=false;await act(async()=>save().props.onClick());assert.equal(closed,1);assert.equal(refreshed,1);
 }finally{if(r)await act(async()=>r.unmount());conflict=false;}
});
test('new files are saved with empty expected hash',async()=>{
 let r;saved=[];
 try{
  await act(async()=>{r=create(React.createElement(Editor,{workspace:'ws',path:'',onClose:()=>{},onSaved:async()=>{}}));});
  await act(async()=>r.root.findByProps({'aria-label':'Percorso nuovo file'}).props.onChange({target:{value:'new.py'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Modifica sorgente'}).props.onChange({target:{value:'value = 1'}}));
  await act(async()=>r.root.findAllByType('button').find(b=>b.children.includes('Salva nel workspace')).props.onClick());
  assert.deepEqual(saved[0],['ws','new.py','value = 1','']);
 }finally{if(r)await act(async()=>r.unmount());}
});
