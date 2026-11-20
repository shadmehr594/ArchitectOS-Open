"""Centerline-first ramp topology and vehicle movement evidence.

V2 intentionally does not reuse CurvedRampVehicleMovementReasonerV1.  The
centerline, its stationing, and a usable END condition are authoritative;
the physical strip is only an offset product of that topology.
"""
from __future__ import annotations

from math import atan2, cos, hypot, pi, sin

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2


class RampCenterlineTopologyV2:
    EPS = 1e-7

    def construct(self, start, start_heading, leg_1_length, turn_direction,
                  turn_angle, inner_radius, clear_width, leg_2_length,
                  start_z=0.0, slope=0.15, end_z=None):
        """Construct line/arc/line topology without a predecessor polygon."""
        h=self._unit(start_heading); sign=1.0 if turn_direction=="left" else -1.0
        r_center=inner_radius+clear_width/2.0; r_outer=inner_radius+clear_width
        tangent_in=[start[0]+h[0]*leg_1_length,start[1]+h[1]*leg_1_length]
        left=[-h[1],h[0]]
        center=[tangent_in[0]+sign*left[0]*r_center,tangent_in[1]+sign*left[1]*r_center]
        a0=atan2(tangent_in[1]-center[1],tangent_in[0]-center[0])
        sample_count=max(12,int(abs(turn_angle)*180/pi/2))
        arc=[]
        for i in range(sample_count+1):
            a=a0+sign*turn_angle*i/sample_count
            arc.append([center[0]+r_center*cos(a),center[1]+r_center*sin(a)])
        tangent_out=arc[-1]
        c,s=cos(sign*turn_angle),sin(sign*turn_angle)
        h2=[h[0]*c-h[1]*s,h[0]*s+h[1]*c]
        end=[tangent_out[0]+h2[0]*leg_2_length,tangent_out[1]+h2[1]*leg_2_length]
        arc_length=r_center*abs(turn_angle); total=leg_1_length+arc_length+leg_2_length
        stations=[0.0,leg_1_length,leg_1_length+arc_length,total]
        points=[list(start),tangent_in]+arc[1:]+[end]
        station_points=[]
        for i,p in enumerate(points):
            if i==0: station=0.0
            elif i==1: station=leg_1_length
            elif i<len(points)-1: station=leg_1_length+arc_length*(i-1)/sample_count
            else: station=total
            station_points.append([p[0],p[1],station,None])
        end_normal=[-h2[1],h2[0]]
        end_edge=[[end[0]-end_normal[0]*clear_width/2,end[1]-end_normal[1]*clear_width/2],
                  [end[0]+end_normal[0]*clear_width/2,end[1]+end_normal[1]*clear_width/2]]
        topology={"contract":"RampCenterlineTopologyV2","start_point":list(start),"start_heading":h,
            "leg_1_start":list(start),"leg_1_end":tangent_in,"leg_1_heading":h,"leg_1_length":leg_1_length,
            "tangent_in":tangent_in,"curve_center":center,"turn_direction":turn_direction,
            "turn_angle":turn_angle,"turn_angle_degrees":turn_angle*180/pi,"R_inner":inner_radius,
            "R_centerline":r_center,"R_outer":r_outer,"centerline_arc":arc,
            "centerline_arc_length":arc_length,"tangent_out":tangent_out,
            "leg_2_start":tangent_out,"leg_2_end":end,"leg_2_heading":h2,"leg_2_length":leg_2_length,
            "end_point":end,"end_heading":h2,"end_edge":end_edge,"effective_total_run":total,
            "stationing":{"S0":0.0,"S1":stations[1],"S2":stations[2],"S3":stations[3]},
            "z_profile":None,"_station_vertices":station_points,
            "centerline":points}
        target_end=start_z-slope*total if end_z is None else end_z
        topology["z_profile"]=PiecewiseRampVerticalProfileV2().solve(topology,start_z,target_end,slope)
        topology.pop("_station_vertices",None)
        return topology

    def surface(self, topology):
        width=2*(topology["R_centerline"]-topology["R_inner"])
        leg1=LineString([topology["leg_1_start"],topology["leg_1_end"]]).buffer(width/2,cap_style=2)
        curve=LineString(topology["centerline_arc"]).buffer(width/2,cap_style=2,join_style=1)
        leg2=LineString([topology["leg_2_start"],topology["leg_2_end"]]).buffer(width/2,cap_style=2)
        complete=unary_union([leg1,curve,leg2]).buffer(0)
        inner_radius=topology["R_inner"]; outer_radius=topology["R_outer"]
        inner_arc=self._radial_arc(topology,inner_radius)
        outer_arc=self._radial_arc(topology,outer_radius)
        status="resolved" if (not complete.is_empty and complete.geom_type=="Polygon") else "invalid_geometry"
        return {"contract":"RampCenterlineSurfaceV2","geometry_status":status,"clear_width":width,
            "leg_1_surface":self._poly(leg1),"curved_annular_surface":self._poly(curve),
            "leg_2_surface":self._poly(leg2),"complete_union_surface":self._poly(complete),
            "inner_arc":inner_arc,"outer_arc":outer_arc,"self_intersects":not complete.is_valid}

    def _radial_arc(self,t,radius):
        center=t["curve_center"]; start=t["centerline_arc"][0]
        a0=atan2(start[1]-center[1],start[0]-center[0]); sign=1 if t["turn_direction"]=="left" else -1
        n=len(t["centerline_arc"])-1
        return [[center[0]+radius*cos(a0+sign*t["turn_angle"]*i/n),
                 center[1]+radius*sin(a0+sign*t["turn_angle"]*i/n)] for i in range(n+1)]

    @staticmethod
    def _unit(v):
        length=hypot(v[0],v[1]);
        if length<=0: raise ValueError("zero heading")
        return [v[0]/length,v[1]/length]

    @staticmethod
    def _poly(value):
        if value.is_empty:return []
        if value.geom_type=="MultiPolygon": value=max(value.geoms,key=lambda g:g.area)
        return [[float(x),float(y)] for x,y in list(value.exterior.coords)[:-1]]


class PiecewiseRampVerticalProfileV2:
    """Solve monotonic segment slopes under a maximum, never an exact slope."""
    EPS=1e-9

    def solve(self,topology,start_z,end_z,maximum_local_slope):
        drop=start_z-end_z;leg1=topology["leg_1_length"];arc=topology["centerline_arc_length"];leg2=topology["leg_2_length"]
        total=leg1+arc+leg2;minimum_run=drop/maximum_local_slope if maximum_local_slope>0 else float("inf")
        failures=[]
        if drop<0:failures.append("profile_would_rise")
        if total+1e-7<minimum_run:failures.append("horizontal_run_below_minimum_for_max_slope")
        # Prefer the long main leg at the design maximum when it cannot consume
        # the complete drop.  The curve/final leg complete the residual drop at
        # one reduced, continuous station gradient.  If leg1 is already longer
        # than the minimum run, use the uniform reduced gradient so no implicit
        # level segment is invented.
        if leg1*maximum_local_slope<drop-self.EPS and arc+leg2>self.EPS:
            s1=maximum_local_slope;remaining=drop-leg1*s1;s_after=remaining/(arc+leg2)
            slopes={"leg_1":s1,"curve":s_after,"leg_2":s_after}
        else:
            uniform=drop/total if total>self.EPS else float("inf")
            slopes={"leg_1":uniform,"curve":uniform,"leg_2":uniform}
        if any(v< -self.EPS or v>maximum_local_slope+self.EPS for v in slopes.values()):failures.append("local_slope_outside_authorized_range")
        z1=start_z-slopes["leg_1"]*leg1;z2=z1-slopes["curve"]*arc;z3=z2-slopes["leg_2"]*leg2
        vertices=[]
        # Interpolate from the authoritative station ranges, not XY indices.
        for x,y,station,_ in topology.get("_station_vertices",[]):
            if station<=leg1+self.EPS:z=start_z-slopes["leg_1"]*station
            elif station<=leg1+arc+self.EPS:z=z1-slopes["curve"]*(station-leg1)
            else:z=z2-slopes["leg_2"]*(station-leg1-arc)
            vertices.append([x,y,station,z])
        return {"contract":"PiecewiseRampVerticalProfileV2","geometry_status":"resolved" if not failures else "not_feasible",
            "failure_reasons":failures,"start_z":start_z,"end_z":z3,"target_end_z":end_z,
            "maximum_local_slope":maximum_local_slope,"minimum_run_at_maximum_slope":minimum_run,
            "total_centerline_length":total,"segment_slopes":slopes,
            "z_at_tangent_in":z1,"z_at_tangent_out":z2,"vertices":vertices,
            "continuous":abs(z3-end_z)<=1e-7,"monotonic_descent":all(v>=-self.EPS for v in slopes.values())}


class VehicleMovementPathV2:
    EPS=1e-7

    def resolve(self,end_edge,end_heading,maneuver_polygon,aisle_centerline,stalls,vehicle_width=3.5):
        field=Polygon(maneuver_polygon); edge=LineString(end_edge); midpoint=edge.interpolate(.5,normalized=True)
        aisle=LineString(aisle_centerline); connector=LineString([[midpoint.x,midpoint.y],list(aisle.coords)[0]])
        spine=LineString(list(connector.coords)+list(aisle.coords)[1:])
        corridor=spine.buffer(vehicle_width/2,cap_style=2,join_style=1)
        failures=[]
        if edge.length<vehicle_width-self.EPS: failures.append("ramp_end_escape_width_insufficient")
        if not field.buffer(self.EPS).covers(connector): failures.append("maneuvering_field_disconnected_from_ramp_end")
        if not field.buffer(self.EPS).covers(corridor): failures.append("vehicle_main_spine_leaves_drivable_field")
        records=[];stall_polys=[Polygon(s) for s in stalls]
        for i,stall in enumerate(stall_polys):
            occupied=[other for j,other in enumerate(stall_polys) if j!=i]
            access=stall.centroid
            branch=LineString([aisle.interpolate(aisle.project(access)).coords[0],[access.x,access.y]])
            branch_corridor=branch.buffer(vehicle_width/2,cap_style=2)
            blocked=[j for j,o in enumerate(occupied) if branch_corridor.intersection(o).area>self.EPS]
            valid=not blocked
            if not valid: failures.extend(["no_independent_entry_path","no_independent_exit_path"])
            records.append({"stall_id":f"P-{i+1:02d}","other_stalls_treated_as_occupied":True,
                "blocked_by_stall_ids":[f"P-{j+1:02d}" for j in blocked],
                "stall_entry_path":self._line(branch) if valid else [],"stall_exit_path":list(reversed(self._line(branch))) if valid else [],
                "return_to_ramp_path":list(reversed(self._line(branch)))+list(reversed(self._line(spine)))[1:] if valid else [],
                "clearance_corridor":RampCenterlineTopologyV2._poly(branch_corridor),
                "independent_entry":valid,"independent_exit":valid,"return_to_ramp":valid})
        return {"contract":"VehicleMovementPathV2","geometry_status":"resolved" if not failures else "not_feasible",
            "failure_reasons":sorted(set(failures)),"semantic_centerline":self._line(spine),
            "clearance_corridor":RampCenterlineTopologyV2._poly(corridor),"stall_paths":records,
            "renderer_authority":"production_contract_only","validation_level":"topology_clearance"}

    @staticmethod
    def _line(line): return [[float(x),float(y)] for x,y in line.coords]


class Parcel2RampCenterlineSearchV2:
    """Small event-based, bidirectional search; never calls the V1 sampler."""
    EPS=1e-7
    MEANINGFUL_RETURN_DEGREES=45.0

    def resolve(self,parcel,frontage,wall_contract,requirements,request):
        result={"contract":"Parcel2RampCenterlineSearchV2","status":"not_run","candidates":[],
            "hard_valid_candidates":[],"physical_ramp_published":False,"human_visual_acceptance":"pending",
            "supersedes_v1_only_as_search_method":True}
        if request.get("contract")!="RampTopologyChangeRequestV1" or request.get("status")!="required": return result
        base=BasementRampParkingDesignReasonerV2();frame=base._frame(parcel,frontage)
        outer=base._to_local_polygon(wall_contract["outer_face"],frame);inner=base._to_local_polygon(wall_contract["inner_face"],frame)
        width=float(requirements["ramp"]["clear_width"]);rin=float(requirements["ramp"]["minimum_inner_turn_radius"])
        slope=float(request["slope"]);start_z=float(requirements["levels"]["ground"]);end_z=float(requirements["levels"]["basement"])
        minimum_run=abs(end_z-start_z)/slope; preferred=requirements["parking"]["maneuvering_clear_zone"]["preferred"]
        minimum=requirements["parking"]["maneuvering_clear_zone"]["minimum"]
        ctor=RampCenterlineTopologyV2(); u0,v0,u1,v1=outer.bounds
        # Events are semantic: side corridors, meaningful return headings, and
        # leg-one stations induced by the available far-field boundary.
        # In the frontage-local frame +v points inward.  The west corridor
        # turns right (toward +u) and the east corridor turns left (toward -u).
        for side,start_u,turn in (("west",u0+width/2,"right"),("east",u1-width/2,"left")):
            for degrees in (45,60,75,90):
                theta=degrees*pi/180
                max_far=max(0.0,v1-v0-(rin+width))
                # Early/mid/latest stations are induced by the legal far-boundary
                # tangent envelope.  They are not a partition of a 16m route.
                events=sorted({max_far*.35,max_far*.65,max_far})
                for leg1 in events:
                  for leg2 in (0.0,width/2,minimum[0]):
                    t=ctor.construct([start_u,v0],[0,1],leg1,turn,theta,rin,width,leg2,start_z,slope,end_z)
                    s=ctor.surface(t); poly=Polygon(s["complete_union_surface"])
                    progress=leg1/max(max_far,self.EPS)
                    classification=self._classify(t,poly,inner,side,progress)
                    failures=[]
                    if degrees<self.MEANINGFUL_RETURN_DEGREES: failures.append("gentle_deflection")
                    if classification=="central_diagonal_cut": failures.append("central_diagonal_crossing")
                    if not outer.buffer(1e-5).covers(poly): failures.append("turn_outside_clear_envelope")
                    if t["z_profile"]["geometry_status"]!="resolved": failures.extend(t["z_profile"]["failure_reasons"])
                    maneuvers=self._end_first_fields(inner,poly,t,preferred,minimum,width)
                    chosen=next((m for m in maneuvers if m["geometry_status"]=="resolved"),None)
                    if chosen is None: failures.append("no_connected_minimum_maneuvering_field")
                    central=inner.buffer(-width);intrusion=poly.intersection(central).area if not central.is_empty else 0.0
                    remaining_geom=inner.difference(poly);largest=max((g.area for g in getattr(remaining_geom,"geoms",[remaining_geom])),default=0)
                    result["candidates"].append({"candidate_id":f"V2-{side.upper()}-{degrees:03d}-L1-{leg1:.3f}-L2-{leg2:.3f}",
                        "classification":classification if not failures else ("perimeter_following_failed" if classification=="perimeter_following_valid" else classification),
                        "geometry_status":"hard_valid" if not failures else "not_feasible","failure_reasons":sorted(set(failures)),
                        "topology":t,"surface":s,"maneuvering_trials":maneuvers,"selected_maneuvering":chosen,
                        "central_field_intrusion_area":intrusion,"largest_contiguous_remaining_field":largest,
                        "distance_start_to_tangent_in":leg1,"distance_tangent_in_to_far_boundary":max_far-leg1,
                        "far_end_progress_ratio":progress,"long_leg_perimeter_alignment":self._alignment(t,inner,side),
                        "central_diagonal_crossing":classification=="central_diagonal_cut"})
        valid=[c for c in result["candidates"] if c["geometry_status"]=="hard_valid"]
        result["hard_valid_candidates"]=[c["candidate_id"] for c in valid]
        result["status"]="candidates_for_human_review" if valid else "unresolved_centerline_topology"
        result["obsolete_constant_slope_contradiction"]=self._obsolete_contradiction(inner,width,rin,minimum_run)
        result["first_geometric_contradiction"]=self._actual_contradiction(result["candidates"],inner,width,rin)
        return result

    def _end_first_fields(self,inner,ramp,t,preferred,minimum,width):
        end=t["end_point"];h=t["end_heading"];lat=[-h[1],h[0]];records=[]
        for dims,label in ((preferred,"preferred"),(minimum,"minimum")):
            w,d=map(float,dims)
            # END-discovered fields: full-width interface at END, with lateral
            # translations induced by the excess field width.
            for offset in (0.0,(w-width)/2,-(w-width)/2):
                c=[end[0]+lat[0]*offset,end[1]+lat[1]*offset]
                p=Polygon([[c[0]-lat[0]*w/2,c[1]-lat[1]*w/2],
                    [c[0]+lat[0]*w/2,c[1]+lat[1]*w/2],
                    [c[0]+lat[0]*w/2+h[0]*d,c[1]+lat[1]*w/2+h[1]*d],
                    [c[0]-lat[0]*w/2+h[0]*d,c[1]-lat[1]*w/2+h[1]*d]])
                interface=LineString(t["end_edge"]).intersection(p.boundary)
                interface_width=interface.length
                valid=inner.buffer(self.EPS).covers(p) and p.intersection(ramp).area<=self.EPS and interface_width>=width-self.EPS
                records.append({"status":label,"polygon":RampCenterlineTopologyV2._poly(p),"dimensions":[w,d],
                    "end_interface":self._coords(interface),"interface_width":interface_width,
                    "connected_component_id":"END-FIELD-1" if valid else None,
                    "geometry_status":"resolved" if valid else "not_feasible"})
            if any(r["geometry_status"]=="resolved" for r in records): break
        return records

    def _classify(self,t,surface,inner,side,progress):
        alignment=self._alignment(t,inner,side)
        central=inner.buffer(-2*(t["R_centerline"]-t["R_inner"]))
        diagonal=abs(t["leg_1_heading"][0])>.15 or (not central.is_empty and surface.intersection(central).area>surface.area*.35)
        if diagonal:return "central_diagonal_cut"
        if t["turn_angle_degrees"]<self.MEANINGFUL_RETURN_DEGREES:return "gentle_deflection"
        if alignment<.75:return "perimeter_following_failed"
        if progress>=.85:return "far_end_perimeter_turn"
        if progress>=.5:return "midfield_turn"
        return "early_turn"

    @staticmethod
    def _alignment(t,inner,side):
        side_x=inner.bounds[0] if side=="west" else inner.bounds[2]
        distances=[abs(p[0]-side_x) for p in (t["leg_1_start"],t["leg_1_end"])]
        return max(0.0,1.0-sum(distances)/(2*max(inner.bounds[2]-inner.bounds[0],1e-7)))

    @staticmethod
    def _coords(g):
        if g.is_empty:return []
        if g.geom_type=="MultiLineString":g=max(g.geoms,key=lambda x:x.length)
        if g.geom_type.startswith("Multi") or g.geom_type=="GeometryCollection":
            return [[[float(x),float(y)] for x,y in part.coords] for part in g.geoms if hasattr(part,"coords")]
        return [[float(x),float(y)] for x,y in g.coords]

    @staticmethod
    def _obsolete_contradiction(inner,width,rin,required):
        quarter_arc=(rin+width/2)*pi/2; residual=required-quarter_arc
        available_width=inner.bounds[2]-inner.bounds[0]
        return {"status":"obsolete_constant_slope_contradiction","assumption":"total route fixed to minimum run",
            "quarter_turn_centerline_arc":quarter_arc,"remaining_station_for_both_legs":residual,
            "required_outer_radius":rin+width,"available_clear_transverse_width":available_width,
            "statement":f"Under the obsolete exact-run assumption only, the arc consumed {quarter_arc:.3f}m and left {residual:.3f}m. This is not a V2 rejection reason."}

    @staticmethod
    def _actual_contradiction(candidates,inner,width,rin):
        contained=[c for c in candidates if "turn_outside_clear_envelope" not in c["failure_reasons"]]
        connected=[c for c in contained if c["selected_maneuvering"]]
        if not contained:
            return {"boundary":"curved_strip_containment","statement":"No centerline-offset annular strip remained inside the legal envelope."}
        if not connected:
            profile_valid=[c for c in contained if c["topology"]["z_profile"]["geometry_status"]=="resolved"]
            best=max(profile_valid or contained,key=lambda c:(c["far_end_progress_ratio"],c["topology"]["turn_angle_degrees"],-c["topology"]["leg_2_length"]))
            return {"boundary":"end_to_minimum_maneuvering_interface","candidate_id":best["candidate_id"],
                "end_edge":best["topology"]["end_edge"],"required_interface_width":width,
                "required_minimum_field":[4.5,4.5],"statement":"A contained variable-profile ramp was generated, but its END admitted no connected 4.5x4.5 field through a 3.5m interface."}
        return None
