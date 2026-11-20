print(
    "USING structural_point_selection_engine.py StructuralPointSelectionEngine"
)


class StructuralPointSelectionEngine:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Structural Point Selection Engine v1.0 ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def select(
        self,
        candidate_points,
        architectural_model=None,
        protected_zones=None,
        constraints=None
    ):

        architectural_model = architectural_model or {}

        protected_zones = protected_zones or []

        constraints = constraints or {}


        max_span = constraints.get(
            "max_span",
            8.0
        )


        points = self._normalize_points(
            candidate_points
        )


        points = self._remove_protected_points(
            points,
            protected_zones
        )


        if not points:

            return {

                "version":
                    self.VERSION,

                "selected_points":
                    [],

                "removed_points":
                    [],

                "reason":
                    "no_valid_candidate_points"

            }


        rows = self._group_rows(
            points
        )


        selected = []

        removed = []


        for row_y, row_points in rows.items():

            row_points = sorted(
                row_points,
                key=lambda item: item["x"]
            )


            row_selected = self._select_row_points(
                row_points,
                max_span
            )


            selected_keys = {

                self._point_key(point)

                for point in row_selected

            }


            for point in row_points:

                if self._point_key(point) in selected_keys:

                    selected.append(
                        point
                    )

                else:

                    removed.append(
                        {

                            **point,

                            "selection_reason":
                                "redundant_row_intersection"

                        }
                    )


        selected = self._restore_critical_points(
            selected,
            points,
            architectural_model,
            protected_zones
        )


        selected = self._deduplicate(
            selected
        )


        selected = sorted(
            selected,
            key=lambda point: (
                point["y"],
                point["x"]
            )
        )


        return {

            "version":
                self.VERSION,

            "selected_points":
                selected,

            "removed_points":
                removed,

            "candidate_count":
                len(points),

            "selected_count":
                len(selected),

            "reason":
                "adaptive_irregular_structural_point_selection"

        }


    # ==================================================
    # ROW SELECTION
    # ==================================================

    def _select_row_points(
        self,
        row_points,
        max_span
    ):

        if len(row_points) <= 2:

            return list(
                row_points
            )


        selected = [
            row_points[0]
        ]


        last_selected = row_points[0]


        for index in range(
            1,
            len(row_points) - 1
        ):

            current = row_points[index]

            next_point = row_points[index + 1]


            span_if_skipped = (
                next_point["x"]
                -
                last_selected["x"]
            )


            if span_if_skipped > max_span:

                selected.append(
                    current
                )

                last_selected = current


        selected.append(
            row_points[-1]
        )


        return selected


    # ==================================================
    # CRITICAL ARCHITECTURAL POINTS
    # ==================================================

    def _restore_critical_points(
        self,
        selected,
        all_points,
        architectural_model,
        protected_zones
    ):

        building = architectural_model.get(
            "building",
            {}
        )


        width = building.get(
            "width"
        )

        depth = building.get(
            "depth"
        )

        origin_x = building.get(
            "origin_x",
            0.0
        )


        origin_y = building.get(
            "origin_y",
            0.0
        )


        try:

            origin_x = float(
                origin_x
            )

            origin_y = float(
                origin_y
            )

        except (
            TypeError,
            ValueError
        ):

            origin_x = 0.0
            origin_y = 0.0


        if width is None or depth is None:

            return selected


        min_x = origin_x

        min_y = origin_y

        max_x = (
            origin_x
            +
            float(
                width
            )
        )

        max_y = (
            origin_y
            +
            float(
                depth
            )
        )


        critical_coordinates = [

            (
                round(
                    min_x,
                    3
                ),
                round(
                    min_y,
                    3
                )
            ),

            (
                round(
                    max_x,
                    3
                ),
                round(
                    min_y,
                    3
                )
            ),

            (
                round(
                    min_x,
                    3
                ),
                round(
                    max_y,
                    3
                )
            ),

            (
                round(
                    max_x,
                    3
                ),
                round(
                    max_y,
                    3
                )
            )

        ]


        existing_keys = {

            self._point_key(point)

            for point in selected

        }


        for point in all_points:

            key = self._point_key(
                point
            )


            if key not in critical_coordinates:

                continue


            if key in existing_keys:

                continue


            if self._inside_protected_zone(
                point,
                protected_zones
            ):

                continue


            restored = dict(
                point
            )


            restored[
                "selection_reason"
            ] = "critical_building_corner"


            selected.append(
                restored
            )


            existing_keys.add(
                key
            )


        return selected


    # ==================================================
    # PROTECTED ZONES
    # ==================================================

    def _remove_protected_points(
        self,
        points,
        protected_zones
    ):

        result = []


        for point in points:

            if self._inside_protected_zone(
                point,
                protected_zones
            ):

                continue


            result.append(
                point
            )


        return result


    def _inside_protected_zone(
        self,
        point,
        protected_zones
    ):

        x = float(
            point.get(
                "x",
                0
            )
        )

        y = float(
            point.get(
                "y",
                0
            )
        )


        for zone in protected_zones:

            if zone.get(
                "allow_column",
                False
            ):

                continue


            # ==============================================
            # ARCHITECTURE-FIRST COORDINATE CONTRACT
            #
            # Structural point selection operates in the
            # architectural source / building-local frame.
            #
            # Therefore:
            #
            # 1. source_polygon is authoritative
            # 2. source_bounds is the source-frame fallback
            # 3. resolved parcel-local polygon / bounds are
            #    legacy fallbacks only when source geometry
            #    is unavailable
            #
            # Never compare building-local structural points
            # directly against parcel-local rotated geometry.
            # ==============================================

            source_polygon = zone.get(
                "source_polygon"
            )


            polygon = None


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

                legacy_polygon = zone.get(
                    "polygon"
                )


                if (
                    isinstance(
                        legacy_polygon,
                        list
                    )
                    and
                    len(
                        legacy_polygon
                    ) >= 3
                ):

                    polygon = legacy_polygon


            # ==============================================
            # POLYGON-AWARE PROTECTED ZONE
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

                if self._point_in_polygon(
                    x,
                    y,
                    polygon
                ):

                    return True


                # Polygon is authoritative.
                #
                # If a real polygon exists and the point is
                # outside it, do NOT fall through to its
                # bounding rectangle because that would
                # create false-positive protected regions.
                continue


            # ==============================================
            # SOURCE-FRAME BOUNDS FALLBACK
            # ==============================================

            bounds = zone.get(
                "source_bounds"
            )


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

                bounds = zone.get(
                    "bounds",
                    []
                )


            if len(
                bounds
            ) != 4:

                continue


            zx, zy, zw, zh = bounds


            zx = float(
                zx
            )

            zy = float(
                zy
            )

            zw = float(
                zw
            )

            zh = float(
                zh
            )


            if (
                zx <= x <= zx + zw
                and
                zy <= y <= zy + zh
            ):

                return True


        return False


    def _point_in_polygon(
        self,
        x,
        y,
        polygon
    ):

        inside = False

        point_count = len(
            polygon
        )


        for index in range(
            point_count
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
                point_count
            ]


            if (
                not isinstance(
                    point_a,
                    (list, tuple)
                )
                or
                not isinstance(
                    point_b,
                    (list, tuple)
                )
                or
                len(
                    point_a
                ) < 2
                or
                len(
                    point_b
                ) < 2
            ):

                continue


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


            # ----------------------------------------------
            # POINT ON SEGMENT
            #
            # Treat polygon boundary as protected.
            # ----------------------------------------------

            cross = (
                (
                    x
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
                    y
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
            ) <= 1e-9:

                dot = (
                    (
                        x
                        -
                        ax
                    )
                    *
                    (
                        x
                        -
                        bx
                    )
                    +
                    (
                        y
                        -
                        ay
                    )
                    *
                    (
                        y
                        -
                        by
                    )
                )


                if dot <= 1e-9:

                    return True


            if (
                (
                    ay > y
                )
                !=
                (
                    by > y
                )
            ):

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
                    (
                        by
                        -
                        ay
                    )
                    +
                    ax
                )


                if x < intersection_x:

                    inside = not inside


        return inside


    # ==================================================
    # ROW GROUPING
    # ==================================================

    def _group_rows(
        self,
        points
    ):

        rows = {}


        for point in points:

            y = round(
                float(
                    point.get(
                        "y",
                        0
                    )
                ),
                3
            )


            rows.setdefault(
                y,
                []
            ).append(
                point
            )


        return rows


    # ==================================================
    # NORMALIZATION
    # ==================================================

    def _normalize_points(
        self,
        points
    ):

        result = []


        for point in points:

            if not isinstance(
                point,
                dict
            ):

                continue


            if (
                "x" not in point
                or
                "y" not in point
            ):

                continue


            normalized = dict(
                point
            )


            normalized["x"] = float(
                normalized["x"]
            )

            normalized["y"] = float(
                normalized["y"]
            )


            normalized.setdefault(
                "reference",
                "corner"
            )


            result.append(
                normalized
            )


        return self._deduplicate(
            result
        )


    def _deduplicate(
        self,
        points
    ):

        result = []

        seen = set()


        for point in points:

            key = self._point_key(
                point
            )


            if key in seen:

                continue


            seen.add(
                key
            )

            result.append(
                point
            )


        return result


    def _point_key(
        self,
        point
    ):

        return (

            round(
                float(
                    point.get(
                        "x",
                        0
                    )
                ),
                3
            ),

            round(
                float(
                    point.get(
                        "y",
                        0
                    )
                ),
                3
            )

        )