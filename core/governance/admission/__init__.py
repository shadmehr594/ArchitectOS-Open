"""Knowledge admission of the Claim Governance substrate (V1).

The boundary that evaluates whether an existing governed Claim + licence state
is ELIGIBLE to become a Knowledge Candidate.

Knowledge admission is NOT truth, NOT approval and NOT fact creation. It is a
governed candidate issuance step only.

Dependency direction

    admission  ->  claim / licence / lineage / validation / admission   ALLOWED
    admission  ->  vision / conversation / knowledge / reasoning / chat  FORBIDDEN
"""

from __future__ import annotations


from core.governance.admission.knowledge_admission_result_v1 import (
    FORBIDDEN_RESULT_FIELDS,
    KnowledgeAdmissionResult,
    KnowledgeAdmissionResultError,
    build_knowledge_admission_result,
)
from core.governance.admission.knowledge_admission_service_v1 import (
    KnowledgeAdmissionService,
    knowledge_admission_service,
)
from core.governance.admission.knowledge_candidate_v1 import (
    CANDIDATE_REFERENCE_PREFIX,
    FORBIDDEN_CANDIDATE_FIELDS,
    KnowledgeCandidate,
    KnowledgeCandidateError,
    build_knowledge_candidate,
    derive_candidate_reference,
)


__all__ = (
    "KnowledgeCandidate",
    "build_knowledge_candidate",
    "derive_candidate_reference",
    "KnowledgeCandidateError",
    "CANDIDATE_REFERENCE_PREFIX",
    "FORBIDDEN_CANDIDATE_FIELDS",
    "KnowledgeAdmissionResult",
    "build_knowledge_admission_result",
    "KnowledgeAdmissionResultError",
    "FORBIDDEN_RESULT_FIELDS",
    "KnowledgeAdmissionService",
    "knowledge_admission_service",
)
