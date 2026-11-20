# ==========================================================
# IFC HEALTH PIPELINE V1
# ARCHITECTOS UNIFIED BIM HEALTH SYSTEM
# ==========================================================


from core.bim.ifc_quality_validator_v2 import (
    IFCQualityValidatorV2
)

from core.bim.ifc_spatial_validator_v1 import (
    IFCSpatialValidatorV1
)

from core.bim.ifc_health_report import (
    IFCHealthReportV1
)



class IFCHealthPipelineV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🚀 IFC Health Pipeline v1.0 ACTIVE"
        )


        self.quality_validator = (
            IFCQualityValidatorV2()
        )


        self.spatial_validator = (
            IFCSpatialValidatorV1()
        )


        self.report_generator = (
            IFCHealthReportV1()
        )



    # ======================================================
    # RUN PIPELINE
    # ======================================================


    def run(
        self,
        ifc_path
    ):


        quality_result = (
            self.quality_validator.validate(
                ifc_path
            )
        )



        spatial_result = (
            self.spatial_validator.validate(
                ifc_path
            )
        )



        report = (
            self.report_generator.generate(
                quality_result
            )
        )



        quality_score = (
            quality_result
            .get(
                "health",
                {}
            )
            .get(
                "score",
                0
            )
        )



        spatial_score = (
            spatial_result
            .get(
                "spatial_health",
                {}
            )
            .get(
                "score",
                0
            )
        )



        overall_score = int(

            (

                quality_score

                +

                spatial_score

            )

            /

            2

        )



        result = {


            "engine":
                "ARCHITECTOS_BIM_HEALTH_PIPELINE",


            "version":
                self.VERSION,



            "file":
                ifc_path,



            "quality":
            {

                "score":
                    quality_score,


                "status":
                    quality_result.get(
                        "status"
                    )

            },



            "spatial":
            {

                "score":
                    spatial_score,


                "status":
                    spatial_result.get(
                        "status"
                    )

            },



            "report":
                report,



            "overall":
            {

                "score":
                    overall_score,


                "status":
                    (
                        "healthy"

                        if overall_score == 100

                        else

                        "warning"

                    )

            }

        }



        return result