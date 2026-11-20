from shapely.geometry import box

from core.architecture.reasoning.terminal_vehicle_alignment_v1 import TerminalVehicleAlignmentV1


def test_site_local_axis_heading_is_already_aligned():
    r=TerminalVehicleAlignmentV1().resolve([10,10],[0,1],list(box(0,0,30,30).exterior.coords)[:-1])
    assert r["geometry_status"]=="resolved"
    assert r["selected"]["geometry_status"]=="already_aligned"


def test_diagonal_heading_requires_real_floor_level_curve():
    r=TerminalVehicleAlignmentV1().resolve([10,10],[.707,.707],list(box(0,0,30,30).exterior.coords)[:-1])
    assert r["geometry_status"]=="resolved"
    assert r["selected"]["alignment_angle_degrees"]>0
    assert r["selected"]["clearance_corridor"]


def test_renderer_cannot_invent_unresolved_alignment():
    r=TerminalVehicleAlignmentV1().resolve([1,1],[.707,.707],list(box(0,0,3,3).exterior.coords)[:-1])
    assert r["geometry_status"]=="unresolved" and r["selected"] is None
