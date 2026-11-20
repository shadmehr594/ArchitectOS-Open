from copy import deepcopy
import json

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, MultiPolygon, Polygon

from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import _take_area, _validated_areal_geometry


def test_valid_polygon_passes_without_change_or_repair():
    source=Polygon([(0,0),(8,0),(8,5),(0,5)])
    result,evidence,failure=_take_area(source,12)
    assert failure is None and result.is_valid
    assert evidence["input_validity"]=="valid" and evidence["repair_applied"] is False
    assert source.equals(Polygon([(0,0),(8,0),(8,5),(0,5)]))


def test_self_intersection_is_audited_and_semantic_loss_fails_closed():
    bowtie=Polygon([(0,0),(4,4),(0,4),(4,0),(0,0)])
    result,evidence,failure=_validated_areal_geometry(bowtie)
    assert result.is_empty and evidence["repair_applied"] is True
    assert evidence["repair_method"]=="GEOSMakeValid"
    assert failure in {"invalid_geometry_repair_multiple_components","invalid_geometry_repair_area_change"}


def test_multipolygon_repair_result_is_not_silently_collapsed():
    bowtie=Polygon([(0,0),(4,4),(0,4),(4,0),(0,0)])
    _,evidence,failure=_validated_areal_geometry(bowtie)
    assert evidence["geometry_type_after"]=="MultiPolygon"
    assert failure=="invalid_geometry_repair_multiple_components"


def test_area_preserving_standard_repair_is_accepted():
    spike=Polygon([(0,0),(4,0),(4,4),(2,4),(2,2),(2,4),(0,4),(0,0)])
    repaired,evidence,failure=_validated_areal_geometry(spike)
    assert failure is None and repaired.is_valid and repaired.geom_type=="Polygon"
    assert evidence["repair_status"]=="accepted"
    assert abs(evidence["area_before"]-evidence["area_after"])<=1e-7


def test_dimensional_collapse_fails_closed():
    collapsed=Polygon([(0,0),(1,0),(2,0),(0,0)])
    repaired,evidence,failure=_validated_areal_geometry(collapsed)
    assert repaired.is_empty and evidence["repair_status"]=="rejected"
    assert failure=="invalid_geometry_repair_dimensional_collapse"


def test_result_and_evidence_are_deterministic_and_input_is_not_mutated():
    source=Polygon([(0,0),(8,0),(8,5),(0,5)]); before=source.wkb
    first=_take_area(source,11); second=_take_area(source,11)
    assert first[0].wkb_hex==second[0].wkb_hex
    assert json.dumps(first[1],sort_keys=True)==json.dumps(second[1],sort_keys=True)
    assert source.wkb==before


def test_rotation_and_translation_invariance():
    source=Polygon([(0,0),(8,0),(8,5),(0,5)])
    base,_,failure=_take_area(source,10); assert failure is None
    transformed=translate(rotate(source,31,origin=(0,0)),13,-7)
    moved,_,failure=_take_area(transformed,10); assert failure is None
    assert abs(base.area-moved.area)<=1e-7
