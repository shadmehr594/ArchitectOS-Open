"""Shared-court, access-graph and conditional-projection residential search."""
from copy import deepcopy
from shapely.geometry import Polygon
from core.architecture.reasoning.residential_floor_access_and_daylight_topology_v1 import ResidentialFloorAccessAndDaylightTopologyV1
from core.architecture.reasoning.shared_residential_daylight_court_intelligence_v1 import SharedResidentialDaylightCourtIntelligenceV1
from core.architecture.reasoning.shared_daylight_court_maintenance_access_v1 import SharedDaylightCourtMaintenanceAccessV1
from core.architecture.reasoning.shared_court_privacy_topology_v1 import SharedCourtPrivacyTopologyV1
from core.architecture.reasoning.daylight_court_vertical_extent_intelligence_v1 import DaylightCourtVerticalExtentIntelligenceV1
from core.architecture.reasoning.projection_and_overhang_opportunity_intelligence_v1 import ProjectionAndOverhangOpportunityIntelligenceV1
from core.architecture.reasoning.residential_common_access_graph_v1 import ResidentialCommonAccessGraphV1

class ResidentialFloorAccessDaylightTopologyV2:
 def resolve(self,site,baseline_scenario_a,pilot_reference,case_definition=None,preferences=None):
  before=deepcopy((site,baseline_scenario_a,pilot_reference));prefs={"allow_public_road_projection":True,"allow_internal_property_projection":False,"prefer_projection_for_terrace":False,"prefer_projection_for_unit_area":False,"prefer_no_projection":False};prefs.update(preferences or {})
  base=ResidentialFloorAccessAndDaylightTopologyV1().resolve(site,baseline_scenario_a,pilot_reference,case_definition)
  rules=base["minab_rules"];projection=ProjectionAndOverhangOpportunityIntelligenceV1().resolve((case_definition or {}).get("jurisdiction","Minab"),site.get("road_width"),rules,prefs,(case_definition or {}).get("underside_projection_elevation"),(case_definition or {}).get("road_reference_elevation",0.0),base["zoning_context"]["ground_coverage_mode"])
  candidates=[]
  for raw in base["candidates"]:
   court=SharedResidentialDaylightCourtIntelligenceV1().resolve(raw["lightwell"]["polygon"],[u["polygon"] for u in raw["unit_envelopes"]])
   if not court["court_serves_both_units"]:continue
   for mode in ("projection_disabled","projection_candidate_enabled"):
    if mode.endswith("enabled") and not projection["conditional_architectural_opportunity"]:continue
    candidates.append(self._enrich(raw,court,rules,projection,mode))
  valid=[c for c in candidates if c["hard_validation_status"]=="hard_valid"]
  review=[]
  for family in ("R-EW","R-NS","R-HYBRID"):
   pool=[c for c in valid if c["split_family"]==family]
   for mode in ("projection_disabled","projection_candidate_enabled"):
    mode_pool=[c for c in pool if c["projection_mode"]==mode]
    if mode_pool:review.append(max(mode_pool,key=lambda c:(c["shared_daylight_court"]["daylight_balance_ratio"],-len(c["architectural_quality_penalties"]))))
  assert (site,baseline_scenario_a,pilot_reference)==before
  return {"contract":"ResidentialFloorAccessDaylightTopologyV2","site":"REAL Parcel 2","source_parcel":site["parcel"],"source_road_width":site.get("road_width"),"local_parcel_polygon":base["local_parcel_polygon"],
   "zoning_context":base["zoning_context"],"minab_rules":rules,"projection_opportunity":projection,"source_search_contract":"ResidentialFloorAccessAndDaylightTopologyV1",
   "candidate_count":len(candidates),"hard_valid_candidate_count":len(valid),"candidates":candidates,"human_review_candidates":review,"human_review_candidate_ids":[c["candidate_id"] for c in review],
   "final_selection_performed":False,"final_residential_topology":None,"room_layout_generated":False,"final_windows_generated":False,"caretaker_unit_requested":False,"caretaker_unit_generated":False,
   "baseline_scenario_a":deepcopy(baseline_scenario_a),"baseline_geometry_preserved":True,"program_changed":False,"basement_deleted":False,"basement_removal_approved":False,
   "structure_executed":False,"bim_executed":False,"ifc_executed":False,"render_pipeline_executed":False}
 def _enrich(self,raw,court,rules,projection,mode):
  c=deepcopy(raw);units=[u["polygon"] for u in c["unit_envelopes"]];maint=SharedDaylightCourtMaintenanceAccessV1().resolve(c["common_lobby_polygon"],c["lightwell"]["polygon"],units)
  if maint["corridor_reservation_required"]:
   clearance=Polygon(maint["maintenance_clearance_geometry"]);updated=[]
   for i,u in enumerate(units):
    carved=Polygon(u).difference(clearance);shape=max(carved.geoms,key=lambda g:g.area) if carved.geom_type=="MultiPolygon" else carved
    polygon=[[float(x),float(y)] for x,y in list(shape.exterior.coords)[:-1]];updated.append(polygon);c["unit_envelopes"][i]["polygon"]=polygon;c["unit_envelopes"][i]["metrics"]["unit_area"]=shape.area
   units=updated;c["unit_1_area"]=Polygon(units[0]).area;c["unit_2_area"]=Polygon(units[1]).area;maint["private_unit_crossing"]=False;maint["access_status"]="resolved_by_explicit_common_corridor_reservation"
  court=SharedResidentialDaylightCourtIntelligenceV1().resolve(c["lightwell"]["polygon"],units)
  graph=ResidentialCommonAccessGraphV1().resolve(c["stair"],c["elevator"],c["common_lobby_polygon"],[u["entry_point"] for u in c["unit_envelopes"]],units,maint)
  privacy=SharedCourtPrivacyTopologyV1().resolve(c["lightwell"]["polygon"],units,rules);extent=DaylightCourtVerticalExtentIntelligenceV1().resolve(court["court_area"],"first_residential_level",{"commercial":True,"parking":True},"pending_rule_resolution")
  hard=list(c["hard_rejection_reasons"])
  if not court["court_serves_both_units"]:hard.append("shared_court_does_not_serve_both_units")
  if graph["graph_status"]!="resolved":hard.append("common_access_graph_not_walkable")
  if not graph["paths_stay_common_until_unit_threshold"]:hard.append("walk_path_crosses_private_unit")
  penalties=list(c["architectural_quality_penalties"])+court["quality_penalties"]
  if privacy["direct_opposition_pairs"]:penalties.append("direct_face_to_face_future_opening_risk")
  c.update({"candidate_id":f'{c["candidate_id"]}-{mode.upper()}',"projection_mode":mode,"projection_opportunity":projection if mode.endswith("enabled") else {"public_road_projection":{"projection_status":"projection_disabled_by_candidate","projection_width":0},"no_projection_fallback_available":True},
   "shared_daylight_court":court,"shared_daylight_court_maintenance_access":maint,"shared_court_privacy_topology":privacy,"daylight_court_vertical_extent":extent,"residential_common_access_graph":graph,
   "unit_entry_doors":graph["unit_entry_doors"],"maintenance_door":maint["maintenance_door"],"architectural_quality_penalties":list(dict.fromkeys(penalties)),"hard_rejection_reasons":list(dict.fromkeys(hard)),"hard_validation_status":"hard_valid" if not hard else "not_feasible"})
  return c
