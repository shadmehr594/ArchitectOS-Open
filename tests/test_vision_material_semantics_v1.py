# -*- coding: utf-8 -*-
"""VISION_MATERIAL_SEMANTICS_V1 — RED then GREEN.

Three named defects, all reproduced against the unmodified production module
before any test was written:

  M1  generic metal is not steel
      MATERIAL_MARKERS mapped ("steel", ("steel","metal","aluminium",
      "aluminum","فلز","فولاد")), so "metal", "aluminum" and Persian فلز all
      became the SPECIFIC alloy `steel`. The ontology has no `steel` identity
      at all, so the observation and the knowledge block contradicted each
      other: observation said `steel`, knowledge said `metal`.

  M2  a panel is not a material identity
      ("composite", ("composite","panelling","panel","پانل")) turned
      "one prominent light/whitish ribbed panel" into `composite`. A panel is
      a product FORM; it can be stone, marble, wood, aluminium or composite.

  M3  alternatives are not simultaneous assertions
      "beige/tan veined stone or marble panels" produced observation
      ['stone','composite'] and knowledge ['marble','stone'] — BOTH sides of
      an "or" promoted to separate established identities.

  M4  a locative adjunct is not part of the negated material
      "No plaster on the brick wall" negated the brick as well, because the
      forward scope ran to the end of the string.

Acceptance principle: no material may become visually verified merely because
its name exists in the ontology, and an ontology lookup establishes what a
term MEANS, never what the image SHOWS.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.vision.architectural_observation_v1 import (  # noqa: E402
    MATERIAL_MARKERS,
    build_architectural_observation,
)
from core.vision.observed_material_knowledge_v1 import (  # noqa: E402
    resolve_observed_material_knowledge,
)


def _observe(phrase):
    return build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")


def _entries(phrase):
    return _observe(phrase).get("material_observations") or []


def _materials(phrase):
    return sorted({material for entry in _entries(phrase)
                   for material in (entry.get("materials") or [])})


def _alternatives(phrase):
    return [list(group) for entry in _entries(phrase)
            for group in (entry.get("material_alternatives") or [])]


def _knowledge(phrase):
    return resolve_observed_material_knowledge(_observe(phrase))


def _established(phrase):
    return [entry.get("ontology_id")
            for entry in (_knowledge(phrase).get("materials") or [])]


def _candidates(phrase):
    return [entry.get("ontology_id")
            for entry in (_knowledge(phrase).get("material_candidates") or [])]


# ============================================================
# M1 — generic metal is not steel
# ============================================================


def test_M1_generic_metal_is_not_steel():
    materials = _materials("flat metal canopy")
    assert "steel" not in materials, "a generic material family became an alloy"
    assert "metal" in materials, "the generic family was not recorded"


def test_M1_generic_metal_knowledge_agrees_with_the_observation():
    """Observation and knowledge must not name different materials."""
    assert "steel" not in _materials("flat metal canopy")
    assert _established("flat metal canopy") == ["metal"]


def test_M1_explicit_steel_is_still_steel():
    assert "steel" in _materials("steel columns")


def test_M1_aluminium_is_not_steel():
    for phrase in ("Aluminum frames", "aluminium window frames"):
        materials = _materials(phrase)
        assert "steel" not in materials, phrase
        assert "aluminium" in materials, phrase


def test_M1_wrought_iron_invents_no_steel():
    materials = _materials("wrought iron railing")
    assert "steel" not in materials
    assert "metal" not in materials


def test_M1_persian_specificity_boundary_is_preserved():
    assert "metal" in _materials("نمای فلز")
    assert "steel" not in _materials("نمای فلز")
    assert "steel" in _materials("ستون فولاد")


def test_M1_metal_and_wood_trim_keeps_both_without_inventing_steel():
    materials = _materials("Dark (black) painted metal/wood trim")
    assert "wood" in materials
    assert "metal" in materials
    assert "steel" not in materials


# ============================================================
# M2 — a panel is not a material identity
# ============================================================


@pytest.mark.parametrize("phrase", [
    "stone panels on the facade",
    "marble panels",
    "one prominent light/whitish ribbed panel",
    "aluminium composite panel",
])
def test_M2_panel_alone_never_means_composite(phrase):
    materials = _materials(phrase)
    if "composite" in phrase.lower():
        assert "composite" in materials, "an explicit composite was dropped"
    else:
        assert "composite" not in materials, (
            "a product form became a material identity: %r" % phrase)


def test_M2_explicit_composite_is_still_composite():
    assert "composite" in _materials("Composite cladding panels")


def test_M2_panel_is_preserved_in_the_source_descriptor():
    phrase = "one prominent light/whitish ribbed panel"
    descriptors = [entry.get("descriptor") for entry in _entries(phrase)]
    assert descriptors == [] or phrase in descriptors


# ============================================================
# M3 — alternatives are not simultaneous assertions
# ============================================================


def test_M3_or_expression_asserts_neither_alternative():
    materials = _materials("beige/tan veined stone or marble panels")
    assert "stone" not in materials, "one side of an 'or' was asserted"
    assert "marble" not in materials, "one side of an 'or' was asserted"


def test_M3_or_expression_preserves_the_complete_alternatives():
    groups = _alternatives("beige/tan veined stone or marble panels")
    assert groups == [["stone", "marble"]], groups


def test_M3_or_expression_keeps_the_exact_source_quotation():
    phrase = "beige/tan veined stone or marble panels"
    for entry in _entries(phrase):
        assert entry.get("evidence_phrase") == phrase
        assert entry.get("descriptor") == phrase


def test_M3_rendered_masonry_stays_one_alternative():
    """A substrate+finish construction is not split into two assertions."""
    groups = _alternatives(
        "clad in light beige/cream stone or rendered masonry")
    assert groups == [["stone", "rendered masonry"]], groups
    materials = _materials("clad in light beige/cream stone or rendered masonry")
    assert "plaster" not in materials
    assert "masonry" not in materials


def test_M3_comma_or_list_is_one_alternative_set():
    groups = _alternatives("facade in stone, marble, or granite")
    assert groups == [["stone", "marble", "granite"]], groups


def test_M3_and_is_still_simultaneous():
    materials = _materials("Brick masonry with stone trim")
    assert "brick" in materials
    assert "stone" in materials
    assert _alternatives("Brick masonry with stone trim") == []


def test_M3_slash_is_not_decided():
    """`/` may be alternatives, a mixed assembly, or two parts — do not guess."""
    groups = _alternatives("Dark (black) painted metal/wood trim")
    assert groups == [], groups
    materials = _materials("Dark (black) painted metal/wood trim")
    assert "metal" in materials and "wood" in materials


# ============================================================
# M3 end to end — the knowledge adapter must not promote both sides
# ============================================================


def test_M3_knowledge_does_not_establish_both_alternatives():
    established = _established("beige/tan veined stone or marble panels")
    assert "stone" not in established, "an alternative became established"
    assert "marble" not in established, "an alternative became established"


def test_M3_knowledge_exposes_the_alternatives_as_candidates():
    candidates = _candidates("beige/tan veined stone or marble panels")
    assert "stone" in candidates, candidates
    assert "marble" in candidates, candidates


def test_M3_candidates_are_never_authoritative():
    knowledge = _knowledge("beige/tan veined stone or marble panels")
    for entry in knowledge.get("material_candidates") or []:
        assert entry.get("established") is False
        assert entry.get("authoritative") is False
        assert entry.get("resolves_evidence") is False
        assert entry.get("verification") == "UNVERIFIED"
    assert knowledge.get("authoritative") is False
    assert knowledge.get("resolves_evidence") is False
    assert knowledge.get("verification") == "UNVERIFIED"


def test_M3_a_material_that_is_also_asserted_elsewhere_stays_established():
    """The alternative is the occurrence beside the `or`, not the first one."""
    phrase = "stone balustrade and stone or marble cladding"
    assert "stone" in _materials(phrase), "the asserted stone was withheld"
    established = _established(phrase)
    assert "stone" in established, established
    assert "marble" not in established, established
    assert "marble" in _candidates(phrase)


def test_M3_the_lookup_still_explains_the_term_it_matched():
    """A candidate is still explained — it is merely not established."""
    from core.knowledge.architectural_knowledge_resolver import (
        ArchitecturalKnowledgeResolver,
    )

    record = ArchitecturalKnowledgeResolver().data["materials"]["marble"]

    candidates = (_knowledge("beige/tan veined stone or marble panels")
                  .get("material_candidates") or [])
    marble = [entry for entry in candidates if entry["ontology_id"] == "marble"]
    assert marble, candidates
    assert marble[0]["ontology_normalized"] == record["normalized"]
    assert marble[0]["ontology_material_type"] == record["material_type"]
    assert marble[0]["ontology_properties"] == list(record["properties"])


# ============================================================
# M4 — a locative adjunct is not part of the negated material
# ============================================================


def test_M4_locative_adjunct_does_not_negate_the_substrate():
    materials = _materials("No plaster on the brick wall")
    assert "plaster" not in materials
    assert "brick" in materials, "the location noun was dragged into absence"


def test_M4_locative_adjunct_with_a_list():
    materials = _materials("No plaster or cladding on the brick wall")
    assert "plaster" not in materials
    assert "brick" in materials


def test_M4_absence_is_still_recorded():
    observation = _observe("No plaster on the brick wall")
    absent = sorted({kind for entry in
                     (observation.get("negative_observations") or [])
                     for kind in (entry.get("materials") or [])})
    assert "plaster" in absent, absent


# ============================================================
# Positive controls — these must keep working
# ============================================================


def test_P_natural_stone_is_generic_stone():
    assert "stone" in _materials("Natural stone facade")
    assert _established("Natural stone facade") == ["stone"]


def test_P_white_marble_resolves_to_marble():
    assert _established("White marble wall") == ["marble"]


def test_P_travertine_resolves_to_travertine_only():
    assert _established("Travertine cladding") == ["travertine"]


def test_P_brick_and_stone_coexist():
    materials = _materials("Brick masonry with stone trim")
    assert "brick" in materials and "stone" in materials
    assert set(_established("Brick masonry with stone trim")) == {"brick", "stone"}


def test_P_glass_and_steel_coexist():
    materials = _materials("Glass windows and steel columns")
    assert "glass" in materials and "steel" in materials


def test_P_concrete_and_plaster_coexist():
    materials = _materials("Concrete wall with plaster finish")
    assert "concrete" in materials and "plaster" in materials


def test_P_composite_cladding_keeps_composite():
    assert "composite" in _materials("Composite cladding panels")


@pytest.mark.parametrize("phrase,label", [
    ("Possibly marble", "marble"),
    ("appears to be stone", "stone"),
])
def test_P_hedged_material_keeps_the_term_and_the_hedge(phrase, label):
    assert label in _established(phrase)
    entries = _entries(phrase)
    assert entries, "the hedged material was dropped entirely"
    assert any(entry.get("hedged") is True for entry in entries), entries
    for entry in entries:
        assert entry.get("confidence") in ("LOW", "MEDIUM")


def test_P_unhedged_material_is_not_marked_hedged():
    entries = _entries("Natural stone facade")
    assert entries
    assert all(not entry.get("hedged") for entry in entries)


def test_P_ontology_identity_is_not_visual_verification():
    knowledge = _knowledge("Natural stone facade")
    assert knowledge["tier"] == "KNOWLEDGE_LOOKUP"
    assert knowledge["authoritative"] is False
    assert knowledge["resolves_evidence"] is False
    assert knowledge["verification"] == "UNVERIFIED"
    for entry in knowledge.get("materials") or []:
        assert entry["authoritative"] is False
        assert entry["resolves_evidence"] is False
        assert entry["subtype_established"] is False


# ============================================================
# The marker tables themselves
# ============================================================


def test_marker_table_separates_the_family_from_the_alloy():
    table = dict(MATERIAL_MARKERS)
    assert "metal" in table.get("metal", ()), "no generic metal identity"
    assert "steel" in table["steel"]
    assert "metal" not in table["steel"], "generic metal is still mapped to steel"
    assert "aluminium" not in table["steel"]
    assert "aluminum" not in table["steel"]
    assert "فلز" not in table["steel"]
    assert "فولاد" in table["steel"]


def test_marker_table_does_not_map_a_panel_to_composite():
    table = dict(MATERIAL_MARKERS)
    assert "panel" not in table["composite"]
    assert "panelling" not in table["composite"]
    assert "composite" in table["composite"]
