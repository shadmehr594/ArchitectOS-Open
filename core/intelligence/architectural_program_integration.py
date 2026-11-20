"""
ArchitectOS Architectural Program Integration v1.0

Applies intelligence decisions into floor programs.
"""


class ArchitecturalProgramIntegration:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Architectural Program Integration v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # APPLY PROGRAM REQUIREMENTS
    # ==================================================

    def apply_program_requirements(
        self,
        floor_program,
        intelligence
    ):


        requirements = intelligence.get(
            "program_requirements",
            []
        )


        level = floor_program.get(
            "level"
        )


        spaces = floor_program.get(
            "spaces",
            []
        )


        existing = [

            item.get("type")

            for item in spaces

        ]



        for requirement in requirements:


            if requirement.get(
                "target"
            ) != level:

                continue



            additions = requirement.get(
                "additions",
                []
            )



            for addition in additions:


                if addition == "mezzanine":


                    if "mezzanine" not in existing:


                        spaces.append(

                            {
                                "type":
                                    "mezzanine",

                                "source":
                                    "architectural_intelligence"

                            }

                        )



                if addition == "street_frontage":


                    if "street_frontage" not in existing:


                        spaces.append(

                            {
                                "type":
                                    "street_frontage",

                                "source":
                                    "architectural_intelligence"

                            }

                        )



        return floor_program



    # ==================================================
    # APPLY VERTICAL SYSTEMS
    # ==================================================

    def apply_vertical_systems(
        self,
        floor_program,
        intelligence
    ):


        systems = intelligence.get(
            "vertical_systems",
            []
        )


        spaces = floor_program.get(
            "spaces",
            []
        )


        existing = [

            item.get("type")

            for item in spaces

        ]



        for system in systems:


            system_type = system.get(
                "type"
            )



            if system_type == "escalator":


                if "escalator_zone" not in existing:


                    spaces.append(

                        {
                            "type":
                                "escalator_zone",

                            "source":
                                "architectural_intelligence"

                        }

                    )



            if system_type == "elevator":


                if "elevator_core" not in existing:


                    spaces.append(

                        {
                            "type":
                                "elevator_core",

                            "source":
                                "architectural_intelligence"

                        }

                    )



            if system_type == "car_lift":


                if "car_lift_zone" not in existing:


                    spaces.append(

                        {
                            "type":
                                "car_lift_zone",

                            "source":
                                "architectural_intelligence"

                        }

                    )



        return floor_program



    # ==================================================
    # MAIN
    # ==================================================

    def integrate(
        self,
        floor_program,
        intelligence
    ):


        floor_program = self.apply_program_requirements(

            floor_program,

            intelligence

        )


        floor_program = self.apply_vertical_systems(

            floor_program,

            intelligence

        )


        return floor_program