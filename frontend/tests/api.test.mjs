import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Run the actual TypeScript adapter under Node; only Vite's environment lookup is replaced.
const source = (
  await readFile(new URL("../src/services/api.ts", import.meta.url), "utf8")
).replace("import.meta.env.VITE_API_BASE_URL", "undefined");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const { api, ApiError } = await import(
  "data:text/javascript;base64," + Buffer.from(compiled).toString("base64")
);
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});
const jsonResponse = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const health = {
  status: "ok",
  ollama_online: false,
  model: "local-model",
  agents: ["Audio Agent"],
};

test("health calls the existing endpoint and preserves Ollama offline state", async () => {
  globalThis.fetch = async (url) => {
    assert.equal(url, "/backend/health");
    return jsonResponse(health);
  };
  assert.deepEqual(await api.health(), health);
});
test("chat uses message/thread_id without the proposed /api/v1 contract", async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "/backend/chat");
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), {
      message: "Test",
      thread_id: "thread-123",
    });
    return jsonResponse({
      response: "Real backend response",
      thread_id: "thread-123",
    });
  };
  assert.equal(
    (await api.chat("Test", "thread-123")).response,
    "Real backend response",
  );
});
test("registry consumes capability IDs from the actual backend schema", async () => {
  const registry = {
    project: "Cora",
    component_count: 1,
    components: [
      {
        id: "supervisor",
        name: "Cora",
        available: true,
        capabilities: [{ id: "route_requests", description: "Route" }],
      },
    ],
  };
  globalThis.fetch = async (url) => {
    assert.equal(url, "/backend/capabilities");
    return jsonResponse(registry);
  };
  assert.deepEqual(await api.registry(), registry);
});
test("a missing endpoint is explicitly classified as unimplemented", async () => {
  globalThis.fetch = async () => jsonResponse({ detail: "Not Found" }, 404);
  await assert.rejects(
    api.registry(),
    (error) => error instanceof ApiError && error.kind === "missing",
  );
});
test("HTTP failure does not invent a successful chat response", async () => {
  globalThis.fetch = async () => jsonResponse({ detail: "Failed" }, 500);
  await assert.rejects(
    api.chat("Test", "thread-123"),
    (error) => error.kind === "http" && error.status === 500,
  );
});
test("network failure is reported as offline", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("network down");
  };
  await assert.rejects(api.health(), (error) => error.kind === "offline");
});
test("proxy unavailability is reported as offline instead of an absent feature", async () => {
  globalThis.fetch = async () => jsonResponse({ detail: "Bad Gateway" }, 502);
  await assert.rejects(
    api.health(),
    (error) => error.kind === "offline" && error.status === 502,
  );
});
test("an HTML proxy fallback cannot be mistaken for a connected backend", async () => {
  globalThis.fetch = async () =>
    new Response("<html>Vite</html>", {
      headers: { "Content-Type": "text/html" },
    });
  await assert.rejects(api.health(), (error) => error.kind === "invalid");
});
test("malformed and null health payloads are rejected", async () => {
  for (const value of [null, {}, { ...health, ollama_online: "yes" }]) {
    globalThis.fetch = async () => jsonResponse(value);
    await assert.rejects(api.health(), (error) => error.kind === "invalid");
  }
});
test("invalid JSON and invalid registry entries are rejected", async () => {
  globalThis.fetch = async () =>
    new Response("{broken", {
      headers: { "Content-Type": "application/json" },
    });
  await assert.rejects(api.health(), (error) => error.kind === "invalid");
  globalThis.fetch = async () => jsonResponse({ components: [null] });
  await assert.rejects(api.registry(), (error) => error.kind === "invalid");
});
