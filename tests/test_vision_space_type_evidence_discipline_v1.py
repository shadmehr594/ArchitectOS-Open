# -*- coding: utf-8 -*-
"""VISION_SPACE_TYPE_EVIDENCE_DISCIPLINE_V1 — focused CPU tests.

The defect under test is a FALSE ARCHITECTURAL CLASSIFICATION, measured on the
real saved observation of facade A (Neue Nationalgalerie):

    architectural_elements[3] = "one prominent light/whitish ribbed panel"

`_space_type_basis` matched the character sequence `bed` INSIDE the word
`ribbed`, and published

    space_type            = "bedroom"
    possible_function     = ["likely bedroom"]
    classification_basis  = ["bedroom from sleeping element (architectural_elements)"]

A description of architectural texture became evidence of sleeping furniture,
and the basis cited `architectural_elements` for an element that field does not
contain.

THE INVARIANT THESE TESTS ENFORCE (brief §4F, ACCEPTANCE PRINCIPLE):

    An architectural classification must be supported by real, affirmative,
    traceable evidence. A substring inside an unrelated word is NOT an
    architectural element. A classification basis must never cite an element
    that the observation does not contain.

The tests below drive the REAL production pipeline
(`build_architectural_observation` -> `ArchitecturalVisionInterpreterV1`).
They do not re-run any vision model: the facade payloads are the saved
`03_understanding.json` artefacts of the four-facade acceptance corpus.

CPU ONLY. No Ollama. No GPU. No ComfyUI. No image inference.
"""

import json
import os
import re

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)
from core.vision.architectural_vision_interpreter_v1 import (
    SPACE_TYPES,
    ArchitecturalVisionInterpreterV1,
    interpret_architectural_vision,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

# The verbatim provider phrase that produced the false classification.
RIBBED_PHRASE = "one prominent light/whitish ribbed panel"

# Requirement constants, written out INDEPENDENTLY of the production
# vocabulary: the tokens that may legitimately establish a sleeping space.
SLEEPING_TOKENS = ("bed", "تخت")

SLEEPING_BASIS_MARKERS = ("sleeping element", "bedroom from")


# ==========================================================
# independent lexical helper — deliberately NOT the production matcher
# ==========================================================


def _token_in(text, token):
    """True only when `token` stands as a whole word (plural tolerated)."""

    lowered = (text or "").lower()

    pattern = r"(?<!\w)" + re.escape(token.lower()) + r"(?:s|es)?(?!\w)"

    return re.search(pattern, lowered) is not None


def _entries(payload, field):
    """The verbatim entries of one evidence field, wherever they live."""

    if field == "furniture_elements":

        extras = payload.get("observation_extras") or {}

        if isinstance(extras, dict) and extras.get("furniture_elements") is not None:

            return list(extras.get("furniture_elements") or [])

        raw = payload.get("raw_observations") or {}

        return list(raw.get("furniture_elements") or [])

    value = payload.get(field)

    if isinstance(value, str):

        return [value]

    return list(value or [])


def _load(case):
    path = os.path.join(CORPUS, FACADE_DIRS[case], "03_understanding.json")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)


def _interpret(payload, **kwargs):
    return ArchitecturalVisionInterpreterV1().interpret(payload, **kwargs)


def _basis_text(result):
    return " | ".join(result.get("classification_basis") or []).lower()


def _function_text(result):
    return " | ".join(result.get("possible_function") or []).lower()


def _interpretation_text(result):
    return " | ".join(result.get("architectural_interpretation") or []).lower()


def _assert_no_sleeping_claim(result, label):
    assert result["space_type"] not in ("bedroom", "master bedroom"), (
        label + ": false sleeping-space classification -> " + result["space_type"]
    )

    assert "bedroom" not in _function_text(result), (
        label + ": bedroom function published -> " + _function_text(result)
    )

    for marker in SLEEPING_BASIS_MARKERS:

        assert marker not in _basis_text(result), (
            label + ": basis claims " + marker + " -> " + _basis_text(result)
        )

    assert "sleeping" not in _interpretation_text(result), (
        label + ": interpretation claims a sleeping element -> "
        + _interpretation_text(result)
    )


# ==========================================================
# CASE A — the real museum facade
# ==========================================================


def test_a1_the_saved_payload_still_contains_the_ribbed_phrase():
    """The defect is real only if the phrase is really in the payload."""

    payload = _load("A")

    assert RIBBED_PHRASE in (payload.get("architectural_elements") or [])

    assert "bed" in RIBBED_PHRASE.lower()

    # The substring is genuinely inside a different word.
    index = RIBBED_PHRASE.lower().find("bed")

    assert RIBBED_PHRASE.lower()[index - 3:index] == "rib"


def test_a2_facade_a_is_not_classified_as_a_sleeping_space():
    result = _interpret(_load("A"))

    _assert_no_sleeping_claim(result, "facade A")


def test_a3_facade_a_publishes_no_bedroom_function():
    result = _interpret(_load("A"))

    assert "likely bedroom" not in (result.get("possible_function") or [])

    assert "possible private couple bedroom" not in (
        result.get("possible_function") or []
    )


def test_a4_facade_a_basis_does_not_cite_a_sleeping_element():
    result = _interpret(_load("A"))

    assert result.get("classification_basis") != [
        "bedroom from sleeping element (architectural_elements)"
    ]

    for entry in result.get("classification_basis") or []:

        assert "sleeping" not in entry.lower()


def test_a5_facade_a_is_unknown_because_no_space_token_exists():
    """Measured outcome: no space-type token is present in facade A.

    This is a RECORD of the measurement, not a target. If a later milestone
    makes facade A classify as `facade`, that change must arrive with its own
    independent evidence and this expectation must be updated deliberately.
    """

    result = _interpret(_load("A"))

    assert result["space_type"] == "unknown"

    assert result.get("classification_basis") == []


def _observation_phrases(observation):
    """Every verbatim phrase the observation layer retained, in any bucket."""

    phrases = []

    for field in ("architectural_elements", "unclassified_observations"):

        for entry in observation.get(field) or []:

            if isinstance(entry, dict) and entry.get("evidence_phrase"):

                phrases.append(entry["evidence_phrase"])

    return phrases


def test_a6_the_ribbed_surface_observation_is_preserved():
    observation = build_architectural_observation(_load("A"))

    assert RIBBED_PHRASE in _observation_phrases(observation)


def test_a7_the_observation_layer_is_untouched_by_the_classification():
    """Elements, floors, materials and negatives must survive verbatim."""

    observation = build_architectural_observation(_load("A"))

    assert len(observation.get("architectural_elements") or []) == 4

    assert (observation.get("visible_floors") or {}).get("count") == 1

    assert observation.get("furniture_elements") == []

    negatives = observation.get("negative_observations") or []

    assert len(negatives) == 2

    assert negatives[0]["kind"] == ["door", "window", "stair"]

    assert negatives[0]["status"] == "absent"

    # The material reading of facade A is a known, accepted outcome.
    materials = observation.get("material_observations") or []

    assert materials, "the material observation was lost"

    assert materials[0]["materials"] == ["glass"]


def test_a8_facade_a_grounding_does_not_claim_a_visible_bed():
    result = _interpret(_load("A"))

    grounding = result.get("grounding") or {}

    assert "sleeping_element" not in (grounding.get("visible_elements") or [])

    assert "bedroom" not in (grounding.get("visible_elements") or [])


# ==========================================================
# CASE B — substring collisions
# ==========================================================

COLLISION_PHRASES = (
    "ribbed panel",
    "ribbed wall",
    "embedded lighting",
    "ribbed ceiling",
    "bedrock texture",
    # Persian: "تخته" (board / panel) contains "تخت" (bed).
    "دیوار تخته‌ای",
)


@pytest.mark.parametrize("phrase", COLLISION_PHRASES)
def test_b1_collisions_in_architectural_elements_are_not_sleeping_evidence(phrase):
    result = interpret_architectural_vision({"architectural_elements": [phrase]})

    _assert_no_sleeping_claim(result, "architectural_elements=" + phrase)


@pytest.mark.parametrize("phrase", COLLISION_PHRASES)
def test_b2_collisions_in_observed_are_not_sleeping_evidence(phrase):
    result = interpret_architectural_vision({"observed": [phrase]})

    _assert_no_sleeping_claim(result, "observed=" + phrase)


@pytest.mark.parametrize(
    "phrase",
    ("ribbed panel", "ribbed wall", "embedded lighting", "bedrock texture"),
)
def test_b3_collisions_in_text_labels_are_not_sleeping_evidence(phrase):
    result = interpret_architectural_vision({"text_labels_if_visible": [phrase]})

    _assert_no_sleeping_claim(result, "text_labels_if_visible=" + phrase)


def test_b4_a_hyphenated_modifier_fragment_does_not_match():
    """`ribbed-panel` keeps `bed` adjacent to a hyphen, not a word edge."""

    result = interpret_architectural_vision(
        {"architectural_elements": ["ribbed-panel cladding"]}
    )

    _assert_no_sleeping_claim(result, "ribbed-panel cladding")


def test_b5_a_compound_word_that_starts_with_bed_is_not_a_bed():
    for phrase in ("bedrock", "bedding texture", "bedside wall panel"):

        result = interpret_architectural_vision({"architectural_elements": [phrase]})

        assert result["space_type"] != "bedroom", phrase


# ==========================================================
# CASE C — genuine sleeping furniture (positive control)
# ==========================================================


@pytest.mark.parametrize(
    "phrase",
    (
        "A bed is visible in the room",
        "Two beds are present",
        "تخت در اتاق دیده می‌شود",
    ),
)
def test_c1_genuine_sleeping_evidence_still_classifies(phrase):
    result = interpret_architectural_vision({"observed": [phrase]})

    assert result["space_type"] == "bedroom", (
        phrase + " -> " + result["space_type"]
    )

    assert "likely bedroom" in (result.get("possible_function") or [])


def test_c2_the_observed_short_form_keeps_its_exact_basis():
    """Legacy contract: a bed found in `observed` publishes ["sleeping element"]."""

    result = interpret_architectural_vision({"observed": ["bed visible"]})

    assert result["space_type"] == "bedroom"

    assert result["classification_basis"] == ["sleeping element"]


def test_c3_a_bed_in_architectural_elements_is_cited_from_that_field():
    result = interpret_architectural_vision(
        {"architectural_elements": ["a bed in the corner"]}
    )

    assert result["space_type"] == "bedroom"

    assert "architectural_elements" in result["classification_basis"][0]


def test_c4_an_explicit_bedroom_token_still_classifies():
    assert interpret_architectural_vision(
        {"observed": ["bedroom with a window"]}
    )["space_type"] == "bedroom"

    assert interpret_architectural_vision(
        {"observed": ["اتاق خواب بزرگ"]}
    )["space_type"] == "bedroom"


# ==========================================================
# CASE D — negation
# ==========================================================


@pytest.mark.parametrize(
    "phrase",
    ("No bed is visible", "No beds are present", "تختی دیده نمی‌شود"),
)
def test_d1_a_negated_sleeping_element_creates_no_bedroom(phrase):
    result = interpret_architectural_vision({"observed": [phrase]})

    assert result["space_type"] not in ("bedroom", "master bedroom"), phrase

    assert "bedroom" not in _function_text(result)


@pytest.mark.parametrize("phrase", ("No bed is visible", "No beds are present"))
def test_d2_the_evidence_of_absence_is_preserved_separately(phrase):
    observation = build_architectural_observation({"observed": [phrase]})

    negatives = observation.get("negative_observations") or []

    assert negatives, phrase + ": absence evidence was lost"

    assert any("bed" in (entry.get("kind") or []) for entry in negatives)

    assert all(entry.get("status") == "absent" for entry in negatives)


def test_d3_a_negated_bed_does_not_suppress_a_real_bed_elsewhere():
    result = interpret_architectural_vision(
        {
            "observed": ["No bed in the corridor"],
            "architectural_elements": ["a bed in the main room"],
        }
    )

    assert result["space_type"] == "bedroom"

    assert "architectural_elements" in result["classification_basis"][0]


# ==========================================================
# CASE E — independent evidence sources
# ==========================================================


def test_e1_the_false_substring_is_ignored_but_the_real_bed_survives():
    result = interpret_architectural_vision(
        {
            "architectural_elements": ["ribbed wall"],
            "observation_extras": {"furniture_elements": ["a real bed is visible"]},
        }
    )

    assert result["space_type"] == "bedroom"

    assert "bedroom" in _function_text(result)


def test_e2_the_basis_names_furniture_elements_when_that_is_the_source():
    result = interpret_architectural_vision(
        {
            "architectural_elements": ["ribbed wall"],
            "observation_extras": {"furniture_elements": ["a real bed is visible"]},
        }
    )

    basis = result["classification_basis"][0]

    assert "furniture_elements" in basis, basis

    assert "architectural_elements" not in basis, (
        "the basis claims architectural_elements although the bed came from "
        "furniture_elements -> " + basis
    )


def test_e3_furniture_only_evidence_is_reachable():
    """A bed reported ONLY under furniture_elements must still classify."""

    result = interpret_architectural_vision(
        {"observation_extras": {"furniture_elements": ["a real bed is visible"]}}
    )

    assert result["space_type"] == "bedroom"

    assert "furniture_elements" in result["classification_basis"][0]


def test_e4_furniture_evidence_does_not_leak_from_a_grounded_local_plan():
    """The local-plan filter clears ungrounded furniture; the basis must agree."""

    result = interpret_architectural_vision(
        {
            "observation_extras": {"furniture_elements": ["a real bed is visible"]},
            "local_plan_reading": {"status": "grounded"},
        }
    )

    assert result["space_type"] != "bedroom"


# ==========================================================
# CASE F — provenance invariant
# ==========================================================

_CITED_FIELD = re.compile(r"\(([^)]*)\)")


def _cited_fields(result):
    fields = []

    for entry in result.get("classification_basis") or []:

        for group in _CITED_FIELD.findall(entry):

            for field in group.split(","):

                field = field.strip()

                if field:

                    fields.append(field)

    return fields


def _assert_citation_is_real(payload, result, label):
    """Every field the basis cites must really contain a matching entry."""

    for field in _cited_fields(result):

        entries = _entries(payload, field)

        assert entries, label + ": basis cites " + field + " but that field is empty"

        lowered = " ".join(entry.lower() for entry in entries)

        matched = any(
            _token_in(lowered, token)
            for token in (
                SLEEPING_TOKENS
                + ("bedroom", "اتاق خواب", "master", "مستر", "kitchen",
                   "آشپزخانه", "bathroom", "حمام", "سرویس", "corridor",
                   "راهرو", "balcony", "بالکن", "entrance", "entry", "ورودی",
                   "living room", "نشیمن", "پذیرایی", "garden", "باغ", "محوطه",
                   "facade", "elevation", "نمای", "exterior", "large bed",
                   "تخت بزرگ", "larger glazing", "sitting area", "نشیمن")
            )
        )

        assert matched, (
            label + ": basis cites " + field + " but no supported term matches "
            "in it -> " + " / ".join(entries)
        )


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f1_every_cited_field_really_contains_the_evidence(case):
    payload = _load(case)

    result = _interpret(payload)

    _assert_citation_is_real(payload, result, "facade " + case)


@pytest.mark.parametrize(
    "payload",
    (
        {"architectural_elements": ["a bed in the corner"]},
        {"observed": ["Two beds are present"]},
        {"observation_extras": {"furniture_elements": ["a bed"]}},
        {"architectural_elements": ["master bedroom"]},
        {"observed": ["a kitchen with cabinets"]},
        {"observed": ["ورودی اصلی"]},
    ),
)
def test_f2_synthetic_citations_are_real(payload):
    result = interpret_architectural_vision(payload)

    _assert_citation_is_real(payload, result, "synthetic")


def test_f3_a_cited_field_is_never_invented():
    """No basis may name a field the payload does not carry."""

    payload = {"architectural_elements": ["a bed in the corner"]}

    result = interpret_architectural_vision(payload)

    for field in _cited_fields(result):

        assert field in payload or field in ("furniture_elements",), (
            "basis cites an unknown field: " + field
        )


def test_f4_the_basis_never_names_an_element_absent_from_the_observation():
    """The facade-A failure, stated as a general invariant."""

    payload = _load("A")

    observation = build_architectural_observation(payload)

    phrases = " ".join(_observation_phrases(observation)).lower()

    furniture = " ".join(
        str(entry) for entry in observation.get("furniture_elements") or []
    ).lower()

    result = _interpret(payload)

    for marker in SLEEPING_BASIS_MARKERS:

        if marker not in _basis_text(result):

            continue

        assert _token_in(phrases, "bed") or _token_in(furniture, "bed"), (
            "the basis claims a sleeping element that the observation does "
            "not contain"
        )


def test_f5_negated_entries_never_satisfy_a_citation():
    result = interpret_architectural_vision(
        {"architectural_elements": ["no bed is present"]}
    )

    assert result["space_type"] != "bedroom"

    assert result["classification_basis"] == []


def test_f6_a_whole_token_is_required_in_a_long_real_entry():
    """The real A entry, reduced: the token must stand as a word."""

    result = interpret_architectural_vision(
        {"architectural_elements": [RIBBED_PHRASE]}
    )

    assert result["space_type"] != "bedroom"


# ==========================================================
# CASE G — other architectural functions
# ==========================================================

FUNCTION_CASES = (
    ("a kitchen with cabinets", "kitchen"),
    ("آشپزخانه", "kitchen"),
    ("two kitchens", "kitchen"),
    ("bathroom with shower", "bathroom"),
    ("حمام", "bathroom"),
    ("living room", "living room"),
    ("نشیمن", "living room"),
    ("corridor", "corridor"),
    ("راهرو", "corridor"),
    ("entrance", "entrance"),
    ("ورودی", "entrance"),
    ("balcony", "balcony"),
    ("بالکن", "balcony"),
)


@pytest.mark.parametrize("phrase,expected", FUNCTION_CASES)
def test_g1_existing_space_types_still_classify(phrase, expected):
    result = interpret_architectural_vision({"observed": [phrase]})

    assert result["space_type"] == expected, (
        phrase + " -> " + result["space_type"]
    )


@pytest.mark.parametrize("phrase,expected", FUNCTION_CASES)
def test_g2_the_classification_is_cited_from_a_real_field(phrase, expected):
    result = interpret_architectural_vision({"observed": [phrase]})

    assert result["classification_basis"], phrase + ": no basis published"

    assert "observed" in result["classification_basis"][0]


def test_g3_no_new_space_types_are_created():
    for phrase, _expected in FUNCTION_CASES:

        result = interpret_architectural_vision({"observed": [phrase]})

        assert result["space_type"] in SPACE_TYPES


def test_g4_the_master_label_keeps_its_lexical_boundary():
    assert interpret_architectural_vision(
        {"observed": ["مسترپیس"]}
    )["space_type"] == "unknown"

    assert interpret_architectural_vision(
        {"observed": ["مستر"]}
    )["space_type"] == "master bedroom"


def test_g5_a_master_label_is_still_cited_from_its_own_field():
    result = interpret_architectural_vision(
        {"architectural_elements": ["master bedroom"]}, ground=False
    )

    assert result["space_type"] == "master bedroom"

    assert "architectural_elements" in result["classification_basis"][0]

    assert "text_labels_if_visible" not in result["classification_basis"][0]


# ==========================================================
# FOUR-FACADE NON-REGRESSION
# ==========================================================


def test_h1_facade_b_keeps_its_facade_classification():
    result = _interpret(_load("B"))

    assert result["space_type"] == "facade"

    assert "architectural_elements" in result["classification_basis"][0]


def test_h2_facade_c_keeps_its_unknown_uncertainty():
    result = _interpret(_load("C"))

    assert result["space_type"] == "unknown"

    assert result["classification_basis"] == []


def test_h3_facade_d_keeps_its_entrance_classification():
    result = _interpret(_load("D"))

    assert result["space_type"] == "entrance"

    assert "observed" not in result["classification_basis"][0]

    assert "architectural_elements" in result["classification_basis"][0]
