# -*- coding: utf-8 -*-
"""R3_NIGHT_MATERIAL_FIDELITY_CPU_V1 — night material-fidelity instruction.

GPU evidence (R3-NIGHT-02) showed the building survived but the brick did not:
the wall was re-rendered as a high-chroma speckled mosaic. Two INSTRUCTION
defects are provable from the submitted prompt itself:

  1. the night delta literally asked for the facade to be "evenly lit";
  2. two ARCHITECTURAL_GRAPHICS rules (HL-026 semantic SVG furniture symbols,
     HL-037 semantic/vector/DWG furniture) were injected into the relight
     instruction at tokens 243-450 of 648, because `_scope_applies()` matched
     the word "architectural" from `image_type`.

These tests pin the corrections. They do NOT claim the next render will look
right: only a supervised GPU comparison can settle that.

No GPU. No ComfyUI submit. No Ollama.
"""

import hashlib
import os

import pytest

from core.architecture.knowledge.human_learning_ledger_v1 import (
    accepted_rules, evaluate_rule_applicability, applicable_rules,
    NOT_APPLICABLE, APPLICABLE,
)
from core.chat.chat_architect import _manual_image_intent
from core.cognition.architectural_terminology_v1 import extract_terms
from core.intent_router import intent_router
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block, resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta, delta_prompt, conflict_terms, is_classified,
)
from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import resolve_render_prompt
from core.render.render_preset_v1 import (
    build_quality_tail, infer_preset, tail_conflicts, tail_reinforcement,
)
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_intent_v1 import INTENT_ANALYZE, INTENT_EDIT, INTENT_OBSERVE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PERSIAN_NIGHT = "این ساختمان را شب کن"
ENGLISH_NIGHT = "make this building at night"

FACADE = {"image_type": "architectural_render_or_photo", "elements": []}

#: Material/style edits are correctly fail-closed without wall evidence, so
#: the "unrelated edits still work" cases must supply it.
FACADE_WITH_WALL = {
    "image_type": "architectural_render_or_photo",
    "element_evidence": {"elements": [{
        "element": "facade wall", "kind": ["wall"], "context_kinds": [],
        "relations": [], "source_quote": "brick wall",
        "evidence_class": "MODEL_REPORTED",
        "verification_status": "UNVERIFIED", "position": None,
    }]},
}

# R3-NIGHT-02 artifacts — must never be modified by this work.
SOURCE_PATH = r"C:\ComfyUI-Zluda\output\architectos_v11_00263_.png"
SOURCE_SHA = "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4"
NIGHT_PATH = r"C:\ComfyUI-Zluda\output\architectos_kontext_edit_00012_.png"
NIGHT_SHA = "2ee2180f0ab3f11de8ce70a9f3c0c93f64ba41c9eed0222c58ac551011b5000e"

GRAPHICS_RULE_IDS = ("HL-026", "HL-037")


# ==========================================================
# HELPERS — the real owners, no re-implementation
# ==========================================================

def _delta(text=PERSIAN_NIGHT):
    return compile_edit_delta(text, image_edit=True)


def _decision(text=PERSIAN_NIGHT, understanding=None, rules=None):
    return resolve_design_decision(
        user_text=text,
        edit_delta=_delta(text),
        image_understanding=(FACADE if understanding is None else understanding),
        preserve_geometry=True,
        preserve_constraints=(),
        human_learning_rules=(
            accepted_rules() if rules is None else rules
        ),
    )


def _block(text=PERSIAN_NIGHT, understanding=None):
    return decision_instruction_block(_decision(text, understanding))


def _effective_prompt(text=PERSIAN_NIGHT):
    """The prompt the sampler would receive, composed by the existing owners."""
    delta = _delta(text)
    block = _block(text)
    preset, _ = infer_preset(extract_terms(text))
    builder = PromptRouter().build(
        {"prompt": text,
         "architectural_intent": {"building_type": "existing building",
                                  "edit_delta": delta},
         "design_context": {"project_id": "chat_project", "mode": "img2img",
                            "image_asset": {"path": "source.png"},
                            "design": {}}},
        mode="img2img",
    )
    if isinstance(builder, dict):
        builder = builder.get("description") or builder.get("raw") or ""
    resolution = resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=builder,
        user_text=text,
        preset_tail=build_quality_tail(preset),
        preset_name=preset,
        conflict_terms=(tuple(tail_conflicts(preset))
                        + tuple(conflict_terms(delta))),
        reinforcement=tail_reinforcement(preset),
        architectural_instruction=block,
    )
    return delta, block, preset, resolution


# ==========================================================
# 1 — night intent unchanged
# ==========================================================

def test_1_night_intent_is_still_time_of_day_change():
    for text in (PERSIAN_NIGHT, ENGLISH_NIGHT):
        delta = _delta(text)
        assert delta["edit_class"] == "time_of_day_change"
        assert delta["time_of_day"] == "night"
        assert is_classified(delta) is True


# ==========================================================
# 2 — workflow unchanged
# ==========================================================

def test_2_the_approved_workflow_is_still_selected():
    selector = WorkflowSelector()
    assert selector.select({
        "engine": "flux", "mode": "img2img",
        "image": {"path": "source.png"},
        "kontext_edit": is_classified(_delta()),
    }) == "flux_kontext_edit.json"


def test_2_an_unclassified_edit_still_uses_plain_img2img():
    assert WorkflowSelector().select({
        "engine": "flux", "mode": "img2img",
        "image": {"path": "source.png"},
    }) == "flux_img2img.json"


# ==========================================================
# 3 — RED: the furniture-graphics contamination
# ==========================================================

def test_3_RED_scope_token_overlap_was_the_root_cause():
    """`ARCHITECTURAL_GRAPHICS` matched on the word "architectural" that
    `image_type` carries for every rendered facade."""
    rules = {rule["id"]: rule for rule in accepted_rules()
             if rule.get("id") in GRAPHICS_RULE_IDS}
    assert set(rules) == set(GRAPHICS_RULE_IDS)
    for rule in rules.values():
        assert str(rule.get("scope")).upper() == "ARCHITECTURAL_GRAPHICS"


def test_3_facade_relighting_receives_no_graphics_rules():
    decision = _decision()
    applied = [rule.get("id") for rule in decision["applied_human_rules"]]
    for rule_id in GRAPHICS_RULE_IDS:
        assert rule_id not in applied, applied


def test_3_the_relight_instruction_names_no_furniture_rule():
    block = _block()
    text = block["constraint_block"]
    assert "HL-026" not in text
    assert "HL-037" not in text
    assert "مبلمان" not in text
    # and no other accepted rule leaked into this operation either
    assert "Accepted human architectural guidance" not in text


def test_3_the_exclusion_is_reported_not_silent():
    """A non-applied rule must be explainable, not merely dropped."""
    for rule_id in GRAPHICS_RULE_IDS:
        rule = next(r for r in accepted_rules() if r["id"] == rule_id)
        verdict = evaluate_rule_applicability(rule, {
            "text": PERSIAN_NIGHT,
            "image_type": "architectural_render_or_photo",
            "operation": "relight",
        })
        assert verdict["status"] == NOT_APPLICABLE
        assert verdict["reason"] == "scope_operation_mismatch"
        assert verdict["operation"] == "relight"


def test_3_the_registry_is_intact():
    """Nothing was disabled, removed or superseded."""
    rules = accepted_rules()
    ids = {rule.get("id") for rule in rules}
    assert set(GRAPHICS_RULE_IDS).issubset(ids)
    assert len(rules) >= 37


# ==========================================================
# 4 — GREEN: legitimate graphics tasks keep their rules
# ==========================================================

@pytest.mark.parametrize("context", [
    {"text": "مبلمان را به صورت SVG و DWG بساز",
     "image_type": "architectural_graphics", "operation": None},
    {"text": "furniture symbols as SVG vector", "operation": "generate_graphics"},
    {"text": "furniture library must be semantic vector ready"},
])
def test_4_graphics_tasks_still_receive_their_rules(context):
    for rule_id in GRAPHICS_RULE_IDS:
        rule = next(r for r in accepted_rules() if r["id"] == rule_id)
        assert evaluate_rule_applicability(rule, context)["status"] == APPLICABLE


def test_4_a_graphics_scope_still_matches_a_graphics_request():
    applied = {rule["id"] for rule in applicable_rules(accepted_rules(), {
        "text": "مبلمان را به صورت SVG و DWG بساز",
        "image_type": "architectural_graphics",
    })}
    assert set(GRAPHICS_RULE_IDS).issubset(applied)


@pytest.mark.parametrize("operation", ["relight", "replace_finish", "restyle"])
def test_4_appearance_operations_exclude_graphics_rules(operation):
    applied = {rule["id"] for rule in applicable_rules(accepted_rules(), {
        "text": PERSIAN_NIGHT,
        "image_type": "architectural_render_or_photo",
        "operation": operation,
    })}
    assert not (set(GRAPHICS_RULE_IDS) & applied)


# ==========================================================
# 5 — source material identity explicitly protected
# ==========================================================

def test_5_source_material_identity_is_explicitly_protected():
    prompt = _effective_prompt()[3]["prompt"].lower()
    assert "real material colour" in prompt
    assert "surface texture" in prompt
    assert "its coursing" in prompt
    assert "appearance of each individual unit" in prompt


def test_5_the_delta_stays_building_agnostic():
    """The night contract applies to every facade, so it must not name one
    material. Naming brick would fix this image and mis-instruct a concrete,
    glass or metal building — the accepted
    `ARCHITECTURAL_NIGHT_EXPOSURE_V1` suite forbids such nouns outright."""
    delta = delta_prompt(_delta()).lower()
    for forbidden in ("brick", "villa", "portico", "chimney", "minab"):
        assert forbidden not in delta, forbidden


def test_5_the_reconstruction_temptations_are_named_and_forbidden():
    prompt = _effective_prompt()[3]["prompt"].lower()
    for temptation in ("cladding", "recolouring", "saturation boost",
                       "staining", "growth"):
        assert temptation in prompt, temptation


# ==========================================================
# 6 — lighting-only operation
# ==========================================================

def test_6_the_authorised_operation_is_relight_only():
    decision = _decision()
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["requested_operation"]["operation"] == "relight"
    assert decision["editable_elements"] == ["lighting", "atmosphere"]


def test_6_the_instruction_restates_the_lighting_only_scope():
    text = _block()["constraint_block"].lower()
    assert "lighting and atmosphere" in text
    assert "do not restyle" in text


# ==========================================================
# 7 — no material redesign requested
# ==========================================================

def test_7_no_positive_material_or_facade_redesign_is_requested():
    """The temptation vocabulary may only appear inside a prohibition."""
    prompt = _effective_prompt()[3]["prompt"].lower()
    for temptation in ("new cladding", "recolour the", "replace the facade",
                       "restyle the facade", "new material"):
        start = 0
        while True:
            index = prompt.find(temptation, start)
            if index < 0:
                break
            preceding = prompt[max(0, index - 12):index]
            assert ("no " in preceding or "not " in preceding
                    or "without " in preceding), (temptation, preceding)
            start = index + 1


def test_7_the_prohibitions_are_stated_not_merely_absent():
    prompt = _effective_prompt()[3]["prompt"].lower()
    assert "no new cladding" in prompt
    assert "do not restyle, re-material or re-model" in prompt


# ==========================================================
# 8 — geometry constraints retained and prioritised
# ==========================================================

@pytest.mark.parametrize("constraint", [
    "silhouette", "massing", "floor count", "roof shape", "openings",
    "windows", "doors", "camera angle", "composition", "proportions",
])
def test_8_geometry_constraints_survive(constraint):
    assert constraint in _effective_prompt()[3]["prompt"].lower()


def test_8_the_floor_count_prohibition_is_intact():
    prompt = _effective_prompt()[3]["prompt"].lower()
    assert "add floors" in prompt
    assert "remove floors" in prompt


def test_8_geometry_constraints_precede_the_quality_tail():
    """Composition order, as `resolve_render_prompt` actually guarantees it:

        compiled intent -> bounded constraint block -> preset/quality tail
                        -> builder preservation block (always last)

    The material-preservation clause must therefore sit EARLY, and the
    builder's geometry block must arrive complete rather than truncated.
    """
    prompt = _effective_prompt()[3]["prompt"]
    preset_tail = prompt.index("night scene, warm lit windows")
    # the relight constraint block precedes the quality tail
    assert prompt.index("Change only the image lighting") < preset_tail
    # the brick-preservation clause precedes the quality tail too
    assert prompt.lower().index("its coursing") < preset_tail
    # the builder geometry block is present exactly once and is not cut
    assert prompt.count("PRESERVE EXACTLY:") == 1
    assert prompt.rstrip().endswith("modify structural layout")


# ==========================================================
# 9 — flat illumination no longer requested
# ==========================================================

def test_9_RED_evenly_lit_was_the_flat_lighting_request():
    delta = _delta()
    assert "evenly lit" not in delta_prompt(delta).lower()


def test_9_controlled_local_lighting_is_requested_instead():
    text = delta_prompt(_delta()).lower()
    assert "controlled local" in text
    assert "gentle falloff" in text


def test_9_the_anti_underexposure_requirement_is_not_regressed():
    """NIGHT_FACADE_LIGHTING_V1 exists because the facade once rendered at
    luma 1.2/255. The rewrite must keep a brightness requirement."""
    text = delta_prompt(_delta()).lower()
    assert "clearly brighter than the sky" in text
    assert "clearly visible" in text


def test_9_interior_light_is_limited_to_existing_windows():
    text = delta_prompt(_delta()).lower()
    assert "existing windows only" in text


# ==========================================================
# 10 — composer integrity: no duplication, no truncation
# ==========================================================

def test_10_the_prompt_is_not_duplicated():
    prompt = _effective_prompt()[3]["prompt"]
    assert prompt.count("PRESERVE:") == 1
    assert prompt.count("no daylight") == 1
    assert prompt.count("PRESERVE EXACTLY:") == 1


def test_10_the_prompt_is_not_truncated_by_the_composer():
    resolution = _effective_prompt()[3]
    assert resolution["source"] == "compiled_authoritative"
    assert resolution["instruction_applied"] is True
    assert resolution["instruction_truncated"] is False
    assert resolution["prompt"].rstrip().endswith("modify structural layout")


def test_10_the_block_stays_within_its_own_budget():
    """The block must stay well inside the documented 1100-char bound."""
    assert len(_block()["constraint_block"]) < 400


def test_10_the_decision_summary_stays_out_of_the_way_of_constraints():
    """Removing the internal decision summary was CONSIDERED and rejected:
    an accepted contract (`test_design_instruction_handoff_v8_1.py`) pins it.
    It must therefore stay, and stay short enough not to crowd constraints."""
    prompt = _effective_prompt()[3]["prompt"]
    assert "Design decision:" in prompt
    assert prompt.index("Design decision:") < prompt.index("PRESERVE EXACTLY:")


# ==========================================================
# 11 — routing unchanged
# ==========================================================

@pytest.mark.parametrize("text", [
    PERSIAN_NIGHT, "این بنا را شب کن", "همینو شب کن",
    "نمای این ساختمان را شب کن", ENGLISH_NIGHT,
    "convert this facade to night", "make it nighttime",
])
def test_11_night_requests_still_route_to_edit(text):
    assert _manual_image_intent("", text, intent_router)["intent"] == INTENT_EDIT
    assert _manual_image_intent(
        "image_to_image", text, intent_router)["intent"] == INTENT_EDIT


# ==========================================================
# 12 — Analyze Image still never renders
# ==========================================================

@pytest.mark.parametrize("text", [PERSIAN_NIGHT, ENGLISH_NIGHT,
                                  "این ساختمان چند طبقه دارد؟"])
def test_12_analyze_mode_never_dispatches_a_render(text):
    intent = _manual_image_intent("analyze_image", text, intent_router)
    assert intent["intent"] in (INTENT_ANALYZE, INTENT_OBSERVE)
    assert intent["intent"] != INTENT_EDIT


# ==========================================================
# 13 — unrelated edits still work
# ==========================================================

def test_13_a_material_edit_is_unaffected():
    text = "متریال نمای این ساختمان را سنگ کن"
    delta = compile_edit_delta(text, image_edit=True)
    assert delta["edit_class"] == "material_change"
    decision = resolve_design_decision(
        user_text=text, edit_delta=delta, image_understanding=FACADE_WITH_WALL,
        preserve_geometry=True, preserve_constraints=(),
        human_learning_rules=accepted_rules())
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["requested_operation"]["operation"] == "replace_finish"
    assert decision["editable_elements"] == ["facade_wall_surface"]


def test_13_a_style_edit_is_unaffected():
    text = "این نما را به سبک نئوکلاسیک تبدیل کن"
    delta = compile_edit_delta(text, image_edit=True)
    decision = resolve_design_decision(
        user_text=text, edit_delta=delta, image_understanding=FACADE_WITH_WALL,
        preserve_geometry=True, preserve_constraints=(),
        human_learning_rules=accepted_rules())
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["requested_operation"]["operation"] == "restyle"


def test_13_a_material_edit_without_wall_evidence_still_fails_closed():
    """The scoping change must not loosen the existing evidence gate."""
    text = "متریال نمای این ساختمان را سنگ کن"
    decision = resolve_design_decision(
        user_text=text, edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=FACADE, preserve_geometry=True,
        preserve_constraints=(), human_learning_rules=accepted_rules())
    assert decision["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"


def test_13_residential_planning_rules_still_apply_to_their_own_operation():
    """The scoping is by operation, so non-graphics rules are untouched."""
    applied = {rule["id"] for rule in applicable_rules(accepted_rules(), {
        "text": "حیاط نورده چند فضای مفید را خدمت دهد",
        "image_type": "floor_plan_or_sketch",
        "operation": "rearrange",
    })}
    assert applied, "a residential planning rule should still apply here"
    assert not (set(GRAPHICS_RULE_IDS) & applied)


# ==========================================================
# 14 — evidence artifacts untouched
# ==========================================================

@pytest.mark.skipif(not os.path.isfile(SOURCE_PATH),
                    reason="R3-NIGHT-02 source fixture not present")
def test_14_the_source_image_is_untouched():
    assert hashlib.sha256(open(SOURCE_PATH, "rb").read()).hexdigest() == SOURCE_SHA


@pytest.mark.skipif(not os.path.isfile(NIGHT_PATH),
                    reason="R3-NIGHT-02 output not present")
def test_14_the_r3_night_02_output_is_untouched():
    assert hashlib.sha256(open(NIGHT_PATH, "rb").read()).hexdigest() == NIGHT_SHA
