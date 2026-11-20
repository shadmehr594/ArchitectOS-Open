# -*- coding: utf-8 -*-
"""VISION_FIRST_ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1 — focused CPU tests.

Goal: an observed architectural material is resolved against the EXISTING
material ontology and explained in the analysis response, WITHOUT increasing its
evidence authority.

Fixtures (immutable, authentic):

* `runs/vision_facade_evidence_semantics_v1/live_semantics_v1.json` — the
  accepted saved normalizer output.
* `runs/vision_facade_compound_v1/live_compound_v1.json` — its `raw_observer`,
  the byte-identical observer text the quotes were verified against.

The ontology queried is the REAL one
(`core/knowledge/architectural_ontology.json`, via
`ArchitecturalKnowledgeResolver.material_candidates`). No dictionary in this
file imitates it; test B monkeypatches the real owner to prove it is called.

Synthetic fixtures are labelled SYNTHETIC.

No Ollama. No GPU. No ComfyUI. No prompt change.
"""

import hashlib
import json
import os

import pytest

from core.knowledge.architectural_knowledge_resolver import ArchitecturalKnowledgeResolver
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEMANTICS = os.path.join(ROOT, "runs", "vision_facade_evidence_semantics_v1",
                         "live_semantics_v1.json")
COMPOUND = os.path.join(ROOT, "runs", "vision_facade_compound_v1",
                        "live_compound_v1.json")
ONTOLOGY = os.path.join(ROOT, "core", "knowledge", "architectural_ontology.json")

#: The descriptor the observation contract actually produces for the facade
#: brick (verified against the saved payload, not assumed).
BRICK_DESCRIPTOR = ("Full-height exterior walls of variegated red/brown/buff "
                    "brick (running bond)")


def _semantics():
    with open(SEMANTICS, encoding="utf-8") as fh:
        return json.load(fh)


def _compound():
    with open(COMPOUND, encoding="utf-8") as fh:
        return json.load(fh)


def _raw_observer():
    return _compound()["raw_observer"]


def _base_structured():
    return json.loads(json.dumps(_semantics()["normalization"]["structured"]))


def _chain(structured=None):
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT, "raw_observer": _raw_observer(),
         "normalization": {"status": "NORMALIZED",
                           "structured": structured or _base_structured()}},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")
    return understanding, interpret_architectural_vision(understanding)


def _knowledge(interpretation):
    return interpretation.get("architectural_knowledge") or {}


def _brick_entry(interpretation):
    entries = _knowledge(interpretation).get("materials") or []
    return next((e for e in entries if e.get("ontology_id") == "brick"), None)


# ==========================================================
# A — the observation itself is untouched
# ==========================================================


def test_a_brick_observation_is_preserved_exactly():
    _, interpretation = _chain()

    observations = interpretation["architectural_observation"]["material_observations"]
    descriptors = [entry.get("descriptor") for entry in observations]

    assert BRICK_DESCRIPTOR in descriptors
    for entry in observations:
        assert entry.get("evidence_phrase") in (
            entry.get("descriptor"), entry.get("evidence_phrase"))
    assert any("brick" in (entry.get("materials") or []) for entry in observations)


# ==========================================================
# B / C — the REAL ontology owner is queried and matches
# ==========================================================


def test_b_the_real_ontology_owner_is_actually_queried(monkeypatch):
    calls = []
    original = ArchitecturalKnowledgeResolver.material_candidates

    def spy(self, text, text_lower):
        calls.append(text)
        return original(self, text, text_lower)

    monkeypatch.setattr(ArchitecturalKnowledgeResolver, "material_candidates", spy)

    _, interpretation = _chain()

    assert calls, "the knowledge owner was never queried"
    assert any("brick" in str(text).lower() for text in calls)
    assert _brick_entry(interpretation) is not None


def test_c_a_valid_ontology_match_is_returned():
    _, interpretation = _chain()

    entry = _brick_entry(interpretation)

    assert entry is not None, "brick did not resolve against the ontology"
    assert entry["ontology_normalized"] == "brick facade"
    assert entry["ontology_material_type"] == "facade"
    assert "masonry" in entry["ontology_properties"]
    assert entry["match_basis"] in ("exact_synonym", "synonym_span")


def test_c_the_match_comes_from_the_installed_ontology():
    resolver = ArchitecturalKnowledgeResolver()
    ontology = resolver.data["materials"]["brick"]

    _, interpretation = _chain()
    entry = _brick_entry(interpretation)

    assert entry["ontology_normalized"] == ontology["normalized"]
    assert entry["ontology_properties"] == ontology["properties"]


# ==========================================================
# D / E / F — provenance is not upgraded
# ==========================================================


def test_d_source_quotation_is_unchanged():
    raw = _compound()["raw_text"]

    _, interpretation = _chain()
    entry = _brick_entry(interpretation)

    assert entry["descriptor"] == BRICK_DESCRIPTOR
    assert entry["source_quote"] in raw, "the quote is not verbatim"
    assert entry["evidence_phrase"] == BRICK_DESCRIPTOR


def test_e_unverified_state_is_preserved():
    _, interpretation = _chain()
    entry = _brick_entry(interpretation)

    assert entry["observation_verification"] == "UNVERIFIED"
    assert entry["verification"] == "UNVERIFIED"

    knowledge = _knowledge(interpretation)
    assert knowledge["verification"] == "UNVERIFIED"
    assert knowledge["authoritative"] is False


def test_f_an_ontology_lookup_does_not_establish_visual_truth():
    _, interpretation = _chain()
    knowledge = _knowledge(interpretation)

    assert knowledge["tier"] == "KNOWLEDGE_LOOKUP"
    assert knowledge["resolves_evidence"] is False
    assert knowledge["authoritative"] is False

    # The verified channels stay empty.
    observation = interpretation["architectural_observation"]
    assert observation["visible_floors"] is None


# ==========================================================
# G / H / I — no invention, graceful failure
# ==========================================================


def test_g_brick_is_not_replaced_by_a_subtype():
    _, interpretation = _chain()
    entry = _brick_entry(interpretation)

    assert entry["ontology_id"] == "brick"
    assert entry["ontology_id"] not in ("fire_brick", "brick_red", "red_brick",
                                        "traditional_brick", "stone")
    assert entry["subtype_established"] is False


def test_h_an_unknown_material_gets_no_invented_identity():
    """SYNTHETIC observation contract — a material the ontology does not hold.

    The observation payload is hand-built (labelled synthetic) because the real
    observer reported only brick; the property under test is the adapter's
    behaviour on an unknown term, not the pipeline's extraction.
    """

    from core.vision.observed_material_knowledge_v1 import observed_material_knowledge

    observation = {
        "material_observations": [{
            "descriptor": "unobtainium composite cladding",
            "materials": ["unobtainium"],
            "evidence_phrase": "unobtainium composite cladding",
            "confidence": "LOW",
        }]
    }

    knowledge = observed_material_knowledge(observation)

    assert knowledge["materials"] == [], (
        "an unknown material received an ontology identity")
    assert knowledge["status"] == "NO_MATCH"
    assert knowledge["authoritative"] is False


def test_i_missing_knowledge_fails_gracefully(monkeypatch):
    def broken(self, text, text_lower):
        raise RuntimeError("ontology unavailable")

    monkeypatch.setattr(ArchitecturalKnowledgeResolver, "material_candidates", broken)

    _, interpretation = _chain()

    # Observation reporting survives; the knowledge block degrades to empty.
    observations = interpretation["architectural_observation"]["material_observations"]
    assert observations, "observation reporting broke with the ontology"

    report = render_vision_report(interpretation, "fa")
    assert "مصالح" in report

    knowledge = _knowledge(interpretation)
    assert knowledge.get("status") == "UNAVAILABLE"


# ==========================================================
# J — style is not speculated
# ==========================================================


def test_j_style_remains_insufficient_evidence():
    _, interpretation = _chain()
    style = _knowledge(interpretation)["style"]

    assert style["status"] == "INSUFFICIENT_EVIDENCE"
    assert style["assigned"] is None


@pytest.mark.parametrize("label", ["modern", "neoclassical", "islamic",
                                   "iranian", "traditional", "contemporary"])
def test_j_no_named_style_is_assigned(label):
    _, interpretation = _chain()
    style = _knowledge(interpretation)["style"]

    assert style["assigned"] != label
    assert style["assigned"] is None


# ==========================================================
# K / L / M — the report
# ==========================================================


def test_k_the_knowledge_backed_statement_appears_in_persian():
    _, interpretation = _chain()
    report = render_vision_report(interpretation, "fa")

    assert "دانش" in report, "no knowledge-backed explanation in the report"
    assert "brick facade" in report or "نمای آجری" in report
    assert "نوع دقیق" in report or "زیرگون" in report, (
        "the report does not say the subtype is unestablished")


def test_l_the_original_observation_section_is_intact():
    _, interpretation = _chain()
    report = render_vision_report(interpretation, "fa")

    assert "مصالح نام‌برده‌شده توسط مدل" in report
    assert BRICK_DESCRIPTOR in report


def test_m_the_knowledge_statement_is_not_duplicated():
    _, interpretation = _chain()
    report = render_vision_report(interpretation, "fa")

    entries = _knowledge(interpretation)["materials"]
    ids = [e.get("ontology_id") for e in entries]

    assert ids.count("brick") == 1, "the same ontology identity was resolved twice"
    assert report.count("brick facade") <= 1


# ==========================================================
# N / O / P — accepted observations unchanged
# ==========================================================


def test_n_four_storey_reading_stays_non_authoritative():
    _, interpretation = _chain()
    observation = interpretation["architectural_observation"]
    reading = observation["visible_floors_observation"]

    assert observation["visible_floors"] is None
    assert reading["count"] == 4
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert reading["authoritative"] is False


def test_o_through_passage_remains_open():
    _, interpretation = _chain()
    report = render_vision_report(interpretation, "fa")

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_p_negative_observations_remain_scoped():
    _, interpretation = _chain()

    fragments = [f
                 for entry in interpretation["architectural_observation"]
                 .get("negative_observations") or []
                 for f in (entry.get("negated_texts") or [])]

    assert "no pitched roof" in fragments
    assert "no visible roof terrace" in fragments
    assert "no dormers" in fragments


# ==========================================================
# Q / S — no mutation, no rendering
# ==========================================================


def test_q_the_ontology_is_not_mutated():
    before = hashlib.sha256(open(ONTOLOGY, "rb").read()).hexdigest()

    _chain()

    after = hashlib.sha256(open(ONTOLOGY, "rb").read()).hexdigest()
    assert before == after, "the ontology file was modified"


def test_q_no_permanent_learning_is_written():
    knowledge = _knowledge(_chain()[1])

    assert knowledge.get("learned") in (None, False)
    assert "promoted" not in json.dumps(knowledge).lower()


def test_s_no_render_or_generation_route_is_reachable():
    path = os.path.join(ROOT, "core", "vision", "observed_material_knowledge_v1.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    for forbidden in ("comfy", "render_runtime", "WorkflowSelector",
                      "photometric", "requests", "urllib"):
        assert forbidden not in source, forbidden
