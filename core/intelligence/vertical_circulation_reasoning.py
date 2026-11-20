"""
ArchitectOS Vertical Circulation Reasoning v2.0

Intelligent decision engine for vertical systems.
"""


class VerticalCirculationReasoning:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"🛗 Vertical Circulation Reasoning v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # VEHICLE ACCESS SITE-AWARE CANDIDATES
    # ==================================================

    def _build_vehicle_access_candidates(
        self,
        building_context
    ):

        site = building_context.get(
            "site",
            {}
        ) or {}


        site_area = site.get(
            "area",
            building_context.get(
                "site_area",
                building_context.get(
                    "area"
                )
            )
        )


        bbox = site.get(
            "bbox",
            {}
        ) or {}


        site_width = bbox.get(
            "width",
            site.get("width")
        )


        site_depth = bbox.get(
            "height",
            site.get("depth")
        )


        road_access = site.get(
            "road_access"
        )


        if road_access is None:

            road_access = site.get(
                "access"
            )

        site_constraints = building_context.get(
            "site_constraints",
            {}
        ) or {}

        access_elevations = site_constraints.get(
            "access_elevations",
            []
        )

        parking = building_context.get("parking", {}) or {}


        evidence = {

            "site_area":
                site_area,

            "site_width":
                site_width,

            "site_depth":
                site_depth,

            "road_access":
                road_access,

            "access_elevations":
                access_elevations if isinstance(access_elevations, list) else [],

            "parking_target":
                {
                    "level": parking.get("level"),
                    "elevation": parking.get("elevation"),
                    "elevation_source": parking.get("elevation_source"),
                }

        }


        ramp_candidate = {

            "type":
                "vehicle_ramp",

            "status":
                "requires_site_fit_analysis",

            "role":
                "continuous_vehicle_access",

            "advantages":
            [
                "continuous_vehicle_movement",
                "no_lift_cycle_dependency",
                "direct_vehicle_connection"
            ],

            "constraints":
            [
                "requires_horizontal_run",
                "requires_slope_resolution",
                "requires_entry_transition",
                "requires_turning_geometry",
                "consumes_site_area"
            ],

            "required_inputs":
            [
                "level_difference",
                "allowable_slope",
                "clear_width",
                "turning_radius",
                "entry_geometry",
                "site_fit"
            ],

            "site_evidence":
                evidence

        }


        car_lift_candidate = {

            "type":
                "car_lift",

            "status":
                "requires_site_fit_analysis",

            "role":
                "mechanized_vehicle_vertical_transport",

            "advantages":
            [
                "compact_horizontal_footprint",
                "avoids_long_ramp_run",
                "suitable_for_constrained_sites"
            ],

            "constraints":
            [
                "requires_lift_shaft",
                "requires_vehicle_queue_space",
                "requires_maneuvering_space",
                "equipment_dependency",
                "cycle_time_dependency"
            ],

            "required_inputs":
            [
                "vehicle_envelope",
                "shaft_dimensions",
                "queue_geometry",
                "maneuvering_geometry",
                "service_levels",
                "site_fit"
            ],

            "site_evidence":
                evidence

        }


        missing_evidence = []


        if site_area is None:

            missing_evidence.append(
                "site_area"
            )


        if site_width is None:

            missing_evidence.append(
                "site_width"
            )


        if site_depth is None:

            missing_evidence.append(
                "site_depth"
            )


        return {

            "candidates":
            [
                ramp_candidate,
                car_lift_candidate
            ],

            "evidence":
                evidence,

            "missing_evidence":
                missing_evidence,

            "selection_ready":
                len(
                    missing_evidence
                ) == 0

        }



    # ==================================================
    # MAIN ANALYSIS
    # ==================================================

    def analyze(
        self,
        building_context
    ):

        building_context = building_context or {}

        systems = []

        # ==================================================
        # NORMALIZE ARCHITECTURAL INTENT
        # ==================================================

        building_type = building_context.get(
            "building_type",
            building_context.get(
                "function",
                "residential"
            )
        )

        requirements = building_context.get(
            "requirements",
            []
        )

        if isinstance(requirements, str):
            requirements = [
                requirements
            ]

        requirements = [
            str(item).lower()
            for item in requirements
        ]

        raw_floors = building_context.get(
            "floors",
            []
        )

        if isinstance(raw_floors, int):

            floor_count = max(
                raw_floors,
                0
            )

            floors = [
                f"F{index}"
                for index in range(
                    floor_count
                )
            ]

        elif isinstance(raw_floors, dict):

            floors = list(
                raw_floors.keys()
            )

            floor_count = len(
                floors
            )

        elif isinstance(raw_floors, (list, tuple)):

            floors = list(
                raw_floors
            )

            floor_count = len(
                floors
            )

        else:

            floors = []

            floor_count = 0

        explicit_vertical = building_context.get("vertical_transport", {})
        explicit_stairs = (
            explicit_vertical.get("stairs", [])
            if isinstance(explicit_vertical, dict) else []
        )
        explicit_stairs = [item for item in explicit_stairs if isinstance(item, dict)]
        if not floors and explicit_stairs:
            ordered = []
            for requirement in explicit_stairs:
                for name in (requirement.get("from_level"), requirement.get("to_level")):
                    if name is not None and name not in ordered:
                        ordered.append(name)
            floors = ordered
            floor_count = len(floors)

        area = building_context.get(
            "area"
        )

        # ==================================================
        # VERTICAL SIZING EVIDENCE
        #
        # IMPORTANT:
        # Do not infer occupancy from site area.
        # Numeric sizing is allowed only when explicit
        # architectural evidence is available.
        # ==================================================

        occupancy_count = building_context.get(
            "occupancy_count"
        )

        occupancy_load = building_context.get(
            "occupancy_load"
        )

        gross_area = building_context.get(
            "gross_area"
        )

        floor_height = building_context.get(
            "floor_height"
        )


        occupancy_evidence = (
            occupancy_count is not None
            or
            occupancy_load is not None
        )


        stair_sizing_status = (
            "evidence_available"
            if occupancy_evidence
            else
            "requires_occupancy_evidence"
        )


        elevator_sizing_status = (
            "evidence_available"
            if occupancy_evidence
            else
            "requires_occupancy_evidence"
        )


        sizing_evidence = {

            "occupancy_count":
                occupancy_count,

            "occupancy_load":
                occupancy_load,

            "gross_area":
                gross_area,

            "floor_height":
                floor_height,

            "floor_count":
                floor_count,

            "building_type":
                building_type
        }

        # ==================================================
        # SEMANTIC REQUIREMENT DETECTION
        # ==================================================

        parking_required = any(

            item in requirements

            for item in [

                "parking",
                "garage",
                "basement_parking",
                "car_parking",
                "vehicle_parking"

            ]

        )

        accessibility_required = any(

            item in requirements

            for item in [

                "accessible",
                "accessibility",
                "disabled_access",
                "wheelchair_access",
                "universal_access"

            ]

        )

        elevator_requested = any(

            item in requirements

            for item in [

                "elevator",
                "lift"

            ]

        )

        car_lift_requested = any(

            item in requirements

            for item in [

                "car_lift",
                "vehicle_lift"

            ]

        )

        ramp_requested = any(

            item in requirements

            for item in [

                "ramp",
                "vehicle_ramp",
                "parking_ramp"

            ]

        )

        escalator_requested = any(

            item in requirements

            for item in [

                "escalator"

            ]

        )

        moving_ramp_requested = any(

            item in requirements

            for item in [

                "moving_ramp",
                "travelator"

            ]

        )

        # ==================================================
        # BUILDING FUNCTION
        # ==================================================

        commercial_types = [

            "commercial",
            "shopping_center",
            "shopping_centre",
            "mall",
            "retail",
            "shop",
            "mixed_use"

        ]

        residential_types = [

            "residential",
            "villa",
            "single_family",
            "apartment",
            "housing"

        ]

        assembly_types = [

            "cinema",
            "movie_theater",
            "movie_theatre",
            "amphitheater",
            "amphitheatre",
            "auditorium",
            "theater",
            "theatre",
            "performance_hall"

        ]


        is_assembly = (
            building_type in assembly_types
        )

        is_commercial = (
            building_type in commercial_types
        )

        is_residential = (
            building_type in residential_types
        )

        multi_level = (
            floor_count > 1
        )

        # ==================================================
        # STAIRS
        # ==================================================

        if explicit_stairs:

            for index, requirement in enumerate(explicit_stairs):
                if requirement.get("required") is False:
                    continue
                parameters = {
                    "stair_type": requirement.get("stair_type"),
                    "required_count": requirement.get("required_count"),
                    "clear_width": requirement.get("clear_width"),
                    "maximum_riser": requirement.get("maximum_riser", requirement.get("riser")),
                    "minimum_tread": requirement.get("minimum_tread", requirement.get("tread")),
                    "flight_count": requirement.get("flight_count"),
                    "landing_required": requirement.get("landing_required"),
                    "landing_width": requirement.get("landing_width"),
                    "landing_depth": requirement.get("landing_depth"),
                    "headroom": requirement.get("headroom"),
                    "conflict_evidence_complete": requirement.get("conflict_evidence_complete"),
                    "conflict_zones": list(requirement.get("conflict_zones") or []),
                    "requirement_source": requirement.get("source"),
                    "evidence_status": requirement.get("evidence_status"),
                }
                zone = requirement.get("stair_zone") or requirement.get("allowed_zone")
                systems.append({
                    "id": requirement.get("id") or f"stair_requirement_{index + 1}",
                    "type": "stairs",
                    "reason": "explicit_project_stair_requirement",
                    "role": requirement.get("role", "vertical_pedestrian_circulation"),
                    "connects": [requirement.get("from_level"), requirement.get("to_level")],
                    "parameters": parameters,
                    "placement_intent": {"protected_zone": zone} if zone is not None else {},
                    "protected_zone": zone is not None,
                    "source": requirement.get("source"),
                    "evidence_status": requirement.get("evidence_status"),
                })

        elif multi_level:

            systems.append(

                {

                    "type":
                        "stairs",

                    "reason":
                        "multi_level_vertical_core",

                    "role":
                        (
                            "assembly_egress_and_public_access"
                            if is_assembly
                            else
                            (
                                "public_vertical_access"
                                if is_commercial
                                else
                                "private_vertical_access"
                            )
                        ),

                    "connects":
                        floors,

                    "parameters":
                    {

                        "stair_type":
                            (
                                "assembly_egress_stair"
                                if is_assembly
                                else
                                (
                                    "public_stair"
                                    if is_commercial
                                    else
                                    "private_stair"
                                )
                            ),

                        "required_count":
                            None,

                        "clear_width":
                            None,

                        "riser":
                            None,

                        "tread":
                            None,

                        "flight_count":
                            None,

                        "landing_required":
                            True,

                        "egress_role":
                            True,

                        "fire_rating":
                            None,

                        "handrail_required":
                            True,

                        "occupancy_basis":
                            (
                                occupancy_count
                                if occupancy_count is not None
                                else occupancy_load
                            ),

                        "gross_area_basis":
                            gross_area,

                        "floor_height_basis":
                            floor_height,

                        "sizing_status":
                            stair_sizing_status,

                        "sizing_evidence":
                            dict(
                                sizing_evidence
                            )

                    },

                    "protected_zone":
                        True

                }

            )

        # ==================================================
        # ELEVATOR
        # ==================================================

        elevator_required = (

            elevator_requested

            or accessibility_required

            or (
                multi_level
                and is_commercial
            )

        )

        if elevator_required:

            systems.append(

                {

                    "type":
                        "elevator",


                    "reason":
                        (
                            "explicit_requirement"
                            if elevator_requested
                            else
                            "vertical_accessibility"
                        ),


                    "role":
                        (
                            "assembly_public_vertical_transport"
                            if is_assembly
                            else
                            (
                                "public_vertical_transport"
                                if is_commercial
                                else
                                "residential_vertical_transport"
                            )
                        ),


                    "connects":
                        floors,


                    "parameters":
                    {

                        "elevator_type":
                            (
                                "assembly_passenger_elevator"
                                if is_assembly
                                else
                                (
                                    "public_passenger_elevator"
                                    if is_commercial
                                    else
                                    "residential_passenger_elevator"
                                )
                            ),


                        "required_count":
                            None,


                        "capacity":
                            None,


                        "rated_load":
                            None,


                        "car_width":
                            None,


                        "car_depth":
                            None,


                        "door_width":
                            None,


                        "shaft_width":
                            None,


                        "shaft_depth":
                            None,


                        "service_floors":
                            floors,


                        "accessible":
                            True,


                        "wheelchair_access":
                            True,


                        "fire_service":
                            None,


                        "stretcher_compatible":
                            None,


                        "machine_room_type":
                            None,

                        "occupancy_basis":
                            occupancy_count
                            if occupancy_count is not None
                            else occupancy_load,

                        "gross_area_basis":
                            gross_area,

                        "floor_height_basis":
                            floor_height,

                        "sizing_status":
                            elevator_sizing_status,

                        "sizing_evidence":
                            dict(
                                sizing_evidence
                            )

                    },


                    "protected_zone":
                        True

                }

            )

        # ==================================================
        # COMMERCIAL PUBLIC FLOW
        # ==================================================

        if (

            is_commercial

            and multi_level

            and (
                escalator_requested
                or building_type in [
                    "mall",
                    "shopping_center",
                    "shopping_centre"
                ]
            )

        ):

            systems.append(

                {

                    "type":
                        "escalator",

                    "reason":
                        "commercial_public_vertical_flow",

                    "connects":
                        floors,

                    "parameters":
                    {

                        "clear_width":
                            None,

                        "capacity":
                            None

                    },

                    "protected_zone":
                        True

                }

            )

        if moving_ramp_requested:

            systems.append(

                {

                    "type":
                        "moving_ramp",

                    "reason":
                        "explicit_public_flow_requirement",

                    "connects":
                        floors,

                    "parameters":
                    {

                        "clear_width":
                            None

                    },

                    "protected_zone":
                        True

                }

            )

        # ==================================================
        # PARKING / VEHICLE ACCESS
        # ==================================================

        if parking_required:

            if car_lift_requested:

                systems.append(

                    {

                        "type":
                            "car_lift",


                        "reason":
                            "explicit_vehicle_lift_requirement",


                        "role":
                            "parking_vertical_vehicle_transport",


                        "connects":
                            floors,


                        "parameters":
                        {

                            "car_lift_type":
                                "vehicle_platform_lift",


                            "vehicle_class":
                                "passenger_vehicle",


                            "rated_capacity":
                                None,


                            "platform_width":
                                None,


                            "platform_length":
                                None,


                            "platform_clear_height":
                                None,


                            "shaft_width":
                                None,


                            "shaft_depth":
                                None,


                            "door_clear_width":
                                None,


                            "vehicle_clearance":
                                None,


                            "service_floors":
                                floors,


                            "entry_alignment":
                                None,


                            "exit_alignment":
                                None,


                            "drive_through_possible":
                                None,


                            "turntable_required":
                                None,


                            "queue_space_required":
                                True,


                            "queue_length":
                                None,


                            "maneuvering_space_required":
                                True,


                            "vehicle_detection_required":
                                True,


                            "safety_interlock_required":
                                True,


                            "pit_required":
                                None,


                            "overhead_clearance":
                                None,


                            "site_fit_required":
                                True

                        },


                        "protected_zone":
                            True

                    }

                )


            elif ramp_requested:

                systems.append(

                    {

                        "type":
                            "vehicle_ramp",

                        "reason":
                            "explicit_vehicle_ramp_requirement",

                        "role":
                            "parking_vehicle_access",

                        "connects":
                            floors,

                        "parameters":
                        {

                            "ramp_type":
                                "vehicle_access_ramp",

                            "clear_width":
                                None,

                            "slope":
                                None,

                            "turning_radius":
                                None,

                            "required_run":
                                None,

                            "entry_clearance":
                                None,

                            "exit_clearance":
                                None,

                            "transition_zone_required":
                                True,

                            "vehicle_only":
                                True,

                            "site_fit_required":
                                True

                        },

                        "protected_zone":
                            True

                    }

                )

            else:

                vehicle_access_analysis = (
                    self._build_vehicle_access_candidates(
                        building_context
                    )
                )

                systems.append(

                    {

                        "type":
                            "vehicle_access_pending",


                        "reason":
                            "parking_requires_site_aware_vehicle_access_decision",


                        "role":
                            "vehicle_access_decision",


                        "connects":
                            floors,


                        "parameters":
                        {

                            "decision_required":
                                True,


                            "decision_mode":
                                "site_aware_comparative_analysis",


                            "candidates":
                                vehicle_access_analysis.get(
                                    "candidates",
                                    []
                                ),


                            "site_evidence":
                                vehicle_access_analysis.get(
                                    "evidence",
                                    {}
                                ),


                            "missing_evidence":
                                vehicle_access_analysis.get(
                                    "missing_evidence",
                                    []
                                ),


                            "selection_ready":
                                vehicle_access_analysis.get(
                                    "selection_ready",
                                    False
                                ),


                            "site_fit_required":
                                True,


                            "geometry_generation_allowed":
                                False,


                            "program_space_generation_allowed":
                                False

                        },


                        "protected_zone":
                            False

                    }

                )

        # ==================================================
        # ACCESSIBLE RAMP
        # ==================================================

        if accessibility_required:

            systems.append(

                {

                    "type":
                        "accessible_ramp",

                    "reason":
                        "accessible_route_requirement",

                    "role":
                        "accessible_pedestrian_route",

                    "connects":
                    [
                        "SITE",
                        floors[0] if floors else "G"
                    ],

                    "parameters":
                    {

                        "ramp_type":
                            "pedestrian_accessible_ramp",

                        "clear_width":
                            None,

                        "slope":
                            None,

                        "landing_required":
                            True,

                        "landing_length":
                            None,

                        "handrail_required":
                            None,

                        "edge_protection_required":
                            None,

                        "wheelchair_access":
                            True,

                        "vehicle_access":
                            False,

                        "site_fit_required":
                            True

                    },

                    "protected_zone":
                        True

                }

            )

        # ==================================================
        # RESULT
        # ==================================================

        return {

            "vertical_systems":
                systems,

            "decision_context":
            {

                "building_type":
                    building_type,

                "area":
                    area,

                "floors":
                    floors,

                "floor_count":
                    floor_count,

                "sizing_evidence":
                    sizing_evidence,

                "occupancy_evidence_available":
                    occupancy_evidence,

                "requirements":
                    requirements,

                "parking_required":
                    parking_required,

                "accessibility_required":
                    accessibility_required,

                "multi_level":
                    multi_level,

                "commercial":
                    is_commercial,

                "residential":
                    is_residential,

                "assembly":
                    is_assembly

            },

            "source":
                "vertical_intelligence_reasoning"

        }
