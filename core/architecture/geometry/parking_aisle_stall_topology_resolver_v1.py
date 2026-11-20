"""Evidence-driven basic parking aisle and accessible stall topology."""

from __future__ import annotations

from math import hypot, isfinite


class ParkingAisleStallTopologyResolverV1:
    VERSION = "1.0"
    EPS = 1e-7

    def resolve(self, arrival, requirement, protected_zones=None):
        base={"served_level":arrival.get("served_level") if isinstance(arrival,dict) else None,
              "parking_aisle":None,"stall_candidate_regions":[],"parking_stalls":[],
              "ingress_egress_connectivity":"pending","maneuver_clearance":"pending",
              "blocked_stalls":[],"vehicle_obstruction_status":"pending",
              "capacity_status":"pending","geometry_status":"pending","unresolved_evidence":[],
              "source":"parking_aisle_stall_topology_resolver_v1"}
        if not isinstance(arrival,dict) or arrival.get("geometry_status")!="resolved":
            base["unresolved_evidence"].append("resolved_parking_arrival"); return base
        if not isinstance(requirement,dict) or requirement.get("evidence_status") not in ("authoritative","resolved"):
            base["unresolved_evidence"].append("authoritative_parking_topology_requirement"); return base
        count=requirement.get("required_parking_count"); sw=requirement.get("stall_width"); sd=requirement.get("stall_depth"); aw=requirement.get("aisle_width")
        line=requirement.get("aisle_centerline"); sides=requirement.get("stall_sides")
        for name,value in (("required_parking_count",count),("stall_width",sw),("stall_depth",sd),("aisle_width",aw)):
            if not self._positive(value):base["unresolved_evidence"].append(name)
        if not isinstance(line,list) or len(line)!=2:base["unresolved_evidence"].append("authoritative_aisle_centerline")
        if not isinstance(sides,list) or not sides or any(side not in ("left","right") for side in sides):base["unresolved_evidence"].append("stall_sides")
        if base["unresolved_evidence"]:return base
        a,b=self._point(line[0]),self._point(line[1]); arrival_point=self._point(arrival.get("arrival_point"))
        length=hypot(b[0]-a[0],b[1]-a[1]) if a and b else 0
        if not a or not b or not arrival_point or length<=self.EPS or hypot(a[0]-arrival_point[0],a[1]-arrival_point[1])>self.EPS:
            base["unresolved_evidence"].append("aisle_connected_to_arrival");return base
        ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length; nx,ny=-uy,ux
        aisle=self._strip(a,b,float(aw)); stalls=[]; cursor=float(arrival.get("minimum_turning_radius") or 0)
        for index in range(int(count)):
            side=sides[index%len(sides)]; sign=1 if side=="left" else -1
            u0=cursor+(index//len(sides))*float(sw);u1=u0+float(sw)
            if u1>length+self.EPS:break
            inner=float(aw)/2;outer=inner+float(sd)
            stalls.append({"stall_id":f"P-{index+1:03d}","served_level":base["served_level"],"side":side,
                "polygon":[[a[0]+ux*u0+nx*sign*inner,a[1]+uy*u0+ny*sign*inner],
                           [a[0]+ux*u1+nx*sign*inner,a[1]+uy*u1+ny*sign*inner],
                           [a[0]+ux*u1+nx*sign*outer,a[1]+uy*u1+ny*sign*outer],
                           [a[0]+ux*u0+nx*sign*outer,a[1]+uy*u0+ny*sign*outer]],
                "aisle_access":True,"geometry_status":"candidate"})
        if len(stalls)<int(count):
            return base|{"parking_aisle":{"centerline":line,"polygon":aisle,"width":float(aw)},
                         "parking_stalls":stalls,"capacity_status":"insufficient_capacity",
                         "geometry_status":"not_feasible","unresolved_evidence":["required_parking_count_not_achievable"]}
        protected=list(protected_zones or [])+[arrival.get("arrival_zone")]
        accepted=[]
        for stall in stalls:
            conflict=False
            sb=self._bbox(stall["polygon"])
            for zone in protected:
                if not isinstance(zone,dict) or zone.get("type")=="parking_arrival_zone":continue
                points=zone.get("polygon")
                if points and self._intersects(sb,self._bbox(points)):conflict=True;break
            if conflict:base["blocked_stalls"].append(stall["stall_id"])
            else:stall["geometry_status"]="resolved";accepted.append(stall)
        if len(accepted)<int(count):
            return base|{"parking_aisle":{"centerline":line,"polygon":aisle,"width":float(aw)},
                         "parking_stalls":accepted,"capacity_status":"insufficient_capacity",
                         "geometry_status":"not_feasible","unresolved_evidence":["protected_zone_blocks_required_stall"]}
        return base|{"parking_aisle":{"centerline":line,"polygon":aisle,"width":float(aw),"geometry_status":"resolved"},
                    "stall_candidate_regions":[s["polygon"] for s in stalls],"parking_stalls":accepted,
                    "ingress_egress_connectivity":"resolved","maneuver_clearance":"clear",
                    "vehicle_obstruction_status":"clear","capacity_status":"resolved",
                    "geometry_status":"resolved","unresolved_evidence":[]}

    @staticmethod
    def _strip(a,b,w):
        l=hypot(b[0]-a[0],b[1]-a[1]);nx=-(b[1]-a[1])/l*w/2;ny=(b[0]-a[0])/l*w/2
        return [[a[0]+nx,a[1]+ny],[b[0]+nx,b[1]+ny],[b[0]-nx,b[1]-ny],[a[0]-nx,a[1]-ny]]
    @staticmethod
    def _point(v):return [float(v[0]),float(v[1])] if isinstance(v,(list,tuple)) and len(v)>=2 else None
    @staticmethod
    def _positive(v):return isinstance(v,(int,float)) and isfinite(float(v)) and float(v)>0
    @staticmethod
    def _bbox(p):return [min(x[0] for x in p),min(x[1] for x in p),max(x[0] for x in p),max(x[1] for x in p)]
    @staticmethod
    def _intersects(a,b):return not(a[2]<=b[0] or a[0]>=b[2] or a[3]<=b[1] or a[1]>=b[3])
