# ==========================================================
# ArchitectOS Runtime Dispatcher v81
# ExecutionPlan -> Runtime Selection
# Vision Binding + Image Memory Source Resolver
# GOD CORE Runtime Bridge
# ==========================================================


from skills.comfyui.comfy_runtime import ComfyRuntime


from core.ai.prompt_intelligence import prompt_intelligence
from core.ai.edit_intelligence import edit_intelligence
from core.ai.design_intelligence import design_intelligence
from core.ai.vision_intelligence import vision_intelligence
from core.ai.prompt_compiler import prompt_compiler


from skills.comfyui.image_memory import memory


# ==========================================================
# GOD CORE RUNTIME
# ==========================================================

from core.runtime.runtime_selector import runtime_selector




class RuntimeDispatcher:


    def __init__(self):

        self.comfy = ComfyRuntime()


        self.runtime_selector = runtime_selector


        print(
            "🚀 Runtime Dispatcher v82 ACTIVE"
        )



    # ======================================================
    # DISPATCH
    # ======================================================

    def dispatch(
        self,
        plan,
        prompt,
        mode="image"
    ):


        workflow = plan.workflow

        engine = plan.engine



        print(
            "🚀 DISPATCH:",
            workflow,
            engine
        )


        print(
            "🧠 INTENT:",
            plan.intent
        )



        # ==================================================
        # GOD CORE DESIGN RUNTIME
        # ==================================================

        if engine == "god_core":


            print(
                "🏗️ GOD CORE DESIGN MODE ACTIVE"
            )


            project = {

                "prompt":
                    prompt,


                "intent":
                    plan.intent,


                "workflow":
                    workflow,


                "metadata":
                    getattr(
                        plan,
                        "metadata",
                        {}
                    )

            }


            runtime = self.runtime_selector.get_runtime()

            print(
                "🏛️ ACTIVE RUNTIME:",
                runtime.engine
            )


            result = runtime.run(
                project
            )


            return result




        # ==================================================
        # PROMPT PIPELINE
        # ==================================================

        enhanced_prompt = prompt_intelligence.enhance(

            prompt,

            intent=plan.intent

        )



        # ==================================================
        # RUNTIME PARAMS
        # ==================================================

        runtime_params = edit_intelligence.analyze(

            plan.intent

        )


        print(
            "🎨 EDIT PARAMS:",
            runtime_params
        )



        # ==================================================
        # SOURCE IMAGE RESOLVER
        # ==================================================

        source_image = None



        # PLAN IMAGE

        if hasattr(
            plan,
            "inputs"
        ):


            if isinstance(
                plan.inputs,
                dict
            ):


                source_image = plan.inputs.get(
                    "image"
                )



        if source_image:


            print(

                "📷 SOURCE IMAGE FROM PLAN:",

                source_image

            )



        # MEMORY FALLBACK

        if not source_image:


            source_image = memory.get_last_image()



        if source_image:


            print(

                "📷 SOURCE IMAGE FROM MEMORY:",

                source_image

            )


        else:


            print(

                "⚠️ NO SOURCE IMAGE AVAILABLE"

            )



        # ==================================================
        # RENOVATION PIPELINE
        # ==================================================

        if workflow == "flux_img2img":


            print(
                "🏠 RENOVATION MODE ACTIVE"
            )



            design_profile = design_intelligence.build(

                plan.intent,

                {

                    "style":
                        "modern"

                }

            )


            print(
                "🏠 DESIGN PROFILE READY"
            )



            print(
                "👁️ BUILDING VISION ANALYSIS"
            )



            building_analysis = vision_intelligence.analyze(

                source_image

            )


            print(
                "👁️ BUILDING ANALYSIS READY"
            )



            compiled_prompt = prompt_compiler.compile(

                enhanced_prompt,

                design_profile,

                building_analysis,

                runtime_params

            )


            enhanced_prompt = compiled_prompt["prompt"]



            print(
                "🏠 RENOVATION PROMPT READY"
            )



        # ==================================================
        # NEW BUILD
        # ==================================================

        elif workflow == "flux":


            print(
                "NEW BUILD MODE ACTIVE"
            )


            print(
                "NEW BUILD PROMPT READY"
            )


        # ==================================================
        # STANDARD MODE
        # ==================================================

        else:


            print(
                "STANDARD PROMPT MODE"
            ) 


        # ==================================================
        # EXECUTION
        # ==================================================

        print(
            "PROMPT PIPELINE COMPLETE"
        )


        # ==================================================
        # ENGINE EXECUTION
        # ==================================================

        if engine in [

            "flux",
            "wan"

        ]:


            if workflow == "flux_img2img":


                return self.comfy.generate(

                    enhanced_prompt,

                    "edit",

                    source_image=source_image,

                    params=runtime_params

                )



            if workflow == "flux":


                return self.comfy.generate(

                    enhanced_prompt,

                    "image",

                    params=runtime_params

                )



            if workflow == "wan_i2v":


                return self.comfy.generate(

                    enhanced_prompt,

                    "video",

                    params=runtime_params

                )



        return {


            "status":

                "failed",


            "error":

                "No runtime available",


            "plan":

                plan.__dict__

        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================

runtime_dispatcher = RuntimeDispatcher() 