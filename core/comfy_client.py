import requests
import json
import uuid
import os


class ComfyClient:

    def __init__(self):
        self.url = "http://127.0.0.1:8188/prompt"

    # --------------------------
    # LOAD WORKFLOW
    # --------------------------
    def load_workflow(self, path):

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # --------------------------
    # INJECT PROMPT
    # --------------------------
    def inject_prompt(self, workflow, prompt):

        for node_id in workflow:

            node = workflow[node_id]

            if "inputs" in node:

                # common ComfyUI node key
                if "text" in node["inputs"]:
                    node["inputs"]["text"] = prompt

                if "prompt" in node["inputs"]:
                    node["inputs"]["prompt"] = prompt

        return workflow

    # --------------------------
    # GENERATE IMAGE
    # --------------------------
    def generate(self, workflow_path, prompt):

        workflow = self.load_workflow(workflow_path)

        workflow = self.inject_prompt(workflow, prompt)

        payload = {
            "prompt": workflow,
            "client_id": str(uuid.uuid4())
        }

        try:
            r = requests.post(self.url, json=payload)

            if r.status_code != 200:
                print("[COMFY ERROR]", r.text)
                return None

            # ComfyUI returns prompt id
            result = r.json()

            prompt_id = result.get("prompt_id")

            if not prompt_id:
                return None

            # NOTE: real implementation would poll /history
            return f"{prompt_id}.png"

        except Exception as e:
            print("[COMFY CLIENT ERROR]", e)
            return None