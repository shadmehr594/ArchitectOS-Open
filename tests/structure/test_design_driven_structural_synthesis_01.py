"""DESIGN-DRIVEN-STRUCTURAL-SYNTHESIS-01 acceptance tests.

Existing structural engine audit + Design-05 input adapter + support / grid
candidate analysis.

The suite proves architectural compatibility ONLY.  It never generates final
columns / beams / slabs, never selects a structural system or member size, never
runs the existing StructuralGridEngine / StructuralElementEngine, and never runs
BIM / IFC / CAD / render.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
    derive_architectural_candidate_v1,
)
from core.architecture.reasoning.architectural_baseline_floor_roof_geometry_v1 import (
    derive_architectural_floor_roof_geometry_v1,
)
from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
    enrich_opening_privacy_parcel_edge_intelligence_v1,
)
from core.architecture.reasoning.architectural_baseline_structural_readiness_v1 import (
    analyze_architectural_structural_readiness_v1,
)
from core.structure.structural_architecture_input_adapter_v1 import (
    StructuralArchitectureInputAdapterError,
    StructuralArchitectureInputAdapterV1,
)
from core.structure.structural_support_candidate_analysis_v1 import (
    STATUS_ANALYSIS_READY,
    STATUS_ANALYSIS_READY_WITH_GAPS,
    STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED,
    STATUS_NO_VALID_SUPPORT_REGION,
    STATUS_PROTECTED_ZONE_CONFLICT,
    STATUS_STALE_PARENT,
    StructuralSupportCandidateAnalysisV1,
    analyze_structural_support_candidates_v1,
)


ROOT = Path(__file__).resolve().parents[2]

# Section 12 / section 20: the EXISTING structural engines must remain byte-identical.
FROZEN_STRUCTURAL_FILES = (
    "core/structure/structural_grid_engine.py",
    "core/structure/structural_element_engine.py",
    "core/structure/architecture_structure_handoff_v1.py",
)
FROZEN_STRUCTURAL_HASHES = {
    "core/structure/structural_grid_engine.py": "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py": "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
    "core/structure/architecture_structure_handoff_v1.py": "3f146069d91b51a2c681edd889e985bf22cb1ddc6df28177ae277c48812587a3",
}

RECT_10x12 = [[0, 0], [10, 0], [10, 12], [0, 12], [0, 0]]
L_SHAPE = [[0, 0], [10, 0], [10, 6], [4, 6], [4, 12], [0, 12], [0, 0]]


# ==========================================================
# CONTROLLED DESIGN-05 FIXTURE (mirrors the frozen Design-05 acceptance)
# ==========================================================

def _resolved(polygons):
    faces, solids, hosts, spaces, nodes, edges = {}, {}, {}, {}, [], []
    for floor, polygon in polygons.items():
        space_id, face_id = f"SPACE-{floor}", f"FACE-{floor}"
        faces[floor] = {"floor": floor, "faces": [
            {"face_id": face_id, "start": polygon[0], "end": polygon[1]}]}
        solids[floor] = {"floor": floor, "solids": [], "floor_envelopes": [
            {"envelope_id": f"ENV-{floor}", "polygon": polygon}]}
        hosts[floor] = {"floor": floor, "unresolved": [], "openings": [{
            "opening_id": f"D-{floor}", "kind": "DOOR", "status": "RESOLVED",
            "host_face_a": face_id, "side_a": space_id, "side_b": f"EXTERIOR:{floor}",
        }]}
        spaces[floor] = {"floor": floor, "unresolved": [], "spaces": [{
            "space_id": space_id, "semantic_class": "LIVING_RECEPTION", "external": False,
            "boundary_ids": [face_id], "polygon": polygon,
        }]}
        nodes.extend([
            {"id": space_id, "semantic_class": "LIVING_RECEPTION"},
            {"id": f"EXTERIOR:{floor}", "semantic_class": "EXTERIOR"},
        ])
        edges.append({"id": f"D-{floor}", "from": space_id, "to": f"EXTERIOR:{floor}",
                      "kind": "DOOR_ACCESS"})
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_STRUCTURAL_SYNTHESIS_01",
        "boundary_extraction": {
            "source_file": "controlled-synthesis-01.dxf", "source_sha256": "5" * 64,
            "tolerance_audit": {"chosen_snap_tolerance_m": 0.001},
            "wall_face_graphs": faces, "wall_solid_graphs": solids,
            "opening_host_graphs": hosts, "space_boundary_graphs": spaces,
            "access_graph": {"nodes": nodes, "edges": edges, "status": "RESOLVED"},
            "unresolved": [],
        },
        "semantic_regions": [], "constraints": [],
        "protected_constraints": [{"constraint_id": "PC-D-R1", "entity_id": "D-R1"}],
        "protected_entities": ["D-R1", "FACE-R1"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }


def _design_04(polygons, *, void=None, roof_type=None, slope=None, external=False):
    floors = list(polygons.keys())
    accepted = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved(polygons), candidate_id="ARCH-BASELINE-SYN01", candidate_version="10",
        acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["syn-01"]},
    )
    design_02 = derive_architectural_candidate_v1(
        accepted, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["d02"]})
    design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
        design_02, enrichment_provenance={"decision": "DESIGN_03", "evidence_ids": ["d03"]})

    evidence = {
        "contract": "ApprovedArchitecturalGeometryEvidenceV1", "status": "VERIFIED",
        "levels": [{"floor_id": floor, "order": index, "elevation": index * 3.2}
                   for index, floor in enumerate(floors)],
        "vertical_circulation": [] if void is None else [void],
    }
    roof = {"status": "VERIFIED", "source_floor_id": floors[-1],
            "use_source_floor_envelope": True}
    if roof_type is not None:
        roof["roof_type"] = roof_type
    if slope is not None:
        roof["slope"] = slope
    if external:
        roof["terraces"] = [{"terrace_id": "T-1", "external": True,
                             "polygon": [[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]]}]
    evidence["roof"] = roof

    return derive_architectural_floor_roof_geometry_v1(
        design_03, geometry_evidence=evidence,
        derivation_provenance={"decision": "DESIGN_04", "evidence_ids": ["d04"]})


def _design_05(polygons=None, *, void=None, roof_type=None, slope=None,
               external=False, readiness_evidence=None):
    parent = _design_04(polygons or {"R1": RECT_10x12}, void=void, roof_type=roof_type,
                        slope=slope, external=external)
    return analyze_architectural_structural_readiness_v1(
        parent, readiness_evidence=readiness_evidence,
        analysis_provenance={"decision": "DESIGN_05", "evidence_ids": ["d05"]})


def _analyze(candidate):
    return analyze_structural_support_candidates_v1(candidate)


def _verified(**collections):
    return {"contract": "ApprovedArchitecturalStructuralReadinessEvidenceV1",
            "status": "VERIFIED", **collections}


def _points(records):
    return [item["point"] for item in records]


def _inside(polygon, point):
    """Strict interior test (boundary points are NOT inside), matching the
    production semantics used to reject support opportunities."""
    from shapely.geometry import Point, Polygon

    return Polygon(polygon).contains(Point(point[0], point[1]))


# ==========================================================
# A. simple rectangular floor → candidate analysis, extents unchanged
# ==========================================================

def test_a_rectangular_floor_produces_candidate_analysis_without_resize():
    candidate = _design_05()
    assert candidate["contract"] == "Design05StructuralReadinessCandidateV1"

    analysis = _analyze(candidate)
    assert isinstance(analysis, StructuralSupportCandidateAnalysisV1)
    assert analysis["contract"] == "StructuralSupportCandidateAnalysisV1"
    assert analysis["version"] == "1.0"
    assert analysis["status"] in (STATUS_ANALYSIS_READY, STATUS_ANALYSIS_READY_WITH_GAPS)
    assert analysis["floors"]
    assert analysis["candidate_support_regions"], "candidate opportunities required"

    floor = analysis["floors"][0]
    assert floor["envelope_polygon"] == candidate["structural_architecture_input"][
        "floor_envelopes"][0]["polygon"]
    assert floor["envelope_area_m2"] == pytest.approx(120.0)
    assert analysis["provenance"]["structural_synthesis_performed"] is False


# ==========================================================
# B / 17. 10×12 must NOT become 8×12 (the legacy fixed-grid regression)
# ==========================================================

def test_b_ten_by_twelve_envelope_is_never_grid_rounded():
    candidate = _design_05({"R1": RECT_10x12})
    analysis = _analyze(candidate)

    envelope = analysis["floors"][0]["envelope_polygon"]
    assert envelope == [[0.0, 0.0], [10.0, 0.0], [10.0, 12.0], [0.0, 12.0], [0.0, 0.0]]

    xs = [point[0] for point in envelope]
    ys = [point[1] for point in envelope]
    width, depth = max(xs) - min(xs), max(ys) - min(ys)
    assert width == pytest.approx(10.0)
    assert depth == pytest.approx(12.0)

    # explicitly forbidden legacy outcomes
    assert (width, depth) != (8.0, 12.0)
    assert (width, depth) != (12.0, 8.0)
    assert (width, depth) != (8.0, 8.0)

    # the analysis must not shrink / expand the architectural envelope
    axes = analysis["floors"][0]["candidate_axis_opportunities"]
    assert min(axes["x"]) == pytest.approx(0.0) and max(axes["x"]) == pytest.approx(10.0)
    assert min(axes["y"]) == pytest.approx(0.0) and max(axes["y"]) == pytest.approx(12.0)
    assert analysis["grid_policy"]["envelope_rounded_to_grid"] is False
    assert analysis["grid_policy"]["outer_supports_deleted_to_fit_spacing"] is False


# ==========================================================
# C. unequal-bay friendly architecture → no forced equal spacing
# ==========================================================

def test_c_no_forced_equal_bay_or_four_meter_spacing():
    analysis = _analyze(_design_05({"R1": L_SHAPE}))
    floor = analysis["floors"][0]

    axes = floor["candidate_axis_opportunities"]
    assert axes["x"] == [0.0, 4.0, 10.0]
    assert axes["y"] == [0.0, 6.0, 12.0]

    spans = floor["span_observations"]["x"]["observed_spans"]
    assert spans == [4.0, 6.0]
    assert floor["span_observations"]["x"]["unequal_spans"] is True
    assert floor["span_observations"]["x"]["equal_bay_forced"] is False

    policy = analysis["grid_policy"]
    assert policy["fixed_four_meter_authority"] is False
    assert policy["equal_bay_by_default"] is False
    assert policy["arbitrary_division"] is False
    assert policy["design_driven"] is True


# ==========================================================
# D. protected stair/elevator void → candidate excluded
# ==========================================================

@pytest.mark.parametrize("void_type", ["stair", "elevator"])
def test_d_vertical_void_is_excluded_from_support_candidates(void_type):
    void = {"id": f"{void_type.upper()}-1", "type": void_type, "status": "VERIFIED",
            "floor_ids": ["R1"], "polygon": [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]}
    candidate = _design_05(void=void)
    analysis = _analyze(candidate)

    floor = analysis["floors"][0]
    assert void["id"] in floor["excluded_region_refs"]
    assert floor["eligible_area_m2"] == pytest.approx(116.0)
    assert floor["eligible_area_m2"] < floor["envelope_area_m2"]

    # no candidate support opportunity may sit inside the protected void
    for point in _points(analysis["candidate_support_regions"]):
        assert not _inside(void["polygon"], point), point
    assert analysis["grid_policy"]["design_driven"] is True


# ==========================================================
# E. ramp / vehicle void → candidate excluded
# ==========================================================

def test_e_ramp_vehicle_void_excludes_support_candidates():
    void = {"id": "RAMP-1", "type": "ramp", "status": "VERIFIED", "floor_ids": ["R1"],
            "polygon": [[4, 4], [7, 4], [7, 8], [4, 8], [4, 4]]}
    analysis = _analyze(_design_05(void=void))

    floor = analysis["floors"][0]
    assert "RAMP-1" in floor["excluded_region_refs"]
    assert floor["eligible_area_m2"] == pytest.approx(120.0 - 12.0)
    for point in _points(analysis["candidate_support_regions"]):
        assert not _inside(void["polygon"], point), point


# ==========================================================
# F. opening / access protected region → candidate not placed through it
# ==========================================================

def test_f_opening_clearance_region_is_not_traversed_by_candidates():
    evidence = _verified(opening_clearances=[{
        "constraint_id": "D-R1-CLEAR", "opening_id": "D-R1", "floor_id": "R1",
        "status": "VERIFIED", "polygon": [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],
    }])
    analysis = _analyze(_design_05(readiness_evidence=evidence))

    floor = analysis["floors"][0]
    assert floor["eligible_area_m2"] == pytest.approx(116.0)
    rejected = _points(analysis["rejected_support_regions"])
    assert [0.0, 0.0] in rejected, rejected
    assert analysis["rejected_support_regions"][0]["committed"] is False
    for point in _points(analysis["candidate_support_regions"]):
        assert not _inside([[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]], point), point


# ==========================================================
# G. irregular floor envelope → never replaced by a rectangle
# ==========================================================

def test_g_irregular_envelope_is_preserved_not_rectangularised():
    analysis = _analyze(_design_05({"R1": L_SHAPE}))
    floor = analysis["floors"][0]

    assert floor["envelope_polygon"] == [
        [0.0, 0.0], [10.0, 0.0], [10.0, 6.0], [4.0, 6.0], [4.0, 12.0], [0.0, 12.0], [0.0, 0.0],
    ]
    assert floor["envelope_area_m2"] == pytest.approx(84.0)
    # the L-shape must not become its 10×12 bounding rectangle
    assert floor["envelope_area_m2"] != pytest.approx(120.0)
    assert len(floor["envelope_polygon"]) == 7


# ==========================================================
# H. external terrace → semantics preserved
# ==========================================================

def test_h_external_terrace_semantics_are_preserved():
    analysis = _analyze(_design_05(external=True))
    terraces = [
        item for item in analysis["external_space_constraints"]
        if item.get("constraint_type") == "EXTERNAL_SPACE_NO_ENCLOSURE_ZONE"
    ]
    assert terraces, analysis["external_space_constraints"]
    assert terraces[0]["structural_policy"] == "NO_STRUCTURE_DRIVEN_ENCLOSURE"
    for point in _points(analysis["candidate_support_regions"]):
        assert not _inside([[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]], point), point


# ==========================================================
# I. missing structural design criteria → STRUCTURAL_DESIGN_INPUT_GAP
# ==========================================================

def test_i_missing_structural_criteria_are_gaps_never_guessed():
    analysis = _analyze(_design_05())
    gaps = [
        item for item in analysis["unresolved_structural_inputs"]
        if item.get("classification") == "STRUCTURAL_DESIGN_INPUT_GAP"
    ]
    assert gaps, analysis["unresolved_structural_inputs"]
    assert {item.get("input") for item in gaps} >= {
        "STRUCTURAL_SYSTEM_SELECTION", "MATERIAL_AND_MEMBER_SIZING",
        "SPAN_AND_SUPPORT_STRATEGY", "LOAD_AND_USE_CRITERIA",
    }
    assert all(item.get("provided_by_architecture") is False for item in gaps)

    # no guessed member sizes / system / loads
    strategy = analysis["strategy_candidates"][0]
    assert strategy["grid_spacing"] is None
    assert strategy["committed"] is False
    assert analysis["provenance"]["member_sizing_performed"] is False
    assert analysis["provenance"]["structural_system_selected"] is False
    assert analysis["provenance"]["loads_defined"] is False


# ==========================================================
# J. multi-floor → floors analysed independently, no geometry reuse
# ==========================================================

def test_j_multi_floor_analysis_is_independent_and_never_reuses_geometry():
    polygons = {"R1": RECT_10x12, "R2": [[0, 0], [8, 0], [8, 10], [0, 10], [0, 0]]}
    analysis = _analyze(_design_05(polygons))

    assert [floor["floor_id"] for floor in analysis["floors"]] == ["R1", "R2"]
    areas = [floor["envelope_area_m2"] for floor in analysis["floors"]]
    assert areas == [pytest.approx(120.0), pytest.approx(80.0)]
    assert analysis["floors"][0]["envelope_polygon"] != analysis["floors"][1]["envelope_polygon"]

    continuity = analysis["cross_floor_continuity"][0]
    assert continuity["floor_geometry_reused"] is False
    assert continuity["support_stack_forced"] is False
    assert continuity["architecture_moved"] is False
    # misalignment is RECORDED, not silently corrected
    assert continuity["condition"] in (
        "SUPPORT_POSITIONS_NOT_VERTICALLY_ALIGNED", "ALIGNED")


# ==========================================================
# K / L. determinism + constraint sensitivity
# ==========================================================

def test_k_same_input_yields_identical_analysis_and_hash():
    first = _analyze(_design_05())
    second = _analyze(_design_05())
    assert first["analysis_hash"] == second["analysis_hash"]
    assert len(first["analysis_hash"]) == 64
    assert all(character in "0123456789abcdef" for character in first["analysis_hash"])
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first


def test_l_changed_architectural_constraint_changes_the_hash():
    baseline = _analyze(_design_05())
    void = {"id": "STAIR-1", "type": "stair", "status": "VERIFIED", "floor_ids": ["R1"],
            "polygon": [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]}
    changed = _analyze(_design_05(void=void))
    assert baseline["analysis_hash"] != changed["analysis_hash"]
    assert baseline["candidate_support_regions"] != changed["candidate_support_regions"]


# ==========================================================
# M / N. no architecture / Design-05 mutation
# ==========================================================

def test_m_no_architecture_or_design_05_mutation():
    candidate = _design_05()
    snapshot = deepcopy(candidate)
    adapter_snapshot_source = deepcopy(candidate["structural_architecture_input"])

    adapted = StructuralArchitectureInputAdapterV1().adapt(candidate)
    analysis = _analyze(candidate)

    assert candidate == snapshot, "Design-05 candidate must not be mutated"
    assert candidate["structural_architecture_input"] == adapter_snapshot_source
    assert adapted["adapter_guard"]["source_mutated"] is False
    assert analysis["provenance"]["design_05_mutated"] is False
    assert analysis["provenance"]["architecture_mutated"] is False
    assert adapted["adapter_guard"]["architecture_resized"] is False


def test_n_adapter_is_read_only_and_carries_full_evidence():
    candidate = _design_05()
    adapted = StructuralArchitectureInputAdapterV1().adapt(candidate)

    assert adapted["contract"] == "StructuralArchitectureInputAdapterV1"
    assert adapted["status"] in ("READY", "READY_WITH_GAPS")
    assert adapted["source"]["candidate_hash"] == candidate["candidate_hash"]
    assert adapted["floors"][0]["envelope_polygon"] == RECT_10x12
    # richer Design-05 evidence is carried forward (no width/depth-only fallback)
    assert adapted["eligible_support_regions"]
    assert adapted["unresolved_architectural_gaps"] is not None
    assert adapted["engine_input_projection"]["structural_architecture_input"]["contract"] == \
        "StructuralArchitectureInputV1"
    guard = adapted["adapter_guard"]
    for flag in ("grid_spacing_chosen", "equal_bay_chosen", "column_count_chosen",
                 "support_points_invented", "architecture_resized",
                 "envelope_rounded_to_grid", "missing_evidence_defaulted",
                 "four_meter_assumption_applied", "legacy_width_depth_only_inference"):
        assert guard[flag] is False, flag


# ==========================================================
# O. no final columns / beams generated
# ==========================================================

def test_o_no_final_columns_or_beams_are_generated():
    analysis = _analyze(_design_05())
    assert analysis["committed_structural_elements"] == []
    assert analysis["generated_columns"] == []
    assert analysis["generated_beams"] == []
    for floor in analysis["floors"]:
        assert floor["committed_columns"] == []
        assert floor["committed_beams"] == []
    for record in analysis["candidate_support_regions"]:
        assert record["committed"] is False
        assert record["is_column"] is False
        assert record["structural_candidate_only"] is True


# ==========================================================
# P. no BIM / IFC execution and no forbidden dependency
# ==========================================================

def test_p_no_bim_ifc_render_or_engine_execution():
    analysis = _analyze(_design_05())
    provenance = analysis["provenance"]
    assert provenance["bim_ifc_executed"] is False
    assert provenance["structural_grid_engine_executed"] is False
    assert provenance["structural_element_engine_executed"] is False
    assert provenance["final_members_committed"] is False


def test_p2_new_modules_have_no_forbidden_dependency():
    forbidden = (
        "import requests", "from requests", "import comfy", "from comfy",
        "import subprocess", "from subprocess", "ifcopenshell", "ezdxf",
        "structural_grid_engine import", "structural_element_engine import",
        "render_runtime", "comfyui",
    )
    for relative in (
        "core/structure/structural_architecture_input_adapter_v1.py",
        "core/structure/structural_support_candidate_analysis_v1.py",
    ):
        lines = [
            line.strip() for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        joined = "\n".join(lines)
        for token in forbidden:
            assert token not in joined, f"{relative}: {token}"


# ==========================================================
# Q. existing engines remain untouched
# ==========================================================

@pytest.mark.parametrize("relative", FROZEN_STRUCTURAL_FILES)
def test_q_existing_structural_engines_are_byte_identical(relative):
    digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    assert digest == FROZEN_STRUCTURAL_HASHES[relative], relative


# ==========================================================
# STATUS MODEL
# ==========================================================

def test_status_stale_parent_is_rejected():
    analysis = _analyze({"contract": "Design05StructuralReadinessCandidateV1"})
    assert analysis["status"] == STATUS_STALE_PARENT
    assert analysis["committed_structural_elements"] == []
    with pytest.raises(StructuralArchitectureInputAdapterError) as caught:
        StructuralArchitectureInputAdapterV1().adapt(
            {"contract": "Design05StructuralReadinessCandidateV1"})
    assert caught.value.status == STATUS_STALE_PARENT


def test_status_protected_zone_conflict_when_zone_leaves_envelope():
    zone = {"zone_id": "P-OUT", "floor_id": "R1", "status": "VERIFIED",
            "polygon": [[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]}
    analysis = _analyze(_design_05(readiness_evidence=_verified(protected_zones=[zone])))
    assert analysis["status"] == STATUS_PROTECTED_ZONE_CONFLICT
    assert analysis["committed_structural_elements"] == []


def test_status_legacy_grid_assumption_is_blocked():
    candidate = _design_05()
    candidate["structural_architecture_input"]["grid_spacing"] = 4.0
    candidate["candidate_hash"] = __import__(
        "core.architecture.contracts.architectural_structural_readiness_v1",
        fromlist=["design_05_semantic_hash"],
    ).design_05_semantic_hash(candidate)
    analysis = _analyze(candidate)
    assert analysis["status"] == STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED
    assert analysis["generated_columns"] == []


def test_status_no_valid_support_region_when_fully_excluded():
    # the exclusion equals the envelope: no conflict, but zero eligible area
    zone = {"zone_id": "P-ALL", "floor_id": "R1", "status": "VERIFIED",
            "polygon": [[0, 0], [10, 0], [10, 12], [0, 12], [0, 0]]}
    analysis = _analyze(_design_05(readiness_evidence=_verified(protected_zones=[zone])))
    assert analysis["status"] == STATUS_NO_VALID_SUPPORT_REGION
    assert analysis["candidate_support_regions"] == []
    assert analysis["committed_structural_elements"] == []


def test_status_protected_zone_conflict_emits_no_candidates():
    zone = {"zone_id": "P-OUT", "floor_id": "R1", "status": "VERIFIED",
            "polygon": [[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]}
    analysis = _analyze(_design_05(readiness_evidence=_verified(protected_zones=[zone])))
    assert analysis["status"] == STATUS_PROTECTED_ZONE_CONFLICT
    assert analysis["floors"] == []
    assert analysis["candidate_support_regions"] == []
    assert analysis["committed_structural_elements"] == []


def test_status_analysis_ready_when_roof_evidence_is_complete():
    analysis = _analyze(_design_05(roof_type="FLAT", slope=0.0))
    assert analysis["status"] == STATUS_ANALYSIS_READY
    assert analysis["unresolved_structural_inputs"], "design input gaps always recorded"


def test_analysis_never_claims_engineering_validity():
    analysis = _analyze(_design_05())
    assert analysis["authority"] == "STRUCTURAL_CANDIDATE_ANALYSIS_ARCHITECTURE_SUBORDINATE"
    text = json.dumps(analysis, ensure_ascii=False).lower()
    assert "structurally_valid" not in text
    assert "engineering_validation" not in text
