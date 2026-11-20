import pytest

from core.architecture.reasoning.curved_ramp_physical_path_length_contract_v1 import CurvedRampPhysicalPathLengthContractV1
from core.architecture.reasoning.far_end_operational_turn_v2 import RampWidthTransitionV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


def result(leg1,leg2):
    topology=RampCenterlineTopologyV2().construct([0,0],[0,1],leg1,'right',.8,5,3.5,leg2,0,.15,-2.4)
    return CurvedRampPhysicalPathLengthContractV1().resolve(topology,RampWidthTransitionV1().resolve(topology,3,3.5,3))


def test_shortest_physical_edge_controls_acceptance():
    evidence=result(10,1)
    assert evidence['centerline_length']>evidence['shortest_physical_path']
    assert evidence['geometry_status']=='insufficient_physical_edge_run'
    assert evidence['failure_reasons']==['shortest_physical_path_below_required_run']


def test_long_route_can_pass_even_when_centerline_exceeds_sixteen():
    evidence=result(17,3)
    assert evidence['centerline_length']>16
    assert evidence['shortest_physical_path']>=16
    assert evidence['geometry_status']=='resolved'


def test_level_edges_and_cross_slope_are_reported_separately():
    evidence=result(17,3)
    assert evidence['level_start_edge'] and evidence['level_end_edge']
    assert evidence['required_max_cross_slope']==pytest.approx(0)
    assert evidence['cross_slope_compliance']=='pending_requirement'
