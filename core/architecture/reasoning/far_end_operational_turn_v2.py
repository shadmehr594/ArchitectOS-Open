"""Reverse-solved operational ramp END for Basement V2."""
from __future__ import annotations

from math import cos, floor, hypot, pi, sin

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.curved_ramp_physical_path_length_contract_v1 import CurvedRampPhysicalPathLengthContractV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2, VehicleMovementPathV2


class ParkingSizeClassContractV1:
    def resolve(self,required_capacity,achieved_capacity,public=False):
        basis=max(int(required_capacity or 0),int(achieved_capacity or 0))
        size="small" if basis<=3 else ("medium" if basis<=25 else "large")
        width=3.0 if size=="small" else (5.0 if public or size=="large" else 3.5)
        return {"contract":"ParkingSizeClassContractV1","required_capacity":required_capacity,
            "achieved_capacity":achieved_capacity,"classification_basis":basis,"parking_size_class":size,
            "public":bool(public),"minimum_entrance_ramp_width":width,
            "classification_rule":{"small":"1-3","medium":"4-25","large":">25"}}


class ParkingEntranceClearHeightContractV1:
    def resolve(self,size_class,small_private,separate_pedestrian_access):
        reduced=size_class=="small" and small_private is True and separate_pedestrian_access is True
        return {"contract":"ParkingEntranceClearHeightContractV1","required_vehicle_entrance_clear_height":1.95 if reduced else 2.10,
            "reduced_height_authorized":reduced,"small_private":small_private,
            "separate_pedestrian_access":separate_pedestrian_access,
            "parking_space_clear_height_is_separate":True}


class RampWidthTransitionV1:
    def resolve(self,topology,entry_width,curve_width,terminal_width):
        # The complete available leg is used as a continuous linear taper;
        # no unsupported fixed transition length is invented.
        return {"contract":"RampWidthTransitionV1","entry_width":entry_width,
            "straight_leg_width":{"start":entry_width,"end":curve_width},"curve_width":curve_width,
            "terminal_leg_width":{"start":curve_width,"end":terminal_width},
            "widening_transition_length":topology["leg_1_length"],
            "narrowing_transition_length":topology["leg_2_length"],
            "minimum_actual_clear_width":min(entry_width,terminal_width,curve_width),
            "transition_function":"linear_over_available_leg","abrupt_width_discontinuity":False,
            "source":"parking_size_class_plus_project_design_safety_policy"}


class RampOperationalEndV1:
    EPS=1e-7
    def resolve(self,end_edge,field_polygon,required_width,end_z,end_heading=None,expected_end_z=None):
        edge=LineString(end_edge);field=Polygon(field_polygon);interface=edge.intersection(field.boundary)
        width=interface.length
        if width<=self.EPS and field.boundary.buffer(1e-6).covers(edge):
            interface=edge;width=edge.length
        mid=edge.interpolate(.5,normalized=True)
        downstream=True
        if end_heading is not None:
            probe=LineString([[mid.x,mid.y],[mid.x+end_heading[0]*1e-3,mid.y+end_heading[1]*1e-3]])
            downstream=field.buffer(self.EPS).covers(probe)
        endpoint_bound=expected_end_z is not None and abs(end_z-float(expected_end_z))<=self.EPS
        valid=endpoint_bound and width>=required_width-self.EPS and downstream
        reasons=[]
        if expected_end_z is None:reasons.append("authoritative_expected_end_z_missing")
        elif not endpoint_bound:reasons.append("end_elevation_not_at_authoritative_endpoint")
        if interface.geom_type in ("Point","MultiPoint") or width<=self.EPS:reasons.append("point_contact_is_not_vehicle_connectivity")
        if width<required_width-self.EPS:reasons.append("no_valid_end_interface")
        if not downstream:reasons.append("end_facing_away_from_drivable_space")
        return {"contract":"RampOperationalEndV1","geometry_status":"resolved" if valid else "not_feasible",
            "failure_reasons":reasons,"end_edge":end_edge,"end_elevation":end_z,
            "interface_segment":self._coords(interface),"interface_length":width,
            "required_connection_width":required_width,"downstream_free_space":downstream,"faces_wall":not downstream}
    @staticmethod
    def _coords(g):
        if g.is_empty:return []
        if g.geom_type=="MultiLineString":g=max(g.geoms,key=lambda x:x.length)
        if not hasattr(g,"coords"):return []
        return [[float(x),float(y)] for x,y in g.coords]


class FarEndOperationalTurnV2:
    EPS=1e-7

    def resolve(self,parcel,frontage,wall_contract,requirements,request):
        result={"contract":"FarEndOperationalTurnV2","status":"not_run","candidates":[],
            "hard_valid_candidates":[],"physical_ramp_published":False,"human_visual_acceptance":"pending"}
        if request.get("status")!="required":return result
        binding=request.get("authoritative_ramp_endpoint_binding")
        if not isinstance(binding,dict) or binding.get("contract")!="AuthoritativeRampEndpointBindingContractV1" or binding.get("status")!="resolved" or binding.get("binding_resolved") is not True:
            result.update({"status":"pending_requirement","failure_reasons":["authoritative_ramp_endpoint_binding_missing_or_unresolved"]})
            return result
        base=BasementRampParkingDesignReasonerV2();frame=base._frame(parcel,frontage)
        outer=base._to_local_polygon(wall_contract["outer_face"],frame);inner=base._to_local_polygon(wall_contract["inner_face"],frame)
        parking=requirements["parking"];size=ParkingSizeClassContractV1().resolve(parking["minimum_count"],0,False)
        height=ParkingEntranceClearHeightContractV1().resolve(size["parking_size_class"],True,None)
        entry_width=size["minimum_entrance_ramp_width"];curve_width=3.5;terminal_width=entry_width
        rin=float(requirements["ramp"]["minimum_inner_turn_radius"]);slope=float(request["slope"])
        start_z=float(binding["expected_start_z"]);end_z=float(binding["expected_end_z"])
        result["authoritative_ramp_endpoint_binding"]=binding
        ctor=RampCenterlineTopologyV2();u0,v0,u1,v1=inner.bounds;ou0,_,ou1,_=outer.bounds
        fields=[]
        west_u=max(u0+entry_width/2,ou0+curve_width/2)
        east_u=min(u1-entry_width/2,ou1-curve_width/2)
        for side,start_u,turn in (("west",west_u,"right"),("east",east_u,"left")):
            sign=1 if turn=="left" else -1
            for degrees in (45,50,51,52,53,54,54.1,54.2,54.3,54.4,54.5,54.6,54.7,54.8,54.9,55,60,75,90,105,120,135):
              theta=degrees*pi/180;h2=[-sign*sin(theta),cos(theta)]
              oriented_fields=self._fields(inner,(5.0,4.5),h2)
              fields.extend(oriented_fields)
              for field_index,field_record in enumerate(oriented_fields):
               field=field_record["shape"]
              # END is the midpoint of the field edge facing against h2.
               end=self._back_edge_midpoint(field,h2);end_edge=self._edge_at(end,h2,terminal_width)
              # A zero terminal leg is retained only as a diagnostic alternative;
              # positive legs are solved backward from field-derived END.
               probe=ctor.construct([start_u,v0],[0,1],0,turn,theta,rin,curve_width,0,start_z,slope,end_z)
               tout0=probe["tangent_out"]
               if abs(h2[0])<=self.EPS:continue
               leg2=(end[0]-tout0[0])/h2[0]
               leg1=end[1]-tout0[1]-h2[1]*leg2
               if leg1<-self.EPS or leg2<-self.EPS:continue
               leg1=max(0,leg1);leg2=max(0,leg2)
               t=ctor.construct([start_u,v0],[0,1],leg1,turn,theta,rin,curve_width,leg2,start_z,slope,end_z)
               width_contract=RampWidthTransitionV1().resolve(t,entry_width,curve_width,terminal_width)
               physical_paths=CurvedRampPhysicalPathLengthContractV1().resolve(t,width_contract,start_z,end_z,slope)
               surface=self._variable_surface(t,width_contract)
               ramp=Polygon(surface["complete_union_surface"])
               t["operational_end_edge"]=end_edge
               end_contract=RampOperationalEndV1().resolve(end_edge,list(field.exterior.coords)[:-1],terminal_width,end_z,h2,binding["expected_end_z"])
               failures=[]
               if physical_paths["geometry_status"]!="resolved":failures.extend(physical_paths["failure_reasons"])
               if not outer.buffer(1e-5).covers(ramp):failures.append("R5_curve_outside_envelope")
               if t["z_profile"]["geometry_status"]!="resolved":failures.append("vertical_profile_invalid")
               if end_contract["geometry_status"]!="resolved":failures.extend(end_contract["failure_reasons"])
               if leg2<=self.EPS and end_contract["geometry_status"]!="resolved":failures.append("zero_terminal_leg_without_operational_end")
               path=None
               if not failures:
                  center=field.centroid;path=VehicleMovementPathV2().resolve(end_edge,h2,list(field.exterior.coords)[:-1],
                      [end,[center.x,center.y]],[],terminal_width)
                  if path["geometry_status"]!="resolved":failures.append("vehicle_motion_to_maneuvering_invalid")
               stalls=[];options=[]
               if not failures:
                  options=base._stall_topologies(inner,field,ramp,Polygon(),parking,None)
                  options=sorted(options,key=lambda o:(-len(o["stalls"]),base._parking_rank(o)))
                  for option in options:
                      trial=VehicleMovementPathV2().resolve(end_edge,h2,list(field.exterior.coords)[:-1],
                          [end,[field.centroid.x,field.centroid.y]],option["stalls"],terminal_width)
                      if trial["geometry_status"]=="resolved":
                          stalls=option["stalls"];path=trial;break
               # Preserve the already-proven geometric END/interface status;
               # the new physical-path gate is an upstream ramp failure and
               # must not rewrite that frozen evidence.
               ramp_end_valid=end_contract["geometry_status"]=="resolved"
               if ramp_end_valid and physical_paths["geometry_status"]=="resolved" and len(stalls)<int(parking["minimum_count"]):
                   failures.append("minimum_independently_usable_stall_count_not_met")
               result["candidates"].append({"candidate_id":f"OP-{field_record['size']}-{side}-{degrees}-{field_index}",
                  "geometry_status":"hard_valid" if not failures else "not_feasible","failure_reasons":sorted(set(failures)),
                  "ramp_operational_end_status":"hard_valid" if ramp_end_valid else "not_feasible",
                  "maneuvering_field":{"dimensions":[field_record["size"]]*2,"polygon":self._poly(field)},
                  "parking_size_class":size,"entrance_clear_height":height,"width_transition":width_contract,
                  "topology":t,"surface":surface,"operational_end":end_contract,"vehicle_movement":path,
                  "physical_path_length_contract":physical_paths,
                  "parking_stalls":[self._poly(s) for s in stalls],"parking_capacity":len(stalls),
                  "parking_search_status":"not_run_upstream_ramp_invalid" if physical_paths["geometry_status"]!="resolved" else ("hard_valid" if len(stalls)>=int(parking["minimum_count"]) else ("generated_not_valid" if options else "not_generated")),
                  "parking_candidates_generated":len(options),
                  "maximum_geometric_stall_count":max((len(o["stalls"]) for o in options),default=0),
                  "terminal_leg":{"contract":"TerminalRampLegV1","length":leg2,"nonzero":leg2>self.EPS},
                  "far_end_progress_ratio":leg1/max(v1-v0-(rin+curve_width),self.EPS)})
        valid=[c for c in result["candidates"] if c["geometry_status"]=="hard_valid"]
        ramp_valid=[c for c in result["candidates"] if c.get("ramp_operational_end_status")=="hard_valid"]
        result["hard_valid_candidates"]=[c["candidate_id"] for c in valid]
        result["ramp_operational_end_candidates"]=[c["candidate_id"] for c in ramp_valid]
        result["status"]="candidates_for_human_review" if valid else ("operational_end_resolved_parking_unresolved" if ramp_valid else "unresolved_operational_end")
        result["first_failure_stage"]=None if valid else self._first_stage(result,fields)
        achieved=max((c["parking_capacity"] for c in valid),default=0)
        result["parking_size_class_contract"]=ParkingSizeClassContractV1().resolve(parking["minimum_count"],achieved,False)
        result["entrance_clear_height_contract"]=height
        return result

    def _fields(self,inner,sizes,heading):
        safe=inner.buffer(-1e-5);u0,v0,u1,v1=safe.bounds;records=[];lat=[-heading[1],heading[0]]
        for size in sizes:
            extent_x=size*(abs(heading[0])+abs(lat[0]))/2;extent_y=size*(abs(heading[1])+abs(lat[1]))/2
            xlo,xhi=u0+extent_x,u1-extent_x;ylo,yhi=v0+extent_y,v1-extent_y
            xs=self._interval_events(xlo,xhi)
            # Search asymmetric and perimeter-adjacent fields as geometric
            # interval events.  No hand-sketch coordinate enters this set.
            ys=sorted(set(self._interval_events(ylo,yhi)+self._interval_events((v0+v1)/2,yhi)))
            for cx in xs:
              for cy in ys:
                back=[cx-heading[0]*size/2,cy-heading[1]*size/2]
                p=Polygon([[back[0]-lat[0]*size/2,back[1]-lat[1]*size/2],
                    [back[0]+lat[0]*size/2,back[1]+lat[1]*size/2],
                    [back[0]+lat[0]*size/2+heading[0]*size,back[1]+lat[1]*size/2+heading[1]*size],
                    [back[0]-lat[0]*size/2+heading[0]*size,back[1]-lat[1]*size/2+heading[1]*size]])
                if inner.buffer(self.EPS).covers(p):records.append({"size":size,"shape":p})
        return records

    @staticmethod
    def _interval_events(low,high):
        if high<low:return []
        span=high-low
        return sorted({low,low+span*.25,low+span*.5,low+span*.75,high})

    def _variable_surface(self,t,w):
        h1=t["leg_1_heading"];n1=[-h1[1],h1[0]];a=t["leg_1_start"];b=t["leg_1_end"]
        leg1=Polygon([[a[0]-n1[0]*w["entry_width"]/2,a[1]-n1[1]*w["entry_width"]/2],
            [a[0]+n1[0]*w["entry_width"]/2,a[1]+n1[1]*w["entry_width"]/2],
            [b[0]+n1[0]*w["curve_width"]/2,b[1]+n1[1]*w["curve_width"]/2],
            [b[0]-n1[0]*w["curve_width"]/2,b[1]-n1[1]*w["curve_width"]/2]])
        curve=LineString(t["centerline_arc"]).buffer(w["curve_width"]/2,cap_style=2,join_style=1)
        h2=t["leg_2_heading"];n2=[-h2[1],h2[0]];c=t["leg_2_start"];d=t["leg_2_end"]
        leg2=Polygon([[c[0]-n2[0]*w["curve_width"]/2,c[1]-n2[1]*w["curve_width"]/2],
            [c[0]+n2[0]*w["curve_width"]/2,c[1]+n2[1]*w["curve_width"]/2],
            [d[0]+n2[0]*w["terminal_leg_width"]["end"]/2,d[1]+n2[1]*w["terminal_leg_width"]["end"]/2],
            [d[0]-n2[0]*w["terminal_leg_width"]["end"]/2,d[1]-n2[1]*w["terminal_leg_width"]["end"]/2]]) if t["leg_2_length"]>self.EPS else Polygon()
        union=unary_union([leg1,curve,leg2]).buffer(0)
        return {"contract":"VariableWidthRampSurfaceV2","leg_1_surface":self._poly(leg1),
            "curve_surface":self._poly(curve),"terminal_leg_surface":self._poly(leg2),
            "complete_union_surface":self._poly(union),"geometry_status":"resolved" if union.geom_type=="Polygon" else "invalid_geometry"}

    @staticmethod
    def _back_edge_midpoint(field,h):
        points=list(field.exterior.coords)[:-1];values=[p[0]*h[0]+p[1]*h[1] for p in points];m=min(values)
        edge_points=[p for p,v in zip(points,values) if abs(v-m)<1e-6]
        if len(edge_points)>=2:return [(edge_points[0][0]+edge_points[1][0])/2,(edge_points[0][1]+edge_points[1][1])/2]
        # For non-cardinal headings use the support point; it will correctly
        # fail full-width interface rather than fabricate an edge.
        p=points[values.index(m)];return [p[0],p[1]]
    @staticmethod
    def _edge_at(center,h,width):
        n=[-h[1],h[0]];return [[center[0]-n[0]*width/2,center[1]-n[1]*width/2],[center[0]+n[0]*width/2,center[1]+n[1]*width/2]]
    @staticmethod
    def _poly(g):
        if g.is_empty:return []
        if g.geom_type=="MultiPolygon":g=max(g.geoms,key=lambda x:x.area)
        return [[float(x),float(y)] for x,y in list(g.exterior.coords)[:-1]]
    @staticmethod
    def _first_stage(result,fields):
        if not any(f["size"]==5 for f in fields):return "no_5x5_operational_end_field"
        if not any(f["size"]==4.5 for f in fields):return "no_4_5x4_5_operational_end_field"
        if not result["candidates"]:return "terminal_leg_cannot_connect_to_R5_curve"
        if not any(c["operational_end"]["geometry_status"]=="resolved" for c in result["candidates"]):return "no_valid_end_interface"
        if not any("R5_curve_outside_envelope" not in c["failure_reasons"] for c in result["candidates"]):return "R5_curve_outside_envelope"
        if any(c.get("ramp_operational_end_status")=="hard_valid" for c in result["candidates"]):return "minimum_independently_usable_stall_count_not_met"
        return "no_complete_vehicle_operation_chain"
