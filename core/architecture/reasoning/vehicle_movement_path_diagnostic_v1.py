"""Read-only diagnosis of VehicleMovementPathV3 evidence."""
from copy import deepcopy

from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points, unary_union

from core.architecture.reasoning.vehicle_movement_path_v3 import VehicleMovementPathV3
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class VehicleMovementPathDiagnosticV1:
    """Explains current path failures without changing candidate geometry."""

    EPS = 1e-7

    def analyze(self, candidate, site_context):
        original = deepcopy(candidate)
        aisle = Polygon(candidate["parking_aisle"])
        stalls = [Polygon(points) for points in candidate["parking_stalls"]]
        movement = candidate["vehicle_movement_path"]
        drivable = aisle
        entrance = LineString(candidate["vehicle_entrance"])
        entrance_center = entrance.interpolate(0.5, normalized=True)
        hub = aisle.representative_point()
        width = float(movement["stall_paths"][0]["minimum_clearance_width"])
        attempts = []

        for index, stall in enumerate(stalls):
            access = stall.boundary.intersection(drivable.boundary)
            target = nearest_points(stall.centroid, access)[1] if not access.is_empty else stall.centroid
            control = [[entrance_center.x, entrance_center.y], [hub.x, hub.y], [target.x, target.y]]
            trajectory = VehicleMovementPathV3._quadratic(control, 41)
            corridor = LineString(trajectory).buffer(width / 2, cap_style=2, join_style=1)
            allowed = unary_union([drivable, stall])
            outside = corridor.difference(allowed)
            occupied = [other for other_index, other in enumerate(stalls) if other_index != index]
            collisions = []
            for other_index, other in enumerate(stalls):
                if other_index == index:
                    continue
                hit = corridor.intersection(other)
                if hit.area > self.EPS:
                    collisions.append({
                        "stall_id": f"P-{other_index + 1:02d}",
                        "intersection_area": hit.area,
                        "intersection_polygon": self._geometry(hit),
                        "obstacle_geometry_source": "occupied_parking_stall_rectangle_not_vehicle_footprint",
                    })
            attempts.append({
                "stall_id": f"P-{index + 1:02d}",
                "strategy": "single_quadratic_forward_entry_reverse_same_path_exit",
                "control_points": control,
                "generated_center_trajectory": trajectory,
                "exit_center_trajectory": list(reversed(trajectory)),
                "return_to_public_access_trajectory": list(reversed(trajectory)),
                "clearance_corridor": RampCenterlineTopologyV2._poly(corridor),
                "outside_drivable_field": not outside.is_empty and outside.area > self.EPS,
                "outside_drivable_field_area": outside.area,
                "outside_drivable_field_geometry": self._geometry(outside),
                "occupied_stall_collisions": collisions,
                "other_stalls_treated_as_occupied": bool(occupied),
                "entry_successful": False,
                "exit_successful": False,
                "independently_usable": False,
            })

        layout_overlap = Polygon(candidate["core"]["polygon"]).intersection(unary_union(stalls))
        missing = [
            "authoritative_vehicle_length",
            "authoritative_vehicle_width",
            "vehicle_wheelbase_and_overhang",
            "steering_kinematics",
        ]
        limitations = [
            "minimum_turning_radius_not_consumed_by_vehicle_path_engine",
            "only_one_quadratic_entry_topology_tested",
            "exit_is_only_reversed_entry_not_independently_searched",
            "no_reverse_entry_strategy",
            "no_multi_point_maneuver",
            "no_steering_direction_change_search",
            "clearance_corridor_is_not_vehicle_footprint_swept_path",
            "occupied_obstacle_is_full_stall_rectangle_not_parked_vehicle_footprint",
        ]
        classifications = ["vehicle_path_intelligence_limitation", "insufficient_search"]
        if layout_overlap.area > self.EPS:
            classifications.append("real_geometric_infeasibility")
        classifications.append("pending_rule_resolution")
        diagnostic = {
            "contract": "VehicleMovementPathDiagnosticV1",
            "candidate_id": candidate["candidate_id"],
            "vehicle_path_engine": "VehicleMovementPathV3",
            "vehicle_model_source": "not_provided",
            "vehicle_dimensions_source": "unresolved_no_authoritative_vehicle_dimensions",
            "missing_vehicle_model_evidence": missing,
            "clearance_width": width,
            "clearance_width_source": "parking.aisle_width_passed_by_PilotParkingFeasibilityStudyV1",
            "clearance_width_classification": "project_geometry_input_not_vehicle_dimension",
            "turning_radius": site_context["requirements"]["parking"].get("minimum_turning_radius"),
            "turning_radius_source": "user_project_requirement",
            "turning_model": "single_quadratic_bezier_without_kinematic_turning_radius_validation",
            "maneuver_strategies_tested": ["single_quadratic_path"],
            "entry_strategies_tested": ["nominal_forward_entry_only"],
            "exit_strategies_tested": ["reverse_of_nominal_entry_only"],
            "reverse_entry_tested": False,
            "forward_exit_tested": False,
            "multi_point_maneuver_tested": False,
            "steering_direction_changes_tested": False,
            "drivable_field_source": "candidate.parking_aisle_used_as_both_maneuvering_polygon_and_aisle_polygon",
            "occupied_stalls_treated_as_obstacles": True,
            "occupied_stall_obstacle_model": "full_stall_rectangle",
            "vehicle_footprint_collision_check": False,
            "swept_path_check": False,
            "path_validation_approximation": "center_trajectory_buffered_by_full_aisle_width",
            "outside_drivable_field_reason": "buffered_clearance_corridor_exceeds_union_of_aisle_and_active_stall",
            "occupied_stall_collision_reason": "buffered_clearance_corridor_intersects_full_rectangle_of_other_stall",
            "number_of_maneuver_attempts": len(attempts),
            "attempts": attempts,
            "successful_entry_strategy": None,
            "successful_exit_strategy": None,
            "independently_usable": False,
            "legacy_semantics": {
                "return_to_ramp_status_present": True,
                "classification": "basement_ramp_semantic_leak_in_field_name",
                "behavior_in_scenario_b": "aisle_centerline_is_used_as_public_access_return_path",
                "compatible_general_name": "return_to_public_access_status",
            },
            "engine_limitations": limitations,
            "layout_geometry_failure": {
                "core_intersects_parking_stalls": layout_overlap.area > self.EPS,
                "intersection_area": layout_overlap.area,
                "intersection_geometry": self._geometry(layout_overlap),
            },
            "failure_classification": {
                "primary": "vehicle_path_intelligence_limitation",
                "applicable": classifications,
                "overall_conclusion": "unresolved",
                "real_pilot_parking_infeasibility_proven": False,
                "same_candidate_layout_hard_valid": False if layout_overlap.area > self.EPS else None,
            },
            "source_site": "REAL Parcel 2",
            "source_parcel": site_context["site"]["parcel"],
            "source_frontage": site_context["site"]["frontage"],
            "source_road_width": site_context["site"].get("road_width"),
            "candidate_geometry_unchanged": candidate == original,
            "program_changed": False,
            "basement_deleted": False,
            "basement_removal_approved": False,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "regulatory_status": "pending_rule_resolution",
        }
        assert candidate == original
        return diagnostic

    @classmethod
    def _geometry(cls, geometry):
        polygons = [g for g in getattr(geometry, "geoms", [geometry]) if g.geom_type == "Polygon"]
        return [cls._poly(p) for p in polygons]

    @staticmethod
    def _poly(polygon):
        return [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
