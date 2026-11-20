from core.architecture.geometry.parking_pedestrian_connection_resolver_v1 import ParkingPedestrianConnectionResolverV1

def arrival(point=(0,0)):return {'served_level':'basement','entry_interface':'vehicle-opening','arrival_point':list(point),'geometry_status':'resolved'}
def layout(stalls=None):return {'geometry_status':'resolved','parking_aisle':{'aisle_id':'A1','polygon':[[-1,-1],[6,-1],[6,-2],[-1,-2]]},'parking_stalls':stalls or []}
def stair(i='S1'):return {'type':'stair_geometry','stair_id':i,'geometry_status':'resolved','served_levels':['basement','F1']}
def req(dest=(5,0),**k):
    x={'connection_id':'PP1','served_level':'basement','required_clear_width':1.0,'evidence_status':'authoritative','destination_interfaces':[{'point':list(dest),'floor':'basement','circulation_space_id':'basement_corridor','stair_core_id':'S1','interface_status':'resolved','stair_interface_status':'resolved','target_zone_id':'S1'}]};x.update(k);return x
def resolve(requirement=None,**k):return ParkingPedestrianConnectionResolverV1().resolve(arrival(),layout(),requirement or req(),vertical=[stair()],**k)
def zone(i,poly,t='protected'):return {'id':i,'type':t,'polygon':poly}

def test_parking_arrival_to_stair_path_resolved():assert resolve()['geometry_status']=='resolved'
def test_path_through_ramp_clearance_rejected():
    z=zone('ramp-clearance',[[2,-1],[3,-1],[3,1],[2,1]],'vehicle_vertical_clearance');assert resolve(vehicle_zones=[z])['geometry_status']=='unresolved_no_safe_path'
def test_path_through_stall_rejected():
    s={'stall_id':'P1','polygon':[[2,-1],[3,-1],[3,1],[2,1]],'aisle_access':True};r=ParkingPedestrianConnectionResolverV1().resolve(arrival(),layout([s]),req(),vertical=[stair()]);assert r['geometry_status']=='unresolved_no_safe_path'
def test_path_through_wall_without_opening_rejected():
    w={'wall_id':'W','floor':'basement','start':[2,-2],'end':[2,2]};assert resolve(walls=[w])['geometry_status']=='unresolved_no_safe_path'
def test_missing_clear_width_pending():
    q=req();q.pop('required_clear_width');assert resolve(q)['geometry_status']=='pending'
def test_two_equal_destinations_pending_tie():
    q=req();q['destination_interfaces']=[dict(q['destination_interfaces'][0],point=[5,1]),dict(q['destination_interfaces'][0],point=[5,-1])];assert resolve(q)['geometry_status']=='pending_tie'
def test_no_safe_path_explicit():
    z=zone('block',[[1,-2],[4,-2],[4,2],[1,2]]);assert resolve(protected_zones=[z])['geometry_status']=='unresolved_no_safe_path'
def test_direct_clear_path_resolved():assert resolve()['path_centerline']==[[0.0,0.0],[5.0,0.0]]
def test_orthogonal_two_segment_path_resolved_when_direct_blocked():
    q=req((5,2),orthogonal_paths_allowed=True);z=zone('block',[[2,-.3],[3,-.3],[3,.8],[2,.8]]);r=resolve(q,protected_zones=[z]);assert r['geometry_status']=='resolved' and len(r['path_centerline'])==3
def test_uncontrolled_vehicle_crossing_rejected():
    z=zone('driveway',[[2,-1],[3,-1],[3,1],[2,1]],'vehicle_driveway');assert resolve(vehicle_zones=[z])['geometry_status']=='unresolved_no_safe_path'
def test_controlled_crossing_requires_explicit_policy():
    z=zone('driveway',[[2,-1],[3,-1],[3,1],[2,1]],'vehicle_driveway');q=req(crossing_policy={'allowed_zone_ids':['driveway']});assert resolve(q,vehicle_zones=[z])['geometry_status']=='resolved'
def test_physical_wall_opening_required_and_consumed():
    w={'wall_id':'W','floor':'basement','start':[2,-2],'end':[2,2]};o={'id':'D','opening_id':'D','host_wall_id':'W','geometry_status':'resolved','opening_start':[2,-.6],'opening_end':[2,.6]};r=resolve(walls=[w],openings=[o]);assert r['geometry_status']=='resolved' and r['physical_opening_ids']==['D']
def test_stair_geometry_without_resolved_interface_is_unresolved():
    q=req();q['destination_interfaces'][0]['stair_interface_status']='pending';assert resolve(q)['geometry_status']=='pending'
def test_full_parking_circulation_stair_chain_resolved():
    r=resolve();assert r['parking_to_building_status']=='resolved' and r['vertical_connection_status']=='resolved'
def test_path_does_not_block_stall_access():
    s={'stall_id':'P1','polygon':[[2,2],[3,2],[3,4],[2,4]],'aisle_access':True};r=ParkingPedestrianConnectionResolverV1().resolve(arrival(),layout([s]),req(),vertical=[stair()]);assert r['stall_conflict_status']=='clear'
def test_deterministic_repeat():assert resolve()==resolve()
def test_south_geometry_supported_connection_resolves():
    q=req((7,5),pedestrian_origin=[15,7.5]);r=ParkingPedestrianConnectionResolverV1().resolve(arrival((15,7.5)),layout(),q,vertical=[stair()]);assert r['geometry_status']=='resolved'
def test_north_geometry_supported_connection_resolves():
    q=req((12,20),pedestrian_origin=[10,22.5]);r=ParkingPedestrianConnectionResolverV1().resolve(arrival((10,22.5)),layout(),q,vertical=[stair()]);assert r['geometry_status']=='resolved'
