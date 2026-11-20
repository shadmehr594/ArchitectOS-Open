"""Declarative furniture unit contract (Phase 3D-AL).

Makes the CURRENT unit confidence for the furniture asset path machine-readable,
keeps that evidence separate from geometry execution, and flags obviously
suspicious asset dimension ranges.

The Phase 3D-AK audit established:

- DiffuScene ``center_xyz`` is a room-local object bounding-box center and the
  pre-doubling ``sizes`` are bbox half-extents (both PROVEN from code and data).
- DiffuScene physical values are strongly consistent with meters, but no
  authoritative unit declaration exists locally, so the unit is SUPPORTED.
- 3D-FUTURE registry dimensions are ``raw_model.obj`` numerical extents verbatim
  and no unit conversion exists in the asset path, so raw-asset meters are
  SUPPORTED, with a small but real mis-scaled population.

This module is METADATA ONLY. It deliberately does NOT:

- load, open or parse any OBJ / registry / data file, or touch the filesystem
- import ``raw_obj_loader``, ``mesh_transform_spec``, ``mesh_transform_executor``
  or ``FurnitureAdapter``
- inspect vertices, faces, bounds or any mesh geometry
- rescale geometry, convert centimeters to meters, or divide / multiply by 100
- authorize, apply or emit a non-identity scale
- move centers, snap to a floor, or recompute transforms
- use randomness, UUIDs, timestamps, environment variables, global counters,
  registry lookups or geometry hashes

CONFIDENCE RULE (the central invariant): compatibility confidence is BOUNDED BY
evidence confidence and can only ever be DOWNGRADED, never upgraded.

    supported + supported           -> at most supported
    proven    + supported           -> at most supported
    supported + unresolved          -> unresolved
    proven    + proven + same unit  -> proven
    different nominal units         -> unresolved

Suspicious dimensions may downgrade a supported/proven result to unresolved, but
they can never raise confidence. No evidence object may silently promote
SUPPORTED to PROVEN.

DIMENSION THRESHOLDS are DIAGNOSTIC HEURISTICS, not authoritative unit
detection. They flag obvious oversize ranges only; they never assert that an
asset is measured in centimeters.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping


OUTPUT_TYPE = "furniture_unit_contract"
OUTPUT_VERSION = "furniture_unit_contract_v1"

UNIT_STATUSES = ("proven", "supported", "unresolved")
UNIT_STATUS_PROVEN = "proven"
UNIT_STATUS_SUPPORTED = "supported"
UNIT_STATUS_UNRESOLVED = "unresolved"

# Diagnostic heuristics derived from the Phase 3D-AK measurement of the real
# registry: 96.7% of assets have a maximum dimension below 2.5 m and the
# plausible furniture ceiling sits well under 5 m, while 198 assets (1.20%)
# exceed 5 m and 178 (1.07%) exceed 50 m. These bounds are DIAGNOSTIC ONLY.
PLAUSIBLE_MAX_DIMENSION_M = 5.0
SEVERE_MAX_DIMENSION_M = 50.0

DIMENSION_STATUS_NOT_EVALUATED = "not_evaluated"
DIMENSION_STATUS_PLAUSIBLE = "plausible"
DIMENSION_STATUS_SUSPICIOUS = "suspicious"

STATE_PROVEN = "unit_contract_proven"
STATE_SUPPORTED = "unit_contract_supported"
STATE_UNRESOLVED = "unit_contract_unresolved"

IDENTITY_SCALE = (1.0, 1.0, 1.0)

EVIDENCE_KEYS = ("numeric_unit", "status", "source", "notes", "proven")


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _non_empty_string(value, label):
    """Return a non-empty string unchanged, else raise.

    ``bool`` is rejected explicitly: a boolean is never a valid identifier.
    """

    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _validate_unit_evidence(evidence, label):
    """Validate and copy one caller-supplied unit evidence descriptor.

    Nothing is inferred from global state: every fact must be supplied, and
    ``proven`` is DERIVED from ``status`` - never accepted as a promotion.
    """

    if not isinstance(evidence, Mapping):
        raise ValueError(f"{label} evidence must be a mapping")

    unknown = set(evidence) - set(EVIDENCE_KEYS)
    if unknown:
        raise ValueError(
            f"unknown {label} evidence key(s): " + ", ".join(sorted(unknown))
        )

    for key in ("numeric_unit", "status", "source"):
        if key not in evidence:
            raise ValueError(f"{label} evidence is missing: {key}")

    numeric_unit = evidence["numeric_unit"]
    if numeric_unit is not None and (
        isinstance(numeric_unit, bool)
        or not isinstance(numeric_unit, str)
        or not numeric_unit.strip()
    ):
        raise ValueError(
            f"{label} evidence numeric_unit must be a non-empty string or None"
        )

    status = evidence["status"]
    if isinstance(status, bool) or status not in UNIT_STATUSES:
        raise ValueError(
            f"{label} evidence status must be one of: " + ", ".join(UNIT_STATUSES)
        )

    source = _non_empty_string(evidence["source"], f"{label} evidence source")

    notes = evidence.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError(f"{label} evidence notes must be a list of strings")
    cleaned_notes = []
    for note in notes:
        if not isinstance(note, str):
            raise ValueError(f"{label} evidence notes must be strings")
        cleaned_notes.append(note)

    derived_proven = status == UNIT_STATUS_PROVEN
    if "proven" in evidence:
        supplied_proven = evidence["proven"]
        if not isinstance(supplied_proven, bool):
            raise ValueError(f"{label} evidence proven must be a boolean")
        # A supplied flag may never contradict (and therefore never promote) the
        # status it claims to describe.
        if supplied_proven != derived_proven:
            raise ValueError(
                f"{label} evidence proven must agree with status "
                f"{status!r} (SUPPORTED can never be reported as PROVEN)"
            )

    return {
        "numeric_unit": numeric_unit,
        "status": status,
        # Derived, never caller-authoritative.
        "proven": derived_proven,
        "source": source,
        "notes": list(cleaned_notes),
    }


def _validate_dimensions(dimensions):
    """Validate optional finite, strictly positive XYZ dimensions.

    Returns a NEW list, or ``None``. No conversion of any kind is applied.
    """

    if dimensions is None:
        return None

    if isinstance(dimensions, (str, bytes)) or not isinstance(
        dimensions, (list, tuple)
    ):
        raise ValueError(
            "asset_dimensions_xyz must be a three-value vector or None"
        )
    if len(dimensions) != 3:
        raise ValueError("asset_dimensions_xyz must be a three-value vector")

    values = []
    for value in dimensions:
        # Strings and booleans are malformed dimensions, not numbers to coerce.
        if isinstance(value, (str, bytes)) or isinstance(value, bool):
            raise ValueError(
                "asset_dimensions_xyz entries must be real numbers"
            )
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                "asset_dimensions_xyz entries must be real numbers"
            )
        if not math.isfinite(number):
            raise ValueError("asset_dimensions_xyz entries must be finite")
        if number <= 0.0:
            raise ValueError(
                "asset_dimensions_xyz entries must be strictly positive"
            )
        values.append(number)

    return values


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------

def _dimension_check(dimensions):
    """Diagnostic oversize check. Never a unit assertion, never a conversion."""

    thresholds = {
        "plausible_max_dimension": PLAUSIBLE_MAX_DIMENSION_M,
        "severe_max_dimension": SEVERE_MAX_DIMENSION_M,
        "basis": "diagnostic_heuristic_not_unit_detection",
    }

    if dimensions is None:
        return {
            "status": DIMENSION_STATUS_NOT_EVALUATED,
            "max_dimension": None,
            "min_dimension": None,
            "severe_oversize": False,
            "thresholds": copy.deepcopy(thresholds),
            "reasons": ["asset_dimensions_not_supplied"],
        }

    maximum = max(dimensions)
    minimum = min(dimensions)
    reasons = []

    if maximum > SEVERE_MAX_DIMENSION_M:
        status = DIMENSION_STATUS_SUSPICIOUS
        severe_oversize = True
        reasons.append("asset_dimension_exceeds_expected_furniture_range")
        reasons.append("asset_dimension_far_exceeds_expected_furniture_range")
    elif maximum > PLAUSIBLE_MAX_DIMENSION_M:
        status = DIMENSION_STATUS_SUSPICIOUS
        severe_oversize = False
        reasons.append("asset_dimension_exceeds_expected_furniture_range")
    else:
        status = DIMENSION_STATUS_PLAUSIBLE
        severe_oversize = False
        reasons.append("asset_dimension_within_expected_furniture_range")

    # NOTE: no unit is ever inferred here. A large asset is reported as
    # out-of-range, never as "centimeters".
    reasons.append("no_unit_conversion_applied")

    return {
        "status": status,
        "max_dimension": maximum,
        "min_dimension": minimum,
        "severe_oversize": severe_oversize,
        "thresholds": copy.deepcopy(thresholds),
        "reasons": reasons,
    }


def _bounded_confidence(diffuscene, raw_asset):
    """Compatibility confidence = the WEAKER of the two evidence statuses."""

    statuses = (diffuscene["status"], raw_asset["status"])

    if UNIT_STATUS_UNRESOLVED in statuses:
        return UNIT_STATUS_UNRESOLVED
    if UNIT_STATUS_SUPPORTED in statuses:
        return UNIT_STATUS_SUPPORTED

    return UNIT_STATUS_PROVEN


def _compatibility(diffuscene, raw_asset, dimension_check):
    reasons = []

    status = _bounded_confidence(diffuscene, raw_asset)
    reasons.append("compatibility_confidence_bounded_by_evidence_confidence")

    if diffuscene["status"] == UNIT_STATUS_UNRESOLVED:
        reasons.append("diffuscene_unit_unresolved")
    if raw_asset["status"] == UNIT_STATUS_UNRESOLVED:
        reasons.append("raw_asset_unit_unresolved")
    if diffuscene["status"] == UNIT_STATUS_SUPPORTED:
        reasons.append("diffuscene_unit_supported_not_proven")
    if raw_asset["status"] == UNIT_STATUS_SUPPORTED:
        reasons.append("raw_asset_unit_supported_not_proven")

    if diffuscene["numeric_unit"] is None or raw_asset["numeric_unit"] is None:
        same_nominal_unit = None
        status = UNIT_STATUS_UNRESOLVED
        reasons.append("nominal_unit_missing")
    else:
        same_nominal_unit = (
            diffuscene["numeric_unit"] == raw_asset["numeric_unit"]
        )
        if not same_nominal_unit:
            status = UNIT_STATUS_UNRESOLVED
            reasons.append("nominal_unit_mismatch")

    # Suspicion can only ever downgrade.
    if dimension_check["status"] == DIMENSION_STATUS_SUSPICIOUS:
        status = UNIT_STATUS_UNRESOLVED
        reasons.append("asset_dimension_suspicious")

    if status == UNIT_STATUS_PROVEN:
        reasons.append("both_units_proven_and_compatible")

    return {
        "status": status,
        "same_nominal_unit": same_nominal_unit,
        # Never authorized in this phase, at any confidence level.
        "geometry_scaling_authorized": False,
        "scale_xyz": list(IDENTITY_SCALE),
        "reasons": reasons,
    }


def _semantics():
    return {
        "metadata_only": True,
        "geometry_modified": False,
        "unit_conversion_applied": False,
        "non_identity_scale_authorized": False,
    }


def _contract_state(compatibility_status):
    if compatibility_status == UNIT_STATUS_PROVEN:
        return STATE_PROVEN
    if compatibility_status == UNIT_STATUS_SUPPORTED:
        return STATE_SUPPORTED

    return STATE_UNRESOLVED


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_furniture_unit_contract(
    *,
    diffuscene_unit_evidence,
    raw_asset_unit_evidence,
    asset_dimensions_xyz=None,
):
    """Build a pure, metadata-only furniture unit contract.

    ``diffuscene_unit_evidence`` and ``raw_asset_unit_evidence`` are REQUIRED
    caller-supplied descriptors (``numeric_unit``, ``status``, ``source``,
    optional ``notes``). Every fact must be supplied explicitly - nothing is
    inferred from global state, and ``proven`` is derived from ``status`` so a
    SUPPORTED evidence object can never be silently promoted.

    ``asset_dimensions_xyz`` is an OPTIONAL, already-known XYZ dimension triple.
    It is only used for a diagnostic oversize check: no OBJ file is opened, no
    geometry is inspected, no conversion is applied and the values are never
    mutated.

    Compatibility confidence is bounded by evidence confidence and can only be
    downgraded. ``geometry_scaling_authorized`` is always ``False`` and
    ``scale_xyz`` is always identity, at every confidence level.

    Pure function: no filesystem access, no registry or model lookup, no
    randomness, no timestamps and no transform execution. Malformed input raises
    ``ValueError``.
    """

    diffuscene = _validate_unit_evidence(
        diffuscene_unit_evidence, "diffuscene"
    )
    raw_asset = _validate_unit_evidence(raw_asset_unit_evidence, "raw_asset")
    dimensions = _validate_dimensions(asset_dimensions_xyz)

    dimension_check = _dimension_check(dimensions)
    compatibility = _compatibility(diffuscene, raw_asset, dimension_check)

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "diffuscene": diffuscene,
        "raw_asset": raw_asset,
        "compatibility": compatibility,
        "asset_dimension_check": dimension_check,
        "semantics": _semantics(),
        # The contract state mirrors the (already bounded) compatibility verdict.
        "status": {
            "state": _contract_state(compatibility["status"]),
            "reasons": list(compatibility["reasons"]),
        },
    }
