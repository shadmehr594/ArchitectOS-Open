# ==========================================================
# ArchitectOS BIM Tool v2.0
# GOD CORE -> BIM FINAL INTEGRATION v109 Bridge
# ==========================================================


from core.tool_interface import BaseTool

from chatos.bim.bim_final_integration_v109 import (
    BIMFinalIntegrationV109
)



class BIMTool(BaseTool):


    name = "bim"



    def __init__(
        self,
        spatial_engine=None,
        graph_engine=None,
        validator=None
    ):


        self.spatial = spatial_engine

        self.graph = graph_engine

        self.validator = validator


        # ======================================
        # BIM FINAL DOMAIN
        # ======================================

        self.bim_engine = BIMFinalIntegrationV109()



    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(
        self,
        input_text
    ):


        # ======================================
        # STEP 1
        # CREATE DESIGN CONTEXT
        # ======================================

        bim_data = {


            "request":
                input_text,


            "geometry":
                {},


            "walls":
                {},


            "openings":
                {},


            "floor":
                {},


            "structure":
                {},


            "mep":
                {}

        }



        # ======================================
        # STEP 2
        # GOD CORE SPATIAL SUPPORT
        # ======================================

        if self.spatial:


            try:

                spatial_result = (
                    self.spatial.generate_grid(
                        floors=1
                    )
                )


                bim_data["geometry"] = {

                    "spaces":
                        spatial_result

                }


            except Exception as e:

                bim_data["spatial_error"] = str(e)




        # ======================================
        # STEP 3
        # BIM v109 FINAL INTEGRATION
        # ======================================


        result = self.bim_engine.execute(

            bim_data

        )



        return {


            "type":

                "bim_result",


            "engine":

                "BIMTool_v2.0",


            "input":

                input_text,


            "result":

                result

        }