"""ARCHITECTOS INTERNAL GENERATOR GUARDRAIL — targeted tests.

Proves the legacy/internal ArchitectOS plan-synthesis branch can never be
mistaken for the PRIMARY production plan generator.

Locked product decision: HouseDiffusion is the primary plan generator under
``HOUSE_DIFFUSION_GENERATION_POLICY_V1``. The internal branch is
diagnostic / explicit-fallback only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.architecture.routing.generation_policy_guard_v1 import (
    ACTIVE_DOWNSTREAM_INTELLIGENCE,
    FALLBACK_REASON_ROUTE_NOT_WIRED,
    HOUSE_DIFFUSION_GENERATION_POLICY_V1,
    HOUSE_DIFFUSION_POLICY,
    INTERNAL_GENERATOR,
    INTERNAL_GENERATOR_MODULES,
    LEGACY_INTERNAL_POLICY,
    PRIMARY_GENERATOR_BYPASS_DETECTED,
    PRIMARY_GENERATOR_HOUSE_DIFFUSION,
    ROLE_DIAGNOSTIC,
    ROLE_EXPLICIT_FALLBACK,
    ROLE_PRIMARY,
    PrimaryGeneratorBypassError,
    guard_internal_plan_generation,
    resolve_policy,
)


ROOT = Path(__file__).resolve().parents[2]

#: Confirmed internal plan-synthesis entrypoints (traced, not guessed).
INTERNAL_GENERATOR_FILES = {
    "core/architecture/brain/architectural_brain.py": "ArchitecturalBrain.design",
    "core/architecture/reasoning/layout_reasoner.py": "LayoutReasoner.generate",
    "core/architecture/reasoning/spatial_placement_reasoner.py": "SpatialPlacementReasoner.place",
    "core/architecture/reasoning/plan_model_reasoner.py": "PlanModelReasoner.generate",
    "core/architecture/reasoning/knowledge_space_generator.py": "KnowledgeSpaceGenerator.generate",
    "core/architecture/reasoning/layout_regeneration_reasoner_v1.py":
        "LayoutRegenerationReasonerV1.regenerate",
    "core/architecture/reasoning/coherent_floor_plan_resolver_v1.py":
        "CoherentFloorPlanResolverV1.resolve",
    "core/architecture/reasoning/architectural_layout_intelligence_v1.py":
        "ArchitecturalLayoutIntelligenceV1.design",
}

#: The smallest existing routing boundaries where the guard is enforced.
ROUTING_BOUNDARIES = {
    "core/intelligence/architectos_design_execution_bridge_v100.py":
        "ArchitectOSDesignExecutionBridge.process",
    "core/tools/design_tool.py": "DesignTool.execute",
}

#: HouseDiffusion lab sources frozen at the ADAPTER-01 checkpoint.
FROZEN_HOUSE_DIFFUSION = {
    "architectos_to_housediffusion.py":
        "771cdcb5ca18b311ee6ef6e7404e352d54d133392aae51ed8082a09cf7187f46",
    "architectos_native_adapter.py":
        "7049b48336a827b6b98873c871c71db087fd8a2b317847ec6cd9182f90093ae7",
    "architectos_program_to_hd_native_compiler.py":
        "09193c8a1a91f93c451103b9e843879df277d297e3fe3948999073c32928290c",
    "native_contract_reference.py":
        "e5a7b54a97b57a3dd52b65d5da3697803e067fdc0be659b6699131fbaba39108",
}

HOUSE_DIFFUSION_LAB = Path(r"D:\AI_Architecture_Lab\house_diffusion")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ==========================================================
# A — the HouseDiffusion policy cannot silently select the internal generator
# ==========================================================

def test_a_policy_primary_is_house_diffusion():
    policy = resolve_policy(HOUSE_DIFFUSION_GENERATION_POLICY_V1)
    assert policy.policy_id == HOUSE_DIFFUSION_GENERATION_POLICY_V1
    assert policy.primary_generator == PRIMARY_GENERATOR_HOUSE_DIFFUSION
    assert policy.is_house_diffusion is True
    # the default policy IS the locked HouseDiffusion policy
    assert resolve_policy(None).policy_id == HOUSE_DIFFUSION_GENERATION_POLICY_V1


def test_a2_silent_selection_of_internal_generator_is_impossible():
    """An undeclared call site defaults to PRIMARY and therefore fails."""
    with pytest.raises(PrimaryGeneratorBypassError) as caught:
        guard_internal_plan_generation()  # no role declared
    assert PRIMARY_GENERATOR_BYPASS_DETECTED in str(caught.value)

    with pytest.raises(PrimaryGeneratorBypassError):
        guard_internal_plan_generation(invocation_role=ROLE_PRIMARY,
                                       source="undeclared.call.site")


# ==========================================================
# B — attempted bypass raises PRIMARY_GENERATOR_BYPASS_DETECTED
# ==========================================================

def test_b_attempted_bypass_raises():
    with pytest.raises(PrimaryGeneratorBypassError) as caught:
        guard_internal_plan_generation(
            invocation_role=ROLE_PRIMARY,
            generation_policy=HOUSE_DIFFUSION_GENERATION_POLICY_V1,
            source="test_bypass",
        )
    message = str(caught.value)
    assert PRIMARY_GENERATOR_BYPASS_DETECTED in message
    assert INTERNAL_GENERATOR in message
    assert PRIMARY_GENERATOR_HOUSE_DIFFUSION in message
    assert caught.value.code == PRIMARY_GENERATOR_BYPASS_DETECTED


def test_b2_unauthorised_fallback_also_raises():
    """A fallback the policy does not authorise is a bypass too."""
    with pytest.raises(PrimaryGeneratorBypassError) as caught:
        guard_internal_plan_generation(
            invocation_role=ROLE_EXPLICIT_FALLBACK,
            generation_policy=LEGACY_INTERNAL_POLICY,  # fallback_authorized=False
            source="test_unauthorised_fallback",
        )
    assert PRIMARY_GENERATOR_BYPASS_DETECTED in str(caught.value)


# ==========================================================
# C — explicit diagnostic invocation remains possible
# ==========================================================

def test_c_diagnostic_invocation_allowed():
    metadata = guard_internal_plan_generation(
        invocation_role=ROLE_DIAGNOSTIC,
        source="test_diagnostic",
    )
    assert metadata["internal_generator_role"] == ROLE_DIAGNOSTIC
    assert metadata["fallback_used"] is False
    assert metadata["production_output"] is False
    assert metadata["primary_generator"] == PRIMARY_GENERATOR_HOUSE_DIFFUSION
    assert metadata["generation_policy"] == HOUSE_DIFFUSION_GENERATION_POLICY_V1


# ==========================================================
# D — explicit authorised fallback remains possible
# ==========================================================

def test_d_explicit_authorised_fallback_allowed_and_recorded():
    assert HOUSE_DIFFUSION_POLICY.fallback_authorized is True
    metadata = guard_internal_plan_generation(
        invocation_role=ROLE_EXPLICIT_FALLBACK,
        source="test_fallback",
    )
    assert metadata["fallback_used"] is True
    assert metadata["fallback_generator"] == INTERNAL_GENERATOR
    assert metadata["fallback_reason"] == FALLBACK_REASON_ROUTE_NOT_WIRED
    assert metadata["primary_generator"] == PRIMARY_GENERATOR_HOUSE_DIFFUSION
    assert metadata["generation_policy"] == HOUSE_DIFFUSION_GENERATION_POLICY_V1
    # no silent fallback: the reason is always populated
    assert metadata["fallback_reason"]


def test_d2_fallback_metadata_contract():
    """The full required fallback metadata contract is present."""
    metadata = guard_internal_plan_generation(
        invocation_role=ROLE_EXPLICIT_FALLBACK,
        primary_generator_attempted=True,
        primary_generator_error="HouseDiffusionUnavailable",
        source="test_metadata_contract",
    )
    for key in ("primary_generator", "primary_generator_attempted", "fallback_used",
                "fallback_generator", "fallback_reason", "generation_policy"):
        assert key in metadata, key
    assert metadata["primary_generator_attempted"] is True
    assert metadata["primary_generator_error"] == "HouseDiffusionUnavailable"


# ==========================================================
# Source markers — the internal branch is visibly non-primary
# ==========================================================

def test_markers_present_on_every_internal_entrypoint():
    for relative, entrypoint in INTERNAL_GENERATOR_FILES.items():
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        assert 'ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"' in text, relative
        assert "PRODUCTION_PRIMARY = False" in text, relative
        assert "NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR." in text, relative
        assert "HOUSE_DIFFUSION_GENERATION_POLICY_V1" in text, relative
        assert entrypoint.split(".")[0] in text, (relative, entrypoint)


def test_marker_modules_are_exactly_the_confirmed_branch():
    """The guard's module list matches the confirmed entrypoint set."""
    declared = {m.rsplit(".", 1)[-1] for m in INTERNAL_GENERATOR_MODULES}
    assert declared == {
        "architectural_brain", "layout_reasoner", "spatial_placement_reasoner",
        "plan_model_reasoner", "knowledge_space_generator",
        "layout_regeneration_reasoner_v1", "coherent_floor_plan_resolver_v1",
        "architectural_layout_intelligence_v1",
    }


# ==========================================================
# Downstream intelligence must NOT be marked legacy
# ==========================================================

def test_downstream_intelligence_is_not_marked_legacy():
    assert "Design-02" in ACTIVE_DOWNSTREAM_INTELLIGENCE
    assert "Design-05" in ACTIVE_DOWNSTREAM_INTELLIGENCE
    assert "AcceptedArchitecturalBaselineEnvelopeV1" in ACTIVE_DOWNSTREAM_INTELLIGENCE

    active_modules = (
        "core/architecture/contracts/accepted_architectural_baseline_envelope_v1.py",
        "core/architecture/reasoning/architectural_baseline_derived_candidate_refinement_v1.py",
        "core/architecture/reasoning/architectural_baseline_opening_privacy_parcel_edge_intelligence_v1.py",
        "core/architecture/reasoning/architectural_baseline_floor_roof_geometry_v1.py",
        "core/architecture/reasoning/architectural_baseline_structural_readiness_v1.py",
    )
    for relative in active_modules:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR" not in text, relative
        assert "PRODUCTION_PRIMARY = False" not in text, relative


# ==========================================================
# The guard is actually wired at the routing boundaries
# ==========================================================

def test_guard_enforced_at_every_routing_boundary():
    for relative, boundary in ROUTING_BOUNDARIES.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "generation_policy_guard_v1" in text, relative
        assert "guard_internal_plan_generation" in text, relative
        assert "ROLE_EXPLICIT_FALLBACK" in text, relative
        assert "PRIMARY_GENERATOR_BYPASS_DETECTED" in text or \
               "GENERATOR-SELECTION BOUNDARY" in text, relative
        # the guard must precede the internal generator invocation
        guard_at = text.index("guard_internal_plan_generation(")
        assert guard_at < len(text)
        assert boundary.split(".")[-1] in text, boundary


def test_no_unguarded_internal_generator_call_site_remains():
    """Every ArchitecturalBrain().design(...) call site is guard-preceded."""
    for relative in ROUTING_BOUNDARIES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if "architectural_brain.design(" not in text and "ArchitecturalBrain().design(" not in text:
            continue
        guard_at = text.index("guard_internal_plan_generation(")
        call_at = min(
            (text.index(token) for token in
             ("ArchitecturalBrain().design(", "architectural_brain.design(")
             if token in text),
            default=None,
        )
        assert call_at is not None, relative
        assert guard_at < call_at, relative


# ==========================================================
# E — the HouseDiffusion production route is unchanged
# ==========================================================

def test_e_house_diffusion_route_unchanged():
    from core.architecture.reasoning.housediffusion_accepted_baseline_adapter_v1 import (
        CONTRACT,
        HouseDiffusionAcceptedBaselineAdapterV1,
    )
    from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
        BASELINE_ROOT,
        EXPECTED_GENERATION_POLICY,
        EXPECTED_PRIMARY_GENERATOR,
    )

    assert CONTRACT == "HouseDiffusionAcceptedBaselineAdapterV1"
    assert EXPECTED_PRIMARY_GENERATOR == "HouseDiffusion"
    assert EXPECTED_GENERATION_POLICY == HOUSE_DIFFUSION_GENERATION_POLICY_V1
    if not BASELINE_ROOT.is_dir():
        pytest.skip(f"accepted HouseDiffusion baseline not present: {BASELINE_ROOT}")
    adapter = HouseDiffusionAcceptedBaselineAdapterV1()
    assert adapter.verifier.verify_identity()["status"] == "RECONNECTED"


# ==========================================================
# F — Design-02..05 remain reachable from HouseDiffusion output
# ==========================================================

def test_f_design_chain_reachable_from_house_diffusion_output():
    from core.architecture.reasoning.housediffusion_accepted_baseline_adapter_v1 import (
        HouseDiffusionAcceptedBaselineAdapterV1,
    )
    from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
        BASELINE_ROOT,
    )

    if not BASELINE_ROOT.is_dir():
        pytest.skip(f"accepted HouseDiffusion baseline not present: {BASELINE_ROOT}")

    adapter = HouseDiffusionAcceptedBaselineAdapterV1()
    envelope = adapter.adapt()
    chain = adapter.run_design_chain(envelope)
    assert chain["design_02"]["contract"] == "DerivedArchitecturalCandidateV1"
    assert chain["design_03"]["contract"] == "Design03DerivedArchitecturalCandidateV1"
    assert chain["design_04"]["contract"] == "Design04DerivedArchitecturalGeometryCandidateV1"
    assert chain["design_05"]["contract"] == "Design05StructuralReadinessCandidateV1"
    # still no structure synthesized
    assert chain["design_05"]["provenance"]["structural_synthesis_performed"] is False


# ==========================================================
# G — no HouseDiffusion source is modified
# ==========================================================

def test_g_house_diffusion_source_unmodified():
    if not HOUSE_DIFFUSION_LAB.is_dir():
        pytest.skip(f"HouseDiffusion lab not present: {HOUSE_DIFFUSION_LAB}")
    for name, expected in FROZEN_HOUSE_DIFFUSION.items():
        path = HOUSE_DIFFUSION_LAB / name
        assert path.is_file(), name
        assert _sha256(path) == expected, name


def test_g2_internal_branch_algorithm_not_modified():
    """Only markers were added - the branch's own logic is untouched."""
    # the deterministic treemap partition is still present and unmarked as active
    treemap = ROOT / "core/architecture/reasoning/coherent_floor_plan_resolver_v1.py"
    text = treemap.read_text(encoding="utf-8")
    assert "def _treemap(" in text
    assert '"partition": "deterministic_squarified_treemap"' in text
    assert "PRODUCTION_PRIMARY = False" in text
