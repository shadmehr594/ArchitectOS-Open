# ==========================================================
# ArchitectOS Zone Model v1
#
# PHASE 11 — PART 3 — ZONE CREATION
#
# Six SEMANTIC zones. A zone is a reasoning grouping, never a shape:
# there are no coordinates, no polygons and no geometry anywhere here.
#
#   PUBLIC_ZONE       tends toward the access side
#   SEMI_PUBLIC_ZONE  sits between the public and the private field
#   PRIVATE_ZONE      requires separation, toward the protected side
#   SERVICE_ZONE      requires functional connection to what it serves
#   CIRCULATION_ZONE  connects the other zones
#   EXTERNAL_ZONE     sits on the open edge
#
# The zone of a space is derived 1:1 from the Phase 10 curriculum
# category, so Phase 10 remains the single source of truth for what a
# space IS. This module only adds the zone-level reasoning vocabulary.
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
)


CONTRACT = "ZoneModelV1"
VERSION = "1.0"


ZONE_PUBLIC = "PUBLIC_ZONE"
ZONE_SEMI_PUBLIC = "SEMI_PUBLIC_ZONE"
ZONE_PRIVATE = "PRIVATE_ZONE"
ZONE_SERVICE = "SERVICE_ZONE"
ZONE_CIRCULATION = "CIRCULATION_ZONE"
ZONE_EXTERNAL = "EXTERNAL_ZONE"


ALL_ZONES = (
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
)


# Phase 10 category -> Phase 11 zone (1:1, no interpretation)
ZONE_BY_CATEGORY = {
    CATEGORY_PUBLIC: ZONE_PUBLIC,
    CATEGORY_SEMI_PUBLIC: ZONE_SEMI_PUBLIC,
    CATEGORY_PRIVATE: ZONE_PRIVATE,
    CATEGORY_SERVICE: ZONE_SERVICE,
    CATEGORY_CIRCULATION: ZONE_CIRCULATION,
    CATEGORY_EXTERNAL: ZONE_EXTERNAL,
}


ZONE_DISPLAY = {
    ZONE_PUBLIC: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u0639\u0645\u0648\u0645\u06cc",
        "en": "public zone",
    },
    ZONE_SEMI_PUBLIC: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 "
              "\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc",
        "en": "semi-public zone",
    },
    ZONE_PRIVATE: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u062e\u0635\u0648\u0635\u06cc",
        "en": "private zone",
    },
    ZONE_SERVICE: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u062e\u062f\u0645\u0627\u062a\u06cc",
        "en": "service zone",
    },
    ZONE_CIRCULATION: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u06af\u0631\u062f\u0634",
        "en": "circulation zone",
    },
    ZONE_EXTERNAL: {
        "fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u0628\u06cc\u0631\u0648\u0646\u06cc",
        "en": "external zone",
    },
}


def zone_display(zone, language="en"):

    entry = ZONE_DISPLAY.get(zone) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(zone)


# ----------------------------------------------------------
# ZONE BEHAVIOUR (PART 3 reasoning)
#
# `access_affinity`  where the zone wants to sit relative to the site
#                    ACCESS edge:  +1 toward it, -1 away from it, 0 neutral
# `separation`       does the zone need to be separated from arrival
# `connects`         does the zone exist to connect others
# ----------------------------------------------------------

ZONE_BEHAVIOUR = {

    ZONE_PUBLIC: {
        "access_affinity": 1,
        "separation": False,
        "connects": False,
        "reason_en": "public spaces tend toward the access side",
        "reason_fa": "\u0641\u0636\u0627\u0647\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc "
                     "\u0628\u0647 \u0637\u0631\u0641 \u0636\u0644\u0639 "
                     "\u062f\u0633\u062a\u0631\u0633\u06cc \u0645\u06cc\u0644 "
                     "\u062f\u0627\u0631\u0646\u062f",
    },

    ZONE_SEMI_PUBLIC: {
        "access_affinity": 0,
        "separation": False,
        "connects": False,
        "reason_en": "semi-public spaces sit between the public and "
                     "private fields",
        "reason_fa": "\u0641\u0636\u0627\u0647\u0627\u06cc "
                     "\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc "
                     "\u0628\u06cc\u0646 \u0639\u0631\u0635\u0647\u0654 "
                     "\u0639\u0645\u0648\u0645\u06cc \u0648 \u062e\u0635\u0648\u0635\u06cc "
                     "\u0642\u0631\u0627\u0631 \u0645\u06cc\u200c\u06af\u06cc\u0631\u0646\u062f",
    },

    ZONE_PRIVATE: {
        "access_affinity": -1,
        "separation": True,
        "connects": False,
        "reason_en": "private spaces require separation and belong toward "
                     "the protected side",
        "reason_fa": "\u0641\u0636\u0627\u0647\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc "
                     "\u0628\u0647 \u062c\u062f\u0627\u06cc\u06cc \u0646\u06cc\u0627\u0632 "
                     "\u062f\u0627\u0631\u0646\u062f \u0648 \u0628\u0627\u06cc\u062f "
                     "\u062f\u0631 \u0637\u0631\u0641 \u0645\u062d\u0641\u0648\u0638 "
                     "\u0642\u0631\u0627\u0631 \u06af\u06cc\u0631\u0646\u062f",
    },

    ZONE_SERVICE: {
        "access_affinity": 0,
        "separation": True,
        "connects": False,
        "reason_en": "service spaces require functional connection to what "
                     "they serve, but controlled access",
        "reason_fa": "\u0641\u0636\u0627\u0647\u0627\u06cc \u062e\u062f\u0645\u0627\u062a\u06cc "
                     "\u0628\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 "
                     "\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc \u0646\u06cc\u0627\u0632 "
                     "\u062f\u0627\u0631\u0646\u062f\u060c \u0627\u0645\u0627 \u0628\u0627 "
                     "\u062f\u0633\u062a\u0631\u0633\u06cc \u06a9\u0646\u062a\u0631\u0644\u200c\u0634\u062f\u0647",
    },

    ZONE_CIRCULATION: {
        "access_affinity": 0,
        "separation": False,
        "connects": True,
        "reason_en": "circulation connects the other zones",
        "reason_fa": "\u0645\u0646\u0637\u0642\u0647\u0654 \u06af\u0631\u062f\u0634 "
                     "\u0633\u0627\u06cc\u0631 \u0645\u0646\u0637\u0642\u0647\u200c\u0647\u0627 "
                     "\u0631\u0627 \u0628\u0647 \u0647\u0645 \u0645\u062a\u0635\u0644 "
                     "\u0645\u06cc\u200c\u06a9\u0646\u062f",
    },

    ZONE_EXTERNAL: {
        "access_affinity": 0,
        "separation": False,
        "connects": False,
        "reason_en": "external spaces sit on the open edge of the site",
        "reason_fa": "\u0641\u0636\u0627\u0647\u0627\u06cc \u0628\u06cc\u0631\u0648\u0646\u06cc "
                     "\u062f\u0631 \u0637\u0631\u0641 \u0628\u0627\u0632 \u0632\u0645\u06cc\u0646 "
                     "\u0642\u0631\u0627\u0631 \u0645\u06cc\u200c\u06af\u06cc\u0631\u0646\u062f",
    },
}


class ZoneModelV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None):

        self.registry = registry or space_types

        print(
            "\U0001f9f1 ZONE MODEL v1.0 ONLINE "
            "(6 semantic zones, no geometry)"
        )

    # ======================================================

    def zone_of(self, space_id):

        record = self.registry.space(space_id)

        if not record:

            return None

        return ZONE_BY_CATEGORY.get(record.get("category"))

    def behaviour(self, zone, language="en"):

        entry = ZONE_BEHAVIOUR.get(zone) or {}

        lang = "fa" if str(language or "").startswith("fa") else "en"

        return {
            "zone": zone,
            "zone_label": zone_display(zone, lang),
            "access_affinity": entry.get("access_affinity", 0),
            "separation": entry.get("separation", False),
            "connects": entry.get("connects", False),
            "reason": entry.get("reason_" + lang),
        }

    def access_affinity(self, space_id):

        zone = self.zone_of(space_id)

        entry = ZONE_BEHAVIOUR.get(zone) or {}

        return entry.get("access_affinity", 0)

    def requires_separation(self, space_id):

        zone = self.zone_of(space_id)

        entry = ZONE_BEHAVIOUR.get(zone) or {}

        return bool(entry.get("separation"))

    # ------------------------------------------------------

    def group(self, space_ids, language="en"):

        """Group spaces into zones, preserving the canonical zone order."""

        buckets = {zone: [] for zone in ALL_ZONES}

        for space_id in space_ids:

            zone = self.zone_of(space_id)

            if zone:

                buckets[zone].append(space_id)

        lang = "fa" if str(language or "").startswith("fa") else "en"

        return [
            {
                "name": zone,
                "label": zone_display(zone, lang),
                "spaces": buckets[zone],
                "count": len(buckets[zone]),
                **{
                    key: value
                    for key, value in (ZONE_BEHAVIOUR.get(zone) or {}).items()
                    if key.startswith("access_") or key in (
                        "separation", "connects"
                    )
                },
            }
            for zone in ALL_ZONES
            if buckets[zone]
        ]

    # ------------------------------------------------------

    def report(self):

        records = self.registry.spaces()

        counts = {zone: 0 for zone in ALL_ZONES}

        for space_id in records:

            zone = self.zone_of(space_id)

            if zone:

                counts[zone] += 1

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "zones": list(ALL_ZONES),

            "zone_count": len(ALL_ZONES),

            "spaces_by_zone": counts,

            "zone_source": "derived_from_phase10_category",

            "contains_geometry": False,
            "contains_coordinates": False,
        }


zone_model = ZoneModelV1()
