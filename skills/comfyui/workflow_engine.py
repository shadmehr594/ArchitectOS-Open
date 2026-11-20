# ==========================================================
# ArchitectOS ComfyUI Workflow Engine v5
# Flux + Img2Img + Wan Support
# Architectural Balance Edition
# ==========================================================


import json
import random

from pathlib import Path



BASE_DIR = Path(__file__).resolve().parents[2]

WORKFLOW_DIR = BASE_DIR / "core" / "render" / "workflows"



class WorkflowEngine:


    def __init__(self):

        self.workflow_dir = WORKFLOW_DIR



    def load(
        self,
        filename: str
    ):


        path = self.workflow_dir / filename


        if not path.exists():

            raise FileNotFoundError(
                f"Workflow not found: {path}"
            )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)



    # ======================================================
    # FLUX T2I
    # ======================================================

    def build_flux_image(
        self,
        prompt: str
    ):


        workflow = self.load(
            "flux.json"
        )


        workflow["206"]["inputs"]["text"] = prompt


        workflow["210"]["inputs"]["seed"] = random.randint(
            1,
            999999999999999
        )


        return workflow



    # ======================================================
    # FLUX IMG2IMG ARCHITECTURAL
    # ======================================================

    def build_flux_edit(
        self,
        image_name: str,
        prompt: str,
        denoise: float = 0.45
    ):


        workflow = self.load(
            "flux_img2img.json"
        )



        # source image

        workflow["300"]["inputs"]["image"] = image_name



        # prompt

        workflow["206"]["inputs"]["text"] = prompt



        # sampling control

        sampler = workflow["210"]["inputs"]


        sampler["seed"] = random.randint(
            1,
            999999999999999
        )


        # balanced architecture edit

        sampler["steps"] = 20

        sampler["cfg"] = 3.0

        sampler["denoise"] = denoise



        return workflow



    # ======================================================
    # WAN VIDEO
    # ======================================================

    def build_wan_video(
        self,
        prompt: str
    ):


        workflow = self.load(
            "wan_i2v.json"
        )


        if "6" in workflow:

            workflow["6"]["inputs"]["text"] = prompt


        return workflow



    def available_workflows(
        self
    ):


        if not self.workflow_dir.exists():

            return []


        return sorted(
            [
                f.name
                for f in self.workflow_dir.glob("*.json")
            ]
        )



engine = WorkflowEngine()