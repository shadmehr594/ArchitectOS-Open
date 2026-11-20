print(
    "USING structural_column_placement_engine.py StructuralColumnPlacementEngine"
)


class StructuralColumnPlacementEngine:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Structural Column Placement Engine v1.0 ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def place(
        self,
        columns,
        architectural_model,
        protected_zones=None,
        constraints=None
    ):

        protected_zones = protected_zones or []

        constraints = constraints or {}


        building = architectural_model.get(
            "building",
            {}
        )


        if not isinstance(
            building,
            dict
        ):

            building = {}


        structural_domain = architectural_model.get(
            "structural_domain",
            {}
        )


        if not isinstance(
            structural_domain,
            dict
        ):

            structural_domain = {}


        architecture_first = bool(
            architectural_model.get(
                "architecture_first",
                False
            )
        )


        domain_resolved = (
            architecture_first
            and
            structural_domain.get(
                "status"
            ) == "resolved"
        )


        if domain_resolved:

            origin_x = float(
                structural_domain.get(
                    "origin_x",
                    0.0
                )
            )

            origin_y = float(
                structural_domain.get(
                    "origin_y",
                    0.0
                )
            )

            width = float(
                structural_domain.get(
                    "width",
                    0.0
                )
            )

            depth = float(
                structural_domain.get(
                    "depth",
                    0.0
                )
            )

        else:

            origin_x = 0.0

            origin_y = 0.0

            width = float(
                building.get(
                    "width",
                    0
                )
            )

            depth = float(
                building.get(
                    "depth",
                    0
                )
            )


        placed = []

        rejected = []


        for column in columns:

            result = self._place_column(
                column,
                origin_x,
                origin_y,
                width,
                depth,
                protected_zones,
                constraints
            )


            if result.get(
                "status"
            ) == "rejected":

                rejected.append(
                    result
                )

                continue


            placed.append(
                result
            )


        return {

            "version":
                self.VERSION,

            "columns":
                placed,

            "rejected_columns":
                rejected,

            "placed_count":
                len(placed),

            "rejected_count":
                len(rejected),

            "reason":
                "architecture_coordinated_column_placement"

        }


    # ==================================================
    # PLACE SINGLE COLUMN
    # ==================================================

    def _place_column(
        self,
        column,
        origin_x,
        origin_y,
        width,
        depth,
        protected_zones,
        constraints
    ):

        placed = dict(
            column
        )


        x = float(
            placed.get(
                "x",
                0
            )
        )


        y = float(
            placed.get(
                "y",
                0
            )
        )


        column_width = float(
            placed.get(
                "width",
                constraints.get(
                    "column_width",
                    0.30
                )
            )
        )


        column_depth = float(
            placed.get(
                "depth",
                constraints.get(
                    "column_depth",
                    0.30
                )
            )
        )


        original_x = x

        original_y = y


        # ==================================================
        # PROPERTY BOUNDARY COORDINATION
        # CORNER-BASED COORDINATES
        # ==================================================

        domain_min_x = origin_x

        domain_min_y = origin_y

        domain_max_x = (
            origin_x
            +
            width
        )

        domain_max_y = (
            origin_y
            +
            depth
        )


        if x < domain_min_x:

            x = domain_min_x


        if y < domain_min_y:

            y = domain_min_y


        if (
            x
            +
            column_width
            >
            domain_max_x
        ):

            x = max(
                domain_min_x,
                domain_max_x
                -
                column_width
            )


        if (
            y
            +
            column_depth
            >
            domain_max_y
        ):

            y = max(
                domain_min_y,
                domain_max_y
                -
                column_depth
            )


        placed["x"] = x

        placed["y"] = y

        placed["width"] = column_width

        placed["depth"] = column_depth

        placed["reference"] = "corner"


        # ==================================================
        # PROTECTED ZONE CHECK
        # ==================================================

        if self._column_intersects_protected_zone(
            placed,
            protected_zones
        ):

            shifted = self._try_shift_away_from_protected_zone(
                placed,
                origin_x,
                origin_y,
                width,
                depth,
                protected_zones
            )


            if shifted is None:

                return {

                    **placed,

                    "status":
                        "rejected",

                    "placement_reason":
                        "protected_zone_conflict_unresolved"

                }


            placed = shifted


        moved = (

            round(
                original_x,
                6
            )
            !=
            round(
                placed["x"],
                6
            )

            or

            round(
                original_y,
                6
            )
            !=
            round(
                placed["y"],
                6
            )

        )


        placed["status"] = "placed"


        if moved:

            placed[
                "placement_reason"
            ] = "shifted_inside_architectural_boundary"

        else:

            placed[
                "placement_reason"
            ] = "original_position_valid"


        return placed


    # ==================================================
    # PROTECTED ZONE INTERSECTION
    # POLYGON-AWARE v1.1
    # ==================================================

    def _column_intersects_protected_zone(
        self,
        column,
        protected_zones
    ):

        cx1 = float(
            column["x"]
        )

        cy1 = float(
            column["y"]
        )

        cx2 = (
            cx1
            +
            float(
                column["width"]
            )
        )

        cy2 = (
            cy1
            +
            float(
                column["depth"]
            )
        )


        column_polygon = [

            [cx1, cy1],

            [cx2, cy1],

            [cx2, cy2],

            [cx1, cy2]

        ]


        for zone in protected_zones:

            if not isinstance(
                zone,
                dict
            ):

                continue


            if zone.get(
                "allow_column",
                False
            ):

                continue


            # ==============================================
            # SOURCE-FRAME PROTECTED GEOMETRY
            #
            # Structural columns are evaluated in the
            # architectural building-local frame.
            #
            # Therefore:
            #
            # source_polygon / source_bounds
            #     = authoritative structural geometry
            #
            # polygon / bounds
            #     = resolved parcel-local geometry
            #
            # Never mix the two coordinate frames.
            # ==============================================

            source_polygon = zone.get(
                "source_polygon"
            )


            if (
                isinstance(
                    source_polygon,
                    list
                )
                and
                len(
                    source_polygon
                ) >= 3
            ):

                polygon = source_polygon

            else:

                polygon = zone.get(
                    "polygon"
                )


            # ==============================================
            # POLYGON-AWARE INTERSECTION
            # ==============================================

            if (
                isinstance(
                    polygon,
                    list
                )
                and
                len(
                    polygon
                ) >= 3
            ):

                valid_polygon = []


                for point in polygon:

                    if (
                        isinstance(
                            point,
                            (list, tuple)
                        )
                        and
                        len(
                            point
                        ) >= 2
                    ):

                        try:

                            valid_polygon.append(
                                [
                                    float(
                                        point[0]
                                    ),
                                    float(
                                        point[1]
                                    )
                                ]
                            )

                        except (
                            TypeError,
                            ValueError
                        ):

                            pass


                if len(
                    valid_polygon
                ) >= 3:

                    # --------------------------------------
                    # 1. Any column corner inside zone
                    # --------------------------------------

                    for column_point in column_polygon:

                        if self._point_in_polygon(
                            column_point,
                            valid_polygon
                        ):

                            return True


                    # --------------------------------------
                    # 2. Any protected-zone vertex inside
                    #    the column rectangle
                    # --------------------------------------

                    for zone_point in valid_polygon:

                        if (

                            cx1
                            <=
                            zone_point[0]
                            <=
                            cx2

                            and

                            cy1
                            <=
                            zone_point[1]
                            <=
                            cy2

                        ):

                            return True


                    # --------------------------------------
                    # 3. Edge / edge intersection
                    # --------------------------------------

                    column_edges = [

                        (
                            column_polygon[0],
                            column_polygon[1]
                        ),

                        (
                            column_polygon[1],
                            column_polygon[2]
                        ),

                        (
                            column_polygon[2],
                            column_polygon[3]
                        ),

                        (
                            column_polygon[3],
                            column_polygon[0]
                        )

                    ]


                    for zone_index in range(
                        len(
                            valid_polygon
                        )
                    ):

                        zone_start = valid_polygon[
                            zone_index
                        ]

                        zone_end = valid_polygon[
                            (
                                zone_index
                                +
                                1
                            )
                            %
                            len(
                                valid_polygon
                            )
                        ]


                        for (
                            column_start,
                            column_end
                        ) in column_edges:

                            if self._segments_intersect(
                                column_start,
                                column_end,
                                zone_start,
                                zone_end
                            ):

                                return True


                    # Polygon existed and there was no
                    # intersection. Do NOT fall through to
                    # its larger bounding box.
                    continue


            # ==============================================
            # LEGACY BOUNDS FALLBACK
            # ==============================================

            source_bounds = zone.get(
                "source_bounds"
            )


            if (
                isinstance(
                    source_bounds,
                    (list, tuple)
                )
                and
                len(
                    source_bounds
                )
                == 4
            ):

                bounds = source_bounds

            else:

                bounds = zone.get(
                    "bounds",
                    []
                )


            if (
                not isinstance(
                    bounds,
                    (list, tuple)
                )
                or
                len(
                    bounds
                ) != 4
            ):

                continue


            try:

                zx = float(
                    bounds[0]
                )

                zy = float(
                    bounds[1]
                )

                zw = float(
                    bounds[2]
                )

                zh = float(
                    bounds[3]
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            zx2 = (
                zx
                +
                zw
            )

            zy2 = (
                zy
                +
                zh
            )


            intersects = not (

                cx2 <= zx

                or

                cx1 >= zx2

                or

                cy2 <= zy

                or

                cy1 >= zy2

            )


            if intersects:

                return True


        return False

    # ==================================================
    # POINT IN POLYGON
    # ==================================================

    def _point_in_polygon(
        self,
        point,
        polygon
    ):

        x = float(
            point[0]
        )

        y = float(
            point[1]
        )


        inside = False


        for index in range(
            len(
                polygon
            )
        ):

            point_a = polygon[
                index
            ]

            point_b = polygon[
                (
                    index
                    +
                    1
                )
                %
                len(
                    polygon
                )
            ]


            ax = float(
                point_a[0]
            )

            ay = float(
                point_a[1]
            )

            bx = float(
                point_b[0]
            )

            by = float(
                point_b[1]
            )


            if self._point_on_segment(
                [x, y],
                [ax, ay],
                [bx, by]
            ):

                return True


            crosses = (

                (
                    ay > y
                )
                !=
                (
                    by > y
                )
            )


            if not crosses:

                continue


            denominator = (
                by
                -
                ay
            )


            if abs(
                denominator
            ) <= 1e-12:

                continue


            intersection_x = (

                (
                    bx
                    -
                    ax
                )
                *
                (
                    y
                    -
                    ay
                )
                /
                denominator
                +
                ax

            )


            if x < intersection_x:

                inside = not inside


        return inside


    # ==================================================
    # SEGMENT INTERSECTION
    # ==================================================

    def _segments_intersect(
        self,
        a,
        b,
        c,
        d
    ):

        tolerance = 1e-9


        def orientation(
            p,
            q,
            r
        ):

            return (

                (
                    q[1]
                    -
                    p[1]
                )
                *
                (
                    r[0]
                    -
                    q[0]
                )

                -

                (
                    q[0]
                    -
                    p[0]
                )
                *
                (
                    r[1]
                    -
                    q[1]
                )

            )


        o1 = orientation(
            a,
            b,
            c
        )

        o2 = orientation(
            a,
            b,
            d
        )

        o3 = orientation(
            c,
            d,
            a
        )

        o4 = orientation(
            c,
            d,
            b
        )


        if (
            (
                o1 > tolerance
                and
                o2 < -tolerance
            )
            or
            (
                o1 < -tolerance
                and
                o2 > tolerance
            )
        ) and (
            (
                o3 > tolerance
                and
                o4 < -tolerance
            )
            or
            (
                o3 < -tolerance
                and
                o4 > tolerance
            )
        ):

            return True


        if (
            abs(
                o1
            )
            <=
            tolerance
            and
            self._point_on_segment(
                c,
                a,
                b
            )
        ):

            return True


        if (
            abs(
                o2
            )
            <=
            tolerance
            and
            self._point_on_segment(
                d,
                a,
                b
            )
        ):

            return True


        if (
            abs(
                o3
            )
            <=
            tolerance
            and
            self._point_on_segment(
                a,
                c,
                d
            )
        ):

            return True


        if (
            abs(
                o4
            )
            <=
            tolerance
            and
            self._point_on_segment(
                b,
                c,
                d
            )
        ):

            return True


        return False


    # ==================================================
    # POINT ON SEGMENT
    # ==================================================

    def _point_on_segment(
        self,
        point,
        start,
        end
    ):

        tolerance = 1e-9


        px = float(
            point[0]
        )

        py = float(
            point[1]
        )

        ax = float(
            start[0]
        )

        ay = float(
            start[1]
        )

        bx = float(
            end[0]
        )

        by = float(
            end[1]
        )


        cross = (

            (
                px
                -
                ax
            )
            *
            (
                by
                -
                ay
            )

            -

            (
                py
                -
                ay
            )
            *
            (
                bx
                -
                ax
            )

        )


        if abs(
            cross
        ) > tolerance:

            return False


        return (

            min(
                ax,
                bx
            )
            -
            tolerance
            <=
            px
            <=
            max(
                ax,
                bx
            )
            +
            tolerance

            and

            min(
                ay,
                by
            )
            -
            tolerance
            <=
            py
            <=
            max(
                ay,
                by
            )
            +
            tolerance

        )


    # ==================================================
    # SHIFT AWAY FROM PROTECTED ZONE
    # ==================================================

    def _try_shift_away_from_protected_zone(
        self,
        column,
        origin_x,
        origin_y,
        width,
        depth,
        protected_zones
    ):

        step_x = column[
            "width"
        ]

        step_y = column[
            "depth"
        ]


        candidates = [

            (
                column["x"] - step_x,
                column["y"]
            ),

            (
                column["x"] + step_x,
                column["y"]
            ),

            (
                column["x"],
                column["y"] - step_y
            ),

            (
                column["x"],
                column["y"] + step_y
            )

        ]


        for x, y in candidates:

            candidate = dict(
                column
            )


            candidate["x"] = x

            candidate["y"] = y


            if not self._inside_property_boundary(
                candidate,
                origin_x,
                origin_y,
                width,
                depth
            ):

                continue


            if self._column_intersects_protected_zone(
                candidate,
                protected_zones
            ):

                continue


            candidate[
                "placement_reason"
            ] = "shifted_away_from_protected_zone"


            return candidate


        return None


    # ==================================================
    # PROPERTY BOUNDARY
    # ==================================================

    def _inside_property_boundary(
        self,
        column,
        origin_x,
        origin_y,
        width,
        depth
    ):

        x = float(
            column[
                "x"
            ]
        )

        y = float(
            column[
                "y"
            ]
        )

        w = float(
            column[
                "width"
            ]
        )

        d = float(
            column[
                "depth"
            ]
        )


        min_x = float(
            origin_x
        )

        min_y = float(
            origin_y
        )

        max_x = (
            min_x
            +
            float(
                width
            )
        )

        max_y = (
            min_y
            +
            float(
                depth
            )
        )


        return (

            x >= min_x

            and

            y >= min_y

            and

            x + w <= max_x

            and

            y + d <= max_y

        )