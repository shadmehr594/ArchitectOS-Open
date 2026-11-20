# ==========================================================
# ArchitectOS Design Render Adapter v3
# Design Runtime -> Render Pipeline
# Full Design Context Transfer
# ==========================================================


from core.render.chat_render_bridge import ChatRenderBridge



class DesignRenderAdapter:


    VERSION = "3.0"



    def __init__(self):

        self.bridge = ChatRenderBridge()


        print(
            "🚀 DESIGN RENDER ADAPTER v3 ONLINE"
        )



    # ======================================================
    # PREPARE DESIGN CONTEXT
    # ======================================================


    def prepare_design(
        self,
        design_result
    ):


        design_result = design_result or {}


        requirements = (
            design_result.get(
                "requirements",
                {}
            )
        )


        return {


            "type":
                design_result.get(
                    "type",
                    "building"
                ),


            "floors":
                design_result.get(
                    "floors",
                    1
                ),


            "style":
                design_result.get(
                    "style",
                    "modern"
                ),


            "requirements":

                {

                    "garden":
                        requirements.get(
                            "garden",
                            False
                        ),

                    "pool":
                        requirements.get(
                            "pool",
                            False
                        ),

                    "parking":
                        requirements.get(
                            "parking",
                            False
                        ),

                    "green_roof":
                        requirements.get(
                            "green_roof",
                            False
                        )

                },


            "spatial":

                design_result.get(
                    "spatial",
                    {}
                ),


            "site":

                design_result.get(
                    "site",
                    {}
                ),


            "structural_grid":

                design_result.get(
                    "structural_grid",
                    {}
                ),


            "source":

                "design_runtime"

        }



    # ======================================================
    # SEND DESIGN TO RENDER
    # ======================================================


    def render(
        self,
        project_id,
        design_result,
        engine="flux"
    ):


        design = self.prepare_design(
            design_result
        )


        return self.bridge.render_design(
            project_id,
            design,
            engine
        )