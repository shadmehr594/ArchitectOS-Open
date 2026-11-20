"""ClaimRequestMaterialAdapter (V1) — the SINGLE producer of ClaimRequestMaterial.

The adapter TRANSLATES a source interpretation artefact into the neutral
`ClaimRequestMaterial`. It derives nothing, decides nothing and reads no score.

It
    maps only EXISTING source fields
    drops every non-allowed field
    refuses a source that carries an authority / truth key
    is the ONLY creator of `ClaimRequestMaterial`

It MUST NOT
    derive a `claim_type_hint` (a cross-vocabulary mapping is forbidden)
    map `candidate_kind` into a claim type
    infer truth, calculate confidence
    create an id
    import / call governance, conversation or vision

Dependency direction

    this module  ->  stdlib only
    this module  ->  core.conversation / core.vision / core.governance  FORBIDDEN

The source is read STRUCTURALLY (duck-typed), so no client import is needed.
"""

from __future__ import annotations


from typing import Any, Dict, Mapping, Optional, Tuple


CONTRACT = "RuntimeClaimRequestMaterialV1"

VERSION = "1.0"


# ----------------------------------------------------------
# provenance labels
# ----------------------------------------------------------

PROVENANCE_INTERACTIVE = "interactive"

PROVENANCE_VISION = "vision"


# ----------------------------------------------------------
# source recognition
# ----------------------------------------------------------

CONVERSATION_STATEMENT_FIELDS = (
    "raw_statement",
    "statement",
    "normalized_meaning",
)


VISION_TRACE_FIELD = "claim_trace"


# ----------------------------------------------------------
# forbidden source keys (top-level)
# ----------------------------------------------------------

FORBIDDEN_SOURCE_FIELDS = (
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "approval",
    "certainty",
    "probability",
    "confidence",
    "confidence_kind",
    "claim_id",
    "licence_id",
    "candidate_reference",
    "scope_authority",
    "knowledge_status",
    "fact_status",
    "proposal",
    "proposal_fields",
    "interpretation_proposal",
)


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_NOT_A_SOURCE = "material_not_a_source"

REASON_UNKNOWN_SOURCE = "material_unknown_source"

REASON_MISSING_STATEMENT = "material_missing_statement"

REASON_FORBIDDEN_FIELD = "material_forbidden_field"


REASONS = (
    REASON_NOT_A_SOURCE,
    REASON_UNKNOWN_SOURCE,
    REASON_MISSING_STATEMENT,
    REASON_FORBIDDEN_FIELD,
)


# The module-private construction authority. Only THIS module may build a
# ClaimRequestMaterial, so no second producer can appear.
_CONSTRUCTION_AUTHORITY = object()


class ClaimRequestMaterialError(ValueError):
    """Raised when a source cannot be translated into a material."""


class ClaimRequestMaterial:

    """An immutable, neutral semantic artifact.

    Exactly five fields: statement, claim_type_hint, basis, limitations,
    provenance.
    """

    __slots__ = (
        "_statement",
        "_claim_type_hint",
        "_basis",
        "_limitations",
        "_provenance",
        "_sealed",
    )

    CONTRACT = CONTRACT

    VERSION = VERSION

    # A material carries advisory semantics. It creates nothing and decides
    # nothing.
    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __init__(
        self,
        *,
        statement,
        claim_type_hint=None,
        basis=(),
        limitations=(),
        provenance=PROVENANCE_INTERACTIVE,
        _authority=None,
    ):

        if _authority is not _CONSTRUCTION_AUTHORITY:

            raise ClaimRequestMaterialError(
                "ClaimRequestMaterial is created only by the adapter; a second "
                "producer is forbidden."
            )

        text = str(statement or "").strip()

        if not text:

            raise ClaimRequestMaterialError(
                "%s: statement is required" % (REASON_MISSING_STATEMENT,)
            )

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_statement", text)

        object.__setattr__(
            self,
            "_claim_type_hint",
            str(claim_type_hint).strip() if claim_type_hint else None,
        )

        object.__setattr__(self, "_basis", tuple(basis or ()))

        object.__setattr__(self, "_limitations", tuple(limitations or ()))

        object.__setattr__(self, "_provenance", str(provenance or "unknown"))

        object.__setattr__(self, "_sealed", True)

    # --------------------------------------------------
    # immutability
    # --------------------------------------------------

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise ClaimRequestMaterialError(
                "ClaimRequestMaterial is immutable: cannot set %r" % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise ClaimRequestMaterialError(
            "ClaimRequestMaterial is immutable: cannot delete %r" % (name,)
        )

    # --------------------------------------------------
    # read-only accessors
    # --------------------------------------------------

    @property
    def statement(self):

        return self._statement

    @property
    def claim_type_hint(self):

        return self._claim_type_hint

    @property
    def basis(self):

        return self._basis

    @property
    def limitations(self):

        return self._limitations

    @property
    def provenance(self):

        return self._provenance

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "statement": self._statement,
            "claim_type_hint": self._claim_type_hint,
            "basis": list(self._basis),
            "limitations": list(self._limitations),
            "provenance": self._provenance,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "ClaimRequestMaterial(provenance=%r, hint=%r)" % (
            self._provenance,
            self._claim_type_hint,
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

    return tuple(
        name for name in dir(source) if not name.startswith("_")
    )


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

            raise ClaimRequestMaterialError(
                "%s: %r" % (REASON_FORBIDDEN_FIELD, key)
            )


# ----------------------------------------------------------
# the two branches
# ----------------------------------------------------------

def _primary_trace(projection) -> Optional[Mapping]:

    trace = _get(projection, VISION_TRACE_FIELD)

    if not isinstance(trace, (list, tuple)) or not trace:

        return None

    primary_id = None

    states = _get(projection, "interpretation_states")

    if isinstance(states, Mapping):

        primary = states.get("primary")

        if isinstance(primary, Mapping):

            primary_id = _text(primary.get("claim_id")) or None

    if primary_id:

        for claim in trace:

            if isinstance(claim, Mapping) and _text(claim.get("claim_id")) == primary_id:

                return claim

    first = trace[0]

    return first if isinstance(first, Mapping) else None


def _from_conversation(source) -> ClaimRequestMaterial:

    statement = _first_present(source, CONVERSATION_STATEMENT_FIELDS)

    if not statement:

        raise ClaimRequestMaterialError(
            "%s: no statement field is present" % (REASON_MISSING_STATEMENT,)
        )

    # claim_type_hint is COPIED only — never derived from another vocabulary
    hint = _text(_get(source, "claim_type_hint")) or None

    return ClaimRequestMaterial(
        statement=statement,
        claim_type_hint=hint,
        basis=_items(_get(source, "basis")),
        limitations=_items(_get(source, "limitations")),
        provenance=PROVENANCE_INTERACTIVE,
        _authority=_CONSTRUCTION_AUTHORITY,
    )


def _from_vision(source) -> ClaimRequestMaterial:

    trace = _primary_trace(source)

    if trace is None:

        raise ClaimRequestMaterialError(
            "%s: claim_trace carries no usable claim" % (REASON_MISSING_STATEMENT,)
        )

    statement = _text(trace.get("label"))

    if not statement:

        semantic_space = _get(source, "semantic_space")

        if isinstance(semantic_space, Mapping):

            statement = _text(semantic_space.get("label"))

    if not statement:

        raise ClaimRequestMaterialError(
            "%s: the trace carries no label" % (REASON_MISSING_STATEMENT,)
        )

    return ClaimRequestMaterial(
        statement=statement,
        # a DIRECT copy of the trace's claim_type — no derivation
        claim_type_hint=_text(trace.get("claim_type")) or None,
        basis=_items(trace.get("interpretation_basis")),
        limitations=_items(_get(source, "non_claims")),
        provenance=PROVENANCE_VISION,
        _authority=_CONSTRUCTION_AUTHORITY,
    )


# ----------------------------------------------------------
# the single producer
# ----------------------------------------------------------

def to_claim_request_material(source) -> ClaimRequestMaterial:

    """Translate a source artefact into a ClaimRequestMaterial.

    The ONLY public way to create a material.
    """

    if source is None or isinstance(source, (str, bytes, int, float, bool)):

        raise ClaimRequestMaterialError(
            "%s: got %r" % (REASON_NOT_A_SOURCE, type(source).__name__)
        )

    _reject_forbidden_fields(source)

    if _has(source, VISION_TRACE_FIELD):

        return _from_vision(source)

    if any(_has(source, name) for name in CONVERSATION_STATEMENT_FIELDS):

        return _from_conversation(source)

    raise ClaimRequestMaterialError(
        "%s: neither a conversation artefact nor an AUv2 projection"
        % (REASON_UNKNOWN_SOURCE,)
    )


class ClaimRequestMaterialAdapter:

    """Stateless translator. The single producer of ClaimRequestMaterial."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    def to_material(self, source) -> ClaimRequestMaterial:

        return to_claim_request_material(source)

    def __repr__(self):

        return "ClaimRequestMaterialAdapter(translates_only=True)"


claim_request_material_adapter = ClaimRequestMaterialAdapter()
