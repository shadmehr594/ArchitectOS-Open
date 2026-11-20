"""Architecture-only spatial reservation and exclusivity gate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import Polygon


@dataclass(frozen=True)
class ReservationZone:
    zone_id: str
    function: str
    floor: str
    polygon: list
    vertical_floors: tuple[str, ...] = ()
    source: str = "generated_geometry"

    def as_dict(self):
        return {"zone_id": self.zone_id, "function": self.function, "floor": self.floor,
                "polygon": deepcopy(self.polygon), "vertical_floors": list(self.vertical_floors),
                "source": self.source}


class SpatialReservationExclusivityV1:
    """Reject incompatible occupied/reserved zones before architectural scoring."""
    EPS = 1e-7
    INCOMPATIBLE = {
        frozenset(("stair", "parking_stall")): "stair_overlaps_parking_stall",
        frozenset(("vertical_core", "parking_stall")): "core_overlaps_parking_stall",
        frozenset(("elevator", "parking_stall")): "elevator_overlaps_parking_stall",
        frozenset(("stair", "vehicle_circulation")): "stair_overlaps_vehicle_circulation",
        frozenset(("vertical_core", "vehicle_circulation")): "core_overlaps_vehicle_circulation",
        frozenset(("elevator", "vehicle_circulation")): "elevator_overlaps_vehicle_circulation",
        frozenset(("daylight_court", "stair")): "daylight_court_overlaps_stair",
        frozenset(("daylight_court", "vertical_core")): "daylight_court_overlaps_core",
        frozenset(("daylight_court", "elevator")): "daylight_court_overlaps_elevator",
        frozenset(("daylight_court", "lobby")): "daylight_court_overlaps_lobby",
        frozenset(("pedestrian_path", "parking_stall")): "pedestrian_path_overlaps_parking_stall",
        frozenset(("pedestrian_path", "vehicle_circulation")): "pedestrian_path_overlaps_vehicle_circulation",
    }

    def evaluate(self, zones: Iterable[ReservationZone | dict]):
        normalized = [self._normalize(z) for z in zones if self._polygon(z)]
        collisions = []
        for index, left in enumerate(normalized):
            for right in normalized[index + 1:]:
                code = self.INCOMPATIBLE.get(frozenset((left["function"], right["function"])))
                if not code:
                    continue
                shared = sorted(set(left["vertical_floors"]) & set(right["vertical_floors"]))
                same_floor = left["floor"] == right["floor"]
                if not same_floor and not shared:
                    continue
                overlap = Polygon(left["polygon"]).intersection(Polygon(right["polygon"])).area
                if overlap <= self.EPS:
                    continue
                collisions.append({"code": code, "left_zone_id": left["zone_id"],
                    "right_zone_id": right["zone_id"], "overlap_area": round(overlap, 8),
                    "collision_scope": "same_floor" if same_floor else "cross_floor_vertical",
                    "affected_floors": [left["floor"]] if same_floor else shared})
        return {"contract": "SpatialReservationExclusivityV1",
                "compatibility_policy": "explicit_incompatibility_fail_closed_for_declared_zones",
                "gate_position": "before_scoring", "zones": normalized, "collisions": collisions,
                "hard_failure_codes": list(dict.fromkeys(c["code"] for c in collisions)),
                "hard_validation_status": "hard_valid" if not collisions else "not_feasible"}

    @staticmethod
    def _polygon(zone):
        return zone.polygon if isinstance(zone, ReservationZone) else zone.get("polygon", [])

    @staticmethod
    def _normalize(zone):
        data = zone.as_dict() if isinstance(zone, ReservationZone) else deepcopy(zone)
        data.setdefault("vertical_floors", [])
        data.setdefault("source", "generated_geometry")
        return data
