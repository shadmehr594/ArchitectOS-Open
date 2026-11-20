class VerticalCirculationIntegrationReasoner:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🔗 VERTICAL CIRCULATION INTEGRATION REASONER v1.0 ONLINE"
        )


    def generate(
        self,
        vertical_output,
        contract
    ):

        result = {

            "circulation_graph": [],

            "systems": [],

            "level_connections": []

        }


        elements = vertical_output.get(
            "vertical_elements",
            []
        )


        # ==================================
        # SYSTEM REGISTRY
        # ==================================

        for element in elements:

            name = element.get(
                "name"
            )

            element_type = element.get(
                "type"
            )


            result["systems"].append(
                name
            )


            # ===============================
            # LEVEL CONNECTION
            # ===============================

            if (
                element.get("from")
                and
                element.get("to")
            ):

                result["level_connections"].append(

                    {

                        "element":
                            name,

                        "from":
                            element.get("from"),

                        "to":
                            element.get("to")

                    }

                )



        # ==================================
        # SPACE CONNECTIONS
        # ==================================

        spaces = [

            item.get("name")

            for item in contract.get(
                "spaces",
                []
            )

        ]


        if "entrance" in spaces:

            for system in result["systems"]:

                result["circulation_graph"].append(

                    {

                        "from":
                            "entrance",

                        "to":
                            system,

                        "type":
                            "access"

                    }

                )


        if "parking" in spaces:

            result["systems"].append(
                "car_lift"
            )


            result["circulation_graph"].append(

                {

                    "from":
                        "parking",

                    "to":
                        "car_lift",

                    "type":
                        "vehicle_vertical_access"

                }

            )


        # ==================================
        # FUTURE READY SYSTEMS
        # ==================================

        future_systems = [

            "escalator",

            "moving_ramp"

        ]


        for system in future_systems:

            if system not in result["systems"]:

                result["systems"].append(
                    system
                )


        return result