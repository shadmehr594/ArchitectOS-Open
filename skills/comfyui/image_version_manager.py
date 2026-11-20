# ==========================================================
# ArchitectOS Image Version Manager v2
# Immutable Render History
# ==========================================================

from pathlib import Path
import shutil
import json
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[2]


HISTORY_DIR = (
    BASE_DIR
    /
    "memory"
    /
    "comfy"
    /
    "history"
)



class ImageVersionManager:


    def __init__(self):

        HISTORY_DIR.mkdir(
            parents=True,
            exist_ok=True
        )



    # =====================================
    # CREATE IMMUTABLE VERSION
    # =====================================

    def save_version(
        self,
        image_path,
        prompt,
        engine
    ):


        versions = list(
            HISTORY_DIR.glob("v*")
        )


        version_number = len(versions) + 1


        version_name = (
            f"v{version_number:03d}"
        )


        version_dir = (
            HISTORY_DIR
            /
            version_name
        )


        version_dir.mkdir(
            exist_ok=True
        )


        source = Path(
            image_path
        )


        target = (
            version_dir
            /
            f"render_{version_name}.png"
        )


        shutil.copy2(
            source,
            target
        )



        meta = {

            "version":
                version_name,

            "image":
                str(target),

            "original":
                str(source),

            "prompt":
                prompt,

            "engine":
                engine,

            "created":
                datetime.now().isoformat()

        }



        with open(
            version_dir / "meta.json",
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                meta,
                f,
                indent=4,
                ensure_ascii=False
            )



        return meta




version_manager = ImageVersionManager()