class CompleteExteriorDesignReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 COMPLETE EXTERIOR DESIGN REASONER v1.0 ONLINE"
        )



    def generate(
        self,
        style,
        facade_language,
        materials,
        facade_assembly,
        facade_composition,
        roof_strategy,
        dome_strategy,
        boundary_wall,
        boundary_entrance,
        landscape_strategy,
        exterior_details
    ):


        return {


            "exterior_design": {


                "style": style,


                "facade": {

                    "language":
                    facade_language,

                    "assembly":
                    facade_assembly,

                    "composition":
                    facade_composition

                },


                "materials":
                materials,


                "roof":
                roof_strategy,


                "dome":
                dome_strategy,


                "boundary": {

                    "wall":
                    boundary_wall,

                    "entrance":
                    boundary_entrance

                },


                "landscape":
                landscape_strategy,


                "details":
                exterior_details


            },


            "source":
            "architectural_reasoning"

        }