"""Focused CPU acceptance for architectural design-completion semantics.

This suite exercises the real GeometryAuthorityHandoffV1 decision owner and
the existing ResponseAdapter boundary.  It does not initialise providers,
renderers, ComfyUI, Ollama, GPU resources, masks or image generation.
"""

from copy import deepcopy
import json

from core.chat.response_adapter import ResponseAdapter
from core.prompt_intelligence.architectural_preservation_intent_v1 import (
    CAPABILITY_INSUFFICIENT,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


REQUEST = (
    "Reject rustic masonry. Redesign the main facade of this unfinished "
    "building in a refined, restrained neoclassical style with subtle texture "
    "in cream travertine. Complete the existing openings with windows, window "
    "frames and glazing. Install a door and door frame inside the existing "
    "doorway. Apply pilasters and capitals as decorative treatment to the "
    "existing structural columns. Finish existing balcony and terrace edges "
    "with balustrade details within the existing boundaries. Preserve the "
    "building massing, floor count, structural grid, opening positions and "
    "dimensions, balcony and terrace boundaries, roof geometry, and camera "
    "perspective. Do not create, relocate or enlarge openings. Do not move "
    "or resize structural columns. Do not add or relocate balconies. Do not "
    "change the courtyard, retaining walls, neighbouring buildings, ground "
    "surfaces or surrounding site layout."
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
                "element": "existing window openings",
                "kind": ["window", "opening"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Existing window openings are reported.",
            },
            {
                "element": "structural columns",
                "kind": ["column", "structure"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Structural columns are reported.",
            },
        ],
    },
}


def _decision(text=REQUEST):
    return resolve_design_decision(
        user_text=text,
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=deepcopy(UNDERSTANDING),
        preserve_geometry=True,
        preserve_constraints=(
            "number_of_floors", "overall_massing", "building_silhouette",
            "main_window_positions", "main_door_positions", "roofline",
        ),
        design_context={
            "preservation_workflow_capabilities": {
                "source_bound_editing": True,
                "soft_depth_guidance": True,
                "style_reference_conditioning": True,
                "evidence": {
                    "source_bound_editing": "Image B is the source latent",
                },
            },
        },
    )


def _intent(decision=None):
    return (decision or _decision())["architectural_preservation_intent"]


def _completion(intent=None):
    return (intent or _intent())["architectural_completion"]


def _operation_ids(intent=None):
    return {
        item["id"] for item in _completion(intent)["allowed_operations"]
    }


def _scope_ids(scope, intent=None):
    return {
        item["id"] for item in (intent or _intent())["scopes"][scope]
    }


def test_01_windows_may_be_completed_only_inside_existing_openings():
    intent = _intent()
    operation = next(
        item for item in _completion(intent)["allowed_operations"]
        if item["id"] == "complete_windows_within_existing_openings"
    )
    assert operation["target"] == "existing_window_openings"
    assert operation["geometry_change_authorized"] is False
    assert operation["spatial_status"] == "SEMANTIC_BOUNDARY_NOT_SPATIALLY_VERIFIED"
    assert "windows_and_openings" in _scope_ids("protected_architecture", intent)


def test_02_new_relocated_or_enlarged_openings_remain_forbidden():
    forbidden = set(_completion()["forbidden_geometric_operations"])
    assert {
        "create_new_window_openings", "relocate_window_openings",
        "enlarge_window_openings", "change_opening_structural_boundaries",
    } <= forbidden
    negative = _intent(_decision(
        "Preserve the existing openings. Do not install windows in the "
        "existing openings."
    ))
    assert "complete_windows_within_existing_openings" not in _operation_ids(negative)


def test_03_door_installation_is_bounded_to_the_existing_doorway():
    intent = _intent()
    assert "install_door_within_existing_doorway" in _operation_ids(intent)
    forbidden = set(_completion(intent)["forbidden_geometric_operations"])
    assert {"create_new_door_openings", "relocate_doorways", "enlarge_doorways"} <= forbidden


def test_04_columns_keep_structural_authority_while_treatment_is_allowed():
    intent = _intent()
    assert "apply_decorative_column_treatment" in _operation_ids(intent)
    assert "structural_grid" in _scope_ids("protected_architecture", intent)
    forbidden = set(_completion(intent)["forbidden_geometric_operations"])
    assert {
        "relocate_structural_columns", "resize_structural_columns",
        "create_unsupported_structural_members",
    } <= forbidden


def test_05_balcony_completion_does_not_authorize_new_geometry():
    intent = _intent()
    assert "finish_balcony_within_existing_boundaries" in _operation_ids(intent)
    assert "balcony_and_terrace_boundaries" in _scope_ids(
        "protected_architecture", intent
    )
    assert {"add_balconies", "relocate_balconies", "extend_balcony_boundaries"} <= set(
        _completion(intent)["forbidden_geometric_operations"]
    )


def test_06_existing_construction_material_is_not_forced_as_final_finish():
    transition = _completion()["material_transition"]
    assert transition["requested_finish_material"]["id"] == "travertine"
    assert transition["source_construction_material_is_mandatory_final_finish"] is False
    assert transition["interpretation"] == (
        "replace_observed_construction_surface_with_requested_finish"
    )
    source = transition["existing_construction_materials"]
    assert source and source[0]["id"] == "exposed brick and block masonry"
    assert source[0]["grounding_category"] == "model_reported_but_unverified"
    assert source[0]["verification_status"] == "UNVERIFIED"


def test_07_requested_material_is_refined_cream_not_rustic_masonry():
    requirements = _intent()["material_style_requirements"]
    assert requirements["style"]["id"] == "neoclassical"
    assert requirements["material"]["id"] == "travertine"
    assert {"refined", "restrained", "cream"} <= set(
        requirements["appearance_qualifiers"]
    )
    assert "rustic_block_stone" in requirements["excluded_material_expressions"]


def test_08_completion_is_separate_from_preservation_and_surface_targeting():
    intent = _intent()
    assert _completion(intent)["status"] == "REQUESTED"
    assert _completion(intent)["preserve_existing_geometry"] is True
    assert _completion(intent)["geometry_change_authorized"] is False
    assert _scope_ids("design_target", intent) == {"main_facade_surface_expression"}
    assert "replace_requested_facade_surface_material" in _operation_ids(intent)
    assert any(value.startswith("geometry:") for value in intent["forbidden_transformations"])


def test_09_unrelated_site_context_remains_protected():
    assert {
        "courtyard", "retaining_walls", "adjacent_buildings",
        "foreground_ground_surfaces", "surrounding_site_layout",
    } <= _scope_ids("protected_context")


def test_10_response_adapter_exposes_complete_contract_and_plain_summary():
    decision = _decision()
    public = ResponseAdapter().adapt({
        "status": "blocked",
        "type": "image_edit",
        "result": "Rendering was not started.",
        "architectural_design_decision": decision,
    })
    contract = public["architectural_preservation_intent"]
    summary = public["architectural_preservation_summary"]
    assert contract == decision["architectural_preservation_intent"]
    assert "تکمیل معماری مجاز:" in summary
    assert "نصب پنجره، قاب و شیشه درون بازشوهای موجود" in summary
    assert "اجرای پوشش، پیلستر یا سرستون روی ستون‌های موجود" in summary
    assert "فقط داخل هندسهٔ موجود" in summary
    assert "جابه‌جایی سازه مجاز نیست" in summary
    assert "معماری حفاظت‌شده:" in summary


def test_11_insufficient_capability_never_triggers_render_or_r4():
    intent = _intent()
    assert intent["preservation_capability"]["status"] == CAPABILITY_INSUFFICIENT
    assert _completion(intent)["execution_capability_status"] == CAPABILITY_INSUFFICIENT
    assert _completion(intent)["spatial_authority"] == {
        "status": "SEMANTIC_ONLY_NOT_SPATIALLY_VERIFIED",
        "mask": None, "pixel_coordinates": None, "segmentation": None,
    }
    assert intent["automatic_r4_approval"] is False
    assert intent["render_executed"] is False
    assert intent["comfy_invoked"] is False


def test_12_ordinary_noncompletion_decision_remains_compatible_and_json_safe():
    decision = _decision("Make the facade lighting warmer.")
    intent = decision["architectural_preservation_intent"]
    assert decision["editable_elements"] == ["lighting", "atmosphere"]
    assert intent["architectural_completion"]["status"] == "NOT_REQUESTED"
    assert intent["architectural_completion"]["allowed_operations"] == []
    assert intent["contract"] == "ArchitecturalPreservationIntentV1"
    json.dumps(intent, ensure_ascii=False)
