"""Residential-floor stair endpoints and arrival geometry."""
from shapely.geometry import Polygon,box
class StairEndpointIntelligenceV1:
 def resolve(self,stair_polygon,common_lobby,unit_entries,elevator_front):
  stair=Polygon(stair_polygon);lobby=Polygon(common_lobby);x0,y0,x1,y1=stair.bounds
  start=[(x0+x1)/2,y0];end=[(x0+x1)/2,y1];landing=box(x0,y1-min(1.2,(y1-y0)/3),x1,y1)
  inside_unit=any(Polygon(u).contains(landing.centroid) for u in unit_entries)
  elevator_conflict=landing.intersection(Polygon(elevator_front)).area>1e-6
  return {"contract":"StairEndpointIntelligenceV1","stair_start_point":start,"stair_end_point":end,"flight_direction":"south_to_north",
   "arrival_direction":"north","departure_direction":"south","landing_geometry":[[float(x),float(y)] for x,y in list(landing.exterior.coords)[:-1]],
   "floor_arrival_zone":[[float(x),float(y)] for x,y in list(lobby.exterior.coords)[:-1]],"floor_departure_zone":[[float(x),float(y)] for x,y in list(lobby.exterior.coords)[:-1]],
   "next_floor_connection":"vertically_aligned_same_stair_shaft","stair_arrives_into_common_space":lobby.buffer(1e-6).intersects(landing),
   "stair_does_not_arrive_inside_unit":not inside_unit,"stair_does_not_conflict_with_unit_entry":not inside_unit,
   "stair_does_not_conflict_with_elevator_front":not elevator_conflict,"stair_arrival_status":"resolved" if not inside_unit else "not_feasible"}
