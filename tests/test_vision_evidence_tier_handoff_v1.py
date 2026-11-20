# -*- coding: utf-8 -*-
"""ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 — focused CPU tests (A-N).

WHAT THESE TEST
===============
That an observer's explicitly stated storey reading SURVIVES the
Normalizer -> Understanding Bridge -> ArchitecturalObservation path, while
remaining a separate, lower-trust OBSERVATION that no existing consumer can
mistake for a verified fact.

WHAT THEY DO NOT TEST
=====================
Nothing here calls Ollama, ComfyUI or the normalizer model. Every
``structured["visible_floors"]`` object below is a TEST FIXTURE hand-built
from a VERBATIM quote taken from the saved live records
(``runs/architectural_eye_live_floor_v1/eye_*.json``). It is NOT a live
normalizer result and must never be read as one.

The ground-truth counts live in the acceptance report, not here, and are never
injected into runtime input.
"""

import json
import os

import pytest

from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import (
    CATEGORIES,
    STRUCTURED_SCHEMA,
    validate_structured,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


# ----------------------------------------------------------------------
# TEST FIXTURE BUILDERS
# ----------------------------------------------------------------------

def _structured(floors):
    """A normalization `structured` object. TEST FIXTURE, not a live result."""

    payload = {
        "drawing_type": None,
        "openings": {"doors": [], "windows": [], "other_openings": []},
    }
    for category in CATEGORIES:
        payload[category] = []
    payload["visible_floors"] = floors
    return payload


def _bridge(floors, raw_text="(test fixture observer text)"):
    return {
        "contract": BRIDGE_CONTRACT,
        "raw_observer": {"raw_text": raw_text,
                         "generation_status": "COMPLETE"},
        "normalization": {"status": "NORMALIZED", "structured": _structured(floors)},
    }


def _run(floors, raw_text="(test fixture observer text)"):
    understanding = build_understanding(
        _bridge(floors, raw_text), provider="ollama", model="qwen3.8:27b",
        image_id="fixture", source_type="other",
    )
    interpretation = interpret_architectural_vision(understanding)
    return understanding, interpretation, interpretation["architectural_observation"]


def _floors(**overrides):
    base = {
        "count": None, "count_scope": None, "ground_floor_included": None,
        "upper_floors": None, "whole_building_visible": None,
        "roof_band_excluded": None, "uncertainty": None, "evidence_quote": None,
        "subject": None, "provider_confidence": None,
    }
    base.update(overrides)
    return base


# ======================================================================
# A - D  the four real acceptance cases, verbatim quotes from the records
# ======================================================================

class TestRealAcceptanceCases:

    def test_A_v3_four_storeys_ground_plus_three_upper(self):
        """Quote: eye_V3.json — 'Total storeys visible (including ground floor): 4'."""
        _, _, obs = _run(_floors(
            count=4, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=3, whole_building_visible=True, roof_band_excluded=True,
            evidence_quote="Total storeys visible (including ground floor): 4",
            subject="subject", provider_confidence="HIGH",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] == 4
        assert reading["upper_floors"] == 3
        assert reading["ground_floor_included"] is True
        assert reading["roof_band_excluded"] is True
        assert reading["countable"] is True

    def test_B_arm_a_three_storeys_subject_visible_neighbours_cropped(self):
        """Quote: eye_ARM_A.json — '3 – ground floor + two upper floors'."""
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, whole_building_visible=True, roof_band_excluded=True,
            evidence_quote="Total storeys visible (central building): 3 – ground floor + two upper floors",
            subject="subject", provider_confidence="HIGH",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] == 3
        assert reading["upper_floors"] == 2
        # The observer said the SUBJECT is complete; neighbours are cropped.
        # That is a subject-scoped visibility claim, and it is preserved.
        assert reading["whole_building_visible"] is True

    def test_C_arm_b_three_storeys_parapet_excluded(self):
        """Quote: eye_ARM_B.json — '3 (one ground floor + two upper floors)'."""
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, whole_building_visible=True, roof_band_excluded=True,
            evidence_quote="Total storeys visible: 3 (one ground floor + two upper floors)",
            subject="subject", provider_confidence="HIGH",
        ))
        assert obs["visible_floors_observation"]["count"] == 3
        assert obs["visible_floors_observation"]["roof_band_excluded"] is True

    def test_D_b01_three_storeys_roof_terrace_not_counted(self):
        """Quote: eye_B01.json — '3 storeys (ground + two upper floors), plus a non-storey roof terrace'."""
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, whole_building_visible=True, roof_band_excluded=True,
            evidence_quote="3 storeys (ground + two upper floors), plus a non-storey roof terrace",
            subject="subject", provider_confidence="HIGH",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] == 3, "a roof terrace must not add a storey"
        assert reading["roof_band_excluded"] is True


# ======================================================================
# E - I  absence, hedging, contradiction, cropping, upper-only
# ======================================================================

class TestEdgeCases:

    def test_E_no_count_yields_no_observation(self):
        _, _, obs = _run(None)
        assert obs["visible_floors_observation"] is None

    def test_E_all_null_object_yields_no_observation(self):
        _, _, obs = _run(_floors())
        assert obs["visible_floors_observation"] is None

    def test_F_hedged_count_keeps_uncertainty_and_is_low_confidence(self):
        _, _, obs = _run(_floors(
            count=4, count_scope="TOTAL", uncertainty="apparent; may be 3",
            evidence_quote="four apparent storeys", subject="subject",
            provider_confidence="MEDIUM",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] == 4
        assert reading["uncertainty"] == "apparent; may be 3"
        assert reading["confidence"] == "LOW"
        assert reading["provider_confidence_reported"] == "MEDIUM"

    def test_G_contradictory_total_and_upper_floors_is_not_resolved(self):
        _, _, obs = _run(_floors(
            count=5, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, evidence_quote="five storeys, two upper floors",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] is None, "a contradiction must not be silently resolved"
        assert reading["contradiction"]["kind"] == "total_disagrees_with_upper_floors"

    def test_G_contradictory_total_without_ground(self):
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=False,
            evidence_quote="three storeys, ground not counted",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] is None
        assert reading["contradiction"]["kind"] == "total_without_ground_floor"

    def test_H_cropped_image_is_not_countable(self):
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", whole_building_visible=False,
            evidence_quote="three storeys visible, building is cropped",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["whole_building_visible"] is False
        assert reading["countable"] is False

    def test_I_upper_only_is_not_a_total(self):
        _, _, obs = _run(_floors(
            count=2, count_scope="UPPER_ONLY", ground_floor_included=False,
            upper_floors=2, evidence_quote="two upper floors are visible",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] == 2
        assert reading["count_is_total"] is False
        assert reading["ground_floor_included"] is False


# ======================================================================
# J - K  wrong attribution
# ======================================================================

class TestAttribution:

    def test_J_street_number_never_becomes_a_floor_count(self):
        """The accepted adjacency rule still rejects an address number."""
        from core.vision.architectural_observation_v1 import detect_visible_floors
        assert detect_visible_floors(
            ["the building at 42 Oak Street has 3 storeys"])["count"] == 3
        assert detect_visible_floors(["project 7, a five storey block"])["count"] == 5

    def test_K_other_building_count_is_not_attributed_to_subject(self):
        _, _, obs = _run(_floors(
            count=6, count_scope="TOTAL", upper_floors=5,
            evidence_quote="the background building is six storeys",
            subject="other",
        ))
        reading = obs["visible_floors_observation"]
        assert reading["count"] is None, "another building's count must not become the subject's"
        assert reading["attributed_to"] == "other"
        assert reading["evidence_quote"] == "the background building is six storeys"


# ======================================================================
# L - N  tier separation and consumer safety
# ======================================================================

class TestTierSeparation:

    def test_L_the_primary_tier_wins_without_claiming_verification(self):
        """The PRIMARY reading wins; the observation's 9 never leaks into it.

        VISION_FLOOR_SUPERSESSION_TRUTH_V1 — this test previously asserted
        `superseded_by_verified is True` and called the primary reading
        "verified evidence". It is not: `visible_floors` here is derived by
        `detect_visible_floors()` from the PROVIDER's own phrase, with
        `provenance.source == "provider_phrase"` and no verification record.
        The tier-separation claim (9 must not become the primary count) is
        unchanged and still asserted; only the false supersession claim is
        corrected. Node ID renamed accordingly:
        `test_L_verified_evidence_takes_precedence` -> this.
        """

        raw = {
            "image_type": "architectural_render_or_photo",
            "observed": ["ground floor plus two upper floors are visible"],
            "inferred": [], "unresolved": [], "architectural_elements": [],
            "text_labels_if_visible": [], "visible_floors": "two upper floors",
            "visible_floors_observation": {
                "trust_tier": "PROVIDER_OBSERVATION", "verification": "UNVERIFIED",
                "count": 9, "confidence": "LOW",
            },
        }
        obs = build_understanding(raw)["observation_extras"]
        assert "visible_floors_observation" in obs

        from core.vision.architectural_observation_v1 import (
            build_architectural_observation,
        )
        contract = build_architectural_observation(raw)
        # The primary reading wins and is untouched by the observation's 9.
        assert contract["visible_floors"]["count"] != 9
        assert contract["visible_floors"]["provenance"]["source"] == "provider_phrase"
        # ... but a provider-derived reading is NOT a verified replacement.
        assert contract["visible_floors_observation"]["superseded_by_verified"] is False

    def test_M_older_records_without_the_field_are_compatible(self):
        legacy_structured = {
            "drawing_type": None,
            "openings": {"doors": [], "windows": [], "other_openings": []},
            **{category: [] for category in CATEGORIES},
        }
        assert "visible_floors" not in legacy_structured
        bridge = {
            "contract": BRIDGE_CONTRACT,
            "raw_observer": {"raw_text": "legacy record", "generation_status": "COMPLETE"},
            "normalization": {"status": "NORMALIZED", "structured": legacy_structured},
        }
        understanding = build_understanding(bridge, provider="ollama",
                                            model="qwen3.8:27b", image_id="legacy")
        obs = interpret_architectural_vision(understanding)["architectural_observation"]
        assert obs["visible_floors"] is None
        assert obs["visible_floors_observation"] is None

    def test_N_unverified_count_cannot_produce_a_render_verdict(self):
        """The render-fidelity consumer must see nothing it can verify."""
        from core.vision.design_constraint_fidelity_v1 import observed_constraints

        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, whole_building_visible=True,
            evidence_quote="3 storeys", subject="subject",
        ))
        assert obs["visible_floors_observation"]["count"] == 3
        verdict = observed_constraints(obs)
        assert verdict["floors"] is None, (
            "an UNVERIFIED observation must never satisfy a floor requirement"
        )

    def test_N_observation_never_becomes_verified_evidence(self):
        understanding, _, _ = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, evidence_quote="3 storeys", subject="subject",
        ))
        assert understanding["observed"] == []
        assert (understanding.get("grounded_provider_evidence") or []) == []

    def test_N_honest_floor_unknown_is_not_deleted(self):
        """A visible_floors_observation must not suppress a genuine unknown.

        The interpreter deletes floor unknowns only when `visible_floors` is
        truthy. A facade reading is used here because that is the branch that
        actually emits "exact floor count is not determinable" — the same
        unknown the live V3 run produced.
        """
        from core.vision.architectural_observation_v1 import (
            build_architectural_observation,
        )
        raw = {
            "image_type": "architectural_render_or_photo",
            "observed": ["brick facade", "large windows", "flat roof"],
            "inferred": [], "unresolved": [], "architectural_elements": [],
            "text_labels_if_visible": [],
            "visible_floors_observation": {
                "trust_tier": "PROVIDER_OBSERVATION", "verification": "UNVERIFIED",
                "count": 3, "confidence": "LOW",
            },
        }
        contract = build_architectural_observation(raw)
        assert contract["visible_floors"] is None

        interpretation = interpret_architectural_vision(build_understanding(raw))
        floor_unknowns = [u for u in (interpretation.get("unknowns") or [])
                          if "floor" in json.dumps(u).lower()]
        assert floor_unknowns, "an honest floor uncertainty must survive"
        assert any("not determinable" in json.dumps(u).lower()
                   for u in floor_unknowns)


# ======================================================================
# RED — prove the handoff is load-bearing
# ======================================================================

class TestRedWithoutTheHandoff:

    def test_red_removing_the_builder_loses_the_reading(self, monkeypatch):
        """With the new bridge step removed, the count disappears again.

        This is the RED state the live acceptance measured: model 4/4,
        contract 0/4. It proves the assertions above are not vacuous.
        """
        import core.vision.image_understanding_v1 as module

        monkeypatch.setattr(module, "_floor_observation_from_structured",
                            lambda raw, **kwargs: None)
        _, _, obs = _run(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, evidence_quote="3 storeys", subject="subject",
        ))
        assert obs["visible_floors"] is None
        assert obs["visible_floors_observation"] is None, "RED: reading lost again"


# ======================================================================
# Schema contract
# ======================================================================

class TestNormalizerSchema:

    def test_schema_has_the_floor_slot(self):
        assert "visible_floors" in STRUCTURED_SCHEMA["properties"]
        field = STRUCTURED_SCHEMA["properties"]["visible_floors"]
        assert "object" in field["type"] and "null" in field["type"]

    def test_schema_accepts_null_floor_slot(self):
        payload = _structured(None)
        validate_structured(payload)  # must not raise

    def test_schema_accepts_a_complete_floor_slot(self):
        validate_structured(_structured(_floors(
            count=3, count_scope="TOTAL", ground_floor_included=True,
            upper_floors=2, whole_building_visible=True, roof_band_excluded=True,
            uncertainty=None, evidence_quote="3 storeys", subject="subject",
            provider_confidence="HIGH",
        )))

    def test_schema_rejects_a_partial_floor_slot(self):
        with pytest.raises(ValueError):
            validate_structured(_structured({"count": 3}))

    def test_schema_rejects_an_invented_scope(self):
        with pytest.raises(ValueError):
            validate_structured(_structured(_floors(count=3, count_scope="GUESS")))

    def test_schema_version_bumped(self):
        from core.vision.observation_normalizer_v1 import SCHEMA_VERSION
        assert SCHEMA_VERSION == "structured-visual-observation-v1.3"


# ======================================================================
# Other observations keep their routing
# ======================================================================

class TestOtherObservationsUnchanged:

    def test_materials_and_elements_still_route(self):
        raw = {
            "image_type": "architectural_render_or_photo",
            "observed": ["brick facade", "large windows"],
            "inferred": [], "unresolved": [], "architectural_elements": ["brick facade"],
            "text_labels_if_visible": [],
            "material_observations": ["brick facade"],
        }
        contract = build_understanding(raw)
        extras = contract["observation_extras"]
        assert extras["material_observations"] == ["brick facade"]

    def test_observation_does_not_promote_other_rejected_claims(self):
        understanding, _, _ = _run(_floors(
            count=3, count_scope="TOTAL", evidence_quote="3 storeys",
            subject="subject",
        ))
        assert understanding["observed"] == []
