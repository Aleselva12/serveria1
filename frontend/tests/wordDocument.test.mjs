import assert from "node:assert/strict";
import { test, afterEach } from "node:test";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import React from "react";
import { create, act } from "react-test-renderer";
const require = createRequire(import.meta.url),
  ext = (n) => JSON.stringify(pathToFileURL(require.resolve(n)).href);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  confirm: () => false,
};
const para = (id, text) => ({
  id,
  text,
  editable: true,
  heading: 0,
  list: false,
  runs: [
    { text, bold: id === "p0", italic: false, underline: false, color: null },
  ],
});
let current,
  conflict = false,
  calls = [];
const reset = () => {
  current = {
    revision: "revision-1",
    editable: true,
    note: "Vista appunti",
    paragraphs: [
      para("p0", "LIDO MARIO"),
      para("p1", "Nota iniziale"),
      para("p2", "Telefono"),
      para("p3", "12345"),
    ],
    blocks: [
      { kind: "paragraph", id: "p0" },
      { kind: "paragraph", id: "p1" },
      {
        kind: "table",
        rows: [
          {
            cells: [
              { colSpan: 1, blocks: [{ kind: "paragraph", id: "p2" }] },
              { colSpan: 1, blocks: [{ kind: "paragraph", id: "p3" }] },
            ],
          },
        ],
      },
    ],
  };
  calls = [];
  conflict = false;
};
reset();
globalThis.__wordApi = {
  word: async () => current,
  download: async () => {},
  saveWord: async (...args) => {
    calls.push(args);
    if (conflict) throw Error("Documento cambiato");
    return {
      ...current,
      revision: "revision-2",
      backupPath: "cora-backup-test.bak",
    };
  },
};
const source = await readFile(
  new URL("../src/components/WordDocument.tsx", import.meta.url),
  "utf8",
);
const code = ts
  .transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  })
  .outputText.replace(/^import ["'][^"']+\.css["'];\s*$/gm, "")
  .replace(
    /from ["'](react\/jsx-runtime|react|lucide-react)["']/g,
    (_, name) => "from " + ext(name),
  )
  .replace(
    /import \{\s*filesApi,?\s*\} from ["']\.\.\/services\/filesApi["'];/,
    "const filesApi=globalThis.__wordApi;",
  );
const Word = (
  await import(
    "data:text/javascript;base64," + Buffer.from(code).toString("base64")
  )
).default;
let renderer;
afterEach(async () => {
  if (renderer) await act(async () => renderer.unmount());
  renderer = null;
  reset();
});
const button = (text) =>
  renderer.root.findAllByType("button").find((b) => b.children.includes(text));
const label = (text, type) =>
  renderer.root
    .findAllByProps({ "aria-label": text })
    .find((n) => !type || n.type === type);
async function mount(editable = true) {
  await act(async () => {
    renderer = create(
      React.createElement(Word, {
        area: "server",
        rootId: "project",
        token: "",
        item: { name: "clienti.docx", path: "clienti.docx" },
        editable,
        close() {},
        saved() {},
      }),
    );
  });
}
test("Word reads formatted paragraphs and tables; read-only resources expose no editing", async () => {
  await mount(false);
  assert.equal(renderer.root.findAllByType("table").length, 1);
  assert.ok(
    renderer.root
      .findAllByType("span")
      .some(
        (n) =>
          n.props.style?.fontWeight === 700 &&
          n.children.includes("LIDO MARIO"),
      ),
  );
  await act(async () =>
    label("Trova cliente o testo", "input").props.onChange({
      target: { value: "LIDO" },
    }),
  );
  assert.equal(
    renderer.root.findAll(
      (n) =>
        typeof n.props.className === "string" &&
        n.props.className.includes("word-match"),
    ).length,
    1,
  );
  assert.equal(button("Modifica documento"), undefined);
  assert.equal(button("Salva con backup"), undefined);
});
test("Word preserves drafts on conflicts and sends exact edits, note anchor and revision", async () => {
  await mount();
  await act(async () => button("Modifica documento").props.onClick());
  await act(async () =>
    label("Modifica paragrafo p1", "button").props.onClick(),
  );
  await act(async () =>
    label("Modifica paragrafo p1", "textarea").props.onChange({
      target: { value: "Nuovo testo cliente" },
    }),
  );
  await act(async () =>
    label("Aggiungi appunto dopo p1", "button").props.onClick(),
  );
  await act(async () =>
    label("Nuovo appunto 1", "textarea").props.onChange({
      target: { value: "01/11/2026\nRichiamare Mario" },
    }),
  );
  conflict = true;
  await act(async () => button("Salva con backup").props.onClick());
  assert.deepEqual(calls[0], [
    "server",
    "",
    "project",
    "clienti.docx",
    "revision-1",
    { p1: "Nuovo testo cliente" },
    [{ after: "p1", text: "01/11/2026\nRichiamare Mario" }],
  ]);
  assert.match(
    renderer.root.findByProps({ role: "alert" }).children.join(""),
    /Documento cambiato/,
  );
  assert.equal(
    label("Nuovo appunto 1", "textarea").props.value,
    "01/11/2026\nRichiamare Mario",
  );
  conflict = false;
  await act(async () => button("Salva con backup").props.onClick());
  assert.equal(button("Salva con backup").props.disabled, true);
  assert.match(
    renderer.root.findByProps({ role: "status" }).children.join(""),
    /cora-backup-test.bak/,
  );
});
test("Word permits a note in an empty document", async () => {
  current = { ...current, paragraphs: [], blocks: [] };
  await mount();
  await act(async () => button("Modifica documento").props.onClick());
  await act(async () => button("Aggiungi appunto").props.onClick());
  await act(async () =>
    label("Nuovo appunto 1", "textarea").props.onChange({
      target: { value: "Primo appunto" },
    }),
  );
  await act(async () => button("Salva con backup").props.onClick());
  assert.equal(calls[0][6][0].after, "end");
});
