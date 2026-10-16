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
globalThis.window={addEventListener(){},removeEventListener(){},confirm:()=>false};
let conflict=true, calls=[];
globalThis.__filesEditorApi={text:async()=>({text:'old\r\n',revision:'oldhash'}),saveText:async(...args)=>{calls.push(args);if(conflict)throw new Error('File cambiato');return {revision:'newhash',backupPath:'cora-backup-1.bak'};}};
const source=await readFile(new URL('../src/components/FileEditor.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from "react\/jsx-runtime"/g,'from '+ext('react/jsx-runtime')).replace(/from ['"]react['"]/g,'from '+ext('react')).replace(/import \{ filesApi \} from ['"]\.\.\/services\/filesApi['"];/,'const filesApi=globalThis.__filesEditorApi;');
const Editor=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
test('file editor retains draft on conflict, confirms discard, saves backup and CRLF',async()=>{
 let r,closed=0,refreshed=0;
 try{
  await act(async()=>{r=create(React.createElement(Editor,{area:'server',rootId:'project',token:'',item:{path:'code.py',name:'code.py'},close:()=>closed++,saved:()=>refreshed++}));});
  const area=()=>r.root.findByProps({'aria-label':'Contenuto del file'});
  await act(async()=>area().props.onChange({target:{value:'new\n'}}));
  await act(async()=>r.root.findByProps({'aria-label':'Chiudi editor'}).props.onClick());
  assert.equal(closed,0);
  const save=()=>r.root.findAllByType('button').find(b=>b.children.includes('Salva con backup'));
  await act(async()=>{save().props.onClick();});
  assert.equal(area().props.value,'new\n');
  assert.match(r.root.findByProps({role:'alert'}).children.join(''),/File cambiato/);
  assert.deepEqual(calls[0],['server','','project','code.py','new\r\n','oldhash']);
  conflict=false;
  await act(async()=>{save().props.onClick();});
  assert.equal(refreshed,1);assert.equal(save().props.disabled,true);
  assert.match(JSON.stringify(r.toJSON()),/cora-backup-1.bak/);
 }finally{if(r)await act(async()=>r.unmount());}
});
