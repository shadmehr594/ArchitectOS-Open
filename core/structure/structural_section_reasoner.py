print(
    "USING structural_section_reasoner.py StructuralSectionReasoner"
)


class StructuralSectionReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗️ Structural Section Reasoner v1.0 ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def solve(
        self,
        member_type,
        span=None,
        level_height=None,
        building_type=None,
        structural_system=None,
        material=None,
        floor_count=None,
        constraints=None
    ):

        constraints = constraints or {}


        context = {

            "member_type":
                member_type,

            "span":
                span,

            "level_height":
                level_height,

            "building_type":
                building_type,

            "structural_system":
                structural_system,

            "material":
                material,

            "floor_count":
                floor_count

        }


        if member_type == "column":

            return self._reason_column(
                context,
                constraints
            )


        if member_type == "beam":

            return self._reason_beam(
                context,
                constraints
            )


        return {

            "version":
                self.VERSION,

            "member_type":
                member_type,

            "status":
                "unsupported",

            "reason":
                "unsupported_member_type"

        }


    # ==================================================
    # COLUMN
    # ==================================================

    def _reason_column(
        self,
        context,
        constraints
    ):

        level_height = self._safe_float(
            context.get(
                "level_height"
            )
        )


        floor_count = self._safe_int(
            context.get(
                "floor_count"
            )
        )


        base_width = self._safe_float(
            constraints.get(
                "base_column_width"
            )
        )


        base_depth = self._safe_float(
            constraints.get(
                "base_column_depth"
            )
        )


        if base_width is None:

            base_width = 0.30


        if base_depth is None:

            base_depth = 0.30


        height_factor = 0.0


        if level_height is not None:

            height_factor = max(
                0.0,
                level_height - 3.0
            ) * 0.02


        floor_factor = 0.0


        if floor_count is not None:

            floor_factor = max(
                0,
                floor_count - 1
            ) * 0.01


        width = (
            base_width
            +
            height_factor
            +
            floor_factor
        )


        depth = (
            base_depth
            +
            height_factor
            +
            floor_factor
        )


        width = self._clamp(
            width,
            constraints.get(
                "min_column_width",
                0.25
            ),
            constraints.get(
                "max_column_width",
                0.80
            )
        )


        depth = self._clamp(
            depth,
            constraints.get(
                "min_column_depth",
                0.25
            ),
            constraints.get(
                "max_column_depth",
                0.80
            )
        )


        return {

            "version":
                self.VERSION,

            "member_type":
                "column",

            "width":
                round(
                    width,
                    3
                ),

            "depth":
                round(
                    depth,
                    3
                ),

            "reference":
                "corner",

            "reason":
                "context_driven_column_section",

            "context":
                context

        }


    # ==================================================
    # BEAM
    # ==================================================

    def _reason_beam(
        self,
        context,
        constraints
    ):

        span = self._safe_float(
            context.get(
                "span"
            )
        )


        base_width = self._safe_float(
            constraints.get(
                "base_beam_width"
            )
        )


        if base_width is None:

            base_width = 0.25


        if span is None:

            span = 0.0


        span_depth_ratio = self._safe_float(
            constraints.get(
                "span_depth_ratio"
            )
        )


        if span_depth_ratio is None:

            span_depth_ratio = 12.0


        depth = (

            span
            /
            span_depth_ratio

            if span > 0

            else 0.40

        )


        width = max(
            base_width,
            depth * 0.45
        )


        width = self._clamp(
            width,
            constraints.get(
                "min_beam_width",
                0.20
            ),
            constraints.get(
                "max_beam_width",
                0.60
            )
        )


        depth = self._clamp(
            depth,
            constraints.get(
                "min_beam_depth",
                0.30
            ),
            constraints.get(
                "max_beam_depth",
                1.20
            )
        )


        return {

            "version":
                self.VERSION,

            "member_type":
                "beam",

            "width":
                round(
                    width,
                    3
                ),

            "depth":
                round(
                    depth,
                    3
                ),

            "span":
                round(
                    span,
                    3
                ),

            "reference":
                "corner",

            "reason":
                "context_driven_beam_section",

            "context":
                context

        }


    # ==================================================
    # HELPERS
    # ==================================================

    def _safe_float(
        self,
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


    def _safe_int(
        self,
        value
    ):

        if value is None:

            return None


        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return None


    def _clamp(
        self,
        value,
        minimum,
        maximum
    ):

        minimum = float(
            minimum
        )

        maximum = float(
            maximum
        )


        return max(
            minimum,
            min(
                value,
                maximum
            )
        )