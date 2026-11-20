"""
ArchitectOS Site Design Engine v1.0

Combines site analysis results
and creates final architectural decisions.

Pipeline:

Site
 |
Analyzer
 |
Neighbors
 |
Setbacks
 |
Courtyard
 |
Separation
 |
Building Form
"""


class SiteDesignEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🌍 Site Design Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # FACADE CONDITIONS
    # ==================================================

    def analyze_facades(
        self,
        neighbors,
        access,
        courtyard
    ):


        facades = {}



        for side in [

            "north",
            "south",
            "east",
            "west"

        ]:


            if courtyard.get(
                "side"
            ) == side:


                facades[side] = "courtyard"



            elif neighbors.get(
                side,
                {}
            ).get(
                "exists",
                False
            ):


                facades[side] = "neighbor"



            elif access.get(
                "side"
            ) == side:


                facades[side] = "street"



            else:

                facades[side] = "open"



        return facades



    # ==================================================
    # MAIN DECISION
    # ==================================================

    def generate(
        self,
        site,
        analysis,
        building_form,
        separation
    ):


        neighbors = analysis.get(

            "neighbors",

            {}

        )


        access = analysis.get(

            "access",

            {}

        )


        courtyard_data = analysis.get(

            "courtyard",

            {}

        )



        facade_conditions = self.analyze_facades(

            neighbors,

            access,

            courtyard_data

        )



        result = {


            "site":

            {

                "area":

                    site.get(

                        "area",

                        0

                    )

            },


            "building":

            {

                "placement":

                    building_form.get(

                        "placement"

                    ),


                "footprint":

                    building_form.get(

                        "footprint"

                    )

            },


            "open_spaces":

            {

                "courtyard":

                    courtyard_data

            },


            "facades":

                facade_conditions,



            "separation":

                separation.get(

                    "separation_joints",

                    {}

                )

        }



        print(

            "\n====== SITE DESIGN DECISION ======"

        )


        print(

            "PLACEMENT:",

            result["building"]["placement"]

        )


        print(

            "FACADES:",

            result["facades"]

        )


        return result