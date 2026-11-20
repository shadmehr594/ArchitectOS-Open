"""Asset-specific forward resolution (Phase 3D-W).

Connects an explicit family rule to a non-executable forward contract:

    rule (registry or caller)  ->  rule_to_forward_contract(...)
    geometry evidence          ->  evaluate_geometry_agreement(...)
    both                       ->  resolve_asset_forward(...)

CRITICAL SAFETY RULE: geometry never originates semantic forward.

The only legal source of a semantic forward axis is an explicit rule. Geometry
may corroborate or reject the rule's declared ``expected_geometry_direction``,
and nothing more. There is deliberately no function here - and none in the
pipeline - that accepts geometry alone and returns a forward axis.

This module is pure: no registry lookup, no category lookup, no vertex
parameters, no geometry measurement, no filesystem access.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from core.asset.forward_geometry_gate import evaluate_geometry_agreement
from core.asset.mesh_transform_spec import (
    FORWARD_AXES,
    FORWARD_CONTRACT_KEYS,
    FORWARD_EVIDENCE_KEYS,
    FORWARD_SOURCES,
    FORWARD_STATUSES,
    GEOMETRY_EVIDENCE_STATES,
    GEOMETRY_GATE_STATES,
    SOURCE_MESH_FRAME,
    resolve_forward_contract,
)


# Rule authority vocabulary. Kept local (rather than imported from the registry)
# so this resolver has no dependency on the registry module at all; a test
# asserts the two vocabularies stay in agreement.
RULE_STATUSES = ("supported", "unresolved", "unsupported")

RULE_KEYS = (
    "status",
    "semantic_forward_axis",
    "expected_geometry_direction",
    "geometry_gate_required",
    "scope",
    "evidence",
)

OUTCOME_NO_FAMILY_SUPPLIED = "no_family_supplied"
OUTCOME_FAMILY_UNKNOWN = "family_unknown"
OUTCOME_RULE_UNRESOLVED = "rule_unresolved"
OUTCOME_RULE_UNSUPPORTED = "rule_unsupported"
OUTCOME_GATE_NOT_EVALUATED_NO_GEOMETRY = "gate_not_evaluated_no_geometry"
OUTCOME_GEOMETRY_UNOBSERVABLE = "geometry_unobservable"
OUTCOME_GEOMETRY_AMBIGUOUS = "geometry_ambiguous"
OUTCOME_GEOMETRY_DISAGREED = "geometry_disagreed"
OUTCOME_GEOMETRY_AGREED = "geometry_agreed"
OUTCOME_SUPPORTED_NO_GATE_REQUIRED = "supported_rule_no_gate_required"
# Defensive fallback only; not reachable for well-formed observable evidence.
OUTCOME_GATE_NOT_EVALUATED = "gate_not_evaluated"

UNRESOLVED_CONTRACT = {
    "status": "unresolved",
    "axis": None,
    "axis_frame": SOURCE_MESH_FRAME,
    "source": "none",
    "family": None,
    "evidence": {
        "rule_id": None,
        "geometry_gate": "not_evaluated",
        "agreement": None,
        "notes": [],
    },
}


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _validate_contract(contract):
    """Compact contract validator. Reuses the public 3D-R vocabularies."""

    if not isinstance(contract, Mapping):
        raise ValueError("forward contract must be a mapping")

    unknown = set(contract) - set(FORWARD_CONTRACT_KEYS)
    if unknown:
        raise ValueError(
            "unknown forward contract field(s): " + ", ".join(sorted(unknown))
        )

    if contract.get("axis_frame") != SOURCE_MESH_FRAME:
        raise ValueError(
            f"forward contract axis_frame must be {SOURCE_MESH_FRAME!r}"
        )

    status = contract.get("status")
    if status not in FORWARD_STATUSES:
        raise ValueError(
            "forward contract status must be one of: " + ", ".join(FORWARD_STATUSES)
        )

    axis = contract.get("axis")
    if axis is not None and axis not in FORWARD_AXES:
        raise ValueError(
            "forward contract axis must be one of: "
            + ", ".join(FORWARD_AXES)
            + " or None"
        )

    source = contract.get("source")
    if source not in FORWARD_SOURCES:
        raise ValueError(
            "forward contract source must be one of: " + ", ".join(FORWARD_SOURCES)
        )

    family = contract.get("family")
    if family is not None and (not isinstance(family, str) or not family.strip()):
        raise ValueError("forward contract family must be a non-empty string or None")

    evidence = contract.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("forward contract evidence must be a mapping")
    evidence_unknown = set(evidence) - set(FORWARD_EVIDENCE_KEYS)
    if evidence_unknown:
        raise ValueError(
            "unknown forward evidence field(s): "
            + ", ".join(sorted(evidence_unknown))
        )
    if evidence.get("geometry_gate") not in GEOMETRY_GATE_STATES:
        raise ValueError(
            "forward evidence geometry_gate must be one of: "
            + ", ".join(GEOMETRY_GATE_STATES)
        )
    agreement = evidence.get("agreement")
    if agreement is not None:
        if isinstance(agreement, bool) or not isinstance(agreement, (int, float)):
            raise ValueError("forward evidence agreement must be a number or null")
        agreement = float(agreement)
        if not math.isfinite(agreement) or not 0.0 <= agreement <= 1.0:
            raise ValueError("forward evidence agreement must be within [0, 1]")
    notes = evidence.get("notes")
    if isinstance(notes, (str, bytes)) or not isinstance(notes, Sequence):
        raise ValueError("forward evidence notes must be an array of strings")
    for note in notes:
        if not isinstance(note, str):
            raise ValueError("forward evidence notes must be strings")

    # Consistency rules mirrored from the 3D-R contract.
    if status in ("verified", "supported"):
        if axis is None:
            raise ValueError(
                f"forward contract status {status!r} requires a concrete axis"
            )
    elif axis is not None:
        raise ValueError(
            f"forward contract status {status!r} requires axis to be null"
        )
    if source == "family_rule" and family is None:
        raise ValueError("forward contract source 'family_rule' requires a family")
    if source == "none" and axis is not None:
        raise ValueError("forward contract source 'none' must not carry an axis")

    return contract


def _validate_rule(rule):
    if not isinstance(rule, Mapping):
        raise ValueError("rule must be a mapping")

    unknown = set(rule) - set(RULE_KEYS)
    if unknown:
        raise ValueError("unknown rule field(s): " + ", ".join(sorted(unknown)))

    status = rule.get("status")
    if status not in RULE_STATUSES:
        raise ValueError(
            "rule status must be one of: " + ", ".join(RULE_STATUSES)
        )

    evidence = rule.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("rule evidence must be a mapping")

    return status


def _validate_family_id(family_id):
    """Strict form used when building a contract (family_rule needs a family)."""

    if family_id is None:
        return None
    if not isinstance(family_id, str) or not family_id.strip():
        raise ValueError("family_id must be a non-empty string or None")

    return family_id


def _is_blank_family_id(family_id):
    """Loose form used by resolution: absent or blank means 'no family supplied'."""

    if family_id is None:
        return True
    if isinstance(family_id, str):
        return not family_id.strip()

    raise ValueError("family_id must be a non-empty string or None")


def _validate_geometry_evidence(evidence):
    if not isinstance(evidence, Mapping):
        raise ValueError("geometry_evidence must be a mapping")
    if evidence.get("state") not in GEOMETRY_EVIDENCE_STATES:
        raise ValueError(
            "geometry_evidence state must be one of: "
            + ", ".join(GEOMETRY_EVIDENCE_STATES)
        )

    return evidence


# ---------------------------------------------------------------------------
# rule -> forward contract
# ---------------------------------------------------------------------------

def rule_to_forward_contract(rule, family_id):
    """Map a registry/caller rule to the existing forward contract shape.

    PURE. ``geometry_gate_required`` is deliberately NOT mapped: it has no
    contract field and is consumed directly from the rule by
    ``resolve_asset_forward``.

    Rule status controls whether an axis may exist at all: only a ``supported``
    rule may carry its declared axis. An ``unresolved`` or ``unsupported`` rule
    produces ``unresolved`` with a null axis - a family-level retraction is never
    restated as an asset-level ``unsupported``.
    """

    status = _validate_rule(rule)
    name = _validate_family_id(family_id)
    if name is None:
        raise ValueError("family_id is required when a rule is supplied")

    if status == "supported":
        axis = rule.get("semantic_forward_axis")
        if axis not in FORWARD_AXES:
            raise ValueError(
                "rule semantic_forward_axis must be one of: "
                + ", ".join(FORWARD_AXES)
            )
        contract_status = "supported"
    else:
        axis = None
        contract_status = "unresolved"

    evidence = rule["evidence"]
    notes = list(evidence.get("notes") or [])
    checkpoint = evidence.get("source_checkpoint")
    if isinstance(checkpoint, str) and checkpoint.strip():
        marker = f"source_checkpoint:{checkpoint}"
        if marker not in notes:
            notes.append(marker)

    return _validate_contract(
        {
            "status": contract_status,
            "axis": axis,
            "axis_frame": SOURCE_MESH_FRAME,
            "source": "family_rule",
            "family": name,
            "evidence": {
                "rule_id": evidence.get("rule_id"),
                "geometry_gate": "not_evaluated",
                "agreement": evidence.get("agreement"),
                "notes": notes,
            },
        }
    )


# ---------------------------------------------------------------------------
# asset-specific resolution
# ---------------------------------------------------------------------------

def resolve_asset_forward(*, rule, family_id=None, geometry_evidence=None):
    """Resolve a non-executable forward contract for one asset.

    ``rule`` may be ``None``. ``family_id`` is explicit upstream knowledge.
    ``geometry_evidence`` is either ``None`` or an already-computed Phase 3D-S
    evidence mapping - vertices are never accepted and geometry is never
    measured here.

    Geometry can only affect whether the ALREADY-DECLARED rule survives; the
    measured axis/sign is never inspected to select a semantic axis.
    """

    if _is_blank_family_id(family_id):
        # A blank value is echoed verbatim for auditability.
        return _result(
            family_id,
            OUTCOME_NO_FAMILY_SUPPLIED,
            "not_evaluated",
            UNRESOLVED_CONTRACT,
            ["family_id_not_supplied"],
        )

    name = family_id

    if rule is None:
        return _result(
            name,
            OUTCOME_FAMILY_UNKNOWN,
            "not_evaluated",
            UNRESOLVED_CONTRACT,
            ["no_rule_for_family"],
        )

    status = _validate_rule(rule)
    base = rule_to_forward_contract(rule, name)

    # --- rule not applicable ----------------------------------------------
    if status == "unresolved":
        return _result(
            name,
            OUTCOME_RULE_UNRESOLVED,
            "not_evaluated",
            base,
            ["rule_status_unresolved"],
        )

    if status == "unsupported":
        return _result(
            name,
            OUTCOME_RULE_UNSUPPORTED,
            "not_evaluated",
            base,
            ["rule_status_unsupported"],
        )

    # --- supported rule ---------------------------------------------------
    gate_required = rule.get("geometry_gate_required")
    if not isinstance(gate_required, bool):
        raise ValueError("rule geometry_gate_required must be a boolean")

    if not gate_required:
        # Geometry is not required. Supplied evidence is deliberately ignored
        # for resolution: it must never invent or replace the declared axis.
        reasons = ["rule_does_not_require_geometry_gate"]
        if geometry_evidence is not None:
            _validate_geometry_evidence(geometry_evidence)
            reasons.append("geometry_not_required_by_rule")

        return _result(
            name,
            OUTCOME_SUPPORTED_NO_GATE_REQUIRED,
            "not_evaluated",
            base,
            reasons,
        )

    expected = rule.get("expected_geometry_direction")
    if expected not in FORWARD_AXES:
        raise ValueError(
            "rule expected_geometry_direction must be one of: "
            + ", ".join(FORWARD_AXES)
        )

    if geometry_evidence is None:
        return _result(
            name,
            OUTCOME_GATE_NOT_EVALUATED_NO_GEOMETRY,
            "not_evaluated",
            resolve_forward_contract(base, "not_evaluated", None),
            ["geometry_evidence_not_supplied"],
        )

    evidence = _validate_geometry_evidence(geometry_evidence)
    state = evidence["state"]

    if state == "unobservable":
        return _result(
            name,
            OUTCOME_GEOMETRY_UNOBSERVABLE,
            "not_evaluated",
            resolve_forward_contract(base, "not_evaluated", "unobservable"),
            ["geometry_unobservable"],
        )

    if state == "ambiguous":
        return _result(
            name,
            OUTCOME_GEOMETRY_AMBIGUOUS,
            "not_evaluated",
            resolve_forward_contract(base, "not_evaluated", "ambiguous"),
            ["geometry_ambiguous"],
        )

    # Observable: the gate may only corroborate or reject the declared
    # expectation. The measured axis/sign is never read here.
    gate = evaluate_geometry_agreement(evidence, expected)

    if gate == "agreed":
        return _result(
            name,
            OUTCOME_GEOMETRY_AGREED,
            "agreed",
            resolve_forward_contract(base, "agreed", state),
            ["geometry_agrees_expected_direction"],
        )

    if gate == "disagreed":
        return _result(
            name,
            OUTCOME_GEOMETRY_DISAGREED,
            "disagreed",
            resolve_forward_contract(base, "disagreed", state),
            ["geometry_disagrees_expected_direction"],
        )

    # Defensive fallback; not reachable for well-formed observable evidence.
    return _result(
        name,
        OUTCOME_GATE_NOT_EVALUATED,
        "not_evaluated",
        resolve_forward_contract(base, "not_evaluated", None),
        ["geometry_gate_not_evaluated"],
    )


def _result(family_id, outcome, geometry_gate, forward_contract, reasons):
    return {
        "family_id": family_id,
        "outcome": outcome,
        "geometry_gate": geometry_gate,
        "forward_contract": _validate_contract(forward_contract),
        "reasons": list(reasons),
    }
