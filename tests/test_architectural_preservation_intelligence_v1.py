"""Focused CPU acceptance for ArchitecturalPreservationIntentV1."""

import json

from core.prompt_intelligence.architectural_preservation_intent_v1 import (
    CAPABILITY_INSUFFICIENT,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


REQUEST = (
    "Design a restrained neoclassical facade for this unfinished building "
    "using cream travertine with subtle stone texture, not rustic block stone. "
    "Preserve the existing structural frame, original floor count, opening "
    "positions, ground-floor openness, balcony and terrace boundaries, roof "
    "geometry, massing and camera perspective. Do not change the courtyard, "
    "foreground ground surfaces, retaining walls, neighbouring buildings or "
    "surrounding site layout. Do not copy arches or a pediment from the style "
    "reference."
)

IMAGE_UNDERSTANDING = {
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
                "element": "windows",
                "kind": ["window", "opening"],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Window openings are reported.",
            },
            {
                "element": "structural frame",
                "kind": ["structure"],
                "evidence_class": "DIRECTLY_OBSERVED",
                "verification_status": "VERIFIED",
                "source_quote": "Verified source-bound observation.",
            },
        ],
    },
}

LAST_EXPERIMENT = {
    "reference": "DUAL_SUPERVISED_GPU_PARTIAL — ONE_GPU",
    "demonstrated": [
        "improved_overall_massing_and_floor_count",
        "improved_structural_grid_continuity",
    ],
    "failed_or_drifted": [
        "railings_and_infill_changed",
        "roof_and_parapet_drift",
        "courtyard_repaved",
        "retaining_walls_changed",
        "neighbouring_buildings_changed",
        "rough_beige_stone_not_subtle_cream_travertine",
    ],
    "visual_acceptance": "PARTIAL_NOT_PRESERVATION_PROOF",
}

SOFT_DUAL_CAPABILITIES = {
    "source_bound_editing": True,
    "soft_depth_guidance": True,
    "style_reference_conditioning": True,
    "prompt_conditioning": True,
    "evidence": {"source_bound_editing": "dual graph Image B source latent"},
}


def _decision(text=REQUEST, *, understanding=IMAGE_UNDERSTANDING, context=None):
    return resolve_design_decision(
        user_text=text,
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=understanding,
        preserve_geometry=True,
        preserve_constraints=(
            "number_of_floors", "overall_massing", "building_silhouette",
            "main_window_positions", "main_door_positions", "roofline",
        ),
        design_context=context or {
            "preservation_workflow_capabilities": SOFT_DUAL_CAPABILITIES,
            "preservation_experiment_evidence": LAST_EXPERIMENT,
        },
    )


def _intent(decision=None):
    return (decision or _decision())["architectural_preservation_intent"]


def _ids(scope, decision=None):
    return {item["id"] for item in _intent(decision)["scopes"][scope]}


def test_01_style_only_facade_redesign_has_one_semantic_design_scope():
    decision = _decision()
    intent = _intent(decision)
    assert decision["requested_operation"]["operation"] == "restyle"
    assert _ids("design_target", decision) == {"main_facade_surface_expression"}
    target = intent["scopes"]["design_target"][0]
    assert target["verification_status"] == "SEMANTIC_TARGET_NOT_SPATIALLY_VERIFIED"


def test_02_to_05_building_identity_requirements_are_protected_not_editable():
    ids = _ids("protected_architecture")
    assert "floor_count" in ids
    assert "structural_grid" in ids
    assert "windows_and_openings" in ids
    assert "balcony_and_terrace_boundaries" in ids
    assert not ids.intersection(_ids("design_target"))


def test_06_to_08_external_site_is_a_required_protected_scope():
    ids = _ids("protected_context")
    assert {
        "courtyard", "foreground_ground_surfaces", "retaining_walls",
        "adjacent_buildings", "surrounding_site_layout",
    } <= ids
    assert all(
        item["grounding_category"] == "user_specified"
        and item["verification_status"] == "REQUIREMENT_NOT_OBSERVATION"
        for item in _intent()["scopes"]["protected_context"]
    )


def test_09_style_reference_geometry_is_forbidden_not_a_target():
    forbidden = " ".join(_intent()["forbidden_transformations"]).lower()
    targets = _ids("design_target")
    assert "arches" in forbidden or "pediment" in forbidden
    assert "arches" not in targets
    assert "pediment" not in targets


def test_10_material_language_is_specific_and_rejects_rustic_block_stone():
    requirements = _intent()["material_style_requirements"]
    assert requirements["style"]["id"] == "neoclassical"
    assert requirements["material"]["id"] == "travertine"
    assert {"restrained", "cream", "subtle_stone_texture"} <= set(
        requirements["appearance_qualifiers"]
    )
    assert "rustic_block_stone" in requirements["excluded_material_expressions"]


def test_11_verified_and_model_reported_observations_remain_distinct():
    evidence = {item["id"]: item for item in _intent()["evidence_register"]}
    assert evidence["facade wall"]["grounding_category"] == "model_reported_but_unverified"
    assert evidence["facade wall"]["verification_status"] == "UNVERIFIED"
    assert evidence["structural frame"]["grounding_category"] == "directly_observed"
    assert evidence["structural frame"]["verification_status"] == "VERIFIED"


def test_11b_model_reported_cannot_be_promoted_by_a_verified_status_label():
    understanding = json.loads(json.dumps(IMAGE_UNDERSTANDING))
    understanding["element_evidence"]["elements"][0]["verification_status"] = "VERIFIED"
    evidence = {
        item["id"]: item for item in _intent(_decision(understanding=understanding))[
            "evidence_register"
        ]
    }
    assert evidence["facade wall"]["grounding_category"] == "model_reported_but_unverified"
    assert evidence["facade wall"]["verification_status"] == "UNVERIFIED"


def test_12_no_mask_segmentation_or_pixel_coordinates_are_invented():
    spatial = _intent()["spatial_authority"]
    assert spatial == {
        "status": "UNKNOWN", "mask": None,
        "pixel_coordinates": None, "segmentation": None,
    }


def test_13_soft_depth_and_prompt_conditioning_fail_closed_truthfully():
    capability = _intent()["preservation_capability"]
    assert capability["status"] == CAPABILITY_INSUFFICIENT
    assert capability["enforceable"] is False
    assert "protected_context_pixel_enforcement" in capability["missing_capabilities"]
    assert capability["truth_constraints"] == {
        "prompt_only_is_hard_preservation": False,
        "soft_depth_is_exact_geometry_lock": False,
        "node_wiring_is_visual_acceptance": False,
    }
    assert _intent()["automatic_r4_approval"] is False


def test_13b_last_real_experiment_is_regression_evidence_not_acceptance():
    evidence = _intent()["experiment_evidence"]
    assert evidence == LAST_EXPERIMENT
    assert "courtyard_repaved" in evidence["failed_or_drifted"]
    assert evidence["visual_acceptance"] == "PARTIAL_NOT_PRESERVATION_PROOF"


def test_14_ordinary_architectural_observation_decision_is_additive_only():
    text = "Make the facade lighting warmer."
    decision = _decision(text)
    assert decision["editable_elements"] == ["lighting", "atmosphere"]
    assert decision["architectural_preservation_intent"]["contract"] == (
        "ArchitecturalPreservationIntentV1"
    )
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"


def test_15_existing_r4_decision_status_is_not_changed_or_auto_approved():
    decision = _decision()
    intent = _intent(decision)
    assert decision["contract"] == "GeometryAuthorityHandoffV1"
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert intent["preservation_capability"]["status"] == CAPABILITY_INSUFFICIENT
    assert intent["automatic_r4_approval"] is False
    assert intent["render_executed"] is False
    assert intent["comfy_invoked"] is False


def test_contract_is_deterministic_and_json_safe():
    first = _intent()
    second = _intent()
    assert first == second
    json.dumps(first, ensure_ascii=False)

