# -*- coding: utf-8 -*-
"""I2I_CAPABILITY_GATE_REPAIR_V1 — CPU-only regression.

The live refusal on 2026-11-03 20:53:18 was:

    ⛔ UNSUPPORTED GEOMETRY EDIT (pre-routing guard):
       floor_count_restructuring_not_supported

19 ms after a real 1792x2400 JPEG upload, with no render attempted. These tests
pin the repair at the real decision boundary (`detect_unsupported_geometry_edit`
and `is_floor_restructuring_edit`) and prove the I2I route is still selected.

No GPU, no ComfyUI POST, no model inference, no image generation.
"""

import os
from copy import deepcopy

import pytest
from PIL import Image

from core.cognition.architectural_render_instruction_v1 import build_render_instruction
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_intent_v1 import (
    detect_unsupported_geometry_edit,
    is_floor_restructuring_edit,
)

# The exact turn that was refused, from the project transcript.
USER_EDIT = (
    "Edit the attached building photo.\r\n\r\nPreserve exactly:\r\n"
    "- building massing\r\n- floor count\r\n- structural frame\r\n"
    "- openings and window positions\r\n- camera angle and perspective\r\n"
    "- site layout and composition\r\n\r\n"
    "Do not add floors, remove floors, or change the geometry.\r\n\r\n"
    "Only change the exterior facade treatment:\r\n"
    "convert the unfinished facade into a clean finished facade with light "
    "cream travertine-style cladding and a realistic completed architectural "
    "appearance.\r\n\r\nKeep the building as the same building.\r\n"
    "Photorealistic result."
)

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "tmp", "i2i_capture", "source_building.png"
)


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine, "prompt_id": None}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


@pytest.fixture(scope="module")
def source_image():
    path = os.path.abspath(FIXTURE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        Image.new("RGB", (576, 960), (120, 120, 120)).save(path)
    return path


def _capture(image_asset, kontext=False):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()
    runtime.render(
        "i2i-gate-v1",
        {
            "prompt": USER_EDIT,
            "original_prompt": USER_EDIT,
            "compiled_render_prompt": (
                "Refine the existing facade. Replace the facade treatment with "
                "cream travertine cladding while keeping the building."
            ),
            "mode": "img2img",
            "seed": 1793714778,
        },
        "flux",
        image_asset=image_asset,
        kontext_edit=kontext,
    )
    assert executor.workflows
    return executor.workflows[0]


# ---------------------------------------------------------------- 1

def test_1_conceptual_facade_edit_is_no_longer_refused():
    """The exact refused turn must now pass the capability gate."""

    guard = detect_unsupported_geometry_edit(USER_EDIT)

    assert guard["unsupported"] is False, guard.get("reason")
    assert is_floor_restructuring_edit(USER_EDIT) is False


def test_1b_conceptual_edit_routes_to_img2img(source_image):
    selector = WorkflowSelector()

    assert selector.select(
        {"engine": "flux", "mode": "img2img", "image": "x.png"}
    ) == "flux_img2img.json"


# ---------------------------------------------------------------- 2

def test_2_preservation_constraints_reach_node_206(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})
    positive = workflow["206"]["inputs"]["text"].lower()

    assert "geometry preservation" in positive
    assert "preserve exactly" in positive
    assert "floor count" in positive
    assert "camera angle" in positive


# ---------------------------------------------------------------- 3

def test_3_exact_preservation_is_not_advertised_as_guaranteed():
    """The instruction may ask for preservation; it must not promise it."""

    instruction = build_render_instruction(USER_EDIT, mode="img2img")
    text = str(instruction.get("english_instruction") or "").lower()

    for overclaim in ("guarantee", "guaranteed", "will preserve exactly",
                      "exactly preserved"):
        assert overclaim not in text


# ---------------------------------------------------------------- 4 / 5

def test_4_explicit_attachment_is_passed_as_the_source(source_image):
    """`_route_image_edit` supplies the selected record's path, so the
    handler's `last_image_asset` fallback is never reached for this turn."""

    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    assert workflow["300"]["inputs"]["image"] == os.path.basename(source_image)


def test_5_no_source_leaves_the_placeholder_and_selects_nothing():
    workflow = _capture(None)

    # Nothing unrelated is substituted.
    assert workflow["300"]["inputs"]["image"] == "input.png"


# ---------------------------------------------------------------- 6

def test_6_no_mask_overwrites_the_source_loader(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})
    types = [n.get("class_type") for n in workflow.values()]

    assert "LoadImageMask" not in types
    assert "ImageCompositeMasked" not in types
    assert workflow["300"]["inputs"]["image"] != "input.png"


# ---------------------------------------------------------------- 7

def test_7_kontext_not_opted_in_still_selects_img2img():
    selector = WorkflowSelector()

    assert selector.select(
        {"engine": "flux", "image": "x.png", "kontext_edit": False}
    ) == "flux_img2img.json"
    assert selector.select(
        {"engine": "flux", "image": "x.png", "kontext_edit": True}
    ) == "flux_kontext_edit.json"


# ---------------------------------------------------------------- 8

def test_8_text_to_image_is_unchanged():
    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "text_to_image"}) == "flux.json"


# ---------------------------------------------------------------- 9

@pytest.mark.parametrize(
    "text,reason",
    [
        ("add two floors", "floor_count_restructuring_not_supported"),
        ("change the floor count to 5", "floor_count_restructuring_not_supported"),
        ("move this window 80 cm to the right", "dimensioned_geometry_edit_not_supported"),
        ("remove the balcony railing", "localized_geometry_edit_not_supported"),
        ("این پنجره رو 80 سانت ببر راست", "dimensioned_geometry_edit_not_supported"),
        ("این پنجره رو حذف کن", "localized_geometry_edit_not_supported"),
    ],
)
def test_9_genuine_geometry_edits_remain_restricted(text, reason):
    guard = detect_unsupported_geometry_edit(text)

    assert guard["unsupported"] is True
    assert guard["reason"] == reason


def test_9b_a_real_floor_request_is_not_suppressed_by_a_nearby_preserve_clause():
    """The repair must not weaken the guard: a genuine addition still refuses."""

    assert is_floor_restructuring_edit(
        "Do not touch the roof. Add two floors."
    ) is True
    assert is_floor_restructuring_edit("add two floors, keep the facade") is True


def test_9c_negated_list_is_one_prohibition():
    """The repaired case, plus the un-comma'd variant that already worked."""

    assert is_floor_restructuring_edit(
        "Do not add floors, remove floors, or change the geometry."
    ) is False
    assert is_floor_restructuring_edit("do not add or remove floors") is False


def test_9d_substring_is_not_a_verb():
    """"move" inside "remove" must not register as a geometry verb."""

    guard = detect_unsupported_geometry_edit(
        "Remove the brick and apply cream travertine."
    )

    assert "move" not in (guard.get("matched") or [])
    # "move" as a real word is still a geometry verb.
    assert detect_unsupported_geometry_edit(
        "move the entrance"
    )["unsupported"] is True


# ---------------------------------------------------------------- 10

def test_10_source_file_is_never_modified_by_a_capture(source_image):
    import hashlib

    before = hashlib.sha256(open(source_image, "rb").read()).hexdigest()
    _capture({"filename": os.path.basename(source_image), "path": source_image})
    after = hashlib.sha256(open(source_image, "rb").read()).hexdigest()

    assert before == after


# ---------------------------------------------------------------- 11

def test_11_no_execution_occurred(source_image):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    runtime.render(
        "i2i-no-exec-v1",
        {"prompt": USER_EDIT, "mode": "img2img", "seed": 1},
        "flux",
        image_asset={"filename": os.path.basename(source_image),
                     "path": source_image},
    )

    assert len(executor.workflows) == 1
