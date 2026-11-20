# ==========================================================
# ArchitectOS Image Fetcher v2
# Reads Comfy History correctly
# ==========================================================

import time
from pathlib import Path

import requests


COMFY_URL = "http://127.0.0.1:8188"

OUTPUT_DIR = Path(
    r"C:\ComfyUI-Zluda\output"
)


def get_image(prompt_id, timeout=10800):

    print(
        "🖼️ WAITING COMFY RESULT:",
        prompt_id
    )

    history_url = (
        f"{COMFY_URL}/history/{prompt_id}"
    )

    if timeout is None:
        timeout=10800

    start = time.time()
    
    while time.time() - start < timeout:

        try:

            data = requests.get(
                history_url,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            if str(prompt_id) in data:

                result = data[str(prompt_id)]

                status = result.get(
                    "status",
                    {}
                )

                if status.get(
                    "completed"
                ):

                    print(
                        "✅ COMFY EXECUTION COMPLETE"
                    )

                    outputs = result.get(
                        "outputs",
                        {}
                    )

                    # -----------------------------------
                    # Read every SaveImage node
                    # -----------------------------------

                    for node in outputs.values():

                        images = node.get(
                            "images",
                            []
                        )

                        if not images:
                            continue

                        image = images[0]

                        filename = image["filename"]

                        subfolder = image.get(
                            "subfolder",
                            ""
                        )

                        image_path = (
                            OUTPUT_DIR /
                            subfolder /
                            filename
                        )

                        print(
                            "🖼️ HISTORY IMAGE:",
                            filename
                        )

                        return {

                            "filename": filename,

                            "path": str(image_path),

                            "url":
                                    f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output",

                            "images": [
                                {
                                    "filename": filename,
                                    "subfolder": subfolder,
                                    "type": "output"
                                }
                            ]
                        }

                    print(
                        "⚠️ History contains no SaveImage output."
                    )

                    break

        except Exception as e:

            print(
                "History error:",
                e
            )

        time.sleep(2)

    # =====================================================
    # FALLBACK
    # =====================================================

    print(
        "🔎 Searching latest PNG..."
    )

    images = sorted(
        OUTPUT_DIR.glob("*.png"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if images:

        latest = images[0]

        print(
            "🖼️ FALLBACK IMAGE:",
            latest.name
        )

        return {

            "filename":
                latest.name,

            "path":
                str(latest),

            "url":
                f"{COMFY_URL}/view?filename={latest.name}&type=output",

            "images": [
                {
                    "filename": latest.name,
                    "subfolder": "",
                    "type": "output"
                }
            ]
        }

    return {

        "error":
            "image file not found",

        "prompt_id":
            prompt_id

    }