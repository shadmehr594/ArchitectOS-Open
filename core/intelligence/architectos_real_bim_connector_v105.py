# ==================================================
# ArchitectOS Real BIM Connector v106
# ==================================================


from core.bim.full_bim_pipeline import FullBIMPipeline

from core.bim.geometry_cleanup_engine_v106 import (
    GeometryCleanupEngine
)



class ArchitectOSRealBIMConnector:


    VERSION = "106.0"



    def __init__(self):


        print(
            "🏗️ ArchitectOS Real BIM Connector v106.0 ACTIVE"
        )


        self.cleanup = GeometryCleanupEngine()


        self.pipeline = FullBIMPipeline()



    # ==================================================
    # REAL BIM EXECUTION
    # ==================================================

    def process(
        self,
        request
    ):


        print(
            "▶️ REAL BIM PIPELINE EXECUTION"
        )


        #
        # STEP 1
        # Geometry Cleanup
        #

        cleanup_result = self.cleanup.process(
            request
        )


        cleaned_request = (
            cleanup_result
            .get(
                "cleaned_model",
                request
            )
        )


        #
        # STEP 2
        # Full BIM Pipeline
        #

        result = self.pipeline.run(
            cleaned_request
        )



        return {


            "engine":
            f"architectos_real_bim_connector_v{self.VERSION}",



            "status":
            "completed",



            "cleanup":
            cleanup_result,



            "bim_pipeline":
            "FullBIMPipeline",



            "result":
            result

        }