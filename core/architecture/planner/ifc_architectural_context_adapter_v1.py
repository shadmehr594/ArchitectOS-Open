# ==========================================================
# IFC ARCHITECTURAL CONTEXT ADAPTER V1
# ARCHITECTOS PLANNER CONTEXT BRIDGE
# ==========================================================


class IFCArchitecturalContextAdapterV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔗 IFC Architectural Context Adapter v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD PLANNER CONTEXT
    # ======================================================


    def adapt(
        self,
        intelligence_report
    ):


        summary = intelligence_report.get(
            "building_summary",
            {}
        )


        quality = intelligence_report.get(
            "architectural_quality",
            {}
        )


        observations = intelligence_report.get(
            "observations",
            []
        )



        context = {


            "source":
                "IFC",



            "context_type":
                "architectural_existing_model",



            "building_state":
            {

                "floors":
                    summary.get(
                        "floors",
                        0
                    ),


                "walls":
                    summary.get(
                        "walls",
                        0
                    ),


                "doors":
                    summary.get(
                        "doors",
                        0
                    ),


                "windows":
                    summary.get(
                        "windows",
                        0
                    ),


                "openings":
                    summary.get(
                        "openings",
                        0
                    )

            },



            "architectural_quality":
            {

                "score":
                    quality.get(
                        "score",
                        0
                    ),


                "status":
                    quality.get(
                        "status",
                        "unknown"
                    )

            },



            "observations":
                observations,



            "planner_ready":
                True

        }



        return context