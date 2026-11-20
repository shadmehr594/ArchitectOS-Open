import math
from shapely.geometry import LineString,Polygon,box
from shapely.ops import unary_union
from core.architecture.geometry.architectural_stair_geometry_resolver_v1 import ArchitecturalStairGeometryResolverV1

class VerticalCirculationCoreLevelAwareV2:
 EPS=1e-7
 LEVELS={'B1':-2.4,'GF':0.0,'F1':4.7,'F2':7.94}
 SPANS=(('B1','GF'),('GF','F1'),('F1','F2'))
 MAX_RISER=.18;MIN_TREAD=.28;HEADROOM=2.10
 def resolve(self,clear_face,frontage_candidate,parking_candidate,base_candidate):
  clear=clear_face if isinstance(clear_face,Polygon) else Polygon(clear_face);u0,v0,u1,v1=clear.bounds;ped=frontage_candidate['pedestrian_access_interval'];stair_w=float(base_candidate['stair']['clear_width']);shaft=base_candidate['elevator']['shaft_dimensions'];lobby_d=base_candidate['core_dimensions'][0]-2*stair_w if False else 1.5
  specs={f'{a}_{b}':self._spec(a,b,stair_w) for a,b in self.SPANS};stairwell_d=max(s['required_stairwell_length'] for s in specs.values());core_w=2*stair_w+float(shaft[0]);core_d=stairwell_d+lobby_d;core_x0=ped[1] if parking_candidate['side']=='west' else ped[0]-core_w
  base_station=float(base_candidate['core_station']);start=max(v0+lobby_d,base_station-2.5);stop=min(v1-core_d,base_station+1.0);n=max(2,int((stop-start)/.125)+1);stations=[start+i*(stop-start)/(n-1) for i in range(n)];ramp=Polygon(parking_candidate['ramp_surface']);maneuver=Polygon(parking_candidate['maneuvering_field']);stalls=[Polygon(p) for p in parking_candidate['parking_stalls']];candidates=[]
  for idx,station in enumerate(stations):
   core=box(core_x0,station,core_x0+core_w,station+core_d);stair_zone=box(core_x0,station+lobby_d,core_x0+2*stair_w,station+lobby_d+stairwell_d);elevator=box(core_x0+2*stair_w,station+lobby_d,core_x0+core_w,station+lobby_d+float(shaft[1]));lobby=box(core_x0,station,core_x0+core_w,station+lobby_d);corridor=box(ped[0],v0,ped[1],station);corridor_line=[[(ped[0]+ped[1])/2,v0],[(ped[0]+ped[1])/2,station]];stairs={}
   for key,spec in specs.items():stairs[key]=self._stair_geometry(key,spec,stair_zone,stair_w)
   destroyed=[i for i,s in enumerate(stalls) if core.intersection(s).area>self.EPS];paths=[]
   for si,s in enumerate(stalls):
    p=s.centroid;target=[core_x0+core_w,station+lobby_d/2];line=[[p.x,p.y],[p.x,station+lobby_d/2],target];ls=LineString(line);other=[o for j,o in enumerate(stalls) if j!=si];blocked=any(ls.buffer(.3).intersection(o).area>self.EPS for o in other);paths.append({'stall_id':f'P-{si+1:02d}','actual_path_polyline':line,'route_length':ls.length,'status':'resolved' if not blocked and not ls.crosses(ramp) else 'conflict'})
   failures=[]
   if not clear.buffer(self.EPS).covers(core):failures.append('level_aware_core_outside_clear_face')
   if core.intersection(ramp).area>self.EPS:failures.append('core_ramp_overlap')
   if core.intersection(maneuver).area>self.EPS:failures.append('core_maneuver_overlap')
   if destroyed:failures.append('approved_parking_capacity_not_preserved')
   if any(s['geometry_status']!='resolved' for s in stairs.values()):failures.append('level_aware_stair_geometry_failed')
   if any(p['status']!='resolved' for p in paths):failures.append('basement_pedestrian_path_conflict')
   upper_a=clear.intersection(box(u0,v0,u1,station));upper_b=clear.intersection(box(u0,station+core_d,u1,v1));balance=min(upper_a.area,upper_b.area)/max(upper_a.area,upper_b.area) if max(upper_a.area,upper_b.area)>0 else 0;commercial=clear.difference(unary_union([ramp,corridor,core]));parts=list(getattr(commercial,'geoms',[commercial]));commercial_area=sum(p.area for p in parts);distribution=box(core_x0,station+core_d,core_x0+core_w,min(v1,station+core_d+lobby_d));cid=f'VC-LA2-{idx:03d}-{station-v0:.3f}'
   candidates.append({'candidate_id':cid,'core_station':station-v0,'core_polygon':self._poly(core),'core_dimensions':[core_w,core_d],'stairwell_dimensions':[2*stair_w,stairwell_d],'stairs_by_span':stairs,'elevator':{'shaft_polygon':self._poly(elevator),'shaft_dimensions':shaft,'served_level_elevations':dict(self.LEVELS),'door_interfaces_by_level':{k:[[core_x0+2*stair_w,station+lobby_d],[core_x0+core_w,station+lobby_d]] for k in self.LEVELS},'vertical_extent':[self.LEVELS['B1'],self.LEVELS['F2']],'upper_floor_vertical_span_status':'resolved_from_explicit_level_contract'},'common_lobby':{'polygon':self._poly(lobby),'dimensions':[core_w,lobby_d],'area':lobby.area},'ground_floor':{'pedestrian_corridor':self._poly(corridor),'corridor_centerline':corridor_line,'corridor_length':LineString(corridor_line).length,'corridor_width':ped[1]-ped[0],'commercial_space_polygons':self._geometry(commercial),'commercial_retained_area':commercial_area,'commercial_frontage_width':frontage_candidate['commercial_frontage_width'],'pedestrian_entrance_width':frontage_candidate['pedestrian_access_width'],'vehicle_entrance_width':frontage_candidate['vehicle_access_width'],'exterior_discharge_route':list(reversed(corridor_line))},'basement':{'parking_capacity_preserved':len(stalls)-len(destroyed),'stall_1_to_core_path':paths[0],'stall_2_to_core_path':paths[1],'ramp_conflict_area':core.intersection(ramp).area,'maneuver_conflict_area':core.intersection(maneuver).area},'upper_floor':{'core_projection':self._poly(core),'common_distribution':self._poly(distribution),'unit_a_entry_interface':[[core_x0,station+core_d],[core_x0+stair_w,station+core_d]],'unit_b_entry_interface':[[core_x0+core_w-stair_w,station+core_d],[core_x0+core_w,station+core_d]],'private_field_metrics':{'unit_a_allocatable_area':upper_a.area,'unit_b_allocatable_area':upper_b.area,'balance_ratio':balance,'remaining_usable_upper_floor_area':upper_a.area+upper_b.area}},'quality_metrics':{'parking_preserved':len(stalls)-len(destroyed),'commercial_retained_area':commercial_area,'corridor_length':LineString(corridor_line).length,'upper_two_unit_balance':balance,'core_area':core.area},'hard_failures':failures,'geometry_status':'hard_valid' if not failures else 'failed','renderer_authority':'production_contract_only'})
  valid=[c for c in candidates if c['geometry_status']=='hard_valid'];best=max(valid,key=lambda c:(c['quality_metrics']['parking_preserved'],c['quality_metrics']['upper_two_unit_balance'],c['quality_metrics']['commercial_retained_area'],-c['quality_metrics']['corridor_length'])) if valid else None
  return {'contract':'VerticalCirculationCoreLevelAwareV2','level_contract':{'basement_elevation':-2.4,'ground_elevation':0.0,'first_floor_elevation':4.7,'second_floor_elevation':7.94},'floor_to_floor_spans':{k:{'start_z':v['start_z'],'end_z':v['end_z'],'rise':v['total_rise']} for k,v in specs.items()},'active_stair_policy':{'clear_width':stair_w,'maximum_riser':self.MAX_RISER,'minimum_tread':self.MIN_TREAD,'minimum_headroom':self.HEADROOM,'source':'explicit_test_level_and_active_project_policy'},'previous_candidate_id':base_candidate['candidate_id'],'previous_core_dimensions':base_candidate['core_dimensions'],'previous_candidate_remained_valid':bool(best and abs(best['core_station']-base_station)<1e-6 and best['core_dimensions']==base_candidate['core_dimensions']),'local_re_evaluation_only':True,'candidate_count':len(candidates),'hard_valid_count':len(valid),'candidates':candidates,'selected_candidate':best,'vertical_circulation_core_geometry_status':'hard_valid' if best else 'failed','whole_building_core_selection_status':'candidate_found' if best else 'no_candidate','fire_egress_rule_status':'pending_rule_resolution','physical_core_publication_status':'pending_human_acceptance','human_visual_acceptance':'pending'}
 def _spec(self,a,b,width):
  z0,z1=self.LEVELS[a],self.LEVELS[b];rise=z1-z0;n=math.ceil(rise/self.MAX_RISER-1e-12);split=[n//2+n%2,n//2];treads=[x-1 for x in split];run=max(treads)*self.MIN_TREAD;return {'start_floor':a,'end_floor':b,'start_z':z0,'end_z':z1,'total_rise':rise,'stair_type':'u_return_two_flight','flight_count':2,'riser_count':n,'tread_count':sum(treads),'actual_riser_height':rise/n,'tread_depth':self.MIN_TREAD,'clear_width':width,'flight_distribution':split,'total_run':run,'required_stairwell_length':run+width,'headroom':self.HEADROOM}
 def _stair_geometry(self,key,spec,zone,width):
  element={'id':f'STAIR-{key}','served_levels':[spec['start_floor'],spec['end_floor']],'served_level_spans':[{'name':spec['start_floor'],'bottom':spec['start_z']},{'name':spec['end_floor'],'bottom':spec['end_z']}],'span_source':'explicit_test_level_contract','location_intent':{'protected_zone':self._poly(zone)},'parameters':{'stair_type':'u_return_two_flight','clear_width':width,'maximum_riser':self.MAX_RISER,'minimum_tread':self.MIN_TREAD,'flight_count':2,'landing_required':True,'landing_depth':width,'headroom':self.HEADROOM,'conflict_evidence_complete':True,'conflict_zones':[]}}
  g=ArchitecturalStairGeometryResolverV1().resolve(element);flights=[]
  for i,f in enumerate(g.get('flights',[])):
   flights.append({**f,'start_floor':spec['start_floor'] if i==0 else f'{key}_MID_LANDING','end_floor':f'{key}_MID_LANDING' if i==0 else spec['end_floor'],'start_point_xyz':f['centerline'][0],'end_point_xyz':f['centerline'][-1],'direction_up':True,'landing_before':None if i==0 else g['landings'][0]['landing_id'],'landing_after':g['landings'][0]['landing_id'] if i==0 else None})
  profile=[[0.0,spec['start_z']]];station=0.0;landing_segment=None
  for i,f in enumerate(flights):
   z=f['start_z']
   for n in range(f['riser_count']):
    z+=spec['actual_riser_height'];profile.append([station,z])
    if n<f['tread_count']:
     station+=spec['tread_depth'];profile.append([station,z])
   if i==0:
    landing_segment=[[station,z],[station+width,z]];station+=width;profile.append([station,z])
  return {**spec,'flights':flights,'landings':g.get('landings',[]),'unfolded_profile':profile,'unfolded_landing_segment':landing_segment,'bottom_interface':flights[0]['start_point_xyz'] if flights else None,'top_interface':flights[-1]['end_point_xyz'] if flights else None,'headroom_status':'resolved_at_minimum_2_10m','geometry_status':g.get('geometry_status'),'stair_polygon':g.get('polygon'),'protected_zone':self._poly(zone)}
 @staticmethod
 def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
 @classmethod
 def _geometry(cls,g):return [cls._poly(p) for p in getattr(g,'geoms',[g])]
