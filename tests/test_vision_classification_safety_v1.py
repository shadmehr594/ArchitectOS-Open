# -*- coding: utf-8 -*-
"""VISION_CLASSIFICATION_SAFETY_V1 — RED then GREEN.

Deterministic classification safety for `core/vision/architectural_observation_v1.py`.

Every phrase below is either:
  * REAL  — copied verbatim from the saved observer output in
            `runs/vision_finished_facade_acceptance_v1/*/01_raw_observer.json`
            (note: the observer emits U+2011 NON-BREAKING HYPHEN, not ASCII '-'),
  * or SYNTHETIC — an explicit counterexample, labelled as such.

Two defect families are covered:

  A. NEGATION SCOPE — a negated enumeration only negated its first member, so
     "No doors, windows, stairs…" produced `door` absent but `window` and
     `stair` VISIBLE.

  B. FALSE SUBSTRING MATCHES — unanchored `marker in phrase` produced
     through->rough, rendered->red, street->tree->plant, and hyphenated
     modifiers invented independent elements (floor-to-ceiling -> floor +
     ceiling; wall-mounted -> wall).

The fix must NOT lose legitimate architectural vocabulary. Cases G, H, I, L
and the `arched-top` / `dark-glazed` compounds exist to prevent that.
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.vision.architectural_observation_v1 import (  # noqa: E402
    ARCHITECTURAL_ELEMENT_MARKERS,
    COLOR_MARKERS,
    MATERIAL_MARKERS,
    OBJECT_MARKERS,
    TEXTURE_MARKERS,
    _labels,
    _negation_spans,
    _positive_labels,
    build_architectural_observation,
)

H = "\u2011"  # non-breaking hyphen, as emitted by the observer

# ---------------------------------------------------------------- REAL phrases
A_NEG = ("No doors, windows, stairs, or vertical{0}circulation elements are "
         "clearly distinguishable").format(H)
B_NEG_ROOF = ("No further upper storey, attic band, or roof terrace is "
              "visible").format(H)
B_NEG_PARAPET = "No parapet, roof terrace, or occupiable top storey is shown"
C_NEG_STAIR = ("No stairs, lifts, or other vertical circulation elements are "
               "visible on the facade")
D_NEG_EXT = ("no visible external stairs, balconies, or vertical{0}circulation "
             "elements").format(H)

A_FLOOR_CEIL = "floor{0}to{0}ceiling glass curtain wall".format(H)
D_WALL_MOUNT = "two wall{0}mounted sconce lights".format(H)
A_THROUGH = ("no interior furniture, sanitary or kitchen fixtures are legible "
             "through the glass")
C_RENDERED = ("clad in light beige/cream stone or rendered masonry with "
              "horizontal rustication lines")
C_ARCHED_TOP = "top level has arched{0}top (round{0}headed) windows".format(H)
C_DARK_GLAZED = ("three stacked levels, each with a dark{0}glazed rectangular "
                 "window behind a projecting balcony").format(H)
B_GROUND_FLOOR = ("Ground floor = level with the central open doorway, the two "
                  "flanking windows, and the two{0}step stone stoop").format(H)
B_UPPER_FLOOR = "Upper floor = level of the curved balcony and its windows"
B_WALLS = ("Exterior walls clad in beige/tan veined stone or marble panels "
           "(large rectangular panels with visible joints)")
A_CURTAIN = "floor{0}to{0}ceiling glass curtain wall with thin dark "
A_ROOF_SLAB = "very deep, flat roof slab".replace("  ", " ")


def _kinds(phrase):
    # Element classification is the ONLY caller that enables compound-modifier
    # suppression — the same flag the production element builder passes.
    present, absent = _positive_labels(
        phrase, ARCHITECTURAL_ELEMENT_MARKERS,
        suppress_compound_modifiers=True)
    return present, absent


# ============================================================
# A. Full coordinated negation across door, window and stair
# ============================================================


def test_A_coordinated_negation_covers_every_member():
    present, absent = _kinds(A_NEG)
    for label in ("door", "window", "stair"):
        assert label not in present, (
            "negated %r was promoted to a VISIBLE element" % label)
        assert label in absent, "negated %r was not recorded as absent" % label


def test_A_coordinated_negation_roof_terrace():
    present, absent = _kinds(B_NEG_ROOF)
    assert "roof" not in present
    assert "roof" in absent


def test_A_coordinated_negation_parapet_terrace():
    present, absent = _kinds(B_NEG_PARAPET)
    assert "roof" not in present
    assert "parapet" in absent


def test_A_coordinated_negation_stair_list():
    present, absent = _kinds(C_NEG_STAIR)
    assert "stair" not in present
    assert "stair" in absent
    # `facade` here is the LOCATION of the observation, not a negated element.
    # The scope must stop at the predicate so the facade is not recorded as
    # absent. (Its classification as a visible element is pre-existing and
    # unchanged by this milestone — see the residual note in the report.)
    assert "facade" not in absent, (
        "the predicate must not drag the location noun into the negation")


def test_A_coordinated_negation_external_stairs_balconies():
    present, absent = _kinds(D_NEG_EXT)
    assert "stair" not in present
    assert "balcony" not in present
    # V1_1 — this test previously passed VACUOUSLY: `balcony` matched nothing
    # at all (the plural `balconies` was unrecognised), so "not in present"
    # was trivially true while the absence classification was silently lost.
    # Requiring the ABSENT bucket is what makes it a real assertion.
    assert "stair" in absent
    assert "balcony" in absent, (
        "a negated plural must be recorded as absent, not silently dropped")


# ============================================================
# B. Restricted negation and "other than" exceptions
# ============================================================


def test_B_other_than_exception_stays_positive():
    # SYNTHETIC counterexample for the exception rule.
    present, absent = _kinds("no visible columns other than the ground-floor piers")
    assert "column" in absent
    assert "pier" in present, "the 'other than' exception must stay positive"


def test_B_except_exception_stays_positive():
    present, absent = _kinds("no openings except the two doorways")
    assert "opening" in absent
    assert "door" in present


# ============================================================
# C. True positive survives a separate scoped negative
# ============================================================


def test_C_positive_window_survives_separate_negative():
    # SYNTHETIC: two independent clauses, opposite polarity.
    present, absent = _kinds(
        "No doors are visible. Two rectangular windows with white frames are visible.")
    assert "window" in present
    assert "door" in absent


def test_C_positive_survives_in_the_next_phrase():
    present, _ = _kinds(B_WALLS)
    assert "wall" in present


# ============================================================
# D–F. Embedded substrings must not become labels
# ============================================================


def test_D_through_is_not_rough():
    assert _labels(A_THROUGH, TEXTURE_MARKERS) == []


def test_D_through_is_not_rough_minimal():
    assert _labels("leading to a view through to the other side", TEXTURE_MARKERS) == []


def test_E_street_is_not_tree():
    street = "Foreground asphalt street with painted lines and a paved footway"
    assert _labels(street, OBJECT_MARKERS) == []


def test_F_rendered_is_not_red():
    # The facade IS beige — that colour is genuine and must survive.
    # Only the spurious `red` (from "RED-ered") must disappear.
    labels = _labels(C_RENDERED, COLOR_MARKERS)
    assert "red" not in labels
    assert "beige" in labels


def test_F_rendered_is_not_red_minimal():
    assert _labels("rendered masonry", COLOR_MARKERS) == []


# ============================================================
# G–I. Genuine vocabulary must survive the fix
# ============================================================


def test_G_genuine_rough_stone_stays_rough():
    assert "rough" in _labels("rough stone", TEXTURE_MARKERS)


def test_G_genuine_raw_concrete_stays_rough():
    assert "rough" in _labels("raw concrete", TEXTURE_MARKERS)


def test_H_genuine_red_brick_stays_red():
    assert "red" in _labels("red brick", COLOR_MARKERS)


def test_H_genuine_dark_frame_stays_dark():
    assert "dark" in _labels("dark-framed glass doors", COLOR_MARKERS)


def test_I_real_tree_is_vegetation():
    assert "plant" in _labels("a mature tree at the left edge", OBJECT_MARKERS)


def test_I_real_plant_is_vegetation():
    assert "plant" in _labels("potted shrubs/plants at the base", OBJECT_MARKERS)


# ============================================================
# J–K. Hyphenated modifiers must not invent elements
# ============================================================


def test_J_floor_to_ceiling_does_not_invent_floor_or_ceiling():
    present, _ = _kinds(A_FLOOR_CEIL)
    assert "floor" not in present, "'floor-to-ceiling' must not assert a floor"
    assert "ceiling" not in present, "'floor-to-ceiling' must not assert a ceiling"
    assert "wall" in present, "the curtain wall itself is still a wall"


def test_K_wall_mounted_keeps_fixture_without_inventing_wall():
    present, _ = _kinds(D_WALL_MOUNT)
    assert "light_fixture" in present
    assert "wall" not in present


# ============================================================
# L. Independently supported floor / ceiling / wall stay valid
# ============================================================


def test_L_independent_ground_floor_is_a_floor():
    present, _ = _kinds(B_GROUND_FLOOR)
    assert "floor" in present


def test_L_independent_upper_floor_is_a_floor():
    present, _ = _kinds(B_UPPER_FLOOR)
    assert "floor" in present


def test_L_independent_ceiling_is_a_ceiling():
    present, _ = _kinds("an exposed coffered ceiling above the gallery")
    assert "ceiling" in present


def test_L_independent_wall_is_a_wall():
    present, _ = _kinds("Exterior walls clad in stone panels")
    assert "wall" in present


def test_L_arched_top_compound_still_asserts_arch():
    # REAL: suppressing every hyphenated compound would destroy this.
    present, _ = _kinds(C_ARCHED_TOP)
    assert "arch" in present


def test_L_dark_glazed_compound_still_asserts_glazing():
    present, _ = _kinds(C_DARK_GLAZED)
    assert "window" in present


@pytest.mark.parametrize("phrase,expected", [
    # Closed compounds / derivations whose HEAD is the marker. The table
    # already lists `doorway`, `staircase`, `archway`, `pilastered`,
    # `louvered`; these four were the only ones the boundary rule lost on the
    # real evidence and the saved fixtures, so they are recorded explicitly.
    ("Flat roofline with a thin parapet / coping edge at the very top", "roof"),
    ("a covered entryway at the side", "entrance"),
    ("a fourth smaller balustraded ledge at the top", "railing"),
    ("a segmental pedimented bay crowning the facade", "pediment"),
])
def test_L_closed_compounds_keep_their_head_element(phrase, expected):
    present, _ = _kinds(phrase)
    assert expected in present, (
        "%r lost the %r label to the word-boundary rule" % (phrase, expected))


# ============================================================
# M–N. Provenance and negativity channel
# ============================================================


def _observation(raw_text):
    return build_architectural_observation({"observed": [raw_text]})


def test_M_evidence_phrase_is_verbatim():
    obs = _observation(A_FLOOR_CEIL)
    for element in obs.get("architectural_elements") or []:
        assert element["evidence_phrase"] == A_FLOOR_CEIL


def test_M_raw_observations_preserved_verbatim():
    obs = _observation(A_NEG)
    assert A_NEG in json.dumps(obs.get("raw_observations"), ensure_ascii=False)


def test_N_negatives_are_absent_not_visible():
    obs = _observation(A_NEG)
    negative = obs.get("negative_observations") or []
    assert negative, "the coordinated negative produced no absence record"
    for record in negative:
        assert record["status"] == "absent"
    visible_kinds = {k for e in (obs.get("architectural_elements") or [])
                     for k in (e.get("kind") or [])}
    assert "window" not in visible_kinds
    assert "stair" not in visible_kinds


def test_N_negatives_carry_no_authority():
    obs = _observation(B_NEG_PARAPET)
    for record in obs.get("negative_observations") or []:
        assert record["status"] == "absent"
        assert record.get("authoritative") is not True
        assert record.get("verification") != "VERIFIED"


# ============================================================
# P. No acceptance-image identity is hardcoded
# ============================================================


def test_P_no_acceptance_image_identity_in_production_module():
    module_path = os.path.join(ROOT, "core", "vision",
                               "architectural_observation_v1.py")
    with open(module_path, encoding="utf-8") as fh:
        source = fh.read()
    for token in ("neue_nationalgalerie", "ref_10", "ref_14",
                  "image_003_977264", "finished_facade_corpus",
                  "vision_finished_facade_acceptance"):
        assert token not in source, "acceptance identity %r leaked into production" % token


def test_P_floor_counts_come_from_text_not_identity():
    from core.vision.architectural_observation_v1 import detect_visible_floors
    four = detect_visible_floors(["Four storeys visible in total"])
    five = detect_visible_floors(["Five storeys are visible"])
    assert four and four.get("count") == 4
    assert five and five.get("count") == 5


# ============================================================
# Q. Material ontology untouched by this milestone
# ============================================================


def test_Q_material_label_set_gained_family_and_alloy_identities():
    """CHANGED by VISION_MATERIAL_SEMANTICS_V1 (was: the V1 ten-label list).

    `metal` and `aluminium` are new identities. Without them the only way to
    name a generic metal was to claim the specific alloy `steel`, which the
    ontology does not even have. The ten original labels are all still here
    and in the same relative order.
    """
    assert [label for label, _ in MATERIAL_MARKERS] == [
        "concrete", "glass", "wood", "stone", "brick", "steel", "metal",
        "aluminium", "tile", "plaster", "composite", "masonry"]


def test_Q_generic_metal_no_longer_resolves_to_steel():
    """FORMERLY `test_Q_metal_still_resolves_to_steel_known_defect`.

    The defect is now fixed at its owner. A generic material family is not an
    alloy: "metal/wood trim" asserts wood and metal, never steel. See
    `tests/test_vision_material_semantics_v1.py` for the full M1 matrix.
    """
    assert _labels("Dark (black) painted metal/wood trim", MATERIAL_MARKERS) == [
        "wood", "metal"]


def test_Q_disjunctive_materials_are_listed_lexically_but_not_asserted():
    """FORMERLY `test_Q_disjunctive_materials_still_collapse_known_defect`.

    `_labels()` is the LEXICAL layer: it lists the material terms a phrase
    contains, and "stone" is the group that covers marble. Deciding which of
    them the observer actually ASSERTED is `_material_semantics()`'s job, and
    there both sides of the "or" are withheld — see
    `tests/test_vision_material_semantics_v1.py::test_M3_*`.

    `composite` is gone from this phrase because "panel" no longer implies it.
    """
    assert _labels("beige/tan veined stone or marble panels", MATERIAL_MARKERS) == [
        "stone"]


@pytest.mark.parametrize("phrase,expected", [
    # Material vocabulary the boundary rule must not silently drop. `rendered`
    # and `tiled` are the -ed forms of existing markers; without them the
    # disjunction defect would look "fixed" merely because the evidence
    # disappeared, which is exactly the confusion this milestone forbids.
    ("filled with a tiled/mosaic dome pattern", "tile"),
    ("clad in stone or rendered masonry", "plaster"),
])
def test_Q_material_vocabulary_survives_the_boundary_rule(phrase, expected):
    assert expected in _labels(phrase, MATERIAL_MARKERS)
