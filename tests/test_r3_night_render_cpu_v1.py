# -*- coding: utf-8 -*-
"""R3_NIGHT_RENDER_CPU_V1 — day-to-night architectural image edit.

Scope
-----
A user says «این ساختمان را شب کن» over an existing building image.
ArchitectOS must recognise an APPEARANCE edit, keep the EXISTING Kontext
instruction-edit route, and instruct the engine to change only lighting and
atmosphere — never to rebuild the building.

These tests pin the DECISION, the INSTRUCTION and the GRAPH BINDING. They
never touch Ollama, ComfyUI or the GPU: a passing CPU test is not proof of a
good night render, and this file does not claim it is.
"""

import hashlib
import json
import os
import struct

import pytest

from core.intent_router import intent_router
from core.vision.image_intent_v1 import (
    classify_image_intent, has_edit_signal, detect_unsupported_geometry_edit,
    INTENT_ANALYZE, INTENT_EDIT, INTENT_OBSERVE,
)
from core.chat.chat_architect import _manual_image_intent
from core.cognition.architectural_terminology_v1 import extract_terms
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta, delta_prompt, conflict_terms, denoise_override,
    is_classified,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    resolve_design_decision, decision_instruction_block,
)
from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import resolve_render_prompt
from core.render.render_preset_v1 import (
    infer_preset, build_quality_tail, tail_conflicts,
)
from core.render.workflow_selector import WorkflowSelector
from core.render.image_workflow_injector import ImageWorkflowInjector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KONTEXT_GRAPH = os.path.join(ROOT, "core", "render", "workflows",
                             "flux_kontext_edit.json")

#: The accepted V3 facade used as the engineering fixture for R3.
SOURCE_PATH = r"C:\ComfyUI-Zluda\output\architectos_v11_00263_.png"
SOURCE_SHA256 = ("ae77532be8dd80bbf35af1a04136b86d"
                 "1689f9b0845b50325f0e4c8a5cde1ab4")

PERSIAN_NIGHT = "این ساختمان را شب کن"
ENGLISH_NIGHT = "make this building at night"

NIGHT_REQUESTS = [
    PERSIAN_NIGHT,
    "این بنا را شب کن",
    "همینو شب کن",
    "این ساختمان را شبانه کن",
    "نمای این ساختمان را شب کن",
    "شبش کن",
    "این ساختمان را به شب تبدیل کن",
    ENGLISH_NIGHT,
    "turn this building into a night scene",
    "convert this facade to night",
    "make it nighttime",
    "day to night conversion of this building",
    "show this building at night",
    "make the building look like night",
]

DESCRIPTIVE_QUESTIONS = [
    "این ساختمان چند طبقه دارد؟",
    "این ساختمان چه رنگی است؟",
    "چه مصالحی در این نما استفاده شده؟",
    "What materials are visible on this building?",
    "Describe this facade.",
]

FACADE_UNDERSTANDING = {
    "image_type": "architectural_render_or_photo",
    "elements": [],
}


def _auto(text):
    """Auto mode is exactly `_manual_image_intent` with no UI mode."""
    return _manual_image_intent("", text, intent_router)


def _night_delta(text=PERSIAN_NIGHT):
    return compile_edit_delta(text, image_edit=True)


# ==========================================================
# FIXTURE — the source image is the engineering authority
# ==========================================================

def _png_dimensions(path):
    with open(path, "rb") as handle:
        header = handle.read(33)
    width, height = struct.unpack(">II", header[16:24])
    return width, height


@pytest.mark.skipif(not os.path.isfile(SOURCE_PATH),
                    reason="V3 facade fixture not present")
def test_source_fixture_digest_is_the_accepted_one():
    digest = hashlib.sha256(open(SOURCE_PATH, "rb").read()).hexdigest()
    assert digest == SOURCE_SHA256


@pytest.mark.skipif(not os.path.isfile(SOURCE_PATH),
                    reason="V3 facade fixture not present")
def test_source_fixture_is_model_compatible():
    """The Kontext latent must equal the source resolution exactly.

    `_bind_reference_edit_contract` refuses non-16-divisible dimensions
    rather than rounding, so the fixture must satisfy that contract.
    """
    width, height = _png_dimensions(SOURCE_PATH)
    assert (width, height) == (768, 704)
    assert width % 16 == 0 and height % 16 == 0


# ==========================================================
# RED — the hazards this milestone must not reintroduce
# ==========================================================

def test_RED_deictic_alone_is_still_not_an_edit_signal():
    """R2 fixed the deictic; a night edit must not undo it."""
    assert intent_router.is_image_edit_request("این ساختمان") is False


def test_RED_night_request_is_not_a_geometry_edit():
    """A night conversion may never be refused as unsupported geometry."""
    for text in (PERSIAN_NIGHT, ENGLISH_NIGHT):
        guard = detect_unsupported_geometry_edit(text, context={})
        assert guard.get("unsupported") is False


def test_RED_night_delta_is_not_generic():
    """An unclassified delta would skip the global-appearance route."""
    assert is_classified(_night_delta()) is True
    assert _night_delta().get("edit_class") == "time_of_day_change"


# ==========================================================
# MATRIX 1 / 2 / 3 — intent
# ==========================================================

@pytest.mark.parametrize("text", NIGHT_REQUESTS)
def test_matrix_1_persian_and_english_night_request_routes_to_edit(text):
    assert _auto(text)["intent"] == INTENT_EDIT
    assert _manual_image_intent(
        "image_to_image", text, intent_router)["intent"] == INTENT_EDIT


def test_matrix_1_persian_night_request_matches_the_edit_vocabulary():
    ok, hits = has_edit_signal(PERSIAN_NIGHT, intent_router)
    assert ok is True and hits


@pytest.mark.parametrize("text", DESCRIPTIVE_QUESTIONS)
def test_matrix_3_descriptive_questions_route_to_analysis(text):
    intent = _auto(text)
    assert intent["intent"] in (INTENT_ANALYZE, INTENT_OBSERVE)
    assert intent["intent"] != INTENT_EDIT


# ==========================================================
# MATRIX 4 — Analyze Image never renders
# ==========================================================

@pytest.mark.parametrize("text", [PERSIAN_NIGHT, ENGLISH_NIGHT,
                                  "این ساختمان را شب کن و طبقاتش را بشمار"])
def test_matrix_4_analyze_mode_never_generates_an_image(text):
    assert _manual_image_intent(
        "analyze_image", text, intent_router)["intent"] != INTENT_EDIT


def test_matrix_4_analyze_mode_is_not_the_classifier():
    """The explicit mode must decide, not the text classifier."""
    assert classify_image_intent(
        PERSIAN_NIGHT, intent_router)["intent"] == INTENT_EDIT
    assert _manual_image_intent(
        "analyze_image", PERSIAN_NIGHT, intent_router)["intent"] == INTENT_ANALYZE


# ==========================================================
# MATRIX 6 / 7 / 8 — the instruction protects the existing building
# ==========================================================

def _resolved_prompt(text=PERSIAN_NIGHT):
    delta = _night_delta(text)
    decision = resolve_design_decision(
        user_text=text, edit_delta=delta,
        image_understanding=FACADE_UNDERSTANDING,
        preserve_geometry=True, preserve_constraints=(),
    )
    block = decision_instruction_block(decision)
    preset, _ = infer_preset(extract_terms(text))
    builder = PromptRouter().build(
        {"prompt": text,
         "architectural_intent": {"building_type": "residential",
                                  "edit_delta": delta},
         "design_context": {"project_id": "chat_project", "mode": "img2img",
                            "image_asset": {"path": "source.png"},
                            "design": {}}},
        mode="img2img",
    )
    resolution = resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=builder,
        user_text=text,
        preset_tail=build_quality_tail(preset),
        preset_name=preset,
        conflict_terms=tuple(tail_conflicts(preset)) + tuple(conflict_terms(delta)),
        architectural_instruction=block,
    )
    return delta, decision, block, preset, resolution


def test_matrix_6_decision_authorises_relight_only():
    _, decision, block, _, _ = _resolved_prompt()
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["requested_operation"]["operation"] == "relight"
    assert decision["editable_elements"] == ["lighting", "atmosphere"]
    assert block["contract"] == "RenderConstraintBlockV1"
    assert "lighting and atmosphere" in block["constraint_block"]
    assert "do not restyle" in block["constraint_block"]


def test_matrix_6_the_instruction_names_the_protected_geometry():
    delta, _, _, _, resolution = _resolved_prompt()
    prompt = resolution["prompt"].lower()
    for protected in ("silhouette", "massing", "floor count", "roof shape",
                      "openings", "camera angle", "composition",
                      "balconies", "railings"):
        assert protected in prompt, protected
    assert "do not" in prompt
    assert "add floors" in prompt and "remove floors" in prompt
    assert delta["time_of_day"] == "night"


def test_matrix_7_floor_count_is_a_preservation_target():
    """Four storeys must survive because the instruction forbids a change to
    the floor count — not because a number is guessed from the image."""
    _, _, _, _, resolution = _resolved_prompt()
    prompt = resolution["prompt"].lower()
    assert "floor count" in prompt
    assert "add floors" in prompt and "remove floors" in prompt
    # no invented storey count is asserted into the prompt
    for invented in ("4 storey", "4-storey", "four storey", "four-storey"):
        assert invented not in prompt


def test_matrix_8_the_edit_is_lighting_only():
    delta, _, block, preset, resolution = _resolved_prompt()
    prompt = resolution["prompt"].lower()
    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "night"
    assert "night" in prompt
    assert preset == "exterior_night"
    assert "redesign" in prompt  # explicitly forbidden, not merely absent
    assert block["constraint_block"]


def test_matrix_8_replacement_wording_appears_only_as_a_prohibition():
    """The prompt may NAME a new building, but only inside the DO NOT block.

    A positive request to create one would be a redesign, which this edit is
    not authorised to perform.
    """
    _, _, _, _, resolution = _resolved_prompt()
    prompt = resolution["prompt"].lower()
    assert "do not" in prompt
    prohibitions = prompt[prompt.index("do not"):]
    for redesign in ("create a new building", "redesign the building",
                     "change volume", "modify structural layout"):
        assert redesign in prohibitions, redesign
        assert redesign not in prompt[:prompt.index("do not")], redesign


def test_matrix_8_daylight_language_is_stripped():
    delta = _night_delta()
    terms = set(conflict_terms(delta))
    for daylight in ("daylight", "natural lighting", "golden hour", "sunlit"):
        assert daylight in terms
    _, _, _, _, resolution = _resolved_prompt()
    prompt = resolution["prompt"].lower()
    assert "golden hour" not in prompt
    assert "sunlit" not in prompt


def test_matrix_8_the_compiled_delta_stays_authoritative():
    _, _, _, _, resolution = _resolved_prompt()
    assert resolution["source"] == "compiled_authoritative"
    assert resolution["instruction_applied"] is True
    assert resolution["instruction_truncated"] is False


def test_matrix_8_a_floor_plan_never_becomes_a_relight_render():
    """KNOWN GAP — pinned as evidence, NOT as approved behaviour.

    `resolve_design_decision` refuses a plan-source MATERIAL or STYLE edit,
    but a `time_of_day_change` over `floor_plan_or_sketch` produces no
    editable element and therefore no constraint block, while the status
    still reads READY. A night edit over a plan image would reach the
    existing workflow with no geometry-preservation instruction at all.

    This is a pre-existing fail-open in the decision layer. R3 does not
    repair it (out of the facade night-edit scope and not proven necessary
    for the supervised job); it is reported as a remaining risk.
    """
    delta = _night_delta()
    decision = resolve_design_decision(
        user_text=PERSIAN_NIGHT, edit_delta=delta,
        image_understanding={"image_type": "floor_plan_or_sketch",
                             "elements": []},
        preserve_geometry=True, preserve_constraints=(),
    )
    assert decision["editable_elements"] == []
    assert decision_instruction_block(decision) == ""
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"


def test_matrix_8_a_plan_source_material_edit_is_still_refused():
    """The neighbouring guard that DOES fail closed, for contrast."""
    decision = resolve_design_decision(
        user_text="متریال نمای این ساختمان را سنگ کن",
        edit_delta=compile_edit_delta(
            "متریال نمای این ساختمان را سنگ کن", image_edit=True),
        image_understanding={"image_type": "floor_plan_or_sketch",
                             "elements": []},
        preserve_geometry=True, preserve_constraints=(),
    )
    assert decision["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"
    assert decision_instruction_block(decision) == ""


# ==========================================================
# MATRIX 13 / workflow — the source, not a mask, drives the edit
# ==========================================================

def test_matrix_9_a_classified_appearance_edit_selects_kontext():
    selector = WorkflowSelector()
    request = {"engine": "flux", "mode": "img2img",
               "image": {"path": "source.png"},
               "kontext_edit": is_classified(_night_delta())}
    assert selector.select(request) == "flux_kontext_edit.json"


def test_matrix_9_an_unclassified_edit_keeps_plain_img2img():
    selector = WorkflowSelector()
    request = {"engine": "flux", "mode": "img2img",
               "image": {"path": "source.png"}}
    assert selector.select(request) == "flux_img2img.json"


def test_matrix_9_a_supplied_mask_still_selects_the_masked_route():
    selector = WorkflowSelector()
    request = {"engine": "flux", "mode": "img2img",
               "image": {"path": "source.png"}, "mask": {"path": "mask.png"}}
    assert selector.select(request) == "flux_kontext_edit.json"


def _inject(mask_asset=None):
    workflow = json.load(open(KONTEXT_GRAPH, encoding="utf-8"))
    asset = {"filename": "architectos_v11_00263_.png",
             "path": SOURCE_PATH,
             "working_dimensions": [768, 704]}
    result = ImageWorkflowInjector().inject(
        workflow, "NIGHT PROMPT", asset,
        {"denoise": None, "seed": 123456789, "steps": 20},
        mask_asset=mask_asset,
    )
    return result, result["workflow"]


def test_matrix_13_global_night_edit_substitutes_no_mask():
    result, workflow = _inject()
    contract = result["reference_edit_contract"]
    assert contract["status"] == "resolved"
    assert contract["scope"] == "global"
    # the output comes straight from the decoder, not from a composite
    assert workflow["9"]["inputs"]["images"] == [contract["save_source_node"], 0]
    assert workflow["9"]["inputs"]["images"][0] != "312"
    # the source is bound as the edit reference
    assert workflow["320"]["inputs"]["latent"] == ["301", 0]
    assert workflow["301"]["inputs"]["pixels"] == ["300", 0]
    assert workflow["300"]["inputs"]["image"] == "architectos_v11_00263_.png"


def test_matrix_13_the_mask_loader_is_unreachable_in_global_scope():
    """ComfyUI validates and executes only the subgraph reachable from an
    output node. The placeholder `LoadImageMask` must therefore stay out of
    the executed graph rather than be substituted with the source."""
    _, workflow = _inject()
    seen, stack = set(), ["9"]
    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in workflow:
            continue
        seen.add(node_id)
        for value in (workflow[node_id].get("inputs") or {}).values():
            if isinstance(value, list) and len(value) == 2 \
                    and isinstance(value[0], str):
                stack.append(value[0])
    assert "310" not in seen  # LoadImageMask
    assert "312" not in seen  # ImageCompositeMasked


def test_matrix_13_latent_and_strength_match_the_source():
    result, workflow = _inject()
    assert workflow["302"]["inputs"]["width"] == 768
    assert workflow["302"]["inputs"]["height"] == 704
    # Kontext is not strength-driven: a preservation denoise must never be
    # injected onto a zero latent.
    assert workflow["210"]["inputs"]["denoise"] == 1.0
    assert result["reference_edit_contract"]["width"] == 768


def test_matrix_13_a_localised_edit_is_unchanged():
    result, workflow = _inject({"filename": "mask.png", "path": "mask.png"})
    assert result["reference_edit_contract"]["scope"] == "localized"
    assert workflow["9"]["inputs"]["images"] == ["312", 0]


def test_matrix_12_the_edit_strength_contract_is_not_applied_to_kontext():
    """TIME_OF_DAY_DENOISE belongs to the plain img2img band only."""
    assert denoise_override(_night_delta()) == pytest.approx(0.30)


# ==========================================================
# MATRIX 10 / 11 — lineage, and no replacement building on failure
# ==========================================================

def _handler():
    from core.chat.handlers.image_handler import ImageHandler
    return ImageHandler(None, None, None, None, None, None, None)


def _bind_session(monkeypatch, session_id):
    from core.chat.handlers import image_handler as module
    monkeypatch.setattr(
        module.session_registry, "current",
        lambda: {"session_id": session_id},
    )


def test_matrix_10_a_failed_render_registers_no_asset(monkeypatch):
    _bind_session(monkeypatch, "r3_failure_session")
    handler = _handler()
    assert handler._register_derived_output({"status": "error"}) is None
    assert handler._register_derived_output(
        {"image_asset": {"path": None}}) is None
    assert handler._register_derived_output(
        {"image_asset": {"path": os.path.join(ROOT, "no_such_render.png")}}
    ) is None


@pytest.mark.skipif(not os.path.isfile(SOURCE_PATH),
                    reason="V3 facade fixture not present")
def test_matrix_11_derived_asset_keeps_source_lineage(monkeypatch):
    _bind_session(monkeypatch, "r3_lineage_session")
    handler = _handler()
    record = handler._register_derived_output(
        {"image_asset": {"path": SOURCE_PATH,
                         "filename": "architectos_v11_00263_.png"}},
        parent_image_id="img_source_0001",
    )
    assert record is not None
    assert record["source_type"] == "image_to_image"
    assert record["parent_image_id"] == "img_source_0001"
    assert record["active"] is True
