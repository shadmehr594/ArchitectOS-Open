"""VISION RETENTION FIX V2 — generic regression tests.

Covers the three fixes:
  A. an evidence-gated canonical image type (positive LOCAL plan structure,
     corroborated — never defined — by the model's drawing type);
  B. a trust-gated conflict path (low-trust OCR cannot create presence);
  C. OCR trust tiers (multi-pass agreement is STABILITY, not independence).

Every fixture is SYNTHETIC: no acceptance image, filename, hash or
case-specific rule.
"""
import pytest

from core.vision.general_visual_observer_v1 import CONTRACT, raw_observation
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import CATEGORIES
from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_grounding_v1 import (
    ground_vision_evidence, _local_present_kinds,
)
from core.vision.architectural_vision_interpreter_v1 import build_plan_reading
from core.vision.local_evidence_trust_v1 import (
    INDEPENDENTLY_VERIFIED_OCR, LOW_TRUST_OCR, STABLE_LOCAL_OCR,
    independently_verified_ocr_texts, local_plan_structure_evidence,
    ocr_trust_state,
)


# ----------------------------------------------------------------- fixtures

def structured():
    return {"drawing_type": None, **{k: [] for k in CATEGORIES},
            "openings": {"doors": [], "windows": [], "other_openings": []}}


def claim(text, *, kind="text", quote=None, certainty="ASSERTED", count=None):
    return {"text": text, "source_quote": quote or text, "kind": kind,
            "certainty": certainty, "count": count}


def bridge(data, text="observation"):
    return {"contract": CONTRACT,
            "raw_observer": raw_observation(provider="test", model="model", backend="test",
                                            thinking_mode="low",
                                            body={"response": text, "done": True}),
            "normalization": {"status": "NORMALIZED", "structured": data}}


def local_reading(*, labels=None, elements=None, furniture=None, sheet_type="single_plan"):
    reading = {
        "contract": "LocalPlanReadingV1", "version": "1.3", "status": "grounded",
        "source": "local_offline_raster", "provider_independent": True,
        "image_size": {"width": 400, "height": 400}, "ocr_status": "analyzed",
        "symbol_analysis_status": "analyzed", "element_analysis_status": "analyzed",
        "labels": labels or [], "openings": [], "element_evidence": elements or [],
        "furniture_evidence": furniture or [],
        "enclosure_geometry": {"count": None, "count_status": "uncertain", "regions": []},
        "sheet_structure": {"sheet_type": sheet_type},
    }
    return reading


def window_element():
    return {"type": "window", "bbox_pixels": [10, 10, 60, 20],
            "source": "local_raster_geometry", "provider_independent": True,
            "status": "visible", "confidence": "MEDIUM",
            "corroboration": ["paired_parallel_lines", "perimeter_wall_context",
                              "glazing_gap"],
            "raster_patch_sha256": "a" * 64,
            "geometry": {"orientation": "horizontal"}, "attributes": {},
            "evidence": "window symbol", "element_id": "synthetic_window"}


def unmet_level_element():
    return {"type": "level", "bbox_pixels": [10, 10, 40, 40],
            "source": "local_raster_geometry", "provider_independent": True,
            "status": "visible", "confidence": "MEDIUM",
            "corroboration": ["quartered_elevation_marker", "orthogonal_cross_hairs",
                              "localized_numeric_annotation_required"],
            "raster_patch_sha256": "b" * 64,
            "geometry": {}, "attributes": {}, "evidence": "level marker",
            "element_id": "synthetic_level"}


def grounded_bed():
    return {"class": "bed", "bbox_pixels": [1, 1, 9, 9], "name": "bed",
            "corroboration": ["frame", "pillow", "blanket"], "status": "visible",
            "confidence": "MEDIUM", "evidence_type": "fixture",
            "source": "local_raster_symbol_topology",
            "provider_independent": True, "item_id": "synthetic",
            "raster_patch_sha256": "a" * 64}


def label(text, *, raw=None, correction=None, passes=2, semantic_function="bathroom"):
    return {"text": text, "raw_ocr": text if raw is None else raw,
            "bbox_pixels": [5, 5, 60, 18], "status": "grounded_ocr",
            "evidence_type": "local_ocr", "confidence": "MEDIUM",
            "correction": correction, "independent_passes": passes,
            "ocr_confidence": 70, "semantic_function": semantic_function}


def understanding(*, local, claims=(), text="observation"):
    data = structured()
    for category, item in claims:
        if category == "drawing_type":
            data[category] = item
        else:
            data[category].append(item)
    return build_understanding(bridge(data, text), provider="test", model="model",
                               image_id="synthetic", source_type="uploaded",
                               local_plan_reading=local)


def drawing_type_claim(value):
    return ("drawing_type", claim(value, kind="map"))


def plan_reading_from(u):
    return build_plan_reading(build_architectural_observation(u))


# --------------------------------------------------- A. canonical image type

def test_1_single_plan_alone_is_not_enough_for_floor_plan():
    u = understanding(local=local_reading(sheet_type="single_plan"))
    assert u["image_type"] != "floor_plan_or_sketch"
    assert u["image_type_evidence"]["basis"] == "UNKNOWN"


def test_2_provider_floor_plan_observation_alone_is_not_enough():
    text = "floor plan"
    u = understanding(local=local_reading(sheet_type="single_plan"),
                      claims=[drawing_type_claim(text)], text=text)
    assert u["provider_drawing_type"]["canonical"] == "floor_plan_or_sketch"
    assert u["image_type"] == "unknown"
    assert u["image_type_evidence"]["basis"] == "PROVIDER_OBSERVED"
    assert u["image_type_evidence"]["provider_is_authoritative"] is False


def test_3_positive_local_plan_structure_activates_the_single_plan_path():
    u = understanding(local=local_reading(elements=[window_element()]))
    assert u["image_type"] == "floor_plan_or_sketch"
    assert u["image_type_evidence"]["basis"] == "LOCAL_STRUCTURAL"
    assert "PLAN_ELEMENT_TOPOLOGY" in u["image_type_evidence"]["local_families"]
    assert isinstance(plan_reading_from(u), dict)


def test_4_local_structure_plus_matching_provider_is_corroborated():
    text = "floor plan"
    u = understanding(local=local_reading(elements=[window_element()]),
                      claims=[drawing_type_claim(text)], text=text)
    assert u["image_type"] == "floor_plan_or_sketch"
    assert u["image_type_evidence"]["basis"] == "CORROBORATED"
    assert u["image_type_evidence"]["provider_agrees"] is True


def test_5_weak_local_plus_provider_facade_is_not_floor_plan():
    text = "classical facade elevation"
    u = understanding(local=local_reading(sheet_type="single_plan"),
                      claims=[drawing_type_claim(text)], text=text)
    assert u["image_type"] == "unknown"
    assert u["image_type_evidence"]["provider_canonical"] == "facade_or_elevation"


def test_6_weak_local_plus_provider_site_diagram_is_not_floor_plan():
    text = "cadastral / land-survey sketch"
    u = understanding(local=local_reading(sheet_type="single_plan"),
                      claims=[drawing_type_claim(text)], text=text)
    assert u["image_type"] == "unknown"
    assert u["image_type_evidence"]["provider_canonical"] == "site_diagram"


def test_7_multi_plan_structure_is_preserved():
    u = understanding(local=local_reading(sheet_type="multi_plan"))
    assert u["image_type"] == "floor_plan_or_sketch"
    assert "MULTI_PANEL_STRUCTURE" in u["image_type_evidence"]["local_families"]


def test_8a_furniture_symbol_topology_is_positive_plan_structure():
    evidence = local_plan_structure_evidence(local_reading(furniture=[grounded_bed()]))
    assert evidence["positive"] is True
    assert "PLAN_FURNITURE_SYMBOL_TOPOLOGY" in evidence["families"]


def test_8b_enclosure_regions_alone_are_not_plan_structure():
    # a facade render produced nine enclosure regions, so regions are not a
    # positive plan signal
    local = local_reading()
    local["enclosure_geometry"] = {
        "count": None, "count_status": "uncertain", "stable_region_count": 3,
        "multiple_spaces": True,
        "regions": [{"region_id": "r%d" % i} for i in range(9)],
    }
    assert local_plan_structure_evidence(local)["positive"] is False


# ------------------------------------------------ B. trust-gated conflicts

def test_8_low_trust_ocr_cannot_create_a_local_present_kind():
    low = label("حمام", raw="ما", correction="architectural_lexicon_match", passes=1)
    local = local_reading(labels=[low])
    assert ocr_trust_state(low, ()) == LOW_TRUST_OCR
    assert _local_present_kinds(local, ()) == set()


def test_9_low_trust_ocr_cannot_create_a_scope_conflict():
    text = "it is a land plan, not an architectural interior"
    local = local_reading(labels=[label("حمام", raw="ما",
                                        correction="architectural_lexicon_match",
                                        passes=1)])
    u = understanding(local=local, claims=[("interpretations", claim(text,
                                                                    kind="classification"))],
                      text=text)
    assert ground_vision_evidence(u)["conflicts"] == []


def test_10_independently_corroborated_ocr_creates_a_local_present_kind():
    scope = "it is a land plan, not an architectural interior"
    ocr = "حمام"
    local = local_reading(labels=[label(ocr, raw=ocr, correction=None, passes=3)])
    u = understanding(local=local,
                      claims=[("interpretations", claim(scope, kind="classification")),
                              ("ocr_exact", claim(ocr, kind="text"))],
                      text=scope + "\n" + ocr)
    texts = independently_verified_ocr_texts(u)
    assert texts == {ocr}
    assert _local_present_kinds(local, texts) == {"bathroom"}
    assert ground_vision_evidence(u)["conflicts"], "trusted presence must conflict"


# ------------------------------------------------------- C. OCR trust tiers

def test_11_same_engine_multi_pass_is_stability_not_independence():
    stable = label("آشپزخانه", raw="آشپزخانه", correction=None, passes=9)
    assert ocr_trust_state(stable, ()) == STABLE_LOCAL_OCR
    assert ocr_trust_state(stable, ()) != INDEPENDENTLY_VERIFIED_OCR


def test_12_lexicon_substitution_with_many_passes_is_still_low_trust():
    guess = label("تراس", raw="زارتم", correction="architectural_lexicon_match",
                  passes=13)
    assert ocr_trust_state(guess, ()) == LOW_TRUST_OCR
    assert ocr_trust_state(guess, {"تراس"}) == LOW_TRUST_OCR


def test_13_stable_exact_ocr_without_corroboration_is_not_a_named_space():
    stable = label("آشپزخانه", raw="آشپزخانه", correction=None, passes=4,
                   semantic_function="kitchen")
    plan = plan_reading_from(understanding(local=local_reading(labels=[stable])))
    assert plan["named_spaces"] == []
    assert plan["read_labels"][0]["status"] == "stable_local_ocr"


def test_14_independently_corroborated_exact_ocr_may_promote():
    scope = "note"
    ocr = "آشپزخانه"
    local = local_reading(labels=[label(ocr, raw=ocr, correction=None, passes=3,
                                        semantic_function="kitchen")])
    u = understanding(local=local, claims=[("ocr_exact", claim(ocr, kind="text"))],
                      text=scope + "\n" + ocr)
    plan = plan_reading_from(u)
    assert plan["read_labels"][0]["status"] == "grounded_ocr"
    assert any(entry["space"] == "kitchen" for entry in plan["named_spaces"])


def test_15_unsatisfied_local_element_requirement_cannot_create_presence():
    local = local_reading(elements=[unmet_level_element()])
    assert _local_present_kinds(local, ()) == set()
    text = "no level code"
    u = understanding(local=local,
                      claims=[("structural_elements",
                               claim(text, kind="level", count=0))],
                      text=text)
    assert ground_vision_evidence(u)["conflicts"] == []


def test_15b_satisfied_requirement_is_not_treated_as_unmet():
    element = window_element()
    local = local_reading(elements=[element])
    assert _local_present_kinds(local, ()) == {"window"}


# --------------------------------------- existing machine-readable semantics

def test_machine_readable_contradiction_is_unchanged():
    data = structured()
    data["furniture"] = [claim("no bed", quote="no bed", count=0, kind="bed")]
    local = local_reading(furniture=[grounded_bed()])
    u = build_understanding(bridge(data, "no bed"), provider="test", model="model",
                            image_id="synthetic", source_type="uploaded",
                            local_plan_reading=local)
    assert u["provider_candidates"][0]["state"] == "CONTRADICTED"
