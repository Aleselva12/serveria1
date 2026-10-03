import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const contractSource = await readFile(new URL("../src/services/capabilityContracts.ts", import.meta.url), "utf8");
const contractUrl = "data:text/javascript;base64," + Buffer.from(ts.transpileModule(contractSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText).toString("base64");
const transportSource = await readFile(new URL("../src/services/transport.ts", import.meta.url), "utf8");
const transportUrl = "data:text/javascript;base64," + Buffer.from(ts.transpileModule(transportSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText).toString("base64");
const compile = (s) =>
  ts.transpileModule(s.replaceAll('"./transport"', JSON.stringify(transportUrl)).replaceAll('"./capabilityContracts"', JSON.stringify(contractUrl)), {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
    },
  }).outputText;
const url = (s) =>
  "data:text/javascript;base64," + Buffer.from(compile(s)).toString("base64");
const apiSource = (
  await readFile(new URL("../src/services/api.ts", import.meta.url), "utf8")
).replace("import.meta.env.VITE_API_BASE_URL", "undefined");
const source = (
  await readFile(
    new URL("../src/services/filesApi.ts", import.meta.url),
    "utf8",
  )
).replace('"./api"', JSON.stringify(url(apiSource)));
const { filesApi } = await import(url(source));
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});
const response = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

test("library roots send owner token only in the header", async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "/backend/api/v1/library/files/roots");
    assert.equal(init.headers.get("Authorization"), "Bearer owner-secret");
    return response({
      roots: [
        {
          id: "library",
          label: "IA",
          writable: true,
          available: true,
          storage: null,
        },
      ],
    });
  };
  assert.equal(
    (await filesApi.roots("library", "owner-secret"))[0].id,
    "library",
  );
});
test("multipart upload preserves filename and leaves boundary to browser", async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "/backend/api/v1/library/files/upload");
    assert.equal(init.headers.has("Content-Type"), false);
    assert.ok(init.body instanceof FormData);
    assert.equal(init.body.get("path"), "manuals");
    assert.equal(init.body.get("file").name, "manual.txt");
    return response({ copy: {}, original: {} }, 201);
  };
  await filesApi.upload(
    "library",
    "secret",
    "library",
    "manuals",
    new File(["test"], "manual.txt"),
  );
});
test("copy imports preserve the source location in JSON", async () => {
  const body = {
    source_root_id: "drive",
    source_path: "reports/a.txt",
    destination: "a.txt",
  };
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "/backend/api/v1/library/files/import");
    assert.equal(init.headers.get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(init.body), body);
    return response({ copy: {}, original: {} }, 201);
  };
  await filesApi.mutate("library", "", "/import", body);
});
test("copy failure preserves backend detail and is never retried", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return response({ detail: "Originale conservato; copia non creata." }, 503);
  };
  await assert.rejects(
    filesApi.mutate("library", "", "/import", {}),
    (e) => e.status === 503 && e.message.includes("Originale conservato"),
  );
  assert.equal(calls, 1);
});
test("malformed listing and HTML proxy fallback are rejected", async () => {
  globalThis.fetch = async () =>
    response({
      rootId: "drive",
      path: "",
      writable: true,
      total: 1,
      items: [null],
    });
  await assert.rejects(
    filesApi.children("server", "", "drive", ""),
    (e) => e.kind === "invalid",
  );
  globalThis.fetch = async () =>
    new Response("<html></html>", { headers: { "Content-Type": "text/html" } });
  await assert.rejects(
    filesApi.roots("server", ""),
    (e) => e.kind === "invalid",
  );
});
test("folder names and search strings are correctly URL encoded", async () => {
  globalThis.fetch = async (url) => {
    const params = new URL(url, "http://localhost").searchParams;
    assert.equal(params.get("path"), "A & B");
    assert.equal(params.get("query"), "x&root_id=other");
    return response({
      rootId: "drive",
      path: "A & B",
      writable: true,
      total: 0,
      items: [],
    });
  };
  await filesApi.children("server", "", "drive", "A & B", "x&root_id=other");
});
