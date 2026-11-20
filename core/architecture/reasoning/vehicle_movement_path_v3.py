"""Validated smooth parking trajectories; rendering is contract-only."""
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points, unary_union

from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class VehicleMovementPathV3:
    EPS=1e-7

    def resolve(self, ramp_centerline, end_edge, maneuvering_polygon, aisle_polygon, stalls,
                minimum_clearance_width=3.0):
        maneuver=Polygon(maneuvering_polygon);aisle=Polygon(aisle_polygon)
        stall_polys=[Polygon(stall) for stall in stalls]
        drivable=unary_union([maneuver,aisle])
        end=LineString(end_edge).interpolate(.5,normalized=True)
        records=[]
        for index,stall in enumerate(stall_polys):
            occupied=[other for i,other in enumerate(stall_polys) if i!=index]
            access=stall.boundary.intersection(drivable.boundary)
            target=nearest_points(stall.centroid,access)[1] if not access.is_empty else stall.centroid
            hub=maneuver.representative_point()
            control=[[end.x,end.y],[hub.x,hub.y],[target.x,target.y]]
            trajectory=self._quadratic(control,41)
            line=LineString(trajectory)
            corridor=line.buffer(minimum_clearance_width/2,cap_style=2,join_style=1)
            allowed=drivable.union(stall)
            wall_violation=not allowed.buffer(self.EPS).covers(corridor)
            blocked=[f"P-{i+1:02d}" for i,other in enumerate(stall_polys) if i!=index and corridor.intersection(other).area>self.EPS]
            valid=not wall_violation and not blocked
            entry=trajectory if valid else []
            exit_path=list(reversed(trajectory)) if valid else []
            ramp_return=exit_path + list(reversed(ramp_centerline))[1:] if valid else []
            records.append({"stall_id":f"P-{index+1:02d}","other_stalls_treated_as_occupied":True,
                "entry_status":"hard_valid" if valid else "not_feasible",
                "exit_status":"hard_valid" if valid else "not_feasible",
                "return_to_ramp_status":"hard_valid" if valid else "not_feasible",
                "center_trajectory":entry,"exit_trajectory":exit_path,"return_to_ramp_trajectory":ramp_return,
                "clearance_corridor":RampCenterlineTopologyV2._poly(corridor),
                "minimum_clearance_width":minimum_clearance_width,
                "obstacle_intersections":["outside_drivable_field"] if wall_violation else [],
                "occupied_stall_intersections":blocked,"ramp_connection_status":"resolved" if valid else "not_feasible"})
        valid=bool(records) and all(r["entry_status"]=="hard_valid" for r in records)
        return {"contract":"VehicleMovementPathV3","geometry_status":"hard_valid" if valid else "generated_not_valid",
            "vehicle_path_validation_level":"topology_clearance","stall_paths":records,
            "renderer_authority":"production_contract_only"}

    @staticmethod
    def _quadratic(points,count):
        p0,p1,p2=points;result=[]
        for i in range(count):
            t=i/(count-1);u=1-t
            result.append([u*u*p0[0]+2*u*t*p1[0]+t*t*p2[0],u*u*p0[1]+2*u*t*p1[1]+t*t*p2[1]])
        return result
