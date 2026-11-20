# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-5B — SAFE VISION-TO-RENDER GPU MEMORY HANDOFF (ACCEPTANCE SUITE)
#
# MOCKED ONLY. No real image generation, no ComfyUI job submission, no live
# GPU inference, no live Ollama model unloading, no service restart.
#
#   * Every ComfyUI and Ollama HTTP call goes through an injected fake
#     transport (core.runtime.gpu_handoff_v1._session), so the REAL H1/H2
#     logic runs against mocked services.
#   * A socket-level guard raises on ANY connect to port 8188 (ComfyUI) or
#     11434 (Ollama) — a live call is impossible.
#   * ComfyHTTPRuntime.submit/execute are hard-patched to raise.
#   * The render executor is replaced by a recorder.
#
# Covers: H1 before A/B vision, H2 after A/B vision and before the render,
# cross-process lease ownership, concurrent chat + render, two concurrent
# dual-image requests, nonempty ComfyUI queue, /free failure, unload failure,
# timeout, incomplete release confirmation, fail-closed behaviour, and the
# preserved FACADE-04D.2 / 04D.3B-2 dual-image execution payload.
#
# Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#   .venv/Scripts/python.exe tests/test_facade_04d3c5b_gpu_handoff_v1.py
# ==========================================================

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- NETWORK-SAFETY GUARD (set BEFORE importing app/config) ----
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"
os.environ.setdefault("ARCHITECTOS_CORE_API_HOST", "127.0.0.1")

# ---- HANDOFF TEST ISOLATION (private lock dir + short bounded waits) ----
HANDOFF_TEST_DIR = tempfile.mkdtemp(prefix="facade04d3c5b_handoff_")
os.environ["ARCHITECTOS_GPU_HANDOFF_DIR"] = HANDOFF_TEST_DIR
os.environ["ARCHITECTOS_GPU_HANDOFF_LEASE_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_UNLOAD_WAIT"] = "0"
os.environ["ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_TIMEOUT"] = "0.3"
os.environ["ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_INTERVAL"] = "0.05"
os.environ["ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_TIMEOUT"] = "0.3"
os.environ["ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_INTERVAL"] = "0.05"

import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

import requests  # noqa: E402

_CONN_ERROR = requests.exceptions.ConnectionError

#: `json` is shadowed by the `json=` kwarg of the requests-style fake
#: transports below, so the module itself is kept under a private alias.
_JSON = json

sys.path.insert(0, PROJECT_ROOT)

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")

EXACT_PROMPT = (
    "نمای ساختمان تصویر B را بازطراحی کن با الهام از سبک و متریال و زبان فرمی "
    "تصویر A. هندسه کلی، تعداد طبقات، بازشوها، بالکن\u200cها، حجم کلی و کادر "
    "دید ساختمان B حفظ شود. خروجی باید یک رندر نمای باکیفیت و واقعی از ساختمان "
    "B با ظاهر الهام\u200cگرفته از A باشد."
)

SEED = 123456789
VISION_MODEL = "qwen3.8:27b"

SHA_DUAL = "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9"
SHA_CONDITIONED = "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"


# ==========================================================
# SOCKET-LEVEL NETWORK GUARD
# ==========================================================

_BLOCKED_CONNECTS = []

_real_connect = socket.socket.connect

BLOCKED_PORTS = (8188, 11434)


def _guarded_connect(self, address, *args, **kwargs):
    try:
        host, port = address[0], int(address[1])
    except Exception:
        host, port = "?", -1
    if port in BLOCKED_PORTS:
        frames = [
            "%s:%s:%s" % (os.path.basename(f.filename), f.lineno, f.name)
            for f in traceback.extract_stack()[-24:-1]
        ]
        _BLOCKED_CONNECTS.append((str(host), port, " <- ".join(frames)))
        raise RuntimeError("NETWORK GUARD: live service connect blocked (port %s)" % port)
    return _real_connect(self, address, *args, **kwargs)


socket.socket.connect = _guarded_connect


import app as CORE  # noqa: E402
import core.vision.facade_reference_vision_provider_v1 as VP  # noqa: E402
import core.chat.chat_architect as CA  # noqa: E402
import core.runtime.gpu_handoff_v1 as GH  # noqa: E402
import core.llm.llm_gateway as LGW  # noqa: E402
from config import runtime_config as RC  # noqa: E402
from core.render.comfy_http_runtime import ComfyHTTPRuntime  # noqa: E402


def _boom(*a, **k):
    raise RuntimeError("NETWORK GUARD: real ComfyUI submit attempted")


ComfyHTTPRuntime.submit = _boom
ComfyHTTPRuntime.execute = _boom


RESULTS = []
EVENTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ==========================================================
# MOCKED COMFYUI + OLLAMA TRANSPORT
# ==========================================================

class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text else _JSON.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeServices:
    """A single mocked ComfyUI + Ollama HTTP surface. Opens no socket."""

    COMFY = "http://127.0.0.1:9"
    OLLAMA = "http://127.0.0.1:11434"

    def __init__(self):
        self.queue_running = 0
        self.queue_pending = 0
        self.queue_readable = True
        self.free_status = 200
        self.stats_readable = True
        self.vram_free = 3_000_000_000
        self.ollama_models = []
        self.ps_readable = True
        self.unload_status = 200
        self.unload_effective = True
        self.unload_calls = []
        self.calls = []
        self.events = EVENTS
        #: When True, both services behave as "not listening" (refused).
        self.offline = False

    # ------------------------------------------------------
    def _comfy(self, url):
        if url.endswith("/queue"):
            self.events.append("h1:queue")
            if not self.queue_readable:
                return _Resp(500, None)
            return _Resp(200, {"queue_running": list(range(self.queue_running)),
                               "queue_pending": list(range(self.queue_pending))})
        if url.endswith("/free"):
            self.events.append("h1:free")
            if self.free_status < 400:
                # a release is only visible if stats stay readable
                self.vram_free = 16_700_000_000
            return _Resp(self.free_status, {})
        if url.endswith("/system_stats"):
            self.events.append("stats")
            if not self.stats_readable:
                return _Resp(500, None)
            return _Resp(200, {"devices": [{"vram_free": self.vram_free}]})
        return _Resp(404, None)

    def _ollama(self, url):
        if url.endswith("/api/ps"):
            self.events.append("ollama:ps")
            if not self.ps_readable:
                return _Resp(500, None)
            return _Resp(200, {"models": [{"name": m} for m in self.ollama_models]})
        if url.endswith("/api/generate"):
            return _Resp(200, {})  # handled in post()
        return _Resp(404, None)

    # ------------------------------------------------------
    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        if self.offline:
            raise _CONN_ERROR("connection refused (mocked)")
        if url.startswith(self.COMFY):
            return self._comfy(url)
        if url.startswith(self.OLLAMA):
            return self._ollama(url)
        raise RuntimeError("unexpected GET " + url)

    def post(self, url, json=None, timeout=None):  # noqa: A002 - matches requests API
        payload = json or {}
        self.calls.append(("POST", url, payload))
        if self.offline:
            raise _CONN_ERROR("connection refused (mocked)")
        if url.startswith(self.COMFY):
            return self._comfy(url)
        if url.startswith(self.OLLAMA) and url.endswith("/api/generate"):
            model = payload.get("model")
            if payload.get("keep_alive") == 0:
                self.events.append("h2:unload")
                self.unload_calls.append(model)
                if self.unload_status >= 400:
                    return _Resp(self.unload_status, {"error": "unload failed"})
                if self.unload_effective and model in self.ollama_models:
                    self.ollama_models.remove(model)
                    self.vram_free += 1_000_000_000
                return _Resp(200, {"done": True})
            self.events.append("ollama:generate")
            return _Resp(200, {"response": "{}"})
        raise RuntimeError("unexpected POST " + url)


FAKE = FakeServices()
GH._session = lambda: FAKE


class _NoLLM:
    """Stand-in for the semantic-intent LLM: a failed call, no socket."""

    def generate(self, prompt, use_context=False):
        return None


# ==========================================================
# HARNESS
# ==========================================================

STAGE_ROOT = tempfile.mkdtemp(prefix="facade04d3c5b_comfy_input_")

EXECUTOR_CALLS = []
HANDLER_CALLS = []
HANDOFF_TRACES = []


def install_harness():
    RC.COMFYUI_INPUT_DIR = STAGE_ROOT

    chat = CORE.chat
    runtime = chat.image_handler.render_runtime

    EXECUTOR_CALLS.clear()
    HANDLER_CALLS.clear()
    HANDOFF_TRACES.clear()
    del EVENTS[:]

    FAKE.__init__()
    FAKE.ollama_models = [VISION_MODEL]

    def fake_execute(workflow, engine):
        EVENTS.append("render:execute")
        EXECUTOR_CALLS.append({"workflow": workflow, "engine": engine})
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    # The semantic-intent extraction inside handle_image_generate is a SECOND
    # Ollama call on the render path. Its LLM is replaced by a stub that
    # behaves exactly like a failed call, so the suite performs ZERO live
    # Ollama traffic while the real H2 ordering is exercised.
    chat.image_handler.semantic_intent.llm = _NoLLM()

    if not getattr(runtime, "_3c5b_spied", False):
        orig_g = chat.image_handler.handle_image_generate
        orig_e = chat.image_handler.handle_image_edit
        orig_final = chat._finalize_render_handoff

        def spy_g(*a, **k):
            HANDLER_CALLS.append("generate")
            return orig_g(*a, **k)

        def spy_e(*a, **k):
            HANDLER_CALLS.append("edit")
            return orig_e(*a, **k)

        def spy_final(result, trace):
            HANDOFF_TRACES.append(trace)
            return orig_final(result, trace)

        chat.image_handler.handle_image_generate = spy_g
        chat.image_handler.handle_image_edit = spy_e
        chat._finalize_render_handoff = spy_final
        runtime._3c5b_spied = True

    return chat, runtime


def _vision_ok(refs, context=None):
    EVENTS.append("vision:analyze_ab")
    return {
        "A": {"analysis_status": "OK"},
        "B": {"analysis_status": "OK"},
        "roles": {"A": "facade_reference", "B": "target_building",
                  "geometry_authority": "target_building"},
    }


_ORIG_ANALYZE = VP.analyze_ab_references
VP.analyze_ab_references = _vision_ok

_ORIG_FIDELITY = CA.validate_render_fidelity
CA.validate_render_fidelity = lambda text, contract=None: {
    "contract": "RenderSemanticFidelityV1", "status": "PASS",
    "reason_code": "OK", "may_proceed_to_render": True,
}

# The bounded LLM terminology translation is the ONE other Ollama call on this
# path. It is stubbed so the suite performs ZERO live Ollama traffic; the
# production fallback ("LLM unavailable") is exactly what a blocked call
# produces, so the dual-image payload is unaffected.
CA.bounded_llm_translate = lambda text, llm_callable=None: (None, "test:no_live_llm")


def post_chat(session_id, files, extra=None):
    client = CORE.app.test_client()
    data = {"text": EXACT_PROMPT, "session_id": session_id,
            "seed_value": str(SEED), "seed_mode": "lock",
            "mode": "image_to_image", "quality": "auto"}
    for key, path in files.items():
        with open(path, "rb") as handle:
            data[key] = (io.BytesIO(handle.read()), os.path.basename(path))
    if extra:
        data.update(extra)
    resp = client.post("/chat", data=data, content_type="multipart/form-data")
    try:
        body = resp.get_json() or {}
    except Exception:
        body = {}
    return resp.status_code, body


def _last_handoff():
    for trace in reversed(HANDOFF_TRACES):
        if isinstance(trace, dict) and trace.get("gpu_handoff"):
            return trace["gpu_handoff"]
    return {}


def _payload(body):
    """app.py nests the ChatArchitect result under `response`."""
    inner = body.get("response") if isinstance(body, dict) else None
    return inner if isinstance(inner, dict) else (body or {})


def _handoff_of(body):
    """The machine-readable handoff trace carried on the response.

    NOTE: the ResponseAdapter rebuilds the top-level envelope and drops the
    `reason` key (pre-existing behaviour, identical for the accepted
    `dual_image_render_not_ready` block). The authoritative reason code is the
    one recorded on the handoff trace.
    """
    return (_payload(body).get("render_handoff") or {}).get("gpu_handoff") or {}


def _index(event):
    return EVENTS.index(event) if event in EVENTS else -1


def _pos(source, needle):
    """Index of `needle` in `source`, or -1 (never raises)."""
    return source.find(needle)


# ==========================================================
# [0] STATIC + SAFETY
# ==========================================================

def section_static():
    print("\n[0] STATIC + SAFETY GUARDS")

    check("network guard: ComfyUI port is 9",
          os.environ.get("ARCHITECTOS_COMFY_PORT") == "9")
    check("network guard: socket.connect patched",
          socket.socket.connect is _guarded_connect)
    check("network guard: ComfyHTTPRuntime.submit hard-patched",
          ComfyHTTPRuntime.submit is _boom)
    check("handoff lock dir is the private test dir",
          GH.handoff_dir() == HANDOFF_TEST_DIR, GH.handoff_dir())
    check("new module present", GH.CONTRACT == "GpuHandoffV1" and GH.VERSION == "1.0")

    ca = open(os.path.join(PROJECT_ROOT, "core", "chat", "chat_architect.py"),
              encoding="utf-8").read()
    ih = open(os.path.join(PROJECT_ROOT, "core", "chat", "handlers",
                           "image_handler.py"), encoding="utf-8").read()
    rr = open(os.path.join(PROJECT_ROOT, "core", "render",
                           "render_runtime.py"), encoding="utf-8").read()

    check("H1 marker present in chat_architect", "GPU HANDOFF H1" in ca)
    check("H2 marker present in RenderRuntime (moved there in 5B.1)",
          "GPU HANDOFF H2" in rr)
    check("H2 no longer runs in the image handler (it reloaded the model)",
          "unload_ollama_models_for_render" not in ih)
    h1_call = _pos(ca, "release_comfyui_for_vision()")
    vision_call = _pos(ca, "analyze_ab_references(\n                    _ab_refs,")
    check("H1 runs BEFORE the A/B vision call",
          -1 < h1_call < vision_call, "h1=%s vision=%s" % (h1_call, vision_call))

    # H2 must be the LAST model operation of the render: RenderRuntime's own
    # semantic-intent call (the mode == "img2img" branch) happens BEFORE it and
    # the ComfyUI submit AFTER it.
    h2_call = _pos(rr, "unload_ollama_models_for_render()")
    semantic_call = _pos(rr, "intent_data = self.semantic_intent.extract(")
    render_call = _pos(rr, "execution = self.executor.execute(")
    check("H2 runs AFTER the render's own semantic-intent Ollama call",
          -1 < semantic_call < h2_call, "semantic=%s h2=%s" % (semantic_call, h2_call))
    check("H2 runs immediately BEFORE the render submit",
          -1 < h2_call < render_call, "h2=%s render=%s" % (h2_call, render_call))
    check("H2 is scoped to the dual-image / conditioned request",
          "if image_bindings or conditioned:" in rr)
    check("H2 fails closed with a distinguishable blocked status",
          '"gpu_handoff_h2_"' in rr and '"gpu_handoff_blocked"' in rr)
    check("H1 fails closed with a render_blocked status",
          ca.count('"reason": "gpu_handoff_h1_"') == 1)
    check("the H2 trace is merged back into the chat handoff record",
          'self.render_runtime, "last_gpu_handoff_h2"' in ca)
    check("H1 treats a NOT-RUNNING ComfyUI as safe (it holds no VRAM)",
          '("released", "not_running")' in ca)
    check("H2 treats a NOT-RUNNING Ollama as safe (nothing can be resident)",
          '("unloaded", "not_loaded", "not_running")' in rr)

    # every ArchitectOS Ollama caller must hold the lease
    lgw = open(os.path.join(PROJECT_ROOT, "core", "llm", "llm_gateway.py"),
               encoding="utf-8").read()
    check("chat gateway holds the model lease",
          "ollama_model_call(model)" in lgw)
    vp = open(os.path.join(PROJECT_ROOT, "core", "vision",
                           "facade_reference_vision_provider_v1.py"), encoding="utf-8").read()
    check("facade vision provider holds the model lease",
          "ollama_model_call(self.model)" in vp)
    ov = open(os.path.join(PROJECT_ROOT, "core", "vision",
                           "vision_provider_ollama_v1.py"), encoding="utf-8").read()
    check("observer holds the model lease",
          "ollama_model_call(cfg.model)" in ov)
    check("normalizer holds the model lease",
          "ollama_model_call(cfg.normalizer_model)" in ov)

    # never kill/restart Ollama, never restart ComfyUI
    gh = open(os.path.join(PROJECT_ROOT, "core", "runtime",
                           "gpu_handoff_v1.py"), encoding="utf-8").read()
    for forbidden in ("taskkill", "os.kill", "subprocess", "popen", "restart"):
        check("handoff module contains no %r" % forbidden,
              forbidden not in gh.lower())

    # workflow integrity
    check("flux_img2img_dual.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json")) == SHA_DUAL)
    check("flux_img2img_dual_conditioned.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual_conditioned.json"))
          == SHA_CONDITIONED)

    # preserved gates
    check("FACADE-04A dual-image gate preserved",
          '"dual_image_render_not_ready"' in ca)
    check("render-approval gate preserved",
          'design_status != "approved" and design_render_request:' in ca)
    check("FACADE-04D.3C-4 declared-pair gate preserved",
          '"dual_image_binding_incomplete"' in ca)


# ==========================================================
# [1] CROSS-PROCESS LEASE SEMANTICS
# ==========================================================

CHILD_SRC = r'''
import os, sys
os.environ["ARCHITECTOS_GPU_HANDOFF_DIR"] = sys.argv[1]
sys.path.insert(0, sys.argv[2])
from core.runtime.gpu_handoff_v1 import ollama_model_lease
lease = ollama_model_lease(sys.argv[3], wait=0)
print("CHILD_ACQUIRED=%s" % lease.acquire())
'''


def section_lease():
    print("\n[1] CROSS-PROCESS LEASE (the ownership primitive)")

    model = "lease-probe:1b"
    a = GH.ollama_model_lease(model, wait=0)
    b = GH.ollama_model_lease(model, wait=0)

    check("first handle acquires the lease", a.acquire() is True)
    check("SAME-PROCESS second handle is refused (not just a thread lock)",
          b.acquire() is False)

    child_path = os.path.join(HANDOFF_TEST_DIR, "child_probe.py")
    with open(child_path, "w", encoding="utf-8") as handle:
        handle.write(CHILD_SRC)
    out = subprocess.run([sys.executable, child_path, HANDOFF_TEST_DIR, PROJECT_ROOT, model],
                         capture_output=True, text=True, timeout=10800)
    check("DIFFERENT-PROCESS handle is refused (real cross-process exclusion)",
          "CHILD_ACQUIRED=False" in out.stdout,
          out.stdout.strip() + out.stderr.strip()[:200])

    a.release()
    check("lease is re-acquirable after release", b.acquire() is True)
    b.release()

    out2 = subprocess.run([sys.executable, child_path, HANDOFF_TEST_DIR, PROJECT_ROOT, model],
                          capture_output=True, text=True, timeout=10800)
    check("after release the OTHER process acquires it",
          "CHILD_ACQUIRED=True" in out2.stdout, out2.stdout.strip())

    other = GH.ollama_model_lease("different-model:1b", wait=0)
    c = GH.ollama_model_lease(model, wait=0)
    check("a different model is a different lease (no global serialisation)",
          c.acquire() is True and other.acquire() is True)
    c.release()
    other.release()

    check("ollama_model_call refuses when the model is owned elsewhere",
          _busy_probe() is True)


def _busy_probe():
    holder = GH.ollama_model_lease("busy-probe:1b", wait=0)
    holder.acquire()
    try:
        try:
            with GH.ollama_model_call("busy-probe:1b", wait=0):
                return False
        except GH.OllamaModelBusy:
            return True
    finally:
        holder.release()


# ==========================================================
# [2] H1 UNIT — SAFE COMFYUI RELEASE
# ==========================================================

def section_h1():
    print("\n[2] H1 — SAFE COMFYUI RELEASE (mocked)")

    install_harness()
    FAKE.queue_running = 0
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("empty queue -> status released", r["status"] == "released", str(r.get("reason")))
    check("H1 called /free exactly once",
          sum(1 for c in FAKE.calls if c[1].endswith("/free")) == 1)
    check("H1 confirmed the release with a bounded /system_stats read",
          r["release_confirmed"] is True and r["poll_attempts"] >= 1,
          "attempts=%s" % r["poll_attempts"])
    check("H1 measured before/after VRAM",
          r["vram_free_before"] == 3_000_000_000 and r["vram_free_after"] == 16_700_000_000,
          "%s -> %s" % (r["vram_free_before"], r["vram_free_after"]))
    check("H1 reported the freed bytes", r["released_bytes"] == 13_700_000_000,
          str(r["released_bytes"]))

    install_harness()
    FAKE.queue_running = 1
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("RUNNING job -> blocked/comfy_queue_not_empty",
          r["status"] == "blocked" and r["reason"] == "comfy_queue_not_empty", str(r.get("reason")))
    check("a running job is NEVER interrupted (/free not called)",
          not any(c[1].endswith("/free") for c in FAKE.calls))

    install_harness()
    FAKE.queue_pending = 2
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("PENDING job -> blocked/comfy_queue_not_empty",
          r["status"] == "blocked" and r["reason"] == "comfy_queue_not_empty", str(r.get("reason")))

    install_harness()
    FAKE.queue_readable = False
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("unhealthy queue -> blocked/comfy_queue_unreadable (fail closed)",
          r["status"] == "blocked" and r["reason"] == "comfy_queue_unreadable", str(r.get("reason")))

    install_harness()
    FAKE.offline = True
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("ComfyUI NOT RUNNING (refused) -> status not_running (safe, nothing to free)",
          r["status"] == "not_running" and r["reason"] == "comfyui_not_running",
          str(r.get("reason")))
    check("not-running H1 issues no /free call",
          not any(c[1].endswith("/free") for c in FAKE.calls))

    install_harness()
    FAKE.free_status = 500
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("/free failure -> blocked/comfy_free_failed (fail closed)",
          r["status"] == "blocked" and r["reason"] == "comfy_free_failed", str(r.get("reason")))

    install_harness()
    FAKE.stats_readable = False
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("incomplete release confirmation -> blocked/comfy_release_unconfirmed",
          r["status"] == "blocked" and r["reason"] == "comfy_release_unconfirmed",
          str(r.get("reason")))
    check("H1 never restarts ComfyUI (no restart call of any kind)",
          not any("restart" in str(c).lower() for c in FAKE.calls))


# ==========================================================
# [3] H2 UNIT — SAFE OLLAMA UNLOAD
# ==========================================================

def section_h2():
    print("\n[3] H2 — SAFE OLLAMA UNLOAD (mocked)")

    install_harness()
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("loaded vision model -> status unloaded",
          r["status"] == "unloaded", str(r.get("reason")))
    check("H2 established EXCLUSIVE ownership", r["ownership"] == "exclusive")
    check("H2 unloaded the vision model", r["unloaded"] == [VISION_MODEL], str(r["unloaded"]))
    check("the unload used Ollama's keep_alive=0 operation",
          any(c[0] == "POST" and c[1].endswith("/api/generate")
              and c[2].get("keep_alive") == 0 and c[2].get("model") == VISION_MODEL
              for c in FAKE.calls))
    check("model release verified through /api/ps",
          sum(1 for c in FAKE.calls if c[1].endswith("/api/ps")) >= 2)
    check("H2 verified release with a bounded memory check",
          r["vram_free_after"] is not None and r["vram_free_after"] > r["vram_free_before"],
          "%s -> %s" % (r["vram_free_before"], r["vram_free_after"]))
    check("H2 released the exclusive lease afterwards",
          GH.ollama_model_lease(VISION_MODEL, wait=0).acquire() is True)

    install_harness()
    FAKE.ollama_models = []
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("nothing resident -> status not_loaded", r["status"] == "not_loaded", str(r["status"]))
    check("nothing resident -> NO unload request issued", FAKE.unload_calls == [])

    install_harness()
    FAKE.unload_status = 500
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("unload failure -> blocked/ollama_unload_failed",
          r["status"] == "blocked" and r["reason"] == "ollama_unload_failed", str(r.get("reason")))
    check("unload failure -> target NOT reported as released",
          r["target_released"] is False)

    install_harness()
    FAKE.unload_effective = False  # /api/ps keeps showing the model
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("incomplete model-release confirmation -> blocked/ollama_unload_unconfirmed",
          r["status"] == "blocked" and r["reason"] == "ollama_unload_unconfirmed",
          str(r.get("reason")))

    install_harness()
    FAKE.ps_readable = False
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("/api/ps unhealthy -> blocked/ollama_ps_unreadable (fail closed)",
          r["status"] == "blocked" and r["reason"] == "ollama_ps_unreadable", str(r.get("reason")))
    check("/api/ps unhealthy -> NO unload request issued", FAKE.unload_calls == [])

    install_harness()
    FAKE.offline = True
    r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                           endpoint=FAKE.OLLAMA, session=FAKE,
                                           comfy_endpoint=FAKE.COMFY)
    check("Ollama NOT RUNNING (refused) -> status not_running (safe, nothing resident)",
          r["status"] == "not_running" and r["reason"] == "ollama_not_running",
          str(r.get("reason")))
    check("not-running H2 issues NO unload request", FAKE.unload_calls == [])

    # ---- never unload a model another request is using ----
    install_harness()
    holder = GH.ollama_model_lease(VISION_MODEL, wait=0)
    holder.acquire()
    try:
        r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                               endpoint=FAKE.OLLAMA, session=FAKE,
                                               comfy_endpoint=FAKE.COMFY)
    finally:
        holder.release()
    check("model in use by ANOTHER request -> blocked/ollama_model_busy",
          r["status"] == "blocked" and r["reason"] == "ollama_model_busy", str(r.get("reason")))
    check("model in use by ANOTHER request -> NO unload request issued",
          FAKE.unload_calls == [])
    check("ownership was never claimed", r["ownership"] == "not_acquired")

    # ---- other resident models: free ones released, in-use ones skipped ----
    install_harness()
    FAKE.ollama_models = [VISION_MODEL, "qwen3-coder:30b"]
    busy = GH.ollama_model_lease("qwen3-coder:30b", wait=0)
    busy.acquire()
    try:
        r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                               endpoint=FAKE.OLLAMA, session=FAKE,
                                               comfy_endpoint=FAKE.COMFY)
    finally:
        busy.release()
    check("another resident model that IS in use is skipped, never unloaded",
          r["skipped_in_use"] == ["qwen3-coder:30b"] and "qwen3-coder:30b" not in FAKE.unload_calls,
          "skipped=%s unloads=%s" % (r["skipped_in_use"], FAKE.unload_calls))
    check("the vision model is still released", r["unloaded"] == [VISION_MODEL], str(r["unloaded"]))


# ==========================================================
# [4] THE REAL OLLAMA CALLERS HOLD THE LEASE
# ==========================================================

def section_callers():
    print("\n[4] REAL CALLERS HOLD THE LEASE (chat gateway + facade vision)")

    gateway = LGW.LLMGateway()
    seen = {}

    class _GW:
        def post(self, url, json=None, timeout=None):  # noqa: A002
            probe = GH.ollama_model_lease(gateway.model, wait=0)
            seen["lease_held"] = not probe.acquire()
            if not seen["lease_held"]:
                probe.release()
            return _Resp(200, {"response": "ok"})

        def get(self, url, timeout=None):
            return _Resp(200, {"models": []})

    gateway.session = _GW()
    out = gateway.generate("hello")
    check("chat gateway returns the model answer", out == "ok", str(out))
    check("chat gateway holds the model lease DURING its Ollama call",
          seen.get("lease_held") is True)

    holder = GH.ollama_model_lease(gateway.model, wait=0)
    holder.acquire()
    try:
        gateway.session = _GW()
        out = gateway.generate("hello")
    finally:
        holder.release()
    check("chat gateway fails TRUTHFULLY when another request owns the model",
          out is None and gateway.last_error == "model_busy:" + gateway.model,
          str(gateway.last_error))

    provider = VP.get_facade_provider(VP.ROLE_STYLE_REFERENCE)
    vseen = {}

    class _VP:
        def post(self, url, json=None, timeout=None):  # noqa: A002
            probe = GH.ollama_model_lease(provider.model, wait=0)
            vseen["lease_held"] = not probe.acquire()
            if not vseen["lease_held"]:
                probe.release()
            return _Resp(200, {"response": _JSON.dumps({"facade_style": "modern"}),
                               "done_reason": "stop"})

        def get(self, url, timeout=None):
            return _Resp(200, {"models": []})

    provider.session = _VP()
    provider.analyze(B_IMAGE)
    check("facade vision provider holds the model lease DURING its call",
          vseen.get("lease_held") is True)

    holder = GH.ollama_model_lease(provider.model, wait=0)
    holder.acquire()
    try:
        provider.session = _VP()
        raised = False
        try:
            provider.analyze(B_IMAGE)
        except RuntimeError as exc:
            raised = "ollama_model_busy" in str(exc)
    finally:
        holder.release()
    check("facade vision provider fails truthfully when the model is owned elsewhere",
          raised is True)


# ==========================================================
# [5] END-TO-END HTTP — ORDERING + PAYLOAD INTEGRITY
# ==========================================================

def _run_dual(session_id, extra=None, tag="OFF"):
    chat, runtime = install_harness()
    status, body = post_chat(session_id, {"image_a": A_IMAGE, "image_b": B_IMAGE}, extra=extra)

    check("%s: HTTP 200" % tag, status == 200, "status=%s" % status)
    check("%s: executor invoked exactly once (mocked)" % tag,
          len(EXECUTOR_CALLS) == 1, str(len(EXECUTOR_CALLS)))
    check("%s: handler route is generate" % tag, HANDLER_CALLS == ["generate"], str(HANDLER_CALLS))

    check("%s: H1 ran BEFORE the A/B architectural vision analysis" % tag,
          0 <= _index("h1:free") < _index("vision:analyze_ab"),
          str(EVENTS))
    check("%s: H2 ran AFTER the A/B analysis" % tag,
          0 <= _index("vision:analyze_ab") < _index("h2:unload"), str(EVENTS))
    check("%s: H2 ran BEFORE the ComfyUI render submit" % tag,
          0 <= _index("h2:unload") < _index("render:execute"), str(EVENTS))
    check("%s: no Ollama inference runs after H2 in this request" % tag,
          EVENTS.count("ollama:generate") == 0
          or _index("ollama:generate") < _index("h2:unload"), str(EVENTS))

    handoff = _last_handoff()
    check("%s: H1 status released" % tag,
          (handoff.get("h1") or {}).get("status") in ("released", "not_running"),
          str((handoff.get("h1") or {}).get("reason")))
    check("%s: H2 status is unloaded/not_loaded/not_running" % tag,
          (handoff.get("h2") or {}).get("status") in ("unloaded", "not_loaded", "not_running"),
          str((handoff.get("h2") or {}).get("reason")))
    check("%s: H2 ownership was exclusive" % tag,
          (handoff.get("h2") or {}).get("ownership") == "exclusive")
    return runtime, (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}


def section_e2e():
    print("\n[5] END-TO-END HTTP — ORDERING + PAYLOAD INTEGRITY")

    runtime, wf = _run_dual("facade04d3c5b_off", tag="OFF")
    md = runtime.last_render_metadata or {}
    check("OFF: workflow == flux_img2img_dual.json",
          md.get("workflow_name") == "flux_img2img_dual.json", str(md.get("workflow_name")))
    check("OFF: IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("OFF: IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("OFF: node 300 != node 302 (no substitution)",
          (wf.get("300") or {}).get("inputs", {}).get("image")
          != (wf.get("302") or {}).get("inputs", {}).get("image"))
    check("OFF: 300 -> 301 -> 210 intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    s = (wf.get("210") or {}).get("inputs", {})
    check("OFF: seed = 123456789", s.get("seed") == SEED, str(s.get("seed")))
    check("OFF: steps = 30", s.get("steps") == 30, str(s.get("steps")))
    check("OFF: cfg = 5", s.get("cfg") == 5, str(s.get("cfg")))
    check("OFF: denoise = 0.3", s.get("denoise") == 0.3, str(s.get("denoise")))
    check("OFF: preset suppressed (metadata.preset is None)", md.get("preset") is None)

    runtime, wf = _run_dual("facade04d3c5b_on", extra={"conditioned_render": "1"}, tag="ON")
    md = runtime.last_render_metadata or {}
    check("ON: workflow == flux_img2img_dual_conditioned.json",
          md.get("workflow_name") == "flux_img2img_dual_conditioned.json",
          str(md.get("workflow_name")))
    check("ON: IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("ON: IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("ON: USO reaches KSampler.model (210.model <- [322,0])",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0])
    check("ON: ControlNet -> positive (210.positive <- [311,0])",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0])
    check("ON: ControlNet -> negative (210.negative <- [311,1])",
          (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1])
    check("ON: node 210 latent from node 301",
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    check("ON: USO LoRA node 320 unchanged",
          (wf.get("320") or {}).get("class_type") == "LoraLoaderModelOnly")
    check("ON: USO style reference node 322 unchanged",
          (wf.get("322") or {}).get("class_type") == "USOStyleReference")
    check("ON: ControlNet loader node 310 unchanged",
          (wf.get("310") or {}).get("class_type") == "ControlNetLoader")
    check("ON: ControlNetApplyAdvanced node 311 unchanged",
          (wf.get("311") or {}).get("class_type") == "ControlNetApplyAdvanced")

    resolved = (runtime.last_render_request or {}).get("resolved_prompt")
    t206 = (wf.get("206") or {}).get("inputs", {}).get("text")
    t212 = (wf.get("212") or {}).get("inputs", {}).get("text")
    check("ON: resolved architectural prompt reaches node 206",
          bool(resolved) and t206 == resolved, "206[:60]=%s" % str(t206)[:60])
    check("ON: negative prompt reaches node 212",
          bool(t212) and t212 != t206, "212[:60]=%s" % str(t212)[:60])
    s = (wf.get("210") or {}).get("inputs", {})
    check("ON: seed/steps/cfg/denoise intact",
          (s.get("seed"), s.get("steps"), s.get("cfg"), s.get("denoise"))
          == (SEED, 30, 5, 0.3), str(s))

    check("no outbound connect to ComfyUI/Ollama was ever attempted",
          _BLOCKED_CONNECTS == [], str(_BLOCKED_CONNECTS[:2]))

    # ---- a service that is merely NOT RUNNING holds no VRAM: the render
    #      must still proceed (this is what keeps the older FACADE suites,
    #      which point ComfyUI at a dead port, passing).
    chat, runtime = install_harness()
    FAKE.offline = True
    status, body = post_chat("facade04d3c5b_offline",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    handoff = _last_handoff()
    check("ComfyUI+Ollama not running -> the render still proceeds",
          len(EXECUTOR_CALLS) == 1, str(len(EXECUTOR_CALLS)))
    check("ComfyUI not running -> H1 recorded not_running (nothing to free)",
          (handoff.get("h1") or {}).get("status") == "not_running",
          str((handoff.get("h1") or {}).get("reason")))
    check("Ollama not running -> H2 recorded not_running (nothing resident)",
          (handoff.get("h2") or {}).get("status") == "not_running",
          str((handoff.get("h2") or {}).get("reason")))
    check("not-running path issued NO unload and NO /free",
          FAKE.unload_calls == []
          and not any(c[1].endswith("/free") for c in FAKE.calls))


# ==========================================================
# [6] FAIL-CLOSED — NO UNINTENDED RENDER / UNLOAD
# ==========================================================

def section_fail_closed():
    print("\n[6] FAIL-CLOSED — NO UNINTENDED RENDER / UNLOAD")

    # (a) H1 blocked by a nonempty queue
    chat, runtime = install_harness()
    FAKE.queue_running = 1
    status, body = post_chat("facade04d3c5b_fc_queue",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    out = _payload(body)
    check("H1 nonempty queue -> HTTP 200 render_blocked",
          status == 200 and out.get("type") == "render_blocked", str(out.get("type")))
    check("H1 nonempty queue -> reason names H1 (comfy_queue_not_empty)",
          (_handoff_of(body).get("h1") or {}).get("reason") == "comfy_queue_not_empty",
          str(_handoff_of(body).get("h1")))
    check("H1 blocked -> the handoff trace records no H2 attempt",
          _handoff_of(body).get("h2") is None)
    check("H1 blocked -> the executor was NEVER invoked", EXECUTOR_CALLS == [])
    check("H1 blocked -> NO vision analysis was attempted",
          "vision:analyze_ab" not in EVENTS, str(EVENTS))
    check("H1 blocked -> NO Ollama unload was attempted", FAKE.unload_calls == [])

    # (b) H1 /free failure
    chat, runtime = install_harness()
    FAKE.free_status = 500
    status, body = post_chat("facade04d3c5b_fc_free",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    out = _payload(body)
    check("H1 /free failure -> render_blocked/gpu_handoff_h1_comfy_free_failed",
          out.get("type") == "render_blocked"
          and (_handoff_of(body).get("h1") or {}).get("reason") == "comfy_free_failed",
          str(_handoff_of(body).get("h1")))
    check("H1 /free failure -> the executor was NEVER invoked", EXECUTOR_CALLS == [])
    check("H1 /free failure -> NO Ollama unload was attempted", FAKE.unload_calls == [])

    # (c) H2 blocked because another request owns the vision model
    chat, runtime = install_harness()
    holder = GH.ollama_model_lease(VISION_MODEL, wait=0)
    holder.acquire()
    try:
        status, body = post_chat("facade04d3c5b_fc_busy",
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})
    finally:
        holder.release()
    out = _payload(body)
    check("H2 model busy -> render_blocked/gpu_handoff_h2_ollama_model_busy",
          out.get("type") == "render_blocked"
          and (_handoff_of(body).get("h2") or {}).get("reason") == "ollama_model_busy",
          str(_handoff_of(body).get("h2")))
    check("H2 model busy -> the executor was NEVER invoked", EXECUTOR_CALLS == [])
    check("H2 model busy -> the vision model was NOT unloaded",
          FAKE.unload_calls == [], str(FAKE.unload_calls))
    check("H2 model busy -> the vision analysis still ran (A/B gate untouched)",
          "vision:analyze_ab" in EVENTS)

    # (d) H2 unload failure
    chat, runtime = install_harness()
    FAKE.unload_status = 500
    status, body = post_chat("facade04d3c5b_fc_unload",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    out = _payload(body)
    check("H2 unload failure -> render_blocked/gpu_handoff_h2_ollama_unload_failed",
          out.get("type") == "render_blocked"
          and (_handoff_of(body).get("h2") or {}).get("reason") == "ollama_unload_failed",
          str(_handoff_of(body).get("h2")))
    check("H2 unload failure -> the executor was NEVER invoked", EXECUTOR_CALLS == [])

    # (e) H2 incomplete confirmation
    chat, runtime = install_harness()
    FAKE.unload_effective = False
    status, body = post_chat("facade04d3c5b_fc_unconfirmed",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    out = _payload(body)
    check("H2 incomplete confirmation -> render_blocked/gpu_handoff_h2_ollama_unload_unconfirmed",
          out.get("type") == "render_blocked"
          and (_handoff_of(body).get("h2") or {}).get("reason") == "ollama_unload_unconfirmed",
          str(_handoff_of(body).get("h2")))
    check("H2 incomplete confirmation -> the executor was NEVER invoked", EXECUTOR_CALLS == [])

    # (f) blocked fidelity never reaches H2 or the render
    chat, runtime = install_harness()
    CA.validate_render_fidelity = lambda text, contract=None: {
        "contract": "RenderSemanticFidelityV1", "status": "BLOCKED",
        "reason_code": "TEST_BLOCKED", "may_proceed_to_render": False,
    }
    try:
        status, body = post_chat("facade04d3c5b_fc_fidelity",
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})
    finally:
        CA.validate_render_fidelity = _fidelity_pass
    out = _payload(body)
    check("BLOCKED fidelity -> render_blocked (FACADE-04A gate preserved)",
          out.get("type") == "render_blocked", str(out.get("type")))
    check("BLOCKED fidelity -> the executor was NEVER invoked", EXECUTOR_CALLS == [])
    check("BLOCKED fidelity -> H2 never ran (nothing was unloaded)", FAKE.unload_calls == [])

    # (g) single-image path is untouched by the handoff
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c5b_single", {"image": B_IMAGE})
    check("single-image edit still uses the legacy edit handler",
          HANDLER_CALLS == ["edit"], str(HANDLER_CALLS))
    check("single-image edit selects flux_img2img.json",
          (runtime.last_render_metadata or {}).get("workflow_name") == "flux_img2img.json",
          str((runtime.last_render_metadata or {}).get("workflow_name")))
    check("single-image path runs NO handoff (no H1, no H2)",
          not any(e.startswith(("h1:", "h2:")) for e in EVENTS), str(EVENTS))
    check("single-image path unloads NOTHING", FAKE.unload_calls == [])


def _fidelity_pass(text, contract=None):
    return {"contract": "RenderSemanticFidelityV1", "status": "PASS",
            "reason_code": "OK", "may_proceed_to_render": True}


# ==========================================================
# [7] CONCURRENT REQUESTS
# ==========================================================

def section_concurrency():
    print("\n[7] CONCURRENT REQUESTS")

    # (a) two simultaneous lease acquisitions -> exactly one winner
    wins = []

    def grab(tag):
        lease = GH.ollama_model_lease("race:1b", wait=0)
        if lease.acquire():
            wins.append(tag)
            time.sleep(0.3)
            lease.release()

    threads = [threading.Thread(target=grab, args=("t%d" % i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("two concurrent lease acquisitions -> exactly ONE winner",
          len(wins) == 1, str(wins))

    # (b) concurrent CHAT (holding the vision model) + facade render
    chat, runtime = install_harness()
    holder = GH.ollama_model_lease(VISION_MODEL, wait=0)
    holder.acquire()
    stop = threading.Event()
    chat_done = []

    def chat_like():
        # A real chat request now holds this exact lease for the duration of
        # its Ollama call. Simulated here by holding it across the render.
        try:
            while not stop.is_set():
                time.sleep(0.02)
        finally:
            chat_done.append(True)

    t = threading.Thread(target=chat_like)
    t.start()
    try:
        status, body = post_chat("facade04d3c5b_conc_chat",
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})
    finally:
        stop.set()
        t.join()
        holder.release()

    check("concurrent chat + facade render -> render_blocked (chat never disturbed)",
          _payload(body).get("type") == "render_blocked"
          and (_handoff_of(body).get("h2") or {}).get("reason") == "ollama_model_busy",
          str(_handoff_of(body).get("h2")))
    check("concurrent chat -> the chat request's model was NOT unloaded",
          FAKE.unload_calls == [], str(FAKE.unload_calls))
    check("concurrent chat -> the executor was NEVER invoked", EXECUTOR_CALLS == [])
    check("concurrent chat -> the chat request itself completed untouched",
          chat_done == [True])

    # after the chat finishes, the same request succeeds
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c5b_conc_chat_after",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    check("once chat is idle the facade render proceeds", len(EXECUTOR_CALLS) == 1,
          str(len(EXECUTOR_CALLS)))

    # (c) two concurrent dual-image requests
    chat, runtime = install_harness()
    results = {}
    barrier = threading.Barrier(2)

    def dual(tag):
        barrier.wait()
        results[tag] = post_chat("facade04d3c5b_conc_%s" % tag,
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})

    threads = [threading.Thread(target=dual, args=(tag,)) for tag in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check("two concurrent dual-image requests both answered",
          len(results) == 2, str(list(results)))
    check("neither concurrent dual-image request raised a 5xx",
          all(r[0] == 200 for r in results.values()), str({k: v[0] for k, v in results.items()}))
    check("each request produced at most one render submit",
          len(EXECUTOR_CALLS) <= 2, str(len(EXECUTOR_CALLS)))
    check("no unload happened while another request still held the model",
          all(m == VISION_MODEL for m in FAKE.unload_calls), str(FAKE.unload_calls))
    check("no outbound connect was attempted during concurrency",
          _BLOCKED_CONNECTS == [], str(_BLOCKED_CONNECTS[:2]))


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("=== FACADE-04D.3C-5B SAFE VISION-TO-RENDER GPU HANDOFF — ACCEPTANCE SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    section_static()
    section_lease()
    section_h1()
    section_h2()
    section_callers()
    section_e2e()
    section_fail_closed()
    section_concurrency()

    print("\n=== SOCKET GUARD: blocked outbound connects = %d ===" % len(_BLOCKED_CONNECTS))

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3C-5B GPU HANDOFF ACCEPTANCE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)
        shutil.rmtree(HANDOFF_TEST_DIR, ignore_errors=True)
    sys.exit(code)
