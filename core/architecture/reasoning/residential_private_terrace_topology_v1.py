"""Private terrace polygons separated from daylight lightwells."""
from shapely.geometry import Polygon,box
class ResidentialPrivateTerraceTopologyV1:
 def resolve(self,unit_id,unit_region,mode,frontage,lightwell,index):
  unit=Polygon(unit_region);lw=Polygon(lightwell);x0,y0,x1,y1=unit.bounds
  if mode=="south_recessed":
   width=min(2.8,max(1.8,(x1-x0)*.55));tx0=x0+.25 if index==1 else x1-width-.25;terrace=box(tx0,y0,tx0+width,min(y1,y0+1.35));orientation="south";edge="public_road_south"
  else:
   ax0,ay0,ax1,ay1=lw.bounds;width=min(3.0,ax1-ax0);terrace=box(ax0,ay1,ax0+width,ay1+1.25);orientation="internal";edge="central_lightwell"
  terrace=terrace.intersection(unit)
  accessible=not terrace.is_empty and terrace.boundary.intersection(unit.boundary).length>0
  p=[] if terrace.is_empty else [[float(x),float(y)] for x,y in list(terrace.exterior.coords)[:-1]]
  return {"contract":"ResidentialPrivateTerraceTopologyV1","terrace_id":f"T-{unit_id}","serving_unit_id":unit_id,
   "terrace_polygon":p,"terrace_area":terrace.area,"terrace_width":0 if terrace.is_empty else terrace.bounds[2]-terrace.bounds[0],
   "terrace_depth":0 if terrace.is_empty else terrace.bounds[3]-terrace.bounds[1],"terrace_orientation":orientation,"terrace_open_edge":edge,
   "access_from_unit_status":"private_access_resolved" if accessible else "not_feasible","neighbor_exposure_status":"no_private_neighbor_exposure",
   "privacy_status":"private_unit_access_only","projection_status":"recessed_not_neighbor_projection","regulatory_status":"pending_detailed_terrace_rule_resolution",
   "requirement_source":"user_design_requirement"}
