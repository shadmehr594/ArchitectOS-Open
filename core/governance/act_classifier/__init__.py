"""Act classifier boundary of the Claim Governance substrate (V1).

The classifier's ONLY responsibility is to say what KIND of human act occurred.

    it does NOT decide truth
    it does NOT create claims
    it does NOT create licences
    it does NOT create EndorsementEvents

It prepares the boundary only. Nothing here calls the event layer.

Dependency direction

    act_classifier  ->  governance internal value objects only
    act_classifier  ->  vision / conversation / knowledge / reasoning / LLM    FORBIDDEN
"""

from __future__ import annotations


from core.governance.act_classifier.act_classification_v1 import (
    ACT_TYPES,
    CONFIDENCE_DESCRIPTORS,
    FORBIDDEN_CLASSIFICATION_FIELDS,
    ActClassification,
    ActClassificationError,
    build_act_classification,
)
from core.governance.act_classifier.act_classifier_v1 import (
    ActClassifier,
    act_classifier,
)


__all__ = (
    "ActClassification",
    "build_act_classification",
    "ActClassificationError",
    "ACT_TYPES",
    "CONFIDENCE_DESCRIPTORS",
    "FORBIDDEN_CLASSIFICATION_FIELDS",
    "ActClassifier",
    "act_classifier",
)
