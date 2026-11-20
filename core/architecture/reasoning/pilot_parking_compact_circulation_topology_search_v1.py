"""Compact-circulation J-family whole-plan topology search."""
from copy import deepcopy
from math import hypot, pi

from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform, unary_union

from core.architecture.reasoning.circulation_termination_intelligence_v1 import (
    CirculationTerminationIntelligenceV1,
)


class PilotParkingCompactCirculationTopologySearchV1:
    EPS = 1e-5
    FAMILIES = tuple(f"PILOT-J{i:02d}" for i in range(1, 7))
    VEHICLE_WIDTHS = (3.0, 3.25, 3.5)
    CAPACITIES = (2, 3)
    MANEUVER_TARGETS = (4.25, 4.5, 4.75)

    def resolve(self, site, requirements, baseline_scenario_a):
        before_site, before_a = deepcopy(site), deepcopy(baseline_scenario_a)
        frame = self._frame(site["parcel"], site["frontage"])
        parcel = self._to_local(Polygon(site["parcel"]), frame)
        candidates = []
        for family in self.FAMILIES:
            for side in ("west", "east"):
                for width in self.VEHICLE_WIDTHS:
                    for capacity in self.CAPACITIES:
                        candidates.append(self._candidate(family, side, width, capacity, parcel, requirements))
        valid = [c for c in candidates if c["hard_geometry_status"] == "hard_valid"]
        shortlist = self._shortlist(valid, 5)
        assert site == before_site and baseline_scenario_a == before_a
        return {
            "contract": "PilotParkingCompactCirculationTopologySearchV1",
            "site": "REAL Parcel 2",
            "site_source": site.get("source"),
            "source_parcel": site["parcel"],
            "source_frontage": site["frontage"],
            "source_road_width": site.get("road_width"),
            "coordinate_system": "parcel_local_frontage_aligned",
            "local_parcel_polygon": self._poly(parcel),
            "topology_families_explored": list(self.FAMILIES),
            "maneuvering_search_targets": {"values": list(self.MANEUVER_TARGETS),
                "classification": "engineering_maneuvering_search_target", "regulatory_requirement": False},
            "candidate_count": len(candidates),
            "hard_valid_candidate_count": len(valid),
            "candidates": candidates,
            "human_review_candidate_ids": [c["candidate_id"] for c in shortlist],
            "human_review_candidates": shortlist,
            "final_selection_performed": False,
            "final_scenario_b_candidate": None,
            "human_architect_review_required": True,
            "baseline_scenario_a": before_a,
            "baseline_geometry_preserved": True,
            "program_changed": False,
            "basement_deleted": False,
            "basement_removal_approved": False,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "regulatory_status": "pending_rule_resolution",
        }

    def _candidate(self, family, side, entrance_width, capacity, parcel, requirements):
        x0, y0, x1, y1 = parcel.bounds
        parking, core_req = requirements["parking"], requirements["core"]
        sw, sd = float(parking["stall_width"]), float(parking["stall_depth"])
        ped_w = float(requirements["parking_pedestrian"]["required_clear_width"])
        core_w = float(core_req["stair_reserved_zone"][0])+float(core_req["elevator_shaft_clear"][0])
        core_d = max(float(core_req["stair_reserved_zone"][1]), float(core_req["lobby_clear"][1]))
        west = side == "west"
        vehicle = [x0, x0+entrance_width] if west else [x1-entrance_width, x1]
        ped = [x1-ped_w, x1] if west else [x0, x0+ped_w]
        commercial_x = [vehicle[1], ped[0]] if west else [ped[1], vehicle[0]]
        target = self.MANEUVER_TARGETS[(self.FAMILIES.index(family)) % len(self.MANEUVER_TARGETS)]
        transverse = family != "PILOT-J03"

        if transverse:
            total_w = capacity*sw
            stall_x0 = x0 if west else x1-total_w
            stalls = [box(stall_x0+i*sw, y1-sd, stall_x0+(i+1)*sw, y1) for i in range(capacity)]
            maneuver_y1 = y1-sd
            maneuver_y0 = maneuver_y1-target
            maneuver_x0 = x0 if west else x1-target
            maneuver = box(maneuver_x0, maneuver_y0, maneuver_x0+target, maneuver_y1)
            last_vehicle = [sum(vehicle)/2, maneuver_y1]
            parking_mode = "rear_transverse_head_in_or_reverse_in_pending_vehicle_model"
        else:
            stall_x0 = vehicle[1] if west else vehicle[0]-sw
            stall_y0 = y1-capacity*sd
            stalls = [box(stall_x0, stall_y0+i*sd, stall_x0+sw, stall_y0+(i+1)*sd) for i in range(capacity)]
            maneuver_y0 = max(y0, stall_y0-target)
            maneuver_y1 = stall_y0
            maneuver_x0 = x0 if west else x1-target
            maneuver = box(maneuver_x0, maneuver_y0, maneuver_x0+target, maneuver_y1)
            last_vehicle = [sum(vehicle)/2, y1]
            parking_mode = "rear_side_longitudinal_direct_access"

        core_y0 = max(y0, maneuver_y0-core_d-0.5)
        if family == "PILOT-J05":
            core_y0 = max(y0, maneuver_y0-core_d)
        if family == "PILOT-J06":
            core_y0 = max(y0, maneuver_y0-core_d/2)
        core_x0 = x1-core_w if west else x0
        core = box(core_x0, core_y0, core_x0+core_w, core_y0+core_d)
        stair_w, stair_d = map(float, core_req["stair_reserved_zone"])
        stair = box(core_x0, core_y0, core_x0+stair_w, core_y0+stair_d)
        lobby_d = float(core_req["lobby_clear"][1])
        lobby = box(core_x0+stair_w, core_y0, core_x0+core_w, core_y0+lobby_d)
        elevator = box(core_x0+stair_w, core_y0+lobby_d, core_x0+core_w,
                       core_y0+lobby_d+float(core_req["elevator_shaft_clear"][1]))
        vehicle_term = CirculationTerminationIntelligenceV1().resolve(
            [sum(vehicle)/2, y0], [0, 1], [last_vehicle], entrance_width, [sum(vehicle)/2, y1])
        pedestrian_target = [sum(ped)/2, core_y0+lobby_d/2]
        ped_term = CirculationTerminationIntelligenceV1().resolve(
            [sum(ped)/2, y0], [0, 1], [pedestrian_target], ped_w, [sum(ped)/2, y1])
        drive_lane = Polygon(vehicle_term["corridor"])
        pedestrian_corridor = Polygon(ped_term["corridor"])
        commercial_depth = max(0.0, core_y0-0.5-y0)
        commercial = box(commercial_x[0], y0, commercial_x[1], y0+commercial_depth)
        stall_union = unary_union(stalls)
        failures = []
        for geometry, reason in [(drive_lane, "vehicle_access_outside_parcel"), (maneuver, "maneuvering_outside_parcel"),
                                 (pedestrian_corridor, "pedestrian_access_outside_parcel"), (core, "core_outside_parcel"),
                                 (commercial, "commercial_outside_parcel")]+[(s, "stall_outside_parcel") for s in stalls]:
            if geometry.is_empty or not parcel.buffer(self.EPS).covers(geometry): failures.append(reason)
        if core.intersection(stall_union).area > self.EPS: failures.append("core_stall_overlap")
        if core.intersection(drive_lane).area > self.EPS: failures.append("core_vehicle_access_blockage")
        if pedestrian_corridor.intersection(stall_union.union(maneuver).union(drive_lane)).area > self.EPS: failures.append("pedestrian_vehicle_conflict")
        if commercial.intersection(unary_union([drive_lane, pedestrian_corridor, core, maneuver, stall_union])).area > self.EPS: failures.append("commercial_service_overlap")
        if not LineString(ped_term["centerline"]).intersects(lobby): failures.append("core_access_failure")
        metrics = self._metrics(parcel, drive_lane, vehicle_term, pedestrian_corridor, ped_term,
                                stalls, maneuver, core, commercial, y1)
        status = "hard_valid" if not failures else "not_feasible"
        cid = f"{family}-{side.upper()}-W{entrance_width:.2f}-P{capacity}"
        return {
            "contract": "PilotParkingCompactCirculationCandidateV1", "candidate_id": cid,
            "family": family, "access_side": side, "parking_topology": parking_mode,
            "parking_count": len(stalls), "independently_usable_parking_count": 0,
            "parking_count_pending_vehicle_model_validation": len(stalls) if status == "hard_valid" else 0,
            "vehicle_entrance": [[vehicle[0], y0], [vehicle[1], y0]], "vehicle_entrance_width": entrance_width,
            "vehicle_entrance_width_source": "engineering_design_search_range",
            "vehicle_access_axis": vehicle_term["centerline"], "vehicle_lane_endpoint": vehicle_term["last_functional_destination"],
            "drive_lane": self._poly(drive_lane), "maneuvering_field": self._poly(maneuver),
            "maneuvering_field_dimensions": [target, target], "maneuvering_field_source": "engineering_maneuvering_search_target",
            "parking_stalls": [{"stall_id": f"P-{i+1:02d}", "polygon": self._poly(s)} for i, s in enumerate(stalls)],
            "vehicle_maneuvering_status": "pending_vehicle_model_validation" if status == "hard_valid" else "not_feasible",
            "vehicle_swept_path_generated": False,
            "pedestrian_entrance": [[ped[0], y0], [ped[1], y0]], "pedestrian_path": ped_term["centerline"],
            "pedestrian_corridor": self._poly(pedestrian_corridor), "pedestrian_corridor_endpoint": ped_term["last_functional_destination"],
            "commercial_entrance": [[commercial_x[0], y0], [commercial_x[1], y0]],
            "commercial_storefront": [[commercial_x[0], y0], [commercial_x[1], y0]],
            "commercial_field": self._poly(commercial), "largest_usable_rectangle": self._poly(commercial),
            "core": {"polygon": self._poly(core), "stair": self._poly(stair), "elevator": self._poly(elevator),
                     "lobby": self._poly(lobby), "location": "between_commercial_and_parking_or_rear_side"},
            "circulation_termination": {"vehicle": vehicle_term, "pedestrian": ped_term},
            "metrics": metrics,
            "upper_floor_access_consequence": {
                "common_access_path_length": ped_term["circulation_length"],
                "likely_common_area_consumption": pedestrian_corridor.area+core.area,
                "core_position_flexibility": "jointly_searchable_in_service_pocket",
                "two_unit_distribution_potential": "preserved_for_future_geometry_not_proven",
                "apartment_rooms_generated": False,
            },
            "hard_geometry_status": status, "hard_rejection_reasons": list(dict.fromkeys(failures)),
            "architectural_efficiency_status": "efficient_for_human_review" if status == "hard_valid" else "rejected",
            "regulatory_status": "pending_rule_resolution", "final_selection_eligible": False,
        }

    def _metrics(self, parcel, drive, vt, ped, pt, stalls, maneuver, core, commercial, rear_y):
        stall_union = unary_union(stalls)
        boundary_touch = sum(s.boundary.intersection(parcel.boundary.buffer(self.EPS)).length for s in stalls)
        total_perimeter = sum(s.length for s in stalls)
        terminality = sum(max(0.0, 1-(rear_y-s.centroid.y)/max(rear_y, self.EPS)) for s in stalls)/len(stalls)
        vehicle_area = unary_union([drive, maneuver]).area
        pedestrian_area = ped.area
        total_circ = unary_union([drive, maneuver, ped]).area
        service = unary_union([stall_union, maneuver, core]).area
        usable = commercial.area+stall_union.area+core.area
        return {
            "vehicle_circulation_area": vehicle_area, "vehicle_circulation_length": vt["circulation_length"],
            "pedestrian_circulation_area": pedestrian_area, "pedestrian_circulation_length": pt["circulation_length"],
            "total_circulation_area": total_circ, "vehicle_dead_run_length": 0.0,
            "pedestrian_dead_run_length": 0.0, "circulation_area_ratio": total_circ/parcel.area,
            "parking_boundary_adjacency_ratio": boundary_touch/total_perimeter if total_perimeter else 0.0,
            "parking_terminality_score": terminality, "core_access_path_length": pt["circulation_length"],
            "commercial_area": commercial.area, "commercial_frontage": commercial.bounds[2]-commercial.bounds[0],
            "commercial_depth": commercial.bounds[3]-commercial.bounds[1],
            "largest_usable_rectangle": self._poly(commercial), "largest_usable_rectangle_area": commercial.area,
            "service_zone_area": service, "whole_plan_net_usable_efficiency": usable/parcel.area,
        }

    @staticmethod
    def _shortlist(candidates, count):
        ranked = sorted(candidates, key=lambda c: (
            -c["metrics"]["total_circulation_area"], c["metrics"]["parking_boundary_adjacency_ratio"],
            c["metrics"]["parking_terminality_score"], c["metrics"]["commercial_area"], c["parking_count"]), reverse=True)
        out, families = [], set()
        for c in ranked:
            if c["family"] in families: continue
            out.append(c); families.add(c["family"])
            if len(out) == count: break
        return out

    @staticmethod
    def _frame(parcel, frontage):
        a, b = frontage; length = hypot(b[0]-a[0], b[1]-a[1]); ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
        nx, ny = -uy, ux; centroid = Polygon(parcel).centroid
        if (centroid.x-a[0])*nx+(centroid.y-a[1])*ny < 0: nx, ny = -nx, -ny
        return a[0], a[1], ux, uy, nx, ny

    @staticmethod
    def _to_local(g, f):
        ox, oy, ux, uy, nx, ny = f
        return transform(lambda x, y, z=None: ((x-ox)*ux+(y-oy)*uy, (x-ox)*nx+(y-oy)*ny), g)

    @staticmethod
    def _poly(p): return [[float(x), float(y)] for x, y in list(p.exterior.coords)[:-1]]
