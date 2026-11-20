"""
ArchitectOS Architectural Geometry Engine v2.1

Generates architectural geometry intent:
spaces, boundaries, openings, slabs,
and vertical elements.
"""
import math


from core.architecture.reasoning.opening_reasoner_v2 import (
    OpeningReasonerV2
)

from core.architecture.geometry.architectural_boundary_segment_resolver_v1 import (
    ArchitecturalBoundarySegmentResolverV1
)

from core.architecture.geometry.architectural_physical_wall_resolver_v1 import (
    ArchitecturalPhysicalWallResolverV1
)

from core.architecture.geometry.architectural_opening_host_resolver_v1 import (
    ArchitecturalOpeningHostResolverV1
)
from core.architecture.geometry.architectural_physical_opening_resolver_v1 import (
    ArchitecturalPhysicalOpeningResolverV1
)
from core.architecture.geometry.architectural_stair_geometry_resolver_v1 import (
    ArchitecturalStairGeometryResolverV1
)
from core.architecture.geometry.exterior_entrance_geometry_resolver_v1 import (
    ExteriorEntranceGeometryResolverV1
)
from core.architecture.geometry.main_entrance_opening_placement_selector_v1 import (
    MainEntranceOpeningPlacementSelectorV1
)
from core.architecture.geometry.pedestrian_access_geometry_resolver_v1 import (
    PedestrianAccessGeometryResolverV1
)
from core.architecture.reasoning.pedestrian_site_access_design_reasoner_v1 import (
    PedestrianSiteAccessDesignReasonerV1
)



class ArchitecturalGeometryEngineV2:


    VERSION = "2.1"



    def __init__(self):

        print(
            "🏗️ ARCHITECTURAL GEOMETRY ENGINE V2.1 ONLINE"
        )


        self.opening_reasoner = OpeningReasonerV2()

        self.boundary_segment_resolver = (
            ArchitecturalBoundarySegmentResolverV1()
        )

        self.physical_wall_resolver = (
            ArchitecturalPhysicalWallResolverV1()
        )

        self.opening_host_resolver = (
            ArchitecturalOpeningHostResolverV1()
        )

        self.physical_opening_resolver = ArchitecturalPhysicalOpeningResolverV1()

        self.stair_geometry_resolver = ArchitecturalStairGeometryResolverV1()
        self.exterior_entrance_geometry_resolver = ExteriorEntranceGeometryResolverV1()
        self.main_entrance_opening_placement_selector = (
            MainEntranceOpeningPlacementSelectorV1()
        )
        self.pedestrian_access_geometry_resolver = (
            PedestrianAccessGeometryResolverV1()
        )
        self.pedestrian_site_access_design_reasoner = (
            PedestrianSiteAccessDesignReasonerV1()
        )

    @staticmethod
    def _place_outer_faces_on_buildable_limits(walls):
        """Interpret the generated envelope as an outer-face limit, not a centreline."""
        exterior = [wall for wall in walls if isinstance(wall, dict) and wall.get("is_exterior") is True]
        points = [point for wall in exterior for point in (wall.get("start"), wall.get("end"))
                  if isinstance(point, (list, tuple)) and len(point) >= 2]
        if not points:
            return walls
        min_x, max_x = min(float(p[0]) for p in points), max(float(p[0]) for p in points)
        min_y, max_y = min(float(p[1]) for p in points), max(float(p[1]) for p in points)
        tolerance = 1e-7
        for wall in walls:
            if not isinstance(wall, dict):
                continue
            thickness = wall.get("thickness")
            if not isinstance(thickness, (int, float)) or thickness <= 0:
                continue
            inset = float(thickness) / 2.0
            for key in ("start", "end"):
                point = wall.get(key)
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                x, y = float(point[0]), float(point[1])
                if abs(x - min_x) <= tolerance:
                    x = min_x + inset
                elif abs(x - max_x) <= tolerance:
                    x = max_x - inset
                if abs(y - min_y) <= tolerance:
                    y = min_y + inset
                elif abs(y - max_y) <= tolerance:
                    y = max_y - inset
                wall[key] = [x, y]
            if wall.get("is_exterior") is True:
                wall["placement_reference"] = "physical_outer_face_on_buildable_limit"
        return walls



    def generate(
        self,
        geometry_intent
    ):


        result = {

            "version":
                self.VERSION,

            "spaces":
                [],

            "boundaries":
                [],

            "boundary_segments":
                [],

            "physical_walls":
                [],

            "openings":
                [],

            "slabs":
                [],

            "floor_geometry":
                [],

            "roof_geometry":
                {},

            "vertical_geometry":
                [],

            "slab_openings":
                [],

            "site_geometry":
                [],

            "parcel_placement":
                {},

            "coordinate_frame":
                {}

        }

        result["project_requirements"] = dict(
            geometry_intent.get("project_requirements", {})
        ) if isinstance(geometry_intent.get("project_requirements"), dict) else {}

        site_geometry_intent = geometry_intent.get("site_geometry_intent", {})
        if isinstance(site_geometry_intent, dict):
            result["site_geometry"] = dict(site_geometry_intent)

        # ==============================================
        # PARCEL PLACEMENT TRANSFORM v1.0
        #
        # GeometryIntent preserves floor-local metric
        # coordinates and carries parcel placement as
        # a separate transform.
        #
        # ArchitecturalGeometry resolves parcel-local
        # coordinates without destroying source x / y.
        # ==============================================

        parcel_placement = geometry_intent.get(
            "parcel_placement",
            {}
        )


        if not isinstance(
            parcel_placement,
            dict
        ):

            parcel_placement = {}


        translation = parcel_placement.get(
            "translation",
            {}
        )


        if not isinstance(
            translation,
            dict
        ):

            translation = {}


        translation_applied = bool(
            parcel_placement.get(
                "translation_applied",
                False
            )
        )


        parcel_dx = translation.get(
            "dx",
            0.0
        )


        parcel_dy = translation.get(
            "dy",
            0.0
        )


        try:

            parcel_dx = float(
                parcel_dx
                or 0.0
            )

            parcel_dy = float(
                parcel_dy
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            parcel_dx = 0.0
            parcel_dy = 0.0
            translation_applied = False

        rotation_applied = bool(
            parcel_placement.get(
                "rotation_applied",
                False
            )
        )


        rotation_degrees = parcel_placement.get(
            "rotation",
            0.0
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
            rotation_applied = False


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


        rigid_transform_available = (

            rotation_applied

            and isinstance(
                source_pivot_x,
                (int, float)
            )

            and isinstance(
                source_pivot_y,
                (int, float)
            )

            and isinstance(
                target_pivot_x,
                (int, float)
            )

            and isinstance(
                target_pivot_y,
                (int, float)
            )

        )


        rotation_radians = math.radians(
            rotation_degrees
        )

        rotation_cos = math.cos(
            rotation_radians
        )

        rotation_sin = math.sin(
            rotation_radians
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


        result[
            "parcel_placement"
        ] = dict(
            parcel_placement
        )


        result[
            "coordinate_frame"
        ] = {

            "source":
                "architectural_metric_floor_local",

            "resolved":
                (
                    "parcel_local"
                    if (
                        translation_applied
                        or
                        rigid_transform_available
                    )
                    else
                    "architectural_metric_floor_local"
                ),

            "translation_applied":
                translation_applied,

            "rotation_applied":
                rotation_applied,

            "rotation_degrees":
                rotation_degrees,

            "rigid_transform_available":
                rigid_transform_available,

            "source_pivot":
                dict(
                    source_pivot
                )
                if source_pivot
                else None,

            "target_pivot":
                dict(
                    target_pivot
                )
                if target_pivot
                else None,

            "translation":
                {
                    "dx":
                        parcel_dx,

                    "dy":
                        parcel_dy
                }
        }




        # ==================================
        # SPACE GEOMETRY
        # ==================================


        for space in geometry_intent.get(
            "spaces",
            []
        ):


            requirements = space.get(
                "design_requirements",
                {}
            )



            source_x = space.get(
                "x"
            )


            source_y = space.get(
                "y"
            )


            parcel_x = None
            parcel_y = None


            if (
                isinstance(
                    source_x,
                    (int, float)
                )
                and
                isinstance(
                    source_y,
                    (int, float)
                )
            ):

                transformed_origin = (
                    transform_point_to_parcel(
                        source_x,
                        source_y
                    )
                )


                if transformed_origin is not None:

                    parcel_x = (
                        transformed_origin[0]
                    )

                    parcel_y = (
                        transformed_origin[1]
                    )

            # ==============================================
            # ROOM FOOTPRINT RESOLUTION v1.0
            #
            # Resolve real parcel-local rectangular room
            # footprint only when:
            #
            # - parcel coordinates are available
            # - width / depth are resolved
            #
            # No dimensions are invented here.
            # ==============================================

            room_width = space.get(
                "width"
            )

            room_depth = space.get(
                "depth"
            )


            room_footprint = None


            if (
                isinstance(
                    parcel_x,
                    (int, float)
                )
                and
                isinstance(
                    parcel_y,
                    (int, float)
                )
                and
                isinstance(
                    room_width,
                    (int, float)
                )
                and
                isinstance(
                    room_depth,
                    (int, float)
                )
                and
                float(
                    room_width
                ) > 0
                and
                float(
                    room_depth
                ) > 0
            ):

                footprint_x = float(
                    parcel_x
                )

                footprint_y = float(
                    parcel_y
                )

                footprint_width = float(
                    room_width
                )

                footprint_depth = float(
                    room_depth
                )

                source_room_points = [

                    [
                        float(
                            source_x
                        ),
                        float(
                            source_y
                        )
                    ],

                    [
                        float(
                            source_x
                        )
                        +
                        footprint_width,

                        float(
                            source_y
                        )
                    ],

                    [
                        float(
                            source_x
                        )
                        +
                        footprint_width,

                        float(
                            source_y
                        )
                        +
                        footprint_depth
                    ],

                    [
                        float(
                            source_x
                        ),

                        float(
                            source_y
                        )
                        +
                        footprint_depth
                    ]

                ]


                transformed_room_points = []


                for point in source_room_points:

                    transformed_point = (
                        transform_point_to_parcel(
                            point[0],
                            point[1]
                        )
                    )


                    if transformed_point is None:

                        transformed_room_points = []

                        break


                    transformed_room_points.append(
                        transformed_point
                    )


               

                if transformed_room_points:

                    transformed_x_values = [

                        point[0]

                        for point in transformed_room_points

                    ]

                    transformed_y_values = [

                        point[1]

                        for point in transformed_room_points

                    ]


                    footprint_min_x = min(
                        transformed_x_values
                    )

                    footprint_max_x = max(
                        transformed_x_values
                    )

                    footprint_min_y = min(
                        transformed_y_values
                    )

                    footprint_max_y = max(
                        transformed_y_values
                    )


                    room_footprint = {

                        "type":
                            (
                                "rotated_rectangle"
                                if rigid_transform_available
                                else "rectangle"
                            ),

                        "coordinate_mode":
                            (
                                "parcel_local"
                                if (
                                    rigid_transform_available
                                    or
                                    translation_applied
                                )
                                else space.get(
                                    "coordinate_mode"
                                )
                            ),

                        "points":
                            transformed_room_points,

                        "min_x":
                            footprint_min_x,

                        "min_y":
                            footprint_min_y,

                        "max_x":
                            footprint_max_x,

                        "max_y":
                            footprint_max_y,

                        "bounding_width":
                            (
                                footprint_max_x
                                -
                                footprint_min_x
                            ),

                        "bounding_depth":
                            (
                                footprint_max_y
                                -
                                footprint_min_y
                            ),

                        "width":
                            footprint_width,

                        "depth":
                            footprint_depth,

                        "area":
                            (
                                footprint_width
                                *
                                footprint_depth
                            ),

                        "rotation_degrees":
                            (
                                rotation_degrees
                                if rigid_transform_available
                                else 0.0
                            ),

                        "source_points":
                            source_room_points,

                        "geometry_status":
                            (
                                "resolved_rotated_room_footprint"
                                if rigid_transform_available
                                else "resolved_room_footprint"
                            )

                    }

                


            result["spaces"].append(

                {

                    "name":
                        space.get(
                            "name"
                        ),

                    "floor":
                        space.get(
                            "floor"
                        ),

                    "elevation":
                        space.get(
                            "elevation"
                        ),

                    "bottom":
                        space.get(
                            "bottom"
                        ),

                    "top":
                        space.get(
                            "top"
                        ),

                    "design_requirements":
                        dict(
                            space.get(
                                "design_requirements",
                                {}
                            )
                        ),

                    "type":
                        "room_volume",

                    "shape":
                        space.get(
                            "shape_intent"
                        ),

                    "height":
                        space.get(
                            "height"
                        ),

                    "level_span_status":
                        space.get(
                            "level_span_status"
                        ),

                    # --------------------------------------
                    # ARCHITECTURAL SEMANTIC CONTRACT
                    # --------------------------------------

                    "design_requirements":
                        dict(
                            requirements
                        ),

                    "protected_zone":
                        bool(
                            requirements.get(
                                "protected_zone",
                                False
                            )
                        ),

                    "placement_scope":
                        requirements.get(
                            "placement_scope"
                        ),

                    "access_requirement":
                        requirements.get(
                            "access_requirement"
                        ),

                    # --------------------------------------
                    # SOURCE ARCHITECTURAL COORDINATES
                    # --------------------------------------

                    "x":
                        source_x,

                    "y":
                        source_y,

                    "coordinate_mode":
                        space.get(
                            "coordinate_mode"
                        ),

                    # --------------------------------------
                    # RESOLVED PARCEL COORDINATES
                    # --------------------------------------

                    "parcel_x":
                        parcel_x,

                    "parcel_y":
                        parcel_y,

                    # --------------------------------------
                    # RESOLVED ARCHITECTURAL DIMENSIONS
                    #
                    # GeometryIntent is authoritative here.
                    # Preserve resolved room extents into
                    # ArchitecturalGeometry.
                    # --------------------------------------

                    "width":
                        space.get(
                            "width"
                        ),

                    "depth":
                        space.get(
                            "depth"
                        ),

                    "resolved_dimensions":
                        (
                            dict(
                                space.get(
                                    "resolved_dimensions"
                                )
                            )
                            if isinstance(
                                space.get(
                                    "resolved_dimensions"
                                ),
                                dict
                            )
                            else None
                        ),

                    "resolved_coordinate_mode":
                        (
                            "parcel_local"
                            if (
                                parcel_x is not None
                                and
                                parcel_y is not None
                                and
                                (
                                    translation_applied
                                    or
                                    rigid_transform_available
                                )
                            )
                            else space.get(
                                "coordinate_mode"
                            )
                        ),

                    "footprint":
                        room_footprint,

                    "geometry_status":
                        (
                            room_footprint.get(
                                "geometry_status",
                                "resolved_room_footprint"
                            )
                            if isinstance(
                                room_footprint,
                                dict
                            )
                            else "room_footprint_pending"
                        ),

                    "parcel_translation":
                        {
                            "dx":
                                parcel_dx,

                            "dy":
                                parcel_dy
                        }
                        if translation_applied
                        else None,

                    "requirements":
                        requirements

                }

            )





            # ==================================
            # BOUNDARY INTENT
            # ==================================


            result["boundaries"].append(

                {


                    "space":
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


                    "type":
                        "wall_boundary",


                    "role":
                        requirements.get(
                            "role"
                        ),


                    "generation":
                        "resolved_from_space_intent"

                }

            )







            # ==============================================
            # OPENING CONTEXT BRIDGE v1.0
            #
            # Preserve space-level architectural evidence
            # and forward parcel / edge intelligence when
            # GeometryIntent already contains it.
            #
            # No opening decision is invented here.
            # ==============================================

            opening_space = {

                "name":
                    space.get(
                        "name"
                    ),

                "zone":
                    requirements.get(
                        "zone"
                    ),

                "role":
                    requirements.get(
                        "role"
                    ),

                "adjacent_to":
                    space.get(
                        "adjacent_to",
                        requirements.get("adjacent_to", [])
                    ),

                "boundary_condition":
                    requirements.get(
                        "boundary_condition"
                    ),

                "privacy_required":
                    requirements.get(
                        "privacy_required",
                        False
                    ),

                "preferred_edge_index":
                    space.get(
                        "preferred_edge_index",
                        requirements.get(
                            "preferred_edge_index"
                        )
                    ),

                "edge_relation":
                    space.get(
                        "edge_relation",
                        requirements.get(
                            "edge_relation"
                        )
                    ),

                "edge_decision_status":
                    space.get(
                        "edge_decision_status",
                        requirements.get(
                            "edge_decision_status"
                        )
                    ),

                "parcel_relation":
                    space.get(
                        "parcel_relation",
                        requirements.get(
                            "parcel_relation"
                        )
                    ),

                "parcel_edges":
                    space.get(
                        "parcel_edges",
                        requirements.get(
                            "parcel_edges",
                            []
                        )
                    ),

                "parcel_edge_roles":
                    space.get(
                        "parcel_edge_roles",
                        requirements.get(
                            "parcel_edge_roles",
                            []
                        )
                    )

            }


            opening_context = {

                "building_type":
                    geometry_intent.get(
                        "building_type",
                        "residential"
                    ),

                "floor":
                    space.get(
                        "floor"
                    ),

                "level_condition":
                    space.get(
                        "level_condition",
                        "above_grade"
                    ),

                "site_context":
                    space.get(
                        "site_context",
                        requirements.get(
                            "site_context",
                            {}
                        )
                    ),

                "parcel_edge_roles":
                    space.get(
                        "parcel_edge_roles",
                        requirements.get(
                            "parcel_edge_roles",
                            []
                        )
                    )

            }

            print(
                "OPENING INPUT DEBUG:",
                opening_space.get("name"),
                opening_space.get("preferred_edge_index"),
                opening_space.get("edge_relation"),
                opening_space.get("edge_decision_status"),
                opening_space.get("parcel_edges"),
                opening_space.get("parcel_edge_roles")
            )


            opening_result = self.opening_reasoner.resolve(
                opening_space,
                opening_context
            )



            for opening in opening_result.get(

                "openings",

                []

            ):


                opening["space"] = space.get(
                    "name"
                )


                opening["floor"] = space.get(
                    "floor"
                )

                # Opening height is the opening's own dimension. Carry
                # host-level Z under explicit names to avoid conflating
                # the two contracts or calculating absolute opening Z.
                opening["level_bottom"] = space.get(
                    "bottom"
                )

                opening["level_top"] = space.get(
                    "top"
                )

                opening["level_height"] = space.get(
                    "height"
                )

                opening["level_span_status"] = space.get(
                    "level_span_status"
                )


                result["openings"].append(

                    opening

                )


        # ==============================================
        # ARCHITECTURAL BOUNDARY SEGMENTS v1.0
        #
        # Resolve real room-footprint edges into
        # floor-aware boundary segments.
        #
        # IMPORTANT:
        #
        # Legacy result["boundaries"] is preserved
        # unchanged because current BIM consumers map
        # every legacy boundary directly to IfcWall.
        #
        # This new contract is additive only.
        # ==============================================

        result[
            "boundary_segments"
        ] = self.boundary_segment_resolver.resolve(
            result.get(
                "spaces",
                []
            )
        )

        result[
            "physical_walls"
        ] = self.physical_wall_resolver.resolve(
            result.get(
                "boundary_segments",
                []
            ),
            geometry_intent.get(
                "wall_thicknesses",
                geometry_intent.get("architectural_intent", {}).get(
                    "wall_thicknesses", {}
                ) if isinstance(geometry_intent.get("architectural_intent"), dict) else {}
            )
        )
        result["physical_walls"] = self._place_outer_faces_on_buildable_limits(
            result.get("physical_walls", [])
        )

        # ==============================================
        # OPENING HOST CONTRACT v1.0
        #
        # Resolve compatible physical-wall candidates
        # without inventing facade placement.
        #
        # Multiple valid candidates remain pending until
        # architectural/site evidence selects one.
        # ==============================================

        result[
            "openings"
        ] = self.opening_host_resolver.resolve(
            result.get(
                "openings",
                []
            ),
            result.get(
                "physical_walls",
                []
            )
        )



        # ==============================================
        # FLOOR GEOMETRY INTENT CONSUMER v1.0
        #
        # Preserve aggregate floor-level geometry intent.
        #
        # IMPORTANT:
        # This does not invent floor polygons.
        # Actual geometry remains pending until spatial
        # envelope resolution is available.
        # ==============================================

        for floor_intent in geometry_intent.get(
            "floor_geometry_intent",
            []
        ):

            if not isinstance(
                floor_intent,
                dict
            ):

                continue


            source_envelope = floor_intent.get(
                "envelope"
            )


            if not isinstance(
                source_envelope,
                dict
            ):

                source_envelope = None


            parcel_envelope = None


            if source_envelope is not None:

                min_x = source_envelope.get(
                    "min_x"
                )

                min_y = source_envelope.get(
                    "min_y"
                )

                max_x = source_envelope.get(
                    "max_x"
                )

                max_y = source_envelope.get(
                    "max_y"
                )


                if all(
                    isinstance(
                        value,
                        (int, float)
                    )
                    for value in (
                        min_x,
                        min_y,
                        max_x,
                        max_y
                    )
                ):

                    source_floor_points = [

                        [
                            float(min_x),
                            float(min_y)
                        ],

                        [
                            float(max_x),
                            float(min_y)
                        ],

                        [
                            float(max_x),
                            float(max_y)
                        ],

                        [
                            float(min_x),
                            float(max_y)
                        ]

                    ]


                    transformed_floor_points = []


                    for point in source_floor_points:

                        transformed_point = (
                            transform_point_to_parcel(
                                point[0],
                                point[1]
                            )
                        )


                        if transformed_point is None:

                            transformed_floor_points = []

                            break


                        transformed_floor_points.append(
                            transformed_point
                        )


                    if transformed_floor_points:

                        transformed_x_values = [

                            point[0]

                            for point in transformed_floor_points

                        ]


                        transformed_y_values = [

                            point[1]

                            for point in transformed_floor_points

                        ]


                        resolved_min_x = min(
                            transformed_x_values
                        )

                        resolved_min_y = min(
                            transformed_y_values
                        )

                        resolved_max_x = max(
                            transformed_x_values
                        )

                        resolved_max_y = max(
                            transformed_y_values
                        )


                        source_width = (
                            float(max_x)
                            -
                            float(min_x)
                        )

                        source_depth = (
                            float(max_y)
                            -
                            float(min_y)
                        )


                        parcel_envelope = {

                            "type":
                                (
                                    "rotated_rectangle"
                                    if rigid_transform_available
                                    else "rectangle"
                                ),

                            "points":
                                transformed_floor_points,

                            "source_points":
                                source_floor_points,

                            "min_x":
                                resolved_min_x,

                            "min_y":
                                resolved_min_y,

                            "max_x":
                                resolved_max_x,

                            "max_y":
                                resolved_max_y,

                            "bounding_width":
                                (
                                    resolved_max_x
                                    -
                                    resolved_min_x
                                ),

                            "bounding_depth":
                                (
                                    resolved_max_y
                                    -
                                    resolved_min_y
                                ),

                            "width":
                                source_width,

                            "depth":
                                source_depth,

                            "area":
                                (
                                    source_width
                                    *
                                    source_depth
                                ),

                            "rotation_degrees":
                                (
                                    rotation_degrees
                                    if rigid_transform_available
                                    else 0.0
                                ),

                            "coordinate_mode":
                                (
                                    "parcel_local"
                                    if (
                                        rigid_transform_available
                                        or
                                        translation_applied
                                    )
                                    else source_envelope.get(
                                        "coordinate_mode",
                                        "architectural_metric"
                                    )
                                ),

                            "source_coordinate_mode":
                                source_envelope.get(
                                    "coordinate_mode",
                                    "architectural_metric"
                                ),

                            "status":
                                (
                                    "resolved_rotated_parcel_envelope"
                                    if rigid_transform_available
                                    else (
                                        "resolved_parcel_envelope"
                                        if translation_applied
                                        else source_envelope.get(
                                            "status",
                                            "resolved_metric_envelope"
                                        )
                                    )
                                )

                        }

            # ==============================================
            # FLOOR SLAB GEOMETRY v1.0
            #
            # Slab is a floor-level architectural element.
            #
            # Prefer resolved parcel-local footprint when
            # parcel placement has been resolved.
            #
            # Preserve source floor-local envelope for
            # provenance.
            # ==============================================

            slab_envelope = (
                parcel_envelope
                if parcel_envelope is not None
                else source_envelope
            )


            slab_coordinate_mode = None


            if isinstance(
                slab_envelope,
                dict
            ):

                slab_coordinate_mode = (
                    slab_envelope.get(
                        "coordinate_mode"
                    )
                )


            slab_status = (

                "resolved_rotated_floor_slab"

                if (
                    isinstance(
                        slab_envelope,
                        dict
                    )
                    and
                    slab_envelope.get(
                        "type"
                    )
                    == "rotated_rectangle"
                )

                else (
                    "resolved_floor_slab"

                    if isinstance(
                        slab_envelope,
                        dict
                    )

                    else "floor_slab_geometry_pending"
                )
            )


            result[
                "slabs"
            ].append(

                {

                    "floor":
                        floor_intent.get(
                            "floor"
                        ),

                    "elevation":
                        floor_intent.get(
                            "elevation"
                        ),

                    "bottom":
                        floor_intent.get(
                            "bottom"
                        ),

                    "top":
                        floor_intent.get(
                            "top"
                        ),

                    "type":
                        "floor_slab",

                    "geometry_type":
                        (
                            "rotated_floor_footprint"
                            if (
                                isinstance(
                                    slab_envelope,
                                    dict
                                )
                                and
                                slab_envelope.get(
                                    "type"
                                )
                                == "rotated_rectangle"
                            )
                            else (
                                "rectangular_floor_footprint"
                                if isinstance(
                                    slab_envelope,
                                    dict
                                )
                                else "floor_slab_intent"
                            )
                        ),

                    "footprint":
                        dict(
                            slab_envelope
                        )
                        if isinstance(
                            slab_envelope,
                            dict
                        )
                        else None,

                    "source_envelope":
                        dict(
                            source_envelope
                        )
                        if isinstance(
                            source_envelope,
                            dict
                        )
                        else None,

                    "coordinate_mode":
                        slab_coordinate_mode,

                    "geometry_status":
                        slab_status,

                    "parcel_translation":
                        {
                            "dx":
                                parcel_dx,

                            "dy":
                                parcel_dy
                        }
                        if translation_applied
                        else None,

                    "source":
                        "resolved_floor_geometry"

                }

            )


            result[
                "floor_geometry"
            ].append(

                {

                    "floor":
                        floor_intent.get(
                            "floor"
                        ),

                    "elevation":
                        floor_intent.get(
                            "elevation"
                        ),

                    "bottom":
                        floor_intent.get(
                            "bottom"
                        ),

                    "top":
                        floor_intent.get(
                            "top"
                        ),

                    "height":
                        floor_intent.get(
                            "height"
                        ),

                    "height_status":
                        floor_intent.get(
                            "height_status"
                        ),

                    "space_names":
                        list(
                            floor_intent.get(
                                "space_names",
                                []
                            )
                            or []
                        ),

                    "space_count":
                        floor_intent.get(
                            "space_count",
                            0
                        ),

                    "coordinate_modes":
                        list(
                            floor_intent.get(
                                "coordinate_modes",
                                []
                            )
                            or []
                        ),

                    "dimensions_resolved":
                        bool(
                            floor_intent.get(
                                "dimensions_resolved",
                                False
                            )
                        ),

                    "geometry_type":
                        floor_intent.get(
                            "geometry_type",
                            "aggregate_floor"
                        ),

                    "geometry_status":
                        floor_intent.get(
                            "geometry_status",
                            "spatial_geometry_pending"
                        ),

                    # --------------------------------------
                    # SOURCE FLOOR-LOCAL ENVELOPE
                    # --------------------------------------

                    "envelope":
                        dict(
                            source_envelope
                        )
                        if isinstance(
                            source_envelope,
                            dict
                        )
                        else None,

                    # --------------------------------------
                    # RESOLVED PARCEL-LOCAL ENVELOPE
                    # --------------------------------------

                    "parcel_envelope":
                        parcel_envelope,

                    "resolved_coordinate_mode":
                        (
                            "parcel_local"
                            if (
                                parcel_envelope is not None
                                and
                                translation_applied
                            )
                            else (
                                source_envelope.get(
                                    "coordinate_mode"
                                )
                                if isinstance(
                                    source_envelope,
                                    dict
                                )
                                else None
                            )
                        ),

                    "parcel_translation":
                        {
                            "dx":
                                parcel_dx,

                            "dy":
                                parcel_dy
                        }
                        if translation_applied
                        else None,

                    "source":
                        floor_intent.get(
                            "source",
                            "architectural_geometry_intent"
                        )

                }

            )

        # ==============================================
        # ROOF ENVELOPE RESOLUTION v1.0
        #
        # Resolve the roof footprint from the highest
        # resolved architectural floor.
        #
        # IMPORTANT:
        # - no roof footprint is invented
        # - roof follows the highest resolved floor
        # - parcel-local geometry is preferred when
        #   parcel translation has already been applied
        # ==============================================

        resolved_roof_source = None


        if result.get(
            "floor_geometry"
        ):

            for floor_geometry in reversed(
                result.get(
                    "floor_geometry",
                    []
                )
            ):

                if not isinstance(
                    floor_geometry,
                    dict
                ):

                    continue


                candidate_envelope = floor_geometry.get(
                    "parcel_envelope"
                )


                if not isinstance(
                    candidate_envelope,
                    dict
                ):

                    candidate_envelope = floor_geometry.get(
                        "envelope"
                    )


                if not isinstance(
                    candidate_envelope,
                    dict
                ):

                    continue


                resolved_roof_source = {

                    "floor":
                        floor_geometry.get(
                            "floor"
                        ),

                    "footprint":
                        dict(
                            candidate_envelope
                        ),

                    "coordinate_mode":
                        candidate_envelope.get(
                            "coordinate_mode"
                        ),

                    "parcel_translation":
                        floor_geometry.get(
                            "parcel_translation"
                        )

                }

                break


        # ==============================================
        # ROOF GEOMETRY INTENT CONSUMER v1.0
        #
        # Preserve semantic roof strategy as geometry
        # intent without inventing an unresolved envelope.
        # ==============================================

        roof_intent = geometry_intent.get(
            "roof_geometry_intent",
            {}
        )


        if isinstance(
            roof_intent,
            dict
        ):

            roof_geometry_status = roof_intent.get(
                "geometry_status",
                "roof_envelope_pending"
            )


            roof_source_floor = None
            roof_footprint = None
            roof_coordinate_mode = None
            roof_parcel_translation = None


            if isinstance(
                resolved_roof_source,
                dict
            ):

                roof_source_floor = (
                    resolved_roof_source.get(
                        "floor"
                    )
                )

                roof_footprint = (
                    resolved_roof_source.get(
                        "footprint"
                    )
                )

                roof_coordinate_mode = (
                    resolved_roof_source.get(
                        "coordinate_mode"
                    )
                )

                roof_parcel_translation = (
                    resolved_roof_source.get(
                        "parcel_translation"
                    )
                )


                if isinstance(
                    roof_footprint,
                    dict
                ):

                    roof_geometry_status = (
                        "resolved_roof_envelope"
                    )


            result[
                "roof_geometry"
            ] = {

                "roof_type":
                    roof_intent.get(
                        "roof_type"
                    ),

                "roof_level":
                    roof_intent.get(
                        "roof_level"
                    ),

                "source_level":
                    roof_intent.get(
                        "source_level"
                    ),

                "source_level_top":
                    roof_intent.get(
                        "source_level_top"
                    ),

                "z_contract_status":
                    roof_intent.get(
                        "z_contract_status"
                    ),

                "elements":
                    list(
                        roof_intent.get(
                            "elements",
                            []
                        )
                        or []
                    ),

                "composition":
                    roof_intent.get(
                        "composition"
                    ),

                "skyline":
                    roof_intent.get(
                        "skyline"
                    ),

                "source_floor":
                    roof_source_floor,

                "footprint":
                    dict(
                        roof_footprint
                    )
                    if isinstance(
                        roof_footprint,
                        dict
                    )
                    else None,

                "coordinate_mode":
                    roof_coordinate_mode,

                "parcel_translation":
                    roof_parcel_translation,

                "geometry_status":
                    roof_geometry_status,

                "source":
                    roof_intent.get(
                        "source",
                        "architectural_geometry_intent"
                    )

            }


        # ==================================
        # VERTICAL GEOMETRY
        # ==================================


        for element in geometry_intent.get(

            "vertical_elements",

            []

        ):



            vertical_contract = {

                "name":
                    element.get(
                        "name"
                    ),

                "type":
                    element.get(
                        "geometry_type"
                    ),

                "location_intent":
                    element.get(
                        "location_intent"
                    ),

                "continuous":
                    element.get(
                        "continuous",
                        True
                    ),

                "connects":
                    list(
                        element.get(
                            "connects",
                            []
                        )
                        or []
                    ),

                "served_levels":
                    list(
                        element.get(
                            "served_levels",
                            []
                        )
                        or []
                    ),

                "served_level_spans":
                    [
                        dict(level_span)
                        for level_span in element.get(
                            "served_level_spans",
                            []
                        )
                        if isinstance(level_span, dict)
                    ],

                "bottom":
                    element.get(
                        "bottom"
                    ),

                "top":
                    element.get(
                        "top"
                    ),

                "span_status":
                    element.get(
                        "span_status"
                    ),

                "span_source":
                    element.get(
                        "span_source"
                    ),

                "parameters":
                    dict(
                        element.get(
                            "parameters",
                            {}
                        )
                    ),

                "flights":
                    [
                        dict(flight)
                        for flight in element.get("flights", [])
                        if isinstance(flight, dict)
                    ],

                "reserved_zone":
                    True,

                "clearance_required":
                    True,

                "structural_exclusion":
                    True,

                "reason":
                    element.get(
                        "reason"
                    )

            }

            if vertical_contract.get("type") == "stair_geometry":
                stair_input = dict(element)
                location_intent = vertical_contract.get("location_intent")
                if isinstance(location_intent, dict):
                    location_intent = dict(location_intent)
                    for zone_key in ("protected_zone", "footprint", "polygon"):
                        zone = location_intent.get(zone_key)
                        zone_points = zone.get("points") if isinstance(zone, dict) else zone
                        if isinstance(zone_points, list):
                            transformed = [transform_point_to_parcel(point[0], point[1])
                                           for point in zone_points
                                           if isinstance(point, (list, tuple)) and len(point) >= 2]
                            if len(transformed) == len(zone_points):
                                if isinstance(zone, dict):
                                    zone = dict(zone); zone["points"] = transformed
                                    location_intent[zone_key] = zone
                                else:
                                    location_intent[zone_key] = transformed
                stair_input["location_intent"] = location_intent
                resolved_stair = self.stair_geometry_resolver.resolve(stair_input)
                vertical_contract.update(resolved_stair)
                slab_opening = resolved_stair.get("slab_opening")
                if isinstance(slab_opening, dict) and resolved_stair.get("geometry_status") == "resolved":
                    result["slab_openings"].append(dict(slab_opening))
                    host_level = slab_opening.get("host_level")
                    for slab in result.get("slabs", []):
                        if slab.get("floor") == host_level:
                            slab.setdefault("physical_openings", []).append(dict(slab_opening))
                            slab["opening_aware_geometry"] = True

            result["vertical_geometry"].append(vertical_contract)







        # ==============================================
        # EXTERIOR ENTRANCE SITE GEOMETRY
        # ==============================================
        # This must run after opening-host, wall and floor-footprint resolution.
        site_geometry = result.get("site_geometry", {})
        if isinstance(site_geometry, dict):
            # Design and validation are intentionally separate. Explicit input
            # candidates retain authority; otherwise architecture-first site
            # geometry is used to design a candidate before the validator runs.
            existing_candidates = site_geometry.get("pedestrian_access_candidates", [])
            if not isinstance(existing_candidates, list):
                existing_candidates = []
            access_design = self.pedestrian_site_access_design_reasoner.design(
                site_geometry,
                result.get("floor_geometry", []),
                result.get("spaces", []),
                result.get("physical_walls", []),
            )
            site_geometry["pedestrian_access_design"] = access_design
            selected_access = access_design.get("selected_access")
            if not existing_candidates and isinstance(selected_access, dict):
                site_geometry["pedestrian_access_candidates"] = [selected_access]
            pedestrian_access = self.pedestrian_access_geometry_resolver.resolve(
                site_geometry, result.get("floor_geometry", [])
            )
            site_geometry["pedestrian_access_resolution"] = pedestrian_access
            if pedestrian_access.get("geometry_status") == "resolved":
                site_geometry["pedestrian_access"] = pedestrian_access

        result["openings"] = self.main_entrance_opening_placement_selector.resolve(
            result.get("openings", []),
            result.get("physical_walls", []),
            result.get("spaces", []),
            result.get("floor_geometry", []),
            result.get("site_geometry", {}),
        )

        # The writer consumes only this upstream, opening-aware wall contract.
        # Pending semantics remain available for diagnostics but never become
        # production CAD/BIM geometry.
        result["openings"], result["physical_walls"] = (
            self.physical_opening_resolver.resolve(
                result.get("openings", []), result.get("physical_walls", [])
            )
        )

        site_geometry = result.get("site_geometry", {})
        if isinstance(site_geometry, dict):
            semantic_transition = site_geometry.get("entrance_transition", {})
            if isinstance(semantic_transition, dict) and semantic_transition:
                site_geometry["exterior_entrance"] = (
                    self.exterior_entrance_geometry_resolver.resolve(
                        result, semantic_transition
                    )
                )

        # ==================================
        # GEOMETRY RULES
        # ==================================


        result["geometry_rules"] = [


            "spaces_generate_boundaries",


            "openings_resolved_by_opening_reasoner",


            "doors_follow_escape_direction_rules",


            "windows_follow_daylight_and_privacy_rules",


            "slabs_follow_floor_organization",


            "vertical_elements_require_alignment",


            "vertical_elements_require_clear_zone"

        ]




        return result
