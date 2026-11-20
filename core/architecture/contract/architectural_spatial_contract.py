class ArchitecturalSpatialContract:

    VERSION = "1.2"


    def __init__(self):

        print(
            f"📐 ARCHITECTURAL SPATIAL CONTRACT v{self.VERSION} ONLINE"
        )


    def generate(
        self,
        layout,
        architectural_intent=None
    ):

        architectural_intent = (
            architectural_intent
            if isinstance(
                architectural_intent,
                dict
            )
            else {}
        )

        contract = {

            "spaces": [],

            "adjacency": [],

            "vertical_organization": {},

            "floor_configuration": {},

            "floor_heights": {},

            "planning_rules": []

        }


        # ==================================
        # SPACES
        #
        # Use semantic space registry
        # Preserve architectural intelligence
        # ==================================

        space_registry = layout.get(
            "space_registry",
            []
        )

        # ==================================================
        # SPATIAL PLACEMENT CONTRACT BRIDGE v1.0
        #
        # Merge SpatialPlacementReasoner evidence back into
        # semantic spaces before creating the architectural
        # spatial contract.
        #
        # IMPORTANT:
        # Identity is (name, floor), not name alone.
        #
        # This preserves:
        #
        # corridor @ ground_floor
        # corridor @ upper_floor
        #
        # as independent architectural instances.
        # ==================================================

        spatial_layout = layout.get(
            "spatial_layout",
            []
        )


        if not isinstance(
            spatial_layout,
            list
        ):

            spatial_layout = []


        spatial_placement_lookup = {}


        for placement in spatial_layout:

            if not isinstance(
                placement,
                dict
            ):

                continue


            placement_name = placement.get(
                "name"
            )

            placement_floor = placement.get(
                "floor"
            )


            if not placement_name:

                continue


            spatial_placement_lookup[
                (
                    placement_name,
                    placement_floor
                )
            ] = placement


        for space in space_registry:

            if not isinstance(
                space,
                dict
            ):

                continue

            spatial_placement = (
                spatial_placement_lookup.get(
                    (
                        space.get(
                            "name"
                        ),
                        space.get(
                            "floor"
                        )
                    ),
                    {}
                )
            )


            if not isinstance(
                spatial_placement,
                dict
            ):

                spatial_placement = {}


            contract["spaces"].append(

                {

                    "name":
                        space.get(
                            "name"
                        ),

                    "canonical_name":
                        space.get(
                            "canonical_name",
                            space.get(
                                "name"
                            )
                        ),

                    "zone":
                        space.get(
                            "zone"
                        ),

                    "planning_zone":
                        space.get(
                            "planning_zone"
                        ),

                    "space_type":
                        space.get(
                            "space_type"
                        ),

                    "access":
                        list(
                            space.get(
                                "access",
                                []
                            )
                        ),

                    "adjacent_to":
                        list(
                            space.get(
                                "adjacent_to",
                                []
                            )
                        ),

                    "floor":
                        space.get(
                            "floor"
                        ),

                    # --------------------------------------
                    # FLOOR HEIGHT EVIDENCE BRIDGE v1.0
                    #
                    # Preserve floor-height intelligence
                    # already resolved by the spatial
                    # placement stage.
                    #
                    # This contract does not invent height.
                    # --------------------------------------

                    "floor_height":
                        spatial_placement.get(
                            "floor_height"
                        ),

                    "floor_height_source":
                        spatial_placement.get(
                            "floor_height_source"
                        ),

                    "floor_height_status":
                        spatial_placement.get(
                            "height_status"
                        ),

                    "floor_constraints":
                        (
                            dict(
                                space.get(
                                    "floor_constraints",
                                    {}
                                )
                            )
                            if isinstance(
                                space.get(
                                    "floor_constraints"
                                ),
                                dict
                            )
                            else {}
                        ),

                    "dimensional_requirements":
                        dict(
                            space.get(
                                "dimensional_requirements",
                                {}
                            )
                        ),

                    "environmental_requirements":
                        dict(
                            space.get(
                                "environmental_requirements",
                                {}
                            )
                        ),

                    "privacy_requirements":
                        dict(
                            space.get(
                                "privacy_requirements",
                                {}
                            )
                        ),

                    "access_requirements":
                        dict(
                            space.get(
                                "access_requirements",
                                {}
                            )
                        ),

                    "orientation_requirements":
                        dict(
                            space.get(
                                "orientation_requirements",
                                {}
                            )
                        ),

                    "acoustic_requirements":
                        dict(
                            space.get(
                                "acoustic_requirements",
                                {}
                            )
                        ),

                    "furniture_requirements":
                        dict(
                            space.get(
                                "furniture_requirements",
                                {}
                            )
                        ),

                    "resolved_dimensions":
                        space.get(
                            "resolved_dimensions"
                        ),

                    "circulation_profile":
                        space.get(
                            "circulation_profile"
                        ),

                    "protected_zone":
                        bool(
                            space.get(
                                "protected_zone",
                                False
                            )
                        ),

                    # --------------------------------------
                    # ARCHITECTURAL PLACEMENT CONTRACT
                    #
                    # Preserve explicit program-level
                    # placement/access requirements.
                    #
                    # No placement decision is invented here.
                    # --------------------------------------

                    "placement_scope":
                        space.get(
                            "placement_scope"
                        ),

                    "access_requirement":
                        space.get(
                            "access_requirement"
                        ),

                    "role":
                        self.get_role(
                            space.get(
                                "planning_zone"
                            )
                        ),

                    "position_intent":
                        self.get_position_intent(
                            space.get(
                                "planning_zone"
                            )
                        ),

                    # --------------------------------------
                    # SPATIAL PLACEMENT EVIDENCE
                    # --------------------------------------

                    "x":
                        spatial_placement.get(
                            "x"
                        ),

                    "y":
                        spatial_placement.get(
                            "y"
                        ),

                    "coordinate_mode":
                        spatial_placement.get(
                            "coordinate_mode"
                        ),

                    "placement_reason":
                        spatial_placement.get(
                            "placement_reason"
                        ),

                    "anchor_space":
                        spatial_placement.get(
                            "anchor_space"
                        ),

                    # --------------------------------------
                    # PARCEL EDGE INTENT
                    # --------------------------------------

                    "access_edge_index":
                        spatial_placement.get(
                            "access_edge_index"
                        ),

                    "road_width":
                        spatial_placement.get(
                            "road_width"
                        ),

                    "access_edge_status":
                        spatial_placement.get(
                            "access_edge_status"
                        ),

                    "parcel_relation":
                        spatial_placement.get(
                            "parcel_relation"
                        ),

                    "preferred_edge_index":
                        spatial_placement.get(
                            "preferred_edge_index"
                        ),

                    "edge_relation":
                        spatial_placement.get(
                            "edge_relation"
                        ),

                    "edge_decision_status":
                        spatial_placement.get(
                            "edge_decision_status"
                        ),

                    "edge_decision_reason":
                        spatial_placement.get(
                            "edge_decision_reason"
                        ),

                    "site_context":
                        spatial_placement.get(
                            "site_context"
                        )

                }

            )


        # ==================================
        # FALLBACK
        #
        # Compatibility with old layouts
        # ==================================

        if not space_registry:

            for zone, spaces in layout.get(
                "zones",
                {}
            ).items():


                for space in spaces:


                    contract["spaces"].append(

                        {

                            "name":
                                space,

                            "canonical_name":
                                space,

                            "zone":
                                zone,

                            "role":
                                self.get_role(
                                    zone
                                ),

                            "position_intent":
                                self.get_position_intent(
                                    zone
                                )

                        }

                    )


        # ==================================
        # VERTICAL ORGANIZATION
        # ==================================

        contract[
            "vertical_organization"
        ] = layout.get(

            "floor_distribution",

            {}

        )

        # ==============================================
        # FLOOR CONFIGURATION CONTRACT v1.0
        #
        # Architectural floor dimensions must originate
        # from explicit architectural intelligence.
        #
        # This contract does NOT invent a storey height.
        #
        # Supported explicit intent:
        #
        # floor_heights = {
        #     "F1": 3.2,
        #     "F2": 3.4
        # }
        #
        # or:
        #
        # floor_height = 3.2
        #
        # A scalar floor_height is interpreted as an
        # explicit uniform-height architectural request.
        # ==============================================

        floor_heights = {}

        floor_height_resolution_status = (
            "architectural_height_pending"
        )

        floor_height_source = None

        # ==============================================
        # FLOOR HEIGHT EVIDENCE RESOLUTION v1.1
        #
        # Resolve real floor heights from semantic
        # space-floor evidence.
        #
        # No F1/F2 semantic mapping is hardcoded.
        # The relationship is inferred from actual
        # floor membership in vertical_organization.
        # ==============================================

        semantic_floor_heights = {}


        for contract_space in contract.get(
            "spaces",
            []
        ):

            if not isinstance(
                contract_space,
                dict
            ):

                continue


            semantic_floor = contract_space.get(
                "floor"
            )


            floor_height = contract_space.get(
                "floor_height"
            )


            if not semantic_floor:

                continue


            if not isinstance(
                floor_height,
                (int, float)
            ):

                continue


            floor_height = float(
                floor_height
            )


            if floor_height <= 0:

                continue


            semantic_floor_heights.setdefault(
                semantic_floor,
                []
            ).append(
                floor_height
            )


        resolved_semantic_floor_heights = {}


        for semantic_floor, candidates in (
            semantic_floor_heights.items()
        ):

            unique_candidates = sorted(
                list(
                    set(
                        candidates
                    )
                )
            )


            if len(
                unique_candidates
            ) == 1:

                resolved_semantic_floor_heights[
                    semantic_floor
                ] = unique_candidates[0]


        # ==============================================
        # REAL FLOOR ↔ SEMANTIC FLOOR RESOLUTION v1.2
        #
        # Resolve floor identity by complete space
        # membership rather than individual space names.
        #
        # IMPORTANT:
        # A space name such as "corridor" may legitimately
        # occur on multiple floors, so name-only matching
        # is not a valid floor identity mechanism.
        #
        # No F1/F2 semantic mapping is hardcoded.
        # ==============================================

        semantic_floor_space_names = {}


        for contract_space in contract.get(
            "spaces",
            []
        ):

            if not isinstance(
                contract_space,
                dict
            ):

                continue


            semantic_floor = contract_space.get(
                "floor"
            )

            space_name = contract_space.get(
                "name"
            )


            if (
                not semantic_floor
                or
                not space_name
            ):

                continue


            semantic_floor_space_names.setdefault(
                semantic_floor,
                []
            ).append(
                space_name
            )


        vertical_organization = contract.get(
            "vertical_organization",
            {}
        )


        if isinstance(
            vertical_organization,
            dict
        ):

            for real_floor, floor_space_names in (
                vertical_organization.items()
            ):

                if not isinstance(
                    floor_space_names,
                    list
                ):

                    continue


                real_floor_names = sorted(
                    [
                        name
                        for name in floor_space_names
                        if name
                    ]
                )


                matched_semantic_floors = []


                for (
                    semantic_floor,
                    semantic_space_names
                ) in semantic_floor_space_names.items():

                    semantic_names = sorted(
                        [
                            name
                            for name in semantic_space_names
                            if name
                        ]
                    )


                    if (
                        semantic_names
                        ==
                        real_floor_names
                    ):

                        matched_semantic_floors.append(
                            semantic_floor
                        )


                if len(
                    matched_semantic_floors
                ) != 1:

                    continue


                semantic_floor = (
                    matched_semantic_floors[0]
                )


                resolved_height = (
                    resolved_semantic_floor_heights.get(
                        semantic_floor
                    )
                )


                if resolved_height is None:

                    continue


                floor_heights[
                    real_floor
                ] = resolved_height

        if floor_heights:

            floor_height_resolution_status = (
                "resolved_from_building_program"
            )

            floor_height_source = (
                "building_program_knowledge"
            )

        explicit_floor_heights = (
            architectural_intent.get(
                "floor_heights"
            )
        )

        explicit_floor_height_applied = False

        if isinstance(
            explicit_floor_heights,
            dict
        ):

            for floor, height in (
                explicit_floor_heights.items()
            ):

                try:

                    resolved_height = float(
                        height
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue

                if resolved_height <= 0:

                    continue

                floor_heights[
                    floor
                ] = resolved_height

                explicit_floor_height_applied = True

        if explicit_floor_height_applied:

            floor_height_resolution_status = (
                "resolved_from_architectural_intent"
            )

            floor_height_source = (
                "architectural_intent"
            )

        explicit_uniform_height = (
            architectural_intent.get(
                "floor_height"
            )
        )

        if explicit_uniform_height is not None:

            try:

                explicit_uniform_height = float(
                    explicit_uniform_height
                )

            except (
                TypeError,
                ValueError
            ):

                explicit_uniform_height = None

            if (
                explicit_uniform_height is not None
                and
                explicit_uniform_height > 0
            ):

                floor_height_resolution_status = (
                    "resolved_from_architectural_intent"
                )

                floor_height_source = (
                    "architectural_intent"
                )


                for floor in contract.get(
                    "vertical_organization",
                    {}
                ).keys():

                    floor_heights[
                        floor
                    ] = (
                        explicit_uniform_height
                    )

        contract[
            "floor_heights"
        ] = floor_heights

        contract[
            "floor_configuration"
        ] = {

            "floor_heights":
                dict(
                    floor_heights
                ),

            "height_resolution_status":
                floor_height_resolution_status,

            "source":
                floor_height_source
        }


        # ==================================
        # RELATIONSHIPS
        # ==================================

        for relation in layout.get(
            "connections",
            []
        ):


            if not isinstance(
                relation,
                dict
            ):

                continue


            adjacency = dict(relation)
            adjacency.setdefault("from", relation.get("from_space_id"))
            adjacency.setdefault("to", relation.get("to_space_id"))
            adjacency.setdefault("relationship", relation.get("type", relation.get("relation_type")))
            contract["adjacency"].append(adjacency)


        # ==================================
        # RULES
        # ==================================

        contract[
            "planning_rules"
        ] = layout.get(

            "layout_strategy",

            []

        )


        return contract



    def get_role(
        self,
        zone
    ):


        roles = {

            "public":
                "social_space",

            "private":
                "privacy_space",

            "service":
                "support_space",

            "external":
                "outdoor_space",

            "circulation":
                "movement_space"

        }


        return roles.get(
            zone,
            "architectural_space"
        )



    def get_position_intent(
        self,
        zone
    ):


        positions = {

            "public":
                "near_entrance",

            "private":
                "protected_zone",

            "service":
                "support_zone",

            "external":
                "boundary_interface",

            "circulation":
                "central_connection"

        }


        return positions.get(
            zone,
            "neutral_position"
        )
