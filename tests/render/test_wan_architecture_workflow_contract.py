import json
from pathlib import Path

from core.render.image_workflow_injector import ImageWorkflowInjector
from core.render.workflow_selector import WorkflowSelector
from core.render.comfy_http_runtime import ComfyHTTPRuntime


WORKFLOW = Path(__file__).parents[2] / "core" / "render" / "workflows" / "wan_i2v.json"


def test_wan_architecture_workflow_is_real_image_to_mp4():
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    classes = {node["class_type"] for node in workflow.values()}
    assert {"LoadImage", "WanImageToVideo", "CreateVideo", "SaveVideo"} <= classes
    assert "EmptyHunyuanLatentVideo" not in classes
    save = next(node for node in workflow.values() if node["class_type"] == "SaveVideo")
    assert save["inputs"]["format"] == "mp4"
    assert save["inputs"]["codec"] == "h264"


def test_wan_selector_and_image_injection_use_approved_render():
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    asset = {"filename": "approved_facade.png"}
    assert WorkflowSelector().select({"engine": "wan", "mode": "i2v", "image": asset}) == "wan_i2v.json"
    injected = ImageWorkflowInjector().inject(workflow, "slow facade camera dolly", asset)["workflow"]
    load = next(node for node in injected.values() if node["class_type"] == "LoadImage")
    assert load["inputs"]["image"] == "approved_facade.png"
    positive = injected["6"]["inputs"]["text"]
    assert positive == "slow facade camera dolly"


def test_comfy_runtime_recognizes_saved_video_as_completed_media():
    runtime = ComfyHTTPRuntime()
    history = {"prompt": {"outputs": {"52": {"videos": [{
        "filename": "architecture_wan_00001.mp4",
        "subfolder": "ArchitectOS",
        "type": "output",
    }]}}}}
    videos = runtime.extract_videos(history)
    assert videos[0]["filename"] == "architecture_wan_00001.mp4"
    assert videos[0]["format"] == "mp4"
