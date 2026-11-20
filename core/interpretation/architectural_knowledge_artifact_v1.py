"""Architectural Knowledge Artifact (V1) — the NEUTRAL, source-agnostic reading.

The neutral projection of an architectural INTERPRETATION. It is the single
output of the interpreter-side AKA adapter and the source-agnostic successor to
the vision-only rich candidate. It carries ADVISORY semantics only.

It carries EXACTLY five fields
    content
    knowledge_hint
    basis
    limitations
    source_kind

It MUST NOT carry
    confidence / score / probability / certainty
    truth / truth_status / is_true / verified_truth
    status / knowledge_status / fact_status
    approval / admission
    licence / candidate_reference / claim_id / any id
    scope
    session / nonce / token
    proposal_fields
    evidence_reference
    normative flags

Producer
    `to_architectural_knowledge_artifact(source)` — the ONLY public producer.
    One contract, TWO branches (vision, conversation), ONE construction authority.

Branches (read STRUCTURALLY, duck-typed; no source import)
    vision        -> ArchitecturalUnderstandingV2
    conversation  -> ConversationInteractionCarrier

Dependency direction

    this module  ->  stdlib only
    this module  ->  core.conversation / core.vision / core.governance / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, Mapping, Optional, Tuple


CONTRACT = "ArchitecturalKnowledgeArtifactV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the fixed source labels
# ----------------------------------------------------------

# A SOURCE LABEL, never an identity.
SOURCE_KIND_VISION = "vision"

SOURCE_KIND_CONVERSATION = "conversation"


SOURCE_KINDS = (SOURCE_KIND_VISION, SOURCE_KIND_CONVERSATION)


# ----------------------------------------------------------
# the EXACT contract. Nothing else may exist on the artifact.
# ----------------------------------------------------------

ARTIFACT_FIELDS = (
    "content",
    "knowledge_hint",
    "basis",
    "limitations",
    "source_kind",
)


# ----------------------------------------------------------
# the LOCAL, CLOSED advisory vocabulary (a mirror, never an import)
# ----------------------------------------------------------

# Declared LOCALLY so this module imports nothing from `core.*`. Aligned to the
# governance CLAIM_TYPES family and a SUBSET of it. The alignment is a CONTRACT,
# never a dependency.
KNOWLEDGE_HINT_VOCABULARY = (
    "existence",
    "semantic_space",
    "functional_role",
    "functional_relationship",
    "spatial_relationship",
    "alternative_interpretation",
)


# ----------------------------------------------------------
# source recognition (structural signatures)
# ----------------------------------------------------------

VISION_SIGNATURE_FIELDS = (
    "claim_trace",
    "interpretation_states",
    "semantic_space",
)


CONVERSATION_SIGNATURE_FIELDS = (
    "statement",
    "raw_statement",
    "normalized_meaning",
)


# ----------------------------------------------------------
# forbidden source keys (top-level) — an authority / truth smuggling attempt
# ----------------------------------------------------------

# A source that EXPOSES one of these is REFUSED, never silently stripped.
FORBIDDEN_SOURCE_FIELDS = (
    "confidence",
    "confidence_kind",
    "score",
    "probability",
    "certainty",
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "status",
    "knowledge_status",
    "fact_status",
    "approval",
    "approved",
    "is_approved",
    "admission",
    "admitted",
    "licence",
    "license",
    "licence_id",
    "license_id",
    "licence_reference",
    "candidate_id",
    "candidate_reference",
    "candidate_type",
    "source_claim_ids",
    "claim_id",
    "scope",
    "scope_authority",
    "session",
    "session_reference",
    "nonce",
    "interaction_nonce",
    "token",
    "token_reference",
    "proposal",
    "proposal_fields",
    "interpretation_proposal",
    "evidence_reference",
    "normative",
    "is_normative",
    "normative_flag",
    "prescriptive",
)


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_NOT_A_SOURCE = "aka_not_a_source"

REASON_UNKNOWN_SOURCE = "aka_unknown_source"

REASON_MISSING_CONTENT = "aka_missing_content"

REASON_FORBIDDEN_FIELD = "aka_forbidden_field"

REASON_UNKNOWN_SOURCE_KIND = "aka_unknown_source_kind"

REASON_UNKNOWN_KNOWLEDGE_HINT = "aka_unknown_knowledge_hint"

REASON_SECOND_PRODUCER = "aka_second_producer"


REASONS = (
    REASON_NOT_A_SOURCE,
    REASON_UNKNOWN_SOURCE,
    REASON_MISSING_CONTENT,
    REASON_FORBIDDEN_FIELD,
    REASON_UNKNOWN_SOURCE_KIND,
    REASON_UNKNOWN_KNOWLEDGE_HINT,
    REASON_SECOND_PRODUCER,
)


class ArchitecturalKnowledgeArtifactError(ValueError):
    """Raised when a source cannot be projected into an artifact."""


# The module-private construction authority. Only THIS module may build an
# ArchitecturalKnowledgeArtifact, so no second producer can appear.
_CONSTRUCTION_AUTHORITY = object()


class ArchitecturalKnowledgeArtifact:

    """An immutable, neutral architectural reading.

    Exactly five fields: content, knowledge_hint, basis, limitations,
    source_kind.
    """

    __slots__ = (
        "_content",
        "_knowledge_hint",
        "_basis",
        "_limitations",
        "_source_kind",
        "_sealed",
    )

    CONTRACT = CONTRACT

    VERSION = VERSION

    FIELDS = ARTIFACT_FIELDS

    # A reading describes. It creates nothing and decides nothing.
    IS_ADVISORY = True

    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __init__(
        self,
        *,
        content,
        knowledge_hint=None,
        basis=(),
        limitations=(),
        source_kind,
        _authority=None,
    ):

        if _authority is not _CONSTRUCTION_AUTHORITY:

            raise ArchitecturalKnowledgeArtifactError(
                "%s: ArchitecturalKnowledgeArtifact is created only by the "
                "adapter; a second producer is forbidden."
                % (REASON_SECOND_PRODUCER,)
            )

        text = _text(content)

        if not text:

            raise ArchitecturalKnowledgeArtifactError(
                "%s: content is required" % (REASON_MISSING_CONTENT,)
            )

        kind = _text(source_kind)

        if kind not in SOURCE_KINDS:

            raise ArchitecturalKnowledgeArtifactError(
                "%s: %r" % (REASON_UNKNOWN_SOURCE_KIND, kind)
            )

        hint: Optional[str] = None

        if knowledge_hint is not None:

            token = _text(knowledge_hint)

            if token not in KNOWLEDGE_HINT_VOCABULARY:

                raise ArchitecturalKnowledgeArtifactError(
                    "%s: %r" % (REASON_UNKNOWN_KNOWLEDGE_HINT, token)
                )

            hint = token

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_content", text)

        object.__setattr__(self, "_knowledge_hint", hint)

        object.__setattr__(self, "_basis", _items(basis))

        object.__setattr__(self, "_limitations", _items(limitations))

        object.__setattr__(self, "_source_kind", kind)

        object.__setattr__(self, "_sealed", True)

    # --------------------------------------------------
    # immutability
    # --------------------------------------------------

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise ArchitecturalKnowledgeArtifactError(
                "ArchitecturalKnowledgeArtifact is immutable: cannot set %r"
                % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise ArchitecturalKnowledgeArtifactError(
            "ArchitecturalKnowledgeArtifact is immutable: cannot delete %r"
            % (name,)
        )

    # --------------------------------------------------
    # read-only accessors
    # --------------------------------------------------

    @property
    def content(self):

        return self._content

    @property
    def knowledge_hint(self):

        return self._knowledge_hint

    @property
    def basis(self):

        return self._basis

    @property
    def limitations(self):

        return self._limitations

    @property
    def source_kind(self):

        return self._source_kind

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "content": self._content,
            "knowledge_hint": self._knowledge_hint,
            "basis": list(self._basis),
            "limitations": list(self._limitations),
            "source_kind": self._source_kind,
            "is_advisory": True,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "ArchitecturalKnowledgeArtifact(source_kind=%r, hint=%r)" % (
            self._source_kind,
            self._knowledge_hint,
        )


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _text(value) -> str:

    return str(value or "").strip()


def _get(source, key, default=None):

    if isinstance(source, Mapping):

        return source.get(key, default)

    return getattr(source, key, default)


def _has(source, key) -> bool:

    if isinstance(source, Mapping):

        return key in source

    return hasattr(source, key)


def _keys(source) -> Tuple[str, ...]:

    if isinstance(source, Mapping):

        return tuple(str(key) for key in source)

    return tuple(name for name in dir(source) if not name.startswith("_"))


def _items(value) -> Tuple[str, ...]:

    if isinstance(value, str):

        return (_text(value),) if _text(value) else ()

    if not isinstance(value, (list, tuple)):

        return ()

    result = []

    for item in value:

        text = _text(item)

        if text and text not in result:

            result.append(text)

    return tuple(result)


def _first_present(source, names) -> str:

    for name in names:

        if _has(source, name):

            text = _text(_get(source, name))

            if text:

                return text

    return ""


def _reject_forbidden_fields(source) -> None:

    for key in _keys(source):

        if key in FORBIDDEN_SOURCE_FIELDS:

            raise ArchitecturalKnowledgeArtifactError(
                "%s: %r" % (REASON_FORBIDDEN_FIELD, key)
            )


# ----------------------------------------------------------
# the two branches
# ----------------------------------------------------------

def _primary_claim(source) -> Optional[Mapping]:

    """The claim the interpreter DECLARED primary, else the first trace claim."""

    trace = _get(source, "claim_trace")

    if not isinstance(trace, (list, tuple)):

        return None

    primary_id = None

    states = _get(source, "interpretation_states")

    if isinstance(states, Mapping):

        primary = states.get("primary")

        if isinstance(primary, Mapping):

            primary_id = _text(primary.get("claim_id")) or None

    if primary_id:

        for claim in trace:

            if isinstance(claim, Mapping) and _text(claim.get("claim_id")) == primary_id:

                return claim

    for claim in trace:

        if isinstance(claim, Mapping):

            return claim

    return None


def _primary_label(source) -> str:

    """The DECLARED primary label, falling back to the semantic-space label."""

    states = _get(source, "interpretation_states")

    if isinstance(states, Mapping):

        primary = states.get("primary")

        if isinstance(primary, Mapping):

            label = _text(primary.get("label"))

            if label:

                return label

    semantic_space = _get(source, "semantic_space")

    if isinstance(semantic_space, Mapping):

        return _text(semantic_space.get("label"))

    return ""


def _vision_basis(source, claim) -> Tuple[str, ...]:

    if isinstance(claim, Mapping):

        basis = _items(claim.get("interpretation_basis"))

        if basis:

            return basis

    semantic_space = _get(source, "semantic_space")

    if isinstance(semantic_space, Mapping):

        return _items(semantic_space.get("basis"))

    return ()


def _from_vision(source) -> ArchitecturalKnowledgeArtifact:

    content = _primary_label(source)

    if not content:

        raise ArchitecturalKnowledgeArtifactError(
            "%s: the vision projection carries no primary label"
            % (REASON_MISSING_CONTENT,)
        )

    claim = _primary_claim(source)

    hint = _text(claim.get("claim_type")) if isinstance(claim, Mapping) else ""

    return ArchitecturalKnowledgeArtifact(
        content=content,
        # a DIRECT copy of the primary claim's claim_type — no derivation
        knowledge_hint=hint or None,
        basis=_vision_basis(source, claim),
        limitations=_items(_get(source, "non_claims")),
        source_kind=SOURCE_KIND_VISION,
        _authority=_CONSTRUCTION_AUTHORITY,
    )


def _from_conversation(source) -> ArchitecturalKnowledgeArtifact:

    content = _first_present(source, CONVERSATION_SIGNATURE_FIELDS)

    if not content:

        raise ArchitecturalKnowledgeArtifactError(
            "%s: the conversation carrier carries no statement"
            % (REASON_MISSING_CONTENT,)
        )

    return ArchitecturalKnowledgeArtifact(
        content=content,
        # claim_type_hint is COPIED only — never derived, never defaulted
        knowledge_hint=_text(_get(source, "claim_type_hint")) or None,
        basis=_items(_get(source, "basis")),
        limitations=_items(_get(source, "limitations")),
        source_kind=SOURCE_KIND_CONVERSATION,
        _authority=_CONSTRUCTION_AUTHORITY,
    )


# ----------------------------------------------------------
# the single producer
# ----------------------------------------------------------

def to_architectural_knowledge_artifact(source) -> ArchitecturalKnowledgeArtifact:

    """Project a source interpretation into the neutral artifact.

    The ONLY public way to create an ArchitecturalKnowledgeArtifact.
    """

    if source is None or isinstance(source, (str, bytes, int, float, bool)):

        raise ArchitecturalKnowledgeArtifactError(
            "%s: got %r" % (REASON_NOT_A_SOURCE, type(source).__name__)
        )

    _reject_forbidden_fields(source)

    if any(_has(source, name) for name in VISION_SIGNATURE_FIELDS):

        return _from_vision(source)

    if any(_has(source, name) for name in CONVERSATION_SIGNATURE_FIELDS):

        return _from_conversation(source)

    raise ArchitecturalKnowledgeArtifactError(
        "%s: neither an AUv2 projection nor a conversation carrier"
        % (REASON_UNKNOWN_SOURCE,)
    )


class ArchitecturalKnowledgeArtifactAdapter:

    """Stateless projector. The single producer of the artifact."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    CARRIES_CONFIDENCE = False

    def to_artifact(self, source) -> ArchitecturalKnowledgeArtifact:

        return to_architectural_knowledge_artifact(source)

    def __repr__(self):

        return "ArchitecturalKnowledgeArtifactAdapter(projects_only=True)"


architectural_knowledge_artifact_adapter = ArchitecturalKnowledgeArtifactAdapter()
