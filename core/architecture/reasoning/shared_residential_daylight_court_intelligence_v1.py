"""Evaluate whether a residential daylight court actually serves both units."""
from shapely.geometry import Polygon
class SharedResidentialDaylightCourtIntelligenceV1:
 def resolve(self,court,unit_polygons):
  court=Polygon(court);units=[Polygon(p) for p in unit_polygons];edges=[u.boundary.intersection(court.boundary).length for u in units];balance=min(edges)/max(edges) if max(edges)>0 else 0
  return {"contract":"SharedResidentialDaylightCourtIntelligenceV1","space_type":"COMMON_SHARED_DAYLIGHT_COURT","court_polygon":court.__geo_interface__["coordinates"][0][:-1],"court_area":court.area,
   "court_min_width":min(court.bounds[2]-court.bounds[0],court.bounds[3]-court.bounds[1]),"unit_1_useful_daylight_edge":"court_boundary_shared_with_unit_1" if edges[0]>0 else None,
   "unit_2_useful_daylight_edge":"court_boundary_shared_with_unit_2" if edges[1]>0 else None,"unit_1_daylight_edge_length":edges[0],"unit_2_daylight_edge_length":edges[1],"daylight_balance_ratio":balance,
   "future_principal_space_daylight_potential_unit_1":"credible_edge_reserved" if edges[0]>=1 else "unresolved","future_principal_space_daylight_potential_unit_2":"credible_edge_reserved" if edges[1]>=1 else "unresolved",
   "court_ownership":"COMMON","court_serves_both_units":all(e>=1 for e in edges),"quality_penalties":(["court_serves_only_one_unit"] if (edges[0]>0) != (edges[1]>0) else [])+(["court_edge_extremely_unbalanced"] if balance<.35 else [])+(["court_exists_only_for_numeric_compliance"] if not any(edges) else [])}
