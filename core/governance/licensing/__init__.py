"""Licensing domain of the Claim Governance substrate (V1).

The boundary that ASSIGNS a licence to an existing claim.

    Claim reference
        -> LicenceAssignmentRequest
        -> validate the claim reference
        -> validate the licence transition (TransitionValidator)
        -> mint a LicenceRecord
        -> LicenceAssignmentResult

Governance owns licence identity. Assigning a licence does NOT create truth,
does NOT approve a fact, and is NOT confidence. No client may supply a
licence_id.

Dependency direction

    licensing  ->  licence / validation / lineage       ALLOWED
    licensing  ->  any client subsystem                 FORBIDDEN
"""

from __future__ import annotations


from core.governance.licensing.licence_assignment_request_v1 import (
    FORBIDDEN_REQUESTED_LICENCES,
    FORBIDDEN_REQUEST_FIELDS,
    LicenceAssignmentRequest,
    LicenceAssignmentRequestError,
    build_licence_assignment_request,
)
from core.governance.licensing.licence_assignment_result_v1 import (
    FORBIDDEN_RESULT_FIELDS,
    LicenceAssignmentResult,
    LicenceAssignmentResultError,
    build_licence_assignment_result,
)
from core.governance.licensing.licence_assignment_service_v1 import (
    LicenceAssignmentService,
    licence_assignment_service,
)


__all__ = (
    "LicenceAssignmentRequest",
    "build_licence_assignment_request",
    "LicenceAssignmentRequestError",
    "FORBIDDEN_REQUEST_FIELDS",
    "FORBIDDEN_REQUESTED_LICENCES",
    "LicenceAssignmentResult",
    "build_licence_assignment_result",
    "LicenceAssignmentResultError",
    "FORBIDDEN_RESULT_FIELDS",
    "LicenceAssignmentService",
    "licence_assignment_service",
)
