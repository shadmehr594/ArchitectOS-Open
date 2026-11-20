# -*- coding: utf-8 -*-
"""VISION_FLOOR_SUPERSESSION_TRUTH_V1 — focused CPU tests.

THE DEFECT
----------
`architectural_observation_v1._floor_observation_slot()` published

    out["superseded_by_verified"] = bool(_verified)

where `_verified` is

    _verified_floors = _provider_floors(extras) or detect_visible_floors(visible_phrases)

Both of those read the PROVIDER's OWN statement. Neither is verification. So the
flag claimed "a verified replacement superseded this observation" whenever ANY
floor reading existed — and in facade C it claimed it while
`visible_floors.count` was `null`:

    visible_floors.count                    = null
    visible_floors.count_scope              = "MULTI_STOREY_UNDETERMINED"
    visible_floors_observation.count        = 4        (provider's unverified reading)
    visible_floors_observation.verification = "UNVERIFIED"
    visible_floors_observation.authoritative = false
    visible_floors_observation.superseded_by_verified = TRUE   <- the contradiction

ACCEPTANCE PRINCIPLE
--------------------
A reported count is not a verified count.
A derived interpretation is not independent verification.
A populated field is not proof of authority.

These tests drive the real `build_architectural_observation()` on the saved
four-facade understanding records and on synthetic CPU payloads. No model call.
No new floor counting engine. No change to floor extraction or arithmetic.
"""

import json
import os

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

# Accepted floor readings, measured before this milestone and required to hold.
EXPECTED_COUNT = {"A": 1, "B": 2, "C": None, "D": 2}
EXPECTED_OBSERVATION_COUNT = {"A": 1, "B": 2, "C": 4, "D": 2}


def _load(case):
    path = os.path.join(CORPUS, FACADE_DIRS[case], "03_understanding.json")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)


def _observe(payload):
    return build_architectural_observation(payload)


def _slot(payload):
    observation = _observe(payload)

    slot = observation.get("visible_floors_observation")

    assert isinstance(slot, dict), "no visible_floors_observation was published"

    return slot


def _assert_no_false_supersession(slot, label):
    assert slot.get("superseded_by_verified") is False, (
        label + ": claimed a verified replacement that does not exist"
    )


# ==========================================================
# A — no floor count was derived or verified
# ==========================================================


def test_a1_no_reading_at_all_cannot_supersede_anything():
    slot = _slot(
        {
            "observed": ["a glass pavilion"],
            "observation_extras": {
                "visible_floors_observation": {"count": 4, "confidence": "LOW"}
            },
        }
    )

    _assert_no_false_supersession(slot, "no primary reading")


def test_a2_a_primary_reading_without_a_count_cannot_supersede():
    """The facade-C shape, in isolation: count is null, nothing was replaced."""

    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": None,
                "descriptor": "multi-storey building",
                "evidence_phrase": "multi-storey building",
            },
            "visible_floors_observation": {"count": 4, "confidence": "LOW"},
        }
    }

    observation = _observe(payload)

    assert observation["visible_floors"]["count"] is None

    _assert_no_false_supersession(
        observation["visible_floors_observation"], "null primary count"
    )


def test_a3_the_tier_invariants_still_hold():
    slot = _slot(
        {
            "observed": ["Two storeys are visible"],
            "observation_extras": {
                "visible_floors_observation": {"count": 2, "confidence": "LOW"}
            },
        }
    )

    assert slot["trust_tier"] == "PROVIDER_OBSERVATION"

    assert slot["verification"] == "UNVERIFIED"

    assert slot["authoritative"] is False

    assert slot["confidence"] == "LOW"


# ==========================================================
# B — an unverified provider count exists
# ==========================================================


def test_b1_a_provider_count_does_not_become_verified_by_being_present():
    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": 3,
                "evidence_phrase": "three storeys",
                "confidence": "MEDIUM",
            },
            "visible_floors_observation": {"count": 3, "confidence": "LOW"},
        }
    }

    observation = _observe(payload)

    assert observation["visible_floors"]["count"] == 3

    _assert_no_false_supersession(
        observation["visible_floors_observation"], "provider count"
    )


def test_b2_a_provider_asserting_verification_is_not_verification():
    """A provider-supplied `verification: VERIFIED` is still a provider claim."""

    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": 3,
                "verification": "VERIFIED",
                "authoritative": True,
                "evidence_phrase": "three storeys",
            },
            "visible_floors_observation": {"count": 4, "confidence": "LOW"},
        }
    }

    _assert_no_false_supersession(
        _slot(payload), "provider-asserted verification"
    )


# ==========================================================
# C — a derived count exists, verification remains UNVERIFIED
# ==========================================================


def test_c1_a_derived_count_is_not_a_verified_replacement():
    payload = {
        "observed": ["Two storeys are visible"],
        "observation_extras": {
            "visible_floors_observation": {"count": 2, "confidence": "LOW"}
        },
    }

    observation = _observe(payload)

    derived = observation["visible_floors"]

    assert derived["count"] == 2

    assert derived["provenance"]["source"] == "provider_phrase"

    assert derived.get("verification") != "VERIFIED"

    _assert_no_false_supersession(
        observation["visible_floors_observation"], "derived count"
    )


def test_c2_the_derived_reading_never_claims_authority():
    observation = _observe(
        {
            "observed": ["Two storeys are visible"],
            "observation_extras": {
                "visible_floors_observation": {"count": 2, "confidence": "LOW"}
            },
        }
    )

    assert observation["visible_floors"].get("authoritative") is not True


# ==========================================================
# D — facade C
# ==========================================================


def test_d1_facade_c_floor_count_stays_undetermined():
    observation = _observe(_load("C"))

    assert observation["visible_floors"]["count"] is None

    assert observation["visible_floors"]["count_scope"] == "MULTI_STOREY_UNDETERMINED"

    assert observation["visible_floors"]["count_is_total"] is False


def test_d2_facade_c_publishes_no_invented_authoritative_count():
    observation = _observe(_load("C"))

    assert observation["visible_floors"]["count"] is None

    # The provider's own reading survives, in its own lower-trust slot.
    assert observation["visible_floors_observation"]["count"] == 4

    assert observation["visible_floors_observation"]["verification"] == "UNVERIFIED"


def test_d3_facade_c_claims_no_false_supersession():
    _assert_no_false_supersession(_slot(_load("C")), "facade C")


# ==========================================================
# E — facades A, B and D
# ==========================================================


@pytest.mark.parametrize("case", ("A", "B", "D"))
def test_e1_the_supported_count_is_preserved(case):
    observation = _observe(_load(case))

    assert observation["visible_floors"]["count"] == EXPECTED_COUNT[case]

    assert observation["visible_floors"]["count_scope"] == "TOTAL"

    assert observation["visible_floors"]["count_is_total"] is True


@pytest.mark.parametrize("case", ("A", "B", "D"))
def test_e2_the_provenance_is_preserved(case):
    observation = _observe(_load(case))

    provenance = observation["visible_floors"]["provenance"]

    assert provenance["source"] == "provider_phrase"

    assert provenance["rule"] == "number_adjacent_to_floor_noun"

    assert provenance["phrase"] == observation["visible_floors"]["evidence_phrase"]


@pytest.mark.parametrize("case", ("A", "B", "D"))
def test_e3_the_observation_count_is_preserved(case):
    slot = _slot(_load(case))

    assert slot["count"] == EXPECTED_OBSERVATION_COUNT[case]

    assert slot["verification"] == "UNVERIFIED"


@pytest.mark.parametrize("case", ("A", "B", "D"))
def test_e4_a_numeric_count_does_not_imply_verification(case):
    """The core acceptance principle, applied to the three supported facades."""

    _assert_no_false_supersession(_slot(_load(case)), "facade " + case)


# ==========================================================
# F — a self-declared verified replacement is still not a verified replacement
# ==========================================================


def test_f1_a_self_declared_verified_replacement_does_not_supersede():
    """The flag must NOT be reachable from provider-controlled metadata.

    V1.1 CORRECTION — this test was `test_f1_a_genuinely_verified_replacement_
    may_supersede` and asserted `is True`, calling itself "the positive control"
    and claiming it proved "the predicate is a real condition and not a
    hardcoded False".

    It proved no such thing. The payload below reaches the builder through
    `observation_extras`, which is provider-controlled, and `_provider_floors()`
    forwards the provider's dict verbatim — so `verification`, `authoritative`
    and `provenance.source` were all written by the provider itself. The test
    fabricated the metadata it then treated as proof of provenance. Its `True`
    assertion was a demonstration of the trust-boundary bypass, not of a
    verification step.

    Reproduced before correcting this expectation: with the V1 predicate, this
    exact payload yields `superseded_by_verified is True`, and so do
    `source: "totally_trusted_thing"`, `count: True`, `count: "garbage"`,
    `count: 0` and `count: -1`. No producer in `core/vision` emits
    `verification: "VERIFIED"`, so there is no independent producer to exercise
    and no `True` case may be required.

    The test is kept — inverted — as a regression against metadata spoofing.
    """

    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": 3,
                "verification": "VERIFIED",
                "authoritative": True,
                "provenance": {
                    "source": "local_raster_geometry",
                    "rule": "independently_measured_level_bands",
                },
            },
            "visible_floors_observation": {"count": 4, "confidence": "LOW"},
        }
    }

    slot = _slot(payload)

    assert slot["superseded_by_verified"] is False, (
        "provider-controlled metadata established a verified replacement"
    )

    # The observation itself is still never promoted.
    assert slot["verification"] == "UNVERIFIED"

    assert slot["authoritative"] is False


def test_f2_a_verified_reading_without_a_count_cannot_supersede():
    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": None,
                "verification": "VERIFIED",
                "authoritative": True,
                "provenance": {"source": "local_raster_geometry"},
            },
            "visible_floors_observation": {"count": 4, "confidence": "LOW"},
        }
    }

    _assert_no_false_supersession(_slot(payload), "verified but countless")


def test_f3_an_unverified_reading_cannot_supersede_however_it_is_dressed():
    for verification in ("UNVERIFIED", "DERIVED", "PROVIDER_OBSERVED", None):

        payload = {
            "observation_extras": {
                "visible_floors": {
                    "count": 3,
                    "verification": verification,
                    "authoritative": True,
                    "provenance": {"source": "local_raster_geometry"},
                },
                "visible_floors_observation": {"count": 4, "confidence": "LOW"},
            }
        }

        _assert_no_false_supersession(_slot(payload), "verification=" + str(verification))


def test_f4_authority_is_required_not_merely_provenance():
    payload = {
        "observation_extras": {
            "visible_floors": {
                "count": 3,
                "verification": "VERIFIED",
                "authoritative": False,
                "provenance": {"source": "local_raster_geometry"},
            },
            "visible_floors_observation": {"count": 4, "confidence": "LOW"},
        }
    }

    _assert_no_false_supersession(_slot(payload), "not authoritative")


# ==========================================================
# G — conflicting provider and derived counts
# ==========================================================


def test_g1_a_conflict_is_preserved_and_neither_value_is_promoted():
    payload = {
        "observed": ["two storeys are visible"],
        "observation_extras": {
            "visible_floors": {
                "count": 9,
                "evidence_phrase": "nine storeys",
                "contradiction": "the observer also reported two storeys",
            },
            "visible_floors_observation": {
                "count": 4,
                "uncertainty": "the observer gave two incompatible counts",
            },
        },
    }

    observation = _observe(payload)

    assert observation["visible_floors"]["count"] == 9

    assert (
        observation["visible_floors"]["contradiction"]
        == "the observer also reported two storeys"
    )

    slot = observation["visible_floors_observation"]

    assert slot["count"] == 4

    assert slot["uncertainty"] == "the observer gave two incompatible counts"

    _assert_no_false_supersession(slot, "conflicting counts")


# ==========================================================
# H — cropped or partially visible buildings
# ==========================================================


def test_h1_a_cropped_building_keeps_its_framing_and_gains_no_supersession():
    payload = {
        "observed": ["Two storeys are visible but the building is cropped"],
        "observation_extras": {
            "visible_floors_observation": {"count": 2, "confidence": "LOW"}
        },
    }

    observation = _observe(payload)

    derived = observation["visible_floors"]

    assert derived["count"] == 2

    assert derived["whole_building_visible"] is False

    assert derived["countable"] is False

    _assert_no_false_supersession(
        observation["visible_floors_observation"], "cropped building"
    )


def test_h2_visible_levels_are_not_converted_into_total_floors():
    """Facade C: four reported storeys never become a five-storey total."""

    observation = _observe(_load("C"))

    assert observation["visible_floors"]["count"] is None

    assert observation["visible_floors"]["count_is_total"] is False

    assert observation["visible_floors_observation"]["count"] == 4


def test_h3_the_undetermined_scope_is_not_upgraded_to_total():
    observation = _observe(_load("C"))

    assert observation["visible_floors"]["count_scope"] != "TOTAL"


# ==========================================================
# The change is confined to the flag
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_i_the_flag_is_the_only_floor_field_this_milestone_touches(case):
    observation = _observe(_load(case))

    derived = observation["visible_floors"]

    assert derived["count"] == EXPECTED_COUNT[case]

    assert observation["visible_floors_observation"]["count"] == (
        EXPECTED_OBSERVATION_COUNT[case]
    )

    assert observation["visible_floors_observation"]["verification"] == "UNVERIFIED"

    assert observation["visible_floors_observation"]["authoritative"] is False
