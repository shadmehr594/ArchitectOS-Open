# ==========================================================
# ArchitectOS Image Response Adapter v1
# Render Result -> Chat/UI Contract
# ==========================================================


from core.chat.chat_attachment import chat_attachment_service


class ImageResponseAdapter:


    VERSION = "v1"


    def __init__(self):

        print(
            "🖼️ IMAGE RESPONSE ADAPTER v1 ONLINE"
        )


        self.output_prefix = (
            "C:/ComfyUI-Zluda/output"
        )


        self.attachment_service = chat_attachment_service



    def adapt(
        self,
        render_result
    ):


        if not isinstance(
            render_result,
            dict
        ):

            return {

                "type":
                    "image",

                "status":
                    "error",

                "error":
                    "invalid_render_result"

            }



        if render_result.get(
            "status"
        ) != "success":


            return render_result



        image = (

            render_result.get(
                "image"
            )

            or

            render_result.get(
                "render",
                {}
            )
            .get(
                "image"
            )

        )


        if not image:


            return render_result



        filename = image.get(
            "filename"
        )


        if not filename:

            return {

                "type":
                    "image",

                "status":
                    "error",

                "error":
                    "missing_filename"

            }



        attachment = image.get(
            "attachment"
        )


        if not isinstance(attachment, dict):

            attachment = self.attachment_service.from_comfy_output(
                image
            )


        if not attachment:

            return {
                "type": "image",
                "status": "chat_artifact_exposure_failure",
                "render_status": "success",
                "error": "render_output_missing_or_outside_approved_root",
                "attachments": []
            }


        public_attachment = self.attachment_service.public_attachment(
            attachment
        )


        response = {


            "type":
                "image",


            "status":
                "success",


            "engine":
                "render_runtime",


            "prompt_id":
                render_result.get(
                    "prompt_id"
                ),


            "image":
                {


                    "filename":
                        filename,


                    "url":
                        public_attachment["url"],


                    "exists":
                        True

                },


            "attachments":
                [public_attachment]

        }


        # ==================================================
        # RENDER_INTENT_RELIABILITY_V1 — DESIGN-FIDELITY PASS-THROUGH
        #
        # The image handler computes `design_fidelity` on the render result
        # (requested / executed / observed, floor and building-type status,
        # `design_accepted`), but this adapter builds a NEW dict and copied
        # only the keys listed above, so a successful image turn silently
        # dropped the whole contract. The caller could not tell a verified
        # design from an UNVERIFIED one.
        #
        # Additive pass-through only: the value is copied verbatim and is
        # never re-derived, re-graded or upgraded. An UNVERIFIED observation
        # stays UNVERIFIED.
        # ==================================================

        if isinstance(render_result.get("design_fidelity"), dict):

            response["design_fidelity"] = render_result["design_fidelity"]

        # ARCHITECTURAL_VISION_RUNTIME_COMPLETION_V1 — the provenance of the
        # observation itself (which image, which provider/model, and why it
        # was unavailable when it was). Without this a caller cannot tell an
        # unobserved UNVERIFIED from a genuinely inconclusive one.
        if isinstance(render_result.get("design_observation"), dict):

            response["design_observation"] = render_result["design_observation"]


        return response
