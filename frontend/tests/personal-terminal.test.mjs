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
let term,sockets,requests;
globalThis.__Terminal=class {
 constructor(options){this.options=options;this.cols=80;this.rows=24;term=this;}
 loadAddon(){} open(){} reset(){} focus(){}
 write(data){this.output=data;} dispose(){this.disposed=true;}
 onData(fn){this.input=fn;return {dispose(){}};} onResize(fn){this.resize=fn;return {dispose(){}};}
};
globalThis.__Fit=class {fit(){}};
globalThis.ResizeObserver=class {observe(){} disconnect(){}};
globalThis.WebSocket=class {
 static OPEN=1;readyState=0;bufferedAmount=0;sent=[];
 constructor(url){this.url=url;sockets.push(this);}
 send(data){this.sent.push(JSON.parse(data));}
 close(){this.closed=true;this.readyState=3;this.onclose?.({reason:''});}
};
let source=await readFile(new URL('../src/components/PersonalTerminal.tsx',import.meta.url),'utf8');
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime')).replace(/from "react"/g,'from '+external('react'))
 .replace(/import \{ Terminal \} from "@xterm\/xterm";/,'const Terminal=globalThis.__Terminal;')
 .replace(/import \{ FitAddon \} from "@xterm\/addon-fit";/,'const FitAddon=globalThis.__Fit;')
 .replace(/import "[^"]+\.css";/g,'');
const Component=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;
const button=(r,name)=>r.root.findAllByType('button').find(b=>b.children.includes(name));
function reset(){
 sockets=[];requests=[];globalThis.window={location:{protocol:'https:',host:'cora.example.ts.net'}};
 globalThis.fetch=async(url,init)=>{requests.push([url,init]);return {ok:true,json:async()=>({username:'ale',idle_seconds:300,max_seconds:1800})};};
}
async function mount(){let r;await act(async()=>{r=create(React.createElement(Component),{createNodeMock:()=>({})});});await act(async()=>button(r,'Terminale del server').props.onClick());return r;}
async function connect(r){await act(async()=>r.root.findByProps({'aria-label':'Password Debian'}).props.onChange({target:{value:'private-password'}}));await act(async()=>r.root.findByType('form').props.onSubmit({preventDefault(){}}));return sockets[0];}
test('password is cleared, sent over WSS only, and mobile keys go to SSH',async()=>{
 reset();const r=await mount();try{
  assert.equal(sockets.length,0);assert.equal(button(r,'Connetti').props.disabled,true);
  const ws=await connect(r);assert.equal(r.root.findByProps({'aria-label':'Password Debian'}).props.value,'');
  assert.equal(ws.url,'wss://cora.example.ts.net/terminal/connect');assert.equal(ws.sent.length,0);
  await act(async()=>{ws.readyState=1;ws.onopen();});
  assert.deepEqual(ws.sent[0],{type:'auth',password:'private-password',cols:80,rows:24});
  await act(async()=>ws.onmessage({data:JSON.stringify({type:'ready'})}));
  await act(async()=>button(r,'Ctrl+C').props.onClick());assert.deepEqual(ws.sent.at(-1),{type:'input',data:'\u0003'});
  await act(async()=>ws.onmessage({data:JSON.stringify({type:'output',data:'<script>text</script>'})}));assert.equal(term.output,'<script>text</script>');
  await act(async()=>button(r,'Disconnetti').props.onClick());assert.equal(ws.closed,true);assert.equal(term.options.disableStdin,true);
 }finally{await act(async()=>r.unmount());}
});
test('HTTP and unconfigured deployments cannot open a shell',async()=>{
 reset();window.location.protocol='http:';let r=await mount();try{assert.equal(requests.length,0);assert.ok(JSON.stringify(r.toJSON()).includes('HTTPS'));assert.equal(sockets.length,0);}finally{await act(async()=>r.unmount());}
 reset();globalThis.fetch=async()=>({ok:false,status:502});r=await mount();try{assert.ok(JSON.stringify(r.toJSON()).includes('configurazione iniziale'));assert.equal(sockets.length,0);}finally{await act(async()=>r.unmount());}
});
test('leaving the page destroys the terminal and closes pending SSH login',async()=>{
 reset();const r=await mount(),ws=await connect(r);await act(async()=>r.unmount());assert.equal(ws.closed,true);assert.equal(term.disposed,true);ws.onopen();assert.equal(ws.sent.length,0);
});
