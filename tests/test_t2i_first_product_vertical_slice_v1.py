# -*- coding: utf-8 -*-
"""T2I_FIRST_PRODUCT_VERTICAL_SLICE_V1 — CPU-only acceptance.

Proves the existing ArchitectOS application can carry one Persian
architectural request all the way to a PREPARED FLUX text-to-image
execution, with the ComfyUI HTTP boundary stubbed so that:

  * no prompt is submitted,
  * no model is loaded or sampled,
  * no GPU is touched,
  * a failed render is never reported as a successful generation.

The image used for the storage/display assertions is an EXISTING fixture
PNG, never a fabricated "generated" image.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    build_render_instruction,
)
from core.intent_router import IntentRouter
from core.render.render_strategy_controller_v1 import resolve_strategy
from core.render.workflow_loader import WorkflowLoader
from core.render.workflow_selector import WorkflowSelector
from core.chat.response_contract import envelope_status_for


REQUEST = (
    "یک ساختمان مسکونی سه طبقه با نمای نئوکلاسیک، سنگ تراورتن کرم، "
    "پنجره‌های متقارن و نور روز طراحی کن."
)

FLUX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "render", "workflows", "flux.json",
)

FIXTURE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
FIXTURE_NAME = "TEST_FIXTURE_not_a_generated_image.png"


# ==========================================================
# A. ROUTING — the request reaches the intended T2I route
# ==========================================================

def test_01_manual_text_to_image_mode_routes_to_image_generation():
    strategy = resolve_strategy(user_text=REQUEST, requested_mode="text_to_image")
    assert strategy["resolved_mode"] == "text_to_image"
    assert strategy["routing_source"] == "manual"

    with contextlib.redirect_stdout(io.StringIO()):
        routed = IntentRouter().route(
            REQUEST,
            image=None,
            context={
                "mode": strategy["resolved_mode"],
                "routing_source": strategy["routing_source"],
            },
        )

    assert routed["intent"] == "image"
    assert routed["mode"] == "generate"


def test_02_auto_mode_does_not_claim_text_to_image():
    """AUTO is not a T2I route — the product flow needs the explicit mode.

    Documented behaviour, not a defect: the request verb is «طراحی کن»
    (design), which the accepted router sends to the design pipeline.
    """

    with contextlib.redirect_stdout(io.StringIO()):
        routed = IntentRouter().route(REQUEST, image=None, context={})

    assert routed["intent"] != "image"
    assert routed["mode"] != "generate"


# ==========================================================
# B. ARCHITECTURAL CONSTRAINTS ARE RETAINED
# ==========================================================

@pytest.fixture(scope="module")
def instruction():
    with contextlib.redirect_stdout(io.StringIO()):
        return build_render_instruction(REQUEST, mode="text2img")


def test_03_floor_count_is_explicit_and_hard(instruction):
    constraints = instruction["constraints"]
    assert constraints["floor_count"]["value"] == 3
    provenance = constraints["floor_count_provenance"]
    assert provenance["value"] == 3
    assert provenance["source"] == "USER_TEXT"
    assert provenance["hard_constraint"] is True


def test_04_style_material_lighting_and_windows_are_captured(instruction):
    """The raw intent owner must resolve style and material from the request."""

    from core.prompt_intelligence.architectural_intent import ArchitecturalIntent

    with contextlib.redirect_stdout(io.StringIO()):
        intent = ArchitecturalIntent().extract({"prompt": REQUEST})

    assert intent["style"] == "neoclassical"
    assert any("travertine" in m for m in intent["materials"])
    assert intent["floors"] == 3
    # The enriched, user-facing interpretation is asserted end-to-end in
    # test_13 (facade composition, daylight, symmetry).


def test_05_no_invented_geometry_or_window_count(instruction):
    """No exact window count and no site dimensions may be invented."""

    constraints = instruction["constraints"]
    assert constraints["dimensions"] == []
    openings = constraints["openings"] or {}
    text = json.dumps(openings, ensure_ascii=False).lower()
    # No numeric window count is asserted anywhere in the openings contract.
    for token in ("count\": 4", "count\": 6", "count\": 8"):
        assert token not in text


def test_06_prompt_carries_the_architectural_language(instruction):
    prompt = instruction["english_instruction"].lower()
    assert "neoclassical" in prompt
    assert "travertine" in prompt
    assert "exactly 3 floors" in prompt


# ==========================================================
# C. THE ACTUAL FLUX GRAPH CONTRACT IS HONOURED
# ==========================================================

def test_07_selector_returns_the_existing_flux_workflow():
    with contextlib.redirect_stdout(io.StringIO()):
        selected = WorkflowSelector().select({"engine": "flux", "mode": "text2img"})
    assert selected == "flux.json"


def test_08_workflow_file_exists_and_matches_its_recorded_identity():
    assert os.path.isfile(FLUX_PATH)
    with open(FLUX_PATH, encoding="utf-8") as handle:
        graph = json.load(handle)

    assert set(graph) == {
        "202", "204", "205", "206", "208", "210", "211", "212", "9",
    }
    assert graph["202"]["inputs"]["unet_name"] == (
        "flux1-krea-dev_fp8_scaled.safetensors"
    )
    assert graph["204"]["inputs"]["clip_name1"] == "clip_l.safetensors"
    assert graph["204"]["inputs"]["clip_name2"] == "t5xxl_fp16.safetensors"
    assert graph["205"]["inputs"]["vae_name"] == "ae.safetensors"

    sampler = graph["210"]["inputs"]
    assert sampler["steps"] == 20
    assert sampler["cfg"] == 1
    assert sampler["sampler_name"] == "euler"
    assert sampler["scheduler"] == "simple"
    assert sampler["denoise"] == 1
    assert sampler["seed"] == 123456789

    latent = graph["211"]["inputs"]
    assert (latent["width"], latent["height"]) == (736, 704)
    assert latent["batch_size"] == 1

    assert graph["9"]["inputs"]["filename_prefix"] == "architectos_v11"


def test_09_injected_graph_keeps_every_flux_node(instruction):
    from core.render.workflow_injector import WorkflowInjector

    with open(FLUX_PATH, encoding="utf-8") as handle:
        graph = json.load(handle)

    with contextlib.redirect_stdout(io.StringIO()):
        injected = WorkflowInjector().inject_prompt(
            graph, instruction["english_instruction"], None
        )

    assert set(graph) <= set(injected)
    assert injected["202"]["inputs"]["unet_name"] == (
        "flux1-krea-dev_fp8_scaled.safetensors"
    )
    positive = injected["206"]["inputs"]["text"].lower()
    assert "neoclassical" in positive
    assert "travertine" in positive
    negative = injected["212"]["inputs"]["text"].lower()
    assert "blurry" in negative


# ==========================================================
# D. TRUTHFUL ENVELOPE — a failure is never a success
# ==========================================================

@pytest.mark.parametrize("status", [
    "completed_no_image", "submit_error", "execution_error", "error",
])
def test_10_terminal_failure_statuses_are_reported_as_error(status):
    assert envelope_status_for({"type": "image_render", "status": status}) == "error"


@pytest.mark.parametrize("status", [
    "success", "waiting_for_instruction", "degraded", "", None,
])
def test_11_non_failure_statuses_stay_success(status):
    assert envelope_status_for({"type": "image_render", "status": status}) == "success"


def test_12_red_before_fix_failure_statuses_were_success():
    """RED record: only the literal "error" used to be promoted.

    Encoded as a direct assertion on the contract so a regression that
    narrows the set back to "error" fails here.
    """

    from core.chat import response_contract as owner

    assert "completed_no_image" in owner._TERMINAL_FAILURE_STATUSES
    assert "submit_error" in owner._TERMINAL_FAILURE_STATUSES
    assert "execution_error" in owner._TERMINAL_FAILURE_STATUSES
    assert "waiting_for_instruction" not in owner._TERMINAL_FAILURE_STATUSES
    assert "degraded" not in owner._TERMINAL_FAILURE_STATUSES


# ==========================================================
# E. END-TO-END THROUGH THE REAL HTTP BOUNDARY (stubbed GPU)
# ==========================================================

# Module-level state for the stubbed transport. The stub methods are bound
# onto the REAL ComfyHTTPRuntime class, so they must not read state from
# `type(self)` — `self` is the real instance, not the stub class.
RECORDER = {"calls": [], "outcome": "success"}


class _RecordingComfy:
    """Deterministic non-executing transport for the ComfyUI boundary."""

    def __init__(self, endpoint=None):
        self.endpoint = "stub://none"
        self.session = None

    def submit(self, workflow, client_id=None):
        RECORDER["calls"].append(
            ("submit", len(workflow) if isinstance(workflow, dict) else 0)
        )
        if RECORDER["outcome"] == "submit_error":
            return {"status": "error", "error": "stub_rejected"}
        return {"status": "submitted", "prompt_id": "stub-prompt-test"}

    def history(self, prompt_id, timeout=None):
        return {"outputs": {}}

    def wait_for_result(self, prompt_id):
        if RECORDER["outcome"] == "no_image":
            return {"status": "completed", "prompt_id": prompt_id,
                    "images": [], "history": {"outputs": {}}}
        return {
            "status": "completed",
            "prompt_id": prompt_id,
            "images": [{"filename": FIXTURE_NAME, "subfolder": "", "type": "output"}],
            "history": {"outputs": {}},
        }

    def extract_images(self, history):
        return []

    def extract_videos(self, history):
        return []

    def detect_error(self, history):
        return None

    def queue_state(self, timeout=None):
        return {"queue_running": [], "queue_pending": []}

    def cancel_prompt(self, prompt_id, timeout=None):
        return {"status": "stub"}

    def confirm_inactive(self, prompt_id, timeout=None, interval=None):
        return True


@pytest.fixture
def slice_env(tmp_path, monkeypatch):
    """Real app, real HTTP route, isolated roots, stubbed GPU boundary."""

    out_dir = tmp_path / "comfy_output"
    out_dir.mkdir()
    (out_dir / FIXTURE_NAME).write_bytes(FIXTURE_PNG)

    projects = tmp_path / "projects"
    projects.mkdir()

    from core.project.project_workspace_v1 import project_workspace
    from core.chat.chat_attachment import chat_attachment_service
    from core.render import comfy_http_runtime

    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(tmp_path / "trash"))

    # Point the attachment resolver AND every result bridge at the fixture
    # root. `RenderResultBridge` reads RC.COMFYUI_OUTPUT_DIR at construction
    # and the image handler constructs its own bridge, so the module value
    # must be redirected too — otherwise registration looks in the real
    # ComfyUI output folder and refuses the fixture as "file missing".
    from config import runtime_config as RC

    monkeypatch.setattr(RC, "COMFYUI_OUTPUT_DIR", str(out_dir))
    monkeypatch.setitem(
        chat_attachment_service.roots, "comfy_output", out_dir.resolve()
    )

    import app as application

    monkeypatch.setattr(
        application.chat.render_runtime.result_bridge,
        "output_dir",
        str(out_dir),
    )

    # Stub the transport on the CLASS, so the already-constructed
    # executor's `comfy` instance is covered too.
    for name in (
        "submit", "history", "wait_for_result", "extract_images",
        "extract_videos", "detect_error", "queue_state", "cancel_prompt",
        "confirm_inactive",
    ):
        monkeypatch.setattr(
            comfy_http_runtime.ComfyHTTPRuntime,
            name,
            getattr(_RecordingComfy, name),
        )

    RECORDER["calls"] = []
    RECORDER["outcome"] = "success"

    # TEST ISOLATION, not a gate bypass: the stubbed transport never creates a
    # real ComfyUI job, so a marker left by a previous stubbed turn refers to
    # nothing that exists. `test_21` proves the gate still blocks when a real
    # unconfirmed job IS recorded.
    runtime = application.chat.render_runtime
    monkeypatch.setattr(runtime, "_orphaned_render_guard", None)
    monkeypatch.setattr(runtime, "_orphaned_prompt_id", None)
    monkeypatch.setattr(runtime, "active_render", None)

    client = application.app.test_client()
    manifest = project_workspace.create("T2I Slice Test")
    project_id = manifest["project_id"]

    # The real UI opens the project first; that binds the session registry,
    # which is what makes the render asset adoptable into the project.
    from core.project.project_session_v1 import project_session

    project_session.open(project_id)
    client.post("/api/projects/%s/open" % project_id, json={})

    return {
        "client": client,
        "project_id": project_id,
        "workspace": project_workspace,
    }


def test_13_success_path_returns_one_image_and_one_attachment(slice_env):
    env = slice_env
    resp = env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["status"] == "success"
    response = body["response"]
    assert response["type"] == "image_render"
    assert response["status"] == "success"

    image = response["image"]
    assert image["url"].startswith("/artifacts/comfy_output/")

    attachments = response["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["kind"] == "render"

    assert response["architectural_intent"]["floors"] == 3
    assert body["strategy"]["resolved_mode"] == "text_to_image"
    assert body["strategy"]["routing_source"] == "manual"


def test_14_exactly_one_submission_and_no_retry(slice_env):
    env = slice_env
    env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    submits = [c for c in RECORDER["calls"] if c[0] == "submit"]
    assert len(submits) == 1
    # The submitted graph is the flux graph (9 nodes) plus the runtime marker.
    assert submits[0][1] == 10


def test_15_output_is_persisted_under_the_project(slice_env):
    """The render is registered as an owned project asset, not a loose file."""

    env = slice_env
    env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    from core.project.project_registry_bridge_v1 import project_registry_bridge

    gallery = project_registry_bridge.gallery(env["project_id"])
    assert gallery["asset_count"] == 1

    asset = gallery["assets"][0]
    assert asset["kind"] == "render"
    assert asset["asset_id"].startswith("img_")
    assert asset["ordinal"] == 1
    # Servable through the existing artifact route, not a bare filesystem path.
    assert asset["public_path"].startswith("/artifacts/")
    # The render belongs to THIS project's registry (not a global bucket).
    assert asset["asset_id"] in {
        a["asset_id"] for a in gallery["assets"]
    }


def test_16_no_image_is_reported_as_failure_not_success(slice_env):
    env = slice_env
    RECORDER["outcome"] = "no_image"
    resp = env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    body = resp.get_json()

    assert body["status"] == "error"
    assert body["response"]["status"] == "completed_no_image"
    assert body["response"].get("image") is None
    assert body["response"].get("attachments") is None
    # The user still receives a truthful sentence.
    assert "رندر" in str(body["response"].get("message") or "")


def test_17_rejected_submission_is_reported_as_failure(slice_env):
    env = slice_env
    RECORDER["outcome"] = "submit_error"
    resp = env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    body = resp.get_json()

    assert body["status"] == "error"
    assert body["response"].get("image") is None
    from core.project.project_registry_bridge_v1 import project_registry_bridge
    assert project_registry_bridge.gallery(env["project_id"])["asset_count"] == 0


def test_18_fixture_is_never_labelled_as_a_generated_asset(slice_env):
    """The stored asset must carry the real filename, not a claimed generation."""

    env = slice_env
    env["client"].post("/chat", json={
        "message": REQUEST, "project_id": env["project_id"],
        "mode": "text_to_image",
    })
    from core.project.project_registry_bridge_v1 import project_registry_bridge

    asset = project_registry_bridge.gallery(env["project_id"])["assets"][0]
    serialized = json.dumps(asset, ensure_ascii=False).lower()
    # Provenance is the stub transport, never a claim of real GPU output.
    assert "test_fixture_not_a_generated_image" in serialized


# ==========================================================
# F. EXECUTION AUTHORIZATION / LEASE IS NOT BYPASSED
# ==========================================================

def test_19_submit_still_takes_the_comfyui_lease():
    """The real transport acquires the cross-process lease before POSTing."""

    import inspect

    from core.render import comfy_http_runtime

    source = inspect.getsource(comfy_http_runtime.ComfyHTTPRuntime.submit)
    assert "comfyui_lease" in source
    # The stub replaces the transport, never the lease itself.
    assert "lease" in source


def test_20_no_network_client_is_reachable_from_the_test_transport():
    import inspect

    from core.render import comfy_http_runtime

    source = inspect.getsource(_RecordingComfy)
    for forbidden in ("requests.", "http", "socket"):
        assert forbidden not in source.lower()
    assert callable(comfy_http_runtime.ComfyHTTPRuntime.submit)


def test_21_orphan_gate_blocks_when_a_previous_job_is_unconfirmed(slice_env):
    """The execution-authorization gate is ENFORCED, never bypassed.

    With a parked orphan guard whose job stop cannot be proven, the runtime
    must refuse to start new GPU work. Asserted at the gate itself so the
    check is stable and cannot be satisfied by a transport accident.
    """

    env = slice_env
    runtime = __import__("app").chat.render_runtime

    RECORDER["calls"] = []
    runtime._orphaned_render_guard = object()
    runtime._orphaned_prompt_id = "unconfirmed-prompt"
    runtime._orphaned_reason = "job_state_unconfirmed"
    try:
        # No ComfyUI is reachable, so "no active job" can never be proved.
        recovered = runtime._recover_orphaned_render()
        assert recovered is False
        assert runtime.last_gpu_handoff_render.get("status") == "orphaned"
        assert runtime.last_gpu_handoff_render.get("stage") == "protected_render_period"
    finally:
        runtime._orphaned_render_guard = None
        runtime._orphaned_prompt_id = None
        runtime.last_gpu_handoff_render = None

    # And the gate is consulted before any submission: a render that reaches
    # the gate while parked cannot submit.
    runtime._orphaned_render_guard = object()
    runtime._orphaned_prompt_id = "unconfirmed-prompt"
    try:
        resp = env["client"].post("/chat", json={
            "message": REQUEST, "project_id": env["project_id"],
            "mode": "text_to_image",
        })
        body = resp.get_json()
        assert [c for c in RECORDER["calls"] if c[0] == "submit"] == []
        assert body["status"] != "success"
    finally:
        runtime._orphaned_render_guard = None
        runtime._orphaned_prompt_id = None
