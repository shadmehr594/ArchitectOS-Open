# ==========================================================
# ArchitectOS Response Contract v1
# Unified Output Schema
# ==========================================================


class ResponseContract:


    VERSION = "v1"



    def build(
        self,
        response_type,
        engine,
        result,
        status="success"
    ):


        return {


            "type":
                response_type,


            "engine":
                engine,


            "result":
                result,


            "status":
                status

        }



    def success(
        self,
        engine,
        result,
        response_type="chat"
    ):


        return self.build(

            response_type,

            engine,

            result,

            "success"

        )



    def error(
        self,
        engine,
        message
    ):


        return self.build(

            "error",

            engine,

            message,

            "failed"

        )



# ==========================================================
# SINGLETON
# ==========================================================


response_contract = ResponseContract()


# ==========================================================
# CHAT_ENVELOPE_STATUS_TRUTH_V1
#
# The Core API's chat envelope carries a TOP-LEVEL `status`, and the UI
# branches on it (`ui/static/app.js: if (payload.status === "error")`). That
# value used to be the constant "success", so a turn whose own response
# status was "error" — a rejected image upload, a failed dispatch — reached
# the UI as a success. The UI then took its success branch and printed
# `response.message`, which for a rejected upload is a success-sounding
# sentence. The failure branch could never fire.
#
# Only "error" is promoted. "waiting_for_instruction" is a normal
# interactive state, and "degraded" is a truthful apology that is still a
# delivered answer, so both keep the existing top-level treatment.
# ==========================================================

# T2I_FIRST_PRODUCT_VERTICAL_SLICE_V1 — a render that produced NO image is a
# failed operation, not a success.
#
# `render_runtime` reports "completed_no_image" when ComfyUI returned no
# output, and "submit_error" / "execution_error" when the submission or the
# sampler failed. `envelope_status_for()` promoted only the literal "error",
# so those turns reached the UI as `status: "success"` with no image: the
# client's failure branch (app.js: `payload.status === "error"`) could never
# fire, and any caller trusting the envelope believed a generation happened.
#
# This is the SAME terminal-failure vocabulary `chat_architect` already uses
# to decide that a render did not succeed, reused rather than re-invented.
# Interactive states (`waiting_for_instruction`, `degraded`) are NOT included
# and keep their existing treatment.
_TERMINAL_FAILURE_STATUSES = frozenset((
    "error",
    "completed_no_image",
    "submit_error",
    "execution_error",
))


def envelope_status_for(formatted_response):
    """Top-level envelope status for a chat turn: the OPERATION outcome."""

    status = ""

    if isinstance(formatted_response, dict):

        status = str(
            formatted_response.get("status") or ""
        ).strip().lower()

    return "error" if status in _TERMINAL_FAILURE_STATUSES else "success"