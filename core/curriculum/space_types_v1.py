# ==========================================================
# ArchitectOS Space Types v1
#
# PHASE 10 — PART 1 — SPACE TYPE KNOWLEDGE MODEL
#
# A UNIFIED space-type contract over knowledge ArchitectOS ALREADY
# OWNS.  This module is an ADAPTER + a small additive overlay, not a
# second knowledge base.
#
# Sources reused (never rewritten):
#   core/architecture/knowledge/architectural_space_knowledge_v1.py
#       SPACE_SPECS — 41 residential spaces: names{fa,en},
#       functional_definition, primary_function, privacy_class,
#       circulation_role, typical_direct_connections,
#       forbidden_or_low_quality_connections, door/enclosure rules,
#       daylight/ventilation, dimensions
#   core/knowledge/architectural_ontology.json
#       40 spaces: synonyms (fa+en), zone, space_type, access,
#       adjacent_to
#
# Everything is read through `knowledge_read_bridge_v1` (PHASE 09), so
# there is exactly ONE reader of the corpus.
#
# What this module ADDS (the genuinely missing parts):
#   - a common identity across the two existing models
#   - `category`: the curriculum taxonomy
#     (PUBLIC / SEMI_PUBLIC / PRIVATE / SERVICE / CIRCULATION / EXTERNAL)
#     derived deterministically, with a small explicit OVERLAY where the
#     curriculum reading differs from the frozen architectural taxonomy.
#     The frozen `privacy_level` is ALWAYS preserved unchanged.
#   - `examples` (curated, additive)
#   - per-field `provenance`
#   - the `STUDY` space, which exists in NEITHER existing model
# ==========================================================


from __future__ import annotations


import copy


from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)


CONTRACT = "SpaceTypesV1"
VERSION = "1.0"


# ----------------------------------------------------------
# CURRICULUM CATEGORY VOCABULARY (PART 1)
# ----------------------------------------------------------

CATEGORY_PUBLIC = "PUBLIC"
CATEGORY_SEMI_PUBLIC = "SEMI_PUBLIC"
CATEGORY_PRIVATE = "PRIVATE"
CATEGORY_SERVICE = "SERVICE"
CATEGORY_CIRCULATION = "CIRCULATION"
CATEGORY_EXTERNAL = "EXTERNAL"

ALL_CATEGORIES = (
    CATEGORY_PUBLIC,
    CATEGORY_SEMI_PUBLIC,
    CATEGORY_PRIVATE,
    CATEGORY_SERVICE,
    CATEGORY_CIRCULATION,
    CATEGORY_EXTERNAL,
)


CATEGORY_DISPLAY = {
    CATEGORY_PUBLIC: {
        "fa": "\u0639\u0645\u0648\u0645\u06cc", "en": "public",
    },
    CATEGORY_SEMI_PUBLIC: {
        "fa": "\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc",
        "en": "semi-public",
    },
    CATEGORY_PRIVATE: {
        "fa": "\u062e\u0635\u0648\u0635\u06cc", "en": "private",
    },
    CATEGORY_SERVICE: {
        "fa": "\u062e\u062f\u0645\u0627\u062a\u06cc", "en": "service",
    },
    CATEGORY_CIRCULATION: {
        "fa": "\u06af\u0631\u062f\u0634", "en": "circulation",
    },
    CATEGORY_EXTERNAL: {
        "fa": "\u0628\u06cc\u0631\u0648\u0646\u06cc", "en": "external",
    },
}


def category_display(category, language="en"):

    entry = CATEGORY_DISPLAY.get(category) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(category)


# ----------------------------------------------------------
# DETERMINISTIC CATEGORY DERIVATION
#
# Rule (documented, no guessing):
#   ENVIRONMENTAL privacy            -> EXTERNAL
#   PUBLIC privacy                   -> PUBLIC
#   SEMI_PUBLIC privacy              -> SEMI_PUBLIC
#   PRIVATE privacy                  -> PRIVATE
#   SERVICE privacy                  -> SERVICE
#   TRANSITION / COMMON privacy      -> CIRCULATION
#                                        (SERVICE when the circulation
#                                         role is a VEHICLE role)
# ----------------------------------------------------------

_CATEGORY_BY_PRIVACY = {
    "ENVIRONMENTAL": CATEGORY_EXTERNAL,
    "PUBLIC": CATEGORY_PUBLIC,
    "SEMI_PUBLIC": CATEGORY_SEMI_PUBLIC,
    "PRIVATE": CATEGORY_PRIVATE,
    "SERVICE": CATEGORY_SERVICE,
    "TRANSITION": CATEGORY_CIRCULATION,
    "COMMON": CATEGORY_CIRCULATION,
}


# ----------------------------------------------------------
# CATEGORY OVERLAY (CURRICULUM)
#
# The curriculum taxonomy is a FUNCTIONAL/SOCIAL reading; the frozen
# `privacy_class` is an architectural one. They legitimately differ for
# a few spaces. Where the curriculum reading is explicit it is applied
# here and marked as an overlay; `privacy_level` is never altered.
# ----------------------------------------------------------

CATEGORY_OVERLAY = {
    # The curriculum treats the dwelling entrance as a public arrival
    # zone (Part 1: "Public: Entrance").
    "UNIT_ENTRY": CATEGORY_PUBLIC,
    "COMMON_ENTRANCE": CATEGORY_PUBLIC,
    # Kitchens are semi-public family space in the curriculum reading
    # (Part 1: "Semi Public: Kitchen"). Frozen privacy stays SERVICE.
    "OPEN_KITCHEN": CATEGORY_SEMI_PUBLIC,
    "CLOSED_KITCHEN": CATEGORY_SEMI_PUBLIC,
    # Bathrooms/laundry/storage are SERVICE in the curriculum reading
    # (Part 1: "Service: Bathroom, Laundry, Storage").
    "FAMILY_BATHROOM": CATEGORY_SERVICE,
    "ENSUITE": CATEGORY_SERVICE,
    "SEPARATE_WC": CATEGORY_SERVICE,
    # Outdoor living surfaces are EXTERNAL in the curriculum reading
    # (Part 1: "External: Yard, Terrace, Balcony").
    "TERRACE_BALCONY": CATEGORY_EXTERNAL,
}


# ----------------------------------------------------------
# CURRICULUM OVERLAY SPACES
#
# Spaces the brief requires that exist in NEITHER existing model.
# ----------------------------------------------------------

OVERLAY_SPACES = {
    "STUDY": {
        "names": {
            "fa": "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631 / \u0645\u0637\u0627\u0644\u0639\u0647",
            "en": "Study",
        },
        "aliases": [
            "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631",  # اتاق کار
            "\u0645\u0637\u0627\u0644\u0639\u0647",        # مطالعه
            "\u062f\u0641\u062a\u0631 \u062e\u0627\u0646\u06af\u06cc",  # دفتر خانگی
            "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631\u06cc",  # اتاق کاری
            "study",
            "home office",
            "study room",
        ],
        "functional_definition": (
            "\u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc "
            "\u0628\u0631\u0627\u06cc \u06a9\u0627\u0631\u060c "
            "\u0645\u0637\u0627\u0644\u0639\u0647 \u0648 "
            "\u062a\u0645\u0631\u06a9\u0632"
        ),
        "primary_function": (
            "\u06a9\u0627\u0631 \u0648 \u0645\u0637\u0627\u0644\u0639\u0647"
        ),
        "privacy_class": "PRIVATE",
        "circulation_role": "DESTINATION_PASS_THROUGH_FORBIDDEN",
        "typical_direct_connections": ["PRIVATE_HALL_CORRIDOR"],
        "forbidden_or_low_quality_connections": [
            "LIVING_RECEPTION", "UNIT_ENTRY",
        ],
        "access": ["private"],
        "zone": "private",
        "examples": [
            "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631 \u06a9\u0646\u0627\u0631 "
            "\u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc",
            "\u0645\u0637\u0627\u0644\u0639\u0647\u0654 \u062f\u0648\u0631 "
            "\u0627\u0632 \u0639\u0631\u0635\u0647\u0654 "
            "\u0639\u0645\u0648\u0645\u06cc",
        ],
    },
}


# ----------------------------------------------------------
# CURATED EXAMPLES (additive)
#
# Short, concrete design examples per space. Only for spaces where a
# useful example is genuinely known; absent means "no example recorded"
# rather than an invented one.
# ----------------------------------------------------------

EXAMPLES = {
    "UNIT_ENTRY": [
        "\u0648\u0631\u0648\u062f\u06cc \u0628\u0627 \u062c\u0627\u06a9\u062a\u200c\u0622\u0648\u06cc\u0632 \u0648 \u0645\u062f\u0631\u06a9\u0654 \u0627\u0645\u0646\u06cc\u062a\u06cc",
    ],
    "FOYER_SHOE_OFF": [
        "\u0647\u0634\u062a\u06cc \u0628\u0627 \u06a9\u0641\u0634\u200c\u06a9\u0646 \u0648 \u06a9\u0645\u062f \u0631\u0648\u067e\u0648\u0634",
    ],
    "LIVING_RECEPTION": [
        "\u0646\u0634\u06cc\u0645\u0646 \u0628\u0627 \u0646\u0648\u0631 \u062c\u0646\u0648\u0628\u06cc \u0648 \u062f\u0633\u062a\u0631\u0633\u06cc \u0628\u0647 \u062a\u0631\u0627\u0633",
    ],
    "GENERAL_HALL": [
        "\u0647\u0627\u0644 \u062e\u0627\u0646\u0648\u0627\u062f\u06af\u06cc \u0628\u0627 \u062f\u0633\u062a\u0631\u0633\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647",
    ],
    "DINING": [
        "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0645\u062c\u0627\u0648\u0631 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627 \u0645\u06cc\u0632 \u062c\u0647\u062a\u200c\u062f\u0627\u0631",
    ],
    "OPEN_KITCHEN": [
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u0632 \u0628\u0627 \u062c\u0632\u06cc\u0631\u0647 \u0648 \u0645\u06cc\u0632 \u0635\u0628\u062d\u0627\u0646\u0647\u200c\u062e\u0648\u0631\u06cc",
    ],
    "CLOSED_KITCHEN": [
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0633\u062a\u0647 \u0628\u0627 \u062f\u0631 \u0634\u06cc\u0634\u0647\u200c\u0627\u06cc \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc",
    ],
    "BEDROOM_SINGLE": [
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u06cc\u06a9\u200c\u0646\u0641\u0631\u0647 \u062f\u0631 \u0627\u0646\u062a\u0647\u0627\u06cc \u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc",
    ],
    "BEDROOM_DOUBLE": [
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u062f\u0648\u0646\u0641\u0631\u0647 \u062f\u0648\u0631 \u0627\u0632 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
    ],
    "MASTER_BEDROOM_SLEEPING": [
        "\u0628\u062e\u0634 \u062e\u0648\u0627\u0628 \u0645\u0633\u062a\u0631 \u0628\u0627 \u0631\u062e\u062a\u06a9\u0646 \u0648 \u062d\u0645\u0627\u0645 \u0645\u0633\u062a\u0631",
    ],
    "ENSUITE": [
        "\u062d\u0645\u0627\u0645 \u0645\u0633\u062a\u0631 \u0641\u0642\u0637 \u0627\u0632 \u0637\u0631\u06cc\u0642 \u0631\u062e\u062a\u06a9\u0646",
    ],
    "FAMILY_BATHROOM": [
        "\u062d\u0645\u0627\u0645 \u062e\u0627\u0646\u0648\u0627\u062f\u06af\u06cc \u0628\u0627 \u062f\u0633\u062a\u0631\u0633\u06cc \u0627\u0632 \u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc",
    ],
    "GUEST_WC": [
        "\u0633\u0631\u0648\u06cc\u0633 \u0645\u0647\u0645\u0627\u0646 \u0646\u0632\u062f\u06cc\u06a9 \u0647\u0634\u062a\u06cc \u0648 \u062f\u0648\u0631 \u0627\u0632 \u0639\u0631\u0635\u0647\u0654 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc",
    ],
    "LAUNDRY_UTILITY": [
        "\u0631\u062e\u062a\u0634\u0648\u06cc\u062e\u0627\u0646\u0647 \u062f\u0631 \u0645\u0633\u06cc\u0631 \u062e\u062f\u0645\u0627\u062a\u06cc",
    ],
    "STORAGE_LINEN": [
        "\u0627\u0646\u0628\u0627\u0631\u06cc \u062f\u0631 \u0627\u0646\u062a\u0647\u0627\u06cc \u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc",
    ],
    "PRIVATE_HALL_CORRIDOR": [
        "\u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc \u06a9\u0647 \u0627\u062a\u0627\u0642\u200c\u0647\u0627\u0631\u0627 \u0633\u0631\u0648\u06cc\u0633 \u0645\u06cc\u200c\u06a9\u0646\u062f",
    ],
    "TERRACE_BALCONY": [
        "\u062a\u0631\u0627\u0633 \u0645\u062a\u0635\u0644 \u0628\u0647 \u0646\u0634\u06cc\u0645\u0646 \u0628\u0627 \u0627\u0631\u062a\u0628\u0627\u0637 \u062a\u0639\u0627\u0645\u0644\u06cc",
    ],
    "PRIVATE_YARD": [
        "\u062d\u06cc\u0627\u0637 \u062e\u0635\u0648\u0635\u06cc \u067e\u0634\u062a \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
    ],
    "COURTYARD": [
        "\u062d\u06cc\u0627\u0637 \u0645\u06cc\u0627\u0646\u200c\u0633\u0631\u0627 \u0628\u0627 \u062f\u0633\u062a\u0631\u0633\u06cc \u0627\u0632 \u0646\u0634\u06cc\u0645\u0646 \u0648 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc",
    ],
    "STAIR": [
        "\u067e\u0644\u0647 \u062f\u0631 \u067e\u0627\u06af\u0631\u062f \u0645\u0634\u062a\u0631\u06a9 \u0628\u0627 \u0646\u0648\u0631 \u0637\u0628\u06cc\u0639\u06cc",
    ],
    "ELEVATOR": [
        "\u0622\u0633\u0627\u0646\u0633\u0648\u0631 \u062f\u0631 \u0644\u0627\u0628\u06cc \u062f\u0633\u062a\u0631\u0633\u06cc",
    ],
    "LOBBY": [
        "\u0644\u0627\u0628\u06cc \u0628\u0627 \u0646\u0638\u0627\u0631\u062a \u0648 \u062f\u0633\u062a\u0631\u0633\u06cc \u0628\u0647 \u067e\u0644\u0647 \u0648 \u0622\u0633\u0627\u0646\u0633\u0648\u0631",
    ],
    "PARKING_BAY": [
        "\u062c\u0627\u06cc \u067e\u0627\u0631\u06a9 \u062f\u0631 \u067e\u06cc\u0644\u0648\u062a\u06cc \u0628\u0627 \u062f\u0633\u062a\u0631\u0633\u06cc \u067e\u06cc\u0627\u062f\u0647 \u062c\u062f\u0627\u06af\u0627\u0646\u0647",
    ],
    "COMMERCIAL_SHOP": [
        "\u0648\u0627\u062d\u062f \u062a\u062c\u0627\u0631\u06cc \u0628\u0627 \u0648\u06cc\u062a\u0631\u06cc\u0646 \u0628\u0647 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
    ],
    "STUDY": [
        "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631 \u06a9\u0646\u0627\u0631 \u0631\u0627\u0647\u0631\u0648 \u062e\u0635\u0648\u0635\u06cc",
        "\u0645\u0637\u0627\u0644\u0639\u0647\u0654 \u062f\u0648\u0631 \u0627\u0632 \u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
    ],
}


# ----------------------------------------------------------
# PREFERRED TERMS
#
# Both existing models contain a kitchen/bedroom/terrace. When a user
# says the bare term we must resolve to the RICHER residential record
# (SPACE_SPECS), not the flatter ontology record. This table is applied
# LAST and WINS. The ontology records stay reachable by their own ids
# and synonyms — nothing is removed.
# ----------------------------------------------------------

PREFERRED_TERM = {
    # Persian
    "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647": "OPEN_KITCHEN",
    "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628": "BEDROOM_DOUBLE",
    "\u062e\u0648\u0627\u0628": "BEDROOM_DOUBLE",
    "\u0646\u0634\u06cc\u0645\u0646": "LIVING_RECEPTION",
    "\u067e\u0630\u06cc\u0631\u0627\u06cc\u06cc": "LIVING_RECEPTION",
    "\u0648\u0631\u0648\u062f\u06cc": "UNIT_ENTRY",
    "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc": "DINING",
    "\u0646\u0627\u0647\u0627\u0631\u062e\u0648\u0631\u06cc": "DINING",
    "\u062d\u0645\u0627\u0645": "FAMILY_BATHROOM",
    "\u0631\u0627\u0647\u0631\u0648": "PRIVATE_HALL_CORRIDOR",
    "\u0631\u0627\u0647 \u067e\u0644\u0647": "STAIR",
    "\u067e\u0644\u0647": "STAIR",
    "\u062a\u0631\u0627\u0633": "TERRACE_BALCONY",
    "\u0628\u0627\u0644\u06a9\u0646": "TERRACE_BALCONY",
    "\u062d\u06cc\u0627\u0637": "PRIVATE_YARD",
    "\u0647\u0627\u0644 \u062e\u0627\u0646\u0648\u0627\u062f\u06af\u06cc": "FAMILY_HALL",
    "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0645\u0633\u062a\u0631": "MASTER_BEDROOM_SLEEPING",
    # CORRECTION_LOOP_01 — the teacher's own SHORT forms. The write path
    # (a teaching statement) and the read path (a question) must resolve
    # the same words to the same space id, or a recorded lesson can never
    # be retrieved. "اتاق خواب مستر" alone was not enough: the user says
    # "اتاق مستر" and, defining it, "اتاق والدین".
    "\u0627\u062a\u0627\u0642 \u0645\u0633\u062a\u0631": "MASTER_BEDROOM_SLEEPING",
    "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0648\u0627\u0644\u062f\u06cc\u0646": "MASTER_BEDROOM_SLEEPING",
    "\u0627\u062a\u0627\u0642 \u0648\u0627\u0644\u062f\u06cc\u0646": "MASTER_BEDROOM_SLEEPING",
    "\u0627\u0646\u0628\u0627\u0631\u06cc": "STORAGE_LINEN",
    "\u0631\u062e\u062a\u0634\u0648\u06cc\u062e\u0627\u0646\u0647": "LAUNDRY_UTILITY",
    # English
    "kitchen": "OPEN_KITCHEN",
    "bedroom": "BEDROOM_DOUBLE",
    "living": "LIVING_RECEPTION",
    "living room": "LIVING_RECEPTION",
    "entrance": "UNIT_ENTRY",
    "dining": "DINING",
    "dining room": "DINING",
    "bathroom": "FAMILY_BATHROOM",
    "corridor": "PRIVATE_HALL_CORRIDOR",
    "stair": "STAIR",
    "stairs": "STAIR",
    "staircase": "STAIR",
    "terrace": "TERRACE_BALCONY",
    "balcony": "TERRACE_BALCONY",
    "yard": "PRIVATE_YARD",
    "family room": "FAMILY_HALL",
    "master bedroom": "MASTER_BEDROOM_SLEEPING",
    # CORRECTION_LOOP_01 — see the Persian short forms above.
    "master room": "MASTER_BEDROOM_SLEEPING",
    "parents room": "MASTER_BEDROOM_SLEEPING",
    "storage": "STORAGE_LINEN",
    "laundry": "LAUNDRY_UTILITY",
}


# ----------------------------------------------------------
# DEFAULT ZONE / ACCESS FALLBACKS
# ----------------------------------------------------------

_ZONE_BY_CATEGORY = {
    CATEGORY_PUBLIC: "public",
    CATEGORY_SEMI_PUBLIC: "semi_public",
    CATEGORY_PRIVATE: "private",
    CATEGORY_SERVICE: "service",
    CATEGORY_CIRCULATION: "circulation",
    CATEGORY_EXTERNAL: "external",
}


class SpaceTypeRegistryV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, read_bridge=None):

        self.read_bridge = read_bridge or knowledge_read_bridge

        self._records = None

        self._index = None

        print(
            "\U0001f4d0 SPACE TYPES v1.0 ONLINE "
            "(adapter over the existing corpus)"
        )

    # ======================================================
    # BUILD (lazy, cached, read-only)
    # ======================================================

    def _space_specs(self):

        payload = self.read_bridge.space_knowledge() or {}

        return payload.get("space_specs") or {}

    def _ontology_spaces(self):

        return self.read_bridge.spaces() or {}

    def _build(self):

        if self._records is not None:

            return self._records

        specs = self._space_specs()

        ontology = self._ontology_spaces()

        records = {}

        # ---- 1. residential specs (richest source) ----
        for space_id, spec in specs.items():

            records[space_id] = self._from_spec(space_id, spec, ontology)

        # ---- 2. ontology-only spaces ----
        for space_id, entry in ontology.items():

            if space_id in records:

                # keep the residential record, but merge ontology
                # synonyms so both vocabularies resolve
                extra = entry.get("synonyms") or []

                existing = records[space_id]["aliases"]

                for synonym in extra:

                    if synonym not in existing:

                        existing.append(synonym)

                continue

            records[space_id] = self._from_ontology(space_id, entry)

        # ---- 3. curriculum overlay spaces ----
        for space_id, overlay in OVERLAY_SPACES.items():

            if space_id in records:

                continue

            records[space_id] = self._from_overlay(space_id, overlay)

        self._records = records

        self._index = self._build_index(records)

        return records

    # ------------------------------------------------------

    def _from_spec(self, space_id, spec, ontology):

        privacy = spec.get("privacy_class") or "SERVICE"

        role = spec.get("circulation_role") or ""

        category, category_source = self._category(
            space_id, privacy, role
        )

        names = spec.get("names") or {}

        ontology_entry = ontology.get(space_id) or {}

        aliases = list(names.get("fa") and [names["fa"]] or [])

        if names.get("en"):

            aliases.append(names["en"])

        aliases.append(space_id.replace("_", " ").lower())

        for synonym in ontology_entry.get("synonyms") or []:

            if synonym not in aliases:

                aliases.append(synonym)

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "space_id": space_id,

            "name": {
                "fa": names.get("fa") or space_id,
                "en": names.get("en") or space_id.replace("_", " ").title(),
            },

            "aliases": [a for a in aliases if a],

            # ---- curriculum taxonomy (PART 1) ----
            "category": category,
            "category_source": category_source,

            # ---- existing architectural taxonomy (UNCHANGED) ----
            "privacy_level": privacy,
            "circulation_role": role,

            "zone": (
                ontology_entry.get("zone")
                or _ZONE_BY_CATEGORY.get(category)
            ),

            "functional_role": spec.get("primary_function"),
            "functional_definition": spec.get("functional_definition"),

            "typical_adjacent": list(
                spec.get("typical_direct_connections") or []
            ),
            "discouraged_adjacent": list(
                spec.get("forbidden_or_low_quality_connections") or []
            ),

            "access_requirements": {
                "requires_enclosure": spec.get("requires_enclosure"),
                "requires_door": spec.get("requires_door"),
                "door_optional": spec.get("door_optional"),
                "open_connection_allowed": spec.get(
                    "open_connection_allowed"
                ),
                "may_be_open_plan": spec.get("may_be_open_plan"),
                "can_be_transit_node": spec.get("can_be_transit_node"),
                "access": list(ontology_entry.get("access") or []),
            },

            "examples": list(EXAMPLES.get(space_id) or []),

            "wet_zone": spec.get("wet_zone"),
            "acoustic_privacy_sensitivity": spec.get(
                "acoustic_privacy_sensitivity"
            ),
            "daylight_requirement": spec.get("daylight_requirement"),
            "area_requirements": spec.get("area_requirements"),
            "special_validation_rules": list(
                spec.get("special_validation_rules") or []
            ),

            "provenance": {
                "names": "SPACE_SPECS",
                "category": category_source,
                "privacy_level": "SPACE_SPECS",
                "circulation_role": "SPACE_SPECS",
                "functional_role": "SPACE_SPECS",
                "typical_adjacent": "SPACE_SPECS",
                "discouraged_adjacent": "SPACE_SPECS",
                "access_requirements": "SPACE_SPECS",
                "examples": (
                    "CURRICULUM_OVERLAY"
                    if EXAMPLES.get(space_id) else None
                ),
                "zone": (
                    "ONTOLOGY" if ontology_entry.get("zone")
                    else "DERIVED_FROM_CATEGORY"
                ),
            },

            "sources": [
                "core/architecture/knowledge/"
                "architectural_space_knowledge_v1.py",
                *(
                    ["core/knowledge/architectural_ontology.json"]
                    if ontology_entry else []
                ),
            ],

            "origin": "SPACE_SPECS",
        }

    # ------------------------------------------------------

    def _from_ontology(self, space_id, entry):

        privacy = _PRIVACY_BY_ZONE.get(
            entry.get("zone"), "SERVICE"
        )

        category, category_source = self._category(
            space_id, privacy, entry.get("space_type") or ""
        )

        aliases = list(entry.get("synonyms") or [])

        aliases.append(space_id.replace("_", " ").lower())

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "space_id": space_id,

            "name": {
                "fa": next(
                    (
                        s for s in (entry.get("synonyms") or [])
                        if _has_persian(s)
                    ),
                    space_id,
                ),
                "en": space_id.replace("_", " ").title(),
            },

            "aliases": [a for a in aliases if a],

            "category": category,
            "category_source": category_source,

            "privacy_level": privacy,
            "circulation_role": entry.get("space_type"),

            "zone": entry.get("zone"),

            "functional_role": entry.get("space_type"),
            "functional_definition": None,

            "typical_adjacent": list(entry.get("adjacent_to") or []),
            "discouraged_adjacent": [],

            "access_requirements": {
                "access": list(entry.get("access") or []),
            },

            "examples": list(EXAMPLES.get(space_id) or []),

            "provenance": {
                "names": "ONTOLOGY",
                "category": category_source,
                "privacy_level": "DERIVED_FROM_ZONE",
                "typical_adjacent": "ONTOLOGY",
                "discouraged_adjacent": None,
                "examples": (
                    "CURRICULUM_OVERLAY"
                    if EXAMPLES.get(space_id) else None
                ),
                "zone": "ONTOLOGY",
            },

            "sources": ["core/knowledge/architectural_ontology.json"],

            "origin": "ONTOLOGY",
        }

    # ------------------------------------------------------

    def _from_overlay(self, space_id, overlay):

        category, category_source = self._category(
            space_id,
            overlay.get("privacy_class") or "PRIVATE",
            overlay.get("circulation_role") or "",
        )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "space_id": space_id,

            "name": dict(overlay.get("names") or {}),

            "aliases": list(overlay.get("aliases") or []),

            "category": category,
            "category_source": category_source,

            "privacy_level": overlay.get("privacy_class"),
            "circulation_role": overlay.get("circulation_role"),

            "zone": overlay.get("zone"),

            "functional_role": overlay.get("primary_function"),
            "functional_definition": overlay.get(
                "functional_definition"
            ),

            "typical_adjacent": list(
                overlay.get("typical_direct_connections") or []
            ),
            "discouraged_adjacent": list(
                overlay.get("forbidden_or_low_quality_connections") or []
            ),

            "access_requirements": {
                "access": list(overlay.get("access") or []),
            },

            "examples": list(
                overlay.get("examples") or EXAMPLES.get(space_id) or []
            ),

            "provenance": {
                "names": "CURRICULUM_OVERLAY",
                "category": category_source,
                "privacy_level": "CURRICULUM_OVERLAY",
                "typical_adjacent": "CURRICULUM_OVERLAY",
                "discouraged_adjacent": "CURRICULUM_OVERLAY",
                "examples": "CURRICULUM_OVERLAY",
            },

            "sources": ["core/curriculum/space_types_v1.py"],

            "origin": "CURRICULUM_OVERLAY",
        }

    # ------------------------------------------------------

    def _category(self, space_id, privacy, role):

        if space_id in CATEGORY_OVERLAY:

            return CATEGORY_OVERLAY[space_id], "CURRICULUM_OVERLAY"

        category = _CATEGORY_BY_PRIVACY.get(privacy)

        if category is None:

            return CATEGORY_SERVICE, "DERIVED_FROM_PRIVACY_CLASS"

        if (
            category == CATEGORY_CIRCULATION
            and "VEHICLE" in str(role or "")
        ):

            return CATEGORY_SERVICE, "DERIVED_FROM_CIRCULATION_ROLE"

        return category, "DERIVED_FROM_PRIVACY_CLASS"

    # ------------------------------------------------------

    def _build_index(self, records):

        index = {}

        for space_id, record in records.items():

            keys = {space_id.lower(), space_id.replace("_", " ").lower()}

            for alias in record.get("aliases") or []:

                keys.add(_normalize(alias))

            for name in (record.get("name") or {}).values():

                if name:

                    keys.add(_normalize(name))

            for key in keys:

                if key and key not in index:

                    index[key] = space_id

        # ---- preferred terms WIN (applied last) ----
        for term, space_id in PREFERRED_TERM.items():

            if space_id in records:

                index[_normalize(term)] = space_id

        return index

    # ======================================================
    # READ API
    # ======================================================

    def spaces(self):

        return copy.deepcopy(self._build())

    def space(self, space_id):

        return copy.deepcopy(self._build().get(space_id))

    def count(self):

        return len(self._build())

    def by_category(self, category):

        return copy.deepcopy(
            {
                space_id: record
                for space_id, record in self._build().items()
                if record.get("category") == category
            }
        )

    def by_privacy(self, privacy):

        return copy.deepcopy(
            {
                space_id: record
                for space_id, record in self._build().items()
                if record.get("privacy_level") == privacy
            }
        )

    def find(self, term, language=None):

        """Resolve a fa/en term to a space id."""

        if not term:

            return None

        self._build()

        return self._index.get(_normalize(term))

    def resolve(self, term, language=None):

        space_id = self.find(term, language=language)

        return self.space(space_id) if space_id else None

    def categories(self):

        return list(ALL_CATEGORIES)

    def report(self):

        records = self._build()

        by_category = {}

        by_origin = {}

        for record in records.values():

            by_category[record["category"]] = (
                by_category.get(record["category"], 0) + 1
            )

            by_origin[record["origin"]] = (
                by_origin.get(record["origin"], 0) + 1
            )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "space_count": len(records),

            "by_category": by_category,

            "by_origin": by_origin,

            "categories": list(ALL_CATEGORIES),

            "overlay_spaces": sorted(OVERLAY_SPACES.keys()),

            "category_overlay": dict(CATEGORY_OVERLAY),

            "spaces_with_examples": len(
                [r for r in records.values() if r.get("examples")]
            ),

            "source_corpus": [
                "core/architecture/knowledge/"
                "architectural_space_knowledge_v1.py (SPACE_SPECS)",
                "core/knowledge/architectural_ontology.json",
            ],
        }


# ----------------------------------------------------------
# HELPERS
# ----------------------------------------------------------

_PRIVACY_BY_ZONE = {
    "public": "PUBLIC",
    "semi_public": "SEMI_PUBLIC",
    "private": "PRIVATE",
    "service": "SERVICE",
    "circulation": "TRANSITION",
    "commercial": "PUBLIC",
    "external": "ENVIRONMENTAL",
    "performance": "PUBLIC",
}


def _has_persian(value):

    for char in str(value or ""):

        if "\u0600" <= char <= "\u06FF":

            return True

    return False


def _normalize(value):

    text = str(value or "").strip().lower()

    text = text.replace("\u200c", " ")

    for source, target in (
        ("\u064a", "\u06cc"),
        ("\u0643", "\u06a9"),
        ("\u0629", "\u0647"),
    ):

        text = text.replace(source, target)

    while "  " in text:

        text = text.replace("  ", " ")

    return text


space_types = SpaceTypeRegistryV1()
