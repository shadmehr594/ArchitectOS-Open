"""TransitionResult (V1) — the immutable answer of the validator.

A result is a JUDGEMENT, not an action: it creates nothing, mutates nothing and
assigns nothing. It carries exactly three fields — allowed, reason, rule_code.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict


CONTRACT = "TransitionResultV1"

VERSION = "1.0"


RULE_ALLOWED = "allowed"

RULE_NOT_IMPLEMENTED = "not_implemented"


RULE_CODES = (
    "allowed",
    "not_implemented",
    "missing_identity",
    "missing_origin",
    "missing_source_type",
    "unknown_source_type",
    "missing_claim_type",
    "unknown_claim_type",
    "missing_licence_reference",
    "missing_creation_event",
    "forbidden_truth_field",
    "invalid_lineage",
    "unknown_previous_licence",
    "unknown_new_licence",
    "forbidden_licence",
    "undefined_transition",
    "missing_event_field",
    "unknown_operation_type",
    "unknown_act_type",
    "event_targets_observation",
    "event_creates_truth",
    "event_mutates_content",
    "unresolved_reference",
    "claim_not_typed",
    "claim_not_scoped",
    "claim_not_licensed",
    "claim_lineage_incomplete",
)


@dataclass(frozen=True)
class TransitionResult:

    allowed: bool

    reason: str

    rule_code: str

    def __post_init__(self):

        if self.rule_code not in RULE_CODES:

            raise ValueError(
                "unknown rule_code: %r" % (self.rule_code,)
            )

    @staticmethod
    def allow(
        reason: str = "transition permitted",
        rule_code: str = RULE_ALLOWED,
    ) -> "TransitionResult":

        return TransitionResult(True, reason, rule_code)

    @staticmethod
    def deny(rule_code: str, reason: str) -> "TransitionResult":

        return TransitionResult(False, reason, rule_code)

    @staticmethod
    def not_implemented(feature: str) -> "TransitionResult":

        return TransitionResult(
            False,
            "not implemented in V1: %s" % (feature,),
            RULE_NOT_IMPLEMENTED,
        )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "allowed": self.allowed,
            "reason": self.reason,
            "rule_code": self.rule_code,
        }

    def __repr__(self):

        return "TransitionResult(allowed=%r, rule_code=%r)" % (
            self.allowed,
            self.rule_code,
        )
