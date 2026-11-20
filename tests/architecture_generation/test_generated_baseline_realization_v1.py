"""HOUSE-DIFFUSION-PRODUCTION-PATH-02A — GeneratedBaselineRealizationV1 tests.

Proves a REAL FRESH HouseDiffusion ``SemanticPlanCandidateV2`` (not the historical
frozen baseline) reaches:

    GeneratedBaselineRealizationV1
    -> GeneratedArchitecturalBaselineV1
    -> HouseDiffusionAcceptedBaselineAdapterV1 (explicit generated path)
    -> AcceptedArchitecturalBaselineEnvelopeV1
    -> Design-02 -> Design-03 -> Design-04 -> Design-05

with full lineage, no invention, and no internal generator.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from core.architecture.contracts.generated_architectural_baseline_v1 import (
    CONTRACT,
    FORBIDDEN_HISTORICAL_PHASE,
    GENERATION_POLICY,
    GeneratedBaselineVerificationError,
    SOURCE_CANDIDATE_SCHEMA,
    SOURCE_ENGINE_HOUSE_DIFFUSION,
    assert_generated_architectural_baseline,
    generated_baseline_sha256,
    verify_generated_architectural_baseline,
)
from core.architecture.contracts.accepted_architectural_baseline_envelope_v1 import (
    verify_accepted_baseline_envelope,
)
from core.architecture.reasoning.generated_baseline_realization_v1 import (
    GeneratedBaselineRealizationV1,
    realize_generated_baseline,
)
from core.architecture.reasoning.housediffusion_accepted_baseline_adapter_v1 import (
    HouseDiffusionAcceptedBaselineAdapterV1,
)
from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
    BASELINE_ROOT,
)


ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = ROOT / "exports" / "housediffusion_production_path_02a"
REALIZATION_MODULE = (ROOT / "core/architecture/reasoning/"
                      "generated_baseline_realization_v1.py")

#: Real fresh candidates produced by the frozen HouseDiffusion engine.
FRESH_CANDIDATES = sorted(EXPORT_DIR.glob("SOURCE_CANDIDATE_*.json"))
#: The original fresh candidate from the verified generation phase.
LEGACY_FRESH = Path(r"D:\AI_Architecture_Lab\full_program_02\semantic_plan_candidate_v2.json")

#: Literals that belong ONLY to the historical bespoke chain (category C/D).
HISTORICAL_HARDCODE_TOKENS = (
    "-0.3726", "0.19747", "0.20527", "0.5583", "0.5661",
    "-0.2188", "0.0937", "0.7109", "-0.1250", "0.4297",
    "0.1486", "0.1171875",
)
HISTORICAL_PATH_TOKENS = (
    "architectural_refinement_01", "wall_opening_02", "access_semantics_02a",
    "plan_completion_02b", "window_intelligence_01", "window_selection_01a",
    "daylight_exterior_access_01b", "baseline_architectural_plan_01",
    "refined_semantic_plan_candidate_v1_4",
)
HISTORICAL_ROOM_LIST_TOKENS = ("PRIVATE_DISTRIBUTION_POCKET",)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_candidates() -> list[tuple[str, dict]]:
    items: list[tuple[str, dict]] = []
    for path in FRESH_CANDIDATES:
        items.append((path.name, _load(path)))
    if LEGACY_FRESH.is_file():
        items.append((LEGACY_FRESH.name, _load(LEGACY_FRESH)))
    return items


pytestmark = pytest.mark.skipif(
    not FRESH_CANDIDATES and not LEGACY_FRESH.is_file(),
    reason="no real HouseDiffusion candidate available",
)


@pytest.fixture(scope="module")
def candidates():
    items = _all_candidates()
    if not items:
        pytest.skip("no real HouseDiffusion candidate available")
    return items


@pytest.fixture(scope="module")
def realized(candidates):
    return [(name, realize_generated_baseline(candidate)) for name, candidate in candidates]


@pytest.fixture(scope="module")
def primary(realized):
    return realized[0][1]


@pytest.fixture(scope="module")
def adapter():
    return HouseDiffusionAcceptedBaselineAdapterV1()


# ==========================================================
# A — a fresh HD candidate is accepted by the realization layer
# ==========================================================

def test_a_fresh_candidate_is_realized(realized):
    assert realized
    for name, document in realized:
        assert document["schema"] == CONTRACT, name
        assert document["baseline_origin"] == "GENERATED", name
        assert document["source_engine"] == SOURCE_ENGINE_HOUSE_DIFFUSION, name
        assert document["source_candidate_schema"] == SOURCE_CANDIDATE_SCHEMA, name
        assert document["generation_policy"] == GENERATION_POLICY, name
        assert verify_generated_architectural_baseline(document)["status"] == "VERIFIED", name


def test_a2_realization_rejects_a_non_housediffusion_candidate(primary):
    tampered = deepcopy(primary)
    with pytest.raises(ValueError):
        realize_generated_baseline({"schema": SOURCE_CANDIDATE_SCHEMA,
                                    "source_engine": "INTERNAL_ARCHITECTOS",
                                    "spaces": []})


# ==========================================================
# B / C — candidate hash and seed preserved
# ==========================================================

def test_b_candidate_hash_preserved(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        assert document["source_candidate_id"] == candidate.get("candidate_id"), name
        stored = document["source_candidate_sha256"]
        assert isinstance(stored, str) and len(stored) == 64, name
        report = verify_generated_architectural_baseline(
            document, source_candidate=candidate)
        assert report["status"] == "VERIFIED", (name, report["failed_checks"])


def test_c_seed_preserved(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        assert document["generation_seed"] == candidate.get("source_seed"), name
        assert document["generator_lineage"]["source_seed"] == candidate.get("source_seed")


# ==========================================================
# D / E — room IDs and polygons preserved verbatim
# ==========================================================

def test_d_room_ids_preserved(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        floor = next(iter(document["floors"].values()))
        source_ids = [s["architectos_identity"] for s in candidate["spaces"]]
        assert [s["space_id"] for s in floor["spaces"]] == source_ids, name
        assert document["program_lineage"]["identity_preserved"] is True
        assert document["program_lineage"]["relabeled"] is False


def test_e_room_polygons_preserved(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        floor = next(iter(document["floors"].values()))
        source = {s["architectos_identity"]: s["polygon"] for s in candidate["spaces"]}
        for space in floor["spaces"]:
            expected = [[round(float(x), 9), round(float(y), 9)]
                        for x, y in source[space["space_id"]]]
            assert space["polygon"] == expected, (name, space["space_id"])
        assert document["geometry_lineage"]["geometry_invented"] is False
        for key in ("geometry_moved", "geometry_resized", "geometry_merged",
                    "geometry_split"):
            assert document["geometry_lineage"][key] is False


# ==========================================================
# F — no internal generator invoked
# ==========================================================

def test_f_no_internal_generator_invoked(primary):
    for key in ("internal_generator_used", "historical_chain_used",
                "historical_hardcoded_coordinates_used"):
        assert primary["realization"][key] is False, key
    assert primary["generator_lineage"]["internal_generator_used"] is False
    blob = json.dumps(primary["generator_lineage"]).lower()
    for token in ("layout_reasoner", "spatial_placement_reasoner", "plan_model_reasoner",
                  "knowledge_space_generator", "coherent_floor_plan_resolver",
                  "architectural_layout_intelligence", "architectural_brain", "treemap"):
        assert token not in blob, token


# ==========================================================
# G / H / I — no historical plan-specific dependency
# ==========================================================

def _code_only(text: str) -> str:
    """Strip the module docstring and line comments.

    The realization module legitimately *names* the historical chain in prose to
    document that it is NOT used; the guard must scan executable code only.
    """
    import ast

    tree = ast.parse(text)
    lines = text.splitlines()
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        for index in range(tree.body[0].lineno - 1, tree.body[0].end_lineno):
            lines[index] = ""
    return "\n".join(line.split("#", 1)[0] for line in lines)


def test_g_no_historical_fixed_room_list_required():
    text = _code_only(REALIZATION_MODULE.read_text(encoding="utf-8"))
    for token in HISTORICAL_ROOM_LIST_TOKENS:
        assert token not in text, token


def test_h_no_historical_fixed_path_required():
    text = _code_only(REALIZATION_MODULE.read_text(encoding="utf-8"))
    for token in HISTORICAL_PATH_TOKENS:
        assert token not in text, token


def test_i_no_hardcoded_coordinate_dependency():
    text = _code_only(REALIZATION_MODULE.read_text(encoding="utf-8"))
    for token in HISTORICAL_HARDCODE_TOKENS:
        assert token not in text, token


def test_i2_realization_is_portable_across_candidates(candidates, realized):
    """Different candidates with the same program must all realize."""
    assert len(realized) >= 2
    counts = {len(next(iter(d["floors"].values()))["spaces"]) for _, d in realized}
    assert counts  # at least one non-empty realization
    for name, document in realized:
        assert document["floors"], name


# ==========================================================
# J — symbolic wall handling
# ==========================================================

def test_j_symbolic_wall_thickness_unresolved(primary):
    floor = next(iter(primary["floors"].values()))
    rule = floor["wall_band_rule"]
    assert rule["wall_band_type"] == "SYMBOLIC_RELATIVE"
    assert rule["metric_thickness"] == "UNKNOWN"
    assert rule["construction_claim"] is False
    assert floor["walls"]
    for wall in floor["walls"]:
        assert wall["thickness_status"] == "WALL_THICKNESS_METRIC_UNRESOLVED"
        assert wall["construction_claim"] is False
        assert wall["wall_band"]["construction_claim"] is False
        assert wall["wall_band"]["metric_thickness"] in (None, "UNKNOWN")
        for key in ("thickness_m", "thickness_mm", "thickness_meters",
                    "metric_thickness_m", "construction_thickness", "wall_thickness_m"):
            assert key not in wall["wall_band"], (wall["wall_id"], key)
    codes = {item["code"] for item in primary["unresolved"]}
    assert "WALL_THICKNESS_METRIC_UNRESOLVED" in codes


# ==========================================================
# K / L — no doors or windows invented
# ==========================================================

def test_k_no_doors_invented(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        floor = next(iter(document["floors"].values()))
        source_ids = {d["door_id"] for d in candidate["doors"]}
        assert {o["opening_id"] for o in floor["openings"]} == source_ids, name
        for opening in floor["openings"]:
            assert opening["construction_claim"] is False
            assert opening["provenance"]["door_invented"] is False


def test_l_no_windows_invented(candidates, realized):
    for name, candidate in candidates:
        assert not candidate.get("windows"), name
    for name, document in realized:
        floor = next(iter(document["floors"].values()))
        assert floor["windows"] == [], name
        assert floor["window_status"] == "UNRESOLVED_OR_NOT_PROVIDED", name
        assert document["realization"]["windows_invented"] is False
    codes = {item["code"] for item in primary_of(realized)["unresolved"]}
    assert "UNRESOLVED_OR_NOT_PROVIDED" in codes


def primary_of(realized):
    return realized[0][1]


# ==========================================================
# M — access derived only from proven evidence
# ==========================================================

def test_m_access_graph_only_from_explicit_evidence(candidates, realized):
    for (name, candidate), (_, document) in zip(candidates, realized):
        access = document["access_graph"]
        assert access["provenance"]["proximity_inference_used"] is False
        assert access["provenance"]["doors_invented"] is False
        door_ids = {d["door_id"] for d in candidate["doors"]}
        for edge in access["edges"]:
            assert edge["evidence"] == "EXPLICIT_SOURCE_DOOR", name
            assert edge["opening_id"] in door_ids, name
        assert set(access["nodes"]) >= {s["architectos_identity"]
                                        for s in candidate["spaces"]}


def test_m2_unreachable_spaces_are_reported_not_invented(realized):
    for name, document in realized:
        access = document["access_graph"]
        unreachable = [u for u in access["unresolved"]
                       if u["code"] == "SPACE_WITHOUT_EXPLICIT_ACCESS"]
        if unreachable:
            assert access["status"] == "PARTIAL", name
            for item in unreachable:
                assert item["space_id"]
        else:
            assert access["status"] == "RESOLVED", name


# ==========================================================
# N / O / P — fail closed
# ==========================================================

def test_n_invalid_geometry_ref_fails_closed(primary):
    tampered = deepcopy(primary)
    floor = next(iter(tampered["floors"].values()))
    floor["spaces"][0]["geometry_sha256"] = "0" * 64
    report = verify_generated_architectural_baseline(tampered)
    assert report["status"] == "REJECTED"
    assert "geometry_refs_resolve" in report["failed_checks"]
    with pytest.raises(GeneratedBaselineVerificationError):
        assert_generated_architectural_baseline(tampered)


def test_o_dangling_opening_host_fails_closed(primary):
    tampered = deepcopy(primary)
    floor = next(iter(tampered["floors"].values()))
    floor["openings"][0]["host_wall_id"] = "GW-DOES-NOT-EXIST"
    report = verify_generated_architectural_baseline(tampered)
    assert report["status"] == "REJECTED"
    assert "no_dangling_opening_hosts" in report["failed_checks"]


def test_o2_unresolved_host_is_explicit_not_fabricated(primary):
    floor = next(iter(primary["floors"].values()))
    for opening in floor["openings"]:
        if opening["host_wall_id"] is None:
            assert opening["host_status"] == "UNRESOLVED"
        else:
            assert opening["host_status"] == "RESOLVED"
            assert opening["host_wall_id"] in {w["wall_id"] for w in floor["walls"]}


def test_p_tampered_source_candidate_hash_rejected(candidates, realized):
    name, candidate = candidates[0]
    document = realized[0][1]
    tampered = deepcopy(candidate)
    tampered["spaces"] = tampered["spaces"][:-1]
    report = verify_generated_architectural_baseline(document, source_candidate=tampered)
    assert report["status"] == "REJECTED"
    assert "source_candidate_hash_matches_loaded_candidate" in report["failed_checks"]


def test_p2_tampered_realization_hash_rejected(primary):
    tampered = deepcopy(primary)
    tampered["realization_sha256"] = "f" * 64
    report = verify_generated_architectural_baseline(tampered)
    assert report["status"] == "REJECTED"
    assert "realization_hash_matches" in report["failed_checks"]


# ==========================================================
# Q — the historical frozen path is unchanged
# ==========================================================

def test_q_historical_frozen_baseline_still_verifies(adapter):
    if not BASELINE_ROOT.is_dir():
        pytest.skip(f"historical baseline not present: {BASELINE_ROOT}")
    identity = adapter.verifier.verify_identity()
    assert identity["status"] == "RECONNECTED"
    assert identity["failed_checks"] == []
    envelope = adapter.adapt()
    assert verify_accepted_baseline_envelope(envelope) is True
    lineage = envelope["boundary_extraction"]["house_diffusion_lineage"]
    assert lineage["source_phase"] == FORBIDDEN_HISTORICAL_PHASE
    assert lineage["counts"]["walls"] == 187


# ==========================================================
# R — the generated baseline never claims historical identity
# ==========================================================

def test_r_no_historical_consolidation_identity(primary):
    assert primary["schema"] != "SemanticArchitecturalPlanBaselineV1"
    assert primary.get("phase") != FORBIDDEN_HISTORICAL_PHASE
    assert primary["baseline_origin"] == "GENERATED"
    blob = json.dumps(primary)
    assert FORBIDDEN_HISTORICAL_PHASE not in blob
    report = verify_generated_architectural_baseline(primary)
    assert report["checks"]["no_historical_phase_impersonation"] is True
    assert report["checks"]["no_historical_schema_impersonation"] is True


# ==========================================================
# S / T — adapter generated path and accepted envelope
# ==========================================================

def test_s_adapter_accepts_generated_baseline(adapter, primary):
    envelope = adapter.adapt_generated(primary, candidate_id="HD-GEN-TEST", candidate_version="1")
    assert envelope["contract"] == "AcceptedArchitecturalBaselineEnvelopeV1"
    assert envelope["acceptance_status"] == "ACCEPTED_FROZEN"
    assert envelope["source_candidate_id"] == "HD-GEN-TEST"
    lineage = envelope["boundary_extraction"]["generated_baseline_lineage"]
    assert lineage["baseline_origin"] == "GENERATED"
    assert lineage["historical_consolidation_impersonated"] is False
    assert lineage["preservation"]["internal_generator_used"] is False


def test_s2_adapter_generated_path_rejects_a_tampered_document(adapter, primary):
    tampered = deepcopy(primary)
    tampered["realization_sha256"] = "a" * 64
    with pytest.raises(GeneratedBaselineVerificationError):
        adapter.adapt_generated(tampered, candidate_id="HD-GEN-BAD", candidate_version="1")


def test_t_reaches_accepted_envelope(adapter, primary):
    envelope = adapter.adapt_generated(primary, candidate_id="HD-GEN-TEST", candidate_version="1")
    assert verify_accepted_baseline_envelope(envelope) is True
    snapshot = envelope["semantic_snapshot"]
    for key in ("wall_face_graphs", "wall_solid_graphs", "opening_host_graphs",
                "space_boundary_graphs", "access_graph"):
        assert snapshot["graph_availability"][key]["status"] == "PRESENT", key
    assert snapshot["canonical_record_references"]["spaces"]["record_ids"]
    assert snapshot["canonical_record_references"]["doors"]["record_ids"]
    assert snapshot["canonical_record_references"]["windows"]["record_ids"] == []


# ==========================================================
# U / V / W / X / Y — the frozen design chain on a REAL generated baseline
# ==========================================================

@pytest.fixture(scope="module")
def chain(adapter, primary):
    envelope = adapter.adapt_generated(primary, candidate_id="HD-GEN-TEST", candidate_version="1")
    return adapter.run_design_chain(envelope)


def test_u_design_02(chain):
    assert chain["design_02"]["contract"] == "DerivedArchitecturalCandidateV1"


def test_v_design_03(chain):
    assert chain["design_03"]["contract"] == "Design03DerivedArchitecturalCandidateV1"
    assert chain["design_03"]["parent_baseline_hash"] == chain["design_02"]["parent_baseline_hash"]


def test_w_design_04_without_inventing_roofs(chain):
    design_04 = chain["design_04"]
    assert design_04["contract"] == "Design04DerivedArchitecturalGeometryCandidateV1"
    assert design_04["floor_geometries"]
    assert design_04["provenance"]["roof_properties_defaulted"] is False
    codes = {item.get("code") for item in (design_04.get("unresolved_evidence") or [])}
    assert "no_verified_architectural_roof_evidence_no_roof_geometry_guessed" in codes
    assert design_04["roof_geometries"] == [] or all(
        roof.get("roof_type") in (None, "UNKNOWN") for roof in design_04["roof_geometries"])


def test_x_design_05_is_readiness_only(chain):
    design_05 = chain["design_05"]
    assert design_05["contract"] == "Design05StructuralReadinessCandidateV1"
    assert design_05["readiness_status"] in (
        "READY_FOR_STRUCTURAL_SYNTHESIS", "READY_WITH_ARCHITECTURAL_GAPS")


def test_y_no_structure_synthesized(chain):
    design_05 = chain["design_05"]
    assert design_05["provenance"]["structural_synthesis_performed"] is False
    assert design_05["generated_structural_elements"] == []
    assert design_05["legacy_structural_grid_guard"]["structural_grid_engine_modified"] is False


# ==========================================================
# Z — multiple real candidates realize successfully
# ==========================================================

def test_z_multiple_real_candidates_realize(adapter, realized):
    assert len(realized) >= 2, "at least two real candidates are required"
    for name, document in realized:
        envelope = adapter.adapt_generated(document, candidate_id=f"HD-GEN-{name}",
                                           candidate_version="1")
        assert verify_accepted_baseline_envelope(envelope) is True, name
        chain = adapter.run_design_chain(envelope)
        assert chain["design_05"]["contract"] == "Design05StructuralReadinessCandidateV1", name


# ==========================================================
# AA / AB — determinism and distinct lineage
# ==========================================================

def test_aa_same_input_same_realization_hash(candidates):
    for name, candidate in candidates:
        first = realize_generated_baseline(candidate)
        second = realize_generated_baseline(candidate)
        assert first["realization_sha256"] == second["realization_sha256"], name
        assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
            second, sort_keys=True, default=str), name
        assert first["realization_sha256"] == generated_baseline_sha256(first)


def test_ab_different_candidate_distinct_lineage(realized):
    hashes = {document["source_candidate_sha256"] for _, document in realized}
    assert len(hashes) == len(realized), "distinct candidates must have distinct source hashes"
    realization_hashes = {document["realization_sha256"] for _, document in realized}
    assert len(realization_hashes) == len(realized)
