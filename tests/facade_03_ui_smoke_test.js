// ==========================================================
// FACADE-03 — BROWSER UI SMOKE TEST (two-file selection + A/B order)
//
// jsdom is NOT installed, so this drives the REAL ui/static/app.js inside a
// minimal DOM shim (node:vm). It verifies the actual production functions:
//   * #imageInput has `multiple`                (index.html)
//   * onAttach() keeps the ordered A/B list     (app.js)
//   * onAttach() labels the roles A/B           (app.js)
//   * onAttach() rejects >2 with a clear error  (app.js)
//   * sendMessage() sends image_a/image_b for 2 files, `image` for 1
//
// NO render is submitted; only the client-side attachment logic runs.
//
// Run:  node tests/facade_03_ui_smoke_test.js
// ==========================================================

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const HTML = fs.readFileSync(path.join(ROOT, "ui", "templates", "index.html"), "utf8");
const APP = fs.readFileSync(path.join(ROOT, "ui", "static", "app.js"), "utf8");

let failures = 0;
function check(name, cond, detail) {
  const ok = !!cond;
  if (!ok) failures += 1;
  console.log((ok ? "  PASS  " : "  FAIL  ") + name + (detail ? "  | " + detail : ""));
}

// ---------------- minimal DOM shim ----------------
function makeEl(id) {
  return {
    id, value: "", textContent: "", innerHTML: "", className: "", disabled: false,
    style: {}, dataset: {}, options: [], scrollHeight: 0, tagName: "DIV",
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    appendChild() {}, removeChild() {}, insertBefore() {}, focus() {}, blur() {},
    setAttribute() {}, getAttribute() { return null; }, addEventListener() {},
    removeEventListener() {}, querySelector() { return makeEl("q"); },
    querySelectorAll() { return []; }, closest() { return null; },
    getContext() { return null; }, remove() {}, cloneNode() { return makeEl(id); },
  };
}
const els = {};
const document = {
  getElementById(id) { return (els[id] = els[id] || makeEl(id)); },
  createElement(tag) { return makeEl(tag); },
  querySelector() { return makeEl("q"); },
  querySelectorAll() { return []; },
  addEventListener() {},
  body: makeEl("body"),
  documentElement: makeEl("html"),
  readyState: "loading",
};
const sandbox = {
  document,
  window: { addEventListener() {}, location: { hash: "", href: "http://x/" }, matchMedia: () => ({ matches: false, addEventListener() {} }) },
  location: { hash: "", href: "http://x/", search: "" },
  navigator: { userAgent: "node", language: "fa" },
  console,
  setTimeout, clearTimeout, setInterval, clearInterval,
  fetch: async () => ({ ok: true, status: 200, json: async () => ({}), text: async () => "" }),
  AbortController: class { constructor() { this.signal = {}; } abort() {} },
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL() {} },
  FormData: class {
    constructor() { this._entries = []; }
    append(k, v) { this._entries.push([k, v]); }
    keys() { return this._entries.map((e) => e[0])[Symbol.iterator](); }
  },
  Blob: class {}, Event: class {}, CustomEvent: class {},
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
};
sandbox.globalThis = sandbox;
sandbox.window.document = document;

const ctx = vm.createContext(sandbox);

// ---------------- index.html ----------------
console.log("\n[1] index.html — two-file input");
const inputTag = (HTML.match(/<input id="imageInput"[^>]*>/) || [""])[0];
check("#imageInput present", inputTag.includes('id="imageInput"'), inputTag);
check("#imageInput has `multiple`", /\bmultiple\b/.test(inputTag), inputTag);

// ---------------- load real app.js ----------------
console.log("\n[2] load real app.js in a DOM shim");
try {
  vm.runInContext(APP, ctx, { filename: "app.js" });
  check("app.js evaluated without throwing", true);
} catch (e) {
  check("app.js evaluated without throwing", false, e.message);
  process.exit(1);
}
check("onAttach is callable", typeof ctx.onAttach === "function");

function file(name, type) { return { name, type: type || "image/jpeg", size: 1234 }; }

// ---------------- onAttach: 2 files, A/B order ----------------
console.log("\n[3] onAttach — two files keep A/B order and label roles");
try {
  ctx.onAttach({ target: { files: [file("A_STYLE.jpg"), file("B01_RAW.jpg")] } });
  const chip = document.getElementById("attachChip").textContent;
  check("chip labels A (style) first", /A \(style\):\s*A_STYLE\.jpg/.test(chip), chip);
  check("chip labels B (target) second", /B \(target\):\s*B01_RAW\.jpg/.test(chip), chip);
  check("A appears before B in the chip", chip.indexOf("A_STYLE.jpg") < chip.indexOf("B01_RAW.jpg"), chip);
} catch (e) {
  check("onAttach two-file run", false, e.message);
}

// ---------------- onAttach: 1 file (legacy) ----------------
console.log("\n[4] onAttach — single file (legacy behaviour preserved)");
try {
  ctx.onAttach({ target: { files: [file("B01_RAW.jpg")] } });
  const chip = document.getElementById("attachChip").textContent;
  check("single file shows 'Attached:'", /^Attached:\s*B01_RAW\.jpg/.test(chip), chip);
} catch (e) {
  check("onAttach single-file run", false, e.message);
}

// ---------------- onAttach: 3 files rejected ----------------
console.log("\n[5] onAttach — three files rejected with a clear message");
try {
  ctx.onAttach({ target: { files: [file("A_STYLE.jpg"), file("B01_RAW.jpg"), file("B02_RAW.jpg")] } });
  const chip = document.getElementById("attachChip").textContent;
  check("chip reports too many images", /too many images/i.test(chip), chip);
} catch (e) {
  check("onAttach three-file run", false, e.message);
}

// ---------------- sendMessage FormData mapping (static) ----------------
console.log("\n[6] sendMessage — multipart field mapping (source-verified)");
check("two files -> image_a + image_b",
  /files\.length\s*>=\s*2[\s\S]{0,120}append\(\s*["']image_a["'][\s\S]{0,120}append\(\s*["']image_b["']/.test(APP));
check("single file -> legacy `image` field",
  /else\s*\{[\s\S]{0,80}append\(\s*["']image["']/.test(APP));

console.log("\n=== UI SMOKE RESULT: " + (failures === 0 ? "ALL PASSED" : failures + " FAILED") + " ===");
process.exit(failures === 0 ? 0 : 1);
