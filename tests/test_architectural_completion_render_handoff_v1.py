"""CPU-only completion-contract handoff to the real render instruction owner.

No handler, provider, network, model, ComfyUI, GPU or image generation is
initialised. The test follows the production pure-function path:

ImageEditDeltaV1 -> GeometryAuthorityHandoffV1 -> RenderConstraintBlockV1
-> RenderPromptResolverV1.
"""

from copy import deepcopy
import json

from core.chat.response_adapter import ResponseAdapter
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)


PERSIAN_REQUEST = (
    "نمای این ساختمان نیمه‌کاره را نئوکلاسیک با تراورتن کرم روشن و ظریف "
    "کامل کن. در و پنجره‌ها را داخل بازشوهای موجود نصب کن، ستون‌های موجود "
    "را با سرستون و پوشش مناسب طراحی کن و بالکن‌ها را تکمیل کن. تعداد طبقات، "
    "سازه، محل و ابعاد بازشوها، بام، حیاط، دیوارهای حائل و ساختمان‌های مجاور "
    "را تغییر نده."
)


UNDERSTANDING = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "original-building", "sha256": "8" * 64},
        "elements": [
            {
                "element": "facade wall",
                "kind": ["wall"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "An unfinished facade wall is reported.",
            },
            {
                "element": "exposed brick and block masonry",
                "kind": ["brick", "block", "unfinished masonry"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Exposed brick and block masonry is reported.",
            },
            {
                "element": "existing openings",
                "kind": ["window", "door", "opening"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Existing facade openings are reported.",
            },
            {
                "element": "structural columns",
                "kind": ["column", "structure"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Structural columns are reported.",
            },
            {
                "element": "balcony and terrace edges",
                "kind": ["balcony", "terrace"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Balcony and terrace edges are reported.",
            },
        ],
    },
}


CAPABILITIES = {
    "source_bound_editing": True,
    "soft_depth_guidance": True,
    "style_reference_conditioning": True,
    "evidence": {"source_bound_editing": "Image B source latent"},
}


def _path(text=PERSIAN_REQUEST):
    delta = compile_edit_delta(text, image_edit=True)
    decision = resolve_design_decision(
        user_text=text,
        edit_delta=delta,
        image_understanding=deepcopy(UNDERSTANDING),
        preserve_geometry=True,
        preserve_constraints=(
            "number_of_floors", "overall_massing", "building_silhouette",
            "main_window_positions", "main_door_positions", "roofline",
        ),
        design_context={
            "preservation_workflow_capabilities": deepcopy(CAPABILITIES),
        },
    )
    instruction = decision_instruction_block(decision)
    effective = resolve_render_prompt(
        compiled_prompt=delta.get("prompt"),
        builder_prompt="generic quality tail",
        architectural_instruction=instruction,
        max_instruction_chars=2400,
    )
    return delta, decision, instruction, effective


def _intent(decision):
    return decision["architectural_preservation_intent"]


def _handoff(instruction):
    return instruction["architectural_completion_handoff"]


def _operation_ids(instruction):
    return set(_handoff(instruction)["allowed_operation_ids"])


def _scope_ids(items):
    return {item["id"] for item in items}


def test_01_all_explicit_completion_operations_reach_effective_instruction():
    _, _, instruction, effective = _path()
    assert _operation_ids(instruction) == {
        "complete_windows_within_existing_openings",
        "install_door_within_existing_doorway",
        "apply_decorative_column_treatment",
        "finish_balcony_within_existing_boundaries",
        "replace_requested_facade_surface_material",
    }
    block = effective["instruction_block"]
    assert "Install requested windows, frames and glazing" in block
    assert "Install requested doors and frames" in block
    assert "non-structural cladding and capitals" in block
    assert "Finish existing balconies and terraces" in block
    assert "Final facade finish: refined cream travertine" in block
    assert effective["instruction_applied"] is True
    assert effective["instruction_truncated"] is False
    assert instruction["constraint_block"] == block


def test_02_structural_geometry_remains_protected_in_text_and_metadata():
    _, _, instruction, effective = _path()
    handoff = _handoff(instruction)
    assert {"structural_grid", "floor_count", "roof_geometry", "building_massing"} <= (
        _scope_ids(handoff["protected_architecture"])
    )
    block = effective["instruction_block"]
    assert "never relocate or resize columns" in block
    assert "create unsupported structural members" in block
    assert {"relocate_structural_columns", "resize_structural_columns"} <= set(
        handoff["forbidden_geometric_operations"]
    )


def test_03_openings_may_be_finished_but_not_created_relocated_or_enlarged():
    _, _, instruction, effective = _path()
    forbidden = set(_handoff(instruction)["forbidden_geometric_operations"])
    assert {
        "create_new_window_openings", "relocate_window_openings",
        "enlarge_window_openings", "create_new_door_openings",
        "relocate_doorways", "enlarge_doorways",
    } <= forbidden
    block = effective["instruction_block"]
    assert "inside existing openings only" in block
    assert "never create, relocate or enlarge openings" in block


def test_04_raw_source_masonry_does_not_override_requested_cladding():
    _, _, instruction, effective = _path()
    transition = _handoff(instruction)["material_transition"]
    assert transition["requested_finish_material"]["id"] == "travertine"
    assert transition["source_construction_material_is_mandatory_final_finish"] is False
    assert transition["existing_construction_materials"][0]["id"] == (
        "exposed brick and block masonry"
    )
    assert "construction context, not a required final finish" in (
        effective["instruction_block"]
    )


def test_05_refined_cream_travertine_is_not_a_rustic_positive_instruction():
    _, _, instruction, effective = _path()
    requirements = _handoff(instruction)["material_style_requirements"]
    assert requirements["material"]["id"] == "travertine"
    assert {"refined", "cream"} <= set(requirements["appearance_qualifiers"])
    assert "Final facade finish: refined cream travertine" in (
        effective["instruction_block"]
    )
    assert "rustic" not in effective["instruction_block"].lower()

    explicit_exclusion = (
        "Reject rustic block stone. Design a refined restrained neoclassical "
        "facade in cream travertine. Complete windows inside existing openings."
    )
    _, _, excluded_instruction, excluded_effective = _path(explicit_exclusion)
    excluded = _handoff(excluded_instruction)["material_style_requirements"][
        "excluded_material_expressions"
    ]
    assert "rustic_block_stone" in excluded
    assert "Exclude these material interpretations: rustic block stone" in (
        excluded_effective["instruction_block"]
    )


def test_06_protected_context_survives_into_the_effective_instruction():
    _, _, instruction, effective = _path()
    assert {"courtyard", "retaining_walls", "adjacent_buildings"} <= _scope_ids(
        _handoff(instruction)["protected_context"]
    )
    assert (
        "Keep this context outside the design scope: courtyard, retaining walls, "
        "adjacent buildings."
    ) in effective["instruction_block"]


def test_07_negated_completion_does_not_become_an_allowed_instruction():
    text = (
        "نمای ساختمان را با تراورتن کرم بازطراحی کن. در و پنجره‌ها را داخل "
        "بازشوهای موجود نصب نکن. سازه و بازشوها را تغییر نده."
    )
    _, _, instruction, effective = _path(text)
    ids = _operation_ids(instruction)
    assert "complete_windows_within_existing_openings" not in ids
    assert "install_door_within_existing_doorway" not in ids
    assert "Install requested windows" not in effective["instruction_block"]
    assert "Install requested doors" not in effective["instruction_block"]


def test_08_provenance_and_uncertainty_survive_without_promotion():
    _, _, instruction, effective = _path()
    handoff = _handoff(instruction)
    assert all(
        item["grounding_category"] == "user_specified"
        and item["verification_status"] == "REQUESTED_NOT_EXECUTED"
        for item in handoff["allowed_operations"]
    )
    source = handoff["material_transition"]["existing_construction_materials"]
    assert source[0]["grounding_category"] == "model_reported_but_unverified"
    assert source[0]["verification_status"] == "UNVERIFIED"
    assert "remain UNVERIFIED" in effective["instruction_block"]
    json.dumps(instruction, ensure_ascii=False)


def test_09_no_mask_coordinates_segmentation_or_hard_authority_is_invented():
    _, _, instruction, _ = _path()
    handoff = _handoff(instruction)
    assert handoff["spatial_authority"] == {
        "status": "SEMANTIC_ONLY_NOT_SPATIALLY_VERIFIED",
        "mask": None,
        "pixel_coordinates": None,
        "segmentation": None,
    }
    assert handoff["hard_preservation_claimed"] is False


def test_10_insufficient_capability_and_r4_fail_closed_truth_survive():
    _, decision, instruction, effective = _path()
    intent = _intent(decision)
    handoff = _handoff(instruction)
    assert handoff["preservation_capability_status"] == (
        "PRESERVATION_CAPABILITY_INSUFFICIENT"
    )
    assert "semantic guidance only, with no hard-preservation guarantee" in (
        effective["instruction_block"]
    )
    assert intent["automatic_r4_approval"] is False
    assert intent["render_executed"] is False
    assert intent["comfy_invoked"] is False
    assert handoff["render_executed"] is False
    assert instruction["provenance"]["architectural_completion_consumed"] is True


def test_11_ordinary_image_edit_and_chat_contracts_remain_compatible():
    _, decision, instruction, effective = _path("Make the facade lighting warmer.")
    assert decision["editable_elements"] == ["lighting", "atmosphere"]
    assert _intent(decision)["architectural_completion"]["status"] == "NOT_REQUESTED"
    assert instruction["architectural_completion_handoff"] == {}
    assert instruction["provenance"]["architectural_completion_consumed"] is False
    assert "completion operations" not in effective["instruction_block"]
    assert "Apply the requested change only to the image-supported targets: " in (
        effective["instruction_block"]
    )
    assert "lighting, atmosphere" in effective["instruction_block"]

    public = ResponseAdapter().adapt({
        "status": "success", "type": "chat", "result": "سلام",
    })
    assert public["result"] == "سلام"
    assert "architectural_completion_handoff" not in public
