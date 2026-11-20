import pytest

from core.architecture.reasoning.curved_ramp_stationed_surface_v1 import CurvedRampStationedSurfaceV1
from core.architecture.reasoning.far_end_operational_turn_v2 import RampWidthTransitionV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


def surface():
    topology=RampCenterlineTopologyV2().construct([0,0],[0,1],10,'right',0.8,5,3.5,2,0,.15,-2.4)
    widths=RampWidthTransitionV1().resolve(topology,3,3.5,3)
    return topology,CurvedRampStationedSurfaceV1().resolve(topology,widths)


def test_every_cross_section_uses_one_station_z():
    _,result=surface()
    assert all(item['left'][2]==pytest.approx(item['center'][2])==pytest.approx(item['right'][2]) for item in result['cross_sections'])
    assert result['surface_twist_status']=='untwisted'


def test_end_cross_section_is_level_at_basement():
    _,result=surface()
    assert result['end_left_z']==pytest.approx(-2.4)
    assert result['end_center_z']==pytest.approx(-2.4)
    assert result['end_right_z']==pytest.approx(-2.4)
    assert result['end_cross_section_level_error']==pytest.approx(0)


def test_curve_edges_have_distinct_longitudinal_grades():
    topology,result=surface();s1=topology['stationing']['S1'];s2=topology['stationing']['S2']
    indices=[i for i,s in enumerate(result['centerline_stations'][:-1]) if s1<=s<s2]
    assert any(abs(result['local_grade_left_edge'][i]-result['local_grade_right_edge'][i])>1e-6 for i in indices)


def test_surface_faces_follow_common_station_pairs():
    _,result=surface()
    assert len(result['surface_3d']['vertices'])==2*len(result['cross_sections'])
    assert len(result['surface_3d']['faces'])==len(result['cross_sections'])-1
