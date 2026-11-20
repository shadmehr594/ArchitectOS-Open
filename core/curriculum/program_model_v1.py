# ==========================================================
# ArchitectOS Program Model v1
#
# PHASE 12 - PART 2 - FLOOR PROGRAM MODEL
#
# The semantic contract that sits between
#
#   SPACE + RELATIONSHIP + BUBBLE DIAGRAM   (Phases 10 + 11)
#                      and
#   future layout generation                (NOT this phase)
#
#   Program
#     -> zones
#       -> spaces
#         -> relationships
#           -> priorities
#             -> constraints
#
# SEMANTIC ONLY. No geometry, no coordinates, no walls, no doors, no
# CAD, no BIM, no IFC, no render. Nothing in this module may be drawn.
#
# Consumed, never duplicated:
#   core/curriculum/space_types_v1.py       (82 spaces)   [Phase 10]
#   core/curriculum/adjacency_model_v1.py   (133 grades)  [Phase 10]
#   core/curriculum/privacy_logic_v1.py     (3 bands)     [Phase 10]
#   core/curriculum/zone_model_v1.py        (6 zones)     [Phase 11]
#   core/curriculum/bubble_diagram_v1.py    (PROGRAM_SPACE_MAP) [Phase 11]
#   core/architecture/knowledge/building_program_knowledge.py
#
# The one thing this module ADDS is the program-level contract: which
# spaces are required vs optional, how they group into zones, in what
# order they matter (priorities) and what must hold between them
# (constraints) - none of which existed before Phase 12.
# ==========================================================


from __future__ import annotations


from core.curriculum.space_types_v1 import (
    space_types,
    category_display,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    relation_display,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
)

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.zone_model_v1 import (
    zone_model,
    zone_display,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    ALL_ZONES,
)

# PROGRAM_SPACE_MAP is Phase 11's table. Reusing it is the point: a
# second copy would drift and reintroduce the duplicate-concept trap.
from core.curriculum.bubble_diagram_v1 import PROGRAM_SPACE_MAP


CONTRACT = "ProgramModelV1"
VERSION = "1.0"


# ----------------------------------------------------------
# BUILDING TYPES
#
# The brief names three: residential, commercial, mixed use. The other
# five already exist in the frozen program corpus and are carried
# through so the model is honest about what it knows rather than
# pretending they do not exist.
# ----------------------------------------------------------

BUILDING_TYPE_RESIDENTIAL = "residential"
BUILDING_TYPE_COMMERCIAL = "commercial"
BUILDING_TYPE_MIXED_USE = "mixed_use"
BUILDING_TYPE_VILLA = "villa"
BUILDING_TYPE_PARKING = "parking"
BUILDING_TYPE_CINEMA = "cinema"
BUILDING_TYPE_AUDITORIUM = "auditorium"
BUILDING_TYPE_AMPHITHEATER = "amphitheater"


# The brief's three primary types.
PRIMARY_BUILDING_TYPES = (
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_COMMERCIAL,
    BUILDING_TYPE_MIXED_USE,
)


ALL_BUILDING_TYPES = (
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_VILLA,
    BUILDING_TYPE_COMMERCIAL,
    BUILDING_TYPE_MIXED_USE,
    BUILDING_TYPE_PARKING,
    BUILDING_TYPE_CINEMA,
    BUILDING_TYPE_AUDITORIUM,
    BUILDING_TYPE_AMPHITHEATER,
)


BUILDING_TYPE_LABELS = {
    BUILDING_TYPE_RESIDENTIAL: {"fa": "\u0645\u0633\u06a9\u0648\u0646\u06cc",
                                "en": "residential"},
    BUILDING_TYPE_VILLA: {"fa": "\u0648\u06cc\u0644\u0627", "en": "villa"},
    BUILDING_TYPE_COMMERCIAL: {"fa": "\u062a\u062c\u0627\u0631\u06cc",
                               "en": "commercial"},
    BUILDING_TYPE_MIXED_USE: {"fa": "\u062a\u0631\u06a9\u06cc\u0628\u06cc "
                                    "(\u062a\u062c\u0627\u0631\u06cc-\u0645\u0633\u06a9\u0648\u0646\u06cc)",
                              "en": "mixed use"},
    BUILDING_TYPE_PARKING: {"fa": "\u067e\u0627\u0631\u06a9\u06cc\u0646\u06af",
                            "en": "parking"},
    BUILDING_TYPE_CINEMA: {"fa": "\u0633\u06cc\u0646\u0645\u0627", "en": "cinema"},
    BUILDING_TYPE_AUDITORIUM: {"fa": "\u0633\u0627\u0644\u0646 "
                                      "\u0627\u062c\u062a\u0645\u0627\u0639\u0627\u062a",
                               "en": "auditorium"},
    BUILDING_TYPE_AMPHITHEATER: {"fa": "\u0622\u0645\u0641\u06cc\u200c\u062a\u0626\u0627\u062a\u0631",
                                 "en": "amphitheater"},
}


def building_type_display(building_type, language="en"):

    entry = BUILDING_TYPE_LABELS.get(building_type) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(building_type)


# ----------------------------------------------------------
# PROGRAM ZONE -> PHASE 11 ZONE (FALLBACK ONLY)
#
# The frozen program corpus carries its OWN coarse zone word
# ('public', 'private', 'service', 'circulation', 'external',
# 'performance'). Phase 11's zone model is the single source of truth
# for a space's zone, so this table is used ONLY when a program space
# name does not resolve to a Phase 10 space id.
#
# 'performance' has NO Phase 11 equivalent. Mapping it to PUBLIC_ZONE
# is an APPROXIMATION and is recorded as such on every space it
# affects, rather than being presented as a derived fact.
# ----------------------------------------------------------

PROGRAM_ZONE_TO_PHASE11 = {
    "public": ZONE_PUBLIC,
    "semi_public": ZONE_SEMI_PUBLIC,
    "private": ZONE_PRIVATE,
    "service": ZONE_SERVICE,
    "circulation": ZONE_CIRCULATION,
    "external": ZONE_EXTERNAL,
    "performance": ZONE_PUBLIC,
}


APPROXIMATED_PROGRAM_ZONES = ("performance",)


# ----------------------------------------------------------
# PRIORITIES
#
# P1 - the program does not work without it
# P2 - important, expected in a competent scheme
# P3 - enhancing / optional
# ----------------------------------------------------------

PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"
PRIORITY_P3 = "P3"

ALL_PRIORITIES = (PRIORITY_P1, PRIORITY_P2, PRIORITY_P3)


PRIORITY_LABELS = {
    PRIORITY_P1: {"fa": "\u0636\u0631\u0648\u0631\u06cc", "en": "essential"},
    PRIORITY_P2: {"fa": "\u0645\u0647\u0645", "en": "important"},
    PRIORITY_P3: {"fa": "\u062a\u06a9\u0645\u06cc\u0644\u06cc", "en": "enhancing"},
}


def priority_display(priority, language="en"):

    entry = PRIORITY_LABELS.get(priority) or {}

    return entry.get(
        "fa" if str(language or "").startswith("fa") else "en"
    ) or str(priority)


# ----------------------------------------------------------
# CONSTRAINT KINDS (semantic - never geometric)
# ----------------------------------------------------------

CONSTRAINT_FORBIDDEN_OPENING = "FORBIDDEN_DIRECT_OPENING"
CONSTRAINT_BUFFERED_CONNECTION = "BUFFERED_CONNECTION"
CONSTRAINT_PRIVACY_SEPARATION = "PRIVACY_SEPARATION"
CONSTRAINT_CONTROLLED_ACCESS = "CONTROLLED_ACCESS"
CONSTRAINT_CAPACITY = "CAPACITY"
CONSTRAINT_ACCESS_REQUIRED = "ACCESS_REQUIRED"


ALL_CONSTRAINT_KINDS = (
    CONSTRAINT_FORBIDDEN_OPENING,
    CONSTRAINT_BUFFERED_CONNECTION,
    CONSTRAINT_PRIVACY_SEPARATION,
    CONSTRAINT_CONTROLLED_ACCESS,
    CONSTRAINT_CAPACITY,
    CONSTRAINT_ACCESS_REQUIRED,
)


# ----------------------------------------------------------
# OCCUPANCY -> CAPACITY RULES
#
# Semantic counts only (how many of a thing), never dimensions.
# ----------------------------------------------------------

PERSONS_PER_BATHROOM = 4


class ProgramModelV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, adjacency=None, privacy=None,
                 zones=None):

        self.registry = registry or space_types

        self.adjacency = adjacency or adjacency_model

        self.privacy = privacy or privacy_logic

        self.zones = zones or zone_model

        print(
            "\U0001f4d0 PROGRAM MODEL v1.0 ONLINE "
            "(program -> zones -> spaces -> priorities -> constraints)"
        )

    # ======================================================
    # SPACE RESOLUTION (consume Phase 11's table, never copy it)
    # ======================================================

    def resolve_space_name(self, name):

        """Program space name -> Phase 10 space id.

        Resolution order, recorded on the result so it is auditable:

          PROGRAM_SPACE_MAP  the Phase 11 table (authoritative)
          REGISTRY_ALIAS     the Phase 10 alias table
          UNRESOLVED         nothing matched - keep the program name
                             and say so; never invent a space id
        """

        key = str(name or "").strip()

        if not key:

            return {
                "program_name": key,
                "space_id": None,
                "resolution": "UNRESOLVED",
            }

        mapped = PROGRAM_SPACE_MAP.get(key)

        if mapped and self.registry.space(mapped):

            return {
                "program_name": key,
                "space_id": mapped,
                "resolution": "PROGRAM_SPACE_MAP",
            }

        found = self.registry.find(key)

        if found:

            return {
                "program_name": key,
                "space_id": found,
                "resolution": "REGISTRY_ALIAS",
            }

        return {
            "program_name": key,
            "space_id": None,
            "resolution": "UNRESOLVED",
        }

    # ------------------------------------------------------

    def zone_for(self, space_id, program_zone):

        """Zone of a program space.

        Phase 11's zone model wins whenever the space resolves. The
        frozen program corpus's own zone word is only a fallback, and an
        approximated fallback says so.
        """

        if space_id:

            zone = self.zones.zone_of(space_id)

            if zone:

                return {
                    "zone": zone,
                    "zone_source": "phase10_category",
                    "approximated": False,
                }

        key = str(program_zone or "").strip().lower()

        zone = PROGRAM_ZONE_TO_PHASE11.get(key)

        if zone:

            return {
                "zone": zone,
                "zone_source": "program_knowledge_fallback",
                "approximated": key in APPROXIMATED_PROGRAM_ZONES,
            }

        return {
            "zone": None,
            "zone_source": "unresolved",
            "approximated": False,
        }

    # ======================================================
    # SPACE ENTRY
    # ======================================================

    def space_entry(self, program_name, program_zone=None, required=True,
                    floor=None, program_payload=None, language="en"):

        resolved = self.resolve_space_name(program_name)

        space_id = resolved["space_id"]

        zone_info = self.zone_for(space_id, program_zone)

        record = self.registry.space(space_id) if space_id else None

        entry = {

            "program_name": resolved["program_name"],

            "space_id": space_id,

            "resolution": resolved["resolution"],

            "required": bool(required),

            "zone": zone_info["zone"],
            "zone_source": zone_info["zone_source"],
            "zone_approximated": zone_info["approximated"],

            "zone_label": (
                zone_display(zone_info["zone"], language)
                if zone_info["zone"] else None
            ),

            "category": (record or {}).get("category"),
            "privacy_level": (record or {}).get("privacy_level"),

            "floor": floor,

            "name": (record or {}).get("name"),

            "priority": None,

            "constraints": [],

            "provenance": {
                "space": (record or {}).get("origin") or "UNRESOLVED",
                "resolution": resolved["resolution"],
                "zone": zone_info["zone_source"],
                "program": (
                    program_payload or {}
                ).get("source") or "BUILDING_PROGRAM_KNOWLEDGE",
            },
        }

        if program_payload:

            for field in (
                "protected_zone", "placement_scope",
                "access_requirement", "dimensional_requirements",
            ):

                if field in program_payload:

                    entry[field] = program_payload[field]

        return entry

    # ======================================================
    # PRIORITIES
    # ======================================================

    def priority_for(self, entry, required=True):

        """P1 / P2 / P3.

        P1  required AND carries the life of the building (the zones the
            program exists for: public field, private field, circulation
            spine, and the service spaces that must physically connect)
        P2  required but supporting, or a private/service space
        P3  optional / enhancing
        """

        if not required:

            return PRIORITY_P3

        zone = entry.get("zone")

        if zone in (ZONE_PUBLIC, ZONE_PRIVATE, ZONE_CIRCULATION):

            return PRIORITY_P1

        if zone == ZONE_SERVICE:

            return PRIORITY_P1

        if zone == ZONE_SEMI_PUBLIC:

            return PRIORITY_P2

        return PRIORITY_P2

    # ======================================================
    # CONSTRAINTS (semantic)
    # ======================================================

    def constraints_between(self, entry_a, entry_b):

        """Semantic constraints implied by the Phase 10 adjacency model."""

        space_a = entry_a.get("space_id")

        space_b = entry_b.get("space_id")

        if not space_a or not space_b:

            return []

        relation = self.adjacency.relation(space_a, space_b)

        if not relation:

            return []

        grade = relation["relation_type"]

        constraints = []

        if grade == REL_FORBIDDEN:

            constraints.append(
                {
                    "kind": CONSTRAINT_FORBIDDEN_OPENING,
                    "spaces": [space_a, space_b],
                    "relation_type": grade,
                    "reason": relation.get("reason"),
                    "confidence": relation.get("confidence"),
                    "provenance": relation.get("provenance"),
                    "geometric": False,
                }
            )

        elif grade == REL_AVOID:

            constraints.append(
                {
                    "kind": CONSTRAINT_BUFFERED_CONNECTION,
                    "spaces": [space_a, space_b],
                    "relation_type": grade,
                    "reason": relation.get("reason"),
                    "confidence": relation.get("confidence"),
                    "provenance": relation.get("provenance"),
                    "geometric": False,
                }
            )

        return constraints

    # ------------------------------------------------------

    def constraints_for_space(self, entry):

        """Constraints that attach to ONE space."""

        space_id = entry.get("space_id")

        constraints = []

        if not space_id:

            return constraints

        control = self.privacy.requires_controlled_access(space_id)

        if control.get("required"):

            constraints.append(
                {
                    "kind": CONSTRAINT_CONTROLLED_ACCESS,
                    "spaces": [space_id],
                    "reason": "; ".join(control.get("reasons") or []),
                    "reasons": control.get("reasons") or [],
                    "provenance": "core/curriculum/privacy_logic_v1.py",
                    "geometric": False,
                }
            )

        zone = entry.get("zone")

        if zone == ZONE_PRIVATE:

            constraints.append(
                {
                    "kind": CONSTRAINT_PRIVACY_SEPARATION,
                    "spaces": [space_id],
                    "reason": (
                        "private space: must be separated from the "
                        "arrival field"
                    ),
                    "provenance": "core/curriculum/privacy_logic_v1.py",
                    "geometric": False,
                }
            )

        if entry.get("access_requirement"):

            constraints.append(
                {
                    "kind": CONSTRAINT_ACCESS_REQUIRED,
                    "spaces": [space_id],
                    "reason": str(entry.get("access_requirement")),
                    "provenance": "BUILDING_PROGRAM_KNOWLEDGE",
                    "geometric": False,
                }
            )

        return constraints

    # ------------------------------------------------------

    def capacity_constraints(self, occupancy, spaces, language="en"):

        """Occupancy -> semantic capacity constraints (counts, not sizes)."""

        constraints = []

        people = (occupancy or {}).get("household_size")

        bedrooms = (occupancy or {}).get("bedrooms")

        bathrooms = len(
            [
                s for s in spaces
                if s.get("space_id") in (
                    "FAMILY_BATHROOM", "ENSUITE", "GUEST_WC",
                    "SEPARATE_WC",
                )
            ]
        )

        if people and bedrooms:

            needed = max(1, people - 1)

            if bedrooms < needed:

                constraints.append(
                    {
                        "kind": CONSTRAINT_CAPACITY,
                        "spaces": ["MASTER_BEDROOM_SLEEPING"],
                        "reason": (
                            "%d people usually need at least %d sleeping "
                            "spaces; the program provides %d"
                            % (people, needed, bedrooms)
                        ),
                        "demand": needed,
                        "provided": bedrooms,
                        "geometric": False,
                    }
                )

        if people and bathrooms:

            needed = max(1, -(-people // PERSONS_PER_BATHROOM))

            if bathrooms < needed:

                constraints.append(
                    {
                        "kind": CONSTRAINT_CAPACITY,
                        "spaces": ["FAMILY_BATHROOM"],
                        "reason": (
                            "%d people usually need at least %d sanitary "
                            "space(s); the program provides %d"
                            % (people, needed, bathrooms)
                        ),
                        "demand": needed,
                        "provided": bathrooms,
                        "geometric": False,
                    }
                )

        return constraints

    # ======================================================
    # BUILD
    # ======================================================

    def build(self, program_payload, building_type, occupancy=None,
              language="en"):

        """The floor program contract for one building program payload."""

        required = list(program_payload.get("required_spaces") or [])

        optional = list(program_payload.get("optional_spaces") or [])

        spaces = []

        for item in required:

            spaces.append(
                self.space_entry(
                    item.get("name"),
                    program_zone=item.get("zone"),
                    required=True,
                    floor=item.get("floor"),
                    program_payload=item,
                    language=language,
                )
            )

        for item in optional:

            spaces.append(
                self.space_entry(
                    item.get("name"),
                    program_zone=item.get("zone"),
                    required=False,
                    floor=item.get("floor"),
                    program_payload=item,
                    language=language,
                )
            )

        return self._assemble(
            spaces,
            building_type,
            occupancy=occupancy,
            language=language,
            declared_relationships=(
                program_payload.get("relationships") or []
            ),
        )

    # ------------------------------------------------------

    def build_from_instances(self, instances, building_type,
                             occupancy=None, language="en"):

        """The floor program contract for an ORDERED space-id list.

        This is the path the reasoning engine uses. Phase 11's
        `program_spaces()` has ALREADY expanded the bedroom count and
        applied the curriculum completion, so that instance list is the
        single source of truth for WHICH spaces exist. Phase 12 must not
        re-derive it - re-deriving is how the two layers would drift.
        """

        spaces = []

        for space_id in instances:

            spaces.append(
                self.space_entry(space_id, required=True, language=language)
            )

        return self._assemble(
            spaces,
            building_type,
            occupancy=occupancy,
            language=language,
            declared_relationships=[],
        )

    # ------------------------------------------------------

    def _assemble(self, spaces, building_type, occupancy=None,
                  language="en", declared_relationships=None):

        """Priorities -> constraints -> zones -> relationships."""

        declared_relationships = declared_relationships or []

        # ---- priorities ----
        for entry in spaces:

            entry["priority"] = self.priority_for(
                entry, required=entry["required"]
            )

        # ---- per-space constraints ----
        for entry in spaces:

            entry["constraints"] = self.constraints_for_space(entry)

        # ---- pair constraints ----
        pair_constraints = []

        seen = set()

        for index, entry_a in enumerate(spaces):

            for entry_b in spaces[index + 1:]:

                for constraint in self.constraints_between(entry_a, entry_b):

                    key = (
                        constraint["kind"],
                        tuple(sorted(constraint["spaces"])),
                    )

                    if key in seen:

                        continue

                    seen.add(key)

                    pair_constraints.append(constraint)

        constraints = list(pair_constraints)

        for entry in spaces:

            constraints.extend(entry["constraints"])

        constraints.extend(
            self.capacity_constraints(occupancy or {}, spaces, language)
        )

        # ---- zone grouping ----
        buckets = {zone: [] for zone in ALL_ZONES}

        for entry in spaces:

            zone = entry.get("zone")

            if zone:

                buckets[zone].append(entry)

        zones = []

        for zone in ALL_ZONES:

            members = buckets[zone]

            if not members:

                continue

            priorities = sorted(
                {m["priority"] for m in members if m["priority"]}
            )

            zones.append(
                {

                    "name": zone,

                    "label": zone_display(zone, language),

                    "spaces": [
                        m["space_id"] or m["program_name"]
                        for m in members
                    ],

                    "count": len(members),

                    "priority": (
                        priorities[0] if priorities else PRIORITY_P2
                    ),

                    "privacy_band": self.privacy.band(
                        members[0]["space_id"]
                    ) if members[0]["space_id"] else None,

                    "reason": self.zones.behaviour(
                        zone, language
                    ).get("reason"),

                    "geometric": False,
                }
            )

        # ---- relationships (translate the DECLARED relations) ----
        relationships = []

        for relation in declared_relationships:

            source = self.resolve_space_name(relation.get("from"))

            target = self.resolve_space_name(relation.get("to"))

            grade = None

            reason = None

            confidence = None

            provenance = "BUILDING_PROGRAM_KNOWLEDGE"

            if source["space_id"] and target["space_id"]:

                graded = self.adjacency.relation(
                    source["space_id"], target["space_id"]
                )

                if graded:

                    grade = graded["relation_type"]

                    reason = graded.get("reason")

                    confidence = graded.get("confidence")

                    provenance = graded.get("provenance")

            relationships.append(
                {

                    "from": relation.get("from"),
                    "to": relation.get("to"),

                    "from_space": source["space_id"],
                    "to_space": target["space_id"],

                    "declared_type": relation.get("type"),

                    "grade": grade,
                    "grade_label": (
                        relation_display(grade, language) if grade else None
                    ),

                    "reason": reason,
                    "confidence": confidence,
                    "provenance": provenance,

                    "geometric": False,
                }
            )

        # ---- priority summary ----
        priorities = [
            {
                "priority": priority,
                "label": priority_display(priority, language),
                "count": len(
                    [s for s in spaces if s["priority"] == priority]
                ),
                "spaces": [
                    s["space_id"] or s["program_name"]
                    for s in spaces
                    if s["priority"] == priority
                ],
            }
            for priority in ALL_PRIORITIES
        ]

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "building_type": building_type,

            "building_type_label": building_type_display(
                building_type, language
            ),

            "occupancy": occupancy or {},

            "language": language,

            "zones": zones,

            "spaces": spaces,

            "relationships": relationships,

            "priorities": priorities,

            "constraints": constraints,

            "counts": {
                "spaces": len(spaces),
                "required": len([s for s in spaces if s["required"]]),
                "optional": len([s for s in spaces if not s["required"]]),
                "resolved": len([s for s in spaces if s["space_id"]]),
                "unresolved": len(
                    [s for s in spaces if not s["space_id"]]
                ),
                "zones": len(zones),
                "relationships": len(relationships),
                "constraints": len(constraints),
            },

            "unresolved_spaces": [
                s["program_name"] for s in spaces if not s["space_id"]
            ],

            # ---- hard scope guarantees ----
            "semantic_only": True,
            "contains_geometry": False,
            "contains_coordinates": False,
            "contains_walls": False,
            "contains_openings": False,
            "render_requested": False,
            "comfy_invoked": False,

            "deterministic": True,
            "llm_used": False,
            "network_used": False,

            "provenance": {
                "spaces": "core/curriculum/space_types_v1.py",
                "zones": "core/curriculum/zone_model_v1.py",
                "relationships": "core/curriculum/adjacency_model_v1.py",
                "privacy": "core/curriculum/privacy_logic_v1.py",
                "space_map": "core/curriculum/bubble_diagram_v1.py",
                "program": "BUILDING_PROGRAM_KNOWLEDGE",
            },
        }

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "building_types": list(ALL_BUILDING_TYPES),
            "primary_building_types": list(PRIMARY_BUILDING_TYPES),

            "zones": list(ALL_ZONES),
            "priorities": list(ALL_PRIORITIES),
            "constraint_kinds": list(ALL_CONSTRAINT_KINDS),

            "space_map_size": len(PROGRAM_SPACE_MAP),

            "program_zone_fallback": dict(PROGRAM_ZONE_TO_PHASE11),
            "approximated_program_zones": list(APPROXIMATED_PROGRAM_ZONES),

            "contains_geometry": False,
            "contains_coordinates": False,

            "next_stage_not_started": (
                "layout generation / floor plan / walls / openings"
            ),
        }


program_model = ProgramModelV1()
