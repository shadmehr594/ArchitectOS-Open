// ==========================================================
// CODER-04 — SAFE CODE BLOCK RENDERING (focused test)
//
// jsdom is NOT installed, so this drives the REAL ui/static/app.js inside a
// minimal DOM shim (node:vm) that builds a real element tree, then inspects
// what renderRichText() produced.
//
// Run:  node tests/coder_04_code_block_render_test.js
// ==========================================================

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const APP = fs.readFileSync(path.join(ROOT, "ui", "static", "app.js"), "utf8");

let failures = 0;
function check(name, cond, detail) {
  const ok = !!cond;
  if (!ok) failures += 1;
  console.log((ok ? "  PASS  " : "  FAIL  ") + name + (detail ? "  | " + detail : ""));
}

// ---------------- minimal DOM that builds a REAL tree ----------------
function makeNode(tag) {
  return {
    nodeType: 1,
    _tag: tag || "div",
    tagName: (tag || "div").toUpperCase(),
    className: "", type: "", style: {}, dataset: {}, attrs: {},
    childNodes: [], textContent: "",
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
    appendChild(n) { this.childNodes.push(n); return n; },
    removeChild(n) { const i = this.childNodes.indexOf(n); if (i >= 0) this.childNodes.splice(i, 1); return n; },
    addEventListener() {}, removeEventListener() {}, focus() {}, blur() {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    querySelector() { return null; }, querySelectorAll() { return []; },
    remove() {}, cloneNode() { return makeNode(this._tag); },
    get firstChild() { return this.childNodes[0] || null; },
  };
}
function makeText(t) { return { nodeType: 3, _text: String(t) }; }

const document = {
  createElement(t) { return makeNode(t); },
  createTextNode(t) { return makeText(t); },
  createDocumentFragment() { return makeNode("#fragment"); },
  getElementById() { return makeNode("div"); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  body: makeNode("body"),
  documentElement: makeNode("html"),
  readyState: "loading",
};

const ctx = {
  document,
  window: { addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }), location: { hash: "", href: "http://x/" } },
  location: { hash: "", href: "http://x/", search: "" },
  navigator: { userAgent: "node", language: "fa" },
  console, setTimeout, clearTimeout, Date, JSON, Math, String, Number, Boolean,
  Object, Array, RegExp, Error, Promise, Map, Set, isNaN, parseInt, parseFloat,
  URL: { revokeObjectURL() {}, createObjectURL() { return "blob:x"; } },
  fetch: () => Promise.reject(new Error("no network")),
  FormData: function () {},
  requestAnimationFrame: (f) => setTimeout(f, 0),
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(APP, ctx, { filename: "app.js" });

const renderRichText = ctx.renderRichText;
check("renderRichText is exported by app.js", typeof renderRichText === "function");

// ---------------- tree helpers ----------------
function textOf(node) {
  if (!node) return "";
  if (node.nodeType === 3) return node._text;
  if (node.textContent && !node.childNodes.length) return String(node.textContent);
  let out = "";
  for (const c of node.childNodes) out += textOf(c);
  return out;
}
function findAll(node, pred, acc) {
  acc = acc || [];
  if (pred(node)) acc.push(node);
  (node.childNodes || []).forEach((c) => findAll(c, pred, acc));
  return acc;
}
const isTag = (t) => (n) => n.nodeType === 1 && n._tag.toLowerCase() === t;
function render(text) { return renderRichText(text); }

// ---------------- 1. Python block: exact fidelity ----------------
const PY = [
  "```python",
  "import sys",
  "",
  "class Calc:",
  "    def __init__(self):",
  "        self.v = 0",
  "",
  "    def total(self, a, b=2**3):",
  '        msg = """line one',
  "        line two\"\"\"",
  "        return a + b  # 1 <= 2 and 3 >= 2",
  "",
  "if __name__ == '__main__':",
  "    print(Calc().total(1, 2))",
  "```",
].join("\n");

const pyTree = render(PY);
const preNodes = findAll(pyTree, isTag("pre"));
const codeNodes = findAll(pyTree, isTag("code"));
check("one <pre> for one fence", preNodes.length === 1, "pre=" + preNodes.length);
check("one <code> for one fence", codeNodes.length === 1, "code=" + codeNodes.length);

const expectedCode = PY.split("\n").slice(1, -1).join("\n");
check("code text is EXACT (indentation, blanks, __name__, **, >=, triple-quote)",
  codeNodes[0] && codeNodes[0].textContent === expectedCode);
check("code node is dir=ltr", codeNodes[0] && codeNodes[0].getAttribute("dir") === "ltr");
check("no <strong>/<em> inside code (no markdown emphasis)",
  findAll(codeNodes[0] || makeNode("x"), (n) => n._tag === "strong" || n._tag === "em").length === 0);
check("language label rendered", textOf(pyTree).indexOf("python") !== -1);
check("copy control present", findAll(pyTree, (n) => n._tag === "button").length === 1);

// ---------------- 2. Persian text before AND after code ----------------
const MIXED = [
  "این کد نمونه است:",
  "```python",
  "x = 1",
  "```",
  "و این هم توضیح پس از کد.",
].join("\n");
const mixedTree = render(MIXED);
const paras = findAll(mixedTree, isTag("p"));
const mixedText = textOf(mixedTree);
check("Persian before code preserved", mixedText.indexOf("این کد نمونه است:") !== -1);
check("Persian after code preserved", mixedText.indexOf("و این هم توضیح پس از کد.") !== -1);
check("paragraphs are still <p>", paras.length >= 2, "p=" + paras.length);
check("code block still present", findAll(mixedTree, isTag("pre")).length === 1);

// ---------------- 3. Two code blocks in one reply ----------------
const TWO = "```bash\necho hi\n```\n\nمتن میان دو بلوک\n\n```javascript\nconst a = 1;\n```";
const twoTree = render(TWO);
check("two code blocks render", findAll(twoTree, isTag("pre")).length === 2);
const langs = findAll(twoTree, (n) => n.className === "msg-code-lang").map((n) => textOf(n));
check("both languages labelled", langs.join(",") === "bash,javascript", langs.join(","));

// ---------------- 4. Malformed / unfinished fence (no crash) ----------------
let malformedOk = true;
let malformedPre = 0;
try {
  const bad = render("```python\nprint('unclosed')");
  malformedPre = findAll(bad, isTag("pre")).length;
} catch (e) { malformedOk = false; }
check("unclosed fence does not crash", malformedOk);
check("unclosed fence still yields a code block", malformedPre === 1, "pre=" + malformedPre);

// ---------------- 5. Ordinary messages unchanged ----------------
const plain = render("سلام، خوبی؟\n\n- یک\n- دو\n\n**پررنگ**");
check("plain paragraph/list/bold still render",
  findAll(plain, isTag("p")).length >= 1 &&
  findAll(plain, isTag("ul")).length === 1 &&
  findAll(plain, isTag("strong")).length === 1);
check("no <pre> for a message without a fence", findAll(plain, isTag("pre")).length === 0);

console.log(failures === 0 ? "\nCODER_04_CODE_BLOCK_RENDER: ALL PASS" : "\nFAILURES: " + failures);
process.exit(failures === 0 ? 0 : 1);
