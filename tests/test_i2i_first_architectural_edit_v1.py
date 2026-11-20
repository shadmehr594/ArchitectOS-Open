# -*- coding: utf-8 -*-
"""I2I_FIRST_RELIABLE_ARCHITECTURAL_EDIT_V1 — CPU-only acceptance.

Drives the REAL RenderRuntime and WorkflowSelector with a non-executing capture
executor. No HTTP, no ComfyUI, no GPU, no model inference.

What these tests CAN prove: routing, source binding, graph shape, prompt
transport, and failure behaviour.
What they CANNOT prove: that the diffusion model will visually preserve the
building. Geometry preservation stays a REQUESTED constraint.
"""

import os
from copy import deepcopy

import pytest
from PIL import Image

from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector

EDIT_REQUEST = (
    "Change the building facade to cream travertine with a modern architectural "
    "appearance. Preserve the existing building massing, floor count, window "
    "positions, doors, balconies and camera perspective."
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


def _capture(image_asset, mode="img2img", kontext=False):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    instruction = build_render_instruction(EDIT_REQUEST, mode="img2img")

    runtime.render(
        "i2i-acceptance-v1",
        {
            "prompt": EDIT_REQUEST,
            "original_prompt": EDIT_REQUEST,
            "compiled_render_prompt": (
                "Refine the existing facade. Replace the facade material with "
                "cream travertine while keeping the building massing and window "
                "layout."
            ),
            "architectural_instruction": {
                "contract": "RenderConstraintBlockV1",
                "version": "1.0",
                "constraint_block": build_constraint_block(instruction),
                "source": "render_instruction.english_instruction",
            },
            "mode": mode,
            "seed": 1793714778,
        },
        "flux",
        image_asset=image_asset,
        kontext_edit=kontext,
    )
    assert executor.workflows, "no workflow was captured"
    return executor.workflows[0]


# ---------------------------------------------------------------- F

def test_f_edit_routes_to_genuine_img2img_not_text_to_image(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    types = [node.get("class_type") for node in workflow.values()]

    assert "EmptyLatentImage" not in types
    assert "LoadImage" in types
    assert "VAEEncode" in types
    assert workflow["210"]["inputs"]["latent_image"] == ["301", 0]
    assert workflow["301"]["inputs"]["pixels"] == ["300", 0]


# ---------------------------------------------------------------- A

def test_a_the_selected_source_image_is_the_one_bound(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    loads = [k for k, v in workflow.items() if v.get("class_type") == "LoadImage"]

    assert loads == ["300"]
    assert workflow["300"]["inputs"]["image"] == os.path.basename(source_image)


# ---------------------------------------------------------------- E

def test_e_no_mask_node_and_no_foreign_source_is_substituted(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    types = [node.get("class_type") for node in workflow.values()]

    # The historical failure was a mask overwriting the image loader. The
    # mask branch only writes LoadImageMask nodes, and this graph has none.
    assert "LoadImageMask" not in types
    assert "ImageCompositeMasked" not in types
    # The placeholder was replaced by the real source, not left in place.
    assert workflow["300"]["inputs"]["image"] != "input.png"


# ---------------------------------------------------------------- D

def test_d_preservation_requirements_reach_the_sampler(source_image):
    """Preservation is carried by the I2I edit prompt builder, not by the
    render-instruction constraint block.

    Measured: `build_constraint_block(build_render_instruction(english_text))`
    is EMPTY for this request — that contract is Persian-oriented. The I2I path
    does not depend on it: `ImageEditPromptBuilder` emits the preservation
    block, which is what actually reaches node 206. This test asserts the
    owner that matters.
    """

    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    positive = workflow["206"]["inputs"]["text"].lower()

    assert "geometry preservation" in positive
    assert "preserve exactly" in positive
    assert "floor count" in positive
    assert "camera angle" in positive
    assert "perspective" in positive
    assert "balconies" in positive
    # And it forbids the destructive alternatives explicitly.
    assert "add floors" in positive
    assert "change volume" in positive


# ---------------------------------------------------------------- B

def test_b_the_text_edit_request_reaches_the_sampler(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    positive = workflow["206"]["inputs"]["text"]

    assert positive.strip()
    assert "travertine" in positive.lower()


# ---------------------------------------------------------------- C

def test_c_output_is_a_new_file_not_the_source(source_image):
    workflow = _capture({"filename": os.path.basename(source_image),
                         "path": source_image})

    prefix = workflow["9"]["inputs"].get("filename_prefix")
    source_name = os.path.basename(source_image)

    assert prefix
    assert prefix != source_name
    assert workflow["300"]["inputs"]["image"] == source_name


# ---------------------------------------------------------------- H

def test_h_missing_source_leaves_the_placeholder_and_substitutes_nothing():
    """With no image asset the graph must not silently acquire a foreign one."""

    workflow = _capture(None)

    # Nothing was substituted: the workflow's own placeholder is untouched.
    assert workflow["300"]["inputs"]["image"] == "input.png"


# ---------------------------------------------------------------- I

def test_i_text_to_image_routing_is_unchanged():
    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "img2img"}) == "flux_img2img.json"
    assert selector.select({"engine": "flux", "image": "x.png"}) == "flux_img2img.json"
    # An explicit Kontext opt-in still wins, unchanged.
    assert selector.select(
        {"engine": "flux", "image": "x.png", "kontext_edit": True}
    ) == "flux_kontext_edit.json"


# ---------------------------------------------------------------- J

def test_j_no_execution_occurred(source_image):
    """The capture executor records the graph and never submits."""

    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    runtime.render(
        "i2i-no-exec-v1",
        {"prompt": EDIT_REQUEST, "mode": "img2img", "seed": 1},
        "flux",
        image_asset={"filename": os.path.basename(source_image),
                     "path": source_image},
    )

    assert len(executor.workflows) == 1
