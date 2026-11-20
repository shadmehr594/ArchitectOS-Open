import requests

COMFY_URL = "http://127.0.0.1:8188"


def send_workflow(workflow):

    response = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow},
        timeout=10800
    )

    data = response.json()

    if "prompt_id" not in data:
        return {"error": "No prompt_id returned", "raw": data}

    return data