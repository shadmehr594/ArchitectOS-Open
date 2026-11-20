# ==========================================================
# ARCHITECTURAL CONTEXT REGISTRY V1
# ARCHITECTOS CONTEXT STORAGE BRIDGE
# ==========================================================


class ArchitecturalContextRegistryV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🗂 Architectural Context Registry v1.0 ACTIVE"
        )


        self.context = None



    # ======================================================
    # REGISTER CONTEXT
    # ======================================================


    def register(
        self,
        context
    ):


        self.context = {


            "building_type":

                context.get(
                    "building_type"
                ),


            "architectural_intent":

                context.get(
                    "architectural_intent"
                ),


            "architectural_goal":

                context.get(
                    "architectural_goal"
                ),


            "target":

                context.get(
                    "target"
                ),


            "confidence":

                context.get(
                    "confidence",
                    0
                ),


            "source":

                context.get(
                    "source",
                    "planner"
                )

        }



        return {


            "engine":

                "ARCHITECTURAL_CONTEXT_REGISTRY_V1",


            "version":

                self.VERSION,


            "context":

                self.context,


            "registered":

                True

        }



    # ======================================================
    # GET CONTEXT
    # ======================================================


    def get_context(self):


        return self.context