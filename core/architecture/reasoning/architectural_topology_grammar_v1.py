"""Topology-first architectural validation and functional proxy proofs."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from enum import Enum
from math import isclose
from typing import Iterable

from core.architecture.contracts.functional_space_ontology_v1 import Ownership, resolve_space_type


class EdgeType(str, Enum):
    OPEN_CONNECTION = "OPEN_CONNECTION"
    DOOR_CONNECTION = "DOOR_CONNECTION"
    COMMON_TO_PRIVATE_ENTRY = "COMMON_TO_PRIVATE_ENTRY"
    PUBLIC_TO_PRIVATE_TRANSITION = "PUBLIC_TO_PRIVATE_TRANSITION"
    SERVICE_ACCESS = "SERVICE_ACCESS"
    VEHICLE_ACCESS = "VEHICLE_ACCESS"
    VERTICAL_ACCESS = "VERTICAL_ACCESS"
    DAYLIGHT_BOUNDARY = "DAYLIGHT_BOUNDARY"


@dataclass(frozen=True)
class AccessEdge:
    a: str
    b: str
    edge_type: EdgeType
    intentional_transit: bool = False
    door_required: bool = False
    reason: str = ""

    def to_dict(self):
        value = asdict(self)
        value["edge_type"] = self.edge_type.value
        return value


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failures: tuple[str, ...]
    metrics: dict


NON_TRANSIT = {"BEDROOM", "MASTER_BEDROOM_SLEEPING", "ENSUITE", "FAMILY_BATHROOM", "GUEST_WC", "STORAGE_LINEN"}


def _dims(room):
    x0, y0, x1, y1 = room["rect"]
    return x1 - x0, y1 - y0


def _area(room):
    w, d = _dims(room)
    return w * d


def validate_access_graph(spaces: list[dict], edges: list[AccessEdge]) -> ValidationResult:
    by = {s["id"]: s for s in spaces}
    failures = []
    degree = Counter()
    graph = defaultdict(set)
    for edge in edges:
        if edge.a not in by or edge.b not in by:
            failures.append(f"EDGE_UNKNOWN_NODE:{edge.a}:{edge.b}")
            continue
        graph[edge.a].add(edge.b); graph[edge.b].add(edge.a)
        degree[edge.a] += 1; degree[edge.b] += 1
        sa, sb = by[edge.a], by[edge.b]
        if edge.edge_type == EdgeType.OPEN_CONNECTION and edge.door_required:
            failures.append(f"OPEN_CONNECTION_HAS_FAKE_DOOR:{edge.a}:{edge.b}")
        if edge.edge_type == EdgeType.COMMON_TO_PRIVATE_ENTRY:
            if sa["owner"] != "COMMON" and sb["owner"] != "COMMON":
                failures.append(f"UNIT_ENTRY_NOT_FROM_COMMON:{edge.a}:{edge.b}")
    for sid, count in degree.items():
        sem = by[sid]["semantic"]
        if sem in NON_TRANSIT and count > 1:
            intentional_terminal = all(not e.intentional_transit for e in edges if sid in {e.a, e.b})
            if not intentional_terminal:
                failures.append(f"FORBIDDEN_TRANSIT_NODE:{sid}:{sem}")
    for s in spaces:
        sem = s["semantic"]
        if sem == "PRIVATE_HALL_CORRIDOR" and degree[s["id"]] < 2:
            failures.append(f"CORRIDOR_DEAD_END_WITHOUT_DESTINATION:{s['id']}")
        if sem in {"STAIR", "ENTRANCE_SHOE_OFF"} and s.get("unsafe_fall_zone", False):
            failures.append(f"UNSAFE_STAIR_DOOR_FALL_ZONE:{s['id']}")
    return ValidationResult(not failures, tuple(sorted(set(failures))), {"node_count": len(spaces), "edge_count": len(edges), "degrees": dict(degree)})


def furniture_proxy(room: dict) -> dict:
    sem = room["semantic"]
    w, d = _dims(room); short, long = min(w, d), max(w, d)
    rule = resolve_space_type(sem).dimensions
    failures = []
    if short + 1e-6 < rule.clear_width_m:
        failures.append("MIN_CLEAR_DIMENSION")
    if _area(room) + 1e-6 < rule.area_range_m2[0]:
        failures.append("MIN_FUNCTIONAL_AREA")
    if sem in {"BEDROOM", "MASTER_BEDROOM_SLEEPING"}:
        bed_w = 1.6 if sem == "MASTER_BEDROOM_SLEEPING" else 1.0
        bed_d = 2.0; side = .6; foot = .7; wardrobe = .6
        if not ((w >= bed_w + side * 2 and d >= bed_d + foot + wardrobe) or (d >= bed_w + side * 2 and w >= bed_d + foot + wardrobe)):
            failures.append("BED_WARDROBE_CIRCULATION_NOT_FIT")
    elif sem == "LIVING_RECEPTION":
        if short < 3.2 or long < 4.5: failures.append("SOFA_AND_CIRCULATION_NOT_FIT")
    elif sem == "DINING":
        if short < 2.7: failures.append("DINING_TABLE_CLEARANCE_NOT_FIT")
    elif sem in {"OPEN_KITCHEN", "CLOSED_KITCHEN"}:
        if short < 2.4 or long < 3.0: failures.append("COUNTER_APPLIANCE_PASSAGE_NOT_FIT")
    elif sem in {"ENSUITE", "FAMILY_BATHROOM", "GUEST_WC"}:
        if short < rule.clear_width_m: failures.append("FIXTURE_DOOR_CLEARANCE_NOT_FIT")
    elif sem == "PARKING_BAY":
        if short < 2.4 or long < 4.8: failures.append("VEHICLE_RECTANGLE_NOT_FIT")
    elif sem == "TERRACE_BALCONY" and short < 1.5:
        failures.append("TERRACE_USABLE_DEPTH_NOT_FIT")
    return {"space_id": room["id"], "semantic": sem, "passed": not failures, "failures": failures,
            "proxy_zones": list(resolve_space_type(sem).furniture_zones), "dimensions_m": [w, d], "area_m2": round(_area(room), 3),
            "provenance": rule.provenance.value, "evidence_id": rule.evidence_id}


def detect_mechanical_grid(spaces: list[dict]) -> ValidationResult:
    occupied = [s for s in spaces if s["semantic"] not in {"LIGHTWELL_COURTYARD", "VEHICLE_MANEUVER_ZONE", "SHARED_ACCESS", "COMMON_ROOF"}]
    areas = [round(_area(s), 2) for s in occupied]
    shapes = [tuple(round(x, 2) for x in sorted(_dims(s))) for s in occupied]
    area_counts = Counter(areas); shape_counts = Counter(shapes)
    heterogeneous = defaultdict(set)
    for s, area in zip(occupied, areas): heterogeneous[area].add(s["semantic"])
    failures = []
    if occupied:
        repeated_shape = max(shape_counts.values(), default=0)
        if repeated_shape >= max(6, int(len(occupied) * .55)):
            failures.append("MECHANICAL_GRID_PACKING_DETECTED")
        spam = [a for a, sems in heterogeneous.items() if len(sems) >= 4 and area_counts[a] >= 5]
        if spam: failures.append("IDENTICAL_AREA_SPAM_ACROSS_UNRELATED_SPACE_TYPES")
    return ValidationResult(not failures, tuple(failures), {"area_histogram": dict(area_counts), "shape_histogram": {str(k): v for k, v in shape_counts.items()}})


def validate_composition(spaces: list[dict], edges: list[AccessEdge], required_levels=("G", "R1", "R2", "ROOF")) -> dict:
    failures = []
    levels = {s["level"] for s in spaces}
    for level in required_levels:
        if level not in levels: failures.append(f"MANDATORY_LEVEL_MISSING:{level}")
    graph = validate_access_graph(spaces, edges); failures.extend(graph.failures)
    grid = detect_mechanical_grid(spaces); failures.extend(grid.failures)
    proxies = [furniture_proxy(s) for s in spaces if s["semantic"] not in {"STAIR", "ELEVATOR_LOBBY", "LIGHTWELL_COURTYARD", "VEHICLE_MANEUVER_ZONE", "SHARED_ACCESS", "COMMON_ROOF", "PENTHOUSE_SERVICE_ENCLOSURE", "COMMON_CORRIDOR_LANDING", "PRIVATE_HALL_CORRIDOR", "ENTRANCE_SHOE_OFF", "COMMERCIAL_SHOP"}]
    failures.extend(f"FURNITURE_PROXY_FAIL:{p['space_id']}:{','.join(p['failures'])}" for p in proxies if not p["passed"])
    common = {"STAIR", "ELEVATOR_LOBBY", "COMMON_CORRIDOR_LANDING", "LIGHTWELL_COURTYARD", "PARKING_BAY", "VEHICLE_MANEUVER_ZONE", "SHARED_ACCESS", "COMMON_ROOF", "PENTHOUSE_SERVICE_ENCLOSURE"}
    for s in spaces:
        if s["semantic"] in common and s["owner"] != "COMMON": failures.append(f"COMMON_SPACE_ASSIGNED_PRIVATE:{s['id']}")
    doors = [e for e in edges if e.door_required]
    if len(doors) >= len(spaces) - 2: failures.append("AUTOMATIC_DOOR_ON_EVERY_SPACE")
    if not any(s["semantic"] == "VEHICLE_MANEUVER_ZONE" for s in spaces): failures.append("MANEUVER_ZONE_MISSING")
    for level in ("R1", "R2"):
        joints = [s for s in spaces if s["level"] == level and set(s.get("separation_joint_edges", [])) >= {"N", "E", "W"}]
        if not joints: failures.append(f"SEPARATION_JOINT_CONCEPT_MISSING:{level}")
    return {"passed": not failures, "failures": sorted(set(failures)), "access_graph": asdict(graph), "anti_grid": asdict(grid), "furniture_proxies": proxies,
            "status": "SOFTWARE ARCHITECTURAL READINESS: PASS / HUMAN ARCHITECTURAL ACCEPTANCE: PENDING" if not failures else "SOFTWARE TOPOLOGY PASS / ARCHITECTURAL COMPOSITION FAIL"}
