from copy import deepcopy
from core.architecture.reasoning.pre_geometry_spatial_constraint_evaluator_v1 import PreGeometrySpatialConstraintEvaluatorV1
from core.architecture.reasoning.layout_regeneration_reasoner_v1 import LayoutRegenerationReasonerV1
from core.architecture.brain.architectural_brain import ArchitecturalBrain
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import _architectural_intent

B=[[0,0],[10,0],[10,6],[0,6]]
def p(n,x,y,w=2,d=2,**k):return {'name':n,'floor':'F1','x':x,'y':y,'width':w,'depth':d,**k}
def r(a,b,**k):return {'connection_id':a+'-'+b,'from':a,'to':b,'required':True,'direct_connection_required':True,**k}

def test_living_dining_missing_is_regenerated_to_shared_boundary():
    z=LayoutRegenerationReasonerV1().regenerate([p('living',0,0),p('dining',7,0)],[r('living','dining')],B)
    assert z['status']=='resolved' and z['quality_score_after']>z['quality_score_before']
def test_kitchen_dining_relationship_is_repaired():
    z=LayoutRegenerationReasonerV1().regenerate([p('dining',0,0),p('kitchen',8,0)],[r('dining','kitchen')],B)
    assert z['status']=='resolved'
def test_isolated_space_without_required_interface_fails_closed():
    e=PreGeometrySpatialConstraintEvaluatorV1().evaluate([p('corridor',0,0,connection_required=True),p('room',5,0)],[],B)
    assert 'corridor' in e['isolated_spaces']
def test_privacy_violation_corrected_with_explicit_clearance():
    rel=r('public','bedroom',type='privacy_separation',direct_connection_forbidden=True,privacy_clearance=1)
    z=LayoutRegenerationReasonerV1().regenerate([p('public',0,0),p('bedroom',2,0)],[rel],B)
    assert z['status']=='resolved'
def test_dead_end_corridor_is_reported_not_invented():
    e=PreGeometrySpatialConstraintEvaluatorV1().evaluate([p('corridor',0,0,circulation_role='corridor',minimum_connections=2),p('room',2,0)],[r('corridor','room')],B)
    assert 'corridor' in e['dead_end_circulation']
def test_candidate_outside_buildable_boundary_rejected():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',9,5)],[r('a','b')],[[0,0],[3,0],[3,2],[0,2]])
    assert z['status']=='unresolved_no_feasible_layout'
def test_stair_protected_zone_rejects_candidate():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',7,0)],[r('a','b')],B,[{'id':'stair','polygon':[[2,0],[4,0],[4,2],[2,2]]}])
    assert all(c['geometry_status']=='rejected' for c in z['candidates'] if c['action_sequence'][0]['action']=='align_right')
def test_ramp_protected_zone_rejects_candidate():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',7,0)],[r('a','b')],B,[{'id':'ramp','polygon':[[2,0],[4,0],[4,2],[2,2]]}])
    assert any(c['geometry_status']=='rejected' for c in z['candidates'])
def test_parking_zone_rejects_candidate():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',7,0)],[r('a','b')],B,[{'id':'parking_aisle','polygon':[[2,0],[4,0],[4,2],[2,2]]}])
    assert any(c['geometry_status']=='rejected' for c in z['candidates'])
def test_already_resolved_relationship_preserved():
    ps=[p('a',0,0),p('b',2,0),p('c',8,3)]
    z=LayoutRegenerationReasonerV1().regenerate(ps,[r('a','b'),r('b','c')],B)
    assert z['status'] in ('resolved','pending_tie','unresolved_no_feasible_layout')
    for candidate in z['candidates']:
        if candidate['geometry_status']=='feasible':
            assert PreGeometrySpatialConstraintEvaluatorV1().shared(candidate['resulting_layout'][0],candidate['resulting_layout'][1])
def test_equal_candidates_remain_pending_tie():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',4,2),p('b',4,2)],[r('a','b')],B)
    assert z['status']=='pending_tie' and z['selected_layout'] is None
def test_no_feasible_candidate_is_explicit():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',5,0)],[r('a','b')],[[0,0],[2,0],[2,2],[0,2]])
    assert z['status']=='unresolved_no_feasible_layout' and z['selected_layout'] is None
def test_selected_layout_improves_quality():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',7,0)],[r('a','b')],B)
    assert z['quality_score_after']>z['quality_score_before']
def test_contract_contains_no_physical_geometry_before_selection():
    z=LayoutRegenerationReasonerV1().regenerate([p('a',0,0),p('b',5,0)],[r('a','b')],[[0,0],[2,0],[2,2],[0,2]])
    assert 'physical_walls' not in z and 'slabs' not in z
def test_deterministic_repeat_produces_identical_result():
    args=([p('a',0,0),p('b',7,0)],[r('a','b')],B)
    one=LayoutRegenerationReasonerV1().regenerate(*deepcopy(args));two=LayoutRegenerationReasonerV1().regenerate(*deepcopy(args))
    assert one==two

def test_architectural_brain_blocks_physical_geometry_when_regeneration_is_unresolved():
    intent=_architectural_intent(0)
    intent['relationships']=[r('living','space_not_in_program')]
    intent['layout_regeneration']={'enabled':True,'max_attempts':1}
    intelligence=ArchitecturalBrain().design(intent).to_dict()['architectural_intelligence']
    geometry=intelligence['architectural_geometry']
    assert geometry['geometry_status']=='pre_geometry_layout_unresolved'
    assert geometry['physical_walls']==geometry['openings']==geometry['slabs']==[]
