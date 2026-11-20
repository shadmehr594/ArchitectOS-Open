"""Derive a readable CAD annotation contract exclusively from resolved architecture."""

from __future__ import annotations

from math import hypot


class ArchitecturalCadDrawingResolverV1:
    VERSION="1.0"

    def resolve(self,geometry):
        dimensions=[];levels=[];labels=[]
        floors=[f for f in geometry.get("floor_geometry",[]) if isinstance(f,dict)]
        for index,floor in enumerate(floors):
            points=self._points((floor.get("footprint") or {}).get("points") if isinstance(floor.get("footprint"),dict) else None)
            if len(points)<3:continue
            box=self._bbox(points);name=str(floor.get("floor"));z=floor.get("elevation",floor.get("bottom"))
            dimensions.extend([
                self._dim(f"{name}_overall_width",[box[0],box[1]],[box[2],box[1]],[box[0],box[1]-0.6],"overall_width"),
                self._dim(f"{name}_overall_depth",[box[0],box[1]],[box[0],box[3]],[box[0]-0.6,box[1]],"overall_depth")])
            if isinstance(z,(int,float)):
                levels.append({"id":f"LEVEL_{name}","level":name,"value":float(z),
                               "anchor":[box[2],box[1]],"label_point":[box[2]+0.5,box[1]+0.45+index*0.35],
                               "leader":True,"geometry_status":"resolved"})
            labels.append({"text":f"{name} AREA {self._area(points):.2f} m2","point":[(box[0]+box[2])/2,(box[1]+box[3])/2],"role":"floor_area"})
        for opening in geometry.get("openings",[]):
            if not isinstance(opening,dict) or opening.get("geometry_status")!="resolved":continue
            a=self._point(opening.get("opening_start"));b=self._point(opening.get("opening_end"))
            if a and b:dimensions.append(self._dim(f"OPENING_{opening.get('id') or opening.get('opening_id')}",a,b,a,"opening_width"))
        for stair in geometry.get("vertical_geometry",[]):
            if not isinstance(stair,dict) or stair.get("type")!="stair_geometry" or stair.get("geometry_status")!="resolved":continue
            p=self._points(stair.get("polygon"));w=stair.get("clear_width")
            if p and isinstance(w,(int,float)):
                dimensions.append({"id":f"{stair.get('stair_id')}_width","value":float(w),"p1":p[0],"p2":p[-1],"base":p[0],"role":"stair_width","geometry_status":"resolved"})
        ramps=[r for r in geometry.get("vertical_geometry",[]) if isinstance(r,dict) and r.get("type")=="vehicle_ramp" and r.get("geometry_status")=="resolved"]
        for ramp in ramps:
            line=ramp.get("centerline") or []
            if len(line)>=2:
                dimensions.append(self._dim(f"{ramp.get('access_id')}_run",line[0],line[-1],line[0],"ramp_run",ramp.get("required_run")))
            if isinstance(ramp.get("width"),(int,float)) and ramp.get("polygon"):
                p=ramp["polygon"];dimensions.append(self._dim(f"{ramp.get('access_id')}_width",p[0],p[-1],p[0],"ramp_width",ramp["width"]))
        parking=geometry.get("site_geometry",{}).get("parking_layout",{})
        aisle=parking.get("parking_aisle",{}) if isinstance(parking,dict) else {}
        if aisle.get("geometry_status")=="resolved" and isinstance(aisle.get("width"),(int,float)):
            p=aisle.get("polygon",[])
            if len(p)>=4:dimensions.append(self._dim("parking_aisle_width",p[0],p[-1],p[0],"parking_aisle_width",aisle["width"]))
        return {"version":self.VERSION,"dimensions":[d for d in dimensions if d],"level_markers":levels,
                "labels":labels,"geometry_status":"resolved" if dimensions else "pending",
                "source":"resolved_architectural_geometry"}

    def _dim(self,id,a,b,base,role,value=None):
        a,b=self._point(a),self._point(b)
        if not a or not b:return None
        return {"id":id,"p1":a,"p2":b,"base":self._point(base),"value":float(value) if isinstance(value,(int,float)) else hypot(b[0]-a[0],b[1]-a[1]),"role":role,"geometry_status":"resolved"}
    @staticmethod
    def _point(v):return [float(v[0]),float(v[1])] if isinstance(v,(list,tuple)) and len(v)>=2 else None
    @classmethod
    def _points(cls,v):return [cls._point(p) for p in v or [] if cls._point(p)]
    @staticmethod
    def _bbox(p):return [min(x[0] for x in p),min(x[1] for x in p),max(x[0] for x in p),max(x[1] for x in p)]
    @staticmethod
    def _area(p):return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))/2)
