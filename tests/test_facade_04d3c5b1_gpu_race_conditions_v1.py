# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-5B.1 — GPU HANDOFF RACE-CONDITION VERIFICATION (ACCEPTANCE SUITE)
#
# MOCKED ONLY. No real rendering, no ComfyUI job submission, no live GPU
# inference, no live Ollama unload, no service restart.
#
#   * A socket-level guard raises on ANY connect to 8188 (ComfyUI) or 11434
#     (Ollama), so a live call is impossible.
#   * Every ComfyUI/Ollama HTTP surface is an injected fake.
#   * The render executor is a recorder.
#
# Verifies the two races found in 5B and the minimal fix:
#   RACE A — an Ollama inference could reload the shared model once H2 had
#            released its model lease, while ComfyUI was still rendering.
#            (Aggravated: RenderRuntime.render() itself reloads it.)
#   RACE B — H1's [GET /queue -> POST /free] window was not atomic against an
#            ArchitectOS render submission.
#
# Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#   .venv/Scripts/python.exe tests/test_facade_04d3c5b1_gpu_race_conditions_v1.py
# ==========================================================

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- NETWORK-SAFETY GUARD (set BEFORE importing app/config) ----
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"
os.environ.setdefault("ARCHITECTOS_CORE_API_HOST", "127.0.0.1")

# ---- HANDOFF TEST ISOLATION (private lock dir + zero/short bounded waits) ----
HANDOFF_TEST_DIR = tempfile.mkdtemp(prefix="facade04d3c5b1_handoff_")
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
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

import requests  # noqa: E402

_CONN_ERROR = requests.exceptions.ConnectionError
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


def _pos(source, needle):
    return source.find(needle)


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
        self.offline = False
        #: probes recorded while H1 is inside its [queue -> /free] window
        self.probes = []
        #: gate so a competing submit can be launched DURING H1's window
        self.h1_at_queue = threading.Event()
        self.h1_hold_seconds = 0.0
        self.submit_attempted_in_window = None

    # ------------------------------------------------------
    def _comfy(self, url):
        if url.endswith("/queue"):
            self.events.append("h1:queue")
            if self.probes is not None:
                self.probes.append(("queue", self._probe_comfyui_lease()))
            if not self.queue_readable:
                return _Resp(500, None)
            # give a competing submitter a chance to land inside the window
            if self.h1_hold_seconds:
                self.h1_at_queue.set()
                time.sleep(self.h1_hold_seconds)
            return _Resp(200, {"queue_running": list(range(self.queue_running)),
                               "queue_pending": list(range(self.queue_pending))})
        if url.endswith("/free"):
            self.events.append("h1:free")
            self.probes.append(("free", self._probe_comfyui_lease()))
            if self.free_status < 400:
                self.vram_free = 16_700_000_000
            return _Resp(self.free_status, {})
        if url.endswith("/system_stats"):
            self.events.append("stats")
            if not self.stats_readable:
                return _Resp(500, None)
            return _Resp(200, {"devices": [{"vram_free": self.vram_free}]})
        return _Resp(404, None)

    def _probe_comfyui_lease(self):
        """Is the ComfyUI submission lease free while H1 is mid-window?"""
        probe = GH.comfyui_lease(wait=0)
        got = probe.acquire()
        if got:
            probe.release()
        return got

    def _ollama(self, url):
        if url.endswith("/api/ps"):
            self.events.append("ollama:ps")
            if not self.ps_readable:
                return _Resp(500, None)
            return _Resp(200, {"models": [{"name": m} for m in self.ollama_models]})
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

    def post(self, url, json=None, timeout=None):  # noqa: A002 - requests API
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


class FakeComfySession:
    """Mocked session for ComfyHTTPRuntime itself (submit / history)."""

    def __init__(self, services):
        self.services = services
        self.submits = []

    def post(self, url, json=None, timeout=None):  # noqa: A002
        if url.endswith("/prompt"):
            self.submits.append({"at": time.monotonic(), "workflow": json})
            self.services.events.append("comfy:prompt")
            return _Resp(200, {"prompt_id": "mock-prompt-1"})
        return _Resp(404, None)

    def get(self, url, timeout=None):
        return _Resp(200, {})


COMFY_SESSION = FakeComfySession(FAKE)


class _NoLLM:
    """Stand-in for the semantic-intent LLM: a failed call, no socket."""

    def generate(self, prompt, use_context=False):
        return None


# ==========================================================
# HARNESS
# ==========================================================

STAGE_ROOT = tempfile.mkdtemp(prefix="facade04d3c5b1_comfy_input_")

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
    COMFY_SESSION.submits.clear()

    def fake_execute(workflow, engine):
        EVENTS.append("render:execute")
        EXECUTOR_CALLS.append({"workflow": workflow, "engine": engine})
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.executor.comfy.session = COMFY_SESSION
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    # the semantic-intent engine is SHARED between the handler and the render
    # runtime; stubbing its LLM removes the last live-Ollama surface
    chat.image_handler.semantic_intent.llm = _NoLLM()

    if not getattr(runtime, "_3c5b1_spied", False):
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
        runtime._3c5b1_spied = True

    return chat, runtime


def _vision_ok(refs, context=None):
    EVENTS.append("vision:analyze_ab")
    return {
        "A": {"analysis_status": "OK"},
        "B": {"analysis_status": "OK"},
        "roles": {"A": "facade_reference", "B": "target_building",
                  "geometry_authority": "target_building"},
    }


VP.analyze_ab_references = _vision_ok

_fidelity_pass = lambda text, contract=None: {  # noqa: E731
    "contract": "RenderSemanticFidelityV1", "status": "PASS",
    "reason_code": "OK", "may_proceed_to_render": True,
}
CA.validate_render_fidelity = _fidelity_pass

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


def _payload(body):
    inner = body.get("response") if isinstance(body, dict) else None
    return inner if isinstance(inner, dict) else (body or {})


def _handoff_of(body):
    return (_payload(body).get("render_handoff") or {}).get("gpu_handoff") or {}


def _last_handoff():
    for trace in reversed(HANDOFF_TRACES):
        if isinstance(trace, dict) and trace.get("gpu_handoff"):
            return trace["gpu_handoff"]
    return {}


def _lease_free(lease_factory):
    probe = lease_factory(wait=0)
    got = probe.acquire()
    if got:
        probe.release()
    return got


# ==========================================================
# [0] STATIC + SAFETY
# ==========================================================

def section_static():
    print("\n[0] STATIC + SAFETY GUARDS")

    check("network guard: ComfyUI port is 9",
          os.environ.get("ARCHITECTOS_COMFY_PORT") == "9")
    check("network guard: socket.connect patched",
          socket.socket.connect is _guarded_connect)
    check("handoff lock dir is the private test dir",
          GH.handoff_dir() == HANDOFF_TEST_DIR, GH.handoff_dir())

    check("the gpu_render lease exists", hasattr(GH, "gpu_render_lease"))
    check("the comfyui lease exists", hasattr(GH, "comfyui_lease"))
    check("a single documented lock order is declared",
          GH.LOCK_ORDER == ("gpu_render", "comfyui", "ollama_model"), str(GH.LOCK_ORDER))

    gh = open(os.path.join(PROJECT_ROOT, "core", "runtime",
                           "gpu_handoff_v1.py"), encoding="utf-8").read()
    rr = open(os.path.join(PROJECT_ROOT, "core", "render",
                           "render_runtime.py"), encoding="utf-8").read()
    ch = open(os.path.join(PROJECT_ROOT, "core", "render",
                           "comfy_http_runtime.py"), encoding="utf-8").read()
    ca = open(os.path.join(PROJECT_ROOT, "core", "chat",
                           "chat_architect.py"), encoding="utf-8").read()
    ih = open(os.path.join(PROJECT_ROOT, "core", "chat", "handlers",
                           "image_handler.py"), encoding="utf-8").read()

    check("ollama_model_call takes gpu_render FIRST, then the model lease",
          _pos(gh, "self._render.acquire()") < _pos(gh, "self._lock.acquire()"))
    check("ollama_model_call releases BOTH leases",
          gh.count("self._lock.release()") >= 1 and gh.count("self._render.release()") >= 2,
          "model=%d render=%d" % (gh.count("self._lock.release()"),
                                  gh.count("self._render.release()")))
    check("H1 takes the comfyui lease", "lease = comfyui_lease()" in gh)
    check("H1 releases it in a finally", "finally:\n        lease.release()" in gh)
    check("H1 fails closed when the lease is unavailable",
          '"comfyui_busy"' in gh)

    check("ComfyHTTPRuntime.submit takes the comfyui lease",
          "comfyui_lease()" in ch)
    check("ComfyHTTPRuntime.submit releases it in a finally",
          "finally:" in ch and "lease.release()" in ch)
    check("ComfyHTTPRuntime.submit refuses when the lease is unavailable",
          "comfyui_lease_unavailable" in ch)

    check("RenderRuntime takes the protected-render lease",
          "gpu_render_lease()" in rr)
    check("the protected lease is scoped to dual-image / conditioned",
          "if image_bindings or conditioned:" in rr)
    check("the protected lease is released in a finally",
          "if _render_guard is not None:" in rr and "_render_guard.release()" in rr)
    check("the protected lease is released on the H2 exception path",
          "except BaseException:" in rr and rr.count("_render_guard.release()") >= 3,
          "releases=%d" % rr.count("_render_guard.release()"))
    check("RenderRuntime blocks BEFORE the executor when ownership fails",
          _pos(rr, "render_lease_unavailable") < _pos(rr, "execution = self.executor.execute("))
    check("H2 now lives in RenderRuntime, immediately before the submit",
          _pos(rr, "unload_ollama_models_for_render()")
          < _pos(rr, "execution = self.executor.execute("))
    check("the image handler no longer runs H2",
          "unload_ollama_models_for_render" not in ih)
    check("the handler refuses a blocked handoff before the result bridge",
          _pos(ih, "gpu_handoff_blocked")
          < _pos(ih, "final_render = self.result_bridge.resolve("))
    check("the chat layer merges the trace from the render runtime",
          'self.render_runtime, "last_gpu_handoff_h2"' in ca)

    for forbidden in ("taskkill", "os.kill", "subprocess", "popen", "restart"):
        check("handoff module contains no %r" % forbidden, forbidden not in gh.lower())

    check("flux_img2img_dual.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json")) == SHA_DUAL)
    check("flux_img2img_dual_conditioned.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual_conditioned.json"))
          == SHA_CONDITIONED)

    # preserved FACADE gates
    check("FACADE-04A dual-image gate preserved",
          '"dual_image_render_not_ready"' in ca)
    check("render-approval gate preserved",
          'design_status != "approved" and design_render_request:' in ca)
    check("FACADE-04D.3C-4 declared-pair gate preserved",
          '"dual_image_binding_incomplete"' in ca)
    check("FACADE-04D.3C-3 prompt-injection fail-closed gate preserved",
          "prompt_injection_blocked" in rr)


# ==========================================================
# [1] RACE A — CONFIRMED AND CLOSED
# ==========================================================

def section_race_a():
    print("\n[1] RACE A — OLLAMA DURING RENDER")

    # ---- REPRODUCTION of the 5B window (lease absent) ----
    # 5B's H2 released the model lease as soon as the unload was confirmed.
    # Nothing then stopped the NEXT inference from reloading the model.
    _lease_free(GH.gpu_render_lease)  # ensure clean
    h2_style = GH.ollama_model_lease(VISION_MODEL, wait=0)
    check("REPRO: H2's model lease is acquired for the unload", h2_style.acquire() is True)
    h2_style.release()  # exactly what 5B did when H2 returned
    reload_after_h2 = None
    try:
        with GH.ollama_model_call(VISION_MODEL, wait=0):
            reload_after_h2 = "RELOADED"
    except GH.OllamaModelBusy:
        reload_after_h2 = "BLOCKED"
    check("REPRO: without a render lease an inference reloads the model during the render",
          reload_after_h2 == "RELOADED",
          "the 5B window is real: %s" % reload_after_h2)

    # ---- FIX: the protected rendering period owns the GPU ----
    guard = GH.gpu_render_lease(wait=0)
    check("FIX: the protected-render lease is acquired exclusively", guard.acquire() is True)
    try:
        blocked = None
        try:
            with GH.ollama_model_call(VISION_MODEL, wait=0):
                blocked = "RELOADED"
        except GH.OllamaModelBusy:
            blocked = "BLOCKED"
        check("FIX: no Ollama inference can start while the render owns the GPU",
              blocked == "BLOCKED", str(blocked))
    finally:
        guard.release()

    check("FIX: the GPU is free again once the protected period ends",
          _lease_free(GH.gpu_render_lease) is True)

    # ---- H2 refuses to unload a model an active inference is using ----
    install_harness()
    holder = GH.ollama_model_lease(VISION_MODEL, wait=0)
    holder.acquire()
    try:
        r = GH.unload_ollama_models_for_render(vision_model=VISION_MODEL,
                                               endpoint=FAKE.OLLAMA, session=FAKE,
                                               comfy_endpoint=FAKE.COMFY)
    finally:
        holder.release()
    check("active inference -> H2 refuses to unload (ollama_model_busy)",
          r["status"] == "blocked" and r["reason"] == "ollama_model_busy", str(r.get("reason")))
    check("active inference -> NO unload request was issued", FAKE.unload_calls == [])

    # ---- the real request path holds the protected lease ACROSS the submit ----
    chat, runtime = install_harness()
    seen = {}
    orig_execute = runtime.executor.execute

    def probing_execute(workflow, engine):
        probe = GH.gpu_render_lease(wait=0)
        seen["held_during_render"] = not probe.acquire()
        if seen["held_during_render"] is False:
            probe.release()
        probe2 = GH.ollama_model_lease(VISION_MODEL, wait=0)
        seen["model_lease_free"] = probe2.acquire()
        if seen["model_lease_free"]:
            probe2.release()
        return orig_execute(workflow, engine)

    runtime.executor.execute = probing_execute
    status, body = post_chat("facade04d3c5b1_protected",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})

    check("the render executed", len(EXECUTOR_CALLS) == 1, str(len(EXECUTOR_CALLS)))
    check("the protected-render lease is HELD while the render executes",
          seen.get("held_during_render") is True, str(seen))
    check("H2's model lease is already released at that point (5B's gap)",
          seen.get("model_lease_free") is True, str(seen))
    check("...which is exactly why the gpu_render lease is required",
          seen.get("held_during_render") is True and seen.get("model_lease_free") is True)
    check("the protected lease is released after the request",
          _lease_free(GH.gpu_render_lease) is True)
    check("H2 ran in this request",
          (_last_handoff().get("h2") or {}).get("status") in
          ("unloaded", "not_loaded", "not_running"),
          str(_last_handoff().get("h2")))
    check("no outbound connect was attempted", _BLOCKED_CONNECTS == [], str(_BLOCKED_CONNECTS[:1]))


# ==========================================================
# [2] RACE B — COMFYUI QUEUE vs /free
# ==========================================================

def section_race_b():
    print("\n[2] RACE B — GET /queue vs POST /free")

    # ---- REPRODUCTION: the window exists when nothing owns it ----
    install_harness()
    _lease_free(GH.comfyui_lease)
    probe = GH.comfyui_lease(wait=0)
    check("REPRO: with no owner, a competing submission CAN enter the window",
          probe.acquire() is True)
    probe.release()

    # ---- FIX: H1 owns the whole window ----
    install_harness()
    FAKE.probes = []
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    check("H1 still releases successfully", r["status"] == "released", str(r.get("reason")))
    check("H1 reports it owned the ComfyUI submission window",
          r.get("comfyui_lease") == "exclusive", str(r.get("comfyui_lease")))
    check("the ComfyUI lease is held at the /queue read",
          ("queue", False) in FAKE.probes, str(FAKE.probes))
    check("the ComfyUI lease is held at the /free call",
          ("free", False) in FAKE.probes, str(FAKE.probes))
    check("the ComfyUI lease is released after H1",
          _lease_free(GH.comfyui_lease) is True)

    # ---- a competing ArchitectOS submit cannot land inside the window ----
    install_harness()
    FAKE.probes = []
    FAKE.h1_hold_seconds = 0.4
    outcome = {}

    def competing_submit():
        FAKE.h1_at_queue.wait(timeout=5)
        runtime = ComfyHTTPRuntime(endpoint=FAKE.COMFY)
        runtime.session = COMFY_SESSION
        outcome["result"] = runtime.submit({"1": {"class_type": "X", "inputs": {}}})

    t = threading.Thread(target=competing_submit)
    t.start()
    r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    t.join(timeout=10)

    check("H1 completed while a submission raced it", r["status"] == "released",
          str(r.get("reason")))
    check("the racing submission was REFUSED (comfyui_lease_unavailable)",
          (outcome.get("result") or {}).get("message") == "comfyui_lease_unavailable",
          str(outcome.get("result")))
    check("the racing submission issued NO POST /prompt",
          COMFY_SESSION.submits == [], str(len(COMFY_SESSION.submits)))
    check("no /free happened after a submission in the same window",
          not (COMFY_SESSION.submits and FAKE.probes), str(FAKE.probes))

    # ---- H1 refuses to free memory while an ArchitectOS submission owns it ----
    install_harness()
    busy = GH.comfyui_lease(wait=0)
    busy.acquire()
    try:
        r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
    finally:
        busy.release()
    check("an in-flight ArchitectOS submission -> H1 blocked/comfyui_busy",
          r["status"] == "blocked" and r["reason"] == "comfyui_busy", str(r.get("reason")))
    check("H1 issued NO /free while a submission owned the window",
          not any(c[1].endswith("/free") for c in FAKE.calls))
    check("H1 issued NO /queue read either (it failed before the read)",
          not any(c[1].endswith("/queue") for c in FAKE.calls))

    # ---- submit works normally when nobody holds the window ----
    install_harness()
    runtime = ComfyHTTPRuntime(endpoint=FAKE.COMFY)
    runtime.session = COMFY_SESSION
    out = runtime.submit({"1": {"class_type": "X", "inputs": {}}})
    check("a submission proceeds normally when the window is free",
          out.get("status") == "submitted" and out.get("prompt_id") == "mock-prompt-1",
          str(out.get("status")))
    check("the ComfyUI lease is released after the submit",
          _lease_free(GH.comfyui_lease) is True)


# ==========================================================
# [3] CONCURRENT DUAL RENDERS
# ==========================================================

def section_concurrent_renders():
    print("\n[3] CONCURRENT DUAL-IMAGE REQUESTS")

    # two simultaneous protected periods -> exactly one winner
    wins = []

    def grab(tag):
        lease = GH.gpu_render_lease(wait=0)
        if lease.acquire():
            wins.append(tag)
            time.sleep(0.3)
            lease.release()

    threads = [threading.Thread(target=grab, args=("t%d" % i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("two simultaneous protected periods -> exactly ONE winner",
          len(wins) == 1, str(wins))
    check("the protected lease is free afterwards",
          _lease_free(GH.gpu_render_lease) is True)

    # a second dual request cannot invalidate the first one's ownership
    chat, runtime = install_harness()
    holder = GH.gpu_render_lease(wait=0)
    holder.acquire()
    try:
        status, body = post_chat("facade04d3c5b1_conc",
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})
    finally:
        holder.release()

    out = _payload(body)
    check("a competing dual request is refused before submission",
          out.get("type") == "render_blocked"
          and (_handoff_of(body).get("render") or {}).get("reason") == "render_lease_unavailable",
          str(_handoff_of(body).get("render")))
    check("the refusal is recorded as a blocked protected render period",
          (_handoff_of(body).get("render") or {}).get("status") == "blocked")
    check("the competing dual request invoked the executor ZERO times",
          EXECUTOR_CALLS == [])
    check("the competing dual request unloaded NOTHING",
          FAKE.unload_calls == [], str(FAKE.unload_calls))
    check("the competing dual request issued NO POST /prompt",
          COMFY_SESSION.submits == [])
    check("the first request's ownership was never invalidated",
          _lease_free(GH.gpu_render_lease) is True)

    # once the protected period ends the request succeeds normally
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c5b1_after",
                             {"image_a": A_IMAGE, "image_b": B_IMAGE})
    check("once the GPU is free the dual render proceeds",
          len(EXECUTOR_CALLS) == 1, str(len(EXECUTOR_CALLS)))


# ==========================================================
# [4] LOCK RELEASE ON FAILURE / EXCEPTION / TIMEOUT
# ==========================================================

def section_lock_release():
    print("\n[4] LOCKS RELEASED ON FAILURE / EXCEPTION / TIMEOUT")

    # (a) H2 blocked inside the protected period -> gpu_render still released
    chat, runtime = install_harness()
    holder = GH.ollama_model_lease(VISION_MODEL, wait=0)
    holder.acquire()
    try:
        status, body = post_chat("facade04d3c5b1_rel_busy",
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE})
    finally:
        holder.release()
    check("H2 busy -> render_blocked",
          _payload(body).get("type") == "render_blocked", str(_payload(body).get("type")))
    check("H2 busy -> the refusal is recorded on the handoff trace",
          (_handoff_of(body).get("render") or {}).get("reason")
          == "gpu_handoff_h2_ollama_model_busy",
          str(_handoff_of(body).get("render")))
    check("H2 busy -> the protected lease is still released",
          _lease_free(GH.gpu_render_lease) is True)
    check("H2 busy -> the executor was never invoked", EXECUTOR_CALLS == [])

    # (b) H2 raising an exception -> gpu_render still released
    chat, runtime = install_harness()
    orig_h2 = GH.unload_ollama_models_for_render

    def exploding_h2(*a, **k):
        raise RuntimeError("injected H2 failure")

    GH.unload_ollama_models_for_render = exploding_h2
    raised = False
    try:
        runtime.render("chat_project",
                       {"prompt": EXACT_PROMPT, "mode": "img2img"},
                       "flux", {"path": B_IMAGE},
                       image_bindings={"style_reference": {"node_id": "302", "filename": "A.jpg"},
                                       "target_building": {"node_id": "300", "filename": "B.jpg"}},
                       conditioned=False)
    except RuntimeError as exc:
        raised = "injected H2 failure" in str(exc)
    finally:
        GH.unload_ollama_models_for_render = orig_h2
    check("an exception inside the protected period propagates", raised is True)
    check("an exception inside the protected period still releases the lease",
          _lease_free(GH.gpu_render_lease) is True)

    # (c) executor failure -> gpu_render still released
    chat, runtime = install_harness()
    def exploding_execute(workflow, engine):
        raise RuntimeError("injected executor failure")
    runtime.executor.execute = exploding_execute
    raised = False
    try:
        runtime.render("chat_project",
                       {"prompt": EXACT_PROMPT, "mode": "img2img"},
                       "flux", {"path": B_IMAGE},
                       image_bindings={"style_reference": {"node_id": "302", "filename": "A.jpg"},
                                       "target_building": {"node_id": "300", "filename": "B.jpg"}},
                       conditioned=False)
    except RuntimeError as exc:
        raised = "injected executor failure" in str(exc)
    check("an executor failure propagates", raised is True)
    check("an executor failure still releases the protected lease",
          _lease_free(GH.gpu_render_lease) is True)

    # (d) H1 failure paths release the comfyui lease
    for label, setup in (
        ("nonempty queue", lambda: setattr(FAKE, "queue_running", 1)),
        ("/free failure", lambda: setattr(FAKE, "free_status", 500)),
        ("unconfirmed release", lambda: setattr(FAKE, "stats_readable", False)),
    ):
        install_harness()
        setup()
        r = GH.release_comfyui_for_vision(endpoint=FAKE.COMFY, session=FAKE)
        check("H1 %s -> blocked and the comfyui lease is released" % label,
              r["status"] == "blocked" and _lease_free(GH.comfyui_lease) is True,
              "%s / %s" % (r.get("reason"), r.get("status")))

    # (e) submit failure path releases the comfyui lease
    install_harness()
    runtime = ComfyHTTPRuntime(endpoint=FAKE.COMFY)

    class FailingSession:
        def post(self, url, json=None, timeout=None):  # noqa: A002
            raise RuntimeError("injected submit transport failure")

        def get(self, url, timeout=None):
            return _Resp(200, {})

    runtime.session = FailingSession()
    out = runtime.submit({"1": {"class_type": "X", "inputs": {}}})
    check("a submit transport failure is reported truthfully",
          out.get("status") == "error", str(out.get("status")))
    check("a submit transport failure still releases the comfyui lease",
          _lease_free(GH.comfyui_lease) is True)

    # (f) bounded waiting — no unbounded wait anywhere
    start = time.monotonic()
    busy = GH.gpu_render_lease(wait=0)
    busy.acquire()
    try:
        blocked = GH.gpu_render_lease(wait=0).acquire()
    finally:
        busy.release()
    elapsed = time.monotonic() - start
    check("a failed acquisition is immediate and bounded (no unbounded wait)",
          blocked is False and elapsed < 1.0, "%.3fs" % elapsed)

    start = time.monotonic()
    busy = GH.comfyui_lease(wait=0)
    busy.acquire()
    try:
        blocked = GH.comfyui_lease(wait=0).acquire()
    finally:
        busy.release()
    elapsed = time.monotonic() - start
    check("the comfyui lease is bounded too", blocked is False and elapsed < 1.0,
          "%.3fs" % elapsed)


# ==========================================================
# [5] ORDINARY CHAT OUTSIDE PROTECTED INTERVALS
# ==========================================================

def section_chat():
    print("\n[5] ORDINARY CHAT OUTSIDE PROTECTED INTERVALS")

    gateway = LGW.LLMGateway()
    seen = {}

    class _GW:
        def post(self, url, json=None, timeout=None):  # noqa: A002
            r = GH.gpu_render_lease(wait=0)
            seen["render_lease_held"] = not r.acquire()
            if seen["render_lease_held"] is False:
                r.release()
            m = GH.ollama_model_lease(gateway.model, wait=0)
            seen["model_lease_held"] = not m.acquire()
            if seen["model_lease_held"] is False:
                m.release()
            return _Resp(200, {"response": "ok"})

        def get(self, url, timeout=None):
            return _Resp(200, {"models": []})

    gateway.session = _GW()
    out = gateway.generate("سلام")
    check("ordinary chat works when no render is in progress", out == "ok", str(out))
    check("chat holds the protected lease only for its own call",
          seen.get("render_lease_held") is True)
    check("chat holds its model lease during the call",
          seen.get("model_lease_held") is True)
    check("the protected lease is released after the chat call",
          _lease_free(GH.gpu_render_lease) is True)
    check("the model lease is released after the chat call",
          _lease_free(lambda wait=0: GH.ollama_model_lease(VISION_MODEL, wait=wait)) is True)

    # chat during a protected render fails truthfully instead of contending
    holder = GH.gpu_render_lease(wait=0)
    holder.acquire()
    try:
        gateway.session = _GW()
        out2 = gateway.generate("سلام")
    finally:
        holder.release()
    check("chat during a protected render fails truthfully (never contends)",
          out2 is None and gateway.last_error == "model_busy:" + gateway.model,
          str(gateway.last_error))
    check("chat during a protected render issues no Ollama HTTP call",
          seen.get("model_lease_held") is True)
    gateway.session = _GW()
    check("chat is fully functional again once the render ends",
          gateway.generate("سلام") == "ok")


# ==========================================================
# [6] PAYLOAD + ROUTING PRESERVED
# ==========================================================

def section_payload():
    print("\n[6] EXECUTION PAYLOAD PRESERVED")

    def run(tag, extra=None):
        chat, runtime = install_harness()
        status, body = post_chat("facade04d3c5b1_%s" % tag,
                                 {"image_a": A_IMAGE, "image_b": B_IMAGE}, extra=extra)
        wf = (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}
        return runtime, wf, status, body

    runtime, wf, status, body = run("off")
    md = runtime.last_render_metadata or {}
    check("OFF: HTTP 200 and exactly one submit", status == 200 and len(EXECUTOR_CALLS) == 1)
    check("OFF: handler route is generate", HANDLER_CALLS == ["generate"], str(HANDLER_CALLS))
    check("OFF: workflow == flux_img2img_dual.json",
          md.get("workflow_name") == "flux_img2img_dual.json", str(md.get("workflow_name")))
    check("OFF: IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("OFF: IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("OFF: 300 -> 301 -> 210 intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    s = (wf.get("210") or {}).get("inputs", {})
    check("OFF: seed/steps/cfg/denoise = 123456789/30/5/0.3",
          (s.get("seed"), s.get("steps"), s.get("cfg"), s.get("denoise"))
          == (SEED, 30, 5, 0.3), str(s))
    check("OFF: preset suppressed", md.get("preset") is None, str(md.get("preset")))

    runtime, wf, status, body = run("on", extra={"conditioned_render": "1"})
    md = runtime.last_render_metadata or {}
    check("ON: workflow == flux_img2img_dual_conditioned.json",
          md.get("workflow_name") == "flux_img2img_dual_conditioned.json",
          str(md.get("workflow_name")))
    check("ON: IMAGE A -> node 302 / IMAGE B -> node 300",
          bool((wf.get("302") or {}).get("inputs", {}).get("image"))
          and bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("ON: USO reaches KSampler.model (210.model <- [322,0])",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0])
    check("ON: ControlNet -> positive (210.positive <- [311,0])",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0])
    check("ON: ControlNet -> negative (210.negative <- [311,1])",
          (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1])
    check("ON: USO LoRA 320 / USOStyleReference 322 / ControlNetLoader 310 unchanged",
          (wf.get("320") or {}).get("class_type") == "LoraLoaderModelOnly"
          and (wf.get("322") or {}).get("class_type") == "USOStyleReference"
          and (wf.get("310") or {}).get("class_type") == "ControlNetLoader")
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")
    check("ON: resolved prompt reaches node 206",
          bool(resolved) and (wf.get("206") or {}).get("inputs", {}).get("text") == resolved)
    t212 = (wf.get("212") or {}).get("inputs", {}).get("text")
    check("ON: negative prompt reaches node 212", bool(t212) and t212 != resolved)
    s = (wf.get("210") or {}).get("inputs", {})
    check("ON: seed/steps/cfg/denoise = 123456789/30/5/0.3",
          (s.get("seed"), s.get("steps"), s.get("cfg"), s.get("denoise"))
          == (SEED, 30, 5, 0.3), str(s))

    # H1/H2 still bracketed correctly around the whole request
    handoff = _last_handoff()
    check("the handoff trace records H1 released/not_running",
          (handoff.get("h1") or {}).get("status") in ("released", "not_running"),
          str((handoff.get("h1") or {}).get("reason")))
    check("the handoff trace records H2 unloaded/not_loaded/not_running",
          (handoff.get("h2") or {}).get("status") in
          ("unloaded", "not_loaded", "not_running"),
          str((handoff.get("h2") or {}).get("reason")))
    check("the handoff trace records the protected period as acquired",
          (handoff.get("render") or {}).get("status") == "acquired",
          str(handoff.get("render")))

    # single-image + text paths untouched by the protected period
    chat, runtime = install_harness()
    status, body = post_chat("facade04d3c5b1_single", {"image": B_IMAGE})
    check("single-image edit still uses the legacy edit handler",
          HANDLER_CALLS == ["edit"], str(HANDLER_CALLS))
    check("single-image edit takes NO protected-render lease (no dual request)",
          _lease_free(GH.gpu_render_lease) is True)

    check("no outbound connect was ever attempted",
          _BLOCKED_CONNECTS == [], str(_BLOCKED_CONNECTS[:1]))


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("=== FACADE-04D.3C-5B.1 GPU HANDOFF RACE CONDITIONS — ACCEPTANCE SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    section_static()
    section_race_a()
    section_race_b()
    section_concurrent_renders()
    section_lock_release()
    section_chat()
    section_payload()

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

    print("ALL FACADE-04D.3C-5B.1 RACE-CONDITION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)
        shutil.rmtree(HANDOFF_TEST_DIR, ignore_errors=True)
    sys.exit(code)
