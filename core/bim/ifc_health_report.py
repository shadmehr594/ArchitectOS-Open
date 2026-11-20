# ==========================================================
# IFC HEALTH REPORT V1
# ARCHITECTOS BIM HEALTH REPORT ENGINE
# ==========================================================


class IFCHealthReportV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "📋 IFC Health Report v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD REPORT
    # ======================================================


    def generate(
        self,
        validation_result
    ):


        statistics = validation_result.get(
            "statistics",
            {}
        )


        health = validation_result.get(
            "health",
            {}
        )


        report = {


            "engine":
                "IFC_HEALTH_REPORT_V1",


            "version":
                self.VERSION,



            "status":
                validation_result.get(
                    "status",
                    "unknown"
                ),



            "health": {


                "score":
                    health.get(
                        "score",
                        0
                    ),


                "geometry":
                    health.get(
                        "geometry",
                        "unknown"
                    ),


                "placement":
                    health.get(
                        "placement",
                        "unknown"
                    ),


                "geometry_content":
                    health.get(
                        "geometry_content",
                        "unknown"
                    ),


                "placement_chain":
                    health.get(
                        "placement_chain",
                        "unknown"
                    )

            },



            "model": {


                "storeys":
                    statistics.get(
                        "storeys",
                        0
                    ),


                "walls":
                    statistics.get(
                        "walls",
                        0
                    ),


                "columns":
                    statistics.get(
                        "columns",
                        0
                    ),


                "beams":
                    statistics.get(
                        "beams",
                        0
                    ),


                "slabs":
                    statistics.get(
                        "slabs",
                        0
                    ),


                "doors":
                    statistics.get(
                        "doors",
                        0
                    ),


                "windows":
                    statistics.get(
                        "windows",
                        0
                    )

            },



            "errors": {


                "geometry":
                    validation_result.get(
                        "geometry_errors",
                        []
                    ),


                "placement":
                    validation_result.get(
                        "placement_errors",
                        []
                    ),


                "placement_chain":
                    validation_result.get(
                        "placement_chain_errors",
                        []
                    ),


                "geometry_content":
                    validation_result.get(
                        "geometry_content_errors",
                        []
                    )

            },


            "recommendations":[]


        }



        if report["health"]["score"] == 100:


            report["recommendations"].append(

                "IFC model is healthy"

            )


        else:


            report["recommendations"].append(

                "Review IFC quality issues"

            )



        return report