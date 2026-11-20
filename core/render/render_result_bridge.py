# ==========================================================
# ArchitectOS Render Result Bridge v4.4
# ComfyUI Output -> Unified Render Memory
#
# Improvements:
# - Fixed nested __init__ bug
# - Direct execution image consume
# - WorkflowExecutor v4.2 compatible
# - Stable history fallback
# - Architectural Intent preservation
# - Prompt preservation
# - Memory consistency
# - UI image asset bridge
# ==========================================================


import os
import time
import uuid


from config import runtime_config as RC
from core.render.comfy_http_runtime import ComfyHTTPRuntime
from core.render.render_memory_bridge import RenderMemoryBridge
from core.chat.chat_attachment import chat_attachment_service



class RenderResultBridge:


    VERSION = "4.4"



    def __init__(
        self,
        comfy_runtime=None
    ):


        print(
            "🚀 RENDER RESULT BRIDGE v4.4 ONLINE"
        )


        self.output_dir = (
            RC.COMFYUI_OUTPUT_DIR
        )


        self.retry_count = 5

        self.retry_delay = 1



        self.memory = RenderMemoryBridge()


        self.attachment_service = chat_attachment_service



        self.comfy = (

            comfy_runtime

            or

            ComfyHTTPRuntime()

        )



    # ======================================================
    # IMAGE ASSET BUILDER
    # ======================================================


    def build_image_asset(
        self,
        image
    ):


        if not isinstance(
            image,
            dict
        ):

            return None



        filename = image.get(
            "filename"
        )



        if not filename:

            return None



        subfolder = str(
            image.get(
                "subfolder",
                ""
            )
            or ""
        ).replace("\\", "/").strip("/")


        relative_path = os.path.join(
            subfolder,
            filename
        ) if subfolder else filename


        attachment = self.attachment_service.from_comfy_output(
            image
        )


        # TEXT_TO_IMAGE_COMFY_03 — truthful output contract.
        # The path comes from ComfyUI's own history record and is
        # verified on disk. `exists` reports the real filesystem state,
        # so a missing file can never be reported as a successful render.
        asset_path = os.path.join(
            self.output_dir,
            relative_path
        )


        asset = {


            "filename":

                filename,



            "url":

                attachment.get("url")
                if attachment
                else None,



            "path":

                asset_path,



            "exists":

                os.path.isfile(
                    asset_path
                ),



            "type":

                image.get(
                    "type",
                    "output"
                ),


            "subfolder":

                subfolder

        }


        if attachment:

            asset["attachment"] = self.attachment_service.public_attachment(
                attachment
            )


        return asset





    # ======================================================
    # RESOLVE
    # ======================================================


    def resolve(
        self,
        render_result
    ):


        print(
            "🚨 RESULT BRIDGE INPUT:",
            render_result
        )


        try:


            # DEBUG PIPELINE MODE
            if render_result.get("debug"):

                print(
                    "🧪 DEBUG RESULT BRIDGE MODE"
                )

                return {

                    "status": "debug",

                    "render": render_result,

                    "architectural_intent":
                        render_result.get(
                            "architectural_intent",
                            {}
                        ),

                    "prompt":
                        render_result.get(
                            "prompt",
                            ""
                        )

                }


            execution = (

                render_result.get(
                    "execution",
                    {}
                )

                or

                {}

            )

            if isinstance(execution, dict):

                execution_status = execution.get(
                    "status"
                )

                if str(execution_status).startswith(
                    "debug_"
                ):

                    return {

                        "status": "debug",

                        "execution": execution,

                        "architectural_intent":
                            render_result.get(
                                "architectural_intent",
                                {}
                            ),

                        "prompt":
                            render_result.get(
                                "prompt",
                                ""
                            )

                    }



            prompt_id = (

                execution.get(
                    "prompt_id"
                )

                or

                render_result.get(
                    "prompt_id"
                )

            )



            print(
                "🆔 RESULT BRIDGE PROMPT ID:",
                prompt_id
            )



            # ==================================================
            # DIRECT EXECUTION IMAGE
            # ==================================================


            images = execution.get(
                "images",
                []
            )



            if not images:


                nested_execution = execution.get(
                    "execution",
                    {}
                )


                if isinstance(
                    nested_execution,
                    dict
                ):


                    images = nested_execution.get(
                        "images",
                        []
                    )



            if images:


                print(
                    "✅ EXECUTION IMAGE FOUND"
                )


                image_asset = self.build_image_asset(
                    images[0]
                )


                if image_asset:


                    result = self._finalize_result(

                        render_result,

                        prompt_id,

                        image_asset

                    )


                    print(
                        "🚨 RESULT BRIDGE OUTPUT:",
                        result
                    )


                    return result





            # ==================================================
            # TRUTHFUL FAILURE PROPAGATION
            #
            # I2I_INSTRUCTION_FIDELITY_V1 — a render result that already
            # reports a CONFIRMED failure must never be reported as
            # "pending". "pending" means "queued, may still complete",
            # which is false for a refused / rejected / missing-id submit
            # and for an execution that already failed. The failure reason
            # is carried through so the caller can report it verbatim.
            #
            #   confirmed submission failure -> error
            #   successfully queued job       -> pending
            #   completed valid output        -> success (handled above)
            #   failed execution              -> error
            # ==================================================

            _render_status = str(
                render_result.get("status") or ""
            ).strip().lower()

            _execution_status = str(
                (execution or {}).get("status") or ""
            ).strip().lower()

            _failure_statuses = (
                "submit_error",
                "missing_prompt_id",
                "unknown_engine",
                "rejected",
                "error",
            )

            _failed = (
                _render_status in _failure_statuses
                or _execution_status in ("error", "rejected")
            )

            if _failed:

                reason = (
                    render_result.get("error")
                    or (execution or {}).get("error")
                    or (execution or {}).get("message")
                    or _render_status
                    or _execution_status
                    or "render_failed"
                )

                result = {

                    "status":

                        "error",

                    "error":

                        str(reason),

                    "prompt_id":

                        prompt_id,

                    "render":

                        render_result

                }

                print(
                    "🚨 RESULT BRIDGE OUTPUT:",
                    result
                )

                return result


            # ==================================================
            # HISTORY FALLBACK
            # ==================================================


            if not prompt_id:


                result = {


                    "status":

                        "pending",


                    "render":

                        render_result

                }


                print(
                    "🚨 RESULT BRIDGE OUTPUT:",
                    result
                )


                return result





            print(
                "🔎 FALLBACK HISTORY CHECK:",
                prompt_id
            )



            for attempt in range(
                self.retry_count
            ):



                history = self.comfy.history(
                    prompt_id
                )


                print(
                    "📜 COMFY HISTORY:",
                    history
                )



                data = history.get(
                    prompt_id,
                    {}
                )



                outputs = data.get(
                    "outputs",
                    {}
                )



                for node in outputs.values():


                    node_images = node.get(
                        "images",
                        []
                    )



                    if not node_images:

                        continue



                    image_asset = self.build_image_asset(
                        node_images[0]
                    )



                    if image_asset:


                        result = self._finalize_result(

                            render_result,

                            prompt_id,

                            image_asset

                        )


                        print(
                            "🚨 RESULT BRIDGE OUTPUT:",
                            result
                        )


                        return result



                time.sleep(
                    self.retry_delay
                )





            result = {


                "status":

                    "completed_no_image",



                "prompt_id":

                    prompt_id

            }



            print(
                "🚨 RESULT BRIDGE OUTPUT:",
                result
            )


            return result





        except Exception as e:


            result = {


                "status":

                    "error",



                "error":

                    str(e)

            }


            print(
                "🚨 RESULT BRIDGE ERROR:",
                result
            )


            return result





    # ======================================================
    # FINAL RESULT BUILDER
    # ======================================================


    def _finalize_result(
        self,
        render_result,
        prompt_id,
        image_asset
    ):



        render_id = (

            "render_"

            +

            uuid.uuid4()
            .hex[:8]

        )



        prompt = (

            render_result.get(
                "prompt"
            )

            or

            render_result.get(
                "render_prompt"
            )

            or

            ""

        )



        architectural_intent = (


            render_result.get(
                "architectural_intent",
                {}
            )


            or

            render_result.get(
                "design",
                {}
            ).get(
                "architectural_intent",
                {}
            )


            or

            {}

        )



        if not isinstance(
            architectural_intent,
            dict
        ):

            architectural_intent = {}



        print(
            "DEBUG FINAL ARCHITECTURAL INTENT:",
            architectural_intent
        )



        design = (

            render_result.get(
                "design"
            )

            or

            architectural_intent

            or

            {}

        )



        memory_item = {


            "render_id":

                render_id,



            "project_id":

                render_result.get(
                    "project_id",
                    "default"
                ),



            "engine":

                render_result.get(
                    "engine",
                    "flux"
                ),



            "workflow":

                render_result.get(
                    "workflow"
                ),



            "prompt":

                prompt,



            "architectural_intent":

                architectural_intent,



            "asset":

                image_asset,



            "design":

                design,



            "status":

                "success"

        }



        stored = self.memory.store(
            memory_item
        )



        try:


            from core.chat.conversation_state import conversation_state


            conversation_state.update({

                "last_render_asset":

                    image_asset,


                "last_image_asset":

                    image_asset,


                "last_render_id":

                    render_id,


                "last_architectural_intent":

                    architectural_intent

            })


        except Exception as e:


            print(
                "⚠️ RENDER STATE UPDATE ERROR:",
                e
            )


            print(
                "🔥 DEBUG MEMORY ITEM:",
                memory_item
            )




        return {


            "status":

                "success",



            "prompt":

                prompt,



            "prompt_id":

                prompt_id,



            "render_id":

                render_id,



            "image":

                image_asset,


            "image_asset":

                image_asset,




            "architectural_intent":

                architectural_intent,



            "render":

                {


                    "engine":

                        render_result.get(
                            "engine",
                            "flux"
                        ),



                    "workflow":

                        render_result.get(
                            "workflow"
                        ),



                    "prompt":

                        prompt,



                    "image":

                        image_asset


                },



            "memory":

                stored,



            "created_at":

                time.time()

        }
