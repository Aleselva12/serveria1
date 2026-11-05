import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const require=createRequire(import.meta.url);
const external=n=>JSON.stringify(pathToFileURL(require.resolve(n)).href);
export const dataUrl=code=>'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
async function compile(name){
 const source=await readFile(new URL('../src/components/'+name,import.meta.url),'utf8');
 return ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText.replace(/from ["']react\/jsx-runtime["']/g,'from '+external('react/jsx-runtime')).replace(/from ["']react["']/g,'from '+external('react'));
}
export const evidenceUrl=dataUrl(await compile('activityEvidence.ts'));
export const explorerUrl=dataUrl((await compile('ActivityExplorer.tsx')).replace(/from ['"]\.\/activityEvidence['"]/g,'from '+JSON.stringify(evidenceUrl)).replace(/import ['"]\.\/activity-explorer.css['"];?/g,''));
