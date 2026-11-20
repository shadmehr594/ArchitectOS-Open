"""Maneuver-field-first reverse solver for curved basement arrivals."""
from math import atan2, pi
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from core.architecture.reasoning.curved_ramp_physical_path_length_contract_v1 import CurvedRampPhysicalPathLengthContractV1
from core.architecture.reasoning.far_end_operational_turn_v2 import RampWidthTransitionV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class ManeuverFieldFirstReverseSolveV1:
    EPS = 1e-7

    def resolve(self, inner_clear_face, start_z=0., end_z=-2.4, maximum_grade=.15, inner_radius=5.):
        inner = inner_clear_face if isinstance(inner_clear_face, Polygon) else Polygon(inner_clear_face)
        u0,v0,u1,v1=inner.bounds; cw,sw=3.5,3.; ctor=RampCenterlineTopologyV2()
        result={"contract":"ManeuverFieldFirstReverseSolveV1","maneuver_field_first":True,
            "old_terminal_postprocessing_reused":False,"v3_terminal_geometry_frozen_as_input":False,
            "field_edge_trials":[],"candidates":[],"hard_valid_candidates":[],
            "physical_ramp_published":False,"human_visual_acceptance":"pending"}
        for fid,field,size in self._fields(inner):
          for edge_name,edge,inward in self._edges(field):
            for sense in (1,-1):
              heading=[inward[0]*sense,inward[1]*sense]; faces=sense==1
              result["field_edge_trials"].append({"field_id":fid,"field_size":size,"edge":edge_name,
                  "approach_sense":"into_field" if faces else "away_from_field","heading":heading,"faces_field":faces})
              if not faces: continue
              for end in self._end_midpoints(edge,sw):
                # The long-leg center is governed by the widened tangent-in
                # cross-section, not by the narrower frontage cross-section.
                for side,start_u,turn in (("west",u0+cw/2,"right"),("east",u1-cw/2,"left")):
                  signed=self._signed_turn([0.,1.],heading); expected=-1 if turn=="right" else 1
                  if abs(signed)<pi/6 or signed*expected<=0 or abs(heading[0])<.5: continue
                  theta=abs(signed)
                  zero=ctor.construct([start_u,v0],[0,1],0,turn,theta,inner_radius,cw,0,start_z,maximum_grade,end_z)
                  tout=zero["tangent_out"]
                  leg2=(end[0]-tout[0])/heading[0]
                  leg1=end[1]-tout[1]-heading[1]*leg2
                  if leg1<=self.EPS or leg2<=self.EPS:
                    result["candidates"].append(self._failure(fid,field,size,edge_name,side,end,heading,leg1,leg2,
                        "terminal_leg_not_generated" if leg2<=self.EPS else "north_leg_cannot_connect_to_frontage"));continue
                  topology=ctor.construct([start_u,v0],[0,1],leg1,turn,theta,inner_radius,cw,leg2,start_z,maximum_grade,end_z)
                  widths=RampWidthTransitionV1().resolve(topology,sw,cw,sw)
                  surface=self._surface(topology,widths)
                  physical=CurvedRampPhysicalPathLengthContractV1().resolve(topology,widths,start_z,end_z,maximum_grade)
                  result["candidates"].append(self._validate(fid,field,size,edge_name,side,heading,topology,widths,surface,physical,inner,start_z,end_z,sw))
        result["hard_valid_candidates"]=[c["candidate_id"] for c in result["candidates"] if c["geometry_status"]=="ramp_operational"]
        result["status"]="ramp_operational_candidates_for_human_review" if result["hard_valid_candidates"] else "reverse_solve_geometric_contradiction"
        result["first_geometric_contradiction"]=self._contradiction(result["candidates"],inner_radius,cw,inner)
        return result

    def _validate(self,fid,field,size,edge_name,side,heading,t,w,surface,physical,inner,start_z,end_z,required):
        ramp=Polygon(surface); end_edge=self._edge(t["end_point"],heading,required)
        interface=LineString(end_edge).intersection(field.boundary); overlap=ramp.intersection(field).area; failures=[]
        if not inner.buffer(self.EPS).covers(ramp): failures.append("ramp_surface_outside_legal_envelope")
        if physical["geometry_status"]!="resolved": failures.extend(physical["failure_reasons"])
        if interface.length<required-self.EPS: failures.append("end_interface_below_3m")
        if overlap>self.EPS: failures.append("ramp_maneuver_overlap_positive")
        if t["leg_2_length"]<=self.EPS: failures.append("terminal_leg_not_generated")
        if t["R_inner"]<5-self.EPS: failures.append("inner_turn_radius_below_5m")
        if t["z_profile"]["geometry_status"]!="resolved": failures.extend(t["z_profile"]["failure_reasons"])
        start_ok=abs(t["start_point"][1]-inner.bounds[1])<=self.EPS
        if not start_ok: failures.append("start_not_on_legal_frontage")
        movement=list(t["centerline"])+[[field.centroid.x,field.centroid.y]]
        if not field.buffer(self.EPS).covers(LineString(movement[-2:])): failures.append("end_to_field_path_disconnected")
        cid=f"MFR-{fid}-{edge_name}-{side}-A{t['turn_angle_degrees']:.1f}-L1{t['leg_1_length']:.3f}-L2{t['leg_2_length']:.3f}"
        return {"candidate_id":cid,"field_id":fid,"field_edge":edge_name,"side":side,
            "geometry_status":"ramp_operational" if not failures else "not_feasible","failure_reasons":sorted(set(failures)),
            "maneuver_field_first":True,"maneuvering_field":self._poly(field),"maneuvering_dimensions":[size,size],
            "arrival_edge":end_edge,"end_edge":end_edge,"end_interface_width":interface.length,
            "end_left_z":end_z,"end_center_z":end_z,"end_right_z":end_z,
            "terminal_leg_length":t["leg_2_length"],"terminal_heading":heading,"topology":t,"width_transition":w,
            "physical_path_length":physical,"ramp_surface":surface,"ramp_maneuver_overlap_area":overlap,
            "vehicle_movement_path":movement,"return_path":list(reversed(movement)),"start_on_legal_frontage":start_ok,
            "remaining_free_area":inner.difference(ramp.union(field)).area,
            "parking_search_status":"not_run_terminal_arrival_validation"}

    @staticmethod
    def _fields(inner):
        u0,v0,u1,v1=inner.bounds; out=[]
        for size in (5.,4.5):
          for ix,x in enumerate(sorted({u0,(u0+u1-size)/2,u1-size})):
            for iy,y in enumerate(sorted({v0,(v0+v1-size)/2,v1-size})):
              p=box(x,y,x+size,y+size)
              if inner.buffer(1e-7).covers(p): out.append((f"M{size:.1f}-X{ix}-Y{iy}",p,size))
        return out

    @staticmethod
    def _edges(field):
        x0,y0,x1,y1=field.bounds
        return (("west",[[x0,y0],[x0,y1]],[1,0]),("east",[[x1,y1],[x1,y0]],[-1,0]),
                ("south",[[x1,y0],[x0,y0]],[0,1]),("north",[[x0,y1],[x1,y1]],[0,-1]))

    @staticmethod
    def _end_midpoints(edge,width):
        line=LineString(edge);lo=width/2;hi=line.length-width/2
        return [] if hi<lo-1e-7 else [[line.interpolate(d).x,line.interpolate(d).y] for d in sorted({lo,(lo+hi)/2,hi})]

    @staticmethod
    def _signed_turn(a,b): return atan2(a[0]*b[1]-a[1]*b[0],a[0]*b[0]+a[1]*b[1])
    @staticmethod
    def _edge(c,h,w):
        n=[-h[1],h[0]];return [[c[0]-n[0]*w/2,c[1]-n[1]*w/2],[c[0]+n[0]*w/2,c[1]+n[1]*w/2]]

    @staticmethod
    def _surface(t,w):
        h=t["leg_1_heading"];n=[-h[1],h[0]];a=t["leg_1_start"];b=t["leg_1_end"]
        leg1=Polygon([[a[0]-n[0]*w["entry_width"]/2,a[1]-n[1]*w["entry_width"]/2],[a[0]+n[0]*w["entry_width"]/2,a[1]+n[1]*w["entry_width"]/2],[b[0]+n[0]*w["curve_width"]/2,b[1]+n[1]*w["curve_width"]/2],[b[0]-n[0]*w["curve_width"]/2,b[1]-n[1]*w["curve_width"]/2]])
        curve=LineString(t["centerline_arc"]).buffer(w["curve_width"]/2,cap_style=2,join_style=1)
        h=t["leg_2_heading"];n=[-h[1],h[0]];c=t["leg_2_start"];d=t["leg_2_end"]
        leg2=Polygon([[c[0]-n[0]*w["curve_width"]/2,c[1]-n[1]*w["curve_width"]/2],[c[0]+n[0]*w["curve_width"]/2,c[1]+n[1]*w["curve_width"]/2],[d[0]+n[0]*w["terminal_leg_width"]["end"]/2,d[1]+n[1]*w["terminal_leg_width"]["end"]/2],[d[0]-n[0]*w["terminal_leg_width"]["end"]/2,d[1]-n[1]*w["terminal_leg_width"]["end"]/2]])
        return ManeuverFieldFirstReverseSolveV1._poly(unary_union([leg1,curve,leg2]).buffer(0))

    @staticmethod
    def _failure(fid,field,size,edge,side,end,heading,l1,l2,reason):
        return {"candidate_id":f"MFR-{fid}-{edge}-{side}-failed","field_id":fid,"field_edge":edge,"side":side,
            "geometry_status":"not_feasible","failure_reasons":[reason],"maneuver_field_first":True,
            "maneuvering_field":ManeuverFieldFirstReverseSolveV1._poly(field),"maneuvering_dimensions":[size,size],
            "end_point":end,"terminal_heading":heading,"leg_1_length":l1,"terminal_leg_length":l2,
            "parking_search_status":"not_run_terminal_arrival_validation"}

    @staticmethod
    def _contradiction(candidates,rin,width,inner):
        assembled=[c for c in candidates if "ramp_surface" in c]
        if assembled:
          best=min(assembled,key=lambda c:len(c["failure_reasons"]))
          return {"candidate_id":best["candidate_id"],"failure_reasons":best["failure_reasons"],
              "required_outer_radius":rin+width,"available_transverse_clear_width":inner.bounds[2]-inner.bounds[0],
              "explanation":"All field edges and both approach senses were tested; this is the least-failing reverse assembly."}
        return {"failure_reasons":["no_positive_terminal_leg_from_any_contained_field_edge"],
            "required_outer_radius":rin+width,"available_transverse_clear_width":inner.bounds[2]-inner.bounds[0]}

    @staticmethod
    def _poly(p): return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
