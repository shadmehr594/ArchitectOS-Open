"""Validation domain of the Claim Governance substrate (V1).

The validator is a GUARD.

    it does NOT create objects
    it does NOT mutate state
    it does NOT assign licences

It answers only: ALLOW / DENY + reason, as an immutable TransitionResult.

Dependency direction

    validation  ->  claim / licence / events / lineage     ALLOWED
    validation  ->  any client subsystem                   FORBIDDEN
    claim / licence / events / lineage  ->  validation     FORBIDDEN
"""

from __future__ import annotations


from core.governance.validation.transition_result_v1 import (
    RULE_CODES,
    RULE_ALLOWED,
    RULE_NOT_IMPLEMENTED,
    TransitionResult,
)
from core.governance.validation.transition_validator_v1 import (
    ALLOWED_LICENCE_TRANSITIONS,
    TransitionValidator,
    transition_validator,
)


__all__ = (
    "TransitionResult",
    "RULE_CODES",
    "RULE_ALLOWED",
    "RULE_NOT_IMPLEMENTED",
    "TransitionValidator",
    "transition_validator",
    "ALLOWED_LICENCE_TRANSITIONS",
)
