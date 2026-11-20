from core.reference_analysis.auxiliary_presentation_entrance_evidence_resolver_v1 import (
    AuxiliaryPresentationEntranceEvidenceResolverV1,
)


def _gate(name="Gate"):
    return {"object_id": name, "name": name, "type": "MESH", "location": [0, 0, 1],
            "rotation_euler": [0, 0, 0], "scale": [1, 1, 1], "world_matrix": [],
            "world_bbox": {"min": [0, -0.1, 0], "max": [1, 0.1, 2]},
            "mesh_statistics": {"polygon_count": 12}}


def _revit():
    return {"doors": [
        {"element_id": 1, "location": {"x": 2, "y": 3}, "host_wall_id": 9},
        {"element_id": 2, "location": {"x": 4, "y": 5}, "host_wall_id": 8},
        {"element_id": 3, "location": {"x": 6, "y": 7}, "host_wall_id": 7}],
        "dxf_comparison": {"translation_revit_minus_dxf": [5.5, 0]}}


def test_two_gate_candidates_remain_fail_closed():
    result = AuxiliaryPresentationEntranceEvidenceResolverV1().resolve(
        {"objects": [_gate("Gate 1"), _gate("Gate 2")]}, _revit())
    assert result["pedestrian_entrance"]["status"] == "UNRESOLVED_MULTIPLE_GATE_CANDIDATES"
    assert result["main_entrance_status"] == "UNRESOLVED"


def test_name_without_mesh_is_not_a_candidate():
    item = _gate("Pedestrian Gate")
    item["type"] = "EMPTY"
    result = AuxiliaryPresentationEntranceEvidenceResolverV1().resolve({"objects": [item]}, _revit())
    assert result["candidate_objects"] == []


def test_bbox_does_not_become_passage_geometry():
    result = AuxiliaryPresentationEntranceEvidenceResolverV1().resolve({"objects": [_gate()]}, _revit())
    assert result["candidate_objects"][0]["passage_segment"] is None
    assert result["candidate_objects"][0]["passage_status"].startswith("UNRESOLVED")


def test_coordinate_transform_requires_multiple_geometric_anchors():
    scene = {"objects": [_gate(),
        {**_gate("Door mesh 1"), "name": "mesh", "location": [2, 3, 1]},
        {**_gate("Door mesh 2"), "name": "mesh", "location": [4, 5, 1]},
        {**_gate("Door mesh 3"), "name": "mesh", "location": [6, 7, 1]}]}
    result = AuxiliaryPresentationEntranceEvidenceResolverV1().resolve(scene, _revit())
    assert result["coordinate_correspondence"]["max_fbx_to_revit_status"] == "PROVEN_IDENTITY_XY"
    assert result["coordinate_correspondence"]["canonical_dxf_transform_status"] == "PROVEN"
