"""Client adapters of the Claim Governance substrate (V1).

Adapters CONNECT existing ArchitectOS structures to governance WITHOUT
transferring ownership. They convert; they do not own, mint or decide.

    AUv2 projection        -> InterpretationProposal
    TeachingCandidate      -> advisory proposal material
    human text             -> EndorsementRequest (preparation only)

Ownership stays where it was: AUv2 stays vision-owned, TeachingCandidate stays
conversation-owned. Governance acquires no ownership and no client import.

Dependency direction

    adapters  ->  core.governance                       ALLOWED
    adapters  ->  vision / conversation / knowledge     FORBIDDEN
"""

from __future__ import annotations


from core.governance.adapters.auv2_proposal_adapter_v1 import (
    Auv2AdapterError,
    PROJECTION_ID_PREFIX,
    to_proposal,
    to_proposals,
)
from core.governance.adapters.endorsement_preparation_adapter_v1 import (
    EndorsementPreparationAdapterError,
    prepare_endorsement_request,
)
from core.governance.adapters.teaching_candidate_adapter_v1 import (
    TeachingCandidateAdapterError,
    TeachingProposalMaterial,
    to_proposal_material,
)


__all__ = (
    "to_proposals",
    "to_proposal",
    "Auv2AdapterError",
    "PROJECTION_ID_PREFIX",
    "to_proposal_material",
    "TeachingProposalMaterial",
    "TeachingCandidateAdapterError",
    "prepare_endorsement_request",
    "EndorsementPreparationAdapterError",
)
