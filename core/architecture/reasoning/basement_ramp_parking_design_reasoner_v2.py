"""Evidence-driven coordinated basement/ramp/parking candidate evaluation V2."""

from __future__ import annotations

from itertools import product
from math import cos, hypot, pi, sin

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


class BasementRampParkingDesignReasonerV2:
    VERSION = "2.0"
    EPS = 1e-7

    def resolve_topology_change_request(self,parcel,frontage,wall_contract,requirements,
                                        obstacle_inventory,request):
        """Evaluate piecewise families only after a proven topology-change request."""
        result={"contract":"PiecewiseRampTopologyEvaluationV1","request":request,
            "status":"pending","candidates":[],"hard_valid_candidates":[],
            "selected_candidate":None,"human_visual_acceptance":"pending"}
        if request.get("contract")!="RampTopologyChangeRequestV1" or request.get("status")!="required":
            result.update({"status":"not_run","reason":"topology_change_request_not_required"})
            return result
        if self._missing(requirements,wall_contract,obstacle_inventory):
            result.update({"status":"pending_requirement","reason":"base_requirement_missing"})
            return result
        slope=float(request["slope"]);levels=requirements["levels"];width=float(requirements["ramp"]["clear_width"])
        total_run=abs(float(levels["basement"])-float(levels["ground"]))/slope
        frame=self._frame(parcel,frontage)
        outer=self._to_local_polygon(wall_contract["outer_face"],frame)
        inner=self._to_local_polygon(wall_contract["inner_face"],frame)
        maneuver=requirements["parking"]["maneuvering_clear_zone"]
        preferred=[float(x) for x in maneuver["preferred"]];minimum=[float(x) for x in maneuver["minimum"]]
        central=inner.buffer(-width);empty=Polygon();evaluated=[]
        generated=self._piecewise_ramp_candidates(inner,outer,slope,total_run,width,minimum)
        for index,ramp in enumerate(generated,1):
            failures=[];turn=self._turn_geometry(ramp,outer,float(levels["ground"]),float(levels["basement"]))
            if not outer.buffer(self.EPS).covers(ramp["local_polygon"]): failures.append("ramp_surface_outside_outer_face_envelope")
            if turn["geometry_status"]!="resolved": failures.extend(turn["failure_reasons"])
            placements=self._maneuver_placements(inner,ramp["end_edge_local"],preferred,minimum,ramp["local_polygon"])
            placement_records=[]
            for placement in placements:
                escape=self._ramp_end_escape(inner,ramp["local_polygon"],ramp["end_edge_local"],
                    ramp["departure_direction_local"],placement["polygon"],width)
                apron=Polygon(escape.get("departure_apron_polygon") or [])
                proof=self._maneuvering_connection_proof(apron,placement["polygon"],width)
                record={"size":placement["size"],"polygon":self._world_polygon(placement["polygon"],frame),
                    "connection_proof":proof,"parking_stalls":[],"vehicle_circulation":None}
                if proof["geometry_status"]=="resolved":
                    aisle=placement["polygon"]
                    options=self._stall_topologies(inner,aisle,ramp["local_polygon"],empty,requirements["parking"],central)
                    if options:
                        count=max(len(o["stalls"]) for o in options);best=[o for o in options if len(o["stalls"])==count]
                        rank=max(self._parking_rank(o) for o in best);best=[o for o in best if self._parking_rank(o)==rank]
                        if len(best)==1:
                            stalls=best[0]["stalls"]
                            circulation=self._vehicle_circulation_spine(inner,ramp["end_edge_local"],escape,
                                placement["polygon"],aisle,stalls)
                            record["parking_stalls"]=[self._world_polygon(s,frame) for s in stalls]
                            record["vehicle_circulation"]=self._world_spine(circulation,frame)
                placement_records.append(record)
            resolved=[p for p in placement_records if p["connection_proof"]["geometry_status"]=="resolved"]
            if not placements: failures.append("no_maneuvering_field_geometrically_available")
            elif not resolved:
                failures.extend(sorted({reason for p in placement_records for reason in p["connection_proof"]["failure_reasons"]}))
            best_placement=max(resolved,key=lambda p:(len(p["parking_stalls"]),p["size"]),default=None)
            if best_placement:
                circulation=best_placement["vehicle_circulation"]
                if len(best_placement["parking_stalls"])<int(requirements["parking"]["minimum_count"]):
                    failures.append("minimum_independently_usable_stall_count_not_met")
                if not circulation or circulation["geometry_status"]!="resolved":
                    failures.append("independent_stall_entry_exit_not_resolved")
            intrusion=ramp["local_polygon"].intersection(central).area if not central.is_empty else 0.0
            remaining=inner.difference(ramp["local_polygon"])
            candidate={"candidate_id":f"PIECEWISE-EVAL-{index:02d}","ramp_id":ramp["ramp_id"],
                "topology":ramp["piecewise_topology"],"slope":slope,"required_total_run":total_run,
                "leg_1_run":ramp["leg1"],"transition_effective_run":ramp["transition_effective_run"],
                "leg_2_run":ramp["leg2"],"total_effective_run":ramp["total_effective_run"],
                "ramp_polygon":self._world_polygon(ramp["local_polygon"],frame),
                "start":self._world(ramp["start_local"],frame),"start_elevation":float(levels["ground"]),
                "end":self._world(ramp["end_local"],frame),"end_elevation":float(levels["basement"]),
                "end_edge":[self._world(p,frame) for p in ramp["end_edge_local"]],
                "turn_geometry":self._world_turn_geometry(turn,frame),"maneuvering_trials":placement_records,
                "best_maneuvering":best_placement,"perimeter_adjacency_ratio":ramp["local_polygon"].intersection(inner.difference(central)).area/max(ramp["local_polygon"].area,self.EPS),
                "central_field_intrusion_area":intrusion,"fragmentation_count":len(getattr(remaining,"geoms",[remaining])),
                "largest_contiguous_remaining_field":max((g.area for g in getattr(remaining,"geoms",[remaining])),default=0.0),
                "failure_reasons":sorted(set(failures)),"geometry_status":"hard_valid" if not failures else "not_feasible"}
            evaluated.append(candidate)
        valid=[c for c in evaluated if c["geometry_status"]=="hard_valid"]
        result["candidates"]=evaluated;result["hard_valid_candidates"]=[c["candidate_id"] for c in valid]
        if not valid:
            result.update({"status":"unresolved_no_feasible_piecewise_topology",
                "first_proven_boundary":next((r for c in evaluated for r in c["failure_reasons"]),"no_piecewise_candidate_generated")})
            return result
        rank=lambda c:(len(c["best_maneuvering"]["parking_stalls"]),c["largest_contiguous_remaining_field"],
            -c["central_field_intrusion_area"],c["perimeter_adjacency_ratio"],-c["fragmentation_count"])
        best=max(rank(c) for c in valid);winners=[c for c in valid if rank(c)==best]
        result["status"]="resolved_unique" if len(winners)==1 else "pending_tie"
        result["selected_candidate"]=winners[0] if len(winners)==1 else None
        return result

    def design(self, parcel, frontage, wall_contract, requirements, obstacle_inventory,
               core_placement_candidates=None, allow_selection=True):
        result = {
            "contract": "BasementRampParkingDesignContractV2",
            "version": self.VERSION,
            "status": "pending_requirement",
            "core_sizing": None,
            "candidates": [],
            "selected_candidate": None,
            "selection_status": "pending",
            "automated_geometry_pass": False,
            "human_visual_acceptance": "pending",
            "ramp_topology_decisions": [],
            "optional_entrance_transition": {"contract":"RampEntranceTransitionRequirementV1",
                "allowable_slope_range":[0.005,0.01],"entrance_transition_length":None,
                "geometry_status":"pending_requirement","unresolved_evidence":["entrance_transition_length"],
                "blocks_continuous_ramp_evaluation":False},
            "unresolved_evidence": [],
        }
        missing = self._missing(requirements, wall_contract, obstacle_inventory)
        if missing:
            result["unresolved_evidence"] = missing
            return result

        if core_placement_candidates is not None:
            core = {
                "contract": "CoreSpaceReservationProxyContractV1",
                "geometry_status": "resolved",
                "missing_dimensions": [],
                "configurations": [],
                "evidence_used": requirements["core"].get("evidence_used", []),
                "shape_proxy": True,
                "final_geometry": False,
            }
        else:
            core = self._core_contract(requirements["core"])
        result["core_sizing"] = core
        if core["geometry_status"] != "resolved":
            result["unresolved_evidence"] = core["missing_dimensions"]
            return result

        frame = self._frame(parcel, frontage)
        outer = self._to_local_polygon(wall_contract["outer_face"], frame)
        inner = self._to_local_polygon(wall_contract["inner_face"], frame)
        u_min, v_min, u_max, v_max = inner.bounds
        ramp = requirements["ramp"]
        width = float(ramp["clear_width"])
        delta_z = float(requirements["levels"]["basement"])-float(requirements["levels"]["ground"])
        slopes = [float(value) for value in ramp.get("allowable_slope_candidates", [ramp["maximum_longitudinal_slope"]])]
        maneuver = requirements["parking"]["maneuvering_clear_zone"]
        preferred = [float(x) for x in maneuver["preferred"]]
        minimum = [float(x) for x in maneuver["minimum"]]
        central_field = inner.buffer(-width)
        perimeter_band = inner.difference(central_field)
        ramp_candidates = []
        for slope in slopes:
            run = abs(delta_z)/slope
            start_interval = self._horizontal_interval(outer, 0.0)
            end_interval = self._horizontal_interval(outer, run)
            if start_interval and end_interval:
                feasible = [max(start_interval[0],end_interval[0])+width/2,
                            min(start_interval[1],end_interval[1])-width/2]
                if feasible[0] <= feasible[1]+self.EPS:
                    for side, center_u in zip(("A","B"), feasible):
                        polygon=box(center_u-width/2,0,center_u+width/2,run)
                        ramp_candidates.append({"ramp_id":f"STRAIGHT-{int(round(slope*100))}-{side}",
                            "family":"straight","slope":slope,"run":run,"width":width,"center_u":center_u,
                            "local_polygon":polygon,"start_local":[center_u,0.0],"end_local":[center_u,run],
                            "end_edge_local":[[center_u-width/2,run],[center_u+width/2,run]],
                            "departure_direction_local":[0.0,1.0],
                            "transition_polygon":None,"placement_evidence":"feasible_interval_boundary_event"})
        # Turned families are downstream alternatives, generated only when the
        # complete connected straight-maneuvering search for that slope fails.
        slopes_requiring_turn=set()
        for slope in slopes:
            straight=[r for r in ramp_candidates if r["family"]=="straight" and abs(r["slope"]-slope)<=self.EPS]
            connected=False
            for item in straight:
                placements=self._maneuver_placements(inner,item["end_edge_local"],preferred,minimum,item["local_polygon"])
                if any(self._ramp_end_escape(inner,item["local_polygon"],item["end_edge_local"],
                       item["departure_direction_local"],p["polygon"],width)["geometry_status"]=="resolved" for p in placements):
                    connected=True;break
            if not connected: slopes_requiring_turn.add(slope)
        for slope in sorted(slopes_requiring_turn):
            ramp_candidates.extend(self._piecewise_ramp_candidates(
                inner,outer,slope,abs(delta_z)/slope,width,minimum))

        core_placements = []
        if core_placement_candidates is not None:
            for item in core_placement_candidates:
                if not isinstance(item, dict) or item.get("selection") is not False:
                    continue
                if item.get("shape_proxy") is not True or item.get("final_geometry") is not False:
                    continue
                world_polygon = Polygon(item.get("polygon") or [])
                if world_polygon.is_valid and world_polygon.area > self.EPS:
                    local_polygon = self._to_local_polygon(
                        list(world_polygon.exterior.coords)[:-1], frame)
                    if inner.buffer(self.EPS).covers(local_polygon):
                        core_placements.append({
                            "core_id": item.get("candidate_id"),
                            "configuration_id": "EXTERNAL_SPACE_RESERVATION_PROXY",
                            "local_polygon": local_polygon,
                            "assumption_contract": item.get("assumption_contract"),
                            "authority_class": item.get("authority_class"),
                            "shape_proxy": True,
                            "final_geometry": False,
                        })
            if not core_placements:
                result["unresolved_evidence"] = ["valid_external_core_reservation_candidate"]
                return result
        else:
            for configuration in core["configurations"]:
                width_c, depth_c = configuration["minimum_width"], configuration["minimum_depth"]
                anchors = [
                    (u_min, v_min), (u_max-width_c, v_min),
                    (u_min, v_max-depth_c), (u_max-width_c, v_max-depth_c),
                ]
                for anchor_index, (u, v) in enumerate(anchors, 1):
                    polygon = Polygon([[u,v],[u+width_c,v],[u+width_c,v+depth_c],[u,v+depth_c]])
                    core_placements.append({
                        "core_id": f"{configuration['configuration_id']}-P{anchor_index}",
                        "configuration_id": configuration["configuration_id"],
                        "local_polygon": polygon,
                    })

        candidates = []
        number = 0
        for ramp_candidate, core_candidate in product(ramp_candidates, core_placements):
            ramp_polygon = ramp_candidate["local_polygon"]
            end = ramp_candidate["end_local"]
            placements=self._maneuver_placements(inner,ramp_candidate["end_edge_local"],preferred,minimum,ramp_polygon)
            old_serial=box(end[0]-minimum[0]/2,end[1],end[0]+minimum[0]/2,end[1]+minimum[1])
            if not placements:
                placements=[{"polygon":old_serial,"size":minimum,"status":"not_feasible","placement_role":"old_serial_diagnostic"}]
            for placement in placements:
              for aisle in self._vehicle_aisle_fields(inner,placement["polygon"],ramp_polygon):
                number += 1
                maneuvering=placement["polygon"]
                failures=[]
                if not outer.buffer(self.EPS).covers(ramp_polygon): failures.append("ramp_surface_outside_outer_face_envelope")
                if placement["status"] != "resolved": failures.append("no_connected_maneuvering_placement")
                if ramp_polygon.intersection(core_candidate["local_polygon"]).area > self.EPS: failures.append("ramp_conflicts_core_candidate")
                if maneuvering.intersection(core_candidate["local_polygon"]).area > self.EPS: failures.append("maneuvering_zone_conflicts_core_candidate")
                if aisle.intersection(core_candidate["local_polygon"]).area > self.EPS: failures.append("core_blocks_vehicle_circulation_spine")
                escape=self._ramp_end_escape(inner,ramp_polygon,ramp_candidate["end_edge_local"],
                                             ramp_candidate["departure_direction_local"],maneuvering,width)
                if escape["geometry_status"] != "resolved": failures.extend(escape["failure_reasons"])
                stall_options=self._stall_topologies(inner,aisle,ramp_polygon,core_candidate["local_polygon"],requirements["parking"],central_field)
                best_count=max((len(option["stalls"]) for option in stall_options),default=0)
                best_stalls=[option for option in stall_options if len(option["stalls"])==best_count]
                if best_stalls:
                    best_rank=max(self._parking_rank(option) for option in best_stalls)
                    best_stalls=[option for option in best_stalls if self._parking_rank(option)==best_rank]
                stalls=best_stalls[0]["stalls"] if len(best_stalls)==1 else []
                stall_evidence=best_stalls[0]["evidence"] if len(best_stalls)==1 else []
                if best_count < int(requirements["parking"]["minimum_count"]): failures.append("minimum_independently_usable_stall_count_not_met")
                elif len(best_stalls)>1: failures.append("parking_stall_topology_pending_tie")
                circulation=self._vehicle_circulation_spine(inner,ramp_candidate["end_edge_local"],
                    escape,maneuvering,aisle,stalls)
                if stalls and circulation["geometry_status"] != "resolved": failures.extend(circulation["failure_reasons"])
                if stall_options: failures.append("pedestrian_protected_route_not_yet_resolved")
                transition=ramp_candidate.get("transition_polygon")
                turn_geometry=self._turn_geometry(ramp_candidate,outer,float(requirements["levels"]["ground"]),float(requirements["levels"]["basement"]))
                if ramp_candidate["family"]=="l_shaped" and turn_geometry["geometry_status"]!="resolved":
                    failures.extend(turn_geometry["failure_reasons"])
                surface=self._surface_3d(ramp_candidate,frame,float(requirements["levels"]["ground"]),float(requirements["levels"]["basement"]))
                semantic_edges=self._ramp_semantic_edges(ramp_candidate,frame,surface,
                    float(requirements["levels"]["ground"]),float(requirements["levels"]["basement"]))
                if semantic_edges["status"] != "resolved": failures.append("ramp_start_end_semantic_binding_unresolved")
                if surface["geometry_status"] != "candidate": failures.append("ramp_surface_3d_unresolved")
                ramp_intrusion=ramp_polygon.area
                central_intrusion=(ramp_polygon.intersection(central_field).area
                                   if not central_field.is_empty else 0.0)
                perimeter_area=ramp_polygon.intersection(perimeter_band).area
                perimeter_ratio=perimeter_area/ramp_intrusion if ramp_intrusion>self.EPS else 0.0
                remaining=max(0.0,v_max-max(point[1] for point in ramp_candidate["end_edge_local"]))
                usable=inner.difference(ramp_polygon.union(maneuvering).union(core_candidate["local_polygon"]))
                components={"valid_stall_count":len(stalls),"vehicle_movement_resolved":bool(stalls),
                    "pedestrian_resolved":False,"contiguous_usable_area":max((g.area for g in getattr(usable,"geoms",[usable])),default=0.0),
                    "ramp_intrusion_area":ramp_intrusion,"fragment_count":len(getattr(usable,"geoms",[usable])),
                    "central_field_intrusion_area":central_intrusion,"perimeter_adjacency_ratio":perimeter_ratio,
                    "core_impact_area":core_candidate["local_polygon"].area,"structural_compatibility":True}
                candidate = {
                "candidate_id": f"BASEMENT-V2-{number:02d}",
                "ramp_id": ramp_candidate["ramp_id"],
                "ramp": {
                    "start": self._world(ramp_candidate["start_local"], frame),
                    "end": self._world(ramp_candidate["end_local"], frame),
                    "polygon": self._world_polygon(ramp_polygon, frame),
                    "width": width, "run": ramp_candidate["run"],
                    "family": ramp_candidate["family"],
                    "start_elevation": float(requirements["levels"]["ground"]),
                    "end_elevation": float(requirements["levels"]["basement"]),
                    "slope": ramp_candidate["slope"],
                    "headroom": float(ramp["required_headroom"]),
                    "surface_3d": surface,
                    "transition_polygon": self._world_polygon(transition,frame) if transition else None,
                    "turn_geometry":self._world_turn_geometry(turn_geometry,frame),
                    "start_edge": [self._world([ramp_candidate["center_u"]-width/2,0],frame),self._world([ramp_candidate["center_u"]+width/2,0],frame)],
                    "end_edge": [self._world(point,frame) for point in ramp_candidate["end_edge_local"]],
                    "direction": [self._world(ramp_candidate["end_local"],frame)[0]-self._world(ramp_candidate["start_local"],frame)[0],self._world(ramp_candidate["end_local"],frame)[1]-self._world(ramp_candidate["start_local"],frame)[1]],
                    "semantic_edges": semantic_edges,
                    "remaining_longitudinal_depth": remaining,
                    "lateral_clear_width": u_max-u_min-width,
                },
                "core": {
                    "core_id": core_candidate["core_id"],
                    "configuration_id": core_candidate["configuration_id"],
                    "polygon": self._world_polygon(core_candidate["local_polygon"], frame),
                },
                "maneuvering_envelope": self._world_polygon(maneuvering, frame),
                "searchable_arrival_region": self._world_polygon(inner,frame),
                "generated_maneuvering_placements": len(placements),
                "old_invalid_serial_maneuvering_polygon": self._world_polygon(old_serial,frame),
                "parking_aisle": self._world_polygon(aisle,frame),
                "parking_stalls": [self._world_polygon(stall,frame) for stall in stalls],
                "parking_stall_evidence": stall_evidence,
                "ramp_end_escape": self._world_escape(escape,frame),
                "vehicle_circulation_spine": self._world_spine(circulation,frame),
                "pedestrian_connection": None, "ramp_slab_void": None,
                "parking_architectural_intelligence": {"contract":"ParkingArchitecturalIntelligenceContractV1",
                    "vehicle_access_chain":"candidate","maneuvering_aisle_shared":maneuvering.equals(aisle),
                    "stall_entry_exit_status":"topology_clearance" if stalls and escape["geometry_status"]=="resolved" else "unresolved",
                    "vehicle_path_validation_level":"topology_clearance",
                    "valid_stall_count":len(stalls),"minimum_required":requirements["parking"]["minimum_count"],
                    "wall_side_clearance_policy":{"unconstrained_width":2.5,"one_constrained_side_width":2.75,
                        "two_constrained_sides_width":3.0,"grouped_stalls_share_internal_boundary":True,
                        "source":"user_project_requirement"},
                    "pedestrian_access_status":"pending_core_lobby_interface"},
                "structural_compatibility_reservation": self._structural_reservation(inner,core_candidate["local_polygon"],frame),
                "ramp_central_field_preservation": {"contract":"RampCentralFieldPreservationV1",
                    "central_field_polygon":self._world_polygon(central_field,frame) if not central_field.is_empty else [],
                    "perimeter_band_source":"inner_clear_face_minus_ramp_width_inward_buffer",
                    "ramp_intrusion_area":ramp_intrusion,"central_field_intersection_area":central_intrusion,
                    "perimeter_adjacency_ratio":perimeter_ratio,
                    "fragmentation_count":components["fragment_count"],
                    "largest_remaining_contiguous_field":components["contiguous_usable_area"],
                    "critical_penalty":ramp_candidate["family"]=="l_shaped" and central_intrusion>self.EPS},
                "maneuvering_clear_zone_contract": {"contract":"ManeuveringClearZoneContractV1",
                    "preferred_size":preferred,"minimum_size":minimum,"selected_size":placement["size"],"polygon":self._world_polygon(maneuvering,frame),
                    "placement_role":placement["placement_role"],"aisle_overlap":True,
                    "turning_radius_evidence":requirements["parking"].get("minimum_turning_radius"),
                    "mandatory_turning_circle":False,"geometry_status":"not_feasible" if failures else "candidate"},
                "rejection_reasons": failures,
                "geometry_status": "not_feasible" if failures else "candidate",
                "candidate_score": 100.0 - 25.0*len(failures) - central_intrusion,
                "score_components": components,
                "source_evidence": [
                    "frontage_interval_boundary_event", "derived_ramp_run",
                    "resolved_core_configuration", "polygonal_maneuvering_clear_zone",
                ],
                }
                candidates.append(candidate)

        result["candidates"] = candidates
        result["ramp_topology_decisions"] = self._topology_decisions(candidates,preferred,minimum)
        feasible = [candidate for candidate in candidates if candidate["geometry_status"] == "candidate"]
        if not feasible:
            result.update({
                "status": "not_feasible",
                "selection_status": "unresolved_no_feasible_solution",
                "unresolved_evidence": sorted({
                    reason for candidate in candidates for reason in candidate["rejection_reasons"]
                }),
                "diagnostic": {
                    "basement_inner_clear_width": u_max-u_min,
                    "maneuvering_preferred_size": preferred,
                    "maneuvering_minimum_size": minimum,
                    "mandatory_turning_circle": False,
                    "first_proven_boundary": "ramp_end_escape_or_downstream_pedestrian_core_chain",
                },
            })
            return result
        if allow_selection is False:
            result.update({
                "status": "candidates_produced",
                "selection_status": "not_performed",
                "selected_candidate": None,
                "automated_geometry_pass": True,
                "unresolved_evidence": sorted({
                    reason for candidate in candidates
                    for reason in candidate["rejection_reasons"]
                }),
            })
            return result
        def architectural_rank(candidate):
            score=candidate["score_components"]
            return (score["valid_stall_count"],score["pedestrian_resolved"],
                    score["contiguous_usable_area"],-score["central_field_intrusion_area"],
                    -score["ramp_intrusion_area"],-score["fragment_count"])
        best = max(architectural_rank(candidate) for candidate in feasible)
        winners = [candidate for candidate in feasible if architectural_rank(candidate)==best]
        if len(winners) != 1:
            result.update({"status": "pending_tie", "selection_status": "pending_tie",
                           "unresolved_evidence": ["decisive_candidate_evidence"]})
            return result
        result.update({"status": "resolved", "selection_status": "resolved",
                       "selected_candidate": winners[0], "automated_geometry_pass": True,
                       "unresolved_evidence": []})
        return result

    def _topology_decisions(self,candidates,preferred,minimum):
        """Separate forward depth from proven lateral-connected maneuvering."""
        decisions=[]
        slopes=sorted({c["ramp"]["slope"] for c in candidates})
        for slope in slopes:
            straight=[c for c in candidates if c["ramp"]["family"]=="straight" and abs(c["ramp"]["slope"]-slope)<=self.EPS]
            connected=[c for c in straight if c["ramp_end_escape"]["geometry_status"]=="resolved"]
            preferred_ok=any(c["maneuvering_clear_zone_contract"]["selected_size"]==preferred for c in connected)
            minimum_ok=any(c["maneuvering_clear_zone_contract"]["selected_size"]==minimum for c in connected)
            if preferred_ok: status="preferred_maneuvering_resolved"
            elif minimum_ok: status="minimum_maneuvering_resolved"
            else: status="maneuvering_requires_topology_change"
            l_alternatives=sorted({c["ramp_id"] for c in candidates
                if c["ramp"]["family"]=="l_shaped" and abs(c["ramp"]["slope"]-slope)<=self.EPS})
            decision={"contract":"RampTopologyDecisionContractV1","slope":slope,
                "straight_run":straight[0]["ramp"]["run"] if straight else None,
                "direct_remaining_depth":max((c["ramp"]["remaining_longitudinal_depth"] for c in straight),default=None),
                "lateral_connected_maneuvering_searched":True,"maneuvering_status":status,
                "connected_straight_candidate_count":len(connected),"turned_alternatives":l_alternatives,
                "topology_change_request":None}
            if status=="maneuvering_requires_topology_change":
                decision["topology_change_request"]={"contract":"RampTopologyChangeRequestV1",
                    "reason":"insufficient_post_ramp_maneuvering_depth",
                    "required_topology_search":["l_shaped","perimeter_turn"],
                    "source_evidence":"straight_end_connected_maneuvering_search_exhausted"}
            decisions.append(decision)
        return decisions

    def _piecewise_ramp_candidates(self,inner,outer,slope,total_run,width,minimum):
        """Generate perimeter-derived two-leg topologies with explicit transition run."""
        u_min,_,u_max,v_max=inner.bounds;transition_run=width*(2.0**0.5)
        available=max(0.0,total_run-transition_run);events=sorted({available/2,max(width,available-width)})
        candidates=[]
        for topology in ("perimeter_turn","dog_leg"):
            for turn_index,leg1 in enumerate(events,1):
                leg2=available-leg1
                if leg1<=self.EPS or leg2<=self.EPS or leg1+width>v_max: continue
                for side in ("left","right"):
                    start_u=u_min+width/2 if side=="left" else u_max-width/2;direction=1 if side=="left" else -1
                    exit_u=start_u+direction*width;end_u=exit_u+direction*leg2;exit_v=leg1+width
                    transition=box(min(start_u,exit_u)-width/2,leg1,
                                   max(start_u,exit_u)+width/2,leg1+width)
                    leg_a=box(start_u-width/2,0,start_u+width/2,leg1)
                    leg_b=box(min(exit_u,end_u),exit_v-width/2,max(exit_u,end_u),exit_v+width/2)
                    polygon=unary_union([leg_a,transition,leg_b])
                    path=[[start_u,leg1],[start_u,leg1+width*.25],
                          [exit_u-direction*width*.25,leg1+width*.75],[exit_u,exit_v]]
                    candidates.append({"ramp_id":f"PIECEWISE-{int(round(slope*100))}-{topology}-{side}-T{turn_index}",
                        "family":"l_shaped","piecewise_topology":topology,"slope":slope,"run":total_run,
                        "required_total_run":total_run,"leg1":leg1,"transition_effective_run":transition_run,"leg2":leg2,
                        "total_effective_run":leg1+transition_run+leg2,"width":width,"center_u":start_u,
                        "local_polygon":polygon,"start_local":[start_u,0.0],"end_local":[end_u,exit_v],
                        "end_edge_local":[[end_u,exit_v-width/2],[end_u,exit_v+width/2]],
                        "departure_direction_local":[direction,0.0],"incoming_direction_local":[0.0,1.0],
                        "outgoing_direction_local":[direction,0.0],"transition_center_path_local":path,
                        "transition_polygon":transition,"placement_evidence":"perimeter_interval_and_run_partition_event"})
        return candidates

    def _core_contract(self, core):
        stair = core["stair_reserved_zone"]
        shaft = core["elevator_shaft_clear"]
        wall = float(core["enclosure_wall_thickness"])
        elevator_external_width = float(shaft[0]) + wall
        elevator_external_depth = float(shaft[1]) + 2.0*wall
        configurations = [
            {"configuration_id": "CORE-SIDE-BY-SIDE", "minimum_width": float(stair[0])+elevator_external_width,
             "minimum_depth": max(float(stair[1]), elevator_external_depth+float(core["lobby_clear"][1]))},
            {"configuration_id": "CORE-SIDE-BY-SIDE-ROTATED", "minimum_width": max(float(stair[1]), elevator_external_depth+float(core["lobby_clear"][1])),
             "minimum_depth": float(stair[0])+elevator_external_width},
        ]
        feasible = [item for item in configurations
                    if item["minimum_width"] <= float(core["maximum_width"])+self.EPS
                    and item["minimum_depth"] <= float(core["maximum_depth"])+self.EPS]
        return {
            "contract": "CoreSizingContractV1", "minimum_width": min((x["minimum_width"] for x in feasible), default=None),
            "minimum_depth": min((x["minimum_depth"] for x in feasible), default=None),
            "maximum_width": core["maximum_width"], "maximum_depth": core["maximum_depth"],
            "stair_reserved_zone": stair, "elevator_reserved_zone": shaft,
            "lobby_reserved_zone": core["lobby_clear"], "wall_enclosure_allowance": wall,
            "configurations": feasible, "geometry_status": "resolved" if feasible else "unresolved",
            "missing_dimensions": [] if feasible else ["core_configuration_within_maximum_envelope"],
            "evidence_used": core.get("evidence_used", []),
        }

    @staticmethod
    def _missing(requirements, wall, inventory):
        missing = []
        for key in ("levels", "ramp", "parking", "core"):
            if not isinstance(requirements.get(key), dict): missing.append(key)
        if not isinstance(wall, dict) or not wall.get("outer_face") or not wall.get("inner_face"):
            missing.append("physical_wall_face_contract")
        if inventory.get("inventory_status") not in ("complete_empty", "complete_with_obstacles"):
            missing.append("complete_fixed_obstacle_inventory")
        return missing

    @staticmethod
    def _frame(parcel, frontage):
        a, b = frontage
        length = hypot(b[0]-a[0], b[1]-a[1])
        tangent = [(b[0]-a[0])/length, (b[1]-a[1])/length]
        normals = [[-tangent[1], tangent[0]], [tangent[1], -tangent[0]]]
        centroid = [sum(p[0] for p in parcel)/len(parcel), sum(p[1] for p in parcel)/len(parcel)]
        normal = max(normals, key=lambda n: (centroid[0]-a[0])*n[0]+(centroid[1]-a[1])*n[1])
        return {"origin": list(a), "tangent": tangent, "normal": normal}

    @staticmethod
    def _world(point, frame):
        a, t, n = frame["origin"], frame["tangent"], frame["normal"]
        return [a[0]+point[0]*t[0]+point[1]*n[0], a[1]+point[0]*t[1]+point[1]*n[1]]

    def _local(self, point, frame):
        dx, dy = point[0]-frame["origin"][0], point[1]-frame["origin"][1]
        return [dx*frame["tangent"][0]+dy*frame["tangent"][1],
                dx*frame["normal"][0]+dy*frame["normal"][1]]

    def _to_local_polygon(self, points, frame):
        return Polygon([self._local(point, frame) for point in points])

    def _world_polygon(self, polygon, frame):
        return [self._world(point, frame) for point in list(polygon.exterior.coords)[:-1]]

    def _turn_geometry(self,candidate,envelope,start_z,end_z):
        if candidate["family"]!="l_shaped":
            return {"contract":"RampTurnGeometryContractV1","geometry_status":"not_applicable",
                    "failure_reasons":[],"turn_validation_level":"not_applicable"}
        transition=candidate.get("transition_polygon");width=float(candidate["width"]);failures=[]
        if transition is None or transition.area<=self.EPS: failures.append("zero_area_transition")
        if transition is not None and not envelope.buffer(self.EPS).covers(transition): failures.append("turn_outside_clear_envelope")
        minimum_width=min(transition.bounds[2]-transition.bounds[0],transition.bounds[3]-transition.bounds[1]) if transition else 0.0
        if minimum_width+self.EPS<width: failures.append("turn_width_below_required_ramp_width")
        path=candidate.get("transition_center_path_local",[])
        if len(path)<4 or LineString(path).length<=self.EPS: failures.append("turn_vehicle_path_not_resolved")
        if candidate["local_polygon"].geom_type not in ("Polygon","MultiPolygon"): failures.append("disconnected_ramp_legs")
        transition_run=float(candidate.get("transition_effective_run",width))
        ratio_entry=max(0.0,min(1.0,candidate["leg1"]/candidate["run"]))
        ratio_exit=max(0.0,min(1.0,(candidate["leg1"]+transition_run)/candidate["run"]))
        coords=list(transition.exterior.coords)[:-1] if transition else []
        return {"contract":"RampTurnGeometryContractV1","geometry_status":"resolved" if not failures else "not_feasible",
            "failure_reasons":failures,"turn_validation_level":"topology_clearance",
            "incoming_leg_direction":candidate.get("incoming_direction_local"),
            "outgoing_leg_direction":candidate.get("outgoing_direction_local"),"full_clear_width":width,
            "inner_turn_boundary":coords[:2],"outer_turn_boundary":coords[2:] if len(coords)>=4 else [],
            "transition_polygon":coords,"minimum_usable_width":minimum_width,
            "leg_continuity":not failures,"vehicle_path_continuity":bool(path) and not failures,
            "transition_center_path":path,
            "effective_transition_run":transition_run,
            "transition_entry_elevation":start_z+(end_z-start_z)*ratio_entry,
            "transition_exit_elevation":start_z+(end_z-start_z)*ratio_exit}

    def _world_turn_geometry(self,turn,frame):
        output=dict(turn)
        for key in ("inner_turn_boundary","outer_turn_boundary","transition_polygon","transition_center_path"):
            if output.get(key): output[key]=[self._world(point,frame) for point in output[key]]
        for key in ("incoming_leg_direction","outgoing_leg_direction"):
            d=output.get(key)
            if d: output[key]=[d[0]*frame["tangent"][0]+d[1]*frame["normal"][0],d[0]*frame["tangent"][1]+d[1]*frame["normal"][1]]
        return output

    def _surface_3d(self, candidate, frame, start_z, end_z):
        if candidate["family"] == "straight":
            points=list(candidate["local_polygon"].exterior.coords)[:-1]
            vertices=[]
            for point in points:
                ratio=max(0.0,min(1.0,point[1]/candidate["run"]))
                world=self._world(point,frame); vertices.append([world[0],world[1],start_z+(end_z-start_z)*ratio])
            return {"vertices":vertices,"faces":[[0,1,2],[0,2,3]],"geometry_status":"candidate"}
        return {"vertices":[],"faces":[],"geometry_status":"pending_piecewise_surface"}

    def _ramp_semantic_edges(self,candidate,frame,surface,start_z,end_z):
        half=float(candidate["width"])/2
        start_edge=[self._world([candidate["center_u"]-half,0],frame),self._world([candidate["center_u"]+half,0],frame)]
        end_edge=[self._world(point,frame) for point in candidate["end_edge_local"]]
        if surface["geometry_status"] != "candidate":
            return {"status":"pending_surface","start_edge":start_edge,"end_edge":end_edge,
                    "start_z":start_z,"end_z":end_z}
        vertices=surface["vertices"]
        start_vertices=[v for v in vertices if abs(v[2]-start_z)<=self.EPS]
        end_vertices=[v for v in vertices if abs(v[2]-end_z)<=self.EPS]
        valid=len(start_vertices)==2 and len(end_vertices)==2 and start_z>end_z
        return {"status":"resolved" if valid else "unresolved","start_edge":start_edge,"end_edge":end_edge,
                "start_vertices":start_vertices,"end_vertices":end_vertices,"start_z":start_z,"end_z":end_z,
                "descent_direction":"road_to_basement"}

    def _structural_reservation(self,inner,core,frame):
        points=list(inner.exterior.coords)[:-1]
        return {"contract":"StructuralCompatibilityReservationV1","status":"candidate_reservation_only",
                "physical_columns":[],"physical_beams":[],
                "perimeter_support_lines":[[self._world(a,frame),self._world(b,frame)] for a,b in zip(points,points[1:]+points[:1])],
                "core_support_zone":self._world_polygon(core,frame),
                "exclusion_roles":["vehicle_path","ramp","maneuvering_aisle","stall_access","pedestrian_route"]}

    def _maneuver_placements(self, inner, end_edge, preferred, minimum, ramp_polygon):
        """Return geometry-event placements touching the ramp arrival interface."""
        u0,v0,u1,v1=inner.bounds; edge=LineString(end_edge)
        placements=[]
        for size in (preferred, minimum):
            w,d=size
            xs={u0,u1-w,end_edge[0][0]-w,end_edge[0][0],end_edge[1][0]-w,end_edge[1][0]}
            ys={v0,v1-d,end_edge[0][1]-d,end_edge[0][1],end_edge[1][1]-d,end_edge[1][1]}
            for x in sorted(xs):
                for y in sorted(ys):
                    polygon=box(x,y,x+w,y+d)
                    if not inner.buffer(self.EPS).covers(polygon): continue
                    if polygon.distance(edge)>self.EPS: continue
                    if polygon.intersection(ramp_polygon).area>self.EPS: continue
                    placements.append({"polygon":polygon,"size":[w,d],"status":"resolved",
                        "placement_role":"lateral_or_arrival_interface_event"})
            if placements: break
        unique={tuple(round(v,7) for v in item["polygon"].bounds):item for item in placements}
        return [unique[key] for key in sorted(unique)]

    def _vehicle_aisle_fields(self,inner,maneuvering,ramp):
        """Expand the END-connected maneuvering field laterally at geometry events."""
        u0,_,u1,_=inner.bounds; x0,y0,x1,y1=maneuvering.bounds
        fields=[maneuvering]
        lateral=inner.intersection(box(u0,y0,u1,y1))
        if lateral.geom_type=="Polygon" and lateral.intersection(ramp).area<=self.EPS:
            fields.append(lateral)
        unique={tuple(round(v,7) for v in field.bounds):field for field in fields}
        return [unique[key] for key in sorted(unique)]

    def _stall_topologies(self, inner, aisle, ramp, core, parking, central_field=None):
        """Generate complete edge bands; capacity is discovered, never capped at two."""
        sw,sd=float(parking["stall_width"]),float(parking["stall_depth"])
        x0,y0,x1,y1=aisle.bounds; options=[]
        definitions=[("north",x0,x1,y1,1), ("south",x0,x1,y0,-1),
                     ("east",y0,y1,x1,1), ("west",y0,y1,x0,-1)]
        for side,a0,a1,edge,sign in definitions:
            count=int((a1-a0+self.EPS)//sw)
            stalls=[]; evidence=[]
            for index in range(count):
                a=a0+index*sw
                stall=(box(a,edge,a+sw,edge+sd) if side=="north" else
                       box(a,edge-sd,a+sw,edge) if side=="south" else
                       box(edge,a,edge+sd,a+sw) if side=="east" else box(edge-sd,a,edge,a+sw))
                if not inner.buffer(self.EPS).covers(stall): continue
                if stall.intersection(ramp).area>self.EPS or stall.intersection(core).area>self.EPS: continue
                # Its complete access edge must touch the shared maneuver/aisle field.
                contact=stall.boundary.intersection(aisle.boundary).length
                if contact+self.EPS < sw: continue
                left_wall=stall.boundary.distance(inner.boundary)<=self.EPS and index==0
                right_wall=stall.boundary.distance(inner.boundary)<=self.EPS and index==count-1
                required=self._required_stall_width(sw,left_wall,right_wall)
                if required>sw+self.EPS: continue
                stalls.append(stall)
                evidence.append({"stall_index":len(stalls)+1,"base_width":sw,
                    "left_side_condition":"wall" if left_wall else "open",
                    "right_side_condition":"wall" if right_wall else "open",
                    "left_clearance_addition":0.25 if left_wall else 0.0,
                    "right_clearance_addition":0.25 if right_wall else 0.0,
                    "resolved_required_width":required,"resolved_depth":sd,
                    "access_edge_contact_length":contact,"usability_status":"topology_clearance"})
            if stalls:
                occupied=unary_union(stalls)
                central_intrusion=occupied.intersection(central_field).area if central_field is not None else 0.0
                perimeter_contact=occupied.boundary.intersection(inner.boundary).length
                usable=inner.difference(occupied)
                options.append({"stalls":stalls,"evidence":evidence,"aisle_side":side,
                    "perimeter_adjacency_ratio":perimeter_contact/max(occupied.length,self.EPS),
                    "central_field_intrusion_area":central_intrusion,
                    "remaining_contiguous_vehicle_field":max((g.area for g in getattr(usable,"geoms",[usable])),default=0.0),
                    "dead_strip_area":max(0.0,inner.area-usable.area-occupied.area)})
        return options

    @staticmethod
    def _parking_rank(option):
        return (option["perimeter_adjacency_ratio"],-option["central_field_intrusion_area"],
                option["remaining_contiguous_vehicle_field"],-option["dead_strip_area"])

    def _vehicle_circulation_spine(self,inner,end_edge,escape,maneuvering,aisle,stalls):
        """Validate every stall with all other stalls occupied at topology-clearance level."""
        apron=Polygon(escape.get("departure_apron_polygon") or [])
        field=unary_union([maneuvering,aisle,apron]).intersection(inner)
        end_line=LineString(end_edge); failures=[]; stall_results=[]; paths=[]
        if field.is_empty or not field.intersects(end_line): failures.append("maneuvering_field_disconnected_from_ramp_end")
        for index,stall in enumerate(stalls):
            occupied=[other for i,other in enumerate(stalls) if i!=index]
            access=stall.boundary.intersection(aisle.boundary)
            access_point=access.interpolate(.5,normalized=True) if not access.is_empty else stall.centroid
            end_mid=end_line.interpolate(.5,normalized=True); hub=maneuvering.representative_point()
            alternatives=[LineString([end_mid,access_point]),
                LineString([end_mid,[end_mid.x,hub.y],[access_point.x,hub.y],access_point]),
                LineString([end_mid,[hub.x,end_mid.y],[hub.x,access_point.y],access_point])]
            valid=[]
            allowed=field.union(stall)
            for path in alternatives:
                if allowed.buffer(self.EPS).covers(path) and not any(path.intersection(other).length>self.EPS for other in occupied): valid.append(path)
            ok=bool(valid)
            if not ok:
                failures.extend(["no_independent_entry_path","no_independent_exit_path","stall_requires_other_stall_to_be_empty"])
            else: paths.append(valid[0])
            stall_results.append({"stall_index":index+1,"other_stalls_treated_as_occupied":True,
                "incoming_path_exists":ok,"outgoing_path_exists":ok,"return_to_ramp_path_exists":ok,
                "path":self._line_coords(valid[0]) if ok else []})
        if stalls and len(paths)!=len(stalls): failures.append("stall_blocks_vehicle_circulation")
        return {"contract":"VehicleCirculationSpineV1","geometry_status":"resolved" if stalls and not failures else "not_feasible",
            "failure_reasons":sorted(set(failures)),"vehicle_spine_polygon":self._polygon_coords(field),
            "vehicle_spine_center_paths":[self._line_coords(path) for path in paths],
            "connected_components":1 if paths and len(paths)==len(stalls) else len(getattr(field,"geoms",[field])),
            "raw_free_field_components":len(getattr(field,"geoms",[field])),
            "minimum_bottleneck_width":escape.get("minimum_connection_width",0.0),
            "connects_ramp_end":field.intersects(end_line),"connects_all_stalls":len(paths)==len(stalls) and bool(stalls),
            "supports_return_to_ramp":len(paths)==len(stalls) and bool(stalls),"stall_results":stall_results,
            "blocked_by_stall_ids":[r["stall_index"] for r in stall_results if not r["outgoing_path_exists"]]}

    @staticmethod
    def _line_coords(line):
        return [[float(x),float(y)] for x,y in line.coords]

    def _world_spine(self,spine,frame):
        output=dict(spine)
        if output.get("vehicle_spine_polygon"): output["vehicle_spine_polygon"]=[self._world(p,frame) for p in output["vehicle_spine_polygon"]]
        output["vehicle_spine_center_paths"]=[ [self._world(p,frame) for p in path] for path in output.get("vehicle_spine_center_paths",[]) ]
        for result in output.get("stall_results",[]):
            if result.get("path"): result["path"]=[self._world(p,frame) for p in result["path"]]
        return output

    @staticmethod
    def _required_stall_width(base_width,left_constrained,right_constrained):
        """Current project-test wall-side clearance policy; not a universal rule."""
        return float(base_width)+0.25*int(bool(left_constrained))+0.25*int(bool(right_constrained))

    def _ramp_end_escape(self,inner,ramp,end_edge,direction,maneuvering,required_width):
        """Prove a non-zero-width connected departure from END into the vehicle field."""
        edge=LineString(end_edge); midpoint=edge.interpolate(0.5,normalized=True)
        dx,dy=direction; length=hypot(dx,dy)
        if length<=self.EPS:
            return {"geometry_status":"not_feasible","failure_reasons":["ramp_end_dead_end"]}
        dx,dy=dx/length,dy/length
        ray=LineString([[midpoint.x,midpoint.y],[midpoint.x+dx*1000,midpoint.y+dy*1000]])
        boundary_hits=ray.intersection(inner.boundary)
        distances=[midpoint.distance(Point(p)) for p in self._intersection_points(boundary_hits)
                   if midpoint.distance(Point(p))>self.EPS]
        obstacle_distance=min(distances,default=0.0)
        connected_free=inner.difference(ramp.buffer(-self.EPS))
        end_probe=Point(midpoint.x+dx*self.EPS*10,midpoint.y+dy*self.EPS*10)
        connected_component=next((g for g in getattr(connected_free,"geoms",[connected_free]) if g.covers(end_probe)),None)
        departure_apron=(Polygon([end_edge[0],end_edge[1],
            [end_edge[1][0]+dx*obstacle_distance,end_edge[1][1]+dy*obstacle_distance],
            [end_edge[0][0]+dx*obstacle_distance,end_edge[0][1]+dy*obstacle_distance]])
            if obstacle_distance>self.EPS else Polygon())
        searchable_escape_field=departure_apron.buffer(required_width,cap_style=2,join_style=2).intersection(inner)
        reachable=(connected_component is not None and connected_component.intersects(maneuvering)
                   and searchable_escape_field.intersection(maneuvering).area>self.EPS)
        contact=edge.length if reachable else 0.0
        px,py=-dy,dx
        cross=LineString([[end_probe.x-px*1000,end_probe.y-py*1000],
                          [end_probe.x+px*1000,end_probe.y+py*1000]])
        section=inner.intersection(cross)
        section_points=self._intersection_points(section)
        signed=[(p[0]-end_probe.x)*px+(p[1]-end_probe.y)*py for p in section_points]
        left_escape=max([value for value in signed if value>=0.0],default=0.0)
        right_escape=abs(min([value for value in signed if value<=0.0],default=0.0))
        failures=[]
        if obstacle_distance<=self.EPS: failures.append("ramp_end_faces_wall")
        if contact+self.EPS<required_width: failures.append("ramp_end_escape_width_insufficient")
        if not reachable: failures.append("maneuvering_field_disconnected_from_ramp_end")
        return {"contract":"RampEndEscapeContractV1","geometry_status":"resolved" if not failures else "not_feasible",
            "failure_reasons":failures,"end_edge":end_edge,"end_midpoint":[midpoint.x,midpoint.y],
            "departure_direction":[dx,dy],"first_obstacle_distance":obstacle_distance,
            "minimum_connection_width":contact,"left_escape_width":left_escape,"right_escape_width":right_escape,
            "departure_apron_polygon":self._polygon_coords(departure_apron),
            "searchable_escape_field_polygon":self._polygon_coords(searchable_escape_field),
            "connected_free_space_polygon":self._polygon_coords(connected_component),
            "connected_maneuvering_polygon":self._polygon_coords(maneuvering) if reachable else []}

    def _maneuvering_connection_proof(self,departure_apron,maneuvering,required_width):
        """Measure the real geometric throat; point contact is never a vehicle corridor."""
        overlap=departure_apron.intersection(maneuvering)
        interface=departure_apron.boundary.intersection(maneuvering.boundary)
        interface_length=float(interface.length)
        overlap_area=float(overlap.area)
        bottleneck=interface_length
        if overlap_area>self.EPS:
            rectangle=overlap.minimum_rotated_rectangle
            lengths=[Point(a).distance(Point(b)) for a,b in zip(list(rectangle.exterior.coords)[:-1],list(rectangle.exterior.coords)[1:])]
            bottleneck=min(lengths,default=0.0)
        combined=departure_apron.union(maneuvering)
        same_component=combined.geom_type=="Polygon"
        resolved=same_component and bottleneck+self.EPS>=required_width
        reasons=[]
        if not same_component: reasons.append("maneuvering_field_disconnected_from_ramp_end")
        if bottleneck+self.EPS<required_width: reasons.append("ramp_end_escape_width_insufficient")
        return {"contract":"RampEndManeuveringConnectionProofV1",
            "geometry_status":"resolved" if resolved else "not_feasible",
            "failure_reasons":reasons,"contact_geometry_type":overlap.geom_type,
            "contact_interface_wkt":interface.wkt,"contact_interface_length":interface_length,
            "overlap_area":overlap_area,"minimum_bottleneck_width":bottleneck,
            "connected_component_count":1 if same_component else len(getattr(combined,"geoms",[combined])),
            "corridor_polygon":self._polygon_coords(combined) if resolved else []}

    @staticmethod
    def _intersection_points(geometry):
        if geometry.is_empty: return []
        if geometry.geom_type=="Point": return [[geometry.x,geometry.y]]
        if geometry.geom_type=="MultiPoint": return [[p.x,p.y] for p in geometry.geoms]
        if geometry.geom_type in ("LineString","LinearRing"):
            return [list(geometry.coords)[0],list(geometry.coords)[-1]]
        return [point for part in getattr(geometry,"geoms",[]) for point in BasementRampParkingDesignReasonerV2._intersection_points(part)]

    @staticmethod
    def _polygon_coords(polygon):
        if polygon is None or polygon.is_empty: return []
        if polygon.geom_type=="Polygon": return [list(p) for p in list(polygon.exterior.coords)[:-1]]
        largest=max(polygon.geoms,key=lambda g:g.area)
        return [list(p) for p in list(largest.exterior.coords)[:-1]]

    def _world_escape(self,escape,frame):
        output=dict(escape)
        for key in ("end_edge","departure_apron_polygon","searchable_escape_field_polygon","connected_free_space_polygon","connected_maneuvering_polygon"):
            if output.get(key): output[key]=[self._world(point,frame) for point in output[key]]
        if output.get("end_midpoint"): output["end_midpoint"]=self._world(output["end_midpoint"],frame)
        d=output.get("departure_direction")
        if d: output["departure_direction"]=[d[0]*frame["tangent"][0]+d[1]*frame["normal"][0],d[0]*frame["tangent"][1]+d[1]*frame["normal"][1]]
        return output

    @staticmethod
    def _horizontal_interval(polygon, v):
        minx, _, maxx, _ = polygon.bounds
        section = polygon.intersection(LineString([[minx-100.0, v], [maxx+100.0, v]]))
        if section.is_empty:
            return None
        bounds = section.bounds
        return [bounds[0], bounds[2]]
