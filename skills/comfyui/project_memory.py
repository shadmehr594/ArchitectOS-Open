# ==========================================================
# ArchitectOS Render Project Memory v1
# Project based image history system
# ==========================================================

import json
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]

PROJECT_DIR = (
    BASE_DIR
    / "memory"
    / "comfy"
    / "projects"
    / "active_project"
)


VERSIONS_DIR = PROJECT_DIR / "versions"

PROJECT_FILE = PROJECT_DIR / "project.json"

HISTORY_FILE = PROJECT_DIR / "history.json"



class ProjectMemory:


    def __init__(self):

        PROJECT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        VERSIONS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )



    # ======================================================
    # CREATE / LOAD PROJECT
    # ======================================================

    def load_project(self):

        if not PROJECT_FILE.exists():

            return {

                "name": "active_project",

                "created":
                    datetime.now().isoformat(),

                "current_version":
                    None

            }


        with open(
            PROJECT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)



    def save_project(
        self,
        data
    ):

        with open(
            PROJECT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )


        return data



    # ======================================================
    # SAVE VERSION
    # ======================================================

    def save_version(
        self,
        image_path,
        prompt,
        engine,
        source=None
    ):


        project = self.load_project()


        history = self.load_history()


        version_number = len(history) + 1


        version_name = (
            f"v{version_number:03d}"
        )


        version_dir = (
            VERSIONS_DIR
            /
            version_name
        )


        version_dir.mkdir(
            parents=True,
            exist_ok=True
        )



        metadata = {

            "version":
                version_name,

            "image":
                str(image_path),

            "prompt":
                prompt,

            "engine":
                engine,

            "source":
                source,

            "created":
                datetime.now().isoformat()

        }



        with open(
            version_dir / "meta.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                metadata,
                f,
                indent=4,
                ensure_ascii=False
            )



        history.append(
            metadata
        )


        with open(
            HISTORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                history,
                f,
                indent=4,
                ensure_ascii=False
            )



        project["current_version"] = version_name


        self.save_project(
            project
        )


        return metadata



    # ======================================================
    # HISTORY
    # ======================================================

    def load_history(self):

        if not HISTORY_FILE.exists():

            return []


        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)



    def latest(self):

        history = self.load_history()


        if not history:

            return None


        return history[-1]



project_memory = ProjectMemory()