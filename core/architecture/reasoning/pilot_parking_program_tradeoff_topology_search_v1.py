"""K-family whole-plan program trade-off topology search."""
from copy import deepcopy
from math import hypot

from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform, unary_union

from core.architecture.reasoning.circulation_termination_intelligence_v1 import CirculationTerminationIntelligenceV1
from core.architecture.reasoning.post_parking_pedestrian_access_v1 import PostParkingPedestrianAccessV1
from core.architecture.reasoning.residual_space_program_allocator_v1 import ResidualSpaceProgramAllocatorV1


class PilotParkingProgramTradeoffTopologySearchV1:
    EPS = 1e-5
    FAMILIES = tuple(f"PILOT-K{i:02d}" for i in range(1, 8))
    MANEUVER_TARGETS = (4.5, 5.0, 5.25)
    CAPACITIES = (2, 3, 4)
    SIDES = ("west", "east")

    DEFAULT_PREFERENCES = {
        "allow_combined_vehicle_pedestrian_gate": True,
        "allow_shared_vehicle_pedestrian_access": False,
        "prefer_independent_pedestrian_entrance": True,
        "prefer_maximum_commercial_frontage": False,
        "prefer_maximum_parking": False,
        "require_residential_storage": False,
        "require_common_wc": False,
    }

    def resolve(self, site, requirements, baseline_scenario_a, preferences=None):
        before_site, before_a = deepcopy(site), deepcopy(baseline_scenario_a)
        prefs = dict(self.DEFAULT_PREFERENCES)
        prefs.update(preferences or {})
        frame = self._frame(site["parcel"], site["frontage"])
        parcel = self._to_local(Polygon(site["parcel"]), frame)
        entrance_modes = ["independent_vehicle_gate_and_independent_pedestrian_gate",
                          "adjacent_vehicle_and_pedestrian_gate"]
        if prefs["allow_combined_vehicle_pedestrian_gate"]:
            entrance_modes.append("combined_vehicle_pedestrian_gate_with_wicket")
        if prefs["allow_shared_vehicle_pedestrian_access"]:
            entrance_modes.append("shared_vehicle_pedestrian_access")
        candidates = []
        for family in self.FAMILIES:
            for side in self.SIDES:
                for mode in entrance_modes:
                    for capacity in self.CAPACITIES:
                        for target in self.MANEUVER_TARGETS:
                            candidates.append(self._candidate(family, side, mode, capacity, target,
                                                              parcel, requirements, prefs))
        valid = [c for c in candidates if c["hard_geometry_status"] == "hard_valid"]
        review = self._tradeoff_review(valid)
        assert site == before_site and baseline_scenario_a == before_a
        return {
            "contract": "PilotParkingProgramTradeoffTopologySearchV1",
            "site": "REAL Parcel 2", "site_source": site.get("source"),
            "source_parcel": site["parcel"], "source_frontage": site["frontage"],
            "source_road_width": site.get("road_width"), "coordinate_system": "parcel_local_frontage_aligned",
            "local_parcel_polygon": self._poly(parcel), "topology_families_explored": list(self.FAMILIES),
            "entrance_modes_explored": entrance_modes,
            "maneuvering_search_targets": {"values": list(self.MANEUVER_TARGETS),
                "classification": "engineering_maneuvering_search_target", "regulatory_requirement": False},
            "preferences": prefs, "candidate_count": len(candidates), "hard_valid_candidate_count": len(valid),
            "candidates": candidates, "human_review_candidate_ids": [c["candidate_id"] for c in review],
            "human_review_candidates": review, "final_selection_performed": False,
            "final_scenario_b_candidate": None, "human_architect_review_required": True,
            "baseline_scenario_a": before_a, "baseline_geometry_preserved": True,
            "program_changed": False, "basement_deleted": False, "basement_removal_approved": False,
            "structure_executed": False, "bim_executed": False, "ifc_executed": False,
            "regulatory_status": "pending_rule_resolution",
        }

    def _candidate(self, family, side, mode, capacity, target, parcel, requirements, base_prefs):
        x0, y0, x1, y1 = parcel.bounds
        parking, core_req = requirements["parking"], requirements["core"]
        sw, sd = map(float, (parking["stall_width"], parking["stall_depth"]))
        ped_w = float(requirements["parking_pedestrian"]["required_clear_width"])
        vehicle_w = 3.5 if mode == "combined_vehicle_pedestrian_gate_with_wicket" else 3.25
        west = side == "west"
        vehicle = [x0, x0+vehicle_w] if west else [x1-vehicle_w, x1]
        if mode == "independent_vehicle_gate_and_independent_pedestrian_gate":
            ped = [x1-ped_w, x1] if west else [x0, x0+ped_w]
        elif mode == "adjacent_vehicle_and_pedestrian_gate":
            ped = [vehicle[1], vehicle[1]+ped_w] if west else [vehicle[0]-ped_w, vehicle[0]]
        else:
            ped = [vehicle[1]-ped_w, vehicle[1]] if west else [vehicle[0], vehicle[0]+ped_w]
        core_w = float(core_req["stair_reserved_zone"][0])+float(core_req["elevator_shaft_clear"][0])
        core_d = max(float(core_req["stair_reserved_zone"][1]), float(core_req["lobby_clear"][1]))
        total_w = capacity*sw
        # Rear-terminal transverse parking; capacity four uses the full real frontage width.
        stall_x0 = x0+(x1-x0-total_w)/2
        stalls_geom = [box(stall_x0+i*sw, y1-sd, stall_x0+(i+1)*sw, y1) for i in range(capacity)]
        maneuver_y1, maneuver_y0 = y1-sd, y1-sd-target
        maneuver_x0 = x0 if west else x1-target
        maneuver = box(maneuver_x0, maneuver_y0, maneuver_x0+target, maneuver_y1)
        core_y1 = maneuver_y0-0.25
        core_y0 = core_y1-core_d
        core_x0 = x1-core_w if west else x0
        core = box(core_x0, core_y0, core_x0+core_w, core_y1)
        stair_w, stair_d = map(float, core_req["stair_reserved_zone"])
        lobby_d = float(core_req["lobby_clear"][1])
        lobby = box(core_x0, core_y1-lobby_d, core_x0+core_w, core_y1)
        stair = box(core_x0, core_y0, core_x0+stair_w, core_y1-lobby_d)
        elevator = box(core_x0+stair_w, core_y0, core_x0+core_w,
                       min(core_y1-lobby_d, core_y0+float(core_req["elevator_shaft_clear"][1])))
        vehicle_center = sum(vehicle)/2
        vehicle_term = CirculationTerminationIntelligenceV1().resolve(
            [vehicle_center, y0], [0, 1], [[vehicle_center, maneuver_y1]], vehicle_w, [vehicle_center, y1])
        drive = Polygon(vehicle_term["corridor"])
        ped_center = sum(ped)/2
        street_target = [lobby.centroid.x, lobby.centroid.y]
        street_line = LineString([(ped_center, y0), (ped_center, street_target[1]), tuple(street_target)])
        street_corridor = street_line.buffer(ped_w/2, cap_style=2, join_style=2)
        storefront_left = vehicle[1] if west else x0
        storefront_right = x1 if west else vehicle[0]
        if mode == "independent_vehicle_gate_and_independent_pedestrian_gate":
            storefront_right = ped[0] if west else vehicle[0]
            storefront_left = vehicle[1] if west else ped[1]
        commercial_depth = max(0, core_y0-y0-0.25)
        commercial = box(storefront_left, y0, storefront_right, y0+commercial_depth)
        stalls = [{"stall_id": f"P-{i+1:02d}", "polygon": self._poly(p)} for i, p in enumerate(stalls_geom)]
        post = PostParkingPedestrianAccessV1().resolve(
            stalls, self._poly(lobby), self._poly(core), [self._poly(drive), self._poly(maneuver)],
            self._poly(parcel), ped_w)
        occupied = [self._poly(g) for g in [drive, maneuver, core, commercial, street_corridor]]
        occupied += [s["polygon"] for s in stalls]
        for access in post["stall_results"]:
            occupied += access["protected_pedestrian_segment"]
        prefs = dict(base_prefs)
        prefs["commercial_anchor"] = self._poly(commercial)
        prefs["require_residential_storage"] = family in ("PILOT-K04", "PILOT-K05")
        prefs["require_common_wc"] = family == "PILOT-K05"
        priorities = {
            "PILOT-K02": ["commercial"], "PILOT-K04": ["storage"],
            "PILOT-K05": ["storage", "wc"],
        }.get(family, [])
        residual = ResidualSpaceProgramAllocatorV1().resolve(self._poly(parcel), occupied, priorities, prefs)
        failures = self._failures(parcel, stalls_geom, core, drive, maneuver, street_corridor, commercial, post)
        hard_status = "hard_valid" if not failures else "not_feasible"
        commercial_area = commercial.area + residual["residual_area_allocated_to_commercial"]
        metrics = self._metrics(parcel, drive, maneuver, street_corridor, commercial_area, storefront_right-storefront_left,
                                core, stalls_geom, post, residual, vehicle_term, street_line)
        cid = f"{family}-{side.upper()}-{self._mode_code(mode)}-P{capacity}-M{target:.2f}"
        return {
            "contract": "PilotParkingProgramTradeoffCandidateV1", "candidate_id": cid, "family": family,
            "tradeoff_intent": self._intent(family), "access_side": side, "entrance_mode": mode,
            "entrance_mode_user_preference_required": mode == "combined_vehicle_pedestrian_gate_with_wicket",
            "entrance_mode_regulatory_status": "pending_rule_resolution",
            "parking_count": capacity, "independently_usable_parking_count": 0,
            "parking_count_pending_vehicle_model_validation": capacity if hard_status == "hard_valid" else 0,
            "vehicle_entrance": [[vehicle[0], y0], [vehicle[1], y0]], "frontage_vehicle_width": vehicle_w,
            "pedestrian_entrance": [[ped[0], y0], [ped[1], y0]], "frontage_pedestrian_width": ped_w,
            "commercial_entrance": [[storefront_left, y0], [storefront_right, y0]],
            "commercial_storefront": [[storefront_left, y0], [storefront_right, y0]],
            "commercial_field": self._poly(commercial), "parking_stalls": stalls,
            "drive_lane": self._poly(drive), "vehicle_access_axis": vehicle_term["centerline"],
            "vehicle_lane_endpoint": vehicle_term["last_functional_destination"],
            "maneuvering_field": self._poly(maneuver), "maneuvering_field_dimensions": [target, target],
            "maneuvering_field_source": "engineering_maneuvering_search_target",
            "vehicle_maneuvering_status": "pending_vehicle_model_validation" if hard_status == "hard_valid" else "not_feasible",
            "street_to_core_path": self._line(street_line), "street_to_core_corridor": self._poly(street_corridor),
            "post_parking_pedestrian_access": post,
            "core": {"polygon": self._poly(core), "stair": self._poly(stair), "elevator": self._poly(elevator),
                     "lobby": self._poly(lobby), "location": "between_front_commercial_and_rear_parking"},
            "residual_space_program": residual, "metrics": metrics,
            "hard_geometry_status": hard_status, "hard_rejection_reasons": list(dict.fromkeys(failures)),
            "architectural_penalties": self._penalties(metrics), "regulatory_status": "pending_rule_resolution",
            "final_selection_eligible": False,
        }

    def _failures(self, parcel, stalls, core, drive, maneuver, pedestrian, commercial, post):
        failures = []
        for geometry, reason in [(core, "core_outside_parcel"), (drive, "vehicle_access_outside_parcel"),
                                 (maneuver, "maneuvering_outside_parcel"), (pedestrian, "pedestrian_access_outside_parcel"),
                                 (commercial, "commercial_access_impossible")]+[(s, "stall_outside_parcel") for s in stalls]:
            if geometry.is_empty or not parcel.buffer(self.EPS).covers(geometry): failures.append(reason)
        su = unary_union(stalls)
        if core.intersection(su).area > self.EPS: failures.append("core_stall_overlap")
        for i, stall in enumerate(stalls):
            if any(stall.intersection(other).area > self.EPS for other in stalls[i+1:]): failures.append("stall_stall_overlap")
        if core.intersection(drive).area > self.EPS: failures.append("core_vehicle_access_blockage")
        if not post["all_parking_users_reach_core_internally"]: failures.append("parking_user_cannot_reach_core_internally")
        return failures

    def _metrics(self, parcel, drive, maneuver, pedestrian, commercial_area, frontage, core, stalls, post, residual, vt, street_line):
        vehicle_area = unary_union([drive, maneuver]).area
        pedestrian_area = pedestrian.area + sum(sum(Polygon(p).area for p in r["protected_pedestrian_segment"])
                                                for r in post["stall_results"])
        programmed = commercial_area+core.area+sum(s.area for s in stalls)+residual["residential_storage_total_area"]+residual["residual_area_allocated_to_wc"]
        return {
            "parking_count": len(stalls), "parking_count_pending_vehicle_model_validation": len(stalls),
            "maneuvering_field_area": maneuver.area, "maneuvering_field_dimensions": [maneuver.bounds[2]-maneuver.bounds[0], maneuver.bounds[3]-maneuver.bounds[1]],
            "frontage_vehicle_width": drive.bounds[2]-drive.bounds[0], "frontage_pedestrian_width": pedestrian.bounds[2]-pedestrian.bounds[0],
            "commercial_frontage": frontage, "parking_to_core_path_length": post["parking_to_core_path_length"],
            "parking_to_core_crossing_count": post["parking_to_core_crossing_count"],
            "street_to_core_path_length": street_line.length, "commercial_area": commercial_area,
            "largest_commercial_rectangle": commercial_area-residual["residual_area_allocated_to_commercial"],
            "residential_storage_count": residual["residential_storage_count"],
            "residential_storage_total_area": residual["residential_storage_total_area"],
            "common_wc_generated": residual["common_wc_generated"], "unallocated_residual_area": residual["unallocated_residual_area"],
            "vehicle_circulation_area": vehicle_area, "pedestrian_circulation_area": pedestrian_area,
            "common_circulation_area": pedestrian_area, "total_circulation_area": unary_union([drive, maneuver, pedestrian]).area,
            "service_area": core.area+sum(s.area for s in stalls)+residual["residential_storage_total_area"]+residual["residual_area_allocated_to_wc"],
            "net_programmed_area": programmed, "whole_plan_space_utilization_ratio": programmed/parcel.area,
            "vehicle_circulation_length": vt["circulation_length"], "pedestrian_circulation_length": street_line.length,
            "vehicle_dead_run_length": 0.0, "pedestrian_dead_run_length": 0.0,
        }

    @staticmethod
    def _penalties(m):
        out=[]
        if m["unallocated_residual_area"] > 15: out.append("unexplained_residual_space")
        if m["total_circulation_area"] > 60: out.append("excessive_common_circulation")
        if m["commercial_frontage"] < 4: out.append("poor_commercial_frontage")
        return out

    def _tradeoff_review(self, valid):
        selectors = [
            ("PILOT-K01", lambda c: (c["parking_count"], c["metrics"]["commercial_frontage"])),
            ("PILOT-K02", lambda c: (c["metrics"]["commercial_area"], -c["metrics"]["unallocated_residual_area"])),
            ("PILOT-K03", lambda c: (c["metrics"]["whole_plan_space_utilization_ratio"], -c["metrics"]["total_circulation_area"])),
            ("PILOT-K04", lambda c: (c["metrics"]["residential_storage_count"], c["parking_count"])),
            ("PILOT-K05", lambda c: (c["metrics"]["common_wc_generated"], c["metrics"]["residential_storage_count"])),
            ("PILOT-K06", lambda c: (c["metrics"]["maneuvering_field_area"], c["metrics"]["commercial_area"])),
        ]
        review=[]
        for family, key in selectors:
            pool=[c for c in valid if c["family"] == family]
            if pool: review.append(max(pool, key=key))
        combined=[c for c in valid if c["entrance_mode"] == "combined_vehicle_pedestrian_gate_with_wicket"]
        if combined and not any(c["entrance_mode"] == "combined_vehicle_pedestrian_gate_with_wicket" for c in review):
            review.append(max(combined, key=lambda c: c["metrics"]["commercial_frontage"]))
        return review[:7]

    @staticmethod
    def _intent(f):
        return {"PILOT-K01":"parking_priority", "PILOT-K02":"commercial_priority", "PILOT-K03":"balanced",
                "PILOT-K04":"parking_and_storage", "PILOT-K05":"parking_storage_and_common_wc",
                "PILOT-K06":"large_maneuver_field", "PILOT-K07":"geometry_discovered"}[f]

    @staticmethod
    def _mode_code(mode):
        return {"independent_vehicle_gate_and_independent_pedestrian_gate":"A",
                "adjacent_vehicle_and_pedestrian_gate":"B",
                "combined_vehicle_pedestrian_gate_with_wicket":"C",
                "shared_vehicle_pedestrian_access":"D"}[mode]

    @staticmethod
    def _frame(parcel, frontage):
        a,b=frontage; length=hypot(b[0]-a[0],b[1]-a[1]); ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
        nx,ny=-uy,ux; centroid=Polygon(parcel).centroid
        if (centroid.x-a[0])*nx+(centroid.y-a[1])*ny < 0: nx,ny=-nx,-ny
        return a[0],a[1],ux,uy,nx,ny

    @staticmethod
    def _to_local(g,f):
        ox,oy,ux,uy,nx,ny=f
        return transform(lambda x,y,z=None:((x-ox)*ux+(y-oy)*uy,(x-ox)*nx+(y-oy)*ny),g)

    @staticmethod
    def _poly(p): return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
    @staticmethod
    def _line(p): return [[float(x),float(y)] for x,y in p.coords]
