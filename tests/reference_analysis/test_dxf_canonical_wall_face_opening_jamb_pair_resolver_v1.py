from pathlib import Path

import ezdxf

from core.reference_analysis.dxf_canonical_plan_architectural_evidence_resolver_v1 import DXFCanonicalPlanArchitecturalEvidenceResolverV1
from core.reference_analysis.dxf_canonical_wall_face_opening_jamb_pair_resolver_v1 import DXFCanonicalWallFaceOpeningJambPairResolverV1
from core.reference_analysis.dxf_canonical_wall_topology_opening_resolver_v1 import DXFCanonicalWallTopologyOpeningResolverV1
from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1


def _contract(tmp_path, *, opening=True, ambiguous=False, rotation=0.0, door=True):
    path = tmp_path / "faces.dxf"
    document = ezdxf.new()
    document.layers.add("A-WALL"); document.layers.add("A-DOOR-FRAM")
    block = document.blocks.new("VALIDATION-BLOCK")
    block.add_line((-0.5, 0), (0.5, 0))
    msp = document.modelspace()
    if rotation == 0.0:
        ys = [0.0, 0.2] + ([0.4] if ambiguous else [])
        for y in ys:
            if opening:
                msp.add_line((0, y), (4, y), dxfattribs={"layer": "A-WALL"})
                msp.add_line((5, y), (10, y), dxfattribs={"layer": "A-WALL"})
            else:
                msp.add_line((0, y), (10, y), dxfattribs={"layer": "A-WALL"})
        msp.add_line((0, 0), (0, ys[-1]), dxfattribs={"layer": "A-WALL"})
        msp.add_line((10, 0), (10, ys[-1]), dxfattribs={"layer": "A-WALL"})
        center = (4.5, ys[-1] / 2)
    else:
        xs = [0.0, 0.2]
        for x in xs:
            msp.add_line((x, 0), (x, 4), dxfattribs={"layer": "A-WALL"})
            msp.add_line((x, 5), (x, 10), dxfattribs={"layer": "A-WALL"})
        msp.add_line((0, 0), (0.2, 0), dxfattribs={"layer": "A-WALL"})
        msp.add_line((0, 10), (0.2, 10), dxfattribs={"layer": "A-WALL"})
        center = (0.1, 4.5)
    if door:
        msp.add_blockref("VALIDATION-BLOCK", center, dxfattribs={"layer": "A-DOOR-FRAM", "rotation": rotation})
    document.saveas(path)
    scope = {"views": [{"view_id": "VIEW-001", "source_handles": [e.dxf.handle for e in msp]}]}
    topology = DXFCanonicalWallTopologyOpeningResolverV1().resolve(path, scope, {"canonical_view_id": "VIEW-001"})
    return DXFCanonicalWallFaceOpeningJambPairResolverV1().resolve(topology)


def test_parallel_faces_and_door_resolve_opening(tmp_path):
    result = _contract(tmp_path)
    assert len(result["wall_face_pair_candidates"]) == 1
    assert len(result["opening_void_candidates"]) == 1
    assert result["door_associations"][0]["status"] == "resolved"


def test_two_possible_face_pairs_preserve_ambiguity(tmp_path):
    result = _contract(tmp_path, ambiguous=True)
    assert len(result["wall_face_pair_candidates"]) > 1
    assert result["door_associations"][0]["status"] == "pending_multiple_candidates"


def test_rotated_door_resolves_after_world_transform(tmp_path):
    result = _contract(tmp_path, rotation=90.0)
    assert result["door_associations"][0]["status"] == "resolved"


def test_wall_without_opening_produces_physical_wall_only(tmp_path):
    result = _contract(tmp_path, opening=False, door=False)
    assert len(result["physical_wall_candidates"]) == 1
    assert result["opening_void_candidates"] == []


def test_real_benchmark_remains_without_guessed_entrance(tmp_path):
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    correspondence = DXFViewCorrespondenceResolverV1().resolve(path, scope)
    evidence = DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(path, scope, correspondence)
    topology = DXFCanonicalWallTopologyOpeningResolverV1().resolve(path, scope, evidence, correspondence)
    output = tmp_path / "dxf_wall_face_opening_jamb_pair_contract.json"
    result = DXFCanonicalWallFaceOpeningJambPairResolverV1().resolve(topology, output)
    assert result["canonical_view_id"] == "VIEW-001"
    assert len(result["door_associations"]) == 7
    assert len(result["window_associations"]) == 4
    assert result["main_entrance_status"] == "UNRESOLVED"
    assert result["production_pipeline_consumable"] is False
    assert output.exists()
