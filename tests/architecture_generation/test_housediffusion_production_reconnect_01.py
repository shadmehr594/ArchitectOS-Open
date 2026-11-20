"""HOUSE-DIFFUSION-PRODUCTION-BASELINE-RECONNECT-01 targeted tests.

Read-only reconnection and verification of the previously ACCEPTED real
HouseDiffusion architectural baseline.

The suite proves:
- the accepted baseline is located and its identity/lineage is proven,
- the CURRENT ArchitectOS contracts cannot consume the baseline artifact
  directly, and the reconnect probe reports that honestly — including the
  ADAPTER-01 adapter that now bridges the two contracts,
- a human-readable plan is exported from the REAL baseline geometry (no
  invention, no internal-layout replacement),
- HouseDiffusion remains the primary plan generator and the internal rule-based
  branch is classified diagnostic-only,
- no frozen Design-02/03/04/05 behaviour is changed and no structure/BIM/IFC/
  render path runs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
    ARCHITECTOS_REQUIRED_GRAPHS,
    BASELINE_ROOT,
    CLASS_DIAGNOSTIC_BRANCH,
    CLASS_LEGACY_INTERNAL_GENERATOR_BRANCH,
    EXPECTED_GENERATION_POLICY,
    EXPECTED_PHASE,
    EXPECTED_PRIMARY_GENERATOR,
    EXPECTED_SCHEMA,
    REQUIRED_ARTIFACTS,
    STATUS_ARTIFACTS_MISSING,
    STATUS_CONSUMER_INCOMPATIBLE,
    STATUS_IDENTITY_UNRESOLVED,
    STATUS_RECONNECTED,
    HouseDiffusionBaselineReconnectV1,
    reconnect_housediffusion_baseline,
)


ROOT = Path(__file__).resolve().parents[2]

FROZEN_STRUCTURAL_HASHES = {
    "core/structure/structural_grid_engine.py":
        "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py":
        "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
}

FROZEN_ARCHITECTURAL = (
    "core/architecture/geometry/architectural_space_boundary_pipeline_v1.py",
    "core/architecture/contracts/accepted_architectural_baseline_envelope_v1.py",
    "core/architecture/reasoning/architectural_baseline_derived_candidate_refinement_v1.py",
    "core/architecture/reasoning/architectural_baseline_opening_privacy_parcel_edge_intelligence_v1.py",
    "core/architecture/reasoning/architectural_baseline_floor_roof_geometry_v1.py",
    "core/architecture/reasoning/architectural_baseline_structural_readiness_v1.py",
)


pytestmark = pytest.mark.skipif(
    not BASELINE_ROOT.is_dir(),
    reason=f"accepted HouseDiffusion baseline root not present: {BASELINE_ROOT}",
)


@pytest.fixture(scope="module")
def reconnect():
    return HouseDiffusionBaselineReconnectV1()


@pytest.fixture(scope="module")
def report(reconnect):
    return reconnect.report()


# ==========================================================
# A — the accepted baseline is located
# ==========================================================

def test_a_accepted_baseline_is_located(reconnect):
    located = reconnect.locate()
    assert located["root_present"] is True
    assert located["all_required_present"] is True
    for name in REQUIRED_ARTIFACTS:
        assert located["artifacts"][name]["present"] is True, name
        assert located["artifacts"][name]["bytes"] > 0


def test_a2_missing_root_fails_closed(tmp_path):
    absent = HouseDiffusionBaselineReconnectV1(tmp_path / "not-here")
    located = absent.locate()
    assert located["root_present"] is False
    assert located["all_required_present"] is False
    assert absent.verify_identity()["status"] == STATUS_ARTIFACTS_MISSING


# ==========================================================
# B — identity / lineage proven
# ==========================================================

def test_b_baseline_identity_is_proven(reconnect):
    identity = reconnect.verify_identity()
    assert identity["status"] == STATUS_RECONNECTED
    assert identity["failed_checks"] == []
    assert identity["schema"] == EXPECTED_SCHEMA
    assert identity["phase"] == EXPECTED_PHASE
    assert identity["generator"]["PRIMARY_PLAN_GENERATOR"] == EXPECTED_PRIMARY_GENERATOR
    assert EXPECTED_GENERATION_POLICY in str(identity["generator"]["GENERATION_POLICY"])


def test_b2_frozen_checkpoint_facts_are_proven_by_the_artifact(reconnect):
    gate = reconnect.verify_identity()["gate"]
    assert gate["BASELINE_ARCHITECTURAL_PLAN_COMPLETE"] == "YES"
    assert gate["BLOCKERS_FOUND"] == 0
    assert gate["PROGRAM_IDENTITIES"] == "8/8"
    assert gate["ACCESSIBLE_PROGRAM_SPACES"] == "8/8"
    assert gate["DERIVED_CIRCULATION_COUNT"] == 1
    assert gate["SEALED_PROGRAM_SPACES"] == 0
    assert gate["ORPHAN_PROGRAM_SPACES"] == 0
    assert gate["HABITABLE_ROOMS_WITH_PROVISIONAL_DAYLIGHT"] == "4/4"
    assert gate["WET_SPACES_WITH_VENTILATION_STRATEGY"] == "2/2"
    assert gate["DOOR_WINDOW_OVERLAPS"] == 0
    assert gate["POLYGON_OVERLAPS"] == 0
    assert gate["FINAL_WINDOWS_CREATED"] == "NO"
    assert gate["FINAL_WORLD_ORIENTATION_KNOWN"] == "NO"
    assert gate["HOUSE_DIFFUSION_MODIFIED"] == "NO"
    assert gate["CHECKPOINT_MODIFIED"] == "NO"
    assert gate["GENERATION_POLICY_MODIFIED"] == "NO"
    assert gate["NO_STRUCTURE"] == "YES"
    assert gate["NO_BIM_IFC"] == "YES"
    assert gate["NO_FURNITURE"] == "YES"
    assert gate["NO_RENDER"] == "YES"


def test_b3_geometry_ref_lineage_and_no_duplication(reconnect):
    identity = reconnect.verify_identity()
    assert identity["checks"]["geometry_refs_present"] is True
    assert identity["checks"]["no_duplicated_geometry"] is True
    assert identity["checks"]["geometry_source_sha256_matches"] is True
    assert identity["geometry_source_present"] is True
    assert identity["provenance_geometry"]["schema"] == "RefinedSemanticPlanCandidateV1_4"


def test_b4_a_tampered_baseline_fails_identity(tmp_path):
    for name in REQUIRED_ARTIFACTS:
        source = BASELINE_ROOT / name
        if source.is_file():
            (tmp_path / name).write_bytes(source.read_bytes())
    target = tmp_path / "semantic_architectural_plan_baseline_v1.json"
    document = json.loads(target.read_text(encoding="utf-8"))
    document["generator"]["PRIMARY_PLAN_GENERATOR"] = "InternalRuleBasedLayout"
    target.write_text(json.dumps(document), encoding="utf-8")

    verifier = HouseDiffusionBaselineReconnectV1(tmp_path)
    assert verifier.verify_identity()["status"] == STATUS_IDENTITY_UNRESOLVED


# ==========================================================
# C — ArchitectOS consumption is honestly probed
# ==========================================================

def test_c_current_contracts_cannot_consume_the_baseline(reconnect):
    consumption = reconnect.probe_architectos_consumption()
    assert consumption["consumption_outcome"] in ("rejected", "accepted")
    if consumption["consumption_outcome"] == "rejected":
        assert consumption["status"] == STATUS_CONSUMER_INCOMPATIBLE
        assert consumption["consumption_error"]
        assert set(ARCHITECTOS_REQUIRED_GRAPHS) <= set(consumption["missing_from_baseline"])


def test_c2_the_required_graphs_are_absent_from_the_baseline(reconnect):
    baseline = json.loads(
        (BASELINE_ROOT / "semantic_architectural_plan_baseline_v1.json").read_text(
            encoding="utf-8"))
    for graph in ARCHITECTOS_REQUIRED_GRAPHS:
        assert graph not in baseline, graph


def test_c3_reconnect_probe_truthfully_reports_adapter_presence(reconnect):
    """The probe must report the repository's REAL integration state.

    During HOUSE-DIFFUSION-PRODUCTION-BASELINE-RECONNECT-01 no adapter between
    ``SemanticArchitecturalPlanBaselineV1`` and
    ``AcceptedArchitecturalBaselineEnvelopeV1`` existed, so this test asserted
    ``adapter_present_in_architectos is False``.  HOUSE-DIFFUSION-ARCHITECTOS-
    ADAPTER-01 created exactly that adapter, so the probe must now report it.

    The probe keys off HouseDiffusion *references*, which now legitimately
    include the ARCHITECTOS-INTERNAL-GENERATOR-GUARDRAIL modules (they name the
    locked generation policy).  What must therefore be proven here is the
    invariant the guardrail protects: no runtime module actually INVOKES
    HouseDiffusion generation.
    """
    adapter = "core/architecture/reasoning/housediffusion_accepted_baseline_adapter_v1.py"
    assert (ROOT / adapter).is_file()

    consumption = reconnect.probe_architectos_consumption()
    assert consumption["adapter_present_in_architectos"] is True

    # no runtime module may invoke HouseDiffusion generation itself
    generator_tokens = (
        "architectos_program_to_hd_native_compiler",
        "architectos_native_adapter",
        "translate_program",
        "build_native_conditioning",
        "p_sample_loop",
        "ckpts/exp/model250000",
    )
    offenders = []
    for base in (ROOT / "core", ROOT / "app.py"):
        if not base.exists():
            continue
        targets = base.rglob("*.py") if base.is_dir() else [base]
        for path in targets:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in generator_tokens):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], offenders


def test_c4_design_02_still_rejects_a_non_conforming_input(reconnect):
    """Design-02 keeps its own contract; the baseline is not smuggled in."""
    from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
        derive_architectural_candidate_v1,
    )

    baseline = json.loads(
        (BASELINE_ROOT / "semantic_architectural_plan_baseline_v1.json").read_text(
            encoding="utf-8"))
    with pytest.raises(Exception):
        derive_architectural_candidate_v1(
            baseline, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["hd"]})


# ==========================================================
# D / E / F — the export comes from the REAL baseline
# ==========================================================

def test_d_no_internal_rule_based_replacement_is_substituted(reconnect):
    plan = reconnect.export_plan()
    assert plan["provenance"]["plan_generated"] is False
    assert plan["provenance"]["internal_layout_engine_used"] is False
    assert plan["provenance"]["geometry_invented"] is False
    assert plan["source"]["generator"]["PRIMARY_PLAN_GENERATOR"] == EXPECTED_PRIMARY_GENERATOR
    assert plan["plan_kind"] == "ACCEPTED_HOUSEDIFFUSION_BASELINE_READ_ONLY_EXPORT"


def test_e_human_readable_plan_is_exported_from_the_real_baseline(reconnect):
    plan = reconnect.export_plan()
    for kwargs in ({}, {"with_openings": True}, {"diagnostic": True}):
        svg = reconnect.render_plan_svg(plan, **kwargs)
        ET.fromstring(svg)
        assert svg.startswith("<svg ")
        assert "ACCEPTED HOUSE-DIFFUSION BASELINE" in svg
    plan_svg = reconnect.render_plan_svg(plan)
    for room in plan["rooms"]:
        if room["polygon"]:
            assert room["display_label"] in plan_svg, room["identity"]


def test_f_plan_shows_the_actual_resolved_rooms_walls_and_openings(reconnect):
    plan = reconnect.export_plan()
    counts = plan["counts"]
    assert counts["program_rooms"] == 8
    assert counts["rooms"] == 9  # 8 program rooms + the derived circulation
    assert counts["walls"] == 187
    assert counts["exterior_walls"] == 168
    assert counts["interior_walls"] == 19
    assert counts["openings"] == 9
    assert counts["provisional_windows"] == 4

    identities = {room["identity"] for room in plan["rooms"]}
    assert identities >= {
        "LIVING_RECEPTION", "CLOSED_KITCHEN", "MASTER_BEDROOM_SLEEPING",
        "BEDROOM_DOUBLE", "FAMILY_BATHROOM", "GUEST_WC", "UNIT_ENTRY",
        "TERRACE_BALCONY", "PRIVATE_DISTRIBUTION_POCKET",
    }
    for wall in plan["walls"]:
        assert wall["wall_role"] in ("EXTERIOR", "INTERIOR")
        assert len(wall["centerline"]) >= 2
    for opening in plan["openings"]:
        assert opening["opening_class"]
        assert len(opening["segment"]) >= 2


def test_f2_geometry_is_resolved_through_geometry_ref_only(reconnect):
    plan = reconnect.export_plan()
    assert plan["geometry_resolution"]["resolved_via_geometry_ref"] is True
    assert plan["geometry_resolution"]["unresolved"] == []
    for room in plan["rooms"]:
        assert room["geometry_ref"]["artifact"]
        assert room["geometry_ref"]["geometry_sha256"]
    # the baseline contract itself carries no copied coordinates
    baseline = json.loads(
        (BASELINE_ROOT / "semantic_architectural_plan_baseline_v1.json").read_text(
            encoding="utf-8"))
    for space in baseline["1_program_spaces"]:
        assert "polygon" not in space


def test_f3_wall_bands_are_symbolic_and_thickness_unresolved(reconnect):
    plan = reconnect.export_plan()
    bands = {json.dumps(wall["wall_band"], sort_keys=True) for wall in plan["walls"]
             if wall.get("wall_band")}
    assert bands
    for band in bands:
        parsed = json.loads(band)
        assert parsed["wall_band_type"] == "SYMBOLIC_RELATIVE"
        assert parsed["metric_thickness"] == "UNKNOWN"


def test_f4_export_is_deterministic(reconnect):
    first = reconnect.export_plan()
    second = reconnect.export_plan()
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str)
    assert reconnect.render_plan_svg(first) == reconnect.render_plan_svg(second)


# ==========================================================
# G / H — frozen behaviour untouched, no forbidden execution
# ==========================================================

def test_g_frozen_architectural_modules_are_byte_identical():
    for relative in FROZEN_ARCHITECTURAL:
        assert len(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()) == 64
    for relative, expected in FROZEN_STRUCTURAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def test_g2_design_02_to_05_still_work_on_their_own_contract():
    """The frozen chain is exercised on its canonical input, proving no regression."""
    from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
        ArchitecturalSpaceBoundaryPipelineV1,
    )
    from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
        derive_architectural_candidate_v1,
    )
    from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
        enrich_opening_privacy_parcel_edge_intelligence_v1,
    )
    from core.architecture.reasoning.architectural_baseline_floor_roof_geometry_v1 import (
        derive_architectural_floor_roof_geometry_v1,
    )
    from core.architecture.reasoning.architectural_baseline_structural_readiness_v1 import (
        analyze_architectural_structural_readiness_v1,
    )

    polygon = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    face_id, space_id = "FACE-R1", "SPACE-R1"
    resolved = {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "HD_RECONNECT_FROZEN_CHAIN_CHECK",
        "boundary_extraction": {
            "source_file": "frozen-check.dxf", "source_sha256": "5" * 64,
            "tolerance_audit": {"chosen_snap_tolerance_m": 0.001},
            "wall_face_graphs": {"R1": {"floor": "R1", "faces": [
                {"face_id": face_id, "start": polygon[0], "end": polygon[1]}]}},
            "wall_solid_graphs": {"R1": {"floor": "R1", "solids": [], "floor_envelopes": [
                {"envelope_id": "ENV-R1", "polygon": polygon}]}},
            "opening_host_graphs": {"R1": {"floor": "R1", "unresolved": [], "openings": [
                {"opening_id": "D-R1", "kind": "DOOR", "status": "RESOLVED",
                 "host_face_a": face_id, "side_a": space_id, "side_b": "EXTERIOR:R1"}]}},
            "space_boundary_graphs": {"R1": {"floor": "R1", "unresolved": [], "spaces": [
                {"space_id": space_id, "semantic_class": "LIVING_RECEPTION",
                 "external": False, "boundary_ids": [face_id], "polygon": polygon}]}},
            "access_graph": {
                "nodes": [{"id": space_id, "semantic_class": "LIVING_RECEPTION"},
                          {"id": "EXTERIOR:R1", "semantic_class": "EXTERIOR"}],
                "edges": [{"id": "D-R1", "from": space_id, "to": "EXTERIOR:R1",
                           "kind": "DOOR_ACCESS"}],
                "status": "RESOLVED"},
            "unresolved": [],
        },
        "semantic_regions": [], "constraints": [],
        "protected_constraints": [{"constraint_id": "PC-D-R1", "entity_id": "D-R1"}],
        "protected_entities": ["D-R1", face_id],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }
    accepted = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        resolved, candidate_id="HD-RECONNECT-FROZEN", candidate_version="1",
        acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["frozen"]})
    design_02 = derive_architectural_candidate_v1(
        accepted, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["d02"]})
    design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
        design_02, enrichment_provenance={"decision": "DESIGN_03", "evidence_ids": ["d03"]})
    design_04 = derive_architectural_floor_roof_geometry_v1(
        design_03,
        geometry_evidence={"contract": "ApprovedArchitecturalGeometryEvidenceV1",
                           "status": "VERIFIED",
                           "levels": [{"floor_id": "R1", "order": 0, "elevation": 0.0}],
                           "vertical_circulation": [],
                           "roof": {"status": "VERIFIED", "source_floor_id": "R1",
                                    "use_source_floor_envelope": True}},
        derivation_provenance={"decision": "DESIGN_04", "evidence_ids": ["d04"]})
    design_05 = analyze_architectural_structural_readiness_v1(
        design_04, readiness_evidence=None,
        analysis_provenance={"decision": "DESIGN_05", "evidence_ids": ["d05"]})

    assert accepted["contract"] == "AcceptedArchitecturalBaselineEnvelopeV1"
    assert design_02["contract"] == "DerivedArchitecturalCandidateV1"
    assert design_04["floor_geometries"]
    assert design_05["contract"] == "Design05StructuralReadinessCandidateV1"
    assert design_05["provenance"]["structural_synthesis_performed"] is False


def test_h_no_structure_bim_ifc_render_or_generation():
    report = reconnect_housediffusion_baseline()
    assert report["plan_counts"]["walls"] > 0
    source = (ROOT / "core/architecture/reasoning/housediffusion_baseline_reconnect_v1.py"
              ).read_text(encoding="utf-8")
    lines = "\n".join(line.strip() for line in source.splitlines()
                      if line.strip().startswith(("import ", "from ")))
    for token in ("import requests", "import comfy", "from comfy", "subprocess",
                  "ifcopenshell", "ezdxf", "render_runtime", "comfyui",
                  "structural_grid_engine", "structural_element_engine",
                  "full_bim_pipeline", "torch", "diffusers"):
        assert token not in lines, token


# ==========================================================
# I — production routing status and branch classification
# ==========================================================

def test_i_house_diffusion_remains_the_primary_generator(report):
    routing = report["production_routing"]
    assert routing["primary_plan_generator"] == "HouseDiffusion"
    assert routing["generation_policy"] == EXPECTED_GENERATION_POLICY
    assert routing["internal_generator_role"] == "DIAGNOSTIC_ONLY_NOT_A_CANDIDATE_SOURCE"
    assert routing["bypass_point"]
    # the primary path is NOT restored yet: that is the phase's blocker
    assert routing["house_diffusion_primary_path_restored"] is False


def test_i2_recent_internal_layout_branch_is_classified_diagnostic(report):
    classification = report["branch_classification"]
    assert classification["ArchitecturalHumanReadablePlanV1"] == CLASS_DIAGNOSTIC_BRANCH
    assert classification["CoherentArchitecturalFloorPlanV1"] == CLASS_DIAGNOSTIC_BRANCH
    assert classification["architectural_layout_intelligence_v1 (01A2B)"] == \
        CLASS_DIAGNOSTIC_BRANCH
    assert classification["treemap_zone_band_partition"] == \
        CLASS_LEGACY_INTERNAL_GENERATOR_BRANCH
    assert classification["retained"] is True
    assert classification["modified"] is False
    assert classification["continued"] is False


def test_i3_the_diagnostic_branch_is_not_deleted_or_modified():
    for relative in (
        "core/architecture/reasoning/architectural_design_robustness_01a.py",
        "core/architecture/reasoning/coherent_floor_plan_resolver_v1.py",
        "core/architecture/reasoning/architectural_layout_intelligence_v1.py",
    ):
        path = ROOT / relative
        assert path.is_file(), relative
        assert path.stat().st_size > 0


def test_report_is_serialisable(report):
    payload = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    assert payload["identity"]["status"] == STATUS_RECONNECTED
    assert payload["plan_counts"]["walls"] == 187
