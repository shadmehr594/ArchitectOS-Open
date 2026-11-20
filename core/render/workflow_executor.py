# ==========================================================
# ArchitectOS Workflow Executor v4.2
# Unified Render Execution Engine
#
# Flux + Img2Img + WAN
#
# Fix:
# - Preserve real ComfyUI execution status
# - Explicit submit/wait tracing
# - Stable prompt execution lifecycle
# - No false completion reporting
# - Safe workflow debug logging
# ==========================================================


from core.render.comfy_http_runtime import ComfyHTTPRuntime
from core.render.wan_connector import WANConnector



class WorkflowExecutor:


    VERSION = "4.2"



    def __init__(self):

        self.comfy = ComfyHTTPRuntime()

        self.wan = WANConnector()


        print(
            "🚀 WORKFLOW EXECUTOR v4.2 ONLINE"
        )



    # ======================================================
    # EXECUTE WORKFLOW
    # ======================================================


    def execute(
        self,
        injected_workflow,
        engine,
        on_submitted=None,
        client_id=None
    ):


        print(
            "🔥 EXECUTOR ENGINE:",
            engine
        )



        # ==================================================
        # FLUX / COMFYUI
        # ==================================================

        if engine == "comfyui":


            print(
                "🎨 COMFYUI EXECUTION START"
            )



            # ==================================================
            # SAFE WORKFLOW DEBUG
            # ==================================================


            if isinstance(
                injected_workflow,
                dict
            ):


                print(
                    "🚨 BEFORE EXECUTOR WORKFLOW KEYS:",
                    list(
                        injected_workflow.keys()
                    )
                )


                print(
                    "🚨 WORKFLOW NODE COUNT:",
                    len(
                        injected_workflow
                    )
                )


            else:


                print(
                    "🚨 INVALID WORKFLOW TYPE:",
                    type(
                        injected_workflow
                    )
                )



            # ==================================================
            # SUBMIT
            # ==================================================


            submitted = self.comfy.submit(

                injected_workflow,

                client_id=client_id

            )


            print(
                "🔥 COMFY SUBMIT RESULT:",
                submitted
            )



            if not isinstance(
                submitted,
                dict
            ):


                return {


                    "engine":

                        "comfyui",



                    "status":

                        "submit_error",



                    "execution":

                        submitted

                }



            # ==================================================
            # TRUTHFUL SUBMIT STATUS
            #
            # A runtime that already reported an error / rejection must
            # never be downgraded into a vague "missing_prompt_id".
            # ==================================================

            submit_status = submitted.get(
                "status"
            )


            if submit_status not in (
                None,
                "submitted"
            ):


                print(
                    "❌ COMFY SUBMIT FAILED:",
                    submit_status
                )


                return {


                    "engine":

                        "comfyui",



                    "status":

                        "submit_error",



                    "execution":

                        submitted

                }



            prompt_id = submitted.get(

                "prompt_id"

            )



            print(
                "🆔 COMFY PROMPT ID:",
                prompt_id
            )



            if not prompt_id:


                return {


                    "engine":

                        "comfyui",



                    "status":

                        "missing_prompt_id",



                    "execution":

                        submitted

                }



            # ==================================================
            # WAIT RESULT
            # ==================================================


            # ==================================================
            # REAL_RENDER_LIFECYCLE_V1 — SUBMISSION CALLBACK
            #
            # The prompt id is valid here and NOTHING is blocking yet:
            # `wait_for_result()` has not started. This is the only point
            # at which a caller can be told the real ComfyUI job id
            # without waiting for the render to finish.
            #
            # Purely observational. Any exception raised inside the
            # callback is swallowed, so a progress feature can never
            # change the outcome of a render. Callers that pass nothing
            # behave exactly as before.
            # ==================================================

            if on_submitted is not None and prompt_id:

                try:

                    on_submitted(prompt_id)

                except Exception as _callback_error:

                    print(
                        "⚠️ SUBMISSION CALLBACK FAILED:",
                        type(_callback_error).__name__,
                        _callback_error
                    )


            print(
                "⏳ WAITING COMFY RESULT:",
                prompt_id
            )



            result = self.comfy.wait_for_result(

                prompt_id

            )



            print(
                "🔥 COMFY WAIT RESULT:",
                result
            )



            if isinstance(
                result,
                dict
            ):


                result["prompt_id"] = prompt_id



                execution_status = result.get(

                    "status",

                    "unknown"

                )


            else:


                execution_status = "unknown"



            print(
                "📌 FINAL EXECUTION STATUS:",
                execution_status
            )



            return {


                "engine":

                    "comfyui",



                "status":

                    execution_status,



                "prompt_id":

                    prompt_id,



                "execution":

                    result

            }





        # ==================================================
        # WAN IMAGE TO VIDEO
        # ==================================================

        if engine == "wan":



            print(
                "🎬 WAN EXECUTION PREPARED"
            )



            return {


                "engine":

                    "wan",



                "status":

                    "prepared",



                "execution":

                    {


                        "runtime":

                            "wan_runtime",



                        "workflow":

                            injected_workflow


                    }

            }





        # ==================================================
        # UNKNOWN ENGINE
        # ==================================================


        print(
            "❌ UNKNOWN EXECUTION ENGINE:",
            engine
        )



        return {


            "status":

                "unknown_engine",



            "engine":

                engine

        }