"""Coupled ground/core/residential topology alternatives; no room planning."""
from copy import deepcopy
from math import pi
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from core.architecture.reasoning.architectural_dependency_graph_v1 import ArchitecturalDependencyGraphV1
from core.architecture.reasoning.architectural_frontage_value_intelligence_v1 import ArchitecturalFrontageValueIntelligenceV1
from core.architecture.reasoning.buildable_space_utilization_intelligence_v1 import BuildableSpaceUtilizationIntelligenceV1
from core.architecture.reasoning.residential_floor_access_daylight_topology_v2 import ResidentialFloorAccessDaylightTopologyV2
from core.architecture.reasoning.vertical_core_placement_tradeoff_intelligence_v1 import VerticalCorePlacementTradeoffIntelligenceV1
from core.architecture.reasoning.vertical_core_transform_intelligence_v2 import VerticalCoreTransformIntelligenceV2
from core.architecture.reasoning.vehicle_movement_path_v3 import VehicleMovementPathV3
from core.architecture.reasoning.pedestrian_site_access_design_reasoner_v1 import PedestrianSiteAccessDesignReasonerV1
from core.architecture.reasoning.spatial_reservation_exclusivity_v1 import ReservationZone, SpatialReservationExclusivityV1
from core.architecture.reasoning.architectural_reasoning_upgrade_v1 import (
    ArchitecturalConstraintPropagationGraph, ArchitecturalSpaceRoleInference,
    CommercialViabilityIntelligence, EntranceImpactEvaluation, ParkingFieldTopologyIntelligence,
    ResidentialEnvelopeQualityIntelligence,
)


class WholeBuildingCoupledTopologySearchV1:
    FAMILY_SPECS=(("WB-NS-CURRENT-CORE","CURRENT_REFERENCE","R-NS",False),
                  ("WB-EW-CURRENT-CORE-HISTORICAL","CURRENT_REFERENCE","R-EW",True),
                  ("WB-EW-NORTH-CORE","NORTH","R-EW",False),("WB-EW-SOUTH-CORE","SOUTH","R-EW",False),
                  ("WB-EW-OFFSET-CORE","OFFSET","R-EW",False),("WB-EW-EAST-CORE","EAST","R-EW",False),
                  ("WB-EW-WEST-CORE","WEST","R-EW",False),("WB-NS-CENTRAL-CORE","CENTRAL","R-NS",False))
    EPS=1e-6

    def resolve(self,site,baseline_scenario_a,pilot_reference,program_requirements):
        before=deepcopy((site,baseline_scenario_a,pilot_reference,program_requirements))
        seed=ResidentialFloorAccessDaylightTopologyV2().resolve(site,baseline_scenario_a,pilot_reference,{"jurisdiction":"Minab"},{"allow_public_road_projection":False})
        parcel=Polygon(seed["local_parcel_polygon"]);placements=VerticalCorePlacementTradeoffIntelligenceV1().generate(seed["local_parcel_polygon"],pilot_reference["geometry"]["core"])
        placement_by_id={p["strategy"]:p for p in placements["candidates"]};candidates=[]
        for family,strategy,split,historical in self.FAMILY_SPECS:
            placement=placement_by_id[strategy];altered=deepcopy(pilot_reference);altered["geometry"]["core"]=deepcopy(placement["core"])
            for mode,ground in self._ground_floor_variants(parcel,altered,placement,program_requirements,site):
                residential=self._residential_floor(site,baseline_scenario_a,altered,split,seed)
                candidate_id=family if mode=="NO_DEDICATED_PEDESTRIAN_ENTRANCE" else family+"-DEDICATED-PED"
                candidates.append(self._compose(candidate_id,strategy,split,historical,placement,ground,residential,program_requirements))
        transverse=self._transverse_candidate(parcel,site,baseline_scenario_a,pilot_reference,program_requirements,seed)
        candidates.append(transverse)
        transform_search, transformed=self._transverse_transform_candidates(parcel,site,baseline_scenario_a,pilot_reference,program_requirements,seed)
        candidates.extend(transformed)
        valid=[c for c in candidates if c["hard_validation_status"]=="hard_valid" and c.get("architectural_review_status")!="human_architectural_review_failed"]
        shortlist=self._pareto_shortlist(valid)
        diagnostics=[] if shortlist else sorted(candidates,key=lambda c:len(c["hard_rejection_reasons"]))[:4]
        graph=ArchitecturalDependencyGraphV1().build({"core_location":"variable","residential_split":"variable","program_requirements":program_requirements})
        assert (site,baseline_scenario_a,pilot_reference,program_requirements)==before
        return {"contract":"WholeBuildingCoupledTopologySearchV1","site":"REAL Parcel 2","source_parcel":site["parcel"],"source_frontage":site["frontage"],
                "local_parcel_polygon":seed["local_parcel_polygon"],"program_requirements":deepcopy(program_requirements),
                "core_placement_tradeoff":placements,"vertical_core_transform_intelligence_v2":transform_search,
                "architectural_dependency_graph":graph,"candidate_count":len(candidates),
                "hard_valid_candidate_count":len(valid),"candidates":candidates,"pareto_shortlist":shortlist,
                "pareto_shortlist_ids":[c["candidate_id"] for c in shortlist],"final_selection_performed":False,
                "diagnostic_shortlist":diagnostics,"diagnostic_shortlist_ids":[c["candidate_id"] for c in diagnostics],
                "final_whole_building_topology":None,"room_layout_generated":False,"final_windows_generated":False,
                "previous_evidence_preserved":True,"baseline_scenario_a":deepcopy(baseline_scenario_a),"baseline_geometry_preserved":True,
                "program_changed":False,"basement_deleted":False,"basement_removal_approved":False,
                "structure_executed":False,"bim_executed":False,"ifc_executed":False}

    def _transverse_candidate(self,parcel,site,baseline,pilot,requirements,seed):
        search=VerticalCorePlacementTradeoffIntelligenceV1().search_north_wall_offsets(
            seed["local_parcel_polygon"],pilot["geometry"]["core"],8.0,[7.0,7.5,8.0,8.5,9.0])
        trials=[]
        for placement in search["candidates"]:
            altered=deepcopy(pilot);altered["geometry"]["core"]=deepcopy(placement["core"])
            ground=self._ground_floor_transverse(parcel,altered,placement,requirements,site)
            residential=self._residential_floor(site,baseline,altered,"R-EW",seed)
            candidate=self._compose("WB-EW-TRANSVERSE-PARKING-CORE-8M","NORTH_WALL_OFFSET_SEARCH","R-EW",False,placement,ground,residential,requirements)
            candidate["north_wall_offset_search"]={"requested_offset":8.0,"tested_offsets":search["tested_offsets"],
                "actual_offset":placement["actual_north_wall_offset"]}
            candidate["parking_topology"]="three_transverse_stalls_east_nose"
            trials.append(candidate)
        selected=min(trials,key=lambda c:(len(c["hard_rejection_reasons"]),abs(c["north_wall_offset_search"]["actual_offset"]-8.0),
                                          c["metrics"]["residential_unallocated_area"],c["metrics"]["common_path_length"]))
        selected["north_wall_offset_search"]["trial_summaries"]=[{"offset":c["north_wall_offset_search"]["actual_offset"],
            "status":c["hard_validation_status"],"failures":c["hard_rejection_reasons"]} for c in trials]
        selected["architectural_review_status"]="human_architectural_review_failed"
        selected["architectural_review_reason"]="core_transform_space_omitted_orientation_and_vehicle-envelope reasoning"
        selected["counterexample_status"]="hard_valid_but_human_architectural_review_failed"
        return selected

    def _transverse_transform_candidates(self,parcel,site,baseline,pilot,requirements,seed):
        """Run the general V2 operator; regenerate every dependent layer per transform."""
        x0,y0,x1,y1=parcel.bounds;vehicle=requirements.get("vehicle_dimensions",[5.0,2.5]);stall_length,stall_width=map(float,vehicle);parking_top=y1
        count=int(requirements.get("parking_required_count",3))
        stalls=[[(x1-stall_length,parking_top-(i+1)*stall_width),(x1,parking_top-(i+1)*stall_width),
                 (x1,parking_top-i*stall_width),(x1-stall_length,parking_top-i*stall_width)] for i in range(count)]
        parking_field=ParkingFieldTopologyIntelligence().derive(stalls,"west",vehicle,requirements.get("turning_requirements",{"turning_depth":stall_length}))
        maneuver=parking_field["circulation_field"]
        array_depth=unary_union([Polygon(s) for s in stalls]).bounds[3]-unary_union([Polygon(s) for s in stalls]).bounds[1]
        drive_width=float(requirements.get("vehicle_access_width",max(stall_width,stall_length*.7)))
        drive=[(x0,y0),(x0+drive_width,y0),(x0+drive_width,parking_top-array_depth),(x0,y1)]
        clearance=float(requirements.get("vehicle_core_clearance",.15))
        search=VerticalCoreTransformIntelligenceV2().search(seed["local_parcel_polygon"],pilot["geometry"]["core"],
            {"parking_stalls":stalls,"maneuvering_field":maneuver,"drive_lane":drive,
             "swept_path":requirements.get("vehicle_swept_path",[])},
            translation_step=float(requirements.get("core_translation_step",.5)),clearance=clearance)
        trials=[]
        for i,placement in enumerate(search["candidates"]):
            if placement["hard_validation_status"]!="hard_valid":continue
            altered=deepcopy(pilot);altered["geometry"]["core"]=deepcopy(placement["core"])
            ground=self._ground_floor_transverse(parcel,altered,placement,requirements,site)
            residential=self._residential_floor(site,baseline,altered,"R-EW",seed)
            candidate=self._compose(f"WB-EW-TRANSVERSE-VCTI2-{i:03d}","ROTATE_TRANSLATE_COUPLED_SEARCH","R-EW",False,placement,ground,residential,requirements)
            candidate["parking_topology"]="three_transverse_stalls_east_nose"
            candidate["transform"]={"rotation_degrees":placement["rotation_degrees"],"translation_vector":placement["translation_vector"]}
            candidate["dependency_regeneration"]={k:"regenerated_and_re_evaluated" for k in ("parking","commercial","pedestrian","residential")}
            candidate["vehicle_forbidden_envelope"]=placement["vehicle_forbidden_envelope"]
            candidate["objective"]=self._transform_objective(candidate,parcel)
            candidate["architectural_review_status"]="machine_candidate_pending_human_review"
            trials.append(candidate)
        feasible=sorted([c for c in trials if c["hard_validation_status"]=="hard_valid"],key=lambda c:c["objective"]["total_score"],reverse=True)
        decision_pool=feasible or sorted(trials,key=lambda c:(len(c["hard_rejection_reasons"]),-c["objective"]["total_score"]))
        decision_pool=sorted(decision_pool,key=lambda c:(Polygon(c["core"]["polygon"]).boundary.intersection(parcel.boundary).length>self.EPS,-c["objective"]["total_score"]))
        selected=[]
        seen=set()
        for candidate in decision_pool:
            signature=(candidate["transform"]["rotation_degrees"],round(candidate["metrics"]["commercial_coherence"],1),round(candidate["metrics"]["unit_area_balance"],1))
            if signature in seen: continue
            seen.add(signature);item=deepcopy(candidate);item["candidate_id"]=f"WB-GENERAL-RULES-TOPOLOGY-{len(selected)+1:02d}";item["transform_search_trial_count"]=len(trials);item["decision_support_only"]=True;item["winner_status"]="not_selected";selected.append(item)
            if len(selected)==3: break
        summary=deepcopy(search);summary["evaluated_transform_count"]=len(trials)
        summary["selected_candidate_id"]=None;summary["decision_support_candidate_ids"]=[c["candidate_id"] for c in selected]
        summary["objective_terms"]=["centrality","edge_penalty","commercial_preservation","pedestrian_access","residential_efficiency"]
        return summary,selected

    def _transform_objective(self,candidate,parcel):
        m=candidate["metrics"];core=Polygon(candidate["core"]["polygon"]);diagonal=max((parcel.bounds[2]-parcel.bounds[0])**2+(parcel.bounds[3]-parcel.bounds[1])**2,.01)**.5
        centrality=max(0,1-core.centroid.distance(parcel.centroid)/diagonal)
        edge_clearance=core.boundary.distance(parcel.boundary);edge_penalty=1/(1+edge_clearance)
        commercial=min(1,m["commercial_area"]/max(parcel.area,.01)) * m["commercial_coherence"]
        pedestrian_length=LineString(candidate["ground_floor"]["pedestrian_path"]).length if candidate["ground_floor"]["pedestrian_path"] else 0
        pedestrian=1 if candidate["ground_floor"]["pedestrian_mode"]=="NO_DEDICATED_PEDESTRIAN_ENTRANCE" else 1/(1+max(0,pedestrian_length))
        residential=m["total_program_efficiency"]*m["unit_area_balance"]
        weights={"centrality":.28,"edge_penalty":.12,"commercial_preservation":.22,"pedestrian_access":.16,"residential_efficiency":.22}
        total=weights["centrality"]*centrality-weights["edge_penalty"]*edge_penalty+weights["commercial_preservation"]*commercial+weights["pedestrian_access"]*pedestrian+weights["residential_efficiency"]*residential
        return {"centrality":centrality,"edge_penalty":edge_penalty,"commercial_preservation":commercial,"pedestrian_access":pedestrian,"pedestrian_path_length":pedestrian_length,"residential_efficiency":residential,"weights":weights,"total_score":total}

    def _ground_floor_transverse(self,parcel,pilot,placement,requirements,site):
        x0,y0,x1,y1=parcel.bounds;vehicle=requirements.get("vehicle_dimensions",[5.0,2.5]);stall_length,stall_width=map(float,vehicle);parking_top=y1
        count=int(requirements.get("parking_required_count",3));stalls=[Polygon([(x1-stall_length,parking_top-(i+1)*stall_width),(x1,parking_top-(i+1)*stall_width),(x1,parking_top-i*stall_width),(x1-stall_length,parking_top-i*stall_width)]) for i in range(count)]
        parking_field=ParkingFieldTopologyIntelligence().derive([self._poly(s) for s in stalls],"west",vehicle,requirements.get("turning_requirements",{"turning_depth":stall_length}))
        maneuver=Polygon(parking_field["circulation_field"]);array_depth=unary_union(stalls).bounds[3]-unary_union(stalls).bounds[1];drive_width=float(requirements.get("vehicle_access_width",max(stall_width,stall_length*.7)))
        drive=Polygon([(x0,y0),(x0+drive_width,y0),(x0+drive_width,parking_top-array_depth),(x0,y1)])
        source=deepcopy(pilot);source["geometry"]["parking_stalls"]=[{"stall_id":f"TP-{i+1:02d}","polygon":self._poly(s)} for i,s in enumerate(stalls)]
        source["geometry"]["drive_lane"]=self._poly(drive);source["geometry"]["maneuvering_field"]=self._poly(maneuver)
        result=self._ground_floor(parcel,source,placement,requirements,site)
        core=Polygon(placement["core"]["polygon"]);lobby=Polygon(placement["core"]["lobby"])
        result["parking_field_topology"]=parking_field;result["vehicle_circulation_field"]=self._poly(maneuver)
        result["stall_orientation"]="long_axis_east_west";result["vehicle_nose_edge"]="east"
        result["corridor_source"]="explicit_geometry_not_residual"
        result["pedestrian_path_source"]="PedestrianSiteAccessDesignReasonerV1"
        hard=[h for h in result["hard_rejection_reasons"] if h!="ground_floor_core_access_outside_envelope"]
        required=[*stalls,maneuver,core]
        if result.get("pedestrian_corridor"):required.append(Polygon(result["pedestrian_corridor"]))
        if not parcel.buffer(self.EPS).covers(unary_union(required)):hard.append("transverse_geometry_outside_envelope")
        if any((s.bounds[2]-s.bounds[0]) <= (s.bounds[3]-s.bounds[1]) for s in stalls):hard.append("stall_not_rotated_transverse")
        if any(abs(s.bounds[2]-x1)>self.EPS for s in stalls):hard.append("vehicle_nose_not_at_east_edge")
        if core.intersection(unary_union(stalls+[maneuver])).area>self.EPS:hard.append("core_parking_maneuvering_collision")
        result["hard_rejection_reasons"]=list(dict.fromkeys(hard));result["hard_validation_status"]="hard_valid" if not hard else "not_feasible"
        return result

    def _ground_floor_variants(self,parcel,pilot,placement,requirements,site):
        no_dedicated=self._ground_floor(parcel,pilot,placement,requirements,site,"NO_DEDICATED_PEDESTRIAN_ENTRANCE")
        design=no_dedicated["pedestrian_access_design"]
        feasible=[i for i,p in enumerate(design.get("candidates",[])) if p.get("geometry_status")=="candidate"]
        dedicated=[self._ground_floor(parcel,pilot,placement,requirements,site,"DEDICATED_PEDESTRIAN_ENTRANCE",i) for i in feasible]
        dedicated.sort(key=lambda g:(bool(g["entrance_impact_evaluation"]["hard_reject"]),g["entrance_impact_evaluation"]["impact_score"]))
        variants=[]
        if not requirements.get("dedicated_pedestrian_entrance_mandatory",False):variants.append(("NO_DEDICATED_PEDESTRIAN_ENTRANCE",no_dedicated))
        elif "dedicated_pedestrian_entrance_mandatory" not in no_dedicated["hard_rejection_reasons"]:
            no_dedicated["hard_rejection_reasons"].append("dedicated_pedestrian_entrance_mandatory")
            no_dedicated["hard_validation_status"]="not_feasible"
        if dedicated:variants.append(("DEDICATED_PEDESTRIAN_ENTRANCE",dedicated[0]))
        return variants

    def _ground_floor(self,parcel,pilot,placement,requirements,site,pedestrian_mode="NO_DEDICATED_PEDESTRIAN_ENTRANCE",pedestrian_candidate_index=None):
        source=pilot["geometry"];core=Polygon(placement["core"]["polygon"]);lobby=Polygon(placement["core"]["lobby"])
        stalls=[Polygon(s["polygon"]) for s in source["parking_stalls"]];drive=Polygon(source["drive_lane"])
        array=unary_union(stalls); horizontal=sum((s.bounds[2]-s.bounds[0]) >= (s.bounds[3]-s.bounds[1]) for s in stalls)>=len(stalls)/2
        dc=drive.representative_point(); ac=array.centroid
        access_direction=("west" if dc.x<ac.x else "east") if horizontal else ("south" if dc.y<ac.y else "north")
        vehicle_dims=requirements.get("vehicle_dimensions",[max(s.bounds[2]-s.bounds[0],s.bounds[3]-s.bounds[1]) for s in stalls][:1]+[min(stalls[0].bounds[2]-stalls[0].bounds[0],stalls[0].bounds[3]-stalls[0].bounds[1])])
        parking_field=ParkingFieldTopologyIntelligence().derive([self._poly(s) for s in stalls],access_direction,vehicle_dims,requirements.get("turning_requirements",{}))
        maneuver=Polygon(parking_field["circulation_field"])
        entrance_line=source.get("vehicle_entrance") or [[drive.bounds[0],drive.bounds[1]],[drive.bounds[2],drive.bounds[1]]]
        ramp_center=[[LineString(entrance_line).centroid.x,LineString(entrance_line).centroid.y],[dc.x,dc.y],[maneuver.representative_point().x,maneuver.representative_point().y]]
        movement_space=maneuver.difference(core)
        movement_parts=[p for p in getattr(movement_space,"geoms",[movement_space]) if p.geom_type=="Polygon"]
        movement_maneuver=max(movement_parts,key=lambda p:p.area) if movement_parts else maneuver
        movement=VehicleMovementPathV3().resolve(ramp_center,entrance_line,self._poly(movement_maneuver),self._poly(unary_union([drive,movement_maneuver]).convex_hull),[self._poly(s) for s in stalls],float(requirements.get("vehicle_movement_clearance_width",vehicle_dims[1])))
        swept_parts=[Polygon(p["clearance_corridor"]) for p in movement["stall_paths"] if p.get("clearance_corridor")]
        swept=unary_union(swept_parts) if swept_parts else Polygon()
        ped_width=float(requirements.get("pedestrian_clear_width",1.2)); x0,y0,x1,y1=parcel.bounds
        ped_site={"parcel_boundary":self._poly(parcel),"confirmed_road_access_edges":["PUBLIC-FRONTAGE"],"parcel_edges":[{"id":"PUBLIC-FRONTAGE","start":[x0,y0],"end":[x1,y0],"confirmed":True,"relation":"road_access"}],"pedestrian_access_width":ped_width,"setbacks":[],"protected_zones":[],"pedestrian_conflict_zones":[],"vehicle_access_zones":[self._poly(drive)],"vehicle_circulation_zones":[self._poly(maneuver)]+[self._poly(g) for g in swept_parts],"parking_access_zones":[self._poly(s) for s in stalls],"generate_multiple_candidates":True}
        floor=[{"floor":"ground","footprint":{"points":self._poly(lobby)}}]; spaces=[{"id":"CORE-LOBBY","name":"main_entrance","floor":"ground","footprint":{"points":self._poly(lobby)}}]
        ped_design=PedestrianSiteAccessDesignReasonerV1().design(ped_site,floor,spaces)
        feasible_ped=[p for p in ped_design.get("candidates",[]) if p.get("geometry_status")=="candidate"]
        selected=(ped_design.get("candidates",[])[pedestrian_candidate_index] if pedestrian_mode=="DEDICATED_PEDESTRIAN_ENTRANCE" and pedestrian_candidate_index is not None else None)
        if selected and selected.get("geometry_status")!="candidate":selected=None
        if selected:
            ped_line=LineString(selected["approach_line"]);ped=ped_line.buffer(ped_width/2,cap_style=2,join_style=2);start=Point(selected["access_point"]);ped_entrance=selected["access_segment"]
        else:
            ped_line=LineString();ped=Polygon();start=Point();ped_entrance=[]
        support=[Polygon(s["polygon"]) for s in pilot.get("generated_program_spaces",[]) if s.get("polygon")]
        baseline_functional=unary_union(stalls+[drive,maneuver,swept,core]+support)
        baseline_available=parcel.difference(baseline_functional)
        baseline_parts=[p for p in getattr(baseline_available,"geoms",[baseline_available]) if p.geom_type=="Polygon" and p.area>self.EPS]
        frontage=LineString([(parcel.bounds[0],parcel.bounds[1]),(parcel.bounds[2],parcel.bounds[1])])
        baseline_roles=ArchitecturalSpaceRoleInference().infer(baseline_parts,unary_union([drive,maneuver,swept]),placement["core"]["polygon"],list(frontage.coords),[])
        baseline_commercial=[Polygon(x["polygon"]) for x in baseline_roles["spaces"] if x["role"]=="commercial_viable"]
        functional=unary_union(stalls+[drive,maneuver,swept,core,ped]+support)
        available=parcel.difference(functional);parts=[p for p in getattr(available,"geoms",[available]) if p.geom_type=="Polygon" and p.area>self.EPS]
        front_parts=[p for p in parts if p.boundary.intersection(frontage.buffer(1e-6)).length>self.EPS]
        access_points=[[start.x,start.y]] if selected else []
        roles=ArchitecturalSpaceRoleInference().infer(parts,unary_union([drive,maneuver,swept]),placement["core"]["polygon"],list(frontage.coords),access_points)
        commercial_parts=[Polygon(x["polygon"]) for x in roles["spaces"] if x["role"]=="commercial_viable"]
        viability=CommercialViabilityIntelligence().evaluate(commercial_parts,list(frontage.coords),access_points,[drive,maneuver,swept,core,ped])
        viable=[Polygon(x) for x in viability["viable_polygons"]];commercial=unary_union(viable) if viable else Polygon();frontage_length=commercial.boundary.intersection(frontage.buffer(1e-6)).length if not commercial.is_empty else 0
        impact=EntranceImpactEvaluation().evaluate(baseline_commercial,viable,{"frontage_edge":list(frontage.coords)},self._line(ped_line) if selected else [],ped,core,support,[drive,maneuver,swept],accessible=(pedestrian_mode=="NO_DEDICATED_PEDESTRIAN_ENTRANCE" or bool(selected)))
        generated=sum(s.intersection(core).area<=self.EPS and parcel.buffer(self.EPS).covers(s) for s in stalls);requested=int(requirements.get("parking_required_count",pilot.get("parking_required_count",len(stalls))))
        parking_paths=[LineString([s.centroid,lobby.centroid]) for s in stalls if s.intersection(core).area<=self.EPS]
        frontage_value=ArchitecturalFrontageValueIntelligenceV1().resolve(site,self._poly(parcel),placement["core"]["polygon"])
        conflicts=[]
        if core.intersection(drive).area>self.EPS:conflicts.append("core_blocks_vehicle_drive_lane")
        if core.intersection(maneuver).area>self.EPS:conflicts.append("core_blocks_maneuvering_field")
        if any(core.intersection(s).area>self.EPS for s in stalls):conflicts.append("core_intersects_parking_stall")
        if generated<requested:conflicts.append("parking_count_shortfall")
        coherence=min(1,max(0,(commercial.area/commercial.convex_hull.area))) if not commercial.is_empty and commercial.convex_hull.area else 0
        if commercial.area<=self.EPS or frontage_length<1.5 or coherence<.6:conflicts.append("commercial_not_geometrically_coherent")
        if pedestrian_mode=="DEDICATED_PEDESTRIAN_ENTRANCE" and not selected:conflicts.append("pedestrian_access_not_resolved")
        elif selected and not parcel.covers(ped):conflicts.append("ground_floor_core_access_outside_envelope")
        if selected and ped.intersection(unary_union(stalls+[drive,maneuver,swept])).area>self.EPS:conflicts.append("pedestrian_path_vehicle_conflict")
        if pedestrian_mode=="NO_DEDICATED_PEDESTRIAN_ENTRANCE" and requirements.get("dedicated_pedestrian_entrance_mandatory",False):conflicts.append("dedicated_pedestrian_entrance_mandatory")
        residual=parcel.difference(unary_union([commercial,core,drive,maneuver,ped]+stalls+support));residual_area=residual.area
        residual_parts=[p for p in getattr(residual,"geoms",[residual]) if p.geom_type=="Polygon" and p.area>.05]
        residual_ratio=residual_area/parcel.area if parcel.area else 1.0
        if residual_ratio>.08:conflicts.append("large_ground_floor_unallocated_area")
        commercial_components=[p for p in getattr(commercial,"geoms",[commercial]) if p.geom_type=="Polygon" and p.area>self.EPS]
        primary_commercial=max(commercial_components,key=lambda p:p.area) if commercial_components else Polygon()
        return {"source_ground_floor_candidate_id":pilot["candidate_id"],"core":deepcopy(placement["core"]),"commercial_polygon":self._poly(primary_commercial) if not primary_commercial.is_empty else [],
                "commercial_polygons":[self._poly(p) for p in commercial_components],
                "commercial_area":commercial.area,"commercial_frontage":frontage_length,"commercial_coherence":coherence,
                "parking_stalls":[self._poly(s) for s in stalls],"parking_count_generated":generated,"parking_required_count":requested,
                "parking_program_satisfaction":"satisfied" if generated>=requested else "failed","drive_lane":self._poly(drive),"maneuvering_field":self._poly(maneuver),
                "parking_field_topology":parking_field,"vehicle_circulation_field":self._poly(maneuver),"vehicle_entrance":entrance_line,
                "vehicle_movement":movement,"vehicle_access_path":ramp_center,"swept_path":[self._poly(g) for g in swept_parts],
                "pedestrian_mode":pedestrian_mode,"pedestrian_access_design":ped_design,"pedestrian_access_candidates":ped_design.get("candidates",[]),"pedestrian_entrance":ped_entrance,
                "pedestrian_path":self._line(ped_line) if selected else [],"pedestrian_corridor":self._poly(ped) if selected else [],"parking_to_core_paths":[self._line(p) for p in parking_paths],
                "parking_to_core_access_status":"credible_pending_vehicle_model_validation" if generated>=requested else "failed",
                "vehicle_circulation_area":unary_union([drive,maneuver,swept]).area,"pedestrian_circulation_area":ped.area,
                "ground_floor_common_area":core.area,"service_area":sum(s.area for s in support),"unallocated_area":residual_area,"unallocated_area_ratio":residual_ratio,
                "unallocated_polygons":[self._poly(p) for p in residual_parts],"free_components":[self._poly(p) for p in parts],"commercial_viability":viability,"architectural_space_roles":roles,
                "functional_area_accounting":{"parcel_area":parcel.area,"functional_union_area":parcel.intersection(functional).area,"free_area":available.area,"double_counting_area":0.0},
                "entrance_impact_evaluation":impact,"commercial_audit":{"before_pedestrian_subtraction":impact["before"],"after_pedestrian_subtraction":impact["after"]},
                "frontage_value":frontage_value,"hard_rejection_reasons":conflicts,"hard_validation_status":"hard_valid" if not conflicts else "not_feasible"}

    def _residential_floor(self,site,baseline,pilot,split,seed):
        study=ResidentialFloorAccessDaylightTopologyV2().resolve(site,baseline,pilot,{"jurisdiction":"Minab"},{"allow_public_road_projection":False})
        pool=[c for c in study["candidates"] if c["split_family"]==split and c["hard_validation_status"]=="hard_valid"]
        if not pool:return {"split_family":split,"candidate":None,"core":deepcopy(pilot["geometry"]["core"]),"hard_validation_status":"not_feasible","hard_rejection_reasons":["residential_split_not_generated_hard_valid"]}
        def coupled_rank(x):
            spaces=[{"space_id":f"U-{i}","classification":"PRIVATE_UNIT","polygon":u["polygon"]} for i,u in enumerate(x["unit_envelopes"])]
            spaces += [{"space_id":"COMMON","classification":"COMMON","polygon":x["common_lobby_polygon"]},
                       {"space_id":"COURT","classification":"DAYLIGHT_COURT","polygon":x["shared_daylight_court"]["court_polygon"]}]
            util=BuildableSpaceUtilizationIntelligenceV1().resolve(study["local_parcel_polygon"],spaces)
            return (-util["unallocated_buildable_area"],-x["common_access_length"],x["unit_area_balance_ratio"],-len(x["architectural_quality_penalties"]))
        c=max(pool,key=coupled_rank)
        spaces=[{"space_id":"UNIT-SOUTH" if split=="R-NS" and i==0 else "UNIT-NORTH" if split=="R-NS" else f"UNIT-{i+1}","classification":"PRIVATE_UNIT","polygon":u["polygon"]} for i,u in enumerate(c["unit_envelopes"])]
        spaces += [{"space_id":"COMMON-LOBBY","classification":"COMMON","polygon":c["common_lobby_polygon"]},{"space_id":"STAIR","classification":"VERTICAL_CIRCULATION","polygon":c["stair"]["landing_geometry"]},{"space_id":"ELEVATOR","classification":"VERTICAL_CIRCULATION","polygon":c["elevator"]["polygon"]},{"space_id":"SHARED-DAYLIGHT-COURT","classification":"DAYLIGHT_COURT","polygon":c["shared_daylight_court"]["court_polygon"]}]
        spaces += [{"space_id":t["terrace_id"],"classification":"PRIVATE_TERRACE","polygon":t["terrace_polygon"]} for t in c["terraces"] if t["terrace_polygon"]]
        util=BuildableSpaceUtilizationIntelligenceV1().resolve(study["local_parcel_polygon"],spaces)
        units=[Polygon(u["polygon"]) for u in c["unit_envelopes"]];metrics=[self._shape_metrics(u) for u in units]
        court=c["shared_daylight_court"]["court_polygon"]
        envelope_quality=[ResidentialEnvelopeQualityIntelligence().evaluate(u,[[(study["local_parcel_polygon"][0]),(study["local_parcel_polygon"][1])]],court,c.get("residential_common_access_graph",{}).get("paths",[])[i] if i<len(c.get("residential_common_access_graph",{}).get("paths",[])) else None) for i,u in enumerate([x["polygon"] for x in c["unit_envelopes"]])]
        hard=[]
        if util["unallocated_buildable_area_ratio"]>.08:hard.append("large_residential_unallocated_area")
        if any(q["quality_status"]=="quality_failure" for q in envelope_quality):hard.append("residential_envelope_quality_failure")
        return {"split_family":split,"candidate":c,"core":deepcopy(pilot["geometry"]["core"]),"unit_1_area":units[0].area,"unit_2_area":units[1].area,
                "unit_area_balance":min(u.area for u in units)/max(u.area for u in units),"unit_aspect_ratios":[m["aspect"] for m in metrics],
                "corridor_likeness":[m["corridor"] for m in metrics],"shared_daylight_court_area":c["shared_daylight_court"]["court_area"],
                "shared_daylight_balance":c["shared_daylight_court"]["daylight_balance_ratio"],"terrace_area_each_unit":[t["terrace_area"] for t in c["terraces"]],
                "common_area":c["common_lobby_area"],"common_path_length":c["common_access_length"],"residential_unallocated_area":util["unallocated_buildable_area"],
                "residential_unallocated_polygons":util["unallocated_residual_polygons"],"buildable_space_utilization":util,"residential_envelope_quality":envelope_quality,
                "hard_rejection_reasons":hard,"hard_validation_status":"hard_valid" if not hard else "not_feasible"}

    def _compose(self,family,strategy,split,historical,placement,ground,residential,requirements):
        aligned=residential.get("core",{}).get("polygon")==placement["core"]["polygon"]
        hard=list(placement["hard_rejection_reasons"])+ground["hard_rejection_reasons"]+residential["hard_rejection_reasons"]
        if not aligned:hard.append("vertical_core_xy_misalignment")
        vertical=("ground","first","second")
        zones=[ReservationZone("CORE","vertical_core","ground",placement["core"]["polygon"],vertical)]
        for key,function in (("stair","stair"),("elevator","elevator"),("lobby","lobby")):
            component=placement["core"].get(key,[])
            component_polygon=component.get("polygon",[]) if isinstance(component,dict) else component
            if component_polygon: zones.append(ReservationZone(key.upper(),function,"ground",component_polygon,vertical))
        zones += [ReservationZone(f"STALL-{i+1}","parking_stall","ground",p) for i,p in enumerate(ground.get("parking_stalls",[]))]
        zones.append(ReservationZone("VEHICLE-FIELD","vehicle_circulation","ground",ground.get("vehicle_circulation_field",[])))
        rc=residential.get("candidate") or {}
        court=(rc.get("shared_daylight_court") or {}).get("court_polygon",[])
        if court: zones.append(ReservationZone("DAYLIGHT-COURT","daylight_court","first",court,("first","second")))
        reservation=SpatialReservationExclusivityV1().evaluate(zones)
        hard += reservation["hard_failure_codes"]
        changed=strategy!="CURRENT_REFERENCE"
        rq=residential.get("unit_area_balance",0);front_loss=ground["frontage_value"]["frontage_value_loss"]
        metrics={"parking_count_generated":ground["parking_count_generated"],"commercial_area":ground["commercial_area"],"commercial_frontage":ground["commercial_frontage"],
                 "commercial_coherence":ground["commercial_coherence"],"vehicle_circulation_area":ground["vehicle_circulation_area"],"pedestrian_circulation_area":ground["pedestrian_circulation_area"],
                 "pedestrian_mode":ground["pedestrian_mode"],"pedestrian_induced_area_loss":ground["entrance_impact_evaluation"]["metrics"]["commercial_usable_area_loss"],
                 "pedestrian_induced_frontage_loss":ground["entrance_impact_evaluation"]["metrics"]["frontage_loss"],"entrance_impact_score":ground["entrance_impact_evaluation"]["impact_score"],
                 "ground_floor_common_area":ground["ground_floor_common_area"],"service_area":ground["service_area"],"ground_floor_unallocated_area":ground["unallocated_area"],
                 "unit_1_area":residential.get("unit_1_area",0),"unit_2_area":residential.get("unit_2_area",0),"unit_area_balance":rq,
                 "unit_aspect_ratios":residential.get("unit_aspect_ratios",[]),"corridor_likeness":residential.get("corridor_likeness",[]),
                 "shared_daylight_court_area":residential.get("shared_daylight_court_area",0),"shared_daylight_balance":residential.get("shared_daylight_balance",0),
                 "terrace_area_each_unit":residential.get("terrace_area_each_unit",[]),"residential_common_area":residential.get("common_area",0),
                 "common_path_length":residential.get("common_path_length",0),"residential_unallocated_area":residential.get("residential_unallocated_area",0),
                 "core_area":placement["core_area"],"core_location":strategy,"core_rotation_degrees":placement.get("rotation_degrees",0),"vertical_alignment_status":"exact_xy_alignment" if aligned else "failed",
                 "stair_access_status":"resolved" if residential.get("candidate") else "failed","elevator_access_status":"resolved" if residential.get("candidate") else "failed",
                 "total_program_efficiency":0 if not residential.get("candidate") else (ground["commercial_area"]+residential["unit_1_area"]+residential["unit_2_area"])/(200*2),
                 "frontage_value_loss":front_loss,"daylight_value_loss":front_loss if strategy=="SOUTH" else 0,
                 "parking_program_satisfaction":ground["parking_program_satisfaction"],"commercial_program_satisfaction":"satisfied" if ground["commercial_area"]>0 else "failed",
                 "residential_quality_score":rq*residential.get("shared_daylight_balance",0),"cross_floor_conflict_count":len(hard)}
        node_values={
            "parking_field":ground.get("parking_field_topology",{"drive_lane":ground["drive_lane"],"maneuvering_field":ground["maneuvering_field"]}),
            "vehicle_movement_swept_path":{"movement":ground.get("vehicle_movement",{}),"swept_path":ground.get("swept_path",[]),"access_path":ground.get("vehicle_access_path",[])},
            "core":placement["core"],"pedestrian_access":{"mode":ground["pedestrian_mode"],"entrance":ground["pedestrian_entrance"],"path":ground["pedestrian_path"],"impact":ground["entrance_impact_evaluation"]},
            "functional_subtraction":{"free_components":ground.get("free_components",[]),"accounting":ground.get("functional_area_accounting",{})},
            "commercial_viability":ground.get("commercial_viability",{}),"space_roles":ground.get("architectural_space_roles",{}),
            "residential_envelopes":[u["polygon"] for u in residential.get("candidate",{}).get("unit_envelopes",[])] if residential.get("candidate") else [],
            "daylight_court":residential.get("candidate",{}).get("shared_daylight_court",{}) if residential.get("candidate") else {},
            "quality_metrics":residential.get("residential_envelope_quality",[]),
        }
        propagation=ArchitecturalConstraintPropagationGraph().regenerate({"candidate_id":family},{k:(lambda state,k=k:node_values[k]) for k in ArchitecturalConstraintPropagationGraph.ORDER})
        return {"contract":"WholeBuildingCoupledTopologyCandidateV1","candidate_id":family,"core_strategy":strategy,"residential_split":split,
                "pedestrian_mode":ground["pedestrian_mode"],
                "historical_counterexample":historical,"ground_floor_changed":changed,"change_reason":"residential_topology_requires_core_relocation" if changed else "reference_geometry_retained",
                "ground_floor":ground,"residential_floor":residential,"core":deepcopy(placement["core"]),"metrics":metrics,"architectural_constraint_propagation":propagation,
                "spatial_reservation":reservation,"hard_collision_gate_executed_before_scoring":True,
                "program_requirements_satisfied":not hard,"hard_rejection_reasons":list(dict.fromkeys(hard)),
                "hard_validation_status":"hard_valid" if not hard else "not_feasible","final_selection_performed":False,
                "room_layout_generated":False,"final_windows_generated":False}

    def _pareto_shortlist(self,valid):
        out=[]
        for c in valid:
            m=c["metrics"]
            dominated=any(o is not c and self._dominates(o["metrics"],m) for o in valid)
            if not dominated:out.append(c)
        return out[:8]
    @staticmethod
    def _dominates(a,b):
        good=(a["parking_count_generated"]>=b["parking_count_generated"] and a["commercial_area"]>=b["commercial_area"] and a["residential_quality_score"]>=b["residential_quality_score"] and a["frontage_value_loss"]<=b["frontage_value_loss"])
        strict=(a["parking_count_generated"]>b["parking_count_generated"] or a["commercial_area"]>b["commercial_area"] or a["residential_quality_score"]>b["residential_quality_score"] or a["frontage_value_loss"]<b["frontage_value_loss"])
        return good and strict
    @staticmethod
    def _shape_metrics(g):
        x0,y0,x1,y1=g.bounds;w=x1-x0;d=y1-y0;aspect=max(w,d)/max(min(w,d),1e-6);return {"aspect":aspect,"corridor":min(1,max(0,(aspect-1)/4)),"compactness":4*pi*g.area/g.length**2 if g.length else 0}
    @staticmethod
    def _poly(g):return [[float(x),float(y)] for x,y in list(g.exterior.coords)[:-1]]
    @staticmethod
    def _line(g):return [[float(x),float(y)] for x,y in g.coords]
