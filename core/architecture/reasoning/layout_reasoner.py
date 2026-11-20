from core.architecture.reasoning.architectural_space_dimension_resolver import (
    ArchitecturalSpaceDimensionResolver
)

from core.architecture.reasoning.external_space_reasoner import (
    ExternalSpaceReasoner
)

from core.architecture.reasoning.spatial_placement_reasoner import (
    SpatialPlacementReasoner
)

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: LayoutReasoner.generate  (internal plan synthesis branch)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class LayoutReasoner:

    VERSION = "1.2"

    def __init__(self):

        print(
            f"📐 LAYOUT REASONER v{self.VERSION} ONLINE"
        )

        self.dimension_resolver = (
            ArchitecturalSpaceDimensionResolver()
        )

        self.external_space_reasoner = (
            ExternalSpaceReasoner()
        )

        self.spatial_placement_reasoner = (
            SpatialPlacementReasoner()
        )

        self.architectural_constraints = (
            self._build_architectural_constraints
        )

    # ==================================================
    # ARCHITECTURAL CONSTRAINT EXTRACTION
    #
    # Converts semantic space metadata into placement
    # constraints consumed by spatial reasoning.
    #
    # ==================================================

    def _build_architectural_constraints(
        self,
        spaces
    ):

        constraints = {

            "privacy_zones": [],

            "quiet_zones": [],

            "daylight_priority": [],

            "protected_zones": [],

            "vehicle_access_spaces": [],

            "edge_preferences": [],

            "floor_constraints": []

        }


        for space in spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            name = space.get(
                "name"
            )


            if not name:

                continue


            architectural_intent = space.get(
                "architectural_intent",
                {}
            )


            if not isinstance(
                architectural_intent,
                dict
            ):

                architectural_intent = {}


            privacy_level = (
                architectural_intent.get(
                    "privacy_level"
                )
            )


            if privacy_level:

                constraints[
                    "privacy_zones"
                ].append(
                    {
                        "space": name,
                        "level": privacy_level
                    }
                )


            if architectural_intent.get(
                "placement_priority"
            ) == "quiet_zone":

                constraints[
                    "quiet_zones"
                ].append(
                    name
                )


            if architectural_intent.get(
                "daylight_priority"
            ):

                constraints[
                    "daylight_priority"
                ].append(
                    {
                        "space": name,
                        "priority":
                            architectural_intent.get(
                                "daylight_priority"
                            )
                    }
                )


            if architectural_intent.get(
                "preferred_edge_role"
            ):

                constraints[
                    "edge_preferences"
                ].append(
                    {
                        "space": name,
                        "role":
                            architectural_intent.get(
                                "preferred_edge_role"
                            )
                    }
                )


            if space.get(
                "protected_zone"
            ):

                constraints[
                    "protected_zones"
                ].append(
                    name
                )


            if space.get(
                "access_requirement"
            ) == "vehicle_access_required":

                constraints[
                    "vehicle_access_spaces"
                ].append(
                    name
                )

            floor_constraints = space.get(
                "floor_constraints",
                {}
            )


            if isinstance(
                floor_constraints,
                dict
            ) and floor_constraints:

                constraints[
                    "floor_constraints"
                ].append(
                    {
                        "space":
                            name,

                        "floor":
                            space.get(
                                "floor"
                            ),

                        "role":
                            floor_constraints.get(
                                "role"
                            ),

                        "allowed_zones":
                            list(
                                floor_constraints.get(
                                    "allowed_zones",
                                    []
                                )
                            ),

                        "preferred_spaces":
                            list(
                                floor_constraints.get(
                                    "preferred_spaces",
                                    []
                                )
                            ),

                        "constraints":
                            dict(
                                floor_constraints.get(
                                    "constraints",
                                    {}
                                )
                            )
                    }
                )


        return constraints

    def generate(
        self,
        spaces,
        relationships,
        design_concept,
        space_program=None,
        site_analysis=None,
        generated_site_spaces=None
    ):

        layout = {

            "zones": {},

            "connections": [],

            "layout_strategy": [],

            "floor_distribution": {},

            "space_registry": [],

            "external_spaces": [],

            "spatial_layout": [],

        }


        design_concept = design_concept or {}

        site_analysis = site_analysis or {}

        # ==================================================
        # SITE SPACE HANDOFF (ARCH-SITE-02)
        #
        # generated_site_spaces carries the SITE-domain spaces
        # resolved by KnowledgeSpaceGenerator:
        #
        #     floor            = "site_level"
        #     placement_domain = "site"
        #
        # They are NOT rooms. They are never added to space_registry,
        # never placed in the floor layout, and no geometry is created
        # for them here.
        #
        # They are indexed so that relationship endpoints referencing a
        # site space resolve to the SITE domain using authoritative
        # site metadata, instead of depending on a hardcoded name list.
        #
        # The parameter is OPTIONAL and backward compatible: callers
        # that pass only generated_spaces keep the previous behaviour.
        # ==================================================

        site_space_index = {}

        if isinstance(
            generated_site_spaces,
            list
        ):

            for site_space in generated_site_spaces:

                if not isinstance(
                    site_space,
                    dict
                ):
                    continue

                for site_key in (
                    site_space.get("name"),
                    site_space.get("canonical_name")
                ):

                    if not site_key:
                        continue

                    site_space_index.setdefault(
                        str(site_key).lower(),
                        site_space
                    )

        # ==================================================
        # PLANNER SPACE PROGRAM BRIDGE
        #
        # PlannerAgent is the source of architectural
        # resolved dimensions.
        #
        # LayoutReasoner consumes resolved dimensions when
        # available and falls back to resolver otherwise.
        # ==================================================

        space_program_lookup = {}

        if isinstance(
            space_program,
            list
        ):

            for program_space in space_program:

                if not isinstance(
                    program_space,
                    dict
                ):
                    continue

                program_name = program_space.get(
                    "name"
                )

                program_floor = program_space.get(
                    "floor",
                    program_space.get(
                        "planner_floor"
                    )
                )

                if program_name:

                    space_program_lookup[
                        (
                            str(program_name).lower(),
                            program_floor
                        )
                    ] = program_space

        building_type = design_concept.get(
            "building_type"
        )


        functions = design_concept.get(
            "functions",
            []
        )


        if not isinstance(
            functions,
            list
        ):

            functions = []


        normalized_functions = [

            str(function).lower()

            for function in functions

            if function is not None

        ]


        if building_type:

            building_type = str(
                building_type
            ).lower()


        # ==================================================
        # GENERIC BUILDING USE RESOLUTION
        #
        # "building" is not an architectural use.
        # If typology is unresolved, use the explicit
        # functional classification without guessing
        # villa / apartment / other typology.
        # ==================================================

        if building_type in (
            None,
            "",
            "building"
        ):

            if len(
                normalized_functions
            ) == 1:

                building_type = normalized_functions[
                    0
                ]


            elif len(
                normalized_functions
            ) > 1:

                building_type = "mixed_use"


        if not building_type:

            building_type = (

                design_concept.get(
                    "function"
                )

                or design_concept.get(
                    "program_type"
                )

            )


            building_type = (
                str(building_type).lower()
                if building_type
                else None
            )

        # ==================================================
        # SPACE LOOKUP
        #
        # Used by circulation intelligence to understand
        # spaces located on each side of a corridor.
        # ==================================================

        space_lookup = {}

        for item in spaces:

            if not isinstance(
                item,
                dict
            ):

                continue

            item_name = item.get(
                "name"
            )

            canonical_item_name = item.get(
                "canonical_name",
                item_name
            )

            if item_name:

                space_lookup[
                    item_name
                ] = item

            if canonical_item_name:

                space_lookup[
                    canonical_item_name
                ] = item

        # ==================================================
        # SPACE CLASSIFICATION
        # ==================================================

        for space in spaces:

            if isinstance(
                space,
                dict
            ):

                name = space.get(
                    "name"
                )

                canonical_name = space.get(
                    "canonical_name",
                    name
                )

                semantic_zone = space.get(
                    "zone"
                )

                space_type = space.get(
                    "space_type"
                )

                access = list(
                    space.get(
                        "access",
                        []
                    )
                )

                adjacent_to = list(
                    space.get(
                        "adjacent_to",
                        []
                    )
                )

                floor = space.get(
                    "floor"
                )


                resolved_dimensions = (
                    space.get(
                        "resolved_dimensions"
                    )
                )

                
                dimensional_requirements = dict(
                    space.get(
                        "dimensional_requirements",
                        {}
                    )
                )

                planner_space = (
                    space_program_lookup.get(
                        (
                            str(name).lower(),
                            floor
                        )
                    )
                )


                if planner_space is not None:

                    if planner_space.get(
                        "zone"
                    ):

                        semantic_zone = planner_space.get(
                            "zone"
                        )


                    if planner_space.get(
                        "canonical_name"
                    ):

                        canonical_name = planner_space.get(
                            "canonical_name"
                        )


                    if planner_space.get(
                        "protected_zone"
                    ):

                        space[
                            "protected_zone"
                        ] = planner_space.get(
                            "protected_zone"
                        )


                    if planner_space.get(
                        "environmental_requirements"
                    ):
                        space[
                            "environmental_requirements"
                        ] = planner_space.get(
                            "environmental_requirements"
                        )


                    if planner_space.get(
                        "privacy_requirements"
                    ):
                        space[
                            "privacy_requirements"
                        ] = planner_space.get(
                            "privacy_requirements"
                        )


                    if planner_space.get(
                        "architectural_intent"
                    ):

                        space[
                            "architectural_intent"
                        ] = planner_space.get(
                            "architectural_intent"
                        )


                    if planner_space.get(
                        "access_requirements"
                    ):
                        space[
                            "access_requirements"
                        ] = planner_space.get(
                            "access_requirements"
                        )

                    if planner_space.get(
                        "dimensional_requirements"
                    ):

                        dimensional_requirements = dict(
                            planner_space.get(
                                "dimensional_requirements"
                            )
                        )

                    if planner_space.get(
                        "circulation_profile"
                    ):

                        circulation_profile = (
                            planner_space.get(
                                "circulation_profile"
                            )
                        )


                        if (
                            isinstance(
                                circulation_profile,
                                dict
                            )
                            and
                            circulation_profile.get(
                                "resolved_width"
                            ) is not None
                        ):

                            dimensional_requirements[
                                "resolved_width"
                            ] = circulation_profile.get(
                                "resolved_width"
                            )

                        space[
                            "circulation_profile"
                        ] = planner_space.get(
                            "circulation_profile"
                        )

                    
            else:

                name = space

                canonical_name = space

                semantic_zone = None

                space_type = None

                access = []

                adjacent_to = []

                floor = None

                dimensional_requirements = {}

            # ==============================================
            # SEMANTIC → PLANNING ZONE
            # ==============================================

            planning_zone = {

                "public":
                    "public",

                "commercial":
                    "public",

                "private":
                    "private",

                "semi_public":
                    "public",

                "service":
                    "service",

                "external":
                    "external",

                "circulation":
                    "circulation"

            }.get(

                semantic_zone,

                "public"

            )


            # ==============================================
            # VARIABLE CORRIDOR INTELLIGENCE
            #
            # Resolve corridor width from architectural
            # function and corridor loading.
            #
            # Existing dimensional knowledge is preserved.
            # Only semantic corridor-like spaces are affected.
            # ==============================================

            corridor_aliases = {

                "corridor",
                "hallway",
                "passage",
                "circulation_corridor",
                "residential_corridor",
                "commercial_corridor"

            }

            normalized_name = str(
                name or ""
            ).lower()

            normalized_canonical_name = str(
                canonical_name or ""
            ).lower()

            normalized_space_type = str(
                space_type or ""
            ).lower()

            is_corridor = (

                normalized_name in corridor_aliases

                or normalized_canonical_name
                    in corridor_aliases

                or normalized_space_type
                    in corridor_aliases

            )

            circulation_profile = (
                space.get(
                    "circulation_profile"
                )
            )

            if (
                isinstance(
                    circulation_profile,
                    dict
                )
                and
                circulation_profile.get(
                    "resolved_width"
                ) is not None
            ):

                dimensional_requirements[
                    "resolved_width"
                ] = circulation_profile.get(
                    "resolved_width"
                )

            elif (
                planning_zone == "circulation"
                and is_corridor
            ):

                adjacent_commercial_count = 0

                for adjacent_name in adjacent_to:

                    adjacent_space = space_lookup.get(
                        adjacent_name,
                        {}
                    )

                    adjacent_type = str(
                        adjacent_space.get(
                            "space_type",
                            ""
                        )
                    ).lower()

                    adjacent_zone = str(
                        adjacent_space.get(
                            "zone",
                            ""
                        )
                    ).lower()

                    adjacent_canonical = str(
                        adjacent_space.get(
                            "canonical_name",
                            adjacent_space.get(
                                "name",
                                ""
                            )
                        )
                    ).lower()

                    if (

                        adjacent_zone == "commercial"

                        or adjacent_type in {
                            "shop",
                            "retail",
                            "commercial"
                        }

                        or adjacent_canonical in {
                            "shop",
                            "retail",
                            "store"
                        }

                    ):

                        adjacent_commercial_count += 1

                # ------------------------------------------
                # CORRIDOR LOADING
                # ------------------------------------------

                if adjacent_commercial_count >= 2:

                    corridor_loading = (
                        "double_loaded"
                    )

                elif adjacent_commercial_count == 1:

                    corridor_loading = (
                        "single_loaded"
                    )

                else:

                    corridor_loading = (
                        "internal"
                    )

                # ------------------------------------------
                # RESIDENTIAL CORRIDOR
                # ------------------------------------------

                residential_types = {

                    "residential",
                    "villa",
                    "single_family",
                    "apartment",
                    "housing"

                }

                commercial_types = {

                    "commercial",
                    "mall",
                    "shopping_center",
                    "shopping_centre",
                    "retail",
                    "shop",
                    "mixed_use"

                }

                if building_type in residential_types:

                    minimum_width = max(

                        float(
                            dimensional_requirements.get(
                                "minimum_width",
                                0
                            )
                            or 0
                        ),

                        1.2

                    )

                    preferred_width = max(

                        float(
                            dimensional_requirements.get(
                                "preferred_width",
                                0
                            )
                            or 0
                        ),

                        1.5

                    )

                    maximum_width = float(

                        dimensional_requirements.get(
                            "maximum_width",
                            2.0
                        )
                        or 2.0

                    )

                    resolved_width = preferred_width

                    circulation_profile = {

                        "circulation_type":
                            "residential_corridor",

                        "loading":
                            corridor_loading,

                        "minimum_width":
                            minimum_width,

                        "preferred_width":
                            preferred_width,

                        "maximum_width":
                            maximum_width,

                        "resolved_width":
                            resolved_width,

                        "protected_zone":
                            True

                    }

                # ------------------------------------------
                # COMMERCIAL CORRIDOR
                # ------------------------------------------

                elif building_type in commercial_types:

                    if corridor_loading == "double_loaded":

                        required_minimum = 4.0

                    elif corridor_loading == "single_loaded":

                        required_minimum = 2.5

                    else:

                        required_minimum = float(

                            dimensional_requirements.get(
                                "minimum_width",
                                2.5
                            )
                            or 2.5

                        )

                    minimum_width = max(

                        float(
                            dimensional_requirements.get(
                                "minimum_width",
                                0
                            )
                            or 0
                        ),

                        required_minimum

                    )

                    resolved_width = minimum_width

                    circulation_profile = {

                        "circulation_type":
                            "commercial_corridor",

                        "loading":
                            corridor_loading,

                        "minimum_width":
                            minimum_width,

                        "resolved_width":
                            resolved_width,

                        "protected_zone":
                            True

                    }

                # ------------------------------------------
                # UNKNOWN BUILDING FUNCTION
                #
                # Do not invent residential/commercial rule.
                # Preserve the knowledge already supplied.
                # ------------------------------------------

                else:

                    resolved_width = (
                        dimensional_requirements.get(
                            "preferred_width"
                        )

                        or dimensional_requirements.get(
                            "minimum_width"
                        )
                    )

                    circulation_profile = {

                        "circulation_type":
                            "generic_corridor",

                        "loading":
                            corridor_loading,

                        "minimum_width":
                            dimensional_requirements.get(
                                "minimum_width"
                            ),

                        "resolved_width":
                            resolved_width,

                        "protected_zone":
                            True,

                        "decision_status":
                            "building_type_required"

                    }

                dimensional_requirements[
                    "circulation_profile"
                ] = circulation_profile

                dimensional_requirements[
                    "resolved_width"
                ] = circulation_profile.get(
                    "resolved_width"
                )

                corridor_resolved_width = (
                    dimensional_requirements.get(
                        "resolved_width"
                    )
                )

                corridor_target_area = (
                    dimensional_requirements.get(
                        "preferred_area"
                    )
                )

                if corridor_target_area is None:

                    corridor_target_area = (
                        dimensional_requirements.get(
                            "minimum_area"
                        )
                    )

                if (
                    corridor_resolved_width is not None
                    and
                    corridor_target_area is not None
                ):

                    try:

                        corridor_resolved_width = float(
                            corridor_resolved_width
                        )

                        corridor_target_area = float(
                            corridor_target_area
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        corridor_resolved_width = None
                        corridor_target_area = None

                if (
                    corridor_resolved_width is not None
                    and
                    corridor_target_area is not None
                    and
                    corridor_resolved_width > 0
                    and
                    corridor_target_area > 0
                ):

                    corridor_resolved_depth = (
                        corridor_target_area
                        /
                        corridor_resolved_width
                    )

                    corridor_resolved_area = (
                        corridor_resolved_width
                        *
                        corridor_resolved_depth
                    )

                    dimensional_requirements[
                        "resolved_depth"
                    ] = corridor_resolved_depth

                    dimensional_requirements[
                        "resolved_area"
                    ] = corridor_resolved_area

            # ==============================================
            # CORRIDOR RESOLVED DIMENSIONS
            #
            # Corridor width comes from circulation
            # intelligence.
            # Convert it into architectural dimensions.
            # ==============================================

            if (
                resolved_dimensions is None
                and
                dimensional_requirements.get(
                    "resolved_width"
                ) is not None
                and
                circulation_profile is not None
            ):

                corridor_width = (
                    dimensional_requirements.get(
                        "resolved_width"
                    )
                )

                corridor_area = (
                    dimensional_requirements.get(
                        "preferred_area"
                    )
                    or
                    dimensional_requirements.get(
                        "minimum_area"
                    )
                )

                if (
                    corridor_area is not None
                    and
                    float(corridor_width) > 0
                ):

                    corridor_depth = (
                        float(corridor_area)
                        /
                        float(corridor_width)
                    )

                    resolved_dimensions = {

                        "width":
                            float(
                                corridor_width
                            ),

                        "depth":
                            corridor_depth,

                        "area":
                            float(
                                corridor_area
                            ),

                        "target_area":
                            float(
                                corridor_area
                            ),

                        "source":
                            "corridor_profile",

                        "status":
                            "resolved_from_circulation"

                    }

            # ==============================================
            # ARCHITECTURAL DIMENSION RESOLUTION
            #
            # Planner resolved dimensions have priority.
            # Resolver is fallback only.
            # ==============================================

            if space.get(
                "resolved_dimensions"
            ):

                resolved_dimensions = space.get(
                    "resolved_dimensions"
                )


                dimension_result = {
                    "dimensional_requirements":
                        dimensional_requirements,

                    "resolved_dimensions":
                        resolved_dimensions
                }

            # ==============================================
            # PRESERVE PLANNER RESOLVED DIMENSIONS
            #
            # Planner is authoritative source when available.
            # Do not recompute from incomplete knowledge.
            # ==============================================

            if resolved_dimensions is not None:

                dimension_result = {
                    "dimensional_requirements":
                        dimensional_requirements,

                    "resolved_dimensions":
                        resolved_dimensions
                }

            else:

                dimension_result = (
                    self.dimension_resolver.resolve(
                        dimensional_requirements,
                        space_type,
                        canonical_name
                    )
                )

            # ==============================================
            # APPLY DIMENSION RESOLUTION RESULT
            #
            # DimensionResolver returns a result contract.
            # Persist that result into the semantic space
            # variables before building space_registry.
            # ==============================================

            if isinstance(
                dimension_result,
                dict
            ):

                resolved_requirements = (
                    dimension_result.get(
                        "dimensional_requirements"
                    )
                )


                if isinstance(
                    resolved_requirements,
                    dict
                ):

                    dimensional_requirements = (
                        resolved_requirements
                    )


                resolved_dimensions = (
                    dimension_result.get(
                        "resolved_dimensions"
                    )
                )
            # ==============================================
            # SEMANTIC SPACE
            # ==============================================

            semantic_space = {

                "name":
                    name,

                "canonical_name":
                    canonical_name,

                "zone":
                    semantic_zone,

                "planning_zone":
                    planning_zone,

                "space_type":
                    space_type,

                "access":
                    access,

                "adjacent_to":
                    adjacent_to,

                "floor":
                    floor,

                "dimensional_requirements":
                    dimensional_requirements,

                "resolved_dimensions":
                    resolved_dimensions,

                "circulation_profile":
                    circulation_profile,

                "protected_zone":
                    bool(
                        space.get(
                            "protected_zone",
                            False
                        )
                        or
                        (
                            circulation_profile
                            and
                            circulation_profile.get(
                                "protected_zone",
                                False
                            )
                        )
                    ),

                # --------------------------------------
                # ARCHITECTURAL PLACEMENT CONTRACT
                #
                # Preserve explicit program / intent
                # metadata without inference.
                # --------------------------------------

                "placement_scope":
                    space.get(
                        "placement_scope"
                    ),

                "access_requirement":
                    space.get(
                        "access_requirement"
                    ),
                    
                "environmental_requirements":
                    space.get(
                        "environmental_requirements",
                        {}
                    ),

                "privacy_requirements":
                    space.get(
                        "privacy_requirements",
                        {}
                    ),

                "access_requirements":
                    space.get(
                        "access_requirements",
                        {} 
                    ),

                "architectural_intent":
                    space.get(
                        "architectural_intent",
                        {}
                    ),

                "floor_constraints":
                    space.get(
                        "floor_constraints",
                        {}
                    ),

                "connects":
                    list(
                        space.get(
                            "connects",
                            []
                        )
                    )
                    if isinstance(
                        space.get(
                            "connects",
                            []
                        ),
                        list
                    )
                    else [],

                "vertical_connection":
                    dict(
                        space.get(
                            "vertical_connection",
                            {}
                        )
                    )
                    if isinstance(
                        space.get(
                            "vertical_connection",
                            {}
                        ),
                        dict
                    )
                    else {}

            }

            # ==============================================
            # SPACE REGISTRY
            # ==============================================

            layout[
                "space_registry"
            ].append(
                semantic_space
            )

            # ==============================================
            # ZONE INDEX
            # ==============================================

            layout[
                "zones"
            ].setdefault(
                planning_zone,
                []
            ).append(
                name
            )

            # ==============================================
            # FLOOR INDEX
            #
            # IMPORTANT:
            # Floor comes from Program Knowledge.
            # Do not infer floor from zone.
            # ==============================================

            resolved_floor = self.resolve_floor(
                floor
            )

            layout[
                "floor_distribution"
            ].setdefault(
                resolved_floor,
                []
            ).append(
                name
            )

        # ==================================================
        # EXTERNAL SPACE INTELLIGENCE
        #
        # Relationships may reference external
        # architectural spaces:
        #
        # terrace
        # garden
        # yard
        # parking
        # ramp
        #
        # They are not ignored.
        # They become semantic external nodes.
        # ==================================================

        known_space_names = {

            str(
                item.get(
                    "name"
                )
            ).lower()

            for item in layout["space_registry"]

            if isinstance(
                item,
                dict
            )
            and item.get(
                "name"
            )

        }


        for relation in relationships:

            if not isinstance(
                relation,
                dict
            ):

                continue


            for endpoint in (

                relation.get(
                    "from"
                ),

                relation.get(
                    "to"
                )

            ):

                if not endpoint:

                    continue


                endpoint_name = str(
                    endpoint
                ).lower()


                if endpoint_name in known_space_names:

                    continue


                # SITE SPACE RESOLUTION (ARCH-SITE-02 / ARCH-SITE-03)
                #
                # A site space is identified by its AUTHORITATIVE semantic
                # metadata (placement_domain == "site" or
                # floor == "site_level"), never by its name.
                #
                # An endpoint with no site record is NOT an external site
                # node. Callers that want site nodes must pass
                # generated_site_spaces.
                site_space = site_space_index.get(
                    endpoint_name
                )


                if site_space is None:

                    continue


                exists = False


                for external_space in layout["external_spaces"]:

                    if external_space.get(
                        "name"
                    ) == endpoint_name:

                        exists = True
                        break


                if exists:

                    continue


                if site_space is not None:

                    # SITE DOMAIN NODE
                    #
                    # Authoritative site metadata is carried through so
                    # the relationship target resolves to the SITE
                    # domain. The node stays a site node: it is not a
                    # room, it receives no floor-layout placement, and
                    # no coordinates or geometry are created here.
                    external_space = {

                        "name":
                            site_space.get("name", endpoint_name),

                        "canonical_name":
                            site_space.get(
                                "canonical_name",
                                endpoint_name
                            ),

                        "zone":
                            site_space.get("zone", "external"),

                        "space_type":
                            site_space.get(
                                "space_type"
                            ) or "external_space",

                        "floor":
                            site_space.get("floor"),

                        "semantic_role":
                            "architectural_external",

                        "placement_domain":
                            site_space.get(
                                "placement_domain",
                                "site"
                            ),

                        "dimensional_requirements":
                            dict(
                                site_space.get(
                                    "dimensional_requirements",
                                    {}
                                )
                            ),

                        "architectural_intent":
                            dict(
                                site_space.get(
                                    "architectural_intent",
                                    {}
                                )
                            ),

                        "protected_zone":
                            bool(
                                site_space.get(
                                    "protected_zone",
                                    False
                                )
                            ),

                        "resolved_dimensions":
                            site_space.get(
                                "resolved_dimensions"
                            )

                    }

                else:

                    external_space = {

                        "name":
                            endpoint_name,

                        "canonical_name":
                            endpoint_name,

                        "zone":
                            "external",

                        "space_type":
                            "external_space",

                        "floor":
                            None,

                        "semantic_role":
                            "architectural_external"

                    }


                resolved_external_space = (
                    self.external_space_reasoner.resolve(
                        external_space,
                        relationships
                    )
                )


                layout["external_spaces"].append(
                    resolved_external_space
                )
        # ==================================================
        # RELATIONSHIPS
        # ==================================================

        for relation in relationships:

            if not isinstance(
                relation,
                dict
            ):

                continue

            connection = dict(relation)
            connection.setdefault("from", relation.get("from_space_id"))
            connection.setdefault("to", relation.get("to_space_id"))
            connection.setdefault("type", relation.get("relation_type", "adjacent"))
            layout["connections"].append(connection)

        # ==================================================
        # DESIGN STRATEGY
        # ==================================================

        if isinstance(
            design_concept,
            dict
        ):

            spatial_idea = design_concept.get(
                "spatial_idea",
                []
            )

            if isinstance(
                spatial_idea,
                list
            ):

                layout[
                    "layout_strategy"
                ].extend(
                    spatial_idea
                )

        # ==================================================
        # SPATIAL PLACEMENT
        #
        # Convert semantic registry into
        # architectural relative placement.
        # ==================================================

        architectural_constraints = (
            self.architectural_constraints(
                layout[
                    "space_registry"
                ]
            )
        )

        if not isinstance(
            site_analysis,
            dict
        ):

            site_analysis = {}


        site_analysis[
            "architectural_constraints"
        ] = architectural_constraints

        layout[
            "spatial_layout"
        ] = self.spatial_placement_reasoner.place(

            layout[
                "space_registry"
            ],

            layout[
                "connections"
            ],

            layout[
                "external_spaces"
            ],

            site_analysis

        )

        # ==================================================
        # RETURN
        # ==================================================

        return layout

    # ==================================================
    # FLOOR RESOLUTION
    # ==================================================

    def resolve_floor(
        self,
        floor
    ):

        if floor in (
            "ground_floor",
            "F1"
        ):

            return "F1"

        if floor in (
            "upper_floor",
            "F2"
        ):

            return "F2"

        if floor in (
            "third_floor",
            "F3"
        ):

            return "F3"

        if floor:

            return floor

        # ----------------------------------------------
        # Unknown floor
        # ----------------------------------------------

        return "UNASSIGNED"
