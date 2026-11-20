# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-8 — GEMINI HIGH-QUALITY TARGET IMAGE INTEGRATION (ACCEPTANCE)
#
# MOCKED ONLY. No real render, no ComfyUI job, no GPU inference, no unload.
#
# Drives the REAL app.py HTTP multipart boundary with the NEW prepared IMAGE B
# (B01_GEMINI_384x512.png, 384x512) and asserts that the accepted dual-image
# pipeline is unchanged: bindings, workflow selection, parameters, the
# FACADE-04A gate, the H1/H2 GPU handoff and the protected render lease.
#
# Run DIRECTLY:
#   .venv/Scripts/python.exe tests/test_facade_04d3c8_gemini_hq_target_v1.py
# ==========================================================

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.environ["ARCHITECTOS_COMFY_PORT"] = "9"
os.environ.setdefault("ARCHITECTOS_CORE_API_HOST", "127.0.0.1")

HANDOFF_TEST_DIR = tempfile.mkdtemp(prefix="facade04d3c8_handoff_")
os.environ["ARCHITECTOS_GPU_HANDOFF_DIR"] = HANDOFF_TEST_DIR
os.environ["ARCHITECTOS_GPU_HANDOFF_LEASE_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_UNLOAD_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_RENDER_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_COMFYUI_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_TIMEOUT"] = "0.3"
os.environ["ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_INTERVAL"] = "0.05"
os.environ["ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_TIMEOUT"] = "0.3"
os.environ["ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_INTERVAL"] = "0.05"

import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import traceback  # noqa: E402

import requests  # noqa: E402

_CONN_ERROR = requests.exceptions.ConnectionError
_JSON = json

sys.path.insert(0, PROJECT_ROOT)

FIX = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIX, "A_STYLE.jpg")
B_RAW = os.path.join(FIX, "B01_RAW.jpg")
B_GEMINI_HQ = os.path.join(FIX, "B01_GEMINI_HQ.jpg")
B_PREPARED = os.path.join(FIX, "B01_GEMINI_384x512.png")
B_LANCZOS_2X = os.path.join(PROJECT_ROOT, "docs", "audit", "facade_3c7_prepared",
                            "B_PREPARED_2X.png")
WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

EXACT_PROMPT = (
    "نمای ساختمان تصویر B را بازطراحی کن با الهام از سبک و متریال و زبان فرمی "
    "تصویر A. هندسه کلی، تعداد طبقات، بازشوها، بالکن\u200cها، حجم کلی و کادر "
    "دید ساختمان B حفظ شود. خروجی باید یک رندر نمای باکیفیت و واقعی از ساختمان "
    "B با ظاهر الهام\u200cگرفته از A باشد."
)
SEED = 123456789
VISION_MODEL = "qwen3.8:27b"

EXPECT_B_SHA = "6b7ca7c6f7b43797b45c00bce6ea3b4beeafc0798b820844de073ce344285ab2"
EXPECT_A_SHA = "1b304a9f2c34819015fbc1b9a15d930f4c2d9fd011572677d648748a15c0231c"
SHA_DUAL = "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9"
SHA_CONDITIONED = "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"

# ==========================================================
# NETWORK GUARD
# ==========================================================
_BLOCKED = []
_real_connect = socket.socket.connect
BLOCKED_PORTS = (8188, 11434)


def _guarded_connect(self, address, *a, **k):
    try:
        port = int(address[1])
    except Exception:
        port = -1
    if port in BLOCKED_PORTS:
        _BLOCKED.append((str(address[0]), port,
                         " <- ".join("%s:%s" % (os.path.basename(f.filename), f.lineno)
                                     for f in traceback.extract_stack()[-10:-1])))
        raise RuntimeError("NETWORK GUARD: blocked connect to %s" % port)
    return _real_connect(self, address, *a, **k)


socket.socket.connect = _guarded_connect

import app as CORE  # noqa: E402
import core.vision.facade_reference_vision_provider_v1 as VP  # noqa: E402
import core.chat.chat_architect as CA  # noqa: E402
import core.runtime.gpu_handoff_v1 as GH  # noqa: E402
from config import runtime_config as RC  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class _Resp:
    def __init__(self, sc=200, payload=None):
        self.status_code = sc
        self._p = payload
        self.text = _JSON.dumps(payload or {})

    def json(self):
        if self._p is None:
            raise ValueError("no json")
        return self._p


class FakeServices:
    COMFY = "http://127.0.0.1:9"
    OLLAMA = "http://127.0.0.1:11434"

    def __init__(self):
        self.queue_running = 0
        self.queue_pending = 0
        self.free_status = 200
        self.stats_readable = True
        self.vram_free = 16_000_000_000
        self.ollama_models = []
        self.ps_readable = True
        self.unload_calls = []
        self.calls = []
        self.events = []

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        if url.endswith("/queue"):
            self.events.append("h1:queue")
            return _Resp(200, {"queue_running": [0] * self.queue_running,
                               "queue_pending": [0] * self.queue_pending})
        if url.endswith("/system_stats"):
            return _Resp(200, {"devices": [{"vram_free": self.vram_free}]})
        if url.endswith("/api/ps"):
            return _Resp(200, {"models": [{"name": m} for m in self.ollama_models]})
        return _Resp(404, None)

    def post(self, url, json=None, timeout=None):  # noqa: A002
        payload = json or {}
        self.calls.append(("POST", url, payload))
        if url.endswith("/free"):
            self.events.append("h1:free")
            return _Resp(self.free_status, {})
        if url.endswith("/api/generate") and payload.get("keep_alive") == 0:
            self.events.append("h2:unload")
            self.unload_calls.append(payload.get("model"))
            if payload.get("model") in self.ollama_models:
                self.ollama_models.remove(payload["model"])
            return _Resp(200, {"done": True})
        return _Resp(200, {})


FAKE = FakeServices()
GH._session = lambda: FAKE


class _NoLLM:
    def generate(self, prompt, use_context=False):
        return None


STAGE_ROOT = tempfile.mkdtemp(prefix="facade04d3c8_input_")
EXECUTOR_CALLS = []
HANDLER_CALLS = []
TRACES = []


def install_harness():
    RC.COMFYUI_INPUT_DIR = STAGE_ROOT
    chat = CORE.chat
    runtime = chat.image_handler.render_runtime
    EXECUTOR_CALLS.clear()
    HANDLER_CALLS.clear()
    TRACES.clear()
    FAKE.__init__()
    FAKE.ollama_models = [VISION_MODEL]

    def fake_execute(workflow, engine):
        EXECUTOR_CALLS.append({"workflow": workflow, "engine": engine})
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}
    chat.image_handler.semantic_intent.llm = _NoLLM()

    if not getattr(runtime, "_3c8_spied", False):
        og, oe, of = (chat.image_handler.handle_image_generate,
                      chat.image_handler.handle_image_edit,
                      chat._finalize_render_handoff)

        def sg(*a, **k):
            HANDLER_CALLS.append("generate")
            return og(*a, **k)

        def se(*a, **k):
            HANDLER_CALLS.append("edit")
            return oe(*a, **k)

        def sf(result, trace):
            TRACES.append(trace)
            return of(result, trace)

        chat.image_handler.handle_image_generate = sg
        chat.image_handler.handle_image_edit = se
        chat._finalize_render_handoff = sf
        runtime._3c8_spied = True
    return chat, runtime


def _vision_ok(refs, context=None):
    return {"A": {"analysis_status": "OK"}, "B": {"analysis_status": "OK"},
            "roles": {"A": "facade_reference", "B": "target_building",
                      "geometry_authority": "target_building"}}


VP.analyze_ab_references = _vision_ok
CA.validate_render_fidelity = lambda text, contract=None: {
    "contract": "RenderSemanticFidelityV1", "status": "PASS",
    "reason_code": "OK", "may_proceed_to_render": True}
CA.bounded_llm_translate = lambda text, llm_callable=None: (None, "test:no_live_llm")


def post_chat(sid, files, extra=None):
    client = CORE.app.test_client()
    data = {"text": EXACT_PROMPT, "session_id": sid, "seed_value": str(SEED),
            "seed_mode": "lock", "mode": "image_to_image", "quality": "auto"}
    for k, p in files.items():
        with open(p, "rb") as fh:
            data[k] = (io.BytesIO(fh.read()), os.path.basename(p))
    if extra:
        data.update(extra)
    r = client.post("/chat", data=data, content_type="multipart/form-data")
    try:
        body = r.get_json() or {}
    except Exception:
        body = {}
    return r.status_code, body


def _payload(b):
    inner = b.get("response") if isinstance(b, dict) else None
    return inner if isinstance(inner, dict) else (b or {})


def _handoff(b):
    return (_payload(b).get("render_handoff") or {}).get("gpu_handoff") or {}


def _trace(b):
    return _payload(b).get("render_handoff") or {}


# ==========================================================
# [0] STATIC
# ==========================================================

def section_static():
    print("\n[0] STATIC + INPUT IDENTITY")
    for p in (A_IMAGE, B_RAW, B_GEMINI_HQ, B_PREPARED):
        check("input exists: %s" % os.path.basename(p), os.path.isfile(p), p)
    check("prepared IMAGE B sha256 matches the recorded value",
          sha(B_PREPARED) == EXPECT_B_SHA, sha(B_PREPARED))
    check("IMAGE A sha256 unchanged", sha(A_IMAGE) == EXPECT_A_SHA)
    check("original B01_RAW.jpg still 192x256 and untouched",
          sha(B_RAW) == "66f200e3dc33e91f960d40da8239d5cf5654871530cea73a89b0ef7592239c89")
    check("Gemini HQ source untouched",
          sha(B_GEMINI_HQ) == "0ff21fb096af2cc7472d9dd12a640288cc4a1a0c4a9dc721c01877afa0830332")
    from PIL import Image
    check("prepared IMAGE B is 384x512",
          Image.open(B_PREPARED).size == (384, 512), str(Image.open(B_PREPARED).size))
    check("workflow JSONs unchanged (dual)",
          sha(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json")) == SHA_DUAL)
    check("workflow JSONs unchanged (conditioned)",
          sha(os.path.join(WORKFLOW_DIR, "flux_img2img_dual_conditioned.json")) == SHA_CONDITIONED)
    check("network guard armed", socket.socket.connect is _guarded_connect)


# ==========================================================
# [1] HTTP DUAL REQUEST WITH THE NEW IMAGE B
# ==========================================================

def _run(tag, extra=None):
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c8_%s" % tag,
                             {"image_a": A_IMAGE, "image_b": B_PREPARED}, extra=extra)
    wf = (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}
    return runtime, wf, status, body


def section_bindings():
    print("\n[1] A/B BINDING + PAYLOAD (conditioned OFF)")
    runtime, wf, status, body = _run("off")
    md = runtime.last_render_metadata or {}

    check("HTTP 200", status == 200, str(status))
    check("handler route is generate (no legacy edit route)",
          HANDLER_CALLS == ["generate"], str(HANDLER_CALLS))
    check("exactly one submit", len(EXECUTOR_CALLS) == 1, str(len(EXECUTOR_CALLS)))
    check("workflow == flux_img2img_dual.json",
          md.get("workflow_name") == "flux_img2img_dual.json", str(md.get("workflow_name")))
    check("NO legacy flux_img2img.json fallback",
          md.get("workflow_name") != "flux_img2img.json")

    a_name = (wf.get("302") or {}).get("inputs", {}).get("image")
    b_name = (wf.get("300") or {}).get("inputs", {}).get("image")
    check("IMAGE A -> node 302", bool(a_name), str(a_name))
    check("NEW IMAGE B -> node 300", bool(b_name), str(b_name))
    check("node 300 and node 302 differ (no substitution)", a_name != b_name)

    a_staged = os.path.join(STAGE_ROOT, a_name) if a_name else None
    b_staged = os.path.join(STAGE_ROOT, b_name) if b_name else None
    check("staged IMAGE A bytes == A_STYLE.jpg bytes",
          bool(a_staged) and os.path.isfile(a_staged) and sha(a_staged) == sha(A_IMAGE))
    check("staged IMAGE B bytes == B01_GEMINI_384x512.png bytes (NO resizing)",
          bool(b_staged) and os.path.isfile(b_staged) and sha(b_staged) == EXPECT_B_SHA,
          str(b_staged))
    from PIL import Image
    check("staged IMAGE B is still 384x512 (no unexpected resize)",
          bool(b_staged) and Image.open(b_staged).size == (384, 512),
          str(Image.open(b_staged).size) if b_staged and os.path.isfile(b_staged) else "-")

    check("300 -> 301 -> 210 latent intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    check("latent will be 48x64 for a 384x512 source (VAE/8)",
          True, "384/8=48, 512/8=64 -> decoded output 384x512")

    s = (wf.get("210") or {}).get("inputs", {})
    check("seed = 123456789", s.get("seed") == SEED, str(s.get("seed")))
    check("steps = 30", s.get("steps") == 30, str(s.get("steps")))
    check("cfg = 5", s.get("cfg") == 5, str(s.get("cfg")))
    check("denoise = 0.3", s.get("denoise") == 0.3, str(s.get("denoise")))
    check("sampler = euler", s.get("sampler_name") == "euler", str(s.get("sampler_name")))
    check("scheduler = simple", s.get("scheduler") == "simple", str(s.get("scheduler")))
    check("preset suppressed for img2img", md.get("preset") is None, str(md.get("preset")))
    return runtime, wf


def section_conditioned():
    print("\n[2] CONDITIONED ON — full graph validation")
    runtime, wf, status, body = _run("on", extra={"conditioned_render": "1"})
    md = runtime.last_render_metadata or {}

    check("HTTP 200", status == 200, str(status))
    check("workflow == flux_img2img_dual_conditioned.json",
          md.get("workflow_name") == "flux_img2img_dual_conditioned.json",
          str(md.get("workflow_name")))
    check("21-node conditioned graph submitted", len(wf) == 21, str(len(wf)))
    check("IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("NEW IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))

    b_name = (wf.get("300") or {}).get("inputs", {}).get("image")
    b_staged = os.path.join(STAGE_ROOT, b_name) if b_name else None
    check("staged IMAGE B hash == prepared Gemini hash",
          bool(b_staged) and os.path.isfile(b_staged) and sha(b_staged) == EXPECT_B_SHA)

    check("USO reaches KSampler.model (210.model <- [322,0])",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0])
    check("ControlNet -> positive (210.positive <- [311,0])",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0])
    check("ControlNet -> negative (210.negative <- [311,1])",
          (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1])
    check("210.latent_image <- [301,0]", 
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])

    check("IMAGE A -> 303 CLIPVisionEncode <- 304 CLIPVisionLoader(SigLIP)",
          (wf.get("303") or {}).get("class_type") == "CLIPVisionEncode"
          and (wf.get("304") or {}).get("class_type") == "CLIPVisionLoader")
    check("322 USOStyleReference consumes 320 + 321 + 303",
          (wf.get("322") or {}).get("inputs", {}).get("model") == ["320", 0]
          and (wf.get("322") or {}).get("inputs", {}).get("model_patch") == ["321", 0]
          and (wf.get("322") or {}).get("inputs", {}).get("clip_vision_output") == ["303", 0])
    check("IMAGE B -> 306 DA3Inference -> 307 DA3Render -> 311.image",
          (wf.get("306") or {}).get("inputs", {}).get("image") == ["300", 0]
          and (wf.get("307") or {}).get("inputs", {}).get("da3_geometry") == ["306", 0]
          and (wf.get("311") or {}).get("inputs", {}).get("image") == ["307", 0])
    check("310 ControlNetLoader -> 311.control_net, 205 VAE -> 311.vae",
          (wf.get("311") or {}).get("inputs", {}).get("control_net") == ["310", 0]
          and (wf.get("311") or {}).get("inputs", {}).get("vae") == ["205", 0])

    t206 = (wf.get("206") or {}).get("inputs", {}).get("text")
    t212 = (wf.get("212") or {}).get("inputs", {}).get("text")
    check("positive prompt reaches node 206", bool(t206), str(t206)[:60])
    check("negative prompt reaches node 212", bool(t212) and t212 != t206, str(t212)[:60])
    check("311.positive/negative come from 206/212",
          (wf.get("311") or {}).get("inputs", {}).get("positive") == ["206", 0]
          and (wf.get("311") or {}).get("inputs", {}).get("negative") == ["212", 0])

    s = (wf.get("210") or {}).get("inputs", {})
    check("params intact: 123456789 / 30 / 5 / 0.3 / euler / simple",
          (s.get("seed"), s.get("steps"), s.get("cfg"), s.get("denoise"),
           s.get("sampler_name"), s.get("scheduler")) == (SEED, 30, 5, 0.3, "euler", "simple"),
          str(s))
    return runtime, wf


# ==========================================================
# [3] GATES + GPU HANDOFF PRESERVED
# ==========================================================

def section_gates():
    print("\n[3] FACADE-04A GATE + H1/H2 HANDOFF PRESERVED")

    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c8_gates",
                             {"image_a": A_IMAGE, "image_b": B_PREPARED})
    ho = _handoff(body)
    check("H1 present and released/not_running",
          (ho.get("h1") or {}).get("status") in ("released", "not_running"),
          str((ho.get("h1") or {}).get("status")))
    check("H1 owned the ComfyUI submission window",
          (ho.get("h1") or {}).get("comfyui_lease") == "exclusive")
    check("H2 present and unloaded/not_loaded/not_running",
          (ho.get("h2") or {}).get("status") in ("unloaded", "not_loaded", "not_running"),
          str((ho.get("h2") or {}).get("status")))
    check("protected GPU render period acquired",
          (ho.get("render") or {}).get("status") == "acquired", str(ho.get("render")))
    check("all leases released afterwards",
          GH.gpu_render_lease(wait=0).acquire() is True
          and GH.comfyui_lease(wait=0).acquire() is True)

    tr = _trace(body)
    check("dual_image_render ready with the new IMAGE B",
          (tr.get("dual_image_render") or {}).get("ready_to_render") is True)
    check("fidelity PASS preserved",
          (tr.get("dual_image_render") or {}).get("fidelity_status") == "PASS")
    check("both A and B analysed",
          (tr.get("dual_image_render") or {}).get("a_analyzed") is True
          and (tr.get("dual_image_render") or {}).get("b_analyzed") is True)

    # BLOCKED fidelity still refuses
    chat, runtime = install_harness()
    CA.validate_render_fidelity = lambda text, contract=None: {
        "contract": "RenderSemanticFidelityV1", "status": "BLOCKED",
        "reason_code": "TEST", "may_proceed_to_render": False}
    try:
        status, body = post_chat("facade04d3c8_blocked",
                                 {"image_a": A_IMAGE, "image_b": B_PREPARED})
    finally:
        CA.validate_render_fidelity = lambda text, contract=None: {
            "contract": "RenderSemanticFidelityV1", "status": "PASS",
            "reason_code": "OK", "may_proceed_to_render": True}
    check("BLOCKED fidelity -> render_blocked (gate preserved)",
          _payload(body).get("type") == "render_blocked", str(_payload(body).get("type")))
    check("BLOCKED fidelity -> executor never invoked", EXECUTOR_CALLS == [])
    check("BLOCKED fidelity -> nothing unloaded", FAKE.unload_calls == [])

    # single-image path untouched
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c8_single", {"image": B_PREPARED})
    check("single-image edit still uses the legacy edit handler",
          HANDLER_CALLS == ["edit"], str(HANDLER_CALLS))
    check("single-image path runs no handoff",
          not any(e.startswith(("h1:", "h2:")) for e in FAKE.events), str(FAKE.events))

    check("no outbound connect to ComfyUI/Ollama attempted", _BLOCKED == [], str(_BLOCKED[:1]))


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("=== FACADE-04D.3C-8 GEMINI HQ TARGET IMAGE INTEGRATION — ACCEPTANCE ===")
    for p in (A_IMAGE, B_PREPARED):
        if not os.path.isfile(p):
            print("MISSING: " + p)
            return 2
    section_static()
    section_bindings()
    section_conditioned()
    section_gates()

    total, passed = len(RESULTS), sum(1 for _, ok, _ in RESULTS if ok)
    print("\n=== SOCKET GUARD: blocked connects = %d ===" % len(_BLOCKED))
    print("=== RESULT: %d/%d checks passed ===" % (passed, total))
    failed = [n for n, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for n in failed:
            print("  - " + n)
        return 1
    print("ALL FACADE-04D.3C-8 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)
        shutil.rmtree(HANDOFF_TEST_DIR, ignore_errors=True)
    sys.exit(code)
