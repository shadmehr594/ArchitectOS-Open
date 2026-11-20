# ==========================================================
# ArchitectOS — DUAL_IMAGE_COMPARISON_V1
#
# Regression tests for the measured defect (V3 §8 R1):
#
#   A two-image comparison computed TWO complete architectural
#   analyses, then answered "I don't see any building photographs
#   attached" because no consumer existed for the A/B evidence.
#
# The cases below exercise the REAL projection module, the REAL
# response adapter and the REAL ChatArchitect method. The only
# recorded input used is the analysis contract from the live V3
# run — it is evidence of what vision actually produced, not an
# expected-output fixture.
#
# NO GPU. NO COMFYUI. NO NETWORK. NO PROVIDER CALL.
# ==========================================================

import ast
import json
import os

import pytest

from core.vision.dual_image_comparison_v1 import (
    CONTRACT,
    build_comparison,
    render_comparison,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIVE_COMPARISON = os.path.join(
    ROOT,
    "runs",
    "architectos_product_integration_v3",
    "p3b_response.json",
)


def _analysis(
    style="neoclassical",
    materials=(("travertine_like_stone", "light stone cladding"),),
    status="ANALYZED_WITH_UNCERTAINTY",
    **overrides
):
    """A minimal but REAL-shaped ReferenceArchitecturalAnalysisV1."""

    payload = {
        "contract": "ReferenceArchitecturalAnalysisV1",
        "version": "1.0",
        "analysis_status": status,
        "provider": "ollama_facade",
        "model": "qwen3.8:27b",
        "image_id": "img_" + style,
        "facade_style": style,
        "style_confidence": 0.9,
        "style_candidates": [{"style": style, "confidence": 0.9}],
        "materials": [
            {"type": name, "confidence": 0.9, "evidence": evidence}
            for name, evidence in materials
        ],
        "windows": {"present": True, "aspect": "tall"},
        "arches": {"present": False},
        "roof_features": ["cornice"],
        "ornament_level": "HIGH",
        "classical_features": ["pilasters"],
        "modern_features": [],
        "symmetry": "symmetric",
        "facade_rhythm": "regular",
        "horizontality": "balanced",
        "verticality": "balanced",
        "color_palette": ["cream", "beige"],
        "dominant_tones": ["light neutral"],
        "entrance_hierarchy": "central",
        "facade_depth": "deep_relief",
        "window_frame_language": "recessed",
        "visible_floor_count": 2,
        "balconies": {"present": False},
        "evidence": ["The facade is clad in light stone."],
        "uncertainties": ["exact stone type"],
        "unsupported_inferences": [],
        "perspective_limitations": ["frontal view only"],
        "occlusions": [],
    }

    payload.update(overrides)

    return payload


def _pair(a=None, b=None):
    return {
        "A": a if a is not None else _analysis(),
        "B": b
        if b is not None
        else _analysis(
            style="vernacular_brick",
            materials=(
                ("brick", "Red brick infill"),
                ("concrete", "Grey concrete frame"),
            ),
        ),
        "roles": {
            "A": "facade_reference",
            "B": "target_building",
            "geometry_authority": "target_building",
        },
    }


def _facets(entries):
    return [entry["facet"] for entry in entries]


# ==========================================================
# 1 — THE COMPARISON IS GROUNDED IN THE CONTRACT
# ==========================================================

def test_comparison_contract_identity_and_no_render():
    comparison = build_comparison(_pair(), user_text="Compare these two.")

    assert comparison["contract"] == CONTRACT
    assert comparison["status"] == "compared"
    assert comparison["provenance"]["analysis_only"] is True
    assert comparison["provenance"]["render_executed"] is False
    assert comparison["roles"]["geometry_authority"] == "target_building"


def test_style_and_materials_are_asserted_as_differences():
    comparison = build_comparison(_pair())

    differing = _facets(comparison["differences"])

    assert "style" in differing
    assert "materials" in differing

    materials = next(
        entry for entry in comparison["differences"] if entry["facet"] == "materials"
    )

    assert "travertine_like_stone" in materials["A"]
    assert "brick" in materials["B"]
    assert materials["source_fields"] == ["materials"]


def test_every_difference_names_its_source_fields():
    comparison = build_comparison(_pair())

    for entry in comparison["differences"]:
        assert entry["source_fields"], entry
        assert entry["A"] and entry["B"], entry


def test_shared_facet_is_not_reported_as_a_difference():
    comparison = build_comparison(_pair())

    assert "floors" in _facets(comparison["shared"])
    assert "floors" not in _facets(comparison["differences"])


def test_one_sided_facet_is_not_comparable_not_a_difference():
    """A value on only one side must never be sold as a measured change."""

    a = _analysis()
    b = _analysis(style="vernacular_brick", visible_floor_count=None)

    comparison = build_comparison(_pair(a=a, b=b))

    assert "floors" in _facets(comparison["not_comparable"])
    assert "floors" not in _facets(comparison["differences"])


def test_absent_element_is_reported_as_absent():
    comparison = build_comparison(_pair())

    arches = next(
        entry
        for entry in comparison["differences"] + comparison["shared"]
        if entry["facet"] == "arches"
    )

    assert arches["A"] == "absent"


# ==========================================================
# 2 — A FAILED ANALYSIS IS REPORTED TRUTHFULLY
# ==========================================================

def test_both_sides_unusable_is_analysis_unavailable():
    pair = {
        "A": {"analysis_status": "PROVIDER_UNAVAILABLE"},
        "B": {"analysis_status": "FAILED"},
        "roles": {},
    }

    comparison = build_comparison(pair)

    assert comparison["status"] == "analysis_unavailable"
    assert comparison["differences"] == []
    assert comparison["a_analyzed"] is False
    assert comparison["b_analyzed"] is False

    text = render_comparison(comparison, language="en")

    # The images WERE received; the failure is the analysis stage.
    assert "analysis stage" in text
    assert "I don't see" not in text


def test_empty_analysis_pair_is_analysis_unavailable():
    comparison = build_comparison({})

    assert comparison["status"] == "analysis_unavailable"


def test_single_usable_side_is_partial_and_asserts_no_difference():
    pair = {
        "A": _analysis(),
        "B": {"analysis_status": "FAILED"},
        "roles": {},
    }

    comparison = build_comparison(pair)

    assert comparison["status"] == "partial"
    assert comparison["differences"] == []


# ==========================================================
# 3 — RENDERING
# ==========================================================

def test_render_is_grounded_and_carries_evidence():
    text = render_comparison(build_comparison(_pair()), language="en")

    assert "WHAT DIFFERS" in text
    assert "travertine_like_stone" in text
    assert "brick" in text
    assert "The facade is clad in light stone." in text
    assert "No render was executed" in text


def test_render_persian_uses_persian_headings():
    text = render_comparison(build_comparison(_pair()), language="fa")

    assert "تفاوت‌ها" in text
    assert "WHAT DIFFERS" not in text


def test_render_language_defaults_to_the_user_text_script():
    text = render_comparison(build_comparison(_pair(), user_text="این دو تصویر را مقایسه کن"))

    assert "تفاوت‌ها" in text


def test_render_mentions_uncertainty_without_claiming_certainty():
    text = render_comparison(build_comparison(_pair()), language="en")

    assert "LIMITS OF THIS COMPARISON" in text
    assert "exact stone type" in text


# ==========================================================
# 4 — THE MODULE IS A PROJECTION, NOT AN ENGINE
# ==========================================================

def test_module_calls_no_provider_and_no_render():
    """The projection may reuse a pure local classifier, nothing else."""

    source = open(
        os.path.join(ROOT, "core", "vision", "dual_image_comparison_v1.py"),
        encoding="utf-8",
    ).read()

    tree = ast.parse(source)

    imported = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = (
        "requests",
        "ollama",
        "core.render",
        "core.runtime",
        "core.vision.vision_provider_ollama_v1",
    )

    for name in imported:
        assert not any(name == item or name.startswith(item + ".") for item in forbidden), name

    assert imported <= {"core.vision.site_object_classification_v1"}, imported


# ==========================================================
# 5 — REAL EVIDENCE FROM THE LIVE V3 RUN
# ==========================================================

@pytest.mark.skipif(
    not os.path.exists(LIVE_COMPARISON),
    reason="live V3 comparison artifact not present",
)
def test_live_artifact_now_produces_a_grounded_comparison():
    """The exact contract that answered 'no images attached' must now answer."""

    payload = json.load(open(LIVE_COMPARISON, encoding="utf-8"))

    analysis_ab = payload["response"]["response"]["render_handoff"][
        "reference_architectural_analysis_ab"
    ]

    comparison = build_comparison(
        analysis_ab,
        user_text="Compare these two building photographs and tell me the main "
        "differences in style and materials.",
    )

    assert comparison["status"] == "compared"
    assert comparison["a_analyzed"] and comparison["b_analyzed"]

    differing = _facets(comparison["differences"])

    assert "style" in differing
    assert "materials" in differing

    text = render_comparison(comparison, language="en")

    assert "neoclassical" in text
    assert "travertine_like_stone" in text
    assert "brick" in text
    assert "concrete" in text
    assert "photographs attached" not in text


# ==========================================================
# 6 — THE RESPONSE CONTRACT
# ==========================================================

def test_adapter_renders_image_comparison_as_text():
    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    comparison = build_comparison(_pair())

    result = {
        "type": "image_comparison",
        "engine": "vision+dual_image_comparison",
        "result": comparison,
        "comparison": comparison,
        "message": render_comparison(comparison, language="en"),
        "status": "success",
        "language": {"input_language": "english", "output_language": "english"},
    }

    adapted = adapter.adapt(result)

    assert adapted["type"] == "image_comparison"
    assert isinstance(adapted["result"], str)
    assert "WHAT DIFFERS" in adapted["result"]
    assert adapted["comparison"]["contract"] == CONTRACT
    assert adapted["result_structured"]["contract"] == CONTRACT


def test_chat_architect_pair_answer_returns_the_contract_without_rendering():
    from core.chat.chat_architect import ChatArchitect

    response = ChatArchitect._answer_about_image_pair(
        None,
        "Compare these two building photographs.",
        _pair(),
        {"contract": "RenderHandoffTraceV1"},
    )

    assert response["type"] == "image_comparison"
    assert response["status"] == "success"
    assert response["comparison"]["provenance"]["render_executed"] is False
    assert response["render_handoff"] == {"contract": "RenderHandoffTraceV1"}

    # No render surface is produced by this reply path.
    assert "outputs" not in response
    assert "image" not in response


def test_chat_architect_pair_answer_is_persian_for_persian_text():
    from core.chat.chat_architect import ChatArchitect

    response = ChatArchitect._answer_about_image_pair(
        None,
        "این دو تصویر را از نظر سبک و مصالح مقایسه کن.",
        _pair(),
    )

    assert response["language"]["output_language"] == "persian"
    assert "تفاوت‌ها" in response["message"]


# ==========================================================
# 7 — THE ROUTING WIRING (order matters)
# ==========================================================

def test_dual_pair_branch_precedes_the_generic_chat_branch():
    """The pair must be answered BEFORE the evidence-free chat branch."""

    path = os.path.join(ROOT, "core", "chat", "chat_architect.py")

    tree = ast.parse(open(path, encoding="utf-8").read())

    handler = None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_internal":
            handler = node
            break

    assert handler is not None

    def _names(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}

    dual_line = None
    chat_line = None

    for node in handler.body:
        if not isinstance(node, ast.If):
            continue

        names = _names(node.test)

        if (
            "_verified_dual_pair" in names
            and "intent" in names
            and dual_line is None
        ):
            dual_line = node.lineno
        elif (
            "intent" in names
            and chat_line is None
            and any(
                isinstance(n, ast.Constant) and n.value == "conversation"
                for n in ast.walk(node.test)
            )
        ):
            chat_line = node.lineno

    assert dual_line is not None, "dual-pair branch missing"
    assert chat_line is not None, "generic chat branch missing"
    assert dual_line < chat_line, (dual_line, chat_line)

    branch = next(
        node
        for node in handler.body
        if isinstance(node, ast.If) and node.lineno == dual_line
    )

    returns = [
        node
        for node in ast.walk(branch)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_answer_about_image_pair"
    ]

    assert returns, "dual-pair branch does not answer from the A/B evidence"
