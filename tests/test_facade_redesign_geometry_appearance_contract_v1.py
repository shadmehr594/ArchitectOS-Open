"""FACADE_REDESIGN_GEOMETRY_APPEARANCE_CONTRACT_V1 — focused contract tests.

The architectural rule under test:

    Preserve building geometry and opening geometry.
    Redesign everything else.

The contract owner is `core.chat.chat_architect._r4_preservation_contract`,
rendered by `_r4_contract_prompt_block`. These tests assert STRUCTURE and
MEANING (which domains are fixed, which are editable), not the presence of a
keyword in a string.

No GPU, no ComfyUI, no model, no inference.
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

from core.chat.chat_architect import (  # noqa: E402
    _r4_acceptance_record,
    _r4_compose_admitted_edit_prompt,
    _r4_contract_prompt_block,
    _r4_preservation_contract,
)

PACK = os.path.join(
    ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1"
)
TARGET = os.path.join(PACK, "TARGET_A_GPU_768x1024.png")
STYLE = os.path.join(PACK, "STYLE_B_PIXEL_EXACT_PAD_768x1024.png")

TARGET_SHA = "fd1088ea4bf01add359af7696fc91a3056b7e8719a98e0de1c58a35e6db86f71"
STYLE_SHA = "a9e3cfecd69a17ce37986c2aff9478ede527354297b3af539d6ba11b4d953604"

RECORDED = os.path.join(ROOT, "runs", "live_handoff_v1", "recorded_understanding.json")
WORKFLOW = "flux_kontext_edit.json"

#: Domains that describe GEOMETRY. They must never appear as editable
#: appearance, and they must always be fixed.
GEOMETRY_DOMAINS = {
    "massing",
    "floor_count",
    "opening_position",
    "opening_dimensions",
    "opening_count",
    "balcony_structure",
    "roof_geometry",
    "camera",
}

#: The appearance domains a facade redesign must be free to change.
REQUIRED_EDITABLE = {
    "facade_material",
    "architectural_style",
    "window_frame_appearance",
    "door_appearance",
    "railing_appearance",
    "balcony_surface_finish",
    "applied_ornament",
}


# ----------------------------------------------------------
# inputs — the genuine recorded request for this acceptance case
# ----------------------------------------------------------


def _recorded_request():
    if os.path.isfile(RECORDED):
        with open(RECORDED, encoding="utf-8") as fh:
            data = json.load(fh)
        text = str(data.get("request_text") or "").strip()
        if text:
            return text
    path = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _source():
    return {
        "image_id": "img_target_a",
        "session_id": "sess_facade_redesign_v1",
        "path": TARGET,
        "source_type": "upload",
    }


def _integrity():
    return {
        "sha256": _sha(TARGET),
        "dimensions": [768, 1024],
        "mean_luma": 118.4,
        "luma_stddev": 41.2,
        "verified": True,
    }


def _acceptance():
    return {
        "scope": "single_source",
        "model": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "data/render_acceptance/flux_kontext_edit.json",
        "record": {"source_sha256": _sha(TARGET)},
    }


def contract(text=None, edit_class="style_change"):
    return _r4_preservation_contract(
        text=text if text is not None else _recorded_request(),
        source=_source(),
        integrity=_integrity(),
        edit_delta={"edit_class": edit_class},
        image_understanding=None,
        acceptance=_acceptance(),
        workflow=WORKFLOW,
    )


def block(text=None, edit_class="style_change"):
    return _r4_contract_prompt_block(contract(text, edit_class))


# ----------------------------------------------------------
# structural readers — meaning, not keyword presence
# ----------------------------------------------------------


def preserve_items(c):
    return [str(item).lower() for item in (c.get("preserve") or ())]


def prohibit_items(c):
    return [str(item).lower() for item in (c.get("prohibit") or ())]


def editable_domains(c):
    return {
        str(entry.get("domain"))
        for entry in (c.get("appearance_editable") or ())
        if isinstance(entry, dict) and entry.get("editable")
    }


def preserved_domains(c):
    return {
        str(entry.get("domain"))
        for entry in (c.get("appearance_preserved") or ())
        if isinstance(entry, dict)
    }


def _section(text, start, ends):
    """Text between a heading and the first following heading."""
    lowered = text
    index = lowered.find(start)
    if index < 0:
        return ""
    tail = lowered[index + len(start):]
    cut = len(tail)
    for end in ends:
        found = tail.find(end)
        if 0 <= found < cut:
            cut = found
    return tail[:cut]


PRESERVE_HEADING = "PRESERVE EXACTLY:"
APPEARANCE_HEADING = "APPEARANCE — EDITABLE BY DEFAULT"


def preserve_section(prompt):
    return _section(
        prompt,
        PRESERVE_HEADING,
        ["DO NOT:", APPEARANCE_HEADING, "UNKNOWN GEOMETRY:"],
    ).lower()


def appearance_section(prompt):
    return _section(
        prompt,
        APPEARANCE_HEADING,
        ["APPEARANCE EXPLICITLY PRESERVED", "UNKNOWN GEOMETRY:"],
    ).lower()


def _mentions(items, *needles):
    """True when one preserve item names every needle (same line)."""
    return any(all(n in item for n in needles) for item in items)


# ==========================================================
# T01–T06 — GEOMETRY IS FIXED
# ==========================================================


def test_T01_four_storeys_remain_geometrically_fixed():
    c = contract()
    items = preserve_items(c)

    assert _mentions(items, "floor", "count") or _mentions(items, "storey", "count")

    # Storeys must be geometry, never an appearance permission.
    assert "storey" not in editable_domains(c)
    assert "floor_count" not in editable_domains(c)
    assert not any("storey" in d or "floor" in d for d in editable_domains(c))


def test_T02_window_positions_remain_fixed():
    items = preserve_items(contract())

    assert _mentions(items, "window", "position")


def test_T03_window_opening_sizes_remain_fixed():
    items = preserve_items(contract())

    assert _mentions(items, "window", "size") or _mentions(items, "window", "dimension")


def test_T04_door_openings_remain_fixed():
    items = preserve_items(contract())

    assert _mentions(items, "door", "position") or _mentions(items, "door", "dimension")


def test_T05_balcony_structural_geometry_remains_fixed():
    c = contract()
    items = preserve_items(c)

    # Structural balcony geometry is preserved ...
    assert _mentions(items, "balcony", "structural") or _mentions(items, "balcony", "projection")

    # ... but the railing's DESIGN is not part of that preservation.
    assert not any("railing" in item for item in items)
    assert "railing_appearance" in editable_domains(c)


def test_T06_main_building_massing_remains_fixed():
    items = preserve_items(contract())

    assert _mentions(items, "massing") or _mentions(items, "silhouette")


# ==========================================================
# T07–T12 — APPEARANCE IS EDITABLE
# ==========================================================


def test_T07_window_frame_appearance_is_editable():
    c = contract()

    assert "window_frame_appearance" in editable_domains(c)

    prompt = block()
    section = preserve_section(prompt)

    # The preservation block must not freeze the frame.
    assert "frame" not in section


def test_T08_door_leaf_appearance_is_editable():
    c = contract()

    assert "door_appearance" in editable_domains(c)

    items = preserve_items(c)
    # The old contract preserved "the existing entrance location and design".
    assert not any("design" in item and "entrance" in item for item in items)


def test_T09_railing_design_is_editable():
    c = contract()

    assert "railing_appearance" in editable_domains(c)

    prompt = block()

    assert "railing" in appearance_section(prompt)
    assert "railing" not in preserve_section(prompt)


def test_T10_brick_can_be_replaced_by_travertine():
    c = contract()

    assert "facade_material" in editable_domains(c)

    scope = " ".join(
        str(entry.get("scope") or "")
        for entry in (c.get("appearance_editable") or ())
        if entry.get("domain") == "facade_material"
    ).lower()

    assert "material" in scope or "cladding" in scope


def test_T11_neoclassical_cornices_and_relief_are_permitted():
    c = contract()

    assert "applied_ornament" in editable_domains(c)

    # No blanket ban on introducing architectural elements: that prohibition
    # is what forbade the cornices the same request requires.
    for item in prohibit_items(c):
        if "invent" in item:
            assert "volume" in item or "opening" in item or "structural" in item, item


def test_T12_decorative_arches_are_distinguishable_from_new_openings():
    c = contract()

    scope = " ".join(
        str(entry.get("scope") or "")
        for entry in (c.get("appearance_editable") or ())
        if entry.get("domain") == "applied_ornament"
    ).lower()

    # Applied decoration is bounded to the surface ...
    assert "applied" in scope or "shallow" in scope or "surface" in scope
    # ... and the opening geometry ban survives.
    assert any(
        "opening" in item and ("add" in item or "resize" in item or "relocate" in item)
        for item in prohibit_items(c)
    )
    # The opening is never made editable.
    assert not any(
        domain in GEOMETRY_DOMAINS or "opening" in domain
        for domain in editable_domains(c)
    )


# ==========================================================
# T13–T15 — PRECEDENCE
# ==========================================================


def test_T13_material_only_request_does_not_authorise_full_redesign():
    c = contract(
        text="Replace only the brick cladding material with cream travertine.",
        edit_class="material_change",
    )

    domains = editable_domains(c)

    assert domains == {"facade_material"}, domains


def test_T14_explicit_railing_preservation_overrides_default_editability():
    c = contract(
        text=(
            "Redesign this facade in a neoclassical style with cream travertine, "
            "but keep the existing railings exactly as they are."
        )
    )

    assert "railing_appearance" in preserved_domains(c)
    assert "railing_appearance" not in editable_domains(c)

    # The rest of the appearance freedom survives.
    assert "facade_material" in editable_domains(c)
    assert "window_frame_appearance" in editable_domains(c)


def test_T15_explicit_opening_change_never_grants_geometry_here():
    c = contract(
        text=(
            "Redesign the facade in neoclassical style and also add a new window "
            "on the right bay."
        )
    )

    # This contract never grants geometry: the appearance layer stays
    # appearance, and the opening geometry stays fixed.
    assert not (editable_domains(c) & GEOMETRY_DOMAINS)
    assert _mentions(preserve_items(c), "window", "position")


# ==========================================================
# T16–T18 — ROUTE SAFETY
# ==========================================================


def test_T16_no_image_a_b_ambiguity_in_the_contract_block():
    """The product's own contract text must not restate the user's letters.

    The user's verbatim request is quoted first and legitimately says
    "IMAGE A"/"IMAGE B"; the semantic roles are what bind. What must not
    happen is the product itself introducing the letters as if they carried
    authority, which is how the original ambiguity arose.
    """

    prompt = block()

    assert prompt.startswith("USER REQUEST (verbatim, authoritative): ")

    own_text = prompt.split("ARCHITECTURAL PRESERVATION CONTRACT", 1)[-1]

    assert "IMAGE A" not in own_text
    assert "IMAGE B" not in own_text


def test_T17_no_comfyui_job_is_submitted(monkeypatch):
    import core.comfy_client as comfy

    def _boom(*args, **kwargs):
        raise AssertionError("a ComfyUI client must not be constructed here")

    for name in ("ComfyClient", "ComfyUIClient"):
        if hasattr(comfy, name):
            monkeypatch.setattr(comfy, name, _boom)

    prompt = block()

    assert "PRESERVE EXACTLY:" in prompt


def test_T18_r4_production_remains_closed():
    acceptance = _r4_acceptance_record(WORKFLOW)

    assert acceptance["accepted"] is False
    assert acceptance["reason"] == "no_acceptance_record"
    assert not os.path.isdir(os.path.join(ROOT, "data", "render_acceptance"))


# ==========================================================
# composition — the contract reaches the instruction
# ==========================================================


def test_contract_reaches_the_instruction_with_both_sections():
    c = contract()
    prompt = _r4_compose_admitted_edit_prompt(
        _recorded_request(), c, "Refine the existing architectural image."
    )

    assert "ArchitecturalPreservationContractV1" in prompt
    assert PRESERVE_HEADING in prompt
    assert APPEARANCE_HEADING in prompt

    # The user's own words stay verbatim and first.
    assert prompt.startswith("USER REQUEST (verbatim, authoritative): ")

    # No appearance-preservation demand survives anywhere in the block.
    lowered = prompt.lower()
    assert "preserve the existing balconies and railings" not in lowered
    assert "entrance location and design" not in lowered
    assert "every building element the user did not explicitly ask to change" not in lowered


def test_appearance_domains_cover_every_required_permission():
    assert editable_domains(contract()) >= REQUIRED_EDITABLE
