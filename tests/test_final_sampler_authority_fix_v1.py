"""CPU-only acceptance for FINAL_SAMPLER_AUTHORITY_FIX_V1.

No GPU, ComfyUI, Ollama, HTTP or socket dispatch is permitted.  The production
RenderRuntime composition, workflow loader, prompt resolver and injectors run;
the executor is replaced before ``render`` and captures the exact workflow.
"""

from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

import core.runtime.gpu_handoff_v1 as gpu_handoff
from core.render.prompt_builder import PromptBuilder
from core.render.render_runtime import RenderRuntime


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "runs"
    / "t2i_visual_acceptance_v1"
    / "final_sampler_authority_gate_v1.json"
)


class _Lease:
    def __init__(self):
        self.acquires = 0
        self.releases = 0

    def acquire(self):
        self.acquires += 1
        return True

    def release(self):
        self.releases += 1


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine):
        self.workflows.append(deepcopy(workflow))
        return {
            "status": "dry_run_capture",
            "engine": engine,
            "prompt_id": None,
        }


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


@pytest.fixture
def cpu_isolation(monkeypatch, tmp_path):
    """Install every guard before a production render path can execute."""

    attempts = []

    def _blocked_connect(self, address, *args, **kwargs):
        attempts.append(repr(address))
        raise AssertionError("network dispatch forbidden in CPU acceptance")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setenv(
        "ARCHITECTOS_GPU_HANDOFF_DIR",
        str(tmp_path / "gpu_handoff"),
    )
    (tmp_path / "gpu_handoff").mkdir()

    leases = []

    def _lease(*args, **kwargs):
        lease = _Lease()
        leases.append(lease)
        return lease

    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", _lease)
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda *args, **kwargs: {
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
        lambda *args, **kwargs: {
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
        lambda *args, **kwargs: {
            "status": "blocked",
            "reason": "cpu_test_no_live_comfyui",
        },
    )

    return {"network_attempts": attempts, "leases": leases}


def _runtime_capture(design, cpu_isolation, image_asset=None):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    result = runtime.render(
        "final-sampler-authority-v1",
        deepcopy(design),
        "flux",
        image_asset,
    )

    assert len(executor.workflows) == 1
    assert cpu_isolation["network_attempts"] == []
    workflow = executor.workflows[0]
    return runtime, result, workflow


def _authoritative_design(compiled, instruction, preset="exterior_day", **extra):
    design = {
        "prompt": "UNTRUSTED LEGACY PROMPT MUST NOT BE CONSUMED",
        "original_prompt": compiled,
        "compiled_render_prompt": compiled,
        "architectural_instruction": {
            "contract": "RenderConstraintBlockV1",
            "version": "1.0",
            "constraint_block": instruction,
            "source": "render_instruction.english_instruction",
        },
        "architectural_intent": {
            "building_type": "residential building",
            "preserve_geometry": False,
        },
        "preset": preset,
        "mode": "text2img",
        "seed": 71001,
    }
    design.update(extra)
    return design


def _assert_positive_graph(workflow, expected_prompt):
    assert workflow["210"]["inputs"]["positive"] == ["206", 0]
    assert workflow["210"]["inputs"]["negative"] == ["212", 0]
    assert workflow["206"]["class_type"] == "CLIPTextEncode"
    assert workflow["206"]["inputs"]["text"] == expected_prompt
    assert workflow["206"]["inputs"]["clip"] == ["204", 0]
    assert workflow["204"]["class_type"] == "DualCLIPLoader"
    assert workflow["204"]["inputs"]["clip_name1"] == "clip_l.safetensors"
    assert workflow["204"]["inputs"]["clip_name2"] == "t5xxl_fp16.safetensors"
    assert workflow["212"]["inputs"]["text"] != expected_prompt


@pytest.mark.parametrize(
    ("value", "expected", "forbidden"),
    [
        (1, "single floor building", ("2 story", "3 story", "5 story")),
        (2, "2 story building", ("single floor", "3 story", "5 story")),
        (3, "3 story building", ("single floor", "2 story", "5 story")),
        (5, "5 story building", ("single floor", "2 story", "3 story")),
        (None, None, ("single floor", " story building")),
    ],
)
def test_floor_count_is_evidence_based(value, expected, forbidden):
    intent = {"building_type": "house", "materials": ["brick"]}
    if value is not None:
        intent["floors"] = value

    built = PromptBuilder().build({"architectural_intent": intent})
    prompt = built["description"].lower()

    if expected:
        assert expected in prompt
        assert built["floors"] == value
    else:
        assert built["floors"] is None

    for phrase in forbidden:
        assert phrase not in prompt


def test_resolved_facade_projection_blocks_ontology_metadata():
    knowledge = {
        "contract": "ResolvedFacadeKnowledgeV1",
        "canonical_style": "beaux_arts",
        "user_facade_details": ["paired entrance columns"],
        "facade_language": {
            "name": "beaux_arts",
            "composition": ["formal symmetry"],
            "elements": ["sculptural relief panels"],
        },
        "materials": {
            "primary": ["metal"],
            "cladding": ["metal panels"],
            "texture": ["brushed texture"],
            "finish": ["matte finish"],
            "resolved": [
                {
                    "name": "metal",
                    "styles": [
                        "modern",
                        "industrial",
                        "french_classical",
                        "second_empire",
                        "french_provincial",
                    ],
                    "uses": ["roof", "railing", "ontology_only"],
                }
            ],
            "compatible_options": [
                {"requested": "metal", "options": ["unapproved alloy"]}
            ],
        },
        "provenance": ["material_ontology.json"],
        "unresolved": [],
    }
    built = PromptBuilder().build(
        {
            "architectural_intent": {
                "building_type": "museum",
                "style": "beaux_arts",
                "resolved_facade_knowledge": knowledge,
            }
        }
    )
    prompt = built["description"].lower()

    assert "beaux arts" in prompt
    assert "paired entrance columns" in prompt
    assert "sculptural relief panels" in prompt
    assert "metal" in prompt
    for contaminant in (
        "industrial",
        "french classical",
        "second empire",
        "french provincial",
        "ontology only",
        "unapproved alloy",
        "material ontology.json",
    ):
        assert contaminant not in prompt


def test_prompt_builder_preserves_explicit_floor_contract():
    built = PromptBuilder().build(
        {
            "architectural_intent": {
                "building_type": "residential building",
                "floor_count": {
                    "contract": "FloorCountV1",
                    "value": 5,
                    "source": "user_explicit",
                    "raw": "five floors",
                },
            }
        }
    )

    assert built["floors"] == 5
    assert "5 story building" in built["description"].lower()


def test_exact_final_clip_t5_matrix(cpu_isolation):
    cases = [
        {
            "id": "floor_1",
            "compiled": "A residential building exterior.",
            "instruction": "The building has exactly 1 floor.",
            "must": ["exactly 1 floor"],
            "forbid": ["single floor building", "2 story", "3 story", "5 story"],
        },
        {
            "id": "floor_2",
            "compiled": "A residential building exterior.",
            "instruction": "The building has exactly 2 floors.",
            "must": ["exactly 2 floors"],
            "forbid": ["single floor building", "3 story", "5 story"],
        },
        {
            "id": "floor_3",
            "compiled": "A residential building exterior.",
            "instruction": "The building has exactly 3 floors.",
            "must": ["exactly 3 floors"],
            "forbid": ["single floor building", "2 story", "5 story"],
        },
        {
            "id": "floor_5",
            "compiled": "A residential building exterior.",
            "instruction": "The building has exactly 5 floors.",
            "must": ["exactly 5 floors"],
            "forbid": ["single floor building", "2 story", "3 story"],
        },
        {
            "id": "floor_unspecified",
            "compiled": "A residential building exterior.",
            "instruction": "Include a clearly defined main entrance.",
            "must": ["clearly defined main entrance"],
            "forbid": ["single floor", " story building", "exactly 1 floor"],
        },
        {
            "id": "entrance_exact_one",
            "compiled": "A stone residential facade.",
            "instruction": "Include exactly 1 wood door for the main entrance.",
            "must": ["exactly 1 wood door", "main entrance"],
            "forbid": ["two doors", "multiple entrance"],
        },
        {
            "id": "entrances_multiple",
            "compiled": "A civic building exterior.",
            "instruction": "Include exactly 3 entrance doors on the ground floor.",
            "must": ["exactly 3 entrance doors", "ground floor"],
            "forbid": ["single entrance", "exactly 1"],
        },
        {
            "id": "entrance_count_unspecified",
            "compiled": "A civic building exterior.",
            "instruction": "Include visible entrance doors at the main facade.",
            "must": ["entrance doors", "main facade"],
            "forbid": ["exactly 1", "single entrance", "exactly 2", "exactly 3"],
        },
        {
            "id": "balcony_rooftop_ownership",
            "compiled": "A residential building with an upper-floor balcony and a rooftop edge.",
            "instruction": (
                "Use metal railings attached to the upper-floor balcony. "
                "Use a stone parapet at the rooftop; keep these as distinct elements."
            ),
            "must": ["metal railings attached", "upper-floor balcony", "stone parapet", "rooftop", "distinct elements"],
            "forbid": ["stone balcony railing", "metal rooftop parapet"],
        },
        {
            "id": "mixed_material_location_attachment",
            "compiled": "A brick facade with timber window frames and a concrete entrance canopy.",
            "instruction": (
                "Keep timber attached to the window frames. "
                "Keep concrete on the entrance canopy and brick on the facade."
            ),
            "must": ["timber attached to the window frames", "concrete on the entrance canopy", "brick on the facade"],
            "forbid": ["timber canopy", "concrete window frames"],
        },
        {
            "id": "explicit_beaux_arts_style",
            "compiled": "A Beaux-Arts residential facade.",
            "instruction": "Use the explicitly requested Beaux-Arts style with paired entrance columns.",
            "must": ["beaux-arts", "paired entrance columns"],
            "forbid": ["french provincial", "second empire", "industrial style", "minimal modern"],
        },
        {
            "id": "style_unspecified",
            "compiled": "A residential building exterior.",
            "instruction": "Include a legible main entrance and windows.",
            "must": ["main entrance", "windows"],
            "forbid": ["modern", "neoclassical", "beaux", "french", "industrial", "minimal"],
        },
        {
            "id": "daylight",
            "compiled": "Render the facade in daylight.",
            "instruction": "Keep the scene in daylight.",
            "preset": "exterior_day",
            "must": ["daylight", "clear sky"],
            "forbid": ["night scene", "sunset light", "golden hour"],
        },
        {
            "id": "night",
            "compiled": "Render the facade at night.",
            "instruction": "Keep the scene at night with lit windows.",
            "preset": "exterior_night",
            "must": ["night", "lit windows", "deep blue sky"],
            "forbid": ["bright natural daylight", "golden hour sunset"],
        },
        {
            "id": "sunset",
            "compiled": "Render the facade at sunset.",
            "instruction": "Keep the scene at sunset.",
            "preset": "exterior_sunset",
            "must": ["sunset", "warm sky gradient"],
            "forbid": ["bright natural daylight", "night scene"],
        },
        {
            "id": "negation",
            "compiled": "A residential facade without balcony railings.",
            "instruction": "Do not include balcony railings; preserve the open balcony edge requested by the user.",
            "must": ["without balcony railings", "do not include balcony railings", "preserve"],
            "forbid": ["required architectural feature — include balcony railings", "metal railing on balcony"],
        },
    ]

    evidence = []
    for case in cases:
        design = _authoritative_design(
            case["compiled"],
            case["instruction"],
            preset=case.get("preset", "exterior_day"),
        )
        runtime, result, workflow = _runtime_capture(
            design,
            cpu_isolation,
        )
        final_prompt = runtime.last_render_request["resolved_prompt"]
        final_lower = final_prompt.lower()

        assert runtime.last_render_request["authoritative_t2i_handoff"] is True
        assert runtime.last_render_request["builder_reconstruction_skipped"] is True
        assert result["request_metadata"]["final_prompt"] == final_prompt
        assert result["prompt_resolution"]["builder_prompt"] == ""
        assert result["prompt_resolution"]["instruction_truncated"] is False
        assert "untrusted legacy prompt" not in final_lower
        for phrase in case["must"]:
            assert phrase.lower() in final_lower, (case["id"], phrase, final_prompt)
        for phrase in case["forbid"]:
            assert phrase.lower() not in final_lower, (case["id"], phrase, final_prompt)

        _assert_positive_graph(workflow, final_prompt)
        evidence.append(
            {
                "id": case["id"],
                "status": "PASS",
                "preset": case.get("preset", "exterior_day"),
                "authoritative_t2i_handoff": True,
                "builder_reconstruction_skipped": True,
                "instruction_truncated": False,
                "final_prompt": final_prompt,
                "node_206_text_matches_final": workflow["206"]["inputs"]["text"] == final_prompt,
                "positive_route": workflow["210"]["inputs"]["positive"],
                "encoder_route": workflow["206"]["inputs"]["clip"],
                "dual_clip_loader": {
                    "node": "204",
                    "class_type": workflow["204"]["class_type"],
                    "clip_name1": workflow["204"]["inputs"]["clip_name1"],
                    "clip_name2": workflow["204"]["inputs"]["clip_name2"],
                },
            }
        )

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(
            {
                "contract": "FinalSamplerAuthorityGateV1",
                "verdict": "PASS",
                "cpu_only": True,
                "network_attempts": cpu_isolation["network_attempts"],
                "case_count": len(evidence),
                "cases": evidence,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_legacy_t2i_fallback_remains_and_invents_no_floor(cpu_isolation):
    design = {
        "prompt": "brick house exterior",
        "original_prompt": "brick house exterior",
        "architectural_intent": {
            "building_type": "house",
            "materials": ["brick"],
            "preserve_geometry": False,
        },
        "preset": "exterior_day",
        "mode": "text2img",
        "seed": 71002,
    }
    runtime, result, workflow = _runtime_capture(design, cpu_isolation)
    final_prompt = runtime.last_render_request["resolved_prompt"]

    assert runtime.last_render_request["authoritative_t2i_handoff"] is False
    assert runtime.last_render_request["builder_reconstruction_skipped"] is False
    assert result["prompt_resolution"]["builder_prompt"]
    assert "single floor" not in final_prompt.lower()
    assert " story building" not in final_prompt.lower()
    _assert_positive_graph(workflow, final_prompt)


def test_captured_failed_visual_payload_is_corrected_at_node_206(cpu_isolation):
    captured_design = json.loads(
        (
            ROOT
            / "runs"
            / "t2i_visual_acceptance_v1"
            / "spatial_gate_v1.json"
        ).read_text(encoding="utf-8")
    )["design"]
    before = json.loads(
        (
            ROOT
            / "runs"
            / "t2i_visual_acceptance_v1"
            / "single_visual_acceptance_result_v1.json"
        ).read_text(encoding="utf-8")
    )["runtime_last_render_request"]["resolved_prompt"]

    runtime, result, workflow = _runtime_capture(
        captured_design,
        cpu_isolation,
    )
    after = runtime.last_render_request["resolved_prompt"]
    after_lower = after.lower()

    assert "the building has exactly 3 floors" in before.lower()
    assert "single floor building" in before.lower()
    assert "french classical" in before.lower()
    assert "beaux arts" in before.lower()

    assert runtime.last_render_request["authoritative_t2i_handoff"] is True
    assert runtime.last_render_request["builder_reconstruction_skipped"] is True
    assert "the building has exactly 3 floors" in after_lower
    assert "single floor building" not in after_lower
    assert "french classical" not in after_lower
    assert "beaux arts" not in after_lower
    assert "second empire" not in after_lower
    assert "french provincial" not in after_lower
    assert result["prompt_resolution"]["instruction_truncated"] is False
    _assert_positive_graph(workflow, after)

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    evidence["cases"].append(
        {
            "id": "captured_failed_visual_payload",
            "status": "PASS",
            "source": "runs/t2i_visual_acceptance_v1/spatial_gate_v1.json",
            "before_prompt": before,
            "final_prompt": after,
            "node_206_text_matches_final": workflow["206"]["inputs"]["text"] == after,
            "authoritative_t2i_handoff": True,
            "builder_reconstruction_skipped": True,
            "instruction_truncated": False,
            "positive_route": workflow["210"]["inputs"]["positive"],
            "encoder_route": workflow["206"]["inputs"]["clip"],
            "dual_clip_loader": {
                "node": "204",
                "class_type": workflow["204"]["class_type"],
                "clip_name1": workflow["204"]["inputs"]["clip_name1"],
                "clip_name2": workflow["204"]["inputs"]["clip_name2"],
            },
        }
    )
    evidence["case_count"] = len(evidence["cases"])
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_i2i_preservation_and_geometry_authority_are_unchanged(cpu_isolation):
    design = {
        "prompt": "Change only the wall finish to brick.",
        "original_prompt": "Change only the wall finish to brick.",
        "compiled_render_prompt": (
            "Change only the wall finish to brick. Preserve the existing "
            "massing, floor count, openings, camera and perspective."
        ),
        "architectural_instruction": {
            "contract": "RenderConstraintBlockV1",
            "version": "1.0",
            "constraint_block": (
                "Do not move, add or remove doors or windows. Preserve the "
                "existing geometry and all opening positions."
            ),
        },
        "architectural_intent": {
            "mode": "img2img",
            "building_type": "house",
            "materials": ["brick"],
            "preserve_geometry": True,
            "preserve_constraints": [
                "number_of_floors",
                "overall_massing",
                "main_window_positions",
                "main_door_positions",
                "camera",
                "perspective",
            ],
        },
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "denoise": 0.3,
        "mode": "img2img",
        "seed": 71003,
    }
    runtime, result, workflow = _runtime_capture(
        design,
        cpu_isolation,
        image_asset={"filename": "cpu_only_source.png"},
    )
    final_prompt = runtime.last_render_request["resolved_prompt"]

    assert runtime.last_render_request["authoritative_t2i_handoff"] is False
    assert runtime.last_render_request["builder_reconstruction_skipped"] is False
    assert result["mode"] == "img2img"
    assert "preserve" in final_prompt.lower()
    assert "do not move, add or remove doors or windows" in final_prompt.lower()
    assert workflow["210"]["inputs"]["denoise"] == pytest.approx(0.3)
    _assert_positive_graph(workflow, final_prompt)
