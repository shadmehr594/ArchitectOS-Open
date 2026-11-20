"""CPU-only acceptance for T2I_PROMPT_FIDELITY_REPAIR_V1.

The production deterministic interpretation, render-instruction and workflow
injection paths run.  The executor is replaced before RenderRuntime.render(),
and sockets are blocked, so no ComfyUI/GPU/Ollama transport is possible.
"""

from copy import deepcopy
import socket

import pytest

import core.runtime.gpu_handoff_v1 as gpu_handoff
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
from core.render.render_runtime import RenderRuntime


TOWER_REQUEST = """یک برج مسکونی لوکس و مدرن ۲۵ طبقه در شب طراحی کن.

برج دارای معماری مدرن و معاصر، نمای شیشه‌ای سرتاسری با شیشه‌های دودی آبی، فریم‌های فلزی تیره، خطوط عمودی ظریف، بالکن‌های مدرن و تناسبات کشیده و بلندمرتبه باشد.

نورپردازی حرفه‌ای شب شامل خطوط LED سفید گرم و طلایی، نورهای داخلی واحدهای مسکونی، انعکاس واقعی نور روی شیشه‌ها و آسمان آبی تیره باشد.

تمام ارتفاع برج از همکف تا بام در تصویر دیده شود. دوربین با فاصله کافی و زاویه سه‌ربع قرار بگیرد تا ساختمان از کادر خارج نشود.

برج دارای ۲۵ طبقه روی زمین با خطوط افقی منظم، نمای مدرن لوکس و تناسبات معماری واقع‌گرایانه باشد.

Photorealistic architectural visualization, luxury contemporary high-rise, cinematic night lighting, realistic glass reflections, premium architectural photography, detailed facade, elegant nighttime city atmosphere.

Avoid classical columns, neoclassical ornaments, unfinished construction, exposed brick, daylight, cropped tower, distorted architecture and duplicated towers."""

THREE_FLOOR_REQUEST = (
    "یک ساختمان مسکونی سه طبقه با نمای نئوکلاسیک، سنگ تراورتن کرم، "
    "پنجره‌های متقارن و نور روز طراحی کن."
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


def test_exact_tower_semantics_keep_requirements_and_exclusions_in_scope():
    compiled, terminology, instruction = _contracts(TOWER_REQUEST)
    terms = terminology["canonical_terms"]
    english = instruction["english_instruction"]
    prohibited = " ".join(
        instruction["constraints"]["negations"]["prohibited_content"]
    ).lower()

    assert "modern style" in terms
    assert "glass facade" in terms
    assert "metal" in terms
    assert "night lighting" in terms
    assert "brick" not in terms
    assert "neoclassical style" not in terms
    assert "natural lighting" not in terms
    assert "three quarter view" in terms
    assert "Camera / view: three quarter view" in english
    assert "Do NOT include: دوربین با فاصله" not in english
    assert "classical columns" in prohibited
    assert "neoclassical ornaments" in prohibited
    assert "exposed brick" in prohibited
    assert "daylight" in prohibited
    assert "cropped tower" in prohibited
    assert "duplicated towers" in prohibited
    assert "exactly 25 floors" in english
    assert "full roofline" in english
    assert "enough camera distance" in english
    assert "brick" not in compiled.lower().split("terminology:")[0]


def test_three_floor_neoclassical_daylight_regression_stays_affirmative():
    compiled, terminology, instruction = _contracts(THREE_FLOOR_REQUEST)
    terms = terminology["canonical_terms"]
    final = (compiled + " " + instruction["english_instruction"]).lower()

    assert "neoclassical style" in terms
    assert "travertine" in terms
    assert "natural lighting" in terms
    assert "exactly 3 floors" in final
    assert "neoclassical" in final
    assert "travertine" in final
    assert "natural lighting" in final


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine, "prompt_id": None}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


class _Lease:
    def acquire(self):
        return True

    def release(self):
        return None


@pytest.fixture
def cpu_isolation(monkeypatch, tmp_path):
    attempts = []

    def _blocked_connect(self, address, *args, **kwargs):
        attempts.append(repr(address))
        raise AssertionError("network dispatch forbidden in CPU acceptance")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(tmp_path / "handoff"))
    (tmp_path / "handoff").mkdir()
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", lambda *a, **k: _Lease())
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda *a, **k: {
            "status": "not_loaded",
            "reason": None,
            "ownership": "cpu_test_stub",
            "unloaded": [],
            "skipped_in_use": [],
            "vram_free_after": 16 * 1024 ** 3,
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "require_render_vram",
        lambda *a, **k: {
            "ok": True,
            "reason": "cpu_test_stub",
            "free_mib": 16384,
            "min_free_mib": 11264,
            "measurement_source": "cpu_test_stub",
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "release_comfyui_for_vision",
        lambda *a, **k: {"status": "blocked", "reason": "cpu_test"},
    )
    return attempts


def _capture_workflow(text, preset, cpu_isolation):
    compiled, _, instruction = _contracts(text)
    block = build_constraint_block(instruction)
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()
    runtime.render(
        "t2i-prompt-fidelity-repair-v1",
        {
            "prompt": "UNTRUSTED LEGACY PROMPT",
            "original_prompt": text,
            "compiled_render_prompt": compiled,
            "architectural_instruction": {
                "contract": "RenderConstraintBlockV1",
                "version": "1.0",
                "constraint_block": block,
                "source": "render_instruction.english_instruction",
            },
            "architectural_intent": {"building_type": "residential building"},
            "preset": preset,
            "mode": "text2img",
            "seed": 1793700658,
        },
        "flux",
        None,
    )
    assert cpu_isolation == []
    assert len(executor.workflows) == 1
    return executor.workflows[0]


def test_exact_effective_clip_inputs_are_repaired_without_transport(cpu_isolation):
    workflow = _capture_workflow(TOWER_REQUEST, "exterior_night", cpu_isolation)
    positive = workflow["206"]["inputs"]["text"]
    negative = workflow["212"]["inputs"]["text"]
    affirmative = positive.split("Do NOT include:", 1)[0].lower()

    assert "contemporary architectural language" in positive.lower()
    assert "glass facade" in positive.lower()
    assert "dark metal" in positive.lower()
    assert "light metal" not in positive.lower()
    assert "night lighting" in positive.lower()
    assert "night scene" in positive.lower()
    assert "exactly 25 floors" in positive.lower()
    assert "three quarter view" in positive.lower()
    assert "full roofline" in positive.lower()
    assert "enough camera distance" in positive.lower()
    assert "neoclassical style" not in affirmative
    assert "natural lighting" not in affirmative
    assert ", brick," not in affirmative
    assert "do not include" in positive.lower()
    assert "exposed brick" in positive.lower()
    assert "daylight" in positive.lower()
    assert negative == (
        "low quality, blurry, distorted, bad geometry, deformed, unrealistic, "
        "bad architecture"
    )
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["210"]["inputs"]["negative"] == ["212", 0]


def test_three_floor_request_reaches_effective_clip_unchanged(cpu_isolation):
    workflow = _capture_workflow(
        THREE_FLOOR_REQUEST, "exterior_day", cpu_isolation
    )
    positive = workflow["206"]["inputs"]["text"].lower()

    assert "exactly 3 floors" in positive
    assert "neoclassical style" in positive
    assert "travertine" in positive
    assert "natural lighting" in positive
    assert "bright natural daylight" in positive
