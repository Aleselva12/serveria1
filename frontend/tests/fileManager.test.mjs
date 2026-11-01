import assert from "node:assert/strict";
import { test, afterEach } from "node:test";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import React from "react";
import { create, act } from "react-test-renderer";
const require = createRequire(import.meta.url);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.document = { addEventListener() {}, removeEventListener() {} };
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  location: { origin: "http://cora.test" },
  confirm: () => true,
};
const jsURL = (code) =>
  "data:text/javascript;base64," + Buffer.from(code).toString("base64");
const cache = new Map();
async function component(name) {
  if (cache.has(name)) return cache.get(name);
  const source = await readFile(
    new URL("../src/components/" + name + ".tsx", import.meta.url),
    "utf8",
  );
  let code = ts
    .transpileModule(source, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
      },
    })
    .outputText.replace(/^import ["'][^"']+\.css["'];\s*$/gm, "");
  const imports = [
    ...new Set([...code.matchAll(/from ["']([^"']+)["']/g)].map((m) => m[1])),
  ];
  for (const dependency of imports) {
    let target;
    if (dependency === "../services/filesApi")
      target = jsURL("export const filesApi=globalThis.__driveApi;");
    else if (dependency === "../services/libraryMonitorApi")
      target = jsURL(
        "export const libraryMonitorApi={status:async()=>({folders:[]}),setFolder:async()=>({folders:[]})};",
      );
    else if (dependency === "../services/sharedFiles")
      target = jsURL("export const sharePageUrl=(url,origin)=>origin+url;");
    else if (dependency.startsWith("./"))
      target = await component(dependency.slice(2));
    else target = pathToFileURL(require.resolve(dependency)).href;
    code = code
      .replaceAll(JSON.stringify(dependency), JSON.stringify(target))
      .replaceAll("'" + dependency + "'", JSON.stringify(target));
  }
  const url = jsURL(code);
  cache.set(name, url);
  return url;
}
const node = (path, kind = "file", capabilities = ["download"]) => ({
  path,
  name: path.split("/").at(-1),
  kind,
  capabilities,
  sizeBytes: kind === "folder" ? null : 42,
  modifiedAt: "2026-11-01T09:00:00Z",
  mimeType: "text/plain",
});
const root = (id, label, writable) => ({
  id,
  label,
  writable,
  available: true,
  storage: { freeBytes: 100, totalBytes: 1000 },
});
let calls = [],
  mutations = [],
  previews = 0;
globalThis.__driveApi = {
  roots: async (area) =>
    area === "server"
      ? [
          root("server", "Intero server Debian", false),
          root("project", "Progetto Cora", true),
        ]
      : [root("library", "Libreria IA", true)],
  children: async (area, token, rootId, path, search, offset, recursive) => {
    calls.push({ area, rootId, path, search, offset, recursive });
    const items =
      rootId === "project"
        ? [
            node("src/nested.py", "file", [
              "download",
              "rename",
              "copy",
              "move",
              "trash",
            ]),
          ]
        : rootId === "library"
          ? [node("copia.txt")]
          : path === ""
            ? [node("srv", "folder", ["read"]), node("note.txt")]
            : [node("progetti", "folder", ["read"])];
    return {
      rootId,
      path,
      writable: rootId !== "server",
      total: items.length,
      items,
    };
  },
  preview: async () => {
    previews++;
    return {
      kind: "text",
      text: "Anteprima del contenuto reale",
      url: "",
      mime: "",
      truncated: false,
    };
  },
  mutate: async (...args) => {
    mutations.push(args);
    return {};
  },
  trashList: async () => [],
  shares: async () => ({ items: [] }),
  download: async () => {},
};
const Manager = (await import(await component("FileManager"))).default;
const Visual = await import(await component("FileVisual"));
let renderer;
afterEach(async () => {
  if (renderer) await act(async () => renderer.unmount());
  renderer = null;
  calls = [];
  mutations = [];
});
async function mount() {
  await act(async () => {
    renderer = create(React.createElement(Manager));
  });
  return renderer.root;
}
const byLabel = (label) => renderer.root.findByProps({ "aria-label": label });
const button = (text) =>
  renderer.root
    .findAllByType("button")
    .find((b) => b.children.some((child) => child === text));

test("Drive layout keeps tabs, both libraries, list switch and real preview", async () => {
  await mount();
  assert.equal(
    renderer.root.findAllByProps({ className: "drive-file-card" }).length,
    1,
  );
  assert.equal(byLabel("Vista griglia").props["aria-pressed"], true);
  assert.ok(previews > 0);
  assert.equal(
    renderer.root.findByProps({ className: "drive-upload-button" }).props
      .disabled,
    true,
  );
  assert.equal(
    renderer.root
      .findAllByType("button")
      .filter((b) => b.props.title === "Modifica testo").length,
    0,
  );
  await act(async () => byLabel("Apri anteprima note.txt").props.onClick());
  assert.ok(
    renderer.root
      .findAllByProps({ "aria-label": "Anteprima note.txt" })
      .some((n) => n.props.role === "dialog"),
  );
  await act(async () => byLabel("Chiudi anteprima").props.onClick());
  await act(async () => byLabel("Vista elenco").props.onClick());
  assert.equal(renderer.root.findAllByType("table").length, 1);
  await act(async () =>
    byLabel("Espandi Intero server Debian").props.onClick(),
  );
  const srv = renderer.root
    .findAllByType("button")
    .find((b) => b.props.title === "srv · Sola lettura");
  assert.ok(srv);
  await act(async () => srv.props.onClick());
  assert.ok(calls.some((c) => c.path === "srv" && c.rootId === "server"));
  await act(async () => byLabel("Cartella superiore").props.onClick());
  assert.equal(calls.at(-1).path, "");
});

test("resource selection changes writable actions and IA tab uses its own API", async () => {
  await mount();
  const project = renderer.root
    .findAllByType("button")
    .find((b) => b.props.title === "Progetto Cora");
  await act(async () => project.props.onClick());
  assert.equal(
    renderer.root.findByProps({ className: "drive-upload-button" }).props
      .disabled,
    false,
  );
  assert.equal(
    renderer.root
      .findAllByType("button")
      .filter((b) => b.props.title === "Modifica testo").length,
    1,
  );
  await act(async () => byLabel("Rinomina nested.py").props.onClick());
  const input = renderer.root
    .findAllByType("input")
    .find((n) => n.props.autoFocus);
  await act(async () =>
    input.props.onChange({ target: { value: "renamed.py" } }),
  );
  await act(async () =>
    renderer.root.findByType("form").props.onSubmit({ preventDefault() {} }),
  );
  assert.equal(mutations[0][3].destination, "src/renamed.py");
  await act(async () =>
    renderer.root.findByProps({ id: "library-tab" }).props.onClick(),
  );
  assert.ok(calls.some((c) => c.area === "library" && c.rootId === "library"));
  assert.equal(
    renderer.root.findByProps({ className: "drive-upload-button" }).props
      .disabled,
    false,
  );
  assert.ok(button("Copia dal server"));
});

test("search keeps root and recursive scope, thumbnail eligibility excludes heavy and unsafe formats", async () => {
  await mount();
  const include = renderer.root
    .findAllByType("input")
    .find((n) => n.props.type === "checkbox");
  await act(async () => include.props.onChange({ target: { checked: true } }));
  await act(async () =>
    byLabel("Cerca per nome").props.onChange({ target: { value: "note" } }),
  );
  await act(async () => new Promise((resolve) => setTimeout(resolve, 280)));
  assert.ok(
    calls.some(
      (c) =>
        c.search === "note" && c.recursive === true && c.rootId === "server",
    ),
  );
  assert.equal(
    Visual.canShowThumbnail({
      ...node("photo.png"),
      sizeBytes: 3 * 1024 * 1024,
    }),
    false,
  );
  assert.equal(Visual.canShowThumbnail(node("unsafe.svg")), false);
  assert.equal(Visual.canShowThumbnail(node("photo.png")), true);
  assert.equal(Visual.canShowThumbnail(node("linked.png", "link")), false);
});

test("thumbnail queue is bounded and blob URLs are released when previews are disabled", async () => {
  const original = globalThis.__driveApi.preview;
  const revoke = URL.revokeObjectURL;
  const released = [];
  const pending = [];
  let active = 0,
    max = 0;
  URL.revokeObjectURL = (url) => released.push(url);
  globalThis.__driveApi.preview = async (_area, _token, _root, item) => {
    active++;
    max = Math.max(max, active);
    return new Promise((resolve) =>
      pending.push(() => {
        active--;
        resolve({
          kind: "media",
          text: "",
          mime: "image/png",
          url: "blob:" + item.path,
          truncated: false,
        });
      }),
    );
  };
  const cards = (enabled) =>
    React.createElement(
      React.Fragment,
      null,
      ...Array.from({ length: 6 }, (_, i) =>
        React.createElement(Visual.default, {
          key: i,
          area: "server",
          rootId: "project",
          token: "",
          item: node("photo" + i + ".png"),
          enabled,
        }),
      ),
    );
  try {
    await act(async () => {
      renderer = create(cards(true));
    });
    assert.equal(pending.length, 3);
    await act(async () => {
      pending.splice(0).forEach((resolve) => resolve());
    });
    assert.equal(pending.length, 3);
    await act(async () => {
      pending.splice(0).forEach((resolve) => resolve());
    });
    assert.equal(max, 3);
    assert.equal(renderer.root.findAllByType("img").length, 6);
    await act(async () => renderer.update(cards(false)));
    assert.equal(new Set(released).size, 6);
    assert.equal(renderer.root.findAllByType("img").length, 0);
  } finally {
    await act(async () => {
      pending.splice(0).forEach((resolve) => resolve());
    });
    globalThis.__driveApi.preview = original;
    URL.revokeObjectURL = revoke;
  }
});
