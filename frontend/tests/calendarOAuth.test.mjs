import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
const script = await readFile(new URL("../public/google-calendar-callback.js", import.meta.url), "utf8");
async function callback({ key = "browser-secret", response = { connected: true }, status = 200, query = "?state=state1&code=auth-code", networkError = false } = {}) {
  const output = { textContent: "" }, calls = [], removed = [];
  let stripped = false;
  const context = {
    URLSearchParams, AbortController, setTimeout, clearTimeout,
    document: { getElementById: () => output },
    window: { location: { search: query, pathname: "/google-calendar-callback.html" },
      history: { replaceState: (_a, _b, path) => { assert.equal(path, "/google-calendar-callback.html"); stripped = true; } } },
    sessionStorage: { getItem: name => { assert.equal(name, "cora:calendar-oauth:state1"); return key; }, removeItem: name => removed.push(name) },
    fetch: async (url, init) => { assert.ok(stripped); calls.push({ url, init }); if (networkError) throw new Error("offline"); return { ok: status < 400, json: async () => response }; },
  };
  await vm.runInNewContext(script, context);
  return { output, calls, removed, stripped };
}
test("OAuth callback strips code before authenticated same-origin POST and consumes browser key", async () => {
  const { calls, removed, output } = await callback();
  assert.equal(calls.length, 1); assert.equal(calls[0].url, "/backend/api/v1/calendar/google/auth/finish");
  assert.equal(calls[0].init.credentials, "include"); assert.equal(calls[0].init.headers["X-Cora-Client"], "ui");
  assert.deepEqual(JSON.parse(calls[0].init.body), { state: "state1", completion_key: "browser-secret", code: "auth-code", error: "" });
  assert.equal(removed.length, 1); assert.match(output.textContent, /collegato/);
});
test("OAuth callback refuses a redirect from another tab/session without sending its code", async () => {
  const { calls, output, stripped } = await callback({ key: null });
  assert.equal(calls.length, 0); assert.ok(stripped); assert.match(output.textContent, /non riconosciuta/);
});
test("OAuth cancellation is sent as cancellation, not as an empty successful authorization", async () => {
  const { calls, output } = await callback({ query: "?state=state1&error=access_denied", response: { connected: false, cancelled: true } });
  assert.equal(JSON.parse(calls[0].init.body).error, "access_denied"); assert.match(output.textContent, /annullata/);
});
test("OAuth failed completion reports error without retrying authorization exchange", async () => {
  const { calls, output } = await callback({ status: 422, response: { detail: "Sessione scaduta" } });
  assert.equal(calls.length, 1); assert.match(output.textContent, /Sessione scaduta/);
});
