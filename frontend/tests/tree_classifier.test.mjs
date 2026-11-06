import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const ui=read("../src/tree/RoadmapPriorities.tsx");
const home=read("../src/tree/TreeHome.tsx");
const api=read("../../core/roadmap_classifier_api.py");
const server=read("../../api.py");

test("local model classifier is available from Roadmap only on explicit click",()=>{
 assert.ok(home.includes('<RoadmapPriorities stars={stars} onOpen={jump}/>'));
 assert.ok(ui.includes('onClick={()=>void evaluate()}'));
 assert.ok(ui.includes('setPreview(null)'));
 assert.ok(ui.includes('disabled={busy||!status?.installed||!eligible.length}'));
 assert.ok(!ui.includes('setInterval('));
 assert.ok(!ui.includes('updateRoadmap('));
});
test("source data uses bounded task IDs and no auto rewrite of map",()=>{
 assert.ok(ui.includes('const MAX_ITEMS=8'));
 assert.ok(ui.includes('controller.abort(),450000'));
 assert.ok(api.includes('TIMEOUT_SECONDS = 420'));
 assert.ok(read("../../deploy/nginx.conf").includes("proxy_read_timeout 480s"));
 assert.ok(ui.includes('problems:(n.knownIssues||[])'));
 assert.ok(ui.includes('goals:(n.timeline?.future||[])'));
 assert.ok(ui.includes('additional_context:context'));
 assert.ok(!ui.includes('api.healthDashboard'));
 assert.ok(api.includes('CORA_ROADMAP_CLASSIFIER_MODEL'));
 assert.ok(api.includes('get_ollama_base_url'));
 assert.ok(api.includes('format": _schema()'));
 assert.ok(api.includes('writes_map'));
 assert.equal(/(?:^|[^a-z0-9.-])openai[.]com(?:[^a-z0-9.-]|$)/i.test(api),false);
 assert.equal(/(?:^|[^a-z0-9.-])github[.]com(?:[^a-z0-9.-]|$)/i.test(api),false);
 assert.ok(!api.includes('subprocess'));
 assert.ok(!api.includes('write_text('));
});
test("new API is registered behind the same existing authentication middleware",()=>{
 assert.ok(server.includes('app.add_middleware(AuthMiddleware)'));
 assert.ok(server.includes('app.include_router(roadmap_classifier_router)'));
 assert.ok(api.includes('max_length=500'));
 assert.ok(api.includes('MAX_TASKS = 8'));
 assert.ok(api.includes('_BUSY.acquire(blocking=False)'));
});
