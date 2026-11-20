# ==========================================================
# ArchitectOS Privacy Logic v1
#
# PHASE 10 — PART 3 — PRIVACY LOGIC
#
# Architectural privacy reasoning over the space-type model and the
# graded adjacency model.
#
# Band basis
#   Privacy reasoning uses the CURRICULUM category band, because the
#   curriculum reading is the one the teacher is being taught against:
#
#     PUBLIC 0   SEMI_PUBLIC 1   PRIVATE 2   SERVICE 2
#     CIRCULATION 0   EXTERNAL 0
#
#   The frozen architectural `privacy_level` is preserved unchanged in
#   every space record and is still reported, but it is not the band
#   used here. (Otherwise an open kitchen would read as SERVICE=2 and
#   "kitchen can connect to living" would be wrongly refused.)
#
# Answers the Part 3 questions:
#   "Bedroom should not open directly to entrance"
#   "Kitchen can connect to living"
#   "Bathroom requires controlled access"
# ==========================================================


from __future__ import annotations


from core.curriculum.space_types_v1 import (
    space_types,
    CATEGORY_PUBLIC,
    CATEGORY_SEMI_PUBLIC,
    CATEGORY_PRIVATE,
    CATEGORY_SERVICE,
    CATEGORY_CIRCULATION,
    CATEGORY_EXTERNAL,
    category_display,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
)


CONTRACT = "PrivacyLogicV1"
VERSION = "1.0"


# ----------------------------------------------------------
# CURRICULUM PRIVACY BANDS
# ----------------------------------------------------------

BAND_PUBLIC = 0
BAND_SEMI_PUBLIC = 1
BAND_PRIVATE = 2

BAND_BY_CATEGORY = {
    CATEGORY_PUBLIC: BAND_PUBLIC,
    CATEGORY_CIRCULATION: BAND_PUBLIC,
    CATEGORY_EXTERNAL: BAND_PUBLIC,
    CATEGORY_SEMI_PUBLIC: BAND_SEMI_PUBLIC,
    CATEGORY_PRIVATE: BAND_PRIVATE,
    CATEGORY_SERVICE: BAND_PRIVATE,
}


# ----------------------------------------------------------
# BAND OVERRIDE
#
# The private hall is PRIVATE-SIDE circulation: it exists to serve
# bedrooms and bathrooms. Treating it as a public field (the default
# for circulation) would wrongly forbid a bedroom opening onto it.
# ----------------------------------------------------------

BAND_OVERRIDE = {
    "PRIVATE_HALL_CORRIDOR": BAND_PRIVATE,
    "FAMILY_HALL": BAND_SEMI_PUBLIC,
    "GENERAL_HALL": BAND_SEMI_PUBLIC,
}


BAND_NAMES = {
    BAND_PUBLIC: {
        "fa": "\u0639\u0631\u0635\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
        "en": "public field",
    },
    BAND_SEMI_PUBLIC: {
        "fa": "\u0639\u0631\u0635\u0647\u0654 \u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc",
        "en": "semi-public field",
    },
    BAND_PRIVATE: {
        "fa": "\u0639\u0631\u0635\u0647\u0654 \u062e\u0635\u0648\u0635\u06cc",
        "en": "private field",
    },
}


# Spaces that require a controlled (mediated) access regardless of band.
_CONTROLLED_ACCESS_RULES = (
    "CONTROLLED",
    "COMMON_TO_PRIVATE_ENTRY_ONLY",
    "PRIVATE_ENTRY_ONLY",
)


class PrivacyLogicV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, adjacency=None):

        self.registry = registry or space_types

        self.adjacency = adjacency or adjacency_model

        print(
            "\U0001f510 PRIVACY LOGIC v1.0 ONLINE "
            "(public / semi-public / private bands)"
        )

    # ======================================================
    # BANDS
    # ======================================================

    def band(self, space_id):

        record = self.registry.space(space_id)

        if not record:

            return None

        if space_id in BAND_OVERRIDE:

            return BAND_OVERRIDE[space_id]

        return BAND_BY_CATEGORY.get(record.get("category"))

    def band_name(self, space_id, language="en"):

        value = self.band(space_id)

        entry = BAND_NAMES.get(value) or {}

        return entry.get(
            "fa" if str(language or "").startswith("fa") else "en"
        ) or str(value)

    def privacy_relation(self, source, target):

        band_a = self.band(source)

        band_b = self.band(target)

        if band_a is None or band_b is None:

            return None

        gap = abs(band_a - band_b)

        if gap == 0:

            return "SAME_BAND"

        if gap == 1:

            return "ADJACENT_BAND"

        return "CONFLICT"

    # ======================================================
    # CONTROLLED ACCESS
    # ======================================================

    def requires_controlled_access(self, space_id):

        record = self.registry.space(space_id)

        if not record:

            return {
                "space_id": space_id,
                "required": None,
                "reasons": ["unknown_space"],
            }

        access = record.get("access_requirements") or {}

        category = record.get("category")

        open_ok = bool(access.get("open_connection_allowed"))

        door_required = access.get("requires_door") == "REQUIRED"

        reasons = []

        required = False

        # A private or service space is always mediated: you do not walk
        # into it straight off a public field.
        if category == CATEGORY_SERVICE:

            required = True

            reasons.append("service space")

        elif category == CATEGORY_PRIVATE:

            required = True

            reasons.append("private space")

        # A required door only forces mediation when the space is NOT
        # allowed to be open plan (otherwise an open kitchen would be
        # wrongly treated as closed).
        if door_required and not open_ok:

            required = True

            reasons.append("a door is required and open plan is not allowed")

        if access.get("requires_enclosure") == "REQUIRED" and not open_ok:

            required = True

            reasons.append("enclosure is required")

        if (
            record.get("wet_zone")
            and category in (CATEGORY_SERVICE, CATEGORY_PRIVATE)
        ):

            reasons.append("wet zone")

        for rule in record.get("special_validation_rules") or []:

            if any(token in str(rule) for token in _CONTROLLED_ACCESS_RULES):

                required = True

                reasons.append("rule: " + str(rule))

        return {
            "space_id": space_id,
            "required": required,
            "reasons": reasons,
        }

    # ======================================================
    # DIRECT OPEN CONNECTION
    # ======================================================

    def direct_open_connection_allowed(self, source, target):

        record = self.adjacency.relation(source, target)

        if not record:

            return {
                "allowed": None,
                "relation_type": None,
                "reasons": ["no relation recorded"],
            }

        relation_type = record["relation_type"]

        reasons = [relation_type]

        if relation_type == REL_FORBIDDEN:

            return {
                "allowed": False,
                "relation_type": relation_type,
                "reasons": reasons + [
                    "forbidden connection: a direct opening is not permitted"
                ],
            }

        if relation_type == REL_AVOID:

            return {
                "allowed": False,
                "relation_type": relation_type,
                "reasons": reasons + [
                    "avoid connection: only a buffered route is acceptable"
                ],
            }

        if relation_type == REL_WEAK:

            return {
                "allowed": False,
                "relation_type": relation_type,
                "reasons": reasons + [
                    "weak connection: a direct opening is not appropriate"
                ],
            }

        privacy = self.privacy_relation(source, target)

        if privacy == "CONFLICT":

            return {
                "allowed": False,
                "relation_type": relation_type,
                "reasons": reasons + [
                    "privacy bands conflict"
                ],
            }

        control_a = self.requires_controlled_access(source)

        control_b = self.requires_controlled_access(target)

        # A controlled space may still connect, but only through a
        # mediated opening (door), which the caller must respect.
        mediated = bool(control_a["required"] or control_b["required"])

        return {
            "allowed": True,
            "relation_type": relation_type,
            "mediated": mediated,
            "reasons": reasons + (
                ["allowed, but the opening must be mediated (door)"]
                if mediated else ["allowed as an open connection"]
            ),
        }

    # ======================================================
    # SEPARATION
    # ======================================================

    def separation_required(self, source, target):

        record = self.adjacency.relation(source, target)

        if not record:

            return {
                "required": None,
                "relation_type": None,
                "reasons": ["no relation recorded"],
            }

        relation_type = record["relation_type"]

        privacy = self.privacy_relation(source, target)

        required = relation_type in (REL_AVOID, REL_FORBIDDEN)

        reasons = [relation_type]

        if privacy == "CONFLICT":

            reasons.append("privacy bands conflict")

        if relation_type == REL_WEAK and privacy == "CONFLICT":

            required = True

            reasons.append(
                "weak connection across conflicting bands"
            )

        if required:

            reasons.append(record.get("reason") or "")

        return {
            "required": required,
            "relation_type": relation_type,
            "privacy_relation": privacy,
            "reasons": [r for r in reasons if r],
        }

    # ======================================================
    # PART 3 CANONICAL QUESTIONS
    # ======================================================

    def evaluate(self, source, target):

        """Full privacy verdict for one ordered pair."""

        a = self.registry.space(source) or {}

        b = self.registry.space(target) or {}

        return {

            "contract": CONTRACT + ".Evaluation",
            "version": VERSION,

            "source_space": source,
            "target_space": target,

            "source_category": a.get("category"),
            "target_category": b.get("category"),

            "source_band": self.band(source),
            "target_band": self.band(target),

            "privacy_relation": self.privacy_relation(source, target),

            "relation_type": self.adjacency.relation_type_of(
                source, target
            ),

            "controlled_access": {
                "source": self.requires_controlled_access(source),
                "target": self.requires_controlled_access(target),
            },

            "direct_open_connection": (
                self.direct_open_connection_allowed(source, target)
            ),

            "separation": self.separation_required(source, target),

            "deterministic": True,
            "llm_used": False,
        }

    # ------------------------------------------------------

    def report(self):

        records = self.registry.spaces()

        by_band = {}

        controlled = []

        for space_id, record in records.items():

            band = BAND_BY_CATEGORY.get(record.get("category"))

            by_band[band] = by_band.get(band, 0) + 1

            if self.requires_controlled_access(space_id)["required"]:

                controlled.append(space_id)

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "band_basis": "curriculum_category",

            "bands": {
                "PUBLIC": BAND_PUBLIC,
                "SEMI_PUBLIC": BAND_SEMI_PUBLIC,
                "PRIVATE": BAND_PRIVATE,
            },

            "spaces_by_band": by_band,

            "controlled_access_spaces": len(controlled),

            "categories": [
                category_display(c) for c in (
                    CATEGORY_PUBLIC,
                    CATEGORY_SEMI_PUBLIC,
                    CATEGORY_PRIVATE,
                    CATEGORY_SERVICE,
                    CATEGORY_CIRCULATION,
                    CATEGORY_EXTERNAL,
                )
            ],
        }


privacy_logic = PrivacyLogicV1()
