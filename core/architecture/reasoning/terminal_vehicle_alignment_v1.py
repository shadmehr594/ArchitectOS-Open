"""Site-local terminal alignment at basement floor elevation."""
from math import atan2, cos, pi, sin

from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class TerminalVehicleAlignmentV1:
    EPS=1e-7

    def resolve(self,start_point,start_heading,clear_envelope,vehicle_width=3.0,inner_radius=5.0):
        envelope=Polygon(clear_envelope);h=self._unit(start_heading)
        axes=[[1,0],[-1,0],[0,1],[0,-1]];records=[]
        for target in axes:
            dot=max(-1,min(1,h[0]*target[0]+h[1]*target[1]));cross=h[0]*target[1]-h[1]*target[0]
            angle=atan2(abs(cross),dot)
            if angle<1e-6:
                records.append({"target_heading":target,"geometry_status":"already_aligned","alignment_angle_degrees":0,
                    "centerline":[start_point],"clearance_corridor":[],"end_point":start_point})
                continue
            if angle>pi/2+1e-6:continue
            direction="left" if cross>0 else "right";rc=inner_radius+vehicle_width/2
            left=[-h[1],h[0]];sign=1 if direction=="left" else -1
            center=[start_point[0]+sign*left[0]*rc,start_point[1]+sign*left[1]*rc]
            a0=atan2(start_point[1]-center[1],start_point[0]-center[0]);points=[]
            for i in range(25):
                a=a0+sign*angle*i/24;points.append([center[0]+rc*cos(a),center[1]+rc*sin(a)])
            line=LineString(points);corridor=line.buffer(vehicle_width/2,cap_style=2,join_style=1)
            valid=envelope.buffer(self.EPS).covers(corridor)
            records.append({"target_heading":target,"geometry_status":"resolved" if valid else "not_feasible",
                "failure_reasons":[] if valid else ["terminal_alignment_corridor_outside_clear_envelope"],
                "alignment_angle_degrees":angle*180/pi,"turn_direction":direction,"R_inner":inner_radius,
                "R_centerline":rc,"centerline":points,"clearance_corridor":RampCenterlineTopologyV2._poly(corridor),
                "end_point":points[-1],"end_heading":target,"floor_elevation":-2.4})
        resolved=[r for r in records if r["geometry_status"] in ("resolved","already_aligned")]
        return {"contract":"TerminalVehicleAlignmentV1","geometry_status":"resolved" if resolved else "unresolved",
            "site_local_axes":{"longitudinal":[0,1],"transverse":[1,0]},"alternatives":records,
            "selected":min(resolved,key=lambda r:r["alignment_angle_degrees"]) if resolved else None}

    @staticmethod
    def _unit(v):
        length=(v[0]**2+v[1]**2)**.5;return [v[0]/length,v[1]/length]
