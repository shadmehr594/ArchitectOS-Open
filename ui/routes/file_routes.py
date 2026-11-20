from flask import Blueprint, request, jsonify
import requests

# PROJECT_WORKSPACE_UI_06 — single source of truth for the Core API URL.
from config import runtime_config as RC


file_api = Blueprint(
    "file_api",
    __name__
)


CORE_FILE_API = RC.CORE_API_URL.rstrip("/") + "/file"


@file_api.route(
    "/api/file",
    methods=["POST"]
)
def file_proxy():

    try:

        uploaded_file = request.files.get(
            "file"
        )


        if not uploaded_file:

            return jsonify({

                "status":"error",
                "message":"No file received"

            }),400



        files = {

            "file":
            (
                uploaded_file.filename,
                uploaded_file.stream,
                uploaded_file.content_type
            )

        }



        response = requests.post(

            CORE_FILE_API,

            files=files,

            timeout=10800

        )


        try:

            payload = response.json()

        except Exception:

            payload = {

                "status":"error",
                "raw":response.text

            }



        return jsonify(payload)



    except Exception as e:


        return jsonify({

            "status":"error",
            "message":str(e)

        }),500