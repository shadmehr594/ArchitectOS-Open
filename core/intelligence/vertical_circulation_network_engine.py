"""
ArchitectOS Vertical Circulation Network Intelligence v1.0

Selects and combines vertical circulation systems.
"""


class VerticalCirculationNetworkEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧠 Vertical Circulation Network Intelligence v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # ANALYZE BUILDING
    # ==================================================

    def analyze(
        self,
        building
    ):


        building_type = building.get(
            "building_type",
            "residential"
        )


        floors = building.get(
            "floors",
            1
        )


        basement = building.get(
            "basement",
            0
        )


        public_flow = building.get(
            "public_flow",
            "medium"
        )


        parking = building.get(
            "parking",
            False
        )


        wheelchair = building.get(
            "wheelchair_access",
            True
        )


        systems = []



        # ==================================
        # PUBLIC FLOW SYSTEMS
        # ==================================

        if (

            building_type in [

                "shopping_center",
                "mall",
                "commercial"

            ]

            and

            public_flow == "high"

        ):


            systems.append(

                {

                    "type":
                        "escalator",

                    "reason":
                        "high_public_flow"

                }

            )



            systems.append(

                {

                    "type":
                        "moving_ramp",

                    "reason":
                        "shopping_cart_and_flow"

                }

            )



        # ==================================
        # ACCESSIBILITY
        # ==================================

        if len(floors) > 1:


            systems.append(

                {

                    "type":
                        "elevator",

                    "reason":
                        "vertical_accessibility",

                    "connects":
                        floors

                }

            )



        # ==================================
        # VERTICAL CORE
        # ==================================

        if floors > 1:


            systems.append(

                {

                    "type":
                        "stairs",

                    "reason":
                        "vertical_core"

                }

            )



        # ==================================
        # PARKING ACCESS
        # ==================================

        if parking and basement > 0:


            systems.append(

                {

                    "type":
                        "vehicle_ramp",

                    "reason":
                        "vehicle_access"

                }

            )


            if basement >= 2:


                systems.append(

                    {

                        "type":
                            "car_lift",

                        "reason":
                            "space_optimization"

                    }

                )



        return {


            "building_type":
                building_type,


            "vertical_systems":
                systems,


            "system_count":
                len(
                    systems
                ),


            "source":
                "vertical_circulation_network"

        }