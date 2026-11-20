# ==========================================================
# ArchitectOS Prompt Router v1.2
# Unified Prompt Output
#
# FIX:
# - Normalize text/image prompt result
# - Stable interface for RenderRuntime
# - Extract architectural_intent from runtime payload
# - Preserve img2img compatibility
# ==========================================================


from core.render.prompt_builder import PromptBuilder
from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder



class PromptRouter:


    VERSION = "1.2"



    def __init__(self):


        self.text_builder = PromptBuilder()


        self.image_builder = ImageEditPromptBuilder()


        print(
            "🧠 PROMPT ROUTER v1.2 ONLINE"
        )



    # ======================================================
    # BUILD
    # ======================================================


    def build(
        self,
        intent,
        mode="text2img"
    ):


        # ==================================================
        # NORMALIZE RUNTIME INPUT
        # ==================================================


        original_input = intent



        if isinstance(
            intent,
            dict
        ):

            runtime_input = intent


            if "architectural_intent" in runtime_input:

                architectural_intent = runtime_input.get(
                    "architectural_intent",
                    {}
                )

            else:

                architectural_intent = runtime_input



            if not isinstance(
                architectural_intent,
                dict
            ):

                architectural_intent = {}



            intent = {

                **architectural_intent,

                "_user_prompt":
                    runtime_input.get(
                        "prompt",
                        ""
                    )

            }

            # ==================================================
            # LIVE_FACADE_CONTRACT_PROPAGATION_FIX_V1
            #
            # RenderRuntime supplies the ALREADY-COMPOSED instruction at
            # `prompt_input["design_context"]["design"]["compiled_render_prompt"]`
            # (render_runtime.py:1455 / :1478). This rebuild used to drop it:
            # only `architectural_intent` survived, so the image builder could
            # never see that a structured ArchitecturalPreservationContractV1
            # was already carried, kept emitting its own legacy GEOMETRY
            # PRESERVATION block, and the resolved prompt ended up with TWO
            # contradictory preservation statements.
            #
            # The trusted runtime carrier is forwarded unchanged. When it is
            # absent nothing is added, so every caller that does not supply a
            # design context keeps its previous input shape and its output
            # byte for byte.
            # ==================================================

            _runtime_design_context = runtime_input.get(
                "design_context"
            )

            if isinstance(
                _runtime_design_context,
                dict
            ):

                intent["design_context"] = _runtime_design_context



        if not isinstance(
            intent,
            dict
        ):


            intent = {}



        print(
            "🔥 PROMPT ROUTER ORIGINAL INPUT:",
            original_input
        )


        print(
            "🔥 PROMPT ROUTER NORMALIZED INTENT:",
            intent
        )



        # ==================================================
        # BUILD PROMPT
        # ==================================================


        if mode in (

            "img2img",

            "image_edit",

            "edit"

        ):


            prompt = self.image_builder.build(

                intent

            )


        else:


            prompt = self.text_builder.build(

                intent

            )



        # ==================================================
        # NORMALIZE OUTPUT
        # ==================================================


        if isinstance(
            prompt,
            dict
        ):


            description = prompt.get(

                "description",

                ""

            )


        else:


            description = str(

                prompt

            )



        return {


            "description":

                description,



            "mode":

                mode,



            "raw":

                prompt



        }