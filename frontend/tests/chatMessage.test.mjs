import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let source=await readFile(new URL('../src/components/ChatMessage.tsx',import.meta.url),'utf8');
let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
for(const pkg of ['react','react/jsx-runtime','react-markdown','remark-gfm','lucide-react']){
 code=code.replaceAll('from "'+pkg+'"','from '+JSON.stringify(pathToFileURL(require.resolve(pkg)).href)).replaceAll("from '"+pkg+"'",'from '+JSON.stringify(pathToFileURL(require.resolve(pkg)).href));
}
const {default:Message}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('assistant renders Markdown, tables and code while dropping executable HTML',()=>{
 const text='**Accordo**\n\n| Data | Nota |\n| --- | --- |\n| Oggi | Richiamare |\n\n```js\nconst x = 1;\n```\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))';
 const html=renderToStaticMarkup(React.createElement(Message,{content:text,assistant:true}));
 assert.match(html,/<strong>Accordo<\/strong>/);assert.match(html,/<table>/);assert.match(html,/<pre>/);
 assert.ok(!html.includes('<script>'));assert.ok(!html.includes('href="javascript:'));
});
test('user content stays literal and cannot insert markup',()=>{
 const html=renderToStaticMarkup(React.createElement(Message,{content:'**test** <img src=x onerror=alert(1)>'}));
 assert.ok(html.includes('**test**'));assert.ok(!html.includes('<img'));
});

test('model output cannot trigger automatic external image requests',()=>{
 const html=renderToStaticMarkup(React.createElement(Message,{content:'![Private image](https://example.invalid/tracker)',assistant:true}));
 assert.ok(!html.includes('<img'));assert.ok(!html.includes('src='));assert.ok(html.includes('Private image'));
});
