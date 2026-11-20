# -*- coding: utf-8 -*-
"""VISION_FLOOR_VERIFICATION_TRUST_BOUNDARY_V1_1 — focused CPU tests.

THE DEFECT
----------
`VISION_FLOOR_SUPERSESSION_TRUTH_V1` fixed the ordinary false-supersession case
by rejecting two provider provenance strings. That was a check on the CONTENT of
the payload, not on the TRUSTWORTHINESS of the producer. `_provider_floors()`
returns `_floor_defaults(dict(value))`, which preserves every field the provider
supplied — including `verification`, `authoritative` and `provenance`. So a
provider-controlled `observation_extras["visible_floors"]` could simply declare
itself independently verified:

    {"visible_floors": {"count": 3,
                        "verification": "VERIFIED",
                        "authoritative": True,
                        "provenance": {"source": "local_raster_geometry"}},
     "visible_floors_observation": {"count": 2}}
    -> visible_floors_observation.superseded_by_verified == True

No independent verification occurred. The string `local_raster_geometry` is a
CLAIM about provenance; it is not proof of provenance. The same hole accepted
`True`, `False`, "garbage", "3", 0 and -1 as floor counts.

ACCEPTANCE PRINCIPLE
--------------------
Verification is determined by the trustworthiness of the evidence source, not by
strings contained inside the evidence. A model cannot verify itself by writing
`VERIFIED`. A source name is a claim about provenance, not proof of provenance.

These tests drive the real `build_architectural_observation()`. No model call, no
new verification engine, no change to floor extraction or to the values of
`visible_floors`.
"""

import ast
import json
import os

import pytest

from core.vision.architectural_observation_v1 import (
    _FLOOR_INDEPENDENT_PRODUCERS,
    _floor_reading_is_verified,
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

# Accepted floor readings, measured at acceptance time and required to hold.
EXPECTED_COUNT = {"A": 1, "B": 2, "C": None, "D": 2}
EXPECTED_OBSERVATION_COUNT = {"A": 1, "B": 2, "C": 4, "D": 2}
EXPECTED_SCOPE = {
    "A": "TOTAL",
    "B": "TOTAL",
    "C": "MULTI_STOREY_UNDETERMINED",
    "D": "TOTAL",
}


def _load(case):
    path = os.path.join(CORPUS, FACADE_DIRS[case], "03_understanding.json")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)


def _load_saved_observation(case):
    path = os.path.join(CORPUS, FACADE_DIRS[case], "05_architectural_observation.json")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)


def _observe(payload):
    return build_architectural_observation(payload)


def _slot(payload):
    observation = _observe(payload)

    slot = observation.get("visible_floors_observation")

    assert isinstance(slot, dict), "no visible_floors_observation was published"

    return slot


def _spoof(**overrides):
    """A provider payload that declares itself independently verified."""

    reading = {
        "count": 3,
        "verification": "VERIFIED",
        "authoritative": True,
        "provenance": {"source": "local_raster_geometry"},
    }

    reading.update(overrides)

    return {
        "observed": ["a brick facade"],
        "observation_extras": {
            "visible_floors": reading,
            "visible_floors_observation": {"count": 2, "confidence": "LOW"},
        },
    }


def _assert_not_superseded(slot, label):
    assert slot.get("superseded_by_verified") is False, (
        label + ": a provider-controlled payload established a verified "
        "replacement. Verification must come from the producer, not the payload."
    )


# ==========================================================
# A — the independently reproduced bypass
# ==========================================================


def test_a1_provider_declared_verification_does_not_supersede():
    """The exact payload from the defect report, through the real builder."""

    slot = _slot(_spoof())

    _assert_not_superseded(slot, "provider declared VERIFIED + local_raster_geometry")


def test_a2_the_observation_still_records_that_it_was_not_adopted():
    slot = _slot(_spoof())

    assert slot["count"] == 2

    assert slot["verification"] == "UNVERIFIED"


# ==========================================================
# B — an arbitrary nonempty source string
# ==========================================================


@pytest.mark.parametrize(
    "source",
    (
        "totally_trusted_thing",
        "oracle",
        "x",
        "local_raster_geometry_v2",
        "architectos.verify.floors",
    ),
)
def test_b1_an_arbitrary_source_name_does_not_supersede(source):
    slot = _slot(_spoof(provenance={"source": source}))

    _assert_not_superseded(slot, "arbitrary source " + source)


# ==========================================================
# C — the provider's own derivation paths
# ==========================================================


@pytest.mark.parametrize("source", ("provider_phrase", "provider_statement"))
def test_c1_the_provider_path_names_never_supersede(source):
    slot = _slot(_spoof(provenance={"source": source}))

    _assert_not_superseded(slot, "provider path " + source)


# ==========================================================
# D — a valid count does not make a self-declared source independent
# ==========================================================


@pytest.mark.parametrize(
    "source",
    ("local_plan_elements_v1", "local_plan_sheet_v1", "local_raster_symbol_topology"),
)
def test_d1_a_real_internal_module_name_is_still_only_a_claim(source):
    """These names exist in the codebase — which is precisely why trusting a
    string that resembles one is unsafe."""

    slot = _slot(_spoof(count=3, provenance={"source": source}))

    _assert_not_superseded(slot, "real-looking internal name " + source)


def test_d2_a_fully_well_formed_reading_still_does_not_supersede():
    """Every key a verification record would carry, all plausible, all fake."""

    slot = _slot(
        _spoof(
            count=3,
            confidence="HIGH",
            count_scope="TOTAL",
            countable=True,
            provenance={
                "source": "local_raster_geometry",
                "rule": "independently_measured_level_bands",
                "phrase": "three storeys",
            },
        )
    )

    _assert_not_superseded(slot, "well-formed synthetic verification record")


# ==========================================================
# E — a non-null count is not necessarily a valid count
# ==========================================================


@pytest.mark.parametrize(
    "count",
    (True, False, "garbage", "3", 0, -1, None, 2.7, [3], {"n": 3}, 0.0, " "),
)
def test_e1_an_invalid_count_cannot_establish_a_verified_replacement(count):
    slot = _slot(_spoof(count=count))

    _assert_not_superseded(slot, "invalid count " + repr(count))


# ==========================================================
# F — ordinary provider-derived floor readings
# ==========================================================


def test_f1_a_plain_provider_dict_count_does_not_supersede():
    slot = _slot(
        {
            "observed": ["a brick facade"],
            "observation_extras": {
                "visible_floors": {"count": 4},
                "visible_floors_observation": {"count": 2},
            },
        }
    )

    _assert_not_superseded(slot, "plain provider dict")


def test_f2_a_bare_numeric_provider_count_does_not_supersede():
    slot = _slot(
        {
            "observed": ["a brick facade"],
            "observation_extras": {
                "visible_floors": 4,
                "visible_floors_observation": {"count": 2},
            },
        }
    )

    _assert_not_superseded(slot, "bare numeric provider count")


def test_f3_a_provider_phrase_does_not_supersede():
    slot = _slot(
        {
            "observed": ["the building shows five storeys"],
            "observation_extras": {
                "visible_floors": "the building shows five storeys",
                "visible_floors_observation": {"count": 2},
            },
        }
    )

    _assert_not_superseded(slot, "provider phrase")


def test_f4_a_phrase_in_observed_only_does_not_supersede():
    slot = _slot(
        {
            "observed": ["Two storeys are visible"],
            "observation_extras": {"visible_floors_observation": {"count": 2}},
        }
    )

    _assert_not_superseded(slot, "phrase in observed")


def test_f5_the_ordinary_reading_is_still_published():
    """The fix must not suppress the count — only the false claim about it."""

    observation = _observe(
        {
            "observed": ["Two storeys are visible"],
            "observation_extras": {"visible_floors_observation": {"count": 2}},
        }
    )

    assert observation["visible_floors"]["count"] == 2

    assert observation["visible_floors"]["provenance"]["source"] == "provider_phrase"


# ==========================================================
# G — the four saved facades
# ==========================================================


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_g1_supersession_remains_false_on_every_facade(case):
    slot = _slot(_load(case))

    _assert_not_superseded(slot, "facade " + case)


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_g2_the_primary_floor_count_is_preserved(case):
    observation = _observe(_load(case))

    assert observation["visible_floors"]["count"] == EXPECTED_COUNT[case]

    assert observation["visible_floors"]["count_scope"] == EXPECTED_SCOPE[case]


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_g3_the_lower_trust_observation_count_is_preserved(case):
    slot = _slot(_load(case))

    assert slot["count"] == EXPECTED_OBSERVATION_COUNT[case]


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_g4_the_floor_provenance_is_unchanged(case):
    """Provenance must still say where the reading actually came from."""

    observation = _observe(_load(case))

    saved = _load_saved_observation(case)

    assert (
        observation["visible_floors"]["provenance"]
        == saved["visible_floors"]["provenance"]
    )


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_g5_the_lower_trust_count_scope_is_unchanged(case):
    observation = _observe(_load(case))

    saved = _load_saved_observation(case)

    assert (
        observation["visible_floors_observation"]["count_scope"]
        == saved["visible_floors_observation"]["count_scope"]
    )


def test_g6_facade_c_is_not_upgraded_from_four_to_five():
    """C reported four storeys and stated no total. Nothing may promote it."""

    observation = _observe(_load("C"))

    assert observation["visible_floors"]["count"] is None

    assert observation["visible_floors_observation"]["count"] == 4


# ==========================================================
# H — the lower-trust observation invariants
# ==========================================================


@pytest.mark.parametrize("case", ("A", "B", "C", "D"))
def test_h1_the_observation_tier_invariants_hold(case):
    slot = _slot(_load(case))

    assert slot["trust_tier"] == "PROVIDER_OBSERVATION"

    assert slot["verification"] == "UNVERIFIED"

    assert slot["authoritative"] is False

    assert slot["confidence"] == "LOW"


def test_h2_a_spoofed_payload_cannot_promote_the_observation_tier():
    slot = _slot(_spoof())

    assert slot["trust_tier"] == "PROVIDER_OBSERVATION"

    assert slot["verification"] == "UNVERIFIED"

    assert slot["authoritative"] is False


# ==========================================================
# I — a fabricated dict is not proof of an independent producer
# ==========================================================


def test_i1_a_self_declared_reading_is_not_accepted_by_the_predicate_itself():
    """The previous positive control called the helper with a dict it had
    fabricated and concluded the predicate was sound. It only proved that the
    predicate trusted payload strings. A fabricated dict must now fail."""

    fabricated = {
        "count": 3,
        "verification": "VERIFIED",
        "authoritative": True,
        "provenance": {"source": "local_raster_geometry"},
    }

    assert _floor_reading_is_verified(fabricated) is False


def test_i2_the_helper_and_the_builder_agree():
    """A direct helper call must not be the only evidence: the builder must
    reach the same conclusion on the same fabricated metadata."""

    fabricated = {
        "count": 3,
        "verification": "VERIFIED",
        "authoritative": True,
        "provenance": {"source": "local_raster_geometry"},
    }

    assert _floor_reading_is_verified(fabricated) is False

    _assert_not_superseded(_slot(_spoof()), "builder on the same metadata")


def _emits_verified_floor_reading(path):
    """True when a module really CONSTRUCTS a `verification: "VERIFIED"` value.

    A textual scan is not good enough: the observation module mentions the
    literal in a comment that documents the spoof, and the predicate compares
    against it. Neither is an emission. This looks at the syntax tree instead —
    a dict literal or a subscript assignment whose value is the constant.
    """

    with open(path, encoding="utf-8") as handle:

        tree = ast.parse(handle.read(), filename=path)

    def _is_verified(node):
        return isinstance(node, ast.Constant) and node.value == "VERIFIED"

    def _is_verification_key(node):
        return isinstance(node, ast.Constant) and node.value == "verification"

    for node in ast.walk(tree):

        if isinstance(node, ast.Dict):

            for key, value in zip(node.keys, node.values):

                if _is_verification_key(key) and _is_verified(value):

                    return True

        if isinstance(node, ast.Assign):

            for target in node.targets:

                if (
                    isinstance(target, ast.Subscript)
                    and _is_verification_key(target.slice)
                    and _is_verified(node.value)
                ):

                    return True

    return False


def test_i3_no_vision_module_produces_a_verified_floor_reading():
    """Executable form of the preflight finding: there is NO independent
    floor-verification producer. If one is ever added it must come with an
    authorized integration contract, and this test is where that is declared."""

    vision_dir = os.path.join(ROOT, "core", "vision")

    offenders = []

    for name in sorted(os.listdir(vision_dir)):

        if not name.endswith(".py"):

            continue

        path = os.path.join(vision_dir, name)

        if _emits_verified_floor_reading(path):

            offenders.append(name)

    assert offenders == [], (
        "a vision module now emits a VERIFIED floor reading: " + repr(offenders)
    )


def test_i4_no_producer_is_authorized_to_assert_an_independent_count():
    """The registry is empty by design, not by accident. Filling it is an
    authorized integration decision, not a test-local convenience."""

    assert _FLOOR_INDEPENDENT_PRODUCERS == ()
