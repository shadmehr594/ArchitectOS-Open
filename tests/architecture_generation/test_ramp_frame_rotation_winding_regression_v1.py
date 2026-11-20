import pytest
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, box

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2


@pytest.mark.parametrize("reverse_frontage", [False, True])
def test_rotated_translated_pivot_and_winding_preserve_ramp_clipping(reverse_frontage):
    helper = BasementRampParkingDesignReasonerV2()
    parcel = box(0, 0, 14, 24)
    outer = box(0.35, 0.35, 13.65, 23.65)
    inner = box(0.65, 0.65, 13.35, 23.35)
    ramp_probe = box(1.0, 0.0, 4.5, 18.0)
    frontage = [[0, 0], [14, 0]]

    angle = 37
    pivot = (41.25, -16.75)
    dx, dy = 83.5, -29.25

    def transformed(geometry):
        return translate(rotate(geometry, angle, origin=pivot), dx, dy)

    world_parcel = transformed(parcel)
    world_outer = transformed(outer)
    world_inner = transformed(inner)
    world_probe = transformed(ramp_probe)
    world_frontage_line = transformed(Polygon(frontage + [[14, -0.01], [0, -0.01]]).boundary)
    coords = list(world_frontage_line.coords)
    # The first long segment is the transformed source frontage.
    world_frontage = [coords[0], coords[1]]
    if reverse_frontage:
        world_frontage = list(reversed(world_frontage))

    parcel_points = list(world_parcel.exterior.coords)[:-1]
    frame = helper._frame(parcel_points, world_frontage)
    local_outer = helper._to_local_polygon(list(world_outer.exterior.coords)[:-1], frame)
    local_inner = helper._to_local_polygon(list(world_inner.exterior.coords)[:-1], frame)
    local_probe = helper._to_local_polygon(list(world_probe.exterior.coords)[:-1], frame)

    assert local_outer.is_valid and local_inner.is_valid and local_probe.is_valid
    assert local_outer.buffer(helper.EPS).covers(local_inner)
    assert local_probe.intersection(local_inner).area == pytest.approx(
        world_probe.intersection(world_inner).area)

    round_trip = Polygon(helper._world_polygon(local_inner, frame))
    assert round_trip.symmetric_difference(world_inner).area <= helper.EPS
