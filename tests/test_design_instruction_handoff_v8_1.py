"""V8.1 — design decision must control the executable image-edit instruction.

CPU only. No model, no vision, no GPU, no ComfyUI. Every provider seam is
forbidden; the renderer is replaced by a recorder that never submits.

The assertions read the FINAL instruction produced by the same resolution
function the render path uses (`resolve_render_prompt`), not a metadata dict.
"""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    conflict_terms as edit_delta_conflict_terms,
    delta_prompt as edit_delta_prompt,
    is_classified as is_classified_edit_delta,
)
from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import resolve_render_prompt
from core.chat.handlers.image_handler import ImageHandler

PRESERVE = (
    "number_of_floors",
    "overall_massing",
    "building_silhouette",
    "main_window_positions",
    "main_door_positions",
    "roofline",
)

MATERIAL_TEXT = (
    "Use light travertine on the facade walls, but preserve the columns, "
    "windows and entrance."
)
STYLE_TEXT = (
    "Change the facade to neoclassical while keeping the mass, openings and "
    "floors unchanged."
)
LIGHTING_TEXT = "نمای ساختمان را شب کن؛ معماری و مصالح تغییر نکنند."
REMOVAL_TEXT = "Remove the wall-mounted lanterns and keep everything else unchanged."
CONFLICT_TEXT = "Redesign the roof but preserve its original shape."


def _element(name, kinds, quote, *, context=(), position=None, evidence="MODEL_REPORTED"):
    return {
        "element": name,
        "kind": list(kinds),
        "context_kinds": list(context),
        "kind_basis": "subject_explicit",
        "source_quote": quote,
        "evidence_class": evidence,
        "verification_status": "VERIFIED" if evidence == "PIXEL_VERIFIED" else "UNVERIFIED",
        "confidence": None,
        "position": position,
        "relations": [],
    }


def _facade(*, lantern_position=None, lantern_evidence="MODEL_REPORTED"):
    return {
        "contract": "ImageUnderstandingV1",
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "image_type": "facade_or_elevation",
        "element_evidence": {
            "contract": "ArchitecturalElementEvidenceV1",
            "source_image": {"image_id": "facade-1", "sha256": "a" * 64},
            "elements": [
                _element("facade wall", ("wall",), "A pale facade wall plane."),
                _element("windows", ("window", "opening"), "Regular window openings."),
                _element("columns", ("column",), "Columns frame the entrance."),
                _element("entrance", ("entrance", "door"), "A central entrance door."),
                _element(
                    "lanterns",
                    ("light_fixture",),
                    "Lantern fixtures mounted on the wall.",
                    context=("wall",),
                    position=lantern_position,
                    evidence=lantern_evidence,
                ),
            ],
        },
    }


MODERN = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "modern-1", "sha256": "b" * 64},
        "elements": [
            _element("rendered wall", ("wall",), "A plain rendered wall plane."),
            _element("strip windows", ("window", "opening"), "Horizontal strip windows."),
        ],
    },
}

PLAN = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "floor_plan_or_sketch",
    "local_plan_reading": {"status": "grounded", "furniture_evidence": []},
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(self, address, *a, **k):
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _decision(text, understanding, *, knowledge=True, preserve_constraints=PRESERVE):
    delta = compile_edit_delta(text, image_edit=True)
    resolved = None
    if knowledge:
        resolved = SharedFacadeKnowledgeResolverV1().resolve({
            "style": delta.get("style"),
            "materials": [delta["material"]] if delta.get("material") else [],
            "normalized_prompt": text,
        })
    decision = resolve_design_decision(
        user_text=text,
        edit_delta=delta,
        image_understanding=understanding,
        resolved_facade_knowledge=resolved,
        preserve_geometry=True,
        preserve_constraints=preserve_constraints,
    )
    return delta, resolved, decision


def _final_instruction(text, understanding, *, knowledge=True, with_decision=True):
    """The exact text the render path resolves, via the real resolution call."""

    delta, resolved, decision = _decision(text, understanding, knowledge=knowledge)

    architectural_intent = {
        "preserve_geometry": True,
        "preserve_constraints": list(PRESERVE),
        "resolved_facade_knowledge": resolved,
        "style": delta.get("style") or "",
        "materials": [delta["material"]] if delta.get("material") else [],
        "request_type": "image_edit",
        "normalized_prompt": text,
        "edit_delta": delta,
    }

    if with_decision:
        architectural_intent["architectural_design_decision"] = decision

    payload = {
        "prompt": text,
        "architectural_intent": architectural_intent,
        "mode": "img2img",
        "compiled_render_prompt": (
            edit_delta_prompt(delta) if is_classified_edit_delta(delta) else None
        ),
    }

    if with_decision:
        block = decision_instruction_block(decision)
        if block:
            payload["architectural_instruction"] = block

    builder_prompt = PromptRouter().build(payload, mode="img2img")["description"]

    resolution = resolve_render_prompt(
        compiled_prompt=payload["compiled_render_prompt"],
        builder_prompt=builder_prompt,
        user_text=text,
        conflict_terms=tuple(edit_delta_conflict_terms(delta)),
        # mirror RenderRuntime.render(): the payload's constraint block is the
        # architectural_instruction argument of the resolver.
        architectural_instruction=payload.get("architectural_instruction"),
    )

    return resolution["final_prompt"], decision, resolution


# ==========================================================
# CASE A — MATERIAL EDIT
# ==========================================================

def test_material_instruction_names_supported_target_and_fixed_elements():
    text, decision, _ = _final_instruction(MATERIAL_TEXT, _facade())

    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["editable_elements"] == ["facade_wall_surface"]

    lowered = text.lower()
    assert "facade wall surface" in lowered, "the decision target must be in the instruction"
    assert "columns" in lowered
    assert "entrance" in lowered
    assert "travertine" in lowered
    # geometric restriction survives in the same text
    assert "roof shape" in lowered or "roofline" in lowered or "massing" in lowered
    assert "design decision" in lowered


def test_material_instruction_does_not_widen_to_other_domains():
    text, _, _ = _final_instruction(MATERIAL_TEXT, _facade())
    lowered = text.lower()

    for forbidden in ("redesign the roof", "add floors", "change the volume"):
        assert forbidden not in lowered or "do not" in lowered


# ==========================================================
# CASE B — STYLE EDIT
# ==========================================================

def test_style_instruction_restricts_to_facade_expression_and_preserves_geometry():
    text, decision, _ = _final_instruction(STYLE_TEXT, _facade())

    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["editable_elements"] == ["facade_surface_expression"]

    lowered = text.lower()
    assert "facade surface expression" in lowered
    assert "neoclassical" in lowered
    assert {"massing", "opening", "roof"} <= set(decision["fixed_constraints"]["domains"])


def test_style_instruction_claims_no_guaranteed_compliance():
    text, _, _ = _final_instruction(STYLE_TEXT, _facade())
    lowered = text.lower()

    for overclaim in ("guarantee", "guaranteed", "will be preserved exactly as requested"):
        assert overclaim not in lowered


# ==========================================================
# CASE C — LIGHTING EDIT (PERSIAN)
# ==========================================================

def test_lighting_instruction_changes_lighting_only_and_preserves_facade():
    text, decision, _ = _final_instruction(LIGHTING_TEXT, MODERN)

    assert decision["requested_operation"]["edit_class"] == "time_of_day_change"
    assert decision["editable_elements"] == ["lighting", "atmosphere"]

    lowered = text.lower()
    assert "lighting" in lowered
    assert "atmosphere" in lowered
    assert "night" in lowered

    # no unrelated architectural change is introduced by the decision block
    assert "neoclassical" not in lowered
    assert "travertine" not in lowered
    assert "facade transformation" not in lowered


# ==========================================================
# CASE D — LOCALIZED REMOVAL
# ==========================================================

class _State:
    def __init__(self):
        self.value = {}

    def get(self):
        return deepcopy(self.value)

    def update(self, values):
        self.value.update(values)


class _RecordingRuntime:
    def __init__(self):
        self.payloads = []
        self.masks = []
        self.resolver = SharedFacadeKnowledgeResolverV1()

    def resolve_shared_facade_knowledge(self, intent):
        resolved = self.resolver.resolve(intent)
        intent["resolved_facade_knowledge"] = resolved
        return resolved

    def render(self, project, payload, engine, asset, **kwargs):
        self.payloads.append(deepcopy(payload))
        self.masks.append(kwargs.get("mask_asset"))
        return {"status": "recorded_no_execution"}


def _handler():
    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": "recorded-source.png"}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _RecordingRuntime()
    handler.result_bridge = SimpleNamespace(
        resolve=lambda result: {"status": result["status"], "engine": "recorded"}
    )
    handler.image_response = SimpleNamespace(adapt=lambda result: deepcopy(result))
    return handler


def test_unlocalized_lantern_removal_never_reaches_the_render_boundary():
    handler = _handler()
    result = handler.handle_image_edit(
        text=REMOVAL_TEXT,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(REMOVAL_TEXT, image_edit=True),
        image_understanding=_facade(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "needs_spatial_targeting"
    assert handler.render_runtime.payloads == [], "no instruction may reach the renderer"


def test_masked_removal_instruction_keeps_subject_and_context_distinct():
    handler = _handler()
    handler.handle_image_edit(
        text=REMOVAL_TEXT,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(REMOVAL_TEXT, image_edit=True),
        image_understanding=_facade(),
        mask_asset={"filename": "mask.png", "dimensions": [384, 512], "mode": "L"},
    )

    assert len(handler.render_runtime.payloads) == 1
    payload = handler.render_runtime.payloads[0]
    decision = payload["architectural_intent"]["architectural_design_decision"]

    assert decision["editable_elements"] == ["lanterns"]
    block = payload.get("architectural_instruction") or {}
    text = (block.get("constraint_block") or "").lower()

    assert "lanterns" in text
    assert "wall" in text
    # the wall must be described as context to keep, never as the removal target
    assert "remove the wall" not in text
    assert "removing the wall" not in text


# ==========================================================
# CASE E — CONFLICT
# ==========================================================

def test_conflicting_request_blocks_and_produces_no_constraint_block():
    _, decision, _ = _final_instruction(CONFLICT_TEXT, _facade())

    assert decision["execution_status"] == "BLOCKED_CONFLICT"
    assert decision_instruction_block(decision) == ""

    handler = _handler()
    result = handler.handle_image_edit(
        text=CONFLICT_TEXT,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(CONFLICT_TEXT, image_edit=True),
        image_understanding=_facade(),
    )
    assert result["status"] == "blocked"
    assert handler.render_runtime.payloads == []


# ==========================================================
# GEOMETRY SAFETY — position metadata is not a mask
# ==========================================================

def test_removal_with_position_metadata_still_requires_spatial_targeting():
    _, decision, _ = _final_instruction(
        REMOVAL_TEXT,
        _facade(lantern_position=[0.4, 0.5, 0.5, 0.6], lantern_evidence="PIXEL_VERIFIED"),
    )

    assert decision["execution_status"] == "NEEDS_SPATIAL_TARGETING", (
        "a recorded position must not substitute for a validated mask"
    )
    assert "mask" in str(decision["workflow_recommendation"]).lower()


def test_position_only_removal_is_blocked_before_render():
    handler = _handler()
    result = handler.handle_image_edit(
        text=REMOVAL_TEXT,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(REMOVAL_TEXT, image_edit=True),
        image_understanding=_facade(
            lantern_position=[0.4, 0.5, 0.5, 0.6], lantern_evidence="PIXEL_VERIFIED"
        ),
    )

    assert result["status"] == "blocked"
    assert handler.render_runtime.payloads == []


# ==========================================================
# GENERALIZATION CONTROLS
# ==========================================================

def test_same_image_different_request_yields_different_instruction():
    material, _, _ = _final_instruction(MATERIAL_TEXT, _facade())
    lighting, _, _ = _final_instruction(LIGHTING_TEXT, _facade())

    assert material != lighting
    assert "facade wall surface" in material.lower()
    assert "atmosphere" in lighting.lower()


def test_same_request_different_evidence_changes_supported_targets():
    facade_text, facade_decision, _ = _final_instruction(MATERIAL_TEXT, _facade())
    plan_text, plan_decision, _ = _final_instruction(MATERIAL_TEXT, PLAN)

    assert facade_decision["editable_elements"] == ["facade_wall_surface"]
    assert plan_decision["editable_elements"] == []
    assert plan_decision["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"
    assert decision_instruction_block(plan_decision) == ""
    assert "facade wall surface" in facade_text.lower()


def test_added_fixed_element_adds_a_preservation_constraint():
    base_text, base_decision, _ = _final_instruction(
        "Change this facade to neoclassical.", _facade()
    )
    fixed_text, fixed_decision, _ = _final_instruction(
        "Change this facade to neoclassical but preserve the columns exactly.",
        _facade(),
    )

    assert "columns" not in (base_decision["fixed_constraints"]["elements"] or [])
    assert "columns" in fixed_decision["fixed_constraints"]["elements"]
    assert fixed_text != base_text


def test_removed_knowledge_context_removes_knowledge_content():
    with_knowledge, _, _ = _final_instruction(STYLE_TEXT, _facade(), knowledge=True)
    without_knowledge, decision, _ = _final_instruction(STYLE_TEXT, _facade(), knowledge=False)

    assert decision["applicable_knowledge"] is None
    assert "neoclassical" in with_knowledge.lower()
    assert "as design guidance only" in with_knowledge.lower()
    assert "as design guidance only" not in without_knowledge.lower()


def test_without_a_decision_contract_the_instruction_is_unchanged():
    legacy, _, _ = _final_instruction(MATERIAL_TEXT, _facade(), with_decision=False)

    assert "design decision" not in legacy.lower()
    assert "facade wall surface" not in legacy.lower()
    # the established compiled + builder composition is preserved
    assert "travertine" in legacy.lower()
    assert "preserve the columns, windows and entrance" in legacy.lower()
