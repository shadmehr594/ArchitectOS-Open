"""
ArchitectOS Vertical Program Integration Engine v2.0

Converts vertical circulation intelligence
into architectural program spaces.
"""


class VerticalProgramIntegrationEngine:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"🏗️ Vertical Program Integration Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # APPLY VERTICAL SYSTEMS
    # ==================================================

    def apply(
    self,
    program,
    vertical_network,
    accessibility_result=None
):


        if not vertical_network:

            return program



        systems = vertical_network.get(

            "vertical_systems",

            []

        )


        current_level = program.get(
            "level"
        )

        accessibility_result = accessibility_result or {}



        spaces = program.get(

            "spaces",

            []

        )



        existing = [

            space.get("type")

            for space in spaces

        ]


        def normalize_connected_levels(
            connects
        ):

            levels = []


            for item in connects or []:


                if isinstance(
                    item,
                    dict
                ):

                    level = item.get(
                        "level"
                    )


                    if level is not None:

                        levels.append(
                            level
                        )


                elif item is not None:

                    levels.append(
                        item
                    )


            return levels



        for system in systems:


            system_type = system.get(
                "type"
            )


            # ==================================================
            # NON-GEOMETRIC DECISION STATE
            # ==================================================

            if system_type == "vehicle_access_pending":

                continue


            connects = system.get(
                "connects",
                []
            )


            # ==================================================
            # NORMALIZE CONNECTED LEVELS
            # ==================================================

            connected_levels = []


            for connected in connects:


                if isinstance(
                    connected,
                    dict
                ):

                    connected_level = connected.get(
                        "level"
                    )


                    if connected_level is not None:

                        connected_levels.append(
                            connected_level
                        )


                elif connected is not None:

                    connected_levels.append(
                        connected
                    )


            # ==================================================
            # FLOOR OWNERSHIP FILTER
            # ==================================================

            if (
                current_level
                and
                connected_levels
                and
                current_level not in connected_levels
            ):

                continue


            space_definition = self.create_vertical_space(

                system

            )


            if not space_definition:

                continue


            if space_definition["type"] not in existing:


                spaces.append(

                    space_definition

                )


                existing.append(
                    space_definition["type"]
                )

        # ==================================
        # ACCESSIBILITY INTEGRATION
        # ==================================

        for item in accessibility_result.get(
            "systems",
            []
        ):

            accessibility_type = item.get(
                "type"
            )


            if (

                accessibility_type

                and

                accessibility_type not in existing

            ):


                spaces.append(

                    {

                        "type":
                            accessibility_type,


                        "source":
                            "accessibility_intelligence",


                        "requirements":
                            [

                                "accessible_design"

                            ],


                        "geometry":
                            item

                    }

                )


                existing.append(
                    accessibility_type
                )



        program["spaces"] = spaces



        return program



    # ==================================================
    # CREATE PROGRAM SPACE
    # ==================================================

    def create_vertical_space(
        self,
        system
    ):


        system_type = system.get(
            "type"
        )



        mapping = {


            "escalator":
            {

                "type":
                    "escalator_zone",

                "requirements":
                    [
                        "atrium_space",
                        "landing_area",
                        "safety_clearance"
                    ]

            },


            "moving_ramp":
            {

                "type":
                    "moving_ramp_zone",

                "requirements":
                    [
                        "shopping_cart_flow",
                        "landing_area"
                    ]

            },


            "elevator":
            {

                "type":
                    "elevator_core",

                "requirements":
                    [
                        "shaft",
                        "machine_room"
                    ]

            },


            "stairs":
            {

                "type":
                    "stair_core",

                "requirements":
                    [
                        "escape_route",
                        "vertical_connection"
                    ]

            },


            "vehicle_ramp":
            {

                "type":
                    "vehicle_ramp_zone",

                "requirements":
                    [
                        "vehicle_access"
                    ]

            },

            "accessible_ramp":
            {

                "type":
                    "accessible_ramp_zone",

                "requirements":
                    [
                        "accessible_route",
                        "wheelchair_access",
                        "landing_area",
                        "pedestrian_clearance"
                    ]

            },


            "car_lift":
            {

                "type":
                    "car_lift_zone",

                "requirements":
                    [
                        "parking_access"
                    ]

            }

        }



        definition = mapping.get(
            system_type
        )


        if not definition:

            return None



        return {


            "type":
                definition["type"],


            "source":
                "vertical_intelligence",


            "reason":
                system.get(
                    "reason"
                ),


            "role":
                system.get(
                    "role"
                ),


            "connects":
                system.get(
                    "connects",
                    []
                ),


            "parameters":
                system.get(
                    "parameters",
                    {}
                ),


            "protected_zone":
                system.get(
                    "protected_zone",
                    False
                ),


            "requirements":
                definition["requirements"]

        }