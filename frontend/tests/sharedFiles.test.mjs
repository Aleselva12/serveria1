import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
const source = await readFile(new URL('../src/services/sharedFiles.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText;
const {sharePageUrl,sharedDownloadPath} = await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
test('share links go through the UI and preserve only an allowed internal download',()=>{
  for(const area of ['server','library']) {
    const path=`/api/v1/${area}/files/shared/${'a'.repeat(43)}`;
    const url=new URL(sharePageUrl(path,'https://cora.example'));
    assert.equal(url.pathname,'/');assert.equal(url.search,'');
    assert.equal(sharedDownloadPath(url.hash),path);
  }
});
test('share links reject external destinations, traversal and malformed tokens',()=>{
  for(const path of ['https://evil.example','//evil.example','/api/v1/server/files/shared/../../private','/api/v1/server/files/shared/short'])
    assert.throws(()=>sharePageUrl(path,'https://cora.example'));
  assert.equal(sharedDownloadPath('#/shared/server/../private'),null);
  assert.equal(sharedDownloadPath('#/shared/other/'+'a'.repeat(43)),null);
});

import React from 'react';
import {create, act} from 'react-test-renderer';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const authSource=(await readFile(new URL('../src/components/AuthGate.tsx',import.meta.url),'utf8'))
  .replace('import App from "../App";', 'const App=()=> <div id="app"/>;')
  .replace('import SharedFile from "./SharedFile";', 'const SharedFile=({path}: {path:string})=> <a id="download" href={path}/>;')
  .replace('import { sharedDownloadPath } from "../services/sharedFiles";', 'const sharedDownloadPath=globalThis.__sharedPath;')
  .replace('import { apiBaseUrl } from "../services/api";', 'const apiBaseUrl="/backend";')
  .replace('import { authenticatedFetch } from "../services/transport";', 'const authenticatedFetch=(...args)=>globalThis.__shareFetch(...args);');
const compiled=ts.transpileModule('import React from "react";\n'+authSource,{compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replaceAll('from "react"','from '+JSON.stringify(pathToFileURL(require.resolve('react')).href));
globalThis.__sharedPath=sharedDownloadPath;
const {default:AuthGate}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
test('private download stays behind login and survives authentication and expiry',async()=>{
  const previousWindow=globalThis.window; const listeners={};
  globalThis.window={location:{hash:'#/shared/library/'+'a'.repeat(43)},addEventListener:(name,fn)=>listeners[name]=fn,removeEventListener:name=>delete listeners[name]};
  globalThis.__shareFetch=async url=>({ok:true,json:async()=>({authenticated:url.endsWith('/login')})});
  let view;
  try {
    await act(async()=>{view=create(React.createElement(AuthGate));});
    assert.equal(view.root.findAllByProps({id:'download'}).length,0);
    assert.equal(view.root.findAllByType('form').length,1);
    await act(async()=>view.root.findByType('form').props.onSubmit({preventDefault(){}}));
    assert.equal(view.root.findByProps({id:'download'}).props.href,'/api/v1/library/files/shared/'+'a'.repeat(43));
    await act(async()=>listeners['cora:unauthorized']());
    assert.equal(view.root.findAllByProps({id:'download'}).length,0);
    assert.equal(view.root.findAllByType('form').length,1);
  } finally {await act(async()=>view?.unmount());globalThis.window=previousWindow;}
});
