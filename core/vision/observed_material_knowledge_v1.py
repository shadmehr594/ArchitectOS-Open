# -*- coding: utf-8 -*-
"""Observed material -> existing architectural knowledge.

ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1
---------------------------------
This is an ADAPTER, not a knowledge engine. It owns no vocabulary, no ontology
and no rules: every match comes from the installed
`core/knowledge/architectural_ontology.json` through the existing owner
`ArchitecturalKnowledgeResolver.material_candidates()` — the same call the
request-side resolver already uses.

WHAT A LOOKUP DOES AND DOES NOT MEAN
------------------------------------
An ontology lookup establishes what a TERM means. It does NOT verify that the
image contains that material. The observer's statement is still a model
observation: `verification` stays UNVERIFIED, `authoritative` is False and
`resolves_evidence` is False. Source-quote verification (the quote really is in
the observer text) is a different thing from independent visual confirmation,
and this module never conflates them.

The generic/subtype boundary is respected: the ontology has a generic `brick`
identity whose own properties are ("masonry", "generic"), and it is never
upgraded to `fire_brick`, `brick_red`, `traditional_brick` or `mud_brick` from
an observed colour or bond pattern. A colour ("red/brown/buff") is not a
manufacturing subtype, and "running bond" is a reported arrangement, not proof
of brick dimensions or composition.
"""

import copy
import re

CONTRACT = "ObservedArchitecturalKnowledgeV1"
TIER = "KNOWLEDGE_LOOKUP"
ONTOLOGY_SOURCE = "core/knowledge/architectural_ontology.json"

#: A disjunctive coordinator next to a term is what marks it as an
#: ALTERNATIVE rather than an assertion.
_DISJUNCTION = re.compile(r"\b(?:or|nor)\b", re.IGNORECASE)

#: How far to look for that coordinator on either side of an occurrence.
_DISJUNCTION_WINDOW = 6

#: A style is never assigned here. Composition cues (a window grid, rows, a
#: flat parapet, brick masonry) are not sufficient evidence for a named style,
#: so the honest answer is that no style is established.
STYLE_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

_resolver = None


def _knowledge_owner():
    """The EXISTING ontology owner, constructed once per process."""

    global _resolver

    if _resolver is None:

        from core.knowledge.architectural_knowledge_resolver import (
            ArchitecturalKnowledgeResolver,
        )

        _resolver = ArchitecturalKnowledgeResolver()

    return _resolver


def _match_basis(descriptor, candidate, record):
    """How the term matched: an exact synonym, or a span inside the text."""

    span = descriptor[candidate["start"]:candidate["end"]].strip()

    synonyms = [str(s).strip().lower() for s in (record.get("synonyms") or [])]

    if span.lower() in synonyms:

        return "exact_synonym", span

    return "synonym_span", span


def _locate_alternative(low, text):
    """Where in ``low`` this alternative actually sits.

    A plain ``find`` picks the FIRST occurrence, which is wrong when the same
    material is also asserted elsewhere:

        "stone balustrade and stone or marble cladding"

    The first `stone` is the balustrade — a definite material. The one that is
    an alternative is the one standing next to the disjunctive coordinator, so
    the occurrence beside an `or`/`nor` wins.
    """

    positions = []

    start = low.find(text)

    while start >= 0:

        positions.append(start)

        start = low.find(text, start + 1)

    if not positions:

        return None

    def scored(position):

        before = low[max(0, position - _DISJUNCTION_WINDOW):position]

        after = low[position + len(text):
                     position + len(text) + _DISJUNCTION_WINDOW]

        return int(bool(_DISJUNCTION.search(before))
                   or bool(_DISJUNCTION.search(after)))

    best = max(positions, key=lambda item: (scored(item), -item))

    return (best, best + len(text))


def _alternative_regions(descriptor, alternatives):
    """Character regions of ``descriptor`` that spell an ALTERNATIVE.

    `material_alternatives` holds verbatim slices of the descriptor, so each
    one can be located again exactly. A candidate whose matched span falls
    inside one of these regions was named as one side of an "or" — it is a
    candidate identity, not an established material.
    """

    regions = []

    low = descriptor.lower()

    for group in alternatives or []:

        for alternative in group or []:

            text = str(alternative or "").strip().lower()

            if not text:

                continue

            region = _locate_alternative(low, text)

            if region:

                regions.append(region)

    return regions


def _inside(regions, candidate):
    """True when the candidate's matched span lies inside an alternative."""

    return any(start <= candidate["start"] and candidate["end"] <= end
               for start, end in regions)


def resolve_observed_material_knowledge(observation):
    """Knowledge for the materials an observation reports, or a safe empty block.

    Never raises: a broken or missing ontology degrades the knowledge block to
    `status = UNAVAILABLE` and leaves observation reporting untouched.

    VISION_MATERIAL_SEMANTICS_V1
    ----------------------------
    The lookup used to scan the FULL descriptor and publish every hit as an
    established material. For "beige/tan veined stone or marble panels" that
    promoted BOTH sides of an "or" into separate ontology entries — the
    observation had already stopped asserting them, and the adapter put them
    back.

    The descriptor is still what gets resolved (the ontology matches TERMS,
    not labels), but a hit that falls inside an alternative region is routed
    to `material_candidates` with `established: False`. `materials` therefore
    means "the model asserted this and the ontology explains it", which is
    the meaning every consumer already relied on.
    """

    observations = []

    if isinstance(observation, dict):

        observations = observation.get("material_observations") or []

    block = {
        "contract": CONTRACT,
        "tier": TIER,
        "verification": "UNVERIFIED",
        "authoritative": False,
        # A lookup explains a term; it never corroborates the image.
        "resolves_evidence": False,
        "ontology_source": ONTOLOGY_SOURCE,
        "learned": False,
        "materials": [],
        "material_candidates": [],
        "style": {
            "status": STYLE_INSUFFICIENT,
            "assigned": None,
            "reason": "composition cues alone do not establish a named style",
        },
    }

    if not observations:

        block["status"] = "NO_OBSERVATION"

        return block

    try:

        owner = _knowledge_owner()

        materials = owner.data.get("materials", {})

    except Exception as error:  # noqa: BLE001

        block["status"] = "UNAVAILABLE"
        block["error"] = type(error).__name__

        return block

    entries = []

    candidate_entries = []

    seen = set()

    seen_candidates = set()

    try:

        for observation_entry in observations:

            if not isinstance(observation_entry, dict):

                continue

            descriptor = (observation_entry.get("descriptor")
                          or observation_entry.get("evidence_phrase") or "")

            if not descriptor:

                continue

            hedged = observation_entry.get("hedged") is True

            regions = _alternative_regions(
                descriptor, observation_entry.get("material_alternatives"))

            candidates = owner.material_candidates(descriptor, descriptor.lower())

            for candidate in owner.suppress_contained_materials(candidates):

                ontology_id = candidate.get("id")

                if not ontology_id:

                    continue

                record = materials.get(ontology_id) or {}

                basis, matched_term = _match_basis(descriptor, candidate, record)

                if _inside(regions, candidate):

                    # Named as ONE SIDE of an "or". The ontology explains what
                    # the term means; it does not make the term established.
                    if ontology_id in seen_candidates:

                        continue

                    seen_candidates.add(ontology_id)

                    candidate_entries.append({
                        "descriptor": descriptor,
                        "evidence_phrase": observation_entry.get("evidence_phrase"),
                        "source_quote": observation_entry.get("evidence_phrase"),
                        "alternative_group": True,
                        "established": False,
                        "hedged": hedged,
                        "ontology_id": ontology_id,
                        "ontology_normalized": candidate.get("normalized"),
                        "ontology_material_type": record.get("material_type"),
                        "ontology_properties": list(record.get("properties") or []),
                        "match_basis": basis,
                        "matched_term": matched_term,
                        "observation_verification": "UNVERIFIED",
                        "verification": "UNVERIFIED",
                        "subtype_established": False,
                        "specifications_established": False,
                        "authoritative": False,
                        "resolves_evidence": False,
                    })

                    continue

                if ontology_id in seen:

                    # One identity is explained ONCE, even when two descriptors
                    # ("facade brick" and "brick piers") name the same material.
                    continue

                seen.add(ontology_id)

                entry = {
                    # ---- the observation, unchanged ----
                    "descriptor": descriptor,
                    "evidence_phrase": observation_entry.get("evidence_phrase"),
                    "source_quote": observation_entry.get("evidence_phrase"),
                    "observation_materials": list(
                        observation_entry.get("materials") or []),
                    "observation_confidence": observation_entry.get("confidence"),
                    "observation_verification": "UNVERIFIED",
                    "verification": "UNVERIFIED",
                    # ---- the knowledge lookup ----
                    "ontology_id": ontology_id,
                    "ontology_normalized": candidate.get("normalized"),
                    "ontology_material_type": record.get("material_type"),
                    "ontology_properties": list(record.get("properties") or []),
                    "match_basis": basis,
                    "matched_term": matched_term,
                    # ---- what the lookup does NOT establish ----
                    "subtype_established": False,
                    "specifications_established": False,
                    "authoritative": False,
                    "resolves_evidence": False,
                }

                if hedged:

                    entry["hedged"] = True

                entries.append(entry)

    except Exception as error:  # noqa: BLE001

        block["status"] = "UNAVAILABLE"
        block["error"] = type(error).__name__

        return block

    # An identity that IS established somewhere is not also a candidate.
    candidate_entries = [item for item in candidate_entries
                         if item["ontology_id"] not in seen]

    block["materials"] = entries

    block["material_candidates"] = candidate_entries

    if entries:

        block["status"] = "RESOLVED"

    elif candidate_entries:

        # Terms were named but none of them was asserted — the lookup still
        # explains them, and says so without establishing anything.
        block["status"] = "CANDIDATES_ONLY"

    else:

        block["status"] = "NO_MATCH"

    return block


def observed_material_knowledge(observation):
    """Public alias used by the interpreter."""

    return copy.deepcopy(resolve_observed_material_knowledge(observation))
