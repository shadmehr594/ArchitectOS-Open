"""
ArchitectOS Vehicle Access Feasibility Reasoner v1.0

Evaluates vehicle ramp and car-lift feasibility
using site and architectural evidence.

This engine does not generate geometry.
"""


class VehicleAccessFeasibilityReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🚗 Vehicle Access Feasibility Reasoner v{self.VERSION} ACTIVE"
        )


    def _normalize_slope(self, building_context):

        slope_percent = building_context.get(
            "allowable_vehicle_ramp_slope_percent"
        )

        if isinstance(slope_percent, (int, float)) and 0 < slope_percent <= 100:
            return {
                "ratio": float(slope_percent) / 100.0,
                "percent": float(slope_percent),
                "source": "allowable_vehicle_ramp_slope_percent",
                "status": "authoritative_percent_normalized",
            }

        legacy_slope = building_context.get(
            "allowable_vehicle_ramp_slope"
        )

        if isinstance(legacy_slope, (int, float)) and 0 < legacy_slope <= 1:
            return {
                "ratio": float(legacy_slope),
                "percent": float(legacy_slope) * 100.0,
                "source": "allowable_vehicle_ramp_slope",
                "status": "legacy_ratio_normalized",
            }

        if isinstance(legacy_slope, (int, float)) and 1 < legacy_slope <= 100:
            return {
                "ratio": float(legacy_slope) / 100.0,
                "percent": float(legacy_slope),
                "source": "allowable_vehicle_ramp_slope",
                "status": "legacy_percent_normalized",
            }

        return {
            "ratio": None,
            "percent": None,
            "source": None,
            "status": "unresolved",
        }


    def _access_elevation_candidates(self, building_context):

        site_constraints = building_context.get("site_constraints", {}) or {}
        accesses = site_constraints.get("access_elevations", [])

        if not isinstance(accesses, list):
            return []

        return [
            item for item in accesses
            if isinstance(item, dict) and item.get("vehicle_access") is True
        ]


    # ==================================================
    # MAIN
    # ==================================================

    def evaluate(
        self,
        vehicle_access_system,
        building_context
    ):

        vehicle_access_system = (
            vehicle_access_system
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        parameters = vehicle_access_system.get(
            "parameters",
            {}
        )


        site_evidence = parameters.get(
            "site_evidence",
            {}
        )


        site_area = site_evidence.get(
            "site_area"
        )

        site_width = site_evidence.get(
            "site_width"
        )

        site_depth = site_evidence.get(
            "site_depth"
        )

        road_access = site_evidence.get(
            "road_access"
        )


        # ==================================================
        # LEVEL DIFFERENCE
        # ==================================================

        access_elevations = self._access_elevation_candidates(
            building_context
        )

        parking = building_context.get("parking", {}) or {}
        target_elevation = parking.get("elevation")
        target_level = parking.get("level")

        # Compatibility is intentionally isolated to projects which do not
        # carry the new access-elevation contract. It never overwrites an
        # authoritative candidate.
        legacy_level_difference = None
        if not access_elevations:
            legacy_level_difference = building_context.get(
                "vehicle_level_difference"
            )
            if legacy_level_difference is None:
                legacy_level_difference = building_context.get(
                    "parking_level_difference"
                )


        # ==================================================
        # RAMP PARAMETERS
        # ==================================================

        slope_contract = self._normalize_slope(building_context)
        allowable_ramp_slope = slope_contract["ratio"]


        minimum_ramp_width = building_context.get(
            "minimum_vehicle_ramp_width"
        )


        turning_radius = building_context.get(
            "vehicle_turning_radius"
        )


        # ==================================================
        # CAR-LIFT PARAMETERS
        # ==================================================

        car_lift_width = building_context.get(
            "car_lift_required_width"
        )


        car_lift_depth = building_context.get(
            "car_lift_required_depth"
        )


        queue_length = building_context.get(
            "car_lift_queue_length"
        )


        # ==================================================
        # RAMP FEASIBILITY
        # ==================================================

        ramp_missing = []


        if not access_elevations and legacy_level_difference is None:

            ramp_missing.append(
                "level_difference"
            )

        if access_elevations and target_elevation is None:

            ramp_missing.append(
                "target_parking_elevation"
            )


        if allowable_ramp_slope is None:

            ramp_missing.append(
                "allowable_vehicle_ramp_slope"
            )


        if minimum_ramp_width is None:

            ramp_missing.append(
                "minimum_vehicle_ramp_width"
            )


        if turning_radius is None:

            ramp_missing.append(
                "vehicle_turning_radius"
            )


        access_candidates = []

        for access in access_elevations:
            access_elevation = access.get("elevation")
            candidate_missing = list(ramp_missing)
            if access_elevation is None:
                candidate_missing.append("access_elevation")

            delta_z = None
            absolute_difference = None
            required_run = None
            ramp_fit = None

            if (
                isinstance(access_elevation, (int, float))
                and isinstance(target_elevation, (int, float))
            ):
                delta_z = float(target_elevation) - float(access_elevation)
                absolute_difference = abs(delta_z)

            if absolute_difference is not None and allowable_ramp_slope:
                required_run = absolute_difference / allowable_ramp_slope

            if required_run == 0.0:
                ramp_fit = True
            elif required_run is not None and site_depth is not None:
                ramp_fit = required_run <= float(site_depth)

            status = (
                "insufficient_evidence"
                if candidate_missing
                else "feasible"
                if ramp_fit is True
                else "not_feasible"
                if ramp_fit is False
                else "insufficient_evidence"
            )

            access_candidates.append(
                {
                    "access_id": access.get("id"),
                    "side": access.get("side"),
                    "access_type": access.get("type"),
                    "vehicle_access": access.get("vehicle_access"),
                    "access_edge_status": access.get("access_edge_status"),
                    "parcel_edge_id": access.get("parcel_edge_id"),
                    "access_elevation": access_elevation,
                    "target_level": target_level,
                    "target_elevation": target_elevation,
                    "delta_z": delta_z,
                    "absolute_level_difference": absolute_difference,
                    "required_run": required_run,
                    "site_fit": ramp_fit,
                    "status": status,
                    "access_mode": (
                        "direct_at_grade"
                        if absolute_difference == 0.0
                        else "vehicle_ramp"
                        if absolute_difference is not None
                        else "unresolved"
                    ),
                    "ramp_geometry_required": (
                        False if absolute_difference == 0.0
                        else True if absolute_difference is not None
                        else False
                    ),
                    "source": access.get("source"),
                    "evidence": access.get("evidence"),
                    "missing_evidence": candidate_missing,
                    # Preserve optional site-design geometry for the separate
                    # pedestrian/vehicle coordinator. Feasibility does not
                    # create, move, or validate this XY evidence.
                    "access_edge_reference": access.get(
                        "access_edge_reference", access.get("parcel_edge_id", access.get("edge_index"))
                    ),
                    "entrance_interval": access.get(
                        "entrance_interval", access.get("access_interval", access.get("access_segment"))
                    ),
                    "access_point": access.get("access_point", access.get("entrance_center")),
                    "driveway_corridor": access.get(
                        "driveway_corridor", access.get("driveway_polygon", access.get("driveway_centerline"))
                    ),
                    "clear_width": access.get("clear_width", minimum_ramp_width),
                    "transition_zone": access.get(
                        "transition_zone", access.get("ramp_transition_zone")
                    ),
                    "candidate_score": access.get("candidate_score", access.get("coordination_score")),
                    "parking_target_reference": access.get(
                        "parking_target_reference", access.get("target_level", target_level)
                    ),
                    "parking_target_point": access.get("parking_target_point", access.get("target_point")),
                    "parking_target_source": access.get("parking_target_source"),
                    "ramp_transition_length": access.get("ramp_transition_length"),
                    "ramp_transition_width": access.get("ramp_transition_width"),
                    "building_entry_allowed": access.get("building_entry_allowed") is True,
                }
            )

        required_ramp_run = None
        ramp_fit = None

        if not access_elevations and legacy_level_difference is not None:
            if allowable_ramp_slope:
                required_ramp_run = abs(float(legacy_level_difference)) / allowable_ramp_slope
            if required_ramp_run is not None and site_depth is not None:
                ramp_fit = required_ramp_run <= float(site_depth)

        feasible_accesses = [
            item for item in access_candidates
            if item["status"] == "feasible"
        ]

        if len(access_candidates) == 1:
            required_ramp_run = access_candidates[0]["required_run"]
            ramp_fit = access_candidates[0]["site_fit"]

        if access_candidates:
            ramp_status = (
                "feasible" if feasible_accesses
                else "not_feasible"
                if access_candidates and all(
                    item["status"] == "not_feasible" for item in access_candidates
                )
                else "insufficient_evidence"
            )
        else:
            ramp_status = (
                "feasible" if ramp_fit is True
                else "not_feasible" if ramp_fit is False
                else "insufficient_evidence"
            )


        ramp_feasibility = {

            "type":
                "vehicle_ramp",

            "status":
                (
                    ramp_status
                ),

            "required_run":
                required_ramp_run,

            "site_depth":
                site_depth,

            "minimum_width":
                minimum_ramp_width,

            "turning_radius":
                turning_radius,

            "missing_evidence":
                ramp_missing,

            "site_fit":
                ramp_fit,

            "access_candidates":
                access_candidates,

            "feasible_access_candidates":
                feasible_accesses,

            "normalized_slope_ratio":
                slope_contract["ratio"],

            "allowable_slope_percent":
                slope_contract["percent"],

            "slope_source":
                slope_contract["source"],

            "slope_status":
                slope_contract["status"]

        }


        # ==================================================
        # CAR-LIFT FEASIBILITY
        # ==================================================

        car_lift_missing = []


        if car_lift_width is None:

            car_lift_missing.append(
                "car_lift_required_width"
            )


        if car_lift_depth is None:

            car_lift_missing.append(
                "car_lift_required_depth"
            )


        if queue_length is None:

            car_lift_missing.append(
                "car_lift_queue_length"
            )


        car_lift_fit = None


        if (
            car_lift_width is not None
            and
            car_lift_depth is not None
            and
            site_width is not None
            and
            site_depth is not None
        ):

            car_lift_fit = (

                float(
                    car_lift_width
                )
                <=
                float(
                    site_width
                )

                and

                float(
                    car_lift_depth
                )
                <=
                float(
                    site_depth
                )

            )


        car_lift_feasibility = {

            "type":
                "car_lift",

            "status":
                (
                    "feasible"
                    if car_lift_fit is True
                    else
                    "not_feasible"
                    if car_lift_fit is False
                    else
                    "insufficient_evidence"
                ),

            "required_width":
                car_lift_width,

            "required_depth":
                car_lift_depth,

            "queue_length":
                queue_length,

            "site_width":
                site_width,

            "site_depth":
                site_depth,

            "missing_evidence":
                car_lift_missing,

            "site_fit":
                car_lift_fit

        }


        # ==================================================
        # RESOLUTION STATE
        # ==================================================

        feasible_candidates = []


        if ramp_feasibility["status"] == "feasible":

            feasible_candidates.append(
                "vehicle_ramp"
            )


        if car_lift_feasibility["status"] == "feasible":

            feasible_candidates.append(
                "car_lift"
            )


        if len(feasible_candidates) == 1:

            resolution_status = (
                "single_feasible_candidate"
            )

        elif len(feasible_candidates) > 1:

            resolution_status = (
                "multiple_feasible_candidates"
            )

        else:

            resolution_status = (
                "unresolved"
            )


        return {

            "engine":
                "VEHICLE_ACCESS_FEASIBILITY_REASONER",

            "version":
                self.VERSION,

            "vehicle_access_status":
                resolution_status,

            "feasible_candidates":
                feasible_candidates,

            "ramp":
                ramp_feasibility,

            "car_lift":
                car_lift_feasibility,

            "site_evidence":
                {

                    "site_area":
                        site_area,

                    "site_width":
                        site_width,

                    "site_depth":
                        site_depth,

                    "road_access":
                        road_access

                },

            "geometry_generation_allowed":
                False,

            "source_vehicle_access":
                vehicle_access_system

        }
