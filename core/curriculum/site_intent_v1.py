# ==========================================================
# ArchitectOS Site Intent v1
#
# PHASE 11 — PART 4 — SITE AWARENESS INPUT
#
# Accepts SEMANTIC site constraints only. No coordinates, no polygons,
# no setbacks in metres, no geometry of any kind.
#
#   "زمین 10×20"        -> semantic dimensions
#   "خیابان جنوب"       -> south edge = ACCESS
#   "حیاط خلوت شمال"    -> north edge = OPEN (protected, quiet)
#
# Output is an INTENT: which edge is the access edge, which is the open
# edge, and therefore which zone should tend toward which edge.
#
# The direction / setback / open-space vocabulary is REUSED from
# core/knowledge/site_ontology.json (which already carries Persian
# synonyms) — this module does not invent a second vocabulary.
# ==========================================================


from __future__ import annotations


import re


from core.conversation.turn_semantics_v1 import match_form, script_of

from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)


CONTRACT = "SiteIntentV1"
VERSION = "1.0"


DIRECTIONS = ("north", "south", "east", "west")


# ----------------------------------------------------------
# EDGE ROLES
# ----------------------------------------------------------

EDGE_ACCESS = "ACCESS"
EDGE_OPEN = "OPEN"
EDGE_NEIGHBOUR = "NEIGHBOUR"
EDGE_DAYLIGHT = "DAYLIGHT"
EDGE_UNKNOWN = "UNKNOWN"


# Persian direction words (also present in site_ontology; duplicated
# here as match-form keys only, not as a second knowledge source).
DIRECTION_WORDS = {
    "north": (
        "\u0634\u0645\u0627\u0644",              # شمال
        "north",
    ),
    "south": (
        "\u062c\u0646\u0648\u0628",              # جنوب
        "south",
    ),
    "east": (
        "\u0634\u0631\u0642",                    # شرق
        "east",
    ),
    "west": (
        "\u063a\u0631\u0628",                    # غرب
        "west",
    ),
}


# Role markers: what the user says is on that edge.
ROLE_MARKERS = {
    EDGE_ACCESS: (
        "\u062e\u06cc\u0627\u0628\u0627\u0646",  # خیابان
        "\u06a9\u0648\u0686\u0647",              # کوچه
        "\u062f\u0633\u062a\u0631\u0633\u06cc",  # دسترسی
        "\u0628\u0631 \u062e\u06cc\u0627\u0628\u0627\u0646",  # بر خیابان
        "\u0648\u0631\u0648\u062f\u06cc \u0627\u0635\u0644\u06cc",  # ورودی اصلی
        "street",
        "road",
        "access",
        "entry",
        "main entrance",
    ),
    EDGE_OPEN: (
        "\u062d\u06cc\u0627\u0637 \u062e\u0644\u0648\u062a",  # حیاط خلوت
        "\u062d\u06cc\u0627\u0637",              # حیاط
        "\u0628\u0627\u063a",                    # باغ
        "\u0641\u0636\u0627\u06cc \u0628\u0627\u0632",  # فضای باز
        "\u0645\u062d\u0648\u0637\u0647",        # محوطه
        "\u067e\u0634\u062a \u0632\u0645\u06cc\u0646",  # پشت زمین
        "rear yard",
        "back yard",
        "garden",
        "open space",
        "yard",
        "courtyard",
    ),
    EDGE_NEIGHBOUR: (
        "\u0647\u0645\u0633\u0627\u06cc\u0647",  # همسایه
        "\u062f\u06cc\u0648\u0627\u0631 \u0647\u0645\u0633\u0627\u06cc\u0647",  # دیوار همسایه
        "\u0645\u062c\u0627\u0648\u0631",        # مجاور
        "neighbour",
        "neighbor",
        "adjacent building",
        "party wall",
    ),
    EDGE_DAYLIGHT: (
        "\u0646\u0648\u0631",                    # نور
        "\u0622\u0641\u062a\u0627\u0628",        # آفتاب
        "\u062c\u0646\u0648\u0628\u06cc",        # جنوبی (sun-facing)
        "\u0646\u0648\u0631\u06af\u06cc\u0631\u06cc",  # نورگیری
        "sunlight",
        "daylight",
        "solar",
        "sun",
    ),
}


# The protected side for the private zone when the user gives no clue.
DEFAULT_PROTECTED = ("north",)


class SiteIntentV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, read_bridge=None):

        self.read_bridge = read_bridge or knowledge_read_bridge

        print(
            "\U0001f9ed SITE INTENT v1.0 ONLINE "
            "(semantic edges only, no coordinates)"
        )

    # ======================================================
    # VOCABULARY (reused from the existing site ontology)
    # ======================================================

    def ontology_directions(self):

        payload = self.read_bridge.site_ontology() or {}

        return payload.get("directions") or {}

    # ======================================================
    # PARSE
    # ======================================================

    def parse(self, text, language=None):

        raw = str(text or "")

        form = match_form(raw)

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        dimensions = self._dimensions(raw)

        edges = self._edges(raw)

        access_edge = self._first(edges, EDGE_ACCESS)

        open_edges = self._all(edges, EDGE_OPEN)

        neighbour_edges = self._all(edges, EDGE_NEIGHBOUR)

        daylight_edges = self._all(edges, EDGE_DAYLIGHT)

        # ---- the protected side ----
        protected = []

        for edge in open_edges + neighbour_edges:

            if edge not in protected:

                protected.append(edge)

        if not protected:

            protected = [
                d for d in DEFAULT_PROTECTED if d not in (access_edge,)
            ]

        # ---- the open edge ----
        open_edge = open_edges[0] if open_edges else (
            protected[0] if protected else None
        )

        intents = self._intents(
            access_edge, open_edge, protected, daylight_edges, lang
        )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "raw_text": raw,
            "language": lang,

            "site": {
                "dimensions": dimensions,
                "orientation": None,
                "has_coordinates": False,
            },

            "edges": edges,

            "access_edge": access_edge,
            "open_edge": open_edge,
            "protected_edges": protected,
            "daylight_edges": daylight_edges,

            "intents": intents,

            "semantic_only": True,
            "contains_geometry": False,
            "contains_coordinates": False,
            "llm_used": False,
            "network_used": False,
        }

    # ------------------------------------------------------

    def _dimensions(self, raw):

        """Semantic dimensions.

        Runs on a form that PRESERVES the separator, because match_form
        strips the multiplication sign and "10×20" would collapse to
        "10 20".
        """

        form = str(raw or "").lower()

        for index, digit in enumerate(
            "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
        ):

            form = form.replace(digit, str(index))

        form = form.replace("\u00d7", "x").replace("*", "x")

        match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)", form
        )

        if not match:

            return None

        def number(value):

            value = value.replace(",", ".")

            try:

                return float(value)

            except ValueError:

                return None

        width = number(match.group(1))

        depth = number(match.group(2))

        if width is None or depth is None:

            return None

        return {
            "width": width,
            "depth": depth,
            "unit": "metre",
            "note": "semantic dimensions only \u2014 no coordinates",
        }

    # ------------------------------------------------------

    def _edges(self, raw):

        """Assign an edge role per direction, segment by segment.

        A role marker only applies to the direction stated WITH IT, so
        "خیابان جنوب، حیاط خلوت شمال" gives south=ACCESS and north=OPEN
        rather than both roles on both edges.
        """

        edges = {}

        segments = re.split(r"[,\u060c;\n\.\u061b]+", str(raw or ""))

        for segment in segments:

            form = match_form(segment)

            if not form:

                continue

            present = [
                direction for direction in DIRECTIONS
                if any(
                    word in form
                    for word in DIRECTION_WORDS[direction]
                )
            ]

            if not present:

                continue

            if len(present) == 1:

                self._assign(edges, present[0], form)

                continue

            # several directions in one segment: use a tight local window
            for direction in present:

                window = self._window(form, direction)

                self._assign(edges, direction, window)

        for direction, entry in edges.items():

            if not entry["roles"]:

                entry["roles"] = [EDGE_UNKNOWN]

            entry["role"] = entry["roles"][0]

        return edges

    def _window(self, form, direction):

        for word in DIRECTION_WORDS[direction]:

            start = form.find(word)

            if start == -1:

                continue

            return form[max(0, start - 18): start + len(word) + 8]

        return form

    def _assign(self, edges, direction, form):

        entry = edges.setdefault(
            direction, {"direction": direction, "roles": []}
        )

        for role, markers in ROLE_MARKERS.items():

            if any(marker in form for marker in markers):

                if role not in entry["roles"]:

                    entry["roles"].append(role)

    # ------------------------------------------------------

    def _first(self, edges, role):

        for direction in DIRECTIONS:

            entry = edges.get(direction)

            if entry and role in entry["roles"]:

                return direction

        return None

    def _all(self, edges, role):

        return [
            direction for direction in DIRECTIONS
            if edges.get(direction)
            and role in edges[direction]["roles"]
        ]

    # ------------------------------------------------------

    def _intents(self, access_edge, open_edge, protected, daylight, lang):

        intents = []

        def add(zone, toward, reason_en, reason_fa):

            if toward:

                intents.append(
                    {
                        "zone": zone,
                        "toward": toward,
                        "reason_en": reason_en,
                        "reason_fa": reason_fa,
                    }
                )

        if access_edge:

            add(
                "PUBLIC_ZONE",
                access_edge,
                "the entrance and public field belong on the access edge",
                "\u0648\u0631\u0648\u062f\u06cc \u0648 \u0639\u0631\u0635\u0647\u0654 "
                "\u0639\u0645\u0648\u0645\u06cc \u0628\u0627\u06cc\u062f \u062f\u0631 "
                "\u0637\u0631\u0641 \u062f\u0633\u062a\u0631\u0633\u06cc \u0628\u0627\u0634\u0646\u062f",
            )

        if protected:

            add(
                "PRIVATE_ZONE",
                protected[0],
                "private rooms belong toward the protected side",
                "\u0627\u062a\u0627\u0642\u200c\u0647\u0627\u06cc "
                "\u062e\u0635\u0648\u0635\u06cc \u0628\u0627\u06cc\u062f \u062f\u0631 "
                "\u0637\u0631\u0641 \u0645\u062d\u0641\u0648\u0638 \u0628\u0627\u0634\u0646\u062f",
            )

        if open_edge:

            add(
                "EXTERNAL_ZONE",
                open_edge,
                "open space sits on the open edge",
                "\u0641\u0636\u0627\u06cc \u0628\u0627\u0632 \u062f\u0631 \u0637\u0631\u0641 "
                "\u0628\u0627\u0632 \u0632\u0645\u06cc\u0646 \u0642\u0631\u0627\u0631 "
                "\u0645\u06cc\u200c\u06af\u06cc\u0631\u062f",
            )

        if access_edge:

            add(
                "CIRCULATION_ZONE",
                access_edge,
                "circulation starts at the arrival edge and distributes "
                "inward",
                "\u06af\u0631\u062f\u0634 \u0627\u0632 \u0637\u0631\u0641 "
                "\u0648\u0631\u0648\u062f \u0634\u0631\u0648\u0639 \u0645\u06cc\u200c\u0634\u0648\u062f "
                "\u0648 \u0628\u0647 \u062f\u0627\u062e\u0644 \u062a\u0648\u0632\u06cc\u0639 "
                "\u0645\u06cc\u200c\u0634\u0648\u062f",
            )

        if daylight:

            add(
                "SEMI_PUBLIC_ZONE",
                daylight[0],
                "semi-public spaces benefit from the daylight edge",
                "\u0641\u0636\u0627\u0647\u0627\u06cc "
                "\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc \u0627\u0632 "
                "\u0637\u0631\u0641 \u0646\u0648\u0631 \u0628\u0647\u0631\u0647 "
                "\u0645\u06cc\u200c\u0628\u0631\u0646\u062f",
            )

        return intents

    # ------------------------------------------------------

    def report(self):

        directions = self.ontology_directions()

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "edge_roles": [
                EDGE_ACCESS, EDGE_OPEN, EDGE_NEIGHBOUR,
                EDGE_DAYLIGHT, EDGE_UNKNOWN,
            ],

            "directions": list(DIRECTIONS),

            "ontology_directions_available": bool(directions),

            "semantic_only": True,
            "contains_geometry": False,
            "contains_coordinates": False,
        }


site_intent = SiteIntentV1()
