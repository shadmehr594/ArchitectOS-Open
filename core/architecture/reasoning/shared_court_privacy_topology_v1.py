"""Pre-window privacy relationships around a shared court."""
from shapely.geometry import Polygon
class SharedCourtPrivacyTopologyV1:
 def resolve(self,court,units,rules):
  court=Polygon(court);edges=[]
  for i,p in enumerate(units):
   g=Polygon(p).boundary.intersection(court.boundary);edges.append({"unit_id":f"UNIT-{i+1}","candidate_opening_edges":self._segments(g),"opening_status":"opening_eligible_subject_to_future_window_design"})
  direct=bool(edges[0]["candidate_opening_edges"] and edges[1]["candidate_opening_edges"])
  return {"contract":"SharedCourtPrivacyTopologyV1","unit_1_candidate_opening_edges":edges[0]["candidate_opening_edges"],"unit_2_candidate_opening_edges":edges[1]["candidate_opening_edges"],
   "direct_opposition_pairs":[{"unit_1_edge":0,"unit_2_edge":0,"status":"avoid_or_apply_privacy_rule"}] if direct else [],"offset_pairs":[],"perpendicular_pairs":[],
   "preferred_future_opening_relationships":["offset","staggered","perpendicular"],"opposing_window_min_distance":rules["rules"]["opposing_independent_unit_windows_min_distance"],
   "privacy_sensitive_opening_min_installation_height":rules["rules"]["opposing_unit_windows_privacy_height"],"rule_semantic_status":"authoritative_clause_semantic_normalization_required",
   "privacy_status":"future_openings_require_offset_or_clause_validation" if direct else "no_direct_opposition_detected","final_windows_generated":False}
 def _segments(self,g):
  if g.is_empty:return []
  parts=[g] if g.geom_type=="LineString" else [x for x in getattr(g,"geoms",[]) if x.geom_type=="LineString"]
  return [[[float(x),float(y)] for x,y in p.coords] for p in parts if p.length>.1]
