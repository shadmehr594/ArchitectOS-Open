"""Floor-aware program ownership and vertical-extent semantics."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import Polygon


@dataclass(frozen=True)
class OwnershipSpace:
    space_id: str
    floor_scope: tuple[str, ...]
    vertical_extent: str
    occupancy_role: str
    polygon: list
    exclusive_with: tuple[str, ...]
    may_overlap_with: tuple[str, ...]
    source_requirement: str

    def as_dict(self):
        return {"space_id": self.space_id, "floor_scope": list(self.floor_scope),
                "vertical_extent": self.vertical_extent, "occupancy_role": self.occupancy_role,
                "polygon": deepcopy(self.polygon), "exclusive_with": list(self.exclusive_with),
                "may_overlap_with": list(self.may_overlap_with),
                "source_requirement": self.source_requirement}


class FloorProgramSpatialOwnershipV1:
    """Authoritative, fail-closed ownership ledger for every generated floor."""
    # Generated contract coordinates are serialized at six decimals; this tolerance
    # absorbs only that deterministic round-trip noise (well below 0.01 cm2).
    EPS = 1e-5
    ROLES = frozenset(("PARKING_STALL", "VEHICLE_CIRCULATION", "VERTICAL_CORE", "STAIR",
        "ELEVATOR", "LOBBY", "PEDESTRIAN_ACCESS", "COMMON", "SERVICE", "COMMERCIAL",
        "RESIDENTIAL_UNIT", "DAYLIGHT_COURT", "TERRACE", "VOID", "UNALLOCATED"))
    NON_EXCLUSIVE = frozenset(("VERTICAL_CORE", "VOID", "UNALLOCATED"))

    def evaluate(self, floor_polygons: dict[str, list], spaces: Iterable[OwnershipSpace | dict]):
        records = [self._normalize(s) for s in spaces]
        failures = []
        for record in records:
            missing = [key for key in ("floor_scope", "vertical_extent", "occupancy_role",
                "exclusive_with", "may_overlap_with", "source_requirement") if key not in record or record[key] is None]
            if missing:
                failures.append(self._failure("ownership_metadata_missing", record["space_id"], details=missing))
            if record.get("occupancy_role") not in self.ROLES:
                failures.append(self._failure("unknown_occupancy_role", record["space_id"]))
            unknown = (set(record.get("exclusive_with", [])) | set(record.get("may_overlap_with", []))) - self.ROLES
            if unknown:
                failures.append(self._failure("ownership_policy_unknown_role", record["space_id"], details=sorted(unknown)))
            if set(record.get("exclusive_with", [])) & set(record.get("may_overlap_with", [])):
                failures.append(self._failure("ownership_policy_conflict", record["space_id"]))
            covered = set(record.get("exclusive_with", [])) | set(record.get("may_overlap_with", [])) | {record.get("occupancy_role")}
            if record.get("occupancy_role") in self.ROLES and covered != set(self.ROLES):
                failures.append(self._failure("ownership_policy_missing", record["space_id"],
                    details=sorted(set(self.ROLES)-covered)))
        for floor, boundary in floor_polygons.items():
            active = [r for r in records if floor in r.get("floor_scope", []) and r.get("polygon")]
            for index, left in enumerate(active):
                for right in active[index + 1:]:
                    overlap = Polygon(left["polygon"]).intersection(Polygon(right["polygon"])).area
                    if overlap <= self.EPS:
                        continue
                    if self._overlap_allowed(left, right):
                        continue
                    code = "double_ownership_overlap" if left["occupancy_role"] not in self.NON_EXCLUSIVE and right["occupancy_role"] not in self.NON_EXCLUSIVE else "ownership_overlap_not_explicitly_allowed"
                    failures.append(self._failure(code, left["space_id"], right["space_id"], floor, overlap))
            boundary_poly = Polygon(boundary)
            occupied = [Polygon(r["polygon"]) for r in active if r["occupancy_role"] not in self.NON_EXCLUSIVE]
            union = occupied[0] if occupied else Polygon()
            for shape in occupied[1:]:
                union = union.union(shape)
            outside = union.difference(boundary_poly).area
            if outside > self.EPS:
                failures.append(self._failure("ownership_outside_floor_boundary", floor, overlap=outside))
        failures.extend(self._vertical_continuity_failures(records))
        accounting = self._accounting(floor_polygons, records)
        for floor, item in accounting.items():
            if not item["balanced"]:
                failures.append(self._failure("residual_accounting_mismatch", floor,
                    details=[item["computed_unallocated_area"], item["declared_unallocated_area"]]))
        return {"contract": "FloorProgramSpatialOwnershipV1", "policy": "explicit_allowlist_fail_closed",
                "spaces": records, "floors": self._by_floor(floor_polygons, records),
                "area_accounting": accounting, "hard_failures": failures,
                "hard_failure_codes": list(dict.fromkeys(f["code"] for f in failures)),
                "hard_validation_status": "hard_valid" if not failures else "not_feasible"}

    def _vertical_continuity_failures(self, records):
        failures = []
        for role in ("VERTICAL_CORE", "STAIR", "ELEVATOR", "LOBBY"):
            members = [r for r in records if r["occupancy_role"] == role]
            for member in members:
                if len(member["floor_scope"]) < 2 or not member["vertical_extent"].startswith("CONTINUOUS:"):
                    failures.append(self._failure("vertical_continuity_missing", member["space_id"], details=[role]))
        return failures

    def _accounting(self, floor_polygons, records):
        result = {}
        for floor, boundary in floor_polygons.items():
            boundary_poly = Polygon(boundary)
            active = [r for r in records if floor in r["floor_scope"] and r["polygon"]]
            allocation = [Polygon(r["polygon"]) for r in active if r["occupancy_role"] not in ("VERTICAL_CORE", "UNALLOCATED")]
            union = allocation[0] if allocation else Polygon()
            for shape in allocation[1:]: union = union.union(shape)
            unallocated = boundary_poly.difference(union).area
            declared = sum(Polygon(r["polygon"]).area for r in active if r["occupancy_role"] == "UNALLOCATED")
            result[floor] = {"floor_area": round(boundary_poly.area, 8), "allocated_union_area": round(union.intersection(boundary_poly).area, 8),
                "computed_unallocated_area": round(unallocated, 8), "declared_unallocated_area": round(declared, 8),
                "balanced": abs(unallocated-declared) <= self.EPS}
            if not result[floor]["balanced"]:
                result[floor]["status"] = "residual_mismatch"
            else:
                result[floor]["status"] = "balanced"
        return result

    @staticmethod
    def _overlap_allowed(left, right):
        a, b = left["occupancy_role"], right["occupancy_role"]
        return b in left["may_overlap_with"] and a in right["may_overlap_with"]

    @staticmethod
    def _by_floor(floor_polygons, records):
        return {floor: [r["space_id"] for r in records if floor in r["floor_scope"]] for floor in floor_polygons}

    @staticmethod
    def _normalize(space):
        return space.as_dict() if isinstance(space, OwnershipSpace) else deepcopy(space)

    @staticmethod
    def _failure(code, left, right=None, floor=None, overlap=0, details=None):
        value = {"code": code, "left_space_id": left}
        if right is not None: value["right_space_id"] = right
        if floor is not None: value["floor"] = floor
        if overlap: value["overlap_area"] = round(overlap, 8)
        if details: value["details"] = details
        return value
