"""ArchitectOS Claim Governance substrate (V1) — ISOLATED.

This package is the independent governance authority. It owns claim identity,
licence state and the event log. It is a substrate, not a pipeline stage.

DEPENDENCY RULE
    clients     -> governance        ALLOWED
    governance  -> any client        FORBIDDEN

Governance must never import vision, conversation, knowledge, reasoning,
render, CAD, BIM or IFC. The rule is enforced by an AST self-check in
core/governance/tests/test_governance_substrate_v1.py.

V1 SCOPE — implemented
    proposal/   InterpretationProposal          authority-free input boundary
    claim/      Claim                           immutable, governance-minted
    licence/    LicenceRecord                   permission to use
    events/     DerivationEvent, EndorsementEvent   append-only
    lineage/    LineageReference, LineageView, DAG safety
    validation/ TransitionValidator             read-only guard
    act_classifier/  ActClassification          deterministic, no LLM
    endorsement/     EndorsementRequest         human feedback boundary
    adapters/        AUv2 / teaching / endorsement-preparation adapters
    intake/     ProposalReceipt                 accepted-proposal intake
    minting/    ClaimMintingService            proposal -> Claim
    licensing/  LicenceAssignmentService       claim -> LicenceRecord
    admission/  KnowledgeAdmissionService      claim + licence -> candidate

V1 — deliberately NOT implemented
    persistence, pipeline wiring, client integration.

No persistence is implemented. All structures are in-memory value objects.
"""

from __future__ import annotations


CONTRACT = "ClaimGovernanceSubstrateV1"

VERSION = "1.0"


SUBSTRATE_IMPLEMENTED = True


# Named flags so the boundary is auditable rather than merely asserted.
PERSISTENCE_IMPLEMENTED = False

TRANSITION_VALIDATOR_IMPLEMENTED = True

LINEAGE_VIEW_IMPLEMENTED = True

CLIENT_ADAPTERS_IMPLEMENTED = True

ENDORSEMENT_CLASSIFIER_IMPLEMENTED = True

# Implemented by the KNOWLEDGE ADMISSION BOUNDARY V1 (core/governance/admission).
KNOWLEDGE_CANDIDATE_ISSUANCE_IMPLEMENTED = True

PIPELINE_WIRING_IMPLEMENTED = False


# Import roots governance must never depend on (client subsystems).
FORBIDDEN_IMPORT_ROOTS = (
    "core.vision",                   # vision
    "core.conversation",             # conversation
    "core.knowledge",                # knowledge
    "core.architecture.reasoning",   # reasoning
    "core.prompt_intelligence",      # render / prompt
    "core.bim",                      # BIM
    "core.structure",                # structure / IFC
)
