"""Endorsement wiring of the Claim Governance substrate (V1).

Human input does NOT modify a claim directly. The only path is

    human text
        -> ActClassifier
        -> ActClassification
        -> EndorsementRequest
        -> governance validation
        -> EndorsementEvent
        -> licence transition

This package prepares that path INSIDE governance. It does not touch the chat
pipeline, the conversation layer or the human-feedback routing.

Dependency direction

    endorsement  ->  governance internal only (act_classifier, events,
                     licence, validation, claim)          ALLOWED
    endorsement  ->  vision / conversation / knowledge / reasoning   FORBIDDEN
"""

from __future__ import annotations


from core.governance.endorsement.endorsement_request_v1 import (
    FORBIDDEN_REQUEST_FIELDS,
    EndorsementRequest,
    EndorsementRequestError,
    build_endorsement_request,
)
from core.governance.endorsement.endorsement_service_v1 import (
    ENDORSEMENT_LICENCE,
    SERVICE_RULE_CODES,
    EndorsementPreparationResult,
    EndorsementService,
    endorsement_service,
)


__all__ = (
    "EndorsementRequest",
    "build_endorsement_request",
    "EndorsementRequestError",
    "FORBIDDEN_REQUEST_FIELDS",
    "EndorsementService",
    "endorsement_service",
    "EndorsementPreparationResult",
    "ENDORSEMENT_LICENCE",
    "SERVICE_RULE_CODES",
)
