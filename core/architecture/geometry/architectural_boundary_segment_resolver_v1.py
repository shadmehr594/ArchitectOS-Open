class ArchitecturalBoundarySegmentResolverV1:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧱 ARCHITECTURAL BOUNDARY SEGMENT RESOLVER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        spaces
    ):

        if not isinstance(
            spaces,
            list
        ):

            return []


        tolerance = 1e-9


        # ==================================================
        # VALID ROOM POLYGON FOOTPRINTS v1.1
        #
        # Authoritative room boundary geometry comes from:
        #
        # footprint["points"]
        #
        # Bounding-box values such as min_x / max_x are
        # intentionally not used for wall reconstruction.
        #
        # Supports:
        # - axis-aligned rectangles
        # - rotated rectangles
        # - future polygonal room footprints
        # ==================================================

        rooms = []


        for space in spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            footprint = space.get(
                "footprint"
            )


            if not isinstance(
                footprint,
                dict
            ):

                continue


            geometry_status = footprint.get(
                "geometry_status"
            )


            if geometry_status not in [

                "resolved_room_footprint",

                "resolved_rotated_room_footprint"

            ]:

                continue


            points = footprint.get(
                "points",
                []
            )


            if not (
                isinstance(
                    points,
                    list
                )
                and len(
                    points
                ) >= 3
            ):

                continue


            normalized_points = []


            for point in points:

                if not (
                    isinstance(
                        point,
                        (list, tuple)
                    )
                    and len(
                        point
                    ) >= 2
                ):

                    normalized_points = []

                    break


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

                    normalized_points = []

                    break


                normalized_points.append(
                    [
                        point_x,
                        point_y
                    ]
                )


            if len(
                normalized_points
            ) < 3:

                continue


            rooms.append(
                {

                    "name":
                        space.get(
                            "name"
                        ),

                    "floor":
                        space.get(
                            "floor"
                        ),

                    "bottom":
                        space.get(
                            "bottom"
                        ),

                    "top":
                        space.get(
                            "top"
                        ),

                    "height":
                        space.get(
                            "height"
                        ),

                    "level_span_status":
                        space.get(
                            "level_span_status"
                        ),

                    "coordinate_mode":
                        footprint.get(
                            "coordinate_mode",
                            space.get(
                                "resolved_coordinate_mode"
                            )
                        ),

                    "points":
                        normalized_points

                }
            )


        # ==================================================
        # RAW POLYGON EDGES v1.1
        #
        # Every consecutive point pair creates a real
        # geometric edge.
        #
        # No horizontal / vertical assumption.
        # ==================================================

        room_edges = []


        for room in rooms:

            points = room.get(
                "points",
                []
            )


            point_count = len(
                points
            )


            for edge_index in range(
                point_count
            ):

                start_point = points[
                    edge_index
                ]

                end_point = points[
                    (
                        edge_index
                        +
                        1
                    )
                    %
                    point_count
                ]


                start_x = float(
                    start_point[0]
                )

                start_y = float(
                    start_point[1]
                )

                end_x = float(
                    end_point[0]
                )

                end_y = float(
                    end_point[1]
                )


                edge_dx = (
                    end_x
                    -
                    start_x
                )

                edge_dy = (
                    end_y
                    -
                    start_y
                )


                edge_length = (
                    edge_dx
                    *
                    edge_dx
                    +
                    edge_dy
                    *
                    edge_dy
                ) ** 0.5


                if edge_length <= tolerance:

                    continue


                unit_x = (
                    edge_dx
                    /
                    edge_length
                )

                unit_y = (
                    edge_dy
                    /
                    edge_length
                )


                room_edges.append(
                    {

                        "space":
                            room.get(
                                "name"
                            ),

                        "floor":
                            room.get(
                                "floor"
                            ),

                        "bottom":
                            room.get(
                                "bottom"
                            ),

                        "top":
                            room.get(
                                "top"
                            ),

                        "height":
                            room.get(
                                "height"
                            ),

                        "level_span_status":
                            room.get(
                                "level_span_status"
                            ),

                        "edge_index":
                            edge_index,

                        "start":
                            [
                                start_x,
                                start_y
                            ],

                        "end":
                            [
                                end_x,
                                end_y
                            ],

                        "length":
                            edge_length,

                        "unit_direction":
                            [
                                unit_x,
                                unit_y
                            ],

                        "coordinate_mode":
                            room.get(
                                "coordinate_mode"
                            )

                    }
                )


        # ==================================================
        # ARBITRARY-ANGLE EDGE SPLITTING +
        # SHARED BOUNDARY DETECTION v1.1
        #
        # Geometry is projected onto each edge's own local
        # one-dimensional axis.
        #
        # This permits shared boundaries at any angle.
        # ==================================================

        boundary_segments = []


        for edge in room_edges:

            edge_start = edge.get(
                "start"
            )

            edge_end = edge.get(
                "end"
            )

            edge_length = edge.get(
                "length"
            )

            edge_direction = edge.get(
                "unit_direction"
            )


            if not (
                isinstance(
                    edge_start,
                    list
                )
                and isinstance(
                    edge_end,
                    list
                )
                and isinstance(
                    edge_length,
                    (int, float)
                )
                and isinstance(
                    edge_direction,
                    list
                )
                and len(
                    edge_direction
                ) >= 2
            ):

                continue


            origin_x = float(
                edge_start[0]
            )

            origin_y = float(
                edge_start[1]
            )

            unit_x = float(
                edge_direction[0]
            )

            unit_y = float(
                edge_direction[1]
            )


            breakpoints = {
                0.0,
                float(
                    edge_length
                )
            }


            overlapping_edges = []


            for candidate in room_edges:

                if candidate is edge:

                    continue


                if candidate.get(
                    "floor"
                ) != edge.get(
                    "floor"
                ):

                    continue


                if candidate.get(
                    "space"
                ) == edge.get(
                    "space"
                ):

                    continue


                candidate_start = candidate.get(
                    "start"
                )

                candidate_end = candidate.get(
                    "end"
                )


                if not (
                    isinstance(
                        candidate_start,
                        list
                    )
                    and len(
                        candidate_start
                    ) >= 2
                    and isinstance(
                        candidate_end,
                        list
                    )
                    and len(
                        candidate_end
                    ) >= 2
                ):

                    continue


                candidate_start_x = float(
                    candidate_start[0]
                )

                candidate_start_y = float(
                    candidate_start[1]
                )

                candidate_end_x = float(
                    candidate_end[0]
                )

                candidate_end_y = float(
                    candidate_end[1]
                )


                # ------------------------------------------
                # COLLINEARITY TEST
                #
                # Distance from candidate endpoints to the
                # infinite line of the current edge.
                # ------------------------------------------

                start_relative_x = (
                    candidate_start_x
                    -
                    origin_x
                )

                start_relative_y = (
                    candidate_start_y
                    -
                    origin_y
                )

                end_relative_x = (
                    candidate_end_x
                    -
                    origin_x
                )

                end_relative_y = (
                    candidate_end_y
                    -
                    origin_y
                )


                start_cross = (
                    start_relative_x
                    *
                    unit_y
                    -
                    start_relative_y
                    *
                    unit_x
                )

                end_cross = (
                    end_relative_x
                    *
                    unit_y
                    -
                    end_relative_y
                    *
                    unit_x
                )


                if (
                    abs(
                        start_cross
                    ) > tolerance
                    or
                    abs(
                        end_cross
                    ) > tolerance
                ):

                    continue


                # ------------------------------------------
                # PROJECT CANDIDATE ONTO CURRENT EDGE AXIS
                # ------------------------------------------

                candidate_start_t = (
                    start_relative_x
                    *
                    unit_x
                    +
                    start_relative_y
                    *
                    unit_y
                )

                candidate_end_t = (
                    end_relative_x
                    *
                    unit_x
                    +
                    end_relative_y
                    *
                    unit_y
                )


                candidate_min_t = min(
                    candidate_start_t,
                    candidate_end_t
                )

                candidate_max_t = max(
                    candidate_start_t,
                    candidate_end_t
                )


                overlap_start = max(
                    0.0,
                    candidate_min_t
                )

                overlap_end = min(
                    float(
                        edge_length
                    ),
                    candidate_max_t
                )


                if (
                    overlap_end
                    -
                    overlap_start
                    <= tolerance
                ):

                    continue


                overlapping_edges.append(
                    {

                        "edge":
                            candidate,

                        "start_t":
                            overlap_start,

                        "end_t":
                            overlap_end

                    }
                )


                breakpoints.add(
                    overlap_start
                )

                breakpoints.add(
                    overlap_end
                )


            sorted_breakpoints = sorted(
                breakpoints
            )


            for segment_index in range(
                len(
                    sorted_breakpoints
                )
                -
                1
            ):

                segment_start_t = (
                    sorted_breakpoints[
                        segment_index
                    ]
                )

                segment_end_t = (
                    sorted_breakpoints[
                        segment_index + 1
                    ]
                )


                segment_length = (
                    segment_end_t
                    -
                    segment_start_t
                )


                if segment_length <= tolerance:

                    continue


                midpoint_t = (
                    segment_start_t
                    +
                    segment_end_t
                ) / 2.0


                adjacent_spaces = []


                for overlap in overlapping_edges:

                    if (
                        overlap.get(
                            "start_t",
                            0.0
                        )
                        -
                        tolerance
                        <=
                        midpoint_t
                        <=
                        overlap.get(
                            "end_t",
                            0.0
                        )
                        +
                        tolerance
                    ):

                        candidate_edge = overlap.get(
                            "edge",
                            {}
                        )


                        candidate_space = (
                            candidate_edge.get(
                                "space"
                            )
                            if isinstance(
                                candidate_edge,
                                dict
                            )
                            else None
                        )


                        if (
                            candidate_space
                            and
                            candidate_space
                            not in adjacent_spaces
                        ):

                            adjacent_spaces.append(
                                candidate_space
                            )


                start_point = [

                    origin_x
                    +
                    unit_x
                    *
                    segment_start_t,

                    origin_y
                    +
                    unit_y
                    *
                    segment_start_t

                ]


                end_point = [

                    origin_x
                    +
                    unit_x
                    *
                    segment_end_t,

                    origin_y
                    +
                    unit_y
                    *
                    segment_end_t

                ]


                boundary_type = (
                    "shared"
                    if adjacent_spaces
                    else "exterior"
                )


                adjacent_space = (
                    adjacent_spaces[0]
                    if len(
                        adjacent_spaces
                    ) == 1
                    else None
                )


                boundary_segments.append(
                    {

                        "floor":
                            edge.get(
                                "floor"
                            ),

                        "bottom":
                            edge.get(
                                "bottom"
                            ),

                        "top":
                            edge.get(
                                "top"
                            ),

                        "height":
                            edge.get(
                                "height"
                            ),

                        "level_span_status":
                            edge.get(
                                "level_span_status"
                            ),

                        "space":
                            edge.get(
                                "space"
                            ),

                        "edge_index":
                            edge.get(
                                "edge_index"
                            ),

                        "orientation":
                            "arbitrary_angle",

                        "start":
                            start_point,

                        "end":
                            end_point,

                        "length":
                            segment_length,

                        "boundary_type":
                            boundary_type,

                        "adjacent_space":
                            adjacent_space,

                        "adjacent_spaces":
                            adjacent_spaces,

                        "coordinate_mode":
                            edge.get(
                                "coordinate_mode"
                            ),

                        "geometry_status":
                            "resolved_boundary_segment",

                        "source":
                            "resolved_room_polygon_footprints"

                    }
                )


        # ==================================================
        # STABLE SEGMENT IDS
        # ==================================================

        floor_counters = {}


        for segment in boundary_segments:

            floor = segment.get(
                "floor",
                "UNKNOWN"
            )


            floor_counters.setdefault(
                floor,
                0
            )


            floor_counters[
                floor
            ] += 1


            segment[
                "boundary_id"
            ] = (
                f"{floor}-B"
                f"{floor_counters[floor]:03d}"
            )


        return boundary_segments
