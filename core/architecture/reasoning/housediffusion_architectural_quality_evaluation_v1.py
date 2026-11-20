"""HouseDiffusionArchitecturalQualityEvaluationV1 — HOUSE-DIFFUSION-CONDITIONING-QUALITY-AUDIT-02A1.

A READ-ONLY evaluator for a raw ``SemanticPlanCandidateV2``.

It MEASURES and CLASSIFIES only.  It never:

* moves, resizes, merges or splits a polygon
* swaps or relabels rooms
* invents doors, corridors or adjacency
* repairs access
* "fixes" poor geometry

Zoning is evaluated TOPOLOGICALLY (adjacency + door graph), never by compass
direction: no north/south/front/rear assumption is made, because no site
evidence exists in the candidate.

Verdict: ``PASS`` / ``REJECT`` / ``INDETERMINATE`` plus explicit reason codes.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import itertools
from typing import Any

from shapely.geometry import Polygon


CONTRACT = "HouseDiffusionArchitecturalQualityEvaluationV1"
VERSION = "1.0"

EXTERIOR = "EXTERIOR"

#: Topological zones (no compass semantics).
PUBLIC_ZONE = ("UNIT_ENTRY", "LIVING_RECEPTION", "GUEST_WC")
SERVICE_ZONE = ("CLOSED_KITCHEN",)
PRIVATE_ZONE = ("MASTER_BEDROOM_SLEEPING", "BEDROOM_DOUBLE", "FAMILY_BATHROOM")
EXTERNAL_ZONE = ("TERRACE_BALCONY",)

#: Rooms that must be enclosed and therefore reachable through explicit doors.
ENCLOSED_REQUIRED = PUBLIC_ZONE + SERVICE_ZONE + PRIVATE_ZONE

#: The program used by HOUSE-DIFFUSION-PRODUCTION-PATH-02A (target areas).
DEFAULT_PROGRAM_TARGET_AREAS = {
    "UNIT_ENTRY": 5.0,
    "LIVING_RECEPTION": 24.0,
    "CLOSED_KITCHEN": 10.0,
    "MASTER_BEDROOM_SLEEPING": 20.0,
    "BEDROOM_DOUBLE": 14.0,
    "FAMILY_BATHROOM": 6.0,
    "GUEST_WC": 4.0,
    "TERRACE_BALCONY": 8.0,
}

#: Adjacency tolerance = factor x the candidate's OWN measured minimum gap.
ADJACENCY_TOLERANCE_FACTOR = 3.0

#: Documented proportional band: generated share vs target share.
AREA_SHARE_LOWER_BOUND = 0.5
AREA_SHARE_UPPER_BOUND = 2.0

#: Reason codes.
R_POLYGON_INVALID = "GEOMETRY_INVALID_POLYGON"
R_OVERLAP = "GEOMETRY_OVERLAP"
R_DETACHED = "GEOMETRY_DETACHED_SPACE"
R_MISSING_REQUIRED = "PROGRAM_MISSING_REQUIRED_IDENTITY"
R_DUPLICATE = "PROGRAM_DUPLICATE_SPACE"
R_AREA_UNDERSIZED = "PROGRAM_AREA_UNDERSIZED"
R_AREA_OVERSIZED = "PROGRAM_AREA_OVERSIZED"
R_AREA_METRIC_UNSUPPORTED = "PROGRAM_METRIC_AREA_UNSUPPORTED"
R_KITCHEN_LIVING = "RELATION_KITCHEN_NOT_ADJACENT_TO_LIVING"
R_ENTRY_LIVING = "RELATION_ENTRY_NOT_ADJACENT_TO_LIVING"
R_BATH_PRIVATE = "RELATION_FAMILY_BATHROOM_NOT_IN_PRIVATE_ZONE"
R_WC_PUBLIC = "RELATION_GUEST_WC_NOT_IN_PUBLIC_ZONE"
R_ACCESS_UNREACHABLE = "ACCESS_ROOM_UNREACHABLE_FROM_EXPLICIT_DOORS"
R_ACCESS_NO_DOOR = "ACCESS_NO_EXPLICIT_DOOR"
R_ZONE_MASTER = "ZONING_MASTER_NOT_IN_PRIVATE_CLUSTER"
R_ZONE_CLUSTER = "ZONING_PRIVATE_CLUSTER_DISCONNECTED"
R_ZONE_MIXING = "ZONING_EXCESSIVE_PUBLIC_PRIVATE_MIXING"

HARD_CODES = frozenset({
    R_POLYGON_INVALID, R_OVERLAP, R_DETACHED, R_MISSING_REQUIRED,
    R_KITCHEN_LIVING, R_ENTRY_LIVING, R_BATH_PRIVATE, R_WC_PUBLIC,
    R_ACCESS_UNREACHABLE, R_ACCESS_NO_DOOR, R_ZONE_MASTER, R_ZONE_CLUSTER,
    R_ZONE_MIXING,
})


def _polygon(value: Any) -> Polygon | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    ring: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, Sequence) or len(point) < 2:
            return None
        try:
            ring.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    if len(ring) < 4:
        return None
    try:
        polygon = Polygon(ring)
    except Exception:  # pragma: no cover - defensive
        return None
    return None if polygon.is_empty else polygon


def _zone_of(identity: str) -> str:
    if identity in PUBLIC_ZONE:
        return "PUBLIC"
    if identity in SERVICE_ZONE:
        return "SERVICE"
    if identity in PRIVATE_ZONE:
        return "PRIVATE"
    if identity in EXTERNAL_ZONE:
        return "EXTERNAL"
    return "UNCLASSIFIED"


class HouseDiffusionArchitecturalQualityEvaluationV1:
    """Measure a raw HouseDiffusion candidate against architectural gates."""

    VERSION = VERSION

    def evaluate(self, candidate: Mapping[str, Any], *,
                 program_target_areas: Mapping[str, float] | None = None,
                 ) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate must be a mapping")

        targets = dict(program_target_areas or DEFAULT_PROGRAM_TARGET_AREAS)
        spaces = list(candidate.get("spaces") or [])
        identities = [str(s.get("architectos_identity")) for s in spaces]
        polygons: dict[str, Polygon] = {}
        for space in spaces:
            polygon = _polygon(space.get("polygon"))
            if polygon is not None:
                polygons[str(space.get("architectos_identity"))] = polygon

        reasons: list[dict[str, Any]] = []
        measurements: dict[str, Any] = {}

        # ---------------- GEOMETRY ----------------
        invalid = [i for i in identities if i not in polygons]
        if invalid:
            reasons.append({"code": R_POLYGON_INVALID, "spaces": sorted(set(invalid))})

        overlap_pairs = []
        total_overlap = 0.0
        for a, b in itertools.combinations(sorted(polygons), 2):
            area = float(polygons[a].intersection(polygons[b]).area)
            if area > 1e-9:
                overlap_pairs.append({"a": a, "b": b, "area": round(area, 9)})
                total_overlap += area
        measurements["overlap_total"] = round(total_overlap, 9)
        measurements["overlap_pairs"] = overlap_pairs
        if overlap_pairs:
            reasons.append({"code": R_OVERLAP, "pairs": overlap_pairs})

        gap = self._measured_gap(polygons)
        tolerance = gap * ADJACENCY_TOLERANCE_FACTOR if gap else 1e-9
        adjacency = self._adjacency(polygons, tolerance)
        components = self._components(polygons, adjacency)

        detached = sorted(set(identities) - self._largest_component(polygons, adjacency))
        measurements["measured_symbolic_gap"] = gap
        measurements["adjacency_tolerance"] = round(tolerance, 9)
        measurements["components"] = len(components)
        measurements["detached_spaces"] = detached
        if detached:
            reasons.append({"code": R_DETACHED, "spaces": detached})

        # ---------------- PROGRAM ----------------
        duplicates = sorted({i for i in identities if identities.count(i) > 1})
        missing = sorted({i for i in targets if i not in identities})
        if duplicates:
            reasons.append({"code": R_DUPLICATE, "spaces": duplicates})
        if missing:
            reasons.append({"code": R_MISSING_REQUIRED, "spaces": missing})

        areas = {i: float(p.area) for i, p in polygons.items()}
        total_area = sum(areas.values())
        target_total = sum(targets.values())
        area_rows = []
        undersized, oversized = [], []
        for identity in sorted(targets):
            if identity not in areas:
                continue
            generated_share = areas[identity] / total_area if total_area else 0.0
            target_share = targets[identity] / target_total if target_total else 0.0
            ratio = (generated_share / target_share) if target_share else None
            polygon = polygons[identity]
            min_x, min_y, max_x, max_y = polygon.bounds
            width, depth = max_x - min_x, max_y - min_y
            min_dimension = min(width, depth)
            row = {
                "identity": identity,
                "zone": _zone_of(identity),
                "area_normalized": round(areas[identity], 6),
                "generated_share": round(generated_share, 6),
                "target_area": targets[identity],
                "target_share": round(target_share, 6),
                "share_ratio": round(ratio, 4) if ratio is not None else None,
                "bbox_width": round(width, 6),
                "bbox_depth": round(depth, 6),
                "min_dimension": round(min_dimension, 6),
                "aspect_ratio": round(max(width, depth) / max(1e-9, min_dimension), 4),
                "metric_area_supported": False,
            }
            area_rows.append(row)
            if ratio is not None and ratio < AREA_SHARE_LOWER_BOUND:
                undersized.append(identity)
            if ratio is not None and ratio > AREA_SHARE_UPPER_BOUND:
                oversized.append(identity)
        measurements["area_rows"] = area_rows
        measurements["area_share_lower_bound"] = AREA_SHARE_LOWER_BOUND
        measurements["area_share_upper_bound"] = AREA_SHARE_UPPER_BOUND
        measurements["area_proportional_basis"] = (
            "share of total generated room area vs share of total target area. "
            "The model has NO metric scale channel, so m2 comparison is UNSUPPORTED.")
        if undersized:
            reasons.append({"code": R_AREA_UNDERSIZED, "spaces": undersized})
        if oversized:
            reasons.append({"code": R_AREA_OVERSIZED, "spaces": oversized})

        # ---------------- ACCESS (explicit doors only) ----------------
        access = self._access(identities, candidate.get("doors") or [])
        measurements["access"] = access
        if not access["has_any_door"]:
            reasons.append({"code": R_ACCESS_NO_DOOR})
        unreachable_enclosed = sorted(
            set(access["unreachable"]) & set(ENCLOSED_REQUIRED))
        if unreachable_enclosed:
            reasons.append({"code": R_ACCESS_UNREACHABLE, "spaces": unreachable_enclosed})

        # ---------------- RELATIONSHIPS ----------------
        # A relation counts as satisfied when the rooms are geometrically adjacent
        # OR are joined by an EXPLICIT generated door.  Both are measured; neither
        # is inferred from proximity alone.
        door_pairs = {frozenset((e["a"], e["b"])) for e in access["edges"]}

        def related(a: str, b: str) -> bool:
            return self._adjacent(a, b, adjacency) or frozenset((a, b)) in door_pairs

        relation_results = {}
        relation_results["kitchen_living_adjacent"] = related(
            "CLOSED_KITCHEN", "LIVING_RECEPTION")
        relation_results["entry_living_adjacent"] = related(
            "UNIT_ENTRY", "LIVING_RECEPTION")
        relation_results["family_bathroom_in_private_zone"] = any(
            related("FAMILY_BATHROOM", other)
            for other in PRIVATE_ZONE if other != "FAMILY_BATHROOM")
        relation_results["guest_wc_in_public_zone"] = any(
            related("GUEST_WC", other)
            for other in PUBLIC_ZONE if other != "GUEST_WC")
        relation_results["basis"] = (
            "geometric adjacency within tolerance OR an explicit generated door; "
            "no proximity-only inference")
        measurements["relations"] = relation_results
        if not relation_results["kitchen_living_adjacent"]:
            reasons.append({"code": R_KITCHEN_LIVING})
        if not relation_results["entry_living_adjacent"]:
            reasons.append({"code": R_ENTRY_LIVING})
        if not relation_results["family_bathroom_in_private_zone"]:
            reasons.append({"code": R_BATH_PRIVATE})
        if not relation_results["guest_wc_in_public_zone"]:
            reasons.append({"code": R_WC_PUBLIC})

        # ---------------- ZONING (topological) ----------------
        zoning = self._zoning(polygons, adjacency, access, door_pairs)
        measurements["zoning"] = zoning
        if not zoning["master_in_private_cluster"]:
            reasons.append({"code": R_ZONE_MASTER,
                            "detail": zoning["master_neighbours"]})
        if not zoning["private_cluster_connected"]:
            reasons.append({"code": R_ZONE_CLUSTER})
        if zoning["excessive_mixing"]:
            reasons.append({"code": R_ZONE_MIXING, "detail": zoning["mixing_detail"]})

        # ---------------- verdict ----------------
        hard = [r for r in reasons if r["code"] in HARD_CODES]
        soft = [r for r in reasons if r["code"] not in HARD_CODES]
        verdict = "REJECT" if hard else ("INDETERMINATE" if soft else "PASS")

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "candidate_id": candidate.get("candidate_id"),
            "source_seed": candidate.get("source_seed"),
            "source_engine": candidate.get("source_engine"),
            "verdict": verdict,
            "hard_failures": [r["code"] for r in hard],
            "soft_findings": [r["code"] for r in soft],
            "reason_codes": [r["code"] for r in reasons],
            "reasons": reasons,
            "measurements": measurements,
            "read_only": True,
            "geometry_altered": False,
        }

    # ------------------------------------------------------------------
    # measurement helpers (no mutation)
    # ------------------------------------------------------------------

    @staticmethod
    def _measured_gap(polygons: Mapping[str, Polygon]) -> float:
        distances = []
        for a, b in itertools.combinations(sorted(polygons), 2):
            distance = float(polygons[a].distance(polygons[b]))
            if distance > 0:
                distances.append(round(distance, 9))
        return min(distances) if distances else 0.0

    @staticmethod
    def _adjacency(polygons: Mapping[str, Polygon], tolerance: float) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {name: set() for name in polygons}
        for a, b in itertools.combinations(sorted(polygons), 2):
            if float(polygons[a].distance(polygons[b])) <= tolerance:
                adjacency[a].add(b)
                adjacency[b].add(a)
        return adjacency

    @staticmethod
    def _adjacent(a: str, b: str, adjacency: Mapping[str, set[str]]) -> bool:
        return b in adjacency.get(a, set())

    @staticmethod
    def _components(polygons: Mapping[str, Polygon],
                    adjacency: Mapping[str, set[str]]) -> list[list[str]]:
        seen: set[str] = set()
        components: list[list[str]] = []
        for name in sorted(polygons):
            if name in seen:
                continue
            stack, group = [name], []
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                group.append(node)
                stack.extend(adjacency.get(node, ()))
            components.append(sorted(group))
        return components

    @classmethod
    def _largest_component(cls, polygons: Mapping[str, Polygon],
                           adjacency: Mapping[str, set[str]]) -> set[str]:
        components = cls._components(polygons, adjacency)
        if not components:
            return set()
        return set(max(components, key=len))

    @staticmethod
    def _access(identities: Sequence[str],
                doors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        nodes = sorted(set(identities) | {EXTERIOR})
        adjacency: dict[str, set[str]] = {node: set() for node in nodes}
        edges = []
        known = set(identities)
        for door in doors:
            if not isinstance(door, Mapping):
                continue
            sides = [str(s) for s in (door.get("between_identities") or [])
                     if str(s) in known]
            if str(door.get("door_type")).upper() == "FRONT":
                a, b = (sides[0] if sides else None), EXTERIOR
            else:
                a = sides[0] if len(sides) > 0 else None
                b = sides[1] if len(sides) > 1 else None
            if not a or not b or a == b:
                continue
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
            edges.append({"opening_id": door.get("door_id"), "a": a, "b": b})

        reachable: set[str] = set()
        stack = [EXTERIOR]
        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)
            stack.extend(adjacency.get(node, ()))

        return {
            "has_any_door": bool(edges),
            "door_count": len(edges),
            "edges": edges,
            "reachable_from_exterior": sorted(reachable - {EXTERIOR}),
            "unreachable": sorted(set(identities) - reachable),
            "proximity_inference_used": False,
        }

    @staticmethod
    def _zoning(polygons: Mapping[str, Polygon],
                adjacency: Mapping[str, set[str]],
                access: Mapping[str, Any],
                door_pairs: set[frozenset[str]]) -> dict[str, Any]:
        master = "MASTER_BEDROOM_SLEEPING"

        def connected(a: str, b: str) -> bool:
            return b in adjacency.get(a, set()) or frozenset((a, b)) in door_pairs

        master_neighbours = sorted(
            {n for n in polygons if n != master and connected(master, n)})
        master_in_cluster = any(n in PRIVATE_ZONE for n in master_neighbours)

        present_private = [i for i in PRIVATE_ZONE if i in polygons]
        cluster_connected = False
        if len(present_private) <= 1:
            cluster_connected = bool(present_private)
        else:
            seen: set[str] = set()
            stack = [present_private[0]]
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(n for n in present_private
                             if n not in seen and connected(node, n))
            cluster_connected = set(present_private) <= seen

        # excessive mixing: a PRIVATE room directly connected to the entry or the
        # guest WC (public wet/entry rooms) is the observable public/private defect
        mixing = []
        for private in PRIVATE_ZONE:
            if private not in polygons:
                continue
            for public in ("UNIT_ENTRY", "GUEST_WC"):
                if public in polygons and connected(private, public):
                    mixing.append({"private": private, "public": public})

        return {
            "master_neighbours": master_neighbours,
            "master_zone": "PRIVATE" if master_in_cluster else "PUBLIC_OR_SERVICE",
            "master_in_private_cluster": master_in_cluster,
            "private_cluster_connected": cluster_connected,
            "excessive_mixing": bool(mixing),
            "mixing_detail": mixing,
            "basis": ("TOPOLOGICAL connectivity (adjacency or explicit door) only; "
                      "no compass/site assumption"),
            "public_zone": list(PUBLIC_ZONE),
            "service_zone": list(SERVICE_ZONE),
            "private_zone": list(PRIVATE_ZONE),
        }


housediffusion_architectural_quality_evaluation = (
    HouseDiffusionArchitecturalQualityEvaluationV1())


def evaluate_candidate(candidate: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return HouseDiffusionArchitecturalQualityEvaluationV1().evaluate(candidate, **kwargs)


__all__ = [
    "CONTRACT", "VERSION", "EXTERIOR",
    "PUBLIC_ZONE", "SERVICE_ZONE", "PRIVATE_ZONE", "EXTERNAL_ZONE",
    "ENCLOSED_REQUIRED", "DEFAULT_PROGRAM_TARGET_AREAS",
    "ADJACENCY_TOLERANCE_FACTOR", "AREA_SHARE_LOWER_BOUND", "AREA_SHARE_UPPER_BOUND",
    "HouseDiffusionArchitecturalQualityEvaluationV1",
    "housediffusion_architectural_quality_evaluation", "evaluate_candidate",
]
