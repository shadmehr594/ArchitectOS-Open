import pytest
from core.architecture.reasoning.opening_reasoner_v2 import OpeningReasonerV2
from core.architecture.geometry.architectural_physical_opening_resolver_v1 import ArchitecturalPhysicalOpeningResolverV1
from core.architecture.reasoning.architectural_spatial_quality_gate_v1 import ArchitecturalSpatialQualityGateV1
from core.export.dwg.dwg_writer import DWGWriter

def wall(i='W1', spaces=('living','dining'), start=(2,0), end=(2,4)):
    return {'wall_id':i,'floor':'F1','start':list(start),'end':list(end),'spaces':list(spaces),'is_exterior':False,'thickness':.15}
def conn(i='C1',a='living',b='dining',point=(2,2),**k):
    value={'connection_id':i,'from_space_id':a,'to_space_id':b,'from':a,'to':b,'from_floor':'F1','to_floor':'F1',
           'required':True,'door_required':True,'privacy_class':None,'circulation_role':'internal',
           'shared_boundary':{'start':[2,0],'end':[2,4]},'required_clear_width':1.0,'required_clear_height':2.1,
           'preferred_opening_point':list(point) if point else None,'geometry_status':'resolved_shared_boundary','evidence_status':'authoritative'}
    value.update(k);return value
def resolve(c,w=None,existing=None):
    w=w or [wall()]; intents=OpeningReasonerV2().resolve_connections(c,w,existing or [])
    openings,walls=ArchitecturalPhysicalOpeningResolverV1().resolve(intents,w);return intents,openings,walls

@pytest.mark.parametrize('a,b,privacy',[
 ('living','dining',None),('dining','kitchen','service'),('bedroom','corridor','private'),('bathroom','corridor','privacy_controlled')])
def test_required_connection_roles_resolve_one_physical_interior_door(a,b,privacy):
    c=conn(a+'-'+b,a,b,privacy_class=privacy);w=[wall('W', (a,b))]
    _,o,walls=resolve([c],w)
    assert len(o)==1 and o[0]['geometry_status']=='resolved' and o[0]['host_wall_id']=='W'
    assert len(walls[0]['solid_segments'])==2
def test_bathroom_living_privacy_violation_is_not_feasible():
    i=OpeningReasonerV2().resolve_connections([conn('P','bathroom','living',privacy_violation=True)],[wall('W',('bathroom','living'))])
    assert i[0]['opening_resolution_status']=='not_feasible_privacy_violation'
def test_spaces_without_relation_produce_no_door():
    assert OpeningReasonerV2().resolve_connections([], [wall()])==[]
def test_semantic_only_relation_without_door_requirement_produces_no_door():
    c=conn();c.update(required=False,door_required=False,geometry_status='semantic_only')
    assert OpeningReasonerV2().resolve_connections([c],[wall()])==[]
def test_missing_shared_boundary_remains_pending():
    c=conn();c['geometry_status']='unresolved';c['shared_boundary']=None
    assert OpeningReasonerV2().resolve_connections([c],[wall()])[0]['opening_resolution_status']=='shared_boundary_pending'
def test_two_matching_physical_walls_remain_pending_multiple_hosts():
    i=OpeningReasonerV2().resolve_connections([conn()],[wall('W1'),wall('W2')])
    assert i[0]['opening_resolution_status']=='pending_multiple_hosts'
def test_two_equal_explicit_placement_points_remain_pending_tie():
    c=conn(point=None,opening_point_candidates=[[2,1],[2,3]])
    assert OpeningReasonerV2().resolve_connections([c],[wall()])[0]['opening_resolution_status']=='pending_tie'
def test_overlap_with_existing_opening_is_rejected():
    existing=[{'id':'D0','geometry_status':'resolved','host_wall_id':'W1','opening_center':[2,2],'resolved_width':1.0}]
    assert OpeningReasonerV2().resolve_connections([conn()],[wall()],existing)[0]['opening_resolution_status']=='not_feasible_opening_overlap'
def test_resolved_opening_segment_cannot_cross_protected_zone():
    zone={'polygon':[[1.8,1.5],[2.2,1.5],[2.2,2.5],[1.8,2.5]]}
    i=OpeningReasonerV2().resolve_connections([conn()],[wall()],[],[zone])
    assert i[0]['opening_resolution_status']=='not_feasible_protected_zone'
def test_explicit_wall_end_clearance_is_enforced_by_physical_resolver():
    _,o,_=resolve([conn(point=(2,.5),end_clearance=0.4)])
    assert o[0]['geometry_status']=='pending'
def test_duplicate_connection_creates_only_one_intent_and_one_door():
    c=conn();_,o,_=resolve([c,dict(c)])
    assert len(o)==1
def test_resolved_door_updates_connection_evidence_shape():
    _,o,_=resolve([conn()]);opening=o[0];c=conn()
    c.update(opening_id=opening['opening_id'],host_wall_id=opening['host_wall_id'],opening_center=opening['opening_center'],opening_geometry_status='resolved',physical_connection_status='resolved')
    assert c['opening_id']=='INTERIOR-C1' and c['physical_connection_status']=='resolved'
def test_door_required_without_physical_door_fails_quality_gate():
    c=conn();c['physical_connection_status']='pending'
    g={'spaces':[{'name':'living'},{'name':'dining'}],'connections':[c],'openings':[]}
    q=ArchitecturalSpatialQualityGateV1().evaluate(g,{'enforce':True,'required_connections':[['living','dining']]})
    assert q['status']=='rejected'
def test_unresolved_door_is_not_publishable_by_cad_writer():
    _,o,w=resolve([conn(point=None)])
    assert o[0]['geometry_status']=='pending' and DWGWriter().resolve_opening_symbol(o[0],{'W1':w[0]}) is None
def test_deterministic_repeat_is_identical():
    reasoner=OpeningReasonerV2();a=reasoner.resolve_connections([conn()],[wall()]);b=reasoner.resolve_connections([conn()],[wall()])
    assert a==b
