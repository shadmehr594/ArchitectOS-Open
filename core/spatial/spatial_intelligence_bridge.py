class SpatialIntelligenceBridge:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 SPATIAL INTELLIGENCE BRIDGE v1.0 ONLINE"
        )



    # ==================================================
    # BUILD PROJECT CONTEXT
    # ==================================================

    def build_context(
        self,
        intent,
        spatial_model,
        reasoning,
        constraints,
        layout_logic,
        plan,
        validation
    ):


        context = {


            "project":

            {

                "building_type":

                    intent.get(
                        "building_type"
                    ),


                "category":

                    intent.get(
                        "category"
                    ),


                "style":

                    intent.get(
                        "style"
                    ),


                "materials":

                    intent.get(
                        "materials",
                        []
                    )

            },



            "spatial":

            {

                "model":

                    spatial_model,


                "reasoning":

                    reasoning,


                "constraints":

                    constraints

            },



            "layout":

            {

                "logic":

                    layout_logic,


                "plan":

                    plan

            },



            "validation":

                validation,



            "render_context":

            {

                "camera":

                    intent.get(
                        "camera"
                    ),


                "mood":

                    intent.get(
                        "mood"
                    )

            },



            "metadata":

            {

                "engine":

                    "Spatial Intelligence Bridge",


                "version":

                    self.VERSION

            }

        }



        return context