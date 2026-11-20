# ==========================================================
# ArchitectOS — V4.3F GPU LEASE LIFECYCLE TESTS
#
# The defect this suite pins: `wait_for_result()` reaching its timeout used to
# return while the ComfyUI job could still be running, and `render()` released
# the `gpu_render` lease unconditionally. Ollama could then load a heavy model
# into the same VRAM while FLUX was still sampling.
#
# These tests drive the REAL `ComfyHTTPRuntime` lifecycle code (queue parsing,
# cancel request, bounded confirmation, timeout classification) through a
# simulated transport, with REAL `CrossProcessLock` files in an isolated
# namespace.
#
# NO GPU. NO COMFYUI. NO SAMPLER. NO NETWORK.
# ==========================================================

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.render.comfy_http_runtime import ComfyHTTPRuntime
from core.render.render_runtime import RenderRuntime
from core.render.workflow_executor import WorkflowExecutor

PROMPT_ID = "sim-prompt-0001"
OTHER_ID = "someone-elses-prompt-9"

BASE_IMAGE = (
    "runs/architectos_product_integration_v3/p3a_transfer_output.png"
)

GIB = 1024 ** 3


# ==========================================================
# SIMULATED COMFYUI TRANSPORT
# ==========================================================

class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class SimState:
    """Deterministic queue/job state for one test."""

    def __init__(self):
        self.running = []          # prompt ids currently executing
        self.pending = []          # prompt ids queued
        self.queue_mode = "ok"     # ok | http500 | raise | malformed | nondict
        self.cancel_mode = "remove"  # remove | noop | http500 | raise | nocancel
        self.history = {}
        self.images = []
        self.error = None

        # recorded traffic
        self.cancel_urls = []
        self.post_bodies = []
        self.get_urls = []

    def queue_payload(self):
        return {
            "queue_running": [[0, pid] for pid in self.running],
            "queue_pending": [[1, pid] for pid in self.pending],
        }

    def active(self, pid):
        return pid in self.running or pid in self.pending

    def drop(self, pid):
        if pid in self.running:
            self.running.remove(pid)
        if pid in self.pending:
            self.pending.remove(pid)


class SimSession:
    """Requests-like transport bound to a `SimState`."""

    def __init__(self, state):
        self.state = state

    def get(self, url, timeout=None):
        self.state.get_urls.append(url)

        if url.endswith("/queue"):
            mode = self.state.queue_mode
            if mode == "raise":
                raise ConnectionError("simulated queue unreachable")
            if mode == "http500":
                return _Response(500, {"error": "boom"})
            if mode == "malformed":
                return _Response(200, {"queue_running": "nope"})
            if mode == "nondict":
                return _Response(200, ["not", "a", "dict"])
            return _Response(200, self.state.queue_payload())

        if "/history/" in url:
            return _Response(200, self.state.history)

        return _Response(404, {})

    def post(self, url, json=None, timeout=None):
        self.state.post_bodies.append(json)

        if "/api/jobs/" in url and url.endswith("/cancel"):
            self.state.cancel_urls.append(url)
            mode = self.state.cancel_mode
            if mode == "raise":
                raise ConnectionError("simulated cancel unreachable")
            if mode == "http500":
                return _Response(500, {"error": "boom"})

            pid = url.split("/api/jobs/")[1].split("/cancel")[0]

            if mode == "remove":
                self.state.drop(pid)
                return _Response(200, {"cancelled": True})

            if mode == "nocancel":
                # Job ended on its own before the cancel landed.
                self.state.drop(pid)
                return _Response(200, {"cancelled": False})

            # "noop": accepted but the job stays where it is.
            return _Response(200, {"cancelled": False})

        return _Response(200, {})


class SimComfy(ComfyHTTPRuntime):
    """Real lifecycle code, simulated transport, tiny wait budget."""

    def __init__(self, state, timeout=0.25, interval=0.05):
        super().__init__("http://sim.invalid")
        self.session = SimSession(state)
        self._wait_timeout = timeout
        self._wait_interval = interval
        self.state = state

    def submit(self, workflow):
        return {
            "status": "submitted",
            "prompt_id": PROMPT_ID,
            "http_status": 200,
            "time": 0.0,
        }

    def wait_for_result(self, prompt_id, timeout=None, interval=None):
        return super().wait_for_result(
            prompt_id,
            timeout=self._wait_timeout,
            interval=self._wait_interval,
        )

    # Output parsing is not the subject here; keep it deterministic.
    def extract_images(self, history):
        return list(self.state.images)

    def extract_videos(self, history):
        return []

    def detect_error(self, history):
        return self.state.error


# ==========================================================
# FIXTURES
# ==========================================================

@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """Isolated real lock namespace + no GPU, no Ollama, no ComfyUI."""

    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))

    # Bounded confirmation so "unconfirmed" tests do not wait 30 s.
    monkeypatch.setenv("ARCHITECTOS_COMFY_CANCEL_CONFIRM_TIMEOUT", "0.3")
    monkeypatch.setenv("ARCHITECTOS_COMFY_CANCEL_CONFIRM_INTERVAL", "0.05")

    def _h2(**kwargs):
        return {
            "status": "unloaded", "reason": None, "ownership": "exclusive",
            "loaded_before": [], "unloaded": [], "failed": [],
            "skipped_in_use": [],
            "vram_free_before": 16 * GIB, "vram_free_after": 16 * GIB,
        }

    monkeypatch.setattr(gh, "unload_ollama_models_for_render", _h2)
    return target


def _design(mode="img2img"):
    return {
        "prompt": "same tower, night",
        "original_prompt": "same tower, night",
        "mode": mode,
        "architectural_intent": {
            "building_type": "tower",
            "style": "modern",
            "materials": [],
            "levels": {"basement": 0, "ground": 1, "above_ground": 5,
                       "mezzanine": 0, "total": 5},
        },
        "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": [],
        "seed": 7,
    }


def _render(state, mode="img2img"):
    """Drive the real render path with the simulated ComfyUI transport."""

    runtime = RenderRuntime()
    executor = WorkflowExecutor()
    comfy = SimComfy(state)
    executor.comfy = comfy
    runtime.executor = executor

    result = runtime.render(
        "v43f",
        _design(mode),
        "flux",
        None if mode == "text2img" else {"path": BASE_IMAGE, "filename": "base.png"},
    )

    return runtime, executor, comfy, result


def _lease_free():
    """True when nothing holds the isolated gpu_render lease."""

    probe = gh.gpu_render_lease(wait=0)
    if probe.acquire():
        probe.release()
        return True
    return False


# ==========================================================
# 1 / 2 — TERMINAL STATES RELEASE THE LEASE
# ==========================================================

def test_completed_job_releases_the_lease(isolated):
    state = SimState()
    state.history = {"outputs": {"9": {}}}
    state.images = ["tower_0001.png"]

    runtime, executor, comfy, result = _render(state)

    assert result.get("status") != "gpu_handoff_orphaned"
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


def test_execution_error_releases_the_lease(isolated):
    state = SimState()
    state.error = ["execution_error", {"exception_message": "boom"}]

    runtime, executor, comfy, result = _render(state)

    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


# ==========================================================
# 3 / 4 — TARGETED CANCELLATION BY PROMPT ID
# ==========================================================

def test_pending_job_is_removed_by_its_specific_id(isolated):
    state = SimState()
    state.pending = [PROMPT_ID]

    runtime, executor, comfy, result = _render(state)

    assert comfy.state.cancel_urls == [
        "http://sim.invalid/api/jobs/%s/cancel" % PROMPT_ID
    ]
    assert PROMPT_ID not in state.pending
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


def test_running_job_is_interrupted_by_its_specific_id(isolated):
    state = SimState()
    state.running = [PROMPT_ID]

    runtime, executor, comfy, result = _render(state)

    assert comfy.state.cancel_urls == [
        "http://sim.invalid/api/jobs/%s/cancel" % PROMPT_ID
    ]
    assert PROMPT_ID not in state.running
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


# ==========================================================
# 5 / 8 — CANCELLATION NOT CONFIRMED RETAINS THE LEASE
# ==========================================================

def test_cancel_requested_but_completion_not_confirmed_retains_lease(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "noop"  # accepted, job keeps running

    runtime, executor, comfy, result = _render(state)

    assert result["status"] == "gpu_handoff_orphaned"
    assert result["reason"] == "job_state_unconfirmed"
    assert result["prompt_id"] == PROMPT_ID
    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False


def test_timeout_while_job_keeps_running_retains_lease(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "noop"

    runtime, executor, comfy, result = _render(state)

    assert runtime.last_gpu_handoff_render["status"] == "orphaned"
    assert runtime.last_gpu_handoff_render["prompt_id"] == PROMPT_ID
    assert _lease_free() is False


# ==========================================================
# 6 / 7 — UNREADABLE OR MALFORMED QUEUE IS NOT "IDLE"
# ==========================================================

@pytest.mark.parametrize("mode", ["http500", "raise", "malformed", "nondict"])
def test_unusable_queue_response_retains_lease(isolated, mode):
    state = SimState()
    state.queue_mode = mode

    runtime, executor, comfy, result = _render(state)

    assert result["status"] == "gpu_handoff_orphaned"
    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False
    # Nothing may be cancelled on the strength of an unreadable queue.
    assert state.cancel_urls == []


# ==========================================================
# 9 — RACE: JOB FINISHES BEFORE THE CANCEL LANDS
# ==========================================================

def test_job_finishing_before_cancel_is_released(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "nocancel"  # already terminal; cancel is a no-op

    runtime, executor, comfy, result = _render(state)

    assert comfy.state.cancel_urls  # a cancel was attempted
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True
    assert result.get("status") != "gpu_handoff_orphaned"


# ==========================================================
# 10 / 11 — TARGETING SAFEGUARDS
# ==========================================================

def test_cancellation_affects_only_the_intended_prompt(isolated):
    state = SimState()
    state.running = [PROMPT_ID, OTHER_ID]
    state.pending = [OTHER_ID]

    runtime, executor, comfy, result = _render(state)

    # Exactly one cancel, for our id only.
    assert len(state.cancel_urls) == 1
    assert PROMPT_ID in state.cancel_urls[0]
    assert OTHER_ID not in state.cancel_urls[0]

    # Our job is gone; the other job is untouched.
    assert PROMPT_ID not in state.running
    assert OTHER_ID in state.running
    assert OTHER_ID in state.pending


def test_no_global_interrupt_and_no_queue_wipe(isolated):
    state = SimState()
    state.running = [PROMPT_ID]

    runtime, executor, comfy, result = _render(state)

    urls = " ".join(state.cancel_urls)
    assert "/interrupt" not in urls
    assert urls.count("/api/jobs/") == 1

    # POST /queue would be a wipe/delete; it must never be used.
    for body in state.post_bodies:
        assert body is None or "clear" not in body
        assert body is None or "delete" not in body


# ==========================================================
# 12 / 13 / 14 — ORPHAN OWNERSHIP, BLOCKING AND RECOVERY
# ==========================================================

def test_orphaned_lease_blocks_concurrent_ollama(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "noop"

    runtime, executor, comfy, result = _render(state)
    assert runtime._orphaned_render_guard is not None

    with pytest.raises(gh.OllamaModelBusy):
        with gh.ollama_model_call("qwen3.8:27b", wait=0):
            pass


def test_subsequent_render_is_blocked_while_job_remains_active(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "noop"

    runtime, executor, comfy, result = _render(state)
    assert result["status"] == "gpu_handoff_orphaned"

    # Second render on the SAME runtime: the orphan gate must stop it before
    # any acquisition or submission.
    calls_before = len(comfy.state.cancel_urls)
    second = runtime.render(
        "v43f-2",
        _design("img2img"),
        "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert second["status"] == "gpu_handoff_orphaned"
    assert second["reason"] == "previous_job_state_unconfirmed"
    assert len(comfy.state.cancel_urls) == calls_before  # nothing new submitted
    assert _lease_free() is False


def test_lease_is_reacquirable_after_confirmed_termination(isolated):
    state = SimState()
    state.running = [PROMPT_ID]
    state.cancel_mode = "noop"

    runtime, executor, comfy, result = _render(state)
    assert runtime._orphaned_render_guard is not None
    assert _lease_free() is False

    # The job finally stops, and the queue is readable again.
    state.running = []

    assert runtime._recover_orphaned_render() is True
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True


# ==========================================================
# 15 — NORMAL PATH UNCHANGED
# ==========================================================

def test_normal_render_success_path_is_unchanged(isolated):
    state = SimState()
    state.history = {"outputs": {"9": {}}}
    state.images = ["tower_0001.png"]

    runtime, executor, comfy, result = _render(state)

    assert comfy.state.cancel_urls == []      # no cancel on a clean render
    assert runtime._orphaned_render_guard is None
    assert _lease_free() is True
    assert result.get("status") != "gpu_handoff_orphaned"


def test_successful_render_does_not_consult_the_queue(isolated):
    """The lifecycle additions must not add work to the happy path."""

    state = SimState()
    state.history = {"outputs": {"9": {}}}
    state.images = ["tower_0001.png"]

    runtime, executor, comfy, result = _render(state)

    assert all("/queue" not in u for u in state.get_urls)
