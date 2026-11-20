# ==========================================================
# ArchitectOS Image Memory v3.1
# Latest Image Registry + ComfyUI Input Manager
# ==========================================================

import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

MEMORY_DIR = BASE_DIR / "memory" / "comfy"
MEMORY_FILE = MEMORY_DIR / "last_image.json"

COMFY_INPUT = Path(r"C:\ComfyUI-Zluda\input")


class ImageMemory:

    def __init__(self):

        MEMORY_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        COMFY_INPUT.mkdir(
            parents=True,
            exist_ok=True
        )

    # ======================================================
    # SAVE FULL RESULT
    # ======================================================

    def save(self, data):

        if not isinstance(data, dict):
            data = {}

        outputs = data.get("outputs", {})

        if outputs.get("path"):
            data["last_image"] = outputs["path"]

            print(
                "📷 MEMORY LAST IMAGE:",
                outputs["path"]
            )


        with open(
            MEMORY_FILE,
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
    # LOAD
    # ======================================================

    def load(self):

        if not MEMORY_FILE.exists():
            return None

        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    # ======================================================
    # SET LAST IMAGE
    # ======================================================

    def set_last_image(self, image_path):

        data = self.load()

        if data is None:
            data = {}

        data["last_image"] = image_path

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

        print(
            "📷 SOURCE IMAGE REGISTERED:",
            image_path
        )

    # ======================================================
    # GET LAST IMAGE
    # ======================================================

    def get_last_image(self):

        data = self.load()

        if not data:
            return None

        image = data.get("last_image")

        if image and Path(image).exists():
            return image

        outputs = data.get("outputs", {})

        path = outputs.get("path")

        if path and Path(path).exists():
            return path

        return None

    # ======================================================
    # PREPARE INPUT
    # ======================================================

    def prepare_input(self):

        image_path = self.get_last_image()

        if not image_path:
            return None

        source = Path(image_path)

        if not source.exists():
            return None

        filename = source.name

        target = COMFY_INPUT / filename

        shutil.copy2(
            source,
            target
        )

        print(
            "📥 IMAGE COPIED TO COMFY INPUT:",
            filename
        )

        return filename


memory = ImageMemory()