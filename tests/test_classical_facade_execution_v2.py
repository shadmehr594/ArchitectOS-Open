# ==========================================================
# ARCHITECTOS — CLASSICAL FACADE EXECUTION V2 — CPU GATES
#
# CPU only. No GPU, no ComfyUI, no socket.
#
# Gate A: the geometry guard must distinguish a GLOBAL facade redesign from a
#         LOCALIZED component edit, without weakening either.
# Gate B: the compiler must carry the user's explicitly named architectural
#         elements into the executable prompt.
# Gate C: a complete-building request must compile to an explicit framing
#         instruction.
# ==========================================================

import pytest

from core.prompt_intelligence.persian_architectural_understanding import (
    persian_architectural_understanding as UNDERSTANDING,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    architectural_prompt_compiler as COMPILER,
)
from core.vision.image_intent_v1 import detect_unsupported_geometry_edit as GUARD


# ----------------------------------------------------------
# the exact texts from the acceptance brief
# ----------------------------------------------------------

BLOCKED_I2I_V1 = (
    "Redesign the architectural facade of this existing two-story brick villa into a "
    "richly detailed Roman-classic / neoclassical stone villa inspired by high-quality "
    "classical architectural references. Replace the red-brick facade character with "
    "sophisticated warm ivory stone architecture, prominent classical entrance "
    "composition, refined columns and capitals, cornices, ornamental frames and "
    "carefully proportioned classical detailing. Retain the two-story building "
    "identity, approximate original massing, front-facing camera and landscape "
    "context. Architectural facade detailing and limited facade-form modifications "
    "are explicitly allowed. Do not add extra floors or arbitrarily rebuild the "
    "surrounding site."
)

T2I_V2 = (
    "Design a complete luxurious two-storey Roman-classic and ornate neoclassical "
    "stone villa, seen in a full-building front-three-quarter architectural view. The "
    "entire facade, roofline, both floors, entrance steps and surrounding landscaped "
    "ground must be visible within the frame. Create a balanced monumental central "
    "entrance framed by correctly proportioned classical columns and finely carved "
    "Corinthian or Composite capitals. Include richly articulated cornices, "
    "architectural relief carving, elegant window pediments, appropriately supported "
    "stone balustraded balconies and realistic light warm-ivory natural stone "
    "cladding. Show convincing large-scale ashlar courses with recessed joints, "
    "subtle per-block stone variations, deep architectural shadows and precise "
    "construction logic. Professional high-detail daylight architectural photography. "
    "No cropped roof or missing building edges, no advertising, no watermark."
)

FAITHFUL_REPHRASINGS = {
    "original": BLOCKED_I2I_V1,
    "no_component_words": (
        "Redesign this existing two-story brick villa as a richly detailed Roman-classic "
        "neoclassical stone villa with warm ivory architecture, monumental composition, "
        "carved cornices and refined classical detailing. Retain the two-story "
        "identity, massing, camera and landscape context."
    ),
    "facade_only": (
        "Transform the facade of this two-story villa into ornate neoclassical ivory "
        "stone architecture with classical detailing."
    ),
    "style_verb": (
        "Restyle this two-story villa in a luxurious Roman-classic neoclassical manner "
        "with ivory stone and ornate detailing."
    ),
    "global_appearance": (
        "Make the facade look like a luxurious Roman-classic neoclassical ivory stone "
        "villa with ornate classical detailing."
    ),
}


def _compile(text, mode="text_to_image"):
    return COMPILER.compile(UNDERSTANDING.interpret({"text": text}), mode=mode)


# ==========================================================
# GATE A — SCOPE
# ==========================================================

def test_1_the_previously_blocked_redesign_is_now_accepted():
    verdict = GUARD(BLOCKED_I2I_V1)

    assert verdict["unsupported"] is False, (
        "the authorised global facade redesign is still refused: %s"
        % verdict.get("reason")
    )

    assert verdict.get("scope_evidence", {}).get("resolved_scope") == "global"


@pytest.mark.parametrize("name", sorted(FAITHFUL_REPHRASINGS))
def test_2_all_faithful_rephrasings_are_accepted(name):
    verdict = GUARD(FAITHFUL_REPHRASINGS[name])

    assert verdict["unsupported"] is False, (
        "%s was refused: %s" % (name, verdict.get("reason"))
    )


def test_3_global_redesign_with_columns_and_entrance_is_accepted():
    verdict = GUARD(
        "Redesign the entire existing villa facade in an ornate Roman-classic "
        "architectural language. Replace the brick facade character with natural "
        "stone and introduce compatible columns, capitals, ornamental cornices and "
        "a monumental entrance while retaining two floors and the original building "
        "identity."
    )

    assert verdict["unsupported"] is False
    assert verdict["scope_evidence"]["resolved_scope"] == "global"


def test_4_global_material_replacement_naming_elements_is_accepted():
    verdict = GUARD(
        "Replace the facade cladding across the whole building with warm natural "
        "stone, adding classical columns and a new entrance composition."
    )

    assert verdict["unsupported"] is False


def test_5_local_column_removal_is_refused():
    verdict = GUARD("Remove this particular column.")

    assert verdict["unsupported"] is True
    assert verdict["reason"] == "localized_geometry_edit_not_supported"


def test_6_local_window_resizing_is_refused():
    verdict = GUARD("Enlarge only this window opening.")

    assert verdict["unsupported"] is True
    assert verdict["reason"] == "localized_geometry_edit_not_supported"


def test_7_local_entrance_relocation_is_refused():
    verdict = GUARD("Move the left entrance two metres.")

    assert verdict["unsupported"] is True
    assert verdict["reason"] in (
        "localized_geometry_edit_not_supported",
        "dimensioned_geometry_edit_not_supported",
    )


def test_8_global_redesign_does_not_override_a_local_structural_edit():
    verdict = GUARD(
        "Redesign the entire facade in an ornate Roman-classic language with natural "
        "stone, but also delete the load-bearing wall."
    )

    assert verdict["unsupported"] is True, (
        "a global redesign authorised an explicit local structural edit"
    )


def test_9a_persian_localized_edit_is_still_refused():
    verdict = GUARD("این پنجره را حذف کن")

    assert verdict["unsupported"] is True


def test_9b_persian_global_redesign_is_accepted():
    verdict = GUARD(
        "نمای ساختمان را به سبک روم کلاسیک با سنگ طبیعی و ستون بازطراحی کن"
    )

    assert verdict["unsupported"] is False


@pytest.mark.parametrize("text", [
    "Make the facade stone.",
    "این نما را سنگ کن",
    "Turn this image into night with warm lighting.",
    "همینو شب کن",
])
def test_10_material_only_and_night_requests_are_untouched(text):
    verdict = GUARD(text)

    assert verdict["unsupported"] is False, (
        "an appearance-only request was flagged as a geometry edit: %s" % text
    )


# ==========================================================
# GATE B — ELEMENT RETENTION
# ==========================================================

def test_11_t2i_retains_every_named_element():
    prompt = _compile(T2I_V2)["positive_prompt"]

    # the meaning, not the substring: each element must be a design
    # instruction with its own architectural qualification.
    required = {
        "columns": "correctly proportioned classical columns",
        "capitals": "Corinthian or Composite capitals",
        "cornices": "cornices with dentils or modillions",
        "arches": "arches with proper voussoirs",
        "pediments": "window pediments",
        "balustrades": "balustraded balconies with visible balusters",
        "relief": "relief carving",
    }

    for name, phrase in required.items():
        assert phrase in prompt, "the prompt lost %s" % name


def test_12_only_named_elements_are_emitted():
    """No ontology dump: a request naming one element emits one element."""
    prompt = _compile("Design a two-storey stone villa with classical columns.")[
        "positive_prompt"
    ]

    assert "classical columns" in prompt

    for absent in ("capitals", "pediments", "voussoirs", "quoins"):
        assert absent not in prompt, (
            "an element the user never named was injected: %s" % absent
        )


def test_13_t2i_never_contradicts_the_requested_floor_count():
    """The compiler must not INVENT a storey count.

    BENCHMARK_V1 correction: this test previously ended in `or True`, which
    made it vacuous. Removing that clause showed the compiler does not carry a
    floor sentence at all — the "The building has exactly 2 floors." line is
    emitted by the render instruction layer downstream of this compiler. The
    claim is therefore narrowed to what this owner can support: no storey-count
    contradiction. The presence of the positive floor line is verified at the
    full production-prompt level in the benchmark preflight, not here.
    """

    prompt = _compile(T2I_V2)["positive_prompt"].lower()

    for wrong in ("three-storey", "three storey", "3 floors", "3-storey",
                  "four-storey", "four storey", "4 floors", "4-storey",
                  "three floors", "four floors"):
        assert wrong not in prompt, (
            "the compiler invented a storey count the user did not ask for: %r"
            % wrong
        )


def test_14_complete_building_framing_survives():
    prompt = _compile(T2I_V2)["positive_prompt"]

    assert "COMPLETE building" in prompt
    assert "roofline" in prompt
    assert "Do not crop the roof" in prompt
    assert "three-quarter" in prompt


def test_15_detail_request_does_not_become_full_building():
    prompt = _compile(
        "Design a close-up detail study of a classical stone cornice."
    )["positive_prompt"]

    assert "COMPLETE building" not in prompt


def test_16_stone_courses_and_joints_are_explicit():
    prompt = _compile(T2I_V2)["positive_prompt"]

    assert "ashlar stone courses" in prompt
    assert "recessed joints" in prompt


def test_17_no_metadata_or_ontology_leaks_into_the_prompt():
    prompt = _compile(T2I_V2)["positive_prompt"]

    for leak in ("_", "{", "}", "roman_classic", "natural_stone", "contract",
                 "snake_case"):
        assert leak not in prompt, "internal token leaked: %r" % leak


# ==========================================================
# GATE C — I2I FREEDOM
# ==========================================================

def test_18_i2i_keeps_its_architectural_redesign_freedom():
    prompt = _compile(BLOCKED_I2I_V1, mode="image_to_image")["positive_prompt"]

    assert "classical columns" in prompt
    assert "capitals" in prompt


def test_19_i2i_does_not_inherit_material_only_preservation():
    """A redesign must not be told to keep every other material unchanged."""
    prompt = _compile(BLOCKED_I2I_V1, mode="image_to_image")["positive_prompt"]

    for contradiction in (
        "keep every other material",
        "keep the same building",
        "no other surface is authorized",
    ):
        assert contradiction not in prompt, (
            "material-only preservation leaked into a redesign: %r" % contradiction
        )
