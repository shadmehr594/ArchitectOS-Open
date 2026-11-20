"""Two-unit residential access/daylight skeleton; no room planning."""
from copy import deepcopy
from math import hypot
from shapely.geometry import LineString,Point,Polygon,box
from shapely.ops import transform,unary_union
from core.architecture.reasoning.minab_residential_architectural_rules_v1 import MinabResidentialArchitecturalRulesV1
from core.architecture.reasoning.zoning_and_buildability_context_v1 import ZoningAndBuildabilityContextV1
from core.architecture.reasoning.stair_endpoint_intelligence_v1 import StairEndpointIntelligenceV1
from core.architecture.reasoning.elevator_lobby_clearance_intelligence_v1 import ElevatorLobbyClearanceIntelligenceV1
from core.architecture.reasoning.residential_private_terrace_topology_v1 import ResidentialPrivateTerraceTopologyV1

class ResidentialFloorAccessAndDaylightTopologyV1:
 FAMILIES=("R-EW","R-NS","R-HYBRID");LIGHTWELLS=("LIGHTWELL-L01","LIGHTWELL-L02","LIGHTWELL-L03","LIGHTWELL-L04","LIGHTWELL-L05");EPS=1e-5
 def resolve(self,site,baseline_scenario_a,pilot_reference,case_definition=None):
  before_site,before_a,before_p=deepcopy(site),deepcopy(baseline_scenario_a),deepcopy(pilot_reference)
  rules=MinabResidentialArchitecturalRulesV1().resolve();zoning=ZoningAndBuildabilityContextV1().resolve(site,case_definition or {})
  frame=self._frame(site["parcel"],site["frontage"]);parcel=self._to_local(Polygon(site["parcel"]),frame)
  core={k:Polygon(v) if isinstance(v,list) else v for k,v in pilot_reference["geometry"]["core"].items() if k in ("polygon","stair","elevator","lobby")}
  candidates=[self._candidate(f,l,parcel,core,rules,pilot_reference) for f in self.FAMILIES for l in self.LIGHTWELLS]
  valid=[c for c in candidates if c["hard_validation_status"]=="hard_valid"]
  review=[]
  for family in self.FAMILIES:review+=sorted([c for c in valid if c["split_family"]==family],key=self._rank,reverse=True)[:2]
  assert site==before_site and baseline_scenario_a==before_a and pilot_reference==before_p
  return {"contract":"ResidentialFloorAccessAndDaylightTopologyV1","site":"REAL Parcel 2","site_source":site.get("source"),
   "source_parcel":site["parcel"],"source_frontage":site["frontage"],"source_road_width":site.get("road_width"),"local_parcel_polygon":self._poly(parcel),
   "zoning_context":zoning,"minab_rules":rules,"pilot_core_reference_status":"unselected_scenario_b_reference",
   "pilot_core_reference_candidate_id":pilot_reference["candidate_id"],"families_explored":list(self.FAMILIES),"lightwell_families_explored":list(self.LIGHTWELLS),
   "candidate_count":len(candidates),"hard_valid_candidate_count":len(valid),"candidates":candidates,"human_review_candidates":review,
   "human_review_candidate_ids":[c["candidate_id"] for c in review],"final_selection_performed":False,"final_residential_topology":None,
   "room_layout_generated":False,"bedroom_polygons":[],"living_polygons":[],"kitchen_polygons":[],"bathroom_polygons":[],
   "baseline_scenario_a":before_a,"baseline_geometry_preserved":True,"program_changed":False,"basement_deleted":False,"basement_removal_approved":False,
   "structure_executed":False,"bim_executed":False,"ifc_executed":False,"render_pipeline_executed":False}
 def _candidate(self,family,lid,parcel,core,rules,pilot):
  x0,y0,x1,y1=parcel.bounds;lw=self._lightwell(lid,parcel);obstacles=unary_union([core["polygon"],lw]);base=self._units(family,parcel)
  units=[u.difference(obstacles) for u in base];terraces=[]
  for i,u in enumerate(units):
   mode="internal_lightwell_adjacent" if family=="R-NS" and i==1 else "south_recessed"
   t=ResidentialPrivateTerraceTopologyV1().resolve(f"UNIT-{i+1}",self._poly_largest(u),mode,[[x0,y0],[x1,y0]],self._poly(lw),i+1);terraces.append(t)
   if t["terrace_polygon"]:units[i]=u.difference(Polygon(t["terrace_polygon"]))
  lobby=core["lobby"];elev=ElevatorLobbyClearanceIntelligenceV1().resolve(self._poly(core["elevator"]),self._poly(lobby))
  entries=[self._entry(lobby,u) for u in units];paths=[LineString([lobby.centroid,Point(e)]) for e in entries]
  common=unary_union([lobby]+[p.buffer(.6,cap_style=2) for p in paths]);stair=StairEndpointIntelligenceV1().resolve(self._poly(core["stair"]),self._poly(lobby),[self._poly_largest(u) for u in units],elev["elevator_front_clear_zone"])
  metrics=[self._unit_metrics(u,parcel,lw) for u in units];fail=[]
  if not parcel.buffer(self.EPS).covers(unary_union([lw,core["polygon"]]+[u for u in units])):fail.append("parcel_boundary_violation")
  if core["polygon"].intersection(lw).area>self.EPS:fail.append("core_lightwell_collision")
  if lw.area+1e-6<12:fail.append("lightwell_area_below_authoritative_minimum")
  if min(lw.bounds[2]-lw.bounds[0],lw.bounds[3]-lw.bounds[1])+1e-6<3:fail.append("lightwell_width_below_authoritative_minimum")
  if any(u.is_empty or not u.is_valid or u.geom_type not in ("Polygon","MultiPolygon") for u in units):fail.append("disconnected_unit_envelope")
  if any(t["terrace_area"]<=self.EPS for t in terraces):fail.append("missing_required_private_terrace")
  if any(t["terrace_open_edge"] in ("north_private_neighbor","west_private_neighbor") for t in terraces):fail.append("terrace_toward_private_neighbor")
  if stair["stair_arrival_status"]!="resolved":fail.append("stair_arrival_inaccessible")
  penalties=[]
  for i,m in enumerate(metrics):
   if m["corridor_likeness_score"]>.62:penalties.append(f"unit_{i+1}_corridor_like")
   if m["aspect_ratio"]>3:penalties.append(f"unit_{i+1}_excessive_depth")
   if m["external_daylight_edge_length"]+m["lightwell_daylight_edge_length"]<=self.EPS:penalties.append(f"unit_{i+1}_daylight_depth_risk")
  balance=min(m["unit_area"] for m in metrics)/max(m["unit_area"] for m in metrics)
  south=[m["frontage_length"] for m in metrics];lightstatus="credible_future_daylight_edges_reserved" if all(m["external_daylight_edge_length"]+m["lightwell_daylight_edge_length"]>0 for m in metrics) else "unresolved"
  return {"contract":"ResidentialFloorAccessAndDaylightCandidateV1","candidate_id":f"{family}-{lid}","split_family":family,
   "east_west_or_north_south_or_hybrid":{"R-EW":"east_west","R-NS":"north_south","R-HYBRID":"hybrid_interlocking"}[family],
   "unit_envelopes":[{"unit_id":f"UNIT-{i+1}","polygon":self._poly_largest(u),"entry_point":entries[i],"entry_transition_polygon":self._poly(paths[i].buffer(.6,cap_style=2)),
    "zoning_transition":["COMMON","SEMI_PRIVATE","PRIVATE"],"main_space_future_daylight_status":"opening_edges_reserved_not_rooms_generated",
    "external_daylight_edge":"south_public_frontage" if metrics[i]["frontage_length"] else None,"lightwell_daylight_edge":"central_lightwell","blocked_neighbor_edges":["north","west"],"metrics":metrics[i]} for i,u in enumerate(units)],
   "unit_1_area":metrics[0]["unit_area"],"unit_2_area":metrics[1]["unit_area"],"unit_area_balance_ratio":balance,
   "common_lobby_polygon":self._poly(lobby),"common_lobby_area":lobby.area,"common_corridor_polygon":self._poly_largest(common),"common_corridor_area":common.area,
   "common_access_paths":[self._line(p) for p in paths],"common_access_length":sum(p.length for p in paths),"common_corridor_termination_status":"terminates_at_last_unit_entry",
   "stair":stair,"elevator":{**elev,"polygon":self._poly(core["elevator"])},"pilot_core_xy":self._poly(core["polygon"]),"residential_core_xy":self._poly(core["polygon"]),
   "stair_vertical_alignment_status":"aligned_to_pilot_reference","elevator_vertical_alignment_status":"aligned_to_pilot_reference","pilot_residential_core_tradeoff_detected":bool(penalties),
   "lightwell":{"lightwell_id":lid,"polygon":self._poly(lw),"area":lw.area,"minimum_width":min(lw.bounds[2]-lw.bounds[0],lw.bounds[3]-lw.bounds[1]),
    "rule_status":rules["rules"]["main_space_lightwell_min_area"]["rule_status"],"natural_airflow_required":True,"object_type":"daylight_ventilation_open_space_not_terrace"},
   "terraces":terraces,"unit_1_terrace_status":terraces[0]["access_from_unit_status"],"unit_1_terrace_area":terraces[0]["terrace_area"],
   "unit_2_terrace_status":terraces[1]["access_from_unit_status"],"unit_2_terrace_area":terraces[1]["terrace_area"],
   "south_frontage_distribution":{"south_frontage_total":x1-x0,"south_frontage_unit_1":south[0],"south_frontage_unit_2":south[1],"south_frontage_common_core":0,
    "south_frontage_terrace_1":terraces[0]["terrace_width"] if terraces[0]["terrace_orientation"]=="south" else 0,"south_frontage_terrace_2":terraces[1]["terrace_width"] if terraces[1]["terrace_orientation"]=="south" else 0},
   "north_edge_opening_status":"forbidden_adjacent_private_parcel","west_edge_opening_status":"forbidden_adjacent_private_parcel",
   "daylight_topology_status":lightstatus,"privacy_status":"neighbor_edges_blocked_opposing_lightwell_openings_pending_detailed_window_design",
   "opposite_unit_opening_relationship":{"status":"opening_edges_reserved_no_windows_generated","minimum_distance_rule":3.0,"applies_if":"opposing_independent_unit_windows_are_later_generated"},
   "architectural_quality_penalties":penalties,"hard_rejection_reasons":fail,"hard_validation_status":"hard_valid" if not fail else "not_feasible",
   "future_room_planning_potential":"credible" if lightstatus.startswith("credible") and balance>.55 else "constrained",
   "residential_net_efficiency":sum(m["unit_area"] for m in metrics)/parcel.area,"room_polygons_generated":False}
 def _lightwell(self,lid,p):
  x0,y0,x1,y1=p.bounds;spec={"LIGHTWELL-L01":((x0+x1)/2-1.5,11,3,4),"LIGHTWELL-L02":(x0+1,10.5,3,4),"LIGHTWELL-L03":((x0+x1)/2-1.5,14.5,3,4),"LIGHTWELL-L04":(x0+2.5,6,3,4),"LIGHTWELL-L05":(x0+1.5,12,3,4)}[lid];return box(spec[0],spec[1],spec[0]+spec[2],spec[1]+spec[3])
 def _units(self,f,p):
  x0,y0,x1,y1=p.bounds
  if f=="R-EW":return [box(x0,y0,(x0+x1)/2,y1),box((x0+x1)/2,y0,x1,y1)]
  if f=="R-NS":return [box(x0,y0,x1,10.5),box(x0,10.5,x1,y1)]
  a=Polygon([(x0,y0),(x0+4,y0),(x0+4,10),(x0+6,10),(x0+6,y1),(x0,y1)]);return [a,p.difference(a)]
 def _unit_metrics(self,u,p,lw):
  q=self._largest(u);x0,y0,x1,y1=q.bounds;w=x1-x0;d=y1-y0;aspect=max(w,d)/max(min(w,d),self.EPS);front=q.boundary.intersection(LineString([(p.bounds[0],p.bounds[1]),(p.bounds[2],p.bounds[1])])).length;le=q.boundary.intersection(lw.boundary).length
  return {"unit_area":u.area,"bounding_width":w,"bounding_depth":d,"minimum_effective_width":min(w,d),"maximum_depth":max(w,d),"aspect_ratio":aspect,
   "compactness":4*3.1415926535*u.area/(u.length*u.length) if u.length else 0,"convexity":u.area/u.convex_hull.area if u.convex_hull.area else 0,
   "largest_usable_rectangle":self._poly(box(x0,y0,x1,y1).intersection(q).envelope),"frontage_length":front,"external_daylight_edge_length":front,
   "lightwell_daylight_edge_length":le,"terrace_access_edge_length":0,"narrow_neck":min(w,d)<2.4,"rear_tail":d>3*w,"fragmentation":u.geom_type=="MultiPolygon",
   "corridor_likeness_score":min(1,max(0,(aspect-1)/4)),"usable_depth_quality":"poor" if aspect>3 else "moderate_or_better"}
 def _entry(self,lobby,u):
  q=self._largest(u);a,b=lobby.exterior.interpolate(lobby.exterior.project(q.centroid)),q.exterior.interpolate(q.exterior.project(lobby.centroid));return [b.x,b.y]
 @staticmethod
 def _largest(g):return max(g.geoms,key=lambda x:x.area) if g.geom_type=="MultiPolygon" else g
 def _poly_largest(self,g):return self._poly(self._largest(g))
 @staticmethod
 def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
 @staticmethod
 def _line(p):return [[float(x),float(y)] for x,y in p.coords]
 @staticmethod
 def _rank(c):return (-len(c["architectural_quality_penalties"]),c["unit_area_balance_ratio"],c["residential_net_efficiency"],-c["common_access_length"])
 @staticmethod
 def _frame(parcel,frontage):
  a,b=frontage;l=hypot(b[0]-a[0],b[1]-a[1]);ux,uy=(b[0]-a[0])/l,(b[1]-a[1])/l;nx,ny=-uy,ux;cen=Polygon(parcel).centroid
  if (cen.x-a[0])*nx+(cen.y-a[1])*ny<0:nx,ny=-nx,-ny
  return a[0],a[1],ux,uy,nx,ny
 @staticmethod
 def _to_local(g,f):
  ox,oy,ux,uy,nx,ny=f;return transform(lambda x,y,z=None:((x-ox)*ux+(y-oy)*uy,(x-ox)*nx+(y-oy)*ny),g)
