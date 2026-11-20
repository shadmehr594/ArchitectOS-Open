# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: SpatialPlacementReasoner.place  (internal plan synthesis branch)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class SpatialPlacementReasoner:

    VERSION = "1.3"


    def __init__(self):

        print(
            f"📍 SPATIAL PLACEMENT REASONER v{self.VERSION} ONLINE"
        )


    def place(
        self,
        space_registry,
        connections,
        external_spaces=None,
        site_analysis=None
    ):

        external_spaces = external_spaces or []

        site_analysis = site_analysis or {}

        architectural_constraints = site_analysis.get(
            "architectural_constraints",
            {}
        )

        if not isinstance(
            architectural_constraints,
            dict
        ):

            architectural_constraints = {}

        def get_space_constraints(
            space_name,
            floor=None
        ):

            result = {}

            for item in architectural_constraints.get(
                "privacy_zones",
                []
            ):

                if item.get(
                    "space"
                ) != space_name:

                    continue

                item_floor = item.get(
                    "floor"
                )

                if (
                    floor is not None
                    and
                    item_floor is not None
                    and
                    item_floor != floor
                ):

                    continue

                result[
                    "privacy_level"
                ] = item.get(
                    "level"
                )


            if space_name in architectural_constraints.get(
                "quiet_zones",
                []
            ):

                result[
                    "quiet_zone"
                ] = True


            for item in architectural_constraints.get(
                "daylight_priority",
                []
            ):

                if item.get(
                    "space"
                ) != space_name:

                    continue

                item_floor = item.get(
                    "floor"
                )

                if (
                    floor is not None
                    and
                    item_floor is not None
                    and
                    item_floor != floor
                ):

                    continue

                result[
                    "daylight_priority"
                ] = item.get(
                    "priority"
                )


            for item in architectural_constraints.get(
                "edge_preferences",
                []
            ):

                if item.get(
                    "space"
                ) != space_name:

                    continue

                item_floor = item.get(
                    "floor"
                )

                if (
                    floor is not None
                    and
                    item_floor is not None
                    and
                    item_floor != floor
                ):

                    continue

                result[
                    "preferred_edge_role"
                ] = item.get(
                    "role"
                )


            if space_name in architectural_constraints.get(
                "protected_zones",
                []
            ):

                result[
                    "protected_zone"
                ] = True


            for item in architectural_constraints.get(
                "floor_constraints",
                []
            ):

                if not isinstance(
                    item,
                    dict
                ):

                    continue


                if item.get(
                    "space"
                ) != space_name:

                    continue


                item_floor = item.get(
                    "floor"
                )


                if (
                    floor is not None
                    and
                    item_floor is not None
                    and
                    item_floor != floor
                ):

                    continue


                result[
                    "floor_constraints"
                ] = {

                    "floor":
                        item_floor,

                    "role":
                        item.get(
                            "role"
                        ),

                    "allowed_zones":
                        list(
                            item.get(
                                "allowed_zones",
                                []
                            )
                        ),

                    "preferred_spaces":
                        list(
                            item.get(
                                "preferred_spaces",
                                []
                            )
                        ),

                    "constraints":
                        dict(
                            item.get(
                                "constraints",
                                {}
                            )
                        )

                }


            return result

        def get_space_frontage_requirement(
            space_name,
            floor=None
        ):

            matching_space = None


            for candidate in space_registry:

                if not isinstance(
                    candidate,
                    dict
                ):

                    continue


                if candidate.get(
                    "name"
                ) != space_name:

                    continue


                if (
                    floor is not None
                    and
                    candidate.get(
                        "floor"
                    ) != floor
                ):

                    continue


                matching_space = candidate

                break


            if not isinstance(
                matching_space,
                dict
            ):

                return 0.0


            resolved_dimensions = matching_space.get(
                "resolved_dimensions",
                {}
            )


            if isinstance(
                resolved_dimensions,
                dict
            ):

                resolved_width = resolved_dimensions.get(
                    "width"
                )


                try:

                    resolved_width = float(
                        resolved_width
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    resolved_width = None


                if (
                    resolved_width is not None
                    and
                    resolved_width > 0
                ):

                    return resolved_width


            dimensional_requirements = matching_space.get(
                "dimensional_requirements",
                {}
            )


            if not isinstance(
                dimensional_requirements,
                dict
            ):

                dimensional_requirements = {}


            minimum_width = dimensional_requirements.get(
                "minimum_width"
            )


            try:

                minimum_width = float(
                    minimum_width
                )

            except (
                TypeError,
                ValueError
            ):

                minimum_width = 0.0


            return max(
                minimum_width,
                0.0
            )

        # ==================================================
        # VERTICAL CONNECTIVITY PROOF v1.0
        #
        # Presence of stairs / elevator is not sufficient
        # evidence for floor connectivity.
        #
        # Connectivity is proven only when an explicit
        # vertical-space contract declares which floors
        # it connects.
        #
        # No floor connection is guessed here.
        # ==================================================

        def resolve_vertical_connectivity_proof(
            target_floor
        ):

            proof = {

                "status":
                    "not_required",

                "candidate_spaces":
                    [],

                "connected_by":
                    [],

                "target_floor":
                    target_floor,

                "evidence":
                    [],

                "reason":
                    None

            }


            if target_floor in (
                None,
                "",
                "ground_floor",
                "F1"
            ):

                proof[
                    "reason"
                ] = "target_floor_does_not_require_vertical_proof"

                return proof


            proof[
                "status"
            ] = "unproven"


            vertical_aliases = {

                "stairs",
                "stair",
                "internal_stair",
                "elevator",
                "lift",
                "vertical_core",
                "service_core"

            }


            normalized_target_floor = str(
                target_floor
            ).lower()


            for candidate in space_registry:

                if not isinstance(
                    candidate,
                    dict
                ):

                    continue


                candidate_name = str(
                    candidate.get(
                        "name",
                        ""
                    )
                    or ""
                )


                candidate_canonical_name = str(
                    candidate.get(
                        "canonical_name",
                        candidate_name
                    )
                    or ""
                )


                candidate_space_type = str(
                    candidate.get(
                        "space_type",
                        ""
                    )
                    or ""
                )


                normalized_candidate_name = (
                    candidate_name.lower()
                )

                normalized_candidate_canonical = (
                    candidate_canonical_name.lower()
                )

                normalized_candidate_type = (
                    candidate_space_type.lower()
                )


                is_vertical_space = (

                    normalized_candidate_name
                    in vertical_aliases

                    or

                    normalized_candidate_canonical
                    in vertical_aliases

                    or

                    normalized_candidate_type
                    in vertical_aliases

                )


                if not is_vertical_space:

                    continue


                if candidate_name not in proof[
                    "candidate_spaces"
                ]:

                    proof[
                        "candidate_spaces"
                    ].append(
                        candidate_name
                    )


                connects = candidate.get(
                    "connects"
                )


                if connects is None:

                    parameters = candidate.get(
                        "parameters",
                        {}
                    )


                    if isinstance(
                        parameters,
                        dict
                    ):

                        connects = parameters.get(
                            "connects"
                        )


                if connects is None:

                    vertical_contract = candidate.get(
                        "vertical_connection",
                        {}
                    )


                    if isinstance(
                        vertical_contract,
                        dict
                    ):

                        connects = vertical_contract.get(
                            "connects"
                        )


                if not isinstance(
                    connects,
                    (list, tuple, set)
                ):

                    continue


                normalized_connects = {

                    str(
                        floor_name
                    ).lower()

                    for floor_name in connects

                    if floor_name is not None

                }


                normalized_floor_aliases = set(
                    normalized_connects
                )


                if "ground_floor" in normalized_connects:

                    normalized_floor_aliases.add(
                        "f1"
                    )


                if "f1" in normalized_connects:

                    normalized_floor_aliases.add(
                        "ground_floor"
                    )


                if "upper_floor" in normalized_connects:

                    normalized_floor_aliases.add(
                        "f2"
                    )


                if "f2" in normalized_connects:

                    normalized_floor_aliases.add(
                        "upper_floor"
                    )


                if "third_floor" in normalized_connects:

                    normalized_floor_aliases.add(
                        "f3"
                    )


                if "f3" in normalized_connects:

                    normalized_floor_aliases.add(
                        "third_floor"
                    )


                if (
                    normalized_target_floor
                    not in normalized_floor_aliases
                ):

                    continue


                ground_connection_available = (

                    "ground_floor"
                    in normalized_floor_aliases

                    or

                    "f1"
                    in normalized_floor_aliases

                )


                if not ground_connection_available:

                    continue


                proof[
                    "connected_by"
                ].append(
                    candidate_name
                )


                proof[
                    "evidence"
                ].append(
                    {
                        "space":
                            candidate_name,

                        "connects":
                            list(
                                connects
                            ),

                        "source":
                            "explicit_vertical_space_contract"
                    }
                )


            if proof[
                "connected_by"
            ]:

                proof[
                    "status"
                ] = "proven"

                proof[
                    "reason"
                ] = "explicit_vertical_connects_match"

            elif proof[
                "candidate_spaces"
            ]:

                proof[
                    "status"
                ] = "unproven"

                proof[
                    "reason"
                ] = (
                    "vertical_space_exists_without_explicit_connects"
                )

            else:

                proof[
                    "status"
                ] = "missing"

                proof[
                    "reason"
                ] = "no_vertical_connection_space_available"


            return proof


        def resolve_placement_decision(
            space_name,
            floor=None,
            space_zone=None
        ):

            constraints = get_space_constraints(
                space_name,
                floor
            )

            decision = {

                "status":
                    "unresolved",

                "preferred_edge_role":
                    None,

                "reason":
                    None

            }


            if constraints.get(
                "preferred_edge_role"
            ):

                decision[
                    "preferred_edge_role"
                ] = constraints.get(
                    "preferred_edge_role"
                )

                decision[
                    "status"
                ] = "resolved"


                decision[
                    "reason"
                ] = "architectural_intent"

            floor_constraints = constraints.get(
                "floor_constraints",
                {}
            )


            if isinstance(
                floor_constraints,
                dict
            ):

                floor_rules = floor_constraints.get(
                    "constraints",
                    {}
                )


                if not isinstance(
                    floor_rules,
                    dict
                ):

                    floor_rules = {}


                if floor_rules.get(
                    "requires_vertical_connection"
                ):

                    decision[
                        "requires_vertical_connection"
                    ] = True

                    decision[
                        "vertical_connection_status"
                    ] = "required"

                    decision[
                        "vertical_connection_reason"
                    ] = "floor_program_constraint"


                if floor_rules.get(
                    "privacy_priority"
                ):

                    decision[
                        "privacy_priority"
                    ] = floor_rules.get(
                        "privacy_priority"
                    )

            # ==================================================
            # FLOOR PROGRAM VALIDATION v1.0
            #
            # Validate the actual semantic zone of the space
            # against the explicit floor-program contract.
            #
            # IMPORTANT:
            # - no floor is inferred here
            # - no zone is guessed here
            # - missing floor knowledge remains unproven
            # - validation is evidence-based only
            # ==================================================

            floor_program_validation = {

                "status":
                    "not_applicable",

                "floor":
                    floor,

                "space_zone":
                    space_zone,

                "allowed_zones":
                    [],

                "floor_role":
                    None,

                "reason":
                    None

            }


            if isinstance(
                floor_constraints,
                dict
            ) and floor_constraints:

                allowed_zones = floor_constraints.get(
                    "allowed_zones",
                    []
                )


                if not isinstance(
                    allowed_zones,
                    list
                ):

                    allowed_zones = []


                floor_program_validation[
                    "allowed_zones"
                ] = list(
                    allowed_zones
                )


                floor_program_validation[
                    "floor_role"
                ] = floor_constraints.get(
                    "role"
                )


                constraint_floor = floor_constraints.get(
                    "floor"
                )


                if (
                    floor is not None
                    and
                    constraint_floor is not None
                    and
                    str(floor).lower()
                    !=
                    str(constraint_floor).lower()
                ):

                    floor_program_validation[
                        "status"
                    ] = "invalid"

                    floor_program_validation[
                        "reason"
                    ] = "space_floor_does_not_match_floor_program"


                elif space_zone is None:

                    floor_program_validation[
                        "status"
                    ] = "unproven"

                    floor_program_validation[
                        "reason"
                    ] = "space_zone_unavailable"


                elif not allowed_zones:

                    floor_program_validation[
                        "status"
                    ] = "unproven"

                    floor_program_validation[
                        "reason"
                    ] = "floor_allowed_zones_unavailable"


                else:

                    normalized_allowed_zones = {

                        str(
                            allowed_zone
                        ).lower()

                        for allowed_zone in allowed_zones

                        if allowed_zone is not None

                    }


                    normalized_space_zone = str(
                        space_zone
                    ).lower()


                    if (
                        normalized_space_zone
                        in normalized_allowed_zones
                    ):

                        floor_program_validation[
                            "status"
                        ] = "valid"

                        floor_program_validation[
                            "reason"
                        ] = "space_zone_allowed_on_floor"

                    else:

                        floor_program_validation[
                            "status"
                        ] = "invalid"

                        floor_program_validation[
                            "reason"
                        ] = "space_zone_not_allowed_on_floor"


            else:

                floor_program_validation[
                    "reason"
                ] = "floor_program_constraints_unavailable"


            decision[
                "floor_program_validation"
            ] = floor_program_validation


            # ==================================================
            # FLOOR PREFERENCE INTELLIGENCE v1.0
            #
            # Floor Program Knowledge distinguishes between:
            #
            # - allowed space
            # - preferred space
            #
            # A space may therefore be valid on a floor
            # without being a preferred program space.
            #
            # IMPORTANT:
            #
            # allowed_not_preferred is NOT invalid.
            # ==================================================

            floor_preference_validation = {

                "status":
                    "unresolved",

                "floor":
                    floor,

                "space":
                    space_name,

                "preferred_spaces":
                    [],

                "reason":
                    None

            }


            floor_constraints = constraints.get(
                "floor_constraints",
                {}
            )


            if not isinstance(
                floor_constraints,
                dict
            ):

                floor_constraints = {}


            preferred_spaces = floor_constraints.get(
                "preferred_spaces",
                []
            )


            if not isinstance(
                preferred_spaces,
                list
            ):

                preferred_spaces = []


            normalized_preferred_spaces = [

                str(
                    preferred_space
                ).lower()

                for preferred_space in preferred_spaces

                if preferred_space is not None

            ]


            floor_preference_validation[
                "preferred_spaces"
            ] = list(
                preferred_spaces
            )


            floor_program_status = (
                floor_program_validation.get(
                    "status"
                )
                if isinstance(
                    floor_program_validation,
                    dict
                )
                else None
            )


            if floor_program_status == "invalid":

                floor_preference_validation[
                    "status"
                ] = "not_evaluated"

                floor_preference_validation[
                    "reason"
                ] = "floor_program_invalid"


            elif not preferred_spaces:

                floor_preference_validation[
                    "status"
                ] = "no_preference_defined"

                floor_preference_validation[
                    "reason"
                ] = (
                    "floor_has_no_preferred_space_contract"
                )


            elif (
                str(
                    space_name
                ).lower()
                in
                normalized_preferred_spaces
            ):

                floor_preference_validation[
                    "status"
                ] = "preferred"

                floor_preference_validation[
                    "reason"
                ] = "space_preferred_on_floor"


            else:

                floor_preference_validation[
                    "status"
                ] = "allowed_not_preferred"

                floor_preference_validation[
                    "reason"
                ] = (
                    "space_allowed_but_not_preferred_on_floor"
                )


            decision[
                "floor_preference_validation"
            ] = floor_preference_validation


            vertical_proof = (
                resolve_vertical_connectivity_proof(
                    floor
                )
            )


            if decision.get(
                "requires_vertical_connection"
            ):

                decision[
                    "vertical_connection_proof"
                ] = vertical_proof


                decision[
                    "vertical_connection_validation"
                ] = vertical_proof.get(
                    "status"
                )


                decision[
                    "vertical_connection_candidates"
                ] = vertical_proof.get(
                    "candidate_spaces",
                    []
                )


                decision[
                    "vertical_connection_connected_by"
                ] = vertical_proof.get(
                    "connected_by",
                    []
                )


                decision[
                    "vertical_connection_decision_reason"
                ] = vertical_proof.get(
                    "reason"
                )


            return decision

        def resolve_space_edge_preference(
            placement_decision,
            parcel_context,
            floor=None,
            space_name=None
        ):

            if not isinstance(
                placement_decision,
                dict
            ):

                return placement_decision


            if not isinstance(
                parcel_context,
                dict
            ):

                return placement_decision


            preferred_role = placement_decision.get(
                "preferred_edge_role"
            )


            if not preferred_role:

                return placement_decision


            edge_roles = parcel_context.get(
                "parcel_edge_roles",
                []
            )


            if not isinstance(
                edge_roles,
                list
            ):

                edge_roles = []


            candidate_edges = []


            for edge in edge_roles:

                if not isinstance(
                    edge,
                    dict
                ):

                    continue


                roles = edge.get(
                    "architectural_roles",
                    []
                )


                if not isinstance(
                    roles,
                    list
                ):

                    roles = []


                confirmed = bool(
                    edge.get(
                        "confirmed",
                        False
                    )
                )


                decision_status = edge.get(
                    "decision_status"
                )


                # ------------------------------------------
                # PRIVACY EDGE
                #
                # Must be backed by confirmed parcel
                # adjacency evidence.
                # ------------------------------------------

                if preferred_role == "privacy_edge":

                    if (
                        confirmed
                        and
                        "privacy_edge" in roles
                    ):

                        candidate_edges.append(
                            edge
                        )


                # ------------------------------------------
                # PUBLIC EDGE
                #
                # Must be backed by confirmed road/public
                # parcel-edge evidence.
                # ------------------------------------------

                elif preferred_role == "public_edge":

                    if (
                        confirmed
                        and
                        "public_edge" in roles
                    ):

                        candidate_edges.append(
                            edge
                        )


                # ------------------------------------------
                # OPEN EDGE
                #
                # IMPORTANT:
                #
                # open_candidate is not enough.
                #
                # An unresolved parcel edge must never be
                # promoted automatically to a confirmed
                # architectural open edge.
                # ------------------------------------------

                elif preferred_role == "open_edge":

                    if (
                        confirmed
                        and
                        decision_status == "resolved"
                        and
                        "open_edge" in roles
                    ):

                        candidate_edges.append(
                            edge
                        )


                # ------------------------------------------
                # ACCESS EDGE
                # ------------------------------------------

                elif preferred_role == "access_edge":

                    if (
                        confirmed
                        and
                        "access_edge" in roles
                    ):

                        candidate_edges.append(
                            edge
                        )

            def privacy_edge_rank(
                edge,
                floor=None
            ):

                edge_index = edge.get(
                    "edge_index"
                )


                boundary = parcel_context.get(
                    "boundary",
                    []
                )


                access_edge_index = parcel_context.get(
                    "access_edge_index"
                )


                if not isinstance(
                    boundary,
                    list
                ):

                    boundary = []


                boundary_count = len(
                    boundary
                )


                # ------------------------------------------
                # ACCESS ADJACENCY PENALTY
                #
                # Privacy spaces prefer parcel edges that
                # are not directly adjacent to the confirmed
                # road/access edge.
                #
                # No geographic direction is inferred.
                # ------------------------------------------

                access_adjacency_penalty = 0


                try:

                    normalized_edge_index = int(
                        edge_index
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    normalized_edge_index = None


                try:

                    normalized_access_edge_index = int(
                        access_edge_index
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    normalized_access_edge_index = None


                if (
                    normalized_edge_index is not None
                    and
                    normalized_access_edge_index is not None
                    and
                    boundary_count >= 3
                ):

                    previous_access_neighbor = (
                        normalized_access_edge_index
                        - 1
                    ) % boundary_count


                    next_access_neighbor = (
                        normalized_access_edge_index
                        + 1
                    ) % boundary_count


                    if normalized_edge_index in {

                        previous_access_neighbor,
                        next_access_neighbor

                    }:

                        access_adjacency_penalty = 1


                # ------------------------------------------
                # EDGE LENGTH
                #
                # When topology is equal, prefer the longer
                # confirmed privacy edge because it provides
                # more usable facade/placement capacity.
                #
                # Squared length is sufficient for ranking.
                # ------------------------------------------

                edge_length_squared = 0.0


                if (
                    normalized_edge_index is not None
                    and
                    boundary_count >= 3
                    and
                    0 <= normalized_edge_index < boundary_count
                ):

                    edge_start = boundary[
                        normalized_edge_index
                    ]


                    edge_end = boundary[
                        (
                            normalized_edge_index
                            + 1
                        )
                        %
                        boundary_count
                    ]


                    if (
                        isinstance(
                            edge_start,
                            (list, tuple)
                        )
                        and
                        isinstance(
                            edge_end,
                            (list, tuple)
                        )
                        and
                        len(edge_start) >= 2
                        and
                        len(edge_end) >= 2
                    ):

                        try:

                            dx = (
                                float(
                                    edge_end[0]
                                )
                                -
                                float(
                                    edge_start[0]
                                )
                            )


                            dy = (
                                float(
                                    edge_end[1]
                                )
                                -
                                float(
                                    edge_start[1]
                                )
                            )


                            edge_length_squared = (
                                dx * dx
                                +
                                dy * dy
                            )

                        except (
                            TypeError,
                            ValueError
                        ):

                            edge_length_squared = 0.0


                # ------------------------------------------
                # EVIDENCE CONFIDENCE
                # ------------------------------------------

                try:

                    confidence = float(
                        edge.get(
                            "confidence",
                            0.0
                        )
                        or 0.0
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    confidence = 0.0

                # ------------------------------------------
                # FRONTAGE CAPACITY
                #
                # Determine whether the current space can
                # still fit on this privacy edge.
                #
                # Allocation is floor-aware and uses the
                # resolved architectural frontage demand.
                # ------------------------------------------

                edge_length = (
                    edge_length_squared ** 0.5
                )


                frontage_requirement = (
                    get_space_frontage_requirement(
                        space_name,
                        floor
                    )
                )


                floor_usage = privacy_edge_usage.get(
                    floor,
                    {}
                )


                if not isinstance(
                    floor_usage,
                    dict
                ):

                    floor_usage = {}


                edge_usage = floor_usage.get(
                    normalized_edge_index,
                    {}
                )


                if not isinstance(
                    edge_usage,
                    dict
                ):

                    edge_usage = {}


                allocated_frontage = edge_usage.get(
                    "allocated_frontage",
                    0.0
                )


                try:

                    allocated_frontage = float(
                        allocated_frontage
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    allocated_frontage = 0.0


                remaining_frontage = max(
                    edge_length
                    -
                    allocated_frontage,
                    0.0
                )


                capacity_penalty = 0


                if (
                    frontage_requirement > 0
                    and
                    remaining_frontage
                    <
                    frontage_requirement
                ):

                    capacity_penalty = 1


                return (

                    capacity_penalty,

                    access_adjacency_penalty,

                    -remaining_frontage,

                    -edge_length_squared,

                    -confidence,

                    normalized_edge_index
                    if normalized_edge_index is not None
                    else 999999

                )


            if candidate_edges:

                if preferred_role == "privacy_edge":

                    selected_edge = min(
                        candidate_edges,
                        key=lambda edge:
                            privacy_edge_rank(
                                edge,
                                floor
                            )
                    )

                else:

                    selected_edge = candidate_edges[
                        0
                    ]


                placement_decision[
                    "preferred_edge_index"
                ] = selected_edge.get(
                    "edge_index"
                )


                placement_decision[
                    "resolved_edge_relation"
                ] = selected_edge.get(
                    "relation"
                )


                placement_decision[
                    "edge_resolution_status"
                ] = "resolved"


                placement_decision[
                    "edge_resolution_reason"
                ] = "parcel_edge_role_match"

                if preferred_role == "privacy_edge":

                    selected_rank = privacy_edge_rank(
                        selected_edge,
                        floor
                    )


                    placement_decision[
                        "edge_selection_strategy"
                    ] = "privacy_edge_ranking"


                    placement_decision[
                        "edge_selection_reason"
                    ] = (
                        "prefer_privacy_edge_away_from_access_with_frontage_capacity"
                    )

                    selected_edge_index = selected_edge.get(
                        "edge_index"
                    )


                    selected_edge_length = (
                        (
                            -selected_rank[3]
                        )
                        ** 0.5
                    )


                    frontage_requirement = (
                        get_space_frontage_requirement(
                            space_name,
                            floor
                        )
                    )


                    floor_usage = privacy_edge_usage.get(
                        floor,
                        {}
                    )


                    if not isinstance(
                        floor_usage,
                        dict
                    ):

                        floor_usage = {}


                    existing_edge_usage = floor_usage.get(
                        selected_edge_index,
                        {}
                    )


                    if not isinstance(
                        existing_edge_usage,
                        dict
                    ):

                        existing_edge_usage = {}


                    allocated_before = float(
                        existing_edge_usage.get(
                            "allocated_frontage",
                            0.0
                        )
                        or 0.0
                    )


                    placement_decision[
                        "edge_selection_evidence"
                    ] = {

                        "capacity_penalty":
                            selected_rank[0],

                        "access_adjacency_penalty":
                            selected_rank[1],

                        "edge_length":
                            selected_edge_length,

                        "allocated_frontage_before":
                            allocated_before,

                        "frontage_requirement":
                            frontage_requirement,

                        "remaining_frontage_before":
                            max(
                                selected_edge_length
                                -
                                allocated_before,
                                0.0
                            ),

                        "confidence":
                            -selected_rank[4],

                        "parcel_id":
                            selected_edge.get(
                                "parcel_id"
                            )

                    }


                    if selected_edge_index is not None:

                        floor_usage = privacy_edge_usage.setdefault(
                            floor,
                            {}
                        )


                        edge_usage = floor_usage.setdefault(
                            selected_edge_index,
                            {
                                "allocated_frontage":
                                    0.0,

                                "spaces":
                                    []
                            }
                        )


                        frontage_requirement = (
                            get_space_frontage_requirement(
                                space_name,
                                floor
                            )
                        )


                        edge_usage[
                            "allocated_frontage"
                        ] = (
                            float(
                                edge_usage.get(
                                    "allocated_frontage",
                                    0.0
                                )
                                or 0.0
                            )
                            +
                            frontage_requirement
                        )


                        if space_name not in edge_usage[
                            "spaces"
                        ]:

                            edge_usage[
                                "spaces"
                            ].append(
                                space_name
                            )


            else:

                placement_decision[
                    "preferred_edge_index"
                ] = None


                placement_decision[
                    "resolved_edge_relation"
                ] = None


                placement_decision[
                    "edge_resolution_status"
                ] = "pending"


                placement_decision[
                    "edge_resolution_reason"
                ] = "no_matching_parcel_edge"


            return placement_decision

        

        placements = []

        # ==================================================
        # PRIVACY EDGE ALLOCATION REGISTRY v1.0
        #
        # Tracks resolved privacy-edge usage per floor.
        #
        # This is a preference-balancing mechanism only.
        # It does not prohibit multiple spaces from sharing
        # the same parcel edge when alternatives are weaker
        # or unavailable.
        # ==================================================

        privacy_edge_usage = {}

        # ==================================================
        # PARCEL ACCESS CONTEXT
        #
        # Resolve site evidence once at function scope so
        # every internal placement branch can consume it.
        # ==================================================

        building_strategy = site_analysis.get(
            "building_strategy",
            {}
        )

        if not isinstance(
            building_strategy,
            dict
        ):

            building_strategy = {}


        access_strategy = site_analysis.get(
            "access_strategy",
            {}
        )

        if not isinstance(
            access_strategy,
            dict
        ):

            access_strategy = {}


        parcel_boundary = building_strategy.get(
            "buildable_boundary",
            building_strategy.get("parcel_boundary")
        )

        coordinate_system = building_strategy.get(
            "coordinate_system"
        )

        access_edge_index = access_strategy.get(
            "access_edge_index"
        )

        road_width = access_strategy.get(
            "road_width"
        )


        parcel_geometry_available = (

            isinstance(
                parcel_boundary,
                list
            )

            and len(
                parcel_boundary
            ) >= 3

            and coordinate_system
                == "local_normalized"

        )

        # ==================================================
        # ENTRANCE → ACCESS EDGE ENRICHMENT
        #
        # Apply the same parcel-access evidence regardless
        # of which internal placement branch created the
        # architectural entrance.
        #
        # IMPORTANT:
        # x / y remain abstract-grid coordinates.
        # ==================================================

        def enrich_entrance_placement(
            placement,
            space
        ):

            if not isinstance(
                placement,
                dict
            ):

                return placement


            if not isinstance(
                space,
                dict
            ):

                return placement


            normalized_space_name = str(
                space.get(
                    "name",
                    ""
                )
                or ""
            ).lower()


            normalized_canonical_name = str(
                space.get(
                    "canonical_name",
                    ""
                )
                or ""
            ).lower()


            normalized_space_type = str(
                space.get(
                    "space_type",
                    ""
                )
                or ""
            ).lower()


            is_entrance_space = (

                normalized_space_name in {
                    "entrance",
                    "entry",
                    "main_entrance",
                    "lobby"
                }

                or normalized_canonical_name in {
                    "entrance",
                    "entry",
                    "main_entrance",
                    "lobby"
                }

                or normalized_space_type in {
                    "entrance",
                    "entry"
                }

            )


            if not is_entrance_space:

                return placement


            placement[
                "access_edge_index"
            ] = access_edge_index


            placement[
                "road_width"
            ] = road_width


            if (
                parcel_geometry_available
                and
                access_edge_index is not None
            ):

                placement[
                    "access_edge_status"
                ] = "resolved_from_parcel"

                placement[
                    "parcel_relation"
                ] = "road_access"

                # ==========================================
                # PARCEL EDGE SPATIAL INTENT v1.0
                #
                # Use the same edge-intent contract used by
                # external architectural spaces.
                #
                # No real x / y coordinate is assigned here.
                # ==========================================

                placement[
                    "preferred_edge_index"
                ] = access_edge_index

                placement[
                    "edge_relation"
                ] = "road"

                placement[
                    "edge_decision_status"
                ] = "resolved"

                placement[
                    "edge_decision_reason"
                ] = "confirmed_road_access_edge"

            else:

                placement[
                    "access_edge_status"
                ] = "pending"

                placement[
                    "parcel_relation"
                ] = None

                placement[
                    "preferred_edge_index"
                ] = None

                placement[
                    "edge_relation"
                ] = None

                placement[
                    "edge_decision_status"
                ] = "pending"

                placement[
                    "edge_decision_reason"
                ] = "confirmed_access_edge_unavailable"


            return placement


        # ==================================================
        # RELATIONSHIP GRAPH
        #
        # Semantic graph is name-based because current
        # architectural connections use semantic names.
        #
        # Actual placement remains floor-aware below.
        # ==================================================

        adjacency_graph = {}


        for connection in connections:

            if not isinstance(
                connection,
                dict
            ):

                continue


            source = connection.get(
                "from"
            )

            target = connection.get(
                "to"
            )


            if not source or not target:

                continue


            source = str(
                source
            )

            target = str(
                target
            )


            adjacency_graph.setdefault(
                source,
                []
            )


            adjacency_graph.setdefault(
                target,
                []
            )


            if target not in adjacency_graph[
                source
            ]:

                adjacency_graph[
                    source
                ].append(
                    target
                )


            if source not in adjacency_graph[
                target
            ]:

                adjacency_graph[
                    target
                ].append(
                    source
                )


        # ==================================================
        # FLOOR GROUPING
        #
        # Placement is solved independently per floor.
        #
        # This prevents semantic duplicates such as:
        #
        # corridor @ ground_floor
        # corridor @ upper_floor
        #
        # from collapsing into one placement instance.
        # ==================================================

        floor_groups = {}


        for space in space_registry:

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


            floor = space.get(
                "floor"
            )


            floor_groups.setdefault(
                floor,
                []
            ).append(
                space
            )


        # ==================================================
        # DIRECTION PREFERENCES
        #
        # These are abstract relative placement directions.
        #
        # They are NOT real parcel coordinates.
        # ==================================================

        direction_preferences = {

            "public": [
                (1, 0),
                (0, 1),
                (0, -1),
                (-1, 0)
            ],

            "service": [
                (0, -1),
                (1, -1),
                (1, 0),
                (-1, -1),
                (-1, 0)
            ],

            "circulation": [
                (0, 1),
                (1, 0),
                (-1, 0),
                (0, -1)
            ],

            "private": [
                (1, 1),
                (1, 0),
                (0, 1),
                (-1, 1),
                (-1, 0)
            ]

        }

        # ==================================================
        # ARCHITECTURAL METRIC PLACEMENT HELPERS v1.0
        #
        # Semantic directions remain unchanged.
        #
        # When all spaces on a floor have resolved width /
        # depth, placement is solved using real rectangular
        # extents instead of abstract point cells.
        #
        # Boundary contact is allowed and represents
        # architectural adjacency.
        # ==================================================

        def get_metric_dimensions(
            space
        ):

            resolved = space.get(
                "resolved_dimensions"
            )


            if not isinstance(
                resolved,
                dict
            ):

                return None, None


            width = resolved.get(
                "width"
            )

            depth = resolved.get(
                "depth"
            )


            try:

                width = float(
                    width
                )

                depth = float(
                    depth
                )

            except (
                TypeError,
                ValueError
            ):

                return None, None


            if (
                width <= 0
                or
                depth <= 0
            ):

                return None, None


            return width, depth


        def rectangles_overlap(
            x1,
            y1,
            w1,
            d1,
            x2,
            y2,
            w2,
            d2
        ):

            # Boundary contact is NOT collision.

            return not (

                x1 + w1 <= x2

                or

                x2 + w2 <= x1

                or

                y1 + d1 <= y2

                or

                y2 + d2 <= y1

            )

        # ==================================================
        # ACCESS EDGE INTERIOR HALF-PLANE v1.0
        #
        # Keep metric architectural candidates on the
        # parcel-interior side of the confirmed access edge.
        #
        # IMPORTANT:
        # - no north / south assumption
        # - no setback assumption
        # - no parcel translation here
        # - polygon winding determines the interior side
        #
        # The local architectural anchor is treated as lying
        # on the confirmed access-edge line.
        # ==================================================

        def metric_candidate_respects_access_edge(
            candidate_x,
            candidate_y,
            candidate_width,
            candidate_depth
        ):

            if not parcel_geometry_available:

                return True


            if access_edge_index is None:

                return True


            if not isinstance(
                parcel_boundary,
                list
            ):

                return True


            boundary_count = len(
                parcel_boundary
            )


            if boundary_count < 3:

                return True


            try:

                edge_index = int(
                    access_edge_index
                )

            except (
                TypeError,
                ValueError
            ):

                return True


            if (
                edge_index < 0
                or
                edge_index >= boundary_count
            ):

                return True


            edge_start = parcel_boundary[
                edge_index
            ]

            edge_end = parcel_boundary[
                (
                    edge_index
                    +
                    1
                )
                %
                boundary_count
            ]


            if (
                not isinstance(
                    edge_start,
                    (list, tuple)
                )
                or
                not isinstance(
                    edge_end,
                    (list, tuple)
                )
                or
                len(edge_start) < 2
                or
                len(edge_end) < 2
            ):

                return True


            try:

                edge_dx = (
                    float(
                        edge_end[0]
                    )
                    -
                    float(
                        edge_start[0]
                    )
                )

                edge_dy = (
                    float(
                        edge_end[1]
                    )
                    -
                    float(
                        edge_start[1]
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                return True


            if (
                edge_dx == 0.0
                and
                edge_dy == 0.0
            ):

                return True


            # ----------------------------------------------
            # POLYGON WINDING
            #
            # Positive signed area:
            #     counter-clockwise polygon
            #     interior lies LEFT of directed edges.
            #
            # Negative signed area:
            #     clockwise polygon
            #     interior lies RIGHT of directed edges.
            # ----------------------------------------------

            signed_area_twice = 0.0


            try:

                for index in range(
                    boundary_count
                ):

                    point_a = parcel_boundary[
                        index
                    ]

                    point_b = parcel_boundary[
                        (
                            index
                            +
                            1
                        )
                        %
                        boundary_count
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


                    signed_area_twice += (
                        ax * by
                        -
                        bx * ay
                    )

            except (
                TypeError,
                ValueError,
                IndexError
            ):

                return True


            if signed_area_twice == 0.0:

                return True


            interior_sign = (
                1.0
                if signed_area_twice > 0.0
                else -1.0
            )


            try:

                candidate_x = float(
                    candidate_x
                )

                candidate_y = float(
                    candidate_y
                )

                candidate_width = float(
                    candidate_width
                )

                candidate_depth = float(
                    candidate_depth
                )

            except (
                TypeError,
                ValueError
            ):

                return False


            # ----------------------------------------------
            # LOCAL ACCESS-EDGE LINE
            #
            # Architectural anchor is local (0, 0).
            # Preserve only the confirmed edge direction.
            # ----------------------------------------------

            candidate_corners = [

                (
                    candidate_x,
                    candidate_y
                ),

                (
                    candidate_x
                    +
                    candidate_width,
                    candidate_y
                ),

                (
                    candidate_x,
                    candidate_y
                    +
                    candidate_depth
                ),

                (
                    candidate_x
                    +
                    candidate_width,
                    candidate_y
                    +
                    candidate_depth
                )

            ]


            tolerance = 1e-9


            for point_x, point_y in candidate_corners:

                cross_value = (
                    edge_dx
                    *
                    point_y
                    -
                    edge_dy
                    *
                    point_x
                )


                if (
                    interior_sign
                    *
                    cross_value
                    <
                    -tolerance
                ):

                    return False


            return True


        def metric_position_is_free(
            candidate_x,
            candidate_y,
            candidate_width,
            candidate_depth,
            existing_placements
        ):

            if not metric_candidate_respects_access_edge(
                candidate_x,
                candidate_y,
                candidate_width,
                candidate_depth
            ):

                return False

            for existing in existing_placements.values():

                if not isinstance(
                    existing,
                    dict
                ):

                    continue


                existing_x = existing.get(
                    "x"
                )

                existing_y = existing.get(
                    "y"
                )

                existing_width = existing.get(
                    "width"
                )

                existing_depth = existing.get(
                    "depth"
                )


                if (
                    existing_x is None
                    or
                    existing_y is None
                    or
                    existing_width is None
                    or
                    existing_depth is None
                ):

                    continue


                if rectangles_overlap(

                    candidate_x,
                    candidate_y,
                    candidate_width,
                    candidate_depth,

                    float(
                        existing_x
                    ),
                    float(
                        existing_y
                    ),
                    float(
                        existing_width
                    ),
                    float(
                        existing_depth
                    )

                ):

                    return False


            return True


        def metric_candidate_from_direction(
            parent_placement,
            child_width,
            child_depth,
            dx,
            dy
        ):

            parent_x = float(
                parent_placement[
                    "x"
                ]
            )

            parent_y = float(
                parent_placement[
                    "y"
                ]
            )

            parent_width = float(
                parent_placement[
                    "width"
                ]
            )

            parent_depth = float(
                parent_placement[
                    "depth"
                ]
            )


            if dx > 0:

                candidate_x = (
                    parent_x
                    +
                    parent_width
                )

            elif dx < 0:

                candidate_x = (
                    parent_x
                    -
                    child_width
                )

            else:

                candidate_x = (
                    parent_x
                )


            if dy > 0:

                candidate_y = (
                    parent_y
                    +
                    parent_depth
                )

            elif dy < 0:

                candidate_y = (
                    parent_y
                    -
                    child_depth
                )

            else:

                candidate_y = (
                    parent_y
                )


            return (
                candidate_x,
                candidate_y
            )

        # ==================================================
        # EARLY PARCEL EDGE CONTEXT v1.0
        #
        # Internal architectural placement decisions may
        # consume parcel-edge roles before the complete
        # parcel-aware site context is assembled later.
        #
        # IMPORTANT:
        # - This is semantic edge evidence only.
        # - No real x / y parcel coordinate is assigned.
        # - No geographic direction is inferred.
        # ==================================================

        early_parcel_edges = building_strategy.get(
            "parcel_edges",
            []
        )

        if not isinstance(
            early_parcel_edges,
            list
        ):

            early_parcel_edges = []


        early_parcel_edge_roles = []


        for early_parcel_edge in early_parcel_edges:

            if not isinstance(
                early_parcel_edge,
                dict
            ):

                continue


            early_edge_index = early_parcel_edge.get(
                "edge_index"
            )

            early_relation = early_parcel_edge.get(
                "relation"
            )

            early_confirmed = bool(
                early_parcel_edge.get(
                    "confirmed",
                    False
                )
            )


            early_edge_role = {

                "edge_index":
                    early_edge_index,

                "relation":
                    early_relation,

                "confirmed":
                    early_confirmed,

                "confidence":
                    early_parcel_edge.get(
                        "confidence",
                        0.0
                    ),

                "primary_role":
                    None,

                "architectural_roles":
                    [],

                "privacy_constraint":
                    False,

                "access_constraint":
                    False,

                "parcel_id":
                    early_parcel_edge.get(
                        "parcel_id"
                    ),

                "road_width":
                    early_parcel_edge.get(
                        "road_width"
                    ),

                "decision_status":
                    "unresolved"

            }


            if (
                early_confirmed
                and
                early_relation == "road"
            ):

                early_edge_role[
                    "primary_role"
                ] = "access_edge"

                early_edge_role[
                    "architectural_roles"
                ] = [
                    "access_edge",
                    "public_edge",
                    "road_edge"
                ]

                early_edge_role[
                    "access_constraint"
                ] = True

                early_edge_role[
                    "decision_status"
                ] = "resolved"


            elif (
                early_confirmed
                and
                early_relation == "neighbor_parcel"
            ):

                early_edge_role[
                    "primary_role"
                ] = "neighbor_edge"

                early_edge_role[
                    "architectural_roles"
                ] = [
                    "neighbor_edge",
                    "privacy_edge"
                ]

                early_edge_role[
                    "privacy_constraint"
                ] = True

                early_edge_role[
                    "decision_status"
                ] = "resolved"


            elif early_edge_index is not None:

                early_edge_role[
                    "primary_role"
                ] = "open_candidate"

                early_edge_role[
                    "architectural_roles"
                ] = [
                    "open_candidate",
                    "open_edge"
                ]

                early_edge_role[
                    "decision_status"
                ] = "pending"


            early_parcel_edge_roles.append(
                early_edge_role
            )


        parcel_context = {

            "coordinate_system":
                coordinate_system,

            "boundary":
                parcel_boundary,

            "road_width":
                road_width,

            "access_edge_index":
                access_edge_index,

            "parcel_edges":
                list(
                    early_parcel_edges
                ),

            "parcel_edge_roles":
                list(
                    early_parcel_edge_roles
                ),

            "geometry_available":
                parcel_geometry_available

        }


        # ==================================================
        # FLOOR PLACEMENT
        # ==================================================

        # ==================================================
        # FLOOR-TO-FLOOR SUPPORT STATE v1.0
        #
        # A resolved upper floor should remain within the
        # geometric support envelope of the immediately
        # preceding resolved floor unless an explicit
        # overhang / cantilever contract exists.
        #
        # The support correction is a rigid translation of
        # the whole floor arrangement. Individual room
        # relationships are never modified here.
        # ==================================================

        previous_floor_support_envelope = None
        previous_floor_support_floor = None


        for floor, floor_spaces in floor_groups.items():

            if not floor_spaces:

                continue

            # ==================================================
            # FLOOR HEIGHT CONTRACT v1.0
            #
            # Floor-to-floor height is architectural program
            # knowledge.
            #
            # It must not be invented by Geometry, Structure,
            # BIM or IFC.
            #
            # BuildingProgramKnowledge._enrich_floor_layer()
            # propagates floor_intelligence into each space as
            # floor_constraints. All spaces belonging to one
            # floor should therefore carry the same explicit
            # floor-height evidence.
            # ==================================================

            floor_height = None
            floor_height_source = None
            floor_height_status = "unresolved"


            floor_height_candidates = []


            for floor_space in floor_spaces:

                if not isinstance(
                    floor_space,
                    dict
                ):

                    continue


                floor_constraints = floor_space.get(
                    "floor_constraints",
                    {}
                )


                if not isinstance(
                    floor_constraints,
                    dict
                ):

                    continue


                candidate_height = floor_constraints.get(
                    "height"
                )


                if candidate_height is None:

                    continue


                try:

                    candidate_height = float(
                        candidate_height
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    continue


                if candidate_height <= 0:

                    continue


                floor_height_candidates.append(
                    {
                        "height":
                            candidate_height,

                        "source":
                            floor_constraints.get(
                                "height_source",
                                "floor_constraints"
                            ),

                        "status":
                            floor_constraints.get(
                                "height_status",
                                "resolved"
                            ),

                        "space":
                            floor_space.get(
                                "name"
                            )
                    }
                )


            if floor_height_candidates:

                unique_floor_heights = sorted(
                    {
                        round(
                            candidate[
                                "height"
                            ],
                            6
                        )

                        for candidate in floor_height_candidates
                    }
                )


                if len(
                    unique_floor_heights
                ) == 1:

                    floor_height = (
                        floor_height_candidates[
                            0
                        ][
                            "height"
                        ]
                    )

                    floor_height_source = (
                        floor_height_candidates[
                            0
                        ].get(
                            "source"
                        )
                    )

                    floor_height_status = "resolved"


                else:

                    floor_height_status = (
                        "conflicting_floor_height_evidence"
                    )


            print(
                "\n====== FLOOR HEIGHT CONTRACT ======"
            )

            print(
                {
                    "floor":
                        floor,

                    "height":
                        floor_height,

                    "status":
                        floor_height_status,

                    "source":
                        floor_height_source,

                    "candidate_count":
                        len(
                            floor_height_candidates
                        ),

                    "candidate_heights":
                        [
                            candidate.get(
                                "height"
                            )
                            for candidate in floor_height_candidates
                        ]
                }
            )

            print(
                "==================================="
            )

            # ----------------------------------------------
            # FLOOR METRIC READINESS
            #
            # Do not declare metric coordinates unless every
            # internal space on this floor has valid real
            # architectural dimensions.
            # ----------------------------------------------

            metric_floor_ready = True


            for metric_space in floor_spaces:

                metric_width, metric_depth = (
                    get_metric_dimensions(
                        metric_space
                    )
                )


                if (
                    metric_width is None
                    or
                    metric_depth is None
                ):

                    metric_floor_ready = False

                    break


            used_positions = set()


            floor_placements = {}


            # ----------------------------------------------
            # FLOOR ANCHOR SELECTION
            #
            # Entrance is preferred on entrance floor.
            # Corridor becomes the anchor on upper floors
            # when no entrance exists.
            #
            # No floor is inferred here.
            # ----------------------------------------------

            anchor_space = None


            for candidate in floor_spaces:

                candidate_name = str(
                    candidate.get(
                        "name",
                        ""
                    )
                ).lower()


                if candidate_name == "entrance":

                    anchor_space = candidate

                    break


            if anchor_space is None:

                for candidate in floor_spaces:

                    candidate_name = str(
                        candidate.get(
                            "name",
                            ""
                        )
                    ).lower()


                    if candidate_name == "corridor":

                        anchor_space = candidate

                        break


            if anchor_space is None:

                anchor_space = floor_spaces[
                    0
                ]


            anchor_name = anchor_space.get(
                "name"
            )


            anchor_key = (
                anchor_name,
                floor
            )


            anchor_resolved = anchor_space.get(
                "resolved_dimensions"
            )


            anchor_width = None
            anchor_depth = None


            if isinstance(
                anchor_resolved,
                dict
            ):

                anchor_width = anchor_resolved.get(
                    "width"
                )

                anchor_depth = anchor_resolved.get(
                    "depth"
                )


            anchor_zone = anchor_space.get(
                "planning_zone",
                anchor_space.get(
                    "zone",
                    "public"
                )
            )


            anchor_placement = {

                "name":
                    anchor_name,

                "architectural_constraints":
                    get_space_constraints(
                        anchor_name,
                        floor
                    ),

                "protected_zone":
                    bool(
                        anchor_space.get(
                            "protected_zone",
                            False
                        )
                        or
                        get_space_constraints(
                            anchor_name,
                            floor
                        ).get(
                            "protected_zone",
                            False
                        )
                    ),

                "placement_decision":
                    resolve_space_edge_preference(
                        resolve_placement_decision(
                            anchor_name,
                            floor,
                            anchor_zone
                        ),
                        parcel_context,
                        floor,
                        anchor_name
                    ),

                "floor":
                    floor,

                "x":
                    0,

                "y":
                    0,

                "width":
                    anchor_width,

                "depth":
                    anchor_depth,

                "zone":
                    anchor_zone,

                "placement_reason":
                    "floor_anchor",

                "anchor_space":
                    None,

                "floor_height":
                    (
                        anchor_space.get(
                            "floor_constraints",
                            {}
                        ).get(
                            "height"
                        )
                        if isinstance(
                            anchor_space.get(
                                "floor_constraints"
                            ),
                            dict
                        )
                        else None
                    ),

                "floor_height_source":
                    (
                        anchor_space.get(
                            "floor_constraints",
                            {}
                        ).get(
                            "height_source"
                        )
                        if isinstance(
                            anchor_space.get(
                                "floor_constraints"
                            ),
                            dict
                        )
                        else None
                    ),

                "coordinate_mode":
                    (
                        "architectural_metric"
                        if metric_floor_ready
                        else "abstract_grid"
                    )

            }

            
            anchor_placement = (
                enrich_entrance_placement(
                    anchor_placement,
                    anchor_space
                )
            )


            floor_placements[
                anchor_key
            ] = anchor_placement


            used_positions.add(
                (
                    0,
                    0
                )
            )


            # ----------------------------------------------
            # PENDING SPACES
            # ----------------------------------------------

            pending_spaces = [

                space

                for space in floor_spaces

                if space is not anchor_space

            ]


            # ----------------------------------------------
            # RELATIONSHIP-DRIVEN ITERATIONS
            #
            # A space is placed when one of its graph
            # neighbors already exists on the SAME floor.
            # ----------------------------------------------

            while pending_spaces:

                progress = False


                for space in list(
                    pending_spaces
                ):

                    name = space.get(
                        "name"
                    )


                    if not name:

                        pending_spaces.remove(
                            space
                        )

                        continue


                    zone = space.get(
                        "planning_zone",
                        space.get(
                            "zone",
                            "public"
                        )
                    )


                    graph_neighbors = adjacency_graph.get(
                        name,
                        []
                    )


                    parent_placement = None
                    parent_name = None


                    for (
                        placed_name,
                        placed_floor
                    ), candidate_placement in floor_placements.items():

                        if placed_floor != floor:

                            continue


                        if placed_name in graph_neighbors:

                            parent_placement = (
                                candidate_placement
                            )

                            parent_name = placed_name

                            break


                    if parent_placement is None:

                        continue


                    resolved_dimensions = space.get(
                        "resolved_dimensions"
                    )


                    width = None
                    depth = None


                    if isinstance(
                        resolved_dimensions,
                        dict
                    ):

                        width = resolved_dimensions.get(
                            "width"
                        )

                        depth = resolved_dimensions.get(
                            "depth"
                        )


                    if metric_floor_ready:

                        try:

                            width = float(
                                width
                            )

                            depth = float(
                                depth
                            )

                        except (
                            TypeError,
                            ValueError
                        ):

                            metric_floor_ready = False


                    offsets = direction_preferences.get(
                        zone,
                        direction_preferences[
                            "public"
                        ]
                    )


                    resolved_x = None
                    resolved_y = None


                    for dx, dy in offsets:

                        if metric_floor_ready:

                            candidate_x, candidate_y = (
                                metric_candidate_from_direction(
                                    parent_placement,
                                    width,
                                    depth,
                                    dx,
                                    dy
                                )
                            )


                            candidate_available = (
                                metric_position_is_free(
                                    candidate_x,
                                    candidate_y,
                                    width,
                                    depth,
                                    floor_placements
                                )
                            )

                        else:

                            candidate_x = (
                                parent_placement[
                                    "x"
                                ]
                                +
                                dx
                            )

                            candidate_y = (
                                parent_placement[
                                    "y"
                                ]
                                +
                                dy
                            )


                            candidate_available = (
                                (
                                    candidate_x,
                                    candidate_y
                                )
                                not in used_positions
                            )


                        if candidate_available:

                            resolved_x = candidate_x
                            resolved_y = candidate_y

                            break


                    if resolved_x is None:

                        if metric_floor_ready:

                            # ----------------------------------
                            # METRIC FALLBACK
                            #
                            # Place the unresolved space after
                            # the current floor right-most edge.
                            #
                            # This is geometrically safe and
                            # does not invent a semantic relation.
                            # ----------------------------------

                            current_right_edges = [

                                (
                                    float(
                                        existing.get(
                                            "x"
                                        )
                                    )
                                    +
                                    float(
                                        existing.get(
                                            "width"
                                        )
                                    )
                                )

                                for existing
                                in floor_placements.values()

                                if (
                                    isinstance(
                                        existing,
                                        dict
                                    )
                                    and
                                    existing.get(
                                        "x"
                                    ) is not None
                                    and
                                    existing.get(
                                        "width"
                                    ) is not None
                                )

                            ]


                            resolved_x = (
                                max(
                                    current_right_edges
                                )
                                if current_right_edges
                                else 0.0
                            )

                            resolved_y = float(
                                parent_placement.get(
                                    "y",
                                    0.0
                                )
                            )

                        else:

                            offset = 1


                            while True:

                                candidate_x = (
                                    parent_placement[
                                        "x"
                                    ]
                                    +
                                    offset
                                )

                                candidate_y = (
                                    parent_placement[
                                        "y"
                                    ]
                                )


                                if (
                                    candidate_x,
                                    candidate_y
                                ) not in used_positions:

                                    resolved_x = candidate_x
                                    resolved_y = candidate_y

                                    break


                                offset += 1


                    placement = {

                        "name":
                            name,

                        "architectural_constraints":
                            get_space_constraints(
                                name,
                                floor
                            ),

                        "protected_zone":
                            bool(
                                space.get(
                                    "protected_zone",
                                    False
                                )
                                or
                                get_space_constraints(
                                    name,
                                    floor
                                ).get(
                                    "protected_zone",
                                    False
                                )
                            ),

                        "placement_decision":
                            resolve_space_edge_preference(
                                resolve_placement_decision(
                                    name,
                                    floor,
                                    zone
                                ),
                                parcel_context,
                                floor,
                                name
                            ),

                        "floor":
                            floor,

                        "x":
                            resolved_x,

                        "y":
                            resolved_y,

                        "width":
                            width,

                        "depth":
                            depth,

                        "zone":
                            zone,

                        "placement_reason":
                            "relationship_anchor",

                        "anchor_space":
                            parent_name,

                        "floor_height":
                            (
                                space.get(
                                    "floor_constraints",
                                    {}
                                ).get(
                                    "height"
                                )
                                if isinstance(
                                    space.get(
                                        "floor_constraints"
                                    ),
                                    dict
                                )
                                else None
                            ),

                        "floor_height_source":
                            (
                                space.get(
                                    "floor_constraints",
                                    {}
                                ).get(
                                    "height_source"
                                )
                                if isinstance(
                                    space.get(
                                        "floor_constraints"
                                    ),
                                    dict
                                )
                                else None
                            ),

                        "coordinate_mode":
                            (
                                "architectural_metric"
                                if metric_floor_ready
                                else "abstract_grid"
                            )

                    }

                

                    placement = (
                        enrich_entrance_placement(
                            placement,
                            space
                        )
                    )


                    floor_placements[
                        (
                            name,
                            floor
                        )
                    ] = placement


                    used_positions.add(
                        (
                            resolved_x,
                            resolved_y
                        )
                    )


                    pending_spaces.remove(
                        space
                    )


                    progress = True


                # ------------------------------------------
                # NO RELATIONSHIP AVAILABLE
                #
                # Do not invent a semantic relation.
                # Allocate only a collision-free abstract
                # position and state the fallback clearly.
                # ------------------------------------------

                if not progress:

                    space = pending_spaces.pop(
                        0
                    )


                    name = space.get(
                        "name"
                    )


                    if not name:

                        continue


                    zone = space.get(
                        "planning_zone",
                        space.get(
                            "zone",
                            "public"
                        )
                    )



                    resolved_dimensions = space.get(
                        "resolved_dimensions"
                    )


                    width = None
                    depth = None


                    if isinstance(
                        resolved_dimensions,
                        dict
                    ):

                        width = resolved_dimensions.get(
                            "width"
                        )

                        depth = resolved_dimensions.get(
                            "depth"
                        )


                    if metric_floor_ready:

                        current_right_edges = [

                            (
                                float(
                                    existing.get(
                                        "x"
                                    )
                                )
                                +
                                float(
                                    existing.get(
                                        "width"
                                    )
                                )
                            )

                            for existing
                            in floor_placements.values()

                            if (
                                isinstance(
                                    existing,
                                    dict
                                )
                                and
                                existing.get(
                                    "x"
                                ) is not None
                                and
                                existing.get(
                                    "width"
                                ) is not None
                            )

                        ]


                        fallback_x = (
                            max(
                                current_right_edges
                            )
                            if current_right_edges
                            else 0.0
                        )

                        fallback_y = 0.0

                    else:

                        fallback_x = 0
                        fallback_y = 0


                        while (
                            fallback_x,
                            fallback_y
                        ) in used_positions:

                            fallback_x += 1


                            if fallback_x > 10:

                                fallback_x = 0
                                fallback_y += 1

                    placement = {

                        "name":
                            name,

                        "architectural_constraints":
                            get_space_constraints(
                                name,
                                floor
                            ),

                        "protected_zone":
                            bool(
                                space.get(
                                    "protected_zone",
                                    False
                                )
                                or
                                get_space_constraints(
                                    name,
                                    floor
                                ).get(
                                    "protected_zone",
                                    False
                                )
                            ),

                        "placement_decision":
                            resolve_space_edge_preference(
                                resolve_placement_decision(
                                    name,
                                    floor,
                                    zone
                                ),
                                parcel_context,
                                floor,
                                name
                            ),

                        "floor":
                            floor,

                        "x":
                            fallback_x,

                        "y":
                            fallback_y,

                        "width":
                            width,

                        "depth":
                            depth,

                        "zone":
                            zone,

                        "placement_reason":
                            "collision_free_fallback",

                        "anchor_space":
                            None,

                        "floor_height":
                            (
                                space.get(
                                    "floor_constraints",
                                    {}
                                ).get(
                                    "height"
                                )
                                if isinstance(
                                    space.get(
                                        "floor_constraints"
                                    ),
                                    dict
                                )
                                else None
                            ),

                        "floor_height_source":
                            (
                                space.get(
                                    "floor_constraints",
                                    {}
                                ).get(
                                    "height_source"
                                )
                                if isinstance(
                                    space.get(
                                        "floor_constraints"
                                    ),
                                    dict
                                )
                                else None
                            ),

                        "coordinate_mode":
                            (
                                "architectural_metric"
                                if metric_floor_ready
                                else "abstract_grid"
                            )

                    }

                    

                    placement = (
                        enrich_entrance_placement(
                            placement,
                            space
                        )
                    )


                    floor_placements[
                        (
                            name,
                            floor
                        )
                    ] = placement


                    used_positions.add(
                        (
                            fallback_x,
                            fallback_y
                        )
                    )

            # ==================================================
            # FLOOR-TO-FLOOR SUPPORT NORMALIZATION v1.0
            #
            # Validate the completed metric floor arrangement
            # against the immediately preceding floor support.
            #
            # IMPORTANT:
            # - the whole floor is translated rigidly
            # - room-to-room relationships are preserved
            # - dimensions are never changed
            # - no cantilever / overhang is invented
            # - if containment is impossible, geometry remains
            #   unchanged and the condition is reported
            # ==================================================

            current_floor_envelope = None


            if metric_floor_ready:

                metric_placements = []


                for candidate_placement in floor_placements.values():

                    if not isinstance(
                        candidate_placement,
                        dict
                    ):

                        continue


                    candidate_x = candidate_placement.get(
                        "x"
                    )

                    candidate_y = candidate_placement.get(
                        "y"
                    )

                    candidate_width = candidate_placement.get(
                        "width"
                    )

                    candidate_depth = candidate_placement.get(
                        "depth"
                    )


                    try:

                        candidate_x = float(
                            candidate_x
                        )

                        candidate_y = float(
                            candidate_y
                        )

                        candidate_width = float(
                            candidate_width
                        )

                        candidate_depth = float(
                            candidate_depth
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        metric_placements = []

                        break


                    if (
                        candidate_width <= 0.0
                        or
                        candidate_depth <= 0.0
                    ):

                        metric_placements = []

                        break


                    metric_placements.append(
                        {
                            "placement":
                                candidate_placement,

                            "min_x":
                                candidate_x,

                            "min_y":
                                candidate_y,

                            "max_x":
                                (
                                    candidate_x
                                    +
                                    candidate_width
                                ),

                            "max_y":
                                (
                                    candidate_y
                                    +
                                    candidate_depth
                                )
                        }
                    )


                if metric_placements:

                    current_min_x = min(
                        item[
                            "min_x"
                        ]
                        for item in metric_placements
                    )

                    current_min_y = min(
                        item[
                            "min_y"
                        ]
                        for item in metric_placements
                    )

                    current_max_x = max(
                        item[
                            "max_x"
                        ]
                        for item in metric_placements
                    )

                    current_max_y = max(
                        item[
                            "max_y"
                        ]
                        for item in metric_placements
                    )


                    current_floor_envelope = {

                        "min_x":
                            current_min_x,

                        "min_y":
                            current_min_y,

                        "max_x":
                            current_max_x,

                        "max_y":
                            current_max_y,

                        "width":
                            (
                                current_max_x
                                -
                                current_min_x
                            ),

                        "depth":
                            (
                                current_max_y
                                -
                                current_min_y
                            ),

                        "coordinate_mode":
                            "architectural_metric"

                    }


            # --------------------------------------------------
            # SUPPORT VALIDATION
            # --------------------------------------------------

            if (
                isinstance(
                    current_floor_envelope,
                    dict
                )
                and
                isinstance(
                    previous_floor_support_envelope,
                    dict
                )
            ):

                support_min_x = float(
                    previous_floor_support_envelope[
                        "min_x"
                    ]
                )

                support_min_y = float(
                    previous_floor_support_envelope[
                        "min_y"
                    ]
                )

                support_max_x = float(
                    previous_floor_support_envelope[
                        "max_x"
                    ]
                )

                support_max_y = float(
                    previous_floor_support_envelope[
                        "max_y"
                    ]
                )


                current_min_x = float(
                    current_floor_envelope[
                        "min_x"
                    ]
                )

                current_min_y = float(
                    current_floor_envelope[
                        "min_y"
                    ]
                )

                current_max_x = float(
                    current_floor_envelope[
                        "max_x"
                    ]
                )

                current_max_y = float(
                    current_floor_envelope[
                        "max_y"
                    ]
                )


                current_width = (
                    current_max_x
                    -
                    current_min_x
                )

                current_depth = (
                    current_max_y
                    -
                    current_min_y
                )


                support_width = (
                    support_max_x
                    -
                    support_min_x
                )

                support_depth = (
                    support_max_y
                    -
                    support_min_y
                )


                support_tolerance = 1e-9


                floor_support_possible = (

                    current_width
                    <=
                    support_width
                    +
                    support_tolerance

                    and

                    current_depth
                    <=
                    support_depth
                    +
                    support_tolerance

                )


                floor_support_dx = 0.0
                floor_support_dy = 0.0


                if floor_support_possible:

                    # ------------------------------------------
                    # VALID X TRANSLATION INTERVAL
                    #
                    # support_min_x <= current_min_x + dx
                    # current_max_x + dx <= support_max_x
                    # ------------------------------------------

                    minimum_dx = (
                        support_min_x
                        -
                        current_min_x
                    )

                    maximum_dx = (
                        support_max_x
                        -
                        current_max_x
                    )


                    if 0.0 < minimum_dx:

                        floor_support_dx = minimum_dx

                    elif 0.0 > maximum_dx:

                        floor_support_dx = maximum_dx


                    # ------------------------------------------
                    # VALID Y TRANSLATION INTERVAL
                    # ------------------------------------------

                    minimum_dy = (
                        support_min_y
                        -
                        current_min_y
                    )

                    maximum_dy = (
                        support_max_y
                        -
                        current_max_y
                    )


                    if 0.0 < minimum_dy:

                        floor_support_dy = minimum_dy

                    elif 0.0 > maximum_dy:

                        floor_support_dy = maximum_dy


                    support_shift_required = (

                        abs(
                            floor_support_dx
                        )
                        >
                        support_tolerance

                        or

                        abs(
                            floor_support_dy
                        )
                        >
                        support_tolerance

                    )


                    if support_shift_required:

                        for candidate_placement in floor_placements.values():

                            if not isinstance(
                                candidate_placement,
                                dict
                            ):

                                continue


                            candidate_x = candidate_placement.get(
                                "x"
                            )

                            candidate_y = candidate_placement.get(
                                "y"
                            )


                            if not (
                                isinstance(
                                    candidate_x,
                                    (int, float)
                                )
                                and
                                isinstance(
                                    candidate_y,
                                    (int, float)
                                )
                            ):

                                continue


                            candidate_placement[
                                "x"
                            ] = (
                                float(
                                    candidate_x
                                )
                                +
                                floor_support_dx
                            )

                            candidate_placement[
                                "y"
                            ] = (
                                float(
                                    candidate_y
                                )
                                +
                                floor_support_dy
                            )


                    # ------------------------------------------
                    # REBUILD ENVELOPE AFTER RIGID SHIFT
                    # ------------------------------------------

                    current_floor_envelope = {

                        "min_x":
                            (
                                current_min_x
                                +
                                floor_support_dx
                            ),

                        "min_y":
                            (
                                current_min_y
                                +
                                floor_support_dy
                            ),

                        "max_x":
                            (
                                current_max_x
                                +
                                floor_support_dx
                            ),

                        "max_y":
                            (
                                current_max_y
                                +
                                floor_support_dy
                            ),

                        "width":
                            current_width,

                        "depth":
                            current_depth,

                        "coordinate_mode":
                            "architectural_metric"

                    }


                    for candidate_placement in floor_placements.values():

                        if not isinstance(
                            candidate_placement,
                            dict
                        ):

                            continue


                        candidate_placement[
                            "supporting_floor"
                        ] = previous_floor_support_floor


                        candidate_placement[
                            "floor_support_status"
                        ] = (
                            "resolved_with_rigid_shift"
                            if support_shift_required
                            else "resolved_without_shift"
                        )


                        candidate_placement[
                            "floor_support_shift"
                        ] = {

                            "dx":
                                floor_support_dx,

                            "dy":
                                floor_support_dy

                        }


                        candidate_placement[
                            "floor_support_reason"
                        ] = (
                            "floor_arrangement_contained_within_supporting_floor"
                        )


                else:

                    for candidate_placement in floor_placements.values():

                        if not isinstance(
                            candidate_placement,
                            dict
                        ):

                            continue


                        candidate_placement[
                            "supporting_floor"
                        ] = previous_floor_support_floor


                        candidate_placement[
                            "floor_support_status"
                        ] = "requires_design_resolution"


                        candidate_placement[
                            "floor_support_shift"
                        ] = {

                            "dx":
                                0.0,

                            "dy":
                                0.0

                        }


                        candidate_placement[
                            "floor_support_reason"
                        ] = (
                            "floor_extent_exceeds_supporting_floor"
                        )


            elif isinstance(
                current_floor_envelope,
                dict
            ):

                # First resolved floor establishes the initial
                # architectural support envelope.

                for candidate_placement in floor_placements.values():

                    if not isinstance(
                        candidate_placement,
                        dict
                    ):

                        continue


                    candidate_placement[
                        "supporting_floor"
                    ] = None


                    candidate_placement[
                        "floor_support_status"
                    ] = "base_support_floor"


                    candidate_placement[
                        "floor_support_shift"
                    ] = {

                        "dx":
                            0.0,

                        "dy":
                            0.0

                    }


                    candidate_placement[
                        "floor_support_reason"
                    ] = (
                        "first_resolved_metric_floor"
                    )


            # --------------------------------------------------
            # SUPPORT STATE FOR NEXT FLOOR
            #
            # Only a resolved metric floor may become the
            # support reference for the following floor.
            # --------------------------------------------------

            if isinstance(
                current_floor_envelope,
                dict
            ):

                previous_floor_support_envelope = dict(
                    current_floor_envelope
                )

                previous_floor_support_floor = floor

            else:

                previous_floor_support_envelope = None
                previous_floor_support_floor = None

            # ----------------------------------------------
            # PRESERVE ORIGINAL FLOOR SPACE ORDER
            # ----------------------------------------------

            for space in floor_spaces:

                key = (
                    space.get(
                        "name"
                    ),
                    floor
                )


                placement = floor_placements.get(
                    key
                )


                if placement is not None:

                    placements.append(
                        placement
                    )

        # ==================================================
        # PARCEL-AWARE SITE CONTEXT
        #
        # SiteReasoner supplies normalized architectural
        # evidence here.
        #
        # IMPORTANT:
        # Internal placements above are still abstract_grid.
        # Parcel coordinates are real local coordinates.
        #
        # Do not mix the two coordinate systems by inventing
        # x / y values for external spaces.
        # ==================================================

        building_strategy = site_analysis.get(
            "building_strategy",
            {}
        )

        if not isinstance(
            building_strategy,
            dict
        ):

            building_strategy = {}


        access_strategy = site_analysis.get(
            "access_strategy",
            {}
        )

        if not isinstance(
            access_strategy,
            dict
        ):

            access_strategy = {}


        parcel_boundary = building_strategy.get(
            "buildable_boundary",
            building_strategy.get("parcel_boundary")
        )

        coordinate_system = building_strategy.get(
            "coordinate_system"
        )

        target_parcel = building_strategy.get(
            "target_parcel"
        )

        parcel_area = building_strategy.get(
            "parcel_area"
        )

        neighbor_constraints = building_strategy.get(
            "neighbor_constraints",
            []
        )

        road_width = access_strategy.get(
            "road_width"
        )

        parcel_edges = building_strategy.get(
            "parcel_edges",
            []
        )

        if not isinstance(
            parcel_edges,
            list
        ):

            parcel_edges = []


        # ==================================================
        # PARCEL EDGE ROLE INTELLIGENCE v1.0
        #
        # Convert raw CAD edge relations into architectural
        # edge roles without inventing geographic direction.
        #
        # Roles are evidence-based:
        #
        # road             -> access_edge / public_edge
        # neighbor_parcel  -> neighbor_edge / privacy_edge
        # unresolved       -> open_candidate / unresolved
        #
        # Geographic north/south/east/west is intentionally
        # not inferred here.
        # ==================================================

        parcel_edge_roles = []


        for parcel_edge in parcel_edges:

            if not isinstance(
                parcel_edge,
                dict
            ):

                continue


            edge_index = parcel_edge.get(
                "edge_index"
            )

            relation = parcel_edge.get(
                "relation"
            )

            confirmed = bool(
                parcel_edge.get(
                    "confirmed",
                    False
                )
            )


            edge_role = {

                "edge_index":
                    edge_index,

                "relation":
                    relation,

                "confirmed":
                    confirmed,

                "primary_role":
                    None,

                "architectural_roles":
                    [],

                "privacy_constraint":
                    False,

                "access_constraint":
                    False,

                "parcel_id":
                    parcel_edge.get(
                        "parcel_id"
                    ),

                "road_width":
                    parcel_edge.get(
                        "road_width"
                    ),

                "decision_status":
                    "unresolved"

            }


            if (
                confirmed
                and
                relation == "road"
            ):

                edge_role[
                    "primary_role"
                ] = "access_edge"

                edge_role[
                    "architectural_roles"
                ] = [
                    "access_edge",
                    "public_edge",
                    "road_edge"
                ]

                edge_role[
                    "access_constraint"
                ] = True

                edge_role[
                    "decision_status"
                ] = "resolved"


            elif (
                confirmed
                and
                relation == "neighbor_parcel"
            ):

                edge_role[
                    "primary_role"
                ] = "neighbor_edge"

                edge_role[
                    "architectural_roles"
                ] = [
                    "neighbor_edge",
                    "privacy_edge"
                ]

                edge_role[
                    "privacy_constraint"
                ] = True

                edge_role[
                    "decision_status"
                ] = "resolved"


            elif edge_index is not None:

                edge_role[
                    "primary_role"
                ] = "open_candidate"

                edge_role[
                    "architectural_roles"
                ] = [
                    "open_candidate"
                ]

                edge_role[
                    "decision_status"
                ] = "pending"


            parcel_edge_roles.append(
                edge_role
            )


        neighbor_parcels = building_strategy.get(
            "neighbor_parcels",
            []
        )

        if not isinstance(
            neighbor_parcels,
            list
        ):

            neighbor_parcels = []


        access_edge_index = access_strategy.get(
            "access_edge_index"
        )


        geographic_orientation_status = (
            building_strategy.get(
                "geographic_orientation_status"
            )
        )


        road_edges = []

        neighbor_edges = []

        unknown_edges = []


        for parcel_edge in parcel_edges:

            if not isinstance(
                parcel_edge,
                dict
            ):

                continue


            edge_index = parcel_edge.get(
                "edge_index"
            )

            relation = parcel_edge.get(
                "relation"
            )


            if edge_index is None:

                continue


            if relation == "road":

                road_edges.append(
                    edge_index
                )


            elif relation == "neighbor_parcel":

                neighbor_edges.append(
                    edge_index
                )


            else:

                unknown_edges.append(
                    edge_index
                )


        parcel_geometry_available = (

            isinstance(
                parcel_boundary,
                list
            )

            and len(
                parcel_boundary
            ) >= 3

            and coordinate_system
                == "local_normalized"

        )


        parcel_context = {

            "target_parcel":
                target_parcel,

            "coordinate_system":
                coordinate_system,

            "boundary":
                parcel_boundary,

            "area":
                parcel_area,

            "road_width":
                road_width,

            "access_edge_index":
                access_edge_index,

            "road_edges":
                list(
                    road_edges
                ),

            "neighbor_edges":
                list(
                    neighbor_edges
                ),

            "unknown_edges":
                list(
                    unknown_edges
                ),

            "parcel_edges":
                list(
                    parcel_edges
                ),

            "parcel_edge_roles":
                list(
                    parcel_edge_roles
                ),

            "neighbor_parcels":
                list(
                    neighbor_parcels
                ),

            "neighbor_constraints":
                neighbor_constraints,

            "geographic_orientation_status":
                geographic_orientation_status,

            "geometry_available":
                parcel_geometry_available

        }

        # ==================================================
        # PARCEL EDGE SELECTION INTELLIGENCE v1.0
        #
        # Resolve architectural edge preference without
        # inventing geographic direction or real coordinates.
        #
        # Edge identity is based only on confirmed CAD
        # parcel-edge evidence.
        # ==================================================

        all_edge_indices = []


        if isinstance(
            parcel_boundary,
            list
        ):

            all_edge_indices = list(
                range(
                    len(
                        parcel_boundary
                    )
                )
            )


        open_edge_indices = [

            edge_index

            for edge_index in all_edge_indices

            if (
                edge_index not in road_edges
                and
                edge_index not in neighbor_edges
            )

        ]


        def resolve_external_edge_intent(
            external_name,
            placement_rule
        ):

            normalized_name = str(
                external_name or ""
            ).lower()

            normalized_rule = str(
                placement_rule or ""
            ).lower()


            result = {

                "preferred_edge_index":
                    None,

                "edge_relation":
                    None,

                "edge_decision_status":
                    "unresolved",

                "edge_decision_reason":
                    None

            }


            if not parcel_geometry_available:

                result[
                    "edge_decision_reason"
                ] = "parcel_geometry_unavailable"

                return result


            # ------------------------------------------
            # TERRACE
            #
            # Prefer a confirmed non-road,
            # non-neighbor/open parcel edge.
            # ------------------------------------------

            if (
                normalized_name == "terrace"
                or
                normalized_rule
                == "adjacent_to_public_space"
            ):

                if open_edge_indices:

                    result[
                        "preferred_edge_index"
                    ] = open_edge_indices[0]

                    result[
                        "edge_relation"
                    ] = "open"

                    result[
                        "edge_decision_status"
                    ] = "resolved"

                    result[
                        "edge_decision_reason"
                    ] = (
                        "prefer_open_edge_away_from_neighbor_privacy_constraints"
                    )

                    return result


                result[
                    "edge_decision_status"
                ] = "pending"

                result[
                    "edge_decision_reason"
                ] = (
                    "no_confirmed_open_edge_available"
                )

                return result


            # ------------------------------------------
            # GARDEN
            #
            # Prefer open edge first.
            # Road edge may remain a secondary
            # architectural possibility, but is not
            # selected automatically here.
            # ------------------------------------------

            if (
                normalized_name == "garden"
                or
                normalized_rule == "open_edge"
            ):

                if open_edge_indices:

                    result[
                        "preferred_edge_index"
                    ] = open_edge_indices[0]

                    result[
                        "edge_relation"
                    ] = "open"

                    result[
                        "edge_decision_status"
                    ] = "resolved"

                    result[
                        "edge_decision_reason"
                    ] = "confirmed_open_parcel_edge"

                    return result


                result[
                    "edge_decision_status"
                ] = "pending"

                result[
                    "edge_decision_reason"
                ] = (
                    "open_edge_not_confirmed"
                )

                return result


            return result


        # ==================================================
        # EXTERNAL SPACE RELATIONS
        #
        # External spaces receive semantic placement
        # evidence, but no site coordinate is invented.
        #
        # Real coordinates belong to parcel-aware
        # placement intelligence.
        # ==================================================

        for external in external_spaces:

            if not isinstance(
                external,
                dict
            ):

                continue


            name = external.get(
                "name"
            )


            if not name:

                continue


            preferred_neighbors = external.get(
                "preferred_neighbors",
                []
            )


            if not isinstance(
                preferred_neighbors,
                list
            ):

                preferred_neighbors = []


            graph_neighbors = adjacency_graph.get(
                name,
                []
            )


            anchor_candidates = []


            for candidate in preferred_neighbors:

                if candidate not in anchor_candidates:

                    anchor_candidates.append(
                        candidate
                    )


            for candidate in graph_neighbors:

                if candidate not in anchor_candidates:

                    anchor_candidates.append(
                        candidate
                    )


            external_anchor = (
                anchor_candidates[0]
                if anchor_candidates
                else None
            )

            edge_intent = (
                resolve_external_edge_intent(
                    name,
                    external.get(
                        "placement_rule"
                    )
                )
            )


            placement = {

                "name":
                    name,

                "floor":
                    None,

                "x":
                    None,

                "y":
                    None,

                "width":
                    None,

                "depth":
                    None,

                "zone":
                    "external",

                "placement_reason":
                    external.get(
                        "placement_rule"
                    ),

                "anchor_space":
                    external_anchor,

                "relation_to_building":
                    external.get(
                        "relation_to_building"
                    ),

                "preferred_edge_index":
                    edge_intent.get(
                        "preferred_edge_index"
                    ),

                "edge_relation":
                    edge_intent.get(
                        "edge_relation"
                    ),

                "edge_decision_status":
                    edge_intent.get(
                        "edge_decision_status"
                    ),

                "edge_decision_reason":
                    edge_intent.get(
                        "edge_decision_reason"
                    ),

                "coordinate_mode":
                    (
                        "parcel_context_available"
                        if parcel_geometry_available
                        else "parcel_pending"
                    ),

                "site_context":
                    dict(
                        parcel_context
                    )

            }

            


            placements.append(
                placement
            )


        return placements
