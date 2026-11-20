# ==========================================================
# ArchitectOS — VISION_EVIDENCE_PROVENANCE_V1
#
# Regression tests for the measured defect (V4.1 §3):
#
#   The bridge adapter reported `observed: []`,
#   `observed_attributed: []`, `architectural_elements: []` and
#   `confidence: "LOW"` for EVERY image, and then FORCED
#   `analysis_status = ANALYZED_WITH_UNCERTAINTY`.
#
#   Measured consequence: an image whose observer asserted
#   "curved concrete balcony slab" was indistinguishable from an
#   image where the model saw nothing, and from a normalizer
#   failure. The interpreter answered `space_type: unknown`.
#
# Every case below drives the REAL adapter and the REAL consumers.
# No provider call, no network, no GPU.
# ==========================================================

import pytest

from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_observation_mode_v1 import build_observation


RAW_TEXT = (
    "A curved concrete balcony slab projects from the second floor. "
    "Tall arched windows are visible. Scaffolding covers the left wing."
)


def _claim(text, kind, certainty="ASSERTED"):
    return {
        "text": text,
        "source_quote": text,
        "kind": kind,
        "certainty": certainty,
        "count": None,
    }


def _structured(observed=(), structural=(), interpretations=(), unknowns=(), ambiguous=()):
    return {
        "drawing_type": None,
        "observed_elements": list(observed) + list(ambiguous),
        "enclosed_spaces": [],
        "walls": [],
        "vertical_circulation": [],
        "furniture": [],
        "fixtures": [],
        "structural_elements": list(structural),
        "axes": [],
        "orientation": [],
        "provider_ocr_candidate": [],
        "ocr_exact": [],
        "ocr_partial": [],
        "ocr_unreadable": [],
        "scale": [],
        "dimensions": [],
        "level_codes": [],
        "spatial_relationships": [],
        "interpretations": list(interpretations),
        "unknowns": list(unknowns),
        "openings": {"doors": [], "windows": [], "other_openings": []},
    }


def _bridge(structured, *, observer_status="COMPLETE", raw_text=RAW_TEXT,
            normalization_status="NORMALIZED", normalization_error=None):
    normalization = {"status": normalization_status, "structured": structured}

    if normalization_error:
        normalization["error"] = normalization_error

    return {
        "contract": BRIDGE_CONTRACT,
        "raw_observer": {
            "raw_text": raw_text,
            "generation_status": observer_status,
            "provider": "ollama",
            "model": "qwen3.8:27b",
        },
        "normalization": normalization,
    }


def _understand(bridge):
    return build_understanding(
        bridge,
        provider="ollama",
        model="qwen3.8:27b",
        image_id="test_image",
        source_type="reference_image",
    )


# ==========================================================
# 1 — THE BANDS ARE DERIVED, NOT HARDCODED
# ==========================================================

def test_asserted_claim_reaches_the_attributed_band():
    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    assert result["observed"] == []
    assert "curved concrete balcony slab" in result["observed_attributed"]
    assert "curved concrete balcony slab" in result["architectural_elements"]
    assert result["evidence_state"] == "INFERRED"


def test_scaffolding_is_attributed_as_a_structural_element():
    result = _understand(_bridge(_structured(
        structural=[_claim("Scaffolding", "scaffolding")],
    )))

    assert "Scaffolding" in result["observed_attributed"]
    assert "Scaffolding" in result["architectural_elements"]


def test_the_state_distinguishes_empty_from_unconfirmed():
    empty = _understand(_bridge(_structured()))
    unconfirmed = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    assert empty["evidence_state"] == "UNKNOWN"
    assert unconfirmed["evidence_state"] == "INFERRED"
    assert empty["analysis_status"] == "PARTIAL"
    assert unconfirmed["analysis_status"] == "ANALYZED_WITH_UNCERTAINTY"


def test_normalization_failure_is_its_own_state():
    result = _understand(_bridge(
        {},
        normalization_status="FAILED",
        normalization_error="ValueError:normalizer_generation_incomplete",
    ))

    assert result["evidence_state"] == "NORMALIZATION_FAILED"
    assert result["analysis_status"] == "PARTIAL"
    assert result["observed_attributed"] == []
    assert "normalizer_generation_incomplete" in result["diagnostics"]["normalization_error"]


def test_provider_failure_is_its_own_state():
    result = _understand(_bridge(
        {},
        observer_status="FAILED",
        raw_text="",
    ))

    assert result["evidence_state"] == "PROVIDER_FAILED"
    assert result["analysis_status"] == "PROVIDER_UNAVAILABLE"


def test_the_three_failures_are_now_distinguishable():
    states = {
        _understand(_bridge({}, normalization_status="FAILED"))["evidence_state"],
        _understand(_bridge({}, observer_status="FAILED", raw_text=""))["evidence_state"],
        _understand(_bridge(_structured()))["evidence_state"],
    }

    assert states == {"NORMALIZATION_FAILED", "PROVIDER_FAILED", "UNKNOWN"}


# ==========================================================
# 2 — NOTHING IS PROMOTED THAT SHOULD STAY UNCERTAIN
# ==========================================================

def test_ambiguous_claim_is_never_promoted():
    result = _understand(_bridge(_structured(
        ambiguous=[_claim("Scaffolding", "scaffolding", certainty="AMBIGUOUS")],
    )))

    assert "Scaffolding" not in result["observed_attributed"]
    assert "Scaffolding" not in result["architectural_elements"]
    assert result["diagnostics"]["ambiguous_count"] == 1


def test_interpretation_is_never_promoted_as_observation():
    result = _understand(_bridge(_structured(
        interpretations=[_claim("this is a luxury villa", "villa")],
    )))

    assert result["observed_attributed"] == []
    assert result["architectural_elements"] == []


def test_unknown_claim_is_never_promoted():
    result = _understand(_bridge(_structured(
        unknowns=[_claim("floor count cannot be determined", "floor")],
    )))

    assert result["observed_attributed"] == []
    assert result["evidence_state"] == "UNKNOWN"


def test_a_non_verbatim_claim_is_dropped_before_the_bands():
    """The normalizer may not invent text the observer never wrote."""

    result = _understand(_bridge(_structured(
        observed=[_claim("golden marble columns", "column")],
    )))

    assert "golden marble columns" not in result["observed_attributed"]


def test_a_dimensional_claim_is_rejected_not_attributed():
    text = "the facade is 12.5 m wide"
    bridge = _bridge(
        _structured(observed=[_claim(text, "facade")]),
        raw_text=text,
    )

    result = _understand(bridge)

    assert text not in result["observed_attributed"]
    assert any(
        entry.get("field") == "observed_attributed"
        for entry in result["safety"]["rejected_claims"]
    )


# ==========================================================
# 3 — CONFIDENCE IS A CLASSIFICATION, NOT AN INVENTION
# ==========================================================

def test_confidence_carries_an_explicit_basis():
    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert "confirmed=" in result["confidence_basis"]
    assert "attributed=" in result["confidence_basis"]
    assert "local_corroboration=" in result["confidence_basis"]


def test_confidence_basis_matches_the_counts():
    result = _understand(_bridge(_structured(
        observed=[
            _claim("curved concrete balcony slab", "balcony"),
            _claim("Tall arched windows", "window"),
        ],
    )))

    assert result["confidence_basis"].startswith(
        "confirmed=%d attributed=%d" % (
            len(result["observed"]), len(result["observed_attributed"]),
        )
    )


# ==========================================================
# 4 — DIAGNOSTICS ARE CARRIED
# ==========================================================

def test_diagnostics_record_the_whole_pipeline():
    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    diagnostics = result["diagnostics"]

    assert diagnostics["observer_generation_status"] == "COMPLETE"
    assert diagnostics["normalization_status"] == "NORMALIZED"
    assert diagnostics["candidate_count"] >= 1
    assert diagnostics["local_corroboration_available"] is False
    assert diagnostics["raw_observer_retained"] is True


def test_incomplete_observer_generation_is_reported():
    result = _understand(_bridge(
        _structured(observed=[_claim("curved concrete balcony slab", "balcony")]),
        observer_status="PARTIAL",
    ))

    assert result["analysis_status"] == "PARTIAL"
    assert any("generation incomplete" in entry for entry in result["unresolved"])


# ==========================================================
# 5 — THE CONSUMERS SEE IT
# ==========================================================

def test_interpreter_no_longer_answers_unknown_space_type():
    from core.vision.architectural_vision_interpreter_v1 import (
        interpret_architectural_vision,
    )

    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    interpretation = interpret_architectural_vision(
        result, user_text="Describe this building."
    )

    assert interpretation["space_type"] == "balcony"


def test_observation_contract_publishes_the_attributed_band():
    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    observation = build_observation(result, language="en")

    assert observation["elements"] == []
    assert observation["counts"]["attributed"] >= 1
    assert any(
        entry["name"] == "curved concrete balcony slab"
        and entry["evidence_class"] == "provider observation (unconfirmed)"
        for entry in observation["attributed_elements"]
    )


def test_observation_never_claims_nothing_was_reported_when_claims_exist():
    result = _understand(_bridge(_structured(
        observed=[_claim("curved concrete balcony slab", "balcony")],
    )))

    observation = build_observation(result, language="en")

    assert not any(
        "no visible element" in str(entry.get("label") or "").lower()
        for entry in observation["unknowns"]
    )
