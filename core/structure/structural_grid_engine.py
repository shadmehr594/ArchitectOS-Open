import math

from core.structure.architectural_structural_anchor_engine import (
    ArchitecturalStructuralAnchorEngine
)


from core.structure.structural_span_reasoner import (
    StructuralSpanReasoner
)


from core.structure.structural_point_selection_engine import (
    StructuralPointSelectionEngine
)


from core.structure.structural_column_optimizer import (
    StructuralColumnOptimizer
)


from core.structure.structural_column_placement_engine import (
    StructuralColumnPlacementEngine
)


from core.structure.adaptive_beam_reasoner import (
    AdaptiveBeamReasoner
)


from core.structure.structural_section_reasoner import (
    StructuralSectionReasoner
)

from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureHandoffV1
)


print("USING structural_grid_engine.py Adaptive StructuralGridEngine")


class StructuralGridEngine:


    VERSION = "2.0"


    def __init__(self):

        print(
            "🏗️ Adaptive Structural Grid Engine v2.0 ACTIVE"
        )


        self.anchor_engine = ArchitecturalStructuralAnchorEngine()

        self.span_reasoner = StructuralSpanReasoner()

        self.point_selector = StructuralPointSelectionEngine()

        self.column_optimizer = StructuralColumnOptimizer()

        self.column_placement_engine = StructuralColumnPlacementEngine()

        self.beam_reasoner = AdaptiveBeamReasoner()

        self.section_reasoner = StructuralSectionReasoner()

        self.architecture_handoff = ArchitectureStructureHandoffV1()


    # ==================================================
    # MAIN BUILD
    # ==================================================

    def build(
        self,
        architectural_model,
        vertical_section
    ):

        architecture_handoff = self.architecture_handoff.create(
            architectural_model,
            vertical_section
        )

        self.architecture_handoff.require_ready(
            architecture_handoff,
            consumer="structural_grid",
        )


        building = architectural_model.get(
            "building",
            {}
        )


        width = building.get(
            "width",
            0
        )


        depth = building.get(
            "depth",
            0
        )

        # ==================================================
        # ARCHITECTURE-FIRST STRUCTURAL DOMAIN v1.0
        #
        # Structural grid reasoning must occur in the
        # building-local architectural frame whenever a
        # resolved architectural support domain exists.
        #
        # IMPORTANT:
        #
        # - do not generate the structural grid from the
        #   parcel-local bounding box
        # - do not remove architectural rotation
        # - source_polygon is authoritative for structural
        #   grid generation
        # - parcel polygon remains the resolved output frame
        # ==================================================

        architecture_first = bool(
            architectural_model.get(
                "architecture_first",
                False
            )
        )


        coordinate_frame = architectural_model.get(
            "coordinate_frame",
            {}
        )


        if not isinstance(
            coordinate_frame,
            dict
        ):

            coordinate_frame = {}

        # ==================================================
        # ARCHITECTURE -> PARCEL RIGID TRANSFORM
        # ==================================================

        parcel_placement = architectural_model.get(
            "parcel_placement",
            {}
        )


        if not isinstance(
            parcel_placement,
            dict
        ):

            parcel_placement = {}


        parcel_transform = parcel_placement.get(
            "transform",
            {}
        )


        if not isinstance(
            parcel_transform,
            dict
        ):

            parcel_transform = {}


        source_pivot = parcel_transform.get(
            "source_pivot",
            {}
        )


        target_pivot = parcel_transform.get(
            "target_pivot",
            {}
        )


        if not isinstance(
            source_pivot,
            dict
        ):

            source_pivot = {}


        if not isinstance(
            target_pivot,
            dict
        ):

            target_pivot = {}


        source_pivot_x = source_pivot.get(
            "x"
        )

        source_pivot_y = source_pivot.get(
            "y"
        )

        target_pivot_x = target_pivot.get(
            "x"
        )

        target_pivot_y = target_pivot.get(
            "y"
        )


        rotation_degrees = parcel_transform.get(
            "rotation_degrees",
            parcel_placement.get(
                "rotation",
                0.0
            )
        )


        try:

            rotation_degrees = float(
                rotation_degrees
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            rotation_degrees = 0.0


        rotation_radians = math.radians(
            rotation_degrees
        )


        rotation_cos = math.cos(
            rotation_radians
        )

        rotation_sin = math.sin(
            rotation_radians
        )


        rigid_transform_available = (

            isinstance(
                source_pivot_x,
                (int, float)
            )

            and

            isinstance(
                source_pivot_y,
                (int, float)
            )

            and

            isinstance(
                target_pivot_x,
                (int, float)
            )

            and

            isinstance(
                target_pivot_y,
                (int, float)
            )

            and

            bool(
                parcel_placement.get(
                    "rotation_applied",
                    coordinate_frame.get(
                        "rotation_applied",
                        False
                    )
                )
            )

        )


        translation = parcel_placement.get(
            "translation",
            {}
        )


        if not isinstance(
            translation,
            dict
        ):

            translation = {}


        try:

            parcel_dx = float(
                translation.get(
                    "dx",
                    0.0
                )
                or 0.0
            )

            parcel_dy = float(
                translation.get(
                    "dy",
                    0.0
                )
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            parcel_dx = 0.0
            parcel_dy = 0.0


        translation_applied = bool(
            parcel_placement.get(
                "translation_applied",
                False
            )
        )


        def transform_point_to_parcel(
            x,
            y
        ):

            if not (
                isinstance(
                    x,
                    (int, float)
                )
                and
                isinstance(
                    y,
                    (int, float)
                )
            ):

                return None


            source_point_x = float(
                x
            )

            source_point_y = float(
                y
            )


            if rigid_transform_available:

                relative_x = (
                    source_point_x
                    -
                    float(
                        source_pivot_x
                    )
                )

                relative_y = (
                    source_point_y
                    -
                    float(
                        source_pivot_y
                    )
                )


                resolved_x = (
                    relative_x
                    *
                    rotation_cos
                    -
                    relative_y
                    *
                    rotation_sin
                    +
                    float(
                        target_pivot_x
                    )
                )

                resolved_y = (
                    relative_x
                    *
                    rotation_sin
                    +
                    relative_y
                    *
                    rotation_cos
                    +
                    float(
                        target_pivot_y
                    )
                )


                return [
                    resolved_x,
                    resolved_y
                ]


            if translation_applied:

                return [

                    source_point_x
                    +
                    parcel_dx,

                    source_point_y
                    +
                    parcel_dy

                ]


            return [
                source_point_x,
                source_point_y
            ]


        primary_support_domain = None

        support_domains = []


        preliminary_anchor_data = self.anchor_engine.extract(
            architectural_model
        )


        if isinstance(
            preliminary_anchor_data,
            dict
        ):

            primary_support_domain = (
                preliminary_anchor_data.get(
                    "primary_support_domain"
                )
            )


            extracted_support_domains = (
                preliminary_anchor_data.get(
                    "support_domains",
                    []
                )
            )


            if isinstance(
                extracted_support_domains,
                list
            ):

                support_domains = [
                    dict(
                        support_domain
                    )
                    for support_domain
                    in extracted_support_domains
                    if isinstance(
                        support_domain,
                        dict
                    )
                ]


        structural_domain = {

            "mode":
                "legacy_building_rectangle",

            "floor":
                None,

            "origin_x":
                0.0,

            "origin_y":
                0.0,

            "width":
                width,

            "depth":
                depth,

            "source_polygon":
                None,

            "parcel_polygon":
                None,

            "coordinate_mode":
                "architectural_metric",

            "rotation_degrees":
                0.0,

            "status":
                "legacy"

        }


        if (
            architecture_first
            and isinstance(
                primary_support_domain,
                dict
            )
        ):

            source_polygon = (
                primary_support_domain.get(
                    "source_polygon"
                )
            )


            parcel_polygon = (
                primary_support_domain.get(
                    "polygon"
                )
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

                valid_source_points = []


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


                    valid_source_points.append(
                        [
                            point_x,
                            point_y
                        ]
                    )


                if len(
                    valid_source_points
                ) >= 3:

                    source_x_values = [

                        point[0]

                        for point in valid_source_points

                    ]


                    source_y_values = [

                        point[1]

                        for point in valid_source_points

                    ]


                    source_min_x = min(
                        source_x_values
                    )

                    source_max_x = max(
                        source_x_values
                    )

                    source_min_y = min(
                        source_y_values
                    )

                    source_max_y = max(
                        source_y_values
                    )


                    domain_width = (
                        source_max_x
                        -
                        source_min_x
                    )


                    domain_depth = (
                        source_max_y
                        -
                        source_min_y
                    )


                    if (
                        domain_width > 0
                        and
                        domain_depth > 0
                    ):

                        width = domain_width

                        depth = domain_depth


                        structural_domain = {

                            "mode":
                                "architectural_support_domain",

                            "floor":
                                primary_support_domain.get(
                                    "floor"
                                ),

                            "origin_x":
                                source_min_x,

                            "origin_y":
                                source_min_y,

                            "width":
                                domain_width,

                            "depth":
                                domain_depth,

                            "source_polygon":
                                valid_source_points,

                            "parcel_polygon":
                                (
                                    list(
                                        parcel_polygon
                                    )
                                    if isinstance(
                                        parcel_polygon,
                                        list
                                    )
                                    else None
                                ),

                            "coordinate_mode":
                                "architectural_metric_floor_local",

                            "resolved_coordinate_mode":
                                primary_support_domain.get(
                                    "coordinate_mode"
                                ),

                            "rotation_degrees":
                                primary_support_domain.get(
                                    "rotation_degrees",
                                    coordinate_frame.get(
                                        "rotation_degrees",
                                        0.0
                                    )
                                ),

                            "status":
                                "resolved"

                        }


        spaces = architectural_model.get(
            "spaces",
            []
        )


        architectural_spaces = architectural_model.get(
            "architectural_spaces",
            []
        )


        if not isinstance(
            architectural_spaces,
            list
        ):

            architectural_spaces = []


        protected = self._extract_protected_zones(
            architectural_spaces,
            legacy_spaces=spaces
        )

        # ==================================================
        # FLOOR-AWARE PROTECTED STRUCTURAL ZONES v1.0
        #
        # Structural reasoning for a support domain must
        # only consume protected zones belonging to that
        # same architectural floor.
        #
        # The complete protected-zone contract is preserved
        # separately for downstream floor-aware structure.
        # ==================================================

        active_structural_floor = (
            structural_domain.get(
                "floor"
            )
            if isinstance(
                structural_domain,
                dict
            )
            else None
        )


        active_protected = []


        if (
            architecture_first
            and active_structural_floor
        ):

            for protected_zone in protected:

                if not isinstance(
                    protected_zone,
                    dict
                ):

                    continue


                protected_floor = protected_zone.get(
                    "floor"
                )


                if (
                    protected_floor is None
                    or
                    protected_floor
                    ==
                    active_structural_floor
                ):

                    active_protected.append(
                        protected_zone
                    )

        else:

            active_protected = list(
                protected
            )


        print(
            "\n====== FLOOR-AWARE STRUCTURAL PROTECTION ======"
        )

        print(
            "ACTIVE STRUCTURAL FLOOR:",
            active_structural_floor
        )

        print(
            "ALL PROTECTED ZONES:",
            [
                (
                    zone.get("floor"),
                    zone.get("name")
                )
                for zone in protected
                if isinstance(
                    zone,
                    dict
                )
            ]
        )

        print(
            "ACTIVE PROTECTED ZONES:",
            [
                (
                    zone.get("floor"),
                    zone.get("name")
                )
                for zone in active_protected
                if isinstance(
                    zone,
                    dict
                )
            ]
        )

        print(
            "==============================================="
        )


        anchor_data = preliminary_anchor_data

        anchor_ownership = None
        master_x_anchors = []
        master_y_anchors = []
        floor_boundary_evidence = []


        if isinstance(
            anchor_data,
            dict
        ):

            anchor_ownership = anchor_data.get(
                "anchor_ownership"
            )


            master_x_anchors = anchor_data.get(
                "master_x_anchors",
                []
            )


            master_y_anchors = anchor_data.get(
                "master_y_anchors",
                []
            )


            floor_boundary_evidence = anchor_data.get(
                "floor_boundary_evidence",
                []
            )


            if not isinstance(
                master_x_anchors,
                list
            ):

                master_x_anchors = []


            if not isinstance(
                master_y_anchors,
                list
            ):

                master_y_anchors = []


            if not isinstance(
                floor_boundary_evidence,
                list
            ):

                floor_boundary_evidence = []


        grid = self._generate_adaptive_grid(
            width,
            depth,
            active_protected,
            anchor_data,
            origin_x=structural_domain.get(
                "origin_x",
                0.0
            ),
            origin_y=structural_domain.get(
                "origin_y",
                0.0
            )
        )

        # ==================================================
        # RESOLVE STRUCTURAL GRID TO PARCEL FRAME
        # ==================================================

        resolved_grid = []


        for point in grid:

            resolved_point = dict(
                point
            )


            parcel_point = transform_point_to_parcel(
                point.get(
                    "x"
                ),
                point.get(
                    "y"
                )
            )


            if parcel_point is not None:

                resolved_point[
                    "parcel_x"
                ] = parcel_point[0]

                resolved_point[
                    "parcel_y"
                ] = parcel_point[1]

                resolved_point[
                    "coordinate_mode"
                ] = (
                    "architectural_metric_floor_local"
                )

                resolved_point[
                    "resolved_coordinate_mode"
                ] = "parcel_local"


            resolved_grid.append(
                resolved_point
            )


        grid = resolved_grid


        levels = architecture_handoff.get(
            "levels",
            []
        )


        floor_count = len(
            levels
        )


        default_level_height = None


        if levels:

            first_level = levels[0]

            if isinstance(
                first_level,
                dict
            ):

                default_level_height = first_level.get(
                    "height"
                )

        candidate_columns = self._generate_columns(
            grid,
            active_protected
        )


        # ==================================================
        # PRE-PLACEMENT COLUMN SECTION RESOLUTION v1.0
        #
        # Physical section dimensions must be resolved
        # BEFORE:
        #
        # - architectural boundary validation
        # - protected-zone intersection
        # - column shifting
        #
        # Otherwise placement may validate a temporary
        # 0.30 m column and SectionReasoner may enlarge it
        # afterward, invalidating the resolved placement.
        # ==================================================

        column_section = self.section_reasoner.solve(
            member_type="column",
            level_height=default_level_height,
            floor_count=floor_count
        )


        resolved_candidate_columns = []


        for column in candidate_columns:

            if not isinstance(
                column,
                dict
            ):

                continue


            resolved_column = dict(
                column
            )


            resolved_column[
                "width"
            ] = column_section.get(
                "width"
            )


            resolved_column[
                "depth"
            ] = column_section.get(
                "depth"
            )


            resolved_column[
                "section_reason"
            ] = column_section.get(
                "reason"
            )


            resolved_column[
                "section_resolution_stage"
            ] = "before_architectural_placement"


            resolved_candidate_columns.append(
                resolved_column
            )


        candidate_columns = resolved_candidate_columns


        optimized_columns = self.column_optimizer.optimize(
            candidate_columns,
            architectural_model
        )


        if isinstance(
            optimized_columns,
            dict
        ):

            optimized_columns = optimized_columns.get(
                "columns",
                optimized_columns.get(
                    "optimized_columns",
                    []
                )
            )


        placement_result = self.column_placement_engine.place(
            optimized_columns,
            architectural_model,
            protected_zones=active_protected
        )


        columns = placement_result.get(
            "columns",
            []
        )

        # ==================================================
        # RESOLVE FINAL STRUCTURAL COLUMNS TO PARCEL FRAME
        #
        # Column placement is authoritative for final
        # structural x / y.
        #
        # Therefore parcel coordinates must be resolved
        # AFTER:
        #
        # - section resolution
        # - optimization
        # - architectural boundary placement
        # - protected-zone coordination
        #
        # Local structural x / y remain unchanged.
        # ==================================================

        resolved_columns = []


        for column in columns:

            if not isinstance(
                column,
                dict
            ):

                continue


            resolved_column = dict(
                column
            )


            parcel_point = transform_point_to_parcel(
                column.get(
                    "x"
                ),
                column.get(
                    "y"
                )
            )


            if parcel_point is not None:

                resolved_column[
                    "parcel_x"
                ] = parcel_point[0]

                resolved_column[
                    "parcel_y"
                ] = parcel_point[1]

                resolved_column[
                    "coordinate_mode"
                ] = (
                    "architectural_metric_floor_local"
                )

                resolved_column[
                    "resolved_coordinate_mode"
                ] = "parcel_local"

                resolved_column[
                    "parcel_resolution_stage"
                ] = (
                    "after_architectural_placement"
                )


            resolved_columns.append(
                resolved_column
            )


        columns = resolved_columns


        beam_result = self.beam_reasoner.generate(
            columns,
            protected_zones=active_protected
        )


        beams = beam_result.get(
            "beams",
            []
        )


        sized_beams = []


        for beam in beams:

            section = self.section_reasoner.solve(
                member_type="beam",
                span=beam.get(
                    "length"
                ),
                level_height=default_level_height,
                floor_count=floor_count
            )


            sized_beam = dict(
                beam
            )


            sized_beam[
                "width"
            ] = section.get(
                "width"
            )


            sized_beam[
                "depth"
            ] = section.get(
                "depth"
            )


            sized_beam[
                "section_reason"
            ] = section.get(
                "reason"
            )


            sized_beams.append(
                sized_beam
            )


        beams = sized_beams

        # ==================================================
        # RESOLVE FINAL STRUCTURAL BEAMS TO PARCEL FRAME
        #
        # Beam connectivity and structural reasoning remain
        # in architectural_metric_floor_local coordinates.
        #
        # Parcel geometry is additional resolved evidence.
        # ==================================================

        resolved_beams = []


        for beam in beams:

            if not isinstance(
                beam,
                dict
            ):

                continue


            resolved_beam = dict(
                beam
            )


            start = beam.get(
                "start"
            )

            end = beam.get(
                "end"
            )


            parcel_start = None
            parcel_end = None


            if (
                isinstance(
                    start,
                    (list, tuple)
                )
                and
                len(
                    start
                ) >= 2
            ):

                parcel_start = transform_point_to_parcel(
                    start[0],
                    start[1]
                )


            if (
                isinstance(
                    end,
                    (list, tuple)
                )
                and
                len(
                    end
                ) >= 2
            ):

                parcel_end = transform_point_to_parcel(
                    end[0],
                    end[1]
                )


            if (
                parcel_start is not None
                and
                parcel_end is not None
            ):

                resolved_beam[
                    "parcel_start"
                ] = parcel_start

                resolved_beam[
                    "parcel_end"
                ] = parcel_end

                resolved_beam[
                    "coordinate_mode"
                ] = (
                    "architectural_metric_floor_local"
                )

                resolved_beam[
                    "resolved_coordinate_mode"
                ] = "parcel_local"


                parcel_dx = (
                    parcel_end[0]
                    -
                    parcel_start[0]
                )

                parcel_dy = (
                    parcel_end[1]
                    -
                    parcel_start[1]
                )


                resolved_beam[
                    "parcel_orientation_degrees"
                ] = math.degrees(
                    math.atan2(
                        parcel_dy,
                        parcel_dx
                    )
                )


            resolved_beams.append(
                resolved_beam
            )


        beams = resolved_beams

        # ==================================================
        # FLOOR STRUCTURAL MASK + VERTICAL CONTINUITY
        #
        # One base structural topology is inherited upward.
        # Upper-floor footprints may deactivate supports,
        # but must not independently redesign the grid.
        # ==================================================

        floor_structural_systems = (
            self._build_floor_structural_systems(
                levels,
                support_domains,
                columns,
                beams
            )
        )


        print(
            "\n====== FLOOR STRUCTURAL CONTINUITY ======"
        )


        for (
            floor_name,
            floor_system
        ) in floor_structural_systems.items():

            print(
                floor_name,
                {
                    "mode":
                        floor_system.get(
                            "topology_mode"
                        ),

                    "columns":
                        floor_system.get(
                            "column_count"
                        ),

                    "beams":
                        floor_system.get(
                            "beam_count"
                        )
                }
            )


        print(
            "========================================="
        )


        return {


            "version":
                self.VERSION,


            "grid_type":
                "adaptive",


            "architecture_first":
                architecture_first,


            "architecture_handoff":
                architecture_handoff,


            "structural_domain":
                structural_domain,


            "support_domains":
                support_domains,


            "floor_structural_systems":
                floor_structural_systems,


            "anchor_ownership":
                anchor_ownership,


            "master_x_anchors":
                list(
                    master_x_anchors
                ),


            "master_y_anchors":
                list(
                    master_y_anchors
                ),


            "floor_boundary_evidence":
                list(
                    floor_boundary_evidence
                ),


            "coordinate_frame":
                dict(
                    coordinate_frame
                ),

            
            "parcel_placement":
                dict(
                    parcel_placement
                ),


            "origin":
                "architectural_corner_origin",


            "grid":
                grid,


            "columns":
                columns,


            "beams":
                beams,


            "protected_zones":
                protected,


            "active_protected_zones":
                active_protected,


            "levels":
                levels

        }



    # ==================================================
    # PROTECTED ARCHITECTURAL ZONES
    # ==================================================

    def _extract_protected_zones(
        self,
        architectural_spaces,
        legacy_spaces=None
    ):

        zones = []


        architectural_spaces = (
            architectural_spaces
            if isinstance(
                architectural_spaces,
                list
            )
            else []
        )


        legacy_spaces = (
            legacy_spaces
            if isinstance(
                legacy_spaces,
                list
            )
            else []
        )


        # ==================================================
        # ARCHITECTURE-FIRST PROTECTED ZONES
        #
        # ArchitecturalGeometry is authoritative when it
        # supplies explicit protected_zone semantics and a
        # resolved footprint.
        #
        # IMPORTANT:
        # - protected status is semantic, not inferred from
        #   the room name
        # - rotated parcel-local footprints are preserved
        # - bounds are also retained temporarily for legacy
        #   structural consumers
        # ==================================================

        for space in architectural_spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            if not bool(
                space.get(
                    "protected_zone",
                    False
                )
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


            # ==================================================
            # RESOLVED PARCEL-LOCAL POLYGON
            # ==================================================

            points = footprint.get(
                "points"
            )


            valid_points = []


            if isinstance(
                points,
                list
            ):

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


            resolved_x_values = [

                point[0]

                for point in valid_points

            ]


            resolved_y_values = [

                point[1]

                for point in valid_points

            ]


            min_x = min(
                resolved_x_values
            )

            max_x = max(
                resolved_x_values
            )

            min_y = min(
                resolved_y_values
            )

            max_y = max(
                resolved_y_values
            )


            # ==================================================
            # SOURCE ARCHITECTURAL POLYGON
            #
            # Structural reasoning operates in the original
            # architectural metric / floor-local coordinate
            # frame.
            #
            # Therefore protected-zone collision tests must use
            # this polygon whenever it is available.
            # ==================================================

            source_points = footprint.get(
                "source_points"
            )


            valid_source_points = []


            if isinstance(
                source_points,
                list
            ):

                for point in source_points:

                    if not (
                        isinstance(
                            point,
                            (list, tuple)
                        )
                        and len(
                            point
                        ) >= 2
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


                    valid_source_points.append(
                        [
                            point_x,
                            point_y
                        ]
                    )


            source_bounds = None


            if len(
                valid_source_points
            ) >= 3:

                source_x_values = [

                    point[0]

                    for point in valid_source_points

                ]


                source_y_values = [

                    point[1]

                    for point in valid_source_points

                ]


                source_min_x = min(
                    source_x_values
                )

                source_max_x = max(
                    source_x_values
                )

                source_min_y = min(
                    source_y_values
                )

                source_max_y = max(
                    source_y_values
                )


                source_bounds = [

                    source_min_x,

                    source_min_y,

                    source_max_x - source_min_x,

                    source_max_y - source_min_y

                ]


            zones.append(
                {
                    "name":
                        space.get(
                            "name"
                        ),

                    "floor":
                        space.get(
                            "floor"
                        ),

                    "type":
                        space.get(
                            "type"
                        ),

                    "protected_zone":
                        True,

                    # --------------------------------------
                    # STRUCTURAL REASONING FRAME
                    # --------------------------------------

                    "source_polygon":
                        (
                            valid_source_points
                            if len(
                                valid_source_points
                            ) >= 3
                            else None
                        ),

                    "source_bounds":
                        source_bounds,

                    "source_coordinate_mode":
                        (
                            footprint.get(
                                "source_coordinate_mode"
                            )
                            or
                            "architectural_metric_floor_local"
                        ),

                    # --------------------------------------
                    # RESOLVED ARCHITECTURAL FRAME
                    # --------------------------------------

                    "polygon":
                        valid_points,

                    "bounds":
                        [
                            min_x,
                            min_y,
                            max_x - min_x,
                            max_y - min_y
                        ],

                    "coordinate_mode":
                        footprint.get(
                            "coordinate_mode",
                            space.get(
                                "coordinate_mode"
                            )
                        ),

                    "geometry_type":
                        footprint.get(
                            "type"
                        ),

                    "geometry_status":
                        space.get(
                            "geometry_status"
                        ),

                    "allow_column":
                        False,

                    "allow_beam":
                        False,

                    "source":
                        "architectural_geometry_protected_zone"
                }
            )

        # ==================================================
        # LEGACY FALLBACK
        #
        # Only use old type/bounds inference when no
        # Architecture-First protected geometry exists.
        # ==================================================

        if zones:

            return zones


        for space in legacy_spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            if space.get(
                "type"
            ) not in [
                "stairs",
                "elevator",
                "duct",
                "corridor",
                "public_circulation"
            ]:

                continue


            bounds = space.get(
                "bounds"
            )


            if not (
                isinstance(
                    bounds,
                    (list, tuple)
                )
                and len(
                    bounds
                ) == 4
            ):

                continue


            zones.append(
                {
                    "name":
                        space.get(
                            "name"
                        ),

                    "floor":
                        space.get(
                            "level"
                        ),

                    "type":
                        space.get(
                            "type"
                        ),

                    "protected_zone":
                        True,

                    "bounds":
                        list(
                            bounds
                        ),

                    "polygon":
                        None,

                    "allow_column":
                        False,

                    "allow_beam":
                        False,

                    "source":
                        "legacy_structural_space_type"
                }
            )


        return zones


    
    # ==================================================
    # ADAPTIVE STRUCTURAL POINT GENERATOR
    # ARCHITECTURE DRIVEN
    # ==================================================

    def _generate_adaptive_grid(
        self,
        width,
        depth,
        protected,
        anchor_data,
        origin_x=0.0,
        origin_y=0.0
    ):

        try:

            origin_x = float(
                origin_x
            )

        except (
            TypeError,
            ValueError
        ):

            origin_x = 0.0


        try:

            origin_y = float(
                origin_y
            )

        except (
            TypeError,
            ValueError
        ):

            origin_y = 0.0


        raw_x_anchors = anchor_data.get(
            "x_anchors",
            []
        )


        raw_y_anchors = anchor_data.get(
            "y_anchors",
            []
        )


        # ==================================================
        # STRUCTURAL SPAN REASONER FRAME NORMALIZATION
        #
        # StructuralSpanReasoner always solves a zero-based
        # domain:
        #
        #     0.0 -> width
        #     0.0 -> depth
        #
        # Architecture-first anchors are stored in the
        # authoritative floor-local frame and may therefore
        # have a non-zero / negative origin.
        #
        # Convert them to the same zero-based frame before
        # span reasoning.
        # ==================================================

        x_anchors = []


        for anchor in raw_x_anchors:

            try:

                normalized_anchor = (
                    float(
                        anchor
                    )
                    -
                    origin_x
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            if (
                normalized_anchor
                <
                -1e-9

                or

                normalized_anchor
                >
                float(
                    width
                )
                +
                1e-9
            ):

                continue


            x_anchors.append(
                normalized_anchor
            )


        y_anchors = []


        for anchor in raw_y_anchors:

            try:

                normalized_anchor = (
                    float(
                        anchor
                    )
                    -
                    origin_y
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            if (
                normalized_anchor
                <
                -1e-9

                or

                normalized_anchor
                >
                float(
                    depth
                )
                +
                1e-9
            ):

                continue


            y_anchors.append(
                normalized_anchor
            )


        x_anchors = sorted(
            set(
                x_anchors
            )
        )


        y_anchors = sorted(
            set(
                y_anchors
            )
        )


        print(
            "\n====== STRUCTURAL SPAN FRAME DEBUG ======"
        )

        print(
            "DOMAIN ORIGIN:",
            origin_x,
            origin_y
        )

        print(
            "DOMAIN SIZE:",
            width,
            depth
        )

        print(
            "RAW X ANCHORS:",
            raw_x_anchors
        )

        print(
            "NORMALIZED X ANCHORS:",
            x_anchors
        )

        print(
            "RAW Y ANCHORS:",
            raw_y_anchors
        )

        print(
            "NORMALIZED Y ANCHORS:",
            y_anchors
        )

        print(
            "========================================="
        )


        x_solution = self.span_reasoner.solve(
            width,
            x_anchors
        )


        y_solution = self.span_reasoner.solve(
            depth,
            y_anchors
        )


        x_values = x_solution.get(
            "axis",
            []
        )


        y_values = y_solution.get(
            "axis",
            []
        )

        # ==================================================
        # STRUCTURAL DOMAIN ORIGIN v1.0
        #
        # StructuralSpanReasoner solves axis coordinates
        # relative to a zero-based domain.
        #
        # Architecture-first structural geometry may have
        # a non-zero floor-local origin.
        #
        # Therefore the solved local axes are translated
        # back into the authoritative architectural
        # floor-local coordinate frame here.
        # ==================================================

        resolved_x_values = []


        for x_value in x_values:

            try:

                resolved_x_values.append(
                    float(
                        x_value
                    )
                    +
                    origin_x
                )

            except (
                TypeError,
                ValueError
            ):

                continue


        resolved_y_values = []


        for y_value in y_values:

            try:

                resolved_y_values.append(
                    float(
                        y_value
                    )
                    +
                    origin_y
                )

            except (
                TypeError,
                ValueError
            ):

                continue


        x_values = resolved_x_values

        y_values = resolved_y_values


        points = []

        seen = set()


        for x in x_values:

            for y in y_values:


                key = (
                    round(x, 3),
                    round(y, 3)
                )


                if key in seen:
                    continue


                point = {

                    "x":
                        x,

                    "y":
                        y,

                    "reference":
                        "corner",

                    "source":
                        "architectural_span_reasoning",

                    "reason":
                        "adaptive_structural_axis_intersection"

                }


                if self._inside_protected_zone(
                    point,
                    protected
                ):
                    continue


                seen.add(
                    key
                )


                points.append(
                    point
                )


        span_candidates = [

            value

            for value in [

                x_solution.get(
                    "span"
                ),

                y_solution.get(
                    "span"
                )

            ]

            if isinstance(
                value,
                (int, float)
            )
            and
            value > 0

        ]


        selection_constraints = {}


        if span_candidates:

            selection_constraints[
                "max_span"
            ] = max(
                span_candidates
            )


        selection = self.point_selector.select(
            points,
            architectural_model={
                "building": {
                    "width":
                        width,

                    "depth":
                        depth,

                    "origin_x":
                        origin_x,

                    "origin_y":
                        origin_y
                }
            },
            protected_zones=protected,
            constraints=selection_constraints
        )


        selected_points = selection.get(
            "selected_points",
            []
        )


        return selected_points



    # ==================================================
    # ADAPTIVE AXIS
    # ==================================================

    def _adaptive_axis(
        self,
        length
    ):


        if length <= 0:

            return []


        values = [0]


        step = 4


        current = step


        while current < length:


            values.append(
                current
            )


            current += step


        if values[-1] != length:

            values.append(
                length
            )


        return values

    # ==================================================
    # FLOOR STRUCTURAL SYSTEMS
    # BASE GRID + FLOOR MASK
    # ==================================================

    def _build_floor_structural_systems(
        self,
        levels,
        support_domains,
        columns,
        beams
    ):

        systems = {}


        support_domains = (
            support_domains
            if isinstance(
                support_domains,
                list
            )
            else []
        )


        columns = (
            columns
            if isinstance(
                columns,
                list
            )
            else []
        )


        beams = (
            beams
            if isinstance(
                beams,
                list
            )
            else []
        )


        domain_by_floor = {}


        for domain in support_domains:

            if not isinstance(
                domain,
                dict
            ):

                continue


            floor = domain.get(
                "floor"
            )


            if not floor:

                continue


            domain_by_floor[
                floor
            ] = domain


        level_names = []


        for level in levels or []:

            if not isinstance(
                level,
                dict
            ):

                continue


            level_name = level.get(
                "name"
            )


            if level_name:

                level_names.append(
                    level_name
                )


        # If vertical levels are incomplete, preserve
        # architectural support-domain floors.
        for floor_name in domain_by_floor.keys():

            if floor_name not in level_names:

                level_names.append(
                    floor_name
                )


        previous_columns = []


        for floor_index, floor_name in enumerate(
            level_names
        ):

            support_domain = domain_by_floor.get(
                floor_name
            )


            # --------------------------------------------------
            # GROUND / BASE STRUCTURAL FLOOR
            #
            # Base topology is already resolved by the main
            # structural grid. Do not redesign it here.
            # --------------------------------------------------

            if floor_index == 0:

                floor_columns = [

                    dict(
                        column
                    )

                    for column in columns

                    if isinstance(
                        column,
                        dict
                    )

                ]


                floor_beams = [

                    dict(
                        beam
                    )

                    for beam in beams

                    if isinstance(
                        beam,
                        dict
                    )

                ]


                removed_columns = []

                removed_beams = []


                for column in floor_columns:

                    column[
                        "structural_floor"
                    ] = floor_name

                    column[
                        "vertical_continuity"
                    ] = "base_support"


                for beam in floor_beams:

                    beam[
                        "structural_floor"
                    ] = floor_name

                    beam[
                        "vertical_continuity"
                    ] = "base_support"


            else:

                floor_columns = []

                removed_columns = []


                # --------------------------------------------------
                # COLUMN INHERITANCE
                #
                # Upper floors inherit the previous/base column
                # topology. A column disappears only when its
                # physical footprint no longer lies within the
                # architectural support domain.
                # --------------------------------------------------

                for column in previous_columns:

                    if not isinstance(
                        column,
                        dict
                    ):

                        continue


                    if (
                        support_domain
                        and
                        not self._column_inside_support_domain(
                            column,
                            support_domain
                        )
                    ):

                        removed_column = dict(
                            column
                        )


                        removed_column[
                            "removed_on_floor"
                        ] = floor_name


                        removed_column[
                            "removal_reason"
                        ] = (
                            "outside_floor_support_domain"
                        )


                        removed_columns.append(
                            removed_column
                        )


                        continue


                    inherited_column = dict(
                        column
                    )


                    inherited_column[
                        "structural_floor"
                    ] = floor_name


                    inherited_column[
                        "vertical_continuity"
                    ] = "inherited_from_below"


                    floor_columns.append(
                        inherited_column
                    )


                active_column_ids = {

                    column.get(
                        "id"
                    )

                    for column in floor_columns

                    if column.get(
                        "id"
                    )

                }


                # --------------------------------------------------
                # BEAM INHERITANCE
                #
                # Keep beam topology only where both supporting
                # columns continue to exist on this floor.
                # --------------------------------------------------

                floor_beams = []

                removed_beams = []


                for beam in beams:

                    if not isinstance(
                        beam,
                        dict
                    ):

                        continue


                    start_column = beam.get(
                        "start_column"
                    )

                    end_column = beam.get(
                        "end_column"
                    )


                    if (
                        start_column not in active_column_ids
                        or
                        end_column not in active_column_ids
                    ):

                        removed_beam = dict(
                            beam
                        )


                        removed_beam[
                            "removed_on_floor"
                        ] = floor_name


                        removed_beam[
                            "removal_reason"
                        ] = (
                            "support_column_not_continuous"
                        )


                        removed_beams.append(
                            removed_beam
                        )


                        continue


                    if (
                        support_domain
                        and
                        not self._beam_inside_support_domain(
                            beam,
                            support_domain
                        )
                    ):

                        removed_beam = dict(
                            beam
                        )


                        removed_beam[
                            "removed_on_floor"
                        ] = floor_name


                        removed_beam[
                            "removal_reason"
                        ] = (
                            "outside_floor_support_domain"
                        )


                        removed_beams.append(
                            removed_beam
                        )


                        continue


                    inherited_beam = dict(
                        beam
                    )


                    inherited_beam[
                        "structural_floor"
                    ] = floor_name


                    inherited_beam[
                        "vertical_continuity"
                    ] = "inherited_from_below"


                    floor_beams.append(
                        inherited_beam
                    )


            systems[
                floor_name
            ] = {

                "floor":
                    floor_name,

                "mode":
                    (
                        "base_structural_grid"
                        if floor_index == 0
                        else "vertical_grid_inheritance"
                    ),

                "support_domain":
                    (
                        dict(
                            support_domain
                        )
                        if isinstance(
                            support_domain,
                            dict
                        )
                        else None
                    ),

                "columns":
                    floor_columns,

                "beams":
                    floor_beams,

                "removed_columns":
                    removed_columns,

                "removed_beams":
                    removed_beams,

                "removed_column_count":
                    len(
                        removed_columns
                    ),

                "removed_beam_count":
                    len(
                        removed_beams
                    ),

                "column_count":
                    len(
                        floor_columns
                    ),

                "beam_count":
                    len(
                        floor_beams
                    ),

                "topology_mode":
                    (
                        "base_structural_grid"
                        if floor_index == 0
                        else "vertical_grid_inheritance"
                    )

            }


            previous_columns = floor_columns


        return systems

    # ==================================================
    # POINT IN POLYGON
    # BOUNDARY-INCLUSIVE
    # ==================================================

    def _point_in_polygon(
        self,
        x,
        y,
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


        try:

            px = float(
                x
            )

            py = float(
                y
            )

        except (
            TypeError,
            ValueError
        ):

            return False


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
        # BOUNDARY COUNTS AS INSIDE
        #
        # Structural support-domain masking must retain
        # members that lie exactly on the floor boundary.
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


            if self._point_on_segment(
                px,
                py,
                point_a[0],
                point_a[1],
                point_b[0],
                point_b[1]
            ):

                return True


        # ----------------------------------------------
        # RAY CASTING
        # ----------------------------------------------

        inside = False


        j = (
            len(
                valid_polygon
            )
            -
            1
        )


        for i in range(
            len(
                valid_polygon
            )
        ):

            xi = valid_polygon[
                i
            ][0]

            yi = valid_polygon[
                i
            ][1]

            xj = valid_polygon[
                j
            ][0]

            yj = valid_polygon[
                j
            ][1]


            intersects = (

                (
                    yi > py
                )
                !=
                (
                    yj > py
                )

                and

                px
                <
                (
                    (
                        xj
                        -
                        xi
                    )
                    *
                    (
                        py
                        -
                        yi
                    )
                    /
                    (
                        (
                            yj
                            -
                            yi
                        )
                        if abs(
                            yj
                            -
                            yi
                        ) > 1e-12
                        else 1e-12
                    )
                    +
                    xi
                )

            )


            if intersects:

                inside = not inside


            j = i


        return inside


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
        by,
        tolerance=1e-9
    ):

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


        min_x = (
            min(
                ax,
                bx
            )
            -
            tolerance
        )

        max_x = (
            max(
                ax,
                bx
            )
            +
            tolerance
        )

        min_y = (
            min(
                ay,
                by
            )
            -
            tolerance
        )

        max_y = (
            max(
                ay,
                by
            )
            +
            tolerance
        )


        return (

            min_x
            <=
            px
            <=
            max_x

            and

            min_y
            <=
            py
            <=
            max_y

        )


    # ==================================================
    # SUPPORT DOMAIN CHECKS
    # ==================================================

    def _column_inside_support_domain(
        self,
        column,
        support_domain
    ):

        polygon = support_domain.get(
            "source_polygon"
        )


        if not (
            isinstance(
                polygon,
                list
            )
            and len(
                polygon
            ) >= 3
        ):

            return True


        x = float(
            column.get(
                "x",
                0.0
            )
        )

        y = float(
            column.get(
                "y",
                0.0
            )
        )


        width = float(
            column.get(
                "width",
                0.0
            )
            or 0.0
        )


        depth = float(
            column.get(
                "depth",
                0.0
            )
            or 0.0
        )


        # ==================================================
        # VERTICAL STRUCTURAL CONTINUITY REFERENCE v1.0
        #
        # Floor support-domain masking must decide whether
        # the structural column line continues vertically.
        #
        # A boundary column may physically overlap the floor
        # edge because its section has finite width/depth.
        # Requiring all four section corners to remain inside
        # the upper-floor footprint incorrectly deletes valid
        # vertically continuous columns.
        #
        # Therefore the physical section center is used as
        # the continuation reference.
        # ==================================================

        center_x = (
            x
            +
            width / 2.0
        )

        center_y = (
            y
            +
            depth / 2.0
        )


        return self._point_in_polygon(
            center_x,
            center_y,
            polygon
        )


    def _beam_inside_support_domain(
        self,
        beam,
        support_domain
    ):

        polygon = support_domain.get(
            "source_polygon"
        )


        if not (
            isinstance(
                polygon,
                list
            )
            and len(
                polygon
            ) >= 3
        ):

            return True


        start = beam.get(
            "start"
        )

        end = beam.get(
            "end"
        )


        if (
            not isinstance(
                start,
                (list, tuple)
            )
            or
            len(
                start
            ) < 2
            or
            not isinstance(
                end,
                (list, tuple)
            )
            or
            len(
                end
            ) < 2
        ):

            return False


        # ==================================================
        # BEAM SUPPORT-DOMAIN CONTINUITY v1.0
        #
        # Structural beams inherit the vertically
        # coordinated master topology.
        #
        # The raw beam endpoints represent structural
        # reference points. Boundary columns may be shifted
        # inward by their physical section dimensions, so
        # requiring the raw endpoint itself to remain inside
        # the upper-floor polygon can incorrectly remove a
        # valid inherited beam.
        #
        # Use points slightly inside the beam axis for the
        # floor-support test while preserving the original
        # beam geometry and topology.
        # ==================================================

        start_x = float(
            start[0]
        )

        start_y = float(
            start[1]
        )

        end_x = float(
            end[0]
        )

        end_y = float(
            end[1]
        )


        dx = (
            end_x
            -
            start_x
        )

        dy = (
            end_y
            -
            start_y
        )


        length = (
            dx * dx
            +
            dy * dy
        ) ** 0.5


        if length <= 1e-9:

            return False


        # Move the domain-test points a small structural
        # distance inside the member axis.
        #
        # This affects only support-domain classification.
        # Beam geometry itself is NOT changed.

        inset = min(
            0.20,
            length * 0.10
        )


        unit_x = (
            dx
            /
            length
        )

        unit_y = (
            dy
            /
            length
        )


        test_start_x = (
            start_x
            +
            unit_x * inset
        )

        test_start_y = (
            start_y
            +
            unit_y * inset
        )


        test_end_x = (
            end_x
            -
            unit_x * inset
        )

        test_end_y = (
            end_y
            -
            unit_y * inset
        )


        return (

            self._point_in_polygon(
                test_start_x,
                test_start_y,
                polygon
            )

            and

            self._point_in_polygon(
                test_end_x,
                test_end_y,
                polygon
            )

        )



    # ==================================================
    # COLUMN GENERATOR
    # ==================================================

    def _generate_columns(
        self,
        grid,
        protected
    ):


        columns = []


        for index, point in enumerate(grid):


            columns.append(

                {

                    "id":
                        f"C-{index+1}",


                    "x":
                        point["x"],


                    "y":
                        point["y"],


                    "z":
                        0,


                    "type":
                        "structural_column",


                    "reference":
                        "corner",


                    "zone":
                        point.get(
                            "source"
                        )

                }

            )


        return columns




    # ==================================================
    # BEAM GENERATOR
    # ==================================================

    def _generate_beams(
        self,
        grid,
        vertical_section,
        protected
    ):


        beams = []


        for i in range(
            len(grid)-1
        ):


            a = grid[i]

            b = grid[i+1]


            if not self._beam_crosses_protected(
                a,
                b,
                protected
            ):


                beams.append(

                    {

                        "id":
                            f"B-{i+1}",


                        "start":
                            [
                                a["x"],
                                a["y"]
                            ],


                        "end":
                            [
                                b["x"],
                                b["y"]
                            ],


                        "type":
                            "adaptive_beam"

                    }

                )


        return beams




    # ==================================================
    # GEOMETRY CHECKS
    # ==================================================

    def _inside_protected_zone(
        self,
        point,
        protected
    ):

        x = float(
            point.get(
                "x",
                0.0
            )
        )

        y = float(
            point.get(
                "y",
                0.0
            )
        )


        for zone in protected:

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


            # ==================================================
            # STRUCTURAL-FRAME PROTECTED POLYGON
            #
            # Structural grid generation occurs in the
            # architectural_metric_floor_local frame.
            #
            # Therefore source_polygon is authoritative here.
            #
            # Resolved parcel-local polygon is preserved only
            # as a fallback for legacy / already-resolved input.
            # ==================================================

            polygon = zone.get(
                "source_polygon"
            )


            if not (
                isinstance(
                    polygon,
                    list
                )
                and len(
                    polygon
                ) >= 3
            ):

                polygon = zone.get(
                    "polygon"
                )


            if (
                isinstance(
                    polygon,
                    list
                )
                and len(
                    polygon
                ) >= 3
            ):

                valid_polygon = []


                for polygon_point in polygon:

                    if not (
                        isinstance(
                            polygon_point,
                            (list, tuple)
                        )
                        and len(
                            polygon_point
                        ) >= 2
                    ):

                        continue


                    try:

                        px = float(
                            polygon_point[0]
                        )

                        py = float(
                            polygon_point[1]
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        continue


                    valid_polygon.append(
                        [
                            px,
                            py
                        ]
                    )


                if len(
                    valid_polygon
                ) >= 3:

                    inside = False

                    j = (
                        len(
                            valid_polygon
                        )
                        -
                        1
                    )


                    for i in range(
                        len(
                            valid_polygon
                        )
                    ):

                        xi = valid_polygon[
                            i
                        ][0]

                        yi = valid_polygon[
                            i
                        ][1]

                        xj = valid_polygon[
                            j
                        ][0]

                        yj = valid_polygon[
                            j
                        ][1]


                        # --------------------------------------
                        # POINT ON POLYGON EDGE
                        # --------------------------------------

                        dx = xj - xi

                        dy = yj - yi


                        cross = (
                            (x - xi) * dy
                            -
                            (y - yi) * dx
                        )


                        if abs(
                            cross
                        ) <= 1e-9:

                            dot = (
                                (x - xi) * (x - xj)
                                +
                                (y - yi) * (y - yj)
                            )


                            if dot <= 1e-9:

                                return True


                        # --------------------------------------
                        # RAY CASTING
                        # --------------------------------------

                        intersects = (

                            (
                                yi > y
                            )
                            !=
                            (
                                yj > y
                            )

                        )


                        if intersects:

                            denominator = (
                                yj
                                -
                                yi
                            )


                            if abs(
                                denominator
                            ) > 1e-12:

                                edge_x = (

                                    (
                                        xj
                                        -
                                        xi
                                    )
                                    *
                                    (
                                        y
                                        -
                                        yi
                                    )
                                    /
                                    denominator
                                    +
                                    xi

                                )


                                if x < edge_x:

                                    inside = not inside


                        j = i


                    if inside:

                        return True


                    # Polygon exists and is authoritative.
                    # Do not fall through to its bounding box,
                    # because that would recreate the rotated
                    # rectangle false-positive problem.

                    continue


            # ==================================================
            # LEGACY RECTANGULAR FALLBACK
            # ==================================================

            bounds = zone.get(
                "source_bounds"
            )


            if not (
                isinstance(
                    bounds,
                    (list, tuple)
                )
                and len(
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


            bx, by, bw, bh = bounds


            try:

                bx = float(
                    bx
                )

                by = float(
                    by
                )

                bw = float(
                    bw
                )

                bh = float(
                    bh
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            if (

                bx <= x <= bx + bw

                and

                by <= y <= by + bh

            ):

                return True


        return False




    def _beam_crosses_protected(
        self,
        start,
        end,
        protected
    ):


        # نسخه اول:
        # جلوگیری از تیر داخل محدوده ممنوع

        for zone in protected:


            bx, by, w, h = zone["bounds"]


            for p in [
                start,
                end
            ]:


                if (

                    bx <= p["x"] <= bx+w

                    and

                    by <= p["y"] <= by+h

                ):

                    return True


        return False
