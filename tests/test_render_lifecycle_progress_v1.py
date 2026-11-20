"""REAL_RENDER_LIFECYCLE_V1 — Phase 2B focused acceptance.

Everything here runs against STUBBED ComfyUI evidence and the real Flask
routes. No ComfyUI job is submitted, no GPU work happens, no model loads.

Covered
  T1  prompt_id published BEFORE the blocking wait
  T2  correct project association
  T3  queued   from queue_pending evidence
  T4  executing from queue_running evidence
  T5  completed evidence -> "retrieving" (output NOT claimed complete)
  T6  failed / cancelled only from explicit evidence
  T7  missing job -> unknown (never completed, never cancelled)
  T8  a foreign project never receives the record
  T9  an older operation cannot clear/overwrite a newer one
  T10 callback cleanup + callback failure never breaks the render
  T11 unreadable queue -> unknown, not "idle"/completed
  T12 render result contract unchanged with and without the callback
"""

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as core_app                                    # noqa: E402
from core.render.workflow_executor import WorkflowExecutor  # noqa: E402
from core.render.render_runtime import RenderRuntime        # noqa: E402


PROMPT_ID = "ab4feeb2-b3d8-45d4-b31f-f547b2165b32"
PROJECT = "project_alpha"


class StubComfy:
    """Minimal stand-in for ComfyHTTPRuntime's read surface."""

    def __init__(self, running=None, pending=None, history=None, queue_ok=True):
        self.running = list(running or [])
        self.pending = list(pending or [])
        self.history_map = dict(history or {})
        self.queue_ok = queue_ok
        self.queue_calls = 0
        self.history_calls = 0

    def queue_state(self, timeout=None):
        self.queue_calls += 1
        return {"ok": self.queue_ok, "running": list(self.running),
                "pending": list(self.pending),
                "reason": None if self.queue_ok else "queue_unreachable:stub"}

    def history(self, prompt_id):
        self.history_calls += 1
        # Real ComfyUI `/history/{id}` returns a dict KEYED BY the prompt id.
        if prompt_id in self.history_map:
            return {prompt_id: self.history_map[prompt_id]}
        return {}


def _client():
    return core_app.app.test_client()


def _install(monkeypatch, comfy, record):
    runtime = core_app.chat.render_runtime
    monkeypatch.setattr(runtime, "active_render", record, raising=False)
    monkeypatch.setattr(runtime.executor, "comfy", comfy, raising=False)
    return runtime


def _status(project=PROJECT):
    response = _client().get("/api/render/status",
                             query_string={"project_id": project})
    return response.status_code, response.get_json()


def _record(project=PROJECT, generation=1):
    return {"prompt_id": PROMPT_ID, "project_id": project,
            "generation": generation, "engine": "flux",
            "workflow": "flux_img2img.json", "submitted_at": 0.0}


# ----------------------------------------------------------------- T1 / T10
class RecordingComfy:
    def __init__(self, fail_callback=False):
        self.events = []
        self.fail_callback = fail_callback

    def submit(self, workflow, client_id=None):
        self.events.append(("submit", client_id))
        # The executor accepts only None or "submitted" here.
        return {"prompt_id": PROMPT_ID, "status": "submitted", "http_status": 200}

    def wait_for_result(self, prompt_id):
        self.events.append(("wait_for_result", prompt_id))
        return {"status": "success", "outputs": {}, "prompt_id": prompt_id}


def test_t1_prompt_id_published_before_blocking_wait():
    comfy = RecordingComfy()
    executor = WorkflowExecutor()
    executor.comfy = comfy

    seen = []
    executor.execute({"1": {"class_type": "X"}}, "comfyui",
                     on_submitted=lambda pid: seen.append((pid, list(comfy.events))))

    assert seen == [(PROMPT_ID, [("submit", None)])], seen
    assert ("wait_for_result", PROMPT_ID) in comfy.events


def test_t10_callback_failure_never_breaks_the_render():
    comfy = RecordingComfy()
    executor = WorkflowExecutor()
    executor.comfy = comfy

    def boom(_pid):
        raise RuntimeError("progress feature exploded")

    result = executor.execute({"1": {"class_type": "X"}}, "comfyui",
                              on_submitted=boom)

    assert isinstance(result, dict)
    assert ("wait_for_result", PROMPT_ID) in comfy.events


def test_t12_result_contract_unchanged_without_callback():
    plain = WorkflowExecutor()
    plain.comfy = RecordingComfy()
    with_cb = WorkflowExecutor()
    with_cb.comfy = RecordingComfy()

    a = plain.execute({"1": {"class_type": "X"}}, "comfyui")
    b = with_cb.execute({"1": {"class_type": "X"}}, "comfyui",
                        on_submitted=lambda pid: None)

    assert isinstance(a, dict) and isinstance(b, dict)
    assert set(a.keys()) == set(b.keys())


# ----------------------------------------------------------------- T9 / T11
def test_t9_older_operation_cannot_clear_newer_record():
    runtime = object.__new__(RenderRuntime)
    runtime.active_render = _record(generation=2)
    runtime._render_generation = 2

    assert runtime._clear_active_render(1) is False
    assert runtime.active_render is not None
    assert runtime.active_render["generation"] == 2

    assert runtime._clear_active_render(2) is True
    assert runtime.active_render is None


def test_t11_cleared_record_leaves_no_stale_state():
    runtime = object.__new__(RenderRuntime)
    runtime.active_render = _record(generation=7)
    runtime._render_generation = 7

    assert runtime._clear_active_render(7) is True
    assert runtime.active_render is None
    # clearing twice is a no-op, never an error
    assert runtime._clear_active_render(7) is False


# ------------------------------------------------------------- status endpoint
def test_t2_correct_project_association(monkeypatch):
    _install(monkeypatch, StubComfy(running=[PROMPT_ID]), _record())

    code, body = _status(PROJECT)

    assert code == 200
    assert body["active"] is True
    assert body["prompt_id"] == PROMPT_ID
    assert body["project_id"] == PROJECT
    assert body["generation"] == 1


def test_t8_foreign_project_never_receives_the_record(monkeypatch):
    _install(monkeypatch, StubComfy(running=[PROMPT_ID]), _record(PROJECT))

    code, body = _status("project_bravo")

    assert code == 200
    assert body["active"] is False
    assert body["status"] == "inactive"
    assert "prompt_id" not in body


def test_t3_queued_from_queue_pending(monkeypatch):
    _install(monkeypatch, StubComfy(pending=[PROMPT_ID]), _record())

    _, body = _status()

    assert body["stage"] == "queued"
    assert body["evidence"] == "queue_pending"


def test_t4_executing_from_queue_running(monkeypatch):
    _install(monkeypatch, StubComfy(running=[PROMPT_ID]), _record())

    _, body = _status()

    assert body["stage"] == "executing"
    assert body["evidence"] == "queue_running"


def test_t5_completed_history_is_retrieving_not_completed(monkeypatch):
    comfy = StubComfy(history={PROMPT_ID: {
        "status": {"completed": True, "status_str": "success"},
        "outputs": {"9": {"images": [{"filename": "x.png"}]}},
    }})
    _install(monkeypatch, comfy, _record())

    _, body = _status()

    # ComfyUI finished, but THIS request has not returned the result yet.
    assert body["stage"] == "retrieving"
    assert body["evidence"] == "history_completed"


def test_t6a_failed_only_from_explicit_error(monkeypatch):
    comfy = StubComfy(history={PROMPT_ID: {
        "status": {"completed": False, "status_str": "error",
                   "messages": [["execution_error", {"node": "9"}]]},
    }})
    _install(monkeypatch, comfy, _record())

    _, body = _status()

    assert body["stage"] == "failed"
    assert body["evidence"] == "history_status_error"


def test_t6b_cancelled_only_from_explicit_interrupt(monkeypatch):
    comfy = StubComfy(history={PROMPT_ID: {
        "status": {"completed": False, "status_str": "error",
                   "messages": [["execution_interrupted", {}]]},
    }})
    _install(monkeypatch, comfy, _record())

    _, body = _status()

    assert body["stage"] == "cancelled"
    assert body["evidence"] == "history_execution_interrupted"


def test_t7_missing_job_is_unknown(monkeypatch):
    _install(monkeypatch, StubComfy(), _record())

    _, body = _status()

    assert body["stage"] == "unknown"
    assert body["evidence"] == "not_in_queue_or_history"


def test_t11b_unreadable_queue_is_unknown_not_idle(monkeypatch):
    _install(monkeypatch, StubComfy(queue_ok=False), _record())

    _, body = _status()

    assert body["stage"] == "unknown"
    assert body["evidence"] == "queue_unreadable"


def test_no_record_is_inactive(monkeypatch):
    _install(monkeypatch, StubComfy(), None)

    code, body = _status()

    assert code == 200
    assert body["active"] is False
    assert body["status"] == "inactive"


def test_project_id_is_required(monkeypatch):
    _install(monkeypatch, StubComfy(), None)

    response = _client().get("/api/render/status")

    assert response.status_code == 400
    assert response.get_json()["error"] == "project_required"


def test_status_endpoint_never_mutates(monkeypatch):
    record = _record()
    runtime = _install(monkeypatch, StubComfy(running=[PROMPT_ID]), record)

    before = dict(record)
    _status()
    _status()

    assert runtime.active_render == before
