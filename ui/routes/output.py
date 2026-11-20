# ==========================================================
# ArchitectOS Output Image Proxy
# Serve ComfyUI Render Results
# ==========================================================


from flask import Blueprint, send_from_directory


output_api = Blueprint(
    "output_api",
    __name__
)


OUTPUT_FOLDER = (
    "C:/ComfyUI-Zluda/output"
)



@output_api.route(
    "/output/<filename>"
)
def serve_output(filename):


    return send_from_directory(

        OUTPUT_FOLDER,

        filename

    )