"""Geometry-search space in front of a residential elevator."""
from shapely.geometry import Polygon,box
class ElevatorLobbyClearanceIntelligenceV1:
 def resolve(self,elevator,lobby):
  e,l=Polygon(elevator),Polygon(lobby);ex0,ey0,ex1,ey1=e.bounds;lx0,ly0,lx1,ly1=l.bounds
  door=[[ex0,ey1],[ex1,ey1]];front=box(max(lx0,ex0),max(ly0,ey1),min(lx1,ex1),ly1)
  if front.is_empty or front.area<1e-6:front=l
  p=[[float(x),float(y)] for x,y in list(front.exterior.coords)[:-1]]
  return {"contract":"ElevatorLobbyClearanceIntelligenceV1","elevator_door_face":door,"elevator_front_clear_zone":p,"standing_zone":p,
   "passing_zone":p,"common_lobby_polygon":[[float(x),float(y)] for x,y in list(l.exterior.coords)[:-1]],
   "elevator_front_status":"generated_pending_regulatory_validation","geometry_source":"engineering_space_search","regulatory_status":"pending_rule_resolution"}
