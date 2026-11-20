# -*- coding: utf-8 -*-
"""CPU-only regressions for the material-knowledge user-report handoff.

No provider, model, renderer, mask, network, or learning path is invoked here.
The authentic facade fixture was already captured by the accepted vision tests;
the beige-brick fixture is explicitly synthetic because it tests wording that
must remain observation evidence rather than become a user-instruction fact.
"""

from __future__ import annotations

import copy
import inspect
import json
import os

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_material_knowledge_connection_v1 import (
    build_architectural_material_knowledge_connection,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_report_v1 import render_vision_report


REQUEST = (
    "Replace beige brick on exposed architectural wall surfaces with natural "
    "cream travertine. Preserve windows, doors, railings, balconies, roof and "
    "other non-target components."
)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _observation(*, with_material=True):
    materials = []
    if with_material:
        materials = [
            {
                "descriptor": "beige brick on exposed facade wall surfaces",
                "materials": ["brick"],
                "evidence_phrase": "beige brick on exposed facade wall surfaces",
                "confidence": "MEDIUM",
            }
        ]
    return {
        "contract": "ArchitecturalObservationV1",
        "material_observations": materials,
        "provenance": {
            "provider": "SYNTHETIC_TEST_FIXTURE",
            "model": "NONE",
            "image_id": "SYNTHETIC-BEIGE-BRICK",
            "source_type": "test_fixture",
        },
    }


def _interpretation(*, with_material=True, request=REQUEST):
    observation = _observation(with_material=with_material)
    return {
        "space_type": "facade",
        "confidence": "MEDIUM",
        "observed_elements": [],
        "spatial_relations": [],
        "interpretations": [],
        "unknowns": [],
        "architectural_observation": observation,
        "architectural_material_knowledge_connection": (
            build_architectural_material_knowledge_connection(observation, request)
        ),
    }


def _material_block(report):
    return report.split("درک درخواست جایگزینی مصالح", 1)[1]


def _accepted_facade_understanding():
    with open(
        os.path.join(
            ROOT,
            "runs",
            "vision_facade_evidence_semantics_v1",
            "live_semantics_v1.json",
        ),
        encoding="utf-8",
    ) as handle:
        semantics = json.load(handle)
    with open(
        os.path.join(
            ROOT,
            "runs",
            "vision_facade_compound_v1",
            "live_compound_v1.json",
        ),
        encoding="utf-8",
    ) as handle:
        compound = json.load(handle)
    return build_understanding(
        {
            "contract": BRIDGE_CONTRACT,
            "raw_observer": compound["raw_observer"],
            "normalization": {
                "status": "NORMALIZED",
                "structured": copy.deepcopy(
                    semantics["normalization"]["structured"]
                ),
            },
        },
        provider="ollama",
        model="qwen3.8:27b",
        image_id="V3",
        source_type="other",
    )


def test_accepted_interpreter_contract_reaches_the_user_report():
    interpretation = interpret_architectural_vision(
        _accepted_facade_understanding(), user_text=REQUEST
    )
    report = render_vision_report(interpretation, "fa")
    message = ResponseAdapter().build_message({
        "type": "image_analysis",
        "status": "success",
        "architectural_interpretation": interpretation,
        "language": {"output_language": "persian"},
    })

    assert message == report
    assert interpretation["architectural_material_knowledge_connection"][
        "status"
    ] == "CONNECTED"
    assert "Full-height exterior walls of variegated red/brown/buff brick" in report
    assert "travertine stone facade [travertine]" in report
    assert "MATERIAL_REPLACEMENT" in report
    assert "NOT_YET_AVAILABLE" in report


def test_supported_brick_to_travertine_replacement_is_visible_and_not_recoloring():
    report = render_vision_report(_interpretation(), "fa")

    assert "beige brick on exposed facade wall surfaces" in report
    assert "natural cream travertine" in report
    assert "travertine stone facade [travertine]" in report
    assert "MATERIAL_REPLACEMENT" in report
    assert "نه صرفاً تغییر رنگ" in report


def test_observation_and_instruction_provenance_remain_separate():
    report = render_vision_report(_interpretation(), "fa")
    block = _material_block(report)
    observed, requested = block.split("مصالح جایگزین درخواستی کاربر", 1)

    assert "منبع: مشاهدهٔ بینایی" in observed
    assert "اطمینان مشاهده: MEDIUM" in observed
    assert "SYNTHETIC_TEST_FIXTURE" in observed
    assert "natural cream travertine" not in observed
    assert "منبع: دستور کاربر" in requested
    assert "مشاهدهٔ بصری نشده" in requested


def test_unknown_spatial_grounding_and_unavailable_execution_are_explicit():
    report = render_vision_report(_interpretation(), "fa")

    assert "نامشخص (UNKNOWN)" in report
    assert "هیچ مختصات یا ماسکی ایجاد نشده است" in report
    assert "هنوز در دسترس نیست (NOT_YET_AVAILABLE)" in report
    assert "این گزارش رندر تولید نکرده است" in report


def test_non_replacement_request_does_not_add_a_replacement_block():
    interpretation = _interpretation(request="What material is visible?")
    report = render_vision_report(interpretation, "fa")

    assert "درک درخواست جایگزینی مصالح" not in report
    assert "MATERIAL_REPLACEMENT" not in report
    assert "NOT_YET_AVAILABLE" not in report


def test_missing_material_observation_stays_explicitly_unestablished():
    report = render_vision_report(_interpretation(with_material=False), "fa")
    block = _material_block(report)

    assert "از شواهد بینایی موجود تعیین نشده است (UNVERIFIED)" in block
    assert "natural cream travertine" in block
    assert "travertine" not in block.split("مصالح جایگزین درخواستی کاربر", 1)[0]


def test_only_explicitly_protected_elements_are_reported():
    request = (
        "Replace brick on exposed architectural wall surfaces with natural "
        "cream travertine. Preserve windows."
    )
    report = render_vision_report(_interpretation(request=request), "fa")
    protected = report.split("اجزای محافظت‌شده فقط طبق دستور صریح کاربر:", 1)[1]
    protected = protected.split("\n", 1)[0]

    assert "windows" in protected
    assert "doors" not in protected
    assert "railings" not in protected
    assert "roof" not in protected


def test_full_explicit_protection_scope_is_visible():
    report = render_vision_report(_interpretation(), "fa")
    protected = report.split("اجزای محافظت‌شده فقط طبق دستور صریح کاربر:", 1)[1]
    protected = protected.split("\n", 1)[0]

    for component in (
        "windows",
        "doors",
        "railings",
        "balconies",
        "roof",
        "other non-target components",
    ):
        assert component in protected


def test_report_projection_is_read_only_and_contains_no_execution_calls():
    interpretation = _interpretation()
    before = copy.deepcopy(interpretation)

    render_vision_report(interpretation, "fa")

    assert interpretation == before
    assert interpretation["architectural_material_knowledge_connection"]["learned"] is False

    from core.vision import vision_report_v1

    source = inspect.getsource(vision_report_v1._material_connection_sections).lower()
    for forbidden in (
        "render_runtime",
        "sam3",
        "comfyui",
        "inference",
        "generate(",
        "mask_builder",
        "knowledge_registry",
    ):
        assert forbidden not in source
