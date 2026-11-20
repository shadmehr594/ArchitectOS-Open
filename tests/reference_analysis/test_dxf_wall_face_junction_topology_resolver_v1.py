import json
from pathlib import Path

from core.reference_analysis.dxf_canonical_plan_architectural_evidence_resolver_v1 import DXFCanonicalPlanArchitecturalEvidenceResolverV1
from core.reference_analysis.dxf_canonical_wall_face_opening_jamb_pair_resolver_v1 import DXFCanonicalWallFaceOpeningJambPairResolverV1
from core.reference_analysis.dxf_canonical_wall_topology_opening_resolver_v1 import DXFCanonicalWallTopologyOpeningResolverV1
from core.reference_analysis.dxf_physical_wall_assembly_continuity_resolver_v1 import DXFPhysicalWallAssemblyContinuityResolverV1
from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1
from core.reference_analysis.dxf_wall_face_junction_topology_resolver_v1 import DXFWallFaceJunctionTopologyResolverV1


def _track(identifier, direction, normal, offset, span):
    return {"track_id": identifier, "direction": direction, "normal": normal,
            "offset": offset, "span": span, "intervals": [{"start": span[0], "end": span[1]}]}


def _assembly(identifier, centerline, faces, status="resolved_continuous_wall"):
    return {"id": identifier, "wall_candidate_ids": [identifier],
            "face_segments": [face["track_id"] for face in faces],
            "face_geometry": [{"wall_candidate_id": identifier,
                               "face_a": faces[0] if faces else None,
                               "face_b": faces[1] if len(faces) > 1 else None}],
            "centerline_candidate": [centerline], "source_handles": [identifier + "-H"],
            "status": status}


def _run(tmp_path, assemblies):
    path = tmp_path / "continuity.json"
    path.write_text(json.dumps({"version": "1.0", "canonical_view_id": "VIEW-001",
                                "physical_wall_assembly_candidates": assemblies,
                                "opening_on_wall_candidates": [], "door_validation": [],
                                "window_validation": []}), encoding="utf-8")
    return DXFWallFaceJunctionTopologyResolverV1().resolve(path)


def test_true_l_corner_merges_one_wall_assembly(tmp_path):
    horizontal = _assembly("A", [[0, 0], [5, 0]], [
        _track("HA", [1, 0], [0, 1], -0.1, [0, 5.1]),
        _track("HB", [1, 0], [0, 1], 0.1, [0, 4.9]),
    ])
    vertical = _assembly("B", [[5, 0], [5, 5]], [
        _track("VA", [0, 1], [-1, 0], -4.9, [0.1, 5]),
        _track("VB", [0, 1], [-1, 0], -5.1, [-0.1, 5]),
    ])
    result = _run(tmp_path, [horizontal, vertical])
    assert len(result["junctions"]) == 1
    assert result["junctions"][0]["type"] == "L"
    assert len(result["physical_wall_assembly_candidates"]) == 1
    assert result["physical_wall_assembly_candidates"][0]["merge_status"] == "merged_by_proven_face_junction"


def test_centerline_crossing_without_face_continuity_is_rejected(tmp_path):
    horizontal = _assembly("A", [[0, 0], [10, 0]], [
        _track("HA", [1, 0], [0, 1], -0.1, [0, 10]), _track("HB", [1, 0], [0, 1], 0.1, [0, 10])])
    vertical = _assembly("B", [[5, -5], [5, 5]], [
        _track("VA", [0, 1], [-1, 0], -4.9, [1, 5]), _track("VB", [0, 1], [-1, 0], -5.1, [1, 5])])
    result = _run(tmp_path, [horizontal, vertical])
    assert result["junctions"] == []
    assert result["rejected_false_intersections"][0]["reason"] == "centerline_intersection_without_required_face_continuity"


def test_true_t_junction_is_accepted(tmp_path):
    host = _assembly("A", [[0, 0], [10, 0]], [
        _track("HA", [1, 0], [0, 1], -0.1, [0, 10]), _track("HB", [1, 0], [0, 1], 0.1, [0, 10])])
    branch = _assembly("B", [[5, 0], [5, 5]], [
        _track("VA", [0, 1], [-1, 0], -4.9, [0.1, 5]), _track("VB", [0, 1], [-1, 0], -5.1, [0.1, 5])])
    result = _run(tmp_path, [host, branch])
    assert result["junctions"][0]["type"] == "T"
    assert result["junctions"][0]["junction_status"] == "resolved"


def test_four_way_crossing_with_missing_face_is_unresolved(tmp_path):
    horizontal = _assembly("A", [[0, 0], [10, 0]], [
        _track("HA", [1, 0], [0, 1], -0.1, [0, 10]), _track("HB", [1, 0], [0, 1], 0.1, [0, 10])])
    vertical = _assembly("B", [[5, -5], [5, 5]], [
        _track("VA", [0, 1], [-1, 0], -5.0, [-5, 5])])
    result = _run(tmp_path, [horizontal, vertical])
    assert result["junctions"] == []
    assert result["rejected_false_intersections"][0]["type"] == "X"


def test_real_benchmark_has_no_guessed_entrance(tmp_path):
    reference = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(reference, {"building_type": "villa", "storeys": 1})
    correspondence = DXFViewCorrespondenceResolverV1().resolve(reference, scope)
    evidence = DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(reference, scope, correspondence)
    topology = DXFCanonicalWallTopologyOpeningResolverV1().resolve(reference, scope, evidence, correspondence)
    faces = DXFCanonicalWallFaceOpeningJambPairResolverV1().resolve(topology)
    continuity_path = tmp_path / "continuity.json"
    DXFPhysicalWallAssemblyContinuityResolverV1().resolve(faces, continuity_path)
    result = DXFWallFaceJunctionTopologyResolverV1().resolve(continuity_path)
    assert result["canonical_view_id"] == "VIEW-001"
    assert result["entrance_evidence_status"] == "UNRESOLVED"
    assert result["production_pipeline_consumable"] is False
    assert len(result["door_validation"]) == 7
    assert len(result["window_validation"]) == 4
