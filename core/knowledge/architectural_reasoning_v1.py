"""Architectural Design Reasoning (V1).

The missing reasoning layer:

    Architectural Knowledge + Project Context + User Requirements
        + Site Constraints + Building Type
                    ↓
        ARCHITECTURAL DESIGN REASONING          <- THIS LAYER
                    ↓
            Design Decisions  (explained, proposed)

It
    uses CONFIRMED memory knowledge as CONTEXT (never as a law)
    understands the four PRIORITY bands
    identifies CONFLICTS between knowledge and the project
    produces ALTERNATIVES with advantages / disadvantages / conditions
    explains TRADE-OFFS
    respects FIXED vs FLEXIBLE elements
    explains everything in the architect's own language

It MUST NOT
    generate a plan / geometry / CAD / BIM / IFC / a render
    decide the final design (the architect does)
    override the architect
    convert knowledge into an absolute rule

Contract note
    The contract here is `ArchitecturalReasoningResultV1`. It is DISTINCT from
    the legacy `ArchitecturalDesignReasoningResultV1`
    (`core/design/design_reasoning/architectural_design_reasoning_v1.py`), which
    is a different, earlier engine.

Dependency direction

    this module  ->  core.knowledge.architectural_knowledge_retrieval_v1 (optional)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional


CONTRACT = "ArchitecturalReasoningResultV1"

VERSION = "1.0"


# ----------------------------------------------------------
# TASK 3 — the architectural priority system
# ----------------------------------------------------------

PRIORITY_SAFETY = "SAFETY"

PRIORITY_ESSENTIAL = "ESSENTIAL_FUNCTION"

PRIORITY_QUALITY = "SPATIAL_QUALITY"

PRIORITY_OPTIONAL = "OPTIONAL_FEATURE"


PRIORITY_ORDER = (
    PRIORITY_SAFETY,
    PRIORITY_ESSENTIAL,
    PRIORITY_QUALITY,
    PRIORITY_OPTIONAL,
)


PRIORITY_BY_TOKEN: Dict[str, str] = {
    # 1 — safety
    "stair": PRIORITY_SAFETY,
    "staircase": PRIORITY_SAFETY,
    "structure": PRIORITY_SAFETY,
    "structural": PRIORITY_SAFETY,
    "column": PRIORITY_SAFETY,
    "core": PRIORITY_SAFETY,
    "elevator": PRIORITY_SAFETY,
    "emergency": PRIORITY_SAFETY,
    "fire": PRIORITY_SAFETY,
    # 2 — essential functions
    "bedroom": PRIORITY_ESSENTIAL,
    "kitchen": PRIORITY_ESSENTIAL,
    "bathroom": PRIORITY_ESSENTIAL,
    "wc": PRIORITY_ESSENTIAL,
    "entrance": PRIORITY_ESSENTIAL,
    "living": PRIORITY_ESSENTIAL,
    "circulation": PRIORITY_ESSENTIAL,
    # 3 — spatial quality
    "privacy": PRIORITY_QUALITY,
    "daylight": PRIORITY_QUALITY,
    "light": PRIORITY_QUALITY,
    "window": PRIORITY_QUALITY,
    "movement": PRIORITY_QUALITY,
    "proportion": PRIORITY_QUALITY,
    # 4 — optional features
    "closet": PRIORITY_OPTIONAL,
    "wardrobe": PRIORITY_OPTIONAL,
    "storage": PRIORITY_OPTIONAL,
    "balcony": PRIORITY_OPTIONAL,
    "luxury": PRIORITY_OPTIONAL,
    "decorative": PRIORITY_OPTIONAL,
}


# ----------------------------------------------------------
# TASK 6 — fixed vs flexible
# ----------------------------------------------------------

FIXED_TOKENS = (
    "stair", "staircase", "structure", "structural", "column", "core",
    "elevator", "shear_wall", "shaft",
)

FLEXIBLE_TOKENS = (
    "closet", "wardrobe", "storage", "furniture", "bed", "seating",
    "shelf", "decorative", "lighting_fixture",
)


# ----------------------------------------------------------
# TASK 5 — alternatives (a closed, documented table)
# ----------------------------------------------------------

_STORAGE_ALTERNATIVES = (
    {
        "label": "Independent closet",
        "advantages": ["dedicated storage", "privacy for dressing"],
        "disadvantages": ["reduces circulation quality in a small room"],
        "conditions": ["enough floor area"],
        "priority": PRIORITY_OPTIONAL,
    },
    {
        "label": "Built-in wardrobe",
        "advantages": ["balances storage and space", "keeps the room compact"],
        "disadvantages": ["less generous than a room of its own"],
        "conditions": ["a suitable wall exists"],
        "priority": PRIORITY_OPTIONAL,
    },
    {
        "label": "No closet, larger bedroom",
        "advantages": ["better room quality", "more circulation"],
        "disadvantages": ["no dedicated storage in the room"],
        "conditions": ["alternative storage exists elsewhere"],
        "priority": PRIORITY_OPTIONAL,
    },
)


ALTERNATIVES_BY_FEATURE: Dict[str, Any] = {
    "closet": _STORAGE_ALTERNATIVES,
    "wardrobe": _STORAGE_ALTERNATIVES,
    "storage": _STORAGE_ALTERNATIVES,
}


# ----------------------------------------------------------
# markers
# ----------------------------------------------------------

AREA_PRESERVING_MARKERS = (
    "maximize", "maximise", "larger", "bigger", "more space",
    "حداکثر", "بزرگ تر", "بزرگتر", "بیشتر", "گسترده",
)

PREFERENCE_MARKERS = (
    "prefer", "i like", "i want", "would like", "my preference",
    "ترجیح", "دوست دارم", "می پسندم", "میپسندم", "علاقه دارم",
)

LIMITED_MARKERS = (
    "small", "limited", "tight", "compact", "کم", "محدود", "کوچک",
)


FORBIDDEN_TERMS = (
    "geometry", "polygon", "coordinate", "coordinates", "dimension",
    "dimensions", "cad", "dwg", "bim", "ifc", "revit",
)


_NON_CLAIMS = {
    "not_a_final_solution": True,
    "not_confidence": True,
    "not_truth": True,
    "not_authority": True,
    "not_a_rule": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_a_plan": True,
    "human_decides": True,
}


class ArchitecturalReasoningError(ValueError):
    """Raised when the reasoning boundary is misused."""


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


# ----------------------------------------------------------
# project context
# ----------------------------------------------------------

CONTEXT_FIELDS = (
    "building_type",
    "site_size",
    "area_limitation",
    "user_requirements",
    "existing_constraints",
    "goals",
    "topic",
    "fixed_elements",
    "requested_modifications",
)


def _context(project_context) -> Dict[str, Any]:

    raw = dict(project_context or {})

    context = {field: raw.get(field) for field in CONTEXT_FIELDS}

    for list_field in (
        "user_requirements", "existing_constraints", "goals",
        "fixed_elements", "requested_modifications",
    ):

        value = context.get(list_field)

        context[list_field] = list(value) if isinstance(value, (list, tuple)) else ([value] if value else [])

    limitation = context.get("area_limitation")

    text = " ".join(
        str(v) for v in (
            [limitation] if limitation is not None else []
        ) + list(context["existing_constraints"]) + list(context["goals"])
    )

    context["area_limited"] = bool(limitation) or _has_any(text, LIMITED_MARKERS)

    return context


def _tokens_from(values) -> List[str]:

    tokens: List[str] = []

    for value in values or []:

        for part in _norm(value).replace("/", " ").replace(",", " ").split():

            if part not in tokens:

                tokens.append(part)

    return tokens


def _priority_of(token) -> Optional[str]:

    return PRIORITY_BY_TOKEN.get(_norm(token).replace("_", " "))


def _entry_priority(entry) -> str:

    best: Optional[str] = None

    for token in (entry.get("element") or []):

        band = _priority_of(token)

        if band and (best is None or PRIORITY_ORDER.index(band) < PRIORITY_ORDER.index(best)):

            best = band

    return best or PRIORITY_QUALITY


def _has_band(entry, band) -> bool:

    """True when ANY element of the entry belongs to a priority band."""

    return any(_priority_of(token) == band for token in (entry.get("element") or []))


# ----------------------------------------------------------
# knowledge gathering
# ----------------------------------------------------------

def _knowledge(retrieval, memory, topic) -> List[Dict[str, Any]]:

    if isinstance(retrieval, dict):

        return [e for e in (retrieval.get("entries") or []) if isinstance(e, dict)]

    if memory is not None and topic:

        from core.knowledge.architectural_knowledge_retrieval_v1 import retrieve

        return list(retrieve(topic, memory).get("entries") or [])

    return []


# ----------------------------------------------------------
# conflict reasoning (TASK 4 / TASK 6)
# ----------------------------------------------------------

def _fixed_flexible_conflicts(context) -> List[Dict[str, Any]]:

    conflicts: List[Dict[str, Any]] = []

    for modification in context.get("requested_modifications") or []:

        if not isinstance(modification, dict):

            continue

        target = _norm(modification.get("target")).replace("_", " ")

        reason = _norm(modification.get("reason")).replace("_", " ")

        if target in FIXED_TOKENS and reason in FLEXIBLE_TOKENS:

            conflicts.append(
                {
                    "statement": (
                        "Refused: the fixed '%s' must not be modified to solve the "
                        "flexible '%s' need." % (target, reason)
                    ),
                    "between": [target, reason],
                    "kind": "fixed_vs_flexible",
                    "priority_impact": PRIORITY_SAFETY,
                }
            )

    return conflicts


def _contradiction_conflicts(context) -> List[Dict[str, Any]]:

    if not context.get("area_limited"):

        return []

    requirements = list(context.get("user_requirements") or [])

    has_optional = any(
        _has_any(req, list(ALTERNATIVES_BY_FEATURE)) for req in requirements
    )

    has_area_need = any(_has_any(req, AREA_PRESERVING_MARKERS) for req in requirements)

    if has_optional and has_area_need:

        return [
            {
                "statement": (
                    "The requirements conflict: a dedicated storage feature and a "
                    "larger room cannot both be fully satisfied in a limited area."
                ),
                "between": ["optional_feature", "area"],
                "kind": "contradictory_requirements",
                "priority_impact": PRIORITY_OPTIONAL,
            }
        ]

    return []


def _area_conflicts(context, knowledge) -> List[Dict[str, Any]]:

    conflicts: List[Dict[str, Any]] = []

    if not context.get("area_limited"):

        return conflicts

    for entry in knowledge:

        # an entry may carry BOTH an essential element and an optional one
        # (e.g. bathroom + closet) — the OPTIONAL element is what competes
        if _has_band(entry, PRIORITY_OPTIONAL):

            conflicts.append(
                {
                    "statement": (
                        "The available area is limited, so this optional feature "
                        "competes with the room's essential quality."
                    ),
                    "between": list(entry.get("element") or []),
                    "kind": "area_limitation",
                    "priority_impact": PRIORITY_OPTIONAL,
                }
            )

    return conflicts


# ----------------------------------------------------------
# TASK 3 — the priority rule
# ----------------------------------------------------------

def _priority_rule_violations(context, knowledge) -> List[Dict[str, Any]]:

    """An optional feature must never damage a higher priority."""

    violations: List[Dict[str, Any]] = []

    if not context.get("area_limited"):

        return violations

    optional = [e for e in knowledge if _has_band(e, PRIORITY_OPTIONAL)]

    essential = [e for e in knowledge if _has_band(e, PRIORITY_ESSENTIAL)]

    if optional and essential:

        violations.append(
            {
                "statement": (
                    "Priority rule: the optional feature must not damage the "
                    "essential function."
                ),
                "between": list(optional[0].get("element") or []) + list(essential[0].get("element") or []),
                "kind": "priority_rule",
                "priority_impact": PRIORITY_ESSENTIAL,
            }
        )

    return violations


# ----------------------------------------------------------
# TASK 7 — the natural reasoning
# ----------------------------------------------------------

CONFLICT_PHRASES = {
    "fa": {
        "area_limitation": "با توجه به محدودیت زیربنا، این ویژگی اختیاری با کیفیت اصلی فضا رقابت می‌کند.",
        "priority_rule": "قاعدهٔ اولویت: ویژگی اختیاری نباید به اولویت‌های بالاتر آسیب بزند.",
        "fixed_vs_flexible": "عنصر ثابت «{target}» نباید برای حل نیاز انعطاف‌پذیر «{reason}» تغییر کند.",
        "contradictory_requirements": "نیازهای مطرح‌شده با هم در تناقض‌اند و نمی‌توان همه را هم‌زمان تأمین کرد.",
    },
    "en": {
        "area_limitation": "Given the limited area, this optional feature competes with the room's essential quality.",
        "priority_rule": "Priority rule: an optional feature must not damage a higher priority.",
        "fixed_vs_flexible": "The fixed '{target}' must not be modified to solve the flexible '{reason}' need.",
        "contradictory_requirements": "The stated requirements conflict; they cannot all be fully satisfied.",
    },
}


DECISION_PHRASES = {
    "fa": {
        "keep_essential": (
            "پیشنهاد من این است که ابتدا کیفیت فضای اصلی حفظ شود و اگر امکان داشت "
            "از گزینه‌های انعطاف‌پذیر (مانند کمد داخلی) استفاده شود."
        ),
        "considerable": "با توجه به زمینهٔ پروژه، این رابطهٔ آموخته‌شده قابل بررسی است.",
        "fixed_untouched": (
            "عنصر ثابت دست‌نخورده می‌ماند؛ نیاز انعطاف‌پذیر باید با یک راه‌حل "
            "انعطاف‌پذیر حل شود."
        ),
        "preference": "این یک ترجیح شخصی شماست؛ در استدلال اثر می‌گذارد اما به‌عنوان قانون ثبت نمی‌شود.",
    },
    "en": {
        "keep_essential": (
            "I suggest keeping the essential space quality first, and using a "
            "flexible option (such as a built-in wardrobe) if possible."
        ),
        "considerable": "Given the project context, this learned relationship can be considered.",
        "fixed_untouched": (
            "The fixed element stays untouched; the flexible need should be solved "
            "with a flexible solution."
        ),
        "preference": "This is your personal preference; it influences the reasoning but is not stored as a rule.",
    },
}


REASONING_HEADER = {"fa": "استدلال معماری من این است:", "en": "Here is my architectural reasoning:"}

REASONING_OPTIONS = {"fa": "گزینه‌ها", "en": "Options"}

REASONING_FOOTER = {"fa": "تصمیم نهایی با معمار است.", "en": "The architect makes the final decision."}


def build_natural_reasoning(result, *, language="fa") -> str:

    lang = _language(language)

    lines: List[str] = [REASONING_HEADER[lang]]

    for conflict in result["conflicts"]:

        phrase = CONFLICT_PHRASES[lang].get(conflict["kind"])

        if not phrase:

            continue

        between = list(conflict.get("between") or [])

        lines.append(
            "• " + phrase.format(
                target=between[0] if between else "",
                reason=between[1] if len(between) > 1 else "",
            )
        )

    for decision in result["decisions"]:

        phrase = DECISION_PHRASES[lang].get(decision.get("kind"))

        if phrase:

            lines.append("• " + phrase)

    if result["alternatives"]:

        lines.append(
            REASONING_OPTIONS[lang] + ": "
            + " · ".join(a["label"] for a in result["alternatives"])
        )

    lines.append(REASONING_FOOTER[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def reason_design(
    project_context,
    *,
    memory=None,
    retrieval=None,
    language=None,
) -> Dict[str, Any]:

    """Reason about a project from confirmed knowledge. Proposes, never decides."""

    context = _context(project_context)

    lang = _language(language)

    knowledge = _knowledge(retrieval, memory, context.get("topic"))

    used_knowledge = [
        {
            "knowledge_id": entry.get("knowledge_id"),
            "element": list(entry.get("element") or []),
            "priority": _entry_priority(entry),
        }
        for entry in knowledge
    ]

    conflicts: List[Dict[str, Any]] = []

    conflicts.extend(_fixed_flexible_conflicts(context))

    conflicts.extend(_contradiction_conflicts(context))

    conflicts.extend(_area_conflicts(context, knowledge))

    conflicts.extend(_priority_rule_violations(context, knowledge))

    # ---- alternatives + trade-offs (TASK 5) ----
    alternatives: List[Dict[str, Any]] = []

    seen_labels = set()

    for entry in knowledge:

        for token in entry.get("element") or []:

            for alternative in ALTERNATIVES_BY_FEATURE.get(_norm(token), ()):

                if alternative["label"] in seen_labels:

                    continue

                seen_labels.add(alternative["label"])

                alternatives.append(dict(alternative))

    trade_offs = [
        {
            "option": a["label"],
            "gains": list(a["advantages"]),
            "costs": list(a["disadvantages"]),
        }
        for a in alternatives
    ]

    # ---- decisions (PROPOSED — never final) ----
    decisions: List[Dict[str, Any]] = []

    reasoning_basis: List[str] = []

    if context.get("area_limited") and any(
        c["kind"] in ("area_limitation", "priority_rule") for c in conflicts
    ):

        decisions.append(
            {
                "statement": (
                    "Keep the essential function and the room's spatial quality; "
                    "the optional feature is reconsidered, not forced."
                ),
                "kind": "keep_essential",
                "priority": PRIORITY_ESSENTIAL,
                "reasoning_basis": ["limited area", "priority rule"],
                "used_knowledge": [k["knowledge_id"] for k in used_knowledge],
                "status": "proposed",
                "requires_human_review": True,
            }
        )

        reasoning_basis.append("limited area + priority rule")

    elif not conflicts and knowledge:

        decisions.append(
            {
                "statement": (
                    "The area allows the learned relationship to be considered."
                ),
                "kind": "considerable",
                "priority": PRIORITY_QUALITY,
                "reasoning_basis": ["no conflict with the project context"],
                "used_knowledge": [k["knowledge_id"] for k in used_knowledge],
                "status": "proposed",
                "requires_human_review": True,
            }
        )

        reasoning_basis.append("no conflict with the project context")

    for conflict in conflicts:

        if conflict["kind"] == "fixed_vs_flexible":

            decisions.append(
                {
                    "statement": (
                        "The fixed element is not touched; solve the flexible need "
                        "with a flexible solution instead."
                    ),
                    "kind": "fixed_untouched",
                    "priority": PRIORITY_SAFETY,
                    "reasoning_basis": ["fixed vs flexible rule"],
                    "used_knowledge": [],
                    "status": "proposed",
                    "requires_human_review": True,
                }
            )

            reasoning_basis.append("fixed vs flexible rule")

    # ---- a user preference influences, never rules (TASK 8 / T5) ----
    for requirement in context.get("user_requirements") or []:

        if _has_any(requirement, PREFERENCE_MARKERS):

            decisions.append(
                {
                    "statement": (
                        "This is your preference: it influences the reasoning but is "
                        "not stored as a rule. «%s»" % requirement
                    ),
                    "kind": "preference",
                    "priority": PRIORITY_QUALITY,
                    "reasoning_basis": ["a stated user preference"],
                    "used_knowledge": [],
                    "status": "proposed",
                    "requires_human_review": True,
                }
            )

            reasoning_basis.append("user preference noted (not a rule)")

    # ---- unresolved questions ----
    unresolved: List[str] = []

    if conflicts and not alternatives:

        unresolved.append("No stored alternative applies to this conflict.")

    if context.get("area_limited"):

        unresolved.append("How much area is actually available for the optional feature?")

    if not knowledge:

        unresolved.append("No confirmed knowledge covers this topic yet.")

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "topic": context.get("topic"),
        "project_context": context,
        "decisions": decisions,
        "reasoning_basis": reasoning_basis,
        "used_knowledge": used_knowledge,
        "conflicts": conflicts,
        "trade_offs": trade_offs,
        "alternatives": alternatives,
        "unresolved_questions": unresolved,
        "human_review_required": True,
        "is_final_solution": False,
        "non_claims": dict(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    result["natural_reasoning"] = build_natural_reasoning(result, language=lang)

    # ---- the reasoning never emits geometry ----
    # Scan the AUTHORED TEXT only. A `knowledge_id` is random hex, so it can
    # contain a forbidden substring (e.g. "cad") by chance — scanning the ids
    # made this guard flaky.
    payload = _norm(
        {
            "decisions": [d.get("statement") for d in decisions],
            "conflicts": [c.get("statement") for c in conflicts],
            "alternatives": [
                {
                    "label": a.get("label"),
                    "advantages": a.get("advantages"),
                    "disadvantages": a.get("disadvantages"),
                }
                for a in alternatives
            ],
            "trade_offs": [
                {"option": t.get("option"), "gains": t.get("gains"), "costs": t.get("costs")}
                for t in trade_offs
            ],
        }
    )

    for term in FORBIDDEN_TERMS:

        if term in payload:

            raise ArchitecturalReasoningError(
                "reasoning refused a geometry term: " + term
            )

    return result


class ArchitecturalDesignReasoningV1:

    """The design reasoning engine. Stateless, deterministic."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    GENERATES_GEOMETRY = False

    DECIDES_FINAL_DESIGN = False

    OVERRIDES_ARCHITECT = False

    def reason(self, project_context, **kwargs) -> Dict[str, Any]:

        return reason_design(project_context, **kwargs)

    def __repr__(self):

        return "ArchitecturalDesignReasoningV1(reasoning_only=True)"


architectural_design_reasoning = ArchitecturalDesignReasoningV1()
