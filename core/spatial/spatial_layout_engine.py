"""
ArchitectOS Spatial Layout Engine v19.3

Generates spatial contract from design graph.

Features:
- Multi floor support
- Building program awareness
- Graph based rooms
- Safe metadata filtering
- Backward compatible with v19.2
"""


class SpatialLayoutEngine:


    VERSION = "19.3"



    def __init__(self):

        self.version = self.VERSION

        print(
            f"📐 Spatial Layout Engine v{self.version} ACTIVE"
        )



    # ==================================================
    # GENERATE SPATIAL
    # ==================================================

    def generate(
        self,
        design,
        plan,
        architectural_intent=None
    ):


        spatial = {


            "version":
                self.version,


            "site":
                plan.get(
                    "site",
                    {}
                ),


            "floors":
                {},


            "strategy":
                "adaptive_spatial_layout_v19.3"

        }



        # ==================================================
        # NORMALIZE DESIGN INPUT
        # ==================================================

        if isinstance(design, list):


            design = {


                "F1": {


                    "nodes":
                    {

                        f"node_{i}": item

                        for i, item in enumerate(design)

                    },


                    "connections":
                    []

                }

            }



        elif (

            isinstance(design, dict)

            and "nodes" in design

        ):


            design = {


                "F1":
                    design

            }



        elif not isinstance(design, dict):


            design = {}




        # ==================================================
        # DETECT REQUIRED FLOORS
        # ==================================================

        required_floors = []

        building_program = {}

        if isinstance(
            architectural_intent,
            dict
        ):

            building_program = architectural_intent.get(
                "building_program",
                {}
            )

            if not isinstance(
                building_program,
                dict
            ):

                building_program = {}


        levels = building_program.get(
            "levels",
            []
        )


        if not isinstance(
            levels,
            list
        ):

            levels = []


        for level in levels:

            if not isinstance(
                level,
                dict
            ):

                continue


            name = level.get(
                "level"
            )


            if name:

                required_floors.append(
                    name
                )




        print(

            "🟢 REQUIRED FLOORS:",

            required_floors

        )




        # ==================================================
        # PROCESS DESIGN FLOORS
        # ==================================================

        for floor, data in design.items():



            if floor in [

                "ROOF",
                "SITE",
                "metadata",
                "reasoning",
                "adaptive_critic",
                "status",
                "version"

            ]:

                continue



            if not isinstance(data, dict):

                continue



            nodes = data.get(
                "nodes",
                None
            )

            connections = data.get(
                "connections",
                []
            )


            if not isinstance(
                connections,
                list
            ):

                connections = []

            # ==========================================
            # SUPPORT NEW SPATIAL GRAPH FORMAT
            # ==========================================

            if nodes is None:

                nodes = {

                    k:v

                    for k,v in data.items()

                    if isinstance(v, dict)

                    and (
                        "x" in v
                        or "y" in v
                        or "w" in v
                        or "h" in v
                    )

                }


            if not isinstance(nodes, dict):

                continue


            spaces = []

            FALLBACK_UNIT = 4.0

            # ==========================================
            # GRAPH-AWARE FALLBACK CONTEXT
            # ==========================================

            connection_map = {}


            for connection in connections:

                source = None
                target = None
                relation_type = None


                # ==========================================
                # DICT CONNECTION CONTRACT
                # ==========================================

                if isinstance(
                    connection,
                    dict
                ):

                    source = connection.get(
                        "from"
                    )

                    target = connection.get(
                        "to"
                    )

                    relation_type = connection.get(
                        "type"
                    )


                # ==========================================
                # LEGACY / DESIGN AGENT LIST CONTRACT
                # ==========================================

                elif (
                    isinstance(
                        connection,
                        (list, tuple)
                    )
                    and
                    len(connection) >= 2
                ):

                    source = connection[0]
                    target = connection[1]

                    relation_type = (
                        "direct_connection"
                    )


                else:

                    continue


                if not source or not target:

                    continue


                connection_map.setdefault(
                    source,
                    []
                ).append(
                    {
                        "target":
                            target,

                        "type":
                            relation_type
                    }
                )


                connection_map.setdefault(
                    target,
                    []
                ).append(
                    {
                        "target":
                            source,

                        "type":
                            relation_type
                    }
                )


            resolved_positions = {}

            occupied_rectangles = []

            DEBUG_SPATIAL_GRAPH = False

            reserved_rectangles = []


            def rectangles_overlap(
                x,
                y,
                w,
                h,
                other
            ):

                return not (

                    x + w <= other["x"]

                    or

                    other["x"] + other["w"] <= x

                    or

                    y + h <= other["y"]

                    or

                    other["y"] + other["h"] <= y

                )


            def position_is_free(
                x,
                y,
                w,
                h,
                space_name=None
            ):

                # ======================================
                # REAL OCCUPANCY
                # ======================================

                for rectangle in occupied_rectangles:

                    if rectangles_overlap(
                        x,
                        y,
                        w,
                        h,
                        rectangle
                    ):

                        return False


                # ======================================
                # FUTURE RESERVATION OCCUPANCY
                #
                # A reserved rectangle behaves like
                # occupied geometry for every space
                # except its own reservation owner.
                # ======================================

                for reservation in reserved_rectangles:

                    reservation_owner = reservation.get(
                        "name"
                    )

                    if (
                        space_name is not None
                        and
                        reservation_owner == space_name
                    ):

                        continue


                    if rectangles_overlap(
                        x,
                        y,
                        w,
                        h,
                        reservation
                    ):

                        return False


                return True


            def get_space_reservation(
                space_name
            ):

                if not space_name:

                    return None


                for reservation in reserved_rectangles:

                    if reservation.get(
                        "name"
                    ) == space_name:

                        return reservation


                return None


            def release_space_reservation(
                space_name
            ):

                if not space_name:

                    return


                reserved_rectangles[:] = [

                    reservation

                    for reservation
                    in reserved_rectangles

                    if reservation.get(
                        "name"
                    ) != space_name

                ]


            def reserve_future_assignments(
                assignments,
                created_by=None
            ):

                if not isinstance(
                    assignments,
                    list
                ):

                    return


                for assignment in assignments:

                    if not isinstance(
                        assignment,
                        dict
                    ):

                        continue


                    reservation_name = assignment.get(
                        "name"
                    )


                    if not reservation_name:

                        continue

                    
                    if reservation_name in resolved_positions:

                        continue


                    # ==================================
                    # FIRST VALID CONTRACT WINS
                    #
                    # Do not silently move an existing
                    # reservation generated by an earlier
                    # graph decision.
                    # ==================================

                    existing_reservation = (
                        get_space_reservation(
                            reservation_name
                        )
                    )

                    if existing_reservation is not None:

                        continue


                    reservation = {

                        "name":
                            reservation_name,

                        "x":
                            assignment.get(
                                "x"
                            ),

                        "y":
                            assignment.get(
                                "y"
                            ),

                        "w":
                            assignment.get(
                                "w"
                            ),

                        "h":
                            assignment.get(
                                "h"
                            ),

                        "created_by":
                            created_by

                    }


                    if (
                        reservation["x"] is None
                        or
                        reservation["y"] is None
                        or
                        reservation["w"] is None
                        or
                        reservation["h"] is None
                    ):

                        continue


                    reserved_rectangles.append(
                        reservation
                    )


                    if DEBUG_SPATIAL_GRAPH:

                        print(
                            "🔒 FUTURE SPACE RESERVED:",
                            "OWNER=",
                            reservation_name,
                            "BY=",
                            created_by,
                            "X=",
                            reservation["x"],
                            "Y=",
                            reservation["y"],
                            "W=",
                            reservation["w"],
                            "H=",
                            reservation["h"]
                        )

            def find_free_adjacent_position(
                target_x,
                target_y,
                target_w,
                target_h,
                space_w,
                space_h,
                space_name=None,
                target_name=None
            ):

                # ======================================
                # EDGE-SLIDING ADJACENCY CANDIDATES v1.0
                #
                # A space may slide along the shared edge
                # of its graph neighbour while preserving
                # true geometric adjacency.
                #
                # This avoids false fallback when the
                # corner-aligned position is blocked.
                # ======================================

                candidates = []

                EDGE_STEP = 0.5


                def append_candidate(
                    direction,
                    x,
                    y
                ):

                    candidate_key = (
                        round(
                            float(x),
                            6
                        ),
                        round(
                            float(y),
                            6
                        ),
                        direction
                    )


                    existing_keys = {
                        (
                            round(
                                float(candidate["x"]),
                                6
                            ),
                            round(
                                float(candidate["y"]),
                                6
                            ),
                            candidate["direction"]
                        )
                        for candidate in candidates
                    }


                    if candidate_key in existing_keys:

                        return


                    candidates.append(
                        {
                            "direction":
                                direction,

                            "x":
                                x,

                            "y":
                                y
                        }
                    )


                # --------------------------------------
                # RIGHT EDGE
                #
                # Candidate must remain vertically
                # overlapping the target edge.
                # --------------------------------------

                right_x = (
                    target_x
                    +
                    target_w
                )

                right_min_y = (
                    target_y
                    -
                    space_h
                    +
                    EDGE_STEP
                )

                right_max_y = (
                    target_y
                    +
                    target_h
                    -
                    EDGE_STEP
                )


                right_y = right_min_y

                while (
                    right_y
                    <=
                    right_max_y
                    +
                    1e-9
                ):

                    append_candidate(
                        "right",
                        right_x,
                        right_y
                    )

                    right_y += EDGE_STEP


                # --------------------------------------
                # BELOW EDGE
                #
                # Candidate must remain horizontally
                # overlapping the target edge.
                # --------------------------------------

                below_y = (
                    target_y
                    +
                    target_h
                )

                below_min_x = (
                    target_x
                    -
                    space_w
                    +
                    EDGE_STEP
                )

                below_max_x = (
                    target_x
                    +
                    target_w
                    -
                    EDGE_STEP
                )


                below_x = below_min_x

                while (
                    below_x
                    <=
                    below_max_x
                    +
                    1e-9
                ):

                    append_candidate(
                        "below",
                        below_x,
                        below_y
                    )

                    below_x += EDGE_STEP


                # --------------------------------------
                # LEFT EDGE
                # --------------------------------------

                left_x = (
                    target_x
                    -
                    space_w
                )

                left_min_y = (
                    target_y
                    -
                    space_h
                    +
                    EDGE_STEP
                )

                left_max_y = (
                    target_y
                    +
                    target_h
                    -
                    EDGE_STEP
                )


                left_y = left_min_y

                while (
                    left_y
                    <=
                    left_max_y
                    +
                    1e-9
                ):

                    append_candidate(
                        "left",
                        left_x,
                        left_y
                    )

                    left_y += EDGE_STEP


                # --------------------------------------
                # ABOVE EDGE
                #
                # Candidate must remain horizontally
                # overlapping the target edge.
                # --------------------------------------

                above_y = (
                    target_y
                    -
                    space_h
                )

                above_min_x = (
                    target_x
                    -
                    space_w
                    +
                    EDGE_STEP
                )

                above_max_x = (
                    target_x
                    +
                    target_w
                    -
                    EDGE_STEP
                )


                above_x = above_min_x

                while (
                    above_x
                    <=
                    above_max_x
                    +
                    1e-9
                ):

                    append_candidate(
                        "above",
                        above_x,
                        above_y
                    )

                    above_x += EDGE_STEP


               


                valid_candidates = []

                def collision_names_for_candidate(
                    candidate_x,
                    candidate_y
                ):

                    collision_names = []


                    for rectangle in occupied_rectangles:

                        if rectangles_overlap(
                            candidate_x,
                            candidate_y,
                            space_w,
                            space_h,
                            rectangle
                        ):

                            collision_names.append(
                                rectangle.get(
                                    "name"
                                )
                            )


                    return collision_names


                # ======================================
                # HYPOTHETICAL COLLISION CHECK
                #
                # Used only while scoring a candidate.
                # It does not modify occupied_rectangles.
                # ======================================

                def overlaps_hypothetical(
                    x,
                    y,
                    w,
                    h,
                    hypothetical
                ):

                    return not (

                        x + w <= hypothetical["x"]

                        or

                        hypothetical["x"] + hypothetical["w"] <= x

                        or

                        y + h <= hypothetical["y"]

                        or

                        hypothetical["y"] + hypothetical["h"] <= y

                    )


                # ======================================
                # TARGET-SIDE CAPACITY
                #
                # Estimate how many still-unresolved
                # graph neighbours of target_name can
                # retain at least one valid adjacency
                # position after placing space_name at
                # the candidate being tested.
                # ======================================

                def remaining_graph_capacity(
                    candidate_x,
                    candidate_y
                ):

                    # ======================================
                    # PLACED-SPACE FUTURE CAPACITY v1.2
                    #
                    # Look-ahead must preserve adjacency
                    # capacity for the space currently being
                    # positioned, not only for the already
                    # resolved graph target.
                    #
                    # Example:
                    #
                    # landing -> corridor -> bedrooms
                    #
                    # When corridor is being placed beside
                    # landing, future capacity belongs to
                    # corridor because bedrooms are still
                    # unresolved.
                    # ======================================

                    if not space_name:

                        return {
                            "independent":
                                0,

                            "joint":
                                0,

                            "future_count":
                                0,

                            "joint_assignment":
                                []
                        }


                    hypothetical = {

                        "x":
                            candidate_x,

                        "y":
                            candidate_y,

                        "w":
                            space_w,

                        "h":
                            space_h

                    }


                    capacity = 0

                    future_feasible_rectangles = {}

                    future_neighbour_count = 0


                    capacity_anchor_name = space_name

                    capacity_anchor_x = candidate_x
                    capacity_anchor_y = candidate_y
                    capacity_anchor_w = space_w
                    capacity_anchor_h = space_h


                    target_relations = connection_map.get(
                        capacity_anchor_name,
                        []
                    )

                    for relation in target_relations:

                        neighbour_name = relation.get(
                            "target"
                        )

                        relation_type = relation.get(
                            "type",
                            "adjacent"
                        )

                        constraint_strength = str(
                            relation.get(
                                "constraint_strength",
                                ""
                            )
                        ).lower()


                        # ==================================
                        # HARD VS SOFT FUTURE RELATION v1.1
                        #
                        # Explicit program relationships are
                        # structurally hard by definition.
                        #
                        # Semantic adjacency remains soft unless
                        # Architectural Knowledge explicitly
                        # promotes it to a required constraint.
                        # ==================================

                        hard_future_relation = (
                            relation_type
                            in {
                                "direct_connection",
                                "adjacent",
                                "private_connection"
                            }
                            or
                            (
                                relation_type == "semantic_adjacent"
                                and
                                constraint_strength == "required"
                            )
                        )


                        if not neighbour_name:

                            continue


                        if neighbour_name == space_name:

                            continue


                        # Already placed neighbours no
                        # longer need target-side capacity.
                        if neighbour_name in resolved_positions:

                            continue

                        if hard_future_relation:

                            future_neighbour_count += 1


                        neighbour_item = normalized_nodes.get(
                            neighbour_name
                        )


                        if not isinstance(
                            neighbour_item,
                            dict
                        ):

                            continue


                        neighbour_space = neighbour_item.get(
                            "space",
                            {}
                        )


                        neighbour_w = neighbour_space.get(
                            "w",
                            FALLBACK_UNIT
                        )


                        neighbour_h = neighbour_space.get(
                            "h",
                            FALLBACK_UNIT
                        )


                        # ==================================
                        # FUTURE NEIGHBOUR EDGE SWEEP v1.0
                        #
                        # Future-capacity reasoning must use
                        # the same edge-placement model as
                        # actual graph placement.
                        #
                        # A future neighbour may occupy any
                        # collision-free segment along a
                        # shared target edge; it is not
                        # restricted to four corner-aligned
                        # positions.
                        # ==================================

                        neighbour_candidates = []


                        def append_future_candidate(
                            x,
                            y
                        ):

                            candidate = (
                                round(
                                    float(x),
                                    12
                                ),
                                round(
                                    float(y),
                                    12
                                )
                            )


                            if candidate not in neighbour_candidates:

                                neighbour_candidates.append(
                                    candidate
                                )


                        # ------------------------------
                        # RIGHT EDGE
                        # ------------------------------
                        neighbour_x = (
                            capacity_anchor_x
                            +
                            capacity_anchor_w
                        )

                        neighbour_min_y = (
                            capacity_anchor_y
                            -
                            neighbour_h
                            +
                            EDGE_STEP
                        )

                        neighbour_max_y = (
                            capacity_anchor_y
                            +
                            capacity_anchor_h
                            -
                            EDGE_STEP
                        )


                        sweep_y = neighbour_min_y

                        while (
                            sweep_y
                            <=
                            neighbour_max_y
                            +
                            1e-9
                        ):

                            append_future_candidate(
                                neighbour_x,
                                sweep_y
                            )

                            sweep_y += EDGE_STEP


                        # ------------------------------
                        # BELOW EDGE
                        # ------------------------------

                        neighbour_y = (
                            capacity_anchor_y
                            +
                            capacity_anchor_h
                        )

                        neighbour_min_x = (
                            capacity_anchor_x
                            -
                            neighbour_w
                            +
                            EDGE_STEP
                        )

                        neighbour_max_x = (
                            capacity_anchor_x
                            +
                            capacity_anchor_w
                            -
                            EDGE_STEP
                        )


                        sweep_x = neighbour_min_x

                        while (
                            sweep_x
                            <=
                            neighbour_max_x
                            +
                            1e-9
                        ):

                            append_future_candidate(
                                sweep_x,
                                neighbour_y
                            )

                            sweep_x += EDGE_STEP


                        # ------------------------------
                        # LEFT EDGE
                        # ------------------------------

                        neighbour_x = (
                            capacity_anchor_x
                            -
                            neighbour_w
                        )

                        neighbour_min_y = (
                            capacity_anchor_y
                            -
                            neighbour_h
                            +
                            EDGE_STEP
                        )

                        neighbour_max_y = (
                            capacity_anchor_y
                            +
                            capacity_anchor_h
                            -
                            EDGE_STEP
                        )


                        sweep_y = neighbour_min_y

                        while (
                            sweep_y
                            <=
                            neighbour_max_y
                            +
                            1e-9
                        ):

                            append_future_candidate(
                                neighbour_x,
                                sweep_y
                            )

                            sweep_y += EDGE_STEP


                        # ------------------------------
                        # ABOVE EDGE
                        # ------------------------------

                        neighbour_y = (
                            capacity_anchor_y
                            -
                            neighbour_h
                        )

                        neighbour_min_x = (
                            capacity_anchor_x
                            -
                            neighbour_w
                            +
                            EDGE_STEP
                        )

                        neighbour_max_x = (
                            capacity_anchor_x
                            +
                            capacity_anchor_w
                            -
                            EDGE_STEP
                        )


                        sweep_x = neighbour_min_x

                        while (
                            sweep_x
                            <=
                            neighbour_max_x
                            +
                            1e-9
                        ):

                            append_future_candidate(
                                sweep_x,
                                neighbour_y
                            )

                            sweep_x += EDGE_STEP


                        neighbour_has_position = False

                        neighbour_valid_positions = []


                        for (
                            neighbour_x,
                            neighbour_y
                        ) in neighbour_candidates:

                            if (
                                neighbour_x < 0
                                or
                                neighbour_y < 0
                            ):

                                continue


                            if not position_is_free(

                                neighbour_x,
                                neighbour_y,

                                neighbour_w,
                                neighbour_h,

                                space_name=neighbour_name

                            ):

                                continue


                            if overlaps_hypothetical(

                                neighbour_x,
                                neighbour_y,

                                neighbour_w,
                                neighbour_h,

                                hypothetical

                            ):

                                continue


                            neighbour_has_position = True

                            neighbour_valid_positions.append(
                                {
                                    "x":
                                        neighbour_x,

                                    "y":
                                        neighbour_y,

                                    "w":
                                        neighbour_w,

                                    "h":
                                        neighbour_h
                                }
                            )

                            
                        # ==================================
                        # HARD FUTURE RESERVATION ONLY
                        #
                        # Soft semantic adjacency may guide
                        # placement when its turn arrives,
                        # but it must not reserve target-edge
                        # capacity during strict look-ahead.
                        # ==================================

                        if (
                            hard_future_relation
                            and
                            neighbour_valid_positions
                        ):

                            future_feasible_rectangles[
                                neighbour_name
                            ] = (
                                neighbour_valid_positions
                            )

                        if (
                            hard_future_relation
                            and
                            neighbour_has_position
                        ):

                            capacity += 1


                    # ==================================
                    # JOINT FUTURE CAPACITY v1.0
                    #
                    # Independent availability is not
                    # sufficient. Future neighbours must
                    # also possess a mutually compatible
                    # set of placements.
                    # ==================================

                    future_names = sorted(
                        future_feasible_rectangles.keys()
                    )


                    joint_assignment = []


                    def future_positions_overlap(
                        first,
                        second
                    ):

                        return not (

                            first["x"] + first["w"]
                            <=
                            second["x"]

                            or

                            second["x"] + second["w"]
                            <=
                            first["x"]

                            or

                            first["y"] + first["h"]
                            <=
                            second["y"]

                            or

                            second["y"] + second["h"]
                            <=
                            first["y"]

                        )

                    def future_downstream_capacity(
                        future_name,
                        future_position
                    ):

                        downstream_relations = (
                            connection_map.get(
                                future_name,
                                []
                            )
                        )

                        downstream_capacity = 0

                        future_x = future_position["x"]
                        future_y = future_position["y"]
                        future_w = future_position["w"]
                        future_h = future_position["h"]

                        for downstream_relation in downstream_relations:

                            downstream_name = (
                                downstream_relation.get(
                                    "target"
                                )
                            )

                            downstream_type = (
                                downstream_relation.get(
                                    "type",
                                    "adjacent"
                                )
                            )

                            if not downstream_name:
                                continue

                            # Do not reason backwards toward
                            # the node currently creating this
                            # future reservation.
                            if downstream_name in {
                                space_name,
                                target_name
                            }:
                                continue

                            if downstream_name == future_name:
                                continue

                            # Already resolved nodes do not need
                            # future reservation capacity.
                            if downstream_name in resolved_positions:
                                continue

                            if downstream_type not in {
                                "direct_connection",
                                "adjacent",
                                "private_connection"
                            }:
                                continue

                            downstream_item = (
                                normalized_nodes.get(
                                    downstream_name
                                )
                            )

                            if not isinstance(
                                downstream_item,
                                dict
                            ):
                                continue

                            downstream_space = (
                                downstream_item.get(
                                    "space",
                                    {}
                                )
                            )

                            downstream_w = downstream_space.get(
                                "w",
                                FALLBACK_UNIT
                            )

                            downstream_h = downstream_space.get(
                                "h",
                                FALLBACK_UNIT
                            )

                            downstream_candidates = []

                            # RIGHT
                            candidate_x = (
                                future_x
                                +
                                future_w
                            )

                            candidate_y = (
                                future_y
                                -
                                downstream_h
                                +
                                EDGE_STEP
                            )

                            max_y = (
                                future_y
                                +
                                future_h
                                -
                                EDGE_STEP
                            )

                            while candidate_y <= max_y + 1e-9:

                                downstream_candidates.append(
                                    (
                                        candidate_x,
                                        candidate_y
                                    )
                                )

                                candidate_y += EDGE_STEP

                            # BELOW
                            candidate_y = (
                                future_y
                                +
                                future_h
                            )

                            candidate_x = (
                                future_x
                                -
                                downstream_w
                                +
                                EDGE_STEP
                            )

                            max_x = (
                                future_x
                                +
                                future_w
                                -
                                EDGE_STEP
                            )

                            while candidate_x <= max_x + 1e-9:

                                downstream_candidates.append(
                                    (
                                        candidate_x,
                                        candidate_y
                                    )
                                )

                                candidate_x += EDGE_STEP

                            # LEFT
                            candidate_x = (
                                future_x
                                -
                                downstream_w
                            )

                            candidate_y = (
                                future_y
                                -
                                downstream_h
                                +
                                EDGE_STEP
                            )

                            max_y = (
                                future_y
                                +
                                future_h
                                -
                                EDGE_STEP
                            )

                            while candidate_y <= max_y + 1e-9:

                                downstream_candidates.append(
                                    (
                                        candidate_x,
                                        candidate_y
                                    )
                                )

                                candidate_y += EDGE_STEP

                            # ABOVE
                            candidate_y = (
                                future_y
                                -
                                downstream_h
                            )

                            candidate_x = (
                                future_x
                                -
                                downstream_w
                                +
                                EDGE_STEP
                            )

                            max_x = (
                                future_x
                                +
                                future_w
                                -
                                EDGE_STEP
                            )

                            while candidate_x <= max_x + 1e-9:

                                downstream_candidates.append(
                                    (
                                        candidate_x,
                                        candidate_y
                                    )
                                )

                                candidate_x += EDGE_STEP

                            downstream_has_position = False

                            for (
                                downstream_x,
                                downstream_y
                            ) in downstream_candidates:

                                if (
                                    downstream_x < 0
                                    or
                                    downstream_y < 0
                                ):
                                    continue

                                if not position_is_free(
                                    downstream_x,
                                    downstream_y,
                                    downstream_w,
                                    downstream_h,
                                    space_name=downstream_name
                                ):
                                    continue

                                if overlaps_hypothetical(
                                    downstream_x,
                                    downstream_y,
                                    downstream_w,
                                    downstream_h,
                                    hypothetical
                                ):
                                    continue

                                if future_positions_overlap(
                                    {
                                        "x":
                                            downstream_x,
                                        "y":
                                            downstream_y,
                                        "w":
                                            downstream_w,
                                        "h":
                                            downstream_h
                                    },
                                    future_position
                                ):
                                    continue

                                collision_with_assignment = any(

                                    future_positions_overlap(
                                        {
                                            "x":
                                                downstream_x,
                                            "y":
                                                downstream_y,
                                            "w":
                                                downstream_w,
                                            "h":
                                                downstream_h
                                        },
                                        assigned_position
                                    )

                                    for assigned_position
                                    in joint_assignment
                                )

                                if collision_with_assignment:
                                    continue

                                downstream_has_position = True
                                break

                            if downstream_has_position:

                                downstream_capacity += 1

                        return downstream_capacity

                    def build_downstream_reservations(
                        future_name,
                        future_position
                    ):

                        downstream_assignments = []

                        downstream_relations = (
                            connection_map.get(
                                future_name,
                                []
                            )
                        )

                
                        future_x = future_position["x"]
                        future_y = future_position["y"]
                        future_w = future_position["w"]
                        future_h = future_position["h"]

                        for downstream_relation in downstream_relations:

                            downstream_name = (
                                downstream_relation.get(
                                    "target"
                                )
                            )

                            downstream_type = (
                                downstream_relation.get(
                                    "type",
                                    "adjacent"
                                )
                            )

                            
                            if not downstream_name:
                                continue

                            if downstream_name in {
                                space_name,
                                target_name,
                                future_name
                            }:
                                continue

                            if downstream_name in resolved_positions:
                                continue

                            if downstream_type not in {
                                "direct_connection",
                                "adjacent",
                                "private_connection"
                            }:
                                continue

                            # Already part of the parent's
                            # joint future problem.
                            #
                            # Do not create a second independent
                            # reservation for the same node.
                            if downstream_name in (
                                future_feasible_rectangles
                            ):
                                continue

                            downstream_item = (
                                normalized_nodes.get(
                                    downstream_name
                                )
                            )

                            if not isinstance(
                                downstream_item,
                                dict
                            ):
                                continue

                            downstream_space = (
                                downstream_item.get(
                                    "space",
                                    {}
                                )
                            )

                            downstream_w = downstream_space.get(
                                "w",
                                FALLBACK_UNIT
                            )

                            downstream_h = downstream_space.get(
                                "h",
                                FALLBACK_UNIT
                            )

                            downstream_candidates = []

                            def append_downstream_candidate(
                                x,
                                y
                            ):

                                candidate = (
                                    round(
                                        float(x),
                                        12
                                    ),
                                    round(
                                        float(y),
                                        12
                                    )
                                )

                                if candidate not in downstream_candidates:

                                    downstream_candidates.append(
                                        candidate
                                    )

                            # ==================================
                            # RIGHT EDGE
                            # ==================================

                            candidate_x = (
                                future_x
                                +
                                future_w
                            )

                            candidate_y = (
                                future_y
                                -
                                downstream_h
                                +
                                EDGE_STEP
                            )

                            max_y = (
                                future_y
                                +
                                future_h
                                -
                                EDGE_STEP
                            )

                            while (
                                candidate_y
                                <=
                                max_y
                                +
                                1e-9
                            ):

                                append_downstream_candidate(
                                    candidate_x,
                                    candidate_y
                                )

                                candidate_y += EDGE_STEP

                            # ==================================
                            # BELOW EDGE
                            # ==================================

                            candidate_y = (
                                future_y
                                +
                                future_h
                            )

                            candidate_x = (
                                future_x
                                -
                                downstream_w
                                +
                                EDGE_STEP
                            )

                            max_x = (
                                future_x
                                +
                                future_w
                                -
                                EDGE_STEP
                            )

                            while (
                                candidate_x
                                <=
                                max_x
                                +
                                1e-9
                            ):

                                append_downstream_candidate(
                                    candidate_x,
                                    candidate_y
                                )

                                candidate_x += EDGE_STEP

                            # ==================================
                            # LEFT EDGE
                            # ==================================

                            candidate_x = (
                                future_x
                                -
                                downstream_w
                            )

                            candidate_y = (
                                future_y
                                -
                                downstream_h
                                +
                                EDGE_STEP
                            )

                            max_y = (
                                future_y
                                +
                                future_h
                                -
                                EDGE_STEP
                            )

                            while (
                                candidate_y
                                <=
                                max_y
                                +
                                1e-9
                            ):

                                append_downstream_candidate(
                                    candidate_x,
                                    candidate_y
                                )

                                candidate_y += EDGE_STEP

                            # ==================================
                            # ABOVE EDGE
                            # ==================================

                            candidate_y = (
                                future_y
                                -
                                downstream_h
                            )

                            candidate_x = (
                                future_x
                                -
                                downstream_w
                                +
                                EDGE_STEP
                            )

                            max_x = (
                                future_x
                                +
                                future_w
                                -
                                EDGE_STEP
                            )

                            while (
                                candidate_x
                                <=
                                max_x
                                +
                                1e-9
                            ):

                                append_downstream_candidate(
                                    candidate_x,
                                    candidate_y
                                )

                                candidate_x += EDGE_STEP

                            selected_position = None

                           

                            for (
                                downstream_x,
                                downstream_y
                            ) in downstream_candidates:

                                if (
                                    downstream_x < 0
                                    or
                                    downstream_y < 0
                                ):
                                    continue

                                if not position_is_free(
                                    downstream_x,
                                    downstream_y,
                                    downstream_w,
                                    downstream_h,
                                    space_name=downstream_name
                                ):
                                    continue

                                downstream_rectangle = {
                                    "name":
                                        downstream_name,

                                    "x":
                                        downstream_x,

                                    "y":
                                        downstream_y,

                                    "w":
                                        downstream_w,

                                    "h":
                                        downstream_h
                                }

                                if future_positions_overlap(
                                    downstream_rectangle,
                                    future_position
                                ):
                                    continue

                                if overlaps_hypothetical(
                                    downstream_x,
                                    downstream_y,
                                    downstream_w,
                                    downstream_h,
                                    hypothetical
                                ):
                                    continue

                                collision = any(

                                    future_positions_overlap(
                                        downstream_rectangle,
                                        assigned_position
                                    )

                                    for assigned_position
                                    in (
                                        joint_assignment
                                        +
                                        downstream_assignments
                                    )
                                )

                                if collision:
                                    continue

                                selected_position = (
                                    downstream_rectangle
                                )

                                break

                            # ==================================
                            # STRICT DOWNSTREAM CONTRACT v1.0
                            #
                            # Reaching this point means the
                            # downstream relation is one of the
                            # hard geometric relationships:
                            #
                            # - direct_connection
                            # - adjacent
                            # - private_connection
                            #
                            # If no collision-free adjacent
                            # position exists, the parent future
                            # assignment is not geometrically
                            # feasible and must be rejected by
                            # the joint-assignment backtracker.
                            #
                            # None is intentionally different
                            # from []:
                            #
                            # []   -> no downstream reservation
                            # None -> hard downstream failure
                            # ==================================

                            if selected_position is None:

                                return None


                            downstream_assignments.append(
                                selected_position
                            )

                        
                        return downstream_assignments


                    def assign_future_neighbour(
                        index
                    ):

                        if index >= len(
                            future_names
                        ):


                            return True


                        neighbour_name = (
                            future_names[index]
                        )


                        ranked_future_positions = sorted(
                            future_feasible_rectangles[
                                neighbour_name
                            ],
                            key=lambda future_position: (
                                -future_downstream_capacity(
                                    neighbour_name,
                                    future_position
                                ),
                                future_position["y"],
                                future_position["x"]
                            )
                        )


                        for future_position in ranked_future_positions:

                            collision = any(

                                future_positions_overlap(
                                    future_position,
                                    assigned_position
                                )

                                for assigned_position
                                in joint_assignment

                            )


                            if collision:

                                continue


                            primary_assignment = {
                                "name":
                                    neighbour_name,

                                "x":
                                    future_position[
                                        "x"
                                    ],

                                "y":
                                    future_position[
                                        "y"
                                    ],

                                "w":
                                    future_position[
                                        "w"
                                    ],

                                "h":
                                    future_position[
                                        "h"
                                    ]
                            }


                            joint_assignment.append(
                                primary_assignment
                            )


                            downstream_assignments = (
                                build_downstream_reservations(
                                    neighbour_name,
                                    primary_assignment
                                )
                            )

                            # ==================================
                            # REJECT INVALID FUTURE BRANCH v1.0
                            #
                            # The primary future assignment was
                            # already pushed into
                            # joint_assignment.
                            #
                            # A None downstream result means one
                            # of its hard downstream graph
                            # contracts could not be satisfied.
                            #
                            # Undo the primary assignment and
                            # try the next geometric candidate.
                            # ==================================

                            if downstream_assignments is None:

                                joint_assignment.pop()

                                continue


                            downstream_start_index = len(
                                joint_assignment
                            )


                            for downstream_assignment in (
                                downstream_assignments
                            ):

                                downstream_name = (
                                    downstream_assignment.get(
                                        "name"
                                    )
                                )

                                if not downstream_name:
                                    continue

                                if any(
                                    assignment.get(
                                        "name"
                                    )
                                    ==
                                    downstream_name

                                    for assignment
                                    in joint_assignment
                                ):
                                    continue

                                joint_assignment.append(
                                    downstream_assignment
                                )


                            if assign_future_neighbour(
                                index + 1
                            ):

                                return True


                            del joint_assignment[
                                downstream_start_index:
                            ]


                            joint_assignment.pop()


                        return False


                    # ==================================
                    # STRICT JOINT FUTURE CAPACITY v1.1
                    #
                    # Joint feasibility is valid only if
                    # every unresolved future neighbour
                    # first possesses at least one
                    # individually feasible rectangle.
                    #
                    # A neighbour missing from
                    # future_feasible_rectangles must not
                    # silently disappear from the joint
                    # assignment problem.
                    # ==================================

                    if (
                        future_neighbour_count == 0
                    ):

                        joint_capacity = 0

                    elif (
                        len(future_names)
                        !=
                        future_neighbour_count
                    ):

                        joint_capacity = 0

                    else:

                        joint_capacity = (
                            future_neighbour_count
                            if assign_future_neighbour(0)
                            else 0
                        )


                    return {
                        "independent":
                            capacity,

                        "joint":
                            joint_capacity,

                        "future_count":
                            future_neighbour_count,

                        "joint_assignment":
                            [
                                dict(
                                    assignment
                                )
                                for assignment
                                in joint_assignment
                            ]
                            if joint_capacity > 0
                            else []
                    }


                    return capacity


                # ======================================
                # BUILD VALID CANDIDATE SET
                # ======================================

                for order, candidate in enumerate(
                    candidates
                ):

                    candidate_x = candidate[
                        "x"
                    ]

                    candidate_y = candidate[
                        "y"
                    ]

                    debug_adjacency = (
                        DEBUG_SPATIAL_GRAPH
                        and
                        space_name in {
                            "guest_wc",
                            "terrace"
                        }
                    )


                    if (
                        candidate_x < 0
                        or
                        candidate_y < 0
                    ):

                        if debug_adjacency:

                            print(
                                "   ❌ REJECT:",
                                "negative_coordinate"
                            )

                        continue


                    if not position_is_free(

                        candidate_x,
                        candidate_y,

                        space_w,
                        space_h,

                        space_name=space_name

                    ):

                        if debug_adjacency:

                            print(
                                "   ❌ REJECT:",
                                "collision",
                                "WITH=",
                                collision_names_for_candidate(
                                    candidate_x,
                                    candidate_y
                                )
                            )

                        continue


                    graph_capacity_result = (
                        remaining_graph_capacity(
                            candidate_x,
                            candidate_y
                        )
                    )


                    graph_capacity = (
                        graph_capacity_result.get(
                            "independent",
                            0
                        )
                    )


                    joint_graph_capacity = (
                        graph_capacity_result.get(
                            "joint",
                            0
                        )
                    )

                    joint_assignment = list(
                        graph_capacity_result.get(
                            "joint_assignment",
                            []
                        )
                    )

                    if debug_adjacency:

                        print(
                            "   ✅ VALID:",
                            "DIRECTION=",
                            candidate.get(
                                "direction"
                            ),
                            "GRAPH_CAPACITY=",
                            graph_capacity
                        )


                    valid_candidates.append(
                        {
                            "x":
                                candidate_x,

                            "y":
                                candidate_y,

                            "direction":
                                candidate[
                                    "direction"
                                ],

                            "graph_capacity":
                                graph_capacity,

                            "joint_graph_capacity":
                                joint_graph_capacity,

                            "joint_assignment":
                                joint_assignment,

                            "order":
                                order
                        }
                    )


                if not valid_candidates:

                    return None


                # ======================================
                # GRAPH-CAPACITY-AWARE SELECTION
                #
                # Primary:
                #   preserve maximum remaining graph
                #   adjacency capacity.
                #
                # Tie-break:
                #   preserve historical deterministic
                #   right/below/left/above preference.
                # ======================================

                best_candidate = max(

                    valid_candidates,

                    key=lambda candidate: (

                        candidate[
                            "joint_graph_capacity"
                        ],

                        candidate[
                            "graph_capacity"
                        ],

                        -candidate[
                            "order"
                        ]

                    )

                )


                return {

                    "x":
                        best_candidate[
                            "x"
                        ],

                    "y":
                        best_candidate[
                            "y"
                        ],

                    "direction":
                        best_candidate[
                            "direction"
                        ],

                    "graph_capacity":
                        best_candidate[
                            "graph_capacity"
                        ],

                    "joint_graph_capacity":
                        best_candidate[
                            "joint_graph_capacity"
                        ],

                    "joint_assignment":
                        [
                            dict(
                                assignment
                            )
                            for assignment
                            in best_candidate.get(
                                "joint_assignment",
                                []
                            )
                        ]

                }

            # ==========================================
            # MULTI-PASS GRAPH POSITION RESOLVER v1.2
            #
            # Pass 1:
            #   Preserve all upstream-resolved anchors.
            #
            # Pass 2+:
            #   Resolve connected unresolved nodes from
            #   already-resolved graph neighbours.
            #
            # Final pass:
            #   Collision-safe fallback for nodes that
            #   still have no placement evidence.
            # ==========================================
            normalized_nodes = {}


            for index, (name, node) in enumerate(
                nodes.items()
            ):

                if not isinstance(
                    node,
                    dict
                ):

                    continue


                space = dict(
                    node
                )

            
                # --------------------------------------
                # NORMALIZE DIMENSIONS
                # --------------------------------------

                width = space.get(
                    "w",
                    space.get(
                        "width"
                    )
                )


                height = space.get(
                    "h",
                    space.get(
                        "height"
                    )
                )

                # --------------------------------------
                # KNOWLEDGE-DRIVEN DIMENSION RESOLUTION
                # --------------------------------------
                #
                # Explicit upstream geometry always wins.
                #
                # When geometry is not explicit, resolve
                # dimensions from architectural program
                # requirements carried by DesignAgent.
                #
                # Priority:
                # 1. explicit w / width + h / height
                # 2. dimensional_requirements
                # 3. FALLBACK_UNIT
                # --------------------------------------

                dimensional_requirements = (
                    space.get(
                        "dimensional_requirements"
                    )
                )

                if not isinstance(
                    dimensional_requirements,
                    dict
                ):

                    dimensional_requirements = {}


                minimum_area = (
                    dimensional_requirements.get(
                        "minimum_area"
                    )
                )

                preferred_area = (
                    dimensional_requirements.get(
                        "preferred_area"
                    )
                )

                minimum_width = (
                    dimensional_requirements.get(
                        "minimum_width"
                    )
                )

                minimum_depth = (
                    dimensional_requirements.get(
                        "minimum_depth"
                    )
                )

                preferred_width = (
                    dimensional_requirements.get(
                        "preferred_width"
                    )
                )


                if (
                    width is None
                    and
                    height is None
                    and
                    dimensional_requirements
                ):

                    space_type = str(
                        space.get(
                            "space_type",
                            ""
                        )
                    ).lower()

                    canonical_name = str(
                        space.get(
                            "canonical_name",
                            ""
                        )
                    ).lower()


                    # ----------------------------------
                    # CORRIDOR / LINEAR CIRCULATION
                    # ----------------------------------

                    if (
                        space_type == "corridor"
                        or
                        canonical_name == "corridor"
                    ):

                        resolved_width = (
                            preferred_width
                            if preferred_width is not None
                            else minimum_width
                        )


                        if resolved_width is not None:

                            width = float(
                                resolved_width
                            )


                            target_area = (
                                preferred_area
                                if preferred_area is not None
                                else minimum_area
                            )


                            if target_area is not None:

                                height = (
                                    float(target_area)
                                    /
                                    width
                                )


                            elif minimum_depth is not None:

                                height = float(
                                    minimum_depth
                                )


                            space[
                                "resolved_width"
                            ] = width


                    # ----------------------------------
                    # GENERAL ARCHITECTURAL SPACE
                    # ----------------------------------

                    else:

                        if minimum_width is not None:

                            width = float(
                                minimum_width
                            )


                        if minimum_depth is not None:

                            height = float(
                                minimum_depth
                            )


                        target_area = (
                            preferred_area
                            if preferred_area is not None
                            else minimum_area
                        )


                        if target_area is not None:

                            target_area = float(
                                target_area
                            )


                            if (
                                width is not None
                                and
                                height is not None
                            ):

                                current_area = (
                                    width
                                    *
                                    height
                                )


                                if current_area < target_area:

                                    height = (
                                        target_area
                                        /
                                        width
                                    )


                            elif width is not None:

                                height = (
                                    target_area
                                    /
                                    width
                                )


                            elif height is not None:

                                width = (
                                    target_area
                                    /
                                    height
                                )


                if width is None:

                    width = FALLBACK_UNIT


                if height is None:

                    height = FALLBACK_UNIT


                space["w"] = width
                space["h"] = height

                space["width"] = width
                space["height"] = height

                space["name"] = name


                normalized_nodes[name] = {

                    "space":
                        space,

                    "index":
                        index

                }


            # ==========================================
            # SEMANTIC GRAPH PRIORITY v1.0
            #
            # Higher score means the space should act
            # earlier as a graph propagation anchor.
            #
            # Priority is derived from architectural
            # semantics, not from dictionary order.
            # ==========================================

            def semantic_graph_priority(
                name
            ):

                item = normalized_nodes.get(
                    name,
                    {}
                )


                space = item.get(
                    "space",
                    {}
                )


                score = 0


                zone = str(
                    space.get(
                        "zone",
                        ""
                    )
                ).lower()


                planning_zone = str(
                    space.get(
                        "planning_zone",
                        ""
                    )
                ).lower()


                space_type = str(
                    space.get(
                        "space_type",
                        ""
                    )
                ).lower()


                canonical_name = str(
                    space.get(
                        "canonical_name",
                        ""
                    )
                ).lower()


                protected_zone = (
                    space.get(
                        "protected_zone"
                    )
                    is True
                )


                circulation_profile = (
                    space.get(
                        "circulation_profile"
                    )
                    or
                    {}
                )


                graph_degree = len(
                    connection_map.get(
                        name,
                        []
                    )
                )


                # --------------------------------------
                # GRAPH HUB IMPORTANCE
                # --------------------------------------

                score += (
                    graph_degree
                    *
                    10
                )


                # --------------------------------------
                # PROTECTED ARCHITECTURAL ROUTES
                # --------------------------------------

                if protected_zone:

                    score += 100


                # --------------------------------------
                # EGRESS / LIFE-SAFETY CIRCULATION
                # --------------------------------------

                if space_type in {
                    "egress",
                    "escape_route"
                }:

                    score += 90


                # --------------------------------------
                # VERTICAL TRANSPORT / CORE
                # --------------------------------------

                if space_type in {
                    "vertical_transport",
                    "vertical_core"
                }:

                    score += 80


                if canonical_name in {
                    "vertical_core",
                    "elevator"
                }:

                    score += 80


                # --------------------------------------
                # GENERAL CIRCULATION
                # --------------------------------------

                if (
                    zone == "circulation"
                    or
                    planning_zone == "circulation"
                ):

                    score += 70


                if space_type in {
                    "circulation",
                    "assembly_circulation",
                    "service_circulation"
                }:

                    score += 70


                # --------------------------------------
                # EXPLICIT CIRCULATION PROFILE
                # --------------------------------------

                if isinstance(
                    circulation_profile,
                    dict
                ) and circulation_profile:

                    score += 60


                # --------------------------------------
                # PUBLIC ACCESS / ENTRANCE
                # --------------------------------------

                if space_type in {
                    "entrance",
                    "public_access"
                }:

                    score += 50


                # --------------------------------------
                # SERVICE ACCESS
                # --------------------------------------

                if space_type in {
                    "service_access",
                    "staff_access"
                }:

                    score += 40


                return score


            def graph_resolution_sort_key(
                name
            ):

                item = normalized_nodes.get(
                    name,
                    {}
                )


                return (
                    -semantic_graph_priority(
                        name
                    ),
                    str(
                        name
                    )
                )


            unresolved_names = set(
                normalized_nodes.keys()
            )


            # ==========================================
            # PASS 1 — UPSTREAM RESOLVED ANCHORS
            # ==========================================

            for name in list(
                unresolved_names
            ):

                item = normalized_nodes[
                    name
                ]

                space = item[
                    "space"
                ]


                x = space.get(
                    "x"
                )

                y = space.get(
                    "y"
                )


                has_resolved_position = (
                    x is not None
                    and
                    y is not None
                )


                if not has_resolved_position:

                    continue


                space[
                    "placement_source"
                ] = (
                    "upstream_resolved"
                )


                resolved_positions[name] = {

                    "x":
                        x,

                    "y":
                        y,

                    "w":
                        space.get(
                            "w",
                            FALLBACK_UNIT
                        ),

                    "h":
                        space.get(
                            "h",
                            FALLBACK_UNIT
                        )

                }


                occupied_rectangles.append(
                    {
                        "name":
                            name,

                        "x":
                            x,

                        "y":
                            y,

                        "w":
                            space.get(
                                "w",
                                FALLBACK_UNIT
                            ),

                        "h":
                            space.get(
                                "h",
                                FALLBACK_UNIT
                            )
                    }
                )


                unresolved_names.remove(
                    name
                )

            # ==========================================
            # SEMANTIC GRAPH SEED v1.0
            #
            # When no upstream geometric anchor exists,
            # seed the connected architectural graph with
            # one deterministic semantic origin.
            #
            # IMPORTANT:
            # - This is not arbitrary fallback placement.
            # - It only starts graph propagation.
            # - Public access / entrance is preferred.
            # - Existing upstream coordinates always win.
            # ==========================================

            def semantic_seed_priority(
                name
            ):

                item = normalized_nodes.get(
                    name,
                    {}
                )


                space = item.get(
                    "space",
                    {}
                )


                score = 0


                zone = str(
                    space.get(
                        "zone",
                        ""
                    )
                ).lower()


                planning_zone = str(
                    space.get(
                        "planning_zone",
                        ""
                    )
                ).lower()


                space_type = str(
                    space.get(
                        "space_type",
                        ""
                    )
                ).lower()


                canonical_name = str(
                    space.get(
                        "canonical_name",
                        ""
                    )
                ).lower()


                protected_zone = (
                    space.get(
                        "protected_zone"
                    )
                    is True
                )


                circulation_profile = (
                    space.get(
                        "circulation_profile"
                    )
                    or
                    {}
                )


                # ======================================
                # SEMANTIC FUNCTION PRIORITY
                # ======================================

                if canonical_name in {
                    "vertical_core",
                    "corridor",
                    "family_lounge",
                    "living_room",
                    "living"
                }:
                    score += 600


                if canonical_name in {
                    "master_bedroom",
                    "bedroom"
                }:
                    score += 300


                if canonical_name in {
                    "bathroom",
                    "service",
                    "storage",
                    "laundry_room"
                }:
                    score -= 300


                if protected_zone:
                    score += 500


                if circulation_profile.get(
                    "role"
                ) == "vertical":
                    score += 500


                # --------------------------------------
                # ENTRANCE / PUBLIC ACCESS
                # --------------------------------------

                if space_type in {
                    "entrance",
                    "public_access"
                }:
                    score += 1000


                if canonical_name in {
                    "lobby",
                    "entrance"
                }:
                    score += 900


                if (
                    zone == "public"
                    or
                    planning_zone == "public"
                ):
                    score += 300


                # --------------------------------------
                # GRAPH CONNECTIVITY
                # --------------------------------------

                score += (
                    len(
                        connection_map.get(
                            name,
                            []
                        )
                    )
                    *
                    10
                )


                return score


                # --------------------------------------
                # PUBLIC ZONE
                # --------------------------------------

                if (
                    zone == "public"
                    or
                    planning_zone == "public"
                ):

                    score += 300


                # --------------------------------------
                # GRAPH CONNECTIVITY
                # --------------------------------------

                score += (
                    len(
                        connection_map.get(
                            name,
                            []
                        )
                    )
                    *
                    10
                )


                return score


            # ==========================================
            # MULTI-COMPONENT SEMANTIC GRAPH SEED v1.1
            #
            # Each unresolved connected component must
            # have its own deterministic semantic seed
            # when it has no path to an already resolved
            # geometric anchor.
            #
            # IMPORTANT:
            # - Existing upstream anchors always win.
            # - Connected components are derived only
            #   from explicit architectural connections.
            # - Isolated nodes are NOT promoted into
            #   artificial graph components.
            # - Seed placement is collision-safe.
            # - Dictionary / connection order must not
            #   affect the result.
            # ==========================================

            def get_unresolved_connected_components():

                remaining = {
                    name
                    for name in unresolved_names
                    if connection_map.get(
                        name
                    )
                }

                components = []


                while remaining:

                    start_name = sorted(
                        remaining,
                        key=lambda name: (
                            -semantic_seed_priority(
                                name
                            ),
                            str(
                                name
                            )
                        )
                    )[0]

                    component = set()

                    stack = [
                        start_name
                    ]


                    while stack:

                        current_name = stack.pop()


                        if current_name in component:

                            continue


                        if current_name not in unresolved_names:

                            continue


                        component.add(
                            current_name
                        )

                        remaining.discard(
                            current_name
                        )


                        neighbours = sorted(

                            connection_map.get(
                                current_name,
                                []
                            ),

                            key=lambda relation:
                                str(
                                    relation.get(
                                        "target",
                                        ""
                                    )
                                )

                        )


                        for relation in neighbours:

                            target_name = relation.get(
                                "target"
                            )


                            if (
                                target_name
                                in
                                unresolved_names
                                and
                                target_name
                                not in
                                component
                            ):

                                stack.append(
                                    target_name
                                )


                    if component:

                        components.append(
                            component
                        )


                return components


            def component_has_resolved_anchor(
                component
            ):

                for component_name in component:

                    for relation in connection_map.get(
                        component_name,
                        []
                    ):

                        target_name = relation.get(
                            "target"
                        )


                        if target_name in resolved_positions:

                            return True


                return False


            def component_sort_key(
                component
            ):

                ranked_names = sorted(
                    component,
                    key=lambda name: (
                        -semantic_seed_priority(
                            name
                        ),
                        str(
                            name
                        )
                    )
                )


                if not ranked_names:

                    return (
                        0,
                        ""
                    )


                best_name = ranked_names[0]


                return (
                    -semantic_seed_priority(
                        best_name
                    ),
                    str(
                        best_name
                    )
                )


            unresolved_components = sorted(
                get_unresolved_connected_components(),
                key=component_sort_key
            )


            for component in unresolved_components:

                # --------------------------------------
                # If this component already touches an
                # upstream/resolved anchor, normal graph
                # propagation must resolve it.
                # --------------------------------------

                if component_has_resolved_anchor(
                    component
                ):

                    continue


                seed_name = sorted(
                    component,
                    key=lambda name: (
                        -semantic_seed_priority(
                            name
                        ),
                        str(
                            name
                        )
                    )
                )[0]


                seed_item = normalized_nodes[
                    seed_name
                ]

                seed_space = seed_item[
                    "space"
                ]


                seed_width = seed_space.get(
                    "w",
                    FALLBACK_UNIT
                )

                seed_height = seed_space.get(
                    "h",
                    FALLBACK_UNIT
                )


                # --------------------------------------
                # COLLISION-SAFE SEMANTIC SEED POSITION
                # --------------------------------------

                seed_x = None
                seed_y = None

                seed_index = 0

                seed_relations = connection_map.get(
                    seed_name,
                    []
                )


                while True:

                    candidate_x = (
                        seed_index
                        %
                        3
                    ) * FALLBACK_UNIT

                    candidate_y = (
                        seed_index
                        //
                        3
                    ) * FALLBACK_UNIT

                    candidate_directions = {
                        "right": (
                            candidate_x + seed_width,
                            candidate_y
                        ),
                        "left": (
                            candidate_x - FALLBACK_UNIT,
                            candidate_y
                        ),
                        "up": (
                            candidate_x,
                            candidate_y + seed_height
                        ),
                        "down": (
                            candidate_x,
                            candidate_y - FALLBACK_UNIT
                        )
                    }

                    free_direction_count = 0
                    direction_debug = {}

                    for direction, (
                        neighbour_x,
                        neighbour_y
                    ) in candidate_directions.items():

                        is_free = position_is_free(
                            neighbour_x,
                            neighbour_y,
                            FALLBACK_UNIT,
                            FALLBACK_UNIT
                        )

                        direction_debug[
                            direction
                        ] = {
                            "x": neighbour_x,
                            "y": neighbour_y,
                            "free": is_free
                        }

                        if is_free:
                            free_direction_count += 1


                    if position_is_free(
                        candidate_x,
                        candidate_y,
                        seed_width,
                        seed_height,
                        space_name=seed_name
                    ):

                        seed_x = candidate_x
                        seed_y = candidate_y

                        break


                    seed_index += 1

                seed_space["x"] = seed_x
                seed_space["y"] = seed_y


                if not resolved_positions:

                    seed_source = (
                        "semantic_graph_seed"
                    )

                else:

                    seed_source = (
                        "semantic_component_seed"
                    )


                seed_space[
                    "placement_source"
                ] = seed_source


                resolved_positions[
                    seed_name
                ] = {

                    "x":
                        seed_x,

                    "y":
                        seed_y,

                    "w":
                        seed_width,

                    "h":
                        seed_height

                }


                occupied_rectangles.append(
                    {

                        "name":
                            seed_name,

                        "x":
                            seed_x,

                        "y":
                            seed_y,

                        "w":
                            seed_width,

                        "h":
                            seed_height

                    }
                )


                unresolved_names.remove(
                    seed_name
                )


            # ==========================================
            # PASS 2+ — GRAPH PROPAGATION
            # ==========================================

            progress = True


            while (
                progress
                and
                unresolved_names
            ):

                progress = False


                for name in sorted(
                    unresolved_names,
                    key=graph_resolution_sort_key
                ):

                    item = normalized_nodes[
                        name
                    ]

                    space = item[
                        "space"
                    ]


                    width = space.get(
                        "w",
                        FALLBACK_UNIT
                    )

                    height = space.get(
                        "h",
                        FALLBACK_UNIT
                    )


                    related_spaces = connection_map.get(
                        name,
                        []
                    )


                    related_spaces = sorted(

                        related_spaces,

                        key=lambda relation: (
                            -semantic_graph_priority(
                                relation.get(
                                    "target"
                                )
                            ),
                            str(
                                relation.get(
                                    "target",
                                    ""
                                )
                            )
                        )

                    )


                    graph_position = None

                    # ==================================
                    # CONSUME FUTURE RESERVATION v1.0
                    #
                    # A previously selected joint graph
                    # assignment is a geometric contract,
                    # not merely scoring evidence.
                    # ==================================

                    existing_reservation = (
                        get_space_reservation(
                            name
                        )
                    )

                    
                    if existing_reservation is not None:

                        reservation_x = (
                            existing_reservation.get(
                                "x"
                            )
                        )

                        reservation_y = (
                            existing_reservation.get(
                                "y"
                            )
                        )


                        if position_is_free(
                            reservation_x,
                            reservation_y,
                            width,
                            height,
                            space_name=name
                        ):

                            graph_position = {

                                "x":
                                    reservation_x,

                                "y":
                                    reservation_y,

                                "direction":
                                    "future_reservation",

                                "graph_capacity":
                                    0,

                                "joint_graph_capacity":
                                    0,

                                "joint_assignment":
                                    [],

                                "reservation_consumed":
                                    True

                            }


                            if DEBUG_SPATIAL_GRAPH:

                                print(
                                    "🔓 FUTURE RESERVATION CONSUMED:",
                                    "SPACE=",
                                    name,
                                    "X=",
                                    reservation_x,
                                    "Y=",
                                    reservation_y
                                )


                    for relation in related_spaces:

                        if graph_position is not None:

                            break

                        target_name = relation.get(
                            "target"
                        )

                        relation_type = relation.get(
                            "type"
                        )
                    

                        target_position = (
                            resolved_positions.get(
                                target_name
                            )
                        )


                        if target_position is None:

                            continue


                        if relation_type not in [
                            "direct_connection",
                            "adjacent",
                            "private_connection",
                            "semantic_adjacent"
                        ]:
                            continue


                        target_x = target_position.get(
                            "x"
                        )

                        target_y = target_position.get(
                            "y"
                        )

                        target_w = target_position.get(
                            "w",
                            FALLBACK_UNIT
                        )

                        target_h = target_position.get(
                            "h",
                            FALLBACK_UNIT
                        )


                        graph_position = (
                            find_free_adjacent_position(

                                target_x,
                                target_y,

                                target_w,
                                target_h,

                                width,
                                height,

                                space_name=name,
                                target_name=target_name

                            )
                        )

                
                        if graph_position is not None:

                            break


                    if graph_position is None:

                        continue

                    if graph_position.get(
                        "joint_assignment"
                    ):

                        if DEBUG_SPATIAL_GRAPH:

                            print(
                                "📌 FUTURE RESERVATION CONTRACT:",
                                "PLACING=",
                                name,
                                "ASSIGNMENT=",
                                graph_position.get(
                                    "joint_assignment"
                                )
                            )


                    x = graph_position[
                        "x"
                    ]

                    y = graph_position[
                        "y"
                    ]


                    # ==================================
                    # RESERVATION COMMIT / CONSUME
                    # ==================================

                    release_space_reservation(
                        name
                    )


                    reserve_future_assignments(
                        graph_position.get(
                            "joint_assignment",
                            []
                        ),
                        created_by=name
                    )


                    space["x"] = x
                    space["y"] = y

                    space[
                        "placement_source"
                    ] = (
                        "graph_relationship"
                    )


                    resolved_positions[name] = {

                        "x":
                            x,

                        "y":
                            y,

                        "w":
                            width,

                        "h":
                            height

                    }


                    occupied_rectangles.append(
                        {
                            "name":
                                name,

                            "x":
                                x,

                            "y":
                                y,

                            "w":
                                width,

                            "h":
                                height
                        }
                    )


                    unresolved_names.remove(
                        name
                    )

                    progress = True


            # ==========================================
            # FINAL PASS — COLLISION-SAFE FALLBACK
            # ==========================================

            for name in sorted(
                unresolved_names,
                key=lambda item:
                    normalized_nodes[
                        item
                    ][
                        "index"
                    ]
            ):

                item = normalized_nodes[
                    name
                ]

                space = item[
                    "space"
                ]

                index = item[
                    "index"
                ]


                width = space.get(
                    "w",
                    FALLBACK_UNIT
                )

                height = space.get(
                    "h",
                    FALLBACK_UNIT
                )


                fallback_columns = 3

                fallback_index = index


                while True:

                    candidate_x = (
                        fallback_index
                        %
                        fallback_columns
                    ) * FALLBACK_UNIT


                    candidate_y = (
                        fallback_index
                        //
                        fallback_columns
                    ) * FALLBACK_UNIT


                    if position_is_free(
                        candidate_x,
                        candidate_y,
                        width,
                        height,
                        space_name=name
                    ):

                        x = candidate_x
                        y = candidate_y

                        break


                    fallback_index += 1


                space["x"] = x
                space["y"] = y

                space[
                    "placement_source"
                ] = (
                    "spatial_fallback"
                )


                resolved_positions[name] = {

                    "x":
                        x,

                    "y":
                        y,

                    "w":
                        width,

                    "h":
                        height

                }


                occupied_rectangles.append(
                    {
                        "name":
                            name,

                        "x":
                            x,

                        "y":
                            y,

                        "w":
                            width,

                        "h":
                            height
                    }
                )


            # ==========================================
            # BUILD FINAL SPACE LIST
            # Preserve original node order.
            # ==========================================

            for name, node in nodes.items():

                item = normalized_nodes.get(
                    name
                )


                if item is None:

                    continue


                space = item[
                    "space"
                ]


                spaces.append(
                    space
                )

           

            spatial["floors"][floor] = {



                "count":

                    len(spaces),



                "spaces":

                    spaces,



                "layout": {


                    "type":

                        "graph_based",



                    "core":

                    [

                        n

                        for n in spaces

                        if "core" in n

                    ],



                    "rooms":

                    [

                        n

                        for n in spaces

                        if "core" not in n

                    ]

                }

            }




        # ==================================================
        # CREATE EMPTY FLOORS FROM PROGRAM
        # ==================================================

        for level in required_floors:


            if level in spatial["floors"]:

                continue


            if level in [

                "basement",
                "floor_1",
                "first_floor",
                "upper"

            ]:


                if "F2" in spatial["floors"]:

                    continue


                floor_name = "F2"


            else:

                continue



            spatial["floors"][floor_name] = {


                "count":

                    0,


                "spaces":

                    [],


                "layout": {


                    "type":

                        "graph_based",


                    "core":

                        [],


                    "rooms":

                        []

                }

            }

        

        return spatial