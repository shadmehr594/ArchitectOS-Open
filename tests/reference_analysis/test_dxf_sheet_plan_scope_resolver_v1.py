from pathlib import Path

import ezdxf

from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import (
    DXFSheetPlanScopeResolverV1,
)


def _add_view(modelspace, x, title, *, plan=True):
    modelspace.add_lwpolyline([(x, 0), (x + 8, 0), (x + 8, 6), (x, 6)], close=True)
    if plan:
        modelspace.add_line((x + 1, 1), (x + 7, 1), dxfattribs={"layer": "A-WALL"})
        modelspace.add_linear_dim(base=(x + 4, 6.5), p1=(x, 6), p2=(x + 8, 6)).render()
    modelspace.add_text("SCALE", dxfattribs={"height": 0.2}).set_placement((x, -1))
    modelspace.add_text("1:100", dxfattribs={"height": 0.2}).set_placement((x + 2, -1))
    modelspace.add_mtext(title, dxfattribs={"char_height": 0.25, "insert": (x, -0.5)})


def test_synthetic_multiview_selects_unique_non_presentation_plan(tmp_path):
    path = tmp_path / "multi_view.dxf"
    document = ezdxf.new()
    modelspace = document.modelspace()
    _add_view(modelspace, 0, "FLOOR PLAN")
    _add_view(modelspace, 15, "FLOOR PLAN PRESENTATION")
    _add_view(modelspace, 30, "SOUTH ELEVATION", plan=False)
    _add_view(modelspace, 45, "NORTH ELEVATION", plan=False)
    document.saveas(path)
    result = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    assert result["view_count"] == 4
    assert result["selection_status"] == "resolved"
    assert result["selected_view_id"] == "VIEW-001"
    assert result["selected_view_transform"]["type"] == "identity"
    assert result["plan_relationships"][0]["relationship"] == "presentation_copy"


def test_ambiguous_two_plan_dxf_fails_closed(tmp_path):
    path = tmp_path / "ambiguous.dxf"
    document = ezdxf.new()
    modelspace = document.modelspace()
    _add_view(modelspace, 0, "FLOOR PLAN")
    _add_view(modelspace, 15, "FLOOR PLAN")
    document.saveas(path)
    result = DXFSheetPlanScopeResolverV1().resolve(path, {"storeys": 1})
    assert result["selection_status"] == "plan_scope_pending"
    assert result["selected_handles"] == []
    assert result["downstream_reference_evidence"]["candidate_parcel_boundaries"] == []
    assert result["downstream_reference_evidence"]["entrance_door_candidates"] == []


def test_real_benchmark_reports_views_without_parcel_or_access_inference():
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    result = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    assert result["view_count"] == 4
    assert [view["view_type"] for view in result["views"]] == [
        "architectural_plan", "architectural_plan", "elevation", "elevation"
    ]
    assert result["selection_status"] == "plan_scope_pending"
    assert result["selected_view_id"] is None
    assert result["plan_relationships"][0]["relationship"] == "presentation_copy_candidate"
    evidence = result["downstream_reference_evidence"]
    assert evidence["parcel_status"] == "UNRESOLVED"
    assert evidence["pedestrian_access_evidence"] == []
    assert evidence["entrance_door_candidates"] == []
