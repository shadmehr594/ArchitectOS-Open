"""Focused regression for exact architectural edit-scope retention V2."""

import hashlib

from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    authority_note,
    resolve_geometry_authority,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


EXACT_REQUEST = (
    "Replace only the exposed red-brick finish on the main facade wall planes "
    "with realistic light natural travertine stone. Preserve the original "
    "architectural design, all windows, shutters, window frames, roof, both "
    "chimneys, entrance, columns, portico, steps, surrounding landscape, "
    "camera and building geometry exactly. Do not alter any other material or "
    "architectural component."
)


def _delta(text):
    return compile_edit_delta(text, image_edit=True)


def test_exact_english_material_scope_and_preservation_survive_compilation():
    delta = _delta(EXACT_REQUEST)
    low = delta["delta_prompt"].lower()

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "travertine"
    assert delta["material_tone"] == "light"
    assert delta["target_surfaces"] == ["main facade wall planes"]
    assert delta["replaced_material"] == "red_brick"
    assert len(delta["explicit_preservation_clauses"]) == 2

    for required in (
        "only the existing finish on the main facade wall planes",
        "light natural travertine",
        "all windows",
        "shutters",
        "window frames",
        "roof",
        "both chimneys",
        "entrance",
        "columns",
        "portico",
        "steps",
        "surrounding landscape",
        "camera",
        "building geometry",
        "any existing brick on those protected components must remain brick",
        "no other surface is authorized",
    ):
        assert required in low


def test_generic_material_request_does_not_invent_exact_scope_or_components():
    delta = _delta("Replace the brick facade with stone")
    low = delta["delta_prompt"].lower()

    assert delta["target_surfaces"] == []
    assert delta["explicit_preservation_clauses"] == []
    assert delta["replaced_material"] == "brick"
    assert "chimney" not in low
    assert "portico" not in low
    assert "landscape" not in low
    assert "stone of unspecified species" in low
    assert "travertine" not in low


def test_style_only_keeps_explicit_preservation_without_material_invention():
    delta = _delta(
        "Convert this facade to neoclassical style. Preserve the windows, "
        "roof, portico and surrounding landscape exactly."
    )
    low = delta["delta_prompt"].lower()

    assert delta["edit_class"] == "style_change"
    assert delta["material"] is None
    assert "neoclassical" in low
    assert "preserve the windows, roof, portico and surrounding landscape exactly" in low
    assert "travertine" not in low


def test_combined_style_material_keeps_both_domains_and_exact_boundaries():
    delta = _delta(
        "Convert this facade to neoclassical style and replace only the brick "
        "finish on the entrance wall surfaces with light travertine. "
        "Preserve the windows, roof and garden."
    )
    low = delta["delta_prompt"].lower()

    assert delta["edit_class"] == "material_change"
    assert delta["style"] == "neoclassical"
    assert delta["target_surfaces"] == ["entrance wall surfaces"]
    assert "light natural travertine" in low
    assert "neoclassical" in low
    assert "preserve the windows, roof and garden" in low
    assert "no other surface is authorized" in low


def test_persian_material_scope_and_preservation_survive_structurally():
    delta = _delta(
        "فقط پوشش آجر روی سطوح اصلی دیوار نما را با سنگ تراورتن روشن جایگزین کن. "
        "هر دو دودکش آجری، ایوان ورودی و ستون‌ها، پنجره‌ها و قاب‌ها، سقف، پله‌ها، "
        "محوطه و دوربین را حفظ کن."
    )
    low = delta["delta_prompt"].lower()

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "travertine"
    assert delta["target_surfaces"] == ["main facade wall planes"]
    assert delta["replaced_material"] == "brick"
    assert "هر دو دودکش آجری" in low
    assert "ایوان ورودی" in low
    assert "محوطه و دوربین را حفظ کن" in low
    assert "no other surface is authorized" in low
    assert "any existing brick on those protected components must remain brick" in low


def test_persian_style_only_preservation_is_retained_without_material_change():
    delta = _delta(
        "این نما را نئوکلاسیک کن. پنجره‌ها، سقف، ایوان و محوطه را حفظ کن."
    )
    low = delta["delta_prompt"].lower()

    assert delta["edit_class"] == "style_change"
    assert delta["material"] is None
    assert "پنجره‌ها" in low
    assert "ایوان و محوطه را حفظ کن" in low


def test_atomic_authority_note_cannot_leave_material_colour_fragment():
    authority = {
        "status": "style_suggestions_filtered",
        "suppressed_terms": ["columns"],
    }
    note = authority_note(authority)

    assert note == "Style vocabulary that would change fixed geometry has been omitted."
    assert "," not in note


def test_accepted_plain_night_and_moonlit_delta_contracts_are_byte_identical():
    # R3_NIGHT_MATERIAL_FIDELITY_CPU_V1 — the PLAIN night delta changed on
    # purpose. The old value was (597,
    # c5d2c43de333979b9d52d739e5ce73397506a303f6628cec3b5293b0c9aa0c36).
    # Two instruction defects were corrected in it:
    #   * "clearly visible and evenly lit" requested uniform flat
    #     illumination of the whole elevation;
    #   * material preservation never forbade re-rendering the wall's units,
    #     and never named cladding, recolouring, saturation or growth.
    # The MOONLIT delta is deliberately UNCHANGED (771,
    # c6605b132f4cca3523ac8ef60dd30bba49a59865925341dd6fef9b0adda55217) —
    # it is a different lighting condition and was not implicated by the GPU
    # evidence. This pin still exists to catch UNINTENDED drift; it was
    # re-baselined once, deliberately, and records both values.
    cases = (
        (
            "Convert this building to night.",
            869,
            "b8783197951cb160e5c4c1b0c881b4ca4fec48dda32ce9f3769129b00192afe8",
        ),
        (
            "این ساختمان را در شب مهتابی واقعی تبدیل کن. آسمان سرمه‌ای تیره باشد.",
            771,
            "c6605b132f4cca3523ac8ef60dd30bba49a59865925341dd6fef9b0adda55217",
        ),
    )

    for text, expected_length, expected_sha in cases:
        prompt = _delta(text)["delta_prompt"]
        assert len(prompt) == expected_length
        assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == expected_sha
