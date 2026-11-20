class ArchitecturalElementPlacementReasonerV2:

    VERSION = "2.0"


    def __init__(self):

        print(
            "🏗 ARCHITECTURAL ELEMENT PLACEMENT REASONER V2 ONLINE"
        )


    def generate(
        self,
        architectural_layout,
        contract,
        vertical_graph
    ):

        result = {

            "floors": {},

            "circulation_graph":
                vertical_graph.get(
                    "circulation_graph",
                    []
                ),

            "vertical_core": [],

            "placement_rules": []

        }


        # ==================================
        # FLOOR DISTRIBUTION
        # ==================================

        floor_distribution = contract.get(
            "vertical_organization",
            {}
        )


        spaces = architectural_layout.get(
            "spaces",
            []
        )


        space_map = {

            item.get("name"):
                item

            for item in spaces

        }


        for floor, names in floor_distribution.items():

            result["floors"][floor] = {

                "spaces": [],

                "elements": [],

                "vertical_core": []

            }


            for name in names:

                if name in space_map:

                    result["floors"][floor]["spaces"].append(

                        space_map[name]

                    )


        # ==================================
        # VERTICAL CORE
        # ==================================

        systems = vertical_graph.get(
            "systems",
            []
        )


        for system in systems:

            element = {

                "name":
                    system,

                "type":
                    "vertical_circulation"

            }


            result["vertical_core"].append(
                element
            )


        # Attach vertical elements
        for floor in result["floors"]:

            result["floors"][floor][
                "vertical_core"
            ] = result["vertical_core"]



        # ==================================
        # RULES
        # ==================================

        result["placement_rules"] = [

            "spaces_follow_vertical_organization",

            "vertical_core_connects_levels",

            "external_access_connected_to_site",

            "circulation_has_priority"

        ]


        return result