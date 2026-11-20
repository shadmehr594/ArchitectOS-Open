"""VISION END-TO-END RETENTION FIX V1 — generic regression tests.

Every fixture here is SYNTHETIC: no acceptance image, no image-specific token,
no tuned pixel threshold. The contracts under test are:

  * the canonical image type is never derived from a local reader's `grounded`
    status alone, and a provider drawing-type observation is surfaced
    separately, with its verification state, never inverted;
  * a local OCR lexicon SUBSTITUTION can never become a grounded space label;
  * the default user-visible answer reports the model's own observation,
    categorised and marked unverified, instead of discarding it;
  * a provider ABSENCE and a local PRESENCE produce a visible CONFLICT without
    changing any verification verdict;
  * the observer runtime defaults are the measured ones.
"""
import copy
import json

import pytest

from config.vision_config import VisionConfig
from core.vision.drawing_type_v1 import canonical_drawing_type, provider_drawing_type
from core.vision.general_visual_observer_v1 import CONTRACT, raw_observation
from core.vision.image_understanding_v1 import build_understanding
from core.vision.local_evidence_trust_v1 import label_promotion
from core.vision.observation_normalizer_v1 import CATEGORIES
from core.vision.provider_candidate_verification_v1 import claim_polarity
from core.vision.architectural_vision_grounding_v1 import ground_vision_evidence
from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_interpreter_v1 import build_plan_reading
from core.vision.vision_report_v1 import render_vision_report


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


def local_reading(*, labels=None, sheet_type=None, elements=None, furniture=None):
    reading = {
        "contract": "LocalPlanReadingV1", "version": "1.3", "status": "grounded",
        "source": "local_offline_raster", "provider_independent": True,
        "image_size": {"width": 200, "height": 200}, "ocr_status": "analyzed",
        "symbol_analysis_status": "analyzed", "element_analysis_status": "analyzed",
        "labels": labels or [], "openings": [], "element_evidence": elements or [],
        "furniture_evidence": furniture or [],
        "enclosure_geometry": {"count": None, "count_status": "uncertain", "regions": []},
    }
    if sheet_type is not None:
        reading["sheet_structure"] = {"sheet_type": sheet_type}
    return reading


def local_bed():
    return {"class": "bed", "bbox_pixels": [1, 1, 9, 9], "name": "bed",
            "corroboration": ["frame", "pillow", "blanket"], "status": "visible",
            "confidence": "MEDIUM", "evidence_type": "fixture",
            "source": "local_raster_symbol_topology",
            "provider_independent": True, "item_id": "synthetic",
            "raster_patch_sha256": "a" * 64}


def plan_reading_from_local(reading):
    """The real path: the observation layer owns `text_labels_if_visible`."""
    observation = build_architectural_observation({"local_plan_reading": reading})
    return build_plan_reading(observation)


def label(text, *, raw=None, correction=None, passes=2, bbox=(5, 5, 60, 18),
          semantic_function="balcony"):
    return {"text": text, "raw_ocr": text if raw is None else raw,
            "bbox_pixels": list(bbox), "status": "grounded_ocr",
            "evidence_type": "local_ocr", "confidence": "MEDIUM",
            "correction": correction, "independent_passes": passes,
            "ocr_confidence": 70, "semantic_function": semantic_function}


# ------------------------------------------------------- DEFECT 1: image type

def test_local_grounded_status_does_not_establish_a_floor_plan():
    u = build_understanding(bridge(structured()), local_plan_reading=local_reading())
    assert u["image_type"] == "unknown"


def test_only_a_positive_multi_panel_structure_is_local_plan_evidence():
    single = build_understanding(bridge(structured()),
                                 local_plan_reading=local_reading(sheet_type="single_plan"))
    multi = build_understanding(bridge(structured()),
                                local_plan_reading=local_reading(sheet_type="multi_plan"))
    assert single["image_type"] == "unknown"
    assert multi["image_type"] == "floor_plan_or_sketch"


def test_provider_drawing_type_is_surfaced_separately_and_never_inverted():
    text = "cadastral / land-survey sketch (kroki)"
    data = structured()
    data["drawing_type"] = claim(text, kind="map")
    u = build_understanding(bridge(data, text), local_plan_reading=local_reading())
    observed = u["provider_drawing_type"]
    assert observed["canonical"] == "site_diagram"
    assert observed["verified"] is False
    assert observed["source"] == "MODEL_OBSERVED"
    # the canonical type is NOT overwritten by the model's observation
    assert u["image_type"] == "unknown"


@pytest.mark.parametrize("text,expected", [
    ("floor plan", "floor_plan_or_sketch"),
    ("cadastral / land-survey sketch (kroki)", "site_diagram"),
    ("site plan", "site_diagram"),
    ("classical facade elevation", "facade_or_elevation"),
    ("photorealistic 3D architectural exterior rendering "
     "(not a line drawing, plan, or section)", "architectural_render_or_photo"),
    ("not a building floor plan", "unknown"),
    ("", "unknown"),
])
def test_canonical_drawing_type_is_negation_aware(text, expected):
    assert canonical_drawing_type(text) == expected


def test_provider_drawing_type_reader_ignores_non_drawing_type_claims():
    data = structured()
    data["observed_elements"] = [claim("five numbered lots", kind="parcel")]
    u = build_understanding(bridge(data), local_plan_reading=local_reading())
    assert u["provider_drawing_type"] is None
    assert provider_drawing_type(u) is None


# ------------------------------------------ DEFECT 2: local OCR trust rule

def plan_reading_from_understanding(u):
    """The real path, carrying the understanding's independent-corroboration set."""
    observation = build_architectural_observation(u)
    return build_plan_reading(observation)


def test_independently_corroborated_ocr_still_names_a_space():
    # VISION_RETENTION_FIX_V2 — promotion needs a genuinely INDEPENDENT
    # corroborator: a provider OCR claim that exactly matches the local text and
    # was CONFIRMED by the existing verifier.
    scope = "observation note"
    ocr = "آشپزخانه"
    data = structured()
    data["ocr_exact"] = [claim(ocr, kind="text")]
    u = build_understanding(bridge(data, scope + "\n" + ocr),
                            local_plan_reading=local_reading(
                                labels=[label(ocr, raw=ocr, correction=None, passes=3,
                                              semantic_function="kitchen")]))
    plan = plan_reading_from_understanding(u)
    statuses = {entry["text"]: entry["status"] for entry in plan["read_labels"]}
    assert statuses[ocr] == "grounded_ocr"
    assert any(entry["space"] == "kitchen" for entry in plan["named_spaces"])


def test_stable_but_not_independent_ocr_does_not_name_a_space():
    # several passes of ONE engine over ONE image = stability, not independence
    stable = label("آشپزخانه", raw="آشپزخانه", correction=None, passes=3,
                   semantic_function="kitchen")
    plan = plan_reading_from_local(local_reading(labels=[stable]))
    entry = plan["read_labels"][0]
    assert entry["status"] == "stable_local_ocr"
    assert entry["semantic_function"] is None and entry["zone"] is None
    assert plan["named_spaces"] == []


def test_lexicon_substitution_is_demoted_and_keeps_its_raw_ocr():
    guess = label("تراس", raw="زارتم", correction="architectural_lexicon_match")
    plan = plan_reading_from_local(local_reading(labels=[guess]))
    entry = plan["read_labels"][0]
    assert entry["status"] == "low_trust_ocr"
    assert entry["semantic_function"] is None
    assert entry["zone"] is None
    assert entry["raw_ocr"] == "زارتم"
    assert entry["correction"] == "architectural_lexicon_match"
    assert plan["named_spaces"] == []
    assert plan["zones"]["open_semi_open"] == []


def test_noisy_wide_bbox_guess_is_demoted():
    wide = label("حمام", raw="۱ ۱ 5 ۱ noise", correction="architectural_lexicon_match",
                 bbox=(10, 10, 199, 30))
    promoted, reason = label_promotion(wide)
    assert promoted is False and reason == "low_trust_ocr"


def test_exact_but_unverified_reading_is_demoted():
    promoted, reason = label_promotion(label("تراس", raw="تراس", passes=1))
    assert promoted is False and reason == "low_trust_ocr"


def test_semantic_function_is_never_created_from_an_unverified_ocr_label():
    guess = label("حمام", raw="ما", correction="architectural_lexicon_match",
                  semantic_function="bathroom")
    plan = plan_reading_from_local(local_reading(labels=[guess]))
    assert plan["named_spaces"] == []
    assert "bathroom" not in plan["zones"]["service"]


def test_low_trust_labels_are_preserved_with_provenance_not_deleted():
    guess = label("تراس", raw="زارتم", correction="architectural_lexicon_match")
    observation = build_architectural_observation(
        {"local_plan_reading": local_reading(labels=[guess])})
    assert observation["text_labels_if_visible"] == []
    preserved = observation["low_trust_ocr_labels"]
    assert preserved and preserved[0]["text"] == "تراس"
    assert preserved[0]["raw_ocr"] == "زارتم"
    assert preserved[0]["status"] == "low_trust_ocr"


# ------------------------------------- DEFECT 3: the default answer reports

def _interpretation(candidates, plan_reading=None):
    interp = {"space_type": "unknown", "confidence": "LOW", "observed_elements": [],
              "spatial_relations": [], "unknowns": [],
              "grounding": {"provider_candidates": candidates}}
    if plan_reading is not None:
        interp["plan_reading"] = plan_reading
    return interp


def _candidate(text, category, *, state="UNVERIFIED", certainty="ASSERTED"):
    return {"text": text, "category": category, "state": state, "grounded": False,
            "certainty": certainty, "kind": category, "count": None}


def test_default_answer_reports_the_model_observation_with_its_state():
    candidates = [
        _candidate("cadastral / land-survey sketch (kroki)", "drawing_type"),
        _candidate("five numbered lots (1-5)", "observed_elements"),
        _candidate("8269.31 m2", "ocr_exact"),
    ]
    text = render_vision_report(_interpretation(candidates), "fa")
    assert "cadastral / land-survey sketch (kroki)" in text
    assert "site_diagram" in text
    assert "تأیید نشده" in text
    assert "five numbered lots" in text
    assert "8269.31 m2" in text
    assert "پلان معماری" not in text


def test_default_answer_never_asserts_a_plan_when_the_model_says_otherwise():
    candidates = [_candidate("photorealistic 3D architectural exterior rendering",
                             "drawing_type")]
    text = render_vision_report(_interpretation(candidates), "fa")
    assert "architectural_render_or_photo" in text
    assert "پلان معماری" not in text


def test_default_answer_is_categorised_and_capped_not_a_raw_dump():
    candidates = ([_candidate("drawing", "drawing_type")]
                  + [_candidate("element %d" % i, "observed_elements") for i in range(60)]
                  + [_candidate("num %d" % i, "ocr_exact") for i in range(60)])
    text = render_vision_report(_interpretation(candidates), "fa")
    assert "مشاهدات معماری مدل" in text
    assert "متن و اعداد" in text
    assert text.count("element ") <= 18
    assert text.count("num ") <= 18


def test_legacy_interpretation_without_provider_observation_is_unchanged():
    legacy = {"space_type": "master bedroom", "confidence": "HIGH",
              "observed_elements": ["sleeping element visible"], "spatial_relations": [],
              "unknowns": []}
    text = render_vision_report(legacy, "fa")
    assert "فضای معماری احتمالی" in text
    assert "مشاهدات معماری مدل" not in text


def test_english_rendering_still_ignores_the_provider_summary():
    candidates = [_candidate("cadastral / land-survey sketch (kroki)", "drawing_type")]
    text = render_vision_report(_interpretation(candidates), "en")
    assert "Possible architectural space" in text


# ------------------------------------------- DEFECT 4: polarity and conflict

@pytest.mark.parametrize("c,expected", [
    ({"text": "bed", "count": 0, "certainty": "ASSERTED", "category": "furniture"}, "ABSENT"),
    ({"text": "bed", "count": None, "certainty": "ASSERTED", "category": "furniture"}, "PRESENT"),
    ({"text": "no bed", "count": None, "certainty": "ASSERTED", "category": "furniture"}, "ABSENT"),
    ({"text": "bed", "count": None, "certainty": "UNKNOWN", "category": "furniture"}, "UNKNOWN"),
    ({"text": "x", "count": None, "certainty": "ASSERTED", "category": "unknowns"}, "UNKNOWN"),
])
def test_claim_polarity_is_structured(c, expected):
    assert claim_polarity(c) == expected


def test_low_trust_ocr_cannot_create_a_conflict():
    # VISION_RETENTION_FIX_V2 — a lexicon guess is not a trusted LOCAL PRESENT,
    # so it must not manufacture a scope conflict.
    text = "it is a land plan, not an architectural interior"
    data = structured()
    data["interpretations"] = [claim(text, kind="classification")]
    u = build_understanding(bridge(data, text), local_plan_reading=local_reading(
        labels=[label("حمام", raw="ما", correction="architectural_lexicon_match",
                      semantic_function="bathroom")]))
    assert ground_vision_evidence(u)["conflicts"] == []


def test_independently_corroborated_ocr_can_create_a_conflict():
    scope = "it is a land plan, not an architectural interior"
    ocr = "حمام"
    data = structured()
    data["interpretations"] = [claim(scope, kind="classification")]
    data["ocr_exact"] = [claim(ocr, kind="text")]
    u = build_understanding(bridge(data, scope + "\n" + ocr),
                            local_plan_reading=local_reading(
                                labels=[label(ocr, raw=ocr, correction=None, passes=3,
                                              semantic_function="bathroom")]))
    conflicts = ground_vision_evidence(u)["conflicts"]
    assert conflicts, "a TRUSTED local interior space must conflict with a scope absence"
    assert conflicts[0]["resolved"] == "CONFLICTING"


def test_machine_readable_contradiction_verdict_is_unchanged():
    data = structured()
    data["furniture"] = [claim("no bed", quote="no bed", count=0, kind="bed")]
    u = build_understanding(bridge(data, "no bed"),
                            local_plan_reading=local_reading(furniture=[local_bed()]))
    assert u["provider_candidates"][0]["state"] == "CONTRADICTED"


def test_prose_absence_without_the_machine_form_stays_unverified():
    data = structured()
    data["furniture"] = [claim("bed", quote="bed", certainty="ASSERTED", kind="bed")]
    u = build_understanding(bridge(data, "no bed"),
                            local_plan_reading=local_reading(furniture=[local_bed()]))
    assert u["provider_candidates"][0]["state"] == "UNVERIFIED"


# ---------------------------------------------- DEFECT 5: observer defaults

def test_observer_runtime_defaults_are_the_measured_ones(monkeypatch):
    for name in ("ARCHITECTOS_VISION_OBSERVER_TOKENS", "ARCHITECTOS_VISION_OBSERVER_TIMEOUT",
                 "ARCHITECTOS_VISION_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    cfg = VisionConfig.from_env()
    assert cfg.observer_tokens == 4096
    assert cfg.observer_timeout == 600
    assert cfg.timeout == 300  # the legacy general value is unchanged


def test_legacy_vision_timeout_still_drives_the_observer(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_VISION_OBSERVER_TIMEOUT", raising=False)
    monkeypatch.setenv("ARCHITECTOS_VISION_TIMEOUT", "90")
    assert VisionConfig.from_env().observer_timeout == 90


def test_observer_specific_timeout_overrides_the_legacy_value(monkeypatch):
    monkeypatch.setenv("ARCHITECTOS_VISION_TIMEOUT", "90")
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_TIMEOUT", "600")
    assert VisionConfig.from_env().observer_timeout == 600


def test_observer_request_uses_the_observer_timeout(monkeypatch, tmp_path):
    from PIL import Image
    from core.vision.vision_provider_ollama_v1 import OllamaVisionProvider

    monkeypatch.delenv("ARCHITECTOS_VISION_OBSERVER_TIMEOUT", raising=False)
    monkeypatch.delenv("ARCHITECTOS_VISION_TIMEOUT", raising=False)
    path = tmp_path / "synthetic.png"
    Image.new("RGB", (64, 48), "white").save(path)

    calls = []

    class Transport:
        def post(self, url, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("stop-after-capture")

    provider = OllamaVisionProvider(config=VisionConfig.from_env(), session=Transport())
    provider.observer.observe({"path": str(path)})
    assert calls and calls[0]["timeout"] == 600
    assert calls[0]["json"]["options"]["num_predict"] == 4096
    assert calls[0]["json"]["options"]["num_ctx"] == 32768
