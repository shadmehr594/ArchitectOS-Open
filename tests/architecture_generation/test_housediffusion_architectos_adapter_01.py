"""HOUSE-DIFFUSION-ARCHITECTOS-ADAPTER-01 targeted tests.

Proves the REAL accepted HouseDiffusion baseline can be adapted into
``AcceptedArchitecturalBaselineEnvelopeV1`` and consumed end-to-end by the
frozen Design-02 → Design-05 chain, losslessly and without any internal
rule-based generator participating.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from core.architecture.contracts.accepted_architectural_baseline_envelope_v1 import (
    verify_accepted_baseline_envelope,
)
from core.architecture.reasoning.housediffusion_accepted_baseline_adapter_v1 import (
    CONTRACT,
    FINAL_WINDOWS_NOT_CREATED,
    FORBIDDEN_INTERNAL_GENERATORS,
    INTERNAL_GENERATOR_BYPASS_DETECTED,
    InternalGeneratorBypassError,
    PARCEL_SITE_CONTEXT_PENDING,
    WALL_THICKNESS_METRIC_UNRESOLVED,
    WORLD_ORIENTATION_PENDING,
    HouseDiffusionAcceptedBaselineAdapterV1,
    _internal_generator_guard,
    adapt_housediffusion_accepted_baseline,
)
from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
    BASELINE_ROOT,
    EXPECTED_GENERATION_POLICY,
    EXPECTED_PRIMARY_GENERATOR,
    EXPECTED_SCHEMA,
)


ROOT = Path(__file__).resolve().parents[2]

FROZEN_STRUCTURAL_HASHES = {
    "core/structure/structural_grid_engine.py":
        "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py":
        "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
}

pytestmark = pytest.mark.skipif(
    not BASELINE_ROOT.is_dir(),
    reason=f"accepted HouseDiffusion baseline root not present: {BASELINE_ROOT}",
)


@pytest.fixture(scope="module")
def adapter():
    return HouseDiffusionAcceptedBaselineAdapterV1()


@pytest.fixture(scope="module")
def adapted(adapter):
    return adapter.adapt()


@pytest.fixture(scope="module")
def chain(adapter, adapted):
    return adapter.run_design_chain(adapted)


def _lineage(envelope):
    return envelope["boundary_extraction"]["house_diffusion_lineage"]


# ==========================================================
# A / B — the real baseline loads and is identity-verified
# ==========================================================

def test_a_real_baseline_loads(adapter):
    located = adapter.verifier.locate()
    assert located["root_present"] is True
    assert located["all_required_present"] is True


def test_b_baseline_identity_and_lineage_verified(adapter, adapted):
    identity = adapter.verifier.verify_identity()
    assert identity["status"] == "RECONNECTED"
    assert identity["failed_checks"] == []
    lineage = _lineage(adapted)
    assert lineage["source_schema"] == EXPECTED_SCHEMA
    assert lineage["source_generator"]["PRIMARY_PLAN_GENERATOR"] == EXPECTED_PRIMARY_GENERATOR
    assert EXPECTED_GENERATION_POLICY in str(lineage["source_generator"]["GENERATION_POLICY"])
    assert lineage["source_gate_baseline_complete"] == "YES"
    assert lineage["source_gate_blockers"] == 0
    assert lineage["geometry_resolved_via_ref"] is True
    assert lineage["geometry_unresolved"] == []


# ==========================================================
# C / D — tamper rejection
# ==========================================================

def test_c_adapter_rejects_tampered_generator_identity(tmp_path):
    for name in ("semantic_architectural_plan_baseline_v1.json",
                 "wall_registry_baseline_v1.json",
                 "opening_registry_baseline_v1.json",
                 "window_registry_provisional_v1.json",
                 "access_graph_baseline_v1.json",
                 "plan_completeness_gate_v1.json"):
        source = BASELINE_ROOT / name
        if source.is_file():
            (tmp_path / name).write_bytes(source.read_bytes())
    target = tmp_path / "semantic_architectural_plan_baseline_v1.json"
    document = json.loads(target.read_text(encoding="utf-8"))
    document["generator"]["PRIMARY_PLAN_GENERATOR"] = "InternalRuleBasedLayout"
    target.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError):
        HouseDiffusionAcceptedBaselineAdapterV1(tmp_path).adapt()


def test_d_adapter_rejects_broken_geometry_ref(tmp_path):
    """A broken geometry reference must be REPORTED, never silently invented.

    The accepted baseline copies no coordinates: every program space and the
    derived circulation carry ``geometry_ref {artifact, item_id,
    geometry_sha256}`` and their geometry is resolved from the source artifact.
    The adapter therefore has to be probed through the PER-ITEM ``geometry_ref``
    chain — that is the room geometry contract.  The document-level
    ``provenance.geometry`` pointer is only the envelope fallback, so tampering
    it alone would not touch room geometry at all.
    """
    for name in ("semantic_architectural_plan_baseline_v1.json",
                 "wall_registry_baseline_v1.json",
                 "opening_registry_baseline_v1.json",
                 "window_registry_provisional_v1.json",
                 "access_graph_baseline_v1.json",
                 "plan_completeness_gate_v1.json"):
        source = BASELINE_ROOT / name
        if source.is_file():
            (tmp_path / name).write_bytes(source.read_bytes())
    target = tmp_path / "semantic_architectural_plan_baseline_v1.json"
    document = json.loads(target.read_text(encoding="utf-8"))

    # the baseline genuinely carries no inline polygons ...
    assert all("polygon" not in space for space in document["1_program_spaces"])
    # ... so breaking the per-item geometry_ref is what actually breaks geometry
    broken = str(tmp_path / "missing-artifact.json")
    for space in document["1_program_spaces"]:
        space["geometry_ref"]["artifact"] = broken
    document["2_derived_circulation"]["geometry_ref"]["artifact"] = broken
    document["provenance"]["geometry"]["artifact"] = broken
    target.write_text(json.dumps(document), encoding="utf-8")

    envelope = HouseDiffusionAcceptedBaselineAdapterV1(tmp_path).adapt()
    lineage = _lineage(envelope)

    # the broken refs must be REPORTED, never silently invented
    assert lineage["geometry_unresolved"], "broken geometry_ref must be recorded"
    assert {item["reason"] for item in lineage["geometry_unresolved"]} == {
        "source_artifact_missing"}
    assert lineage["geometry_resolved_via_ref"] is True

    extraction = envelope["boundary_extraction"]
    spaces = extraction["space_boundary_graphs"]["ground_floor"]["spaces"]
    # every room that could not be resolved is accounted for, exactly once
    assert len(lineage["geometry_unresolved"]) == len(spaces)
    # fail closed: no polygon/perimeter may be invented for an unresolvable ref
    assert spaces
    assert all(room["polygon"] == [] for room in spaces)
    assert all(room["perimeter_m"] is None for room in spaces)
    # and no envelope or solid may be fabricated from the missing artifact
    solids = extraction["wall_solid_graphs"]["ground_floor"]
    assert solids["floor_envelopes"] == []
    assert solids["solids"] == []


# ==========================================================
# E / F / G — IDs preserved
# ==========================================================

def test_e_room_ids_and_identities_preserved(adapted):
    graph = adapted["boundary_extraction"]["space_boundary_graphs"]["ground_floor"]
    identities = {space["space_id"] for space in graph["spaces"]}
    assert identities == {
        "LIVING_RECEPTION", "CLOSED_KITCHEN", "MASTER_BEDROOM_SLEEPING",
        "BEDROOM_DOUBLE", "FAMILY_BATHROOM", "GUEST_WC", "UNIT_ENTRY",
        "TERRACE_BALCONY", "PRIVATE_DISTRIBUTION_POCKET",
    }
    for space in graph["spaces"]:
        assert space["canonical_name"] == space["space_id"]
        assert space["geometry_ref"]["geometry_sha256"]
        assert len(space["polygon"]) >= 4


def test_f_wall_ids_roles_and_centerlines_preserved(adapted):
    graph = adapted["boundary_extraction"]["wall_face_graphs"]["ground_floor"]
    faces = graph["faces"]
    assert len(faces) == 187
    roles = {face["wall_role"] for face in faces}
    assert roles == {"EXTERIOR", "INTERIOR"}
    for face in faces:
        assert face["wall_id"]
        assert face["face_id"] == f"FACE-{face['wall_id']}"
        assert len(face["start"]) == 2 and len(face["end"]) == 2

    registry_ids = {wall["wall_id"] for wall in
                    json.loads((BASELINE_ROOT / "wall_registry_baseline_v1.json").read_text(
                        encoding="utf-8"))["walls"]}
    assert {face["wall_id"] for face in faces} <= registry_ids


def test_g_opening_ids_types_and_hosts_preserved(adapted):
    graph = adapted["boundary_extraction"]["opening_host_graphs"]["ground_floor"]
    openings = graph["openings"]
    assert len(openings) == 9
    registry = json.loads((BASELINE_ROOT / "opening_registry_baseline_v1.json").read_text(
        encoding="utf-8"))["baseline_openings"]
    assert {item["opening_id"] for item in openings} == {item["id"] for item in registry}

    roles = {item["semantic_role"] for item in openings}
    assert "MAIN_ENTRANCE_DOOR" in roles
    classes = {item["opening_class"] for item in openings}
    assert {"NATIVE_DOOR", "DERIVED_DOOR", "DERIVED_FULL_WIDTH_PORTAL",
            "GLAZED_BALCONY_DOOR"} <= classes
    for item in openings:
        assert item["kind"] == "DOOR"
        assert item["host_boundary_id"]
        assert len(item["opening_segment"]) >= 2
        assert item["construction_claim"] is False


# ==========================================================
# H — access graph semantics preserved
# ==========================================================

def test_h_access_graph_semantics_preserved(adapted):
    graph = adapted["boundary_extraction"]["access_graph"]
    source = json.loads((BASELINE_ROOT / "access_graph_baseline_v1.json").read_text(
        encoding="utf-8"))
    assert len(graph["nodes"]) == len(source["nodes"])
    assert len(graph["edges"]) == len(source["edges"])
    assert graph["status"] == "RESOLVED"
    assert graph["method"] == source.get("method")
    # the accepted access graph is a list of space identities (strings); the
    # adapter must preserve both the order and the exact identities verbatim.
    assert graph["nodes"] == source["nodes"]
    assert all(isinstance(node, str) for node in graph["nodes"])
    assert [edge.get("opening_id") for edge in graph["edges"]] == [
        edge.get("opening_id") for edge in source["edges"]]
    assert [edge.get("a") for edge in graph["edges"]] == [
        edge.get("a") for edge in source["edges"]]
    assert [edge.get("b") for edge in graph["edges"]] == [
        edge.get("b") for edge in source["edges"]]


# ==========================================================
# I / J — symbolic wall handling
# ==========================================================

def test_i_symbolic_wall_thickness_remains_unresolved(adapted):
    graph = adapted["boundary_extraction"]["wall_face_graphs"]["ground_floor"]
    rule = graph["wall_band_rule"]
    assert rule["wall_band_type"] == "SYMBOLIC_RELATIVE"
    assert rule["metric_thickness"] == "UNKNOWN"
    assert rule["status"] == WALL_THICKNESS_METRIC_UNRESOLVED
    assert rule["construction_claim"] is False
    codes = {item["code"] for item in adapted["boundary_extraction"]["unresolved"]}
    assert WALL_THICKNESS_METRIC_UNRESOLVED in codes


def test_j_no_construction_thickness_invented(adapted):
    # no wall band may carry a metric/construction thickness claim
    graph = adapted["boundary_extraction"]["wall_face_graphs"]["ground_floor"]
    assert graph["wall_band_rule"]["metric_thickness"] == "UNKNOWN"
    assert graph["wall_band_rule"]["construction_claim"] is False
    for face in graph["faces"]:
        assert face["construction_claim"] is False
        assert face["thickness_status"] == WALL_THICKNESS_METRIC_UNRESOLVED
        band = face["wall_band"] or {}
        assert band.get("metric_thickness") in (None, "UNKNOWN")
        assert band.get("construction_claim") is False
        # a symbolic relative band is allowed; a metric thickness field is not
        for metric_key in ("thickness_m", "thickness_mm", "thickness_meters",
                           "metric_thickness_m", "construction_thickness"):
            assert band.get(metric_key) is None, (face["wall_id"], metric_key)
    solids = adapted["boundary_extraction"]["wall_solid_graphs"]["ground_floor"]
    assert solids["solids"] == []
    for envelope in solids["floor_envelopes"]:
        assert envelope["construction_claim"] is False

    # no construction claim anywhere in the wall/solid graphs
    def _no_true_construction_claim(node):
        if isinstance(node, dict):
            if node.get("construction_claim") is True:
                raise AssertionError(f"construction_claim=True at {node}")
            for value in node.values():
                _no_true_construction_claim(value)
        elif isinstance(node, list):
            for item in node:
                _no_true_construction_claim(item)

    _no_true_construction_claim(graph)
    _no_true_construction_claim(solids)


# ==========================================================
# K — no final windows invented
# ==========================================================

def test_k_no_final_windows_invented(adapted):
    graph = adapted["boundary_extraction"]["opening_host_graphs"]["ground_floor"]
    assert all(item["kind"] != "WINDOW" for item in graph["openings"])
    codes = {item["code"] for item in adapted["boundary_extraction"]["unresolved"]}
    assert FINAL_WINDOWS_NOT_CREATED in codes
    windows = json.loads(
        (BASELINE_ROOT / "window_registry_provisional_v1.json").read_text(encoding="utf-8"))
    assert windows.get("FINAL_WINDOWS_CREATED") in ("NO", None)


# ==========================================================
# L / M / N / O / P / Q — graph realization from real geometry
# ==========================================================

def test_l_boundary_extraction_created_from_real_geometry(adapted):
    extraction = adapted["boundary_extraction"]
    assert extraction["source_file"] == "house_diffusion_accepted_baseline_v1"
    assert extraction["source_sha256"]
    for key in ("wall_face_graphs", "wall_solid_graphs", "opening_host_graphs",
                "space_boundary_graphs", "access_graph"):
        assert isinstance(extraction.get(key), (dict,)), key
    assert extraction["house_diffusion_lineage"]["preservation"]["geometry_invented"] is False


def test_m_wall_face_graphs_created_from_real_walls(adapted):
    faces = adapted["boundary_extraction"]["wall_face_graphs"]["ground_floor"]["faces"]
    assert len(faces) == 187
    assert sum(1 for f in faces if f["wall_role"] == "EXTERIOR") == 168
    assert sum(1 for f in faces if f["wall_role"] == "INTERIOR") == 19


def test_n_wall_solid_graphs_created_without_construction_claim(adapted):
    graph = adapted["boundary_extraction"]["wall_solid_graphs"]["ground_floor"]
    assert graph["solids"] == []
    assert graph["floor_envelopes"]
    assert graph["unresolved"][0]["code"] == WALL_THICKNESS_METRIC_UNRESOLVED


def test_o_opening_host_graphs_created_from_real_openings(adapted):
    graph = adapted["boundary_extraction"]["opening_host_graphs"]["ground_floor"]
    assert len(graph["openings"]) == 9
    assert graph["unresolved"] == []
    for item in graph["openings"]:
        assert item["host_face_a"].startswith("FACE-")
        assert item["side_a"] and item["side_b"]


def test_p_space_boundary_graphs_created_from_real_rooms(adapted):
    graph = adapted["boundary_extraction"]["space_boundary_graphs"]["ground_floor"]
    assert len(graph["spaces"]) == 9
    source = json.loads(
        (BASELINE_ROOT / "architectural_refinement_01/refined_semantic_plan_candidate_v1_4.json")
        .read_text(encoding="utf-8")) if (
            BASELINE_ROOT / "architectural_refinement_01/refined_semantic_plan_candidate_v1_4.json"
        ).is_file() else None
    for space in graph["spaces"]:
        assert space["polygon"]
        assert space["area_m2"] is not None
    if source:
        real = {s["architectos_identity"]: s["polygon"] for s in source["spaces"]}
        for space in graph["spaces"]:
            if space["space_id"] in real:
                assert space["polygon"] == [[float(p[0]), float(p[1])]
                                            for p in real[space["space_id"]]]


def test_q_access_graph_created_from_real_access_graph(adapted):
    graph = adapted["boundary_extraction"]["access_graph"]
    assert graph["provenance"]["source"] == "house_diffusion_access_graph_baseline_v1"
    assert len(graph["nodes"]) == 10
    assert len(graph["edges"]) == 9


# ==========================================================
# R — the envelope is accepted by the canonical acceptance function
# ==========================================================

def test_r_accepted_baseline_envelope_accepts_the_adapter_output(adapted):
    assert adapted["contract"] == "AcceptedArchitecturalBaselineEnvelopeV1"
    assert adapted["acceptance_status"] == "ACCEPTED_FROZEN"
    assert adapted["architecture_only"] is True
    assert verify_accepted_baseline_envelope(adapted) is True
    snapshot = adapted["semantic_snapshot"]
    assert snapshot["access_evidence_status"] == "RESOLVED"
    assert snapshot["canonical_record_references"]["spaces"]["record_ids"]
    assert snapshot["canonical_record_references"]["doors"]["record_ids"]
    for key in ("wall_face_graphs", "wall_solid_graphs", "opening_host_graphs",
                "space_boundary_graphs", "access_graph"):
        assert snapshot["graph_availability"][key]["status"] == "PRESENT", key


# ==========================================================
# S / T / U / V / W — the REAL HouseDiffusion chain
# ==========================================================

def test_s_design_02_accepts_the_real_housediffusion_result(chain, adapted):
    design_02 = chain["design_02"]
    assert design_02["contract"] == "DerivedArchitecturalCandidateV1"
    assert design_02["parent_baseline_id"] == adapted["candidate_id"]
    assert design_02["parent_baseline_hash"] == adapted["candidate_hash"]


def test_t_design_03_accepts_the_real_housediffusion_result(chain, adapted):
    design_03 = chain["design_03"]
    assert design_03["contract"] == "Design03DerivedArchitecturalCandidateV1"
    assert design_03["parent_baseline_hash"] == adapted["candidate_hash"]
    assert design_03["parent_candidate_id"] == chain["design_02"]["candidate_id"]


def test_u_design_04_accepts_the_real_housediffusion_result(chain):
    design_04 = chain["design_04"]
    assert design_04["contract"] == "Design04DerivedArchitecturalGeometryCandidateV1"
    assert design_04["floor_geometries"]
    codes = {item.get("code") for item in (design_04.get("unresolved_evidence") or [])}
    assert "no_verified_architectural_roof_evidence_no_roof_geometry_guessed" in codes
    assert design_04["roof_geometries"] == [] or all(
        roof.get("roof_type") in (None, "UNKNOWN") for roof in design_04["roof_geometries"])
    assert design_04["provenance"]["roof_properties_defaulted"] is False


def test_v_design_05_accepts_the_real_housediffusion_result(chain):
    design_05 = chain["design_05"]
    assert design_05["contract"] == "Design05StructuralReadinessCandidateV1"
    assert design_05["readiness_status"] in (
        "READY_FOR_STRUCTURAL_SYNTHESIS", "READY_WITH_ARCHITECTURAL_GAPS")
    assert design_05["eligible_support_regions"]


def test_w_design_05_does_not_synthesize_structure(chain):
    design_05 = chain["design_05"]
    assert design_05["provenance"]["structural_synthesis_performed"] is False
    assert design_05["generated_structural_elements"] == []
    assert design_05["legacy_structural_grid_guard"]["structural_grid_engine_modified"] is False
    assert design_05["legacy_structural_grid_guard"]["architecture_resize_to_grid_allowed"] is False


# ==========================================================
# X — internal generator never invoked
# ==========================================================

def test_x_internal_layout_generator_never_invoked(adapted):
    preservation = _lineage(adapted)["preservation"]
    assert preservation["internal_generator_used"] is False
    source = (ROOT / "core/architecture/reasoning/"
              "housediffusion_accepted_baseline_adapter_v1.py").read_text(encoding="utf-8")
    lines = "\n".join(line.strip() for line in source.splitlines()
                      if line.strip().startswith(("import ", "from ")))
    for forbidden in FORBIDDEN_INTERNAL_GENERATORS:
        assert forbidden not in lines, forbidden


def test_x2_guard_fails_on_internal_generator_participation():
    key = "core.architecture.reasoning.layout_reasoner"
    # The guard detects modules NEWLY imported inside the block, so the key must
    # be absent beforehand.  Another suite sharing the pytest session may already
    # have imported it (architectural_brain -> layout_reasoner), so make this
    # test independent of suite ordering rather than relying on session state.
    previous = sys.modules.pop(key, None)
    try:
        with pytest.raises(InternalGeneratorBypassError) as caught:
            with _internal_generator_guard():
                sys.modules[key] = None
        assert INTERNAL_GENERATOR_BYPASS_DETECTED in str(caught.value)
    finally:
        sys.modules.pop(key, None)
        if previous is not None:
            sys.modules[key] = previous


# ==========================================================
# Y / Z — nothing outside the adapter was touched
# ==========================================================

def test_y_baseline_files_untouched(adapter):
    located = adapter.verifier.locate()
    for name, item in located["artifacts"].items():
        assert item["present"] is True, name
        assert item["bytes"] > 0, name
    # hashes must still match what the reconnect verifier recorded
    assert adapter.verifier.verify_identity()["status"] == "RECONNECTED"


def test_z_house_diffusion_lab_source_untouched():
    lab = Path(r"D:\AI_Architecture_Lab\house_diffusion")
    if lab.is_dir():
        assert (lab / "architectos_to_housediffusion.py").is_file()
    for relative, expected in FROZEN_STRUCTURAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


# ==========================================================
# AA / AB — determinism
# ==========================================================

def test_aa_deterministic_output(adapter):
    first = adapter.adapt()
    second = adapter.adapt()
    assert first["candidate_hash"] == second["candidate_hash"]
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str)


def test_ab_same_baseline_same_adapter_hash(adapter):
    first = adapter.adapt(candidate_id="HD-AB-01", candidate_version="7")
    second = adapter.adapt(candidate_id="HD-AB-01", candidate_version="7")
    assert first["candidate_hash"] == second["candidate_hash"]
    assert first["candidate_id"] == "HD-AB-01"
    assert verify_accepted_baseline_envelope(first) is True
    # a different accepted identity must produce a different envelope hash
    third = adapter.adapt(candidate_id="HD-AB-02", candidate_version="7")
    assert third["candidate_hash"] != first["candidate_hash"]


def test_lineage_report_fields(adapted):
    lineage = _lineage(adapted)
    assert lineage["adapter"] == CONTRACT
    assert lineage["direction"] == (
        "SemanticArchitecturalPlanBaselineV1 -> AcceptedArchitecturalBaselineEnvelopeV1")
    assert lineage["counts"] == {
        "rooms": 9, "program_rooms": 8, "walls": 187, "exterior_walls": 168,
        "interior_walls": 19, "openings": 9, "access_nodes": 10, "access_edges": 9,
    }
    preservation = lineage["preservation"]
    for key in ("geometry_moved", "geometry_resized", "geometry_merged", "geometry_split",
                "geometry_invented", "metric_wall_thickness_invented",
                "final_windows_invented", "world_orientation_invented",
                "parcel_context_invented", "internal_generator_used",
                "house_diffusion_modified"):
        assert preservation[key] is False, key


def test_pending_evidence_is_explicit(adapted):
    codes = {item["code"] for item in adapted["boundary_extraction"]["unresolved"]}
    assert codes == {
        WALL_THICKNESS_METRIC_UNRESOLVED, FINAL_WINDOWS_NOT_CREATED,
        WORLD_ORIENTATION_PENDING, PARCEL_SITE_CONTEXT_PENDING,
    }


def test_module_level_wrapper(adapter):
    envelope = adapt_housediffusion_accepted_baseline()
    assert envelope["contract"] == "AcceptedArchitecturalBaselineEnvelopeV1"
    assert verify_accepted_baseline_envelope(envelope) is True


def test_adapter_does_not_mutate_the_envelope_after_hashing(adapted):
    snapshot = deepcopy(adapted)
    assert verify_accepted_baseline_envelope(adapted) is True
    assert adapted == snapshot
