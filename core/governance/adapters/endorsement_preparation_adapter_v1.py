"""Human text -> EndorsementRequest preparation adapter (V1).

PREPARATION ONLY.

This adapter classifies the human act and builds an authority-free
EndorsementRequest. It does NOT create an EndorsementEvent, does NOT call the
endorsement service, and does NOT modify the conversation layer.

The gate that decides remains the EndorsementService; this adapter only
prepares its input. It deliberately imports the REQUEST module only — never the
service module — so it cannot call the service.
"""

from __future__ import annotations


from typing import Optional


from core.governance.act_classifier import act_classifier
from core.governance.endorsement.endorsement_request_v1 import (
    EndorsementRequest,
    build_endorsement_request,
)


CONTRACT = "EndorsementPreparationAdapterV1"

VERSION = "1.0"


class EndorsementPreparationAdapterError(ValueError):
    """Raised when an endorsement request cannot be prepared."""


def prepare_endorsement_request(
    text,
    *,
    actor_reference,
    target_claim_reference,
    requested_scope: Optional[str] = None,
    text_reference: Optional[str] = None,
    language: Optional[str] = None,
) -> EndorsementRequest:

    """Classify the act and prepare an authority-free EndorsementRequest."""

    classification = act_classifier.classify(
        text,
        text_reference=text_reference,
        language=language,
    )

    return build_endorsement_request(
        actor_reference=actor_reference,
        target_claim_reference=target_claim_reference,
        act_classification=classification,
        requested_scope=requested_scope,
    )
