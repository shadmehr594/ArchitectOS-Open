import pytest
from core.architecture.reasoning.opening_reasoner_v2 import OpeningReasonerV2
from core.architecture.geometry.architectural_physical_opening_resolver_v1 import ArchitecturalPhysicalOpeningResolverV1
from core.architecture.reasoning.architectural_spatial_quality_gate_v1 import ArchitecturalSpatialQualityGateV1
from core.export.dwg.dwg_writer import DWGWriter

def space(name='living',floor='F1'):return {'id':name,'name':name,'floor':floor,'privacy_level':'private' if name in ('bedroom','bathroom') else 'public'}
def wall(i='W1',room='living',exterior=True,start=(0,0),end=(6,0)):return {'wall_id':i,'floor':'F1','start':list(start),'end':list(end),'spaces':[room],'is_exterior':exterior,'height':3.0,'thickness':.3}
def req(i='WIN1',room='living',point=(3,0),**k):
    x={'window_id':i,'space_id':room,'floor':'F1','required':True,'width':1.5,'height':1.2,'sill_height':.9,
       'preferred_opening_point':list(point) if point else None,'source':'project_requirement','evidence_status':'authoritative'};x.update(k);return x
def pipeline(room='living',walls=None,requirements=None,existing=None,zones=None):
    reasoner=OpeningReasonerV2();walls=walls or [wall(room=room)];exp=reasoner.resolve_exterior_exposure([space(room)],walls)
    intents=reasoner.resolve_windows(exp,requirements or [req(room=room)],walls,existing or [],zones or [])
    openings,resolved_walls=ArchitecturalPhysicalOpeningResolverV1().resolve(intents,walls)
    return exp,intents,openings,resolved_walls

def test_exterior_living_window_resolves():
    e,i,o,w=pipeline();assert e[0]['exterior_exposure_status']=='resolved' and o[0]['geometry_status']=='resolved'
def test_interior_only_room_has_no_physical_window():
    _,i,o,_=pipeline(walls=[wall(exterior=False)]);assert i[0]['window_resolution_status']=='forbidden_interior_only' and o[0]['geometry_status']=='pending'
def test_bedroom_exterior_window_is_valid():
    assert pipeline('bedroom',requirements=[req(room='bedroom')])[2][0]['geometry_status']=='resolved'
def test_bathroom_privacy_metadata_is_preserved_when_valid():
    _,i,o,_=pipeline('bathroom',requirements=[req(room='bathroom',privacy_control='obscure')]);assert i[0]['privacy_status']=='resolved_from_requirement' and o[0]['geometry_status']=='resolved'
def test_missing_room_exposure_remains_pending():
    i=OpeningReasonerV2().resolve_windows([], [req()], [wall()]);assert i[0]['window_resolution_status']=='exterior_exposure_pending'
def test_interior_wall_candidate_is_rejected():
    assert pipeline(walls=[wall(exterior=False)])[2][0]['geometry_status']=='pending'
def test_multiple_exterior_hosts_remain_pending():
    walls=[wall('W1'),wall('W2',start=(0,0),end=(6,0))];_,i,o,_=pipeline(walls=walls);assert i[0]['window_resolution_status']=='pending_multiple_hosts'
def test_multiple_equal_points_remain_pending_tie():
    _,i,o,_=pipeline(requirements=[req(point=None,opening_point_candidates=[[2,0],[4,0]])]);assert i[0]['window_resolution_status']=='pending_tie'
def test_window_overlap_with_door_is_rejected():
    door={'id':'D','geometry_status':'resolved','host_wall_id':'W1','opening_center':[3,0],'resolved_width':1.0}
    _,i,_,_=pipeline(existing=[door]);assert i[0]['window_resolution_status']=='not_feasible_opening_overlap'
def test_explicit_corner_clearance_is_enforced():
    _,_,o,_=pipeline(requirements=[req(point=(.75,0),end_clearance=.5)]);assert o[0]['geometry_status']=='pending'
def test_protected_zone_conflict_is_rejected():
    zone={'polygon':[[2.5,-1],[3.5,-1],[3.5,1],[2.5,1]]};_,i,_,_=pipeline(zones=[zone]);assert i[0]['window_resolution_status']=='not_feasible_protected_zone'
def test_duplicate_window_requirement_creates_one_opening():
    q=req();_,_,o,_=pipeline(requirements=[q,dict(q)]);assert len(o)==1
def test_resolved_window_interrupts_wall_solid_segments():
    *_,walls=pipeline();assert len(walls[0]['solid_segments'])==2 and walls[0]['physical_openings'][0]['type']=='window'
def test_unresolved_window_is_not_published_to_cad():
    _,_,o,w=pipeline(requirements=[req(point=None)]);assert DWGWriter().resolve_opening_symbol(o[0],{'W1':w[0]}) is None
def test_window_host_must_belong_to_served_room():
    exposure={'space_id':'living','floor':'F1','exterior_exposure_status':'resolved','exterior_wall_ids':['W1']}
    i=OpeningReasonerV2().resolve_windows([exposure],[req()],[wall(room='bedroom')]);assert i[0]['window_resolution_status']=='no_usable_exterior_host'
def test_room_name_typology_alone_cannot_create_physical_window():
    intent=OpeningReasonerV2().resolve(space('living'),{'floor':'F1'})['openings'][0];intent.update(space='living',floor='F1',host_wall_id='W1')
    o,_=ArchitecturalPhysicalOpeningResolverV1().resolve([intent],[wall()]);assert o[0]['geometry_status']=='pending'
def test_required_window_updates_quality_failure_when_unresolved():
    g={'spaces':[space()],'physical_walls':[wall()],'openings':[],'project_requirements':{'window_requirements':[req()]}}
    q=ArchitecturalSpatialQualityGateV1().evaluate(g,{'enforce':True,'isolation_exempt_spaces':['living']});assert q['status']=='rejected'
def test_deterministic_repeat():
    a=pipeline()[1];b=pipeline()[1];assert a==b
