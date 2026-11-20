"""LIVE_FACADE_CONTRACT_PROPAGATION_FIX_V1 — real-route regression tests.

These tests drive the REAL production route:

    PromptRouter.build(prompt_input, mode)
        -> ImageEditPromptBuilder.build(intent)
        -> resolve_render_prompt(...)

Nothing here applies a regex suppression itself or fabricates builder output.
The harness only reconstructs the INPUT from the recorded V5 case.

CPU ONLY. No GPU, no ComfyUI, no Ollama, no live vision.
"""

import re

import pytest

import _lfcp_capture_v1 as lfcp


CONTRACT_MARKER = "ArchitecturalPreservationContractV1"

GEOMETRY_REQUIRED = (
    "building massing",
    "silhouette",
    "storey count",
    "positions and dimensions of the existing window openings",
    "do not add, remove, resize or relocate any window, door or opening",
    "balcony positions and their structural projection geometry",
    "roofline, roof shape and parapet",
    "camera position, framing, perspective",
)

APPEARANCE_REQUIRED = (
    "facade material",
    "architectural style",
    "window frame appearance",
    "door appearance",
    "railing appearance",
    "balcony surface finish",
    "applied ornament",
)

FORBIDDEN_IN_PRODUCT_TEXT = (
    "GEOMETRY PRESERVATION",
    "existing terraces",
    "stairs and railings",
    "every building element the user did not explicitly ask",
    "entrance location and design",
)


@pytest.fixture(scope="module")
def data():
    return lfcp.capture()


def _by_name(data, name):
    for record in data["scenarios"]:
        if record["scenario"] == name:
            return record
    raise AssertionError("scenario not captured: %s" % name)


# ==========================================================
# T01–T05 — PROPAGATION REACHES THE REAL BUILDER
# ==========================================================


def test_T01_real_router_forwards_design_context(data):
    record = _by_name(data, "D_facade_redesign")
    assert record["builder_received"]["has_design_context"] is True
    assert record["builder_received"]["design_context_is_dict"] is True
    assert record["builder_received"]["has_compiled_render_prompt"] is True


def test_T02_builder_received_keys_carry_the_carrier(data):
    keys = _by_name(data, "D_facade_redesign")["builder_received"]["keys"]
    assert "design_context" in keys
    # The rebuild must still keep the original intent and the user prompt.
    assert "_user_prompt" in keys
    assert "building_type" in keys


def test_T03_suppression_fires_on_the_real_route(data):
    record = _by_name(data, "D_facade_redesign")
    assert record["builder_scan"]["contradictions"] == []
    assert "GEOMETRY PRESERVATION" not in record["builder_prompt"]
    assert "existing terraces" not in record["builder_prompt"].lower()


def test_T04_exactly_one_preservation_block_in_final_prompt(data):
    record = _by_name(data, "D_facade_redesign")
    assert record["final_scan"]["preserve_exactly_count"] == 1


def test_T05_final_prompt_keeps_contract_and_appearance_permission(data):
    record = _by_name(data, "D_facade_redesign")
    assert record["final_has_contract_marker"] is True
    assert record["final_has_appearance_editable"] is True


# ==========================================================
# T06–T07 — NO LEGACY APPEARANCE FREEZE SURVIVES
# ==========================================================


def test_T06_no_legacy_markers_in_final_product_text(data):
    record = _by_name(data, "D_facade_redesign")
    assert record["final_scan"]["contradictions"] == []
    lowered = record["final_prompt"].lower()
    for phrase in FORBIDDEN_IN_PRODUCT_TEXT:
        assert phrase.lower() not in lowered, phrase


def test_T07_no_railing_door_or_window_frame_appearance_freeze(data):
    lowered = _by_name(data, "D_facade_redesign")["final_prompt"].lower()
    for pattern in (
        r"preserv\w*[^.]{0,80}\brailings?\b",
        r"preserv\w*[^.]{0,80}\bwindow frames?\b",
        r"preserv\w*[^.]{0,80}\bdoor (?:leaf|design)\b",
    ):
        assert not re.search(pattern, lowered), pattern


# ==========================================================
# T08–T09 — GEOMETRY FIXED, APPEARANCE EDITABLE
# ==========================================================


def test_T08_geometry_is_still_preserved(data):
    lowered = _by_name(data, "D_facade_redesign")["final_prompt"].lower()
    for phrase in GEOMETRY_REQUIRED:
        assert phrase in lowered, phrase


def test_T09_appearance_is_editable(data):
    lowered = _by_name(data, "D_facade_redesign")["final_prompt"].lower()
    for phrase in APPEARANCE_REQUIRED:
        assert phrase in lowered, phrase


# ==========================================================
# T10–T14 — NEGATIVE CONTROLS
# ==========================================================


def test_T10_A_generic_edit_output_is_byte_identical(data):
    record = _by_name(data, "A_generic_edit")
    assert record["builder_output_unchanged"] is True
    assert record["final_output_unchanged"] is True
    # The legacy block is still the correct output for a non-facade edit.
    assert record["final_scan"]["preserve_exactly_count"] == 1


def test_T11_B_lighting_edit_output_is_byte_identical(data):
    record = _by_name(data, "B_lighting_edit")
    assert record["builder_output_unchanged"] is True
    assert record["final_output_unchanged"] is True


def test_T12_C_material_only_edit_output_is_byte_identical(data):
    record = _by_name(data, "C_material_only")
    assert record["builder_output_unchanged"] is True
    assert record["final_output_unchanged"] is True
    # A material-only request must not acquire facade-redesign permission.
    assert record["final_has_appearance_editable"] is False


def test_T13_D_facade_redesign_is_the_only_changed_route(data):
    changed = [r["scenario"] for r in data["scenarios"] if not r["final_output_unchanged"]]
    assert set(changed) == {"D_facade_redesign", "E_railing_preserve"}


def test_T14_E_explicit_railing_preservation_overrides_freedom(data):
    record = _by_name(data, "E_railing_preserve")
    contract = record["contract"]
    assert "railing_appearance" in [e["domain"] for e in contract["appearance_preserved"]]
    assert "railing_appearance" not in contract["appearance_editable"]
    assert record["final_has_appearance_preserved_by_user"] is True
    assert record["final_scan"]["preserve_exactly_count"] == 1


# ==========================================================
# T15–T17 — THE SAFETY GATE MUST NOT BE BYPASSABLE BY TEXT
# ==========================================================


def test_T15_bare_marker_mention_does_not_bypass_preservation(data):
    record = _by_name(data, "F_marker_mention_no_contract")
    # The carrier IS now present, so only the structural check protects us.
    assert record["builder_received"]["has_design_context"] is True
    # ...and the legacy preservation block is still emitted.
    assert "GEOMETRY PRESERVATION" in record["builder_prompt"]
    assert record["builder_output_unchanged"] is True


def test_T16_text_alone_is_not_provenance():
    """A rendered header without the contract OBJECT must not suppress."""
    from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder

    header = (
        "USER REQUEST (verbatim, authoritative): x "
        "ARCHITECTURAL PRESERVATION CONTRACT (%s): PRESERVE EXACTLY: ..."
        % CONTRACT_MARKER
    )

    def build(design):
        return ImageEditPromptBuilder().build(
            {
                "_user_prompt": "make the windows larger",
                "architectural_intent": {
                    "request_type": "edit",
                    "building_type": "residential",
                    "preserve_geometry": True,
                    "normalized_prompt": "make the windows larger",
                },
                "design_context": {"design": design},
            }
        )

    # Header present, no structured contract -> the legacy block must survive.
    assert "GEOMETRY PRESERVATION" in build({"compiled_render_prompt": header})

    # Malformed contracts are not provenance either.
    for bogus in (
        {"contract": "SomeOtherContractV1", "preserve": ["x"]},
        {"contract": CONTRACT_MARKER},                       # no preserve list
        {"contract": CONTRACT_MARKER, "preserve": []},       # empty preserve
        "not a dict",
        None,
    ):
        out = build(
            {"compiled_render_prompt": header, "r4_preservation_contract": bogus}
        )
        assert "GEOMETRY PRESERVATION" in out, bogus

    # A genuine contract suppresses.
    good = build(
        {
            "compiled_render_prompt": header,
            "r4_preservation_contract": {
                "contract": CONTRACT_MARKER,
                "preserve": ["the existing building massing and overall silhouette"],
            },
        }
    )
    assert "GEOMETRY PRESERVATION" not in good


def test_T16b_full_header_spoof_is_rejected(data):
    """Adversarial request containing the FULL literal header."""
    record = _by_name(data, "H_header_spoof_no_contract")
    assert record["builder_received"]["has_design_context"] is True
    # The legacy preservation block is still emitted: no suppression.
    assert "GEOMETRY PRESERVATION" in record["builder_prompt"]
    assert record["final_output_unchanged"] is True
    assert record["final_scan"]["preserve_exactly_count"] == 1


def test_T16c_the_textual_rules_would_have_been_spoofed():
    """Proves the vulnerability was real, not hypothetical."""
    text = lfcp.scenario_header_spoof()["compiled_render_prompt"]

    # The milestone-3 predicate (bare substring).
    assert CONTRACT_MARKER in text

    # The milestone-5 predicate (literal header).
    header_rule = re.compile(
        r"ARCHITECTURAL\s+PRESERVATION\s+CONTRACT\s*\(\s*"
        + re.escape(CONTRACT_MARKER)
        + r"\s*\)\s*:"
    )
    assert header_rule.search(text)

    # Neither is provenance: the spoof carries no structured contract.
    assert lfcp.scenario_header_spoof().get("contract") is None


def test_T17_absent_or_non_dict_carrier_adds_no_key():
    from core.prompt_intelligence.prompt_router import PromptRouter
    from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder

    seen = {}
    original = ImageEditPromptBuilder.build

    def spy(self, intent, *a, **kw):
        seen["keys"] = sorted(intent.keys())
        return original(self, intent, *a, **kw)

    base = {
        "request_type": "edit",
        "building_type": "residential",
        "preserve_geometry": True,
        "normalized_prompt": "make the windows larger",
    }

    ImageEditPromptBuilder.build = spy
    try:
        PromptRouter().build({"prompt": "make the windows larger", "architectural_intent": base}, mode="img2img")
        assert "design_context" not in seen["keys"]

        PromptRouter().build(
            {"prompt": "make the windows larger", "architectural_intent": base, "design_context": "not a dict"},
            mode="img2img",
        )
        assert "design_context" not in seen["keys"]
    finally:
        ImageEditPromptBuilder.build = original


# ==========================================================
# T18–T19 — TEXT2IMG AND PROVENANCE
# ==========================================================


def test_T18_text2img_route_is_untouched(data):
    record = _by_name(data, "G_text2img_control")
    # The text builder is a different class, so the image-builder spy never
    # runs: the absence of the key is the correct evidence here.
    assert "has_design_context" not in record["builder_received"]
    assert record["builder_output_unchanged"] is True
    assert record["final_output_unchanged"] is True


def test_T19_capture_declares_it_is_not_a_gpu_submission(data):
    provenance = data["provenance"]
    assert provenance["is_gpu_submitted_prompt"] is False
    assert provenance["is_live_chat_architect_run"] is False
    assert data["gpu_submissions"] == 0
    assert data["comfyui_jobs"] == 0
    assert data["ollama_calls"] == 0
