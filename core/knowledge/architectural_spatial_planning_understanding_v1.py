"""Architectural Spatial Planning Understanding (V1).

Understands HOW the spaces of a request are PLANNED — before any plan, any
geometry, any drawing.

    "یک خانه دوبلکس برای خانواده ۴ نفره می‌خواهم، زمین کوچک است،
     نور مهم است، حریم هم مهم است."
              ↓
    Building Intent  +  Spatial Planning Concept (conceptual floors)
    + relationships + fixed/flexible + the priority ladder
    + conceptual alternatives + context-dependent parameters
              ↓
    an UNDERSTANDING, spoken in words — never a plan

It
    extracts the required spaces from the intent
    organises them conceptually (which zone on which level)
    derives the relationships between spaces
    separates the FIXED from the FLEXIBLE
    reasons with the priority ladder (SAFETY → ESSENTIAL → QUALITY → OPTIONAL)
    offers SEVERAL conceptual alternatives — and never decides
    reads every number as a context-dependent PARAMETER, never a constant

It MUST NOT
    produce a plan / geometry / coordinates / walls / CAD / BIM / IFC / a render
    generate a design, place anything, or select final dimensions
    turn a stated number into an absolute architectural law
    write anything into the knowledge memory
    decide the design — the human architect remains the final decision maker

Reuse (never reinvent)
    architectural_intent_understanding_v1        -> the request reading
    architectural_spatial_organization_v1        -> zones + relationships
    architectural_associative_retrieval_v1       -> SPACE_SURFACE + retrieval
    architectural_reasoning_v1 / _quality_v1     -> the priority ladder, fixed/flexible, conflicts
    core.curriculum.space_types_v1 / zone_model_v1 -> the corpus + the 6 zones
    core.curriculum.site_intent_v1               -> the semantic site condition
    core.curriculum.bubble_diagram_v1            -> the program spaces (read-only)

Dependency direction

    this module  ->  core.curriculum / core.knowledge / core.conversation only
    this module  ->  core.vision / core.render / core.rendering / core.cad / core.bim /
                     core.ifc / core.geometry / core.spatial / core.ai / core.runtime  FORBIDDEN
"""

from __future__ import annotations


import re


from typing import Any, Dict, List, Optional, Tuple


from core.curriculum.zone_model_v1 import (
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    ZONE_PRIVATE,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_SERVICE,
    zone_display,
)

from core.curriculum.site_intent_v1 import site_intent

from core.curriculum.bubble_diagram_v1 import bubble_diagram_builder

from core.knowledge.architectural_intent_understanding_v1 import (
    CONTRACT as INTENT_CONTRACT,
    understand_intent,
)

from core.knowledge.architectural_spatial_organization_v1 import (
    CONTRACT as SPATIAL_ORGANIZATION_CONTRACT,
    classify_space,
    derive_relationships,
    understand_spatial_organization,
)

from core.knowledge.architectural_associative_retrieval_v1 import (
    SPACE_SURFACE,
    associative_retrieve,
)

from core.knowledge.architectural_reasoning_v1 import (
    ALTERNATIVES_BY_FEATURE,
    FIXED_TOKENS,
    FLEXIBLE_TOKENS,
    PRIORITY_BY_TOKEN,
    PRIORITY_ESSENTIAL,
    PRIORITY_OPTIONAL,
    PRIORITY_ORDER,
    PRIORITY_QUALITY,
    PRIORITY_SAFETY,
    reason_design,
)

from core.knowledge.architectural_reasoning_quality_v1 import improve_reasoning


CONTRACT = "ArchitecturalSpatialPlanningUnderstandingV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the conceptual levels (a level is a REASONING grouping, never a shape)
# ----------------------------------------------------------

LEVEL_GROUND = "GROUND_FLOOR"

LEVEL_UPPER = "UPPER_FLOOR"

LEVEL_MAIN = "MAIN_LEVEL"


LEVEL_DISPLAY = {
    LEVEL_GROUND: {"fa": "طبقهٔ همکف", "en": "ground floor"},
    LEVEL_UPPER: {"fa": "طبقهٔ بالا", "en": "upper floor"},
    LEVEL_MAIN: {"fa": "طبقهٔ اصلی", "en": "main level"},
}


# which zones tend to sit on which conceptual level of a multi-level house
GROUND_ZONES = (ZONE_PUBLIC, ZONE_SEMI_PUBLIC, ZONE_SERVICE, ZONE_CIRCULATION, ZONE_EXTERNAL)

UPPER_ZONES = (ZONE_PRIVATE, ZONE_CIRCULATION)


def level_display(level, language="en"):

    entry = LEVEL_DISPLAY.get(level) or {}

    return entry.get("fa" if str(language or "").startswith("fa") else "en") or str(level)


# ----------------------------------------------------------
# the fixed / flexible vocabulary (reused tokens + the access concept)
# ----------------------------------------------------------

FIXED_KINDS = tuple(FIXED_TOKENS) + ("access", "required_access", "circulation")

FLEXIBLE_KINDS = tuple(FLEXIBLE_TOKENS) + ("optional_room", "extra_room")


# ----------------------------------------------------------
# the priority ladder (the brief's order, reused verbatim)
# ----------------------------------------------------------

SPATIAL_PRIORITY_ORDER = PRIORITY_ORDER

PRIORITY_LABELS = {
    "fa": {
        PRIORITY_SAFETY: "ایمنی",
        PRIORITY_ESSENTIAL: "عملکرد ضروری",
        PRIORITY_QUALITY: "کیفیت فضایی",
        PRIORITY_OPTIONAL: "ویژگی اختیاری",
    },
    "en": {
        PRIORITY_SAFETY: "safety",
        PRIORITY_ESSENTIAL: "essential function",
        PRIORITY_QUALITY: "spatial quality",
        PRIORITY_OPTIONAL: "optional feature",
    },
}


# ----------------------------------------------------------
# the two conceptual alternatives (the brief's Option A / Option B)
# ----------------------------------------------------------

CONCEPTUAL_ALTERNATIVES = (
    {
        "id": "A",
        "concept": "central_circulation",
        "label": {"fa": "گردشِ مرکزی", "en": "central circulation"},
        "gains": {"fa": ["ارتباطِ بهتر"], "en": ["better connection"]},
        "costs": {"fa": ["حریمِ کمتر"], "en": ["less privacy"]},
        "trade_offs": {"fa": ["ارتباط در برابر حریم"], "en": ["connection vs privacy"]},
    },
    {
        "id": "B",
        "concept": "separated_private_zone",
        "label": {"fa": "جداسازیِ منطقهٔ خصوصی", "en": "separated private zone"},
        "gains": {"fa": ["حریمِ بالاتر"], "en": ["higher privacy"]},
        "costs": {"fa": ["نیاز به مساحتِ بیشتر"], "en": ["requires more area"]},
        "trade_offs": {"fa": ["حریم در برابر مساحت"], "en": ["privacy vs area"]},
    },
)


# ----------------------------------------------------------
# markers (the planning-level reading)
# ----------------------------------------------------------

AREA_LIMIT_MARKERS = (
    "کوچک", "کوچیک", "محدود", "کم", "تنگ", "small", "limited", "tight", "compact",
)

AREA_DEMAND_MARKERS = (
    "بزرگ", "بزرگتر", "گسترده", "بیشتر", "حداکثر", "وسیع",
    "large", "big", "bigger", "larger", "maximize", "maximise", "spacious",
)

PREFERENCE_MARKERS = (
    "دوست دارم", "ترجیح", "می پسندم", "میپسندم", "علاقه دارم",
    "prefer", "i like", "i want", "would like", "my preference",
)

PRIVACY_MARKERS = ("حریم", "خصوصی", "privacy", "private")

DAYLIGHT_MARKERS = ("نور", "روشنایی", "نورگیر", "daylight", "light", "lightwell")

CONTEXT_MARKERS = (
    "آموزش", "شرایط", "زمین", "این پروژه", "در این",
    "teaching", "condition", "site", "project", "this",
)

# a site condition is only reported when the request actually names an orientation
DIRECTION_MARKERS = (
    "شمال", "جنوب", "شرق", "غرب",
    "north", "south", "east", "west",
)

FORBIDDEN_TERMS = (
    "geometry", "polygon", "coordinate", "coordinates", "dimension", "dimensions",
    "cad", "dwg", "bim", "ifc", "revit", "wall", "walls", "render",
)


FLOOR_WORDS = {
    "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "two": 2, "three": 3, "four": 4, "five": 5,
}


NUMBER_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


HOUSEHOLD_UNIT = "نفره|نفر|نفرى|person|people|member|members"


# A colloquial spelling is a SURFACE form of the same building type — it is not a
# second piece of architectural knowledge.
COLLOQUIAL_BUILDING_TYPE = {
    "خونه": "residential",
    "واحد": "residential",
}


_NON_CLAIMS = {
    "not_a_plan": True,
    "not_geometry": True,
    "not_coordinates": True,
    "not_walls": True,
    "not_cad_or_bim": True,
    "not_a_render": True,
    "not_a_design": True,
    "not_invented": True,
    "confirmed_memory_only": True,
    "human_decides": True,
}


PLANNING_HEADER = {
    "fa": "این برنامه‌ریزیِ فضایی را از درخواست شما برداشت کردم:",
    "en": "This is the spatial planning I read from your request:",
}

PLANNING_FOOTER = {
    "fa": "تصمیم نهایی با معمار است.",
    "en": "The architect makes the final decision.",
}


class ArchitecturalSpatialPlanningUnderstandingError(ValueError):
    """Raised when the spatial-planning boundary is misused."""


# ----------------------------------------------------------
# small helpers
# ----------------------------------------------------------

def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _has_any(text, markers) -> bool:

    form = _norm(text)

    return any(_norm(marker) in form for marker in markers)


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _ascii_digits(text) -> str:

    result = []

    for char in str(text or ""):

        code = ord(char)

        if 0x06F0 <= code <= 0x06F9:          # Persian digits

            result.append(chr(ord("0") + code - 0x06F0))

        elif 0x0660 <= code <= 0x0669:        # Arabic-Indic digits

            result.append(chr(ord("0") + code - 0x0660))

        else:

            result.append(char)

    return "".join(result)


def _unique(values) -> List[str]:

    result: List[str] = []

    for value in values:

        if value and value not in result:

            result.append(value)

    return result


def _fa_list(items) -> str:

    items = [str(i) for i in items if i]

    if not items:

        return ""

    if len(items) == 1:

        return items[0]

    return "، ".join(items[:-1]) + " و " + items[-1]


def _en_list(items) -> str:

    items = [str(i) for i in items if i]

    if not items:

        return ""

    if len(items) == 1:

        return items[0]

    return ", ".join(items[:-1]) + " and " + items[-1]


def _join(items, language="fa") -> str:

    return _en_list(items) if _language(language) == "en" else _fa_list(items)


def _label(entry, language="fa") -> Any:

    """A {fa,en} label entry -> the requested language, else the entry itself."""

    if isinstance(entry, dict):

        return entry.get(_language(language)) or entry.get("fa") or entry.get("en")

    return entry


def _localize(value, language="fa"):

    if isinstance(value, dict) and ("fa" in value or "en" in value):

        return _label(value, language)

    if isinstance(value, list):

        return [_localize(v, language) for v in value]

    return value


# ----------------------------------------------------------
# TASK 1 — Building Intent (spaces + floors + site condition)
# ----------------------------------------------------------

def detect_floors(text, building_type=None) -> int:

    """The conceptual number of levels. A stated count wins; else the type."""

    form = _norm(_ascii_digits(text))

    match = re.search(
        r"(\d+)\s*(?:طبقه|طبقات|floor|floors|storey|storeys|story|stories)", form
    )

    if match:

        value = int(match.group(1))

        if value >= 1:

            return value

    for word, value in FLOOR_WORDS.items():

        if re.search(r"%s\s*(?:طبقه|floor)" % _norm(word), form):

            return value

    if _norm(building_type) == "duplex":

        return 2

    return 1


def detect_household(request) -> Dict[str, Any]:

    """The household size, from a digit OR a spoken number ("چهار نفر")."""

    form = _norm(_ascii_digits(request))

    match = re.search(r"([0-9]+)\s*(?:%s)" % HOUSEHOLD_UNIT, form)

    if match:

        return {"size": int(match.group(1))}

    for word, value in NUMBER_WORDS.items():

        if re.search(r"%s\s*(?:%s)" % (_norm(word), HOUSEHOLD_UNIT), form):

            return {"size": value}

    return {}


def detect_building_type(request, fallback=None):

    """The intent's building type, or a colloquial surface form of the same type."""

    if fallback:

        return fallback

    form = _norm(request)

    for surface, building_type in COLLOQUIAL_BUILDING_TYPE.items():

        if _norm(surface) in form:

            return building_type

    return None


def extract_spaces(intent, *, request="", language="fa", building_type=None) -> Tuple[List[str], List[str], List[str]]:

    """The required spaces, resolved to the corpus. If the request names none, the
    residential program is read (read-only) from the curriculum. Nothing invented."""

    raw = _unique(list((intent.get("intent") or {}).get("program") or []))

    if not raw:

        if building_type is None:

            building_type = (intent.get("intent") or {}).get("building_type")

        if _norm(building_type) in (
            "residential", "villa", "duplex", "apartment", "penthouse", ""
        ):

            try:

                parsed = bubble_diagram_builder.program_spaces(request, language=language)

            except Exception:  # noqa: BLE001 — the program is an enrichment, never fatal

                parsed = {}

            raw = _unique(list(parsed.get("space_ids") or []))

    spaces: List[str] = []

    unclassified: List[str] = []

    for term in raw:

        resolved = classify_space(term)

        space_id = resolved.get("space_id")

        if space_id:

            if space_id not in spaces:

                spaces.append(space_id)

        elif str(term).strip() not in unclassified:

            unclassified.append(str(term).strip())

    notes = [] if spaces else ["no space could be resolved from the request"]

    return spaces, unclassified, notes


def read_site_condition(request, *, language="fa") -> Dict[str, Any]:

    """The semantic site condition — no coordinates, no dimensions.

    A condition is reported ONLY when the request actually names an orientation;
    the site reader's default edge is never presented as a finding."""

    if not request or not _has_any(request, DIRECTION_MARKERS):

        return {}

    try:

        parsed = site_intent.parse(request, language=language)

    except Exception:  # noqa: BLE001 — site reading is an enrichment, never fatal

        return {}

    if not isinstance(parsed, dict):

        return {}

    return {
        "orientation": (parsed.get("site") or {}).get("orientation"),
        "access_edge": parsed.get("access_edge"),
        "open_edge": parsed.get("open_edge"),
        "protected_edges": list(parsed.get("protected_edges") or []),
        "daylight_edges": list(parsed.get("daylight_edges") or []),
        "zone_intents": list(parsed.get("intents") or []),
    }


def detect_daylight_strategy(spaces, request) -> Optional[str]:

    """A lightwell (or a stated daylight need) is a SPATIAL STRATEGY — never a size."""

    tokens = {_norm(s).replace("_", " ") for s in spaces or []}

    if "lightwell" in tokens or "light well" in tokens:

        return "central_lightwell"

    if _has_any(request, ("نورگیری مرکزی", "central light", "lightwell", "نورگیر")):

        return "central_lightwell"

    return None


# ----------------------------------------------------------
# TASK 2 — the spatial planning concept (conceptual levels + zones)
# ----------------------------------------------------------

def build_spatial_planning_concept(spaces, floors, *, language="fa") -> Dict[str, Any]:

    """Group the spaces into zones, then place the zones on conceptual levels.

    This is a REASONING grouping. There is no coordinate, no wall and no shape."""

    zone_spaces: Dict[str, List[str]] = {}

    unclassified: List[str] = []

    for term in spaces or []:

        resolved = classify_space(term)

        space_id = resolved.get("space_id") or str(term)

        zone = resolved.get("zone")

        if zone:

            zone_spaces.setdefault(zone, [])

            if space_id not in zone_spaces[zone]:

                zone_spaces[zone].append(space_id)

        elif space_id not in unclassified:

            unclassified.append(space_id)

    levels: List[Dict[str, Any]] = []

    if floors and floors >= 2:

        ground = {
            zone: list(zone_spaces[zone])
            for zone in GROUND_ZONES
            if zone_spaces.get(zone)
        }

        upper = {
            zone: list(zone_spaces[zone])
            for zone in UPPER_ZONES
            if zone_spaces.get(zone)
        }

        levels.append(
            {
                "level": LEVEL_GROUND,
                "label": level_display(LEVEL_GROUND, language),
                "zones": ground,
                "access_note": "the public, semi-public and service zones sit on the entry level",
            }
        )

        levels.append(
            {
                "level": LEVEL_UPPER,
                "label": level_display(LEVEL_UPPER, language),
                "zones": upper,
                "access_note": "the private zone sits on the upper level, away from arrival",
            }
        )

    else:

        ordered = {
            zone: list(zone_spaces[zone])
            for zone in (
                ZONE_PUBLIC, ZONE_SEMI_PUBLIC, ZONE_SERVICE, ZONE_CIRCULATION,
                ZONE_PRIVATE, ZONE_EXTERNAL,
            )
            if zone_spaces.get(zone)
        }

        levels.append(
            {
                "level": LEVEL_MAIN,
                "label": level_display(LEVEL_MAIN, language),
                "zones": ordered,
                "access_note": "the zones are ordered from arrival toward the protected side",
            }
        )

    circulation = build_circulation(floors, zone_spaces)

    return {
        "levels": levels,
        "zones": zone_spaces,
        "unclassified": unclassified,
        "circulation": circulation,
    }


def build_circulation(floors, zone_spaces) -> Dict[str, Any]:

    circulation_spaces = list(zone_spaces.get(ZONE_CIRCULATION) or [])

    if floors and floors >= 2:

        return {
            "vertical_core": "stair",
            "is_fixed": True,
            "connects_levels": [LEVEL_GROUND, LEVEL_UPPER],
            "spaces": circulation_spaces,
            "reason": "the vertical core links the levels and stays fixed",
        }

    return {
        "vertical_core": None,
        "is_fixed": bool(circulation_spaces),
        "connects_levels": [LEVEL_MAIN],
        "spaces": circulation_spaces,
        "reason": "circulation connects the zones on the single level",
    }


# ----------------------------------------------------------
# TASK 3 — relationships (reused from the spatial organization)
# ----------------------------------------------------------

def build_relationships(spaces, floors, *, language="fa") -> List[Dict[str, Any]]:

    relationships = derive_relationships(spaces)

    if floors and floors >= 2:

        relationships = list(relationships) + [
            {
                "a": "stair",
                "b": LEVEL_UPPER,
                "a_zone": ZONE_CIRCULATION,
                "b_zone": None,
                "kind": "connected",
                "fixed": True,
                "note": "the vertical core links the entry level to the upper level",
            }
        ]

    return relationships


# ----------------------------------------------------------
# TASK 4 — fixed vs flexible
# ----------------------------------------------------------

def build_fixed_flexible(intent, spaces, circulation, *, language="fa") -> Dict[str, Any]:

    request = str(intent.get("request") or "")

    fixed = _unique(list(intent.get("fixed_elements") or []))

    flexible = _unique(list(intent.get("flexible_elements") or []))

    form = _norm(request)

    for token in FIXED_KINDS:

        if _norm(token).replace("_", " ") in form and token not in fixed:

            fixed.append(token)

    for token in FLEXIBLE_KINDS:

        if _norm(token).replace("_", " ") in form and token not in flexible:

            flexible.append(token)

    if circulation.get("is_fixed") and "stair" not in fixed:

        fixed.append("stair")

    return {
        "fixed": fixed,
        "flexible": flexible,
        "rule": (
            "a flexible need must never damage a fixed or essential element"
        ),
    }


# ----------------------------------------------------------
# TASK 5 — priority reasoning
# ----------------------------------------------------------

def priority_of(token) -> str:

    """The priority of an element, from the shared table.

    A required space that is not named in the table defaults to the essential
    function rung — the ladder never silently drops a required space."""

    form = _norm(token).replace("_", " ")

    words = set(form.split())

    for candidate, priority in PRIORITY_BY_TOKEN.items():

        key = _norm(candidate).replace("_", " ")

        if key == form or key in words:

            return priority

    return PRIORITY_ESSENTIAL


def build_priority_reasoning(fixed_flexible, spaces, request, *, language="fa") -> List[Dict[str, Any]]:

    reasoning: List[Dict[str, Any]] = []

    def add(element, priority, reason):

        if element and not any(r["element"] == element for r in reasoning):

            reasoning.append(
                {"element": element, "priority": priority, "reason": reason}
            )

    for element in fixed_flexible["fixed"]:

        add(element, priority_of(element), "a fixed element holds its function")

    for space_id in spaces or []:

        add(space_id, priority_of(space_id), "a required space serves an essential function")

    if _has_any(request, PRIVACY_MARKERS):

        add("privacy", PRIORITY_QUALITY, "privacy is a spatial quality the request stresses")

    if _has_any(request, DAYLIGHT_MARKERS):

        add("daylight", PRIORITY_QUALITY, "daylight is a spatial quality the request stresses")

    for element in fixed_flexible["flexible"]:

        add(element, priority_of(element), "an optional feature is reconsidered, never forced")

    reasoning.sort(key=lambda r: PRIORITY_ORDER.index(r["priority"]))

    return reasoning


# ----------------------------------------------------------
# TASK 6 — conceptual alternatives
# ----------------------------------------------------------

def build_conceptual_alternatives(zone_spaces, reasoning_alternatives, *, language="fa") -> List[Dict[str, Any]]:

    alternatives: List[Dict[str, Any]] = []

    if zone_spaces.get(ZONE_PRIVATE):

        for entry in CONCEPTUAL_ALTERNATIVES:

            alternatives.append(
                {
                    "id": entry["id"],
                    "concept": entry["concept"],
                    "label": _localize(entry["label"], language),
                    "gains": _localize(entry["gains"], language),
                    "costs": _localize(entry["costs"], language),
                    "trade_offs": _localize(entry["trade_offs"], language),
                    "is_final": False,
                }
            )

    for entry in reasoning_alternatives or []:

        label = entry.get("label")

        if not label or any(a["label"] == label for a in alternatives):

            continue

        alternatives.append(
            {
                "id": None,
                "concept": "optional_feature_alternative",
                "label": label,
                "gains": list(entry.get("advantages") or []),
                "costs": list(entry.get("disadvantages") or []),
                "trade_offs": [],
                "is_final": False,
            }
        )

    return alternatives


# ----------------------------------------------------------
# TASK 7 — context-dependent parameters (a number is never a constant)
# ----------------------------------------------------------

PARAMETER_PATTERNS = (
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*(متر\s*مربع|مترمربع|م2|m2|m²|sqm|square\s*met(?:er|re)s?)"
        ),
        "area",
        "m2",
    ),
    (
        re.compile(r"(\d+(?:[.,]\d+)?)\s*(متر|متری|met(?:er|re)s?|\bm\b)"),
        "length",
        "m",
    ),
    (
        re.compile(r"(\d+)\s*(طبقه|طبقات|floor|floors|storey|storeys|story|stories)"),
        "levels",
        "count",
    ),
    (
        re.compile(r"(\d+)\s*(نفره|نفر|person|people|member|members)"),
        "household",
        "count",
    ),
)


PARAMETER_ROLE = {
    "area": {"fa": "مساحت", "en": "area"},
    "length": {"fa": "عرض/طول", "en": "length"},
    "levels": {"fa": "تعداد طبقات", "en": "number of levels"},
    "household": {"fa": "تعداد نفرات", "en": "household size"},
}


def extract_parameters(request, *, language="fa") -> List[Dict[str, Any]]:

    """Every number is a PARAMETER for this condition — never a constant."""

    form = _norm(_ascii_digits(request))

    contextualized = _has_any(request, CONTEXT_MARKERS)

    parameters: List[Dict[str, Any]] = []

    for pattern, role, unit in PARAMETER_PATTERNS:

        for match in pattern.finditer(form):

            # a length match that is really the head of an area phrase is skipped
            if role == "length":

                tail = form[match.end():match.end() + 8]

                if re.match(r"\s*(?:مربع|مربعی|2|²|square)", tail):

                    continue

            value = match.group(1).replace(",", ".")

            key = (role, value, unit)

            if any((p["role"], p["value"], p["unit"]) == key for p in parameters):

                continue

            parameters.append(
                {
                    "name": role,
                    "role": _localize(PARAMETER_ROLE[role], language),
                    "value": value,
                    "unit": unit,
                    "is_constant": False,
                    "contextualized": contextualized,
                    "note": (
                        "برای این شرایط، %s = %s %s یک مقدار پیشنهادی است، نه یک ثابت."
                        % (_localize(PARAMETER_ROLE[role], "fa"), value, unit)
                        if _language(language) == "fa"
                        else "for this condition, %s = %s %s is a suggested value, "
                             "not a constant." % (_localize(PARAMETER_ROLE[role], "en"), value, unit)
                    ),
                }
            )

    return parameters


# ----------------------------------------------------------
# TASK 8 — the planning-level conflicts (reported, never solved)
# ----------------------------------------------------------

def build_planning_conflicts(intent, fixed_flexible, zone_spaces, request, *, language="fa"):

    conflicts: List[Dict[str, Any]] = []

    area_limited = _has_any(request, AREA_LIMIT_MARKERS) or bool(intent.get("constraint"))

    area_demand = _has_any(request, AREA_DEMAND_MARKERS)

    if area_limited and area_demand:

        conflicts.append(
            {
                "kind": "area_limitation",
                "priority": PRIORITY_ESSENTIAL,
                "statement": (
                    "با توجه به محدودیتِ مساحت، حفظِ عملکردِ فضاهای ضروری اولویتِ بالاتری "
                    "دارد و برای عنصرِ اختیاری راهکارِ جایگزین بررسی می‌شود."
                    if _language(language) == "fa"
                    else "given the limited area, keeping the essential function has a higher "
                         "priority; the optional feature is reconsidered with an alternative."
                ),
                "between": list(intent.get("constraint") or []) + list(intent.get("preference") or []),
            }
        )

    if area_limited and fixed_flexible["flexible"]:

        conflicts.append(
            {
                "kind": "area_vs_optional",
                "priority": PRIORITY_OPTIONAL,
                "statement": (
                    "نیازِ انعطاف‌پذیر (اختیاری) نباید به فضاهای ضروری آسیب بزند؛ گزینه‌های "
                    "جایگزین برای آن بررسی می‌شود."
                    if _language(language) == "fa"
                    else "the flexible (optional) need must not damage the essential spaces; "
                         "an alternative is explored for it."
                ),
                "between": list(fixed_flexible["flexible"]),
            }
        )

    if fixed_flexible["fixed"] and fixed_flexible["flexible"]:

        conflicts.append(
            {
                "kind": "fixed_vs_flexible",
                "priority": PRIORITY_SAFETY,
                "statement": (
                    "عنصرِ ثابت (مثل راه‌پله) دست‌نخورده می‌ماند؛ نیازِ انعطاف‌پذیر با یک "
                    "راهکارِ انعطاف‌پذیر حل می‌شود، نه با کوچک‌کردنِ عنصرِ ثابت."
                    if _language(language) == "fa"
                    else "the fixed element (such as the stair) stays untouched; the flexible "
                         "need is solved flexibly, not by shrinking the fixed element."
                ),
                "between": list(fixed_flexible["fixed"]) + list(fixed_flexible["flexible"]),
            }
        )

    if _has_any(request, PRIVACY_MARKERS) and _has_any(request, DAYLIGHT_MARKERS):

        conflicts.append(
            {
                "kind": "privacy_daylight_tradeoff",
                "priority": PRIORITY_QUALITY,
                "statement": (
                    "حریم و نورگیری همزمان کشیده می‌شوند؛ باید بین آن‌ها تعادل ایجاد شود."
                    if _language(language) == "fa"
                    else "privacy and daylight pull at the same time; a balance between them "
                         "is to be explored."
                ),
                "between": ["privacy", "daylight"],
            }
        )

    return conflicts


# ----------------------------------------------------------
# the natural planning (spoken, never a form / JSON / schema)
# ----------------------------------------------------------

def _dedupe_conflicts(conflicts) -> List[Dict[str, Any]]:

    """Keep one conflict per kind — the planning reading wins over the inherited one."""

    result: List[Dict[str, Any]] = []

    seen = set()

    for conflict in conflicts or []:

        if not isinstance(conflict, dict):

            continue

        kind = conflict.get("kind")

        if kind in seen:

            continue

        seen.add(kind)

        result.append(conflict)

    return result


def build_natural_planning(result, *, language="fa") -> str:

    lang = _language(language)

    lines = [PLANNING_HEADER[lang]]

    intent = result["building_intent"]

    if intent.get("building_type"):

        text = str(intent["building_type"])

        if intent.get("household", {}).get("size"):

            text += " — %d" % intent["household"]["size"]

        lines.append("• نوع پروژه: %s" % text if lang == "fa" else "• project type: %s" % text)

    if intent.get("floors"):

        lines.append(
            "• تعداد طبقاتِ برداشت‌شده: %d" % intent["floors"]
            if lang == "fa"
            else "• levels read: %d" % intent["floors"]
        )

    concept = result["spatial_planning_concept"]

    for level in concept["levels"]:

        parts = []

        for zone, spaces in level["zones"].items():

            parts.append(
                "%s: %s" % (zone_display(zone, lang), "، ".join(spaces))
                if lang == "fa"
                else "%s: %s" % (zone_display(zone, lang), ", ".join(spaces))
            )

        if parts:

            lines.append(
                "• %s — %s" % (level["label"], " · ".join(parts))
            )

    circulation = concept.get("circulation") or {}

    if circulation.get("vertical_core"):

        lines.append(
            "• هستهٔ عمودی (راه‌پله) طبقات را وصل می‌کند و ثابت است."
            if lang == "fa"
            else "• the vertical core (the stair) links the levels and stays fixed."
        )

    site = concept.get("site_condition") or {}

    if site.get("open_edge") or site.get("protected_edges"):

        edges = _join(
            [site.get("open_edge")] + list(site.get("protected_edges") or []), lang
        )

        lines.append(
            "• شرطِ زمین: لبهٔ %s خوانده شد." % edges
            if lang == "fa"
            else "• site condition: the %s edge was read." % edges
        )

    if concept.get("daylight_strategy") == "central_lightwell":

        lines.append(
            "• راهبردِ نور: نورگیرِ مرکزی به‌عنوان راهکارِ نورگیری در نظر گرفته می‌شود."
            if lang == "fa"
            else "• daylight strategy: a central lightwell is considered as the daylight move."
        )

    # ---- the balance sentence (the human acceptance criterion) ----
    facets = []

    if _has_any(result.get("request"), DAYLIGHT_MARKERS):

        facets.append("نورگیری" if lang == "fa" else "daylight")

    if _has_any(result.get("request"), PRIVACY_MARKERS):

        facets.append("حریم" if lang == "fa" else "privacy")

    if _has_any(result.get("request"), AREA_LIMIT_MARKERS) or result["building_intent"].get("area_limited"):

        facets.append("محدودیتِ مساحت" if lang == "fa" else "the limited area")

    if len(facets) >= 2:

        lines.append(
            "برداشت من این است که باید بین %s تعادل ایجاد شود." % _fa_list(facets)
            if lang == "fa"
            else "I read this as a balance to be found between %s." % _en_list(facets)
        )

    # ---- the public / private separation ----
    if ZONE_PUBLIC in concept["zones"] and ZONE_PRIVATE in concept["zones"]:

        lines.append(
            "فضاهای عمومی و خصوصی باید جدا شوند و راهکارهای مختلف قابل بررسی هستند."
            if lang == "fa"
            else "the public and the private areas are to be separated, and several "
                 "approaches can be explored."
        )

    # ---- fixed / flexible ----
    ff = result["fixed_flexible"]

    if ff["fixed"] or ff["flexible"]:

        lines.append(
            "• ثابت: %s — انعطاف‌پذیر: %s"
            % (
                _join(ff["fixed"], lang) or "-",
                _join(ff["flexible"], lang) or "-",
            )
            if lang == "fa"
            else "• fixed: %s — flexible: %s"
            % (
                _join(ff["fixed"], lang) or "-",
                _join(ff["flexible"], lang) or "-",
            )
        )

    # ---- the priority ladder ----
    labels = PRIORITY_LABELS[lang]

    lines.append(
        "• اولویت‌ها: " + " → ".join(labels[p] for p in SPATIAL_PRIORITY_ORDER)
        if lang == "fa"
        else "• priorities: " + " → ".join(labels[p] for p in SPATIAL_PRIORITY_ORDER)
    )

    # ---- the context-dependent parameters (a number is a suggestion, not a law) ----
    parameters = result.get("context_dependent_parameters") or []

    if parameters:

        rendered = [
            "%s = %s %s" % (p["role"], p["value"], p["unit"]) for p in parameters
        ]

        lines.append(
            "• پارامترها (مقدارِ پیشنهادی برای این شرایط، نه ثابت): " + _join(rendered, lang)
            if lang == "fa"
            else "• parameters (suggested for this condition, not constant): "
                 + _join(rendered, lang)
        )

    # ---- the conceptual alternatives ----
    alternatives = result["conceptual_alternatives"]

    if alternatives:

        rendered = [
            "%s: %s (%s)" % (a["label"], _join(a["gains"], lang), _join(a["costs"], lang))
            for a in alternatives[:3]
        ]

        lines.append(
            "• گزینه‌های مفهومی: " + " · ".join(rendered)
            if lang == "fa"
            else "• conceptual alternatives: " + " · ".join(rendered)
        )

    # ---- the trade-offs that must be said out loud (never a decision) ----
    conflicts = sorted(
        result.get("conflicts") or [],
        key=lambda c: PRIORITY_ORDER.index(c.get("priority") or PRIORITY_OPTIONAL),
    )

    for conflict in conflicts[:2]:

        statement = conflict.get("statement")

        if not statement:

            continue

        lines.append(
            "• نکته: %s" % statement if lang == "fa" else "• note: %s" % statement
        )

    lines.append(PLANNING_FOOTER[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def _resolve_sources(source, *, memory, lang):

    """Accept a request string, an intent result, or a spatial-organization result."""

    if isinstance(source, dict) and source.get("contract") == SPATIAL_ORGANIZATION_CONTRACT:

        organization = source

        intent = understand_intent(
            str(source.get("request") or ""), memory=memory, language=lang
        )

        return intent, organization

    if isinstance(source, dict) and source.get("contract") == INTENT_CONTRACT:

        intent = source

        organization = understand_spatial_organization(intent, memory=memory, language=lang)

        return intent, organization

    if isinstance(source, str) and source.strip():

        intent = understand_intent(source, memory=memory, language=lang)

        organization = understand_spatial_organization(intent, memory=memory, language=lang)

        return intent, organization

    raise ArchitecturalSpatialPlanningUnderstandingError(
        "spatial planning needs a non-empty request string, an intent result or a "
        "spatial-organization result"
    )


def understand_spatial_planning(source, *, memory=None, language=None) -> Dict[str, Any]:

    """Read a request as a conceptual SPATIAL PLANNING — never a plan."""

    if isinstance(source, str):

        probe = source

    elif isinstance(source, dict):

        probe = str(source.get("request") or "")

    else:

        raise ArchitecturalSpatialPlanningUnderstandingError(
            "unsupported source type: %s" % (type(source).__name__,)
        )

    if not str(probe).strip():

        raise ArchitecturalSpatialPlanningUnderstandingError(
            "spatial planning needs a non-empty request"
        )

    lang = _language(language or ("en" if str(probe).isascii() else "fa"))

    intent, organization = _resolve_sources(source, memory=memory, lang=lang)

    request = str(intent.get("request") or probe)

    # ---- TASK 1 — building intent ----
    building_type = detect_building_type(
        request, fallback=(intent.get("intent") or {}).get("building_type")
    )

    household = dict((intent.get("intent") or {}).get("household") or {})

    if not household:

        household = detect_household(request)

    floors = detect_floors(request, building_type)

    spaces, unclassified, space_notes = extract_spaces(
        intent, request=request, language=lang, building_type=building_type
    )

    site_condition = read_site_condition(request, language=lang)

    daylight_strategy = detect_daylight_strategy(spaces, request)

    building_intent = {
        "building_type": building_type,
        "household": household,
        "floors": floors,
        "spaces": list(spaces),
        "unclassified": list(unclassified),
        "site_condition": site_condition,
        "daylight_strategy": daylight_strategy,
        "area_limited": _has_any(request, AREA_LIMIT_MARKERS) or bool(intent.get("constraint")),
        "notes": list(space_notes),
    }

    # ---- TASK 2 — the concept ----
    concept = build_spatial_planning_concept(spaces, floors, language=lang)

    concept["site_condition"] = site_condition

    concept["daylight_strategy"] = daylight_strategy

    # ---- TASK 3 — relationships ----
    relationships = build_relationships(spaces, floors, language=lang)

    # ---- TASK 4 — fixed / flexible ----
    fixed_flexible = build_fixed_flexible(intent, spaces, concept["circulation"], language=lang)

    # ---- TASK 5 — priorities ----
    priority_reasoning = build_priority_reasoning(fixed_flexible, spaces, request, language=lang)

    # ---- TASK 6 — alternatives (reasoning alternatives when memory is present) ----
    retrieval: Dict[str, Any] = {}

    reasoning_alternatives: List[Dict[str, Any]] = []

    reasoning_error: Optional[str] = None

    if memory is not None:

        try:

            retrieval = associative_retrieve(request, memory, language=lang)

            reasoning = reason_design(
                {
                    "building_type": building_type,
                    "area_limitation": building_intent["area_limited"],
                    "user_requirements": list(intent.get("requirement") or [])
                    + list(intent.get("preference") or []),
                    "topic": " ".join(spaces + list(retrieval.get("topics", {}).get("spaces", []))),
                },
                retrieval=retrieval,
            )

            reasoning_alternatives = list(reasoning.get("alternatives") or [])

        except Exception as exc:  # noqa: BLE001 — the reasoning is an enrichment, never fatal

            reasoning_error = "%s: %s" % (type(exc).__name__, exc)

    alternatives = build_conceptual_alternatives(
        concept["zones"], reasoning_alternatives, language=lang
    )

    # ---- TASK 7 — parameters ----
    parameters = extract_parameters(request, language=lang)

    # ---- TASK 8 — conflicts ----
    conflicts = build_planning_conflicts(
        intent, fixed_flexible, concept["zones"], request, language=lang
    )

    conflicts.extend(list(organization.get("conflicts") or []))

    conflicts = _dedupe_conflicts(conflicts)

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "language": lang,
        "request": request,
        "building_intent": building_intent,
        "spatial_planning_concept": concept,
        "spaces": list(spaces),
        "relationships": relationships,
        "fixed_flexible": fixed_flexible,
        "priority_reasoning": priority_reasoning,
        "priorities": list(SPATIAL_PRIORITY_ORDER),
        "conceptual_alternatives": alternatives,
        "context_dependent_parameters": parameters,
        "conflicts": conflicts,
        "retrieved_knowledge": list(retrieval.get("entries") or []),
        "reasoning_error": reasoning_error,
        "human_review_required": True,
        "is_final_solution": False,
        "design_generated": False,
        "plan_generated": False,
        "geometry_generated": False,
        "non_claims": dict(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    result["natural_planning"] = build_natural_planning(result, language=lang)

    _assert_no_forbidden_authorship(result)

    return result


def _assert_no_forbidden_authorship(result) -> None:

    """Scan the AUTHORED text only (never the non_claims keys — the known trap)."""

    authored = [
        result.get("natural_planning"),
        " ".join(
            str(a.get(key))
            for a in result.get("conceptual_alternatives") or []
            for key in ("label", "gains", "costs", "trade_offs")
        ),
        " ".join(str(c.get("statement")) for c in result.get("conflicts") or []),
    ]

    payload = _norm(" ".join(str(part) for part in authored))

    for term in FORBIDDEN_TERMS:

        if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(term), payload):

            raise ArchitecturalSpatialPlanningUnderstandingError(
                "spatial planning refused a forbidden term: " + term
            )


class ArchitecturalSpatialPlanningUnderstandingV1:

    """The spatial-planning understanding boundary. Stateless, deterministic."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    IS_UNDERSTANDING = True

    GENERATES_GEOMETRY = False

    GENERATES_PLAN = False

    DECIDES_FINAL_DESIGN = False

    def understand(self, source, **kwargs) -> Dict[str, Any]:

        return understand_spatial_planning(source, **kwargs)

    def concept(self, spaces, floors=1, **kwargs) -> Dict[str, Any]:

        return build_spatial_planning_concept(spaces, floors, **kwargs)

    def parameters(self, request, **kwargs) -> List[Dict[str, Any]]:

        return extract_parameters(request, **kwargs)

    def __repr__(self):

        return "ArchitecturalSpatialPlanningUnderstandingV1(understanding_only=True)"


architectural_spatial_planning_understanding = ArchitecturalSpatialPlanningUnderstandingV1()
