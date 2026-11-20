"""CPU-only acceptance for the visual architectural knowledge continuation.

These tests exercise the existing deterministic Persian-understanding,
architectural-compiler, terminology, ontology-resolver, and prompt-builder
contracts.  They never open a network connection or invoke a renderer.
"""

from copy import deepcopy
import socket

import pytest

import core.runtime.gpu_handoff_v1 as gpu_handoff
from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    compile_prompt,
)
from core.prompt_intelligence.persian_architectural_understanding import understand
from core.render.prompt_builder import PromptBuilder
from core.render.render_runtime import RenderRuntime
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
    ArchitecturalVisionProvider,
    ReferenceImageArchitecturalUnderstandingV1,
)


def _deterministic_prompt(text):
    understanding = understand(text)
    compiled = compile_prompt(
        understanding,
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )
    terminology = normalize_architectural_terms(text)
    prompt = augment_compiled_prompt(
        compiled.get("positive_prompt", ""),
        terminology,
    )
    return understanding, terminology, prompt.lower()


def test_iranian_traditional_and_qazaghi_brick_survive_the_live_compiler():
    understanding, terminology, prompt = _deterministic_prompt(
        "نمای سنتی ایرانی با جزئیات آجر قزاقی و آجرکاری برجسته رندر کن"
    )

    assert understanding["style"]["target"] == "iranian_brick"
    assert understanding["materials"]["primary"] == "traditional_brick"
    assert "qazaghi brick detailing" in prompt
    assert "geometric brick relief" in prompt
    assert "tower" not in terminology["canonical_terms"]


def test_orsi_and_tilework_are_retained_as_explicit_elements():
    understanding, terminology, prompt = _deterministic_prompt(
        "نمای سنتی ایرانی با پنجره ارسی و کاشی‌کاری در ورودی رندر کن"
    )

    assert understanding["style"]["target"] == "iranian_traditional"
    assert "orsi windows" in prompt
    assert "architectural tilework" in prompt
    assert "orsi windows" in terminology["canonical_terms"]


def test_persian_french_family_name_reaches_its_existing_canonical_style():
    understanding, _, prompt = _deterministic_prompt(
        "نمای بوزار با سنگ طبیعی رندر کن"
    )

    assert understanding["style"]["target"] == "beaux_arts"
    assert "beaux-arts" in prompt
    assert "natural stone" in prompt


def test_persian_contemporary_reaches_modern_without_classical_leakage():
    understanding, _, prompt = _deterministic_prompt(
        "نمای معاصر با شیشه و بتن رندر کن"
    )

    assert understanding["style"]["target"] == "modern"
    assert "contemporary architectural language" in prompt
    assert "classical style" not in prompt


def test_neoclassical_does_not_emit_a_competing_generic_classical_style():
    understanding, terminology, prompt = _deterministic_prompt(
        "نمای نئوکلاسیک با سنگ تراورتن رندر کن"
    )

    assert understanding["style"]["target"] == "neoclassical"
    assert "neoclassical style" in terminology["canonical_terms"]
    assert "classical style" not in terminology["canonical_terms"]
    assert "restrained neoclassical" in prompt


def test_explicit_courtyard_landscape_features_survive_without_defaults():
    _, terminology, prompt = _deterministic_prompt(
        "حیاط ایرانی با کف‌سازی آجری، گیاهان و آب‌نما رندر کن"
    )

    for term in ("courtyard", "brick paving", "plants", "water feature"):
        assert term in terminology["canonical_terms"]
        assert term in prompt


def test_mixed_materials_remain_distinct_in_the_compiled_prompt():
    _, terminology, prompt = _deterministic_prompt(
        "نمای مدرن با آجر و فلز و شیشه رندر کن"
    )

    for term in ("brick", "metal", "glass"):
        assert term in terminology["canonical_terms"]
        assert term in prompt


def test_qazaghi_detail_is_connected_through_the_existing_iranian_brick_resolver():
    resolved = SharedFacadeKnowledgeResolverV1().resolve(
        {"style": "iranian_brick"}
    )
    prompt = str(
        PromptBuilder().build(
            {
                "style": "iranian_brick",
                "resolved_facade_knowledge": resolved,
            }
        )
    ).lower()

    assert "qazaghi brick detailing" in prompt
    assert "orsi window" not in prompt
    assert "beaux" not in prompt


def test_material_compatibility_metadata_never_becomes_style_intent():
    resolved = SharedFacadeKnowledgeResolverV1().resolve(
        {"style": "modern", "materials": ["metal"]}
    )
    prompt = str(
        PromptBuilder().build(
            {
                "style": "modern",
                "materials": ["metal"],
                "resolved_facade_knowledge": resolved,
            }
        )
    ).lower()

    for unrelated in ("french classical", "beaux arts", "second empire"):
        assert unrelated not in prompt


def test_image_edit_intent_producer_uses_the_same_canonical_style_ids():
    engine = ArchitecturalIntent()
    cases = {
        "نمای سنتی ایرانی با آجر قزاقی": "iranian_brick",
        "نمای بوزار با سنگ طبیعی": "beaux_arts",
        "نمای معاصر با شیشه و بتن": "modern",
    }

    for text, expected in cases.items():
        intent = engine.extract({"prompt": text})
        assert intent["style"] == expected, (text, intent["style"])


class _Lease:
    def acquire(self):
        return True

    def release(self):
        return None


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine):
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


@pytest.fixture
def cpu_runtime_isolation(monkeypatch, tmp_path):
    attempts = []

    def _blocked_connect(self, address, *args, **kwargs):
        attempts.append(repr(address))
        raise AssertionError("network dispatch forbidden in CPU acceptance")

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
    return attempts


def _final_sampler_prompt(text, cpu_runtime_isolation):
    understanding = understand(text)
    compiled_contract = compile_prompt(
        understanding,
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )
    terminology = normalize_architectural_terms(text)
    compiled = augment_compiled_prompt(
        compiled_contract.get("positive_prompt", ""), terminology
    )
    instruction = build_render_instruction(
        text,
        understanding=understanding,
        compiled=compiled_contract,
    )
    block = build_constraint_block(instruction)

    style = (understanding.get("style") or {}).get("target")
    materials = understanding.get("materials") or {}
    requested_materials = list(materials.get("mentions") or [])
    if materials.get("primary") and materials["primary"] not in requested_materials:
        requested_materials.insert(0, materials["primary"])

    design = {
        "prompt": text,
        "original_prompt": text,
        "compiled_render_prompt": compiled,
        "architectural_intent": {
            "building_type": "building",
            "style": style,
            "materials": requested_materials,
            "preserve_geometry": False,
        },
        "mode": "text2img",
        "preset": "exterior_day",
        "seed": 78101,
    }
    if block:
        design["architectural_instruction"] = {
            "contract": "RenderConstraintBlockV1",
            "version": "1.0",
            "constraint_block": block,
            "source": "render_instruction.english_instruction",
        }

    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()
    runtime.render("visual-knowledge-cpu", design, "flux")

    assert cpu_runtime_isolation == []
    assert len(executor.workflows) == 1
    final_prompt = runtime.last_render_request["resolved_prompt"]
    assert executor.workflows[0]["206"]["inputs"]["text"] == final_prompt
    return final_prompt.lower()


@pytest.mark.parametrize(
    "text,must,forbid",
    [
        (
            "نمای سنتی ایرانی با آجر رندر کن",
            ("traditional iranian", "brick"),
            ("beaux-arts", "second empire"),
        ),
        (
            "جزئیات آجر قزاقی را در نما رندر کن",
            ("qazaghi brick detailing", "traditional brick"),
            ("tower", "orsi"),
        ),
        (
            "پنجره ارسی را در نمای سنتی ایرانی رندر کن",
            ("orsi windows", "traditional iranian"),
            ("beaux-arts",),
        ),
        (
            "کاشی‌کاری ایرانی را در ورودی نما رندر کن",
            ("architectural tilework", "glazed tile"),
            ("industrial style",),
        ),
        (
            "نمای نئوکلاسیک با سنگ تراورتن رندر کن",
            ("restrained neoclassical", "travertine"),
            ("beaux-arts", "second empire"),
        ),
        (
            "نمای بوزار با سنگ طبیعی رندر کن",
            ("beaux-arts", "natural stone"),
            ("modern style", "french provincial"),
        ),
        (
            "نمای معاصر با شیشه و بتن رندر کن",
            ("contemporary architectural", "glass", "concrete"),
            ("classical style",),
        ),
        (
            "نمای مدرن با آجر و فلز و شیشه رندر کن",
            ("brick", "metal", "glass"),
            ("beaux-arts",),
        ),
        (
            "بالکن طبقات بالا با نرده فلزی و جان‌پناه سنگی پشت‌بام رندر کن",
            ("balcony", "metal", "stone parapet", "rooftop"),
            ("metal rooftop parapet", "stone balcony railing"),
        ),
        (
            "حیاط ایرانی با کف‌سازی آجری، گیاهان و آب‌نما رندر کن",
            ("courtyard", "brick paving", "plants", "water feature"),
            ("tower",),
        ),
    ],
)
def test_representative_requests_reach_the_final_sampler_cpu_only(
    text, must, forbid, cpu_runtime_isolation
):
    final_prompt = _final_sampler_prompt(text, cpu_runtime_isolation)
    for phrase in must:
        assert phrase in final_prompt, (phrase, final_prompt)
    for phrase in forbid:
        assert phrase not in final_prompt, (phrase, final_prompt)


class _FakeVisionProvider(ArchitecturalVisionProvider):
    name = "cpu-fake-vision"
    model = "structured-fixture"

    def __init__(self, raw):
        self.raw = raw

    def is_available(self):
        return True

    def analyze(self, image_asset):
        return deepcopy(self.raw)


def test_reference_observation_stays_ephemeral_but_reaches_the_handoff(tmp_path):
    image_a = tmp_path / "style-reference.bin"
    image_b = tmp_path / "target-building.bin"
    image_a.write_bytes(b"STYLE-A")
    image_b.write_bytes(b"TARGET-B")

    a = ReferenceImageArchitecturalUnderstandingV1(
        _FakeVisionProvider(
            {
                "facade_style": "neoclassical",
                "materials": [{"type": "stone", "confidence": 0.8}],
                "classical_features": ["paired pilasters"],
            }
        )
    ).analyze(str(image_a), use_cache=False)
    b = ReferenceImageArchitecturalUnderstandingV1(
        _FakeVisionProvider(
            {
                "visible_floor_count": 3,
                "windows": {"rhythm": "regular", "frame": "recessed"},
                "balconies": {"present": True, "type": "open balcony"},
                "roof_features": ["flat parapet"],
            }
        )
    ).analyze(str(image_b), use_cache=False)

    instruction = build_render_instruction(
        "سبک نمای تصویر A را به ساختمان تصویر B منتقل کن",
        reference_analysis_ab={
            "A": a,
            "B": b,
            "roles": {
                "appearance_source": "A",
                "geometry_authority": "B",
            },
        },
    )
    full = instruction["english_instruction"].lower()
    block = build_constraint_block(instruction).lower()

    assert a["provenance"]["analysis_only"] is True
    assert b["provenance"]["analysis_only"] is True
    assert "resolved_facade_knowledge" not in a
    assert "as observed by the model (unverified)" in full
    assert "style neoclassical" in full
    assert "materials stone" in full
    assert "image b (geometry authority)" in full
    assert "take the facade appearance from image a" not in block
    assert "do not copy the style reference's (image a) massing" in block
