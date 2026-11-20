# ==========================================================
# PHASE 2D-6 — PLAN / APPROVED DESIGN → RENDER CONTRACT
# Contract only: no render execution, no ComfyUI, no design mutation.
# ==========================================================

import copy
import inspect
import json

from core.prompt_intelligence.approved_design_render_contract_v1 import (
    CONTRACT,
    VERSION,
    FORBIDDEN_GEOMETRY_CHANGES,
    ApprovedDesignRenderContractV1,
    ApprovedDesignRenderContractBuilder,
    build_render_contract,
)
from core.prompt_intelligence.persian_architectural_understanding import understand


APPROVED = {
    "approval_status": True,
    "design_status": "approved",
    "project_state": "APPROVED",
    "last_design": {"type": "villa"},
    "last_architectural_intent": {"style": "modern"},
    "approved_design_id": "D-1",
    "approved_candidate_id": "C-7",
    "approved_candidate_version": "3",
    "approved_candidate_hash": "abc123",
    "design_source_type": "approved_bim_design",
}

NOT_APPROVED = {
    "approval_status": False,
    "design_status": "waiting_approval",
    "project_state": "WAITING_APPROVAL",
    "last_design": {"type": "villa"},
}


def _build(state, text=None, **kw):
    understanding = understand(text) if text else None
    return build_render_contract(state, understanding=understanding, **kw)


# ==========================================================
# A / B / C — approval gate
# ==========================================================

def test_A_approved_ready_with_exact_lineage():
    c = _build(APPROVED, "نما مدرن‌تر شه")
    assert isinstance(c, ApprovedDesignRenderContractV1)
    assert c["status"] == "READY"
    assert c["approved_candidate_id"] == "C-7"
    assert c["approved_candidate_version"] == "3"
    assert c["approved_candidate_hash"] == "abc123"
    assert c["lineage"]["lineage_complete"] is True


def test_B_no_approved_design():
    c = _build(NOT_APPROVED)
    assert c["status"] == "APPROVAL_REQUIRED"
    assert c["approval_status"] is False
    assert c["approved_candidate_id"] is None
    assert c["authoritative_geometry_source"] is None
    assert c["render_intent"] == {}
    assert _build({})["status"] == "NO_APPROVED_DESIGN"


def test_C_recent_candidate_not_approved():
    c = _build({"approval_status": False, "design_status": "none", "last_design": {"type": "villa"}})
    assert c["status"] == "APPROVAL_REQUIRED"
    assert c["approval_provenance"]["reason"] == "design_not_approved"


# ==========================================================
# D / E / F / G — allowed vs forbidden changes
# ==========================================================

def test_D_material_change_allowed_geometry_preserved():
    c = _build(APPROVED, "سنگش روشن‌تر شه")
    assert c["status"] == "READY"
    assert c["preserve_constraints"]["massing"] is True
    assert c["preserve_constraints"]["geometry"] is True
    assert "facade_materials" in c["allowed_render_changes"]
    assert c["render_intent"]["materials"]["primary"] == "stone"


def test_E_add_floor_requires_design_revision():
    c = _build(APPROVED, "یه طبقه اضافه کن")
    assert c["status"] == "DESIGN_REVISION_REQUIRED"
    assert "add_floor" in c["forbidden_geometry_changes"]
    assert c["render_intent"] == {}


def test_F_move_windows_requires_design_revision():
    c = _build(APPROVED, "پنجره‌ها رو جابه‌جا کن")
    assert c["status"] == "DESIGN_REVISION_REQUIRED"
    assert "move_primary_openings" in c["forbidden_geometry_changes"]


def test_F2_window_frame_expression_is_not_a_design_revision():
    c = _build(APPROVED, "قاب پنجره‌ها ظریف‌تر شه")
    assert c["status"] == "READY"
    assert "window_frame_expression" in c["allowed_render_changes"]


def test_G_lighter_stone_allowed():
    c = _build(APPROVED, "سنگش روشن‌تر شه")
    assert c["status"] == "READY"
    assert c["forbidden_geometry_changes"] == list(FORBIDDEN_GEOMETRY_CHANGES)


def test_plan_change_requires_design_revision():
    c = _build(APPROVED, "پلان رو عوض کن")
    assert c["status"] == "DESIGN_REVISION_REQUIRED"


# ==========================================================
# H / I / J — reference interaction
# ==========================================================

def test_H_material_only_reference_keeps_design_authority():
    c = _build(APPROVED, "از این عکس فقط متریالش رو بگیر")
    assert c["authoritative_geometry_source"] == "APPROVED_DESIGN"
    ref = c["render_intent"]["reference_policy"]
    assert ref["role"] == "material_only"
    assert ref["reference_material_source"] is True
    assert ref["reference_style_transfer"] is False


def test_I_style_only_reference_does_not_copy_geometry():
    c = _build(APPROVED, "سبکش مثل این عکس باشه")
    ref = c["render_intent"]["reference_policy"]
    assert ref["role"] == "style_only"
    assert ref["reference_style_transfer"] is True
    assert ref["reference_geometry_copy"] is False
    assert c["authoritative_geometry_source"] == "APPROVED_DESIGN"


def test_J_copy_reference_geometry_false_never_authoritative():
    c = _build(APPROVED, "مثل این عکس باشه ولی فرمش رو کپی نکن")
    assert c["render_intent"]["reference_policy"]["reference_geometry_copy"] is False
    assert c["authoritative_geometry_source"] == "APPROVED_DESIGN"


def test_reference_never_swaps_design_authority():
    """A = approved design, B = reference image; A must remain authoritative."""
    c = _build(APPROVED, "از این عکس فقط متریالش رو بگیر")
    assert c["authoritative_geometry_source"] == "APPROVED_DESIGN"
    assert c["approved_candidate_id"] == "C-7"


# ==========================================================
# K / L — render modes
# ==========================================================

def test_K_image_edit_base_image_authoritative():
    c = _build({**APPROVED, "base_image_id": "IMG-9", "base_image_hash": "h9"}, "نما مدرن‌تر شه")
    assert c["render_mode"] == "IMAGE_EDIT"
    assert c["authoritative_geometry_source"] == "APPROVED_BUILDING_IMAGE"


def test_L_text_to_image_no_false_preserve_language():
    c = _build(APPROVED, "نما مدرن‌تر شه", mode="TEXT_TO_IMAGE")
    assert c["render_mode"] == "TEXT_TO_IMAGE"
    assert c["authoritative_geometry_source"] == "APPROVED_DESIGN"
    blob = json.dumps(c, ensure_ascii=False).lower()
    assert "uploaded" not in blob
    assert "base building image" not in blob


def test_design_visualization_when_plan_without_facade_image():
    c = _build(APPROVED, "نما مدرن‌تر شه")
    assert c["render_mode"] in ("DESIGN_VISUALIZATION", "FACADE_REFINEMENT")
    assert "approved_facade_geometry" in c["required_context"]


# ==========================================================
# M — lineage gaps
# ==========================================================

def test_M_lineage_gap_structured_not_invented():
    c = _build({**APPROVED, "approved_candidate_version": None, "approved_candidate_hash": None},
               "سنگش روشن‌تر شه")
    assert c["status"] == "READY_WITH_WARNINGS"
    assert c["approved_candidate_version"] is None
    assert c["approved_candidate_hash"] is None
    assert any(w["code"] == "DESIGN_LINEAGE_INCOMPLETE" for w in c["warnings"])
    assert "approved_candidate_version" in c["unresolved_requirements"]


def test_M_strict_lineage_mode():
    c = _build({**APPROVED, "approved_candidate_hash": None}, require_full_lineage=True)
    assert c["status"] == "DESIGN_LINEAGE_INCOMPLETE"


# ==========================================================
# N — compiled prompt conflict
# ==========================================================

def test_N_compiled_prompt_conflict_preserve_wins():
    compiled = {
        "contract": "ArchitecturalCompiledPromptV1",
        "version": "1.0",
        "status": "COMPILED",
        "deterministic_hash": "x",
        "change_instructions": ["Replace the windows."],
        "preservation_instructions": ["Preserve the current window locations."],
    }
    c = _build(APPROVED, "پنجره‌ها همین بمونه", compiled_prompt=compiled)
    assert c["conflicts"], "conflict must be recorded"
    assert c["conflicts"][0]["resolution"] == "preservation_authoritative"
    assert c["preserve_constraints"]["windows"] is True
    assert c["status"] == "READY_WITH_WARNINGS"


# ==========================================================
# O — determinism / hashing
# ==========================================================

def test_O_deterministic_hash_and_round_trip():
    a = _build(APPROVED, "سنگش روشن‌تر شه")
    b = _build(APPROVED, "سنگش روشن‌تر شه")
    assert a["contract_hash"] == b["contract_hash"]
    assert len(a["contract_hash"]) == 64
    assert json.loads(json.dumps(a, ensure_ascii=False)) == a


def test_O_render_hash_distinct_from_design_hash():
    c = _build(APPROVED, "سنگش روشن‌تر شه")
    assert c["contract_hash"] != c["approved_candidate_hash"]
    assert c["approved_candidate_hash"] == "abc123"  # preserved, not recomputed


def test_contract_identity_and_fields():
    c = _build(APPROVED, "سنگش روشن‌تر شه")
    assert c["contract"] == CONTRACT
    assert c["version"] == VERSION
    for key in (
        "contract", "version", "status", "session_id", "project_id",
        "approved_design_id", "approved_candidate_id", "approved_candidate_version",
        "approved_candidate_hash", "approval_status", "approval_timestamp_or_marker",
        "approval_provenance", "design_source_type", "plan_reference",
        "geometry_reference", "image_reference", "authoritative_geometry_source",
        "preserve_constraints", "allowed_render_changes", "forbidden_geometry_changes",
        "architectural_understanding", "compiled_prompt_reference",
        "reference_image_policy", "reference_architectural_analysis",
        "render_mode", "render_intent", "required_context", "unresolved_requirements",
        "warnings", "conflicts", "lineage", "provenance", "contract_hash",
    ):
        assert key in c, key


# ==========================================================
# §24 / §25 / §26 / §28
# ==========================================================

def test_new_approved_candidate_rebinds():
    old = _build(APPROVED, "سنگش روشن‌تر شه")
    new_state = {**APPROVED, "approved_candidate_id": "C-8", "approved_candidate_hash": "def456"}
    new = _build(new_state, "سنگش روشن‌تر شه")
    assert old["approved_candidate_id"] == "C-7"
    assert new["approved_candidate_id"] == "C-8"
    assert new["approved_candidate_hash"] == "def456"
    assert new["contract_hash"] != old["contract_hash"]


def test_only_approved_candidate_becomes_authority():
    state = {**APPROVED, "candidate_pool": ["C-1", "C-2", "C-7"]}
    c = _build(state, "سنگش روشن‌تر شه")
    assert c["approved_candidate_id"] == "C-7"


def test_presentation_only_when_present():
    c = _build(APPROVED, "سنگش روشن‌تر شه")
    assert c["render_intent"]["presentation"] == {}
    c2 = _build(APPROVED, "سنگش روشن‌تر شه", context={"lighting_preference": "golden hour"})
    assert c2["render_intent"]["presentation"]["lighting_preference"] == "golden hour"


def test_reference_unavailable_warning():
    analysis = {"contract": "ReferenceArchitecturalAnalysisV1", "analysis_status": "PROVIDER_UNAVAILABLE",
                "analysis_hash": "z"}
    c = _build(APPROVED, "از این عکس فقط متریالش رو بگیر", reference_analysis=analysis)
    assert any(w["code"] == "REFERENCE_IMAGE_NOT_ANALYZED" for w in c["warnings"])
    assert c["status"] in ("READY", "READY_WITH_WARNINGS")


# ==========================================================
# P / Q — isolation and purity
# ==========================================================

def test_P_no_render_or_generation_side_effect():
    source = inspect.getsource(
        inspect.getmodule(ApprovedDesignRenderContractBuilder)
    ).lower()
    for forbidden in (
        "import requests", "from core.render", "import comfy", "from comfy",
        "comfyui_bridge", "render_runtime(", "text2img(", "img2img(",
        "workflow_executor",
    ):
        assert forbidden not in source, forbidden


def test_Q_builder_is_pure_no_design_mutation():
    state = copy.deepcopy(APPROVED)
    snapshot = copy.deepcopy(state)
    builder = ApprovedDesignRenderContractBuilder()
    builder.build(state, understanding=understand("سنگش روشن‌تر شه"))
    assert state == snapshot, "builder must not mutate the approval/design state"
    source = inspect.getsource(inspect.getmodule(ApprovedDesignRenderContractBuilder)).lower()
    for forbidden in (".update(", ".setdefault(", ".pop(", ".clear(", "del state", "del approval_state"):
        assert forbidden not in source, forbidden


# ==========================================================
# R — regressions available
# ==========================================================

def test_R_2d1_to_2d5_still_work():
    from core.cognition.persian_normalizer import persian_normalizer
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
    from core.chat.architectural_conversation_context_v1 import ArchitecturalConversationContextMergerV1
    from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
        ReferenceImageArchitecturalUnderstandingV1,
    )

    assert persian_normalizer.normalize("نماي ۲")["normalized_text"] == "نمای 2"
    u = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert compile_prompt(u)["status"] == "COMPILED"
    merged = ArchitecturalConversationContextMergerV1().merge({}, u, raw_text="x", normalized_text="x")
    assert merged["contract"] == "ArchitecturalConversationContextV1"
    assert ReferenceImageArchitecturalUnderstandingV1().analyze(None)["analysis_status"] == "UNSUPPORTED_IMAGE"
