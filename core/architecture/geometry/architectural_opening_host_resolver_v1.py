import math


class ArchitecturalOpeningHostResolverV1:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🚪 ARCHITECTURAL OPENING HOST RESOLVER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        openings,
        physical_walls
    ):

        if not isinstance(
            openings,
            list
        ):

            openings = []


        if not isinstance(
            physical_walls,
            list
        ):

            physical_walls = []


        resolved_openings = []


        for opening in openings:

            if not isinstance(
                opening,
                dict
            ):

                continue


            resolved_opening = dict(
                opening
            )


            opening_floor = opening.get(
                "floor"
            )

            opening_space = opening.get(
                "space"
            )

            opening_type = opening.get(
                "type"
            )

            opening_category = opening.get(
                "category"
            )

            connects_to = opening.get("connects_to")


            required_width = (
                self._resolve_required_width(
                    opening.get(
                        "width"
                    )
                )
            )


            candidates = []


            for wall in physical_walls:

                if not isinstance(
                    wall,
                    dict
                ):

                    continue


                if wall.get(
                    "floor"
                ) != opening_floor:

                    continue


                wall_spaces = wall.get(
                    "spaces",
                    []
                )


                if not isinstance(
                    wall_spaces,
                    list
                ):

                    wall_spaces = []


                if (
                    opening_space
                    not in wall_spaces
                ):

                    continue

                if (
                    opening_type == "door"
                    and opening_category != "main_entrance"
                    and connects_to
                    and connects_to not in wall_spaces
                ):
                    continue


                if (
                    opening_type == "window"
                    or
                    opening_category
                    == "main_entrance"
                ):

                    if not (
                        wall.get(
                            "is_exterior"
                        )
                        is True
                    ):

                        continue


                wall_length = (
                    self._wall_length(
                        wall
                    )
                )


                if (
                    required_width is not None
                    and
                    wall_length is not None
                    and
                    wall_length
                    < required_width
                ):

                    continue


                candidates.append(
                    wall
                )


            candidate_wall_ids = [
                wall.get(
                    "wall_id"
                )
                for wall in candidates
                if wall.get(
                    "wall_id"
                )
            ]


            candidate_boundary_ids = []


            for wall in candidates:

                boundary_ids = wall.get(
                    "boundary_ids",
                    []
                )


                if not isinstance(
                    boundary_ids,
                    list
                ):

                    continue


                for boundary_id in boundary_ids:

                    if (
                        boundary_id
                        and
                        boundary_id
                        not in candidate_boundary_ids
                    ):

                        candidate_boundary_ids.append(
                            boundary_id
                        )


            resolved_opening[
                "candidate_wall_ids"
            ] = candidate_wall_ids


            resolved_opening[
                "candidate_boundary_ids"
            ] = candidate_boundary_ids


            resolved_opening[
                "candidate_count"
            ] = len(
                candidates
            )


            resolved_opening[
                "host_wall_id"
            ] = None


            resolved_opening[
                "host_boundary_id"
            ] = None


            resolved_opening[
                "host_resolution_status"
            ] = None


            resolved_opening[
                "host_resolution_reason"
            ] = None


            if not candidates:

                resolved_opening[
                    "host_resolution_status"
                ] = (
                    "host_unresolved_no_candidate"
                )

                resolved_opening[
                    "host_resolution_reason"
                ] = (
                    "no_compatible_physical_wall"
                )


            elif len(
                candidates
            ) == 1:

                selected_wall = (
                    candidates[0]
                )


                resolved_opening[
                    "host_wall_id"
                ] = selected_wall.get(
                    "wall_id"
                )


                boundary_ids = (
                    selected_wall.get(
                        "boundary_ids",
                        []
                    )
                )


                if (
                    isinstance(
                        boundary_ids,
                        list
                    )
                    and
                    len(
                        boundary_ids
                    ) == 1
                ):

                    resolved_opening[
                        "host_boundary_id"
                    ] = boundary_ids[0]


                resolved_opening[
                    "host_resolution_status"
                ] = (
                    "resolved_unique_physical_wall"
                )


                resolved_opening[
                    "host_resolution_reason"
                ] = (
                    "single_compatible_wall_candidate"
                )


            else:

                resolved_opening[
                    "host_resolution_status"
                ] = (
                    "host_pending_multiple_candidates"
                )


                resolved_opening[
                    "host_resolution_reason"
                ] = (
                    "multiple_compatible_walls_require_architectural_evidence"
                )


            resolved_openings.append(
                resolved_opening
            )


        return resolved_openings


    def _resolve_required_width(
        self,
        width
    ):

        if not isinstance(
            width,
            (int, float)
        ):

            return None


        width = float(
            width
        )


        if width <= 0:

            return None


        # OpeningReasoner currently expresses
        # opening dimensions in millimetres,
        # while architectural plan geometry
        # is expressed in metres.

        if width > 20:

            width = (
                width / 1000.0
            )


        return width


    def _wall_length(
        self,
        wall
    ):

        start = wall.get(
            "start"
        )

        end = wall.get(
            "end"
        )


        if not self._valid_point(
            start
        ):

            return None


        if not self._valid_point(
            end
        ):

            return None


        dx = (
            float(
                end[0]
            )
            -
            float(
                start[0]
            )
        )

        dy = (
            float(
                end[1]
            )
            -
            float(
                start[1]
            )
        )


        return math.sqrt(
            dx * dx
            +
            dy * dy
        )


    def _valid_point(
        self,
        point
    ):

        return (
            isinstance(
                point,
                (list, tuple)
            )
            and
            len(
                point
            ) >= 2
            and
            isinstance(
                point[0],
                (int, float)
            )
            and
            isinstance(
                point[1],
                (int, float)
            )
        )
