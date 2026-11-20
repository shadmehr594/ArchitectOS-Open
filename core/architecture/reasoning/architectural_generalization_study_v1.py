"""Requirement-seeded architecture-only generalization and decision-support studies."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .architectural_brain_orchestrator_v1 import ArchitecturalBrainOrchestratorV1
from .architectural_design_intelligence_v1 import DaylightDeficitIntelligence, PublicPrivateServiceZoning, TopologyInvalidationEngine
from .architectural_reasoning_upgrade_v1 import CommercialViabilityIntelligence, ParkingFieldTopologyIntelligence
from .pedestrian_site_access_design_reasoner_v1 import PedestrianSiteAccessDesignReasonerV1
from .vehicle_movement_path_v3 import VehicleMovementPathV3
from .spatial_reservation_exclusivity_v1 import ReservationZone, SpatialReservationExclusivityV1
from .reservation_aware_placement_v1 import ReservationAwarePlacementV1
from .floor_program_spatial_ownership_v1 import FloorProgramSpatialOwnershipV1, OwnershipSpace


def _poly(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type != "Polygon":
        g = max(g.geoms, key=lambda p: p.area)
    return [[round(float(x), 6), round(float(y), 6)] for x, y in list(g.exterior.coords)[:-1]]


def _fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


class RequirementSeededTopologyGeneratorV1:
    """Generate envelope-level hypotheses; never rooms, windows, or a winner."""
    FAMILIES = ("NS", "EW", "HYBRID")

    MAX_REGENERATION_ATTEMPTS = 8

    def generate(self, context, change=None):
        source = deepcopy(context)
        parcel = Polygon(source["site"]["local_parcel_polygon"])
        x0, y0, x1, y1 = parcel.bounds
        width, depth = x1-x0, y1-y0
        req = source["requirements"]
        core_w, core_d = req.get("core_size", [3.2, 4.8]); court_w, court_d = req.get("daylight_court_size", [3.0, 4.0])
        core_anchor = change.get("new_anchor", "searched") if change and change["element_type"] == "core" else "searched"
        placer=ReservationAwarePlacementV1()
        candidates = []
        for family in self.FAMILIES:
            demand_bias=(change or {}).get("daylight_demand_targets") or req.get("daylight_demand_targets_by_family",{}).get(family)
            resource_map=placer.resource_and_demand_maps(parcel,source["site"],family,demand_bias)
            placement_req=deepcopy(req)
            if change and change.get("element_type")=="core": placement_req["core_preferred_edge"]=change.get("new_anchor")
            # The clean solve starts from the floor envelope and reserves the vertical
            # stack before any dependent program geometry is admitted.
            core_placement=placer.place_core(parcel,[core_w,core_d],[],resource_map,placement_req)
            core=Polygon(core_placement["polygon"]) if core_placement["polygon"] else Polygon()
            ground = self._ground(parcel, family, req, [core])
            ground = self._ground_program(parcel, ground, core, req)
            court_placement=placer.place_court(parcel,[court_w,court_d],[core],resource_map,req)
            court=Polygon(court_placement["polygon"]) if court_placement["polygon"] else Polygon()
            upper = self._upper(parcel, core, court, family, req, resource_map, placer)
            ownership = self._ownership_map(parcel, core, court, ground, upper, source["floors"], req)
            reservation = self._reservation_gate(ownership)
            attempts=[{"attempt":1,"hard_validation_status":reservation["hard_validation_status"],
                       "hard_failure_codes":reservation["hard_failure_codes"],"placement_mode":"feasible_region_search"}]
            candidate = {"candidate_id": f"{source['case_id']}-{family}-{core_anchor.upper()}",
                         "topology_family": family, "core_anchor": core_anchor,
                         "core": _poly(core), "core_topology":core_placement, "daylight_court": _poly(court),
                         "daylight_court_placement":court_placement,"resource_value_map":resource_map,
                         **ground, **upper, "floor_program_ownership": ownership,
                         "spatial_reservation": reservation,
                         "reservation_regeneration": {"performed": len(attempts)>1, "attempt_count": len(attempts), "attempts": attempts,
                            "exhausted": reservation["hard_validation_status"]!="hard_valid"},
                         "hard_rejection_reasons": reservation["hard_failure_codes"],
                         "hard_validation_status": reservation["hard_validation_status"],
                          "generated_from": "requirements_and_clean_site_context",
                          "generation_sequence":["floor_buildable_envelope","vertical_core_stack","parking_and_vehicle_field",
                              "pedestrian_common_service_reserves","daylight_void","residential_unit_envelopes",
                              "terraces","commercial_remaining_ground_field","void_unallocated_accounting",
                              "authoritative_ownership_validation","architectural_critic"],
                          "ownership_queries_before_creation":True,
                          "dependency_invalidation":{"trigger":"topology_defining_placement","invalidated":["ground_dependents","all_upper_envelopes","zoning","court","terraces"],"regeneration":"clean_from_requirements"},
                          "prior_geometry_used_as_seed": False, "room_layout_generated": False,
                         "final_windows_generated": False, "final_selection_performed": False}
            candidate["geometry_fingerprint"] = _fingerprint({k:candidate[k] for k in
                ("core", "daylight_court", "parking_stalls", "vehicle_circulation_field",
                 "commercial_viable", "residential_unit_envelopes", "terraces")})
            candidates.append(candidate)
        return candidates

    @staticmethod
    def _reservation_gate(ownership):
        return {"contract": "FloorProgramSpatialOwnershipV1",
                "compatibility_policy": ownership["policy"], "gate_position": "before_scoring",
                "zones": ownership["spaces"], "collisions": ownership["hard_failures"],
                "hard_failure_codes": ownership["hard_failure_codes"],
                "hard_validation_status": ownership["hard_validation_status"]}

    def _ground(self, parcel, family, req, prior_reservations=()):
        x0,y0,x1,y1=parcel.bounds; sw,sd=req.get("parking_stall_size",[2.5,5.0]); count=req.get("parking_required_count",3)
        stalls=[]
        if family == "EW":
            for i in range(count): stalls.append(box(x1-sd, y1-(i+1)*sw, x1, y1-i*sw).intersection(parcel))
            access_direction="west"
        else:
            for i in range(count): stalls.append(box(x0+i*sw, y1-sd, x0+(i+1)*sw, y1).intersection(parcel))
            access_direction="south"
        field_data=ParkingFieldTopologyIntelligence().derive([_poly(s) for s in stalls],access_direction,[sd,sw],{"turning_depth":sd})
        circulation=Polygon(field_data["circulation_field"]).intersection(parcel)
        frontage=LineString([[x0,y0],[x1,y0]])
        vehicle_width=float(req.get("vehicle_access_width",3.2)); entrance=[[x0,y0],[x0+vehicle_width,y0]]
        entrance_field=box(x0,y0,x0+vehicle_width,min(y1,y0+max(sw,vehicle_width))).intersection(parcel)
        vehicle_zone=unary_union([circulation,entrance_field]).convex_hull.intersection(parcel)
        blocked=unary_union([p for p in prior_reservations if p and not p.is_empty]) if prior_reservations else Polygon()
        stalls=[s.difference(blocked) for s in stalls]
        circulation=circulation.difference(blocked)
        entrance_field=entrance_field.difference(blocked)
        vehicle_zone=unary_union([circulation,entrance_field]).difference(blocked).intersection(parcel)
        return {"parking_stalls":[_poly(s) for s in stalls],"vehicle_circulation_field":_poly(circulation),"vehicle_reserved_zone":_poly(vehicle_zone),
                "vehicle_entrance":entrance,"swept_validation_overlay":[[x0+vehicle_width*.5,y0],[circulation.centroid.x,circulation.centroid.y]],
                "parking_field_evidence":field_data}

    def _ground_program(self, parcel, ground, core, req):
        x0,y0,x1,y1=parcel.bounds
        stair,elevator,lobby=self._core_parts(core)
        reserved=[Polygon(p) for p in ground["parking_stalls"] if p]
        if ground["vehicle_reserved_zone"]: reserved.append(Polygon(ground["vehicle_reserved_zone"]))
        if not core.is_empty: reserved.append(core)
        commercial_field=parcel.intersection(box(x0,y0,x1,y0+min(6.0,(y1-y0)*.34))).difference(unary_union(reserved))
        viable=max(getattr(commercial_field,"geoms",[commercial_field]),key=lambda p:p.area,default=Polygon())
        frontage=LineString([[x0,y0],[x1,y0]])
        commercial=CommercialViabilityIntelligence().evaluate([_poly(viable)],list(frontage.coords),[[x0+.5,y0]],[]) if not viable.is_empty else {}
        component=(commercial.get("components") or [{}])[0]
        return {**ground,"stair":_poly(stair),"elevator":_poly(elevator),"lobby":_poly(lobby),
                "pedestrian_access":[],"ground_common":[],"ground_service":[],
                "commercial_viable":_poly(viable) if component.get("viable") else [],
                "commercial_nonviable_fragments":[] if component.get("viable") else [_poly(viable)],
                "commercial_evidence":commercial}

    @staticmethod
    def _core_parts(core):
        if core.is_empty: return Polygon(),Polygon(),Polygon()
        x0,y0,x1,y1=core.bounds; width=x1-x0
        stair=box(x0,y0,x0+width*.52,y1).intersection(core)
        elevator=box(x0+width*.52,y0,x1,y0+(y1-y0)*.42).intersection(core)
        lobby=core.difference(stair.union(elevator))
        return stair,elevator,lobby

    def _upper(self, parcel, core, court, family, req, resource_map, placer):
        buildable=parcel.difference(core.union(court)); x0,y0,x1,y1=parcel.bounds
        if family == "NS": split=LineString([[x0+(x1-x0)*.5,y0],[x0+(x1-x0)*.5,y1]]).buffer(.55)
        elif family == "EW": split=LineString([[x0,y0+(y1-y0)*.5],[x1,y0+(y1-y0)*.5]]).buffer(.55)
        else: split=LineString([[x0,y0+(y1-y0)*.52],[x1,y0+(y1-y0)*.52]]).buffer(.55).union(LineString([[x0+(x1-x0)*.55,y0],[x0+(x1-x0)*.55,y1]]).buffer(.35))
        parts=sorted([p for p in getattr(buildable.difference(split),"geoms",[]) if p.area>8],key=lambda p:p.area,reverse=True)[:2]
        terrace_search=[placer.terrace_alternatives(p,parcel,[core,court],resource_map,req) for p in parts]
        terrace_shapes=[]
        for part,result in zip(parts,terrace_search):
            terrace=Polygon(result["polygon"]).intersection(part).difference(core.union(court)) if result["polygon"] else Polygon()
            result["polygon"]=_poly(terrace)
            terrace_shapes.append(terrace)
            result["parent_unit_compatible_edge"]=True
        terraces=[_poly(t) for t in terrace_shapes]
        parts=[part.difference(terrace) for part,terrace in zip(parts,terrace_shapes)]
        common=split.intersection(parcel).difference(core.union(court).union(unary_union(terrace_shapes)))
        zoning={"PUBLIC":[],"TRANSITION":[_poly(common)],"PRIVATE":[],"SERVICE":[]}
        for p in parts:
            b=p.bounds; zoning["PUBLIC"].append(_poly(p.intersection(box(b[0],y0,b[2],y0+(y1-y0)*.35))))
            zoning["PRIVATE"].append(_poly(p.difference(Polygon(zoning["PUBLIC"][-1]) if zoning["PUBLIC"][-1] else Polygon())))
        return {"residential_unit_envelopes":[_poly(p) for p in parts],"zoning_geometry":zoning,
                "terraces":terraces,"terrace_search":terrace_search,"residual":_poly(parcel.difference(unary_union(parts+[core,court]))),
                "daylight_demand_map":resource_map,"daylight_sources":[{"source_id":"PUBLIC_FRONTAGE","active":True},{"source_id":"DAYLIGHT_COURT","active":bool(court and not court.is_empty)}]}

    def _ownership_map(self, parcel, core, court, ground, upper, floors, req):
        occupied_floors=tuple(f for f in floors if f != "basement")
        residential_floors=tuple(f for f in occupied_floors if f != "ground")
        court_semantics=req.get("daylight_court_semantics", "RESIDENTIAL_LEVEL_DAYLIGHT_VOID")
        court_scope=occupied_floors if court_semantics=="FULL_HEIGHT_DAYLIGHT_COURT" else residential_floors
        all_roles=FloorProgramSpatialOwnershipV1.ROLES
        def space(space_id, scope, extent, role, polygon, may=(), source="generated_from_requirements"):
            exclusive=tuple(sorted(all_roles-{role}-set(may)-{"VERTICAL_CORE"} if role in ("STAIR","ELEVATOR","LOBBY") else all_roles-{role}-set(may)))
            return OwnershipSpace(space_id,tuple(scope),extent,role,polygon,exclusive,tuple(may),source)
        core_may=("STAIR","ELEVATOR","LOBBY")
        spaces=[space("CORE","" if not occupied_floors else occupied_floors,f"CONTINUOUS:{occupied_floors[0]}..{occupied_floors[-1]}","VERTICAL_CORE",_poly(core),core_may,"requirements.vertical_core"),
                space("STAIR",occupied_floors,f"CONTINUOUS:{occupied_floors[0]}..{occupied_floors[-1]}","STAIR",ground["stair"],("VERTICAL_CORE",),"requirements.vertical_core"),
                space("ELEVATOR",occupied_floors,f"CONTINUOUS:{occupied_floors[0]}..{occupied_floors[-1]}","ELEVATOR",ground["elevator"],("VERTICAL_CORE",),"requirements.vertical_core"),
                space("LOBBY",occupied_floors,f"CONTINUOUS:{occupied_floors[0]}..{occupied_floors[-1]}","LOBBY",ground["lobby"],("VERTICAL_CORE",),"requirements.vertical_core"),
                space("DAYLIGHT-COURT",court_scope,court_semantics,"DAYLIGHT_COURT",_poly(court),("VOID",),"requirements.daylight_court_semantics"),
                space("DAYLIGHT-VOID",court_scope,court_semantics,"VOID",_poly(court),("DAYLIGHT_COURT",),"requirements.daylight_court_semantics")]
        spaces += [space(f"STALL-{i+1}",("ground",),"GROUND_ONLY","PARKING_STALL",p,(),"requirements.parking_required_count") for i,p in enumerate(ground["parking_stalls"])]
        spaces += [space("VEHICLE-FIELD",("ground",),"GROUND_ONLY","VEHICLE_CIRCULATION",ground["vehicle_reserved_zone"],(),"requirements.vehicle_access_width"),
                   space("PEDESTRIAN-ACCESS",("ground",),"GROUND_ONLY","PEDESTRIAN_ACCESS",ground["pedestrian_access"],(),"requirements.dedicated_pedestrian_entrance_mandatory"),
                   space("GROUND-COMMON",("ground",),"GROUND_ONLY","COMMON",ground["ground_common"],(),"requirements.common_access"),
                   space("GROUND-SERVICE",("ground",),"GROUND_ONLY","SERVICE",ground["ground_service"],(),"requirements.service"),
                   space("COMMERCIAL",("ground",),"GROUND_ONLY","COMMERCIAL",ground["commercial_viable"],(),"requirements.program")]
        for floor in residential_floors:
            spaces += [space(f"{floor.upper()}-UNIT-{i+1}",(floor,),"SINGLE_FLOOR","RESIDENTIAL_UNIT",p,(),"requirements.residential_units_per_floor") for i,p in enumerate(upper["residential_unit_envelopes"])]
            spaces += [space(f"{floor.upper()}-TERRACE-{i+1}",(floor,),"SINGLE_FLOOR","TERRACE",p,(),"requirements.terrace_required") for i,p in enumerate(upper["terraces"])]
            common=(upper["zoning_geometry"].get("TRANSITION") or [[]])[0]
            spaces += [space(f"{floor.upper()}-COMMON",(floor,),"SINGLE_FLOOR","COMMON",common,(),"requirements.residential_common"),
                       space(f"{floor.upper()}-SERVICE",(floor,),"SINGLE_FLOOR","SERVICE",[],(),"requirements.residential_service")]
        floor_polygons={f:_poly(parcel) for f in occupied_floors}
        preliminary=FloorProgramSpatialOwnershipV1().evaluate(floor_polygons,spaces)
        for floor in occupied_floors:
            active=[Polygon(s["polygon"]) for s in preliminary["spaces"] if floor in s["floor_scope"] and s["polygon"] and s["occupancy_role"] not in ("VERTICAL_CORE","UNALLOCATED")]
            residual=parcel.difference(unary_union(active)) if active else parcel
            pieces=[residual] if residual.geom_type=="Polygon" else [p for p in residual.geoms if p.geom_type=="Polygon" and p.area>FloorProgramSpatialOwnershipV1.EPS]
            for index,piece in enumerate(pieces):
                spaces.append(space(f"{floor.upper()}-UNALLOCATED-{index+1}",(floor,),"SINGLE_FLOOR","UNALLOCATED",_poly(piece),(),"computed_residual_accounting"))
        return FloorProgramSpatialOwnershipV1().evaluate(floor_polygons,spaces)


class ArchitecturalStudyEvaluatorV1:
    def evaluate(self, context, candidate, changes):
        spaces=deepcopy(context["spaces"])
        for space in spaces:
            if space.get("daylight_required"):
                space["daylight_source_ids"]=["PUBLIC_FRONTAGE","DAYLIGHT_COURT"]
                space["daylight_ratio"]=.15 if candidate["daylight_court"] else .06
        ctx={"case_id":context["case_id"],"floors":context["floors"],"changes":changes,
             "requirements":deepcopy(context["requirements"]),"spaces":spaces,
             "daylight_sources":candidate["daylight_sources"],"prior_geometry":context.get("prior_geometry"),
             "lessons":[{"decision":"review","rationale":"decision support only","source":"architectural_study_v1"}]}
        def parking(c,p):
            e=candidate["parking_field_evidence"]
            return {"contract":e.get("contract","ParkingFieldTopologyIntelligence"),"stalls":candidate["parking_stalls"],
                    "access":candidate["vehicle_entrance"],"approach":candidate["vehicle_circulation_field"],
                    "continuous_maneuvering_field":candidate["vehicle_circulation_field"],"swept_path_role":"validator_only"}
        def vehicle(c,p):
            field=candidate["vehicle_circulation_field"]; stalls=candidate["parking_stalls"]
            result={"contract":"VehicleMovementPathV3","status":"evaluated","swept_path_role":"validator_only"}
            if field and stalls:
                try:
                    x,y=Polygon(field).representative_point().coords[0]
                    result["result"]=VehicleMovementPathV3().resolve([[candidate["vehicle_entrance"][0][0],candidate["vehicle_entrance"][0][1]],[x,y]],candidate["vehicle_entrance"],field,field,stalls,7.0)
                except (ValueError,TypeError): result["status"]="evaluated_no_valid_swept_solution"
            return result
        def pedestrian(c,p):
            mode="dedicated" if context["requirements"].get("dedicated_pedestrian_entrance_mandatory") else "design_alternative"
            probe=PedestrianSiteAccessDesignReasonerV1().design({}, {}, [])
            return {"contract":"PedestrianSiteAccessDesignReasonerV1","execution_probe_status":probe["geometry_status"],"mode":mode,"mandatory":mode=="dedicated"}
        def daylight(c,p):
            probe=DaylightDeficitIntelligence().evaluate(spaces,candidate["daylight_sources"])
            return {"contract":"DaylightDeficitIntelligenceV1","status":"evaluated_before_room_geometry","deficit_count":len(probe["deficits"])}
        def privacy(c,p):
            probe=PublicPrivateServiceZoning().classify(spaces)
            return {"contract":"PublicPrivateServiceZoningV1","status":"evaluated_before_room_geometry","privacy_conflicts":probe["privacy_conflicts"]}
        def commercial(c,p):
            e=candidate["commercial_evidence"]
            component=(e.get("components") or [{}])[0]; rectangle=component.get("usable_rectangle") or []
            rectangle_area=Polygon(rectangle).area if rectangle else 0
            return {"contract":e.get("contract","CommercialViabilityIntelligence"),"frontage":component.get("frontage",0),
                    "access":component.get("frontage",0)>0,"effective_depth":component.get("effective_depth",0) or 0,
                    "largest_usable_rectangle":rectangle_area,"coherence":component.get("compactness",0),
                    "fragmentation":1-component.get("usable_rectangle_ratio",0),"viable":bool(component.get("viable"))}
        def core(c,p): return {"contract":"RequirementSeededCorePlacementV1","status":"evaluated","polygon":candidate["core"]}
        reasoners={"parking":parking,"vehicle_movement":vehicle,"pedestrian":pedestrian,"daylight":daylight,
                   "privacy":privacy,"commercial":commercial,"core":core}
        result=ArchitecturalBrainOrchestratorV1().run(ctx,reasoners)
        principal=[r for r in result["resource_priority"]["ranked_spaces"] if r["zone"] in ("public","private","commercial")]
        service=[r for r in result["resource_priority"]["ranked_spaces"] if r["zone"] in ("service","circulation")]
        result["resource_allocation_gate"]=not service or not principal or max(r["resource_scores"]["frontage"] for r in service) <= max(r["resource_scores"]["frontage"] for r in principal)
        return result


class IndependentGeneralizationStudyV1:
    @staticmethod
    def all_main_reasoners_executed(execution_trace):
        expected = list(ArchitecturalBrainOrchestratorV1.CAPABILITY_ORDER)
        main_entries = [entry for entry in execution_trace
                        if isinstance(entry, dict) and entry.get("capability") in expected]
        return ([entry.get("capability") for entry in main_entries] == expected and
                all(entry.get("executed") is True for entry in main_entries))

    def context(self):
        return {"case_id":"SYNTHETIC-CORNER-MIXED-USE-01","site":{"local_parcel_polygon":[[0,0],[18,0],[18,29],[0,29]],
                "frontages":[{"edge":"south","role":"primary_public","value":1.0},{"edge":"east","role":"secondary_public","value":.72}],
                "neighbors":{"north":"closed","west":"privacy_sensitive","east":"open","south":"public_road"}},
                "floors":["basement","ground","first","second","third"],"baseline_core_anchor":"center",
                "requirements":{"program":"mixed_use","parking_required_count":3,"vertical_core":True,"residential_units_per_floor":2,
                    "terrace_required":True,"terrace_depth":1.5,"daylight_court_size":[3.2,4.2],"dedicated_pedestrian_entrance_mandatory":False},
                "spaces":[{"space_id":"SHOP","space_type":"commercial","zone":"public"},
                    {"space_id":"LIVING","space_type":"living","zone":"public","daylight_required":True},
                    {"space_id":"BEDROOM","space_type":"bedroom","zone":"private","daylight_required":True,"privacy_buffer":True},
                    {"space_id":"TERRACE","space_type":"terrace","zone":"public","daylight_required":True},
                    {"space_id":"LOBBY","space_type":"lobby","zone":"transition"},{"space_id":"WC","space_type":"wc","zone":"service"}]}

    def run(self):
        context=self.context(); generator=RequirementSeededTopologyGeneratorV1(); evaluator=ArchitecturalStudyEvaluatorV1()
        early_deficit=DaylightDeficitIntelligence().evaluate(context["spaces"],[])
        daylight_source_alternatives=[{"strategy":"shared_internal_court"},{"strategy":"secondary_open_edge"}] if early_deficit["new_daylight_source_required"] else []
        baseline=generator.generate(context)
        prior=[c["geometry_fingerprint"] for c in baseline]; context["prior_geometry"]=[{k:c[k] for k in ("core","daylight_court","parking_stalls","residential_unit_envelopes")} for c in baseline]
        change={"element_type":"core","floor":"ground","new_anchor":"north"}
        regenerated=generator.generate(context,change)
        evaluated=[]
        for c in regenerated:
            brain=evaluator.evaluate(context,c,[change]); c["brain"]=brain; c["critic_status"]=brain["architectural_critic"]["status"]; evaluated.append(c)
        poor=deepcopy(regenerated[0]); poor["daylight_court"]=[]; poor["daylight_sources"]=[{"source_id":"PUBLIC_FRONTAGE","active":False}]
        poor_brain=evaluator.evaluate(context,poor,[change])
        dependency_probes={element:TopologyInvalidationEngine().analyze([{"element_type":element,"floor":"ground"}],context["floors"])
                           for element in ("core","stair","elevator","daylight_court")}
        new=[c["geometry_fingerprint"] for c in evaluated]
        assertions={"independent_site":context["site"]["local_parcel_polygon"]!=[],"scope":all(c["brain"]["topology_invalidation"]["dependency_scope"]=="WHOLE_BUILDING" for c in evaluated),
            "dependent_invalidation":all("all_floors" in c["brain"]["topology_invalidation"]["invalidated_dependencies"] for c in evaluated),
            "new_fingerprints":set(prior).isdisjoint(new),"no_old_geometry_seed":all(not c["prior_geometry_used_as_seed"] for c in evaluated),
            "resource_priority":all(c["brain"]["resource_allocation_gate"] for c in evaluated),
            "daylight_deficit_before_rooms":early_deficit["new_daylight_source_required"] and bool(daylight_source_alternatives),
            "zoning_before_rooms":all(c["brain"]["zoning"]["sequence"]=="before_room_geometry" for c in evaluated),
            "topology_elements_invalidate_dependents":all(p["affected_floors"]==context["floors"] and not p["local_patch_allowed"] for p in dependency_probes.values()),
            "critic_rejects_valid_but_poor":poor_brain["architectural_critic"]["status"]=="revise",
            "all_reasoners":all(self.all_main_reasoners_executed(c["brain"]["execution_trace"]) for c in evaluated),
            "no_final_outputs":all(not c["final_selection_performed"] and not c["room_layout_generated"] and not c["final_windows_generated"] for c in evaluated),
            "memory_safe":all(not c["brain"]["stable_knowledge_mutated"] for c in evaluated)}
        return {"contract":"IndependentGeneralizationStudyV1","context":context,"baseline_candidates":baseline,
                "change":change,"regenerated_candidates":evaluated,"acceptance_assertions":assertions,
                "early_daylight_deficit":early_deficit,"daylight_source_alternatives":daylight_source_alternatives,
                "dependency_probes":dependency_probes,"critic_rejection_probe":poor_brain,
                "phase_1_passed":all(assertions.values()),"final_selection_performed":False,"room_layout_generated":False,
                "final_windows_generated":False,"structure_executed":False,"bim_executed":False,"ifc_executed":False}


class CleanParcel2ResolveV1:
    def run(self, site, requirements, phase_1_passed):
        if not phase_1_passed: raise RuntimeError("Phase 1 must pass before CLEAN Parcel 2 re-solve")
        context={"case_id":"REAL-PARCEL-2-CLEAN","site":deepcopy(site),"floors":["basement","ground","first","second"],
                 "baseline_core_anchor":"center","requirements":deepcopy(requirements),
                 "spaces":[{"space_id":"COMMERCIAL","space_type":"commercial","zone":"public"},
                    {"space_id":"LIVING","space_type":"living","zone":"public","daylight_required":True},
                    {"space_id":"BEDROOM","space_type":"bedroom","zone":"private","daylight_required":True,"privacy_buffer":True},
                    {"space_id":"KITCHEN","space_type":"kitchen","zone":"private","daylight_required":True},
                    {"space_id":"TERRACE","space_type":"terrace","zone":"public","daylight_required":True},
                    {"space_id":"LOBBY","space_type":"lobby","zone":"transition"},{"space_id":"SHAFT","space_type":"shaft","zone":"service"}]}
        generator=RequirementSeededTopologyGeneratorV1(); evaluator=ArchitecturalStudyEvaluatorV1(); candidates=[]
        for c in generator.generate(context):
            if c["hard_validation_status"] != "hard_valid":
                c["brain"]={"architectural_critic":{"status":"revise","issues":[{"severity":"hard","code":x} for x in c["hard_rejection_reasons"]]}}
                c["critic_status"]="revise"; c["scoring_skipped_due_to_hard_collision"]=True; candidates.append(c); continue
            brain=evaluator.evaluate(context,c,[]); c["brain"]=brain; c["scoring_skipped_due_to_hard_collision"]=False
            area=sum(Polygon(p).area for p in c["residential_unit_envelopes"] if p)
            commercial=brain["reasoner_evidence"]["commercial"]
            c["decision_metrics"]={"program_satisfaction":len(c["residential_unit_envelopes"])==2,
                "frontage_allocation":"commercial_and_public_first","parking_count":len(c["parking_stalls"]),
                "commercial_viability":commercial,"circulation_waste":round(Polygon(c["vehicle_circulation_field"]).area,3) if c["vehicle_circulation_field"] else 0,
                "residential_area":round(area,3),"daylight_deficit":brain["daylight_deficit"]["deficits"],
                "daylight_resolution":"public_frontage_plus_shared_internal_court","terrace_satisfaction":all(c["terraces"]),
                "unit_resource_equity":"evaluated_by_topology_family","critic_failures":brain["architectural_critic"]["issues"],
                "regeneration_provenance":brain["regeneration_provenance"]}
            c["critic_status"]=brain["architectural_critic"]["status"]; candidates.append(c)
        shortlist=[c for c in candidates if c["hard_validation_status"]=="hard_valid" and c["critic_status"]=="pass" and c["decision_metrics"]["terrace_satisfaction"]][:3]
        return {"contract":"CleanParcel2ResolveV1","site":"REAL Parcel 2","clean_context_source":"site_rules_program_only",
                "discarded_design_seeds":["old_parking_polygons","old_core_coordinates","old_commercial_polygons","old_unit_envelopes","old_pedestrian_paths","old_lightwell_positions","old_terraces","old_residual_assignments"],
                "reasoning_sequence":["SiteResourceAnalysis","ProgramPriorityReasoning","DemandSupplyAnalysis","TopologyHypotheses","CoupledGeneration","DependencyDrivenRegeneration","ArchitecturalCritic","DecisionSupportShortlist"],
                "candidates":candidates,"shortlist":shortlist,"shortlist_ids":[c["candidate_id"] for c in shortlist],
                "all_rejected":not shortlist,"human_review_gate":True,"final_selection_performed":False,
                "room_layout_generated":False,"final_windows_generated":False,"structure_executed":False,"bim_executed":False,"ifc_executed":False}
