# ==========================================================
# ArchitectOS Render Project State v1
# Tracks current design state
# ==========================================================

import json
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]

STATE_DIR = BASE_DIR / "memory" / "project"

STATE_FILE = STATE_DIR / "project_state.json"



class ProjectState:


    def __init__(self):

        STATE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )



    # =====================================
    # UPDATE CURRENT STATE
    # =====================================

    def update(
        self,
        version
    ):


        state = {

            "project_name":
                "ArchitectOS Render Project",

            "current_version":
                version.get("version"),

            "image":
                version.get("image"),

            "prompt":
                version.get("prompt"),

            "engine":
                version.get("engine"),

            "source":
                version.get("source"),

            "updated":
                datetime.now().isoformat()

        }


        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                state,
                f,
                indent=4,
                ensure_ascii=False
            )


        return state



    # =====================================
    # LOAD STATE
    # =====================================

    def load(self):


        if not STATE_FILE.exists():

            return None


        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:


            return json.load(f)



    # =====================================
    # EXISTS
    # =====================================

    def exists(self):

        return STATE_FILE.exists()



project_state = ProjectState()