from copy import deepcopy


def enrich_space_semantics(room):

    room_name = str(room).lower()

    if room_name in [
        "stairs",
        "vertical_core",
        "core"
    ]:
        return {
            "space_type": "vertical_core",
            "canonical_name": "vertical_core",
            "zone": "circulation",
            "protected_zone": True,
            "circulation_profile": {
                "role": "vertical"
            }
        }

    if room_name in [
        "living",
        "living_room"
    ]:
        return {
            "space_type": "living",
            "canonical_name": "living_room",
            "zone": "public"
        }

    if room_name in [
        "bedroom",
        "master_bedroom"
    ]:
        return {
            "space_type": "bedroom",
            "canonical_name": room_name,
            "zone": "private"
        }

    if room_name in [
        "bathroom",
        "wc"
    ]:
        return {
            "space_type": "service",
            "canonical_name": room_name,
            "zone": "service"
        }

    return {
        "space_type": room_name,
        "canonical_name": room_name
    }



class DesignAgent:


    def __init__(self, style="balanced"):

        self.style = style


    def build(self, plan):

        design = {}

        # =====================================
        # ARCHITECTURAL INTENT
        # =====================================

        architectural_intent = plan.get(
            "architectural_intent",
            {}
        )

        building_type = architectural_intent.get(
            "building_type",
            plan.get(
                "building_type",
                "generic"
            )
        )

        style = (
            architectural_intent.get("style")
            or plan.get(
                "style",
                self.style
            )
        )

        materials = architectural_intent.get(
            "materials",
            []
        )

        objects = architectural_intent.get(
            "objects",
            []
        )

        site_features = architectural_intent.get(
            "site",
            []
        )

        environment = architectural_intent.get(
            "environment",
            []
        )

        floors = plan.get(
            "floors",
            1
        )

        plan_requirements = plan.get(
            "plan_requirements"
        )

        authoritative_plan_program = plan.get(
            "authoritative_plan_program"
        )

        authoritative_program = (
            plan.get("program_source") == "plan_requirements"
            and
            isinstance(plan_requirements, dict)
            and
            plan_requirements.get("contract")
            == "ArchitecturalPlanRequirementsV1"
            and
            isinstance(authoritative_plan_program, dict)
            and
            authoritative_plan_program.get("contract")
            == "AuthoritativeSemanticPlanProgramV1"
        )

        source_spaces = (
            authoritative_plan_program.get("spaces", {})
            if authoritative_program
            else plan.get("spaces", {})
        )

        spaces = (
            deepcopy(source_spaces)
            if isinstance(source_spaces, dict)
            else {}
        )

        authoritative_required_space_types = {
            str(item.get("space_type") or "").lower()
            for item in (
                plan_requirements.get("spaces", [])
                if isinstance(plan_requirements, dict)
                else []
            )
            if isinstance(item, dict)
            and item.get("required") is True
        }

        units = plan.get(
            "units",
            {
                "per_floor": 1
            }
        )

        units_per_floor = units.get(
            "per_floor",
            1
        )

        # =====================================
        # BUILDING PROGRAM / CORE INTENT
        # =====================================

        building_program = architectural_intent.get(
            "building_program",
            {}
        )

        if not isinstance(
            building_program,
            dict
        ):
            building_program = {}

        core_program = building_program.get(
            "core",
            {}
        )

        if not isinstance(
            core_program,
            dict
        ):
            core_program = {}


        vertical_systems = building_program.get(
            "vertical_systems",
            []
        )

        if not isinstance(
            vertical_systems,
            list
        ):
            vertical_systems = []


        stair_system = {}

        for vertical_system in vertical_systems:

            if not isinstance(
                vertical_system,
                dict
            ):
                continue

            if vertical_system.get(
                "type"
            ) == "stairs":

                stair_system = dict(
                    vertical_system
                )

                break


        stair_parameters = stair_system.get(
            "parameters",
            {}
        )

        if not isinstance(
            stair_parameters,
            dict
        ):
            stair_parameters = {}


        stair_connects = stair_system.get(
            "connects",
            []
        )

        if not isinstance(
            stair_connects,
            list
        ):
            stair_connects = []


        program_stairs = core_program.get(
            "stairs",
            []
        )

        stairs_required = (
            (
                isinstance(
                    program_stairs,
                    list
                )
                and
                len(program_stairs) > 0
            )
            or
            bool(
                stair_system
            )
        )

        vertical_transport = architectural_intent.get(
            "vertical_transport",
            {}
        )

        if not isinstance(vertical_transport, dict):
            vertical_transport = {}

        explicit_vertical_transport = any(
            isinstance(vertical_transport.get(system_name), list)
            and bool(vertical_transport.get(system_name))
            for system_name in (
                "elevators", "stairs", "ramps", "escalators"
            )
        )

        protected_vertical_system = any(
            isinstance(vertical_system, dict)
            and vertical_system.get("protected_zone") is True
            for vertical_system in vertical_systems
        )

        vertical_core_required = (
            not authoritative_program
            or bool(
                authoritative_required_space_types
                & {"stairs", "vertical_core", "elevator"}
            )
            or explicit_vertical_transport
            or (floors > 1 and protected_vertical_system)
        )

        # =====================================
        # FLOOR-AWARE SPACE PROGRAM LOOKUP
        #
        # Planner preserves full architectural
        # space metadata in `space_program`.
        #
        # DesignAgent maps that metadata onto
        # floor-specific design nodes without
        # resolving geometry here.
        # =====================================

        space_program = plan.get(
            "space_program",
            []
        )

        if not isinstance(
            space_program,
            list
        ):
            space_program = []


        space_program_lookup = {}


        for space_contract in space_program:

            if not isinstance(
                space_contract,
                dict
            ):
                continue

            space_name = space_contract.get(
                "name"
            )

            planner_floor = space_contract.get(
                "planner_floor"
            )

            if not space_name:
                continue


            lookup_key = (
                str(space_name).lower(),
                str(planner_floor).lower()
                if planner_floor is not None
                else None
            )


            space_program_lookup[
                lookup_key
            ] = space_contract


        def get_space_program_metadata(
            room,
            planner_floor
        ):

            lookup_key = (
                str(room).lower(),
                str(planner_floor).lower()
            )


            space_contract = (
                space_program_lookup.get(
                    lookup_key
                )
            )


            if not isinstance(
                space_contract,
                dict
            ):
                return {}


            metadata = {}


            zone = space_contract.get(
                "zone"
            )

            if zone is not None:

                metadata[
                    "zone"
                ] = zone


            floor_role = space_contract.get(
                "floor"
            )

            if floor_role is not None:

                metadata[
                    "program_floor"
                ] = floor_role


            dimensional_requirements = (
                space_contract.get(
                    "dimensional_requirements"
                )
            )

            if isinstance(
                dimensional_requirements,
                dict
            ):

                metadata[
                    "dimensional_requirements"
                ] = dict(
                    dimensional_requirements
                )


            return metadata

        # =====================================
        # INTENT SPACE ENRICHMENT
        # =====================================

        if building_type == "house" and not authoritative_program:

            spaces.setdefault(
                "ground_floor",
                []
            )

            spaces.setdefault(
                "typical_floor",
                []
            )

            ground_defaults = [
                "entrance",
                "living",
                "kitchen",
                "stairs"
            ]

            typical_defaults = [
                "living",
                "kitchen",
                "bedroom",
                "bathroom"
            ]

            for room in ground_defaults:

                if room not in spaces["ground_floor"]:

                    spaces["ground_floor"].append(
                        room
                    )

            for room in typical_defaults:

                if room not in spaces["typical_floor"]:

                    spaces["typical_floor"].append(
                        room
                    )

        # =====================================
        # FLOOR GENERATION
        # =====================================

        for i in range(floors):

            floor_number = i + 1

            floor_name = f"F{floor_number}"

            nodes = {}

            connections = []

            # =====================================
            # GROUND FLOOR
            # =====================================

            if floor_number == 1:

                rooms = spaces.get(
                    "ground_floor",
                    [
                        "lobby",
                        "entrance",
                        "stairs"
                    ]
                )

                for index, room in enumerate(rooms):

                    node_id = (
                        f"{floor_name}_{room}_{index}"
                    )

                    nodes[node_id] = {

                        "type":
                            room,

                        **enrich_space_semantics(
                            room
                        ),

                        **get_space_program_metadata(
                            room,
                            "ground_floor"
                        )

                    }

                    if (
                        str(room).lower()
                        in {
                            "stairs",
                            "stair"
                        }
                        and
                        stair_system
                    ):

                        nodes[node_id][
                            "vertical_system_type"
                        ] = "stairs"

                        nodes[node_id][
                            "vertical_role"
                        ] = stair_system.get(
                            "role"
                        )

                        nodes[node_id][
                            "connects"
                        ] = list(
                            stair_connects
                        )

                        nodes[node_id][
                            "parameters"
                        ] = dict(
                            stair_parameters
                        )

                        nodes[node_id][
                            "protected_zone"
                        ] = stair_system.get(
                            "protected_zone",
                            nodes[node_id].get(
                                "protected_zone",
                                False
                            )
                        )

                        nodes[node_id][
                            "vertical_system_contract"
                        ] = dict(
                            stair_system
                        )

            # =====================================
            # UPPER FLOORS
            # =====================================

            else:

                typical_spaces = spaces.get(
                    "typical_floor",
                    [
                        "living",
                        "kitchen",
                        "bedroom",
                        "bathroom"
                    ]
                )

                for unit in range(
                    units_per_floor
                ):

                    apartment_id = (
                        f"UNIT_{unit+1}"
                    )

                    unit_nodes = []

                    for index, room in enumerate(
                        typical_spaces
                    ):

                        node_id = (
                            f"{floor_name}_{apartment_id}_{room}_{index}"
                        )

                        nodes[node_id] = {

                            "type":
                                room,

                            "unit":
                                unit + 1,

                            **enrich_space_semantics(
                                room
                            ),

                            **get_space_program_metadata(
                                room,
                                "typical_floor"
                            )

                        }

                        unit_nodes.append(
                            node_id
                        )

                    # apartment internal graph

                    # =====================================
                    # KNOWLEDGE-DRIVEN UNIT GRAPH
                    # =====================================
                    #
                    # Do not create artificial sequential
                    # room-to-room connections here.
                    #
                    # Real architectural relationships are
                    # resolved later by the architectural
                    # relationship graph from Planner /
                    # BuildingProgramKnowledge.
                    # =====================================

                    pass

            # =====================================
            # FLOOR-AWARE VERTICAL LANDING
            # =====================================
            #
            # A required stair must terminate on
            # every connected upper floor.
            #
            # The landing is the architectural
            # interface between the vertical core
            # and the floor circulation system.
            # =====================================

            if (
                floor_number > 1
                and
                stairs_required
            ):

                landing_id = (
                    f"{floor_name}_stair_landing"
                )

                nodes[landing_id] = {
                    "type":
                        "stair_landing",

                    "space_type":
                        "circulation",

                    "canonical_name":
                        "stair_landing",

                    "zone":
                        "circulation",

                    "protected_zone":
                        stair_system.get(
                            "protected_zone",
                            True
                        ),

                    "circulation_profile":
                        {
                            "role":
                                "vertical_landing"
                        },

                    "vertical_system_type":
                        "stairs",

                    "vertical_role":
                        stair_system.get(
                            "role"
                        ),

                    "connects":
                        list(
                            stair_connects
                        ),

                    "parameters":
                        dict(
                            stair_parameters
                        ),

                    "vertical_system_contract":
                        dict(
                            stair_system
                        )
                }

            # =====================================
            # VERTICAL CORE
            # =====================================

            core_id = (
                f"{floor_name}_core"
            )

            if vertical_core_required:

                nodes[core_id] = {

                    "type":
                        "vertical_core",

                    "space_type":
                        "vertical_core",

                    "canonical_name":
                        "vertical_core",

                    "zone":
                        "circulation",

                    "protected_zone":
                        True,

                    "circulation_profile":
                        {
                            "role":
                                "vertical"
                        },

                    "vertical_system_contracts":
                        [
                            dict(vertical_system)

                            for vertical_system
                            in vertical_systems

                            if (
                                isinstance(
                                    vertical_system,
                                    dict
                                )
                                and
                                vertical_system.get(
                                    "protected_zone"
                                )
                                is True
                                and
                                (
                                    not vertical_system.get(
                                        "connects"
                                    )
                                    or
                                    floor_name
                                    in vertical_system.get(
                                        "connects",
                                        []
                                    )
                                )
                            )
                        ]
                }

            # =====================================
            # FLOOR ARRIVAL CONNECTION CONTRACT
            # =====================================
            #
            # An upper-floor stair landing must join
            # the usable floor graph through the most
            # appropriate circulation / shared space.
            #
            # IMPORTANT:
            # - Do not connect directly to bedrooms or
            #   service rooms.
            # - Do not hardcode family_lounge.
            # - Prefer circulation and shared spaces.
            # - If no architecturally valid arrival
            #   space exists, do not invent one.
            # =====================================

            if (
                floor_number > 1
                and
                stairs_required
            ):

                landing_id = (
                    f"{floor_name}_stair_landing"
                )

                if landing_id in nodes:

                    arrival_candidates = []

                    arrival_type_priority = {
                        "corridor": 1000,
                        "hall": 950,
                        "lobby": 900,
                        "unit_entry": 850,
                        "entry_hall": 850,
                        "family_lounge": 800,
                        "living": 750,
                        "living_room": 750
                    }

                    for (
                        candidate_id,
                        candidate_data
                    ) in nodes.items():

                        if candidate_id in {
                            landing_id,
                            core_id
                        }:
                            continue

                        if not isinstance(
                            candidate_data,
                            dict
                        ):
                            continue

                        candidate_type = str(
                            candidate_data.get(
                                "type",
                                ""
                            )
                        ).lower()

                        candidate_space_type = str(
                            candidate_data.get(
                                "space_type",
                                ""
                            )
                        ).lower()

                        candidate_canonical = str(
                            candidate_data.get(
                                "canonical_name",
                                ""
                            )
                        ).lower()

                        candidate_zone = str(
                            candidate_data.get(
                                "zone",
                                ""
                            )
                        ).lower()

                        # ---------------------------------
                        # INVALID ARRIVAL TARGETS
                        # ---------------------------------

                        if candidate_zone in {
                            "private",
                            "service"
                        }:
                            continue

                        if candidate_type in {
                            "stairs",
                            "stair",
                            "stair_landing",
                            "vertical_core",
                            "core",
                            "elevator",
                            "lift",
                            "bathroom",
                            "wc",
                            "bedroom",
                            "master_bedroom"
                        }:
                            continue

                        # ---------------------------------
                        # ARCHITECTURAL ARRIVAL SCORE
                        # ---------------------------------

                        arrival_score = 0

                        for semantic_name in {
                            candidate_type,
                            candidate_space_type,
                            candidate_canonical
                        }:

                            arrival_score = max(
                                arrival_score,
                                arrival_type_priority.get(
                                    semantic_name,
                                    0
                                )
                            )

                        if candidate_zone == "circulation":
                            arrival_score += 500

                        elif candidate_zone == "semi_public":
                            arrival_score += 300

                        elif candidate_zone == "public":
                            arrival_score += 200

                        if arrival_score <= 0:
                            continue

                        arrival_candidates.append(
                            (
                                -arrival_score,
                                str(candidate_id),
                                candidate_id
                            )
                        )

                    if arrival_candidates:

                        arrival_candidates.sort()

                        arrival_node_id = (
                            arrival_candidates[0][2]
                        )

                        connections.append(
                            {
                                "from":
                                    landing_id,

                                "to":
                                    arrival_node_id,

                                "type":
                                    "direct_connection",

                                "source":
                                    "floor_arrival_contract"
                            }
                        )

            # =====================================
            # ARCHITECTURAL RELATIONSHIP GRAPH
            # =====================================

            relationship_sources = []

            plan_relationships = plan.get(
                "relationships",
                []
            )

            if isinstance(
                plan_relationships,
                list
            ):
                relationship_sources.extend(
                    plan_relationships
                )


            intent_relationships = architectural_intent.get(
                "relationships",
                []
            )

            if isinstance(
                intent_relationships,
                list
            ):
                relationship_sources.extend(
                    intent_relationships
                )


            # -------------------------------------
            # BUILD SEMANTIC NODE LOOKUP
            # -------------------------------------

            semantic_node_map = {}


            for node_id, node_data in nodes.items():

                if not isinstance(
                    node_data,
                    dict
                ):
                    continue


                candidates = [
                    node_data.get("type"),
                    node_data.get("space_type"),
                    node_data.get("canonical_name")
                ]


                for candidate in candidates:

                    if not candidate:
                        continue


                    key = str(
                        candidate
                    ).lower()


                    semantic_node_map.setdefault(
                        key,
                        []
                    ).append(
                        node_id
                    )


            # -------------------------------------
            # RELATION TYPE NORMALIZATION
            # -------------------------------------

            relation_type_map = {

                "connected":
                    "direct_connection",

                "direct_access":
                    "direct_connection",

                "adjacent":
                    "adjacent",

                "semantic_adjacent":
                    "semantic_adjacent",

                "private_connection":
                    "private_connection",

                "vertical_connection":
                    "vertical_connection",

                "visual_connection":
                    "visual_connection",

                "connected_to":
                    "direct_connection"
            }


            # -------------------------------------
            # BUILD REAL ARCHITECTURAL EDGES
            # -------------------------------------

            relationship_edges = set()


            for relation in relationship_sources:

                if not isinstance(
                    relation,
                    dict
                ):
                    continue


                source_name = relation.get(
                    "from"
                )

                target_name = relation.get(
                    "to"
                )

                relation_type = relation.get(
                    "type",
                    "connected"
                )


                if not source_name or not target_name:
                    continue


                source_key = str(
                    source_name
                ).lower()

                target_key = str(
                    target_name
                ).lower()


                # living_room <-> living compatibility
                aliases = {

                    "living_room":
                        "living",

                    "living":
                        "living",

                    "guest":
                        "guest_room",

                    "guest_room":
                        "guest_room",

                    "stairs":
                        "stairs",

                    "stair":
                        "stairs"
                }


                source_lookup = aliases.get(
                    source_key,
                    source_key
                )

                target_lookup = aliases.get(
                    target_key,
                    target_key
                )


                source_nodes = semantic_node_map.get(
                    source_lookup,
                    []
                )

                target_nodes = semantic_node_map.get(
                    target_lookup,
                    []
                )


                # Relationship belongs to another floor /
                # site / roof. Do not invent a local edge.
                if not source_nodes or not target_nodes:
                    continue


                normalized_relation_type = (
                    relation_type_map.get(
                        str(relation_type).lower(),
                        str(relation_type).lower()
                    )
                )


                for source_node in source_nodes:

                    for target_node in target_nodes:

                        if source_node == target_node:
                            continue


                        edge_key = tuple(
                            sorted(
                                [
                                    source_node,
                                    target_node
                                ]
                            )
                        )


                        if edge_key in relationship_edges:
                            continue


                        relationship_connection = {
                            "from": source_node,
                            "to": target_node,
                            "type": normalized_relation_type,
                            "source": "architectural_relationship",
                        }

                        if relation.get("validation_status"):
                            relationship_connection.update({
                                "requirement": relation.get("requirement"),
                                "validation_status": relation.get(
                                    "validation_status"
                                ),
                                "validation_requires": relation.get(
                                    "validation_requires"
                                ),
                                "geometric": False,
                            })

                        connections.append(
                            relationship_connection
                        )


                        relationship_edges.add(
                            edge_key
                        )


            # =====================================
            # VERTICAL CORE CONTRACT
            # =====================================
            #
            # Core is NOT a universal room hub.
            # Only explicit circulation spaces
            # attach directly to it.
            # =====================================

            for node_id, node_data in nodes.items():

                if not vertical_core_required:
                    continue

                if node_id == core_id:
                    continue


                if not isinstance(
                    node_data,
                    dict
                ):
                    continue


                node_type = str(
                    node_data.get(
                        "type",
                        ""
                    )
                ).lower()


                node_space_type = str(
                    node_data.get(
                        "space_type",
                        ""
                    )
                ).lower()


                protected_zone = (
                    node_data.get(
                        "protected_zone"
                    )
                    is True
                )


                is_circulation = (

                    node_type in {
                        "stairs",
                        "stair",
                        "elevator",
                        "lift"
                    }

                    or

                    (
                        node_space_type
                        in {
                            "circulation",
                            "vertical_transport"
                        }
                    )

                    or

                    (
                        protected_zone
                        and
                        node_id != core_id
                        and
                        node_type
                        not in {
                            "vertical_core",
                            "core"
                        }
                    )

                )


                if not is_circulation:
                    continue


                edge_key = tuple(
                    sorted(
                        [
                            node_id,
                            core_id
                        ]
                    )
                )


                if edge_key in relationship_edges:
                    continue


                connections.append(
                    {
                        "from":
                            node_id,

                        "to":
                            core_id,

                        "type":
                            "direct_connection",

                        "source":
                            "vertical_circulation_contract"
                    }
                )


                relationship_edges.add(
                    edge_key
                )

            # =====================================
            # COMMIT FLOOR DESIGN
            # =====================================

            design[floor_name] = {

                "nodes":
                    nodes,

                "connections":
                    connections

            }

        # =====================================
        # ROOF
        # =====================================

        if "roof" in spaces:

            nodes = {}

            connections = []

            for index, item in enumerate(
                spaces["roof"]
            ):

                node_id = (
                    f"ROOF_{item}_{index}"
                )

                nodes[node_id] = {

                    "type":
                        item

                }

            design["ROOF"] = {

                "nodes":
                    nodes,

                "connections":
                    connections

            }

        # =====================================
        # SITE
        # =====================================

        if "site" in spaces:

            nodes = {}

            connections = []

            for index, item in enumerate(
                spaces["site"]
            ):

                node_id = (
                    f"SITE_{item}_{index}"
                )

                nodes[node_id] = {

                    "type":
                        item

                }

            design["SITE"] = {

                "nodes":
                    nodes,

                "connections":
                    connections

            }

        # =====================================
        # METADATA
        # =====================================

        design["metadata"] = {

            "building_type":
                building_type,

            "style":
                style,

            "materials":
                materials,

            "objects":
                objects,

            "site":
                site_features,

            "environment":
                environment,

            "architectural_intent":
                architectural_intent,

            "program_source":
                plan.get("program_source"),

            "plan_requirements":
                deepcopy(plan_requirements),

            "authoritative_plan_program":
                deepcopy(authoritative_plan_program),

            "relationship_constraints":
                deepcopy(plan.get("relationships", [])),

            "circulation_constraint":
                deepcopy(plan.get("circulation")),

            "geometry_validation":
                deepcopy(plan.get("geometry_validation"))

        }

        return design
