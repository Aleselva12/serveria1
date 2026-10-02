import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = (
  await readFile(
    new URL("../src/services/calendarApi.ts", import.meta.url),
    "utf8",
  )
).replace(
  'import { apiBaseUrl } from "./api";',
  'const apiBaseUrl="/backend";',
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const { calendarApi } = await import(
  "data:text/javascript;base64," + Buffer.from(compiled).toString("base64")
);
const originalFetch = globalThis.fetch;
afterEach(() => (globalThis.fetch = originalFetch));
const event = {
  id: "id",
  title: "Meeting",
  start: "2026-10-02T09:00:00+02:00",
  end: "2026-10-02T10:00:00+02:00",
  all_day: false,
  notes: "",
  version: 2,
  created_by: "user",
  updated_by: "user",
};
const json = (value, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
test("calendar sends token only as header and encodes range offsets", async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(init.headers.Authorization, "Bearer secret");
    assert.ok(!url.includes("secret"));
    assert.ok(url.includes("%2B02%3A00"));
    return json([event]);
  };
  assert.equal(
    (await calendarApi.list(event.start, event.end, "secret"))[0].id,
    "id",
  );
});
test("update and delete carry the displayed event version", async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(init.method, "PATCH");
    assert.equal(JSON.parse(init.body).version, 2);
    return json(event);
  };
  await calendarApi.save(event, "", event);
  globalThis.fetch = async (url, init) => {
    assert.equal(init.method, "DELETE");
    assert.ok(url.endsWith("?version=2"));
    return json(event);
  };
  await calendarApi.remove(event, "");
});
test("409 keeps detail and does not retry mutating requests", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return json({ detail: "Evento cambiato: riaprilo" }, 409);
  };
  await assert.rejects(() => calendarApi.remove(event, ""), /Evento cambiato/);
  assert.equal(calls, 1);
});
test("malformed lists and proxy HTML are rejected before rendering", async () => {
  globalThis.fetch = async () => json([{ ...event, start: "invalid" }]);
  await assert.rejects(
    () => calendarApi.list(event.start, event.end, ""),
    /non validi/,
  );
  globalThis.fetch = async () =>
    new Response("<html>fallback</html>", {
      headers: { "Content-Type": "text/html" },
    });
  await assert.rejects(
    () => calendarApi.list(event.start, event.end, ""),
    /non valida/,
  );
});
