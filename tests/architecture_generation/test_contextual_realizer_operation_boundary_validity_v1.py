from copy import deepcopy
import json

from shapely.affinity import rotate, translate
from shapely.geometry import MultiPolygon, Polygon

from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import _boolean_operation, _validate_published_geometry


def test_valid_intersection_difference_union_chain_stays_valid():
    parcel=Polygon([(0,0),(8,0),(8,6),(0,6)])
    cut=Polygon([(2,-1),(7,-1),(7,7),(2,7)])
    intersection,evidence,failure=_boolean_operation(parcel,cut,"chain.intersection")
    assert failure is None and intersection.is_valid
    difference,more,failure=_boolean_operation(intersection,Polygon([(3,1),(4,1),(4,2),(3,2)]),"chain.difference")
    assert failure is None and difference.is_valid
    union,last,failure=_boolean_operation(Polygon(),difference,"chain.union",multipart_result_allowed=True,multipart_left_allowed=True)
    assert failure is None and union.is_valid
    assert all("operation_name" in item for item in evidence+more+last)


def test_invalid_intersection_input_is_repaired_with_evidence():
    spike=Polygon([(0,0),(4,0),(4,4),(2,4),(2,2),(2,4),(0,4),(0,0)])
    result,evidence,failure=_boolean_operation(spike,Polygon([(-1,-1),(5,-1),(5,5),(-1,5)]),"probe.intersection")
    assert failure is None and result.is_valid
    assert evidence[0]["repair_applied"] and evidence[0]["repair_method"]=="GEOSMakeValid"


def test_invalid_difference_input_is_repaired_with_evidence():
    spike=Polygon([(0,0),(4,0),(4,4),(2,4),(2,2),(2,4),(0,4),(0,0)])
    result,evidence,failure=_boolean_operation(spike,Polygon([(1,1),(2,1),(2,2),(1,2)]),"probe.difference")
    assert failure is None and result.is_valid and any(x["repair_applied"] for x in evidence)


def test_invalid_union_accumulator_is_handled_fail_closed():
    bowtie=Polygon([(0,0),(4,4),(0,4),(4,0),(0,0)])
    result,evidence,failure=_boolean_operation(bowtie,Polygon([(5,0),(6,0),(6,1),(5,1)]),"probe.union",
        multipart_result_allowed=True,multipart_left_allowed=True)
    assert result.is_empty and failure in {"invalid_geometry_repair_multiple_components","invalid_geometry_repair_area_change"}


def test_valid_intermediate_multipolygon_and_accumulator_are_allowed():
    a=Polygon([(0,0),(1,0),(1,1),(0,1)]); b=Polygon([(3,0),(4,0),(4,1),(3,1)])
    result,evidence,failure=_boolean_operation(a,b,"probe.union",multipart_result_allowed=False)
    assert failure is None and result.is_valid and result.geom_type=="MultiPolygon"
    assert evidence[-1]["component_count_after"]==2


def test_valid_used_by_floor_multipolygon_accumulator_accepts_another_space():
    accumulator=MultiPolygon([Polygon([(0,0),(1,0),(1,1),(0,1)]),Polygon([(3,0),(4,0),(4,1),(3,1)])])
    new_space=Polygon([(6,0),(7,0),(7,1),(6,1)])
    result,evidence,failure=_boolean_operation(accumulator,new_space,"used_by_floor.union",
        multipart_result_allowed=True,multipart_left_allowed=True)
    assert failure is None and result.is_valid and len(result.geoms)==3


def test_published_contiguous_role_rejects_disconnected_domain_only_at_publication():
    geometry=MultiPolygon([Polygon([(0,0),(1,0),(1,1),(0,1)]),Polygon([(3,0),(4,0),(4,1),(3,1)])])
    result,evidence,failure=_validate_published_geometry(geometry,"RESIDENTIAL_UNIT","unit")
    assert result.is_empty and failure=="published_function_continuity_required"
    assert evidence["continuity_required"] and evidence["publication_status"]=="rejected"


def test_accumulator_continuity_is_not_confused_with_space_continuity():
    geometry=MultiPolygon([Polygon([(0,0),(1,0),(1,1),(0,1)]),Polygon([(3,0),(4,0),(4,1),(3,1)])])
    accumulator,_,failure=_boolean_operation(Polygon(),geometry,"used_by_floor.union",
        multipart_result_allowed=True,multipart_left_allowed=True)
    assert failure is None and accumulator.geom_type=="MultiPolygon"
    published,_,failure=_validate_published_geometry(geometry,"STAIR","stair")
    assert published.is_empty and failure=="published_function_continuity_required"


def test_hole_shell_topology_case_is_audited_without_crash():
    shell=Polygon([(0,0),(6,0),(6,6),(0,6)],holes=[[(2,2),(4,2),(4,4),(2,4)]])
    result,evidence,failure=_boolean_operation(shell,Polygon([(1,1),(5,1),(5,5),(1,5)]),"hole.intersection")
    assert failure is None and result.is_valid
    assert evidence[-1]["result_validity"]=="valid"


def test_operation_boundary_is_deterministic_non_mutating_and_transform_invariant():
    a=Polygon([(0,0),(8,0),(8,5),(0,5)]); b=Polygon([(2,-1),(7,-1),(7,6),(2,6)])
    before=(a.wkb,b.wkb)
    first=_boolean_operation(a,b,"stable.intersection"); second=_boolean_operation(a,b,"stable.intersection")
    assert first[0].wkb_hex==second[0].wkb_hex
    assert json.dumps(first[1],sort_keys=True)==json.dumps(second[1],sort_keys=True)
    assert (a.wkb,b.wkb)==before
    moved_a=translate(rotate(a,27,origin=(0,0)),9,-4); moved_b=translate(rotate(b,27,origin=(0,0)),9,-4)
    moved,_,failure=_boolean_operation(moved_a,moved_b,"stable.intersection")
    assert failure is None and abs(moved.area-first[0].area)<=1e-7
