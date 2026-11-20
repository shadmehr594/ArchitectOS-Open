"""
ArchitectOS Adaptive Residential Layout Engine v1.0

Generates residential layout strategy
from project conditions.
"""


class AdaptiveResidentialLayoutEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧠 Adaptive Residential Layout Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # LIGHTWELL DECISION
    # ==================================================

    def decide_lightwells(
        self,
        floors,
        units_per_floor,
        coverage
    ):


        total_units = (

            floors *

            units_per_floor

        )


        if coverage >= 90 and total_units > 4:

            return {

                "required":
                    True,

                "count":
                    1,

                "reason":
                    "high_density"

            }


        if total_units > 12:

            return {

                "required":
                    True,

                "count":
                    2,

                "reason":
                    "multi_unit"

            }


        return {

            "required":
                False,

            "count":
                0,

            "reason":
                "natural_facade"

        }



    # ==================================================
    # DUCT STRATEGY
    # ==================================================

    def decide_ducts(
        self,
        separate=True
    ):


        if separate:

            return {

                "bathroom":
                    "independent",

                "kitchen":
                    "independent"

            }


        return {

            "bathroom":
                "shared",

            "kitchen":
                "shared"

        }



    # ==================================================
    # CORE STRATEGY
    # ==================================================

    def decide_core(
        self,
        units_per_floor
    ):


        if units_per_floor <= 4:

            return {

                "type":
                    "central",

                "access":
                    "corridor"

            }


        return {

            "type":
                "central_plus_corridor",

            "access":
                "double_loaded"

        }



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        project
    ):


        lightwells = self.decide_lightwells(

            project.get(
                "floors",
                1
            ),

            project.get(
                "units_per_floor",
                1
            ),

            project.get(
                "coverage",
                60
            )

        )


        result = {


            "project":
                project,


            "strategy":

            {


                "lightwells":
                    lightwells,


                "ducts":
                    self.decide_ducts(

                        project.get(
                            "separate_ducts",
                            True

                        )

                    ),


                "core":
                    self.decide_core(

                        project.get(
                            "units_per_floor",
                            1

                        )

                    )

            }

        }


        return result