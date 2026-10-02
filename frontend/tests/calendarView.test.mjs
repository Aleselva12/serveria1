import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import React from "react";
import { create, act } from "react-test-renderer";
const require = createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  confirm() {
    return true;
  },
};
const compile = (s) =>
  ts.transpileModule(s, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
const url = (s) =>
  "data:text/javascript;base64," + Buffer.from(s).toString("base64");
const timeURL = url(
  compile(
    await readFile(
      new URL("../src/services/calendarTime.ts", import.meta.url),
      "utf8",
    ),
  ),
);
const time = await import(timeURL);
let events = [],
  proposals = [],
  fail = false;
const saved = (data) => ({
  ...data,
  id: "evt",
  version: 1,
  created_by: "user",
  updated_by: "user",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  deleted_at: null,
});
globalThis.__calendarViewApi = {
  list: async (start, end, token, deleted) => {
    if (fail) throw new Error("DB offline");
    return deleted ? [] : events;
  },
  proposals: async () => proposals,
  save: async (data, token, event) => {
    if (fail) throw new Error("Save failed");
    const result = saved(data);
    events = [result];
    return result;
  },
  history: async () => [],
  resolve: async () => {
    proposals = [];
    return { event: null };
  },
};
let source = await readFile(
  new URL("../src/components/Calendar.tsx", import.meta.url),
  "utf8",
);
source = source.replace(
  /import \{ calendarApi \} from "..\/services\/calendarApi";/,
  "const calendarApi=globalThis.__calendarViewApi;",
);
let output = compile(source).replace(
  'from "../services/calendarTime"',
  "from " + JSON.stringify(timeURL),
);
for (const pkg of ["react", "react/jsx-runtime", "lucide-react"])
  output = output.replaceAll(
    "from " + JSON.stringify(pkg),
    "from " + JSON.stringify(pathToFileURL(require.resolve(pkg)).href),
  );
const { default: Calendar } = await import(url(output));
const button = (r, label) =>
  r.root.findAllByType("button").find((b) => b.children.join("") === label);
async function mount() {
  let r;
  await act(async () => {
    r = create(React.createElement(Calendar));
  });
  return r;
}
async function unmount(r) {
  await act(async () => r.unmount());
}
test("manual event appears in month/day and is loaded again after reopening", async () => {
  events = [];
  proposals = [];
  fail = false;
  let r = await mount();
  const title = () =>
    r.root.findAllByType("input").find((i) => i.props.maxLength === 200);
  await act(async () =>
    title().props.onChange({ target: { value: "Cliente" } }),
  );
  await act(async () =>
    r.root.findByType("form").props.onSubmit({ preventDefault() {} }),
  );
  assert.equal(events[0].title, "Cliente");
  assert.ok(r.root.findAllByProps({ className: "calendar-event" }).length);
  await act(async () => button(r, "Giorno").props.onClick());
  assert.equal(
    r.root.findAllByProps({ className: "calendar-timed-event" }).length,
    1,
  );
  await unmount(r);
  r = await mount();
  assert.equal(
    r.root.findAllByProps({ className: "calendar-event" }).length,
    1,
  );
  await unmount(r);
});
test("failed write preserves the form and displays an error", async () => {
  events = [];
  proposals = [];
  fail = false;
  const r = await mount();
  await act(async () =>
    r.root
      .findAllByType("input")
      .find((i) => i.props.maxLength === 200)
      .props.onChange({ target: { value: "Do not lose" } }),
  );
  fail = true;
  await act(async () =>
    r.root.findByType("form").props.onSubmit({ preventDefault() {} }),
  );
  assert.equal(
    r.root.findAllByType("input").find((i) => i.props.maxLength === 200).props
      .value,
    "Do not lose",
  );
  assert.equal(
    r.root.findByProps({ role: "alert" }).children[0],
    "Save failed",
  );
  await unmount(r);
  fail = false;
});
test("agent proposal is visible and resolved through approval control", async () => {
  events = [];
  fail = false;
  proposals = [
    {
      id: "p",
      actor: "supervisor",
      action: "create",
      payload: {
        title: "Proposta",
        start: time.dayStart(time.romeToday()),
        end: time.dayStart(time.shiftDay(time.romeToday(), 1)),
      },
      previous: {},
      reason: "Richiesta",
    },
  ];
  const r = await mount();
  assert.ok(button(r, "Approva"));
  await act(async () => button(r, "Approva").props.onClick());
  assert.equal(proposals.length, 0);
  assert.equal(button(r, "Approva"), undefined);
  await unmount(r);
});
