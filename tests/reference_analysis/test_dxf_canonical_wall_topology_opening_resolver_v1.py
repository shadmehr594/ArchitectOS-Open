from pathlib import Path

import ezdxf
import pytest

from core.reference_analysis.dxf_canonical_plan_architectural_evidence_resolver_v1 import (
    DXFCanonicalPlanArchitecturalEvidenceResolverV1,
)
from core.reference_analysis.dxf_canonical_wall_topology_opening_resolver_v1 import (
    DXFCanonicalWallTopologyOpeningResolverV1,
)
from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1


def _fixture(tmp_path, *, door=True, rotation=0.0, second_host=False):
    path = tmp_path / "wall-topology.dxf"
    document = ezdxf.new()
    document.layers.add("A-WALL")
    document.layers.add("A-DOOR-FRAM")
    block = document.blocks.new("TEST-OPENING")
    block.add_line((-0.5, 0), (0.5, 0))
    modelspace = document.modelspace()
    if rotation == 0.0:
        walls = [((0, 0), (4, 0)), ((5, 0), (10, 0)), ((10, 0), (10, 8)),
                 ((10, 8), (0, 8)), ((0, 8), (0, 0))]
        center = (4.5, 0)
        if second_host:
            walls += [((0, 0.1), (4, 0.1)), ((5, 0.1), (10, 0.1))]
    else:
        walls = [((0, 0), (0, 4)), ((0, 5), (0, 10)), ((0, 10), (8, 10)),
                 ((8, 10), (8, 0)), ((8, 0), (0, 0))]
        center = (0, 4.5)
    for start, end in walls:
        modelspace.add_line(start, end, dxfattribs={"layer": "A-WALL"})
    if door:
        modelspace.add_blockref("TEST-OPENING", center,
                                dxfattribs={"layer": "A-DOOR-FRAM", "rotation": rotation})
    document.saveas(path)
    handles = [entity.dxf.handle for entity in modelspace]
    scope = {"views": [{"view_id": "VIEW-001", "source_handles": handles}]}
    evidence = {"canonical_view_id": "VIEW-001"}
    return DXFCanonicalWallTopologyOpeningResolverV1().resolve(path, scope, evidence)


def test_simple_house_matching_gap_resolves_door_host(tmp_path):
    result = _fixture(tmp_path)
    assert len(result["opening_candidates"]) == 1
    assert result["door_associations"][0]["host_status"] == "resolved"
    assert len(result["door_associations"][0]["host_wall_handles"]) == 2


def test_two_possible_host_gaps_remain_pending(tmp_path):
    result = _fixture(tmp_path, second_host=True)
    assert result["door_opening_associations"][0]["status"] == "pending_multiple_candidates"
    assert result["door_associations"][0]["host_wall_id"] is None


def test_translated_rotated_block_uses_world_geometry(tmp_path):
    result = _fixture(tmp_path, rotation=90.0)
    geometry = result["door_world_geometry"][0]
    assert geometry["center"] == pytest.approx([0.0, 4.5])
    assert abs(geometry["opening_axis"][0]) < 1e-8
    assert abs(abs(geometry["opening_axis"][1]) - 1.0) < 1e-8
    assert result["door_associations"][0]["host_status"] == "resolved"


def test_gap_without_door_remains_opening_candidate_only(tmp_path):
    result = _fixture(tmp_path, door=False)
    assert len(result["opening_candidates"]) == 1
    assert result["door_associations"] == []


def test_real_benchmark_has_no_fake_entrance(tmp_path):
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    correspondence = DXFViewCorrespondenceResolverV1().resolve(path, scope)
    evidence = DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(path, scope, correspondence)
    output = tmp_path / "dxf_wall_topology_opening_contract.json"
    result = DXFCanonicalWallTopologyOpeningResolverV1().resolve(
        path, scope, evidence, correspondence, output,
    )
    assert result["canonical_view_id"] == "VIEW-001"
    assert len(result["door_associations"]) == 7
    assert len(result["window_associations"]) == 4
    assert result["production_pipeline_consumable"] is False
    assert "main_entrance" in result["unresolved_items"]
    assert output.exists()
