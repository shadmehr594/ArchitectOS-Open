# ==========================================================
# ArchitectOS — V4.3B PRE-RENDER INTEGRATION GATE
#
# Covers the two boundaries V4.3A did not exercise:
#
#   A — the false "single floor building" claim that the generic img2img
#       builder tail appends to every EDIT prompt.
#   B — the REAL application path:
#           ChatArchitect._route_image_edit
#             -> ImageHandler.handle_image_edit
#             -> RenderRuntime.render
#             -> WorkflowExecutor.execute   <-- intercepted
#
# The executor is the last practical boundary: the injected graph captured
# here is the exact payload that would have been POSTed to ComfyUI /prompt.
# Nothing is submitted. NO GPU. NO COMFYUI. NO SAMPLER.
# ==========================================================

import hashlib
import os

import pytest

from core.chat.chat_architect import ChatArchitect
from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    conflict_terms,
    delta_prompt,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.vision.image_intent_v1 import classify_image_intent


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_IMAGE = os.path.join(
    ROOT, "runs", "architectos_product_integration_v3", "p3a_transfer_output.png"
)

GENERIC_BUILDER_TAIL = (
    "modern tower architectural visualization, single floor building, "
    "minimal modern architecture, architectural photography, 35mm lens, "
    "golden hour natural lighting, cinematic realistic render, "
    "physically accurate materials, 8k ultra realistic"
)

FLOOR_CLAIM = "single floor building"


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ==========================================================
# A — FALSE FLOOR CLAIM REMOVED FROM I2I PROMPTS
# ==========================================================

@pytest.mark.parametrize("text", [
    "same tower, morning",
    "same tower, noon",
    "same tower, sunset",
    "same tower, dusk",
    "same tower, night",
    "same tower, make the facade stone",
    "same tower, make it brighter",
])
def test_false_default_floor_claim_is_a_conflict_term(text):
    delta = compile_edit_delta(text)

    assert FLOOR_CLAIM in conflict_terms(delta)


@pytest.mark.parametrize("text", [
    "same tower, morning",
    "same tower, sunset",
    "same tower, night",
])
def test_false_default_floor_claim_never_reaches_the_prompt(text):
    delta = compile_edit_delta(text)

    resolution = resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=GENERIC_BUILDER_TAIL,
        preset_tail="",
        conflict_terms=tuple(conflict_terms(delta)),
    )

    assert FLOOR_CLAIM not in resolution["final_prompt"]
    assert FLOOR_CLAIM in resolution["removed_conflicting_tail_terms"]


def test_lighting_edit_does_not_insert_a_floor_specification():
    """The removal must not be replaced by an invented count."""

    delta = compile_edit_delta("same tower, night")
    prompt = delta_prompt(delta).lower()

    assert "floor" in prompt            # only the PRESERVE clause
    assert "story building" not in prompt
    assert "single floor" not in prompt


def test_explicit_user_floor_specification_is_not_stripped():
    """A real constraint must survive: the conflict term matches ONLY the
    builder's default phrase."""

    builder = GENERIC_BUILDER_TAIL.replace(
        FLOOR_CLAIM, "30 story building"
    )

    delta = compile_edit_delta("same tower, night")

    resolution = resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=builder,
        preset_tail="",
        conflict_terms=tuple(conflict_terms(delta)),
    )

    assert "30 story building" in resolution["final_prompt"]


# ==========================================================
# B — REAL APPLICATION PATH
# ==========================================================

class _StubBrain:
    """ChatArchitect reads only architectural_intent_engine from the brain."""


class _CapturingExecutor:
    """Stands in for WorkflowExecutor at the last practical boundary."""

    def __init__(self):
        self.calls = []

    def execute(self, injected_workflow, engine):
        self.calls.append({"engine": engine, "workflow": injected_workflow})
        return {
            "status": "dry_run_capture",
            "engine": engine,
            "error": "v4_3b_test_no_sampler",
        }


@pytest.fixture(scope="module")
def app():
    if not os.path.exists(BASE_IMAGE):
        pytest.skip("validated base render not present: %s" % BASE_IMAGE)

    chat = ChatArchitect(_StubBrain())
    return chat


def _run_edit(app, tmp_path, text, seed=1234567):
    """Drive the real edit path with a redirected ComfyUI input directory."""

    # Keep the per-request source copy inside the test sandbox.
    app.image_handler.image_bridge.asset_bridge.comfy_input = str(tmp_path)

    executor = _CapturingExecutor()
    app.render_runtime.executor = executor
    app.render_runtime.last_render_request = {}
    app.render_runtime.last_render_metadata = {}

    result = app._route_image_edit(
        text=text,
        image_record={"path": BASE_IMAGE, "filename": os.path.basename(BASE_IMAGE)},
        image_reference=None,
        compiled_render_prompt="",
        terminology=normalize_architectural_terms(text),
        render_seed=seed,
        context={},
    )

    workflow = executor.calls[0]["workflow"] if executor.calls else {}
    positive = ""
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
            text_value = (node.get("inputs") or {}).get("text")
            if isinstance(text_value, str) and len(text_value) > len(positive):
                positive = text_value

    load_image = None
    sampler = {}
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "LoadImage":
            load_image = (node.get("inputs") or {}).get("image")
        if node.get("class_type") == "KSampler":
            sampler = node.get("inputs") or {}

    source_path = os.path.join(str(tmp_path), load_image) if load_image else None

    return {
        "result": result,
        "executor_called": bool(executor.calls),
        "workflow": workflow,
        "prompt": positive,
        "load_image": load_image,
        "source_path": source_path,
        "source_sha256": (
            _sha256(source_path) if source_path and os.path.exists(source_path) else None
        ),
        "denoise": sampler.get("denoise"),
        "steps": sampler.get("steps"),
        "seed": sampler.get("seed"),
        "workflow_name": (app.render_runtime.last_render_metadata or {}).get("workflow_name"),
        "mode": (app.render_runtime.last_render_request or {}).get("mode"),
        "resolved_prompt": (app.render_runtime.last_render_request or {}).get("resolved_prompt"),
    }


@pytest.fixture(scope="module")
def variant_runs(app, tmp_path_factory):
    """Run the three variants ONCE; every assertion reads the same capture."""

    tmp = tmp_path_factory.mktemp("comfy_input")

    return {
        "morning": _run_edit(app, tmp, "same tower, morning"),
        "sunset": _run_edit(app, tmp, "same tower, sunset"),
        "night": _run_edit(app, tmp, "same tower, night"),
    }


@pytest.mark.parametrize("label,marker", [
    ("morning", "morning"),
    ("sunset", "golden-hour"),
    ("night", "night photography"),
])
def test_real_path_reaches_img2img_with_the_intended_lighting(variant_runs, label, marker):
    run = variant_runs[label]

    assert run["executor_called"] is True
    assert run["mode"] == "img2img"
    assert run["workflow_name"] == "flux_img2img.json"
    assert run["denoise"] == 0.3

    prompt = run["prompt"]
    assert "REFERENCE:" in prompt
    assert "DELTA:" in prompt
    assert "PRESERVE:" in prompt
    assert marker in prompt.lower()

    assert FLOOR_CLAIM not in prompt.lower()


def test_real_path_never_contradicts_the_requested_time_of_day(variant_runs):
    morning = variant_runs["morning"]["prompt"].lower()
    sunset = variant_runs["sunset"]["prompt"].lower()
    night = variant_runs["night"]["prompt"].lower()

    assert "golden hour" not in morning
    assert "night" not in morning

    assert "night" not in sunset
    assert "golden-hour" in sunset

    assert "golden hour" not in night
    # "no daylight" is a negation, not a daylight claim.
    assert "daylight" not in night.replace("no daylight", "")


def test_three_variants_share_one_immutable_base(variant_runs):
    """C — the common-base invariant at the final payload boundary."""

    runs = [variant_runs[k] for k in ("morning", "sunset", "night")]

    base_sha = _sha256(BASE_IMAGE)

    assert all(r["source_sha256"] == base_sha for r in runs)
    assert len({r["source_sha256"] for r in runs}) == 1

    # Same workflow, same strength, same seed policy.
    assert {r["workflow_name"] for r in runs} == {"flux_img2img.json"}
    assert {r["denoise"] for r in runs} == {0.3}
    assert {r["steps"] for r in runs} == {runs[0]["steps"]}
    assert {r["seed"] for r in runs} == {1234567}

    # Only the DELTA clause differs.
    deltas = []
    for r in runs:
        start = r["prompt"].index("DELTA:")
        end = r["prompt"].index(", PRESERVE:")
        deltas.append(r["prompt"][start:end])
    assert len(set(deltas)) == 3

    references = []
    for r in runs:
        start = r["prompt"].index("REFERENCE:")
        end = r["prompt"].index(", DELTA:")
        references.append(r["prompt"][start:end])
    assert len(set(references)) == 1


def test_no_source_image_does_not_become_an_edit(app):
    for text in ("same tower, morning", "same tower, night"):
        routed = app.intent_router.route(
            text, image=None, context={"conversation_state": {}}
        )

        assert routed["mode"] != "edit"


def test_unrelated_chat_is_not_an_edit(app):
    state = {
        "last_render_asset": {"path": BASE_IMAGE},
        "last_image_asset": {"path": BASE_IMAGE},
        "last_route_intent": "image",
    }

    for text in (
        "good morning",
        "what colour is the sky in this image?",
        "write me a python function",
        "design a new building",
    ):
        routed = app.intent_router.route(
            text, image=None, context={"conversation_state": state}
        )
        assert routed["mode"] != "edit"

        assert classify_image_intent(text, app.intent_router)["intent"] != "edit"
