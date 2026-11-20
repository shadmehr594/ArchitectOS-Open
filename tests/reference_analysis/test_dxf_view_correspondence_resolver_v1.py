from pathlib import Path

import ezdxf
import pytest

from core.reference_analysis.dxf_sheet_plan_scope_resolver_v1 import DXFSheetPlanScopeResolverV1
from core.reference_analysis.dxf_view_correspondence_resolver_v1 import DXFViewCorrespondenceResolverV1


def _view(modelspace, x, *, noise=False, changed=False):
    modelspace.add_mtext("FLOOR PLAN", dxfattribs={"char_height": 0.2, "insert": (x, -1)})
    modelspace.add_text("1:100", dxfattribs={"height": 0.2}).set_placement((x + 2, -1))
    modelspace.add_text("+0.40", dxfattribs={"height": 0.2}).set_placement((x + 2, 2))
    modelspace.add_line((x, 0), (x + 8, 0), dxfattribs={"layer": "A-WALL"})
    modelspace.add_line((x + 8, 0), (x + 8, 6), dxfattribs={"layer": "A-WALL"})
    modelspace.add_line((x + 8, 6), (x, 6), dxfattribs={"layer": "A-WALL"})
    modelspace.add_line((x, 6), (x, 0 if not changed else 1), dxfattribs={"layer": "A-WALL"})
    if "D" not in modelspace.doc.blocks:
        block = modelspace.doc.blocks.new("D")
        block.add_line((0, 0), (1, 0))
    modelspace.add_blockref("D", (x + 4, 0), dxfattribs={"layer": "A-DOOR-FRAM"})
    modelspace.add_linear_dim(base=(x + 4, 7), p1=(x, 6), p2=(x + 8, 6)).render()
    if noise:
        for index in range(20):
            modelspace.add_circle((x + index * 0.1, 3), 0.02, dxfattribs={"layer": "A-FLOR"})


def _resolve(tmp_path, *, noise=False, changed=False):
    path = tmp_path / "views.dxf"
    document = ezdxf.new()
    document.layers.add("A-WALL")
    document.layers.add("A-DOOR-FRAM")
    document.layers.add("A-FLOR")
    modelspace = document.modelspace()
    _view(modelspace, 0)
    _view(modelspace, 20, noise=noise, changed=changed)
    document.saveas(path)
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"storeys": 1})
    return DXFViewCorrespondenceResolverV1().resolve(path, scope)


def test_exact_translated_duplicate_is_equivalent_and_canonicalized(tmp_path):
    result = _resolve(tmp_path)
    assert result["equivalence_status"] == "equivalent"
    assert result["translation_vector"] == [20.0, 0.0]
    assert result["canonicalization_allowed"] is True
    assert result["primary_view_id"] is None
    assert result["canonical_analysis_view_id"] == "VIEW-001"


def test_presentation_floor_noise_does_not_change_architectural_equivalence(tmp_path):
    result = _resolve(tmp_path, noise=True)
    assert result["equivalence_status"] == "equivalent"
    assert result["presentation_only_entities"][0]["additional_count"] == 20
    assert result["architectural_difference_detected"] is False


def test_changed_architectural_wall_forbids_canonicalization(tmp_path):
    result = _resolve(tmp_path, changed=True)
    assert result["equivalence_status"] == "not_equivalent"
    assert result["architectural_difference_detected"] is True
    assert result["canonicalization_allowed"] is False


def test_real_benchmark_correspondence():
    path = Path(__file__).resolve().parents[2] / "exports" / "DEFAULT" / "reference_analysis" / "آلبوم نقشه ها.dxf"
    scope = DXFSheetPlanScopeResolverV1().resolve(path, {"building_type": "villa", "storeys": 1})
    result = DXFViewCorrespondenceResolverV1().resolve(path, scope)
    assert result["view_a"] == "VIEW-001" and result["view_b"] == "VIEW-002"
    assert result["equivalence_status"] == "equivalent"
    assert result["translation_vector"] == pytest.approx([24.6395755042, -0.9230753717])
    assert result["wall_match_score"] > 0.96
    assert result["door_match_score"] == 1.0
    assert result["window_match_score"] == 1.0
    assert result["level_annotation_match_score"] == 1.0
    assert result["primary_view_id"] is None
    assert result["canonicalization_allowed"] is True
    assert result["canonical_analysis_view_id"] == "VIEW-001"
