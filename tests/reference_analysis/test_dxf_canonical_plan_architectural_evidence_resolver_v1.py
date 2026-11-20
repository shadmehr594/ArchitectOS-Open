from pathlib import Path

import ezdxf

from core.reference_analysis.dxf_canonical_plan_architectural_evidence_resolver_v1 import (
    DXFCanonicalPlanArchitecturalEvidenceResolverV1,
)
from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1


def _add_door_block(document):
    if "DOOR-900 x 2000mm" not in document.blocks:
        block = document.blocks.new("DOOR-900 x 2000mm")
        block.add_line((-0.45, 0), (0.45, 0))


def _synthetic(tmp_path, *, two_doors=False, leader=True, steps=True):
    path = tmp_path / "canonical.dxf"
    doc = ezdxf.new()
    for layer in ("A-WALL", "A-DOOR-FRAM", "A-FLOR", "A-ANNO"):
        doc.layers.add(layer)
    _add_door_block(doc)
    msp = doc.modelspace()
    msp.add_mtext("FLOOR PLAN", dxfattribs={"char_height": 0.2, "insert": (0, 12)})
    for start, end in [((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0))]:
        msp.add_line(start, end, dxfattribs={"layer": "A-WALL"})
    msp.add_blockref("DOOR-900 x 2000mm", (4, 0), dxfattribs={"layer": "A-DOOR-FRAM"})
    if two_doors:
        msp.add_blockref("DOOR-900 x 2000mm", (7, 0), dxfattribs={"layer": "A-DOOR-FRAM"})
    platform = msp.add_lwpolyline([(3, 0), (5, 0), (5, -2), (3, -2)], close=True, dxfattribs={"layer": "A-FLOR"})
    level = msp.add_text("+0.40", dxfattribs={"height": 0.2, "layer": "A-ANNO"})
    level.set_placement((6, -1))
    if leader:
        msp.add_leader([(6, -1), (5, -1)], dxfattribs={"layer": "A-ANNO"})
    n = msp.add_text("n:2", dxfattribs={"height": 0.2, "layer": "A-ANNO"})
    n.set_placement((4, -3.0))
    h = msp.add_text("h:0.20", dxfattribs={"height": 0.2, "layer": "A-ANNO"})
    h.set_placement((4, -3.2))
    if steps:
        msp.add_lwpolyline([(3, -2), (5, -2), (5, -4), (3, -4)], close=True, dxfattribs={"layer": "A-FLOR"})
        for y in (-2.0, -3.0, -4.0):
            msp.add_line((3, y), (5, y), dxfattribs={"layer": "A-FLOR"})
    doc.saveas(path)
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"storeys": 1})
    correspondence = {"canonicalization_allowed": True, "canonical_analysis_view_id": "VIEW-001",
                      "unmatched_authoritative_geometry": []}
    metadata = {"site_datum": 0.0, "finished_floor": 0.4, "platform_elevation": 0.4,
                "riser_count": 2, "riser_height": 0.2}
    return DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(path, scope, correspondence, metadata)


def test_resolved_synthetic_entrance_transition(tmp_path):
    result = _synthetic(tmp_path)
    assert result["building_footprint"]["status"] == "resolved"
    assert result["main_entrance_analysis"]["status"] == "resolved"
    assert result["platform_candidate"]["geometry_status"] == "AUTHORITATIVE"
    assert result["entrance_transition_reference"]["status"] == "resolved"
    assert result["entrance_transition_reference"]["riser_count"] == 2
    assert result["entrance_transition_reference"]["riser_height"] == 0.20


def test_two_exterior_doors_remain_pending(tmp_path):
    result = _synthetic(tmp_path, two_doors=True, leader=False, steps=False)
    assert result["main_entrance_analysis"]["status"] == "pending_multiple_candidates"
    assert result["entrance_transition_reference"]["status"] == "UNRESOLVED"


def test_level_proximity_without_leader_is_unresolved(tmp_path):
    result = _synthetic(tmp_path, leader=False)
    assert result["level_annotation_binding"][0]["binding_status"] == "UNRESOLVED"


def test_vertical_step_text_without_xy_geometry_is_preserved(tmp_path):
    result = _synthetic(tmp_path, steps=False)
    group = result["step_annotation_groups"][0]
    assert (group["riser_count"], group["riser_height"], group["total_rise"]) == (2, 0.2, 0.4)
    assert group["geometry_binding_status"] == "UNRESOLVED"
    assert group["bound_step_geometry"] is None


def test_real_benchmark_stays_evidence_driven():
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    correspondence = DXFViewCorrespondenceResolverV1().resolve(path, scope)
    result = DXFCanonicalPlanArchitecturalEvidenceResolverV1().resolve(
        path, scope, correspondence,
        {"site_datum": 0.0, "finished_floor": 0.4, "platform_elevation": 0.4,
         "riser_count": 2, "riser_height": 0.2},
    )
    assert result["canonical_view_id"] == "VIEW-001"
    assert len(result["door_evidence"]) == 7
    assert len(result["level_annotation_binding"]) == 2
    assert len(result["step_annotation_groups"]) == 2
    assert result["parcel_boundary"]["status"] == "UNRESOLVED"
    assert result["user_authoritative_metadata"]["used_for_xy_resolution"] is False
