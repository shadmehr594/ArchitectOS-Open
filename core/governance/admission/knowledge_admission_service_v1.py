"""KnowledgeAdmissionService (V1) — the GATE that admits a KnowledgeCandidate.

Knowledge admission answers ONE question: is an existing governed Claim + licence
state ELIGIBLE to become a Knowledge Candidate? It is a gate, never a truth
engine. It returns an immutable KnowledgeAdmissionResult.

Inputs it may consume
    a claim reference
    a licence reference
    lineage references
    the TransitionValidator's verdict

It may NOT
    assign truth (or verified truth / certainty / probability / confidence)
    promote automatically
    transfer client ownership
    modify a Claim
    modify a LicenceRecord
    create a Claim
    create a LicenceRecord
    create an event (none is required by the existing governance contract)
    escalate scope
    bypass the TransitionValidator

Settled vs. unsettled
    The structural rules (input type, forbidden authority fields, claim
    reference, licence reference, lineage completeness, scope vocabulary) are
    settled and are decided here. The ELIGIBILITY rule is settled ONLY when a
    resolved claim is supplied, because the settled rule is
    TransitionValidator.can_be_candidate(). When no claim is supplied, the
    eligibility rule is NOT settled and an explicit NOT_IMPLEMENTED boundary
    result is returned instead of guessing.

Dependency direction

    admission  ->  claim / licence / lineage / validation / admission   ALLOWED
    admission  ->  vision / conversation / knowledge / reasoning / chat  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Iterable, Mapping, Optional


from core.governance.admission.knowledge_admission_result_v1 import (
    KnowledgeAdmissionResult,
    build_knowledge_admission_result,
    not_implemented_admission_result,
)
from core.governance.admission.knowledge_candidate_v1 import (
    FORBIDDEN_CANDIDATE_FIELDS,
    KnowledgeCandidate,
    build_knowledge_candidate,
)
from core.governance.claim import SCOPES
from core.governance.licence import validate_licence_reference
from core.governance.lineage.lineage_reference_v1 import is_claim_reference
from core.governance.validation import transition_validator


CONTRACT = "KnowledgeAdmissionServiceV1"

VERSION = "1.0"


# The ONLY input keys a caller may supply when the candidate is given as a
# mapping. Everything else is refused.
ALLOWED_CANDIDATE_INPUT_FIELDS = (
    "source_claim_reference",
    "claim_reference",
    "licence_reference",
    "scope",
    "lineage_reference",
)


# Input fields that would inject authority, identity or an escalation. A caller
# may never supply these; identity and the candidate reference are DERIVED.
FORBIDDEN_INPUT_FIELDS = tuple(FORBIDDEN_CANDIDATE_FIELDS) + (
    "candidate_reference",
    "claim_id",
    "licence_id",
    "license_id",
    "licence",
    "license",
    "licence_state",
    "created_licence",
    "scope_escalation",
    "escalated_scope",
)


class _AdmissionInputError(ValueError):
    """Raised internally when a supplied input is malformed."""


def _present(value) -> bool:

    return bool(str(value or "").strip())


def _clean_lineage(values) -> tuple:
    """Normalise a lineage input, refusing a bare string and empty items."""

    if values is None:

        return ()

    if isinstance(values, str):

        raise _AdmissionInputError(
            "lineage_reference must be a sequence of references, not a string"
        )

    if not isinstance(values, (list, tuple)):

        try:

            values = list(values)

        except TypeError:

            raise _AdmissionInputError(
                "lineage_reference must be a sequence of references"
            )

    result = []

    for item in values:

        text = str(item or "").strip()

        if not text:

            raise _AdmissionInputError(
                "lineage_reference may not contain an empty reference"
            )

        if text not in result:

            result.append(text)

    return tuple(result)


class KnowledgeAdmissionService:

    """Stateless admission gate. It decides eligibility; it decides nothing else."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    def admit(
        self,
        candidate_input,
        *,
        claim=None,
        known_claim_references: Optional[Iterable[str]] = None,
        known_licence_references: Optional[Iterable[str]] = None,
    ) -> KnowledgeAdmissionResult:

        """Gate a candidate input.

        `candidate_input` is a KnowledgeCandidate (the advisory candidate) OR a
        mapping carrying source_claim_reference, licence_reference, scope and
        lineage_reference.

        `claim` is the OPTIONAL resolved Claim. It is read only, never modified.
        It is required for the settled eligibility rule; without it the gate
        returns an explicit NOT_IMPLEMENTED boundary result.
        """

        # ---- 1. validate candidate input type ----
        if isinstance(candidate_input, KnowledgeCandidate):

            raw = candidate_input.to_dict()

            is_candidate = True

            source_claim_reference = candidate_input.source_claim_reference

            licence_reference = candidate_input.licence_reference

            scope = candidate_input.scope

            lineage_reference = candidate_input.lineage_reference

        elif isinstance(candidate_input, Mapping):

            raw = candidate_input

            is_candidate = False

            source_claim_reference = raw.get(
                "source_claim_reference"
            ) or raw.get("claim_reference")

            licence_reference = raw.get("licence_reference")

            scope = raw.get("scope")

            lineage_reference = raw.get("lineage_reference", ())

        else:

            return self._deny(
                "candidate_not_typed",
                "admission requires a KnowledgeCandidate or a mapping, got %r"
                % (type(candidate_input).__name__,),
            )

        # ---- 2. reject forbidden authority fields ----
        # A mapping is caller-supplied, so it may never carry a derived identity
        # (candidate_reference) or a forbidden authority field. A KnowledgeCandidate
        # is already a governance value whose own forbidden fields are refused at
        # construction, so only its authority vocabulary is re-checked here.
        forbidden_here = (
            FORBIDDEN_CANDIDATE_FIELDS if is_candidate else FORBIDDEN_INPUT_FIELDS
        )

        for key in raw:

            if key in forbidden_here:

                return self._deny(
                    "forbidden_authority_field",
                    "a candidate input may not carry %r — admission is not "
                    "truth, approval or licensing" % (key,),
                )

        if not is_candidate:

            for key in raw:

                if key not in ALLOWED_CANDIDATE_INPUT_FIELDS:

                    return self._deny(
                        "unknown_input_field",
                        "unknown candidate input field: %r" % (key,),
                    )

        # ---- 3. validate claim reference ----
        if not _present(source_claim_reference):

            return self._deny(
                "missing_claim_reference",
                "admission requires a source claim reference",
            )

        if not is_claim_reference(source_claim_reference):

            return self._deny(
                "invalid_claim_reference",
                "claim reference is not claim-shaped: %r"
                % (source_claim_reference,),
            )

        if known_claim_references is not None:

            if str(source_claim_reference) not in {
                str(item) for item in known_claim_references
            }:

                return self._deny(
                    "unresolved_reference",
                    "claim reference does not resolve: %r"
                    % (source_claim_reference,),
                )

        # ---- 4. validate licence reference (canonical boundary) ----
        licence_check = validate_licence_reference(
            licence_reference,
            known_licence_references=known_licence_references,
        )

        if not licence_check.valid:

            return self._deny(licence_check.rule_code, licence_check.reason)

        licence_reference = licence_check.licence_reference

        # ---- 5. validate lineage completeness ----
        try:

            parents = _clean_lineage(lineage_reference)

        except _AdmissionInputError as error:

            return self._deny("invalid_lineage", str(error))

        for parent in parents:

            if parent == str(source_claim_reference):

                return self._deny(
                    "claim_lineage_incomplete",
                    "a claim may not be its own parent: %r" % (parent,),
                )

            if not is_claim_reference(parent):

                return self._deny(
                    "claim_lineage_incomplete",
                    "parent %r is not a claim reference" % (parent,),
                )

            if known_claim_references is not None:

                if parent not in {
                    str(item) for item in known_claim_references
                }:

                    return self._deny(
                        "claim_lineage_incomplete",
                        "parent %r does not resolve" % (parent,),
                    )

        if not _present(scope):

            return self._deny(
                "missing_scope", "admission requires a candidate scope"
            )

        if scope not in SCOPES:

            return self._deny(
                "unknown_scope", "unknown candidate scope: %r" % (scope,)
            )

        # ---- 6. validate admission eligibility ----
        # The settled eligibility rule is TransitionValidator.can_be_candidate().
        # It needs a resolved claim. Without one the rule is NOT settled, so an
        # explicit NOT_IMPLEMENTED boundary result is returned (never a guess).
        if claim is None:

            return self._not_implemented(
                "admission eligibility without a resolved claim"
            )

        claim_id = str(getattr(claim, "claim_id", "") or "")

        if claim_id != str(source_claim_reference):

            return self._deny(
                "claim_reference_mismatch",
                "the supplied claim %r does not match the candidate claim "
                "reference %r" % (claim_id, source_claim_reference),
            )

        claim_scope = str(getattr(claim, "original_scope", "") or "")

        if claim_scope != str(scope):

            return self._deny(
                "scope_escalation",
                "candidate scope %r must equal the claim scope %r — admission "
                "never widens scope" % (scope, claim_scope),
            )

        claim_licence = str(getattr(claim, "licence_reference", "") or "")

        if claim_licence != str(licence_reference):

            return self._deny(
                "licence_reference_mismatch",
                "the candidate licence reference %r does not match the claim "
                "licence reference %r" % (licence_reference, claim_licence),
            )

        # The validator decides eligibility — the service never decides it.
        check = transition_validator.can_be_candidate(
            claim,
            known_claim_ids=known_claim_references,
        )

        if not check.allowed:

            return self._deny(check.rule_code, check.reason)

        # ---- 7. return immutable result ----
        if is_candidate:

            candidate_reference = candidate_input.candidate_reference

        else:

            candidate_reference = build_knowledge_candidate(
                source_claim_reference=source_claim_reference,
                licence_reference=licence_reference,
                scope=scope,
                lineage_reference=parents,
            ).candidate_reference

        return build_knowledge_admission_result(
            admitted=True,
            candidate_reference=candidate_reference,
            reason=(
                "candidate admitted: %s (eligibility confirmed by "
                "TransitionValidator)" % (source_claim_reference,)
            ),
        )

    # ==================================================
    # denials — every denial is an immutable result, never an exception
    # ==================================================

    @staticmethod
    def _deny(rule_code, detail) -> KnowledgeAdmissionResult:

        return build_knowledge_admission_result(
            admitted=False,
            candidate_reference=None,
            reason="%s: %s" % (rule_code, detail),
        )

    @staticmethod
    def _not_implemented(feature) -> KnowledgeAdmissionResult:

        return not_implemented_admission_result(feature)

    def __repr__(self):

        return (
            "KnowledgeAdmissionService(stateless=True, creates_claims=False, "
            "creates_licences=False, creates_events=False, "
            "bypasses_validator=False)"
        )


knowledge_admission_service = KnowledgeAdmissionService()
