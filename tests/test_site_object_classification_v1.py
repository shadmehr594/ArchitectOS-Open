# ==========================================================
# ArchitectOS — SITE_OBJECT_CLASSIFICATION_V1
#
# Regression tests for the verified handoff gap (V4 §6 / V4.1 §4):
#
#   Vision reported `occlusions: ["scaffolding", "debris"]` and
#   NOTHING consumed it. The render instruction therefore never
#   distinguished the worksite from the building, and the measured
#   output kept the scaffolding while losing the curved balconies.
#
# The cases drive the REAL classifier, the REAL instruction builder
# and the REAL comparison reply. The only recorded input is the
# analysis contract from the live V3 run.
#
# NO GPU. NO COMFYUI. NO NETWORK. NO DETECTOR.
# ==========================================================

import ast
import json
import os

import pytest

from core.vision.site_object_classification_v1 import (
    CONTRACT,
    classify_site_objects,
    request_wants_finished_building,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIVE_ANALYSIS = os.path.join(
    ROOT, "runs", "architectos_product_integration_v3", "p3b_response.json"
)


def _target_analysis():
    payload = json.load(open(LIVE_ANALYSIS, encoding="utf-8"))

    return payload["response"]["response"]["render_handoff"][
        "reference_architectural_analysis_ab"
    ]["B"]


def _analysis(occlusions=(), evidence=(), roof_features=(), balconies=None,
              balcony_language=None):
    return {
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "occlusions": list(occlusions),
        "evidence": list(evidence),
        "roof_features": list(roof_features),
        "balconies": balconies or {"present": True},
        "balcony_language": balcony_language,
        "visible_floor_count": 4,
        "symmetry": "symmetric",
        "windows": {"rhythm": "regular"},
    }


# ==========================================================
# 1 — THE CLASSIFIER
# ==========================================================

def test_real_worksite_objects_are_temporary_not_architecture():
    classification = classify_site_objects(_target_analysis())

    phrases = [
        entry["phrase"].lower()
        for entry in classification["temporary_objects"]
    ]

    assert any("scaffold" in phrase for phrase in phrases)
    assert any("debris" in phrase for phrase in phrases)


def test_scaffolding_is_never_classified_as_architecture():
    classification = classify_site_objects(
        _analysis(occlusions=["scaffolding covers the left wing"])
    )

    architectural = (
        classification["permanent_geometry"] + classification["permanent_details"]
    )

    assert all("scaffold" not in entry["phrase"].lower() for entry in architectural)


def test_a_curved_balcony_is_never_classified_as_temporary():
    classification = classify_site_objects(
        _analysis(evidence=["A curved concrete balcony slab projects from the second floor."])
    )

    temporary = [entry["phrase"].lower() for entry in classification["temporary_objects"]]

    assert all("balcony" not in phrase for phrase in temporary)
    assert any(
        "balcony" in entry["phrase"].lower()
        for entry in classification["permanent_geometry"]
    )


def test_an_unrecognised_phrase_stays_uncertain():
    classification = classify_site_objects(
        _analysis(evidence=["A mysterious glimmering object stands near the gate."])
    )

    assert any(
        "mysterious glimmering object" in entry["phrase"].lower()
        for entry in classification["uncertain"]
    )


def test_site_context_is_separated_from_the_building():
    classification = classify_site_objects(
        _analysis(evidence=["An existing tree stands beside the retaining wall."])
    )

    context = [entry["phrase"].lower() for entry in classification["site_context"]]

    assert any("tree" in phrase for phrase in context)


def test_classification_reports_its_own_method():
    classification = classify_site_objects(_target_analysis())

    assert classification["contract"] == CONTRACT
    assert classification["detector_used"] is False
    assert classification["image_opened"] is False
    assert classification["provider_calls"] == 0
    assert classification["classification_method"] == (
        "lexical_projection_over_reported_strings"
    )


def test_the_module_imports_nothing():
    path = os.path.join(ROOT, "core", "vision", "site_object_classification_v1.py")

    tree = ast.parse(open(path, encoding="utf-8").read())

    imported = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported == set(), imported


# ==========================================================
# 2 — INTENT
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "Visualize the finished building with the new facade.",
        "Show me the completed building.",
        "Remove the scaffolding and render the final facade.",
        "نمای نهایی و تکمیل‌شده را رندر کن.",
    ],
)
def test_an_explicit_finish_request_is_detected(text):
    wanted, evidence = request_wants_finished_building(text)

    assert wanted is True
    assert evidence and evidence.startswith("finished_request:")


@pytest.mark.parametrize(
    "text",
    [
        "Apply this facade style to the building.",
        "Show me the building as it is now.",
        "Change the cladding material to travertine.",
        "",
    ],
)
def test_an_ambiguous_request_never_authorises_removal(text):
    wanted, _ = request_wants_finished_building(text)

    assert wanted is False


# ==========================================================
# 3 — THE INSTRUCTION CONSUMES IT
# ==========================================================

def _instruction(text, analysis_b):
    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    return build_render_instruction(
        text,
        reference_analysis_ab={"A": _analysis(), "B": analysis_b,
                               "roles": {"A": "facade_reference",
                                         "B": "target_building"}},
    )


def test_instruction_names_the_temporary_objects():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(occlusions=["scaffolding", "debris on ground"]),
    )

    instruction = result["english_instruction"].lower()

    assert "temporary construction objects" in instruction
    assert "scaffolding" in instruction
    assert "debris" in instruction


def test_ambiguous_request_keeps_the_objects_as_observed():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(occlusions=["scaffolding"]),
    )

    instruction = result["english_instruction"]

    assert "does not ask for the finished building" in instruction
    assert "do not remove them" in instruction
    assert result["site_objects"]["finished_request"] is False


def test_finished_request_authorises_removal_explicitly():
    result = _instruction(
        "Visualize the finished building.",
        _analysis(occlusions=["scaffolding"]),
    )

    instruction = result["english_instruction"]

    assert "asks for the FINISHED building" in instruction
    assert "do not reproduce" in instruction
    assert result["site_objects"]["finished_request"] is True


def test_the_acceptance_rule_is_a_hard_constraint():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(occlusions=["scaffolding"]),
    )

    constraints = " ".join(result["hard_constraints"]).lower()

    assert "never architectural features" in constraints
    assert "do not remove a permanent" in constraints


def test_instruction_reports_the_classification_for_audit():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(occlusions=["scaffolding", "debris"]),
    )

    site = result["site_objects"]

    assert site["contract"] == CONTRACT
    assert site["counts"]["temporary_objects"] >= 2


# ==========================================================
# 4 — CURVED GEOMETRY IS CARRIED AS SHAPE, NOT PRESENCE
# ==========================================================

def test_curved_target_produces_a_shape_constraint():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(roof_features=["curved parapets"], balcony_language="curved balcony slabs"),
    )

    instruction = result["english_instruction"].lower()

    assert "curved architectural forms" in instruction
    assert "do not straighten" in instruction


def test_a_straight_target_gets_no_curve_constraint():
    result = _instruction(
        "Apply this facade style to the building.",
        _analysis(roof_features=["flat roofline"], balcony_language=None),
    )

    assert "curved architectural forms" not in result["english_instruction"].lower()


# ==========================================================
# 5 — THE COMPARISON REPLY REPORTS THEM FAITHFULLY
# ==========================================================

@pytest.mark.skipif(not os.path.exists(LIVE_ANALYSIS), reason="live artifact absent")
def test_comparison_reply_reports_temporary_objects():
    from core.vision.dual_image_comparison_v1 import (
        build_comparison,
        render_comparison,
    )

    comparison = build_comparison(
        {
            "A": _analysis(),
            "B": _target_analysis(),
            "roles": {"A": "facade_reference", "B": "target_building"},
        },
        user_text="Compare these two building photographs.",
    )

    assert comparison["site_objects"]["B"]["counts"]["temporary_objects"] >= 1

    text = render_comparison(comparison, language="en")

    assert "TEMPORARY OBJECTS AND SITE CONTEXT" in text
    assert "scaffolding" in text.lower()
