"""Program-level pilot parking study using generated, fail-closed geometry."""
from copy import deepcopy
from math import hypot

from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform, unary_union

from core.architecture.reasoning.commercial_spatial_quality_evaluation_v1 import (
    CommercialSpatialQualityEvaluationV1,
)
from core.architecture.reasoning.vehicle_movement_path_v3 import VehicleMovementPathV3


class PilotParkingFeasibilityStudyV1:
    """Tests Scenario B without mutating its Scenario A inputs."""

    EPS = 1e-5
    FAMILIES = ("PILOT-P01", "PILOT-P02", "PILOT-P03", "PILOT-P04")

    def resolve(self, site, requirements, baseline_scenario_a):
        source_site = deepcopy(site)
        source_baseline = deepcopy(baseline_scenario_a)
        frame = self._frame(site["parcel"], site["frontage"])
        parcel = self._to_local(Polygon(site["parcel"]), frame)
        parking = requirements["parking"]
        pedestrian_width = float(requirements["parking_pedestrian"]["required_clear_width"])
        core = requirements["core"]

        candidates = []
        for family in self.FAMILIES:
            for variant in range(3):
                candidates.append(
                    self._candidate(
                        family, variant, parcel, parking, pedestrian_width, core
                    )
                )

        hard_valid = [c for c in candidates if c["hard_geometry_status"] == "hard_valid"]
        quality_valid = [
            c for c in hard_valid
            if c["commercial_quality_status"] == "quality_valid"
        ]
        eligible = [
            c for c in quality_valid
            if c["independently_usable_parking_count"] >= int(parking["minimum_count"])
            and c["vehicle_maneuvering_status"] == "hard_valid"
            and c["pedestrian_access_status"] == "resolved"
        ]
        best = max(eligible, key=self._rank) if eligible else None
        diagnostic_pool = quality_valid or hard_valid or candidates
        diagnostic = max(diagnostic_pool, key=self._rank) if diagnostic_pool else None
        chosen = best or diagnostic

        assert site == source_site
        assert baseline_scenario_a == source_baseline
        rejection_reasons = {
            c["candidate_id"]: c["rejection_reasons"]
            for c in candidates if c["rejection_reasons"]
        }
        worthy = True if best else (False if hard_valid and not quality_valid else "unresolved")
        return {
            "contract": "PilotParkingFeasibilityStudyV1",
            "site": "REAL Parcel 2",
            "site_source": site.get("source"),
            "site_geometry_source": "authoritative_normalized_real_parcel_2",
            "coordinate_system": "parcel_local_frontage_aligned",
            "source_parcel": site["parcel"],
            "source_frontage": site["frontage"],
            "source_road_width": site.get("road_width"),
            "local_parcel_polygon": self._poly(parcel),
            "baseline_scenario": "basement_parking",
            "baseline_scenario_a": source_baseline,
            "baseline_geometry_preserved": True,
            "baseline_geometry_regenerated": False,
            "existing_ramp_core_geometry_regenerated": False,
            "candidate_families_required": list(self.FAMILIES),
            "candidate_families_explored": sorted({c["family"] for c in candidates}),
            "candidate_count": len(candidates),
            "candidates": candidates,
            "pilot_parking_geometry_status": "generated_hard_valid" if hard_valid else "generated_not_valid",
            "pilot_parking_capacity": chosen["pilot_parking_capacity"] if chosen else 0,
            "independently_usable_parking_count": chosen["independently_usable_parking_count"] if chosen else 0,
            "vehicle_access_status": chosen["vehicle_access_status"] if chosen else "not_feasible",
            "vehicle_maneuvering_status": chosen["vehicle_maneuvering_status"] if chosen else "not_feasible",
            "pedestrian_access_status": chosen["pedestrian_access_status"] if chosen else "not_feasible",
            "core_repositioning_status": "independently_reoptimized",
            "core_repositioning_permitted": True,
            "existing_core_reuse_required": False,
            "commercial_quality_status": chosen["commercial_quality_status"] if chosen else "not_evaluated",
            "best_pilot_candidate": best,
            "best_diagnostic_candidate_id": chosen["candidate_id"] if chosen else None,
            "candidate_rejection_reasons": rejection_reasons,
            "scenario_b_worthy_of_final_comparison": worthy,
            "regulatory_approval_status": "pending_rule_resolution",
            "unresolved_regulatory_rules": [
                "parking_regulatory_approval",
                "fire_egress_and_accessibility_approval",
            ],
            "program_changed": False,
            "basement_deleted": False,
            "basement_removal_approved": False,
            "basement_removal_recommended_for_evaluation": True,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "human_decision_required": True,
        }

    def _candidate(self, family, variant, parcel, parking, pedestrian_width, core_req):
        x0, y0, x1, y1 = parcel.bounds
        sw = float(parking["stall_width"])
        sd = float(parking["stall_depth"])
        aw = float(parking["aisle_width"])
        count = int(parking["minimum_count"])
        side = "west" if variant != 1 else "east"
        aisle_x0 = x0 if side == "west" else x1 - aw
        aisle_x1 = aisle_x0 + aw
        if family == "PILOT-P02":
            stall_y0 = y0 + variant * sw * 0.25
        elif family == "PILOT-P03":
            stall_y0 = y1 - count * sw - variant * sw * 0.25
        else:
            stall_y0 = y0 + (y1 - y0 - count * sw) * (0.25 + 0.25 * variant)
        aisle = box(aisle_x0, y0, aisle_x1, y1)
        stall_x0 = aisle_x1 if side == "west" else aisle_x0 - sd
        stalls = [box(stall_x0, stall_y0 + i * sw, stall_x0 + sd, stall_y0 + (i + 1) * sw) for i in range(count)]

        core_w = float(core_req["stair_reserved_zone"][0]) + float(core_req["elevator_shaft_clear"][0])
        core_d = max(float(core_req["stair_reserved_zone"][1]), float(core_req["lobby_clear"][1]))
        core_y = [y1 - core_d, y0 + (y1-y0-core_d)/2, y0][variant]
        if family == "PILOT-P04":
            core_y = y0 + (y1-y0-core_d) * (variant + 1) / 4
        core_x = x1 - core_w if side == "west" else x0
        core = box(core_x, core_y, core_x + core_w, core_y + core_d)
        stair_w, stair_d = map(float, core_req["stair_reserved_zone"])
        stair = box(core_x, core_y, core_x + stair_w, core_y + stair_d)
        lobby_d = float(core_req["lobby_clear"][1])
        lobby = box(core_x + stair_w, core_y, core_x + core_w, core_y + lobby_d)
        elevator = box(core_x + stair_w, core_y + lobby_d, core_x + core_w,
                       core_y + lobby_d + float(core_req["elevator_shaft_clear"][1]))

        ped_x0 = x1 - pedestrian_width if side == "west" else x0
        ped_target_y = core_y + lobby_d / 2
        pedestrian = box(ped_x0, y0, ped_x0 + pedestrian_width, ped_target_y)
        entrance = [[ped_x0, y0], [ped_x0 + pedestrian_width, y0]]
        ped_center = [[ped_x0 + pedestrian_width/2, y0], [ped_x0 + pedestrian_width/2, ped_target_y]]
        vehicle_entrance = [[aisle_x0, y0], [aisle_x1, y0]]
        vehicle_center = (aisle_x0 + aisle_x1) / 2
        path = VehicleMovementPathV3().resolve(
            [[vehicle_center, y0], [vehicle_center, y1]], vehicle_entrance,
            self._poly(aisle), self._poly(aisle), [self._poly(s) for s in stalls], aw
        )

        failures = []
        for geom, reason in [(aisle, "vehicle_path_blocked"), (core, "parcel_boundary_violation"),
                             (pedestrian, "parcel_boundary_violation")]:
            if not parcel.buffer(self.EPS).covers(geom):
                failures.append(reason)
        if any(not parcel.buffer(self.EPS).covers(s) for s in stalls):
            failures.append("parking_stall_collision")
        if core.intersection(unary_union([aisle] + stalls)).area > self.EPS:
            failures.append("parking_stall_collision")
        vehicle_field = unary_union([aisle] + stalls)
        if pedestrian.intersection(vehicle_field).area > self.EPS:
            failures.append("pedestrian_vehicle_conflict")
        if not LineString(ped_center).intersects(lobby):
            failures.append("core_access_failure")
        if path["geometry_status"] != "hard_valid":
            failures.append("maneuvering_unproven")

        occupied = unary_union([vehicle_field, core, pedestrian])
        commercial = parcel.difference(occupied)
        parts = [g for g in getattr(commercial, "geoms", [commercial]) if g.geom_type == "Polygon" and g.area > self.EPS]
        frontage = LineString([(x0, y0), (x1, y0)])
        frontage_width = sum(p.boundary.intersection(frontage.buffer(self.EPS)).length for p in parts)
        quality = None
        if parts:
            quality_candidate = {
                "candidate_id": f"{family}-{variant+1:02d}",
                "core_polygon": self._poly(core),
                "ground_floor": {
                    "commercial_space_polygons": [self._poly(p) for p in parts],
                    "commercial_frontage_width": frontage_width,
                },
            }
            quality = CommercialSpatialQualityEvaluationV1().evaluate(quality_candidate, parcel)
            failures.extend(self._quality_reasons(quality))
        else:
            failures.append("commercial_frontage_failure")
        failures = list(dict.fromkeys(failures))
        independent = sum(
            item["entry_status"] == "hard_valid" and item["exit_status"] == "hard_valid"
            for item in path["stall_paths"]
        )
        geometry_failures = [f for f in failures if not f.startswith("commercial_")]
        return {
            "contract": "PilotParkingCandidateV1",
            "candidate_id": f"{family}-{variant+1:02d}",
            "family": family,
            "variant": variant + 1,
            "stall_orientation": "perpendicular_to_longitudinal_aisle",
            "parking_stalls": [self._poly(s) for s in stalls],
            "parking_aisle": self._poly(aisle),
            "vehicle_entrance": vehicle_entrance,
            "vehicle_movement_path": path,
            "pedestrian_entrance": entrance,
            "pedestrian_circulation": self._poly(pedestrian),
            "pedestrian_vehicle_separation": pedestrian.intersection(vehicle_field).area <= self.EPS,
            "core": {"polygon": self._poly(core), "stair": self._poly(stair),
                     "elevator": self._poly(elevator), "common_lobby": self._poly(lobby),
                     "source": "independent_scenario_b_core_generation"},
            "commercial_usable_field": [self._poly(p) for p in parts],
            "commercial_frontage": frontage_width,
            "commercial_quality": quality,
            "pilot_parking_capacity": len(stalls),
            "independently_usable_parking_count": independent,
            "vehicle_access_status": "resolved" if parcel.buffer(self.EPS).covers(aisle) else "not_feasible",
            "vehicle_maneuvering_status": path["geometry_status"],
            "pedestrian_access_status": "resolved" if not any(f in failures for f in ("pedestrian_vehicle_conflict", "core_access_failure", "parcel_boundary_violation")) else "not_feasible",
            "core_repositioning_status": "independently_reoptimized",
            "commercial_quality_status": quality["architectural_quality_status"] if quality else "quality_failed",
            "hard_geometry_status": "hard_valid" if not geometry_failures else "not_feasible",
            "regulatory_status": "pending_rule_resolution",
            "rejection_reasons": failures,
        }

    @staticmethod
    def _quality_reasons(quality):
        mapping = {
            "commercial_narrow_neck_dependency": "commercial_narrow_neck",
            "commercial_rear_tail_created": "commercial_rear_tail",
            "commercial_space_fragmented_by_core": "commercial_fragmentation",
            "commercial_core_position_creates_unusable_residual_space": "commercial_fragmentation",
        }
        return [mapping[x] for x in quality["architectural_quality_failures"] if x in mapping]

    @staticmethod
    def _rank(candidate):
        quality = candidate.get("commercial_quality") or {}
        return (
            candidate["hard_geometry_status"] == "hard_valid",
            candidate["independently_usable_parking_count"],
            candidate["vehicle_maneuvering_status"] == "hard_valid",
            candidate["pedestrian_access_status"] == "resolved",
            candidate["commercial_quality_status"] == "quality_valid",
            quality.get("usable_rectangular_field_area", 0),
            quality.get("commercial_total_area", 0),
            candidate["candidate_id"],
        )

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
