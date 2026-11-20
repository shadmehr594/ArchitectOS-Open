"""Explicit level-name bridge and elevation provenance (Phase 3D-AO refinement).

Phase 3D-AO resolves a support plane from a room volume contract, and that
contract accepts a level contract as an optional elevation source. Recon of
``core/architecture/reasoning/project_level_contract_v1.py`` established that:

- ``exact_levels`` is the ONLY exact elevation carrier, and it is authoritative
  only by gate: a record is admitted only when its ``authority_class`` is one of
  ``("HARD_REGULATION", "PROJECT_REQUIREMENT")`` AND it carries non-empty
  ``provenance``. Any conflict voids the ENTIRE map.
- ``exact_levels`` also contains SPAN-DERIVED elevations, computed across
  ``floor_to_floor_span`` records. "Exact" therefore does not mean "directly
  measured", and ``level_evidence`` is the only way to tell the two apart.
- ``range_hypotheses`` are echoed but never used, and are hard-flagged
  ``range_hypotheses_authoritative: False``.

The remaining gap was naming. Level names are free-form, and this repository
carries at least three disagreeing vocabularies:

- space boundary engine ``FLOORS = ("G", "R1", "R2", "ROOF")``
- IFC exporter / spatial contract ``"F1"``, ``"F2"``
- level contract / floor-type resolver ``"ground"``, ``"basement"``, ``"roof"``

Using a space record's ``floor`` label directly as the level key therefore
silently misses. This module makes that bridge EXPLICIT and reports where the
elevation came from.

This module is METADATA ONLY. It deliberately does NOT:

- move, snap, shift, scale or correct any geometry
- change any placement, transform, vertex, bound, center or scale
- authorise a geometry adjustment
- read or write any external data, or access the filesystem
- use randomness, UUIDs, timestamps or global counters
- import ``FurnitureAdapter``, ``placement_identity``,
  ``asset_scene_instance_collection``, ``furniture_unit_contract``,
  ``furniture_support_policy``, the Phase 3D-AN contact contract, the Phase
  3D-AO room volume contract, ``raw_obj_loader``, ``mesh_transform_spec`` or
  ``mesh_transform_executor``

The Phase 3D-AN and Phase 3D-AO modules are named by phase rather than by module
path on purpose: each ships a wiring guard that scans production sources for its
own module name as a plain substring, so even a documentation mention registers
as a reference. The boundary is unchanged either way.

NO WIRING: nothing consumes this module yet. The room volume contract is
untouched, so current behaviour is unchanged.

CONTRACT GATING (as approved)
-----------------------------
- ``level_contract`` absent -> ``unresolved`` (never silently accepted).
- ``level_contract`` present but missing its ``contract`` name -> ``unresolved``.
- ``contract`` present and NOT ``"ProjectLevelContractV1"`` -> ``ValueError``;
  a wrong contract object is malformed input, not a resolution outcome.
- ``status != "resolved"`` -> ``unresolved``.
- evidence with MIXED authority classes, or an authority outside the exact set,
  -> ``unresolved``. A winner is never selected.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


OUTPUT_TYPE = "level_elevation_resolution"
OUTPUT_VERSION = "level_elevation_resolution_v1"

LEVEL_CONTRACT_NAME = "ProjectLevelContractV1"
LEVEL_CONTRACT_STATUSES = ("resolved", "conflicted", "unresolved")

# Mirrors ProjectLevelContractV1.EXACT_AUTHORITIES (read-only alignment).
EXACT_AUTHORITIES = ("HARD_REGULATION", "PROJECT_REQUIREMENT")

EVIDENCE_KINDS = ("level_elevation", "floor_to_floor_span")

SOURCE_EXPLICIT = "explicit_level_name"
SOURCE_BRIDGE = "floor_bridge_mapping"

DERIVATION_DIRECT = "directly_stated"
DERIVATION_SPAN = "derived_from_floor_to_floor_span"

ELEVATION_RESOLVED = "resolved"
ELEVATION_UNRESOLVED = "unresolved"

STATE_RESOLVED = "level_elevation_resolved"
STATE_UNRESOLVED = "level_elevation_unresolved"


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _finite_scalar(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a real number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a real number")
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")

    return number


def _non_empty_string(value, label):
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _optional_non_empty_string(value, label):
    if value is None:
        return None

    return _non_empty_string(value, label)


def _validate_bridge_mapping(mapping):
    """Validate an optional explicit {floor_label: level_name} bridge."""

    if mapping is None:
        return None
    if not isinstance(mapping, Mapping):
        raise ValueError(
            "level_name_by_floor must be a mapping of floor label to level name "
            "or None"
        )

    cleaned = {}
    for floor_label, level_name in mapping.items():
        cleaned[_non_empty_string(floor_label, "level_name_by_floor key")] = (
            _non_empty_string(
                level_name, f"level_name_by_floor[{floor_label!r}]"
            )
        )

    return cleaned


def _validate_level_contract(level_contract):
    """Validate the level contract and report whether it may be trusted."""

    if level_contract is None:
        return {
            "contract": None,
            "status": None,
            "authoritative": False,
            "exact_levels": {},
            "level_evidence": {},
            "reasons": ["level_contract_not_supplied"],
        }

    if not isinstance(level_contract, Mapping):
        raise ValueError("level_contract must be a mapping or None")

    name = level_contract.get("contract")
    if name is None:
        # Deliberately NOT silently accepted: an unnamed contract is unresolved.
        return {
            "contract": None,
            "status": None,
            "authoritative": False,
            "exact_levels": {},
            "level_evidence": {},
            "reasons": ["level_contract_name_missing"],
        }

    if name != LEVEL_CONTRACT_NAME:
        raise ValueError(
            f"level_contract.contract must be {LEVEL_CONTRACT_NAME!r} when present"
        )

    status = level_contract.get("status")
    if isinstance(status, bool) or status not in LEVEL_CONTRACT_STATUSES:
        raise ValueError(
            "level_contract.status must be one of: "
            + ", ".join(LEVEL_CONTRACT_STATUSES)
        )

    if status != "resolved":
        return {
            "contract": name,
            "status": status,
            "authoritative": False,
            "exact_levels": {},
            "level_evidence": {},
            "reasons": [
                f"level_contract_status_{status}_not_authoritative_for_elevation"
            ],
        }

    exact_levels = level_contract.get("exact_levels")
    if not isinstance(exact_levels, Mapping):
        raise ValueError(
            "a resolved level_contract requires an exact_levels mapping"
        )

    cleaned_levels = {}
    for level, elevation in exact_levels.items():
        cleaned_levels[_non_empty_string(level, "exact_levels level name")] = (
            _finite_scalar(elevation, f"exact_levels[{level!r}]")
        )

    raw_evidence = level_contract.get("level_evidence", {})
    if not isinstance(raw_evidence, Mapping):
        raise ValueError(
            "level_contract.level_evidence must be a mapping when present"
        )

    cleaned_evidence = {}
    for level, records in raw_evidence.items():
        level = _non_empty_string(level, "level_evidence level name")
        if isinstance(records, (str, bytes)) or not isinstance(
            records, (list, tuple)
        ):
            raise ValueError(
                f"level_evidence[{level!r}] must be a list of records"
            )
        cleaned_records = []
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise ValueError(
                    f"level_evidence[{level!r}][{index}] must be a mapping"
                )
            kind = record.get("kind")
            if isinstance(kind, bool) or kind not in EVIDENCE_KINDS:
                raise ValueError(
                    f"level_evidence[{level!r}][{index}].kind must be one of: "
                    + ", ".join(EVIDENCE_KINDS)
                )
            authority = record.get("authority_class")
            if authority is not None and (
                isinstance(authority, bool) or not isinstance(authority, str)
            ):
                raise ValueError(
                    f"level_evidence[{level!r}][{index}].authority_class must be "
                    "a string or None"
                )
            provenance = record.get("provenance")
            if provenance is None:
                provenance = []
            if isinstance(provenance, (str, bytes)) or not isinstance(
                provenance, (list, tuple)
            ):
                raise ValueError(
                    f"level_evidence[{level!r}][{index}].provenance must be a "
                    "list of strings"
                )
            cleaned_provenance = []
            for item in provenance:
                cleaned_provenance.append(
                    _non_empty_string(
                        item,
                        f"level_evidence[{level!r}][{index}].provenance entry",
                    )
                )
            cleaned_records.append(
                {
                    "kind": kind,
                    "authority_class": authority,
                    "provenance": cleaned_provenance,
                }
            )
        cleaned_evidence[level] = cleaned_records

    return {
        "contract": name,
        "status": status,
        "authoritative": True,
        "exact_levels": cleaned_levels,
        "level_evidence": cleaned_evidence,
        "reasons": ["level_contract_resolved_and_authoritative"],
    }


def _semantics():
    """Static, declarative facts. Every geometry action stays False."""

    return {
        "metadata_only": True,
        "geometry_modified": False,
        "placement_modified": False,
        "snap_applied": False,
        "geometry_adjustment_authorized": False,
    }


def _dedupe(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)

    return seen


# ---------------------------------------------------------------------------
# bridge resolution
# ---------------------------------------------------------------------------

def _resolve_level_name(level_name, floor, bridge):
    """Apply the approved precedence: explicit name, then bridge, then nothing."""

    reasons = []
    consulted = bridge is not None and floor is not None
    mapping_verified = floor in bridge if consulted else None

    if level_name is not None:
        source = SOURCE_EXPLICIT
        used = False
        resolved = level_name
        reasons.append("level_name_supplied_explicitly")
        if consulted and mapping_verified:
            reasons.append("bridge_mapping_would_also_have_resolved")
    elif consulted and mapping_verified:
        source = SOURCE_BRIDGE
        used = True
        resolved = bridge[floor]
        reasons.append("level_name_resolved_from_explicit_bridge_mapping")
    else:
        source = None
        used = False
        resolved = None
        if bridge is None:
            reasons.append("neither_level_name_nor_bridge_mapping_supplied")
        elif floor is None:
            reasons.append("floor_label_not_supplied_for_bridge_lookup")
        else:
            reasons.append("floor_label_absent_from_bridge_mapping")

    if resolved is not None and floor is not None:
        floor_label_equals_level_name = floor == resolved
    else:
        floor_label_equals_level_name = None

    return {
        "used": used,
        "source": source,
        "mapping_verified": mapping_verified,
        "level_name": resolved,
        "space_floor_label": floor,
        "floor_label_equals_level_name": floor_label_equals_level_name,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# elevation resolution
# ---------------------------------------------------------------------------

def _unresolved_elevation(reasons):
    return {
        "status": ELEVATION_UNRESOLVED,
        "value_m": None,
        "derivation": None,
        "authority_class": None,
        "provenance": [],
        "evidence": [],
        "reasons": list(reasons),
    }


def _resolve_elevation(bridge, contract):
    if bridge["level_name"] is None:
        return _unresolved_elevation(["level_name_unresolved"])

    if not contract["authoritative"]:
        return _unresolved_elevation(list(contract["reasons"]))

    level_name = bridge["level_name"]
    if level_name not in contract["exact_levels"]:
        return _unresolved_elevation(["level_name_absent_from_exact_levels"])

    evidence = contract["level_evidence"].get(level_name)
    if not evidence:
        # Fail closed: an elevation with no evidence chain cannot be trusted and
        # cannot be labelled as stated or span-derived.
        return _unresolved_elevation(["level_evidence_absent"])

    authorities = {record["authority_class"] for record in evidence}
    if len(authorities) != 1:
        # Never select a winner.
        return _unresolved_elevation(["mixed_authority_classes"])

    authority_class = authorities.pop()
    if authority_class not in EXACT_AUTHORITIES:
        return _unresolved_elevation(["evidence_authority_not_exact"])

    provenance = _dedupe(
        [item for record in evidence for item in record["provenance"]]
    )
    if not provenance:
        return _unresolved_elevation(["evidence_provenance_absent"])

    derivation = (
        DERIVATION_SPAN
        if any(record["kind"] == "floor_to_floor_span" for record in evidence)
        else DERIVATION_DIRECT
    )

    return {
        "status": ELEVATION_RESOLVED,
        "value_m": contract["exact_levels"][level_name],
        "derivation": derivation,
        "authority_class": authority_class,
        "provenance": provenance,
        "evidence": [dict(record) for record in evidence],
        "reasons": [f"elevation_{derivation}"],
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def resolve_level_elevation(
    *,
    level_contract,
    level_name=None,
    floor=None,
    level_name_by_floor=None,
):
    """Resolve one EXACT level elevation, with an explicit name bridge.

    Precedence, exactly as approved:

    1. an explicit ``level_name``;
    2. ``level_name_by_floor[floor]`` - an explicit, caller-supplied bridge
       between the space-record floor vocabulary and the level-name vocabulary;
    3. otherwise unresolved.

    The ``floor`` label is NEVER used as a level name on its own; it is recorded
    for provenance and for the ``floor_label_equals_level_name`` diagnostic.

    ``level_contract`` is a ``ProjectLevelContractV1`` result mapping. It is
    consumed read-only and this module never imports the module that produced
    it. An absent contract, an unnamed contract, or a contract whose status is
    not ``resolved`` all yield ``elevation.status == "unresolved"``; a contract
    that is present but names something else raises ``ValueError``.

    ``elevation.provenance`` is derived from the level's own evidence chain, and
    ``elevation.derivation`` distinguishes a directly stated elevation from one
    computed across a ``floor_to_floor_span`` record. Mixed or non-exact
    authority classes yield ``unresolved`` - no winner is ever selected.

    Pure function: no filesystem, no external data, no geometry, no randomness.
    Malformed input raises ``ValueError``.
    """

    resolved_level_name = _optional_non_empty_string(level_name, "level_name")
    resolved_floor = _optional_non_empty_string(floor, "floor")
    bridge_mapping = _validate_bridge_mapping(level_name_by_floor)

    bridge = _resolve_level_name(
        resolved_level_name, resolved_floor, bridge_mapping
    )
    contract = _validate_level_contract(level_contract)
    elevation = _resolve_elevation(bridge, contract)

    state = (
        STATE_RESOLVED
        if elevation["status"] == ELEVATION_RESOLVED
        else STATE_UNRESOLVED
    )

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "bridge_resolution": bridge,
        "level_contract": {
            "contract": contract["contract"],
            "status": contract["status"],
            "authoritative": contract["authoritative"],
            "reasons": list(contract["reasons"]),
        },
        "elevation": elevation,
        "semantics": _semantics(),
        "status": {
            "state": state,
            "reasons": _dedupe(
                list(bridge["reasons"])
                + list(contract["reasons"])
                + list(elevation["reasons"])
            ),
        },
    }
