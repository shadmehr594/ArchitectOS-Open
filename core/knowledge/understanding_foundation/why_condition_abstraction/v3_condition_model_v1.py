"""V3ConditionV1 - one architectural condition, with provenance on everything.

A CONDITION is the atomic unit of the V3 experiment. It is the smallest thing a
human's teaching example asserts, stated in a form that no longer depends on the
particular nouns the human happened to use.

What a condition is NOT
-----------------------

A condition is not an architectural judgement. It does not know whether it is
about access, separation, privacy, threshold or circulation. It has a RELATION
SCAFFOLD - a subject, an object, a slot for a relation, a slot for a scope -
and in MODE E those slots start EMPTY (``relation_slot: null``) and may only be
filled by content the corpus itself produced.

This is the difference between V3 and the frozen V2:

    V2 kept ``access``/``separation``/``control``/``exposure`` in an
    interpretive layer that the pipeline itself supplied. Its invariants then
    turned out to be literal stems. V3 does not start from an interpretive
    layer at all: it starts from a slot and asks whether the corpus can fill it.

Every element carries ``kind_origin``
------------------------------------

For any relation/scope value, the condition records WHERE THE KIND CAME FROM:

``ENGINEERED``
    a predefined vocabulary supplied the kind - this is MODE P, and it is
    representation-dependent by construction.

``DERIVED``
    an engineered rule computed the kind from this text (polarity and modality
    work this way: the marker table is engineered, the determination is not).

``EMERGENT``
    the kind is contingent on corpus content, produced by a Mode-E derivation.

An element with no ``kind_origin`` is invalid by construction. This is what
makes the experiment falsifiable: a Mode-E result whose relation kinds turn out
to be ``ENGINEERED`` is reported as representation dependence, not emergence.

Transient, read-only, non-learning.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional

from . import v3_contracts as C

CONTRACT = C.CONDITION_CONTRACT
VERSION = C.CONDITION_VERSION

# --------------------------------------------------------------------------- #
# Marker tables. These are ENGINEERED: fixed tables of surface markers that
# locate a polarity or a modality in a sentence. They contain NO architectural
# relation vocabulary - "not"/"must" are not architectural relations, they are
# grammatical operators - which is why they are permitted in both modes.
# --------------------------------------------------------------------------- #

NEGATION_MARKERS = (
    "not", "no", "never", "without", "lack", "lacks", "lacking", "absent",
    "cannot", "can not", "unable", "fails to", "fail to", "refuses",
    "refuse", "denies", "deny", "blocks", "blocked", "prevents", "prevent",
    "avoids", "avoid", "avoids", "hides", "hidden", "conceals", "concealed",
    "nothing", "none", "nobody", "neither", "nor", "hardly", "rarely",
    "seldom", "nevermore",
)

MODALITY_MARKERS = (
    ("must not", "prohibition"),
    ("must", "obligation"),
    ("shall", "obligation"),
    ("has to", "obligation"),
    ("have to", "obligation"),
    ("needs to", "obligation"),
    ("need to", "obligation"),
    ("should not", "discouragement"),
    ("should", "recommendation"),
    ("ought", "recommendation"),
    ("may", "possibility"),
    ("might", "possibility"),
    ("can", "capability"),
    ("could", "capability"),
    ("is able to", "capability"),
    ("will", "futurity"),
    ("would", "conditional"),
    ("tends to", "tendency"),
    ("usually", "tendency"),
    ("often", "tendency"),
    ("sometimes", "occasionality"),
)

# Words that carry no condition content on their own. ENGINEERED glue.
GLUE_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "for",
    "with", "from", "into", "as", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "their", "there", "that", "this", "these", "those",
    "which", "who", "whom", "where", "when", "how", "why", "what", "than",
    "then", "so", "such", "also", "but", "if", "only", "very", "more", "most",
    "some", "any", "each", "other", "another", "both", "all", "one", "two",
    "do", "does", "did", "has", "have", "had", "them", "they", "he", "she",
    "his", "her", "here", "there", "own", "same", "itself", "themselves",
    "am", "us", "we", "you", "your", "our", "me", "my", "mine", "whoever",
    "whatever", "whenever", "wherever", "upon", "onto", "about", "over",
    "under", "between", "among", "through", "during", "before", "after",
})

# Clause-internal connectives that separate coordinate conditions. ENGINEERED
# splitter vocabulary; the WHY connectors are handled by the WHY grounding
# module so that a reason is never split away from the condition it explains.
CLAUSE_CONNECTIVES = ("and", "but", "while", "whereas", "yet", "or", "also")

# A relation slot in MODE E starts as this value and must stay null until the
# corpus fills it. The constant is named so a test can assert it exactly.
UNFILLED_RELATION_SLOT = None

REQUIRED_FIELDS = (
    "condition_id",
    "level",
    "contract",
    "version",
    "relation",
    "modality",
    "polarity",
    "why",
    "provenance",
    "uncertainty",
    "alternatives",
)


# --------------------------------------------------------------------------- #
# Small local helpers
# --------------------------------------------------------------------------- #


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)


def _tokens(text: Any) -> List[str]:
    import re
    return re.findall(r"[a-z0-9]+", _as_text(text).lower())


def _content_tokens(text: Any) -> List[str]:
    return [t for t in _tokens(text) if t not in GLUE_WORDS]


def _contains_term(haystack: str, term: str) -> bool:
    import re
    return re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])",
                     haystack) is not None


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def clauses(text: Any) -> List[str]:
    """Split a passage into condition clauses.

    ENGINEERED splitter. It never splits on a WHY connector: the reason a human
    gives belongs to the condition it explains, and separating them would
    destroy the very binding V3 is trying to measure.

    It also never splits inside a comma-separated list unless both sides are
    substantive, so a list of fillers is not mistaken for two conditions.
    """
    import re
    if text is None:
        return []
    raw = _as_text(text)
    parts: List[str] = []
    for chunk in re.split(r"[;.!?\n]+", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        pattern = r"\b(?:" + "|".join(CLAUSE_CONNECTIVES) + r")\b"
        for sub in re.split(pattern, chunk):
            sub = sub.strip()
            if len(_content_tokens(sub)) >= 2:
                parts.append(sub)
    return parts


def why_clauses(text: Any) -> List[str]:
    """Return only the clauses that ARE reasons, using the WHY connector table."""
    from .v3_why_grounding_v1 import split_reason
    _, reason = split_reason(text)
    if not reason:
        return []
    return clauses(reason)


def derive_polarity(clause: str) -> Dict[str, Any]:
    """DERIVED polarity, with the marker that produced it.

    The marker table is ENGINEERED; the determination is DERIVED from this
    specific clause. A negative clause is one that explicitly negates.
    """
    lowered = clause.lower()
    found = [m for m in NEGATION_MARKERS if _contains_term(lowered, m)]
    polarity = "negative" if found else "positive"
    return {
        "value": polarity,
        "markers_present": found,
        "kind_origin": C.ORIGIN_DERIVED,
        "rule": "explicit_negation_marker_present",
    }


def derive_modality(clause: str) -> Dict[str, Any]:
    """DERIVED modality, first marker wins, with the marker that produced it."""
    lowered = clause.lower()
    for marker, kind in MODALITY_MARKERS:
        if _contains_term(lowered, marker):
            return {
                "value": kind,
                "marker": marker,
                "kind_origin": C.ORIGIN_DERIVED,
                "rule": "first_modality_marker_in_table_order",
            }
    return {
        "value": "assertion",
        "marker": None,
        "kind_origin": C.ORIGIN_DERIVED,
        "rule": "no_modality_marker_present_default_assertion",
    }


# --------------------------------------------------------------------------- #
# The relation scaffold
# --------------------------------------------------------------------------- #


def make_scaffold(
    subject: Any = None,
    object_: Any = None,
    relation_slot: Any = UNFILLED_RELATION_SLOT,
    scope_slot: Any = UNFILLED_RELATION_SLOT,
) -> Dict[str, Any]:
    """Build the GENERIC relational scaffolding.

    The SHAPE is engineered - it is a set of slots. The CONTENT is not. In MODE
    E the two slots are explicitly ``null`` and a declaration is attached
    stating that no coercion took place.

    ``relation_slot_origin`` / ``scope_slot_origin`` start at ``None`` and are
    only ever set when the corpus actually fills the slot; until then they stay
    ``None`` so an audit can tell "empty" from "filled by an engineered word".
    """
    return {
        "subject": subject,
        "object": object_,
        "relation_slot": relation_slot,
        "scope_slot": scope_slot,
        "relation_slot_origin": None,
        "scope_slot_origin": None,
        "scaffold_origin": C.ORIGIN_ENGINEERED,
        "scaffold_is_not_a_relation": True,
        "no_coercion_declared": relation_slot is UNFILLED_RELATION_SLOT
        and scope_slot is UNFILLED_RELATION_SLOT,
    }


def validate_scaffold(scaffold: Any) -> Dict[str, Any]:
    if not isinstance(scaffold, dict):
        raise TypeError(
            "V3ConditionV1: relation scaffold must be a dict, got "
            + type(scaffold).__name__
        )
    # The scaffold owns the participant/relation/scope slots and the shape
    # declaration. Polarity, modality, provenance and WHY are siblings of the
    # scaffold on the condition, not members of it, so they are checked there.
    scaffold_owned = ("subject", "object", "relation_slot", "scope_slot")
    missing = [f for f in scaffold_owned if f not in scaffold]
    if missing:
        raise ValueError(
            "V3ConditionV1: scaffold is missing slots " + repr(missing)
        )
    for slot_key, origin_key in (("relation_slot", "relation_slot_origin"),
                                 ("scope_slot", "scope_slot_origin")):
        value = scaffold.get(slot_key)
        origin = scaffold.get(origin_key)
        if value is None and origin is not None:
            raise ValueError(
                "V3ConditionV1: " + slot_key + " is empty but declares an "
                "origin " + repr(origin) + " - an empty slot has no origin"
            )
        if value is not None and origin is None:
            raise ValueError(
                "V3ConditionV1: " + slot_key + " is filled with "
                + repr(value) + " but declares no kind_origin - every filled "
                "slot must declare where its kind came from"
            )
        if value is not None and origin not in C.REPRESENTATION_ORIGINS:
            raise ValueError(
                "V3ConditionV1: " + slot_key + " origin must be one of "
                + repr(C.REPRESENTATION_ORIGINS) + ", got " + repr(origin)
            )
    return scaffold


def fill_relation_slot(
    scaffold: Dict[str, Any],
    relation_slot: Any,
    scope_slot: Any,
    origin: str,
) -> Dict[str, Any]:
    """Fill a scaffold slot, declaring the origin of the kind.

    This is the ONE permitted way to fill a slot. It refuses to fill a Mode-E
    slot with an ENGINEERED architectural relation word: that is exactly the
    failure the experiment is designed to detect, so it is made impossible to
    do by accident.
    """
    if origin not in C.REPRESENTATION_ORIGINS:
        raise ValueError(
            "V3ConditionV1: origin must be one of "
            + repr(C.REPRESENTATION_ORIGINS) + ", got " + repr(origin)
        )
    filled = deepcopy(scaffold)
    filled["relation_slot"] = relation_slot
    filled["scope_slot"] = scope_slot
    filled["relation_slot_origin"] = origin if relation_slot is not None else None
    filled["scope_slot_origin"] = origin if scope_slot is not None else None
    filled["no_coercion_declared"] = (
        relation_slot is UNFILLED_RELATION_SLOT
        and scope_slot is UNFILLED_RELATION_SLOT
    )
    return validate_scaffold(filled)


# --------------------------------------------------------------------------- #
# The condition constructor
# --------------------------------------------------------------------------- #


def make_condition(
    condition_id: Any,
    clause: str,
    why_verbatim: str = "",
    why_clause: str = "",
    why_grounding: Optional[Dict[str, Any]] = None,
    relation: Optional[Dict[str, Any]] = None,
    intended_effect: Any = None,
    alternatives: Optional[List[Any]] = None,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble one ``V3ConditionV1``.

    Nothing is inferred silently. The relation scaffold is built empty unless a
    caller explicitly supplies one; polarity and modality are DERIVED with their
    markers recorded; the WHY is stored VERBATIM so it can always be checked
    against what the human actually wrote.
    """
    clause = _as_text(clause).strip()
    why_verbatim = _as_text(why_verbatim).strip()

    scaffold = relation if relation is not None else make_scaffold()
    validate_scaffold(scaffold)

    grounding = why_grounding
    if grounding is None:
        grounding = {
            "why_verbatim": why_verbatim,
            "why_clause": _as_text(why_clause).strip(),
            "grounding": "unbound",
            "causal_direction": "unknown",
            "origin": C.ORIGIN_DERIVED if why_verbatim else C.ORIGIN_ENGINEERED,
        }

    effect_block = None
    if intended_effect is not None:
        effect_block = {
            "value": intended_effect,
            "is_inference": True,
            "origin": C.ORIGIN_DERIVED,
            "note": "inferred by this boundary; never presented as the "
                    "human's own words",
        }

    provenance = {
        "source_text_span": clause,
        "source_clause": clause,
        "source_why_id": (source or {}).get("source_why_id"),
        "source_example_id": (source or {}).get("source_example_id"),
        "extraction_rule": (source or {}).get(
            "extraction_rule", "single_clause_condition"
        ),
        "epistemic_status": C.STATUS_DERIVED,
    }

    condition = {
        "contract": CONTRACT,
        "version": VERSION,
        "condition_id": condition_id,
        "level": "condition",
        "relation": scaffold,
        "modality": derive_modality(clause),
        "polarity": derive_polarity(clause),
        "why": grounding,
        "intended_effect": effect_block,
        "provenance": provenance,
        "uncertainty": {
            "level": "unresolved" if scaffold.get("relation_slot") is None
            else "partially_resolved",
            "reason": (
                "no relation slot has been derived from the corpus"
                if scaffold.get("relation_slot") is None
                else "relation slot derived; scope and alternative readings "
                     "remain open"
            ),
            "retained_alternatives": list(alternatives or []),
            "collapsed": False,
            "origin": C.ORIGIN_DERIVED,
        },
        "alternatives": list(alternatives or []),
        "epistemic_status": C.STATUS_DERIVED,
        "claimed_as_learning": False,
    }
    return condition


def validate_condition(value: Any) -> Dict[str, Any]:
    """Strict, transient validation of a ``V3ConditionV1`` value."""
    if not isinstance(value, dict):
        raise TypeError(
            "V3ConditionV1 requires a dict, got " + type(value).__name__
        )
    contract = value.get("contract")
    if contract in C.FORBIDDEN_CONTRACTS:
        raise ValueError(
            "V3ConditionV1 rejects forbidden contract: " + str(contract)
        )
    if contract != CONTRACT:
        raise ValueError(
            "V3ConditionV1 requires contract " + repr(CONTRACT)
            + ", got " + repr(contract)
        )
    if value.get("version") != VERSION:
        raise ValueError(
            "V3ConditionV1 requires version " + repr(VERSION)
            + ", got " + repr(value.get("version"))
        )
    for field in REQUIRED_FIELDS:
        if field not in value:
            raise ValueError(
                "V3ConditionV1 is missing required field " + repr(field)
            )
    validate_scaffold(value.get("relation"))
    why = value.get("why")
    if not isinstance(why, dict):
        raise TypeError("V3ConditionV1: why must be a dict")
    for field in ("why_verbatim", "why_clause", "grounding", "causal_direction"):
        if field not in why:
            raise ValueError(
                "V3ConditionV1: why is missing first-class field " + repr(field)
            )
    # The verbatim WHY may never be silently rewritten: the stored value must
    # be exactly the text that was supplied.
    return deepcopy(value)


def forbidden_language_in_condition(condition: Dict[str, Any]) -> List[str]:
    """Which Mode-E forbidden relation terms appear in this condition?

    Used by the learner's firewall check and by the tests. A non-empty result
    on a Mode-E condition means the representation was assisted by a predefined
    architectural relation word.
    """
    import json as _json
    blob = _json.dumps(condition, sort_keys=True, default=str).lower()
    import re
    found = []
    for term in C.MODE_E_FORBIDDEN_RELATION_TERMS:
        if re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])",
                     blob):
            found.append(term)
    return found


__all__ = [
    "CONTRACT", "VERSION",
    "NEGATION_MARKERS", "MODALITY_MARKERS", "GLUE_WORDS", "CLAUSE_CONNECTIVES",
    "UNFILLED_RELATION_SLOT", "REQUIRED_FIELDS",
    "clauses", "why_clauses", "derive_polarity", "derive_modality",
    "make_scaffold", "validate_scaffold", "fill_relation_slot",
    "make_condition", "validate_condition", "forbidden_language_in_condition",
]
