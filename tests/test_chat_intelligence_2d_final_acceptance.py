"""Final acceptance lock for the additive Chat Intelligence 2D stack.

This suite composes the public 2D-1 ... 2D-7 contracts without invoking the
legacy router, RenderRuntime, AutoCAD, BIM, IFC, or an external provider.
"""

from copy import deepcopy
import inspect
import json
from pathlib import Path
import re

import pytest

from core.chat.architectural_conversation_context_v1 import (
    ArchitecturalConversationContextMergerV1,
)
from core.chat.chat_input_adapter import ChatInputAdapter
from core.cognition.persian_normalizer import persian_normalizer
from core.prompt_intelligence.approved_design_render_contract_v1 import (
    build_render_contract,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
from core.prompt_intelligence.persian_architectural_understanding import (
    PersianArchitecturalUnderstandingEngine,
    understand,
)
from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
    ArchitecturalVisionProvider,
    ReferenceImageArchitecturalUnderstandingV1,
)
from core.prompt_intelligence.render_revision_delta_v1 import (
    build_render_revision_delta,
)


APPROVED = {
    "approval_status": True,
    "design_status": "approved",
    "project_state": "APPROVED",
    "last_design": {"type": "villa"},
    "approved_design_id": "D-FREEZE",
    "approved_candidate_id": "C-FREEZE",
    "approved_candidate_version": "1",
    "approved_candidate_hash": "design-hash",
    "design_source_type": "approved_bim_design",
}

ACTIVE_RENDER = {
    "active_render_id": "R-FREEZE",
    "active_render_hash": "render-hash",
}


def _request(text):
    return ChatInputAdapter().normalize(text)


def _turn(previous, text, context=None):
    request = _request(text)
    understanding = understand(request)
    merged = ArchitecturalConversationContextMergerV1().merge(
        previous,
        understanding,
        raw_text=request["raw_text"],
        normalized_text=request["normalized_text"],
        context=context,
    )
    return request, understanding, merged


def _effective(previous, text, context=None):
    request, understanding, merged = _turn(previous, text, context=context)
    effective = merged["active_architectural_understanding"]
    compiled = compile_prompt(effective) if merged["turn_has_architectural_signal"] else {}
    return request, understanding, merged, effective, compiled


def test_A_persian_request_flows_from_raw_input_to_professional_prompt():
    raw = "همين حجم و پنجره‌ها بمونه، فقط نما مدرن‌تر شه و سنگ روشن باشه"
    request, understanding, merged, effective, compiled = _effective({}, raw)

    assert request["raw_text"] == raw
    assert request["normalized_text"].startswith("همین حجم")
    assert understanding["normalized_text"] == request["normalized_text"]
    assert effective["preserve_constraints"]["massing"] is True
    assert effective["preserve_constraints"]["windows"] is True
    assert effective["style"]["target"] == "modern"
    assert effective["materials"]["primary"] == "stone"
    assert effective["materials"]["tone"] == "light"
    assert compiled["status"] == "COMPILED"
    assert "Preserve the existing building massing." in compiled["positive_prompt"]
    assert "Preserve the current window locations" in compiled["positive_prompt"]
    assert "contemporary" in compiled["positive_prompt"]
    assert "light natural stone" in compiled["positive_prompt"]
    assert not any("\u0600" <= char <= "\u06ff" for char in compiled["positive_prompt"])
    assert merged["turn_has_architectural_signal"] is True


def test_B_multi_turn_merge_carries_preserve_and_style_then_applies_material_delta():
    _, _, first, _, _ = _effective(
        {}, "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه"
    )
    _, _, second, effective, compiled = _effective(
        first, "خوبه فقط سنگش روشن‌تر شه"
    )

    assert second["active_preserve_constraints"] == {
        "massing": True,
        "windows": True,
    }
    assert second["active_style"]["target"] == "modern"
    assert second["active_materials"]["primary"] == "stone"
    assert second["active_materials"]["tone"] == "light"
    assert effective["style"]["target"] == "modern"
    assert "lighter natural stone tone" in compiled["positive_prompt"]

    repeated = _effective(first, "خوبه فقط سنگش روشن‌تر شه")[2]
    assert second["context_hash"] == repeated["context_hash"]


def test_C_latest_explicit_window_change_overrides_only_window_preservation():
    _, _, first = _turn({}, "همین حجم و پنجره‌ها بمونه")
    _, _, second = _turn(first, "حالا پنجره‌ها رو عوض کن")

    assert second["active_preserve_constraints"]["massing"] is True
    assert "windows" not in second["active_preserve_constraints"]
    assert any(
        operation["target"] == "windows" and operation["operation"] == "replace"
        for operation in second["active_architectural_understanding"]["change_operations"]
    )


def test_D_ambiguous_request_requires_clarification_without_fabricated_prompt():
    _, understanding, merged, effective, compiled = _effective({}, "بهترش کن")

    assert understanding["intent_type"] == "clarify"
    assert merged["pending_clarifications"]
    assert effective["intent_type"] == "clarify"
    assert compiled["status"] == "NEEDS_CLARIFICATION"
    assert compiled["positive_prompt"] == ""
    assert compiled["negative_prompt"] == ""


def test_E_material_only_reference_policy_does_not_fake_pixel_claims(tmp_path):
    image = tmp_path / "modern_travertine_facade.png"
    image.write_bytes(b"not-real-vision-evidence")
    understanding = understand("از این عکس فقط متریالش رو بگیر")
    analysis = ReferenceImageArchitecturalUnderstandingV1().analyze(str(image))

    assert understanding["reference_image_policy"]["role"] == "material_only"
    assert understanding["reference_image_policy"]["copy_reference_geometry"] is False
    assert analysis["analysis_status"] == "PROVIDER_UNAVAILABLE"
    assert analysis["facade_style"] is None
    assert analysis["materials"] == []
    assert analysis["provenance"]["pixel_analysis"] is False


def test_F_approved_design_is_geometry_authority_and_input_is_not_mutated():
    state = deepcopy(APPROVED)
    snapshot = deepcopy(state)
    effective = _effective({}, "همین حجم بمونه فقط سنگش روشن‌تر شه")[3]
    compiled = compile_prompt(effective)
    contract = build_render_contract(
        state, understanding=effective, compiled_prompt=compiled
    )

    assert contract["status"] in ("READY", "READY_WITH_WARNINGS")
    assert contract["authoritative_geometry_source"] == "APPROVED_DESIGN"
    assert contract["preserve_constraints"]["geometry"] is True
    assert contract["preserve_constraints"]["massing"] is True
    assert state == snapshot


def test_G_design_level_change_is_rejected_by_render_contract_and_revision():
    understanding = understand("یه طبقه اضافه کن")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    assert contract["status"] == "DESIGN_REVISION_REQUIRED"
    assert revision["status"] == "DESIGN_REVISION_REQUIRED"
    assert revision["revision_scope"] == "DESIGN"
    assert revision["delta_operations"] == []


def test_H_active_render_revision_is_appearance_only_and_preserves_design_authority():
    understanding = understand("همینه فقط سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    assert revision["status"] == "READY"
    assert revision["revision_scope"] == "RENDER_ONLY"
    assert revision["base_render_id"] == "R-FREEZE"
    assert revision["material_delta"]["tone_direction"] == "LIGHTER"
    assert revision["approved_design_authority"]["authoritative_geometry_source"] == "APPROVED_DESIGN"
    assert revision["approved_design_authority"]["base_render_is_authority"] is False
    assert revision["provenance"]["design_mutation"] is False


@pytest.mark.parametrize(
    ("text", "forbidden_type"),
    [
        ("مدرن‌تر نشه", "STYLE_REFINEMENT"),
        ("قوس‌ها بیشتر نشن", "ARCH_INTENSITY_CHANGE"),
        ("سنگش روشن‌تر نشه", "MATERIAL_TONE_CHANGE"),
    ],
)
def test_I_negated_comparatives_never_leak_positive_deltas(text, forbidden_type):
    understanding = understand(text)
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    assert all(
        operation["revision_type"] != forbidden_type
        for operation in revision["delta_operations"]
    )


def test_J_luxury_increase_retains_negative_complexity_constraint():
    understanding = understand("لوکس‌ترش کن ولی شلوغ نشه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    assert revision["style_delta"]["target"] == "luxury"
    assert revision["style_delta"]["direction"] == "increase"
    assert revision["ornament_delta"]["direction"] == "decrease"
    assert any(
        constraint.get("constraint") == "avoid_heavy_ornament"
        for constraint in revision["style_delta"]["negative_constraints"]
    )


def test_K_generic_chat_produces_no_architectural_contract_spam():
    _, understanding, merged = _turn({}, "سلام، امروز چطوری؟")

    assert understanding["intent_type"] == "none"
    assert merged["turn_has_architectural_signal"] is False
    assert compile_prompt({})["status"] == "NO_ARCHITECTURAL_INTENT"


class _CountingProvider(ArchitecturalVisionProvider):
    name = "counting"
    model = "acceptance-only"

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def analyze(self, image_asset):
        self.calls += 1
        return {"facade_style": "modern"}


def test_L_no_image_never_calls_vision_provider():
    provider = _CountingProvider()
    analyzer = ReferenceImageArchitecturalUnderstandingV1(provider)

    assert analyzer.analyze_if_present(None) == {}
    assert provider.calls == 0


def test_M_missing_approval_is_structured_for_render_contract_and_revision():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(
        {
            "approval_status": False,
            "design_status": "waiting_approval",
            "project_state": "WAITING_APPROVAL",
            "last_design": {"type": "villa"},
        },
        understanding=understanding,
    )
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    assert contract["status"] == "APPROVAL_REQUIRED"
    assert revision["status"] == "APPROVAL_REQUIRED"
    assert revision["delta_operations"] == []


def test_freeze_invariant_optional_llm_cannot_overwrite_deterministic_fields():
    engine = PersianArchitecturalUnderstandingEngine()
    deterministic = engine.interpret("نما مدرن‌تر شه و سنگ روشن باشه")
    enriched = engine.enrich_with_llm(
        deterministic,
        llm_callable=lambda _: {
            "style": {"target": "classic"},
            "materials": {"primary": "brick"},
        },
    )

    assert enriched["style"]["target"] == "modern"
    assert enriched["materials"]["primary"] == "stone"
    assert {item["resolution"] for item in enriched["conflicts"]} == {
        "deterministic_authoritative"
    }


def test_freeze_invariant_serialization_and_hashes_are_deterministic():
    text = "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه و سنگ روشن باشه"
    stable_previous = {"session_id": "S-FREEZE", "conversation_id": "C-FREEZE"}
    first = _effective(stable_previous, text)
    second = _effective(stable_previous, text)

    assert first[2]["context_hash"] == second[2]["context_hash"]
    assert first[4]["deterministic_hash"] == second[4]["deterministic_hash"]
    assert json.loads(json.dumps(first[4], ensure_ascii=False)) == first[4]


def test_final_runtime_composition_is_additive_and_keeps_router_after_2d_stack():
    source_path = Path("core/chat/chat_architect.py")
    source = source_path.read_text(encoding="utf-8")

    ordered_markers = [
        "self.input_adapter.normalize(",
        "persian_architectural_understanding.interpret(",
        "architectural_conversation_context.apply_turn(",
        "architectural_prompt_compiler.compile(",
        "reference_image_understanding.analyze(",
        "approved_design_render_contract.build(",
        "render_revision_delta.build(",
        "self.intent_router.route(",
    ]
    positions = [source.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions)

    for key in (
        '"raw_text"',
        '"normalized_text"',
        '"architectural_understanding"',
        '"architectural_context"',
        '"architectural_compiled_prompt"',
        '"reference_architectural_analysis"',
        '"approved_design_render_contract"',
        '"render_revision_delta"',
    ):
        assert key in source

    revision_module = inspect.getmodule(build_render_revision_delta)
    revision_source = inspect.getsource(revision_module).lower()
    for forbidden in (
        "from core.render",
        "render_runtime(",
        "import comfy",
        "from comfy",
        "core.structure",
        "core.bim",
        "core.ifc",
    ):
        assert forbidden not in revision_source


# ==========================================================
# FREEZE EXTENSIONS — closes the remaining acceptance coverage
# (appended during 2D FINAL ACCEPTANCE; existing tests preserved)
# ==========================================================

# ---- E (completion): full textual reference policy ----

def test_E_full_textual_reference_policy_material_only_no_geometry_copy():
    understanding = understand("از این عکس فقط متریالش رو بگیر، فرمش رو کپی نکن")
    policy = understanding["reference_image_policy"]
    assert policy["referenced"] is True
    assert policy["role"] == "material_only"
    assert policy["copy_reference_geometry"] is False


def test_E_reference_geometry_is_never_authoritative():
    understanding = understand("مثل این عکس باشه")
    contract = build_render_contract(
        APPROVED,
        understanding=understanding,
        reference_analysis={
            "contract": "ReferenceArchitecturalAnalysisV1",
            "analysis_status": "PROVIDER_UNAVAILABLE",
        },
    )
    # a reference image can never become the geometry authority
    assert contract["authoritative_geometry_source"] == "APPROVED_DESIGN"
    assert contract["render_intent"]["reference_policy"]["reference_geometry_copy"] is False


# ---- I (completion): the full negation matrix ----

@pytest.mark.parametrize(
    ("text", "family"),
    [
        ("مدرن‌تر نشه", "style_delta"),
        ("کلاسیک‌تر نشه", "style_delta"),
        ("لوکس‌تر نشه", "style_delta"),
        ("قوس‌ها بیشتر نشن", "arch_delta"),
        ("سنگش روشن‌تر نشه", "material_delta"),
        ("نور روشن‌تر نشه", "lighting_delta"),
    ],
)
def test_I_full_negation_matrix_never_leaks_positive(text, family):
    understanding = understand(text)
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    assert revision[family] == {}, f"{text}: {family} must stay empty"
    assert revision["delta_operations"] == [], f"{text}: no positive operation"
    assert revision["status"] in (
        "NO_RENDER_REVISION_INTENT", "READY", "READY_WITH_WARNINGS"
    ), text


def test_I_negated_illumination_retains_time_of_day_only():
    understanding = understand("نور عصر باشه، روشن‌تر نشه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    assert revision["lighting_delta"]["time_of_day"] == "evening"
    assert revision["lighting_delta"]["direction"] is None


# ---- C (completion): override resolution provenance ----

def test_C_override_records_resolution_provenance():
    _, _, first = _turn({}, "همین حجم بمونه")
    _, _, second = _turn(first, "پنجره‌ها همین بمونه")
    _, _, third = _turn(second, "حالا پنجره‌ها رو عوض کن")

    assert third["active_preserve_constraints"]["massing"] is True   # unrelated intact
    assert third["active_preserve_constraints"].get("windows") is not True
    assert any(
        entry.get("field") == "windows"
        and entry.get("resolution") == "latest_change_overrides_preserve"
        for entry in third["provenance"]["resolutions"]
    ), json.dumps(third["provenance"]["resolutions"], ensure_ascii=False)


# ---- 4. CONTRACT COMPATIBILITY ----

def _contract_documents():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    return {
        "NormalizedRequest": _request("نما مدرن‌تر شه"),
        "PersianArchitecturalUnderstandingV1": understanding,
        "ArchitecturalConversationContextV1": ArchitecturalConversationContextMergerV1().merge(
            {}, understanding, raw_text="x", normalized_text="x"
        ),
        "ArchitecturalCompiledPromptV1": compile_prompt(understanding),
        "ReferenceArchitecturalAnalysisV1": ReferenceImageArchitecturalUnderstandingV1().analyze(None),
        "ApprovedDesignRenderContractV1": contract,
        "RenderRevisionDeltaV1": revision,
    }


def test_contract_compatibility_identity_and_round_trip():
    documents = _contract_documents()
    assert set(documents) == {
        "NormalizedRequest",
        "PersianArchitecturalUnderstandingV1",
        "ArchitecturalConversationContextV1",
        "ArchitecturalCompiledPromptV1",
        "ReferenceArchitecturalAnalysisV1",
        "ApprovedDesignRenderContractV1",
        "RenderRevisionDeltaV1",
    }
    for name, document in documents.items():
        assert document["contract"] == name, name
        assert document["version"] == "1.0", name
        assert json.loads(json.dumps(document, ensure_ascii=False, default=str)) == document, name


def test_contract_hashes_are_stable_and_authorities_stay_distinct():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision_a = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    revision_b = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )

    # deterministic
    assert revision_a["delta_hash"] == revision_b["delta_hash"]
    assert contract["contract_hash"] == build_render_contract(
        APPROVED, understanding=understanding
    )["contract_hash"]

    # no authority is conflated / silently overwritten
    assert revision_a["delta_hash"] != contract["contract_hash"]
    assert revision_a["delta_hash"] != revision_a["approved_candidate_hash"]
    assert revision_a["delta_hash"] != revision_a["base_render_hash"]

    snapshot = deepcopy(contract)
    build_render_revision_delta(contract, understanding=understanding, render_state=ACTIVE_RENDER)
    assert contract == snapshot, "2D-7 must not mutate the 2D-6 contract"
    assert revision_a["approved_candidate_hash"] == "design-hash"


# ---- 5. AUTHORITY ORDER ----

def test_authority_order_is_explicit_and_never_inverted():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    assert revision["approved_design_authority"]["priority_order"] == [
        "approved_design",
        "hard_preserve_constraints",
        "render_revision_delta",
        "previous_render_appearance",
        "reference_image_evidence",
    ]
    assert revision["approved_design_authority"]["base_render_is_authority"] is False


def test_approved_design_outranks_base_render_drift():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract,
        understanding=understanding,
        render_state={**ACTIVE_RENDER, "base_render_observed_floor_count": 5},
        context={"approved_floor_count": 3},
    )
    assert revision["base_render_drift"]["detected"] is True
    assert revision["base_render_drift"]["resolution"] == "approved_design_authoritative"
    assert revision["approved_design_authority"]["base_render_is_authority"] is False
    assert any(w["code"] == "BASE_RENDER_VISUAL_DRIFT" for w in revision["warnings"])


# ---- 6. FINAL INVARIANTS (2D-1 … 2D-7) ----

def test_invariant_2d1_raw_preserved_deterministic_no_translation():
    raw = "نماي ۲ مدرن‌تر"
    first = persian_normalizer.normalize(raw)
    second = persian_normalizer.normalize(raw)
    assert first == second
    assert first["raw_text"] == raw
    assert first["normalized_text"] == "نمای 2 مدرن‌تر"
    assert any("\u0600" <= char <= "\u06ff" for char in first["normalized_text"])


def test_invariant_2d2_constraints_explicit_ambiguity_not_guessed():
    understanding = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert understanding["preserve_constraints"] is not None
    assert understanding["negative_constraints"]
    assert understanding["negative_constraints"][0]["constraint"]

    ambiguous = understand("بهترش کن")
    assert ambiguous["intent_type"] == "clarify"
    assert ambiguous["style"]["target"] is None
    assert ambiguous["materials"]["primary"] is None


def test_invariant_2d3_english_projection_with_separated_negatives():
    understanding = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    compiled = compile_prompt(understanding)
    assert compiled["status"] == "COMPILED"
    assert compiled["positive_prompt"]
    assert compiled["negative_prompt"]
    assert not any("\u0600" <= char <= "\u06ff" for char in compiled["positive_prompt"])
    assert not any("\u0600" <= char <= "\u06ff" for char in compiled["negative_prompt"])
    assert len(compiled["deterministic_hash"]) == 64


def test_invariant_2d4_primary_route_and_reset_boundary():
    source = Path("core/chat/chat_architect.py").read_text(encoding="utf-8")
    assert "self.context_builder.build(" in source
    assert "architectural_conversation_context.apply_turn(" in source
    assert "مهدی" not in source

    from core.chat.architectural_conversation_context_v1 import (
        architectural_conversation_context,
    )

    architectural_conversation_context.reset()
    assert architectural_conversation_context.get() == {}
    merged = architectural_conversation_context.apply_turn(
        understanding=understand("نما مدرن‌تر شه"), raw_text="x", normalized_text="x"
    )
    assert merged["active_style"]["target"] == "modern"
    architectural_conversation_context.reset()


def test_invariant_2d5_no_orientation_metric_or_structural_inference():
    analysis = ReferenceImageArchitecturalUnderstandingV1().analyze(None)
    for field in ("visible_floor_count", "facade_style", "materials", "style_candidates"):
        assert analysis.get(field) in (None, [], {}), field


def test_invariant_2d6_approval_never_inferred_and_state_not_mutated():
    for state in ({}, {
        "approval_status": False,
        "design_status": "waiting_approval",
        "project_state": "WAITING_APPROVAL",
        "last_design": {"type": "villa"},
    }):
        contract = build_render_contract(state, understanding=understand("نما مدرن‌تر شه"))
        assert contract["status"] in ("APPROVAL_REQUIRED", "NO_APPROVED_DESIGN")

    state = deepcopy(APPROVED)
    snapshot = deepcopy(state)
    build_render_contract(state, understanding=understand("سنگش روشن‌تر شه"))
    assert state == snapshot


def test_invariant_2d7_no_render_execution_and_design_revision_gate():
    understanding = understand("سنگش روشن‌تر شه")
    contract = build_render_contract(APPROVED, understanding=understanding)
    revision = build_render_revision_delta(
        contract, understanding=understanding, render_state=ACTIVE_RENDER
    )
    assert revision["provenance"]["semantic_delta_only"] is True
    assert revision["provenance"]["render_execution"] is False
    assert revision["provenance"]["design_mutation"] is False
    assert revision["approved_design_authority"]["base_render_is_authority"] is False

    # illegal design change is gated at both levels
    geometry = understand("پنجره‌ها رو جابه‌جا کن")
    geometry_contract = build_render_contract(APPROVED, understanding=geometry)
    geometry_revision = build_render_revision_delta(
        geometry_contract, understanding=geometry, render_state=ACTIVE_RENDER
    )
    assert geometry_contract["status"] == "DESIGN_REVISION_REQUIRED"
    assert geometry_revision["status"] == "DESIGN_REVISION_REQUIRED"
    assert geometry_revision["delta_operations"] == []
    assert "move_primary_openings" in geometry_revision["forbidden_changes"]


# ---- 14. FORBIDDEN DEPENDENCY + TRACK ISOLATION SCAN ----

_2D_MODULES = (
    "core/cognition/persian_normalizer.py",
    "core/prompt_intelligence/persian_architectural_understanding.py",
    "core/prompt_intelligence/architectural_prompt_compiler_v1.py",
    "core/chat/architectural_conversation_context_v1.py",
    "core/prompt_intelligence/reference_image_architectural_understanding_v1.py",
    "core/prompt_intelligence/approved_design_render_contract_v1.py",
    "core/prompt_intelligence/render_revision_delta_v1.py",
)

_FORBIDDEN_IMPORTS = (
    "import requests", "from requests",
    "import comfy", "from comfy",
    "import openai", "from openai",
    "import anthropic", "from anthropic",
    "import torch", "from torch",
    "import transformers", "from transformers",
    "import subprocess", "from subprocess",
    "urllib.request", "http.client", "import socket",
)

_FOREIGN_TRACKS = (
    "architectural_change_", "housediffusion", "site_fit",
    "render_runtime", "prompt_router", "core.bim", "core.ifc",
    "core.structure",
)


def _import_lines(path):
    with open(path, encoding="utf-8") as handle:
        return "\n".join(
            line.strip() for line in handle if re.match(r"\s*(import|from)\s", line)
        )


def test_forbidden_dependency_scan_all_2d_modules():
    for path in _2D_MODULES:
        joined = _import_lines(path)
        for forbidden in _FORBIDDEN_IMPORTS:
            assert forbidden not in joined, f"{path}: {forbidden}"


def test_2d_track_is_isolated_from_other_owned_tracks():
    for path in _2D_MODULES:
        joined = _import_lines(path).lower()
        for foreign in _FOREIGN_TRACKS:
            assert foreign not in joined, f"{path}: {foreign}"

