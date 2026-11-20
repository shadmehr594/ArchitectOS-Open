"""CPU-only readiness checks for floor-count and night visual acceptance.

The production RenderRuntime, preset resolver, prompt composition and workflow
injectors run unchanged.  Network and GPU dispatch are blocked before render()
is called; the executor only captures the injected workflow.
"""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
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
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    denoise_override,
    preservation_level,
)
from core.prompt_intelligence.persian_architectural_understanding import understand
from core.render.image_edit_capability_v1 import audit as audit_image_edit_capability
from core.render.image_edit_presets_v1 import resolve_preservation_with_denoise
from core.render.render_preset_v1 import resolve_preset
from core.render.render_runtime import RenderRuntime


ROOT = Path(__file__).resolve().parents[1]
PRESERVED_FLOOR_EVIDENCE = (
    ROOT / "runs" / "t2i_visual_acceptance_v1" / "spatial_gate_v1.json"
)

FLOOR_REQUEST = (
    "یک ساختمان مسکونی سه‌طبقه طراحی و رندر کن. ساختمان در مجموع سه طبقه روی "
    "زمین داشته باشد: همکف و دو طبقه بالای آن. نمای ساختمان دارای پنجره‌های "
    "بلند و قوسی باشد. دقیقاً یک در ورودی اصلی چوبی طراحی کن. برای ساختمان "
    "بالکنی مشخص و قابل‌تشخیص در طبقات بالایی طراحی کن و برای همان بالکن نرده "
    "فلزی قرار بده. برای پشت‌بام جانپناه سنگی در نظر بگیر. نرده فلزی بالکن و "
    "جانپناه سنگی پشت‌بام دو عنصر متفاوت هستند و باید در محل صحیح خودشان قرار "
    "بگیرند. تمام عناصر باید از نظر معماری قابل‌تشخیص باشند. یک نمای پرسپکتیو "
    "خارجی از کل ساختمان در نور روز تولید کن، به‌طوریکه هر سه طبقه، ورودی، "
    "بالکن و بام دیده شوند."
)

NIGHT_T2I_REQUEST = (
    "یک ساختمان مسکونی سه‌طبقه طراحی و رندر کن. ساختمان در مجموع سه طبقه روی "
    "زمین داشته باشد: همکف و دو طبقه بالای آن. نمای ساختمان دارای پنجره‌های "
    "بلند و قوسی باشد. دقیقاً یک در ورودی اصلی چوبی طراحی کن. برای ساختمان "
    "بالکنی مشخص و قابل‌تشخیص در طبقات بالایی طراحی کن و برای همان بالکن نرده "
    "فلزی قرار بده. برای پشت‌بام جانپناه سنگی در نظر بگیر. نرده فلزی بالکن و "
    "جانپناه سنگی پشت‌بام دو عنصر متفاوت هستند و باید در محل صحیح خودشان قرار "
    "بگیرند. تمام عناصر باید از نظر معماری قابل‌تشخیص باشند. یک نمای شبانه و "
    "پرسپکتیو خارجی از کل ساختمان تولید کن، به‌طوریکه هر سه طبقه، ورودی، "
    "بالکن و بام دیده شوند؛ آسمان شب تیره و پنجره‌ها روشن باشند."
)

DAY_TO_NIGHT_REQUEST = "همینو شب کن"

SUNSET_T2I_REQUEST = (
    "یک نمای پرسپکتیو خارجی از ساختمان مسکونی در غروب رندر کن؛ "
    "نور غروب و آسمان گرم دیده شود."
)

UNSPECIFIED_TIME_T2I_REQUEST = (
    "یک نمای پرسپکتیو خارجی از ساختمان مسکونی رندر کن."
)


class _Lease:
    def acquire(self):
        return True

    def release(self):
        return None


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        # R4_POSITIVE_INSTRUCTION_CONTRACT_V1 — harness compatibility only.
        # `RenderRuntime.render()` passes `on_submitted=`; this fake predates
        # that keyword (2026-10-21 vs render_runtime 2026-10-23), so every test
        # here died with TypeError before reaching its assertions. No assertion
        # or expectation is changed.
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


@pytest.fixture
def cpu_isolation(monkeypatch, tmp_path):
    network_attempts = []

    def _blocked_connect(self, address, *args, **kwargs):
        network_attempts.append(repr(address))
        raise AssertionError("network dispatch forbidden in CPU readiness")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    handoff = tmp_path / "gpu_handoff"
    handoff.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(handoff))
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
        lambda *a, **k: {
            "status": "blocked",
            "reason": "cpu_test_no_live_comfyui",
        },
    )
    return network_attempts


def _capture(design, cpu_isolation, image_asset=None):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    with redirect_stdout(io.StringIO()):
        result = runtime.render(
            "night-floors-cpu-readiness",
            deepcopy(design),
            "flux",
            deepcopy(image_asset),
        )

    assert cpu_isolation == []
    assert len(executor.workflows) == 1
    return runtime, result, executor.workflows[0]


def _instruction_contract(text, understanding=None, compiled=None):
    instruction = build_render_instruction(
        text,
        mode="text2img",
        context={"mode": "text2img"},
        understanding=understanding,
        compiled=compiled,
    )
    return {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": build_constraint_block(instruction),
        "source": "render_instruction.english_instruction",
    }


def _t2i_design(text, seed):
    understanding = understand(text)
    compiled_contract = compile_prompt(
        understanding,
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )
    terminology = normalize_architectural_terms(text)
    compiled = augment_compiled_prompt(
        compiled_contract.get("positive_prompt", ""),
        terminology,
    )
    preset = resolve_preset(terminology=terminology)
    design = {
        "prompt": text,
        "original_prompt": text,
        "compiled_render_prompt": compiled,
        "architectural_instruction": _instruction_contract(
            text,
            understanding=understanding,
            compiled=compiled_contract,
        ),
        "architectural_intent": {
            "building_type": "residential building",
            "preserve_geometry": False,
        },
        "terminology": terminology,
        "preset_resolution": preset,
        "mode": "text2img",
        "seed": seed,
    }
    return design, preset, compiled


def test_exact_accepted_three_floor_request_reaches_final_sampler(cpu_isolation):
    preserved = json.loads(PRESERVED_FLOOR_EVIDENCE.read_text(encoding="utf-8"))
    design = deepcopy(preserved["design"])
    assert design["original_prompt"] == FLOOR_REQUEST

    current, preset, compiled = _t2i_design(FLOOR_REQUEST, 731001)
    design["compiled_render_prompt"] = compiled
    design["architectural_instruction"] = current["architectural_instruction"]
    design["terminology"] = current["terminology"]
    design["preset_resolution"] = preset
    design["seed"] = 731001

    runtime, result, workflow = _capture(design, cpu_isolation)
    final = runtime.last_render_request["resolved_prompt"]
    lowered = final.lower()

    required = (
        "the building has exactly 3 floors",
        "exactly 1 wood door for the entrance",
        "arched tall windows for the facade",
        "balcony on the upper floor",
        "metal railing for the balcony",
        "stone parapet for the rooftop",
        "frame the complete building: show the whole exterior elevation",
        "the entrance, the balcony and the roof visible in one view",
        "perspective view",
    )
    for phrase in required:
        assert phrase in lowered, (phrase, final)

    for forbidden in (
        "single floor building",
        "exactly 3 wood door",
        "stone railing for the balcony",
        "metal parapet for the rooftop",
        "french classical",
        "beaux arts",
    ):
        assert forbidden not in lowered, (forbidden, final)

    assert result["workflow"] == "flux.json"
    assert result["preset"] == "exterior_day"
    assert "balanced exposure" in lowered
    assert "bright natural daylight" in lowered
    assert "natural lighting" in lowered
    assert "night scene" not in lowered
    assert "sunset" not in lowered
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["206"]["inputs"]["text"] == final
    assert workflow["206"]["inputs"]["clip"] == ["204", 0]
    assert workflow["204"]["inputs"]["clip_name2"] == "t5xxl_fp16.safetensors"
    print("FLOOR_FINAL_PROMPT=" + final)


def test_t2i_night_routes_without_daylight_conflict(cpu_isolation):
    understanding = understand(NIGHT_T2I_REQUEST)
    compiled_contract = compile_prompt(
        understanding,
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )
    terminology = normalize_architectural_terms(NIGHT_T2I_REQUEST)
    compiled = augment_compiled_prompt(
        compiled_contract.get("positive_prompt", ""),
        terminology,
    )
    preset = resolve_preset(terminology=terminology)

    assert preset["name"] == "exterior_night"
    assert preset["reason"] == "explicit_night"

    design = {
        "prompt": NIGHT_T2I_REQUEST,
        "original_prompt": NIGHT_T2I_REQUEST,
        "compiled_render_prompt": compiled,
        "architectural_instruction": _instruction_contract(
            NIGHT_T2I_REQUEST,
            understanding=understanding,
            compiled=compiled_contract,
        ),
        "architectural_intent": {
            "building_type": "residential building",
            "preserve_geometry": False,
        },
        "terminology": terminology,
        "preset_resolution": preset,
        "mode": "text2img",
        "seed": 731002,
    }

    runtime, result, workflow = _capture(design, cpu_isolation)
    final = runtime.last_render_request["resolved_prompt"]
    lowered = final.lower()

    assert result["preset"] == "exterior_night"
    assert result["workflow"] == "flux.json"
    for required in (
        "night scene",
        "warm lit windows glowing",
        "controlled artificial exterior lighting",
        "architectural night photography",
        "deep blue sky",
    ):
        assert required in lowered, (required, final)
    for conflict in (
        "bright natural daylight",
        "golden hour",
        "sunset",
        "midday",
        "clear sky",
    ):
        assert conflict not in lowered, (conflict, final)

    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["206"]["inputs"]["text"] == final
    assert workflow["206"]["inputs"]["clip"] == ["204", 0]
    assert workflow["204"]["class_type"] == "DualCLIPLoader"
    assert workflow["204"]["inputs"]["clip_name1"] == "clip_l.safetensors"
    assert workflow["204"]["inputs"]["clip_name2"] == "t5xxl_fp16.safetensors"
    assert workflow["202"]["inputs"]["unet_name"] == "flux1-krea-dev_fp8_scaled.safetensors"
    assert workflow["210"]["inputs"]["steps"] == 22
    assert workflow["210"]["inputs"]["cfg"] == 1
    assert workflow["210"]["inputs"]["sampler_name"] == "euler"
    assert workflow["210"]["inputs"]["scheduler"] == "simple"
    assert workflow["210"]["inputs"]["denoise"] == 1
    assert "balanced daylight" not in lowered
    assert "daylight" not in lowered
    print("NIGHT_T2I_FINAL_PROMPT=" + final)


def test_t2i_sunset_keeps_golden_hour_without_day_or_night_conflict(cpu_isolation):
    design, preset, compiled = _t2i_design(SUNSET_T2I_REQUEST, 731004)
    assert preset["name"] == "exterior_sunset"
    assert preset["reason"] == "explicit_sunset"
    assert "balanced daylight" not in compiled.lower()

    runtime, result, workflow = _capture(design, cpu_isolation)
    final = runtime.last_render_request["resolved_prompt"]
    lowered = final.lower()

    assert result["preset"] == "exterior_sunset"
    assert result["workflow"] == "flux.json"
    for required in (
        "sunset lighting",
        "warm golden hour sunset light",
        "long soft shadows",
        "warm sky gradient",
    ):
        assert required in lowered, (required, final)
    for conflict in (
        "balanced daylight",
        "bright natural daylight",
        "clear sky",
        "night scene",
        "deep blue sky",
    ):
        assert conflict not in lowered, (conflict, final)
    assert workflow["206"]["inputs"]["text"] == final
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["206"]["inputs"]["clip"] == ["204", 0]
    assert workflow["204"]["class_type"] == "DualCLIPLoader"
    print("SUNSET_T2I_FINAL_PROMPT=" + final)


def test_t2i_unspecified_time_preserves_existing_default_preset(cpu_isolation):
    design, preset, compiled = _t2i_design(UNSPECIFIED_TIME_T2I_REQUEST, 731005)
    assert preset["name"] == "exterior_day"
    assert preset["reason"] == "exterior_default"
    assert "daylight" not in compiled.lower()

    runtime, result, workflow = _capture(design, cpu_isolation)
    final = runtime.last_render_request["resolved_prompt"]
    lowered = final.lower()

    assert result["preset"] == "exterior_day"
    assert "bright natural daylight" in lowered
    assert "night scene" not in lowered
    assert "sunset" not in lowered
    assert "exactly" not in lowered
    assert " story building" not in lowered
    assert "single floor" not in lowered
    assert workflow["206"]["inputs"]["text"] == final
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["206"]["inputs"]["clip"] == ["204", 0]
    assert workflow["204"]["class_type"] == "DualCLIPLoader"


def test_day_to_night_i2i_binds_source_and_requests_only_lighting(cpu_isolation):
    delta = compile_edit_delta(DAY_TO_NIGHT_REQUEST)
    preservation = resolve_preservation_with_denoise(
        text=DAY_TO_NIGHT_REQUEST,
        explicit=preservation_level(delta) or "high_preservation",
        denoise=denoise_override(delta),
    )
    source = {
        "filename": "accepted_day_source.png",
        "path": "accepted_day_source.png",
        "original_source_path": "accepted_day_source.png",
    }
    design = {
        "prompt": DAY_TO_NIGHT_REQUEST,
        "original_prompt": DAY_TO_NIGHT_REQUEST,
        "compiled_render_prompt": delta["prompt"],
        "architectural_intent": {
            "building_type": "existing building",
            "style": "existing architectural style",
            "materials": ["preserve existing facade materials"],
            "preserve_geometry": True,
            "preserve_constraints": [
                "building_silhouette",
                "massing",
                "floor_count",
                "wall_positions",
                "roof_shape",
                "openings",
                "structural_layout",
                "camera_angle",
                "perspective",
                "composition",
            ],
            "mode": "img2img",
            "edit_delta": delta,
        },
        "edit_delta": delta,
        "edit_conflict_terms": delta["conflict_terms"],
        "preservation": preservation,
        "denoise": preservation["denoise"],
        "mode": "img2img",
        "seed": 731003,
    }

    runtime, result, workflow = _capture(design, cpu_isolation, source)
    final = runtime.last_render_request["resolved_prompt"]
    lowered = final.lower()

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "night"
    assert result["preset"] is None
    assert result["request_metadata"]["preset_source"] == "suppressed_for_img2img"
    assert result["workflow"] == "flux_img2img.json"
    assert workflow["300"]["class_type"] == "LoadImage"
    assert workflow["300"]["inputs"]["image"] == source["filename"]
    assert workflow["301"]["class_type"] == "VAEEncode"
    assert workflow["301"]["inputs"]["pixels"] == ["300", 0]
    assert workflow["210"]["inputs"]["latent_image"] == ["301", 0]
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["206"]["inputs"]["text"] == final
    assert workflow["210"]["inputs"]["denoise"] == 0.30
    assert workflow["210"]["inputs"]["steps"] == 30
    assert workflow["210"]["inputs"]["cfg"] == 5
    assert workflow["202"]["inputs"]["unet_name"] == "flux1-krea-dev_fp8_scaled.safetensors"

    for required in (
        "convert the scene to true architectural night photography",
        "no daylight",
        "do not redesign the building",
        "preserve exactly",
        "original building silhouette",
        "floor count",
        "roof shape",
        "openings",
        "camera angle",
        "perspective",
        "composition",
    ):
        assert required in lowered, (required, final)
    for reconstruction in (
        "facade transformation",
        "architect-designed facade transformation",
        "strongly express the requested architectural style",
        "natural lighting",
        "golden hour",
        "single floor building",
    ):
        assert reconstruction not in lowered, (reconstruction, final)
    print("DAY_TO_NIGHT_I2I_FINAL_PROMPT=" + final)


def test_default_i2i_geometry_preservation_is_truthfully_limited():
    capability = audit_image_edit_capability(
        ROOT / "core" / "render" / "workflows" / "flux_img2img.json"
    )
    identity = capability["identity_preservation"]

    assert capability["capabilities"]["supports_global_img2img"] is True
    assert capability["capabilities"]["supports_instruction_edit"] is False
    assert identity["mechanism"] == "low_denoise_source_latent"
    assert identity["relies_on_low_denoise_only"] is True
    assert identity["has_structural_conditioning"] is False
    assert identity["has_region_conditioning"] is False
