# -*- coding: utf-8 -*-
"""R2_FLOOR_QUOTE_INTEGRITY_V1 — focused CPU tests.

The defect: `visible_floors` is not yielded by `iter_claims()`, so the ordinary
per-claim source quarantine never inspected its `evidence_quote`. The normalizer
could therefore emit Markdown-cleaned or spliced quotations that do not occur in
the observer text, and the reading was still accepted.

The correction resolves every accepted quote to ONE contiguous span of the
original text (re-resolving across emphasis markers when needed) and fails
closed otherwise. It never touches the count and never joins fragments.

No Ollama. No GPU. Fixtures are the authentic saved live records.
"""

import copy
import json
import os

import pytest

from core.vision.observation_normalizer_v1 import (
    parse_normalization, normalizer_input, validate_structured,
    resolve_floor_evidence_quote, STRUCTURED_SCHEMA, SCHEMA_VERSION,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.design_constraint_fidelity_v1 import observed_constraints


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURES = {
    "V3": os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json"),
    "ARM_A": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_A_v13.json"),
    "ARM_B": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_B_v13.json"),
    "B01": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_B01_v13.json"),
}


def _record(key):
    with open(FIXTURES[key], encoding="utf-8") as fh:
        return json.load(fh)


def _source(key):
    """The exact text the normalizer was given, as production truncates it."""
    text, _ = normalizer_input(_record(key)["raw_text"], 24000)
    return text


def _model_object(key):
    """The authentic JSON the normalizer model returned, as a dict."""
    return json.loads(_record(key)["normalization"]["raw_text"])


def _replay(key):
    diag = {}
    structured = parse_normalization(
        _record(key)["normalization"]["raw_text"], _source(key), diagnostics=diag)
    return structured, diag


def _parse_object(obj, source_text):
    diag = {}
    structured = parse_normalization(
        json.dumps(obj, ensure_ascii=False), source_text, diagnostics=diag)
    return structured, diag


def _with_floor(key, **floor):
    """The saved model object with its floor slot replaced field by field."""
    obj = _model_object(key)
    slot = dict(obj.get("visible_floors") or {})
    slot.update(floor)
    obj["visible_floors"] = slot
    return obj


# ==========================================================
# A–D  the four saved live fixtures
# ==========================================================

def test_A_v3_exact_quote_is_unchanged():
    structured, diag = _replay("V3")
    floor = structured["visible_floors"]
    assert floor["count"] == 4
    assert floor["evidence_quote"] == "Total storeys visible (including ground floor): 4"
    assert diag["floor_quote"]["status"] == "EXACT"
    assert diag["floor_quote"]["method"] == "exact"
    assert floor["evidence_quote"] in _source("V3")


def test_B_arm_a_quote_is_recovered_as_one_raw_span():
    structured, diag = _replay("ARM_A")
    quote = structured["visible_floors"]["evidence_quote"]
    assert structured["visible_floors"]["count"] == 3
    assert quote == "**3** – ground floor + two upper floors"
    assert quote in _source("ARM_A")
    assert diag["floor_quote"]["status"] == "RECOVERED"
    assert diag["floor_quote"]["method"] == "markdown_span"


def test_C_arm_b_quote_is_not_joined_across_fragments():
    structured, diag = _replay("ARM_B")
    quote = structured["visible_floors"]["evidence_quote"]
    source = _source("ARM_B")
    assert structured["visible_floors"]["count"] == 3
    # The model's own reconstruction joined two spans; the stored quote must be
    # the ORIGINAL contiguous slice, including the awkward marker boundary.
    assert quote == "Total storeys visible:** **3** (one ground floor + two upper floors)"
    assert quote in source
    assert quote != "Total storeys visible: **3** (one ground floor + two upper floors)"
    assert diag["floor_quote"]["status"] == "RECOVERED"


def test_D_b01_quote_is_recovered_as_one_raw_span():
    structured, diag = _replay("B01")
    quote = structured["visible_floors"]["evidence_quote"]
    assert structured["visible_floors"]["count"] == 3
    assert quote == ("**3 storeys** (ground + two upper floors), "
                     "plus a non\u2011storey roof terrace")
    assert quote in _source("B01")
    assert diag["floor_quote"]["status"] == "RECOVERED"


# ==========================================================
# E–H  failure modes
# ==========================================================

def test_E_unrelated_number_cannot_validate_a_floor_quote():
    """A number the text never mentions is not a quotation, whatever the count."""
    source = "The building is three storeys. Street number 42 is on the door."
    obj = _with_floor("V3", count=4, evidence_quote="42 storeys")
    structured, diag = _parse_object(obj, source)
    assert structured["visible_floors"] is None
    assert diag["floor_quote"]["status"] == "REJECTED"
    assert diag["floor_quote"]["reason"] == "no_contiguous_span"
    # the count was not rewritten to obtain a match
    assert diag["floor_quote"]["count"] == 4


def test_E_no_quote_is_never_manufactured_from_the_count():
    obj = _with_floor("V3", count=4, evidence_quote=None)
    structured, diag = _parse_object(obj, _source("V3"))
    assert structured["visible_floors"]["count"] == 4
    assert structured["visible_floors"]["evidence_quote"] is None
    assert diag["floor_quote"]["status"] == "ABSENT"


def test_F_fabricated_quote_is_rejected_and_not_promoted():
    obj = _with_floor("B01", evidence_quote="the building has five storeys")
    structured, diag = _parse_object(obj, _source("B01"))
    assert structured["visible_floors"] is None
    record = diag["floor_quote"]
    assert record["status"] == "REJECTED"
    assert record["promoted"] is False
    assert record["candidate_quote"] == "the building has five storeys"
    assert diag["floor_quote_failures"]


def test_G_contradictory_count_and_quote_fail_closed():
    """A count paired with a quotation the text does not contain is suppressed.

    Semantic count-vs-quote agreement is deliberately NOT parsed here: doing so
    would require a floor-count parser, which this phase forbids. The bridge
    already records numeric contradictions between total and upper floors.
    """
    obj = _with_floor("ARM_B", count=5, evidence_quote="five storeys, ground plus four")
    structured, diag = _parse_object(obj, _source("ARM_B"))
    assert structured["visible_floors"] is None
    assert diag["floor_quote"]["status"] == "REJECTED"


def test_H_duplicate_exact_span_is_ambiguous_and_rejected():
    quote = "Total storeys visible (including ground floor): 4"
    source = quote + "\n" + quote + "\n"
    obj = _with_floor("V3", evidence_quote=quote)
    structured, diag = _parse_object(obj, source)
    assert structured["visible_floors"] is None
    assert diag["floor_quote"]["reason"] == "exact_ambiguous"


def test_H_duplicate_markdown_span_is_ambiguous_and_rejected():
    source = "**3** storeys at the front. Later: **3** storeys at the back."
    obj = _with_floor("ARM_A", count=3, evidence_quote="3 storeys")
    structured, diag = _parse_object(obj, source)
    assert structured["visible_floors"] is None
    assert diag["floor_quote"]["reason"] == "ambiguous_span"


def test_H_resolver_never_picks_between_two_candidate_spans():
    resolved, method = resolve_floor_evidence_quote(
        "3 storeys", "**3** storeys here, and **3** storeys there")
    assert resolved is None
    assert method == "ambiguous_span"


# ==========================================================
# I–L  preservation
# ==========================================================

def test_I_missing_floor_observation_stays_null():
    obj = _model_object("V3")
    obj["visible_floors"] = None
    structured, diag = _parse_object(obj, _source("V3"))
    assert structured["visible_floors"] is None
    assert "floor_quote" not in diag


def test_J_hedged_reading_preserves_uncertainty():
    obj = _with_floor("V3", count=4, uncertainty="apparent; may be 3",
                      evidence_quote="Total storeys visible (including ground floor): 4")
    structured, diag = _parse_object(obj, _source("V3"))
    assert structured["visible_floors"]["count"] == 4
    assert structured["visible_floors"]["uncertainty"] == "apparent; may be 3"
    assert diag["floor_quote"]["status"] == "EXACT"


def test_K_cropped_building_keeps_limited_countability():
    obj = _with_floor("V3", whole_building_visible=False,
                      evidence_quote="Total storeys visible (including ground floor): 4")
    structured, _ = _parse_object(obj, _source("V3"))
    assert structured["visible_floors"]["whole_building_visible"] is False
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": _record("V3")["raw_observer"],
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")
    reading = understanding["observation_extras"]["visible_floors_observation"]
    assert reading["countable"] is False


def test_L_old_records_without_the_field_remain_compatible():
    obj = _model_object("V3")
    obj.pop("visible_floors", None)
    validate_structured(obj)  # optional field, so absence is legal
    structured, diag = _parse_object(obj, _source("V3"))
    assert "visible_floors" not in structured
    assert "floor_quote" not in diag


# ==========================================================
# M–P  end-to-end invariants
# ==========================================================

def test_M_counts_subjects_and_breakdowns_are_unchanged():
    expected = {
        "V3": (4, 3, True, True, "subject"),
        "ARM_A": (3, 2, True, True, "subject"),
        "ARM_B": (3, 2, True, True, "subject"),
        "B01": (3, 2, True, True, "subject"),
    }
    for key, (count, upper, ground, roof_excluded, subject) in expected.items():
        structured, _ = _replay(key)
        floor = structured["visible_floors"]
        assert floor["count"] == count, key
        assert floor["upper_floors"] == upper, key
        assert floor["ground_floor_included"] is ground, key
        assert floor["roof_band_excluded"] is roof_excluded, key
        assert floor["subject"] == subject, key
        assert floor["count_scope"] == "TOTAL", key


def test_M_every_accepted_quote_is_a_contiguous_substring():
    for key in FIXTURES:
        structured, diag = _replay(key)
        quote = structured["visible_floors"]["evidence_quote"]
        source = _source(key)
        assert diag["floor_quote"]["promoted"] is True, key
        assert isinstance(quote, str) and quote, key
        assert quote in source, key
        assert source.count(quote) == 1, key


def test_N_verified_channel_is_untouched():
    for key in FIXTURES:
        structured, _ = _replay(key)
        understanding = build_understanding(
            {"contract": BRIDGE_CONTRACT,
             "raw_observer": _record(key)["raw_observer"],
             "normalization": {"status": "NORMALIZED", "structured": structured}},
            provider="ollama", model="qwen3.8:27b", image_id=key, source_type="other")
        observation = interpret_architectural_vision(understanding)["architectural_observation"]
        assert observation["visible_floors"] is None, key
        reading = observation["visible_floors_observation"]
        assert reading["count"] == structured["visible_floors"]["count"], key
        assert reading["confidence"] == "LOW", key
        assert reading["verification"] == "UNVERIFIED", key
        assert reading["authoritative"] is False, key
        assert reading["trust_tier"] == "PROVIDER_OBSERVATION", key
        assert reading["provider_confidence_reported"] == "HIGH", key
        assert understanding["grounded_provider_evidence"] == [], key
        assert understanding["observed"] == [], key


def test_O_invalid_quote_cannot_reach_render_acceptance():
    obj = _with_floor("ARM_B", evidence_quote="an invented quotation about storeys")
    structured, diag = _parse_object(obj, _source("ARM_B"))
    assert structured["visible_floors"] is None
    assert diag["floor_quote"]["status"] == "REJECTED"

    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": _record("ARM_B")["raw_observer"],
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="ARM_B", source_type="other")
    observation = interpret_architectural_vision(understanding)["architectural_observation"]
    assert observation["visible_floors"] is None
    assert observation["visible_floors_observation"] is None
    verdict = observed_constraints(observation)
    assert verdict["floors"] is None
    assert verdict["available"] is False


def test_O_recovered_quote_also_cannot_reach_render_acceptance():
    """Validating a quote must not make the reading authoritative."""
    structured, diag = _replay("ARM_A")
    assert diag["floor_quote"]["promoted"] is True
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": _record("ARM_A")["raw_observer"],
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="ARM_A", source_type="other")
    observation = interpret_architectural_vision(understanding)["architectural_observation"]
    verdict = observed_constraints(observation)
    assert verdict["floors"] is None
    assert observation["visible_floors"] is None


def test_P_ordinary_claim_verification_does_not_regress():
    structured, diag = _replay("ARM_A")
    # The two markdown-mangled structural claims were rejected before the fix
    # and must still be rejected; the accepted count must be unchanged.
    assert diag["rejected_claim_count"] == 2
    assert diag["accepted_claim_count"] == 33
    reasons = {f["reason"] for f in diag["source_resolution_failures"]}
    assert reasons == {"no_match"}


def test_P_normalizer_still_validates_the_whole_schema():
    structured, _ = _replay("V3")
    validate_structured(structured)
    assert SCHEMA_VERSION == "structured-visual-observation-v1.3"
    assert "visible_floors" in STRUCTURED_SCHEMA["properties"]


def test_schema_still_accepts_null_floor_slot():
    obj = _model_object("V3")
    obj["visible_floors"] = None
    validate_structured(obj)


def test_resolver_rejects_non_text_and_empty_quotes():
    assert resolve_floor_evidence_quote(None, "3 storeys")[0] is None
    assert resolve_floor_evidence_quote("", "3 storeys")[1] == "quote_empty"
    assert resolve_floor_evidence_quote("**", "3 storeys")[1] == "quote_markers_only"
