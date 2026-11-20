from pathlib import Path

from core.reference_analysis.dxf_canonical_plan_architectural_evidence_resolver_v1 import DXFCanonicalPlanArchitecturalEvidenceResolverV1
from core.reference_analysis.dxf_canonical_wall_face_opening_jamb_pair_resolver_v1 import DXFCanonicalWallFaceOpeningJambPairResolverV1
from core.reference_analysis.dxf_canonical_wall_topology_opening_resolver_v1 import DXFCanonicalWallTopologyOpeningResolverV1
from core.reference_analysis.dxf_physical_wall_assembly_continuity_resolver_v1 import DXFPhysicalWallAssemblyContinuityResolverV1
from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1


def _wall(identifier, centerline, status="resolved_candidate", openings=None):
    return {"id": identifier, "faces": [identifier + "-A", identifier + "-B"],
            "centerline": centerline, "thickness": 0.2, "openings": openings or [],
            "source_handles": [identifier + "-H"], "status": status}


def _pair(identifier, status="resolved_face_pair"):
    return {"id": identifier, "status": status}


def _contract(walls, pairs, voids=None, doors=None):
    return {"version": "1.0", "canonical_view_id": "VIEW-001",
            "physical_wall_candidates": walls, "wall_face_pair_candidates": pairs,
            "opening_void_candidates": voids or [], "door_associations": doors or [],
            "window_associations": [], "provenance": {"source_handles": []}}


def test_l_junction_propagates_to_single_assembly():
    contract = _contract(
        [_wall("W1", [[0, 0], [5, 0]]), _wall("W2", [[5, 0], [5, 5]])],
        [_pair("W1"), _pair("W2")],
    )
    result = DXFPhysicalWallAssemblyContinuityResolverV1().resolve(contract)
    assert len(result["physical_wall_assembly_candidates"]) == 1
    assert result["junctions"][0]["type"] == "L"
    assert result["junctions"][0]["propagation_allowed"] is True


def test_parallel_walls_without_junction_stay_separate():
    contract = _contract(
        [_wall("W1", [[0, 0], [5, 0]]), _wall("W2", [[0, 1], [5, 1]])],
        [_pair("W1"), _pair("W2")],
    )
    result = DXFPhysicalWallAssemblyContinuityResolverV1().resolve(contract)
    assert len(result["physical_wall_assembly_candidates"]) == 2
    assert result["junctions"] == []


def test_opening_is_preserved_on_wall_assembly():
    void = {"id": "V1", "wall_candidate_id": "W1", "width": 1.0,
            "orientation": [1, 0], "status": "resolved_void_candidate", "evidence": ["paired interruption"]}
    door = {"door_id": "D1", "source_handle": "D-H", "opening_void_id": "V1",
            "status": "resolved", "evidence": ["world geometry validation"]}
    contract = _contract([_wall("W1", [[0, 0], [5, 0]], openings=["V1"])], [_pair("W1")], [void], [door])
    result = DXFPhysicalWallAssemblyContinuityResolverV1().resolve(contract)
    assert result["opening_on_wall_candidates"][0]["status"] == "resolved_candidate"
    assert result["door_validation"][0]["status"] == "validated"


def test_ambiguous_parallel_face_candidate_remains_pending():
    contract = _contract(
        [_wall("W1", [[0, 0], [5, 0]], status="pending_ambiguity")],
        [_pair("W1", status="pending_multiple_face_pairs")],
    )
    result = DXFPhysicalWallAssemblyContinuityResolverV1().resolve(contract)
    assert result["physical_wall_assembly_candidates"][0]["status"] == "pending_ambiguity"
    assert "ambiguous_wall_assemblies" in result["unresolved_items"]


def test_real_benchmark_does_not_guess_entrance(tmp_path):
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    correspondence = DXFViewCorrespondenceResolverV1().resolve(path, scope)
    evidence = DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(path, scope, correspondence)
    topology = DXFCanonicalWallTopologyOpeningResolverV1().resolve(path, scope, evidence, correspondence)
    faces = DXFCanonicalWallFaceOpeningJambPairResolverV1().resolve(topology)
    output = tmp_path / "dxf_physical_wall_assembly_continuity_contract.json"
    result = DXFPhysicalWallAssemblyContinuityResolverV1().resolve(faces, output)
    assert result["canonical_view_id"] == "VIEW-001"
    assert result["entrance_evidence_status"] == "UNRESOLVED"
    assert result["production_pipeline_consumable"] is False
    assert len(result["door_validation"]) == 7
    assert len(result["window_validation"]) == 4
    assert output.exists()
