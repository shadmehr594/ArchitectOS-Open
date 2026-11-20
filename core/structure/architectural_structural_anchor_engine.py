print(
    "USING architectural_structural_anchor_engine.py"
)


class ArchitecturalStructuralAnchorEngine:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Architectural Structural Anchor Engine v1.0 ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def extract(
        self,
        architectural_model
    ):


        if not isinstance(
            architectural_model,
            dict
        ):

            architectural_model = {}


        anchors = {

            # ------------------------------------------
            # LEGACY CARTESIAN ANCHORS
            # ------------------------------------------

            "x_anchors":
                [],

            "y_anchors":
                [],

            "master_x_anchors": 
                [],

            "master_y_anchors": 
                [],

            # ------------------------------------------
            # STRUCTURAL ARCHITECTURAL CONSTRAINTS
            # ------------------------------------------

            "floor_boundary_evidence": 
                [],

            "core_zones":
                [],

            "external_edges":
                [],

            "structural_hints":
                [],

            # ------------------------------------------
            # ARCHITECTURE-FIRST GEOMETRY
            #
            # Real parcel-local polygons are preserved
            # here without flattening them into X/Y axes.
            # ------------------------------------------

            "architectural_space_polygons":
                [],

            "support_domains":
                [],

            "primary_support_domain":
                None,

            "coordinate_frame":
                {},

            "architecture_first":
                False

        }


        # ==================================================
        # BUILDING
        # ==================================================

        building = architectural_model.get(
            "building",
            {}
        )


        if not isinstance(
            building,
            dict
        ):

            building = {}


        width = building.get(
            "width",
            0
        )


        depth = building.get(
            "depth",
            0
        )


        try:

            width = float(
                width
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            width = 0.0


        try:

            depth = float(
                depth
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            depth = 0.0


        # ==================================================
        # LEGACY SPACES
        # ==================================================

        spaces = architectural_model.get(
            "spaces",
            []
        )


        if not isinstance(
            spaces,
            list
        ):

            spaces = []


        # ==================================================
        # ARCHITECTURE-FIRST SPACES
        # ==================================================

        architectural_spaces = architectural_model.get(
            "architectural_spaces",
            []
        )


        if not isinstance(
            architectural_spaces,
            list
        ):

            architectural_spaces = []


        # ==================================================
        # COORDINATE FRAME
        # ==================================================

        coordinate_frame = architectural_model.get(
            "coordinate_frame",
            {}
        )


        if not isinstance(
            coordinate_frame,
            dict
        ):

            coordinate_frame = {}


        anchors[
            "coordinate_frame"
        ] = dict(
            coordinate_frame
        )


        anchors[
            "architecture_first"
        ] = bool(
            architectural_spaces
        )

        # ==================================================
        # ARCHITECTURAL GEOMETRY SUPPORT DOMAIN v1.0
        #
        # Structural support geometry must come from the
        # resolved architectural floor/slab footprint.
        #
        # IMPORTANT:
        #
        # - parcel-local polygon remains authoritative
        # - no bounding-box structural domain is invented
        # - no rotation is removed
        # - source floor-local polygon is preserved
        # - lowest available architectural slab becomes
        #   the primary structural support domain
        # ==================================================

        architectural_geometry = architectural_model.get(
            "architectural_geometry",
            {}
        )


        if not isinstance(
            architectural_geometry,
            dict
        ):

            architectural_geometry = {}


        slabs = architectural_geometry.get(
            "slabs",
            []
        )


        if not isinstance(
            slabs,
            list
        ):

            slabs = []


        floor_priority = {

            "basement":
                -1,

            "parking":
                -1,

            "ground_floor":
                0,

            "f1":
                0,

            "upper_floor":
                1,

            "f2":
                1,

            "third_floor":
                2,

            "f3":
                2

        }


        for slab in slabs:

            if not isinstance(
                slab,
                dict
            ):

                continue


            footprint = slab.get(
                "footprint"
            )


            if not isinstance(
                footprint,
                dict
            ):

                continue


            points = footprint.get(
                "points"
            )


            if (
                not isinstance(
                    points,
                    list
                )
                or
                len(
                    points
                ) < 3
            ):

                continue


            polygon = []


            for point in points:

                if (
                    not isinstance(
                        point,
                        (list, tuple)
                    )
                    or
                    len(
                        point
                    ) < 2
                ):

                    continue


                try:

                    point_x = float(
                        point[0]
                    )

                    point_y = float(
                        point[1]
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue


                polygon.append(
                    [
                        point_x,
                        point_y
                    ]
                )


            if len(
                polygon
            ) < 3:

                continue


            source_points = footprint.get(
                "source_points"
            )


            normalized_source_points = []


            if isinstance(
                source_points,
                list
            ):

                for point in source_points:

                    if (
                        not isinstance(
                            point,
                            (list, tuple)
                        )
                        or
                        len(
                            point
                        ) < 2
                    ):

                        continue


                    try:

                        source_x = float(
                            point[0]
                        )

                        source_y = float(
                            point[1]
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        continue


                    normalized_source_points.append(
                        [
                            source_x,
                            source_y
                        ]
                    )


            polygon_x_values = [

                point[0]

                for point in polygon

            ]


            polygon_y_values = [

                point[1]

                for point in polygon

            ]


            min_x = min(
                polygon_x_values
            )

            min_y = min(
                polygon_y_values
            )

            max_x = max(
                polygon_x_values
            )

            max_y = max(
                polygon_y_values
            )


            floor = slab.get(
                "floor"
            )


            normalized_floor = str(
                floor
                or ""
            ).lower()


            support_domain = {

                "floor":
                    floor,

                "polygon":
                    polygon,

                "source_polygon":
                    normalized_source_points,

                "bounds":
                    [
                        min_x,
                        min_y,
                        max_x - min_x,
                        max_y - min_y
                    ],

                "geometry_type":
                    slab.get(
                        "geometry_type",
                        footprint.get(
                            "type",
                            "polygon"
                        )
                    ),

                "geometry_status":
                    slab.get(
                        "geometry_status"
                    ),

                "coordinate_mode":
                    footprint.get(
                        "coordinate_mode",
                        slab.get(
                            "coordinate_mode"
                        )
                    ),

                "rotation_degrees":
                    footprint.get(
                        "rotation_degrees",
                        coordinate_frame.get(
                            "rotation_degrees"
                        )
                    ),

                "priority":
                    floor_priority.get(
                        normalized_floor,
                        100
                    ),

                "source":
                    "architectural_floor_slab"

            }


            anchors[
                "support_domains"
            ].append(
                support_domain
            )


        if anchors[
            "support_domains"
        ]:

            sorted_support_domains = sorted(

                anchors[
                    "support_domains"
                ],

                key=lambda domain: (
                    domain.get(
                        "priority",
                        100
                    ),
                    str(
                        domain.get(
                            "floor"
                        )
                        or ""
                    )
                )

            )


            anchors[
                "support_domains"
            ] = sorted_support_domains


            anchors[
                "primary_support_domain"
            ] = dict(
                sorted_support_domains[
                    0
                ]
            )

        # ==================================================
        # MASTER GRID + FLOOR BOUNDARY EVIDENCE v1.1
        #
        # One vertically coordinated structural grid belongs
        # to the primary / lowest structural support domain.
        #
        # Upper-floor support boundaries are architectural
        # masking evidence only. They must NOT automatically
        # become master structural axes.
        #
        # Example:
        #
        # ground_floor:
        #     0.0 -> 14.4968
        #
        # upper_floor:
        #     0.0 -> 12.1633
        #
        # 12.1633 means:
        #     upper-floor support terminates here
        #
        # It does NOT automatically mean:
        #     create a new structural column axis here
        # ==================================================

        primary_support_domain = anchors.get(
            "primary_support_domain"
        )


        master_x_anchors = []

        master_y_anchors = []

        floor_boundary_evidence = []


        # ==================================================
        # PRIMARY SUPPORT DOMAIN -> MASTER GRID EVIDENCE
        # ==================================================

        if isinstance(
            primary_support_domain,
            dict
        ):

            primary_source_polygon = (
                primary_support_domain.get(
                    "source_polygon"
                )
            )


            if isinstance(
                primary_source_polygon,
                list
            ):

                primary_points = []


                for point in primary_source_polygon:

                    if (
                        not isinstance(
                            point,
                            (list, tuple)
                        )
                        or
                        len(
                            point
                        ) < 2
                    ):

                        continue


                    try:

                        point_x = float(
                            point[0]
                        )

                        point_y = float(
                            point[1]
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        continue


                    primary_points.append(
                        (
                            point_x,
                            point_y
                        )
                    )


                if primary_points:

                    primary_x_values = [

                        point[0]

                        for point in primary_points

                    ]


                    primary_y_values = [

                        point[1]

                        for point in primary_points

                    ]


                    master_x_anchors.extend(
                        [
                            min(
                                primary_x_values
                            ),
                            max(
                                primary_x_values
                            )
                        ]
                    )


                    master_y_anchors.extend(
                        [
                            min(
                                primary_y_values
                            ),
                            max(
                                primary_y_values
                            )
                        ]
                    )


        # ==================================================
        # ALL FLOOR SUPPORT DOMAINS -> BOUNDARY EVIDENCE
        # ==================================================

        for support_domain in anchors.get(
            "support_domains",
            []
        ):

            if not isinstance(
                support_domain,
                dict
            ):

                continue


            source_polygon = support_domain.get(
                "source_polygon"
            )


            if not isinstance(
                source_polygon,
                list
            ):

                continue


            valid_points = []


            for point in source_polygon:

                if (
                    not isinstance(
                        point,
                        (list, tuple)
                    )
                    or
                    len(
                        point
                    ) < 2
                ):

                    continue


                try:

                    point_x = float(
                        point[0]
                    )

                    point_y = float(
                        point[1]
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue


                valid_points.append(
                    [
                        point_x,
                        point_y
                    ]
                )


            if len(
                valid_points
            ) < 3:

                continue


            domain_x_values = [

                point[0]

                for point in valid_points

            ]


            domain_y_values = [

                point[1]

                for point in valid_points

            ]


            floor_boundary_evidence.append(
                {
                    "floor":
                        support_domain.get(
                            "floor"
                        ),

                    "min_x":
                        min(
                            domain_x_values
                        ),

                    "max_x":
                        max(
                            domain_x_values
                        ),

                    "min_y":
                        min(
                            domain_y_values
                        ),

                    "max_y":
                        max(
                            domain_y_values
                        ),

                    "source_polygon":
                        [
                            list(
                                point
                            )
                            for point in valid_points
                        ],

                    "geometry_type":
                        support_domain.get(
                            "geometry_type"
                        ),

                    "coordinate_mode":
                        "architectural_metric_floor_local",

                    "reason":
                        (
                            "floor_support_boundary_not_"
                            "automatic_structural_axis"
                        )
                }
            )


        anchors[
            "master_x_anchors"
        ] = sorted(
            list(
                set(
                    master_x_anchors
                )
            )
        )


        anchors[
            "master_y_anchors"
        ] = sorted(
            list(
                set(
                    master_y_anchors
                )
            )
        )


        anchors[
            "floor_boundary_evidence"
        ] = floor_boundary_evidence


        anchors[
            "multi_floor_axis_evidence"
        ] = {

            "master_x_anchors":
                list(
                    anchors[
                        "master_x_anchors"
                    ]
                ),

            "master_y_anchors":
                list(
                    anchors[
                        "master_y_anchors"
                    ]
                ),

            "floor_boundary_evidence":
                [
                    dict(
                        evidence
                    )
                    for evidence in floor_boundary_evidence
                ],

            "support_domain_count":
                len(
                    anchors.get(
                        "support_domains",
                        []
                    )
                ),

            "coordinate_mode":
                "architectural_metric_floor_local",

            "mode":
                "master_grid_with_floor_boundary_masks"

        }


        # ----------------------------------
        # BUILDING BOUNDARY
        #
        # Legacy rectangular boundary must
        # not contaminate Architecture-First
        # structural axis reasoning.
        #
        # When resolved architectural support
        # domains exist, their source polygons
        # are authoritative.
        # ----------------------------------

        architecture_first = bool(
            architectural_model.get(
                "architecture_first",
                False
            )
        )


        if not architecture_first:

            anchors["x_anchors"].extend(
                [
                    0,
                    width
                ]
            )

            anchors["y_anchors"].extend(
                [
                    0,
                    depth
                ]
            )


        # ==================================================
        # LEGACY SPACE BASED ANCHORS
        #
        # Existing structural behavior remains available.
        # ==================================================

        for space in spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            bounds = space.get(
                "bounds",
                []
            )


            if not isinstance(
                bounds,
                (list, tuple)
            ):

                continue


            if len(
                bounds
            ) != 4:

                continue


            try:

                x = float(
                    bounds[0]
                )

                y = float(
                    bounds[1]
                )

                w = float(
                    bounds[2]
                )

                h = float(
                    bounds[3]
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            normalized_bounds = [
                x,
                y,
                w,
                h
            ]


            anchors[
                "x_anchors"
            ].extend(
                [
                    x,
                    x + w
                ]
            )


            anchors[
                "y_anchors"
            ].extend(
                [
                    y,
                    y + h
                ]
            )


            space_type = space.get(
                "type"
            )


            # ==============================================
            # LEGACY CORE PROTECTION
            # ==============================================

            if space_type in [

                "stairs",
                "elevator",
                "duct"

            ]:

                anchors[
                    "core_zones"
                ].append(
                    {
                        "type":
                            space_type,

                        "name":
                            space.get(
                                "name"
                            ),

                        "floor":
                            space.get(
                                "level",
                                space.get(
                                    "floor"
                                )
                            ),

                        "bounds":
                            normalized_bounds,

                        "geometry_type":
                            "axis_aligned_rectangle",

                        "coordinate_mode":
                            "legacy_structural",

                        "allow_column":
                            False,

                        "allow_beam":
                            False,

                        "source":
                            "legacy_structural_space"
                    }
                )


                anchors[
                    "structural_hints"
                ].append(
                    {
                        "type":
                            "avoid_structure",

                        "source":
                            space.get(
                                "name"
                            ),

                        "floor":
                            space.get(
                                "level",
                                space.get(
                                    "floor"
                                )
                            ),

                        "bounds":
                            normalized_bounds,

                        "coordinate_mode":
                            "legacy_structural",

                        "reason":
                            "legacy_protected_core"
                    }
                )


        # ==================================================
        # ARCHITECTURE-FIRST POLYGON ANCHORS
        #
        # ArchitecturalGeometry supplies the authoritative
        # parcel-local room footprint.
        #
        # IMPORTANT:
        #
        # A rotated polygon must NOT be decomposed into
        # independent X and Y anchors.
        #
        # Doing that would generate a Cartesian grid from
        # the polygon bounding box and destroy the original
        # rigid-transform orientation.
        #
        # Therefore real polygons are preserved separately
        # for the future Structural Support Domain.
        # ==================================================

        for architectural_space in architectural_spaces:

            if not isinstance(
                architectural_space,
                dict
            ):

                continue


            footprint = architectural_space.get(
                "footprint"
            )


            if not isinstance(
                footprint,
                dict
            ):

                continue


            points = footprint.get(
                "points"
            )


            if (
                not isinstance(
                    points,
                    list
                )
                or
                len(
                    points
                ) < 3
            ):

                continue


            polygon = []


            for point in points:

                if (
                    not isinstance(
                        point,
                        (list, tuple)
                    )
                    or
                    len(
                        point
                    ) < 2
                ):

                    continue


                try:

                    point_x = float(
                        point[0]
                    )

                    point_y = float(
                        point[1]
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue


                polygon.append(
                    [
                        point_x,
                        point_y
                    ]
                )


            if len(
                polygon
            ) < 3:

                continue


            # ==============================================
            # POLYGON BOUNDS
            #
            # Bounds are metadata / compatibility only.
            # Polygon remains authoritative.
            # ==============================================

            polygon_x_values = [

                point[0]

                for point in polygon

            ]


            polygon_y_values = [

                point[1]

                for point in polygon

            ]


            min_x = min(
                polygon_x_values
            )

            min_y = min(
                polygon_y_values
            )

            max_x = max(
                polygon_x_values
            )

            max_y = max(
                polygon_y_values
            )


            polygon_bounds = [

                min_x,

                min_y,

                max_x - min_x,

                max_y - min_y

            ]


            protected_zone = bool(
                architectural_space.get(
                    "protected_zone",
                    False
                )
            )


            polygon_contract = {

                "name":
                    architectural_space.get(
                        "name"
                    ),

                "floor":
                    architectural_space.get(
                        "floor"
                    ),

                "type":
                    architectural_space.get(
                        "type"
                    ),

                "polygon":
                    polygon,

                "bounds":
                    polygon_bounds,

                "geometry_type":
                    footprint.get(
                        "type",
                        "polygon"
                    ),

                "geometry_status":
                    architectural_space.get(
                        "geometry_status"
                    ),

                "coordinate_mode":
                    footprint.get(
                        "coordinate_mode",
                        architectural_space.get(
                            "coordinate_mode"
                        )
                    ),

                "protected_zone":
                    protected_zone,

                "placement_scope":
                    architectural_space.get(
                        "placement_scope"
                    ),

                "access_requirement":
                    architectural_space.get(
                        "access_requirement"
                    ),

                "source":
                    "architectural_geometry"

            }


            anchors[
                "architectural_space_polygons"
            ].append(
                polygon_contract
            )


            # ==============================================
            # ARCHITECTURE-FIRST PROTECTED CORE
            #
            # Protected status comes directly from the
            # architectural semantic contract.
            #
            # No type guessing is performed here.
            # ==============================================

            if protected_zone:

                anchors[
                    "core_zones"
                ].append(
                    {
                        **polygon_contract,

                        "allow_column":
                            False,

                        "allow_beam":
                            False,

                        "source":
                            "architectural_geometry_protected_zone"
                    }
                )


                anchors[
                    "structural_hints"
                ].append(
                    {
                        "type":
                            "avoid_structure",

                        "source":
                            architectural_space.get(
                                "name"
                            ),

                        "floor":
                            architectural_space.get(
                                "floor"
                            ),

                        "polygon":
                            polygon,

                        "bounds":
                            polygon_bounds,

                        "geometry_type":
                            footprint.get(
                                "type",
                                "polygon"
                            ),

                        "coordinate_mode":
                            footprint.get(
                                "coordinate_mode",
                                architectural_space.get(
                                    "coordinate_mode"
                                )
                            ),

                        "reason":
                            "architectural_protected_zone"
                    }
                )


        # ==================================================
        # ARCHITECTURE-FIRST ANCHOR OWNERSHIP
        #
        # If resolved architectural support domains exist,
        # remove legacy rectangular building-boundary
        # anchors and rebuild the structural anchor set from
        # architectural source-frame evidence only.
        # ==================================================

        architecture_first = bool(
            architectural_model.get(
                "architecture_first",
                False
            )
        )


        support_domains = anchors.get(
            "support_domains",
            []
        )


        if (
            architecture_first
            and isinstance(
                support_domains,
                list
            )
            and support_domains
        ):

            master_x = anchors.get(
                "master_x_anchors",
                []
            )


            master_y = anchors.get(
                "master_y_anchors",
                []
            )


            if isinstance(
                master_x,
                list
            ):

                anchors[
                    "x_anchors"
                ] = list(
                    master_x
                )


            if isinstance(
                master_y,
                list
            ):

                anchors[
                    "y_anchors"
                ] = list(
                    master_y
                )


            anchors[
                "anchor_ownership"
            ] = (
                "architectural_support_domains"
            )


        # ==================================================
        # CLEAN LEGACY AXIS DUPLICATES
        #
        # Polygon geometry is intentionally untouched.
        # ==================================================

        anchors[
            "x_anchors"
        ] = sorted(
            list(
                set(
                    anchors[
                        "x_anchors"
                    ]
                )
            )
        )


        anchors[
            "y_anchors"
        ] = sorted(
            list(
                set(
                    anchors[
                        "y_anchors"
                    ]
                )
            )
        )


        return anchors