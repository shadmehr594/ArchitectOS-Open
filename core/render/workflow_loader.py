# ==========================================================
# ArchitectOS Workflow Loader v1
# ComfyUI / WAN Workflow Manager
# ==========================================================


import os
import json



class WorkflowLoader:


    VERSION = "1.0"



    def __init__(
        self,
        base_path=None
    ):


        if base_path:

            self.base_path = base_path


        else:

            current_dir = os.path.dirname(
                os.path.abspath(__file__)
            )

            self.base_path = os.path.join(
                current_dir,
                "workflows"
            )



        print(
            "📂 WORKFLOW PATH:",
            self.base_path
        )


        print(
            "📦 WORKFLOW LOADER v1 ONLINE"
        )



    # ======================================================
    # LOAD WORKFLOW
    # ======================================================


    def load(
        self,
        name
    ):


        path = os.path.join(
            self.base_path,
            name
        )


        print(
            "🔎 LOAD WORKFLOW:",
            name
        )


        print(
            "📄 CHECK PATH:",
            path
        )



        if not os.path.exists(path):

            return {

                "status":
                    "error",

                "message":
                    "workflow_not_found",

                "path":
                    path

            }



        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:


            data = json.load(f)



        return {

            "status":
                "loaded",

            "name":
                name,

            "workflow":
                data

        }



    # ======================================================
    # AVAILABLE
    # ======================================================


    def available(self):


        if not os.path.exists(
            self.base_path
        ):

            return []



        return os.listdir(
            self.base_path
        )