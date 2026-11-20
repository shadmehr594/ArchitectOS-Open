"""FACADE_FULL_PROMPT_SEMANTIC_CONSISTENCY_V1 — complete-instruction tests.

The contract-only tests (test_facade_redesign_geometry_appearance_contract_v1)
proved the structured contract is right. They could not see the SECOND
preservation block that the legacy builder appends to the same instruction.

These tests assert on the COMPLETE final instruction, over product-authored
text only (the user's verbatim request is excluded from the scan, because the
user is allowed to say whatever they like).

No GPU, no ComfyUI, no Ollama, no inference.
"""

import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.prompt_intelligence.image_edit_prompt_builder import (  # noqa: E402
    ImageEditPromptBuilder,
)

import _fpsc_capture_v1 as fpsc  # noqa: E402

RECORDED_PROMPT = os.path.join(ROOT, "runs", "dual_render_v5", "node206_submitted.txt")
PREFIX_CAPTURE = os.path.join(
    ROOT, "runs", "facade_redesign_contract_v1", "final_prompt.txt"
)
GOLDEN = os.path.join(
    ROOT, "runs", "facade_full_prompt_v1", "builder_golden_pre_change.json"
)

CONTRACT_MARKER = "ArchitecturalPreservationContractV1"


def _norm(text):
    return " ".join(str(text).split())


@pytest.fixture(scope="module")
def built():
    return fpsc.build_prompt()


@pytest.fixture(scope="module")
def final(built):
    return built["final"]


@pytest.fixture(scope="module")
def product_text(final, built):
    return final.replace(_norm(built["request_text"]), "")


def _intent(design_context=None, edit_class="style_change", user=None):
    intent = {
        "_user_prompt": user
        or "Redesign the facade of this building in a neoclassical style with cream travertine.",
        "architectural_intent": {
            "request_type": "facade",
            "building_type": "residential",
            "style": "neoclassical",
            "materials": ["light ivory natural stone"],
            "preserve_geometry": True,
            "normalized_prompt": "Redesign the facade in neoclassical style.",
        },
        "edit_delta": {"edit_class": edit_class},
    }
    if design_context is not None:
        intent["design_context"] = design_context
    return intent


def _with_contract(text=None):
    return {
        "design": {
            "compiled_render_prompt": (
                "USER REQUEST (verbatim, authoritative): x "
                "ARCHITECTURAL PRESERVATION CONTRACT "
                "(" + CONTRACT_MARKER + "): PRESERVE EXACTLY: ..."
            )
            + (" " + text if text else ""),
            # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — the builder now keys on
            # the structured contract OBJECT as provenance, not on the rendered
            # header text (which a user request could reproduce verbatim).
            "r4_preservation_contract": {
                "contract": CONTRACT_MARKER,
                "preserve": [
                    "the existing building massing and overall silhouette"
                ],
            },
        }
    }


# ==========================================================
# T01–T06 — GEOMETRY FIXED IN THE COMPLETE INSTRUCTION
# ==========================================================


def test_T01_user_request_is_preserved_verbatim(final, built):
    assert _norm(built["request_text"]) in final


def test_T02_original_building_massing_is_fixed(product_text):
    lowered = product_text.lower()
    assert "massing" in lowered
    assert "silhouette" in lowered


def test_T03_four_storeys_are_fixed(product_text):
    assert "storey count" in product_text.lower()


def test_T04_opening_locations_and_dimensions_are_fixed(product_text):
    lowered = product_text.lower()
    assert "positions and dimensions of the existing window openings" in lowered
    assert "positions and dimensions of the existing door openings" in lowered


def test_T05_opening_count_is_fixed(product_text):
    assert (
        "do not add, remove, resize or relocate any window, door or opening"
        in product_text.lower()
    )


def test_T06_primary_balcony_structural_geometry_is_fixed(product_text):
    assert (
        "balcony positions and their structural projection geometry"
        in product_text.lower()
    )


# ==========================================================
# T07–T11 — APPEARANCE EDITABLE IN THE COMPLETE INSTRUCTION
# ==========================================================


def test_T07_railing_appearance_is_editable(product_text):
    assert "railing appearance: railing or balustrade design" in product_text.lower()


def test_T08_window_frame_appearance_is_editable(product_text):
    assert "window frame appearance: frame design" in product_text.lower()


def test_T09_door_appearance_is_editable(product_text):
    assert "door appearance: door leaf design" in product_text.lower()


def test_T10_facade_materials_are_editable(product_text):
    assert "facade material: cladding material" in product_text.lower()


def test_T11_applied_neoclassical_ornament_is_allowed(product_text):
    lowered = product_text.lower()
    assert "applied ornament: cornices" in lowered
    # The legacy ban on introducing architectural elements is scoped to
    # geometry now, so it no longer forbids the cornices.
    for clause in re.findall(r"do not invent[^.]{0,160}", lowered):
        assert "volume" in clause or "opening" in clause or "structural" in clause


# ==========================================================
# T12–T13 — NO SECOND, CONTRADICTORY PRESERVATION BLOCK
# ==========================================================


def test_T12_no_second_legacy_instruction_freezes_editable_appearance(product_text):
    lowered = product_text.lower()

    assert "geometry preservation" not in lowered
    assert "terraces" not in lowered
    assert "existing terraces, balconies, stairs and railings" not in lowered
    assert "entrance location and design" not in lowered

    for pattern in (
        r"preserv\w*[^.]{0,80}\brailings?\b",
        r"preserv\w*[^.]{0,80}\bwindow frames?\b",
        r"preserv\w*[^.]{0,80}\bdoor (?:leaf|design)\b",
    ):
        assert not re.search(pattern, product_text, re.I), pattern


def test_T13_exactly_one_preserve_block_in_product_text(product_text):
    assert product_text.count("PRESERVE EXACTLY") == 1


def test_T13b_full_contradiction_scan_is_clean(final, built):
    result = fpsc.scan(final, built["request_text"])

    assert result["clean"] is True, result["contradictions"]
    assert result["preserve_exactly_count"] == 1


def test_T13c_the_defect_was_real_in_the_prefix_capture():
    """Permanent record: the 9,506-char pre-fix capture DID contradict itself."""

    assert os.path.isfile(PREFIX_CAPTURE), "pre-fix capture evidence missing"

    text = open(PREFIX_CAPTURE, encoding="utf-8").read()
    request_text = json.load(
        open(
            os.path.join(ROOT, "runs", "live_handoff_v1", "recorded_understanding.json"),
            encoding="utf-8",
        )
    )["request_text"]

    result = fpsc.scan(_norm(text), request_text)

    assert result["clean"] is False
    assert result["preserve_exactly_count"] == 2
    rules = {hit["rule"] for hit in result["contradictions"]}
    assert "legacy geometry header" in rules
    assert "legacy circulation noun" in rules
    assert "legacy railings preservation" in rules


# ==========================================================
# T14–T16 — PRECEDENCE AND ROLES
# ==========================================================


def test_T14_explicit_user_preservation_remains_authoritative():
    contract = fpsc.contract_for(
        "Redesign this facade in neoclassical style with cream travertine, "
        "but keep the existing railings exactly as they are."
    )

    domains = {e["domain"] for e in contract["appearance_preserved"]}
    editable = {e["domain"] for e in contract["appearance_editable"]}

    assert "railing_appearance" in domains
    assert "railing_appearance" not in editable
    assert "facade_material" in editable


def test_T15_material_only_does_not_permit_style_redesign():
    contract = fpsc.contract_for(
        "Replace only the brick cladding material with cream travertine.",
        edit_class="material_change",
    )

    editable = {e["domain"] for e in contract["appearance_editable"]}

    assert editable == {"facade_material"}


def test_T16_target_and_style_roles_are_correct(final):
    assert "TARGET_BUILDING" in final
    assert "STYLE_REFERENCE" in final

    own = final.split("ARCHITECTURAL PRESERVATION CONTRACT", 1)[-1]
    assert "IMAGE A" not in own
    assert "IMAGE B" not in own


# ==========================================================
# T17–T18 — THE PRODUCTION CHANGE, AT ITS OWNER
# ==========================================================


def test_T17_without_structured_contract_the_legacy_block_is_emitted():
    """Sensitivity: the legacy block is still there for every other route."""

    prompt = _norm(ImageEditPromptBuilder().build(_intent()))

    assert "GEOMETRY PRESERVATION" in prompt
    assert "existing terraces, balconies, stairs and railings" in prompt
    assert prompt.count("PRESERVE EXACTLY") == 1


def test_T18_with_structured_contract_the_legacy_block_is_suppressed():
    without = _norm(ImageEditPromptBuilder().build(_intent()))
    with_contract = _norm(
        ImageEditPromptBuilder().build(_intent(design_context=_with_contract()))
    )

    assert "GEOMETRY PRESERVATION" not in with_contract
    assert "terraces" not in with_contract
    assert with_contract.count("PRESERVE EXACTLY") == 0

    # The sections that carry content the contract does not are kept.
    assert "FACADE TRANSFORMATION" in with_contract
    assert "ARCHITECTURAL VISUALIZATION QUALITY" in with_contract

    # And nothing ELSE changed: removing the geometry section from the
    # no-contract output reproduces the contract-present output exactly.
    section = fpsc.GEOMETRY_SECTION_RE.search(without)
    assert section, "legacy section not found in the no-contract output"
    assert _norm(fpsc.GEOMETRY_SECTION_RE.sub("", without)) == with_contract


def test_T18b_generic_builder_output_is_unchanged_for_other_routes():
    """The pre-change goldens still reproduce byte-for-byte."""

    assert os.path.isfile(GOLDEN), "pre-change golden missing"

    golden = json.load(open(GOLDEN, encoding="utf-8"))

    cases = {
        "style_restyle": _intent(),
        "material_only": {
            "_user_prompt": "Replace only the brick cladding material with cream travertine.",
            "architectural_intent": {
                "request_type": "facade",
                "materials": ["cream travertine"],
                "preserve_geometry": True,
                "normalized_prompt": (
                    "Replace only the brick cladding material with cream travertine."
                ),
            },
            "edit_delta": {"edit_class": "material_change"},
        },
        "lighting": {
            "_user_prompt": "Make this a night scene.",
            "architectural_intent": {
                "request_type": "facade",
                "normalized_prompt": "night scene",
            },
            "edit_delta": {"edit_class": "lighting_change"},
        },
    }

    for name, intent in cases.items():
        prompt = _norm(ImageEditPromptBuilder().build(intent))
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        assert digest == golden[name]["sha256"], name


# ==========================================================
# T19 — NO SUBMISSION EDGE
# ==========================================================


def test_T19_no_gpu_or_comfyui_submission(monkeypatch):
    import core.comfy_client as comfy

    def _boom(*_a, **_k):
        raise AssertionError("no ComfyUI client may be constructed")

    for name in ("ComfyClient", "ComfyUIClient"):
        if hasattr(comfy, name):
            monkeypatch.setattr(comfy, name, _boom)

    prompt = _norm(ImageEditPromptBuilder().build(_intent(design_context=_with_contract())))

    assert "FACADE TRANSFORMATION" in prompt
