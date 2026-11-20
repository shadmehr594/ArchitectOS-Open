"""
ArchitectOS Vertical Program Adapter v1.0

Converts vertical circulation decisions
into floor program spaces.
"""


class VerticalProgramAdapter:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🛗 Vertical Program Adapter v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # APPLY VERTICAL SYSTEMS
    # ==================================================

    def adapt(
        self,
        floor_program,
        vertical_result
    ):


        systems = vertical_result.get(
            "vertical_systems",
            []
        )


        existing = [

            space.get("type")

            for space in floor_program.get(
                "spaces",
                []
            )

        ]



        for system in systems:


            system_type = system.get(
                "type"
            )


            if not system_type:

                continue



            space_type = self.map_system_to_space(
                system_type
            )



            if (
                space_type
                and
                space_type not in existing
            ):


                floor_program["spaces"].append(

                    {

                        "type":
                            space_type,


                        "source":
                            "vertical_reasoning",


                        "reason":
                            system.get(
                                "reason"
                            ),


                        "connects":
                            system.get(
                                "connects",
                                []
                            )

                    }

                )



        return floor_program



    # ==================================================
    # SYSTEM MAPPING
    # ==================================================

    def map_system_to_space(
        self,
        system_type
    ):


        mapping = {


            "elevator":
                "elevator_core",


            "escalator":
                "escalator_zone",


            "car_lift":
                "car_lift_zone",


            "vehicle_ramp":
                "vehicle_ramp_zone",


            "ramp":
                "ramp_zone",


            "stairs":
                "stair_core",


            "moving_ramp":
                "moving_ramp_zone"

        }



        return mapping.get(
            system_type
        )