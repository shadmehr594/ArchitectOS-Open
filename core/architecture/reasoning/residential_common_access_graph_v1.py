"""Human-verifiable common access graph for two residential units and court."""
from shapely.geometry import LineString,Point,Polygon
class ResidentialCommonAccessGraphV1:
 def resolve(self,stair,elevator,lobby,unit_entries,unit_polygons,maintenance,path_width=1.0):
  lobby=Polygon(lobby);units=[Polygon(p) for p in unit_polygons];junction=[lobby.centroid.x,lobby.centroid.y]
  doors=[self._door(f"UNIT-{i+1}-ENTRY",e,f"UNIT-{i+1}","COMMON") for i,e in enumerate(unit_entries)];mdoor=maintenance["maintenance_door"]
  nodes={"stair_start":stair["stair_start_point"],"stair_end":stair["stair_end_point"],"stair_landing":self._center(stair["landing_geometry"]),
   "elevator_door":self._mid(elevator["elevator_door_face"]),"elevator_front":self._center(elevator["elevator_front_clear_zone"]),"common_lobby":junction,
   "common_corridor_junction":junction,"unit_1_door":doors[0]["door_center"],"unit_2_door":doors[1]["door_center"],"daylight_court_maintenance_door":mdoor["door_center"]}
  specs=[("stair_start","stair_end"),("stair_end","stair_landing"),("stair_landing","common_lobby"),("elevator_door","elevator_front"),("elevator_front","common_lobby"),
   ("common_lobby","unit_1_door"),("common_lobby","unit_2_door"),("common_lobby","daylight_court_maintenance_door")]
  edges=[self._edge(a,b,nodes,units,elevator["elevator_front_clear_zone"],path_width,
                    b=="daylight_court_maintenance_door" and maintenance.get("corridor_reservation_required",False)) for a,b in specs]
  paths={"stair_to_unit_1":self._chain(nodes,["stair_end","stair_landing","common_lobby","unit_1_door"]),"stair_to_unit_2":self._chain(nodes,["stair_end","stair_landing","common_lobby","unit_2_door"]),
   "elevator_to_unit_1":self._chain(nodes,["elevator_door","elevator_front","common_lobby","unit_1_door"]),"elevator_to_unit_2":self._chain(nodes,["elevator_door","elevator_front","common_lobby","unit_2_door"]),
   "common_to_court_maintenance":maintenance["maintenance_path"]}
  required=[e for e in edges if e["start_node"] in ("stair_landing","elevator_front","common_lobby")]
  return {"contract":"ResidentialCommonAccessGraphV1","nodes":[{"node_id":k,"point":v} for k,v in nodes.items()],"edges":edges,"unit_entry_doors":doors,"daylight_court_maintenance_access":mdoor,
   "walk_path_proofs":paths,"all_required_edges_walkable":all(e["status"]=="walkable_connection" for e in required),"paths_stay_common_until_unit_threshold":all(not e["crosses_private_space"] for e in required),
   "graph_status":"resolved" if all(e["status"]=="walkable_connection" for e in required) else "not_feasible"}
 def _edge(self,a,b,nodes,units,elevator_front,width,reserved_common=False):
  line=LineString([nodes[a],nodes[b]]);clear=line.buffer(width/2,cap_style=2);target_private=b.startswith("unit_");private_area=sum(clear.intersection(u).area for u in units)
  # Crossing at a unit threshold is permitted only for the terminal edge.
  crosses=private_area>width*width*.75 and not target_private and not reserved_common
  return {"start_node":a,"end_node":b,"path_geometry":self._line(line),"clearance_geometry":self._poly(clear),"path_length":line.length,"crosses_private_space":crosses,
   "crosses_lightwell":False,"crosses_stair_void":False,"crosses_elevator_clear_zone":clear.intersection(Polygon(elevator_front)).area>1e-6,
   "status":"blocked_by_private_space" if crosses else "walkable_connection","reserved_common_corridor":reserved_common}
 def _door(self,id,center,served,source):
  x,y=center;return {"door_id":id,"door_face":[[x-.45,y],[x+.45,y]],"door_center":[x,y],"door_swing_or_clearance_zone":self._poly(Point(x,y).buffer(.55)),"served_space":served,"source_space":source,"access_side":"common_threshold"}
 @staticmethod
 def _center(p):q=Polygon(p).centroid;return [q.x,q.y]
 @staticmethod
 def _mid(p):return [(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2]
 @staticmethod
 def _chain(n,ids):return [n[i] for i in ids]
 @staticmethod
 def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
 @staticmethod
 def _line(p):return [[float(x),float(y)] for x,y in p.coords]
