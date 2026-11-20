"""Conversation claim-type hint interpreter (V1).

The conversation-side INTERPRETATION layer. It CLASSIFIES the claim type of a
statement and emits an ADVISORY `claim_type_hint`. It derives nothing else.

It
    declares its OWN closed claim-type vocabulary (a subset of the governance
    CLAIM_TYPES, declared LOCALLY and never imported)
    classifies the STATEMENT with a DECLARED, CLOSED, boolean rule set
    emits a CLEAN, immutable artefact: `claim_type_hint` + `provenance`
    returns `None` when no rule matches (absence is first-class)

It MUST NOT
    import governance / conversation / vision / runtime (stdlib only)
    read candidate_kind / knowledge_class / domain / confidence / any score
    infer truth, calculate confidence, or default a claim type
    create an identity, persist, or decide admission

Dependency direction

    this module  ->  stdlib only
    this module  ->  core.*  FORBIDDEN

The consumer (`ClaimRequestMaterial.claim_type_hint`) COPIES this value; the
runtime never derives it, and governance validates the vocabulary.
"""

from __future__ import annotations


import re


from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


CONTRACT = "ConversationClaimTypeHintV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the fixed provenance label
# ----------------------------------------------------------

# A SOURCE label, never an identity.
PROVENANCE_CONVERSATION = "conversation"


# ----------------------------------------------------------
# the LOCAL claim-type vocabulary (a mirror, never an import)
# ----------------------------------------------------------

# Declared LOCALLY so this module imports nothing from `core.*`. It is aligned
# to the governance vocabulary and must remain a SUBSET of it. The alignment is
# a CONTRACT, not a dependency.
CLAIM_TYPE_HINT_VOCABULARY = (
    "existence",
    "semantic_space",
    "functional_role",
    "functional_relationship",
    "spatial_relationship",
    "alternative_interpretation",
)


# ----------------------------------------------------------
# the DECLARED, CLOSED rule set
# ----------------------------------------------------------
#
# A marker is matched as a CONTIGUOUS token phrase. Matching is boolean: there
# is no score, no threshold, no arithmetic, and no confidence.
#
# Persian markers are written as escapes so the source stays pure ASCII.

ALTERNATIVE_INTERPRETATION_MARKERS = (
    "instead",
    "rather than",
    "but rather",
    "as opposed to",
    "i meant",
    "correction",
    "on the contrary",
    "\u0628\u0644\u06a9\u0647",              # بلكه   (rather)
    "\u062f\u0631 \u0648\u0627\u0642\u0639",  # در واقع (in fact)
    "\u0645\u0646\u0638\u0648\u0631\u0645",    # منظورم (I mean)
    "\u0627\u0634\u062a\u0628\u0627\u0647",    # اشتباه (mistake)
)


SPATIAL_RELATIONSHIP_MARKERS = (
    "next to",
    "adjacent to",
    "adjacent",
    "beside",
    "near",
    "far from",
    "opposite",
    "above",
    "below",
    "between",
    "in front of",
    "behind",
    "north of",
    "south of",
    "east of",
    "west of",
    "overlaps",
    "touches",
    "\u06a9\u0646\u0627\u0631",              # كنار   (beside)
    "\u0645\u062c\u0627\u0648\u0631",        # مجاور  (adjacent)
    "\u0646\u0632\u062f\u06cc\u06a9",        # نزدیك  (near)
    "\u062f\u0648\u0631 \u0627\u0632",        # دور از (far from)
    "\u0631\u0648\u0628\u0631\u0648",        # روبرو  (opposite)
    "\u0628\u0627\u0644\u0627",              # بالا   (above)
    "\u067e\u0627\u06cc\u06cc\u0646",        # پایین  (below)
    "\u0628\u06cc\u0646",                    # بین    (between)
    "\u062c\u0644\u0648\u06cc",              # جلوی   (in front of)
    "\u067e\u0634\u062a",                    # پشت    (behind)
)


FUNCTIONAL_RELATIONSHIP_MARKERS = (
    "connected to",
    "connects to",
    "opens to",
    "leads to",
    "accessed from",
    "access from",
    "linked to",
    "attached to",
    "\u0645\u062a\u0635\u0644",              # متصل   (connected)
    "\u0645\u0646\u062a\u0647\u06cc",        # منتهی  (leading to)
    "\u062f\u0633\u062a\u0631\u0633\u06cc",  # دسترسی (access)
)


FUNCTIONAL_ROLE_MARKERS = (
    "used for",
    "used as",
    "serves as",
    "functions as",
    "is for",
    "purpose of",
    "role of",
    "serves",
    "\u06a9\u0627\u0631\u0628\u0631\u06cc",          # كاربری (use)
    "\u0628\u0647 \u0639\u0646\u0648\u0627\u0646",    # به عنوان (as)
    "\u0646\u0642\u0634",                            # نقش    (role)
)


EXISTENCE_MARKERS = (
    "there is",
    "there are",
    "there exists",
    "exists",
    "is present",
    "contains",
    "has a",
    "has an",
    "\u0648\u062c\u0648\u062f \u062f\u0627\u0631\u062f",  # وجود دارد (exists)
    "\u0645\u0648\u062c\u0648\u062f \u0627\u0633\u062a",  # موجود است (is present)
)


SEMANTIC_SPACE_MARKERS = (
    "is a",
    "is an",
    "means",
    "refers to",
    "is called",
    "is defined as",
    "is known as",
    "definition of",
    "\u06cc\u0639\u0646\u06cc",              # یعنی   (means)
    "\u0628\u0647 \u0645\u0639\u0646\u06cc",  # به معنی (means)
    "\u062a\u0639\u0631\u06cc\u0641",        # تعریف  (definition)
)


# The DECLARED ORDER. The first rule whose marker matches WINS. The order is a
# priority, not a score: `existence` precedes `semantic_space` so that
# "there is a ..." is an existence claim rather than a definition.
RULES = (
    ("alternative_interpretation", ALTERNATIVE_INTERPRETATION_MARKERS),
    ("spatial_relationship", SPATIAL_RELATIONSHIP_MARKERS),
    ("functional_relationship", FUNCTIONAL_RELATIONSHIP_MARKERS),
    ("functional_role", FUNCTIONAL_ROLE_MARKERS),
    ("existence", EXISTENCE_MARKERS),
    ("semantic_space", SEMANTIC_SPACE_MARKERS),
)


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_NOT_A_STATEMENT = "hint_not_a_statement"

REASON_UNKNOWN_CLAIM_TYPE = "hint_unknown_claim_type"


REASONS = (
    REASON_NOT_A_STATEMENT,
    REASON_UNKNOWN_CLAIM_TYPE,
)


class ConversationClaimTypeHintError(ValueError):
    """Raised when a statement or a claim type is malformed."""


# ----------------------------------------------------------
# the clean artefact
# ----------------------------------------------------------

@dataclass(frozen=True)
class ConversationClaimTypeHint:

    """An immutable, advisory claim-type hint.

    Exactly two data fields: `claim_type_hint` and `provenance`.
    """

    claim_type_hint: Optional[str] = None

    provenance: str = PROVENANCE_CONVERSATION

    CONTRACT = CONTRACT

    VERSION = VERSION

    # A hint advises. It creates nothing and decides nothing.
    IS_ADVISORY = True

    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        if self.claim_type_hint is not None:

            token = str(self.claim_type_hint).strip()

            if token not in CLAIM_TYPE_HINT_VOCABULARY:

                raise ConversationClaimTypeHintError(
                    "%s: %r" % (REASON_UNKNOWN_CLAIM_TYPE, token)
                )

            object.__setattr__(self, "claim_type_hint", token)

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "claim_type_hint": self.claim_type_hint,
            "provenance": self.provenance,
            "is_advisory": True,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "ConversationClaimTypeHint(claim_type_hint=%r)" % (
            self.claim_type_hint,
        )


# ----------------------------------------------------------
# normalisation and matching
# ----------------------------------------------------------

# Keep word characters, whitespace and the zero-width non-joiner (which glues
# Persian compounds); everything else becomes a separator.
_NON_TEXT = re.compile(r"[^\w\s\u200c]+", re.UNICODE)


def _tokens(text) -> Tuple[str, ...]:

    normalized = _NON_TEXT.sub(" ", str(text or "").lower())

    return tuple(normalized.split())


def _contains_phrase(tokens, phrase) -> bool:

    phrase_tokens = tuple(str(phrase).lower().split())

    if not phrase_tokens:

        return False

    span = len(phrase_tokens)

    for start in range(len(tokens) - span + 1):

        if tokens[start:start + span] == phrase_tokens:

            return True

    return False


def _classify(tokens) -> Optional[str]:

    """Return the first matching claim type, or None. Boolean; never a score."""

    for claim_type, markers in RULES:

        for marker in markers:

            if _contains_phrase(tokens, marker):

                return claim_type

    return None


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def to_claim_type_hint(statement, *, meaning=None) -> ConversationClaimTypeHint:

    """Classify a statement into an ADVISORY claim-type hint.

    `statement` MUST be a string. A blank statement yields `None` (absence is
    first-class — there is NO default).

    `meaning` is accepted for call-site compatibility and is DELIBERATELY NOT
    READ: the classification comes from the statement alone, so the layer can
    never depend on a conversation taxonomy or on any structural field.
    """

    if not isinstance(statement, str):

        raise ConversationClaimTypeHintError(
            "%s: got %r" % (REASON_NOT_A_STATEMENT, type(statement).__name__)
        )

    return ConversationClaimTypeHint(
        claim_type_hint=_classify(_tokens(statement)),
    )


class ConversationClaimTypeHintInterpreter:

    """The conversation-side claim-type interpreter. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    IS_ADVISORY = True

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    CARRIES_CONFIDENCE = False

    def interpret(self, statement, *, meaning=None) -> ConversationClaimTypeHint:

        return to_claim_type_hint(statement, meaning=meaning)

    def __repr__(self):

        return (
            "ConversationClaimTypeHintInterpreter("
            "advisory=True, classifies_only=True)"
        )


conversation_claim_type_hint_interpreter = ConversationClaimTypeHintInterpreter()
