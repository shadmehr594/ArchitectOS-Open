# ==========================================================
# ArchitectOS Bubble Diagram v1
#
# PHASE 11 — PART 1 (model) + PART 2 (graph reasoning) + PART 7 (output)
#
#   SPACE + RELATIONSHIP  ->  SEMANTIC SPATIAL DIAGRAM
#
# This is NOT a floor plan, NOT geometry, NOT drawing. The output is a
# machine-readable SEMANTIC bubble diagram: zones, bubbles and graded
# relations. There are no coordinates anywhere in this module.
#
# Reused (never rewritten):
#   core/architecture/knowledge/building_program_knowledge.py
#       -> the required-space program (8 building types)
#   core/curriculum/space_types_v1.py      (82 spaces)
#   core/curriculum/adjacency_model_v1.py  (133 graded relations)
#   core/curriculum/privacy_logic_v1.py
#   core/curriculum/zone_model_v1.py
#   core/curriculum/site_intent_v1.py
# ==========================================================


from __future__ import annotations


import copy
import re


from core.conversation.turn_semantics_v1 import match_form, script_of

from core.curriculum.space_types_v1 import space_types

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
)

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.zone_model_v1 import (
    zone_model,
    ZONE_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    ZONE_SEMI_PUBLIC,
)

from core.curriculum.site_intent_v1 import site_intent


CONTRACT = "BubbleDiagramV1"
VERSION = "1.0"


DIAGRAM_TYPE = "semantic_bubble_diagram"


# Short relation labels for the machine-readable output (PART 7).
SHORT_RELATION = {
    REL_STRONG: "STRONG",
    REL_NORMAL: "NORMAL",
    REL_WEAK: "WEAK",
    REL_AVOID: "AVOID",
    REL_FORBIDDEN: "FORBIDDEN",
}


IMPORTANCE_HIGH = "HIGH"
IMPORTANCE_MEDIUM = "MEDIUM"
IMPORTANCE_LOW = "LOW"


# Primary program spaces never fall below MEDIUM importance: they are the
# spaces the dwelling exists for, regardless of how many connections the
# diagram happens to contain.
PRIMARY_SPACES = frozenset(
    (
        "LIVING_RECEPTION",
        "OPEN_KITCHEN",
        "CLOSED_KITCHEN",
        "DINING",
        "MASTER_BEDROOM_SLEEPING",
        "BEDROOM_DOUBLE",
        "BEDROOM_SINGLE",
        "FAMILY_BATHROOM",
        "UNIT_ENTRY",
        "STUDY",
    )
)


# ----------------------------------------------------------
# PROGRAM PARSING
# ----------------------------------------------------------

BUILDING_WORDS = {
    "residential": (
        "\u062e\u0627\u0646\u0647",              # خانه
        "\u0645\u0633\u06a9\u0648\u0646\u06cc",  # مسکونی
        "\u0622\u067e\u0627\u0631\u062a\u0645\u0627\u0646",  # آپارتمان
        "\u062e\u0627\u0646\u0647\u200c\u0648\u0627\u0631",  # خانه‌وار
        "house",
        "home",
        "residential",
        "apartment",
    ),
    "villa": (
        "\u0648\u06cc\u0644\u0627",              # ویلا
        "villa",
    ),
    "commercial": (
        "\u062a\u062c\u0627\u0631\u06cc",        # تجاری
        "\u0641\u0631\u0648\u0634\u06af\u0627\u0647",  # فروشگاه
        "commercial",
        "retail",
        "shop",
    ),
}


PERSIAN_NUMBERS = {
    "\u06cc\u06a9": 1,        # یک
    "\u062f\u0648": 2,        # دو
    "\u0633\u0647": 3,        # سه
    "\u0686\u0647\u0627\u0631": 4,  # چهار
    "\u067e\u0646\u062c": 5,  # پنج
    "\u0634\u0634": 6,        # شش
}


ENGLISH_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}


BEDROOM_WORDS = (
    "\u062e\u0648\u0627\u0628\u0647",        # خوابه
    "\u062e\u0648\u0627\u0628",              # خواب
    "bedroom",
    "bed",
)


# ----------------------------------------------------------
# PROGRAM NAME -> PHASE 10 SPACE ID
# ----------------------------------------------------------

PROGRAM_SPACE_MAP = {
    "entrance": "UNIT_ENTRY",
    "foyer": "FOYER_SHOE_OFF",
    "living": "LIVING_RECEPTION",
    "living_room": "LIVING_RECEPTION",
    "dining": "DINING",
    "kitchen": "OPEN_KITCHEN",
    "kitchen_clean": "OPEN_KITCHEN",
    "kitchen_dirty": "CLOSED_KITCHEN",
    "master_bedroom": "MASTER_BEDROOM_SLEEPING",
    "bedroom": "BEDROOM_DOUBLE",
    "guest_bedroom": "BEDROOM_DOUBLE",
    "bathroom": "FAMILY_BATHROOM",
    "ensuite": "ENSUITE",
    "guest_wc": "GUEST_WC",
    "wc": "SEPARATE_WC",
    "storage": "STORAGE_LINEN",
    "store": "STORAGE_LINEN",
    "laundry": "LAUNDRY_UTILITY",
    "utility": "LAUNDRY_UTILITY",
    "corridor": "PRIVATE_HALL_CORRIDOR",
    "hall": "PRIVATE_HALL_CORRIDOR",
    "stairs": "STAIR",
    "stair": "STAIR",
    "elevator": "ELEVATOR",
    "lobby": "LOBBY",
    "terrace": "TERRACE_BALCONY",
    "balcony": "TERRACE_BALCONY",
    "yard": "PRIVATE_YARD",
    "garden": "PRIVATE_YARD",
    "courtyard": "COURTYARD",
    "parking": "PARKING_BAY",
    "study": "STUDY",
    "office": "STUDY",
    "retail": "retail",
    "shop": "retail",
}


# Spaces the curriculum always expects in a dwelling even when the
# frozen program does not list them. Additive completion, provenance
# marked.
CURRICULUM_COMPLETION = {
    "residential": ("DINING", "STORAGE_LINEN"),
    "villa": ("STORAGE_LINEN", "TERRACE_BALCONY"),
}


# ----------------------------------------------------------
# POSITION INTENT (PART 4 -> PART 1)
# ----------------------------------------------------------

# Candidate site-intent keys per zone, most specific first.
#
# The site payload is NOT uniform: `access_edge` and `open_edge` are
# scalars, while `protected_edges` and `daylight_edges` are LISTS. Asking
# for the singular "protected_edge" silently returned None, so the private
# zone -- the one that matters most for site reasoning -- never received an
# edge at all.
_ZONE_EDGE_PREFERENCE = {
    ZONE_PUBLIC: ("access_edge",),
    ZONE_PRIVATE: ("protected_edges", "open_edge"),
    ZONE_EXTERNAL: ("open_edge", "protected_edges"),
    ZONE_SEMI_PUBLIC: ("daylight_edges", "open_edge"),
    ZONE_SERVICE: (),
    ZONE_CIRCULATION: ("access_edge",),
}


def _site_edge(site, preference):

    """Read one edge from a site-intent payload.

    Handles both the scalar and the list-valued site keys.
    """

    value = site.get(preference)

    if isinstance(value, (list, tuple)):

        return value[0] if value else None

    return value


class BubbleDiagramBuilderV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, adjacency=None, zones=None,
                 privacy=None, site=None):

        self.registry = registry or space_types

        self.adjacency = adjacency or adjacency_model

        self.zones = zones or zone_model

        self.privacy = privacy or privacy_logic

        self.site = site or site_intent

        self._program_cache = None

        print(
            "\U0001f535 BUBBLE DIAGRAM v1.0 ONLINE "
            "(semantic only \u2014 no geometry, no coordinates)"
        )

    # ======================================================
    # PROGRAM
    # ======================================================

    def _program_knowledge(self):

        if self._program_cache is not None:

            return self._program_cache

        try:

            from core.architecture.knowledge.building_program_knowledge import (  # noqa: E501
                BuildingProgramKnowledge,
            )

            self._program_cache = BuildingProgramKnowledge()

        except Exception as error:

            print("PHASE 11 PROGRAM KNOWLEDGE ERROR:", error)

            self._program_cache = None

        return self._program_cache

    # ------------------------------------------------------

    def parse_program(self, text, language=None):

        raw = str(text or "")

        form = match_form(raw)

        # ---- building type ----
        program = None

        for name, words in BUILDING_WORDS.items():

            if any(word in form for word in words):

                program = name

                break

        # ---- bedroom count ----
        bedrooms = self._bedroom_count(form)

        if program is None and bedrooms is not None:

            program = "residential"

        if program is None:

            program = "residential"

        return {

            "program": program,

            "bedrooms": bedrooms,

            "source": (
                "explicit" if bedrooms is not None else "default"
            ),
        }

    # ------------------------------------------------------

    def _bedroom_count(self, form):

        """Bedroom count, only when a number sits ADJACENT to a bedroom
        word.

        A bare number word anywhere in the sentence is NOT a bedroom
        count. "خانه \u062f\u0648 \u0633\u0631\u0648\u06cc\u0633" (a house with two
        bathrooms) must not override an explicit "\u06f3 \u062e\u0648\u0627\u0628\u0647"
        (three bedrooms); scanning for the number word alone did exactly
        that.

        Priority: explicit digits ("3 \u062e\u0648\u0627\u0628\u0647") outrank a
        spelled-out Persian number word, which outranks English.
        """

        tail = "(?:\u062e\u0648\u0627\u0628|bedroom|bed)"

        match = re.search(r"(\d+)\s*" + tail, form)

        if match:

            value = int(match.group(1))

            return value if value >= 1 else None

        for word, value in PERSIAN_NUMBERS.items():

            if re.search(re.escape(word) + r"\s*" + tail, form):

                return value

        for word, value in ENGLISH_NUMBERS.items():

            if re.search(r"\b" + word + r"\s*" + tail, form):

                return value

        return None

    # ------------------------------------------------------

    def program_spaces(self, text, language=None):

        """Ordered Phase 10 space ids for a program statement."""

        parsed = self.parse_program(text, language)

        program = parsed["program"]

        bedrooms = parsed["bedrooms"] or 3

        knowledge = self._program_knowledge()

        raw_names = []

        source = "CURRICULUM_FALLBACK"

        if knowledge is not None:

            try:

                data = knowledge.get_program(program) or {}

                raw_names = [
                    entry.get("name")
                    for entry in (data.get("required_spaces") or [])
                ]

                source = "BUILDING_PROGRAM_KNOWLEDGE"

            except Exception as error:

                print("PHASE 11 PROGRAM LOOKUP ERROR:", error)

        if not raw_names:

            raw_names = [
                "entrance", "living", "dining", "kitchen", "guest_wc",
                "corridor", "master_bedroom", "bedroom", "bathroom",
            ]

        # ---- map to Phase 10 ids, expanding bedrooms ----
        instances = []

        for name in raw_names:

            space_id = PROGRAM_SPACE_MAP.get(str(name))

            if not space_id:

                continue

            if space_id in ("BEDROOM_DOUBLE", "MASTER_BEDROOM_SLEEPING"):

                # bedrooms are expanded below, from the count
                continue

            if not any(i == space_id for i in instances):

                instances.append(space_id)

        # bedrooms: one master sleeping space + (bedrooms - 1) bedrooms
        instances.append("MASTER_BEDROOM_SLEEPING")

        for _index in range(max(0, bedrooms - 1)):

            instances.append("BEDROOM_DOUBLE")

        # ---- additive curriculum completion ----
        added = []

        for space_id in CURRICULUM_COMPLETION.get(program, ()):

            if space_id not in instances:

                instances.append(space_id)

                added.append(space_id)

        # ---- drop ids the registry does not know ----
        instances = [
            space_id for space_id in instances
            if self.registry.space(space_id)
        ]

        return {

            "parsed": parsed,

            "instances": instances,

            "space_ids": list(instances),

            "program_source": source,

            "curriculum_completion_added": added,

            "bedrooms": bedrooms,
        }

    # ======================================================
    # BUILD
    # ======================================================

    def build(
        self,
        requirement,
        site_text=None,
        language=None,
        project_id=None,
    ):

        raw = str(requirement or "")

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        program = self.program_spaces(raw, lang)

        site = self.site.parse(site_text or "", lang) if site_text else None

        # ---- bubbles ----
        bubbles = []

        # stable ids: `<SPACE_ID>` when unique, else `<SPACE_ID>_<n>`
        totals = {}

        for space_id in program["instances"]:

            totals[space_id] = totals.get(space_id, 0) + 1

        counters = {}

        for space_id in program["instances"]:

            counters[space_id] = counters.get(space_id, 0) + 1

            bubble_id = (
                space_id if totals[space_id] == 1
                else "%s_%d" % (space_id, counters[space_id])
            )

            bubbles.append(
                self._bubble(bubble_id, space_id, site, lang)
            )

        bubble_by_space = {}

        for bubble in bubbles:

            bubble_by_space.setdefault(
                bubble["space_id"], []
            ).append(bubble["bubble_id"])

        # ---- connections + separation rules ----
        for bubble in bubbles:

            self._wire(bubble, bubbles, bubble_by_space, lang)

        # ---- importance (needs the wiring) ----
        for bubble in bubbles:

            self._importance(bubble)

        # ---- zone grouping ----
        zone_input = []

        for bubble in bubbles:

            if bubble["space_id"] not in zone_input:

                zone_input.append(bubble["space_id"])

        zones = self.zones.group(zone_input, lang)

        # ---- machine-readable relation list (PART 7) ----
        relations = []

        seen = set()

        for bubble in bubbles:

            for connection in bubble["connections"]:

                pair = tuple(
                    sorted([bubble["bubble_id"], connection["to_bubble"]])
                )

                if pair in seen:

                    continue

                seen.add(pair)

                relations.append(
                    {
                        "from": pair[0],
                        "to": pair[1],
                        "type": SHORT_RELATION.get(
                            connection["relation_type"],
                            connection["relation_type"],
                        ),
                        "relation_type": connection["relation_type"],
                        "reason": connection["reason"],
                        "confidence": connection["confidence"],
                        "provenance": connection["provenance"],
                    }
                )

        separation_rules = []

        seen_separation = set()

        for bubble in bubbles:

            for rule in bubble["separation_rules"]:

                pair = tuple(
                    sorted([bubble["bubble_id"], rule["to"]])
                )

                if pair in seen_separation:

                    continue

                seen_separation.add(pair)

                separation_rules.append(
                    {
                        "from": pair[0],
                        "to": pair[1],
                        "type": rule["short_type"],
                        "relation_type": rule["relation_type"],
                        "reason": rule["reason"],
                    }
                )

        reasoning = self._diagram_reasoning(
            program, site, bubbles, zones, lang
        )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "diagram_type": DIAGRAM_TYPE,

            "project_id": project_id,

            "language": lang,

            "input": {
                "requirement": raw,
                "site": site_text or "",
            },

            "program": {
                "building_type": program["parsed"]["program"],
                "bedrooms": program["bedrooms"],
                "bedroom_count_source": program["parsed"]["source"],
                "source": program["program_source"],
                "curriculum_completion_added": (
                    program["curriculum_completion_added"]
                ),
                "space_count": len(bubbles),
            },

            "site": site,

            "zones": zones,

            "bubbles": bubbles,

            "relations": relations,

            "separation_rules": separation_rules,

            "reasoning": reasoning,

            "provenance": {
                "program": program["program_source"],
                "spaces": "core/curriculum/space_types_v1.py",
                "zones": "core/curriculum/zone_model_v1.py",
                "relations": "core/curriculum/adjacency_model_v1.py",
                "privacy": "core/curriculum/privacy_logic_v1.py",
                "site": (
                    "core/curriculum/site_intent_v1.py" if site else None
                ),
            },

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
        }

    # ======================================================
    # BUBBLE (PART 1 CONTRACT)
    # ======================================================

    def _bubble(self, bubble_id, space_id, site, lang):

        record = self.registry.space(space_id) or {}

        zone = self.zones.zone_of(space_id)

        return {

            "contract": CONTRACT + ".Bubble",
            "version": VERSION,

            "bubble_id": bubble_id,

            "space_id": space_id,

            "space_type": (
                record.get("functional_role")
                or record.get("circulation_role")
                or space_id
            ),

            "name": (record.get("name") or {}).get(lang),

            "category": record.get("category"),

            # `privacy` is the Phase 11 contract name, `privacy_level` the
            # frozen Phase 10 name. Both are exposed and neither is
            # renamed, so no existing consumer breaks.
            "privacy": record.get("privacy_level"),
            "privacy_level": record.get("privacy_level"),

            "zone": zone,

            "importance": None,
            "importance_reason": None,

            # Raw connection score (STRONG +2, NORMAL +1 per connection,
            # plus a zone contribution). `importance` is the band over it.
            "adjacency_weight": None,

            "connections": [],

            # Brief-contract views of `connections`, filled in `_wire`:
            # required_connections  -> STRONG / NORMAL
            # forbidden_connections -> AVOID / FORBIDDEN
            "required_connections": [],
            "forbidden_connections": [],

            "separation_rules": [],

            "position_intent": self._position_intent(
                space_id, zone, site, lang
            ),

            "reasoning": [],

            "provenance": {
                "space": record.get("origin"),
                "category": record.get("category_source"),
                "zone": "derived_from_phase10_category",
                "connections": "core/curriculum/adjacency_model_v1.py",
            },
        }

    # ------------------------------------------------------

    def _position_intent(self, space_id, zone, site, lang):

        preferences = _ZONE_EDGE_PREFERENCE.get(zone) or ()

        intent = {
            "zone": zone,
            "edge_role": preferences[0] if preferences else None,
            "edge": None,
            "determined": False,
            "reason": None,
        }

        if not site or not preferences:

            intent["reason"] = (
                "\u0628\u062f\u0648\u0646 \u0627\u0637\u0644\u0627\u0639\u0627\u062a "
                "\u0632\u0645\u06cc\u0646\u060c \u062c\u0647\u062a \u0645\u0634\u062e\u0635 "
                "\u0646\u06cc\u0633\u062a"
                if lang == "fa"
                else "no site input, so no edge is determined"
            )

            return intent

        for preference in preferences:

            edge = _site_edge(site, preference)

            if edge:

                intent["edge_role"] = preference

                intent["edge"] = edge

                intent["determined"] = True

                intent["reason"] = "%s \u2192 %s" % (zone, edge)

                break

        if not intent["determined"]:

            intent["reason"] = (
                "\u0648\u0631\u0648\u062f\u06cc \u0632\u0645\u06cc\u0646 "
                "\u0644\u0628\u0647\u0654 \u0645\u0631\u0628\u0648\u0637 \u0628\u0647 "
                "\u0627\u06cc\u0646 \u0645\u0646\u0637\u0642\u0647 \u0631\u0627 "
                "\u0645\u0634\u062e\u0635 \u0646\u06a9\u0631\u062f\u0647 \u0627\u0633\u062a"
                if lang == "fa"
                else "the site input names no edge for this zone"
            )

        return intent

    # ------------------------------------------------------

    def _wire(self, bubble, bubbles, bubble_by_space, lang):

        space_id = bubble["space_id"]

        for other in bubbles:

            if other["bubble_id"] == bubble["bubble_id"]:

                continue

            relation = self.adjacency.relation(
                space_id, other["space_id"]
            )

            if not relation:

                continue

            relation_type = relation["relation_type"]

            entry = {
                "to_bubble": other["bubble_id"],
                "to_space": other["space_id"],
                "relation_type": relation_type,
                "short_type": SHORT_RELATION.get(
                    relation_type, relation_type
                ),
                "reason": relation.get("reason"),
                "confidence": relation.get("confidence"),
                "provenance": relation.get("provenance"),
            }

            bubble["connections"].append(entry)

            if relation_type in (REL_STRONG, REL_NORMAL):

                bubble["required_connections"].append(dict(entry))

            if relation_type in (REL_AVOID, REL_FORBIDDEN):

                bubble["forbidden_connections"].append(dict(entry))

            if relation_type in (REL_AVOID, REL_FORBIDDEN):

                bubble["separation_rules"].append(
                    {
                        "to": other["bubble_id"],
                        "to_space": other["space_id"],
                        "relation_type": relation_type,
                        "short_type": SHORT_RELATION.get(
                            relation_type, relation_type
                        ),
                        "reason": relation.get("reason"),
                    }
                )

            if relation_type == REL_FORBIDDEN:

                bubble["reasoning"].append(
                    "FORBIDDEN direct opening with %s: %s"
                    % (other["space_id"], relation.get("reason"))
                )

            elif relation_type == REL_AVOID:

                bubble["reasoning"].append(
                    "must not sit directly on %s: %s"
                    % (other["space_id"], relation.get("reason"))
                )

        control = self.privacy.requires_controlled_access(space_id)

        if control.get("required"):

            bubble["reasoning"].append(
                "controlled access required (%s)"
                % ", ".join(control.get("reasons") or [])
            )

    # ------------------------------------------------------

    def _importance(self, bubble):

        score = 0

        for connection in bubble["connections"]:

            if connection["relation_type"] == REL_STRONG:

                score += 2

            elif connection["relation_type"] == REL_NORMAL:

                score += 1

        zone = bubble["zone"]

        if zone in (ZONE_PUBLIC, ZONE_CIRCULATION):

            score += 2

        if zone == ZONE_PRIVATE:

            score += 1

        bubble["adjacency_weight"] = score

        if score >= 6:

            bubble["importance"] = IMPORTANCE_HIGH

        elif score >= 3:

            bubble["importance"] = IMPORTANCE_MEDIUM

        else:

            bubble["importance"] = IMPORTANCE_LOW

        # primary program spaces never fall below MEDIUM
        if (
            bubble["importance"] == IMPORTANCE_LOW
            and bubble["space_id"] in PRIMARY_SPACES
        ):

            bubble["importance"] = IMPORTANCE_MEDIUM

            bubble["importance_reason"] = (
                "primary program space (connection score %d)" % score
            )

            return

        bubble["importance_reason"] = (
            "connection score %d within this diagram" % score
        )

    # ------------------------------------------------------

    def _diagram_reasoning(self, program, site, bubbles, zones, lang):

        lines = []

        lines.append(
            "Program: %s with %s bedrooms, %d spaces."
            % (
                program["parsed"]["program"],
                program["bedrooms"],
                len(bubbles),
            )
        )

        for zone in zones:

            lines.append(
                "Zone %s holds %d space(s)."
                % (zone["name"], zone["count"])
            )

        if site:

            if site.get("access_edge"):

                lines.append(
                    "Access edge is %s, so the public zone and the "
                    "entrance belong there."
                    % site["access_edge"]
                )

            if site.get("protected_edges"):

                lines.append(
                    "Protected edge is %s, so the private zone belongs "
                    "there." % site["protected_edges"][0]
                )

        forbidden = [
            b["bubble_id"] for b in bubbles
            if any(
                r["relation_type"] == REL_FORBIDDEN
                for r in b["separation_rules"]
            )
        ]

        if forbidden:

            lines.append(
                "Forbidden direct openings involve: %s."
                % ", ".join(sorted(set(forbidden)))
            )

        return lines

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "diagram_type": DIAGRAM_TYPE,

            "relation_types": list(SHORT_RELATION.values()),

            "bubble_fields": (
                "bubble_id", "space_id", "space_type", "category",
                "privacy", "privacy_level", "zone", "importance",
                "adjacency_weight", "connections", "required_connections",
                "forbidden_connections", "separation_rules",
                "position_intent", "reasoning", "provenance",
            ),

            "contains_geometry": False,
            "contains_coordinates": False,

            "next_stage_not_started": (
                "floor plan / layout placement / walls / openings"
            ),
        }


bubble_diagram_builder = BubbleDiagramBuilderV1()
