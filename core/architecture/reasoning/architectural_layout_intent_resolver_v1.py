class ArchitecturalLayoutIntentResolverV1:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🧭 ARCHITECTURAL LAYOUT INTENT RESOLVER V1 ONLINE"
        )



    def resolve(
        self,
        contract
    ):

        result = {

            "spaces": [],

            "adjacency": [],

            "layout_rules": []

        }


        # ==================================
        # SPACE INTENT
        # ==================================

        for space in contract.get(
            "spaces",
            []
        ):


            result["spaces"].append(

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

                    "floor":
                        space.get(
                            "floor"
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

                    "dimensional_requirements":
                        dict(
                            space.get(
                                "dimensional_requirements",
                                {}
                            )
                        ),

                    "resolved_dimensions":
                        space.get(
                            "resolved_dimensions"
                        ),

                    "role":
                        space.get(
                            "role"
                        ),

                    "position_intent":
                        self.get_position_intent(
                            space.get(
                                "planning_zone",
                                space.get(
                                    "zone"
                                )
                            )
                        ),

                    "importance":
                        self.get_importance(
                            space.get(
                                "role"
                            )
                        ),

                    # --------------------------------------
                    # PRESERVE SPATIAL / PARCEL EVIDENCE
                    # --------------------------------------

                    "x":
                        space.get(
                            "x"
                        ),

                    "y":
                        space.get(
                            "y"
                        ),

                    "coordinate_mode":
                        space.get(
                            "coordinate_mode"
                        ),

                    "placement_reason":
                        space.get(
                            "placement_reason"
                        ),

                    "anchor_space":
                        space.get(
                            "anchor_space"
                        ),

                    "access_edge_index":
                        space.get(
                            "access_edge_index"
                        ),

                    "road_width":
                        space.get(
                            "road_width"
                        ),

                    "access_edge_status":
                        space.get(
                            "access_edge_status"
                        ),

                    "parcel_relation":
                        space.get(
                            "parcel_relation"
                        ),

                    "preferred_edge_index":
                        space.get(
                            "preferred_edge_index"
                        ),

                    "edge_relation":
                        space.get(
                            "edge_relation"
                        ),

                    "edge_decision_status":
                        space.get(
                            "edge_decision_status"
                        ),

                    "edge_decision_reason":
                        space.get(
                            "edge_decision_reason"
                        ),

                    "site_context":
                        space.get(
                            "site_context"
                        )

                }

            )



        # ==================================
        # ADJACENCY
        # ==================================

        result["adjacency"] = contract.get(
            "adjacency",
            []
        )



        # ==================================
        # RULES
        # ==================================

        result["layout_rules"] = [

            "public_spaces_prefer_access",

            "private_spaces_require_separation",

            "service_spaces_support_functional_core",

            "circulation_connects_major_spaces"

        ]


        return result




    def get_position_intent(
        self,
        zone
    ):


        mapping = {


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


        return mapping.get(

            zone,

            "neutral_position"

        )



    def get_importance(
        self,
        role
    ):


        mapping = {


            "social_space":
                "high",


            "privacy_space":
                "medium",


            "support_space":
                "medium",


            "movement_space":
                "high"

        }


        return mapping.get(

            role,

            "normal"

        )