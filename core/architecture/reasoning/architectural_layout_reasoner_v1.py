class ArchitecturalLayoutReasonerV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 ARCHITECTURAL LAYOUT REASONER v1.0 ONLINE"
        )



    def generate(
        self,
        spatial_contract,
        design_context=None
    ):


        result = {


            "spaces": [],

            "relationships": [],

            "layout_strategy": [],

            "architectural_rules": []

        }



        design_context = design_context or {}

        

        # ==================================
        # SPACE INTELLIGENCE
        # ==================================


        for space in spatial_contract.get(
            "spaces",
            []
        ):


            name = space.get(
                "name"
            )


            zone = space.get(
                "zone"
            )


            role = space.get(
                "role"
            )



            space_intent = {


                "name":
                    name,


                "zone":
                    zone,


                "role":
                    role,


                "design_requirements":
                    self.get_space_requirements(
                        name,
                        zone
                    )

            }



            result["spaces"].append(
                space_intent
            )



        # ==================================
        # RELATIONSHIP REASONING
        # ==================================


        for relation in spatial_contract.get(
            "adjacency",
            []
        ):


            result["relationships"].append(

                {


                    "from":
                        relation.get("from"),


                    "to":
                        relation.get("to"),


                    "relationship":
                        relation.get("relationship"),


                    "priority":
                        self.get_relation_priority(
                            relation.get("relationship")
                        )

                }

            )



        # ==================================
        # PLANNING STRATEGY
        # ==================================


        result["layout_strategy"].extend(

            spatial_contract.get(
                "planning_rules",
                []
            )

        )



        # ==================================
        # ARCHITECTURAL RULES
        # ==================================


        result["architectural_rules"] = [

            "public_spaces_prefer_external_connection",

            "private_spaces_require_privacy",

            "service_spaces_support_main_spaces",

            "circulation_connects_vertical_levels"

        ]



        return result


    def get_space_requirements(
        self,
        name,
        zone
    ):


        requirements = {}



        if zone == "public":

            requirements = {

                "daylight":
                    "high",

                "social_quality":
                    "high",

                "external_relation":
                    True

            }



        elif zone == "private":

            requirements = {

                "privacy":
                    "high",

                "noise_control":
                    "high",

                "daylight":
                    "medium"

            }



        elif zone == "service":

            requirements = {

                "efficiency":
                    "high",

                "adjacency_to_public":
                    True

            }



        elif zone == "external":

            requirements = {

                "landscape_relation":
                    True,

                "visual_connection":
                    True

            }

        elif zone == "circulation":

            requirements = {

                "connectivity":
                    "high",

                "vertical_relation":
                    True,

                "central_position":
                    True

            }



        return requirements




    def get_relation_priority(
        self,
        relation
    ):


        priorities = {


            "direct_connection":
                "high",


            "visual_connection":
                "medium",


            "adjacent":
                "high",


            "private_connection":
                "high"

        }


        return priorities.get(
            relation,
            "normal"
        )
# =====================================
# Backward Compatibility Alias
# =====================================

ArchitecturalLayoutReasoner = ArchitecturalLayoutReasonerV1