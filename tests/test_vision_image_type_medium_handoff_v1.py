# -*- coding: utf-8 -*-
"""VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1 — focused CPU tests.

TWO FACTS, KEPT APART
---------------------
  * WHAT KIND OF SOURCE IMAGE THIS IS      -> `image_medium`   (photograph / rendering / drawing)
  * WHAT ARCHITECTURAL SCENE IT DEPICTS    -> `image_type`     (interior / exterior / mixed / plan / diagram / unknown)

The four-facade audit reported `image_type = "unknown"` on A/B/C/D and read it as
a lost handoff. The preflight falsifies the causal story: the drawing-type
observation IS carried into the understanding record as
`provider_drawing_type` (raw text + canonical family + verification state). What
is genuinely missing is a CANONICAL MEDIUM — `canonical_drawing_type()` collapses
"photograph" and "rendering" into the single family
`architectural_render_or_photo`, so no consumer can tell a photograph from a
render without re-parsing free text.

`image_type` is `unknown` on all four for a different, deliberate reason:
`_image_type_evidence` refuses to let a MODEL observation set the canonical type
(`basis: "PROVIDER_OBSERVED"`, `VISION_RETENTION_FIX_V2`). These tests require
that gate to stay exactly as it is — a populated handoff field must never make a
value independently verified.

CPU ONLY. No model calls. No Ollama. No GPU. No ComfyUI. No image inference.
The four-facade payloads are the saved `03_understanding.json` artefacts and are
replayed through the real bridge function, never re-observed.
"""

import hashlib
import json
import os
from collections import Counter

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)
from core.vision.architectural_vision_interpreter_v1 import (
    ArchitecturalVisionInterpreterV1,
)
from core.vision.drawing_type_v1 import (
    CANONICAL_MEDIA,
    canonical_drawing_type,
    canonical_medium,
)
from core.vision.image_understanding_v1 import _build_bridge_understanding


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

# The medium the provider itself stated, per facade. Written out independently
# of the implementation: these are the provider's own words, quoted in
# `provider_drawing_type.text`.
EXPECTED_MEDIUM = {
    "A": "photograph",   # "colour photograph of a built structure"
    "B": "photograph",   # "Photograph of a building exterior (front facade)"
    "C": "rendering",    # "3D architectural rendering (perspective elevation ...)"
    "D": "photograph",   # "Photographic exterior elevation (facade) ..."
}

# The scene category these tests REQUIRE to stay unknown. None of the four may be
# upgraded to "exterior" merely because the medium is a photograph or a render.
EXPECTED_SCENE = {case: "unknown" for case in FACADE_DIRS}

# Accepted space types from VISION_SPACE_TYPE_EVIDENCE_DISCIPLINE_V1.
EXPECTED_SPACE_TYPE = {
    "A": "unknown",
    "B": "facade",
    "C": "unknown",
    "D": "entrance",
}


def _load(case):
    path = os.path.join(CORPUS, FACADE_DIRS[case], "03_understanding.json")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)


def _rebuild(saved):
    """Re-run the REAL bridge adapter on the saved normalizer record.

    No model call: the bridge payload (normalizer output + raw observer text) is
    the one saved with the acceptance corpus.
    """

    return _build_bridge_understanding(
        saved["visual_observer_bridge"],
        provider=saved["provider"],
        model=saved["model"],
        image_id=saved["image_id"],
        source_type=saved["source_type"],
        source_hash=saved["source_hash"],
        local_plan_reading=saved.get("local_plan_reading"),
    )


def _medium_of(record):
    value = record.get("image_medium")

    assert isinstance(value, dict), "image_medium is missing from the understanding record"

    return value


# ==========================================================
# VISION_RETENTION_BASELINE_MIGRATION_V1 — the accepted layer
#
# `test_23` used to assert that a CPU replay reproduces the saved observation
# layer EXACTLY. That was true while the saved corpus was current. The corpus
# was captured BEFORE `DESCRIPTIVE_ARCHITECTURAL_CLAIM_RETENTION_V1`, which
# deliberately admits descriptive architectural claims into the observation
# layer. The identity expectation is therefore obsolete for exactly the fields
# that change carries — and for nothing else.
#
# The historical snapshots are NOT rewritten. The accepted post-retention layer
# is pinned in a versioned fixture whose provenance hashes are checked against
# the corpus on every run, so the fixture cannot silently drift onto a
# different snapshot or a different code state.
# ==========================================================

BASELINE_PATH = os.path.join(ROOT, "tests", "fixtures", "vision",
                             "retention_baseline_v1.json")

#: The only two verifier reasons a retained provider claim may rest on.
ALLOWED_ATTRIBUTION_REASONS = (
    "no_applicable_independent_corroboration",
    "claim_properties_not_verified",
)

#: A retained claim must never be able to invent an architectural level.
FLOOR_KINDS = frozenset(("floor", "storey", "story", "level"))


def _baseline():
    with open(BASELINE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _element_multiset(elements):
    """Element identity is (kinds, phrase): the same phrase with a different
    kind set is a different claim, and the same claim twice is a duplicate."""

    return Counter((tuple(entry.get("kind") or ()), entry.get("evidence_phrase"))
                   for entry in elements)


def _material_multiset(entries):
    return Counter(json.dumps(entry, ensure_ascii=False, sort_keys=True)
                   for entry in entries or [])


# ==========================================================
# 1. THE VOCABULARY ITSELF — medium is NOT the scene vocabulary
# ==========================================================


def test_1_medium_vocabulary_is_its_own_closed_set():
    assert set(CANONICAL_MEDIA) == {"photograph", "rendering", "drawing", "unknown"}


def test_2_medium_vocabulary_shares_no_value_with_the_scene_vocabulary():
    """A photograph is not a scene; an exterior is not a medium."""

    scene = {
        "architectural_render_or_photo",
        "facade_or_elevation",
        "floor_plan_or_sketch",
        "site_diagram",
        "unknown",
    }

    overlap = (set(CANONICAL_MEDIA) & scene) - {"unknown"}

    assert overlap == set(), "medium and scene vocabularies overlap: " + str(overlap)


def test_3_medium_never_returns_a_scene_value():
    for text in (
        "photograph of a building exterior",
        "3D rendering of an interior space",
        "floor plan drawing",
        "site diagram",
        "exterior",
        "interior",
    ):

        assert canonical_medium(text)["medium"] in CANONICAL_MEDIA


# ==========================================================
# 2. THE FOUR REAL FACADES — the medium survives the handoff
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_4_the_medium_survives_the_normalizer_to_understanding_handoff(case):
    rebuilt = _rebuild(_load(case))

    assert _medium_of(rebuilt)["medium"] == EXPECTED_MEDIUM[case]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_5_the_medium_quotes_the_provider_verbatim(case):
    saved = _load(case)

    record = _medium_of(_rebuild(saved))

    provider_text = (saved.get("provider_drawing_type") or {}).get("text")

    assert record["evidence_text"] == provider_text


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_6_the_medium_is_never_verified(case):
    record = _medium_of(_rebuild(_load(case)))

    assert record["verified"] is False

    assert record["source"] == "MODEL_OBSERVED"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_7_the_medium_is_not_the_drawing_type(case):
    """The two facts are published side by side, never merged."""

    saved = _load(case)

    rebuilt = _rebuild(saved)

    assert "medium" not in rebuilt.get("provider_drawing_type", {})

    assert "canonical" not in _medium_of(rebuilt)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_8_the_canonical_image_type_is_untouched(case):
    saved = _load(case)

    rebuilt = _rebuild(saved)

    assert rebuilt["image_type"] == saved["image_type"] == "unknown"

    assert rebuilt["image_type_evidence"]["canonical_image_type"] == "unknown"

    assert rebuilt["image_type_evidence"]["basis"] == "PROVIDER_OBSERVED"


# ==========================================================
# 3. MEDIUM IS NEVER ASSUMED TO BE A SCENE
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_9_a_photograph_is_never_assumed_to_be_exterior(case):
    rebuilt = _rebuild(_load(case))

    scene = build_architectural_observation(rebuilt)["image_type"]

    assert scene == EXPECTED_SCENE[case], (
        "the scene category changed because the medium is now known: " + scene
    )

    assert scene != "exterior"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_10_a_render_is_never_assumed_to_be_exterior(case):
    """Same rule for the one render in the corpus."""

    rebuilt = _rebuild(_load(case))

    scene = build_architectural_observation(rebuilt)["image_type"]

    assert scene != "exterior"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_11_the_render_or_photo_family_maps_to_mixed_not_exterior(case):
    """The scene vocabulary's own rule: render-or-photo is neutral about scene."""

    from core.vision.architectural_observation_v1 import _refine_image_type

    assert _refine_image_type("architectural_render_or_photo", "") == "mixed"


# ==========================================================
# 4. SYNTHETIC MEDIUM / SCENE MATRIX
# ==========================================================

SYNTHETIC = (
    # (label, drawing-type text, expected medium)
    ("interior photograph", "Interior photograph of a living room", "photograph"),
    ("exterior photograph", "Exterior photograph of a building facade", "photograph"),
    ("interior render", "3D rendering of an interior space", "rendering"),
    ("exterior render", "3D rendering of the exterior facade", "rendering"),
    ("architectural plan", "Architectural floor plan drawing", "drawing"),
    ("diagram", "Site diagram of the plot", "drawing"),
    ("unrecognised value", "holographic scan of the site", "unknown"),
)


@pytest.mark.parametrize("label,text,expected", SYNTHETIC)
def test_12_the_medium_is_read_from_the_stated_text(label, text, expected):
    assert canonical_medium(text)["medium"] == expected, label


@pytest.mark.parametrize("label,text,expected", SYNTHETIC)
def test_13_a_scene_word_in_the_text_is_not_the_medium(label, text, expected):
    """`exterior` / `interior` in the text must not become the medium."""

    assert canonical_medium(text)["medium"] != "exterior", label

    assert canonical_medium(text)["medium"] != "interior", label


def test_14_a_missing_drawing_type_is_unknown_not_a_guess():
    assert canonical_medium(None)["medium"] == "unknown"

    assert canonical_medium("")["medium"] == "unknown"


def test_15_a_missing_drawing_type_handoff_publishes_unknown():
    saved = _load("A")

    saved["visual_observer_bridge"] = dict(saved["visual_observer_bridge"])

    rebuilt = _rebuild(saved)

    # The saved corpus always carries a drawing type; the empty case is proved
    # directly against the vocabulary instead.
    assert canonical_medium(None)["basis"] == "NO_DRAWING_TYPE_OBSERVATION"

    assert _medium_of(rebuilt)["medium"] in CANONICAL_MEDIA


def test_16_conflicting_descriptions_are_unknown_not_a_coin_flip():
    result = canonical_medium("a photograph, possibly a rendering, of the facade")

    assert result["medium"] == "unknown"

    assert result["basis"] == "CONFLICTING_MEDIUM_EVIDENCE"


def test_17_a_negated_medium_does_not_contribute():
    """The real facade-A text: 'a colour photograph ... (not a drawing, plan, or section)'."""

    text = (
        "This is a colour photograph of a built structure "
        "(not a drawing, plan, or section)."
    )

    assert canonical_medium(text)["medium"] == "photograph"


def test_18_a_negated_photograph_is_not_a_photograph():
    assert canonical_medium("This is not a photograph; it is a 3D rendering")["medium"] == "rendering"


def test_19_an_unrecognised_value_does_not_become_unknown_medium_with_a_scene():
    result = canonical_medium("holographic scan")

    assert result["medium"] == "unknown"

    assert result["basis"] == "NO_MEDIUM_EVIDENCE"


# ==========================================================
# 5. SCENE CLASSIFICATION STAYS INDEPENDENT OF THE MEDIUM
# ==========================================================


@pytest.mark.parametrize(
    "label,upstream,expected_scene",
    (
        ("interior photograph", "architectural_render_or_photo", "interior"),
        ("exterior photograph", "architectural_render_or_photo", "exterior"),
        ("interior render", "architectural_render_or_photo", "interior"),
        ("exterior render", "architectural_render_or_photo", "exterior"),
        ("architectural plan", "floor_plan_or_sketch", "plan"),
        ("diagram", "site_diagram", "diagram"),
    ),
)
def test_20_the_scene_comes_from_scene_evidence_not_from_the_medium(
    label, upstream, expected_scene
):
    payload = {
        "image_type": upstream,
        "observed": [label + " of the building"],
    }

    observation = build_architectural_observation(payload)

    assert observation["image_type"] == expected_scene, (
        label + " -> " + observation["image_type"]
    )


def test_21_an_unknown_scene_stays_unknown_even_with_a_known_medium():
    """The four facades: medium known, scene unknown. No promotion."""

    rebuilt = _rebuild(_load("A"))

    assert _medium_of(rebuilt)["medium"] == "photograph"

    assert build_architectural_observation(rebuilt)["image_type"] == "unknown"


# ==========================================================
# 6. PROVENANCE AND NON-REGRESSION
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_22_the_normalizer_evidence_is_untouched(case):
    saved = _load(case)

    rebuilt = _rebuild(saved)

    assert rebuilt["provider_drawing_type"] == saved["provider_drawing_type"]

    assert rebuilt["image_type_evidence"] == saved["image_type_evidence"]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_23_the_observation_layer_is_untouched(case):
    """A CPU replay must reproduce the accepted observation layer exactly.

    Replay is identity for every field EXCEPT the two the authorised retention
    change moves: `architectural_elements` and `material_observations`. For
    those, the difference is pinned to the exact authorised delta. Anything
    else — a lost element, an unexplained addition, a promoted claim, a new
    floor — fails.
    """

    saved = _load(case)

    rebuilt = _rebuild(saved)

    before = build_architectural_observation(saved)

    after = build_architectural_observation(rebuilt)

    baseline = _baseline()

    assert baseline["contract"] == "VISION_RETENTION_BASELINE_V1"

    # ---- PROVENANCE: the baseline belongs to THIS corpus snapshot ----------
    corpus_file = os.path.join(CORPUS, FACADE_DIRS[case], "03_understanding.json")

    assert baseline["corpus_sha256"][case] == _sha256(corpus_file), (
        case + ": the saved snapshot is not the one the baseline was taken from")

    expected = baseline["facades"][case]

    # ---- 1. every field the retention change does not touch is unchanged ---
    for field in (
        "image_type",
        "furniture_elements",
        "negative_observations",
        "unclassified_observations",
        "visible_floors",
        "text_labels_if_visible",
        "provenance",
    ):

        assert after.get(field) == before.get(field), case + ": " + field + " changed"

    # ---- 2. the accepted post-retention element list, in order -------------
    assert after["architectural_elements"] == expected["elements"], (
        case + ": the observation layer is not the accepted post-retention layer")

    assert len(after["architectural_elements"]) == expected["current_element_count"]

    assert len(before["architectural_elements"]) == expected["historical_element_count"]

    # ---- 3. nothing historical was lost or rewritten ----------------------
    before_elements = _element_multiset(before["architectural_elements"])

    after_elements = _element_multiset(after["architectural_elements"])

    assert before_elements - after_elements == Counter(), (
        case + ": a historical architectural element disappeared")

    # ---- 4. the difference is EXACTLY the authorised retention delta -------
    expected_delta = Counter(
        (tuple(entry["kind"]), entry["evidence_phrase"])
        for entry in expected["retained_delta"]
    )

    assert after_elements - before_elements == expected_delta, (
        case + ": the observation gained elements outside the authorised delta")

    assert sum(expected_delta.values()) == len(expected["retained_delta"])

    # ---- 5. a duplicate provider path is not a second physical element -----
    phrases = [entry["evidence_phrase"] for entry in after["architectural_elements"]]

    assert len(set(phrases)) == len(phrases), (
        case + ": the same evidence phrase is counted twice")

    # ---- 6. materials move only where a retained claim states a material ---
    assert after["material_observations"] == expected["material_observations"], (
        case + ": material observations are not the accepted post-retention set")

    before_materials = _material_multiset(before["material_observations"])

    after_materials = _material_multiset(after["material_observations"])

    assert before_materials - after_materials == Counter(), (
        case + ": a historical material observation disappeared")

    assert (after_materials - before_materials) == _material_multiset(
        expected["material_delta"]), (
        case + ": material observations grew outside the authorised delta")

    retained_phrases = {entry["evidence_phrase"] for entry in expected["retained_delta"]}

    for entry in expected["material_delta"]:

        assert entry["evidence_phrase"] in retained_phrases, (
            case + ": material growth is not sourced from a retained claim")

    # ---- 7. TRUST: retention is not verification --------------------------
    candidates = {}

    for candidate in rebuilt.get("provider_candidates") or []:

        candidates.setdefault(candidate.get("text"), []).append(candidate)

    for entry in expected["retained_delta"]:

        phrase = entry["evidence_phrase"]

        claims = candidates.get(phrase) or []

        assert claims, case + ": retained element has no saved provider claim: " + phrase

        assert entry["admission_reason"] in ALLOWED_ATTRIBUTION_REASONS

        assert all(claim.get("grounded") is False for claim in claims), (
            case + ": a retained claim is grounded: " + phrase)

        assert all(claim.get("state") != "CONFIRMED" for claim in claims), (
            case + ": a retained claim was promoted to CONFIRMED: " + phrase)

        assert all((claim.get("verification") or {}).get("local_evidence") == []
                   for claim in claims), (
            case + ": a retained claim carries local evidence: " + phrase)

        assert any((claim.get("verification") or {}).get("reason")
                   in ALLOWED_ATTRIBUTION_REASONS for claim in claims), (
            case + ": a retained claim rests on a non-attributable reason: " + phrase)

        assert all(claim.get("polarity") != "ABSENT" for claim in claims), (
            case + ": a negated claim was retained as a visible element: " + phrase)

        # ---- 8. retention invents no architectural level -------------------
        assert not (set(entry["kind"]) & FLOOR_KINDS), (
            case + ": a retained claim invented a floor kind: " + phrase)

    # ---- 9. the authoritative readings are the accepted ones --------------
    assert (after["visible_floors"] or {}).get("count") == expected["visible_floors_count"]

    assert ArchitecturalVisionInterpreterV1().interpret(rebuilt)["space_type"] == (
        expected["space_type"])


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_24_the_space_type_does_not_regress(case):
    result = ArchitecturalVisionInterpreterV1().interpret(_rebuild(_load(case)))

    assert result["space_type"] == EXPECTED_SPACE_TYPE[case]


def test_25_facade_a_is_still_not_a_bedroom():
    result = ArchitecturalVisionInterpreterV1().interpret(_rebuild(_load("A")))

    assert result["space_type"] != "bedroom"

    assert "bedroom" not in " ".join(result.get("possible_function") or [])


def test_26_facade_c_floor_count_is_not_upgraded():
    rebuilt = _rebuild(_load("C"))

    floors = build_architectural_observation(rebuilt)["visible_floors"]

    assert floors["count"] is None

    assert floors["provenance"]["rule"] == "multi_storey_descriptor"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_27_no_value_becomes_verified_because_the_field_is_populated(case):
    rebuilt = _rebuild(_load(case))

    assert _medium_of(rebuilt)["verified"] is False

    assert rebuilt["image_type_evidence"]["provider_is_authoritative"] is False

    assert rebuilt["image_type"] == "unknown"


def test_28_the_medium_is_a_projection_not_a_second_classifier():
    """`canonical_medium` must not decide the drawing family, and vice versa."""

    text = "3D architectural rendering (perspective elevation of a building facade)"

    assert canonical_drawing_type(text) == "architectural_render_or_photo"

    assert canonical_medium(text)["medium"] == "rendering"
