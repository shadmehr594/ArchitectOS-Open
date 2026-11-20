"""Frontage-inward whole-plan topology search for pilot parking scenarios."""
from copy import deepcopy
from math import hypot, pi

from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform, unary_union

from core.architecture.reasoning.commercial_spatial_quality_evaluation_v1 import (
    CommercialSpatialQualityEvaluationV1,
)


class PilotParkingWholePlanTopologySearchV1:
    """Generates review candidates without claiming swept-path feasibility."""

    EPS = 1e-5
    FAMILIES = tuple(f"PILOT-H{i:02d}" for i in range(1, 7))
    VEHICLE_ENTRANCE_WIDTHS = (3.0, 3.25, 3.5)
    CAPACITIES = (2, 3)

    def resolve(self, site, requirements, baseline_scenario_a):
        site_before = deepcopy(site)
        baseline_before = deepcopy(baseline_scenario_a)
        frame = self._frame(site["parcel"], site["frontage"])
        parcel = self._to_local(Polygon(site["parcel"]), frame)
        candidates = []
        for family in self.FAMILIES:
            for side in ("west", "east"):
                for entrance_width in self.VEHICLE_ENTRANCE_WIDTHS:
                    for capacity in self.CAPACITIES:
                        candidates.append(self._generate_candidate(
                            family, side, entrance_width, capacity, parcel, requirements
                        ))
        hard_valid = [c for c in candidates if c["hard_geometry_status"] == "hard_valid"]
        promising = self._shortlist(hard_valid, 5)
        assert site == site_before and baseline_scenario_a == baseline_before
        return {
            "contract": "PilotParkingWholePlanTopologySearchV1",
            "site": "REAL Parcel 2",
            "site_source": site.get("source"),
            "site_geometry_source": "authoritative_normalized_real_parcel_2",
            "source_parcel": site["parcel"],
            "source_frontage": site["frontage"],
            "source_road_width": site.get("road_width"),
            "coordinate_system": "parcel_local_frontage_aligned",
            "local_parcel_polygon": self._poly(parcel),
            "frontage_length": LineString(self._poly(parcel)[:2]).length,
            "topology_families_explored": list(self.FAMILIES),
            "vehicle_entrance_width_search": {
                "values": list(self.VEHICLE_ENTRANCE_WIDTHS),
                "classification": "engineering_design_search_range",
                "regulatory_requirement": False,
            },
            "parking_capacity_search": list(self.CAPACITIES),
            "candidate_count": len(candidates),
            "hard_valid_candidate_count": len(hard_valid),
            "candidates": candidates,
            "promising_candidate_ids_for_human_review": [c["candidate_id"] for c in promising],
            "promising_candidates": promising,
            "final_scenario_b_candidate": None,
            "final_selection_performed": False,
            "human_architect_review_required": True,
            "scenario_b_worthy_of_final_comparison": "pending_human_architect_review",
            "baseline_scenario_a": baseline_before,
            "baseline_geometry_preserved": True,
            "baseline_geometry_regenerated": False,
            "program_changed": False,
            "basement_deleted": False,
            "basement_removal_approved": False,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "regulatory_status": "pending_rule_resolution",
        }

    def _generate_candidate(self, family, side, entrance_width, capacity, parcel, requirements):
        x0, y0, x1, y1 = parcel.bounds
        parking = requirements["parking"]
        core_req = requirements["core"]
        pedestrian_width = float(requirements["parking_pedestrian"]["required_clear_width"])
        stall_w, stall_d = float(parking["stall_width"]), float(parking["stall_depth"])
        core_w = float(core_req["stair_reserved_zone"][0]) + float(core_req["elevator_shaft_clear"][0])
        core_d = max(float(core_req["stair_reserved_zone"][1]), float(core_req["lobby_clear"][1]))
        service_gap = 0.5
        stall_y1 = y1 - core_d - service_gap
        stall_y0 = stall_y1 - capacity * stall_w

        west_vehicle = side == "west"
        vehicle_interval = [x0, x0 + entrance_width] if west_vehicle else [x1-entrance_width, x1]
        pedestrian_mode = "opposite_edge" if family in ("PILOT-H01", "PILOT-H02", "PILOT-H03", "PILOT-H04", "PILOT-H05") else "between_vehicle_and_commercial"
        if pedestrian_mode == "opposite_edge":
            pedestrian_interval = [x1-pedestrian_width, x1] if west_vehicle else [x0, x0+pedestrian_width]
        else:
            pedestrian_interval = ([vehicle_interval[1], vehicle_interval[1]+pedestrian_width]
                                   if west_vehicle else [vehicle_interval[0]-pedestrian_width, vehicle_interval[0]])
        used = sorted([vehicle_interval, pedestrian_interval], key=lambda value: value[0])
        commercial_interval = [used[0][1], used[1][0]]
        if commercial_interval[1] <= commercial_interval[0] + self.EPS:
            commercial_interval = [vehicle_interval[1], x1] if west_vehicle else [x0, vehicle_interval[0]]

        drive_lane = box(vehicle_interval[0], y0, vehicle_interval[1], y1)
        if west_vehicle:
            stall_x0, stall_x1 = vehicle_interval[1], vehicle_interval[1] + stall_d
            core_x0 = x1-core_w
        else:
            stall_x0, stall_x1 = vehicle_interval[0]-stall_d, vehicle_interval[0]
            core_x0 = x0
        if family == "PILOT-H02":
            core_x0 += (-pedestrian_width/4 if west_vehicle else pedestrian_width/4)
        stalls = [box(stall_x0, stall_y0+i*stall_w, stall_x1, stall_y0+(i+1)*stall_w)
                  for i in range(capacity)]
        maneuvering_zone = box(vehicle_interval[0], stall_y0-service_gap,
                               vehicle_interval[1], stall_y1+service_gap)
        stall_entry_zones = []
        for stall in stalls:
            sx0, sy0, sx1, sy1 = stall.bounds
            interface_x = sx0 if west_vehicle else sx1
            stall_entry_zones.append(box(interface_x-self.EPS, sy0, interface_x+self.EPS, sy1))

        core_y0 = y1-core_d
        if family == "PILOT-H04":
            core_y0 = stall_y0-core_d-service_gap
        if family == "PILOT-H06":
            core_y0 = stall_y0 + stall_w/2
        core = box(core_x0, core_y0, core_x0+core_w, core_y0+core_d)
        stair_w, stair_d = map(float, core_req["stair_reserved_zone"])
        stair = box(core_x0, core_y0, core_x0+stair_w, core_y0+stair_d)
        lobby_d = float(core_req["lobby_clear"][1])
        lobby = box(core_x0+stair_w, core_y0, core_x0+core_w, core_y0+lobby_d)
        elevator = box(core_x0+stair_w, core_y0+lobby_d, core_x0+core_w,
                       core_y0+lobby_d+float(core_req["elevator_shaft_clear"][1]))
        pedestrian_corridor = box(pedestrian_interval[0], y0, pedestrian_interval[1], core_y0+lobby_d/2)
        pedestrian_path = [[sum(pedestrian_interval)/2, y0], [sum(pedestrian_interval)/2, core_y0+lobby_d/2]]

        commercial_depth = max(0.0, stall_y0-service_gap-y0)
        if family == "PILOT-H03":
            commercial_depth = max(0.0, stall_y0-y0)
        commercial = box(commercial_interval[0], y0, commercial_interval[1], y0+commercial_depth)
        commercial_entrance = [[commercial_interval[0], y0], [commercial_interval[1], y0]]
        vehicle_axis = [[sum(vehicle_interval)/2, y0], [sum(vehicle_interval)/2, y1]]
        vehicle_entrance = [[vehicle_interval[0], y0], [vehicle_interval[1], y0]]
        pedestrian_entrance = [[pedestrian_interval[0], y0], [pedestrian_interval[1], y0]]

        failures = []
        named = [(drive_lane, "vehicle_access_outside_parcel"), (maneuvering_zone, "maneuvering_zone_outside_parcel"),
                 (core, "core_outside_parcel"), (pedestrian_corridor, "pedestrian_access_outside_parcel"),
                 (commercial, "commercial_field_outside_parcel")]
        named += [(stall, "parking_stall_outside_parcel") for stall in stalls]
        for geometry, reason in named:
            if geometry.is_empty or not parcel.buffer(self.EPS).covers(geometry):
                failures.append(reason)
        stall_union = unary_union(stalls)
        if core.intersection(stall_union).area > self.EPS:
            failures.append("core_stall_overlap")
        if core.intersection(drive_lane).area > self.EPS:
            failures.append("core_vehicle_access_blockage")
        if pedestrian_corridor.intersection(drive_lane).area > self.EPS:
            failures.append("pedestrian_vehicle_conflict")
        if pedestrian_corridor.intersection(stall_union).area > self.EPS:
            failures.append("pedestrian_stall_conflict")
        if not LineString(pedestrian_path).intersects(lobby):
            failures.append("core_pedestrian_connection_failure")
        if commercial.intersection(unary_union([drive_lane, pedestrian_corridor, stall_union, core])).area > self.EPS:
            failures.append("commercial_service_overlap")
        if LineString(vehicle_entrance).length <= self.EPS or LineString(commercial_entrance).length <= self.EPS:
            failures.append("frontage_allocation_failure")

        quality_input = {
            "candidate_id": self._id(family, side, entrance_width, capacity),
            "core_polygon": self._poly(core),
            "ground_floor": {"commercial_space_polygons": [self._poly(commercial)],
                             "commercial_frontage_width": LineString(commercial_entrance).length},
        }
        legacy_quality = CommercialSpatialQualityEvaluationV1().evaluate(quality_input, parcel)
        perimeter = commercial.length
        actual_metrics = {
            "commercial_area": commercial.area,
            "commercial_frontage": LineString(commercial_entrance).length,
            "largest_contiguous_usable_field": commercial.area,
            "largest_usable_rectangle": self._poly(commercial),
            "largest_usable_rectangle_area": commercial.area,
            "average_depth": commercial_depth,
            "maximum_depth": commercial_depth,
            "compactness": 4*pi*commercial.area/(perimeter*perimeter) if perimeter else 0.0,
            "convexity": commercial.area/commercial.convex_hull.area if commercial.area else 0.0,
            "narrow_neck": False,
            "rear_tail": False,
            "core_induced_fragmentation": 1,
            "frontage_connected": True,
            "metric_geometry_source": "explicit_frontage_connected_commercial_field",
        }
        topology_quality_failures = []
        if actual_metrics["commercial_frontage"] <= self.EPS:
            topology_quality_failures.append("commercial_frontage_failure")
        if actual_metrics["largest_usable_rectangle_area"] <= self.EPS:
            topology_quality_failures.append("commercial_usable_field_failure")
        hard_status = "hard_valid" if not failures else "not_feasible"
        quality_status = "quality_valid_for_human_review" if not topology_quality_failures else "quality_failed"
        return {
            "contract": "PilotParkingWholePlanCandidateV1",
            "candidate_id": self._id(family, side, entrance_width, capacity),
            "family": family,
            "access_side": side,
            "parking_count": len(stalls),
            "independently_usable_parking_count": 0,
            "parking_count_pending_vehicle_model_validation": len(stalls) if not failures else 0,
            "frontage_allocation": {
                "vehicle_access_interval": vehicle_interval,
                "pedestrian_common_interval": pedestrian_interval,
                "commercial_storefront_interval": commercial_interval,
                "three_functions_explicitly_separated": True,
            },
            "vehicle_entrance": vehicle_entrance,
            "vehicle_entrance_width": entrance_width,
            "vehicle_entrance_width_source": "engineering_design_search_range",
            "vehicle_access_axis": vehicle_axis,
            "drive_lane": self._poly(drive_lane),
            "maneuvering_zone": self._poly(maneuvering_zone),
            "stall_entry_zones": [self._poly(zone) for zone in stall_entry_zones],
            "parking_stalls": [{"stall_id": f"P-{i+1:02d}", "polygon": self._poly(stall),
                                 "orientation": "perpendicular_to_direct_access_lane"}
                                for i, stall in enumerate(stalls)],
            "vehicle_access_status": "topology_resolved" if "vehicle_access_outside_parcel" not in failures else "not_feasible",
            "vehicle_maneuvering_status": "pending_vehicle_model_validation" if not failures else "not_feasible",
            "vehicle_swept_path_generated": False,
            "vehicle_model_source": "unresolved",
            "pedestrian_entrance": pedestrian_entrance,
            "pedestrian_path": pedestrian_path,
            "pedestrian_corridor": self._poly(pedestrian_corridor),
            "pedestrian_access_status": "resolved" if not any("pedestrian" in f for f in failures) else "not_feasible",
            "commercial_entrance": commercial_entrance,
            "commercial_storefront": commercial_entrance,
            "commercial_usable_field": [self._poly(commercial)],
            "commercial_quality": actual_metrics,
            "commercial_quality_status": quality_status,
            "commercial_quality_failures": topology_quality_failures,
            "legacy_commercial_evaluator": legacy_quality,
            "core": {"polygon": self._poly(core), "stair": self._poly(stair),
                     "elevator": self._poly(elevator), "lobby": self._poly(lobby),
                     "location_classification": "rear_service_zone" if family != "PILOT-H06" else "side_service_zone",
                     "source": "scenario_b_joint_parking_core_topology_search"},
            "hard_geometry_status": hard_status,
            "hard_rejection_reasons": list(dict.fromkeys(failures)),
            "regulatory_status": "pending_rule_resolution",
            "final_selection_eligible": False,
            "human_review_status": "pending",
        }

    @staticmethod
    def _shortlist(candidates, count):
        def rank(c):
            quality = (c["commercial_quality_status"] == "quality_valid_for_human_review",
                       c["commercial_quality"]["largest_usable_rectangle_area"],
                       c["commercial_quality"]["commercial_frontage"])
            if c["family"] == "PILOT-H05":
                return (quality[0], c["parking_count"], quality[1], quality[2],
                        -c["vehicle_entrance_width"], c["candidate_id"])
            return (quality[0], quality[1], quality[2], c["parking_count"],
                    -c["vehicle_entrance_width"], c["candidate_id"])
        ranked = sorted(candidates, key=rank, reverse=True)
        selected = []
        families = set()
        for candidate in ranked:
            if candidate["family"] in families:
                continue
            selected.append(candidate)
            families.add(candidate["family"])
            if len(selected) == count:
                break
        return selected

    @staticmethod
    def _id(family, side, width, capacity):
        return f"{family}-{side.upper()}-W{width:.2f}-P{capacity}"

    @staticmethod
    def _frame(parcel, frontage):
        a, b = frontage
        length = hypot(b[0]-a[0], b[1]-a[1])
        ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
        nx, ny = -uy, ux
        centroid = Polygon(parcel).centroid
        if (centroid.x-a[0])*nx + (centroid.y-a[1])*ny < 0:
            nx, ny = -nx, -ny
        return a[0], a[1], ux, uy, nx, ny

    @staticmethod
    def _to_local(geometry, frame):
        ox, oy, ux, uy, nx, ny = frame
        return transform(lambda x, y, z=None: ((x-ox)*ux+(y-oy)*uy, (x-ox)*nx+(y-oy)*ny), geometry)

    @staticmethod
    def _poly(polygon):
        return [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
