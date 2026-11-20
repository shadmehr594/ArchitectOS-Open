from core.architecture.reasoning.parcel_fit_reasoner import (
    ParcelFitReasoner
)

from core.architecture.reasoning.parcel_placement_reasoner import (
    ParcelPlacementReasoner
)

class ArchitecturalGeometryIntentGeneratorV1:

    VERSION = "1.3"


    def __init__(self):

        print(
            f"📐 ARCHITECTURAL GEOMETRY INTENT GENERATOR v{self.VERSION} ONLINE"
        )


        from core.architecture.reasoning.opening_reasoner_v1 import (
            OpeningReasonerV1
        )


        self.opening_reasoner = OpeningReasonerV1()

        self.parcel_fit_reasoner = (
            ParcelFitReasoner()
        )

        self.parcel_placement_reasoner = (
            ParcelPlacementReasoner()
        )



    def generate(
        self,
        placement_output,
        roof_strategy=None,
        site_analysis=None,
        vertical_section=None,
        entrance_transition=None,
        architectural_intent=None
    ):

        roof_strategy = roof_strategy or {}

        site_analysis = site_analysis or {}

        vertical_section = vertical_section or {}
        entrance_transition = entrance_transition if isinstance(entrance_transition, dict) else {}

        # VerticalBuildingSectionEngine is the sole source of truth for Z.
        # Preserve level bounds as supplied; geometry must not rebuild them
        # from floor order, elevation, or height.
        vertical_levels_by_name = {}
        vertical_levels = []

        for vertical_level in vertical_section.get(
            "levels",
            []
        ):

            if not isinstance(vertical_level, dict):

                continue

            level_name = vertical_level.get("name")

            if level_name is not None:

                vertical_levels_by_name[level_name] = vertical_level
                vertical_levels.append(vertical_level)

        print(
            "SITE ANALYSIS DEBUG:",
            site_analysis.keys()
        )

        result = {

            "spaces": [],

            "openings": [],

            "vertical_elements": [],

            "floor_geometry_intent": [],

            "roof_geometry_intent": {},

            "site_geometry_intent": {},

            "parcel_fit_evaluation": {},

            "parcel_placement": {},

            "geometry_rules": []
        }

        if isinstance(architectural_intent, dict):
            result["project_requirements"] = {
                "vertical_transport": architectural_intent.get("vertical_transport", {}),
                "vehicle_access": architectural_intent.get("vehicle_access", {}),
                "vehicle_ramp_requirements": architectural_intent.get("vehicle_ramp_requirements", []),
                "parking_requirements": architectural_intent.get("parking_requirements", []),
                "window_requirements": architectural_intent.get("window_requirements", []),
                "parking_pedestrian_requirements": architectural_intent.get("parking_pedestrian_requirements", []),
                "spatial_quality_requirements": architectural_intent.get("spatial_quality_requirements", {}),
            }

        # ==============================================
        # SITE GEOMETRY INTENT v1.0
        #
        # Preserve authoritative SiteReasoner evidence
        # for parcel-fit geometry.
        #
        # No building translation or rotation is
        # performed at this stage.
        # ==============================================

        building_strategy = site_analysis.get(
            "building_strategy",
            {}
        )

        print(
            "BUILDING STRATEGY DEBUG:",
            building_strategy
        )

        if not isinstance(
            building_strategy,
            dict
        ):

            building_strategy = {}


        access_strategy = site_analysis.get(
            "access_strategy",
            {}
        )

        if not isinstance(
            access_strategy,
            dict
        ):

            access_strategy = {}


        parcel_boundary = building_strategy.get(
            "parcel_boundary"
        )
        buildable_boundary = building_strategy.get(
            "buildable_boundary"
        )

        coordinate_system = building_strategy.get(
            "coordinate_system"
        )

        target_parcel = building_strategy.get(
            "target_parcel"
        )

        parcel_area = building_strategy.get(
            "parcel_area"
        )

        parcel_edges = building_strategy.get(
            "parcel_edges",
            []
        )

        neighbor_parcels = building_strategy.get(
            "neighbor_parcels",
            []
        )

        access_edge_index = access_strategy.get(
            "access_edge_index"
        )

        road_width = access_strategy.get(
            "road_width"
        )

        separation = site_analysis.get("separation", site_analysis.get("separation_joints", {}))
        if isinstance(separation, dict) and "separation_joints" in separation:
            separation = separation.get("separation_joints", {})
        if not isinstance(separation, dict):
            separation = {}


        parcel_geometry_available = (

            isinstance(
                parcel_boundary,
                list
            )

            and len(
                parcel_boundary
            ) >= 3

            and coordinate_system
                == "local_normalized"

        )


        result[
            "site_geometry_intent"
        ] = {

            "target_parcel":
                target_parcel,

            "coordinate_system":
                coordinate_system,

            "parcel_boundary":
                parcel_boundary,

            "buildable_boundary":
                buildable_boundary,

            "separation_joint_application":
                dict(site_analysis.get("separation_joint_application", {}))
                if isinstance(site_analysis.get("separation_joint_application"), dict)
                else {},

            "parcel_area":
                parcel_area,

            "parcel_edges":
                list(
                    parcel_edges
                )
                if isinstance(
                    parcel_edges,
                    list
                )
                else [],

            "neighbor_parcels":
                list(
                    neighbor_parcels
                )
                if isinstance(
                    neighbor_parcels,
                    list
                )
                else [],

            "access_edge_index":
                access_edge_index,

            "road_width":
                road_width,

            "pedestrian_access_candidates":
                list(access_strategy.get("pedestrian_access_candidates", []))
                if isinstance(access_strategy.get("pedestrian_access_candidates"), list)
                else [],

            "separation_joints":
                dict(separation),

            "parcel_geometry_available":
                parcel_geometry_available,

            "parcel_fit_status":
                (
                    "ready_for_fit_evaluation"
                    if parcel_geometry_available
                    else "parcel_geometry_pending"
                ),

            "source":
                "site_reasoner"
        }

        if entrance_transition:
            result["site_geometry_intent"]["entrance_transition"] = dict(entrance_transition)

        for key in (
            "pedestrian_access_width",
            "pedestrian_access_preference",
            "confirmed_road_access_edges",
            "setbacks",
            "setback_zones",
            "protected_zones",
            "pedestrian_conflict_zones",
            "vehicle_access_zones",
            "vehicle_circulation_zones",
            "parking_access_zones",
        ):
            if key in access_strategy:
                value = access_strategy.get(key)
                result["site_geometry_intent"][key] = (
                    dict(value) if isinstance(value, dict)
                    else list(value) if isinstance(value, list)
                    else value
                )

        conflict_inventory = architectural_intent.get("site_conflict_inventory") if isinstance(architectural_intent, dict) else None
        if isinstance(conflict_inventory, dict) and conflict_inventory.get("evidence_complete") is True:
            result["site_geometry_intent"]["conflict_zones"] = list(conflict_inventory.get("zones", []))
            result["site_geometry_intent"]["conflict_inventory_source"] = conflict_inventory.get("source")
        pedestrian_requirements = architectural_intent.get("pedestrian_site_access_requirements") if isinstance(architectural_intent, dict) else None
        if isinstance(pedestrian_requirements, dict) and pedestrian_requirements.get("evidence_status") in ("authoritative", "resolved"):
            result["site_geometry_intent"].update({
                "pedestrian_access_width": pedestrian_requirements.get("clear_width"),
                "pedestrian_access_preference": {"access_edge_reference": pedestrian_requirements.get("access_edge_reference")},
                "setbacks": list(pedestrian_requirements.get("setbacks", [])),
                "protected_zones": list(pedestrian_requirements.get("protected_zones", [])),
                "pedestrian_conflict_zones": list(pedestrian_requirements.get("pedestrian_conflict_zones", [])),
                "vehicle_access_zones": list(pedestrian_requirements.get("vehicle_access_zones", [])),
                "vehicle_circulation_zones": list(pedestrian_requirements.get("vehicle_circulation_zones", [])),
                "parking_access_zones": list(pedestrian_requirements.get("parking_access_zones", [])),
            })

        # ==============================================
        # LAYOUT CONTRACT BRIDGE v1.0
        #
        # Convert modern LayoutReasoner spatial_layout
        # into legacy floor grouped contract.
        #
        # No geometry decision is made here.
        # Only data normalization.
        # ==============================================

        if (
            "floors" not in placement_output
            and
            "spatial_layout" in placement_output
        ):

            normalized_floors = {}


            for space in placement_output.get(
                "spatial_layout",
                []
            ):

                if not isinstance(
                    space,
                    dict
                ):

                    continue


                floor = space.get(
                    "floor"
                )


                if floor is None:

                    continue


                # ==============================================
                # RESOLVED DIMENSION CONTRACT NORMALIZATION
                #
                # SpatialPlacementReasoner may expose resolved
                # metric dimensions directly as width / depth.
                #
                # Floor Geometry Intent consumes the canonical
                # resolved_dimensions contract.
                #
                # No dimension is invented here.
                # Existing authoritative metric values are only
                # normalized into the geometry contract.
                # ==============================================

                resolved_dimensions = space.get(
                    "resolved_dimensions"
                )


                if not isinstance(
                    resolved_dimensions,
                    dict
                ):

                    width = space.get(
                        "width"
                    )

                    depth = space.get(
                        "depth"
                    )


                    try:

                        metric_width = float(
                            width
                        )

                        metric_depth = float(
                            depth
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        metric_width = None
                        metric_depth = None


                    if (
                        metric_width is not None
                        and
                        metric_depth is not None
                        and
                        metric_width > 0
                        and
                        metric_depth > 0
                    ):

                        space[
                            "resolved_dimensions"
                        ] = {

                            "width":
                                metric_width,

                            "depth":
                                metric_depth,

                            "area":
                                (
                                    metric_width
                                    *
                                    metric_depth
                                )

                        }


                normalized_floors.setdefault(
                    floor,
                    {
                        "spaces": []
                    }
                )


                normalized_floors[
                    floor
                ][
                    "spaces"
                ].append(
                    space
                )


            placement_output[
                "floors"
            ] = normalized_floors


            placement_output[
                "floors"
            ] = normalized_floors

        # ==============================================
        # FLOOR GEOMETRY INTENT v1.0
        #
        # Floor geometry is aggregated at floor level.
        #
        # IMPORTANT:
        # This is still geometry intent.
        # Do not invent a polygon while spatial
        # coordinates remain abstract_grid or dimensions
        # are unresolved.
        # ==============================================

        for floor, floor_data in placement_output.get(
            "floors",
            {}
        ).items():

            if not isinstance(
                floor_data,
                dict
            ):

                continue


            floor_spaces = floor_data.get(
                "spaces",
                []
            )


            if not isinstance(
                floor_spaces,
                list
            ):

                floor_spaces = []


            if floor == "SITE":

                continue


            space_names = [

                space.get(
                    "name"
                )

                for space in floor_spaces

                if isinstance(
                    space,
                    dict
                )
                and space.get(
                    "name"
                )

            ]


            coordinate_modes = [

                space.get(
                    "coordinate_mode"
                )

                for space in floor_spaces

                if isinstance(
                    space,
                    dict
                )
                and space.get(
                    "coordinate_mode"
                )

            ]


            dimensions_resolved = all(

                isinstance(
                    space.get(
                        "resolved_dimensions"
                    ),
                    dict
                )

                for space in floor_spaces

                if isinstance(
                    space,
                    dict
                )

            ) if floor_spaces else False


            geometry_status = (

                "ready_for_floor_envelope_resolution"

                if (
                    dimensions_resolved
                    and
                    coordinate_modes
                    and
                    all(
                        mode != "abstract_grid"
                        for mode in coordinate_modes
                    )
                )

                else "spatial_geometry_pending"
            )

            # ==============================================
            # METRIC FLOOR ENVELOPE RESOLUTION v1.0
            #
            # Resolve the aggregate floor envelope only when
            # every architectural space has valid metric
            # coordinates and dimensions.
            #
            # No parcel translation is performed here.
            # Coordinates remain floor-local metric values.
            # ==============================================

            metric_floor_envelope = None


            if (
                geometry_status
                == "ready_for_floor_envelope_resolution"
            ):

                metric_rectangles = []


                for space in floor_spaces:

                    if not isinstance(
                        space,
                        dict
                    ):

                        continue


                    x = space.get(
                        "x"
                    )

                    y = space.get(
                        "y"
                    )

                    resolved_dimensions = space.get(
                        "resolved_dimensions"
                    )


                    if not isinstance(
                        resolved_dimensions,
                        dict
                    ):

                        metric_rectangles = []

                        break


                    width = resolved_dimensions.get(
                        "width"
                    )

                    depth = resolved_dimensions.get(
                        "depth"
                    )


                    try:

                        x = float(
                            x
                        )

                        y = float(
                            y
                        )

                        width = float(
                            width
                        )

                        depth = float(
                            depth
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        metric_rectangles = []

                        break


                    if (
                        width <= 0
                        or
                        depth <= 0
                    ):

                        metric_rectangles = []

                        break


                    metric_rectangles.append(
                        {
                            "x":
                                x,

                            "y":
                                y,

                            "width":
                                width,

                            "depth":
                                depth
                        }
                    )


                if (
                    metric_rectangles
                    and
                    len(
                        metric_rectangles
                    )
                    ==
                    len(
                        floor_spaces
                    )
                ):

                    min_x = min(
                        rectangle[
                            "x"
                        ]
                        for rectangle in metric_rectangles
                    )

                    min_y = min(
                        rectangle[
                            "y"
                        ]
                        for rectangle in metric_rectangles
                    )

                    max_x = max(
                        rectangle[
                            "x"
                        ]
                        +
                        rectangle[
                            "width"
                        ]
                        for rectangle in metric_rectangles
                    )

                    max_y = max(
                        rectangle[
                            "y"
                        ]
                        +
                        rectangle[
                            "depth"
                        ]
                        for rectangle in metric_rectangles
                    )


                    envelope_width = (
                        max_x
                        -
                        min_x
                    )

                    envelope_depth = (
                        max_y
                        -
                        min_y
                    )


                    metric_floor_envelope = {

                        "min_x":
                            min_x,

                        "min_y":
                            min_y,

                        "max_x":
                            max_x,

                        "max_y":
                            max_y,

                        "width":
                            envelope_width,

                        "depth":
                            envelope_depth,

                        "area":
                            (
                                envelope_width
                                *
                                envelope_depth
                            ),

                        "coordinate_mode":
                            "architectural_metric",

                        "origin_mode":
                            "floor_local",

                        "status":
                            "resolved_metric_envelope"

                    }


                    geometry_status = (
                        "resolved_metric_envelope"
                    )

            # ==============================================
            # FLOOR LEVEL SPAN RESOLUTION v1.2
            #
            # AUTHORITATIVE ORDER:
            #
            # 1. vertical_section.levels[*]
            #    is the architectural Z source of truth.
            #
            # 2. floor_data["height"]
            # 3. space-level floor_height evidence
            #    only as compatibility fallback
            #
            # Bounds and height are copied, never derived
            # from each other in the geometry layer.
            # ==============================================

            resolved_floor_height = None
            floor_height_status = (
                "floor_height_unresolved"
            )

            vertical_level = vertical_levels_by_name.get(
                floor,
                {}
            )

            level_bottom = vertical_level.get(
                "bottom"
            )

            level_top = vertical_level.get(
                "top"
            )

            authoritative_level_height = vertical_level.get(
                "height"
            )

            if isinstance(
                authoritative_level_height,
                (int, float)
            ) and authoritative_level_height > 0:

                resolved_floor_height = authoritative_level_height
                floor_height_status = (
                    "resolved_from_vertical_section_level"
                )


            # ----------------------------------------------
            # AUTHORITATIVE FLOOR-LEVEL CONTRACT
            # ----------------------------------------------

            authoritative_floor_height = None


            if isinstance(
                floor_data,
                dict
            ):

                authoritative_floor_height = (
                    floor_data.get(
                        "height"
                    )
                )


            if (
                resolved_floor_height is None
                and isinstance(
                authoritative_floor_height,
                (int, float)
                )
            ):

                authoritative_floor_height = float(
                    authoritative_floor_height
                )


                if authoritative_floor_height > 0:

                    resolved_floor_height = (
                        authoritative_floor_height
                    )

                    floor_height_status = (
                        "resolved_from_floor_contract"
                    )


            # ----------------------------------------------
            # SPACE-LEVEL COMPATIBILITY FALLBACK
            # ----------------------------------------------

            if resolved_floor_height is None:

                resolved_floor_heights = []


                for floor_space in floor_spaces:

                    if not isinstance(
                        floor_space,
                        dict
                    ):

                        continue


                    floor_height = floor_space.get(
                        "floor_height"
                    )


                    if not isinstance(
                        floor_height,
                        (int, float)
                    ):

                        continue


                    floor_height = float(
                        floor_height
                    )


                    if floor_height <= 0:

                        continue


                    resolved_floor_heights.append(
                        floor_height
                    )


                unique_floor_heights = sorted(
                    list(
                        set(
                            resolved_floor_heights
                        )
                    )
                )


                if len(
                    unique_floor_heights
                ) == 1:

                    resolved_floor_height = (
                        unique_floor_heights[
                            0
                        ]
                    )

                    floor_height_status = (
                        "resolved_from_space_evidence"
                    )


                elif len(
                    unique_floor_heights
                ) > 1:

                    resolved_floor_height = None

                    floor_height_status = (
                        "conflicting_floor_height_evidence"
                    )


            result[
                "floor_geometry_intent"
            ].append(

                {

                    "floor":
                        floor,

                    "elevation":
                        level_bottom,

                    "bottom":
                        level_bottom,

                    "top":
                        level_top,

                    "height":
                        resolved_floor_height,

                    "height_status":
                        floor_height_status,

                    "space_names":
                        space_names,

                    "space_count":
                        len(
                            space_names
                        ),

                    "coordinate_modes":
                        list(
                            dict.fromkeys(
                                coordinate_modes
                            )
                        ),

                    "dimensions_resolved":
                        dimensions_resolved,

                    "geometry_status":
                        geometry_status,

                    "geometry_type":
                        (
                            "metric_floor_envelope"
                            if metric_floor_envelope
                            is not None
                            else "aggregate_floor"
                        ),

                    "envelope":
                        metric_floor_envelope,

                    "source":
                        "architectural_element_placement"

                }

            )

        # ==============================================
        # PARCEL FIT EVALUATION v1.0
        #
        # Evaluate dimensional fit only after metric
        # floor envelopes and parcel geometry exist.
        #
        # No translation or rotation is applied here.
        # ==============================================

        result[
            "parcel_fit_evaluation"
        ] = self.parcel_fit_reasoner.evaluate(
            result.get(
                "site_geometry_intent",
                {}
            ),
            result.get(
                "floor_geometry_intent",
                []
            )
        )

        # ==============================================
        # PARCEL PLACEMENT RESOLUTION v1.0
        #
        # Convert parcel-fit feasibility into a formal
        # parcel placement transform.
        #
        # IMPORTANT:
        # - floor-local x / y coordinates are preserved
        # - translation is stored as a separate transform
        # - no geometry mutation occurs here
        # ==============================================

        parcel_fit_evaluation = result.get(
            "parcel_fit_evaluation",
            {}
        )


        reference_floor = None


        if isinstance(
            parcel_fit_evaluation,
            dict
        ):

            reference_floor = parcel_fit_evaluation.get(
                "reference_floor"
            )


        placement_spaces = []


        placement_floors = placement_output.get(
            "floors",
            {}
        )


        if isinstance(
            placement_floors,
            dict
        ):

            # Building placement is anchored by the architectural entrance,
            # which need not belong to the footprint-reference floor (for
            # example, when a basement is the first/largest resolved floor).
            # Preserve every resolved floor-space as candidate evidence; the
            # placement reasoner still requires a unique entrance tied to the
            # confirmed access edge.
            for floor_data in placement_floors.values():

                if not isinstance(floor_data, dict):

                    continue


                floor_spaces = floor_data.get("spaces", [])


                if isinstance(floor_spaces, list):

                    placement_spaces.extend(floor_spaces)


        result[
            "parcel_placement"
        ] = self.parcel_placement_reasoner.resolve(
            result.get(
                "site_geometry_intent",
                {}
            ),
            parcel_fit_evaluation,
            placement_spaces
        )

        # ==============================================
        # ROOF GEOMETRY INTENT v1.0
        #
        # Preserve RoofFormReasoner semantic strategy.
        #
        # Geometry remains pending until the upper
        # building envelope is spatially resolved.
        # ==============================================

        resolved_roof_strategy = roof_strategy.get(
            "roof_strategy",
            roof_strategy
        )


        if not isinstance(
            resolved_roof_strategy,
            dict
        ):

            resolved_roof_strategy = {}

        roof_level = vertical_section.get(
            "roof_level"
        )

        roof_source_level = (
            vertical_levels[-1].get("name")
            if vertical_levels
            else None
        )

        roof_source_level_top = (
            vertical_levels[-1].get("top")
            if vertical_levels
            else None
        )

        if (
            isinstance(roof_level, (int, float))
            and isinstance(roof_source_level_top, (int, float))
        ):

            roof_z_contract_status = (
                "consistent_with_last_level_top"
                if roof_level == roof_source_level_top
                else "conflicting_roof_level_and_last_level_top"
            )

        else:

            roof_z_contract_status = "roof_z_contract_unresolved"


        result[
            "roof_geometry_intent"
        ] = {

            "roof_type":
                resolved_roof_strategy.get(
                    "roof_type"
                ),

            "roof_level":
                roof_level,

            "source_level":
                roof_source_level,

            "source_level_top":
                roof_source_level_top,

            "z_contract_status":
                roof_z_contract_status,

            "elements":
                list(
                    resolved_roof_strategy.get(
                        "elements",
                        []
                    )
                    or []
                ),

            "composition":
                resolved_roof_strategy.get(
                    "composition"
                ),

            "skyline":
                resolved_roof_strategy.get(
                    "skyline"
                ),

            "geometry_status":
                (
                    "roof_envelope_pending"
                    if resolved_roof_strategy
                    else "roof_strategy_unavailable"
                ),

            "source":
                roof_strategy.get(
                    "source",
                    "architectural_reasoning"
                )
                if isinstance(
                    roof_strategy,
                    dict
                )
                else "architectural_reasoning"

        }



        # ==================================
        # SPACE GEOMETRY INTENT
        # ==================================

        for floor, data in placement_output.get(
            "floors",
            {}
        ).items():

            vertical_level = vertical_levels_by_name.get(
                floor,
                {}
            )

            level_bottom = vertical_level.get(
                "bottom"
            )

            level_top = vertical_level.get(
                "top"
            )

            level_height = vertical_level.get(
                "height"
            )

            level_span_resolved = all(
                isinstance(value, (int, float))
                for value in (
                    level_bottom,
                    level_top,
                    level_height
                )
            )


            for space in data.get(
                "spaces",
                []
            ):

                placement_decision = space.get(
                    "placement_decision",
                    {}
                )

                if not isinstance(
                    placement_decision,
                    dict
                ):
                    placement_decision = {}

                print(
                    "GEOMETRY INTENT PARCEL DEBUG:",
                    space.get("name"),
                    "LOCAL:",
                    space.get("parcel_edges"),
                    "BUILDING:",
                    len(parcel_edges)
                )


                space_geometry = {


                    "name":
                        space.get(
                            "name"
                        ),


                    "floor":
                        floor,


                    "elevation":
                        level_bottom,


                    "bottom":
                        level_bottom,


                    "top":
                        level_top,


                    "height":
                        (
                            level_height
                            if level_span_resolved
                            else self.resolve_height(
                                data,
                                space
                            )
                        ),


                    "level_span_status":
                        (
                            "resolved_from_vertical_section_level"
                            if level_span_resolved
                            else "vertical_section_level_unresolved"
                        ),


                    "geometry_type":
                        space.get(

                            "geometry_type",

                            "room"

                        ),


                    "shape_intent":
                        self.get_shape_intent(

                            space.get(
                                "zone"
                            )

                        ),

                    # --------------------------------------
                    # PRESERVE SPATIAL / PARCEL EVIDENCE
                    # --------------------------------------

                    "x":
                        space.get(
                            "x"
                        ),

                    "y":
                        space.get(
                            "y"
                        ),

                    # --------------------------------------
                    # PRESERVE RESOLVED SPACE DIMENSIONS
                    #
                    # SpatialPlacementReasoner already carries
                    # authoritative resolved_dimensions.
                    # GeometryIntent must preserve them for
                    # room geometry generation.
                    # --------------------------------------

                    "resolved_dimensions":
                        (
                            dict(
                                space.get(
                                    "resolved_dimensions"
                                )
                            )
                            if isinstance(
                            space.get(
                                    "resolved_dimensions"
                            ),
                                dict
                            )

                            else

                            {

                                "width":
                                    space.get(
                                        "width"
                                    ),

                                "depth":
                                    space.get(
                                        "depth"
                                    ),

                                "area":
                                    (
                                        float(
                                            space.get(
                                                "width",
                                                0
                                            )
                                        )
                                        *
                                        float(
                                            space.get(
                                                "depth",
                                                0
                                            )
                                        )
                                    )

                            }
                        ),

                    "width":
                        (
                            space.get(
                                "resolved_dimensions",
                                {}
                            ).get(
                                "width"
                            )
                            if isinstance(
                                space.get(
                                    "resolved_dimensions"
                                ),
                                dict
                            )
                            else 
                            space.get(
                                "width"
                            )
                        ),

                    "depth":
                        (
                            space.get(
                                "resolved_dimensions",
                                {}
                            ).get(
                                "depth"
                            )
                            if isinstance(
                                space.get(
                                    "resolved_dimensions"
                                ),
                                dict
                            )
                            else 
                            space.get(
                                "depth"
                            )
                        ),

                    "coordinate_mode":
                        space.get(
                            "coordinate_mode"
                        ),

                    "placement_reason":
                        space.get(
                            "placement_reason"
                        ),

                    "anchor_space":
                        space.get(
                            "anchor_space"
                        ),

                    "access_edge_index":
                        space.get(
                            "access_edge_index"
                        ),

                    "road_width":
                        space.get(
                            "road_width"
                        ),

                    "access_edge_status":
                        space.get(
                            "access_edge_status"
                        ),

                    "parcel_relation":
                        space.get(
                            "parcel_relation"
                        ),

                    "preferred_edge_index":
                        placement_decision.get(
                            "preferred_edge_index",
                            space.get(
                                "preferred_edge_index"
                            )
                        ),

                    "edge_relation":
                        placement_decision.get(
                            "resolved_edge_relation",
                            space.get(
                                "edge_relation"
                            )
                        ),

                    "edge_decision_status":
                        placement_decision.get(
                            "edge_resolution_status",
                            space.get(
                                "edge_decision_status"
                            )
                        ),

                    "edge_decision_reason":
                        placement_decision.get(
                            "edge_resolution_reason",
                            space.get(
                                "edge_decision_reason"
                            )
                        ),

                    "site_context":
                        space.get(
                            "site_context"
                        ),

                    "parcel_edges":
                        list(
                            building_strategy.get(
                                "parcel_edges",
                                []
                            )
                        ),


                    "parcel_edge_roles":
                        [
                            {
                                "edge_index":
                                    edge.get(
                                        "edge_index"
                                    ),

                                "relation":
                                    edge.get(
                                        "relation"
                                    ),

                                "confirmed":
                                    bool(
                                        edge.get(
                                            "confirmed",
                                            False
                                        )
                                    ),

                                "confidence":
                                    edge.get(
                                        "confidence"
                                    ),

                                "privacy_constraint":
                                    edge.get(
                                        "privacy_constraint",
                                        False
                                    ),

                                "parcel_id":
                                    edge.get(
                                        "parcel_id"
                                    )
                            }

                            for edge in building_strategy.get(
                                "parcel_edges",
                                []
                            )

                            if isinstance(
                                edge,
                                dict
                            )
                        ],

                    "design_requirements":
                    {

                        "role":
                            space.get(
                                "role"
                            ),

                        "zone":
                            space.get(
                                "zone"
                            ),

                        "position_intent":
                            space.get(
                                "position_intent"
                            ),

                        "importance":
                            space.get(
                                "importance",
                                "normal"
                            ),

                        "protected_zone":
                            bool(
                                space.get(
                                    "protected_zone",
                                    False
                                )
                            ),

                        "placement_scope":
                            space.get(
                                "placement_scope"
                            ),

                        "access_requirement":
                            space.get(
                                "access_requirement"
                            ),

                        # ----------------------------------
                        # PARCEL / EDGE EVIDENCE
                        # ----------------------------------

                        "access_edge_index":
                            space.get(
                                "access_edge_index"
                            ),

                        "road_width":
                            space.get(
                                "road_width"
                            ),

                        "access_edge_status":
                            space.get(
                                "access_edge_status"
                            ),

                        "parcel_relation":
                            space.get(
                                "parcel_relation"
                            ),

                        "preferred_edge_index":
                            space.get(
                                "preferred_edge_index"
                            ),

                        "edge_relation":
                            space.get(
                                "edge_relation"
                            ),

                        "edge_decision_status":
                            space.get(
                                "edge_decision_status"
                            ),

                        "edge_decision_reason":
                            space.get(
                                "edge_decision_reason"
                            ),

                        "site_context":
                            space.get(
                                "site_context"
                            )
                    }

                }



                result["spaces"].append(
                    space_geometry
                )



                # ==================================
                # OPENING INTELLIGENCE
                # ==================================

                opening_result = self.opening_reasoner.resolve(
                    space_geometry
                )


                if opening_result:

                    result["openings"].append(
                        {

                            "floor":
                                floor,


                            **opening_result

                        }
                    )





        # ==================================
        # VERTICAL ELEMENT GEOMETRY
        # ==================================

        for element in placement_output.get(
            "vertical_core",
            []
        ):


            element_name = element.get(
                "name"
            )


            if not element_name:

                element_name = element.get(
                    "type"
                )

            connects = element.get(
                "connects",
                []
            )

            if isinstance(connects, str):

                connects = [connects]

            elif not isinstance(connects, (list, tuple)):

                connects = []

            continuous = element.get(
                "continuous",
                True
            )

            served_level_spans = [
                {
                    "name": level.get("name"),
                    "bottom": level.get("bottom"),
                    "top": level.get("top"),
                    "height": level.get("height")
                }
                for level in vertical_levels
                if level.get("name") in connects
            ]

            span_source = "explicit_connected_levels"

            if (
                not served_level_spans
                and not connects
                and continuous
            ):

                served_level_spans = [
                    {
                        "name": level.get("name"),
                        "bottom": level.get("bottom"),
                        "top": level.get("top"),
                        "height": level.get("height")
                    }
                    for level in vertical_levels
                ]

                span_source = "continuous_all_levels"

            span_bottom = (
                served_level_spans[0].get("bottom")
                if served_level_spans
                else None
            )

            span_top = (
                served_level_spans[-1].get("top")
                if served_level_spans
                else None
            )

            span_status = (
                "resolved_from_vertical_section_levels"
                if served_level_spans
                and isinstance(span_bottom, (int, float))
                and isinstance(span_top, (int, float))
                else "vertical_core_span_unresolved"
            )

            # These are level-transition intents, not physical stair flights.
            # Physical risers, treads and geometry are resolved later from
            # explicit stair rules and protected-core geometry.
            stair_flights = [
                {
                    "from_level": served_level_spans[index].get("name"),
                    "to_level": served_level_spans[index + 1].get("name"),
                    "bottom": served_level_spans[index].get("bottom"),
                    "top": served_level_spans[index + 1].get("bottom"),
                    "source": "vertical_section.levels",
                    "geometry_status": "level_transition_only",
                }
                for index in range(max(0, len(served_level_spans) - 1))
                if isinstance(served_level_spans[index].get("bottom"), (int, float))
                and isinstance(served_level_spans[index + 1].get("bottom"), (int, float))
            ]



            result["vertical_elements"].append(

                {


                    "name":
                        element_name,


                    "geometry_type":
                        self.get_vertical_geometry(

                            element_name

                        ),


                    "category":
                        element.get(
                            "category"
                        ),


                    "location_intent":
                        element.get(
                            "placement_intent"
                        ),


                    "continuous":
                        continuous,


                    "connects":
                        list(connects),


                    "served_levels":
                        [
                            level.get("name")
                            for level in served_level_spans
                        ],


                    "served_level_spans":
                        served_level_spans,


                    "bottom":
                        span_bottom,


                    "top":
                        span_top,


                    "span_status":
                        span_status,


                    "span_source":
                        span_source,


                    "parameters":
                        dict(
                            element.get(
                                "parameters",
                                {}
                            )
                        ),

                    "stair_id":
                        element.get("stair_id", element.get("id", element_name)),

                    "protected_zone":
                        element.get("protected_zone"),

                    "source_evidence":
                        element.get("source_evidence", {
                            "levels": "vertical_section.levels",
                            "system": "vertical_core"
                        }),

                    "flights":
                        stair_flights,


                    "reason":
                        element.get(
                            "reason"
                        )

                }

            )





        # ==================================
        # GEOMETRY RULES
        # ==================================

        result["geometry_rules"] = [


            "rooms_have_defined_boundaries",


            "public_spaces_prefer_external_edges",


            "private_spaces_require_controlled_openings",


            "opening_size_based_on_space_function",


            "opening_type_based_on_architectural_role",


            "vertical_core_requires_continuous_alignment",


            "accessibility_elements_require_clear_geometry"


        ]



        return result






    # ==================================
    # HEIGHT RESOLUTION
    # ==================================

    def resolve_height(
        self,
        floor_data,
        space
    ):


        if isinstance(
            space,
            dict
        ):

            floor_height = space.get(
                "floor_height"
            )


            if isinstance(
                floor_height,
                (int, float)
            ):

                if float(
                    floor_height
                ) > 0:

                    return float(
                        floor_height
                    )


        if isinstance(
            floor_data,
            dict
        ):

            floor_height = floor_data.get(
                "height"
            )


            if isinstance(
                floor_height,
                (int, float)
            ):

                if float(
                    floor_height
                ) > 0:

                    return float(
                        floor_height
                    )


        return None






    # ==================================
    # SPACE SHAPE INTENT
    # ==================================

    def get_shape_intent(
        self,
        zone
    ):


        mapping = {


            "public":
                "open_rectangular_space",


            "private":
                "controlled_private_space",


            "service":
                "compact_service_space",


            "external":
                "site_related_space",


            "circulation":
                "connection_space"

        }


        return mapping.get(

            zone,

            "generic_space"

        )






    # ==================================
    # VERTICAL GEOMETRY
    # ==================================

    def get_vertical_geometry(
        self,
        name
    ):


        mapping = {


            "stairs":
                "stair_geometry",


            "elevator":
                "vertical_shaft",


            "ramp":
                "ramp_geometry",


            "accessible_ramp":
                "accessible_ramp_geometry",


            "vehicle_ramp":
                "vehicle_ramp_geometry",


            "car_lift":
                "vehicle_lift_geometry",


            "escalator":
                "escalator_geometry",


            "moving_ramp":
                "moving_ramp_geometry"

        }


        return mapping.get(

            name,

            "vertical_element"

        )
