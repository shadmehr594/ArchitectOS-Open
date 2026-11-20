"""FACADE_STYLE_TRANSFER_FAILURE_CORRECTION_V1 — RED tests.

Reproduces the material contradiction that produced a brick facade for a
cream-stone request.

MEASURED DEFECT (job ff38a9d2, node 206):
    terminology_terms = [..., "material", "stone", "brick", "travertine", ...]
and the final prompt carried "... the base., material, brick, natural lighting".

`brick` was claimed as a REQUESTED material because the request contains
"the approved beige-brick residential building" — a DESCRIPTION of the target
building. The same request forbids brick twice:
    "not a brick facade recolored beige"
    "No red/orange brick redesign"

`_is_negated()` requires EVERY occurrence to sit in a negation window, so the
descriptive mention alone un-forbids the material.

These tests drive the REAL production extractor. No GPU, no ComfyUI, no LLM.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.cognition.architectural_terminology_v1 import extract_terms  # noqa: E402

PACK = os.path.join(
    ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1"
)
REQUEST = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")


def _request():
    with open(REQUEST, encoding="utf-8") as fh:
        return fh.read().strip()


def _terms(text):
    return extract_terms(text)["canonical_terms"]


# ==========================================================
# R1 — the real request must not request brick
# ==========================================================


def test_R1_the_real_request_does_not_request_brick():
    terms = _terms(_request())

    assert "brick" not in terms, (
        "the request forbids brick twice but brick was claimed as a requested "
        f"material: {terms}"
    )


def test_R1b_the_real_request_still_requests_stone():
    terms = _terms(_request())

    assert "stone" in terms
    assert "travertine" in terms


# ==========================================================
# R2 — a hyphenated descriptor is not a request
# ==========================================================


def test_R2_hyphenated_descriptor_is_not_a_material_request():
    terms = _terms("The approved beige-brick residential building must be redone.")

    assert "brick" not in terms


def test_R2b_plain_descriptor_is_also_not_a_request_when_forbidden():
    text = (
        "This is a brick building. Do not keep the brick; use cream stone instead."
    )
    terms = _terms(text)

    assert "brick" not in terms
    assert "stone" in terms


# ==========================================================
# R3/R4 — genuine affirmative requests must survive
# ==========================================================


def test_R3_an_affirmative_brick_request_is_preserved():
    terms = _terms("Redesign the facade with warm red brick cladding.")

    assert "brick" in terms


def test_R4_mixed_prohibition_keeps_the_affirmative_part():
    terms = _terms(
        "Do not use brick on the ground floor; use brick on the upper floors."
    )

    assert "brick" in terms


# ==========================================================
# R5 — existing negation behaviour must not regress
# ==========================================================


def test_R5_existing_negation_behaviour_is_unchanged():
    terms = _terms("true night, not dusk")

    assert "night lighting" in terms
    assert "dusk lighting" not in terms


def test_R5b_existing_affirmative_behaviour_is_unchanged():
    terms = _terms("warm exterior facade with natural lighting")

    assert "exterior space" in terms
    assert "natural lighting" in terms


# ==========================================================
# R6 — the compiled tag tail must be materially coherent
# ==========================================================


def test_R6_tag_tail_does_not_carry_brick():
    """The tail is what node 206 ends with: '..., material, brick, ...'."""

    terms = _terms(_request())
    tail = ", ".join(terms)

    assert "brick" not in tail, f"tag tail still carries brick: {tail}"
