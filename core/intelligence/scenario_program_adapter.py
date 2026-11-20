"""
ArchitectOS Scenario Program Adapter v1.0

Converts scenario requirements into architectural spaces.
"""


class ScenarioProgramAdapter:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏛️ Scenario Program Adapter v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # APPLY SCENARIO
    # ==================================================

    def apply(
        self,
        floor_program,
        scenario_result
    ):


        requirements = scenario_result.get(
            "requirements",
            []
        )


        spaces = floor_program.get(
            "spaces",
            []
        )


        existing = [

            space.get(
                "type"
            )

            for space in spaces

        ]



        for requirement in requirements:



            if requirement == "car_lift":


                if "car_lift_zone" not in existing:


                    spaces.append(

                        {
                            "type":
                                "car_lift_zone",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "ramp":


                if "vehicle_ramp" not in existing:


                    spaces.append(

                        {
                            "type":
                                "vehicle_ramp",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "ventilation":


                if "ventilation_room" not in existing:


                    spaces.append(

                        {
                            "type":
                                "ventilation_room",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "internal_stair":


                if "internal_stair" not in existing:


                    spaces.append(

                        {
                            "type":
                                "internal_stair",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "double_height":


                if "double_height_space" not in existing:


                    spaces.append(

                        {
                            "type":
                                "double_height_space",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "private_zone":


                if "private_zone" not in existing:


                    spaces.append(

                        {
                            "type":
                                "private_zone",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "private_terrace":


                if "private_terrace" not in existing:


                    spaces.append(

                        {
                            "type":
                                "private_terrace",

                            "source":
                                "scenario_reasoning"

                        }

                    )



            elif requirement == "large_glazing":


                if "large_glazing_zone" not in existing:


                    spaces.append(

                        {
                            "type":
                                "large_glazing_zone",

                            "source":
                                "scenario_reasoning"

                        }

                    )



        return floor_program