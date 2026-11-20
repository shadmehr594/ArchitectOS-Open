# ==========================================================
# ArchitectOS Comfy Runtime v8.4
# Flux + Img2Img + Wan Runtime
# Image Memory Stable Edition
# ==========================================================

from pathlib import Path
import shutil

from skills.comfyui.workflow_engine import engine
from skills.comfyui.client import send_workflow
from skills.comfyui.image_fetcher import get_image

from skills.comfyui.image_memory import memory
from skills.comfyui.project_memory import project_memory
from skills.comfyui.project_state import project_state
from skills.comfyui.image_snapshot import snapshot_manager

from core.ai.visual_critic import visual_critic


class ComfyRuntime:

    def __init__(self):

        self.engine = engine

        print(
            "🎨 Comfy Runtime v8.4 ACTIVE"
        )

    # ======================================================
    # GENERATE
    # ======================================================

    def generate(
        self,
        prompt,
        mode="image",
        source_image=None,
        params=None
    ):

        print("🎨 COMFY RUNTIME START")
        print("🖼️ MODE:", mode)

        params = params or {}

        # ==================================================
        # IMAGE
        # ==================================================

        if mode == "image":

            workflow = self.engine.build_flux_image(prompt)
            engine_name = "flux"

        # ==================================================
        # EDIT
        # ==================================================

        elif mode == "edit":

            filename = None

            if source_image:

                source_path = Path(source_image)

                if source_path.exists():

                    input_dir = Path(
                        r"C:\ComfyUI-Zluda\input"
                    )

                    input_dir.mkdir(
                        exist_ok=True
                    )

                    target = input_dir / source_path.name

                    shutil.copy(
                        source_path,
                        target
                    )

                    filename = source_path.name

                    print(
                        "📥 SOURCE:",
                        filename
                    )

            if not filename:

                filename = memory.prepare_input()

            if not filename:

                return {
                    "status": "failed",
                    "error": "No valid source image"
                }

            workflow = self.engine.build_flux_edit(
                filename,
                prompt,
                denoise=params.get(
                    "denoise",
                    0.45
                )
            )

            engine_name = "flux_img2img"

        # ==================================================
        # VIDEO
        # ==================================================

        elif mode == "video":

            workflow = self.engine.build_wan_video(
                prompt
            )

            engine_name = "wan"

        else:

            return {
                "status": "failed",
                "error": f"Unknown mode: {mode}"
            }

        # ==================================================
        # SEND
        # ==================================================

        response = send_workflow(
            workflow
        )

        if (
            not isinstance(response, dict)
            or
            "prompt_id" not in response
        ):

            return {
                "status": "failed",
                "error": response
            }

        prompt_id = response["prompt_id"]

        print(
            "🎨 PROMPT:",
            prompt_id
        )

        outputs = get_image(
            prompt_id
        )

        # ==================================================
        # NORMALIZE OUTPUT
        # ==================================================

        if isinstance(outputs, dict):

            images = outputs.get(
                "images",
                []
            )

            if images:

                first = images[0]

                filename = first.get(
                    "filename"
                )

                outputs["filename"] = filename

                outputs["subfolder"] = first.get(
                    "subfolder",
                    ""
                )

                outputs["type"] = first.get(
                    "type",
                    "output"
                )

                outputs["path"] = (
                    f"C:/ComfyUI-Zluda/output/{filename}"
                )

        result = {

            "status": "completed",

            "engine": engine_name,

            "prompt": prompt,

            "prompt_id": prompt_id,

            "outputs": outputs,

            "parameters": params

        }

        # ==================================================
        # MEMORY
        # ==================================================

        if isinstance(outputs, dict):

            if outputs.get("filename"):

                memory.save(
                    result
                )

                print(
                    "🧠 IMAGE MEMORY UPDATED"
                )

            if outputs.get("path"):

                try:

                    memory.set_last_image(
                        outputs["path"]
                    )

                    review = visual_critic.analyze(
                        outputs["path"],
                        prompt
                    )

                    result["visual_review"] = review

                    version = project_memory.save_version(
                        outputs["path"],
                        prompt,
                        engine_name,
                        None
                    )

                    snapshot = snapshot_manager.save(
                        outputs["path"],
                        version["version"]
                    )

                    version["snapshot"] = snapshot

                    project_state.update(
                        version
                    )

                    print(
                        "📚 PROJECT VERSION:",
                        version["version"]
                    )

                except Exception as e:

                    print(
                        "⚠️ MEMORY ERROR:",
                        e
                    )

        return {

            "status": "completed",

            "engine": engine_name,

            "prompt": prompt,

            "prompt_id": prompt_id,

            "result": outputs,

            "outputs": outputs,

            "parameters": params,

            "visual_review": result.get(
                "visual_review"
            )

        }