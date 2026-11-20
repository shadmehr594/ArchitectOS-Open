# ==========================================================
# ArchitectOS Adjacency Model v1
#
# PHASE 10 — PART 2 — ADJACENCY MODEL
#
# Relationships are NOT boolean. Five grades:
#
#   STRONG_CONNECTION    one continuous functional zone
#   NORMAL_CONNECTION    a proper, expected connection
#   WEAK_CONNECTION      possible but buffered / indirect only
#   AVOID_CONNECTION     should not be direct; privacy conflict
#   FORBIDDEN_CONNECTION must never open directly
#
# Every relation carries:
#   source_space, target_space, relation_type, reason, confidence,
#   provenance
#
# Evidence model
#   - A curated CURRICULUM overlay carries the canonical relations the
#     curriculum depends on, each with a stated REASON. This is
#     necessary: privacy band alone cannot separate "Bedroom<->Living"
#     (WEAK) from "Bedroom<->Entrance" (AVOID) — both are a 2-band gap.
#   - Everything else is DERIVED deterministically from the existing
#     corpus (typical_direct_connections,
#     forbidden_or_low_quality_connections, door/enclosure rules,
#     ontology adjacent_to and building-type relationships).
#
# Read-only. No writes. No second knowledge base.
# ==========================================================


from __future__ import annotations


import copy


from core.curriculum.space_types_v1 import space_types


CONTRACT = "AdjacencyModelV1"
VERSION = "1.0"


# ----------------------------------------------------------
# RELATION VOCABULARY
# ----------------------------------------------------------

REL_STRONG = "STRONG_CONNECTION"
REL_NORMAL = "NORMAL_CONNECTION"
REL_WEAK = "WEAK_CONNECTION"
REL_AVOID = "AVOID_CONNECTION"
REL_FORBIDDEN = "FORBIDDEN_CONNECTION"


ALL_RELATION_TYPES = (
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
)


# Higher = more connected. FORBIDDEN is the floor.
STRENGTH = {
    REL_FORBIDDEN: 0,
    REL_AVOID: 1,
    REL_WEAK: 2,
    REL_NORMAL: 3,
    REL_STRONG: 4,
}


RELATION_DISPLAY = {
    REL_STRONG: {
        "fa": "\u0627\u0631\u062a\u0628\u0627\u0637 \u0642\u0648\u06cc",
        "en": "strong connection",
    },
    REL_NORMAL: {
        "fa": "\u0627\u0631\u062a\u0628\u0627\u0637 \u0645\u0639\u0645\u0648\u0644\u06cc",
        "en": "normal connection",
    },
    REL_WEAK: {
        "fa": "\u0627\u0631\u062a\u0628\u0627\u0637 \u0636\u0639\u06cc\u0641",
        "en": "weak connection",
    },
    REL_AVOID: {
        "fa": "\u0627\u0631\u062a\u0628\u0627\u0637 \u0646\u0627\u0645\u0646\u0627\u0633\u0628",
        "en": "avoid connection",
    },
    REL_FORBIDDEN: {
        "fa": "\u0627\u0631\u062a\u0628\u0627\u0637 \u0645\u0645\u0646\u0648\u0639",
        "en": "forbidden connection",
    },
}


def relation_display(relation_type, language="en"):

    entry = RELATION_DISPLAY.get(relation_type) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(relation_type)


# ----------------------------------------------------------
# PRIVACY BANDS (PART 3 basis)
# ----------------------------------------------------------

PRIVACY_BANDS = {
    "PUBLIC": 0,
    "TRANSITION": 0,
    "COMMON": 0,
    "ENVIRONMENTAL": 0,
    "SEMI_PUBLIC": 1,
    "PRIVATE": 2,
    "SERVICE": 2,
}


def privacy_band(privacy_level):

    return PRIVACY_BANDS.get(privacy_level, 1)


# ----------------------------------------------------------
# CURATED RELATION OVERLAY
#
# Each entry: (space_a, space_b, relation_type, reason_fa, reason_en,
#              confidence)
# Stored undirected: order does not matter.
# ----------------------------------------------------------

RELATION_OVERLAY = (
    # ---- the brief's five canonical relations ----
    (
        "OPEN_KITCHEN", "DINING", REL_STRONG,
        "\u0622\u0645\u0627\u062f\u0647\u200c\u0633\u0627\u0632\u06cc \u063a\u0630\u0627 \u0648 \u063a\u0630\u0627 \u062e\u0648\u0631\u062f\u0646 \u06cc\u06a9 \u0645\u062d\u0648\u0631\u0647\u0654 \u06a9\u0627\u0631\u06a9\u0631\u062f\u06cc \u067e\u06cc\u0648\u0633\u062a\u0647 \u0647\u0633\u062a\u0646\u062f",
        "food preparation and eating form one continuous functional zone",
        0.95,
    ),
    (
        "LIVING_RECEPTION", "TERRACE_BALCONY", REL_NORMAL,
        "\u062a\u0631\u0627\u0633 \u0627\u062f\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u06cc \u0632\u0646\u062f\u06af\u06cc \u062f\u0631 \u0628\u06cc\u0631\u0648\u0646 \u0627\u0633\u062a\u061b \u0627\u0631\u062a\u0628\u0627\u0637 \u0645\u0633\u062a\u0642\u06cc\u0645 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a \u0648\u0644\u06cc \u0628\u062f\u0648\u0646 \u062f\u0631 \u0646\u06cc\u0633\u062a",
        "the terrace extends living outdoors; a direct connection is proper but not doorless",
        0.9,
    ),
    (
        "BEDROOM_DOUBLE", "LIVING_RECEPTION", REL_WEAK,
        "\u062e\u0648\u0627\u0628 \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u062c\u062f\u0627\u06cc\u06cc \u0635\u0648\u062a\u06cc \u0648 \u062f\u06cc\u062f\u0627\u0631\u06cc \u0627\u0633\u062a\u061b \u0641\u0642\u0637 \u0645\u0633\u06cc\u0631 \u0628\u0627\u0641\u0631 \u067e\u0630\u06cc\u0631\u0641\u062a\u0646\u06cc \u0627\u0633\u062a",
        "sleep needs acoustic and visual separation; only a buffered route is acceptable",
        0.85,
    ),
    (
        "BEDROOM_DOUBLE", "UNIT_ENTRY", REL_AVOID,
        "\u062a\u0636\u0627\u062f \u0639\u0631\u0635\u0647\u0654 \u062e\u0635\u0648\u0635\u06cc \u0628\u0627 \u0639\u0631\u0635\u0647\u0654 \u0648\u0631\u0648\u062f\u06cc\u061b \u0641\u0636\u0627\u06cc \u062e\u0648\u0627\u0628 \u0646\u0628\u0627\u06cc\u062f \u0631\u0648\u06cc \u0645\u0633\u06cc\u0631 \u0648\u0631\u0648\u062f \u0628\u0627\u0634\u062f",
        "privacy band conflict; a sleeping space must not sit on the arrival path",
        0.9,
    ),
    (
        "FAMILY_BATHROOM", "LIVING_RECEPTION", REL_FORBIDDEN,
        "\u0628\u0627\u0632\u0634\u0648\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0641\u0636\u0627\u06cc \u062e\u062f\u0645\u0627\u062a\u06cc \u0628\u0647 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc \u0631\u0633\u0645\u06cc \u0645\u0645\u0646\u0648\u0639 \u0627\u0633\u062a",
        "a wet/service space must never open directly onto a formal public space",
        0.95,
    ),
    # ---- supporting relations from PART 3 ----
    (
        "ENSUITE", "MASTER_BEDROOM_SLEEPING", REL_STRONG,
        "\u062d\u0645\u0627\u0645 \u0645\u0633\u062a\u0631 \u0628\u062e\u0634\u06cc \u0627\u0632 \u0633\u0648\u06cc\u062a \u062e\u0648\u0627\u0628 \u0627\u0633\u062a",
        "the ensuite is part of the master sleeping suite",
        0.9,
    ),
    (
        "BEDROOM_DOUBLE", "PRIVATE_HALL_CORRIDOR", REL_STRONG,
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0628\u0627\u06cc\u062f \u0627\u0632 \u0631\u0627\u0647\u0631\u0648\u06cc \u062e\u0635\u0648\u0635\u06cc \u062f\u0633\u062a\u0631\u0633\u06cc \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
        "a bedroom is entered from the private hall",
        0.9,
    ),
    (
        "GUEST_WC", "FOYER_SHOE_OFF", REL_NORMAL,
        "\u0633\u0631\u0648\u06cc\u0633 \u0645\u0647\u0645\u0627\u0646 \u062f\u0631 \u0622\u0633\u062a\u0627\u0646\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc \u0648 \u0628\u06cc\u0631\u0648\u0646 \u0627\u0632 \u0639\u0631\u0635\u0647\u0654 \u062e\u0635\u0648\u0635\u06cc \u0642\u0631\u0627\u0631 \u0645\u06cc\u200c\u06af\u06cc\u0631\u062f",
        "the guest WC sits at the public threshold, outside the private zone",
        0.85,
    ),
    (
        "LAUNDRY_UTILITY", "LIVING_RECEPTION", REL_FORBIDDEN,
        "\u0641\u0636\u0627\u06cc \u062e\u062f\u0645\u0627\u062a\u06cc \u0646\u0628\u0627\u06cc\u062f \u0628\u0647 \u0646\u0634\u06cc\u0645\u0646 \u0628\u0627\u0632 \u0634\u0648\u062f",
        "a utility space must not open onto the living room",
        0.9,
    ),
    (
        "LIVING_RECEPTION", "DINING", REL_STRONG,
        "\u0646\u0634\u06cc\u0645\u0646 \u0648 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u06cc\u06a9 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc \u067e\u06cc\u0648\u0633\u062a\u0647 \u0645\u06cc\u200c\u0633\u0627\u0632\u0646\u062f",
        "living and dining form one continuous public field",
        0.9,
    ),
    (
        "OPEN_KITCHEN", "LIVING_RECEPTION", REL_NORMAL,
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647\u0654 \u0628\u0627\u0632 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u0628\u0647 \u0646\u0634\u06cc\u0645\u0646 \u0645\u062a\u0635\u0644 \u0628\u0627\u0634\u062f",
        "an open kitchen may connect to the living room",
        0.85,
    ),
    (
        "STUDY", "LIVING_RECEPTION", REL_AVOID,
        "\u0645\u0637\u0627\u0644\u0639\u0647 \u0648 \u06a9\u0627\u0631 \u0628\u0647 \u062a\u0645\u0631\u06a9\u0632 \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f \u0648 \u0646\u0628\u0627\u06cc\u062f \u0628\u0647 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc \u0628\u0627\u0632 \u0634\u0648\u062f",
        "study needs focus and must not open onto the public field",
        0.85,
    ),
    (
        "STAIR", "PRIVATE_HALL_CORRIDOR", REL_NORMAL,
        "\u067e\u0644\u0647 \u0631\u0627\u0647\u0631\u0648\u06cc \u062e\u0635\u0648\u0635\u06cc \u0631\u0627 \u062a\u063a\u0630\u06cc\u0647 \u0645\u06cc\u200c\u06a9\u0646\u062f",
        "the stair feeds the private hall",
        0.8,
    ),
    (
        "TERRACE_BALCONY", "BEDROOM_DOUBLE", REL_WEAK,
        "\u062f\u0633\u062a\u0631\u0633\u06cc \u062e\u0635\u0648\u0635\u06cc \u0628\u0647 \u0628\u06cc\u0631\u0648\u0646 \u0645\u0645\u06a9\u0646 \u0627\u0633\u062a \u0648\u0644\u06cc \u0627\u0631\u062a\u0631\u062c\u0627\u062d \u062f\u0627\u0631\u062f \u0627\u0632 \u0646\u0634\u06cc\u0645\u0646 \u0628\u0627\u0634\u062f",
        "private outdoor access is possible but the living room is preferred",
        0.75,
    ),
    (
        "STORAGE_LINEN", "PRIVATE_HALL_CORRIDOR", REL_NORMAL,
        "\u0627\u0646\u0628\u0627\u0631\u06cc \u0627\u0632 \u0631\u0627\u0647\u0631\u0648\u06cc \u062e\u0635\u0648\u0635\u06cc \u062f\u0633\u062a\u0631\u0633\u06cc \u0645\u06cc\u200c\u06af\u06cc\u0631\u062f",
        "storage is served from the private hall",
        0.8,
    ),
)


# ----------------------------------------------------------
# ONTOLOGY RELATION TYPE -> GRADE
# ----------------------------------------------------------

_ONTOLOGY_RELATION_GRADE = {
    "direct_access": REL_STRONG,
    "connected": REL_NORMAL,
    "adjacent": REL_NORMAL,
    "vertical_connection": REL_NORMAL,
}


def _key(a, b):

    return tuple(sorted([str(a), str(b)]))


class AdjacencyModelV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, read_bridge=None):

        self.registry = registry or space_types

        self._read_bridge = read_bridge

        self._relations = None

        print(
            "\U0001f517 ADJACENCY MODEL v1.0 ONLINE "
            "(5 grades, reason + provenance)"
        )

    # ======================================================
    # BUILD
    # ======================================================

    def _ontology_relations(self):

        try:

            from core.conversation.knowledge_read_bridge_v1 import (
                knowledge_read_bridge,
            )

            bridge = self._read_bridge or knowledge_read_bridge

            ontology = bridge.architectural_ontology()

        except Exception:

            return []

        pairs = []

        for space_id, entry in (ontology.get("spaces") or {}).items():

            for target in entry.get("adjacent_to") or []:

                pairs.append((space_id, target, REL_NORMAL, "adjacent_to"))

        for building in (ontology.get("building_types") or {}).values():

            for relation in building.get("relationships") or []:

                source = relation.get("from")

                target = relation.get("to")

                grade = _ONTOLOGY_RELATION_GRADE.get(
                    relation.get("type"), REL_NORMAL
                )

                if source and target:

                    pairs.append(
                        (source, target, grade, relation.get("type"))
                    )

        return pairs

    # ------------------------------------------------------

    def _build(self):

        if self._relations is not None:

            return self._relations

        relations = {}

        # ---- 1. curated overlay (authoritative) ----
        for (
            source, target, relation_type, reason_fa, reason_en, confidence
        ) in RELATION_OVERLAY:

            relations[_key(source, target)] = self._record(
                source,
                target,
                relation_type,
                reason_en,
                confidence,
                "CURRICULUM_OVERLAY",
                reason_fa=reason_fa,
                derived=False,
            )

        # ---- 2. ontology evidence ----
        for source, target, grade, kind in self._ontology_relations():

            pair = _key(source, target)

            if pair in relations:

                continue

            if not self.registry.space(source) or not (
                self.registry.space(target)
            ):

                continue

            relations[pair] = self._record(
                source,
                target,
                grade,
                "ontology evidence: " + str(kind),
                0.6,
                "DERIVED_FROM_ONTOLOGY",
                derived=True,
            )

        # ---- 3. deterministic derivation from SPACE_SPECS ----
        for space_id, record in self.registry.spaces().items():

            for target in record.get("typical_adjacent") or []:

                pair = _key(space_id, target)

                if pair in relations:

                    continue

                if not self.registry.space(target):

                    continue

                grade, reason = self._derive(
                    space_id, target, listed=True, discouraged=False
                )

                relations[pair] = self._record(
                    space_id,
                    target,
                    grade,
                    reason,
                    0.7,
                    "DERIVED_FROM_SPACE_SPECS",
                    derived=True,
                )

            for target in record.get("discouraged_adjacent") or []:

                pair = _key(space_id, target)

                if pair in relations:

                    continue

                if not self.registry.space(target):

                    continue

                grade, reason = self._derive(
                    space_id, target, listed=False, discouraged=True
                )

                relations[pair] = self._record(
                    space_id,
                    target,
                    grade,
                    reason,
                    0.75,
                    "DERIVED_FROM_SPACE_SPECS",
                    derived=True,
                )

        self._relations = relations

        return relations

    # ------------------------------------------------------

    def _derive(self, source, target, listed, discouraged):

        a = self.registry.space(source) or {}

        b = self.registry.space(target) or {}

        band_a = privacy_band(a.get("privacy_level"))

        band_b = privacy_band(b.get("privacy_level"))

        gap = abs(band_a - band_b)

        access_a = a.get("access_requirements") or {}

        access_b = b.get("access_requirements") or {}

        open_ok = bool(
            access_a.get("open_connection_allowed")
            or access_b.get("open_connection_allowed")
        )

        door_required = (
            access_a.get("requires_door") == "REQUIRED"
            or access_b.get("requires_door") == "REQUIRED"
        )

        wet = bool(a.get("wet_zone") or b.get("wet_zone"))

        if discouraged:

            if gap >= 2 and wet:

                return (
                    REL_FORBIDDEN,
                    "listed as low quality AND a wet space opens across a "
                    "privacy conflict",
                )

            if gap >= 2:

                return (
                    REL_AVOID,
                    "listed as low quality and the privacy bands conflict",
                )

            return (
                REL_AVOID,
                "explicitly listed as a low quality connection",
            )

        if listed:

            if open_ok and not door_required and gap == 0:

                return (
                    REL_STRONG,
                    "listed as a direct connection, open plan allowed and "
                    "the same privacy band",
                )

            if gap <= 1:

                return (
                    REL_NORMAL,
                    "listed as a direct connection",
                )

            return (
                REL_WEAK,
                "listed, but the privacy bands are two steps apart",
            )

        if gap >= 2:

            return (
                REL_AVOID,
                "privacy band conflict and no direct connection listed",
            )

        if (a.get("zone") and a.get("zone") == b.get("zone")) or gap <= 1:

            return (
                REL_NORMAL,
                "same zone or adjacent privacy bands",
            )

        return (REL_WEAK, "no strong evidence either way")

    # ------------------------------------------------------

    def _record(
        self,
        source,
        target,
        relation_type,
        reason,
        confidence,
        provenance,
        reason_fa=None,
        derived=True,
    ):

        a, b = sorted([str(source), str(target)])

        return {

            "contract": CONTRACT + ".Relation",
            "version": VERSION,

            "relation_id": a + "::" + b,

            "source_space": a,
            "target_space": b,

            "relation_type": relation_type,

            "strength": STRENGTH.get(relation_type, 0),

            "reason": reason,
            "reason_fa": reason_fa,

            "confidence": round(float(confidence), 3),

            "provenance": provenance,

            "derived": bool(derived),

            "symmetric": True,
        }

    # ======================================================
    # READ API
    # ======================================================

    def relation(self, source, target):

        return copy.deepcopy(
            self._build().get(_key(source, target))
        )

    def relation_between(self, term_a, term_b):

        """Resolve two fa/en terms, then return their relation."""

        id_a = self.registry.find(term_a)

        id_b = self.registry.find(term_b)

        if not id_a or not id_b:

            return None

        return self.relation(id_a, id_b)

    def relations(self, space_id=None, relation_type=None):

        items = list(self._build().values())

        if space_id:

            items = [
                r for r in items
                if space_id in (r["source_space"], r["target_space"])
            ]

        if relation_type:

            items = [
                r for r in items if r["relation_type"] == relation_type
            ]

        return copy.deepcopy(
            sorted(items, key=lambda r: -r["strength"])
        )

    def relation_type_of(self, source, target):

        record = self.relation(source, target)

        return record["relation_type"] if record else None

    def should_connect(self, source, target):

        record = self.relation(source, target)

        return bool(
            record and record["relation_type"] in (REL_STRONG, REL_NORMAL)
        )

    def should_separate(self, source, target):

        record = self.relation(source, target)

        return bool(
            record and record["relation_type"] in (REL_AVOID, REL_FORBIDDEN)
        )

    def is_forbidden(self, source, target):

        return self.relation_type_of(source, target) == REL_FORBIDDEN

    def explain(self, source, target, language="en"):

        record = self.relation(source, target)

        if not record:

            return None

        lang = "fa" if str(language or "").startswith("fa") else "en"

        reason = (
            record.get("reason_fa")
            if lang == "fa" and record.get("reason_fa")
            else record.get("reason")
        )

        return {

            "source_space": record["source_space"],
            "target_space": record["target_space"],
            "relation_type": record["relation_type"],
            "relation_label": relation_display(
                record["relation_type"], lang
            ),
            "reason": reason,
            "confidence": record["confidence"],
            "provenance": record["provenance"],
            "acceptable": record["relation_type"] in (
                REL_STRONG, REL_NORMAL
            ),
            "language": lang,
        }

    # ------------------------------------------------------

    def report(self):

        relations = list(self._build().values())

        by_type = {}

        by_provenance = {}

        for record in relations:

            by_type[record["relation_type"]] = (
                by_type.get(record["relation_type"], 0) + 1
            )

            by_provenance[record["provenance"]] = (
                by_provenance.get(record["provenance"], 0) + 1
            )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "relation_count": len(relations),

            "by_relation_type": by_type,

            "by_provenance": by_provenance,

            "relation_types": list(ALL_RELATION_TYPES),

            "curated_relations": len(RELATION_OVERLAY),

            "boolean_relations": False,

            "overlay_is_authoritative": True,
        }


adjacency_model = AdjacencyModelV1()
