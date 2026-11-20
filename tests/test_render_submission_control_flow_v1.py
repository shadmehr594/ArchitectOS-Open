"""EXECUTOR_CONTROL_FLOW_RECOVERY_V3 — submission reachability guard.

WHY THIS FILE EXISTS
====================
The B+ diff wrapped the WebSocket listener setup in a `try`, then wrote
the `_publish_submitted` callback and the `executor.execute(...)` call
INSIDE the listener's `except Exception` handler. `execution` was
therefore assigned on exactly one line — a line that only runs when the
listener setup FAILS.

On the normal path the handler never executed, so the first read of
`execution` (``print("🔥 WORKFLOW EXECUTION RESULT:", execution)``) raised
``UnboundLocalError: cannot access local variable 'execution'`` and no
render could ever be submitted. Live acceptance V2 observed exactly that.

Why the existing suites were blind to it: they mock
``RenderRuntime.render`` or mock ``executor.execute`` and assert it was
called. With the method mocked, "the executor was never called" is not
observable, and an `inspect.getsource` substring check finds the call
textually present — inside the dead handler.

WHAT THIS FILE DOES INSTEAD
===========================
It calls the REAL ``RenderRuntime.render()`` and lets it run all ~2000
lines up to and including submission. Only EXTERNAL collaborators are
substituted, at their real seams:

  * ``core.runtime.gpu_handoff_v1.gpu_render_lease`` / H2 / VRAM probe
    (no GPU may be touched — and ``render()`` imports these lazily, so
    patching the source module is the correct seam),
  * ``self.executor`` — an INSTRUMENTED stub that records the call and
    invokes ``on_submitted`` exactly as ``WorkflowExecutor`` does,
  * ``self.result_bridge`` — post-submission asset resolution only,
  * outbound sockets, refused outright.

Everything the defect touched is real: the try/except nesting, the
``_publish_submitted`` closure, ``_publish_active_render``, the
generation guard, the lease release and the listener cleanup.

NO GPU. NO ComfyUI SUBMISSION. NO Ollama LOAD. NO NETWORK.
"""

import contextlib
import io
import os
import socket
import sys

import flask
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import core.runtime.gpu_handoff_v1 as gpu_handoff  # noqa: E402
from core.render import render_runtime as rr_module  # noqa: E402
from core.render.comfy_ws_listener import SAMPLER_NODE_TYPES  # noqa: E402
from core.render.render_runtime import RenderRuntime  # noqa: E402


PROMPT_ID = "control-flow-prompt-1"
PROJECT_ID = "control-flow-project"


class NetworkForbidden(RuntimeError):
    """Raised if the render tries to reach the network."""


# ======================================================
# SUBSTITUTED SEAMS — external I/O only
# ======================================================


class FakeGuard:
    """Stands in for the protected GPU render lease."""

    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self):
        self.acquired += 1
        return True

    def release(self):
        self.released += 1

    def stats(self):
        return {"acquired": self.acquired, "released": self.released}


class FakeListener:
    """Stands in for ComfyProgressListener.

    Records lifecycle calls into a shared log so ORDERING is assertable.
    """

    instances = []
    start_result = True
    raises = None
    log_sink = None

    def __init__(self, url, prompt_id="", client_id=None, sampler_node_ids=frozenset()):
        if FakeListener.raises is not None:
            raise FakeListener.raises

        self.url = url
        self.prompt_id = prompt_id
        self.client_id = client_id
        self.sampler_node_ids = frozenset(sampler_node_ids)
        self.bound = []
        self.stops = 0
        self.started = 0
        # The instance is built inside render(), so the sink must be a
        # class attribute set BEFORE the call, not an instance attribute.
        self.log = FakeListener.log_sink
        FakeListener.instances.append(self)

    def _record(self, entry):
        if self.log is not None:
            self.log.append(entry)

    def start(self):
        self.started += 1
        self._record("listener.start")
        return FakeListener.start_result

    def stop(self):
        self.stops += 1
        self._record("listener.stop")
        return True

    def bind_prompt_id(self, prompt_id):
        self.bound.append(prompt_id)
        self._record("listener.bind:%s" % (prompt_id,))

    def stats(self):
        return {"last_error": "fake listener never connected", "connected": False}


class RecordingExecutor:
    """Instrumented executor.

    Mirrors `WorkflowExecutor.execute(..., on_submitted=, client_id=)`:
    it invokes `on_submitted(prompt_id)` after a valid prompt id and
    before returning, which is where the render binds the listener and
    publishes the active record.
    """

    def __init__(self, endpoint=None, log=None, raises=None, probe=None):
        self.comfy = _ComfyEndpoint(endpoint)
        self.calls = []
        self.raises = raises
        self.probe = probe
        self.log = log if log is not None else []

    def execute(self, workflow, engine, on_submitted=None, client_id=None):
        self.calls.append(
            {
                "workflow": workflow,
                "engine": engine,
                "client_id": client_id,
                "has_callback": on_submitted is not None,
            }
        )
        self.log.append("executor.execute")

        if self.raises is not None:
            raise self.raises

        if on_submitted is not None:
            on_submitted(PROMPT_ID)

        if self.probe is not None:
            self.probe()

        return {
            "status": "completed",
            "prompt_id": PROMPT_ID,
            "images": [],
        }


class _ComfyEndpoint:
    """Only the attributes `render()` reads off `executor.comfy`.

    Deliberately has no `queue_state`, so `_comfy_lifecycle()` reports
    "no lifecycle channel" and the lease-retention logic is not silently
    driven by a fake queue.
    """

    def __init__(self, endpoint):
        self.endpoint = endpoint


class StubBridge:
    """Post-submission asset resolution only; never reached by the defect."""

    def resolve(self, context):
        return {"image_asset": None, "status": "ok", "stub": True}


H2_OK = {
    "status": "not_running",
    "reason": "no_ollama_service",
    "ownership": None,
    "unloaded": [],
    "skipped_in_use": [],
}

VRAM_OK = {
    "ok": True,
    "reason": "sufficient_free_vram",
    "free_mib": 16000,
    "min_free_mib": 11264,
    "measurement_source": "test_stub",
}


# ======================================================
# FIXTURES
# ======================================================


@pytest.fixture(scope="module")
def runtime():
    """One REAL instance; construction is not free and is not under test here."""
    with contextlib.redirect_stdout(io.StringIO()):
        return RenderRuntime()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Refuse every outbound connection for the whole module."""

    def _blocked(*args, **kwargs):
        target = args[0] if args else None
        raise NetworkForbidden("outbound connection refused: %r" % (target,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture
def gpu_seams(monkeypatch):
    """No GPU: lease, H2 and the VRAM probe are all substituted."""
    guard = FakeGuard()
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", lambda *a, **kw: guard)
    monkeypatch.setattr(
        gpu_handoff, "unload_ollama_models_for_render", lambda *a, **kw: dict(H2_OK)
    )
    monkeypatch.setattr(
        gpu_handoff, "require_render_vram", lambda *a, **kw: dict(VRAM_OK)
    )
    return guard


@pytest.fixture
def listener_class(monkeypatch):
    """Reset and install the fake listener for one test."""
    FakeListener.instances = []
    FakeListener.start_result = True
    FakeListener.raises = None
    FakeListener.log_sink = None
    monkeypatch.setattr(rr_module, "ComfyProgressListener", FakeListener)
    return FakeListener


@pytest.fixture
def published(runtime, monkeypatch):
    """Record every active-render publication, without replacing the logic."""
    records = []
    original = runtime._publish_active_render

    def _recorder(record):
        records.append(dict(record))
        return original(record)

    monkeypatch.setattr(runtime, "_publish_active_render", _recorder)
    return records


def _design():
    """A fresh design payload per call: render() mutates it in place."""
    return {
        "prompt": "a two storey red brick house with a pitched roof",
        "mode": "text2img",
        "architectural_intent": {
            "building_type": "house",
            "style": "traditional",
            "floors": 2,
            "materials": ["red_brick"],
        },
    }


def _run_render(runtime, executor, owner=PROJECT_ID):
    """Run the real render() inside a request-scoped ownership context."""
    app = flask.Flask("control_flow_harness")
    out = io.StringIO()
    generation_before = runtime._render_generation

    with app.app_context():
        if owner is not None:
            flask.g.project_id = owner

        with contextlib.redirect_stdout(out):
            result = runtime.render(
                project_id=owner or "chat_project",
                design=_design(),
                engine="flux",
            )

    return result, out.getvalue(), generation_before


# ======================================================
# S0 — the harness itself is honest
# ======================================================


def test_network_guard_is_actually_armed():
    """If this fails, every "no network" claim in this file is void."""
    with pytest.raises(NetworkForbidden):
        socket.create_connection(("127.0.0.1", 8188), timeout=0.2)


# ======================================================
# S1 — happy path, no listener: submission MUST be reached
# ======================================================


def test_happy_path_reaches_executor_submission(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    """The exact defect: pre-fix this raised UnboundLocalError before submit."""
    executor = RecordingExecutor(endpoint=None)
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    result, out, generation_before = _run_render(runtime, executor)

    assert len(executor.calls) == 1, "render() did not submit exactly once"
    assert executor.calls[0]["has_callback"] is True
    assert isinstance(executor.calls[0]["client_id"], str)
    assert executor.calls[0]["client_id"], "client_id must not be empty"

    assert "🔥 WORKFLOW EXECUTION RESULT" in out

    assert len(published) == 1, "active render record was not published"
    record = published[0]
    assert record["prompt_id"] == PROMPT_ID
    assert record["project_id"] == PROJECT_ID
    assert record["generation"] == generation_before + 1
    assert record["engine"] == "flux"
    assert record["workflow"] == result["workflow"]
    assert record["client_id"] == executor.calls[0]["client_id"]
    assert isinstance(record["sampler_node_ids"], list)

    assert result["status"] == "ok"
    assert result["execution"]["prompt_id"] == PROMPT_ID

    assert runtime.active_render is None
    assert runtime._progress_listener is None
    assert gpu_seams.acquired == 1
    assert gpu_seams.released == 1


# ======================================================
# S2 — listener setup RAISES: telemetry failure must be nonfatal
# ======================================================


def test_listener_setup_exception_does_not_skip_submission(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    listener_class.raises = RuntimeError("listener construction exploded")
    executor = RecordingExecutor(endpoint="http://127.0.0.1:8188")
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    result, out, _ = _run_render(runtime, executor)

    assert "SAMPLING PROGRESS SETUP FAILED" in out
    assert "listener construction exploded" in out

    assert len(executor.calls) == 1, "a telemetry failure must not skip submission"
    assert len(published) == 1
    assert published[0]["prompt_id"] == PROMPT_ID
    assert result["status"] == "ok"

    assert runtime._progress_listener is None
    assert runtime.active_render is None
    assert gpu_seams.released == 1


# ======================================================
# S3 — listener handshake FAILS: honest fallback, still submits
# ======================================================


def test_listener_handshake_failure_does_not_skip_submission(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    listener_class.start_result = False
    executor = RecordingExecutor(endpoint="http://127.0.0.1:8188")
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    result, out, _ = _run_render(runtime, executor)

    assert "SAMPLING PROGRESS UNAVAILABLE" in out
    assert len(executor.calls) == 1

    assert len(listener_class.instances) == 1
    failed = listener_class.instances[0]
    assert failed.started == 1
    assert failed.stops == 1, "the failed listener must be stopped exactly once"
    assert failed.bound == [], "an unstarted listener must never be bound"

    assert len(published) == 1
    assert runtime._progress_listener is None
    assert result["status"] == "ok"


# ======================================================
# S4 — happy path WITH listener: order, binding, cleanup
# ======================================================


def test_listener_is_started_before_submit_bound_and_stopped(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    log = []
    seen_progress_listener = []
    listener_class.log_sink = log

    executor = RecordingExecutor(
        endpoint="http://127.0.0.1:8188",
        log=log,
        probe=lambda: seen_progress_listener.append(runtime._progress_listener),
    )
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    result, _, _ = _run_render(runtime, executor)

    assert len(listener_class.instances) == 1
    listener = listener_class.instances[0]

    assert log == [
        "listener.start",
        "executor.execute",
        "listener.bind:%s" % PROMPT_ID,
        "listener.stop",
    ], "listener lifecycle order changed: %r" % (log,)

    assert listener.bound == [PROMPT_ID]
    assert seen_progress_listener == [listener], (
        "the listener must be exposed on the runtime while the job is live"
    )
    assert runtime._progress_listener is None, "listener must be cleared on exit"

    # The published sampler ids must be derived from the SUBMITTED graph,
    # not guessed. Cross-check against the workflow the executor received.
    workflow = executor.calls[0]["workflow"]
    assert isinstance(workflow, dict) and workflow
    assert set(published[0]["sampler_node_ids"]) == set(listener.sampler_node_ids)
    assert published[0]["sampler_node_ids"], "no sampler node was identified"
    for node_id in published[0]["sampler_node_ids"]:
        assert node_id in workflow
        assert workflow[node_id]["class_type"] in SAMPLER_NODE_TYPES

    assert result["status"] == "ok"
    assert gpu_seams.released == 1


# ======================================================
# S5 — executor RAISES: propagate, release, no false success
# ======================================================


def test_executor_exception_propagates_and_cleans_up(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    log = []
    executor = RecordingExecutor(
        endpoint="http://127.0.0.1:8188",
        log=log,
        raises=RuntimeError("comfyui submit rejected"),
    )
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    with pytest.raises(RuntimeError) as excinfo:
        _run_render(runtime, executor)

    assert "comfyui submit rejected" in str(excinfo.value)

    assert len(executor.calls) == 1
    assert published == [], "a failed submission must not publish a live record"
    assert runtime.active_render is None
    assert runtime._progress_listener is None

    listener = listener_class.instances[0]
    assert listener.stops == 1, "the listener must be stopped on the exception path"

    assert gpu_seams.acquired == 1
    assert gpu_seams.released == 1, "the lease must not be leaked on a raise"
    assert runtime._orphaned_render_guard is None


# ======================================================
# S6 — unowned render: submits, publishes nothing
# ======================================================


def test_unowned_render_still_submits_but_publishes_nothing(
    runtime, gpu_seams, listener_class, published, monkeypatch
):
    executor = RecordingExecutor(endpoint="http://127.0.0.1:8188")
    monkeypatch.setattr(runtime, "executor", executor)
    monkeypatch.setattr(runtime, "result_bridge", StubBridge())

    result, _, _ = _run_render(runtime, executor, owner=None)

    assert len(executor.calls) == 1, "ownership must not gate submission"
    assert published == [], "an unowned render must never publish a record"
    assert runtime.active_render is None
    assert listener_class.instances == [], (
        "no socket is opened when no record can be published"
    )
    assert result["status"] == "ok"
    assert gpu_seams.released == 1



# [ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
try:
    from flask import request as _arch_req, jsonify as _arch_jsonify

    def _resolve_arch_repo_root() -> str:
        import os
        import sys
        here_d = os.path.dirname(os.path.abspath(__file__))
        cand = here_d
        for _ in range(5):
            if os.path.isdir(os.path.join(cand, "core")) and os.path.isdir(os.path.join(cand, "ui")):
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                return cand
            parent = os.path.dirname(cand)
            if parent == cand:
                break
            cand = parent
        if here_d not in sys.path:
            sys.path.insert(0, here_d)
        from core.site.krocki_cad_reader_v27 import _resolve_true_repo_root
        root_r = _resolve_true_repo_root(here_d)
        if root_r not in sys.path:
            sys.path.insert(0, root_r)
        return root_r

    def _sync_project_renders_and_assets(repo_root: str, project_id: str) -> None:
        import os
        import shutil
        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        dir_a = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        dir_b = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        for src_d, dst_d in ((dir_a, dir_b), (dir_b, dir_a)):
            try:
                for fn in os.listdir(src_d):
                    if fn.endswith((".png", ".svg", ".dxf", ".json", ".jpg")):
                        sp = os.path.join(src_d, fn)
                        dp = os.path.join(dst_d, fn)
                        if os.path.isfile(sp) and (not os.path.isfile(dp) or os.path.getmtime(sp) > os.path.getmtime(dp) + 0.5):
                            shutil.copy2(sp, dp)
            except Exception:
                pass

    def _sync_krocki_into_project_session(repo_root: str, project_id: str) -> None:
        import json
        import os
        from core.site.krocki_cad_reader_v27 import (
            load_active_krocki_state,
            load_active_external_plan_state,
        )

        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(krocki, dict) and not isinstance(ext_plan, dict):
            return
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        for state_file in (
            os.path.join(repo_root, "data", "projects", p_folder, "session_state.json"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json"),
        ):
            state_data = {}
            if os.path.isfile(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                except Exception:
                    state_data = {}
            if isinstance(krocki, dict):
                state_data["active_site_krocki"] = krocki
                prev_p = state_data.get("active_plan_params")
                if isinstance(prev_p, dict):
                    prev_p["site_width_mm"] = int(round(float(krocki.get("width_m", 10.0)) * 1000))
                    prev_p["site_length_mm"] = int(round(float(krocki.get("length_m", 20.0)) * 1000))
                    prev_p["site_area_m2"] = round(float(krocki.get("site_area_m2", 200.0)), 2)
                    prev_p["krocki_polygon_mm"] = krocki.get("polygon_vertices_mm") or []
                    prev_p["krocki_source_file"] = krocki.get("source_file")
                    prev_p["krocki_is_irregular"] = bool(krocki.get("is_irregular_polygon", False))
                    prev_p["street_sides"] = krocki.get("street_sides") or ["SOUTH"]
                    prev_p["party_wall_sides"] = krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
                    prev_p["boundary_neighbors"] = krocki.get("boundary_neighbors") or {}
                    prev_p["south_y_west_mm"] = int(krocki.get("south_y_west_mm", 0))
                    prev_p["south_y_east_mm"] = int(krocki.get("south_y_east_mm", 0))
                    prev_p["north_y_west_mm"] = int(krocki.get("north_y_west_mm", prev_p["site_length_mm"]))
                    prev_p["north_y_east_mm"] = int(krocki.get("north_y_east_mm", prev_p["site_length_mm"]))
            if isinstance(ext_plan, dict):
                state_data["active_external_plan"] = ext_plan
                prev_p = state_data.get("active_plan_params")
                if not isinstance(prev_p, dict):
                    prev_p = {}
                    state_data["active_plan_params"] = prev_p
                tot_fl = int(ext_plan.get("total_floors", 2))
                typ_str = str(ext_plan.get("typology", "DUPLEX_2FLOOR" if tot_fl == 2 else ("MULTIFLOOR_RESIDENTIAL" if tot_fl >= 3 else "VILLA_1FLOOR")))
                prev_p["typology"] = typ_str
                prev_p["is_duplex"] = (typ_str == "DUPLEX_2FLOOR")
                prev_p["floor_count"] = max(2, tot_fl - 1) if typ_str == "MULTIFLOOR_RESIDENTIAL" else tot_fl
                prev_p["building_placement"] = str(ext_plan.get("building_placement") or ("SOUTH" if ext_plan.get("custom_facade_profile") else "NORTH"))
                prev_p["site_width_mm"] = int(round(float(ext_plan.get("width_m", 10.0)) * 1000))
                prev_p["site_length_mm"] = int(round(float(ext_plan.get("length_m", 20.0)) * 1000))
                prev_p["coverage_ratio"] = float(ext_plan.get("coverage_ratio", 0.60 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 0.65))
                prev_p["south_cantilever_mm"] = int(round(float(ext_plan.get("cantilever_m", 1.2 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 1.0)) * 1000))
                if ext_plan.get("universal_facade_spec"):
                    prev_p["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                if ext_plan.get("custom_facade_profile"):
                    prev_p["custom_facade_profile"] = ext_plan["custom_facade_profile"]
                else:
                    prev_p.pop("custom_facade_profile", None)
                for _rs_d in (prev_p.get("active_render_state"), state_data.get("active_render_state")):
                    if isinstance(_rs_d, dict):
                        if ext_plan.get("universal_facade_spec"):
                            _rs_d["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                        if ext_plan.get("custom_facade_profile"):
                            _rs_d["custom_facade_profile"] = ext_plan["custom_facade_profile"]
            try:
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state_data, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _is_3d_facade_render_chat_command(text: str, prev_params: dict = None) -> bool:
        from core.planning.multifloor_v1.engine.nl_design_parser import is_3d_render_or_render_edit_prompt
        return is_3d_render_or_render_edit_prompt(text or "", prev_params)

    def _handle_plan_locked_3d_render_request(jbody: dict):
        import base64
        import json
        import os
        import shutil
        import uuid
        from core.site.krocki_cad_reader_v27 import load_active_krocki_state
        from core.planning.multifloor_v1.engine.nl_design_parser import (
            parse_architectural_prompt,
            update_geometry_locked_render_state,
        )
        from core.planning.multifloor_v1.engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from core.planning.multifloor_v1.engine.comfyui_bridge import ComfyUIRenderBridge

        repo_root = _resolve_arch_repo_root()
        user_msg = str(jbody.get("message") or jbody.get("prompt") or jbody.get("text") or "").strip()
        raw_q = str(
            jbody.get("quality")
            or jbody.get("render_quality")
            or jbody.get("preset")
            or jbody.get("quality_preset")
            or _arch_req.args.get("quality")
            or "draft"
        ).strip().lower()
        if any(w in user_msg.lower() for w in ("کیفیت بالا", "نهایی", "high", "final", "ultra")):
            quality = "high"
        elif any(w in user_msg.lower() for w in ("سریع", "درفت", "تست", "draft", "fast", "preview")):
            quality = "draft"
        elif raw_q in ("auto", ""):
            quality = "draft"
        else:
            quality = raw_q
        clean_pid = str(jbody.get("project_id") or _arch_req.args.get("project_id") or "default").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        _sync_krocki_into_project_session(repo_root, clean_pid)

        st_path_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json")
        st_path_data = os.path.join(repo_root, "data", "projects", p_folder, "session_state.json")
        plan_params = None
        full_state_obj = {}
        for st_path in (st_path_plans, st_path_data):
            if os.path.isfile(st_path):
                try:
                    with open(st_path, "r", encoding="utf-8") as sf:
                        st_obj = json.load(sf)
                    if isinstance(st_obj.get("active_plan_params"), dict):
                        full_state_obj = dict(st_obj)
                        plan_params = dict(st_obj["active_plan_params"])
                        break
                except Exception:
                    pass

        from core.site.krocki_cad_reader_v27 import load_active_external_plan_state
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan_now = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(plan_params, dict):
            plan_params = parse_architectural_prompt(user_msg, active_site_krocki=krocki)
        if isinstance(ext_plan_now, dict) and ext_plan_now.get("total_floors"):
            _tot_e = int(ext_plan_now.get("total_floors", 1))
            _typ_e = str(ext_plan_now.get("typology", "MULTIFLOOR_RESIDENTIAL" if _tot_e >= 3 else ("DUPLEX_2FLOOR" if _tot_e == 2 else "VILLA_1FLOOR")))
            plan_params["typology"] = _typ_e
            plan_params["is_duplex"] = (_typ_e == "DUPLEX_2FLOOR")
            plan_params["floor_count"] = max(2, _tot_e - 1) if _typ_e == "MULTIFLOOR_RESIDENTIAL" else _tot_e
            plan_params["building_placement"] = str(ext_plan_now.get("building_placement") or "NORTH")
            plan_params["coverage_ratio"] = float(ext_plan_now.get("coverage_ratio", 0.65))
            if ext_plan_now.get("universal_facade_spec"):
                plan_params["universal_facade_spec"] = ext_plan_now["universal_facade_spec"]
            if ext_plan_now.get("custom_facade_profile"):
                plan_params["custom_facade_profile"] = ext_plan_now["custom_facade_profile"]
            else:
                plan_params.pop("custom_facade_profile", None)
        # Only self-heal stale DUPLEX_2FLOOR sessions if NO external plan (`ext_plan_now`) or `custom_facade_profile` is active!
        if (
            not isinstance(ext_plan_now, dict)
            and isinstance(plan_params, dict)
            and not plan_params.get("custom_facade_profile")
            and not plan_params.get("universal_facade_spec")
            and plan_params.get("typology") == "DUPLEX_2FLOOR"
            and "دوبلکس" not in str(plan_params.get("raw_prompt", ""))
            and "دوبلکس" not in user_msg
        ):
            plan_params["typology"] = "MULTIFLOOR_RESIDENTIAL"
            plan_params["is_duplex"] = False
            plan_params["floor_count"] = 2
            plan_params["building_placement"] = "NORTH"
            plan_params["coverage_ratio"] = 0.60
            plan_params["south_cantilever_mm"] = 1200
        if isinstance(krocki, dict):
            plan_params.setdefault("site_width_mm", int(round(float(krocki.get("width_m", 10.0)) * 1000)))
            plan_params.setdefault("site_length_mm", int(round(float(krocki.get("length_m", 20.0)) * 1000)))
            plan_params.setdefault("site_area_m2", round(float(krocki.get("site_area_m2", 200.0)), 2))
            plan_params.setdefault("krocki_polygon_mm", krocki.get("polygon_vertices_mm") or [])
            plan_params.setdefault("krocki_is_irregular", bool(krocki.get("is_irregular_polygon", False)))
            plan_params.setdefault("street_sides", krocki.get("street_sides") or ["SOUTH"])
            plan_params.setdefault("party_wall_sides", krocki.get("party_wall_sides") or ["WEST"])
            plan_params.setdefault("boundary_neighbors", krocki.get("boundary_neighbors") or {})
            plan_params.setdefault("south_y_west_mm", int(krocki.get("south_y_west_mm", 0)))
            plan_params.setdefault("south_y_east_mm", int(krocki.get("south_y_east_mm", 0)))

        # Update ONLY the geometry-locked render state while freezing 100% of plan_params geometry!
        prev_r_state = plan_params.get("active_render_state") or full_state_obj.get("active_render_state") or {}
        r_state = update_geometry_locked_render_state(prev_r_state, user_msg, plan_params)
        if plan_params.get("universal_facade_spec"):
            r_state["universal_facade_spec"] = plan_params["universal_facade_spec"]
        if plan_params.get("custom_facade_profile"):
            r_state["custom_facade_profile"] = plan_params["custom_facade_profile"]
        plan_params["active_render_state"] = r_state
        plan_params["render_facade_side"] = r_state["facade_side"]
        plan_params["facade_style_fa"] = r_state["style_label_fa"]
        plan_params["facade_material_fa"] = r_state["stone_label_fa"]
        plan_params["render_lighting_mode"] = r_state["lighting_mode"]

        synth = ParametricArchitecturalSynthesizer()
        project_res = synth.synthesize_from_params(plan_params)
        spec = ComfyUIRenderBridge.parse_render_request_from_chat("", prev_render_state=r_state, plan_params=plan_params)

        out_dir_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        out_dir_data = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(out_dir_plans, exist_ok=True)
        os.makedirs(out_dir_data, exist_ok=True)

        existing_renders = [fn for fn in os.listdir(out_dir_data) if fn.startswith("render_") and fn.endswith(".png") and not fn.endswith(("_depth.png", "_lineart.png"))]
        next_ord = len(existing_renders) + 1
        render_fn = f"render_{next_ord:03d}_{uuid.uuid4().hex[:6]}.png"
        scaffold_png_path = os.path.join(out_dir_data, render_fn)

        _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
            project_res,
            scaffold_png_path,
            chat_text="",
            quality=quality,
            prev_render_state=r_state,
        )

        # Persist updated active_render_state back to session_state.json so subsequent iterative edits stay locked!
        full_state_obj["active_plan_params"] = plan_params
        full_state_obj["active_render_state"] = r_state
        for st_p in (st_path_plans, st_path_data):
            try:
                os.makedirs(os.path.dirname(st_p), exist_ok=True)
                with open(st_p, "w", encoding="utf-8") as sf:
                    json.dump(full_state_obj, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        final_png_path = scaffold_png_path
        comfy_status = "PLAN_LOCKED_3D_RAYSHADED_V33"
        try:
            bridge = ComfyUIRenderBridge()
            c_res = bridge.render_via_comfyui(
                project_res,
                user_msg,
                controlnet_png_path=scaffold_png_path,
                output_dir=out_dir_data,
                timeout_sec=240 if quality in ("draft", "preview", "fast", "auto") else 1200,
                quality=quality,
            )
            if c_res.get("status") == "RENDERED_BY_COMFYUI" and c_res.get("render_png_path") and os.path.isfile(c_res["render_png_path"]):
                shutil.copy2(c_res["render_png_path"], scaffold_png_path)
                comfy_status = "COMFYUI_IMG2IMG_PLAN_LOCKED_V33"
        except Exception:
            pass

        plan_render_copy = os.path.join(out_dir_plans, render_fn)
        try:
            shutil.copy2(final_png_path, plan_render_copy)
        except Exception:
            pass
        _sync_project_renders_and_assets(repo_root, clean_pid)

        with open(final_png_path, "rb") as rf:
            b64_png = base64.b64encode(rf.read()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_png}"
        web_rel_url = f"/planning/drawing/{p_folder}/renders/{render_fn}"

        n_floors = len(project_res.floors)
        typ_fa = "ویلایی ۱ طبقه" if n_floors == 1 else (f"دوبلکس ۲ طبقه" if n_floors == 2 else f"{n_floors} طبقه (همکف/پیلوت + {n_floors-1} طبقه تیپ)")
        reply_fa = (
            f"🎨 **رندر سه‌بعدی {spec['facade_label_fa']} کاملاً مقید به پلان و بدون تغییر حجم آماده شد.**\n"
            f"🏛️ **تعداد طبقات و تیپ پلان:** {typ_fa} (`Seed قفل‌شده: {spec['locked_seed']}`)\n"
            f"✨ **سبک و متریال:** {spec['style_label_fa']}\n"
            f"💡 **نورپردازی:** {spec['time_label_fa']}\n"
            f"📁 **مسیر ذخیره روی هارد:** `{final_png_path}`\n"
            f"🖼️ **لینک دانلود مستقیم رندر:** {web_rel_url}"
        )

        asset_entry = {
            "id": f"asset_{uuid.uuid4().hex[:8]}",
            "name": f"Render #{next_ord} ({spec['facade_label_fa']} - {typ_fa})",
            "type": "plan_locked_3d_render",
            "ordinal": next_ord,
            "filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "url": data_uri,
            "image_url": data_uri,
            "preview_url": data_uri,
            "web_url": web_rel_url,
            "status": "completed",
            "active": True,
        }

        return _arch_jsonify({
            "status": "success",
            "ok": True,
            "success": True,
            "mode": "plan_locked_3d_render",
            "type": "plan_locked_3d_render",
            "intent": "render",
            "render_status": "completed",
            "render_engine": comfy_status,
            "project_id": p_folder,
            "reply": reply_fa,
            "assistant_text": reply_fa,
            "display_text": reply_fa,
            "ui_text": reply_fa,
            "bot_reply": reply_fa,
            "message": reply_fa,
            "text": reply_fa,
            "response": reply_fa,
            "content": reply_fa,
            "answer": reply_fa,
            "chat_reply": reply_fa,
            "output_text": reply_fa,
            "summary_fa": reply_fa,
            "messages": [
                {"role": "user", "text": user_msg, "content": user_msg},
                {"role": "assistant", "text": reply_fa, "content": reply_fa, "image_url": data_uri, "url": web_rel_url},
            ],
            "chat": {
                "reply": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "assistant_text": reply_fa,
                "image_url": data_uri,
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "reply": reply_fa,
                "image_url": data_uri,
            },
            "filename": render_fn,
            "original_filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "output_path": final_png_path,
            "image_path": final_png_path,
            "render_path": final_png_path,
            "file_path": final_png_path,
            "path": final_png_path,
            "dimensions": "1280 × 864",
            "width": 1280,
            "height": 864,
            "image_url": data_uri,
            "preview_url": data_uri,
            "render_url": data_uri,
            "svg_url": data_uri,
            "web_url": web_rel_url,
            "url": web_rel_url,
            "positive_prompt": prompt_en,
            "asset": asset_entry,
            "assets": [asset_entry],
            "renders": [asset_entry],
            "images": [final_png_path],
            "output_images": [final_png_path],
            "files": {
                "png": web_rel_url,
                "render_png": final_png_path,
                "image": final_png_path,
                "output_path": final_png_path,
            },
            "result": {
                "status": "success",
                "ok": True,
                "reply": reply_fa,
                "message": reply_fa,
                "text": reply_fa,
                "response": reply_fa,
                "output_path": final_png_path,
                "image_path": final_png_path,
                "saved_location": final_png_path,
                "filename": render_fn,
                "image_url": data_uri,
                "preview_url": data_uri,
                "asset": asset_entry,
            },
        }), 200

    def _handle_external_plan_upload_request():
        """
        v51.0 Universal External Plan, Multi-Floor Typical Plan (via Elevation Codes) & 2D Elevation/Section Upload Handler:
        Supports `.dwg`, `.dxf`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
        """
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_external_plan_or_elevation,
            save_active_external_plan_state,
            export_external_plan_preview_svg,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        user_hint = str(
            _arch_req.form.get("hint")
            or (_arch_req.get_json(silent=True) or {}).get("hint")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "external_plan.dwg"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("plan")
                or _arch_req.files.get("external_plan")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "external_plan.dwg")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg", ".3ds", ".rvt", ".ifc", ".obj", ".glb", ".gltf", ".fbx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    raw_ext = ".dwg"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "external_plan.png")
                raw_ext = os.path.splitext(orig_name)[1].lower() or ".png"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
                "message": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            ext_info = parse_external_plan_or_elevation(saved_path, user_hint=user_hint)
            ext_info["original_filename"] = orig_name
            save_active_external_plan_state(repo_root, clean_pid, ext_info, sync_global_default=True)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            # Also sync to the most recently active project_* directory so UI Chat and Studio always see the exact uploaded file!
            try:
                projs_root = os.path.join(repo_root, "data", "projects")
                if os.path.isdir(projs_root):
                    p_cands = []
                    for pn in os.listdir(projs_root):
                        pd = os.path.join(projs_root, pn)
                        if pn.startswith("project_") and pn not in ("project_default", "project_v337b_probe") and os.path.isdir(pd):
                            st_f = os.path.join(pd, "session_state.json")
                            mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                            p_cands.append((mt, pn))
                    p_cands.sort(key=lambda x: x[0], reverse=True)
                    for _, recent_pn in p_cands[:2]:
                        save_active_external_plan_state(repo_root, recent_pn, ext_info, sync_global_default=False)
                        _sync_krocki_into_project_session(repo_root, recent_pn)
            except Exception:
                pass
            svg_name = f"external_plan_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_external_plan_preview_svg(ext_info, svg_path)
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "external_plan_info": ext_info,
                "doc_type": ext_info["doc_type"],
                "doc_type_fa": ext_info["doc_type_fa"],
                "total_floors": ext_info["total_floors"],
                "floors_desc_fa": ext_info["floors_desc_fa"],
                "elevation_codes_m": ext_info["elevation_codes_m"],
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": ext_info["summary_fa"],
                "reply": (
                    f"📐 **{ext_info['summary_fa']}**\n"
                    f"🧱 **فایل‌های سه‌بعدی تولیدشده برای Blender و BIM**:\n"
                    f"- `GLB (Blender -> Import -> glTF 2.0)`: `{ext_info.get('glb_shell_path') or ''}`\n"
                    f"- `OBJ (Blender -> Import -> Wavefront .obj)`: `{ext_info.get('obj_shell_path') or ''}`\n"
                    f"- `IFC4 (SweptSolid 3D BIM)`: `{ext_info.get('ifc_shell_path') or ''}`\n"
                    f"✅ اکنون می‌توانید در چت بنویسید: «از نمای جنوبی با سبک نئوکلاسیک و سنگ تراورتن کرم رندر بگیر» یا «رندر شبش رو بگیر»."
                ),
                "message": ext_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل پلان/نمای خارجی: {exc}",
                "reply": f"⚠️ خطا در تحلیل پلان/نمای خارجی: {exc}",
            }), 200

    def _handle_krocki_upload_request():
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_krocki_dxf_or_dwg,
            export_krocki_preview_svg,
            save_active_krocki_state,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "krocki.dxf"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("krocki")
                or _arch_req.files.get("krocki_file")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dwg" if "dwg" in orig_name.lower() else ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل کروکی در درخواست ارسالی یافت نشد.",
                "message": "فایل کروکی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            krocki_info = parse_krocki_dxf_or_dwg(saved_path)
            krocki_info["original_filename"] = orig_name
            save_active_krocki_state(repo_root, clean_pid, krocki_info)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            svg_name = f"krocki_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_krocki_preview_svg(krocki_info, svg_path)
            export_krocki_preview_svg(krocki_info, os.path.join(renders_dir, "krocki_preview.svg"))
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "krocki_info": krocki_info,
                "krocki": krocki_info,
                "site": krocki_info,
                "width_m": krocki_info["width_m"],
                "length_m": krocki_info["length_m"],
                "site_area_m2": krocki_info["site_area_m2"],
                "area_m2": krocki_info["site_area_m2"],
                "vertex_count": krocki_info["vertex_count"],
                "is_irregular_polygon": krocki_info["is_irregular_polygon"],
                "street_sides": krocki_info.get("street_sides", ["SOUTH"]),
                "party_wall_sides": krocki_info.get("party_wall_sides", ["WEST"]),
                "boundary_neighbors": krocki_info.get("boundary_neighbors", {}),
                "boundary_labels_fa": krocki_info.get("boundary_labels_fa", {}),
                "south_y_west_mm": krocki_info.get("south_y_west_mm", 0),
                "south_y_east_mm": krocki_info.get("south_y_east_mm", 0),
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": krocki_info["summary_fa"],
                "reply": f"📐 {krocki_info['summary_fa']}\n✅ اکنون می‌توانید دستور طراحی پلان روی این زمین را در چت بنویسید.",
                "message": krocki_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل کروکی: {exc}",
                "reply": f"⚠️ خطا در تحلیل کروکی: {exc}",
            }), 200

    for _k_route in (
        "/api/site/upload_krocki",
        "/api/site/krocki",
        "/api/krocki",
        "/api/upload_krocki",
        "/api/site/upload",
    ):
        try:
            app.add_url_rule(
                _k_route,
                endpoint=f"archos_krocki_{_k_route.replace('/', '_')}",
                view_func=_handle_krocki_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    def _handle_latest_render_query():
        import base64
        import os
        repo_root = _resolve_arch_repo_root()
        pid = str(_arch_req.args.get("project_id") or "default").strip()
        if pid.lower() in ("", "null", "none", "undefined"):
            pid = "default"
        p_folder = pid if pid.startswith("project_") else f"project_{pid}"
        _sync_project_renders_and_assets(repo_root, pid)
        cands = []
        for r_dir in (
            os.path.join(repo_root, "data", "projects", p_folder, "renders"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "renders"),
            os.path.join(repo_root, "data", "projects", "project_default", "renders"),
        ):
            if os.path.isdir(r_dir):
                for fn in os.listdir(r_dir):
                    if fn.startswith("render_") and fn.endswith((".png", ".jpg")) and not fn.endswith(("_depth.png", "_lineart.png", "_comfy_input.png")) and "_comfy_" not in fn and "_depth_" not in fn:
                        fp = os.path.join(r_dir, fn)
                        cands.append((os.path.getmtime(fp), fp, fn))
        if not cands:
            return _arch_jsonify({"ok": False}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        _, latest_fp, latest_fn = cands[0]
        with open(latest_fp, "rb") as rf:
            b64 = base64.b64encode(rf.read()).decode("ascii")
        d_uri = f"data:image/png;base64,{b64}"
        return _arch_jsonify({
            "ok": True,
            "filename": latest_fn,
            "saved_location": latest_fp,
            "image_url": d_uri,
            "web_url": f"/planning/drawing/{p_folder}/renders/{latest_fn}",
        }), 200

    try:
        import os as _pid_os
        _pid_root = _resolve_arch_repo_root()
        _pid_dir = _pid_os.path.join(_pid_root, "logs", "runtime")
        _pid_os.makedirs(_pid_dir, exist_ok=True)
        _is_ui_srv = _pid_os.path.basename(_pid_os.path.dirname(_pid_os.path.abspath(__file__))).lower() == "ui"
        _pid_fn = _pid_os.path.join(_pid_dir, "ui.pid" if _is_ui_srv else "orchestrator.pid")
        with open(_pid_fn, "w", encoding="utf-8") as _pf:
            _pf.write(str(_pid_os.getpid()))
    except Exception:
        pass

    def _resolve_latest_active_ext_plan_json(repo_root: str, clean_pid: str):
        import json, os
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        cands_j = []
        for jp in (
            os.path.join(repo_root, "data", "projects", p_folder, "site", "active_external_plan.json"),
            os.path.join(repo_root, "data", "active_external_plan.json"),
            os.path.join(repo_root, "data", "projects", "project_default", "site", "active_external_plan.json"),
        ):
            if os.path.isfile(jp):
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    cands_j.append((float(d.get("uploaded_at_ts") or os.path.getmtime(jp)), d, os.path.dirname(jp)))
                except Exception:
                    pass
        if cands_j:
            cands_j.sort(key=lambda x: x[0], reverse=True)
            return cands_j[0][1], cands_j[0][2]
        return {}, os.path.join(repo_root, "data", "projects", p_folder, "site")

    def _handle_3d_scene_json_query():
        import json, os
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        sj_direct = str(act_d.get("scene_3d_json_path") or "")
        if sj_direct and os.path.isfile(sj_direct):
            with open(sj_direct, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            data["ok"] = True
            data["source_filename"] = act_d.get("original_filename") or os.path.basename(str(act_d.get("source_file") or ""))
            data["is_3d_model"] = bool(act_d.get("is_3d_model") or act_d.get("is_direct_3d_bim_import"))
            data["total_floors"] = int(act_d.get("total_floors") or 1)
            return _arch_jsonify(data), 200
        cands = []
        if os.path.isdir(site_dir):
            for fn in os.listdir(site_dir):
                if fn.endswith("_scene.json") and "1d49dd1a" not in fn:
                    fp = os.path.join(site_dir, fn)
                    cands.append((os.path.getmtime(fp), fp))
            if not cands:
                for fn in os.listdir(site_dir):
                    if fn.endswith("_scene.json"):
                        fp = os.path.join(site_dir, fn)
                        cands.append((os.path.getmtime(fp), fp))
        if not cands:
            return _arch_jsonify({"ok": False, "elements": []}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        with open(cands[0][1], "r", encoding="utf-8") as jf:
            data = json.load(jf)
        data["ok"] = True
        return _arch_jsonify(data), 200

    def _handle_cad_layers_api():
        import json, os
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        project_id = (_arch_req.args.get("project_id") if _arch_req.method == "GET" else (_arch_req.get_json(silent=True) or {}).get("project_id")) or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        cad_fp = str(act_d.get("vectorized_dxf_path") or act_d.get("source_file") or "")
        if not cad_fp or not os.path.isfile(cad_fp):
            cands_c = []
            if os.path.isdir(site_dir):
                for fn in os.listdir(site_dir):
                    if fn.lower().endswith((".dwg", ".dxf")) and not fn.lower().endswith(("_elevations_and_sections.dxf", "_normalized_layers.dxf")) and "1d49dd1a" not in fn:
                        fp = os.path.join(site_dir, fn)
                        cands_c.append((os.path.getmtime(fp), fp))
            if cands_c:
                cands_c.sort(key=lambda x: x[0], reverse=True)
                cad_fp = cands_c[0][1]
        overrides = {}
        apply_all_floors = True
        if _arch_req.method == "POST":
            body = _arch_req.get_json(silent=True) or {}
            overrides = body.get("layer_overrides") or {}
            apply_all_floors = bool(body.get("apply_all_floors", True))
        res = MultiStoryCAD3DShellExtruder.auto_normalize_and_rewrite_dxf_layers(
            cad_fp, user_layer_overrides=overrides, apply_all_floors=apply_all_floors
        )
        if act_d.get("original_filename"):
            res["source_filename"] = act_d["original_filename"]
        return _arch_jsonify(res), 200

    def _handle_download_bim_bundle():
        import os, zipfile, tempfile
        from flask import send_file as _arch_send_file
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        repo_root = _resolve_arch_repo_root()
        site_dir = os.path.join(repo_root, "data", "projects", p_folder, "site")
        z_tmp = os.path.join(tempfile.gettempdir(), f"{p_folder}_Revit_BIM_Bundle_v50.zip")
        with zipfile.ZipFile(z_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(site_dir):
                for fn in sorted(os.listdir(site_dir)):
                    if fn.endswith((".ifc", ".glb", ".obj", ".mtl", "_revit_journal.txt", "_build_revit_rvt.py", "_elevations_and_sections.dxf", "_normalized_layers.dxf")):
                        fp = os.path.join(site_dir, fn)
                        if os.path.isfile(fp):
                            zf.write(fp, arcname=fn)
        return _arch_send_file(z_tmp, as_attachment=True, download_name=f"{p_folder}_Revit_IFC_RVT_Bundle.zip")

    try:
        app.add_url_rule("/api/3d/scene_json", endpoint="archos_3d_scene_json_v48", view_func=_handle_3d_scene_json_query, methods=["GET"])
        app.add_url_rule("/api/cad/layers", endpoint="archos_cad_layers_v49", view_func=_handle_cad_layers_api, methods=["GET", "POST"])
        app.add_url_rule("/api/cad/reclassify_layers", endpoint="archos_cad_reclassify_v49", view_func=_handle_cad_layers_api, methods=["POST"])
        app.add_url_rule("/api/3d/download_bim", endpoint="archos_download_bim_v50", view_func=_handle_download_bim_bundle, methods=["GET"])
    except Exception:
        pass

    try:
        app.add_url_rule("/api/render/latest" , endpoint="archos_latest_render_v33_7", view_func=_handle_latest_render_query, methods=["GET"])
    except Exception:
        pass

    for _ep_route in (
        "/api/plan/upload_external",
        "/api/site/upload_plan",
        "/api/upload_plan",
    ):
        try:
            app.add_url_rule(
                _ep_route,
                endpoint=f"archos_extplan_{_ep_route.replace('/', '_')}",
                view_func=_handle_external_plan_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    @app.before_request
    def _architectos_v27_1_krocki_interceptor():
        path_low = (_arch_req.path or "").lower()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/scene_json":
            return _handle_3d_scene_json_query()
        if path_low.rstrip("/") in ("/api/cad/layers", "/api/cad/reclassify_layers"):
            return _handle_cad_layers_api()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/download_bim":
            return _handle_download_bim_bundle()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/render/latest":
            return _handle_latest_render_query()
        if _arch_req.method in ("POST", "OPTIONS") and ("upload_external" in path_low or "upload_plan" in path_low):
            return _handle_external_plan_upload_request()
        if _arch_req.method in ("POST", "OPTIONS") and ("krocki" in path_low or "/api/site/upload" in path_low or "/api/site/parse" in path_low):
            return _handle_krocki_upload_request()
        if _arch_req.method == "POST" and path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
            _jb = _arch_req.get_json(silent=True) or {}
            if _jb.get("external_plan_upload_only") or _jb.get("action") == "upload_external_plan":
                return _handle_external_plan_upload_request()
            if _jb.get("krocki_upload_only") or _jb.get("action") == "upload_krocki":
                return _handle_krocki_upload_request()
            _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
            _repo = _resolve_arch_repo_root()
            if _pid:
                _sync_krocki_into_project_session(_repo, _pid)
                _sync_project_renders_and_assets(_repo, _pid)
            _user_txt = str(_jb.get("message") or _jb.get("prompt") or _jb.get("text") or "").strip()
            _is_ui_proxy = os.path.basename(os.path.dirname(os.path.abspath(__file__))).lower() == "ui"
            if _is_3d_facade_render_chat_command(_user_txt):
                if path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
                    return _handle_plan_locked_3d_render_request(_jb)

    @app.after_request
    def _architectos_v30_asset_sync_after_request(response):
        try:
            path_low = (_arch_req.path or "").lower()
            if "/api/chat" in path_low or "/api/project" in path_low or "/api/session" in path_low:
                _jb = _arch_req.get_json(silent=True) or {}
                _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
                if _pid:
                    _sync_project_renders_and_assets(_resolve_arch_repo_root(), _pid)
        except Exception:
            pass
        return response

except Exception as _arch_hook_err:
    print("[!] Warning registering ArchitectOS v51.0 Krocki, External Plan & Render routes:", _arch_hook_err)
# [/ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
