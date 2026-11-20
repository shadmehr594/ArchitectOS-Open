import math


print(
    "USING adaptive_beam_reasoner.py AdaptiveBeamReasoner"
)


class AdaptiveBeamReasoner:


    VERSION = "1.1"


    def __init__(self):

        print(
            "🏗️ Adaptive Beam Reasoner v1.1 ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        columns,
        protected_zones=None,
        constraints=None
    ):

        protected_zones = protected_zones or []

        constraints = constraints or {}


        max_direct_span = constraints.get(
            "max_direct_span",
            None
        )


        columns = self._normalize_columns(
            columns
        )


        candidates = self._build_candidate_connections(
            columns
        )


        valid_candidates = []


        for beam in candidates:

            if self._segment_crosses_protected_zone(
                beam,
                protected_zones
            ):

                continue


            if (
                max_direct_span is not None
                and
                beam["length"] > max_direct_span
            ):

                beam[
                    "beam_type"
                ] = "long_span_candidate"


            valid_candidates.append(
                beam
            )


        selected = self._select_minimal_connections(
            columns,
            valid_candidates
        )


        for index, beam in enumerate(
            selected
        ):

            beam["id"] = beam.get(
                "id",
                f"B-{index + 1}"
            )


        return {

            "version":
                self.VERSION,

            "beams":
                selected,

            "candidate_count":
                len(candidates),

            "valid_candidate_count":
                len(valid_candidates),

            "beam_count":
                len(selected),

            "reason":
                "adaptive_column_based_beam_reasoning"

        }


    # ==================================================
    # NORMALIZE COLUMNS
    # ==================================================

    def _normalize_columns(
        self,
        columns
    ):

        result = []


        for index, column in enumerate(
            columns
        ):

            if not isinstance(
                column,
                dict
            ):

                continue


            if (
                "x" not in column
                or
                "y" not in column
            ):

                continue


            item = dict(
                column
            )


            item["x"] = float(
                item["x"]
            )

            item["y"] = float(
                item["y"]
            )


            item.setdefault(
                "id",
                f"C-{index + 1}"
            )


            item.setdefault(
                "reference",
                "corner"
            )


            result.append(
                item
            )


        return result


    # ==================================================
    # CANDIDATE CONNECTIONS
    # ==================================================

    def _build_candidate_connections(
        self,
        columns
    ):

        candidates = []


        for i in range(
            len(columns)
        ):

            for j in range(
                i + 1,
                len(columns)
            ):

                start = columns[i]

                end = columns[j]


                dx = (
                    end["x"]
                    -
                    start["x"]
                )

                dy = (
                    end["y"]
                    -
                    start["y"]
                )


                length = math.sqrt(
                    dx * dx
                    +
                    dy * dy
                )


                if length <= 0:

                    continue


                orientation = self._classify_orientation(
                    dx,
                    dy
                )


                candidates.append(
                    {
                        "start_column":
                            start["id"],

                        "end_column":
                            end["id"],

                        "start":
                            [
                                start["x"],
                                start["y"]
                            ],

                        "end":
                            [
                                end["x"],
                                end["y"]
                            ],

                        "length":
                            length,

                        "orientation":
                            orientation,

                        "beam_type":
                            "direct",

                        "reference":
                            "corner",

                        "coordinate_mode":
                            start.get(
                                "coordinate_mode",
                                "architectural_metric_floor_local"
                            ),

                        "reason":
                            "column_connectivity_candidate"
                    }
                )


        return candidates


    # ==================================================
    # ORIENTATION
    # ==================================================

    def _classify_orientation(
        self,
        dx,
        dy
    ):

        tolerance = 1e-6


        if abs(
            dy
        ) <= tolerance:

            return "x"


        if abs(
            dx
        ) <= tolerance:

            return "y"


        return "diagonal"


    # ==================================================
    # PROTECTED ZONE INTERSECTION
    #
    # ARCHITECTURE-FIRST FRAME RULE:
    #
    # Structural columns / beams are currently generated
    # in architectural_metric_floor_local coordinates.
    #
    # Therefore protected geometry must be checked in the
    # SAME source frame.
    #
    # Priority:
    #
    # 1. source_polygon
    # 2. source_bounds
    # 3. polygon       -> legacy / same-frame fallback
    # 4. bounds        -> legacy fallback
    #
    # parcel-local polygon must NOT override an available
    # source_polygon.
    # ==================================================

    def _segment_crosses_protected_zone(
        self,
        beam,
        protected_zones
    ):

        if not isinstance(
            beam,
            dict
        ):

            return False


        start = beam.get(
            "start"
        )

        end = beam.get(
            "end"
        )


        if not (
            isinstance(
                start,
                (list, tuple)
            )
            and
            len(
                start
            ) >= 2
            and
            isinstance(
                end,
                (list, tuple)
            )
            and
            len(
                end
            ) >= 2
        ):

            return False


        try:

            x1 = float(
                start[0]
            )

            y1 = float(
                start[1]
            )

            x2 = float(
                end[0]
            )

            y2 = float(
                end[1]
            )

        except (
            TypeError,
            ValueError
        ):

            return False


        for zone in protected_zones:

            if not isinstance(
                zone,
                dict
            ):

                continue


            if zone.get(
                "allow_beam",
                False
            ):

                continue


            # ==============================================
            # 1. SOURCE POLYGON
            # Authoritative Architecture-First geometry
            # ==============================================

            source_polygon = zone.get(
                "source_polygon"
            )


            if self._valid_polygon(
                source_polygon
            ):

                if self._segment_intersects_polygon(
                    x1,
                    y1,
                    x2,
                    y2,
                    source_polygon
                ):

                    return True


                # Source polygon exists and does not
                # intersect. Do NOT test parcel polygon
                # or its larger bounds afterward.
                continue


            # ==============================================
            # 2. SOURCE BOUNDS
            # Architecture-first rectangular fallback
            # ==============================================

            source_bounds = zone.get(
                "source_bounds"
            )


            if self._valid_bounds(
                source_bounds
            ):

                if self._segment_intersects_bounds(
                    x1,
                    y1,
                    x2,
                    y2,
                    source_bounds
                ):

                    return True


                continue


            # ==============================================
            # 3. POLYGON FALLBACK
            #
            # Used for legacy protected-zone contracts or
            # callers where polygon is already in the same
            # structural coordinate frame.
            # ==============================================

            polygon = zone.get(
                "polygon"
            )


            if self._valid_polygon(
                polygon
            ):

                if self._segment_intersects_polygon(
                    x1,
                    y1,
                    x2,
                    y2,
                    polygon
                ):

                    return True


                continue


            # ==============================================
            # 4. LEGACY BOUNDS FALLBACK
            # ==============================================

            bounds = zone.get(
                "bounds"
            )


            if self._valid_bounds(
                bounds
            ):

                if self._segment_intersects_bounds(
                    x1,
                    y1,
                    x2,
                    y2,
                    bounds
                ):

                    return True


        return False


    # ==================================================
    # POLYGON VALIDATION
    # ==================================================

    def _valid_polygon(
        self,
        polygon
    ):

        if not (
            isinstance(
                polygon,
                list
            )
            and
            len(
                polygon
            ) >= 3
        ):

            return False


        valid_count = 0


        for point in polygon:

            if not (
                isinstance(
                    point,
                    (list, tuple)
                )
                and
                len(
                    point
                ) >= 2
            ):

                continue


            try:

                float(
                    point[0]
                )

                float(
                    point[1]
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            valid_count += 1


        return valid_count >= 3


    # ==================================================
    # BOUNDS VALIDATION
    # ==================================================

    def _valid_bounds(
        self,
        bounds
    ):

        if not (
            isinstance(
                bounds,
                (list, tuple)
            )
            and
            len(
                bounds
            ) == 4
        ):

            return False


        try:

            float(
                bounds[0]
            )

            float(
                bounds[1]
            )

            float(
                bounds[2]
            )

            float(
                bounds[3]
            )

        except (
            TypeError,
            ValueError
        ):

            return False


        return True


    # ==================================================
    # SEGMENT / POLYGON
    # ==================================================

    def _segment_intersects_polygon(
        self,
        x1,
        y1,
        x2,
        y2,
        polygon
    ):

        valid_polygon = []


        for point in polygon:

            if not (
                isinstance(
                    point,
                    (list, tuple)
                )
                and
                len(
                    point
                ) >= 2
            ):

                continue


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

                continue


        if len(
            valid_polygon
        ) < 3:

            return False


        # ----------------------------------------------
        # Beam start or end inside protected polygon
        # ----------------------------------------------

        if self._point_in_polygon(
            x1,
            y1,
            valid_polygon
        ):

            return True


        if self._point_in_polygon(
            x2,
            y2,
            valid_polygon
        ):

            return True


        # ----------------------------------------------
        # Beam intersects any polygon boundary edge
        # ----------------------------------------------

        for index in range(
            len(
                valid_polygon
            )
        ):

            point_a = valid_polygon[
                index
            ]

            point_b = valid_polygon[
                (
                    index
                    +
                    1
                )
                %
                len(
                    valid_polygon
                )
            ]


            if self._segments_intersect(
                x1,
                y1,
                x2,
                y2,
                point_a[0],
                point_a[1],
                point_b[0],
                point_b[1]
            ):

                return True


        return False


    # ==================================================
    # POINT IN POLYGON
    # Boundary counts as protected.
    # ==================================================

    def _point_in_polygon(
        self,
        x,
        y,
        polygon
    ):

        inside = False

        count = len(
            polygon
        )


        if count < 3:

            return False


        for index in range(
            count
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
                count
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
                x,
                y,
                ax,
                ay,
                bx,
                by
            ):

                return True


            crosses = (

                (ay > y)
                !=
                (by > y)

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
            ) < 1e-12:

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
    # SEGMENT / BOUNDS
    # ==================================================

    def _segment_intersects_bounds(
        self,
        x1,
        y1,
        x2,
        y2,
        bounds
    ):

        try:

            rx1 = float(
                bounds[0]
            )

            ry1 = float(
                bounds[1]
            )

            width = float(
                bounds[2]
            )

            depth = float(
                bounds[3]
            )

        except (
            TypeError,
            ValueError
        ):

            return False


        rx2 = (
            rx1
            +
            width
        )

        ry2 = (
            ry1
            +
            depth
        )


        return self._segment_intersects_rectangle(
            x1,
            y1,
            x2,
            y2,
            rx1,
            ry1,
            rx2,
            ry2
        )


    # ==================================================
    # SEGMENT / RECTANGLE
    # ==================================================

    def _segment_intersects_rectangle(
        self,
        x1,
        y1,
        x2,
        y2,
        rx1,
        ry1,
        rx2,
        ry2
    ):

        if self._point_inside_rectangle(
            x1,
            y1,
            rx1,
            ry1,
            rx2,
            ry2
        ):

            return True


        if self._point_inside_rectangle(
            x2,
            y2,
            rx1,
            ry1,
            rx2,
            ry2
        ):

            return True


        edges = [

            (
                rx1,
                ry1,
                rx2,
                ry1
            ),

            (
                rx2,
                ry1,
                rx2,
                ry2
            ),

            (
                rx2,
                ry2,
                rx1,
                ry2
            ),

            (
                rx1,
                ry2,
                rx1,
                ry1
            )

        ]


        for ex1, ey1, ex2, ey2 in edges:

            if self._segments_intersect(
                x1,
                y1,
                x2,
                y2,
                ex1,
                ey1,
                ex2,
                ey2
            ):

                return True


        return False


    # ==================================================
    # POINT INSIDE RECTANGLE
    #
    # Boundary is considered protected.
    # ==================================================

    def _point_inside_rectangle(
        self,
        x,
        y,
        rx1,
        ry1,
        rx2,
        ry2
    ):

        tolerance = 1e-9


        return (

            rx1 - tolerance
            <=
            x
            <=
            rx2 + tolerance

            and

            ry1 - tolerance
            <=
            y
            <=
            ry2 + tolerance

        )


    # ==================================================
    # SEGMENT INTERSECTION
    #
    # Includes collinear / touching conditions.
    # ==================================================

    def _segments_intersect(
        self,
        ax,
        ay,
        bx,
        by,
        cx,
        cy,
        dx,
        dy
    ):

        tolerance = 1e-9


        def orientation(
            px,
            py,
            qx,
            qy,
            rx,
            ry
        ):

            value = (

                (
                    qy
                    -
                    py
                )
                *
                (
                    rx
                    -
                    qx
                )

                -

                (
                    qx
                    -
                    px
                )
                *
                (
                    ry
                    -
                    qy
                )

            )


            if abs(
                value
            ) <= tolerance:

                return 0


            return (
                1
                if value > 0
                else 2
            )


        o1 = orientation(
            ax,
            ay,
            bx,
            by,
            cx,
            cy
        )

        o2 = orientation(
            ax,
            ay,
            bx,
            by,
            dx,
            dy
        )

        o3 = orientation(
            cx,
            cy,
            dx,
            dy,
            ax,
            ay
        )

        o4 = orientation(
            cx,
            cy,
            dx,
            dy,
            bx,
            by
        )


        if (
            o1 != o2
            and
            o3 != o4
        ):

            return True


        if (
            o1 == 0
            and
            self._point_on_segment(
                cx,
                cy,
                ax,
                ay,
                bx,
                by
            )
        ):

            return True


        if (
            o2 == 0
            and
            self._point_on_segment(
                dx,
                dy,
                ax,
                ay,
                bx,
                by
            )
        ):

            return True


        if (
            o3 == 0
            and
            self._point_on_segment(
                ax,
                ay,
                cx,
                cy,
                dx,
                dy
            )
        ):

            return True


        if (
            o4 == 0
            and
            self._point_on_segment(
                bx,
                by,
                cx,
                cy,
                dx,
                dy
            )
        ):

            return True


        return False


    # ==================================================
    # POINT ON SEGMENT
    # ==================================================

    def _point_on_segment(
        self,
        px,
        py,
        ax,
        ay,
        bx,
        by
    ):

        tolerance = 1e-9


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
    # MINIMAL CONNECTIVITY
    # ==================================================

    def _select_minimal_connections(
        self,
        columns,
        candidates
    ):

        if len(
            columns
        ) <= 1:

            return []


        candidates = sorted(
            candidates,
            key=lambda beam: beam[
                "length"
            ]
        )


        parent = {

            column["id"]:
                column["id"]

            for column in columns

        }


        def find(
            item
        ):

            while parent[
                item
            ] != item:

                parent[
                    item
                ] = parent[
                    parent[
                        item
                    ]
                ]

                item = parent[
                    item
                ]


            return item


        def union(
            a,
            b
        ):

            root_a = find(
                a
            )

            root_b = find(
                b
            )


            if root_a == root_b:

                return False


            parent[
                root_b
            ] = root_a


            return True


        selected = []


        for beam in candidates:

            start_id = beam[
                "start_column"
            ]

            end_id = beam[
                "end_column"
            ]


            if union(
                start_id,
                end_id
            ):

                selected.append(
                    beam
                )


            if len(
                selected
            ) == len(
                columns
            ) - 1:

                break


        return selected