from shapely.geometry import box

from core.architecture.reasoning.terminal_vehicle_alignment_v2 import TerminalVehicleAlignmentV2


def test_alignment_is_not_resolved_without_axis_aligned_field():
    result=TerminalVehicleAlignmentV2().resolve([8,8],[1,0],list(box(0,0,10,10).exterior.coords)[:-1],list(box(0,0,2,8).exterior.coords)[:-1])
    assert result['terminal_alignment_status']=='alignment_path_pending'
    assert result['selected'] is None


def test_alignment_resolves_only_with_real_end_and_field():
    result=TerminalVehicleAlignmentV2().resolve([2,2],[1,0],list(box(0,0,20,20).exterior.coords)[:-1],list(box(0,0,2,2).exterior.coords)[:-1])
    assert result['terminal_alignment_status']=='hard_valid'
    assert result['selected']['maneuvering_orientation']=='site_local_axes'
    assert result['selected']['end_interface_width']>=3.0
