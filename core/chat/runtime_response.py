# ==========================================================
# ArchitectOS Runtime Response v29
# Unified Output Contract
# Runtime -> Adapter -> UI Compatibility Layer
# Render/Image Promotion Layer
# ==========================================================


class RuntimeResponse:


    VERSION = "v29"



    def __init__(
        self,
        response_type,
        engine,
        result,
        metadata=None,
        status="success"
    ):


        self.data = {

            "type": response_type,

            "engine": engine,

            "result": result,

            "metadata": metadata or {},

            "status": status

        }



        # ==================================================
        # RESULT PROMOTION
        # Render / Image / Design Compatibility
        # ==================================================


        if isinstance(result, dict):


            # --------------------------
            # DIRECT IMAGE
            # --------------------------

            if "image" in result:

                self.data["image"] = result["image"]



            # --------------------------
            # RENDER OBJECT
            # --------------------------

            if "render" in result:

                self.data["render"] = result["render"]



            # --------------------------
            # RENDER ASSET
            # --------------------------

            if "render_asset" in result:

                self.data["image"] = (
                    result["render_asset"]
                )

                self.data["render_asset"] = (
                    result["render_asset"]
                )



            # --------------------------
            # IMAGE PATH
            # --------------------------

            if "image_path" in result:

                self.data["image"] = (
                    result["image_path"]
                )



            # --------------------------
            # ASSET PATH
            # --------------------------

            if "asset_path" in result:

                self.data["image"] = (
                    result["asset_path"]
                )



            # --------------------------
            # OUTPUT PATH
            # --------------------------

            if "output" in result:

                self.data["image"] = (
                    result["output"]
                )



            # --------------------------
            # DESIGN
            # --------------------------

            if "design" in result:

                self.data["design"] = (
                    result["design"]
                )



            # --------------------------
            # PROMPT
            # --------------------------

            if "prompt" in result:

                self.data["prompt"] = (
                    result["prompt"]
                )



            # --------------------------
            # ARCH INTENT
            # --------------------------

            if "architectural_intent" in result:

                self.data["architectural_intent"] = (
                    result["architectural_intent"]
                )



            # --------------------------
            # MEMORY
            # --------------------------

            if "memory" in result:

                self.data["memory"] = (
                    result["memory"]
                )



    # ==================================================
    # JSON OUTPUT
    # ==================================================

    def json(self):

        return self.data




# ==========================================================
# SINGLETON
# ==========================================================

runtime_response = RuntimeResponse