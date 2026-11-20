"""Architectural Spatial Organization Understanding (V1).

Understands HOW spaces should be organized architecturally — before any plan.

    "First understand the relationships between spaces, then generate space."

It
    classifies the program into ZONES (reusing the EXISTING corpus + zone model)
    derives the RELATIONSHIPS between spaces from their zones
    separates FIXED from FLEXIBLE relationships
    combines SEVERAL spaces (multi-space reasoning)
    explains the spatial PRIORITIES and trade-offs
    reports a conflict — and never decides

It MUST NOT
    draw / plan / generate geometry / CAD / BIM / IFC / a render
    hardcode the space classification as universal architectural law
    guess a space that is not in the corpus
    turn a relationship into an absolute rule

Reuse (no reinvention)
    core/curriculum/space_types_v1   -> the 82-space residential corpus + categories
    core/curriculum/zone_model_v1    -> the 6 zones + ZONE_BY_CATEGORY + zone_display
    architectural_associative_retrieval_v1 -> SPACE_SURFACE (fa/en)
    architectural_intent_understanding_v1  -> the request reading
    architectural_reasoning_v1 / _quality  -> conflicts / dimensions

Dependency direction

    this module  ->  core.curriculum / core.knowledge.* only
    this module  ->  core.vision / core.render / core.cad / core.bim / core.ifc /
                     core.geometry / core.spatial / core.ai / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional, Tuple


from core.curriculum.space_types_v1 import space_types

from core.curriculum.zone_model_v1 import (
    ZONE_BY_CATEGORY,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    ZONE_PRIVATE,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_SERVICE,
    zone_display,
)

from core.conversation.turn_semantics_v1 import classify_turn

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    extract_architectural_knowledge_candidate_v1,
)

from core.knowledge.architectural_associative_retrieval_v1 import (
    SPACE_SURFACE,
    associative_retrieve,
)

from core.knowledge.architectural_intent_understanding_v1 import (
    CONTRACT as INTENT_CONTRACT,
    understand_intent,
)

from core.knowledge.architectural_reasoning_v1 import (
    FIXED_TOKENS,
    FLEXIBLE_TOKENS,
    reason_design,
)

from core.knowledge.architectural_reasoning_quality_v1 import improve_reasoning


CONTRACT = "ArchitecturalSpatialOrganizationV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the relationship vocabulary (a declared, symmetric table)
# ----------------------------------------------------------

REL_ADJACENT = "adjacent"
REL_SEPARATED = "separated"
REL_CONNECTED = "connected"
REL_PRIVATE_TRANSITION = "private_transition"
REL_SERVICE = "service_relationship"

RELATIONSHIP_KINDS = (
    REL_ADJACENT,
    REL_SEPARATED,
    REL_CONNECTED,
    REL_PRIVATE_TRANSITION,
    REL_SERVICE,
)


ZONE_RELATIONSHIP: Dict[Tuple[str, str], str] = {
    (ZONE_PUBLIC, ZONE_PUBLIC): REL_ADJACENT,
    (ZONE_PUBLIC, ZONE_SEMI_PUBLIC): REL_ADJACENT,
    (ZONE_PUBLIC, ZONE_PRIVATE): REL_SEPARATED,
    (ZONE_PUBLIC, ZONE_SERVICE): REL_SERVICE,
    (ZONE_PUBLIC, ZONE_CIRCULATION): REL_CONNECTED,
    (ZONE_PUBLIC, ZONE_EXTERNAL): REL_CONNECTED,
    (ZONE_SEMI_PUBLIC, ZONE_SEMI_PUBLIC): REL_ADJACENT,
    (ZONE_SEMI_PUBLIC, ZONE_PRIVATE): REL_PRIVATE_TRANSITION,
    (ZONE_SEMI_PUBLIC, ZONE_SERVICE): REL_SERVICE,
    (ZONE_SEMI_PUBLIC, ZONE_CIRCULATION): REL_CONNECTED,
    (ZONE_SEMI_PUBLIC, ZONE_EXTERNAL): REL_CONNECTED,
    (ZONE_PRIVATE, ZONE_PRIVATE): REL_ADJACENT,
    # a private zone's service relationship (e.g. an ensuite bathroom) is a
    # PRIVACY relationship, not a plain service one
    (ZONE_PRIVATE, ZONE_SERVICE): REL_PRIVATE_TRANSITION,
    (ZONE_PRIVATE, ZONE_CIRCULATION): REL_CONNECTED,
    (ZONE_PRIVATE, ZONE_EXTERNAL): REL_CONNECTED,
    (ZONE_SERVICE, ZONE_SERVICE): REL_ADJACENT,
    (ZONE_SERVICE, ZONE_CIRCULATION): REL_CONNECTED,
    (ZONE_CIRCULATION, ZONE_CIRCULATION): REL_ADJACENT,
    (ZONE_EXTERNAL, ZONE_EXTERNAL): REL_ADJACENT,
}


# A FIXED relationship is a strong architectural requirement (the circulation
# between zones, and the separation a private zone requires). The rest may be
# adjusted — a flexible element must never damage a fixed relationship.
FIXED_RELATIONSHIP_KINDS = (REL_CONNECTED, REL_SEPARATED)

FLEXIBLE_RELATIONSHIP_KINDS = (REL_ADJACENT, REL_PRIVATE_TRANSITION, REL_SERVICE)


# ----------------------------------------------------------
# the spatial priority order (the brief's small-house example)
# ----------------------------------------------------------

SPATIAL_PRIORITIES = (
    "essential_circulation",
    "privacy",
    "natural_light",
    "optional_storage",
)


PRIORITY_LABELS = {
    "fa": {
        "essential_circulation": "گردش ضروری",
        "privacy": "حریم",
        "natural_light": "نور طبیعی",
        "optional_storage": "ذخیره‌سازی اختیاری",
    },
    "en": {
        "essential_circulation": "essential circulation",
        "privacy": "privacy",
        "natural_light": "natural light",
        "optional_storage": "optional storage",
    },
}


RELATIONSHIP_LABELS = {
    "fa": {
        REL_ADJACENT: "همجوار",
        REL_SEPARATED: "جدا",
        REL_CONNECTED: "مرتبط (گردش)",
        REL_PRIVATE_TRANSITION: "انتقال خصوصی",
        REL_SERVICE: "رابطهٔ خدماتی",
    },
    "en": {
        REL_ADJACENT: "adjacent",
        REL_SEPARATED: "separated",
        REL_CONNECTED: "connected",
        REL_PRIVATE_TRANSITION: "private transition",
        REL_SERVICE: "service relationship",
    },
}


ORGANIZATION_HEADER = {
    "fa": "سازمان فضایی که از درخواست شما برداشت کردم:",
    "en": "This is the spatial organization I read from your request:",
}

ORGANIZATION_FOOTER = {
    "fa": "تصمیم نهایی با معمار است.",
    "en": "The architect makes the final decision.",
}


_NON_CLAIMS = {
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_a_design": True,
    "not_invented": True,
    "confirmed_memory_only": True,
    "human_decides": True,
}


class ArchitecturalSpatialOrganizationError(ValueError):
    """Raised when the spatial-organization boundary is misused."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _unique(values) -> List[str]:

    result: List[str] = []

    for value in values:

        if value and value not in result:

            result.append(value)

    return result


# ----------------------------------------------------------
# TASK 1 — space classification (reusing the corpus)
# ----------------------------------------------------------

def resolve_surface(term) -> Optional[str]:

    """A Persian/English surface form -> the English token."""

    form = _norm(term)

    for surface, token in SPACE_SURFACE.items():

        if _norm(surface) in form:

            return token

    return None


# The corpus names some spaces differently from the surface vocabulary — a
# closet is a DRESSING space in the residential corpus. This alias only
# RESOLVES a name; it adds no architectural knowledge.
CORPUS_ALIASES = {
    "closet": "dressing",
    "wardrobe": "dressing",
    "dressing room": "dressing",
    "stair": "stair",
    "corridor": "corridor",
}


def classify_space(term) -> Dict[str, Any]:

    """surface -> space_id -> category -> zone. Nothing is invented."""

    surface = resolve_surface(term) or str(term or "").strip()

    space_id = space_types.find(surface) if surface else None

    if not space_id and surface:

        alias = CORPUS_ALIASES.get(_norm(surface))

        if alias:

            space_id = space_types.find(alias)

    record = space_types.space(space_id) if space_id else None

    category = record.get("category") if isinstance(record, dict) else None

    return {
        "term": str(term),
        "space_id": space_id,
        "category": category,
        "zone": ZONE_BY_CATEGORY.get(category),
    }


def classify_program(program) -> Dict[str, Any]:

    """Group the program into zones. An unknown space is REPORTED, not guessed."""

    zones: Dict[str, List[str]] = {}

    space_zone: Dict[str, Optional[str]] = {}

    unclassified: List[str] = []

    for term in program or []:

        classified = classify_space(term)

        zone = classified["zone"]

        label = classified["space_id"] or str(term)

        space_zone[str(term)] = zone

        if zone:

            zones.setdefault(zone, [])

            if label not in zones[zone]:

                zones[zone].append(label)

        elif str(term).strip() not in unclassified:

            unclassified.append(str(term))

    return {"zones": zones, "space_zone": space_zone, "unclassified": unclassified}


# ----------------------------------------------------------
# TASK 2 — relationship derivation
# ----------------------------------------------------------

def zone_relationship(zone_a, zone_b) -> Optional[str]:

    return ZONE_RELATIONSHIP.get((zone_a, zone_b)) or ZONE_RELATIONSHIP.get((zone_b, zone_a))


def derive_relationships(program) -> List[Dict[str, Any]]:

    """One relationship per ORDERED PAIR of classified spaces."""

    classified = [classify_space(term) for term in program or []]

    classified = [c for c in classified if c["zone"]]

    relationships: List[Dict[str, Any]] = []

    for index, first in enumerate(classified):

        for second in classified[index + 1:]:

            kind = zone_relationship(first["zone"], second["zone"])

            if not kind:

                continue

            relationships.append(
                {
                    "a": first["space_id"],
                    "b": second["space_id"],
                    "a_zone": first["zone"],
                    "b_zone": second["zone"],
                    "kind": kind,
                    "fixed": kind in FIXED_RELATIONSHIP_KINDS,
                }
            )

    return relationships


# ----------------------------------------------------------
# TASK 3 — the fixed vs flexible guard
# ----------------------------------------------------------

def fixed_flexible_guard(program, relationships) -> List[Dict[str, Any]]:

    """A flexible element must not damage a fixed relationship."""

    found: List[Dict[str, Any]] = []

    form = _norm(" ".join(str(t) for t in program or []))

    fixed_elements = [t for t in FIXED_TOKENS if _norm(t).replace("_", " ") in form]

    flexible_elements = [t for t in FLEXIBLE_TOKENS if _norm(t).replace("_", " ") in form]

    if fixed_elements and flexible_elements:

        found.append(
            {
                "statement": (
                    "The flexible element must not damage the fixed element's "
                    "relationship."
                ),
                "between": fixed_elements + flexible_elements,
                "kind": "fixed_vs_flexible",
                "priority_impact": "SAFETY",
            }
        )

    for relationship in relationships:

        if relationship["kind"] == REL_SEPARATED and relationship["fixed"]:

            continue

    return found


# ----------------------------------------------------------
# TASK 4 — the natural organization
# ----------------------------------------------------------

def build_natural_organization(result, *, language="fa") -> str:

    lang = _language(language)

    labels = RELATIONSHIP_LABELS[lang]

    lines = [ORGANIZATION_HEADER[lang]]

    for zone, spaces in result["zones"].items():

        lines.append("• %s: %s" % (zone_display(zone, lang), "، ".join(spaces)))

    if result["relationships"]:

        rendered = [
            "%s ↔ %s (%s)" % (r["a"], r["b"], labels.get(r["kind"], r["kind"]))
            for r in result["relationships"][:6]
        ]

        lines.append("• روابط: " + " · ".join(rendered) if lang == "fa"
                     else "• relationships: " + " · ".join(rendered))

    if result["fixed_relationships"]:

        lines.append(
            "• روابط ثابت: " + " · ".join(
                "%s ↔ %s" % (r["a"], r["b"]) for r in result["fixed_relationships"]
            )
        )

    if result["unclassified"]:

        lines.append(
            "• طبقه‌بندی‌نشده (در پیکرهٔ فضاها نبود): " + "، ".join(result["unclassified"])
            if lang == "fa"
            else "• unclassified (not in the space corpus): " + ", ".join(result["unclassified"])
        )

    if result["priorities"]:

        priority_labels = PRIORITY_LABELS[lang]

        lines.append(
            "• اولویت‌های فضایی: " + " → ".join(
                priority_labels.get(p, p) for p in result["priorities"]
            )
        )

    lines.append(ORGANIZATION_FOOTER[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def understand_spatial_organization(source, *, memory=None, language=None) -> Dict[str, Any]:

    """Read a request (or a teaching statement) as spatial organization."""

    if not isinstance(source, (str, dict)) or (isinstance(source, str) and not source.strip()):

        raise ArchitecturalSpatialOrganizationError(
            "spatial organization needs a request string or an intent result"
        )

    lang = _language(language)

    teaching = None

    if isinstance(source, dict) and source.get("contract") == INTENT_CONTRACT:

        intent = source

        program = list((intent.get("intent") or {}).get("program") or [])

        request = str(intent.get("request") or "")

    elif isinstance(source, str):

        request = source

        if (classify_turn(source) or {}).get("turn_kind") == "TEACHING_STATEMENT":

            teaching = extract_architectural_knowledge_candidate_v1(
                source, turn_kind="TEACHING_STATEMENT"
            )

        if teaching is not None:

            program = list(teaching.get("element") or [])

            intent = {}

        else:

            intent = understand_intent(source, memory=memory, language=lang)

            program = list((intent.get("intent") or {}).get("program") or [])

    else:

        raise ArchitecturalSpatialOrganizationError(
            "unsupported source type: %s" % (type(source).__name__,)
        )

    classified = classify_program(program)

    relationships = derive_relationships(program)

    fixed_relationships = [r for r in relationships if r["fixed"]]

    flexible_relationships = [r for r in relationships if not r["fixed"]]

    conflicts = list(fixed_flexible_guard(program, relationships))

    # ---- connect to the CONFIRMED knowledge ----
    retrieval: Dict[str, Any] = {}

    quality: Dict[str, Any] = {}

    if memory is not None and request:

        retrieval = associative_retrieve(request, memory, language=lang)

        reasoning = reason_design(
            {
                "area_limitation": bool(intent.get("constraint")),
                "user_requirements": list(intent.get("requirement") or [])
                + list(intent.get("preference") or []),
                "topic": " ".join(program + retrieval.get("topics", {}).get("spaces", [])),
            },
            retrieval=retrieval,
        )

        quality = improve_reasoning(
            reasoning, retrieval=retrieval, memory=memory, language=lang
        )

        conflicts.extend(quality.get("conflicts") or [])

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "language": lang,
        "request": request,
        "program": program,
        "zones": classified["zones"],
        "space_zone": classified["space_zone"],
        "unclassified": classified["unclassified"],
        "relationships": relationships,
        "fixed_relationships": fixed_relationships,
        "flexible_relationships": flexible_relationships,
        "teaching": teaching,
        "priorities": list(SPATIAL_PRIORITIES),
        "conflicts": conflicts,
        "retrieved_knowledge": list(retrieval.get("entries") or []),
        "dimensions": list(quality.get("dimensions") or []),
        "human_review_required": True,
        "is_final_solution": False,
        "design_generated": False,
        "plan_generated": False,
        "non_claims": dict(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    result["natural_organization"] = build_natural_organization(result, language=lang)

    return result


class ArchitecturalSpatialOrganizationV1:

    """The spatial-organization boundary. Stateless, deterministic."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    GENERATES_GEOMETRY = False

    GENERATES_PLAN = False

    DECIDES_FINAL_DESIGN = False

    def understand(self, source, **kwargs) -> Dict[str, Any]:

        return understand_spatial_organization(source, **kwargs)

    def classify(self, program) -> Dict[str, Any]:

        return classify_program(program)

    def relationships(self, program) -> List[Dict[str, Any]]:

        return derive_relationships(program)

    def __repr__(self):

        return "ArchitecturalSpatialOrganizationV1(understanding_only=True)"


architectural_spatial_organization = ArchitecturalSpatialOrganizationV1()
