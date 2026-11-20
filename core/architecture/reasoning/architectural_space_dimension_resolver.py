class ArchitecturalSpaceDimensionResolver:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📐 ARCHITECTURAL SPACE DIMENSION RESOLVER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        dimensional_requirements,
        space_type=None,
        canonical_name=None
    ):

        requirements = dict(
            dimensional_requirements
            or
            {}
        )


        normalized_space_type = str(
            space_type
            or
            ""
        ).lower()


        normalized_canonical_name = str(
            canonical_name
            or
            ""
        ).lower()


        is_corridor = (
            normalized_space_type
            ==
            "corridor"
            or
            normalized_canonical_name
            ==
            "corridor"
        )


        minimum_area = (
            requirements.get(
                "minimum_area"
            )
        )


        preferred_area = (
            requirements.get(
                "preferred_area"
            )
        )


        minimum_width = (
            requirements.get(
                "minimum_width"
            )
        )


        minimum_depth = (
            requirements.get(
                "minimum_depth"
            )
        )


        resolved_width = (
            requirements.get(
                "resolved_width"
            )
        )


        resolved_depth = (
            requirements.get(
                "resolved_depth"
            )
        )


        resolved_area = (
            requirements.get(
                "resolved_area"
            )
        )


        def as_float(
            value
        ):

            if value is None:

                return None


            try:

                return float(
                    value
                )

            except (
                TypeError,
                ValueError
            ):

                return None


        minimum_area = as_float(
            minimum_area
        )

        preferred_area = as_float(
            preferred_area
        )

        minimum_width = as_float(
            minimum_width
        )

        minimum_depth = as_float(
            minimum_depth
        )

        resolved_width = as_float(
            resolved_width
        )

        resolved_depth = as_float(
            resolved_depth
        )

        resolved_area = as_float(
            resolved_area
        )


        target_area = (
            preferred_area
            if preferred_area is not None
            else
            minimum_area
        )


        # ==============================================
        # CORRIDOR
        #
        # Corridor width may already have been resolved
        # by circulation intelligence.
        # ==============================================

        if is_corridor:

            if resolved_width is None:

                resolved_width = as_float(
                    requirements.get(
                        "preferred_width"
                    )
                )


            if resolved_width is None:

                resolved_width = minimum_width


            if (
                resolved_width is not None
                and
                resolved_depth is None
                and
                target_area is not None
                and
                resolved_width > 0
            ):

                resolved_depth = (
                    target_area
                    /
                    resolved_width
                )


            if (
                resolved_width is not None
                and
                resolved_depth is not None
            ):

                resolved_area = (
                    resolved_width
                    *
                    resolved_depth
                )


        # ==============================================
        # GENERAL ARCHITECTURAL SPACE
        # ==============================================

        else:

            if (
                resolved_width is None
                or
                resolved_depth is None
            ):

                if (
                    target_area is not None
                    and
                    target_area > 0
                ):

                    balanced_dimension = (
                        target_area
                        **
                        0.5
                    )


                    resolved_width = max(
                        balanced_dimension,
                        minimum_width
                        if minimum_width is not None
                        else 0.0
                    )


                    resolved_depth = max(
                        (
                            target_area
                            /
                            resolved_width
                        ),
                        minimum_depth
                        if minimum_depth is not None
                        else 0.0
                    )


            if (
                resolved_width is not None
                and
                resolved_depth is not None
            ):

                resolved_area = (
                    resolved_width
                    *
                    resolved_depth
                )


        if resolved_width is not None:

            requirements[
                "resolved_width"
            ] = resolved_width


        if resolved_depth is not None:

            requirements[
                "resolved_depth"
            ] = resolved_depth


        if resolved_area is not None:

            requirements[
                "resolved_area"
            ] = resolved_area


        resolved_dimensions = None


        if (
            resolved_width is not None
            and
            resolved_depth is not None
            and
            resolved_area is not None
        ):

            resolved_dimensions = {
                "width":
                    resolved_width,

                "depth":
                    resolved_depth,

                "area":
                    resolved_area,

                "target_area":
                    target_area,

                "minimum_width":
                    minimum_width,

                "minimum_depth":
                    minimum_depth,

                "source":
                    (
                        "preferred_area"
                        if preferred_area is not None
                        else
                        "minimum_area"
                    ),

                "status":
                    "resolved_from_program_knowledge"
            }


        return {
            "dimensional_requirements":
                requirements,

            "resolved_dimensions":
                resolved_dimensions
        }