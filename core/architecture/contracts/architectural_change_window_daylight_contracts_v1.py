"""Versioned, generator-independent contracts for 01H window/daylight realization."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
import json
from typing import Any, Mapping, TypeVar


SCHEMA_VERSION = "architectural_change_window_daylight_contracts_v1"

WINDOW_DAYLIGHT_STATUS_REALIZED = "REALIZED"
WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS = "REALIZED_WITH_WARNINGS"
WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT = "REJECTED_CONSTRAINT"
WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY = "REJECTED_WINDOW_GEOMETRY"
WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE = "REJECTED_DAYLIGHT_EVIDENCE"
WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY = "REJECTED_PRIVACY"
WINDOW_DAYLIGHT_STATUS_STALE_PARENT = "STALE_PARENT"
WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY = "UNSUPPORTED_STRATEGY"
WINDOW_DAYLIGHT_STATUS_FAILED = "FAILED"
WINDOW_DAYLIGHT_STATUSES = (
    WINDOW_DAYLIGHT_STATUS_REALIZED,
    WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS,
    WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
    WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
    WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
    WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY,
    WINDOW_DAYLIGHT_STATUS_STALE_PARENT,
    WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY,
    WINDOW_DAYLIGHT_STATUS_FAILED,
)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_text_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field_name} must be a tuple of non-empty strings")


def _require_mapping_tuple(value: tuple[Mapping[str, Any], ...], field_name: str) -> None:
    if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{field_name} must be a tuple of mappings")


def _payload(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _payload(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_payload(item) for item in value]
    return deepcopy(value)


@dataclass(frozen=True)
class WindowDaylightDelta:
    window_interface_id: str
    target_space_id: str
    host_exterior_boundary_ref: str
    operation: str
    before_window: Mapping[str, Any] | None
    after_window: Mapping[str, Any]
    boundary_segment: tuple[tuple[float, float], tuple[float, float]]
    width: float
    height: float
    area: float
    source_of_dimensions: str
    position: Mapping[str, Any]
    source_of_position: str
    daylight_goal: Mapping[str, Any]
    privacy_constraints: tuple[str, ...]
    facade_exterior_relation: Mapping[str, Any]
    affected_openings: tuple[str, ...]
    preserved_constraints: tuple[str, ...]
    reason: str
    strategy_id: str
    provenance: Mapping[str, Any]
    delta_version: str = "architectural_change_window_daylight_delta_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "window_interface_id", "target_space_id", "host_exterior_boundary_ref",
            "operation", "source_of_dimensions", "source_of_position", "reason",
            "strategy_id", "delta_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.before_window is not None and not isinstance(self.before_window, Mapping):
            raise ValueError("before_window must be a mapping or None")
        for field_name in (
            "after_window", "position", "daylight_goal", "facade_exterior_relation", "provenance",
        ):
            if not isinstance(getattr(self, field_name), Mapping):
                raise ValueError(f"{field_name} must be a mapping")
        for field_name in ("width", "height", "area"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field_name} must be a positive number")
        if abs(float(self.area) - float(self.width) * float(self.height)) > 1e-7:
            raise ValueError("area must equal width * height")
        if (
            not isinstance(self.boundary_segment, tuple)
            or len(self.boundary_segment) != 2
            or any(not isinstance(point, tuple) or len(point) != 2 for point in self.boundary_segment)
        ):
            raise ValueError("boundary_segment must contain two coordinate pairs")
        for field_name in ("privacy_constraints", "affected_openings", "preserved_constraints"):
            _require_text_tuple(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class WindowDaylightRealizationResult:
    realization_id: str
    strategy_id: str
    parent_candidate_id: str
    derived_candidate_id: str | None
    status: str
    window_daylight_changes: tuple[WindowDaylightDelta, ...]
    affected_entities: tuple[str, ...]
    applied_operations: tuple[str, ...]
    rejected_operations: tuple[str, ...]
    geometry_checks: tuple[Mapping[str, Any], ...]
    daylight_checks: tuple[Mapping[str, Any], ...]
    privacy_checks: tuple[Mapping[str, Any], ...]
    constraint_checks: tuple[Mapping[str, Any], ...]
    required_downstream_rechecks: tuple[str, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    parent_hash: str
    derived_hash: str | None
    provenance: Mapping[str, Any]
    realization_version: str = "architectural_change_window_daylight_realization_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "realization_id", "strategy_id", "parent_candidate_id", "parent_hash",
            "realization_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.derived_candidate_id is not None:
            _require_text(self.derived_candidate_id, "derived_candidate_id")
        if self.derived_hash is not None:
            _require_text(self.derived_hash, "derived_hash")
        if self.status not in WINDOW_DAYLIGHT_STATUSES:
            raise ValueError(f"unsupported window/daylight realization status: {self.status}")
        if not isinstance(self.window_daylight_changes, tuple) or any(
            not isinstance(item, WindowDaylightDelta) for item in self.window_daylight_changes
        ):
            raise ValueError("window_daylight_changes must be a tuple of WindowDaylightDelta")
        for field_name in (
            "affected_entities", "applied_operations", "rejected_operations",
            "required_downstream_rechecks", "warnings", "failures",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        for field_name in ("geometry_checks", "daylight_checks", "privacy_checks", "constraint_checks"):
            _require_mapping_tuple(getattr(self, field_name), field_name)
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        committed = self.status in {
            WINDOW_DAYLIGHT_STATUS_REALIZED,
            WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS,
        }
        if committed and (
            not self.window_daylight_changes
            or self.derived_candidate_id is None
            or self.derived_hash is None
        ):
            raise ValueError("realized result requires a delta and derived candidate identity")
        if not committed and (
            self.window_daylight_changes
            or self.derived_candidate_id is not None
            or self.derived_hash is not None
        ):
            raise ValueError("rejected result cannot publish committed changes")


ContractT = TypeVar("ContractT", WindowDaylightDelta, WindowDaylightRealizationResult)


def serialize_contract(contract: ContractT) -> dict[str, Any]:
    if not isinstance(contract, (WindowDaylightDelta, WindowDaylightRealizationResult)):
        raise ValueError("unsupported 01H contract type")
    return {"schema_version": SCHEMA_VERSION, "contract_type": type(contract).__name__, "data": _payload(contract)}


def deserialize_contract(envelope: Mapping[str, Any]) -> ContractT:
    if not isinstance(envelope, Mapping) or envelope.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported 01H contract envelope")
    raw = envelope.get("data")
    if not isinstance(raw, Mapping):
        raise ValueError("contract data must be a mapping")
    values = deepcopy(dict(raw))
    name = envelope.get("contract_type")
    if name == "WindowDaylightDelta":
        for field_name in ("privacy_constraints", "affected_openings", "preserved_constraints"):
            values[field_name] = tuple(values.get(field_name, ()))
        values["boundary_segment"] = tuple(tuple(point) for point in values["boundary_segment"])
        return WindowDaylightDelta(**values)
    if name == "WindowDaylightRealizationResult":
        raw_changes = values.get("window_daylight_changes")
        if not isinstance(raw_changes, (list, tuple)):
            raise ValueError("window_daylight_changes must be a list or tuple")
        changes = []
        for raw_change in raw_changes:
            change = deepcopy(dict(raw_change))
            for field_name in ("privacy_constraints", "affected_openings", "preserved_constraints"):
                change[field_name] = tuple(change.get(field_name, ()))
            change["boundary_segment"] = tuple(tuple(point) for point in change["boundary_segment"])
            changes.append(WindowDaylightDelta(**change))
        values["window_daylight_changes"] = tuple(changes)
        for field_name in (
            "affected_entities", "applied_operations", "rejected_operations",
            "geometry_checks", "daylight_checks", "privacy_checks", "constraint_checks",
            "required_downstream_rechecks", "warnings", "failures",
        ):
            values[field_name] = tuple(values.get(field_name, ()))
        return WindowDaylightRealizationResult(**values)
    raise ValueError(f"unknown 01H contract type: {name}")


def dumps_contract(contract: ContractT) -> str:
    return json.dumps(serialize_contract(contract), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_contract(document: str) -> ContractT:
    if not isinstance(document, str):
        raise ValueError("contract document must be a string")
    return deserialize_contract(json.loads(document))


__all__ = [
    "SCHEMA_VERSION", "WINDOW_DAYLIGHT_STATUSES",
    "WINDOW_DAYLIGHT_STATUS_REALIZED", "WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS",
    "WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT",
    "WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY",
    "WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE",
    "WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY", "WINDOW_DAYLIGHT_STATUS_STALE_PARENT",
    "WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY", "WINDOW_DAYLIGHT_STATUS_FAILED",
    "WindowDaylightDelta", "WindowDaylightRealizationResult",
    "serialize_contract", "deserialize_contract", "dumps_contract", "loads_contract",
]
