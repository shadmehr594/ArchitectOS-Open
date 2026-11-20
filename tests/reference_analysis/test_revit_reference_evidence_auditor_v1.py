import json

from core.reference_analysis.revit_reference_evidence_auditor_v1 import (
    RevitReferenceEvidenceAuditorV1,
)


def _contract(file_name="album.rvt"):
    return {
        "file": file_name,
        "levels": [
            {"element_id": 1, "name": "site", "elevation": 0.0, "is_building_story": True},
            {"element_id": 2, "name": "floor", "elevation": 0.4, "is_building_story": True},
        ],
        "floors": [], "walls": [], "doors": [], "windows": [], "stairs": [],
        "generic_models": [], "dimensions": [], "entrance_evidence": {"status": "UNRESOLVED"},
    }


def test_level_flags_do_not_become_architectural_storey_count(tmp_path):
    path = tmp_path / "revit_reference_contract_album.json"
    path.write_text(json.dumps(_contract()), encoding="utf-8")
    result = RevitReferenceEvidenceAuditorV1().audit(path)
    levels = result["reference_analysis"]["level_analysis"]
    assert levels["native_level_count"] == 2
    assert levels["architectural_storey_count"] is None
    assert levels["finished_floor_040_status"] == "AUTHORITATIVE_LEVEL"


def test_no_album_dxf_is_not_compared_to_sina(tmp_path):
    path = tmp_path / "revit_reference_contract_sina.json"
    path.write_text(json.dumps(_contract("sina.rvt")), encoding="utf-8")
    result = RevitReferenceEvidenceAuditorV1().audit(path)
    assert result["dxf_comparison"]["status"] == "NOT_APPLICABLE_NO_CORRESPONDING_DXF_REFERENCE"


def test_instance_correspondence_requires_unique_translation_consensus():
    revit = [{"element_id": 10, "location": {"x": 6.0, "y": 2.0}, "host_wall_id": 99}]
    dxf = [{"door_id": "D1", "source_handle": "A", "insertion_point": [1.0, 2.0]}]
    pairs, translation = RevitReferenceEvidenceAuditorV1()._match_instances(revit, dxf, "door")
    assert translation == [5.0, 0.0]
    assert pairs[0]["revit_host_wall_id"] == 99


def test_generic_model_is_not_converted_to_native_stair():
    contract = _contract()
    contract["generic_models"] = [{
        "element_id": 20, "family": "Generic Models 6", "geometry": {},
        "solid_geometry": [{"horizontal_faces": [
            {"elevation": 0.0}, {"elevation": 0.2}, {"elevation": 0.4},
            {"elevation": 0.6}, {"elevation": 0.8}, {"elevation": 1.0},
        ]}],
    }]
    result = RevitReferenceEvidenceAuditorV1()._stairs(contract, "album")
    assert result["native_stair_count"] == 0
    assert result["generic_model_stair_geometry_candidates"]
    assert result["semantic_conversion_performed"] is False
