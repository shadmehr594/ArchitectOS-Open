"""Human learning ledger — the accepted-rule storage owner.

This module does not invent knowledge. It reads and appends to the EXISTING
append-only accepted-human-learning ledger
(``core/architecture/knowledge/human_architectural_learning_registry_v1.json``)
using that file's own schema. It is not a second knowledge database.

Guarantees:

* A rule enters the ledger ONLY through an explicit human confirmation
  (``confirmed_by`` is required). Nothing here is reachable from a model
  output, a vision observation or an unconfirmed teaching candidate.
* Existing items are never rewritten. Append refuses a duplicate id, and
  supersession deactivates with ``superseded_by`` instead of deleting.
* Writes are atomic (temp file in the same directory, then ``os.replace``).
* The teacher's original wording, scope, provenance and modality are preserved
  verbatim. Nothing is strengthened or generalised here.

The teaching-candidate store's Phase 08 boundary is untouched: candidates keep
their closed status set and ``promote()`` still refuses. Acceptance into this
ledger is a separate, explicit human action.
"""

import json
import os
import re
import tempfile
import time

CONTRACT = "HumanLearningLedgerV1"
VERSION = "1.0"

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge",
    "human_architectural_learning_registry_v1.json",
)

PROVENANCE_HUMAN_ACCEPTED_RULE = "HUMAN_ACCEPTED_RULE"

MODALITY_MANDATORY = "MANDATORY"
MODALITY_RECOMMENDATION = "RECOMMENDATION"
MODALITY_UNSPECIFIED = "UNSPECIFIED"

#: Applicability verdicts. A rule is only ever applied on APPLICABLE; anything
#: the evidence cannot settle is NEEDS_REVIEW rather than a guess.
APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
NEEDS_REVIEW = "NEEDS_REVIEW"

#: Display vocabulary of the EXISTING style ontology
#: (core/architecture/knowledge/architectural_style_ontology.json). Only names
#: are listed; no architectural condition is encoded here.
STYLE_ALIASES = {
    "modern": ("modern", "مدرن"),
    "classic": ("classic", "classical", "کلاسیک"),
    "neoclassical": ("neoclassical", "نئوکلاسیک", "نوکلاسیک"),
    "roman_classic": ("roman classic", "کلاسیک رومی", "رومی"),
    "iranian_traditional": ("iranian traditional", "سنتی ایرانی", "ایرانی سنتی"),
    "islamic_architecture": ("islamic architecture", "islamic", "معماری اسلامی", "اسلامی"),
    "iranian_brick": ("iranian brick", "آجری ایرانی", "آجر ایرانی"),
    "french_classical": ("french classical", "کلاسیک فرانسوی"),
    "beaux_arts": ("beaux arts", "بوزار"),
    "second_empire": ("second empire", "امپراتوری دوم"),
    "french_provincial": ("french provincial", "فرانسوی روستایی"),
}

#: Scopes that belong to one project and must never be applied to a generic
#: request from another context.
PROJECT_SCOPES = (
    "CURRENT_PROJECT",
    "CURRENT_SITE_CONTRACT",
    "MINAB_USER_PROJECT",
    "PROJECT",
)

REQUIRED_FIELDS = ("id", "human_observation_fa", "generalized_rule", "scope")

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

_STOPWORDS = frozenset(
    "the a an of and or to in on for with is are be this that it as at by "
    "از به در با که این آن را و یا است شود شود، می‌توان می تواند باید".split()
)

#: English modality markers. The Persian markers are taken from the existing
#: architectural knowledge structurer rather than duplicated here.
_EN_REQUIREMENT = (
    "must", "must not", "shall", "required", "never", "mandatory",
    "prohibited", "not allowed",
)
_EN_PREFERENCE = (
    "should", "prefer", "preferably", "recommended", "may", "can",
    "consider", "better",
)
_EN_NEGATION = ("must not", "should not", "never", "no ", "not ", "prohibited")

#: A rule that proposes a CHANGE inside a fixed domain contradicts an explicit
#: current constraint. Advisory guidance about proportion does not.
CHANGE_MARKERS = (
    "تغییر", "اصلاح", "بازطراحی", "جابه‌جا", "حذف", "اضافه",
    "change", "modify", "alter", "redesign", "remove", "add ", "relocate",
)

DOMAIN_TOKENS = {
    "massing": (
        "ارتفاع", "طبقه", "طبقات", "حجم", "جرم", "height", "floor", "floors",
        "massing", "volume", "storey", "story",
    ),
    "roof": ("سقف", "بام", "شیروانی", "roof", "roofline", "parapet"),
    "opening": (
        "بازشو", "پنجره", "در", "درها", "opening", "openings", "window",
        "windows", "door", "doors",
    ),
    "circulation": ("مسیر", "راهرو", "پله", "circulation", "corridor", "stair"),
    "camera": ("دوربین", "زاویه", "camera", "angle", "perspective"),
}


# ----------------------------------------------------------
# TEXT UTILITIES
# ----------------------------------------------------------

def _tokens(text):
    return {
        token.lower()
        for token in _WORD.findall(str(text or ""))
        if len(token) > 2 and token.lower() not in _STOPWORDS
    }


def _norm(value):
    return " ".join(str(value or "").lower().replace("_", " ").split())


def _stems(tokens):
    """Token set with a bounded English plural normalization.

    Lets an English fixed element ("columns") match a rule whose subject is
    written as "column"; Persian tokens are unaffected.
    """

    out = set()

    for token in tokens:
        out.add(token)
        if len(token) > 3 and token.endswith("s"):
            out.add(token[:-1])

    return out


def _canonical_style(value):
    """Canonical style id for a style mention, using the ontology vocabulary."""

    form = _norm(value)

    if not form:
        return None

    pairs = [
        (_norm(alias), canonical)
        for canonical, aliases in STYLE_ALIASES.items()
        for alias in aliases
        if _norm(alias)
    ]

    for alias, canonical in pairs:
        if form == alias:
            return canonical

    for alias, canonical in sorted(pairs, key=lambda pair: -len(pair[0])):
        if alias in form:
            return canonical

    return None


def named_styles(text):
    """Canonical styles NAMED in the text, longest mention first."""

    form = _norm(text)
    found = set()

    pairs = sorted(
        (
            (_norm(alias), canonical)
            for canonical, aliases in STYLE_ALIASES.items()
            for alias in aliases
            if _norm(alias)
        ),
        key=lambda pair: -len(pair[0]),
    )

    for alias, canonical in pairs:
        if alias and alias in form:
            found.add(canonical)
            form = form.replace(alias, " ")

    return found


def _request_domain(context):
    image_type = _norm(context.get("image_type"))

    if image_type in ("facade or elevation", "architectural render or photo"):
        return "facade"

    if image_type == "floor plan or sketch":
        return "floor_plan"

    return None


def _is_accepted_rule(rule):
    if not isinstance(rule, dict):
        return False, "invalid_rule"

    if rule.get("superseded_by"):
        return False, "superseded"

    if not rule.get("active"):
        return False, "inactive"

    if rule.get("candidate_id") or str(rule.get("status") or "") in (
        "observed", "needs_confirmation", "rejected",
    ):
        return False, "not_accepted_rule"

    if not rule.get("human_observation_fa"):
        return False, "no_statement"

    return True, None


def evaluate_rule_applicability(rule, context=None):
    """Decide whether ONE accepted rule may inform THIS request.

    Structured ``applies_to`` conditions are authoritative when present. A
    dimension the context cannot settle yields NEEDS_REVIEW, never a guess.
    Rules without structured conditions fall back to the T1 scope/topic gate
    plus two evidence-only exclusions: a named style that contradicts the
    request's style, and a subject the current request explicitly preserves.
    """

    accepted, reason = _is_accepted_rule(rule)

    if not accepted:
        return {"rule_id": (rule or {}).get("id") if isinstance(rule, dict) else None,
                "status": NOT_APPLICABLE, "reason": reason}

    context = context if isinstance(context, dict) else {}

    observation = str(rule.get("human_observation_fa") or "")
    generalized = str(rule.get("generalized_rule") or "")
    fixed = {_norm(item) for item in (context.get("fixed_elements") or []) if _norm(item)}

    applies_to = rule.get("applies_to")

    if isinstance(applies_to, dict) and applies_to:

        domains = [_norm(item) for item in (applies_to.get("domains") or []) if _norm(item)]

        if domains:
            domain = _request_domain(context)
            if not domain:
                return {"rule_id": rule.get("id"), "status": NEEDS_REVIEW,
                        "reason": "domain_unknown", "dimension": "domains"}
            if _norm(domain) not in domains:
                return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                        "reason": "domain_mismatch", "dimension": "domains",
                        "expected": domains, "observed": domain}

        styles = [_norm(item) for item in (applies_to.get("styles") or []) if _norm(item)]

        if styles:
            request_style = _canonical_style(context.get("style"))
            if not request_style:
                return {"rule_id": rule.get("id"), "status": NEEDS_REVIEW,
                        "reason": "style_unknown", "dimension": "styles"}
            if request_style not in styles:
                return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                        "reason": "style_conflict", "dimension": "styles",
                        "expected": styles, "observed": request_style}

        operations = [_norm(item) for item in (applies_to.get("operations") or []) if _norm(item)]

        if operations:
            operation = _norm(context.get("operation"))
            if not operation:
                return {"rule_id": rule.get("id"), "status": NEEDS_REVIEW,
                        "reason": "operation_unknown", "dimension": "operations"}
            if operation not in operations:
                return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                        "reason": "operation_mismatch", "dimension": "operations",
                        "expected": operations, "observed": operation}

        subjects = [_norm(item) for item in (applies_to.get("subjects") or []) if _norm(item)]

        fixed_stems = set()

        for element in fixed:
            fixed_stems |= _stems(_tokens(element))

        for subject in subjects:
            if subject in fixed or subject in fixed_stems:
                return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                        "reason": "subject_preserved", "dimension": "subjects",
                        "subject": subject}

        return {"rule_id": rule.get("id"), "status": APPLICABLE,
                "reason": "structured_conditions_met", "dimension": "applies_to"}

    # ---- legacy (T1) gate ----------------------------------------------

    # R3_NIGHT_MATERIAL_FIDELITY_CPU_V1 — a graphics-scoped rule is not
    # applicable to a rendered-image appearance operation, whatever the
    # scope-token overlap says. Structured `applies_to` conditions above
    # remain authoritative when an author states them explicitly.
    excluded_operation = _scope_operation_mismatch(rule.get("scope"), context)

    if excluded_operation:
        return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                "reason": "scope_operation_mismatch",
                "dimension": "scope_operation",
                "scope": str(rule.get("scope") or ""),
                "operation": excluded_operation}

    scope_match = _scope_applies(str(rule.get("scope") or ""), context)

    topic_overlap = _tokens(observation + " " + generalized) & _tokens(
        context.get("text") or ""
    )

    if not (scope_match or topic_overlap):
        return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                "reason": "no_relevance", "dimension": "scope_or_topic"}

    rule_styles = named_styles(observation + " " + generalized)
    request_style = _canonical_style(context.get("style"))

    if rule_styles and request_style and request_style not in rule_styles:
        return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                "reason": "style_conflict", "dimension": "styles",
                "expected": sorted(rule_styles), "observed": request_style}

    rule_tokens = _stems(_tokens(observation + " " + generalized))

    for element in fixed:
        if element in rule_tokens or (_stems(_tokens(element)) & rule_tokens):
            return {"rule_id": rule.get("id"), "status": NOT_APPLICABLE,
                    "reason": "subject_preserved", "dimension": "subjects",
                    "subject": element}

    return {"rule_id": rule.get("id"), "status": APPLICABLE,
            "reason": "scope_or_topic_match", "dimension": "scope_or_topic"}


def rule_applicability_report(rules, context=None):
    """Per-rule verdicts, so a non-applied rule is explainable."""

    context = _normalise_context(context)

    return [evaluate_rule_applicability(rule, context) for rule in rules or []
            if isinstance(rule, dict)]


def _structure_markers():
    try:
        from core.knowledge.architectural_knowledge_structurer_v1 import (
            PREFERENCE_MARKERS,
            REQUIREMENT_MARKERS,
        )

        return tuple(REQUIREMENT_MARKERS), tuple(PREFERENCE_MARKERS)
    except Exception:
        return (), ()


def modality_of(text):
    """Classify the teacher's modal strength without strengthening it.

    Requirement markers are checked first, because Persian «نباید» contains
    «باید». Anything unmarked stays UNSPECIFIED rather than becoming a rule.
    """

    form = _norm(text)

    if not form:
        return MODALITY_UNSPECIFIED

    requirement_markers, preference_markers = _structure_markers()

    for marker in tuple(requirement_markers) + _EN_REQUIREMENT:
        if _norm(marker) and _norm(marker) in form:
            return MODALITY_MANDATORY

    for marker in tuple(preference_markers) + _EN_PREFERENCE:
        if _norm(marker) and _norm(marker) in form:
            return MODALITY_RECOMMENDATION

    return MODALITY_UNSPECIFIED


def polarity_of(text):
    """NEGATIVE when the teacher's statement forbids, else POSITIVE.

    Negation is checked FIRST: Persian «نباید» contains «باید», so testing the
    requirement markers first would read a prohibition as a requirement.
    """

    form = _norm(text)

    for marker in ("نباید", "نبای", "ممنوع", "not ", "never", "no ", "prohibited", "without"):
        if marker in form:
            return "NEGATIVE"

    return "POSITIVE"


# ----------------------------------------------------------
# STORAGE
# ----------------------------------------------------------

def ledger_path(path=None):
    return os.path.abspath(path or DEFAULT_PATH)


def _empty():
    return {"schema": "human_architectural_learning_registry_v1",
            "append_only": True,
            "items": []}


def load_ledger(path=None):
    """Read the ledger. Never creates or modifies it."""

    target = ledger_path(path)

    if not os.path.exists(target):
        return _empty()

    with open(target, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        return _empty()

    payload.setdefault("items", [])

    return payload


def active_rules(path=None):
    return [item for item in load_ledger(path).get("items") or []
            if isinstance(item, dict) and item.get("active")]


def accepted_rules(path=None):
    """Active accepted rules, read through the EXISTING read-only bridge.

    ``KnowledgeReadBridgeV1`` is the established read interface for this
    ledger and refuses writes. The direct loader is only a fallback for an
    isolated path used by tests.
    """

    if path is None:
        try:
            from core.conversation.knowledge_read_bridge_v1 import (
                KnowledgeReadBridgeV1,
            )

            items = KnowledgeReadBridgeV1().learning_registry()

            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]

        except Exception:
            pass

    return active_rules(path)


def _atomic_write(path, payload):
    target = ledger_path(path)
    directory = os.path.dirname(target) or "."

    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=directory,
        prefix=".ledger-",
        suffix=".tmp",
        delete=False,
    )

    try:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, target)
    except Exception:
        handle.close()
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def append_accepted_rule(rule, path=None, confirmed_by=None):
    """Append ONE human-confirmed rule. Refuses everything else.

    ``confirmed_by`` is the explicit human confirmation. Without it nothing is
    written — a recognised statement is not architectural truth.
    """

    if not str(confirmed_by or "").strip():
        raise ValueError(
            "explicit human confirmation is required to accept a rule"
        )

    if not isinstance(rule, dict):
        raise ValueError("rule must be a dict")

    missing = [field for field in REQUIRED_FIELDS if not str(rule.get(field) or "").strip()]

    if missing:
        raise ValueError("rule is missing required fields: %s" % ", ".join(missing))

    payload = load_ledger(path)

    items = payload.get("items") or []

    if any(item.get("id") == rule["id"] for item in items if isinstance(item, dict)):
        raise ValueError(
            "rule %r already exists; use supersede_rule to revise it" % rule["id"]
        )

    observation = str(rule["human_observation_fa"])

    record = {
        "id": str(rule["id"]),
        "date": str(rule.get("date") or time.strftime("%Y-%m-%d")),
        "source_checkpoint": str(rule.get("source_checkpoint") or "HUMAN_TEACHING_T1"),
        "human_observation_fa": observation,
        "generalized_rule": str(rule["generalized_rule"]),
        "scope": str(rule["scope"]),
        "provenance": PROVENANCE_HUMAN_ACCEPTED_RULE,
        "modality": str(rule.get("modality") or modality_of(observation)),
        "confirmed_by": str(confirmed_by),
        "confirmed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "negative_example": rule.get("negative_example"),
        "positive_pattern": rule.get("positive_pattern"),
        "regression_test_ids": list(rule.get("regression_test_ids") or []),
        "superseded_by": None,
        "active": True,
    }

    # Teacher-supplied extras are preserved, never overwritten by the defaults.
    for key, value in rule.items():
        if key not in record:
            record[key] = value

    items.append(record)

    payload["items"] = items
    payload.setdefault("append_only", True)

    _atomic_write(path, payload)

    return record


def supersede_rule(rule_id, superseded_by, path=None):
    """Deactivate a rule in favour of another, keeping the full history."""

    payload = load_ledger(path)

    items = payload.get("items") or []

    ids = {item.get("id") for item in items if isinstance(item, dict)}

    if rule_id not in ids:
        raise ValueError("unknown rule %r" % rule_id)

    if superseded_by not in ids:
        raise ValueError("unknown superseding rule %r" % superseded_by)

    if rule_id == superseded_by:
        raise ValueError("a rule cannot supersede itself")

    for item in items:

        if not isinstance(item, dict):
            continue

        if item.get("id") == rule_id:
            item["active"] = False
            item["superseded_by"] = superseded_by

    payload["items"] = items

    _atomic_write(path, payload)

    return load_ledger(path)


# ----------------------------------------------------------
# APPLICABILITY
# ----------------------------------------------------------

#: R3_NIGHT_MATERIAL_FIDELITY_CPU_V1 — SCOPE / OPERATION COMPATIBILITY.
#:
#: `_scope_applies()` matches a rule's scope TOKENS against the request text.
#: `ARCHITECTURAL_GRAPHICS` therefore matched on the single word
#: "architectural", which is present in `image_type` for EVERY rendered
#: facade (`architectural_render_or_photo`). Two accepted furniture-graphics
#: rules (HL-026 semantic SVG furniture symbols, HL-037 semantic/vector/
#: DWG-ready furniture) were consequently injected into a day-to-night
#: relighting instruction — proven in the submitted R3-NIGHT-02 prompt at
#: tokens 243-450 of 648.
#:
#: A furniture-symbol or vector-library contract cannot govern the lighting of
#: a photographed facade. The exclusion is by OPERATION, not by rule: the
#: rules stay accepted and stay available to the architectural-graphics tasks
#: they were taught for (operation absent, or a graphics operation). Nothing is
#: disabled, deleted or superseded.
_SCOPE_EXCLUDED_OPERATIONS = {
    "ARCHITECTURAL_GRAPHICS": ("relight", "replace_finish", "restyle"),
}


def _scope_operation_mismatch(scope, context):
    """The excluded operation for this scope, or None when compatible."""

    scope_text = _norm(scope).upper().replace(" ", "_")

    excluded = _SCOPE_EXCLUDED_OPERATIONS.get(scope_text)

    if not excluded:
        return None

    # `_norm` rewrites underscores to spaces ("replace_finish" ->
    # "replace finish"), so BOTH sides are normalized. Comparing a normalized
    # operation against a raw constant silently disabled the gate.
    operation = _norm(context.get("operation"))

    if operation and operation in {_norm(item) for item in excluded}:
        return operation

    return None


def _scope_applies(scope, context):
    """True when the rule's SCOPE names this request's context.

    ``GENERAL`` deliberately does NOT apply unconditionally: a general rule is
    still only relevant when its own wording overlaps the request. Otherwise
    every general planning principle would be attached to every facade edit.
    """

    scope_text = _norm(scope).upper().replace(" ", "_")

    if not scope_text or scope_text in ("GENERAL", "UNKNOWN"):
        return False

    if scope_text in PROJECT_SCOPES:
        # A project rule is applicable only when the caller declares the same
        # project scope; it never leaks into a generic decision.
        return bool(context.get("allow_project_scoped"))

    scope_tokens = _tokens(scope.replace("_", " "))

    if not scope_tokens:
        return False

    return bool(scope_tokens & _tokens(context.get("text") or ""))


def _normalise_context(context):
    context = context if isinstance(context, dict) else {}

    context_text = " ".join(
        str(value or "")
        for value in (
            context.get("text"),
            context.get("building_type"),
            context.get("image_type"),
        )
    )

    normalised = dict(context)
    normalised["text"] = context_text

    return normalised


def applicable_rules(rules, context=None):
    """Filter accepted rules to those this request may legitimately use.

    A rule is returned only when ``evaluate_rule_applicability`` says
    APPLICABLE. Everything else — irrelevant, superseded, pending, preserved
    subject, unknown style — is excluded rather than guessed.
    """

    context = _normalise_context(context)

    context_tokens = _tokens(context.get("text") or "")

    applicable = []

    for item in rules or []:

        if not isinstance(item, dict):
            continue

        evaluation = evaluate_rule_applicability(item, context)

        if evaluation.get("status") != APPLICABLE:
            continue

        observation = item.get("human_observation_fa")

        applicable.append(
            {
                "id": item.get("id"),
                "generalized_rule": item.get("generalized_rule"),
                "human_observation": observation,
                "scope": str(item.get("scope") or ""),
                "provenance": PROVENANCE_HUMAN_ACCEPTED_RULE,
                "original_provenance": item.get("provenance"),
                "modality": str(item.get("modality") or modality_of(observation)),
                "polarity": polarity_of(observation),
                "match": evaluation.get("reason"),
                "matched_terms": sorted(
                    _tokens(
                        " ".join(
                            str(item.get(key) or "")
                            for key in ("human_observation_fa", "generalized_rule")
                        )
                    ) & context_tokens
                ),
                "active": True,
            }
        )

    return applicable
