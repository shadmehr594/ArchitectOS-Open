# ==========================================================
# IFC PLANNER BRIDGE V1
# ARCHITECTOS IFC → PLANNER CONTEXT BRIDGE
# ==========================================================


from core.architecture.planner.ifc_architectural_context_adapter_v1 import (
    IFCArchitecturalContextAdapterV1
)



class IFCPlannerBridgeV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 IFC Planner Bridge v1.0 ACTIVE"
        )


        self.adapter = (
            IFCArchitecturalContextAdapterV1()
        )



    # ======================================================
    # CONVERT IFC REPORT TO PLANNER INPUT
    # ======================================================


    def build_planner_input(
        self,
        intelligence_report
    ):


        context = self.adapter.adapt(
            intelligence_report
        )


        planner_input = {


            "source":

                "IFC",



            "planner_context":

                context,



            "intent":

                "existing_building_analysis",



            "ready":

                context.get(
                    "planner_ready",
                    False
                )

        }


        return planner_input