"""Generic, authority-aware contracts required before Room Planning V2 geometry.

This module deliberately validates declarations only.  It neither allocates nor
generates room geometry and it never promotes design knowledge to regulation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class ProvenanceClass(str, Enum):
    REGULATION = "REGULATION"
    PROJECT_REQUIREMENT = "PROJECT_REQUIREMENT"
    DESIGN_KNOWLEDGE_NON_AUTHORITATIVE = "DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"


class EvidenceStatus(str, Enum):
    VERIFIED_APPLICABLE = "VERIFIED_APPLICABLE"
    UNVERIFIED_AUTHORITY = "UNVERIFIED_AUTHORITY"
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    provenance_class: ProvenanceClass
    status: EvidenceStatus
    clause: str | None = None
    printed_page: int | None = None
    pdf_page: int | None = None
    applicability: str = "unresolved"

    @property
    def may_enforce_regulation(self) -> bool:
        return (
            self.provenance_class is ProvenanceClass.REGULATION
            and self.status is EvidenceStatus.VERIFIED_APPLICABLE
            and bool(self.clause)
            and self.printed_page is not None
            and self.pdf_page is not None
            and self.applicability == "applicable"
        )


@dataclass(frozen=True)
class ResolvedRoom:
    room_id: str
    use: str
    access_resolved: bool
    useful_dimensions_resolved: bool
    adjacency_resolved: bool
    privacy_resolved: bool
    daylight_ventilation_resolved: bool
    furniture_usability_resolved: bool
    service_relation_resolved: bool | None
    evidence: tuple[EvidenceRef, ...] = ()

    @property
    def is_resolved(self) -> bool:
        required = (
            self.access_resolved,
            self.useful_dimensions_resolved,
            self.adjacency_resolved,
            self.privacy_resolved,
            self.daylight_ventilation_resolved,
            self.furniture_usability_resolved,
        )
        return all(required) and self.service_relation_resolved is not False


@dataclass(frozen=True)
class Door:
    door_id: str
    space_a: str
    space_b: str
    host_boundary_id: str
    opening_geometry: Mapping[str, Any]
    swing_clearance_checked: bool
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class DaylightSource:
    source_id: str
    source_type: str  # EXTERIOR_EDGE | LIGHTWELL | PATIO | VOID
    geometry: Mapping[str, Any]
    ventilation_capability: str
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class Window:
    window_id: str
    room_id: str
    source_id: str
    host_boundary_id: str
    geometry: Mapping[str, Any]
    area_m2: float | None
    conflict_checks_passed: bool
    opening_basis: EvidenceRef | None


@dataclass(frozen=True)
class LightwellPatioVoid:
    source_id: str
    kind: str
    geometry: Mapping[str, Any]
    area_m2: float
    served_room_ids: tuple[str, ...]
    counted_as_unallocatable_area: bool
    privacy_checked: bool
    ventilation_checked: bool
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class AllocationAccounting:
    unit_area_m2: float
    room_area_m2: float
    circulation_area_m2: float
    lightwell_patio_void_area_m2: float
    residual_area_m2: float

    @property
    def balances(self) -> bool:
        total = self.room_area_m2 + self.circulation_area_m2 + self.lightwell_patio_void_area_m2 + self.residual_area_m2
        return abs(total - self.unit_area_m2) <= 1e-6 and min(asdict(self).values()) >= 0


@dataclass(frozen=True)
class RoomPlanningContract:
    rooms: tuple[ResolvedRoom, ...]
    doors: tuple[Door, ...]
    sources: tuple[DaylightSource, ...]
    windows: tuple[Window, ...]
    voids: tuple[LightwellPatioVoid, ...]
    allocation: AllocationAccounting
    unit_threshold_space_id: str
    common_corridor_space_id: str
    private_circulation_space_ids: tuple[str, ...]
    building_program_provenance: ProvenanceClass
    room_level_v2_geometry_generated: bool = False


def validate_contract(contract: RoomPlanningContract) -> dict[str, Any]:
    """Return an audit result without mutating caller-owned input."""
    c = deepcopy(contract)
    errors: list[str] = []
    room_ids = {r.room_id for r in c.rooms}
    source_ids = {s.source_id for s in c.sources}
    door_graph = {r: set() for r in room_ids | {c.unit_threshold_space_id, c.common_corridor_space_id} | set(c.private_circulation_space_ids)}
    for d in c.doors:
        if d.space_a == d.space_b or not d.host_boundary_id or not d.opening_geometry or not d.swing_clearance_checked:
            errors.append(f"INVALID_DOOR:{d.door_id}")
        door_graph.setdefault(d.space_a, set()).add(d.space_b)
        door_graph.setdefault(d.space_b, set()).add(d.space_a)
    if c.common_corridor_space_id in set(c.private_circulation_space_ids) | room_ids:
        errors.append("COMMON_CORRIDOR_CROSSES_UNIT_THRESHOLD")
    if c.unit_threshold_space_id not in door_graph.get(c.common_corridor_space_id, set()):
        errors.append("NO_COMMON_CORRIDOR_TO_THRESHOLD_DOOR")

    windows_by_room: dict[str, list[Window]] = {}
    for w in c.windows:
        windows_by_room.setdefault(w.room_id, []).append(w)
        if w.room_id not in room_ids or w.source_id not in source_ids or not w.geometry or not w.host_boundary_id:
            errors.append(f"BROKEN_ROOM_SOURCE_WINDOW_CHAIN:{w.window_id}")
        if w.area_m2 is not None and (w.opening_basis is None or not w.opening_basis.may_enforce_regulation):
            errors.append(f"UNAUTHORIZED_NUMERIC_OPENING_PROMOTION:{w.window_id}")
        if not w.conflict_checks_passed:
            errors.append(f"WINDOW_CONFLICT_UNRESOLVED:{w.window_id}")

    for room in c.rooms:
        if not room.is_resolved:
            errors.append(f"ROOM_NOT_RESOLVED:{room.room_id}")
        if room.daylight_ventilation_resolved and not windows_by_room.get(room.room_id):
            errors.append(f"NO_ROOM_SOURCE_WINDOW_CHAIN:{room.room_id}")
        if room.use in {"bedroom", "living", "habitable_room"}:
            neighbors = door_graph.get(room.room_id, set())
            if neighbors and neighbors <= {r.room_id for r in c.rooms if r.use in {"bedroom", "living", "habitable_room"}}:
                errors.append(f"HABITABLE_ROOM_ACCESS_ONLY_THROUGH_HABITABLE_ROOM:{room.room_id}")

    void_source_ids = {v.source_id for v in c.voids}
    if not void_source_ids <= source_ids:
        errors.append("VOID_WITHOUT_DAYLIGHT_SOURCE")
    for v in c.voids:
        if not v.counted_as_unallocatable_area or v.area_m2 <= 0:
            errors.append(f"VOID_NOT_COUNTED_IN_ALLOCATION:{v.source_id}")
        if not set(v.served_room_ids) <= room_ids:
            errors.append(f"VOID_SERVED_ROOM_GRAPH_INVALID:{v.source_id}")
    if abs(sum(v.area_m2 for v in c.voids) - c.allocation.lightwell_patio_void_area_m2) > 1e-6:
        errors.append("VOID_ALLOCATION_MISMATCH")
    if not c.allocation.balances:
        errors.append("ALLOCATION_DOES_NOT_BALANCE")
    if c.building_program_provenance is not ProvenanceClass.DESIGN_KNOWLEDGE_NON_AUTHORITATIVE:
        errors.append("BUILDING_PROGRAM_KNOWLEDGE_PROMOTED")
    if c.room_level_v2_geometry_generated:
        errors.append("ROOM_LEVEL_V2_GEOMETRY_FORBIDDEN_AT_CONTRACT_GATE")

    return {
        "status": "PASS" if not errors else "FAIL_CLOSED",
        "errors": tuple(sorted(set(errors))),
        "door_graph": {k: tuple(sorted(v)) for k, v in sorted(door_graph.items())},
        "served_room_graph": {v.source_id: tuple(sorted(v.served_room_ids)) for v in c.voids},
        "room_source_window_graph": tuple(sorted((w.room_id, w.source_id, w.window_id) for w in c.windows)),
        "ready_for_room_planning_v2": not errors,
        "room_level_v2_geometry_generated": False,
    }

