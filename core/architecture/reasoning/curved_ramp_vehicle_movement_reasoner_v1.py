"""Curved ramp and vehicle-movement evidence, gated by RampTopologyChangeRequestV1."""
from __future__ import annotations

from math import atan2, cos, hypot, pi, sin

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2


class CurvedRampVehicleMovementReasonerV1:
    EPS=1e-7

    def resolve(self,parcel,frontage,wall_contract,requirements,obstacle_inventory,request):
        result={"contract":"CurvedRampSearchContractV1","status":"not_run","request":request,
            "candidates":[],"hard_valid_candidates":[],"selected_candidate":None,
            "physical_ramp_published":False,"human_visual_acceptance":"pending"}
        if request.get("contract")!="RampTopologyChangeRequestV1" or request.get("status")!="required": return result
        base=BasementRampParkingDesignReasonerV2();frame=base._frame(parcel,frontage)
        outer=base._to_local_polygon(wall_contract["outer_face"],frame);inner=base._to_local_polygon(wall_contract["inner_face"],frame)
        slope=float(request["slope"]);start_z=float(requirements["levels"]["ground"]);end_z=float(requirements["levels"]["basement"])
        width=float(requirements["ramp"]["clear_width"]);inner_radius=float(requirements["ramp"]["minimum_inner_turn_radius"])
        required_run=abs(end_z-start_z)/slope;preferred=requirements["parking"]["maneuvering_clear_zone"]["preferred"]
        minimum=requirements["parking"]["maneuvering_clear_zone"]["minimum"]
        central=inner.buffer(-width);raw=[]
        for side in ("left","right"):
            # Deterministic angular/run events; no random or Parcel-2 coordinate.
            for angle_degrees in range(10,91,5):
                angle=angle_degrees*pi/180.0
                center_radius=inner_radius+width/2;arc_length=center_radius*angle
                remaining=required_run-arc_length
                if remaining<=self.EPS: continue
                # Fractions are topology events over the remaining run, not site coordinates.
                for fraction_index in range(1,20):
                    fraction=fraction_index/20.0
                    leg1=remaining*fraction;leg2=remaining-leg1
                    raw.append(self._curved_candidate(outer,inner,frame,side,angle,inner_radius,width,
                        leg1,arc_length,leg2,required_run,slope,start_z,end_z,preferred,minimum,central,base,requirements["parking"]))
        # A dog-leg family uses two opposite tangent arcs; its radius envelope is
        # evaluated explicitly and retained only when geometrically distinct.
        for side in ("left","right"):
            for angle in (pi/6,pi/4):
                raw.append(self._dog_leg_candidate(outer,inner,frame,side,angle,inner_radius,width,
                    required_run,slope,start_z,end_z,preferred,minimum,central,base,requirements["parking"]))
        candidates=[c for c in raw if c is not None]
        result["candidates"]=candidates
        valid=[c for c in candidates if c["geometry_status"]=="hard_valid"]
        result["hard_valid_candidates"]=[c["candidate_id"] for c in valid]
        result["status"]="candidates_for_human_review" if valid else "unresolved_no_feasible_curved_topology"
        result["first_proven_boundary"]=next((reason for c in candidates for reason in c["failure_reasons"]),"no_curved_candidate_generated") if not valid else None
        return result

    def _curved_candidate(self,outer,inner,frame,side,angle,r_inner,width,leg1,arc_length,leg2,
                          required_run,slope,start_z,end_z,preferred,minimum,central,base,parking):
        u0,_,u1,_=outer.bounds;sign=1.0 if side=="left" else -1.0
        start_u=u0+width/2 if side=="left" else u1-width/2
        center_radius=r_inner+width/2;outer_radius=r_inner+width
        center=[start_u+sign*center_radius,leg1]
        samples=24;centerline=[[start_u,0.0],[start_u,leg1]]
        inner_arc=[];center_arc=[];outer_arc=[]
        for index in range(samples+1):
            t=angle*index/samples
            a=pi-t if sign>0 else t
            center_arc.append([center[0]+center_radius*cos(a),center[1]+center_radius*sin(a)])
            inner_arc.append([center[0]+r_inner*cos(a),center[1]+r_inner*sin(a)])
            outer_arc.append([center[0]+outer_radius*cos(a),center[1]+outer_radius*sin(a)])
        centerline.extend(center_arc[1:])
        heading=([sin(pi-angle),-cos(pi-angle)] if sign>0 else [-sin(angle),cos(angle)])
        tangent_out=center_arc[-1];end=[tangent_out[0]+heading[0]*leg2,tangent_out[1]+heading[1]*leg2]
        centerline.append(end)
        surface=LineString(centerline).buffer(width/2,cap_style=2,join_style=1,resolution=24)
        transition=LineString(center_arc).buffer(width/2,cap_style=2,join_style=1,resolution=24)
        end_edge=[[end[0]-heading[1]*width/2,end[1]+heading[0]*width/2],
                  [end[0]+heading[1]*width/2,end[1]-heading[0]*width/2]]
        maneuver_trials=self._maneuver_trials(inner,surface,end,end_edge,heading,preferred,minimum,width,base)
        best=next((m for m in maneuver_trials if m["connection_proof"]["geometry_status"]=="resolved"),None)
        failures=self._curved_failures(outer,surface,transition,r_inner,width,required_run,leg1+arc_length+leg2,best)
        movement=None;stalls=[]
        if best:
            stalls,movement=self._parking_and_movement(inner,surface,best,end_edge,heading,parking,width,base)
            if not movement or movement["geometry_status"]!="resolved": failures.append("vehicle_main_spine_disconnected")
        remaining=inner.difference(surface);central_intrusion=surface.intersection(central).area if not central.is_empty else 0.0
        z_in=start_z-slope*leg1;z_out=start_z-slope*(leg1+arc_length)
        for trial in maneuver_trials:
            trial["polygon"]=base._world_polygon(trial.pop("local_polygon"),frame)
            trial["end_interface_segment"]=[base._world(p,frame) for p in trial["end_interface_segment"]]
            trial["end_to_maneuver_centerline"]=[base._world(p,frame) for p in trial.get("end_to_maneuver_centerline",[])]
            trial["end_to_maneuver_clearance_corridor"]=[base._world(p,frame) for p in trial.get("end_to_maneuver_clearance_corridor",[])]
            corridor=trial["connection_proof"].get("corridor_polygon")
            if corridor: trial["connection_proof"]["corridor_polygon"]=[base._world(p,frame) for p in corridor]
        centerline_3d=[[centerline[0][0],centerline[0][1],start_z],
            [centerline[1][0],centerline[1][1],start_z-slope*leg1]]
        for index,point in enumerate(center_arc[1:],1):
            s=leg1+arc_length*index/samples
            centerline_3d.append([point[0],point[1],start_z-slope*s])
        centerline_3d.append([end[0],end[1],end_z])
        return {"candidate_id":f"CURVED-{side.upper()}-{round(angle*180/pi):03d}-{round(leg1,3)}",
            "topology":"perimeter_curved_turn","side":side,"geometry_status":"hard_valid" if not failures else "not_feasible",
            "failure_reasons":sorted(set(failures)),"slope":slope,"clear_width":width,
            "inner_radius":r_inner,"centerline_radius":center_radius,"outer_radius":outer_radius,
            "turn_angle_radians":angle,"turn_angle_degrees":angle*180/pi,"centerline_arc_length":arc_length,
            "leg_1_length":leg1,"leg_2_length":leg2,"effective_run":leg1+arc_length+leg2,"required_run":required_run,
            "start":base._world([start_u,0],frame),"start_elevation":start_z,"end":base._world(end,frame),"end_elevation":end_z,
            "end_edge":[base._world(p,frame) for p in end_edge],"departure_direction":self._world_direction(heading,frame),
            "tangent_point_in":base._world([start_u,leg1],frame),"tangent_point_out":base._world(tangent_out,frame),
            "z_at_tangent_in":z_in,"z_at_tangent_out":z_out,
            "inner_arc":[base._world(p,frame) for p in inner_arc],"centerline_arc":[base._world(p,frame) for p in center_arc],
            "outer_arc":[base._world(p,frame) for p in outer_arc],"centerline":[base._world(p,frame) for p in centerline],
            "centerline_3d":centerline_3d,
            "transition_polygon":base._world_polygon(transition,frame),"ramp_surface":base._world_polygon(surface,frame),
            "maneuvering_trials":maneuver_trials,"best_maneuvering":best,"parking_stalls":stalls,"vehicle_movement_path":movement,
            "perimeter_adjacency":surface.intersection(inner.difference(central)).area/max(surface.area,self.EPS),
            "central_field_intrusion_area":central_intrusion,"fragmentation_count":len(getattr(remaining,"geoms",[remaining])),
            "largest_contiguous_remaining_free_field":max((g.area for g in getattr(remaining,"geoms",[remaining])),default=0.0),
            "parking_capacity":len(stalls)}

    def _dog_leg_candidate(self,outer,inner,frame,side,angle,r_inner,width,required_run,slope,start_z,end_z,preferred,minimum,central,base,parking):
        center_radius=r_inner+width/2;arc_total=2*center_radius*angle;remaining=required_run-arc_total
        if remaining<=self.EPS: return None
        # Two opposite arcs need their full swept width; generate geometry from
        # the same tangent construction, then reject if the second arc cannot fit.
        candidate=self._curved_candidate(outer,inner,frame,side,angle,r_inner,width,
            remaining/2,center_radius*angle,remaining/2,required_run,slope,start_z,end_z,preferred,minimum,central,base,parking)
        candidate["candidate_id"]=candidate["candidate_id"].replace("CURVED","DOGLEG")
        candidate["topology"]="curved_dog_leg"
        candidate["failure_reasons"]=sorted(set(candidate["failure_reasons"]+["second_tangent_arc_not_geometrically_resolved"]))
        candidate["geometry_status"]="not_feasible"
        return candidate

    def _maneuver_trials(self,inner,surface,end,end_edge,heading,preferred,minimum,width,base):
        lateral=[-heading[1],heading[0]];records=[];center_radius=5.0+width/2
        for size in (preferred,minimum):
            w,d=map(float,size)
            for turn_sign in (-1,0,1):
              for angle_degrees in ((0,) if turn_sign==0 else (10,20,30,40,50,60,70,80,90)):
                angle=angle_degrees*pi/180.0;connector=[end]
                final_heading=list(heading);curve=[]
                if turn_sign:
                    normal=[-heading[1]*turn_sign,heading[0]*turn_sign]
                    center=[end[0]+normal[0]*center_radius,end[1]+normal[1]*center_radius]
                    start_angle=atan2(end[1]-center[1],end[0]-center[0])
                    for index in range(1,25):
                        a=start_angle+turn_sign*angle*index/24
                        curve.append([center[0]+center_radius*cos(a),center[1]+center_radius*sin(a)])
                    connector.extend(curve)
                    final_heading=[heading[0]*cos(angle)-turn_sign*heading[1]*sin(angle),
                                   turn_sign*heading[0]*sin(angle)+heading[1]*cos(angle)]
                final_lateral=[-final_heading[1],final_heading[0]]
                for straight_length in (0.0,d/4,d/2,d):
                  path=list(connector)
                  path_end=path[-1]
                  if straight_length>self.EPS:
                      path_end=[path_end[0]+final_heading[0]*straight_length,path_end[1]+final_heading[1]*straight_length]
                      path.append(path_end)
                  if len(path)==1:
                      path.append([path_end[0]+final_heading[0]*self.EPS*10,
                                   path_end[1]+final_heading[1]*self.EPS*10])
                  line=LineString(path);corridor=line.buffer(width/2,cap_style=2,join_style=1,resolution=24)
                  for offset in sorted({-(w-width)/2,0.0,(w-width)/2}):
                    back=[path_end[0]+final_lateral[0]*offset,path_end[1]+final_lateral[1]*offset]
                    polygon=Polygon([[back[0]-final_lateral[0]*w/2,back[1]-final_lateral[1]*w/2],
                        [back[0]+final_lateral[0]*w/2,back[1]+final_lateral[1]*w/2],
                        [back[0]+final_lateral[0]*w/2+final_heading[0]*d,back[1]+final_lateral[1]*w/2+final_heading[1]*d],
                        [back[0]-final_lateral[0]*w/2+final_heading[0]*d,back[1]-final_lateral[1]*w/2+final_heading[1]*d]])
                    if not inner.buffer(self.EPS).covers(polygon) or not inner.buffer(self.EPS).covers(corridor): continue
                    if polygon.intersection(surface).area>self.EPS or corridor.intersection(surface).area>1e-5: continue
                    proof=base._maneuvering_connection_proof(corridor,polygon,width)
                    if proof["geometry_status"]!="resolved": continue
                    records.append({"dimensions":[w,d],"local_polygon":polygon,"polygon":base._polygon_coords(polygon),
                        "end_interface_segment":end_edge,"connection_proof":proof,
                        "end_to_maneuver_centerline":base._line_coords(line),
                        "end_to_maneuver_clearance_corridor":base._polygon_coords(corridor),
                        "connector_turn_angle_degrees":angle_degrees,"connector_inner_radius":5.0 if turn_sign else None,
                        "connector_validation_level":"topology_clearance"})
            if any(r["connection_proof"]["geometry_status"]=="resolved" for r in records): break
        return records

    @staticmethod
    def _curved_failures(outer,surface,transition,r_inner,width,required_run,effective,best):
        failures=[]
        if r_inner<5.0-1e-7: failures.append("inner_turn_radius_below_5m")
        if transition.area<=1e-7: failures.append("zero_area_transition")
        if not outer.buffer(1e-7).covers(surface): failures.append("turn_outside_clear_envelope")
        if abs(effective-required_run)>1e-6: failures.append("effective_run_mismatch")
        if best is None: failures.append("maneuvering_field_disconnected_from_ramp_end")
        return failures

    def _parking_and_movement(self,inner,ramp,maneuver,end_edge,heading,parking,width,base):
        field=Polygon(maneuver["local_polygon"]);empty=Polygon()
        options=base._stall_topologies(inner,field,ramp,empty,parking,None)
        count=max((len(o["stalls"]) for o in options),default=0)
        options=[o for o in options if len(o["stalls"])==count]
        if options:
            rank=max(base._parking_rank(o) for o in options);options=[o for o in options if base._parking_rank(o)==rank]
        stalls=options[0]["stalls"] if len(options)==1 else []
        end_mid=LineString(end_edge).centroid;far=field.centroid
        connector=list(maneuver.get("end_to_maneuver_centerline") or [[end_mid.x,end_mid.y]])
        if Point(connector[-1]).distance(far)>self.EPS: connector.append([far.x,far.y])
        main=LineString(connector)
        main_corridor=Polygon(maneuver.get("end_to_maneuver_clearance_corridor") or main.buffer(width/2,cap_style=2,join_style=1).exterior.coords)
        failures=[];stall_paths=[]
        for index,stall in enumerate(stalls):
            occupied=[other for j,other in enumerate(stalls) if j!=index]
            access=stall.boundary.intersection(field.boundary)
            point=access.interpolate(.5,normalized=True) if not access.is_empty else stall.centroid
            branch=LineString([[far.x,far.y],[point.x,point.y]])
            corridor=branch.buffer(width/2,cap_style=2,join_style=1)
            allowed=field.union(stall)
            valid=allowed.buffer(self.EPS).covers(corridor) and not any(corridor.intersection(o).area>self.EPS for o in occupied)
            if not valid: failures.extend(["no_independent_entry_path","no_independent_exit_path","no_return_to_ramp_path"])
            stall_paths.append({"stall_id":f"P-{index+1:02d}","occupied_obstacles":[f"P-{j+1:02d}" for j in range(len(stalls)) if j!=index],
                "stall_entry_path":base._line_coords(branch) if valid else [],"stall_exit_path":list(reversed(base._line_coords(branch))) if valid else [],
                "stall_return_to_ramp_path":list(reversed(base._line_coords(branch)))+list(reversed(base._line_coords(main)))[1:] if valid else [],
                "entry_clearance_valid":valid,"exit_clearance_valid":valid,"return_clearance_valid":valid,
                "clearance_corridor":base._polygon_coords(corridor)})
        if len(stalls)<int(parking["minimum_count"]): failures.append("minimum_independently_usable_stall_count_not_met")
        return stalls,{"contract":"VehicleMovementPathV1","geometry_status":"resolved" if stalls and not failures else "not_feasible",
            "failure_reasons":sorted(set(failures)),"vehicle_main_spine":base._line_coords(main),
            "vehicle_main_spine_length":main.length,"movement_direction":"ramp_end_to_maneuvering_and_return",
            "movement_curve_segments":[],"movement_straight_segments":[base._line_coords(main)],
            "clearance_corridor":base._polygon_coords(main_corridor),"minimum_path_clearance":width,
            "stall_paths":stall_paths,"renderer_authority":"production_contract_only"}

    @staticmethod
    def _centerline_3d(points,leg1,arc,leg2,start_z,slope):
        output=[];cumulative=0.0;previous=None
        for point in points:
            if previous is not None: cumulative+=hypot(point[0]-previous[0],point[1]-previous[1])
            output.append([point[0],point[1],start_z-slope*cumulative]);previous=point
        return output

    @staticmethod
    def _world_direction(direction,frame):
        t,n=frame["tangent"],frame["normal"]
        return [direction[0]*t[0]+direction[1]*n[0],direction[0]*t[1]+direction[1]*n[1]]
