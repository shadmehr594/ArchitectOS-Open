"""Common maintenance path and door to a shared daylight court."""
from shapely.geometry import LineString,Polygon,Point
class SharedDaylightCourtMaintenanceAccessV1:
 def resolve(self,lobby,court,units,path_width=1.0):
  lobby,court=Polygon(lobby),Polygon(court);units=[Polygon(p) for p in units];door=court.exterior.interpolate(court.exterior.project(lobby.centroid));source=lobby.exterior.interpolate(lobby.exterior.project(door));line=LineString([source,door]);clear=line.buffer(path_width/2,cap_style=2);cross=sum(clear.intersection(u).area for u in units)
  face=self._door_face(court,door)
  return {"contract":"SharedDaylightCourtMaintenanceAccessV1","maintenance_door":{"door_id":"DAYLIGHT-COURT-MAINTENANCE-DOOR","door_face":face,"door_center":[door.x,door.y],"door_swing_or_clearance_zone":self._poly(door.buffer(.45)),"served_space":"COMMON_SHARED_DAYLIGHT_COURT","source_space":"COMMON","access_side":"nearest_common_lobby_edge"},
   "maintenance_path":self._line(line),"maintenance_clearance_geometry":self._poly(clear),"maintenance_path_length":line.length,"maintenance_source":"COMMON","private_unit_crossing":cross>1e-6,"private_unit_crossing_area":cross,
   "common_area_cost":clear.area,"access_status":"resolved_after_common_corridor_reservation" if cross>1e-6 else "resolved_in_existing_common_space","corridor_reservation_required":cross>1e-6}
 def _door_face(self,c,d):
  coords=list(c.exterior.coords);seg=min(zip(coords,coords[1:]),key=lambda ab:LineString(ab).distance(d));return [[float(x),float(y)] for x,y in seg]
 @staticmethod
 def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
 @staticmethod
 def _line(p):return [[float(x),float(y)] for x,y in p.coords]
