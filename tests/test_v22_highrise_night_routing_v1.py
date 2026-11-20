"""V22_HIGHRISE_NIGHT_ROUTING_V1 — CPU contract tests.

Covers the three wiring points authorised on 2026-11-08:

* ``workflow_selector`` resolves an explicit ``v22_mode`` to the base graph
  the mode builder expects, and refuses every combination it cannot honour.
* ``render_runtime`` composes the mode onto the loaded graph and strips the
  builder's bookkeeping stamp before submission.
* ``chat_architect`` recognises colloquial Persian follow-up re-renders that
  carry no contiguous edit phrase.

CPU only. Nothing here submits a graph, loads a model or touches ComfyUI:
CPU PASS is not visual PASS, and no v22 mode has been rendered.
"""

import copy
import json
import os

import pytest

from core.render.workflow_selector import (
    WorkflowSelector,
    V22_MODE_TXT2IMG_EXACT_FLOORS,
    V22_MODE_DAY_TO_NIGHT_RELIGHT,
    V22_MODE_BASE_WORKFLOW,
)

from core.render.render_runtime import strip_v22_graph_metadata

from core.render.experimental.architectos_v22_highrise_night_v1 import (
    MissingControlNetNodeError,
    build_mode_specific_stage2_workflow,
    parse_requested_floor_count_detail,
    requires_exact_floor_control,
    synthesize_exact_n_story_tower_controlnet,
)

from core.chat.chat_architect import (
    ChatArchitect,
    compile_edit_delta,
    detect_render_followup,
    resolve_state_edit_signal,
)


WORKFLOW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "render", "workflows",
)


def _load(name):
    with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------

def test_selector_unchanged_without_v22_mode():
    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "img2img"}) == \
        "flux_img2img.json"
    assert selector.select({"engine": "flux", "kontext_edit": True}) == \
        "flux_kontext_edit.json"
    assert selector.select({"engine": "flux", "uso_reference": True}) == \
        "flux_uso_reference.json"


def test_selector_maps_each_mode_to_its_base_graph():
    selector = WorkflowSelector()

    assert selector.select({
        "engine": "flux",
        "v22_mode": V22_MODE_TXT2IMG_EXACT_FLOORS,
    }) == "flux.json"

    assert selector.select({
        "engine": "flux",
        "mode": "img2img",
        "image": "day.png",
        "v22_mode": V22_MODE_DAY_TO_NIGHT_RELIGHT,
    }) == "flux_img2img.json"

    assert set(V22_MODE_BASE_WORKFLOW) == {
        V22_MODE_TXT2IMG_EXACT_FLOORS,
        V22_MODE_DAY_TO_NIGHT_RELIGHT,
    }


def test_selector_refuses_unknown_mode():
    selector = WorkflowSelector()

    assert selector.select({
        "engine": "flux",
        "v22_mode": "MODE_9_DOES_NOT_EXIST",
    }) is None


def test_selector_refuses_mode_source_mismatch():
    selector = WorkflowSelector()

    # MODE_1 is text-to-image: an image makes it an edit.
    assert selector.select({
        "engine": "flux",
        "image": "day.png",
        "v22_mode": V22_MODE_TXT2IMG_EXACT_FLOORS,
    }) is None

    # MODE_3 relights a source latent: with no source it must not degrade
    # into a fresh generation.
    assert selector.select({
        "engine": "flux",
        "v22_mode": V22_MODE_DAY_TO_NIGHT_RELIGHT,
    }) is None


def test_selector_refuses_competing_optins():
    selector = WorkflowSelector()

    for extra in (
        {"kontext_edit": True},
        {"uso_reference": True},
        {"dual_image": True},
        {"conditioned": True},
        # a mask forces the Kontext route
        {"mask": "mask.png"},
    ):
        request = {"engine": "flux", "v22_mode": V22_MODE_TXT2IMG_EXACT_FLOORS}
        request.update(extra)

        assert selector.select(request) is None, extra


def test_selector_refuses_non_flux_engine():
    selector = WorkflowSelector()

    assert selector.select({
        "engine": "wan",
        "v22_mode": V22_MODE_TXT2IMG_EXACT_FLOORS,
    }) is None


# ---------------------------------------------------------------------------
# Mode builder composition (no submission)
# ---------------------------------------------------------------------------

def test_mode_1_attaches_controlnet_and_stays_text_to_image():
    graph = build_mode_specific_stage2_workflow(
        _load("flux.json"),
        V22_MODE_TXT2IMG_EXACT_FLOORS,
        "a 25 storey tower",
        "",
        123456789,
        control_image_name="scaffold.png",
    )

    assert graph["311"]["class_type"] == "ControlNetApplyAdvanced"
    assert graph["310"]["class_type"] == "ControlNetLoader"
    assert graph["312"]["inputs"]["image"] == "scaffold.png"

    assert graph["210"]["inputs"]["positive"] == ["311", 0]
    assert graph["210"]["inputs"]["negative"] == ["311", 1]

    assert graph["210"]["inputs"]["denoise"] == 0.96
    assert graph["311"]["inputs"]["strength"] == 0.86
    assert graph["311"]["inputs"]["end_percent"] == 0.88

    # text-to-image, not img2img: the latent is still empty
    assert graph["211"]["class_type"] == "EmptyLatentImage"
    assert "301" not in graph


def test_mode_3_attaches_controlnet_to_the_img2img_base_graph():
    graph = build_mode_specific_stage2_workflow(
        _load("flux_img2img.json"),
        V22_MODE_DAY_TO_NIGHT_RELIGHT,
        "night",
        "",
        7,
        control_image_name="geometry.png",
        source_image_name="night_prepass.png",
    )

    assert graph["311"]["class_type"] == "ControlNetApplyAdvanced"
    assert graph["300"]["inputs"]["image"] == "night_prepass.png"
    assert graph["210"]["inputs"]["denoise"] == 0.34
    assert graph["311"]["inputs"]["strength"] == 0.96
    assert graph["311"]["inputs"]["end_percent"] == 1.00

    # the source latent is preserved: MODE_3 is a relight, not a generation
    assert graph["301"]["class_type"] == "VAEEncode"


def test_mode_1_requires_a_control_image():
    with pytest.raises(MissingControlNetNodeError):
        build_mode_specific_stage2_workflow(
            _load("flux.json"),
            V22_MODE_TXT2IMG_EXACT_FLOORS,
            "a tower",
            "",
            1,
            control_image_name=None,
        )


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        build_mode_specific_stage2_workflow(
            _load("flux.json"),
            "MODE_9_DOES_NOT_EXIST",
            "a tower",
            "",
            1,
            control_image_name="x.png",
        )


def test_builder_does_not_mutate_the_caller_graph():
    base = _load("flux.json")
    before = copy.deepcopy(base)

    build_mode_specific_stage2_workflow(
        base,
        V22_MODE_TXT2IMG_EXACT_FLOORS,
        "a tower",
        "",
        1,
        control_image_name="scaffold.png",
    )

    assert base == before


# ---------------------------------------------------------------------------
# Submission graph
# ---------------------------------------------------------------------------

def test_metadata_stamp_is_stripped_and_nodes_survive():
    graph = build_mode_specific_stage2_workflow(
        _load("flux.json"),
        V22_MODE_TXT2IMG_EXACT_FLOORS,
        "a tower",
        "",
        1,
        control_image_name="scaffold.png",
    )

    assert graph["_architectos_mode"] == V22_MODE_TXT2IMG_EXACT_FLOORS

    submitted = strip_v22_graph_metadata(graph)

    assert "_architectos_mode" not in submitted
    assert submitted["210"]["class_type"] == "KSampler"
    assert submitted["311"]["class_type"] == "ControlNetApplyAdvanced"


def test_metadata_strip_tolerates_absent_key_and_non_dict():
    assert strip_v22_graph_metadata({"9": {}}) == {"9": {}}
    assert strip_v22_graph_metadata(None) is None


# ---------------------------------------------------------------------------
# Floor-count reading (the chat wiring's input)
# ---------------------------------------------------------------------------

def test_persian_floor_count_is_read():
    assert parse_requested_floor_count_detail("یک برج ۲۵ طبقه رندر کن").count == 25
    assert parse_requested_floor_count_detail("a 12 storey tower").count == 12


def test_negated_floor_count_is_not_accepted():
    reading = parse_requested_floor_count_detail("۲۵ طبقه نمی‌خواهم")

    assert reading.count is None
    assert reading.negated is True


def test_floor_control_threshold():
    assert requires_exact_floor_control(25) is True
    assert requires_exact_floor_control(5) is True
    assert requires_exact_floor_control(4) is False
    assert requires_exact_floor_control(None) is False


def test_scaffold_counts_tiers_and_carries_no_identity():
    image, meta = synthesize_exact_n_story_tower_controlnet(12)

    assert image.shape == (1344, 896, 3)
    assert meta["tier_count"] == 12
    assert meta["tier_count_matches_request"] is True
    assert meta["carries_building_identity"] is False
    assert meta["cropped"] is False


# ---------------------------------------------------------------------------
# Chat: colloquial Persian follow-up detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "رندر شبش بگیر",
    "شبش کن",
    "از یه زاویه دیگه رندر بگیر",
    "همین ساختمون رو رندر شب بگیر",
    "رندر شبانه بده",
    "render it at night",
    "another angle please",
])
def test_followup_render_is_detected(text):
    result = detect_render_followup(text)

    assert result["matched"] is True
    assert result["contract"] == "RenderFollowupV1"


@pytest.mark.parametrize("text", [
    "این رندر شب هست یا روز؟",
    "چرا رندر شب اینقدر تیره است؟",
    "یک ویلای ۲ طبقه بساز",
    "تحلیل کن",
    "سلام",
    "",
])
def test_non_followup_is_not_detected(text):
    assert detect_render_followup(text)["matched"] is False


def test_plain_render_request_is_not_a_followup():
    # "رندر بگیر" is already in the contiguous edit-phrase table; the
    # detector must not claim it, so the two signals stay separable.
    assert detect_render_followup("رندر بگیر")["matched"] is False


# ---------------------------------------------------------------------------
# Chat: the routing predicate the state gate actually consumes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "رندر شبش بگیر",
    "شبش کن",
    "از یه زاویه دیگه رندر بگیر",
    "همین ساختمون رو رندر شب بگیر",
])
def test_state_edit_signal_is_true_for_every_required_followup(text):
    from core.intent_router import IntentRouter

    router = IntentRouter()

    assert resolve_state_edit_signal(
        text, compile_edit_delta(text), router
    ) is True


def test_followup_signal_does_not_depend_on_the_delta():
    """A generic delta leaves the follow-up grammar as the ONLY signal."""

    text = "از یه زاویه دیگه رندر بگیر"

    delta = compile_edit_delta(text)

    assert delta["edit_class"] == "generic_edit"

    # intent_router=None removes the second signal entirely.
    assert resolve_state_edit_signal(text, delta, None) is True


def test_new_design_brief_is_not_a_followup():
    text = (
        "یک ساختمان مسکونی سه طبقه با نمای نئوکلاسیک، سنگ تراورتن کرم، "
        "پنجره‌های متقارن و نور روز طراحی کن."
    )

    assert detect_render_followup(text)["matched"] is False


def test_explicit_text_to_image_turn_is_recognised():
    chat = ChatArchitect.__new__(ChatArchitect)

    assert chat._explicit_text_to_image_turn({
        "routing_source": "manual", "mode": "text_to_image",
    }) is True

    # Auto mode infers the operation; it is not an explicit generation turn.
    assert chat._explicit_text_to_image_turn({
        "routing_source": "auto", "mode": "text_to_image",
    }) is False

    assert chat._explicit_text_to_image_turn({}) is False
    assert chat._explicit_text_to_image_turn(None) is False


# ---------------------------------------------------------------------------
# Chat: staging the scaffold for ComfyUI
# ---------------------------------------------------------------------------

def test_floor_control_scaffold_is_staged_and_reused(tmp_path, monkeypatch):
    from config import runtime_config as runtime_config

    from core.chat.chat_architect import _v22_exact_floor_control

    monkeypatch.setattr(
        runtime_config, "COMFYUI_INPUT_DIR", str(tmp_path)
    )

    name, meta = _v22_exact_floor_control(12)

    assert name.startswith("architectos_v22_floors_12_")
    assert name.endswith(".png")
    assert meta["tier_count"] == 12
    assert (tmp_path / name).is_file()

    # Digest-addressed: the same request reuses the same file instead of
    # writing a second copy.
    second, _ = _v22_exact_floor_control(12)

    assert second == name
    assert len(list(tmp_path.iterdir())) == 1


# ---------------------------------------------------------------------------
# Runtime: fail-closed gate, before anything can be submitted
# ---------------------------------------------------------------------------

def test_runtime_refuses_v22_when_the_controlnet_asset_is_missing(monkeypatch):
    from core.render import dual_image_conditioning_v1 as conditioning

    from core.render.render_runtime import RenderRuntime

    monkeypatch.setattr(
        conditioning,
        "verify_conditioning_models",
        lambda *a, **k: {
            "status": "blocked",
            "present": {"geometry_controlnet": False},
            "missing": [{"role": "geometry_controlnet"}],
            "invalid": [],
        },
    )

    result = RenderRuntime().render(
        "p",
        {"prompt": "a tower", "mode": "generate"},
        "flux",
        None,
        v22_mode=V22_MODE_TXT2IMG_EXACT_FLOORS,
        v22_control_image="scaffold.png",
    )

    assert result["status"] == "v22_controlnet_unavailable"
    assert result["v22_mode"] == V22_MODE_TXT2IMG_EXACT_FLOORS
    # nothing was submitted: the gate runs before the executor
    assert "prompt_id" not in result


def test_runtime_refuses_a_graph_that_cannot_carry_controlnet(monkeypatch):
    from core.render import dual_image_conditioning_v1 as conditioning

    from core.render.render_runtime import RenderRuntime

    monkeypatch.setattr(
        conditioning,
        "verify_conditioning_models",
        lambda *a, **k: {
            "status": "ready",
            "present": {"geometry_controlnet": True},
            "missing": [],
            "invalid": [],
        },
    )

    # MODE_3 needs a control map; without one the base graph has no
    # ControlNet branch to configure, and the mode must not degrade.
    result = RenderRuntime().render(
        "p",
        {"prompt": "night", "mode": "img2img"},
        "flux",
        {"filename": "day.png", "path": "day.png"},
        v22_mode=V22_MODE_DAY_TO_NIGHT_RELIGHT,
        v22_control_image=None,
        v22_source_image="night_prepass.png",
    )

    assert result["status"] in ("v22_graph_invalid", "v22_mode_invalid")
    assert result["v22_mode"] == V22_MODE_DAY_TO_NIGHT_RELIGHT
