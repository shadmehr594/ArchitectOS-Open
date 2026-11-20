class ArchitecturalPhysicalWallResolverV1:

    VERSION = "1.0"

    COORDINATE_PRECISION = 8


    def __init__(self):

        print(
            f"🧱 ARCHITECTURAL PHYSICAL WALL RESOLVER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        boundary_segments,
        thicknesses=None
    ):

        thicknesses = thicknesses if isinstance(thicknesses, dict) else {}
        allowed = {0.10, 0.15, 0.20, 0.30, 0.35}

        def selected(key, default):
            value = thicknesses.get(key, default)
            try:
                value = round(float(value), 2)
            except (TypeError, ValueError):
                value = default
            return value if value in allowed else default

        if not isinstance(
            boundary_segments,
            list
        ):

            boundary_segments = []


        grouped_segments = {}


        for segment in boundary_segments:

            if not isinstance(
                segment,
                dict
            ):

                continue


            floor = segment.get(
                "floor"
            )


            start = segment.get(
                "start"
            )

            end = segment.get(
                "end"
            )


            if not self._valid_point(
                start
            ):

                continue


            if not self._valid_point(
                end
            ):

                continue


            canonical_start = (
                self._canonical_point(
                    start
                )
            )


            canonical_end = (
                self._canonical_point(
                    end
                )
            )


            if canonical_end < canonical_start:

                canonical_start, canonical_end = (
                    canonical_end,
                    canonical_start
                )


            key = (
                floor,
                canonical_start,
                canonical_end
            )


            grouped_segments.setdefault(
                key,
                []
            ).append(
                segment
            )


        physical_walls = []


        floor_counters = {}


        for (
            floor,
            canonical_start,
            canonical_end
        ), segments in grouped_segments.items():

            if not segments:

                continue


            floor_counters.setdefault(
                floor,
                0
            )


            floor_counters[
                floor
            ] += 1


            physical_wall_id = (
                f"{floor}-W"
                f"{floor_counters[floor]:03d}"
            )


            spaces = []

            boundary_ids = []

            boundary_types = []

            coordinate_modes = []


            for segment in segments:

                space = segment.get(
                    "space"
                )


                if (
                    space is not None
                    and
                    space not in spaces
                ):

                    spaces.append(
                        space
                    )


                boundary_id = segment.get(
                    "boundary_id"
                )


                if (
                    boundary_id is not None
                    and
                    boundary_id not in boundary_ids
                ):

                    boundary_ids.append(
                        boundary_id
                    )


                boundary_type = segment.get(
                    "boundary_type"
                )


                if (
                    boundary_type is not None
                    and
                    boundary_type not in boundary_types
                ):

                    boundary_types.append(
                        boundary_type
                    )


                coordinate_mode = segment.get(
                    "coordinate_mode"
                )


                if (
                    coordinate_mode is not None
                    and
                    coordinate_mode not in coordinate_modes
                ):

                    coordinate_modes.append(
                        coordinate_mode
                    )


            shared_segments = [

                segment

                for segment in segments

                if segment.get(
                    "boundary_type"
                ) == "shared"

            ]


            exterior_segments = [

                segment

                for segment in segments

                if segment.get(
                    "boundary_type"
                ) == "exterior"

            ]


            if len(
                shared_segments
            ) >= 2:

                wall_type = (
                    "interior_shared_wall"
                )

                topology_status = (
                    "resolved_shared_pair"
                )

                is_exterior = False


            elif exterior_segments:

                wall_type = (
                    "exterior_wall"
                )

                topology_status = (
                    "resolved_exterior"
                )

                is_exterior = True


            elif len(
                shared_segments
            ) == 1:

                wall_type = (
                    "interior_shared_wall"
                )

                topology_status = (
                    "shared_pair_incomplete"
                )

                is_exterior = False


            else:

                wall_type = (
                    "wall"
                )

                topology_status = (
                    "boundary_classification_pending"
                )

                is_exterior = None

            # ==============================================
            # WALL THICKNESS CONTRACT v1.0
            #
            # Resolve architectural wall thickness from the
            # already-resolved physical wall classification.
            #
            # IMPORTANT:
            # - thickness belongs to the physical wall
            # - no CAD/export layer should invent thickness
            # - unresolved wall classification remains None
            # ==============================================

            wall_thickness = None

            wall_thickness_source = None

            wall_thickness_status = (
                "wall_thickness_unresolved"
            )


            if wall_type == "exterior_wall":

                wall_thickness = selected("exterior", 0.30)

                wall_thickness_source = (
                    "architectural_wall_type"
                )

                wall_thickness_status = (
                    "resolved_from_wall_type"
                )


            elif wall_type == "interior_shared_wall":

                wall_thickness = selected("interior", 0.10)

                wall_thickness_source = (
                    "architectural_wall_type"
                )

                wall_thickness_status = (
                    "resolved_from_wall_type"
                )


            start_point = [
                canonical_start[0],
                canonical_start[1]
            ]


            end_point = [
                canonical_end[0],
                canonical_end[1]
            ]

            # All source segments for one physical wall must carry the
            # same authoritative level span. Preserve it only on exact
            # agreement; never derive a wall bound from height.
            resolved_span = {}
            span_conflict = False

            for span_key in (
                "bottom",
                "top",
                "height"
            ):

                source_values = [
                    segment.get(span_key)
                    for segment in segments
                ]

                values_agree = bool(
                    source_values
                    and all(
                        value == source_values[0]
                        for value in source_values
                    )
                )

                resolved_span[span_key] = (
                    source_values[0]
                    if values_agree
                    else None
                )

                if not values_agree:

                    span_conflict = True

            span_statuses = [
                segment.get("level_span_status")
                for segment in segments
            ]

            level_span_status = (
                "conflicting_source_level_spans"
                if span_conflict
                else (
                    span_statuses[0]
                    if span_statuses
                and all(
                    status == span_statuses[0]
                    for status in span_statuses
                )
                    else "conflicting_source_level_spans"
                )
            )


            physical_walls.append(
                {

                    "wall_id":
                        physical_wall_id,

                    "floor":
                        floor,

                    "bottom":
                        resolved_span["bottom"],

                    "top":
                        resolved_span["top"],

                    "height":
                        resolved_span["height"],

                    "level_span_status":
                        level_span_status,

                    "start":
                        start_point,

                    "end":
                        end_point,

                    "wall_type":
                        wall_type,

                    "thickness":
                        wall_thickness,

                    "thickness_source":
                        wall_thickness_source,

                    "thickness_status":
                        wall_thickness_status,

                    "is_exterior":
                        is_exterior,

                    "spaces":
                        spaces,

                    "space_count":
                        len(
                            spaces
                        ),

                    "boundary_ids":
                        boundary_ids,

                    "source_boundary_count":
                        len(
                            segments
                        ),

                    "source_boundary_types":
                        boundary_types,

                    "coordinate_mode":
                        (
                            coordinate_modes[0]
                            if len(
                                coordinate_modes
                            ) == 1
                            else None
                        ),

                    "topology_status":
                        topology_status,

                    "source":
                        "architectural_boundary_segments"

                }
            )


        return physical_walls


    def _valid_point(
        self,
        point
    ):

        if not isinstance(
            point,
            (list, tuple)
        ):

            return False


        if len(
            point
        ) < 2:

            return False


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

            return False


        return True


    def _canonical_point(
        self,
        point
    ):

        return (

            round(
                float(
                    point[0]
                ),
                self.COORDINATE_PRECISION
            ),

            round(
                float(
                    point[1]
                ),
                self.COORDINATE_PRECISION
            )

        )
