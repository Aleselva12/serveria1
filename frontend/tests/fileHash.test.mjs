import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/services/fileHash.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {hashFile}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('incremental file digest matches SHA-256 at block and slice boundaries',async()=>{
 for(const length of [0,3,55,56,63,64,65,1024*1024-1,1024*1024,1024*1024+1,2*1024*1024+63]){
  const bytes=Buffer.alloc(length);for(let i=0;i<length;i++)bytes[i]=i%251;
  assert.equal(await hashFile(new Blob([bytes])),createHash('sha256').update(bytes).digest('hex'),`length ${length}`);
 }
});
