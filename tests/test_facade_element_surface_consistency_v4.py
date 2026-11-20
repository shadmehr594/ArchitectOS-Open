"""FACADE_STYLE_TRANSFER_READINESS_V4 — surface vs structural consistency.

The final assembled prompt contained BOTH:

  compiler : "REQUIRED ARCHITECTURAL ELEMENTS — include …; each must be
              correctly proportioned, STRUCTURALLY SUPPORTED and integrated
              into the facade RATHER THAN APPLIED AS SURFACE DECORATION."

  builder  : "Apply classical detailing as a SURFACE treatment only."

The user asked for applied cornices, shallow pilaster-like relief and stone
window surrounds WITHOUT changing the building geometry. The two sentences tell
the model to do opposite things.

Drives the REAL compiler. No LLM, no GPU, no ComfyUI.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.prompt_intelligence.architectural_prompt_compiler_v1 import (  # noqa: E402
    ArchitecturalPromptCompiler,
)


def _facade_restyle_understanding():
    """An existing building whose geometry is preserved (the accepted case)."""

    return {
        "scope": "facade",
        "style": {"target": "neoclassical", "intensity": {"level": "MEDIUM"}},
        "materials": {"primary": "light_ivory_natural_stone", "tone": "cream"},
        "elements": ["cornices", "sculptural relief"],
        "preserve_constraints": {"reference_geometry": True},
        "reference_image_policy": {
            "referenced": True,
            "preserve_base_geometry": True,
        },
        "change_operations": [{"operation": "replace", "target": "facade"}],
        "entrance": {"position": None},
    }


def _structural_understanding():
    """A request that genuinely changes the building, not just its surface."""

    understanding = _facade_restyle_understanding()
    understanding["reference_image_policy"] = {"referenced": False}
    understanding["preserve_constraints"] = {}
    return understanding


def _elements(understanding):
    return " ".join(
        ArchitecturalPromptCompiler()._compile_elements(understanding)
    ).lower()


# ==========================================================
# R1 / R2 — the contradiction must go
# ==========================================================


def test_R1_surface_elements_are_not_demanded_to_be_structural():
    text = _elements(_facade_restyle_understanding())

    assert "structurally supported" not in text, text
    assert "rather than applied as surface decoration" not in text, text


def test_R2_surface_elements_are_described_as_applied_treatment():
    text = _elements(_facade_restyle_understanding())

    assert "surface" in text, text
    assert "wall plane" in text or "existing" in text, text


def test_R2b_the_elements_are_still_required():
    text = _elements(_facade_restyle_understanding())

    assert "required architectural elements" in text
    assert "cornice" in text


# ==========================================================
# R3 — genuine structural requests keep their wording
# ==========================================================


def test_R3_structural_requests_keep_the_structural_wording():
    text = _elements(_structural_understanding())

    assert "structurally supported" in text, text


# ==========================================================
# R4 — consistency with the builder's own instruction
# ==========================================================


def test_R4_no_surface_versus_structural_contradiction():
    elements = _elements(_facade_restyle_understanding())

    # the compiler must not demand structure while the builder demands surface
    assert not (
        "structurally supported" in elements
        and "surface" in elements
    ), elements


# ==========================================================
# R5 / R6 — earlier fixes must survive
# ==========================================================


def test_R5_prohibited_elements_stay_excluded():
    understanding = _facade_restyle_understanding()
    understanding["elements"] = ["columns", "cornices"]
    understanding["negative_constraints"] = [
        {"constraint": "Do not copy the reference's arches or protruding columns."}
    ]

    text = _elements(understanding)

    assert "columns" not in text
    assert "cornice" in text


def test_R6_no_elements_means_no_sentence():
    understanding = _facade_restyle_understanding()
    understanding["elements"] = []

    assert ArchitecturalPromptCompiler()._compile_elements(understanding) == []
