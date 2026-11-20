"""CPU-only acceptance for the narrow tall-tower portrait T2I preset."""

from copy import deepcopy
import hashlib
from pathlib import Path

from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
from core.prompt_intelligence.persian_architectural_understanding import understand
from core.render.render_preset_v1 import get_preset, resolve_preset
from core.render.render_runtime import RenderRuntime
from tests.test_t2i_prompt_fidelity_repair_v1 import (
    THREE_FLOOR_REQUEST,
    TOWER_REQUEST,
    cpu_isolation,
)


WORKFLOW = Path("core/render/workflows/flux.json")
BASELINE_WORKFLOW_SHA256 = (
    "c2b9c603c58fe6a21e93643edcbf5a71f65cffd4af061771562d84fa013961c4"
)


def _contracts(text):
    understanding = understand(text)
    compiled = compile_prompt(understanding, mode="text2img")
    terminology = normalize_architectural_terms(text)
    compiled_render = augment_compiled_prompt(
        compiled.get("positive_prompt") or "", terminology
    )
    instruction = build_render_instruction(
        text,
        understanding=understanding,
        compiled=compiled,
        mode="text2img",
    )
    return compiled_render, terminology, instruction


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine, "prompt_id": None}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


def _capture_workflow(text, preset_resolution, cpu_isolation):
    compiled, terminology, instruction = _contracts(text)
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()
    runtime.render(
        "t2i-tall-tower-portrait-v1",
        {
            "prompt": "UNTRUSTED LEGACY PROMPT",
            "original_prompt": text,
            "compiled_render_prompt": compiled,
            "terminology": terminology,
            "architectural_instruction": {
                "contract": "RenderConstraintBlockV1",
                "version": "1.0",
                "constraint_block": build_constraint_block(instruction),
                "source": "render_instruction.english_instruction",
            },
            "preset_resolution": preset_resolution,
            "mode": "text2img",
            "seed": 1793700658,
        },
        "flux",
        None,
    )
    assert cpu_isolation == []
    assert len(executor.workflows) == 1
    return executor.workflows[0]


def test_exact_tower_selects_portrait_preset_and_captured_graph(cpu_isolation):
    _, terminology, instruction = _contracts(TOWER_REQUEST)
    resolved = resolve_preset(
        terminology=terminology,
        architectural_instruction=instruction,
    )
    workflow = _capture_workflow(TOWER_REQUEST, resolved, cpu_isolation)
    positive = workflow["206"]["inputs"]["text"].lower()

    assert resolved["name"] == "exterior_night_tall"
    assert workflow["211"]["inputs"]["width"] == 576
    assert workflow["211"]["inputs"]["height"] == 960
    assert workflow["210"]["inputs"]["steps"] == 22
    assert "exactly 25 floors" in positive
    assert "full roofline" in positive
    assert "three quarter view" in positive
    assert "glass facade" in positive
    assert "dark metal" in positive
    assert "night scene" in positive
    assert "required architectural feature — include doors" not in positive
    affirmative = positive.split("do not include:", 1)[0]
    assert "exposed brick" not in affirmative
    assert "neoclassical" not in affirmative
    assert "daylight" not in affirmative


def test_ordinary_night_facade_keeps_original_preset():
    text = "یک نمای ساختمان مسکونی در شب با نورپردازی گرم طراحی کن."
    _, terminology, instruction = _contracts(text)
    resolved = resolve_preset(
        terminology=terminology,
        architectural_instruction=instruction,
    )
    assert resolved["name"] == "exterior_night"
    assert (resolved["width"], resolved["height"], resolved["steps"]) == (
        768,
        704,
        22,
    )


def test_three_floor_daylight_control_is_unchanged():
    _, terminology, instruction = _contracts(THREE_FLOOR_REQUEST)
    resolved = resolve_preset(
        terminology=terminology,
        architectural_instruction=instruction,
    )
    assert resolved["name"] == "exterior_day"
    assert (resolved["width"], resolved["height"], resolved["steps"]) == (
        768,
        704,
        20,
    )


def test_tall_selection_requires_requested_countable_tower_and_night():
    cases = (
        "یک برج بلند در شب طراحی کن.",
        "یک برج ۲۵ طبقه در روز طراحی کن.",
        "این برج ۲۵ طبقه است و شب دیده می‌شود.",
        "یک ساختمان ۲۵ طبقه در شب طراحی کن.",
    )
    for text in cases:
        _, terminology, instruction = _contracts(text)
        assert resolve_preset(
            terminology=terminology,
            architectural_instruction=instruction,
        )["name"] != "exterior_night_tall"


def test_existing_tower_aliases_share_the_canonical_selection():
    text = (
        "Create a 20 floor high-rise residential building at night, with the full "
        "building visible from ground level to roof."
    )
    _, terminology, instruction = _contracts(text)
    assert "tower" in terminology["canonical_terms"]
    assert resolve_preset(
        terminology=terminology,
        architectural_instruction=instruction,
    )["name"] == "exterior_night_tall"


def test_preset_pixel_budget_and_night_policy_are_bounded():
    regular = get_preset("exterior_night")
    tall = get_preset("exterior_night_tall")
    assert tall["width"] % 64 == tall["height"] % 64 == 0
    assert tall["width"] * tall["height"] == 552960
    assert tall["width"] * tall["height"] / (
        regular["width"] * regular["height"]
    ) < 1.023
    assert tall["steps"] == regular["steps"] == 22
    assert tall["quality_tail"] == regular["quality_tail"]
    assert tall["tags"] == regular["tags"]


def test_flux_workflow_is_unchanged():
    assert hashlib.sha256(WORKFLOW.read_bytes()).hexdigest() == (
        BASELINE_WORKFLOW_SHA256
    )


def test_real_persian_door_remains_a_feature_after_image_preposition_fix():
    instruction = build_render_instruction("یک در ورودی چوبی طراحی کن.")
    features = instruction["constraints"]["feature_requirements"]
    assert any(item["element"] == "door" for item in features)
