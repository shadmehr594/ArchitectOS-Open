"""CPU acceptance for resolved instruction binding in the dual runner.

The real A/B files and canonical workflow are hashed and the actual graph is
built. Models are represented by an identity-ready test double. No staging,
permit, lease, transport, network, GPU, ComfyUI or production asset path runs.
"""

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from core.chat.chat_architect import _r4_acceptance_record
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.render.dual_supervised_experiment_v1 import (
    DEFAULT_PROMPT,
    FIXED_PROFILE,
    NEGATIVE_PROMPT,
    WORKFLOW_SHA256,
    ExperimentBlocked,
    InputSpec,
    canonical_sha256,
    cpu_preflight,
    file_sha256,
    text_sha256,
)
from tools.run_dual_supervised_experiment_v1 import (
    load_architectural_instruction,
)


ROOT = Path(__file__).resolve().parents[1]
IMAGE_A = Path(os.environ.get("ARCHITECTOS_TEST_IMAGE_A", str(ROOT / "tests" / "assets" / "sample_a.jpg")))
IMAGE_B = (
    ROOT / "uploads" / "chat_media"
    / "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg"
)
WORKFLOW = (
    ROOT / "core" / "render" / "workflows"
    / "flux_img2img_dual_conditioned.json"
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
        "source_image": {"image_id": "target-building", "sha256": "8" * 64},
        "elements": [
            {
                "element": "facade wall", "kind": ["wall"],
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
                "source_quote": "Existing openings are reported.",
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


def models_ready(**_):
    return {
        "status": "ready", "hash_verified": False,
        "present": {"all": True}, "missing": [], "invalid": [],
    }


def resolved_instruction():
    delta = compile_edit_delta(PERSIAN_REQUEST, image_edit=True)
    decision = resolve_design_decision(
        user_text=PERSIAN_REQUEST,
        edit_delta=delta,
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
                "evidence": {"source_bound_editing": "Image B source latent"},
            },
        },
    )
    return decision_instruction_block(decision)


def _preflight(instruction=None):
    return cpu_preflight(
        InputSpec(str(IMAGE_A), str(IMAGE_B)),
        str(WORKFLOW),
        profile=FIXED_PROFILE,
        model_verifier=models_ready,
        architectural_instruction=instruction,
    )


@pytest.fixture(scope="module")
def bound():
    instruction = resolved_instruction()
    evidence, graph = _preflight(instruction)
    return instruction, evidence, graph


@pytest.fixture(scope="module")
def legacy():
    evidence, graph = _preflight()
    return evidence, graph


def test_01_actual_resolved_instruction_reaches_node_206(bound):
    instruction, evidence, graph = bound
    binding = evidence["instruction_binding"]
    assert binding["instruction_bound"] is True
    assert binding["source_contract"] == "RenderConstraintBlockV1"
    assert binding["instruction_truncated"] is False
    assert instruction["constraint_block"] in graph["206"]["inputs"]["text"]
    assert graph["206"]["inputs"]["text"] == (
        binding["effective_positive_instruction"]
    )
    assert binding["effective_positive_instruction_sha256"] == text_sha256(
        graph["206"]["inputs"]["text"]
    )


def test_02_explicit_completion_operations_survive_in_node_206(bound):
    _, evidence, graph = bound
    ids = set(
        evidence["instruction_binding"]["architectural_completion_handoff"][
            "allowed_operation_ids"
        ]
    )
    assert ids == {
        "complete_windows_within_existing_openings",
        "install_door_within_existing_doorway",
        "apply_decorative_column_treatment",
        "finish_balcony_within_existing_boundaries",
        "replace_requested_facade_surface_material",
    }
    text = graph["206"]["inputs"]["text"]
    assert "Install requested windows, frames and glazing" in text
    assert "Install requested doors and frames" in text
    assert "non-structural cladding and capitals" in text
    assert "Finish existing balconies and terraces" in text
    assert "Final facade finish: refined cream travertine" in text


def test_03_protected_geometry_and_site_constraints_survive(bound):
    _, evidence, graph = bound
    handoff = evidence["instruction_binding"]["architectural_completion_handoff"]
    protected = {item["id"] for item in handoff["protected_architecture"]}
    context = {item["id"] for item in handoff["protected_context"]}
    assert {"floor_count", "structural_grid", "windows_and_openings", "roof_geometry"} <= protected
    assert {"courtyard", "retaining_walls", "adjacent_buildings"} <= context
    text = graph["206"]["inputs"]["text"]
    assert "Keep protected building geometry" in text
    assert "courtyard, retaining walls, adjacent buildings" in text


def test_04_negative_requirements_remain_prohibitions(bound):
    _, evidence, graph = bound
    positive = graph["206"]["inputs"]["text"]
    assert "never create, relocate or enlarge openings" in positive
    assert "never relocate or resize columns" in positive
    assert "never add, relocate or extend balconies" in positive
    assert graph["212"]["inputs"]["text"] == NEGATIVE_PROMPT
    assert evidence["instruction_binding"]["negative_instruction"] == NEGATIVE_PROMPT
    assert evidence["instruction_binding"]["negative_instruction_sha256"] == text_sha256(
        NEGATIVE_PROMPT
    )


def test_05_original_a_b_role_bindings_are_unchanged(bound):
    _, evidence, graph = bound
    names = evidence["planned_staged_filenames"]
    assert evidence["inputs"]["image_a"]["authority"] == "style_only"
    assert evidence["inputs"]["image_b"]["authority"] == "geometry"
    assert graph["302"]["inputs"]["image"] == names["image_a"]
    assert graph["300"]["inputs"]["image"] == names["image_b"]
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["306"]["inputs"]["image"] == ["300", 0]


def test_06_canonical_workflow_identity_is_unchanged(bound):
    _, evidence, _ = bound
    assert file_sha256(str(WORKFLOW)) == WORKFLOW_SHA256
    assert evidence["workflow"]["sha256"] == (
        "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"
    )


def test_07_profile_sampler_and_controlnet_are_unchanged(bound):
    _, evidence, graph = bound
    assert evidence["profile_sha256"] == (
        "cf56c73cc759af68cc2bedf948a66306d478e59b3e9852037f97e45629b2a73c"
    )
    sampler = graph["210"]["inputs"]
    assert (sampler["steps"], sampler["cfg"], sampler["denoise"], sampler["seed"]) == (
        30, 5.0, 0.30, 20261030,
    )
    assert (sampler["sampler_name"], sampler["scheduler"]) == ("euler", "simple")
    control = graph["311"]["inputs"]
    assert (control["strength"], control["start_percent"], control["end_percent"]) == (
        0.8, 0.0, 0.8,
    )


def test_08_effective_graph_hash_changes_deterministically_with_instruction(bound, legacy):
    instruction, evidence, graph = bound
    legacy_evidence, legacy_graph = legacy
    assert evidence["effective_graph_sha256"] == canonical_sha256(graph)
    assert legacy_evidence["effective_graph_sha256"] == canonical_sha256(legacy_graph)
    assert evidence["effective_graph_sha256"] != legacy_evidence["effective_graph_sha256"]
    second_evidence, second_graph = _preflight(deepcopy(instruction))
    assert second_evidence["effective_graph_sha256"] == evidence["effective_graph_sha256"]
    assert second_graph["206"]["inputs"]["text"] == graph["206"]["inputs"]["text"]


def test_09_legacy_cpu_runner_and_cli_contract_loading_remain_compatible(legacy, tmp_path):
    evidence, graph = legacy
    assert graph["206"]["inputs"]["text"] == DEFAULT_PROMPT
    assert evidence["effective_graph_sha256"] == (
        "7b6a21f9ac92a00eb2b2f4adbcf4a917400eda05e1bdfe3c17abcbbffea28a9b"
    )
    assert evidence["instruction_binding"]["mode"] == "DEFAULT_PROMPT"

    path = tmp_path / "instruction.json"
    instruction = resolved_instruction()
    path.write_text(json.dumps(instruction, ensure_ascii=False), encoding="utf-8")
    assert load_architectural_instruction(str(path)) == instruction

    bad = tmp_path / "bad.json"
    bad.write_text('{"contract":"not-approved"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="INVALID_ARCHITECTURAL_INSTRUCTION"):
        load_architectural_instruction(str(bad))


def test_10_production_r4_remains_fail_closed(bound):
    _, evidence, _ = bound
    completion = evidence["instruction_binding"]["architectural_completion_handoff"]
    assert completion["preservation_capability_status"] == (
        "PRESERVATION_CAPABILITY_INSUFFICIENT"
    )
    assert completion["hard_preservation_claimed"] is False
    record = _r4_acceptance_record("flux_img2img_dual_conditioned.json")
    assert record["accepted"] is False


def test_11_cpu_preflight_cannot_submit_or_consume_a_permit(bound):
    _, evidence, _ = bound
    assert evidence["mode"] == "CPU_PREFLIGHT"
    assert evidence["nonexecuting"] is True
    assert evidence["permit"] == {"identity": None, "state": "NOT_ISSUED"}
    assert evidence["leases"] == {"gpu_render": "NOT_ACQUIRED", "comfyui": "NOT_ACQUIRED"}
    assert evidence["submission_attempt_count"] == 0
    assert evidence["prompt_id"] is None
    assert evidence["zero_external_work"] == {
        "gpu_jobs": 0, "comfyui_submissions": 0,
        "ollama_inference": 0, "production_chat_posts": 0,
    }


def test_12_no_production_asset_or_acceptance_record_is_created(bound):
    _, evidence, _ = bound
    assert evidence["production_asset_registered"] is False
    assert evidence["visual_review_status"] == "NOT_REVIEWED"
    assert evidence["preservation_status"] == "UNVERIFIED"
    assert evidence["production_r4_admission_changed"] is False
    assert evidence["output"] is None


def test_invalid_or_spatially_promoted_instruction_is_refused_before_graph():
    instruction = resolved_instruction()
    promoted = deepcopy(instruction)
    promoted["architectural_completion_handoff"]["spatial_authority"]["mask"] = "fake"
    with pytest.raises(ExperimentBlocked, match="spatial_authority_invalid"):
        _preflight(promoted)

