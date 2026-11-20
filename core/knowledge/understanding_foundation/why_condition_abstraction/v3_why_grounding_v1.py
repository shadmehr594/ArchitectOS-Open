"""V3WhyGroundingV1 - the WHY as a first-class participant.

V2 recorded a human's reason, but the reason never carried the abstraction: the
derived invariants were stems, and a WHY swap only removed them because the
reasons happened to supply those same stems. V3 treats the WHY as a participant
with its own structure, and it measures the BINDING between a condition and a
reason rather than assuming one.

What grounding means here
-------------------------

A condition is GROUNDED when a human's reason is about THAT condition: the
reason and the condition share content, and the reason's own causal direction
can be read from the text.

A condition is UNGROUNDED when no reason is supplied, or when the reason shares
nothing with it. An ungrounded condition is not discarded - it is retained and
labelled, because silently dropping it would hide the fact that the abstraction
rests on ungrounded material.

The three grounding verdicts
----------------------------

``necessary``   the reason is about this condition and nothing in the condition
                text repeats the reason verbatim as filler - the reason is
                doing work.
``context``     the reason and the condition share content, but the condition
                text already contains it: the reason is consistent with the
                situation rather than the point of it.
``unbound``     no usable binding. Reported, never hidden.

Determination vs claim
----------------------

These are DETERMINATIONS reached by an engineered rule over emergent content,
never truth claims about human intent. Every determination carries the rule that
produced it and the evidence it used.

Transient, read-only, non-learning.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from . import v3_contracts as C

CONTRACT = C.WHY_GROUNDING_CONTRACT
VERSION = C.WHY_GROUNDING_VERSION

# --------------------------------------------------------------------------- #
# WHY connectors. ENGINEERED: these locate the boundary between a condition and
# the human's reason for it. They contain no architectural vocabulary - they are
# ordinary causal connectives.
#
# Ordered longest-first so "so that" is matched before "so".
# --------------------------------------------------------------------------- #

WHY_CONNECTORS = (
    "for this reason",
    "as a result of",
    "as a result",
    "in order to",
    "in order that",
    "so that",
    "which means",
    "this means",
    "that means",
    "the reason is",
    "the reason being",
    "which allows",
    "which lets",
    "which keeps",
    "which prevents",
    "which avoids",
    "allowing",
    "enabling",
    "permitting",
    "to allow",
    "to enable",
    "to avoid",
    "to prevent",
    "to keep",
    "to let",
    "to stop",
    "to make sure",
    "the point is",
    "that way",
    "for the purpose of",
    "because of",
    "because",
    "since",
    "therefore",
    "thus",
    "hence",
    "so",
)

# The connector table must never contain an architectural relation word; a test
# asserts it against the Mode-E firewall.
CONNECTOR_TABLE_IS_ENGINEERED = True

# Causal direction of a reason, read from its own markers. ENGINEERED table,
# DERIVED determination.
DIRECTION_PURPOSE_MARKERS = (
    "in order to", "so that", "to allow", "to enable", "to avoid",
    "to prevent", "to keep", "to let", "to stop", "to make sure", "that way",
    "which allows", "which lets", "which keeps", "which prevents",
    "which avoids", "allowing", "enabling", "permitting",
    # Deontic need-markers: a reason stated as a requirement is a PURPOSE, not
    # a cause. "the user needs to recover" says what the condition is FOR.
    "needs to", "need to", "has to", "have to", "requires", "require",
    "deserves", "deserve",
)
DIRECTION_CAUSE_MARKERS = (
    "because", "because of", "since", "as a result", "as a result of",
    "for this reason", "due to", "owing to", "stems from", "arises from",
)
DIRECTION_CONSEQUENCE_MARKERS = (
    "therefore", "thus", "hence", "so", "which means", "this means",
    "that means",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)


def split_reason(text: Any) -> Tuple[str, str]:
    """Split a teaching sentence into (condition_part, reason_part).

    ENGINEERED. The FIRST winning connector decides the split; connectors are
    tested longest-first so "so that" is never truncated to "so". If no
    connector is present the whole text is the condition and the reason is
    empty - V3 does not invent a reason.

    The reason is returned VERBATIM from the original text, so it can always be
    compared against what the human actually wrote.
    """
    import re
    raw = _as_text(text)
    lowered = raw.lower()

    # The discontinuous purpose construction "for <subject> to <verb>" has no
    # single connector token, so it is matched structurally first. It is an
    # ordinary English purpose form, not architectural vocabulary.
    discontinuous = re.search(
        r"(?<![a-z0-9_])for(?![a-z0-9_])(.{1,40}?)(?<![a-z0-9_])to(?![a-z0-9_])",
        lowered,
    )
    if discontinuous is not None:
        condition = raw[: discontinuous.start()].strip(" ,;.")
        reason = raw[discontinuous.start():].strip(" ,;.")
        if condition and reason:
            return condition, reason

    for connector in WHY_CONNECTORS:
        pattern = r"(?<![a-z0-9_])" + re.escape(connector) + r"(?![a-z0-9_])"
        match = re.search(pattern, lowered)
        if match is None:
            continue
        condition = raw[: match.start()].strip(" ,;.")
        reason = raw[match.end():].strip(" ,;.")
        if condition and reason:
            return condition, reason
        # A connector at position 0 makes the whole text a reason with no
        # stated condition; that is recorded honestly rather than guessed.
        if reason and not condition:
            return "", reason
    return raw.strip(), ""


def _stem_light(token: str) -> str:
    """A deliberately SHALLOW fold, used for the binding overlap only.

    V3 does not rely on this fold for abstraction: it is used solely to ask
    whether a reason and a condition are about overlapping material. The fold is
    kept minimal on purpose - V2's aggressive stem folder was what made its
    invariants turn out to be literal stems. V3 keeps the fold blunt so that a
    binding cannot be manufactured by morphology alone.
    """
    t = token.lower()
    # An "-es" plural only follows a sibilant, so it must be tested BEFORE the
    # plain "-s" rule or "watches" would be folded to "watche". The order below
    # is the whole fix: "-ses"/"-ches"/"-shes"/"-xes"/"-zes" drop two letters.
    for ending in ("ses", "ches", "shes", "xes", "zes"):
        if t.endswith(ending) and len(t) - 2 >= 3:
            return t[:-2]
    if t.endswith("s") and not t.endswith("ss") and len(t) - 1 >= 3:
        return t[:-1]
    return t


def _overlap(a: str, b: str) -> List[str]:
    from .v3_condition_model_v1 import _content_tokens
    left = {_stem_light(t) for t in _content_tokens(a)}
    right = {_stem_light(t) for t in _content_tokens(b)}
    return sorted(left & right)


def read_causal_direction(reason: str) -> Dict[str, Any]:
    """DERIVED direction of the human's reason, with the marker that produced it."""
    import re
    lowered = _as_text(reason).lower()
    checks = (
        ("purpose", DIRECTION_PURPOSE_MARKERS),
        ("cause", DIRECTION_CAUSE_MARKERS),
        ("consequence", DIRECTION_CONSEQUENCE_MARKERS),
    )
    for direction, markers in checks:
        for marker in markers:
            if re.search(r"(?<![a-z0-9_])" + re.escape(marker)
                         + r"(?![a-z0-9_])", lowered):
                return {
                    "value": direction,
                    "marker": marker,
                    "kind_origin": C.ORIGIN_DERIVED,
                    "rule": "first_direction_marker_by_table_order",
                }
    return {
        "value": "unknown",
        "marker": None,
        "kind_origin": C.ORIGIN_DERIVED,
        "rule": "no_direction_marker_present",
    }


def ground_condition(
    condition_text: Any,
    reason_text: Any,
    source_why_id: Any = None,
    source_example_id: Any = None,
) -> Dict[str, Any]:
    """Build the ``V3WhyGroundingV1`` record binding a condition to a reason.

    The record states: the verbatim reason, the reason's clause, its causal
    direction, whether it is bound to the condition, the determination, and the
    rule and evidence used to reach it.
    """
    condition_text = _as_text(condition_text).strip()
    reason_verbatim = _as_text(reason_text).strip()

    direction = read_causal_direction(reason_verbatim)
    shared = _overlap(condition_text, reason_verbatim) if reason_verbatim else []

    if not reason_verbatim:
        determination = "unbound"
        grounding = "no_reason_supplied"
        rule = "reason_required_but_absent"
    elif not shared:
        determination = "unbound"
        grounding = "reason_shares_no_content_with_condition"
        rule = "binding_requires_shared_content"
    else:
        # Does the CONDITION text already contain the shared content on its own?
        # If so the reason is context; if the overlap exists only because the
        # reason names something the condition does not, it is necessary.
        from .v3_condition_model_v1 import _content_tokens
        condition_stems = {_stem_light(t) for t in _content_tokens(condition_text)}
        reason_stems = {_stem_light(t) for t in _content_tokens(reason_verbatim)}
        reason_only = reason_stems - condition_stems
        if reason_only:
            determination = "necessary"
            grounding = "reason_carries_content_the_condition_does_not"
        else:
            determination = "context"
            grounding = "condition_already_states_the_shared_content"
        rule = "binding_shared_content_and_reason_exclusive_content"

    record = {
        "contract": CONTRACT,
        "version": VERSION,
        "why_verbatim": reason_verbatim,
        "why_clause": reason_verbatim,
        "causal_direction": direction,
        "determination": determination,
        "grounding": grounding,
        "binding": {
            "shared_content": shared,
            "shared_content_count": len(shared),
            "bound": determination != "unbound",
        },
        "rule": rule,
        "source_why_id": source_why_id,
        "source_example_id": source_example_id,
        "origin": C.ORIGIN_DERIVED,
        "epistemic_status": C.STATUS_DERIVED,
        "is_a_claim_about_human_intent": False,
        "note": (
            "a DETERMINATION reached by an engineered rule over emergent "
            "content; not a truth claim about what the human meant"
        ),
    }
    return record


def validate_grounding(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3WhyGroundingV1 requires a dict, got " + type(value).__name__
        )
    if value.get("contract") != CONTRACT:
        raise ValueError(
            "V3WhyGroundingV1 requires contract " + repr(CONTRACT)
            + ", got " + repr(value.get("contract"))
        )
    if value.get("version") != VERSION:
        raise ValueError(
            "V3WhyGroundingV1 requires version " + repr(VERSION)
            + ", got " + repr(value.get("version"))
        )
    for field in ("why_verbatim", "why_clause", "causal_direction",
                  "determination", "grounding", "binding", "rule"):
        if field not in value:
            raise ValueError(
                "V3WhyGroundingV1 is missing field " + repr(field)
            )
    if value["determination"] not in ("necessary", "context", "unbound"):
        raise ValueError(
            "V3WhyGroundingV1 determination must be one of "
            "('necessary', 'context', 'unbound'), got "
            + repr(value["determination"])
        )
    return deepcopy(value)


def why_swap_effect(
    original_grounding: Dict[str, Any],
    swapped_grounding: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Measure whether replacing ONLY the WHY changes the grounding.

    Used by the ``WHY_IGNORED`` failure-mode check. If a condition's grounding
    is unchanged after its reason is replaced with an unrelated one, the WHY was
    never being used, and the failure mode fires.

    ``swapped_grounding`` being None means the swap could not be constructed,
    which is INCONCLUSIVE rather than a pass.
    """
    if swapped_grounding is None:
        return {
            "measurable": False,
            "state": "INCONCLUSIVE",
            "reason": "no swapped grounding was supplied",
        }
    before = original_grounding.get("determination")
    after = swapped_grounding.get("determination")
    before_binding = (original_grounding.get("binding") or {}).get("bound")
    after_binding = (swapped_grounding.get("binding") or {}).get("bound")
    before_shared = (original_grounding.get("binding") or {}).get(
        "shared_content_count", 0
    )
    after_shared = (swapped_grounding.get("binding") or {}).get(
        "shared_content_count", 0
    )
    changed = (
        (before != after)
        or (before_binding != after_binding)
        or (before_shared != after_shared)
    )
    # If BOTH the original and the swapped reason are unbound, the swap carries
    # no information about whether the WHY is doing work - the comparison is
    # vacuous and must be reported as INCONCLUSIVE, never as a pass or a fail.
    both_unbound = (before == "unbound") and (after == "unbound")
    if both_unbound:
        state = "INCONCLUSIVE"
        reason = (
            "both the original and the swapped WHY are unbound, so the swap "
            "cannot show whether the WHY is used"
        )
    elif changed:
        state = "MEASURED_PASS"
        reason = "replacing only the WHY changed the grounding"
    else:
        state = "MEASURED_FAIL"
        reason = (
            "replacing only the WHY left the grounding unchanged, so the WHY "
            "was not being used"
        )
    return {
        "measurable": not both_unbound,
        "state": state,
        "determination_before": before,
        "determination_after": after,
        "bound_before": before_binding,
        "bound_after": after_binding,
        "shared_content_count_before": before_shared,
        "shared_content_count_after": after_shared,
        "why_changes_grounding": changed,
        "reason": reason,
    }


__all__ = [
    "CONTRACT", "VERSION",
    "WHY_CONNECTORS", "CONNECTOR_TABLE_IS_ENGINEERED",
    "DIRECTION_PURPOSE_MARKERS", "DIRECTION_CAUSE_MARKERS",
    "DIRECTION_CONSEQUENCE_MARKERS",
    "split_reason", "read_causal_direction", "ground_condition",
    "validate_grounding", "why_swap_effect",
    "grounding_stable_under_text_change",
]


def grounding_stable_under_text_change(
    condition_a: str,
    reason_a: str,
    condition_b: str,
    reason_b: str,
) -> Dict[str, Any]:
    """Compare two groundings for a STABILITY measurement.

    A stability measurement, never learning evidence. If the two groundings
    agree, that tells us the representation is stable for those inputs. It says
    nothing about whether anything was learned. The field name reflects this
    explicitly so the result cannot be misread.
    """
    left = ground_condition(condition_a, reason_a)
    right = ground_condition(condition_b, reason_b)
    fields = ("determination", "causal_direction")
    agreement = {
        field: (left.get(field) == right.get(field)) for field in fields
    }
    return {
        "semantics": C.FINGERPRINT_SEMANTICS,
        "is_learning_evidence": False,
        "agreement": agreement,
        "stable": all(agreement.values()),
        "left_determination": left.get("determination"),
        "right_determination": right.get("determination"),
        "note": "representation stability only; never evidence of learning",
    }
