"""NS-preferred residential refinement with explicit space and privacy accounting."""
from copy import deepcopy
from math import pi
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from core.architecture.reasoning.buildable_space_utilization_intelligence_v1 import BuildableSpaceUtilizationIntelligenceV1
from core.architecture.reasoning.projection_vertical_stack_intelligence_v1 import ProjectionVerticalStackIntelligenceV1
from core.architecture.reasoning.residential_floor_access_daylight_topology_v2 import ResidentialFloorAccessDaylightTopologyV2
from core.architecture.reasoning.residential_private_terrace_topology_v1 import ResidentialPrivateTerraceTopologyV1
from core.architecture.reasoning.shared_residential_daylight_court_intelligence_v1 import SharedResidentialDaylightCourtIntelligenceV1
from core.architecture.reasoning.shared_daylight_court_maintenance_access_v1 import SharedDaylightCourtMaintenanceAccessV1
from core.architecture.reasoning.residential_common_access_graph_v1 import ResidentialCommonAccessGraphV1
from core.architecture.reasoning.shared_court_terrace_privacy_separation_v1 import SharedCourtTerracePrivacySeparationV1


class ResidentialNSSharedCourtRefinementV1:
    FAMILY_NAMES = ("NS-A", "NS-B", "NS-C", "NS-D", "NS-E", "NS-F")

    def resolve(self, site, baseline_scenario_a, pilot_reference, case_definition=None, preferences=None):
        before = deepcopy((site, baseline_scenario_a, pilot_reference))
        case_definition = case_definition or {}
        preferences = {"preferred_residential_split_direction":"north_south", "preference_source":"human_architect_review", **(preferences or {})}
        source = ResidentialFloorAccessDaylightTopologyV2().resolve(site, baseline_scenario_a, pilot_reference, case_definition,
                                                                    {"allow_public_road_projection":True})
        ns_pool = [c for c in source["candidates"] if c["split_family"] == "R-NS" and c["hard_validation_status"] == "hard_valid"]
        if not ns_pool: raise ValueError("no_ns_seed_geometry")
        seed = next((c for c in ns_pool if c["projection_mode"] == "projection_disabled"), ns_pool[0])
        candidates = []
        for index, family in enumerate(self.FAMILY_NAMES):
            raw = self._rebuild_ns_geometry(seed, family, source)
            if family == "NS-E":
                raw["projection_mode"] = "projection_candidate_enabled"
                raw["projection_opportunity"] = deepcopy(source["projection_opportunity"])
            candidates.append(self._candidate(raw, family, source, case_definition, privacy_variant=family == "NS-D",
                                              projection_variant=family == "NS-E"))
        for split in ("R-EW", "R-HYBRID"):
            pool = [c for c in source["candidates"] if c["split_family"] == split and c["hard_validation_status"] == "hard_valid"]
            if pool:
                candidates.append(self._candidate(max(pool, key=lambda c:c["shared_daylight_court"]["daylight_balance_ratio"]),
                                                  f"{split}-COUNTEREXAMPLE", source, case_definition, counterexample=True))
        valid = [c for c in candidates if c["hard_validation_status"] == "hard_valid"]
        ns_valid = sorted([c for c in valid if c["refinement_family"].startswith("NS-")], key=self._rank, reverse=True)
        review = ns_valid[:5] + [c for c in valid if c["candidate_role"] == "secondary_counterexample"]
        assert (site, baseline_scenario_a, pilot_reference) == before
        return {
            "contract":"ResidentialNSSharedCourtRefinementV1", "site":"REAL Parcel 2", "source_parcel":site["parcel"],
            "local_parcel_polygon":source["local_parcel_polygon"], "preferred_residential_split_direction":preferences["preferred_residential_split_direction"],
            "preference_source":preferences["preference_source"], "preference_is_final_approval":False,
            "ns_search_families":list(self.FAMILY_NAMES), "ew_and_hybrid_retained":True,
            "candidate_count":len(candidates), "hard_valid_candidate_count":len(valid), "candidates":candidates,
            "human_review_candidates":review, "human_review_candidate_ids":[c["candidate_id"] for c in review],
            "final_selection_performed":False, "final_residential_topology":None, "room_layout_generated":False,
            "final_windows_generated":False, "baseline_scenario_a":deepcopy(baseline_scenario_a), "baseline_geometry_preserved":True,
            "program_changed":False, "basement_deleted":False, "basement_removal_approved":False,
            "structure_executed":False, "bim_executed":False, "ifc_executed":False,
        }

    def _rebuild_ns_geometry(self, seed, family, source):
        c=deepcopy(seed); parcel=Polygon(source["local_parcel_polygon"]);x0,y0,x1,y1=parcel.bounds
        split=y0+(y1-y0)*.525; min_width=source["minab_rules"]["rules"]["main_space_lightwell_min_width"]["value"]
        min_area=source["minab_rules"]["rules"]["main_space_lightwell_min_area"]["value"]
        width=min_width if family not in ("NS-C","NS-D") else min_width+.2
        depth=min_area/width if family not in ("NS-C","NS-D") else 4.2
        center_x=(x0+x1)/2
        if family in ("NS-B","NS-F"):
            lobby=Polygon(c["common_lobby_polygon"]); center_x=x0+(x1-x0)*(.32 if lobby.centroid.x>(x0+x1)/2 else .68)
        if family=="NS-C": center_x=x0+(x1-x0)*.62
        if family=="NS-D": center_x=x0+(x1-x0)*.45
        cx=max(x0+width/2,min(x1-width/2,center_x)); court=box(cx-width/2,split-depth/2,cx+width/2,split+depth/2)
        core=Polygon(c["pilot_core_xy"]); bases=[parcel.intersection(box(x0,y0,x1,split)),parcel.intersection(box(x0,split,x1,y1))]
        units=[b.difference(unary_union([core,court])) for b in bases]; terraces=[]
        for i,u in enumerate(units):
            shape=max(u.geoms,key=lambda g:g.area) if u.geom_type=="MultiPolygon" else u
            mode="south_recessed" if i==0 else "internal_lightwell_adjacent"
            terrace=ResidentialPrivateTerraceTopologyV1().resolve(f"UNIT-{i+1}",self._poly(shape),mode,[[x0,y0],[x1,y0]],self._poly(court),i+1)
            terraces.append(terrace)
            if terrace["terrace_polygon"]: units[i]=u.difference(Polygon(terrace["terrace_polygon"]))
        unit_polys=[self._poly(max(u.geoms,key=lambda g:g.area) if u.geom_type=="MultiPolygon" else u) for u in units]
        maintenance=SharedDaylightCourtMaintenanceAccessV1().resolve(c["common_lobby_polygon"],self._poly(court),unit_polys)
        if maintenance["corridor_reservation_required"]:
            clearance=Polygon(maintenance["maintenance_clearance_geometry"])
            for i,u in enumerate(units):
                carved=u.difference(clearance);units[i]=max(carved.geoms,key=lambda g:g.area) if carved.geom_type=="MultiPolygon" else carved
            maintenance["private_unit_crossing"]=False;maintenance["access_status"]="resolved_by_explicit_common_corridor_reservation"
        units=[max(u.geoms,key=lambda g:g.area) if u.geom_type=="MultiPolygon" else u for u in units]
        unit_polys=[self._poly(u) for u in units]
        lobby=Polygon(c["common_lobby_polygon"]);entries=[]
        for u in units:
            b=u.exterior.interpolate(u.exterior.project(lobby.centroid));entries.append([b.x,b.y])
        graph=ResidentialCommonAccessGraphV1().resolve(c["stair"],c["elevator"],c["common_lobby_polygon"],entries,unit_polys,maintenance)
        shared=SharedResidentialDaylightCourtIntelligenceV1().resolve(self._poly(court),unit_polys)
        c["unit_envelopes"]=[{**c["unit_envelopes"][i],"polygon":unit_polys[i],"entry_point":entries[i],"metrics":{**c["unit_envelopes"][i]["metrics"],"unit_area":units[i].area}} for i in range(2)]
        c.update({"lightwell":{**c["lightwell"],"polygon":self._poly(court),"area":court.area,"minimum_width":min(width,depth)},"terraces":terraces,
                  "unit_1_area":units[0].area,"unit_2_area":units[1].area,"shared_daylight_court":shared,"shared_daylight_court_maintenance_access":maintenance,
                  "residential_common_access_graph":graph,"unit_entry_doors":graph["unit_entry_doors"],"maintenance_door":maintenance["maintenance_door"],
                  "hard_rejection_reasons":[],"hard_validation_status":"hard_valid"})
        return c

    def _candidate(self, raw, family, source, case_definition, privacy_variant=False, projection_variant=False, counterexample=False):
        c = deepcopy(raw)
        units = [u["polygon"] for u in c["unit_envelopes"]]
        terraces = c["terraces"]
        privacy = SharedCourtTerracePrivacySeparationV1().resolve(
            c["shared_daylight_court"]["court_polygon"], units, terraces,
            c["shared_daylight_court_maintenance_access"], source["minab_rules"],
            wall_thickness=0.12, wall_start_level=case_definition.get("first_residential_floor_level", 0.0),
            wall_end_level=case_definition.get("top_residential_level"),
        )
        if not privacy_variant:
            privacy = {**privacy, "privacy_wall_centerline":[], "privacy_wall_polygon":[], "privacy_wall_thickness":None,
                       "divider_topology_status":"alternative_without_constructed_divider", "failure_reasons":[]}
        projection_enabled = projection_variant and c["projection_mode"].endswith("enabled")
        stack = ProjectionVerticalStackIntelligenceV1().resolve(
            case_definition.get("vertical_levels", {}),
            source["minab_rules"]["rules"]["projection_public_road_min_clear_height"]["value"],
            case_definition.get("road_reference_elevation", 0.0), projection_enabled,
        )
        projection_width = c["projection_opportunity"]["public_road_projection"].get("projection_width", 0) if projection_enabled else 0
        projection_area = projection_width * source["source_road_width"] if projection_width and stack["usable_projection_area_claim_permitted"] else 0.0
        spaces = [
            {"space_id":"UNIT-SOUTH" if c["split_family"] == "R-NS" else "UNIT-1", "classification":"PRIVATE_UNIT", "polygon":units[0]},
            {"space_id":"UNIT-NORTH" if c["split_family"] == "R-NS" else "UNIT-2", "classification":"PRIVATE_UNIT", "polygon":units[1]},
            {"space_id":"COMMON-LOBBY", "classification":"COMMON", "polygon":c["common_lobby_polygon"]},
            {"space_id":"STAIR", "classification":"VERTICAL_CIRCULATION", "polygon":c["stair"]["landing_geometry"]},
            {"space_id":"ELEVATOR", "classification":"VERTICAL_CIRCULATION", "polygon":c["elevator"]["polygon"]},
            {"space_id":"SHARED-DAYLIGHT-COURT", "classification":"DAYLIGHT_COURT", "polygon":privacy["clear_daylight_court_polygon"] or c["shared_daylight_court"]["court_polygon"]},
        ]
        spaces += [{"space_id":t["terrace_id"], "classification":"PRIVATE_TERRACE", "polygon":t["terrace_polygon"]} for t in terraces if t["terrace_polygon"]]
        if privacy["privacy_wall_polygon"]:
            spaces.append({"space_id":"PRIVACY-WALL", "classification":"STRUCTURAL_OR_SHAFT_RESERVATION", "polygon":privacy["privacy_wall_polygon"]})
        utilization = BuildableSpaceUtilizationIntelligenceV1().resolve(source["local_parcel_polygon"], spaces, projection_area)
        for index,residual in enumerate(utilization["unallocated_residual_polygons"]):
            if residual["usability"] != "usable": continue
            shape=Polygon(residual["polygon"]);receivers=[x for x in spaces if x["classification"] in ("PRIVATE_UNIT","COMMON")]
            receiver=max(receivers,key=lambda x:Polygon(x["polygon"]).boundary.intersection(shape.boundary).length)
            if Polygon(receiver["polygon"]).boundary.intersection(shape.boundary).length > .1:
                spaces.append({"space_id":f'{receiver["space_id"]}-RESIDUAL-MERGE-{index+1}',"classification":receiver["classification"],"polygon":residual["polygon"],"allocation_source":"adjacency_based_usable_residual_merge"})
        utilization = BuildableSpaceUtilizationIntelligenceV1().resolve(source["local_parcel_polygon"], spaces, projection_area)
        unit_metrics = [self._shape_metrics(Polygon(u)) for u in units]
        hard = list(c["hard_rejection_reasons"])
        if not c["shared_daylight_court"]["court_serves_both_units"]: hard.append("shared_court_does_not_serve_both_units")
        if c["split_family"] == "R-NS" and any(t["terrace_area"] <= 0 for t in terraces): hard.append("missing_private_terrace")
        if privacy_variant and privacy["divider_topology_status"] == "rejected": hard += privacy["failure_reasons"]
        penalties = list(dict.fromkeys(c["architectural_quality_penalties"] + utilization["architectural_quality_penalties"]))
        c.update({
            "contract":"ResidentialNSSharedCourtRefinementCandidateV1", "candidate_id":f"{family}-{c['projection_mode'].upper()}",
            "refinement_family":family, "candidate_role":"secondary_counterexample" if counterexample else "ns_preferred_search",
            "unit_south_polygon":units[0] if c["split_family"] == "R-NS" else None,
            "unit_north_polygon":units[1] if c["split_family"] == "R-NS" else None,
            "shared_court_terrace_privacy_separation":privacy, "projection_vertical_stack":stack,
            "buildable_space_utilization":utilization,
            "quality_metrics":{
                "unit_area_balance":min(Polygon(units[0]).area,Polygon(units[1]).area)/max(Polygon(units[0]).area,Polygon(units[1]).area),
                "unit_aspect_ratio":[m["aspect_ratio"] for m in unit_metrics], "largest_usable_rectangle":[m["largest_rectangle_area"] for m in unit_metrics],
                "maximum_effective_depth":[m["maximum_depth"] for m in unit_metrics], "compactness":[m["compactness"] for m in unit_metrics],
                "corridor_likeness":[m["corridor_likeness"] for m in unit_metrics],
                "shared_court_daylight_balance":c["shared_daylight_court"]["daylight_balance_ratio"],
                "terrace_quality":"private_access_resolved" if all(t["access_from_unit_status"] == "private_access_resolved" for t in terraces) else "failed",
                "common_area":utilization["common_area"], "common_path_length":c["common_access_length"],
                "maintenance_access_cost":c["shared_daylight_court_maintenance_access"]["maintenance_path_length"],
                "privacy_conflicts":1 if privacy["privacy_conflict_detected"] and privacy["divider_topology_status"] != "accepted" else 0,
                "unallocated_buildable_area":utilization["unallocated_buildable_area"],
                "unallocated_buildable_area_ratio":utilization["unallocated_buildable_area_ratio"],
                "projection_net_architectural_gain":projection_area,
            },
            "north_unit_terrace_adjacent_to_shared_daylight_court":bool(c["split_family"] == "R-NS" and terraces[1]["terrace_open_edge"] == "central_lightwell"),
            "maintenance_access_source":"COMMON", "architectural_quality_penalties":penalties,
            "hard_rejection_reasons":list(dict.fromkeys(hard)), "hard_validation_status":"hard_valid" if not hard else "not_feasible",
            "room_polygons_generated":False, "final_windows_generated":False,
        })
        return c

    @staticmethod
    def _shape_metrics(shape):
        x0,y0,x1,y1=shape.bounds; w=x1-x0; d=y1-y0; short=max(min(w,d),1e-6)
        return {"aspect_ratio":max(w,d)/short, "maximum_depth":max(w,d),
                "compactness":4*pi*shape.area/(shape.length**2) if shape.length else 0,
                "corridor_likeness":min(1.0,max(0.0,(max(w,d)/short-1)/4)),
                "largest_rectangle_area":shape.envelope.intersection(shape).area}

    @staticmethod
    def _poly(shape):
        return [[float(x),float(y)] for x,y in list(shape.exterior.coords)[:-1]]

    @staticmethod
    def _rank(c):
        q=c["quality_metrics"]
        access = c["residential_common_access_graph"]["graph_status"] == "resolved"
        daylight = c["shared_daylight_court"]["court_serves_both_units"]
        privacy = -q["privacy_conflicts"]
        terrace = q["terrace_quality"] == "private_access_resolved"
        utilization = -q["unallocated_buildable_area_ratio"]
        proportions = -max(q["unit_aspect_ratio"])
        return (access, daylight, privacy, terrace, utilization, proportions, -q["common_area"], q["unit_area_balance"], q["projection_net_architectural_gain"])
