# ==========================================================
# ArchitectOS — V4.3F CLOSEOUT: ORPHAN OWNERSHIP AND MISSING READERS
#
# Two questions, both about whether an unconfirmed ComfyUI job can lose its
# GPU lease:
#
#   A. Is `RenderRuntime` reused across requests, or can it be discarded while
#      an orphaned job is still active?
#   B. Does a missing queue reader silently release a job that may be running?
#
# NO GPU. NO COMFYUI. NO OLLAMA. Real `CrossProcessLock` files, isolated
# namespace.
# ==========================================================

import gc

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.chat.chat_architect import ChatArchitect
from core.render.comfy_http_runtime import ComfyHTTPRuntime
from core.render.render_runtime import RenderRuntime
from core.render.workflow_executor import WorkflowExecutor

PROMPT_ID = "closeout-prompt-0001"
BASE_IMAGE = "runs/architectos_product_integration_v3/p3a_transfer_output.png"
GIB = 1024 ** 3


class _StubBrain:
    """ChatArchitect only reads architectural_intent_engine from the brain."""


# ----------------------------------------------------------
# SIMULATED COMFYUI
# ----------------------------------------------------------

class _Response:
    def __init__(self, code, payload):
        self.status_code = code
        self._p = payload

    def json(self):
        return self._p


class SimQueue:
    def __init__(self, prompt_id=PROMPT_ID):
        self.prompt_id = prompt_id
        self.running = True

    def get(self, url, timeout=None):
        if url.endswith("/queue"):
            return _Response(200, {
                "queue_running": [[0, self.prompt_id]] if self.running else [],
                "queue_pending": [],
            })
        if "/history/" in url:
            return _Response(200, {})
        return _Response(404, {})

    def post(self, url, json=None, timeout=None):
        return _Response(200, {"cancelled": False})   # accepted, inert


class SimComfy(ComfyHTTPRuntime):
    def __init__(self, queue):
        super().__init__("http://closeout.invalid")
        self.session = queue
        self.queue = queue

    def submit(self, workflow):
        return {"status": "submitted", "prompt_id": PROMPT_ID}

    def wait_for_result(self, prompt_id, timeout=None, interval=None):
        return super().wait_for_result(prompt_id, timeout=0.25, interval=0.05)

    def extract_images(self, history):
        return []

    def extract_videos(self, history):
        return []

    def detect_error(self, history):
        return None


def _h2(**kwargs):
    return {
        "status": "unloaded", "reason": None, "ownership": "exclusive",
        "loaded_before": [], "unloaded": [], "failed": [], "skipped_in_use": [],
        "vram_free_before": 16 * GIB, "vram_free_after": 16 * GIB,
    }


def _design():
    return {
        "prompt": "same tower, night",
        "original_prompt": "same tower, night",
        "mode": "img2img",
        "architectural_intent": {
            "building_type": "tower", "style": "modern", "materials": [],
            "levels": {"basement": 0, "ground": 1, "above_ground": 5,
                       "mezzanine": 0, "total": 5},
        },
        "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": [],
        "seed": 7,
    }


def _lease_free():
    probe = gh.gpu_render_lease(wait=0)
    if probe.acquire():
        probe.release()
        return True
    return False


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    monkeypatch.setenv("ARCHITECTOS_COMFY_CANCEL_CONFIRM_TIMEOUT", "0.3")
    monkeypatch.setenv("ARCHITECTOS_COMFY_CANCEL_CONFIRM_INTERVAL", "0.05")
    monkeypatch.delenv("ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB", raising=False)
    monkeypatch.setattr(gh, "unload_ollama_models_for_render", _h2)
    return target


def _chat_with_sim_queue():
    """The real application object, with a simulated ComfyUI behind it."""

    chat = ChatArchitect(_StubBrain())
    queue = SimQueue()
    comfy = SimComfy(queue)

    executor = WorkflowExecutor()
    executor.comfy = comfy
    chat.render_runtime.executor = executor

    return chat, queue, comfy


def _orphan(chat):
    return chat.render_runtime.render(
        "closeout", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )


# ==========================================================
# A1 / A2 — OWNERSHIP AND LIFETIME
# ==========================================================

def test_chat_architect_owns_one_render_runtime(isolated):
    chat = ChatArchitect(_StubBrain())

    # The handler that actually renders uses the SAME object.
    assert chat.image_handler.render_runtime is chat.render_runtime

    # And it is not rebuilt on access.
    assert id(chat.render_runtime) == id(chat.render_runtime)


def test_runtime_is_not_recreated_between_requests(isolated):
    chat, queue, _ = _chat_with_sim_queue()
    before = id(chat.render_runtime)

    queue.running = False
    chat.render_runtime.render(
        "closeout-1", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert id(chat.render_runtime) == before


# ==========================================================
# A3 / A5 — ORPHAN SURVIVES THE REQUEST BOUNDARY
# ==========================================================

def test_orphan_survives_the_request_boundary(isolated):
    chat, queue, _ = _chat_with_sim_queue()

    first = _orphan(chat)
    assert first["status"] == "gpu_handoff_orphaned"

    # The request has returned to its caller. A NEW request arrives, served by
    # the same process-scoped runtime.
    second = chat.render_runtime.render(
        "closeout-2", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert second["status"] == "gpu_handoff_orphaned"
    assert second["reason"] == "previous_job_state_unconfirmed"
    assert _lease_free() is False

    with pytest.raises(gh.OllamaModelBusy):
        with gh.ollama_model_call("qwen3.8:27b", wait=0):
            pass


def test_orphan_recovers_through_the_owned_runtime_when_queue_clears(isolated):
    chat, queue, _ = _chat_with_sim_queue()

    assert _orphan(chat)["status"] == "gpu_handoff_orphaned"
    assert _lease_free() is False

    queue.running = False

    result = chat.render_runtime.render(
        "closeout-3", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result.get("status") != "gpu_handoff_orphaned"
    assert chat.render_runtime._orphaned_render_guard is None
    assert _lease_free() is True


# ==========================================================
# A4 — DROPPING LOCAL REFERENCES MUST NOT RELEASE THE LEASE
# ==========================================================

def test_orphan_survives_local_reference_drop_and_gc(isolated):
    chat, queue, _ = _chat_with_sim_queue()

    runtime = chat.render_runtime
    assert _orphan(chat)["status"] == "gpu_handoff_orphaned"

    # Drop every local reference we hold. The application still owns `chat`,
    # exactly as `app.py` does at module scope.
    del runtime
    gc.collect()

    assert _lease_free() is False
    assert chat.render_runtime._orphaned_render_guard is not None

    with pytest.raises(gh.OllamaModelBusy):
        with gh.ollama_model_call("qwen3.8:27b", wait=0):
            pass


def test_a_discarded_runtime_would_release_the_lease(isolated):
    """Why ownership matters: GC of an UNOWNED runtime frees the advisory lock.

    This is the failure mode the application's module-scoped ownership avoids.
    It is demonstrated here rather than assumed.
    """

    queue = SimQueue()
    runtime = RenderRuntime()
    executor = WorkflowExecutor()
    executor.comfy = SimComfy(queue)
    runtime.executor = executor

    result = runtime.render(
        "closeout-unowned", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )
    assert result["status"] == "gpu_handoff_orphaned"
    assert _lease_free() is False

    del runtime
    gc.collect()

    # The guard died with the object; the OS released the advisory lock while
    # the simulated job is still running.
    assert queue.running is True
    assert _lease_free() is True


def test_a_second_runtime_cannot_acquire_while_orphan_is_held(isolated):
    chat, queue, _ = _chat_with_sim_queue()
    assert _orphan(chat)["status"] == "gpu_handoff_orphaned"

    # e.g. an ImageTool-owned runtime in the same process
    other = RenderRuntime()
    other_executor = WorkflowExecutor()
    other_executor.comfy = SimComfy(queue)
    other.executor = other_executor

    result = other.render(
        "closeout-other", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "render_lease_unavailable"
    assert other_executor.comfy.queue.running is True   # nothing submitted


# ==========================================================
# B — MISSING QUEUE READER
# ==========================================================

class _StatusExecutor:
    """No `.comfy` at all: the runtime has no observation channel."""

    def __init__(self, status, prompt_id=None):
        self.status = status
        self.prompt_id = prompt_id
        self.calls = []

    def execute(self, workflow, engine):
        self.calls.append(engine)
        return {"status": self.status, "prompt_id": self.prompt_id}


class _RaisingExecutor:
    def __init__(self, comfy=None):
        self.comfy = comfy
        self.calls = []

    def execute(self, workflow, engine):
        self.calls.append(engine)
        raise RuntimeError("simulated executor failure")


class _StaticQueue:
    def __init__(self, running):
        self.running = running

    def queue_state(self):
        return {
            "ok": True,
            "running": ["some-prompt"] if self.running else [],
            "pending": [],
            "reason": None,
        }


def _render_with(executor):
    runtime = RenderRuntime()
    runtime.executor = executor
    raised = None
    try:
        result = runtime.render(
            "closeout-status", _design(), "flux",
            {"path": BASE_IMAGE, "filename": "base.png"},
        )
    except BaseException as exc:      # the exception is expected to propagate
        raised = exc
        result = {"status": "raised"}
    return runtime, result, raised


def test_submitted_job_without_queue_reader_retains_lease(isolated):
    runtime, result, _ = _render_with(
        _StatusExecutor("timeout_unconfirmed", PROMPT_ID)
    )

    assert result["status"] == "gpu_handoff_orphaned"
    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False

    with pytest.raises(gh.OllamaModelBusy):
        with gh.ollama_model_call("qwen3.8:27b", wait=0):
            pass


def test_lost_prompt_id_without_reader_retains_lease(isolated):
    runtime, result, _ = _render_with(_StatusExecutor("missing_prompt_id", None))

    assert result["status"] == "gpu_handoff_orphaned"
    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False


def test_proven_submit_failure_releases_lease(isolated):
    runtime, result, _ = _render_with(_StatusExecutor("submit_error", None))

    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


def test_completed_job_without_reader_releases_lease(isolated):
    runtime, result, _ = _render_with(_StatusExecutor("completed", PROMPT_ID))

    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


def test_exception_without_reader_keeps_previous_behaviour(isolated):
    """No submission evidence and no channel: nothing to observe or recover."""

    runtime, _, raised = _render_with(_RaisingExecutor(comfy=None))
    assert raised is not None
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


def test_exception_with_reader_retains_when_a_job_is_active(isolated):
    runtime, _, raised = _render_with(_RaisingExecutor(comfy=_StaticQueue(True)))
    assert raised is not None

    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False


def test_exception_with_reader_releases_when_queue_is_clear(isolated):
    runtime, _, raised = _render_with(_RaisingExecutor(comfy=_StaticQueue(False)))
    assert raised is not None

    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True
