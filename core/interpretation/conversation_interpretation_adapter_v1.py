"""Conversation interpretation -> carrier adapter (V1).

The INTEGRATION adapter between the conversation claim-type interpretation layer
and the runtime `ClaimRequestMaterialAdapter`.

It
    calls `conversation_claim_type_hint_v1.to_claim_type_hint`
    COPIES the resulting `claim_type_hint` into a clean carrier
    forwards `basis` / `limitations` verbatim (interpreter-declared)
    leaves an absent hint ABSENT (`None`)

It MUST NOT
    derive a hint from candidate_kind / knowledge_class / domain
    derive a hint from a confidence / score / probability / similarity
    map one vocabulary onto another
    substitute a fallback default (there is NO `existence` default)
    import the governance vocabulary
    read the `meaning` argument for the claim type

Dependency direction

    this module  ->  core.interpretation.{conversation_claim_type_hint_v1,
                                           conversation_interaction_carrier_v1}
    this module  ->  core.conversation / core.vision / core.governance / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Iterable, Optional


from core.interpretation.conversation_claim_type_hint_v1 import (
    to_claim_type_hint,
)
from core.interpretation.conversation_interaction_carrier_v1 import (
    ConversationInteractionCarrier,
)


CONTRACT = "ConversationInterpretationAdapterV1"

VERSION = "1.0"


def to_interaction_carrier(
    statement,
    *,
    basis: Iterable[str] = (),
    limitations: Iterable[str] = (),
    meaning=None,
) -> ConversationInteractionCarrier:

    """Build a clean carrier from a statement via the interpretation layer.

    The hint is COPIED from the interpretation layer — never derived here, never
    defaulted. An unclassifiable statement yields `claim_type_hint = None`.

    `meaning` is accepted for call-site compatibility and is passed through to
    the interpretation layer, which does NOT read it for the claim type.
    """

    hint = to_claim_type_hint(statement, meaning=meaning)

    return ConversationInteractionCarrier(
        statement=statement,
        claim_type_hint=hint.claim_type_hint,
        basis=basis,
        limitations=limitations,
    )


class ConversationInterpretationAdapter:

    """The conversation interpretation -> carrier adapter. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    IS_ADVISORY = True

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    CARRIES_CONFIDENCE = False

    def to_carrier(
        self,
        statement,
        *,
        basis: Iterable[str] = (),
        limitations: Iterable[str] = (),
        meaning=None,
    ) -> ConversationInteractionCarrier:

        return to_interaction_carrier(
            statement,
            basis=basis,
            limitations=limitations,
            meaning=meaning,
        )

    def __repr__(self):

        return (
            "ConversationInterpretationAdapter("
            "copies_only=True, no_default=True)"
        )


conversation_interpretation_adapter = ConversationInterpretationAdapter()
