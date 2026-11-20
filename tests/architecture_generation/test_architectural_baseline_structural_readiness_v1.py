"""ARCHITECTURAL-BASELINE-DESIGN-05 acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from core.architecture.contracts.architectural_structural_readiness_v1 import (
    canonical_design_05_document,
    design_05_semantic_hash,
    verify_design_05_candidate,
)
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
from core.architecture.reasoning import architectural_baseline_structural_readiness_v1 as design_05_module
from core.architecture.reasoning.architectural_baseline_structural_readiness_v1 import (
    Design05ReadinessAnalysisError,
    analyze_architectural_structural_readiness_v1,
)


ROOT = Path(__file__).resolve().parents[2]
FROZEN_HASHES = {
    "core/architecture/contracts/architectural_floor_roof_geometry_v1.py": "04edb851a56bd12bd859b48b8aacc84ec4141d8baa3c066260965020ea467329",
    "core/architecture/reasoning/architectural_baseline_floor_roof_geometry_v1.py": "c1316dbff842103a2453eb51ff76c48dcdea0cd9b6fc20b907ae1b3c28e16eb6",
    "core/structure/structural_grid_engine.py": "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py": "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
    "core/structure/architecture_structure_handoff_v1.py": "3f146069d91b51a2c681edd889e985bf22cb1ddc6df28177ae277c48812587a3",
}


def _resolved(*, floors=("R1",), external=False):
    faces, solids, hosts, spaces, nodes, edges = {}, {}, {}, {}, [], []
    for index, floor in enumerate(floors):
        x = 0
        polygon = [[x, 0], [x + 4, 0], [x + 4, 4], [x, 4], [x, 0]]
        space_id, face_id = f"SPACE-{floor}", f"FACE-{floor}"
        faces[floor] = {"floor": floor, "faces": [{"face_id": face_id, "start": [x, 0], "end": [x + 4, 0]}]}
        solids[floor] = {"floor": floor, "solids": [], "floor_envelopes": [{"envelope_id": f"ENV-{floor}", "polygon": polygon}]}
        opening = {
            "opening_id": f"D-{floor}", "kind": "DOOR", "status": "RESOLVED",
            "host_face_a": face_id, "side_a": space_id, "side_b": f"EXTERIOR:{floor}",
        }
        hosts[floor] = {"floor": floor, "openings": [opening], "unresolved": []}
        spaces[floor] = {"floor": floor, "spaces": [{
            "space_id": space_id,
            "semantic_class": "EXTERNAL_TERRACE" if external else "LIVING_RECEPTION",
            "external": external, "boundary_ids": [face_id], "polygon": polygon,
        }], "unresolved": []}
        nodes.extend([
            {"id": space_id, "semantic_class": "EXTERNAL" if external else "LIVING_RECEPTION"},
            {"id": f"EXTERIOR:{floor}", "semantic_class": "EXTERIOR"},
        ])
        edges.append({"id": f"D-{floor}", "from": space_id, "to": f"EXTERIOR:{floor}", "kind": "DOOR_ACCESS"})
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_DESIGN_05_BASELINE",
        "boundary_extraction": {
            "source_file": "controlled-design-05.dxf", "source_sha256": "5" * 64,
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


def _design_04(*, floors=("R1",), void=None, roof=True, external=False, elevations=False):
    accepted = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved(floors=floors, external=external), candidate_id="ARCH-BASELINE-005",
        candidate_version="10", acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["acceptance-05"]},
    )
    design_02 = derive_architectural_candidate_v1(
        accepted, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["d02"]},
    )
    design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
        design_02, enrichment_provenance={"decision": "DESIGN_03", "evidence_ids": ["d03"]},
    )
    evidence = {
        "contract": "ApprovedArchitecturalGeometryEvidenceV1", "status": "VERIFIED",
        "levels": [{"floor_id": floor, "order": index, **({"elevation": index * 3.2} if elevations else {})} for index, floor in enumerate(floors)],
        "vertical_circulation": [] if void is None else [void],
    }
    if roof:
        evidence["roof"] = {"status": "VERIFIED", "source_floor_id": floors[-1], "use_source_floor_envelope": True}
        if external:
            evidence["roof"]["terraces"] = [{
                "terrace_id": "T-1", "external": True,
                "polygon": [[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]],
            }]
    design_04 = derive_architectural_floor_roof_geometry_v1(
        design_03, geometry_evidence=evidence,
        derivation_provenance={"decision": "DESIGN_04", "evidence_ids": ["d04"]},
    )
    return accepted, design_02, design_03, design_04


def _analyze(parent=None, evidence=None):
    if parent is None:
        parent = _design_04()[3]
    return analyze_architectural_structural_readiness_v1(
        parent, readiness_evidence=evidence,
        analysis_provenance={"decision": "DESIGN_05", "evidence_ids": ["d05"]},
    )


def _verified(**collections):
    return {"contract": "ApprovedArchitecturalStructuralReadinessEvidenceV1", "status": "VERIFIED", **collections}


def test_a_valid_floor_creates_readiness_without_structural_elements():
    result = _analyze()
    assert result["contract"] == "Design05StructuralReadinessCandidateV1"
    assert result["eligible_support_regions"]
    assert result["generated_structural_elements"] == []
    assert result["provenance"]["structural_synthesis_performed"] is False


def test_b_known_stair_void_is_protected_and_excluded():
    void = {"id": "STAIR-1", "type": "stair", "status": "VERIFIED", "floor_ids": ["R1"], "polygon": [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]}
    result = _analyze(_design_04(void=void)[3])
    assert result["vertical_void_constraints"][0]["void_id"] == "STAIR-1"
    assert result["eligible_support_regions"][0]["area_m2"] == pytest.approx(15.0)


def test_c_missing_vertical_void_polygon_is_semantic_and_blocking_not_guessed():
    void = {"id": "ELEVATOR-1", "type": "elevator", "status": "VERIFIED", "floor_ids": ["R1"]}
    result = _analyze(_design_04(void=void)[3])
    assert result["readiness_status"] == "BLOCKED_VERTICAL_VOID_EVIDENCE"
    gap = next(item for item in result["unresolved_architectural_evidence"] if item["code"] == "VERTICAL_VOID_GEOMETRY_PENDING")
    assert gap["blocks_full_structural_synthesis"] is True
    assert result["eligible_support_regions"][0]["area_m2"] == pytest.approx(16.0)


def test_d_explicit_opening_conflict_region_restricts_eligibility_without_door_swing_inference():
    evidence = _verified(opening_clearances=[{
        "constraint_id": "D-R1-CLEAR", "opening_id": "D-R1", "floor_id": "R1",
        "status": "VERIFIED", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
    }])
    result = _analyze(evidence=evidence)
    assert result["eligible_support_regions"][0]["area_m2"] == pytest.approx(15.0)
    semantic = next(item for item in result["opening_clearance_constraints"] if item["constraint_id"] == "OPENING:D-R1")
    assert semantic["door_swing_inferred"] is False and semantic["polygon"] is None


def test_e_external_roof_terrace_is_no_enclosure_constraint():
    result = _analyze(_design_04(external=True)[3])
    terrace = next(item for item in result["external_space_constraints"] if item.get("roof_geometry_ref"))
    assert terrace["constraint_type"] == "EXTERNAL_SPACE_NO_ENCLOSURE_ZONE"
    assert terrace["structural_policy"] == "NO_STRUCTURE_DRIVEN_ENCLOSURE"


def test_f_unknown_floor_elevation_is_preserved_without_three_meter_default():
    result = _analyze()
    floor = next(item for item in result["floor_roof_constraints"] if item["record_type"] == "FLOOR_ARCHITECTURAL_INPUT")
    assert floor["elevation"] is None
    assert any(item["code"] == "FLOOR_ELEVATION_UNRESOLVED" and item["default_applied"] is False for item in result["unresolved_architectural_evidence"])
    assert result["provenance"]["floor_elevation_defaulted"] is False


def test_g_unknown_roof_type_and_slope_are_gaps_without_assumption():
    result = _analyze()
    roof = next(item for item in result["floor_roof_constraints"] if item["record_type"] == "ROOF_ARCHITECTURAL_INPUT")
    assert roof["roof_type"] == "UNKNOWN" and roof["slope"] is None
    assert {item["code"] for item in result["unresolved_architectural_evidence"]} >= {"ROOF_TYPE_UNRESOLVED", "ROOF_SLOPE_UNRESOLVED"}


def test_h_architecture_extents_are_authoritative_and_grid_resize_is_forbidden():
    result = _analyze()
    guard = result["legacy_structural_grid_guard"]
    assert guard["architecture_resize_to_grid_allowed"] is False
    assert guard["four_meter_grid_authoritative"] is False
    assert result["structural_architecture_input"]["floor_envelopes"][0]["polygon"] == _design_04()[3]["floor_geometries"][0]["polygon"]


def test_i_eligibility_is_architecture_minus_only_proven_exclusions():
    evidence = _verified(protected_zones=[{
        "zone_id": "P-1", "floor_id": "R1", "status": "VERIFIED",
        "polygon": [[1, 1], [3, 1], [3, 2], [1, 2], [1, 1]],
    }])
    result = _analyze(evidence=evidence)
    region = result["eligible_support_regions"][0]
    assert region["area_m2"] == pytest.approx(14.0)
    assert region["eligibility_status"] == "DETERMINED_FROM_ARCHITECTURE_MINUS_PROVEN_EXCLUSIONS"
    assert len(region["polygons"][0]["holes"]) == 1


def test_j_no_column_beam_grid_support_points_or_structural_decisions_are_generated():
    result = _analyze()
    assert result["generated_structural_elements"] == []
    assert result["structural_architecture_input"]["grid_spacing"] is None
    assert result["structural_architecture_input"]["column_count"] is None
    assert result["structural_architecture_input"]["beam_layout"] is None
    assert all(item["placement_points_generated"] is False for item in result["eligible_support_regions"])
    assert all(item["beam_lines_generated"] is False for item in result["eligible_support_regions"])


def test_k_protected_zone_conflict_is_not_ready():
    evidence = _verified(protected_zones=[{
        "zone_id": "P-OUT", "floor_id": "R1", "status": "VERIFIED",
        "polygon": [[3, 1], [5, 1], [5, 2], [3, 2], [3, 1]],
    }])
    result = _analyze(evidence=evidence)
    assert result["readiness_status"] == "BLOCKED_PROTECTED_ZONE"
    check = next(item for item in result["readiness_checks"] if item["check"] == "PROTECTED_ZONE_COMPATIBILITY")
    assert check["status"] == "FAIL"


def test_l_same_input_has_deterministic_identity_hash_and_serialization():
    parent = _design_04()[3]
    first, second = _analyze(parent), _analyze(parent)
    assert first == second
    loaded = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))
    assert canonical_design_05_document(loaded) == canonical_design_05_document(first)
    assert design_05_semantic_hash(loaded) == first["candidate_hash"]
    assert verify_design_05_candidate(loaded)


def test_m_changed_protected_evidence_changes_identity_version_and_hash():
    first = _analyze(evidence=_verified(protected_zones=[]))
    changed = _verified(protected_zones=[{
        "zone_id": "P-2", "floor_id": "R1", "status": "VERIFIED",
        "polygon": [[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]],
    }])
    second = _analyze(evidence=changed)
    assert first["candidate_id"] != second["candidate_id"]
    assert first["candidate_version"] != second["candidate_version"]
    assert first["candidate_hash"] != second["candidate_hash"]


def test_n_design_04_parent_is_unchanged_and_lineage_is_preserved():
    accepted, _, _, parent = _design_04()
    before = deepcopy(parent)
    result = _analyze(parent)
    assert parent == before
    assert result["parent_candidate_hash"] == parent["candidate_hash"]
    assert result["parent_baseline_hash"] == accepted["candidate_hash"]
    assert result["lineage"]["design_04_parent_mutated"] is False


def test_o_explicit_multifloor_void_alignment_uses_links_only_and_no_support_stacks():
    void = {"id": "SHAFT-1", "type": "elevator", "status": "VERIFIED", "floor_ids": ["R1", "R2"], "polygon": [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]}
    result = _analyze(_design_04(floors=("R1", "R2"), void=void, elevations=True)[3])
    check = next(item for item in result["readiness_checks"] if item.get("void_id") == "SHAFT-1")
    assert check["floor_ids"] == ["R1", "R2"] and check["status"] == "PASS"
    assert check["support_stack_inferred"] is False


def test_p_no_forbidden_dependency_and_no_structural_execution_import():
    contract_module = __import__("core.architecture.contracts.architectural_structural_readiness_v1", fromlist=["x"])
    imports = []
    for module in (design_05_module, contract_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = ("chat", "llm", "memory", "voice", "render", ".structure", ".bim", "ifc", "cad")
    assert not any(token in document for token in forbidden)
    assert _analyze()["side_effects"] == {"structure": False, "bim": False, "ifc": False, "render": False, "chat_intelligence": False}


def test_q_frozen_parent_and_structural_engine_files_are_byte_unchanged():
    for relative, expected in FROZEN_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_r_unverified_or_malformed_evidence_is_transactional_failure():
    with pytest.raises(Design05ReadinessAnalysisError) as caught:
        _analyze(evidence={"status": "DRAFT", "protected_zones": []})
    assert caught.value.status == "FAILED"
    assert caught.value.to_dict()["candidate_committed"] is False


def test_s_stale_parent_is_rejected_before_analysis():
    parent = _design_04()[3]
    parent["candidate_version"] = "tampered"
    with pytest.raises(Design05ReadinessAnalysisError) as caught:
        _analyze(parent)
    assert caught.value.status == "STALE_PARENT"


def test_t_explicit_geometry_without_floor_or_canonical_opening_binding_is_blocked():
    evidence = _verified(opening_clearances=[{
        "constraint_id": "UNBOUND", "opening_id": "NOT-CANONICAL", "status": "VERIFIED",
        "polygon": [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
    }])
    result = _analyze(evidence=evidence)
    assert result["readiness_status"] == "BLOCKED_GEOMETRY_EVIDENCE"
    codes = {item["code"] for item in result["unresolved_architectural_evidence"]}
    assert "OPENING_CLEARANCE_ZONE_FLOOR_BINDING_UNRESOLVED" in codes
    assert "OPENING_REFERENCE_UNRESOLVED" in codes
