# ==========================================================
# ArchitectOS Workflow Injector v3.7
# Universal Workflow Prompt + Seed Injection
#
# FIX:
# - Explicit positive / negative routing
# - Detect positive / negative from KSampler graph
# - Inject negative prompt correctly
# - Stable CLIP handling
# - Img2Img denoise control
# - Seed override + cache breaker
# - Safe workflow mutation
# ==========================================================


import copy
import time



class WorkflowInjector:


    VERSION = "3.7"



    def __init__(self):

        print(
            "🔧 WORKFLOW INJECTOR v3.7 ONLINE"
        )



    # ======================================================
    # NORMALIZE PROMPT
    # ======================================================


    def normalize_prompt(
        self,
        prompt
    ):


        if prompt is None:

            return ""



        if isinstance(
            prompt,
            dict
        ):


            return str(

                prompt.get(
                    "description",
                    ""
                )

            )



        return str(
            prompt
        )



    # ======================================================
    # NORMALIZE NEGATIVE
    # ======================================================


    def normalize_negative(
        self,
        negative_prompt
    ):


        if negative_prompt is None:

            return (
                "low quality, blurry, "
                "distorted, bad geometry, "
                "deformed, unrealistic, "
                "bad architecture"
            )



        return str(
            negative_prompt
        )



    # ======================================================
    # GRAPH ROUTING
    # ======================================================


    def detect_clip_routes(
        self,
        workflow
    ):


        positive_nodes = set()

        negative_nodes = set()



        for node_id, node in workflow.items():


            if not isinstance(
                node,
                dict
            ):
                continue



            if node.get(
                "class_type"
            ) != "KSampler":

                continue



            inputs = node.get(
                "inputs",
                {}
            )



            positive = inputs.get(
                "positive"
            )


            negative = inputs.get(
                "negative"
            )



            if (
                isinstance(
                    positive,
                    list
                )
                and len(positive) > 0
            ):

                positive_nodes.add(
                    str(
                        positive[0]
                    )
                )



            if (
                isinstance(
                    negative,
                    list
                )
                and len(negative) > 0
            ):

                negative_nodes.add(
                    str(
                        negative[0]
                    )
                )



        return (
            positive_nodes,
            negative_nodes
        )


    # ======================================================
    # PROMPT INJECTION
    # ======================================================


    def inject_prompt(
        self,
        workflow,
        prompt,
        negative_prompt
    ):


        positive_text = self.normalize_prompt(
            prompt
        )


        negative_text = self.normalize_negative(
            negative_prompt
        )



        (
            positive_nodes,
            negative_nodes

        ) = self.detect_clip_routes(
            workflow
        )



        print(
            "✅ POSITIVE NODE MAP:",
            positive_nodes
        )


        print(
            "⛔ NEGATIVE NODE MAP:",
            negative_nodes
        )



        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue



            if node.get(
                "class_type"
            ) != "CLIPTextEncode":

                continue



            inputs = node.get(
                "inputs",
                {}
            )



            if "text" not in inputs:

                continue



            # ==============================================
            # NEGATIVE
            # ==============================================


            if str(
                node_id
            ) in negative_nodes:


                inputs["text"] = negative_text


                print(
                    "⛔ NEGATIVE PROMPT INJECTED:",
                    node_id
                )


                continue



            # ==============================================
            # POSITIVE
            # ==============================================


            if str(
                node_id
            ) in positive_nodes:


                inputs["text"] = positive_text


                print(
                    "🔥 POSITIVE PROMPT INJECTED:",
                    node_id
                )


                continue



            print(
                "⚠️ UNKNOWN CLIP NODE SKIPPED:",
                node_id
            )



        return workflow



    # ======================================================
    # IMG2IMG DENOISE
    # ======================================================


    def inject_denoise(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow



        if context.get(
            "mode"
        ) != "img2img":

            return workflow



        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue



            if node.get(
                "class_type"
            ) != "KSampler":

                continue



            inputs = node.get(
                "inputs",
                {}
            )



            old_value = inputs.get(
                "denoise"
            )



            inputs["denoise"] = 0.55



            print(
                "🎚️ DENOISE UPDATED:",
                node_id,
                old_value,
                "->",
                0.55
            )



        return workflow



    # ======================================================
    # SEED
    # ======================================================


    def inject_seed(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow



        seed = context.get(
            "seed"
        )



        if seed is None:

            return workflow



        seed = int(
            seed
        )



        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue



            if node.get(
                "class_type"
            ) != "KSampler":

                continue



            inputs = node.get(
                "inputs",
                {}
            )



            old_seed = inputs.get(
                "seed"
            )



            inputs["seed"] = seed



            print(
                "🎲 SEED UPDATED:",
                node_id,
                old_seed,
                "->",
                seed
            )



        return workflow



    # ======================================================
    # DIMENSIONS  (TEXT_TO_IMAGE_COMFY_03)
    #
    # Controlled injection of EmptyLatentImage width/height.
    # Values must be positive and divisible by 8 (latent-safe).
    # Invalid values are refused rather than silently corrupting
    # the workflow.
    # ======================================================


    @staticmethod
    def _valid_dimension(value):

        try:

            value = int(value)

        except (TypeError, ValueError):

            return None

        if value <= 0 or value % 8 != 0:

            return None

        return value


    def inject_dimensions(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow


        width = self._valid_dimension(
            context.get("width")
        )

        height = self._valid_dimension(
            context.get("height")
        )


        if width is None and height is None:

            return workflow


        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue


            if node.get(
                "class_type"
            ) != "EmptyLatentImage":

                continue


            inputs = node.get(
                "inputs",
                {}
            )


            if width is not None:

                old_width = inputs.get("width")

                inputs["width"] = width

                print(
                    "📐 WIDTH UPDATED:",
                    node_id,
                    old_width,
                    "->",
                    width
                )


            if height is not None:

                old_height = inputs.get("height")

                inputs["height"] = height

                print(
                    "📐 HEIGHT UPDATED:",
                    node_id,
                    old_height,
                    "->",
                    height
                )


        return workflow



    # ======================================================
    # SAMPLER STEPS  (TEXT_TO_IMAGE_COMFY_03)
    #
    # steps is a plain integer input on KSampler, so it is safely
    # injectable. cfg / sampler_name / scheduler are deliberately
    # NOT injected - they are part of the proven flux baseline.
    # ======================================================


    def inject_steps(
        self,
        workflow,
        context
    ):


        if not isinstance(
            context,
            dict
        ):

            return workflow


        steps = context.get("steps")


        try:

            steps = int(steps)

        except (TypeError, ValueError):

            return workflow


        if steps <= 0 or steps > 150:

            return workflow


        for node_id,node in workflow.items():


            if not isinstance(
                node,
                dict
            ):

                continue


            if node.get(
                "class_type"
            ) != "KSampler":

                continue


            inputs = node.get(
                "inputs",
                {}
            )


            old_steps = inputs.get("steps")


            inputs["steps"] = steps


            print(
                "🪜 STEPS UPDATED:",
                node_id,
                old_steps,
                "->",
                steps
            )


        return workflow



    # ======================================================
    # CACHE BREAKER
    # ======================================================


    def break_cache(
        self,
        workflow
    ):


        # ==================================================
        # CACHE BREAKER METADATA
        # ==================================================

        workflow["_architectos_runtime"] = {

            "timestamp":
                time.time(),

            "injector":
                self.VERSION

        }


        print(
            "♻️ CACHE BREAKER APPLIED"
        )


        return workflow



    # ======================================================
    # MAIN
    # ======================================================


    def inject(
        self,
        workflow,
        prompt,
        context=None,
        negative_prompt=None
    ):


        # ==================================================
        # ISOLATED WORKING COPY
        #
        # Every render request mutates its own deep copy. The loaded
        # canonical workflow object is never mutated in place, so
        # prompt / seed / dimensions / preset values cannot leak
        # between sequential renders.
        # ==================================================

        injected = copy.deepcopy(
            workflow
        )



        injected = self.inject_dimensions(
            injected,
            context
        )



        injected = self.inject_steps(
            injected,
            context
        )



        injected = self.inject_denoise(
            injected,
            context
        )



        injected = self.inject_seed(
            injected,
            context
        )



        injected = self.inject_prompt(
            injected,
            prompt,
            negative_prompt
        )



        injected = self.break_cache(
            injected
        )



        return {


            "workflow":

                injected,



            "architectos_prompt":

                self.normalize_prompt(
                    prompt
                ),



            "negative_prompt":

                self.normalize_negative(
                    negative_prompt
                ),



            "context":

                context or {},



            "status":

                "injected"

        }