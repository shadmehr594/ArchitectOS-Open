"""GeneratedBaselineRealizationV1 — HOUSE-DIFFUSION-PRODUCTION-PATH-02A.

The SMALLEST generic, deterministic, NON-DESIGNING realization layer that turns a
FRESH HouseDiffusion generation (``SemanticPlanCandidateV2``) into
``GeneratedArchitecturalBaselineV1``.

THIS IS NOT A DESIGN ENGINE.

It may only DERIVE and NORMALIZE what the source candidate actually supports:

    DERIVED  room polygons / identities / areas (copied verbatim from the candidate)
    DERIVED  symbolic wall centrelines from room-boundary adjacency
    DERIVED  opening host binding by geometric proximity of a SOURCE door segment
    DERIVED  access graph by BFS over EXPLICIT source doors only
    PRESERVED the candidate's own floor envelope

It never:

* redesigns, relocates, merges or splits a room
* improves adjacency or synthesizes a replacement plan
* invents wall thickness (symbolic bands stay ``WALL_THICKNESS_METRIC_UNRESOLVED``,
  ``construction_claim = false``; no 0.2 m / 0.3 m is ever assigned)
* invents doors or windows
* infers access from proximity alone
* invents site orientation, vertical circulation or structure
* invokes the internal ArchitectOS layout generator

Missing evidence is reported as ``UNRESOLVED`` / ``NOT_PROVIDED`` rather than
fabricated.

The historical bespoke chain (architectural_refinement_01 derive_01b..01f, the
hand-tuned wall/opening and access stages, the hand-selected window stages) is
NOT used: those are PLAN-SPECIFIC_HARDCODE / DESIGN_DECISION and are excluded by
contract.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import itertools
import json
from typing import Any

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from core.architecture.contracts.generated_architectural_baseline_v1 import (
    BASELINE_ORIGIN_GENERATED,
    CONTRACT,
    GENERATION_POLICY,
    REALIZATION_CONTRACT,
    SOURCE_CANDIDATE_SCHEMA,
    SOURCE_ENGINE_HOUSE_DIFFUSION,
    VERSION,
    WALL_THICKNESS_METRIC_UNRESOLVED,
    WINDOW_STATUS_NOT_PROVIDED,
    generated_baseline_sha256,
)


CONTRACT_NAME = REALIZATION_CONTRACT
REALIZATION_VERSION = "1.0"

EXTERIOR = "EXTERIOR"

#: Adjacency tolerance is MEASURED from the candidate, never hard-coded.
ADJACENCY_TOLERANCE_FACTOR = 1.5

NATIVE_DOOR_TYPES = {"T17": "NATIVE_INTERIOR_DOOR", "T15": "NATIVE_FRONT_DOOR"}


def _round(value: float, digits: int = 9) -> float:
    return round(float(value), digits)


def _ring(value: Any) -> list[list[float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    ring: list[list[float]] = []
    for point in value:
        if not isinstance(point, Sequence) or len(point) < 2:
            return []
        try:
            ring.append([_round(point[0]), _round(point[1])])
        except (TypeError, ValueError):
            return []
    return ring


def _polygon(value: Any) -> Polygon | None:
    ring = _ring(value)
    if len(ring) < 4:
        return None
    try:
        polygon = Polygon(ring)
    except Exception:  # pragma: no cover - defensive
        return None
    return None if polygon.is_empty else polygon


def _geometry_sha256(polygon: Polygon) -> str:
    payload = [[_round(x), _round(y)] for x, y in polygon.exterior.coords]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def _canonical_candidate_sha256(candidate: Mapping[str, Any]) -> str:
    def norm(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): norm(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [norm(v) for v in value]
        return value

    return hashlib.sha256(
        json.dumps(norm(candidate), ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()


def _line_parts(geometry: Any) -> list[list[list[float]]]:
    """Extract straight segment(s) as [[x1,y1],[x2,y2]] from a shapely geometry."""
    if geometry is None or geometry.is_empty:
        return []
    kind = geometry.geom_type
    if kind == "LineString":
        coords = list(geometry.coords)
        return [[[_round(coords[0][0]), _round(coords[0][1])],
                 [_round(coords[-1][0]), _round(coords[-1][1])]]]
    if kind in ("MultiLineString", "GeometryCollection"):
        parts: list[list[list[float]]] = []
        for part in geometry.geoms:
            parts.extend(_line_parts(part))
        return parts
    return []


class GeneratedBaselineRealizationV1:
    """Realize a fresh HouseDiffusion candidate into a generated baseline."""

    VERSION = REALIZATION_VERSION

    # ------------------------------------------------------------------
    # public entry
    # ------------------------------------------------------------------

    def realize(self, candidate: Mapping[str, Any], *,
                candidate_path: str | None = None) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate must be a mapping")
        if candidate.get("source_engine") != SOURCE_ENGINE_HOUSE_DIFFUSION:
            raise ValueError(
                "GeneratedBaselineRealizationV1 only realizes HOUSE_DIFFUSION output; "
                f"got source_engine={candidate.get('source_engine')!r}")
        schema = candidate.get("schema")
        if schema != SOURCE_CANDIDATE_SCHEMA:
            raise ValueError(
                f"unsupported source candidate schema {schema!r}; "
                f"expected {SOURCE_CANDIDATE_SCHEMA}")

        spaces = self._spaces(candidate)
        if not spaces:
            raise ValueError("candidate has no rooms to realize")

        floor_id = self._floor_id(spaces)
        gap = self._measured_gap(spaces)
        polygons = {item["space_id"]: _polygon(item["polygon"]) for item in spaces}

        envelope, envelope_source = self._envelope(candidate, polygons)
        walls, wall_unresolved = self._walls(spaces, polygons, gap)
        openings, opening_unresolved = self._openings(candidate, spaces, walls, gap)
        windows, window_status = self._windows(candidate)
        circulation = self._circulation(candidate)
        access = self._access_graph(spaces, openings, walls)

        unresolved: list[dict[str, Any]] = []
        unresolved.extend(wall_unresolved)
        unresolved.extend(opening_unresolved)
        unresolved.extend(access.get("unresolved") or [])

        bridge = envelope.get("minimal_bridge_distance")
        if bridge and gap and bridge > gap * ADJACENCY_TOLERANCE_FACTOR:
            unresolved.append({
                "classification": "GENERATION_GEOMETRY_FINDING",
                "code": "FLOOR_FOOTPRINT_CLOSED_ACROSS_DETACHED_ROOM",
                "detail": (
                    f"the source generation places at least one room detached from the "
                    f"rest of the plan: the minimal bridge is {bridge} against a measured "
                    f"wall gap of {gap}. The floor footprint was closed across that "
                    f"distance so the plate is expressible as a single polygon. No room "
                    f"was moved, resized or invented."),
                "minimal_bridge_distance": bridge,
                "measured_symbolic_gap": gap,
            })

        unresolved.append({
            "classification": "MISSING_CANONICAL_EVIDENCE",
            "code": WALL_THICKNESS_METRIC_UNRESOLVED,
            "detail": ("HouseDiffusion supplies room polygons and symbolic boundary "
                       "adjacency only; no metric wall thickness exists"),
        })
        unresolved.append({
            "classification": "NON_BLOCKING_FUTURE_RECHECK",
            "code": WINDOW_STATUS_NOT_PROVIDED,
            "detail": "the source candidate provides no window evidence",
        })
        unresolved.append({
            "classification": "NON_BLOCKING_FUTURE_RECHECK",
            "code": "WORLD_ORIENTATION_PENDING",
            "detail": "no world orientation exists in the source candidate",
        })
        unresolved.append({
            "classification": "NON_BLOCKING_FUTURE_RECHECK",
            "code": "PARCEL_SITE_CONTEXT_PENDING",
            "detail": "no parcel/site context exists in the source candidate",
        })

        floor_document = {
            "floor_id": floor_id,
            "envelope": envelope,
            "spaces": spaces,
            "wall_band_rule": {
                "wall_band_type": "SYMBOLIC_RELATIVE",
                "metric_thickness": "UNKNOWN",
                "status": WALL_THICKNESS_METRIC_UNRESOLVED,
                "construction_claim": False,
                "source": "ARCHITECTOS_DERIVED",
                "derivation": "measured inter-room gap; symbolic only",
            },
            "walls": walls,
            "openings": openings,
            "windows": windows,
            "window_status": window_status,
            "circulation": circulation,
            "unresolved": deepcopy(unresolved),
        }

        document: dict[str, Any] = {
            "schema": CONTRACT,
            "contract_version": VERSION,
            "baseline_origin": BASELINE_ORIGIN_GENERATED,
            "source_engine": SOURCE_ENGINE_HOUSE_DIFFUSION,
            "source_candidate_schema": SOURCE_CANDIDATE_SCHEMA,
            "source_candidate_id": candidate.get("candidate_id"),
            "source_candidate_sha256": _canonical_candidate_sha256(candidate),
            "source_candidate_path": candidate_path,
            "generation_seed": candidate.get("source_seed"),
            "realization_contract": REALIZATION_CONTRACT,
            "realization_version": REALIZATION_VERSION,
            "generation_policy": GENERATION_POLICY,
            "generator_lineage": {
                "primary_plan_generator": "HouseDiffusion",
                "generation_policy": GENERATION_POLICY,
                "source_engine": candidate.get("source_engine"),
                "source_seed": candidate.get("source_seed"),
                "source_candidate_id": candidate.get("candidate_id"),
                "source_counters": deepcopy(candidate.get("counters")),
                "source_generation_metrics": deepcopy(candidate.get("generation_metrics")),
                "source_fallback": deepcopy(candidate.get("fallback")),
                "internal_generator_used": False,
                "house_diffusion_modified": False,
            },
            "geometry_lineage": {
                "geometry_source": "SOURCE_CANDIDATE_INLINE_POLYGONS",
                "geometry_ref_style": "INLINE",
                "geometry_moved": False,
                "geometry_resized": False,
                "geometry_merged": False,
                "geometry_split": False,
                "geometry_invented": False,
                "measured_symbolic_gap": gap,
            },
            "program_lineage": {
                "space_count": len(spaces),
                "identities": [item["space_id"] for item in spaces],
                "native_types": [item.get("native_type") for item in spaces],
                "identity_preserved": True,
                "relabeled": False,
            },
            "floors": {floor_id: floor_document},
            "access_graph": access,
            "unresolved": deepcopy(unresolved),
            "realization": {
                "derived_only": True,
                "metric_wall_thickness_invented": False,
                "doors_invented": False,
                "windows_invented": False,
                "site_orientation_invented": False,
                "vertical_circulation_invented": False,
                "structure_invented": False,
                "internal_generator_used": False,
                "historical_chain_used": False,
                "historical_hardcoded_coordinates_used": False,
            },
        }
        document["realization_sha256"] = generated_baseline_sha256(document)
        return document

    # ------------------------------------------------------------------
    # derivation steps
    # ------------------------------------------------------------------

    @staticmethod
    def _floor_id(spaces: Sequence[Mapping[str, Any]]) -> str:
        for item in spaces:
            if item.get("floor"):
                return str(item["floor"])
        return "ground_floor"

    @staticmethod
    def _spaces(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in candidate.get("spaces") or []:
            if not isinstance(raw, Mapping):
                continue
            identity = str(raw.get("architectos_identity") or raw.get("space_id") or "")
            if not identity or identity in seen:
                continue
            seen.add(identity)
            polygon = _polygon(raw.get("polygon"))
            if polygon is None:
                continue
            records.append({
                "space_id": identity,
                "canonical_name": identity,
                "instance_label": raw.get("instance_label"),
                "source_space_id": raw.get("space_id"),
                "native_type": raw.get("native_type"),
                "native_type_name": raw.get("native_type_name"),
                "floor": raw.get("floor") or "ground_floor",
                "polygon": [[_round(x), _round(y)] for x, y in polygon.exterior.coords],
                "area_normalized": raw.get("area_normalized"),
                "perimeter_normalized": _round(polygon.length),
                "centroid": [_round(polygon.centroid.x), _round(polygon.centroid.y)],
                "bbox": [_round(v) for v in polygon.bounds],
                "geometry_sha256": _geometry_sha256(polygon),
                "construction_claim": False,
                "provenance": {
                    "source": "house_diffusion_source_candidate",
                    "geometry_invented": False,
                    "identity_preserved": True,
                },
            })
        return records

    @staticmethod
    def _measured_gap(spaces: Sequence[Mapping[str, Any]]) -> float:
        """The candidate's OWN dominant inter-room gap. Never hard-coded."""
        polygons = [p for p in (_polygon(item["polygon"]) for item in spaces) if p is not None]
        return GeneratedBaselineRealizationV1._gap_from_polygons(polygons)

    @staticmethod
    def _gap_from_polygons(polygons: Sequence[Polygon]) -> float:
        distances = []
        for a, b in itertools.combinations(polygons, 2):
            distance = float(a.distance(b))
            if distance > 0:
                distances.append(round(distance, 9))
        return min(distances) if distances else 0.0

    def _envelope(self, candidate: Mapping[str, Any],
                  polygons: Mapping[str, Polygon]) -> tuple[dict[str, Any], str]:
        """Derive the floor footprint from the REAL source room polygons.

        The floor footprint is the CLOSED union of the actual room polygons.  The
        closing radius is the MINIMAL radius that makes the footprint a single
        plate, derived deterministically from the measured inter-room distances
        (half the longest edge of the room minimum-spanning-tree).  Nothing is
        moved, resized or invented: no site boundary is introduced, no room is
        relocated, and every measured quantity is recorded.

        The source candidate's own ``envelope`` is a *closing* envelope that can
        both micro-clip rooms and miss detached ones, so it is preserved as
        EVIDENCE rather than used as the containment authority.
        """
        shapes = [p for p in polygons.values() if p is not None]
        raw = candidate.get("envelope")
        source_polygon = _polygon((raw or {}).get("polygon")) if isinstance(raw, Mapping) else None

        if shapes:
            union = unary_union(shapes)
            gap = self._gap_from_polygons(shapes)
            bridge, bridged_pair = self._minimal_bridge(shapes)
            closing = max(bridge / 2.0, (gap / 2.0) if gap else 0.0)
            closed = union.buffer(closing, join_style=2) if closing > 0 else union
            parts = list(closed.geoms) if closed.geom_type == "MultiPolygon" else [closed]
            footprint = max(parts, key=lambda part: part.area)

            record: dict[str, Any] = {
                "polygon": [[_round(x), _round(y)] for x, y in footprint.exterior.coords],
                "area_normalized": _round(footprint.area),
                "closing_radius": _round(closing),
                "measured_symbolic_gap": _round(gap) if gap else None,
                "minimal_bridge_distance": _round(bridge) if bridge else None,
                "minimal_bridge_pair": bridged_pair,
                "source": ("DERIVED_UNION_OF_SOURCE_ROOM_POLYGONS_CLOSED_BY_MINIMAL_BRIDGE"
                           if bridge else
                           "DERIVED_UNION_OF_SOURCE_ROOM_POLYGONS_CLOSED_BY_MEASURED_HALF_GAP"),
                "geometry_invented": False,
                "site_boundary_invented": False,
                "rooms_moved": False,
                "rooms_resized": False,
                "footprint_parts_before_closing": (
                    len(union.geoms) if union.geom_type == "MultiPolygon" else 1),
                "rooms_contained": all(footprint.covers(shape) for shape in shapes),
            }
            if source_polygon is not None:
                record["source_candidate_envelope"] = {
                    "polygon": [[_round(x), _round(y)] for x, y in
                                source_polygon.exterior.coords],
                    "area_normalized": (raw or {}).get("area_normalized"),
                    "closing_radius": (raw or {}).get("closing_radius"),
                    "components": (raw or {}).get("components"),
                    "contains_floor_footprint": bool(
                        union.difference(source_polygon).area <= 1e-9),
                    "note": ("preserved as generator evidence only; the containment "
                             "authority is the closed room footprint"),
                }
            return record, record["source"]

        # No room geometry at all: fall back to the supplied envelope, if any.
        if source_polygon is not None:
            return {
                "polygon": [[_round(x), _round(y)] for x, y in source_polygon.exterior.coords],
                "area_normalized": (raw or {}).get("area_normalized"),
                "source": "SOURCE_CANDIDATE_ENVELOPE",
                "geometry_invented": False,
                "rooms_contained": None,
            }, "SOURCE_CANDIDATE_ENVELOPE"

        return {"polygon": [], "source": "UNAVAILABLE", "geometry_invented": False}, "UNAVAILABLE"

    @staticmethod
    def _minimal_bridge(shapes: Sequence[Polygon]) -> tuple[float, list[str] | None]:
        """Longest edge of the room minimum-spanning-tree.

        This is the MINIMAL distance that has to be bridged to express the floor
        footprint as one plate.  Deterministic: Prim's algorithm over rooms ordered
        by index, tie-broken by index.
        """
        count = len(shapes)
        if count < 2:
            return 0.0, None
        distances = [[float(shapes[i].distance(shapes[j])) for j in range(count)]
                     for i in range(count)]
        in_tree = [False] * count
        best = [float("inf")] * count
        parent = [-1] * count
        in_tree[0] = True
        for j in range(1, count):
            best[j] = distances[0][j]
            parent[j] = 0
        bridge = 0.0
        pair: list[int] | None = None
        for _ in range(count - 1):
            candidate_index, candidate_value = -1, float("inf")
            for j in range(count):
                if not in_tree[j] and best[j] < candidate_value:
                    candidate_index, candidate_value = j, best[j]
            if candidate_index < 0:
                break
            in_tree[candidate_index] = True
            if candidate_value > bridge:
                bridge = candidate_value
                pair = sorted((parent[candidate_index], candidate_index))
            for j in range(count):
                if not in_tree[j] and distances[candidate_index][j] < best[j]:
                    best[j] = distances[candidate_index][j]
                    parent[j] = candidate_index
        return bridge, ([str(i) for i in pair] if pair else None)

    def _walls(self, spaces: Sequence[Mapping[str, Any]],
               polygons: Mapping[str, Polygon],
               gap: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Derive symbolic wall centrelines from room-boundary adjacency."""
        tolerance = gap * ADJACENCY_TOLERANCE_FACTOR if gap else 1e-9
        names = sorted(polygons)
        walls: list[dict[str, Any]] = []
        index = 0

        for a_name, b_name in itertools.combinations(names, 2):
            polygon_a, polygon_b = polygons[a_name], polygons[b_name]
            if polygon_a is None or polygon_b is None:
                continue
            distance = float(polygon_a.distance(polygon_b))
            if distance > tolerance:
                continue
            if distance > 0:
                midline = (polygon_a.buffer(distance / 2.0, join_style=2).boundary
                           .intersection(polygon_b.buffer(distance / 2.0, join_style=2).boundary))
            else:
                midline = polygon_a.boundary.intersection(polygon_b.boundary)
            for segment in _line_parts(midline):
                if LineString(segment).length <= 1e-9:
                    continue
                index += 1
                walls.append(self._wall_record(
                    f"GW-INT-{index:03d}", "INTERIOR", [a_name, b_name], segment,
                    "derived from the midline between two gap-separated source rooms"))

        # exterior walls: the closed union's outline (no invented site boundary)
        shapes = [p for p in polygons.values() if p is not None]
        unresolved: list[dict[str, Any]] = []
        if shapes:
            union = unary_union(shapes)
            closed = union.buffer(gap / 2.0, join_style=2) if gap else union
            outline = closed if closed.geom_type == "Polygon" else max(
                (g for g in closed.geoms), key=lambda g: g.area)
            coords = [[_round(x), _round(y)] for x, y in outline.exterior.coords]
            for i in range(len(coords) - 1):
                segment = [coords[i], coords[i + 1]]
                if LineString(segment).length <= 1e-9:
                    continue
                index += 1
                walls.append(self._wall_record(
                    f"GW-EXT-{index:03d}", "EXTERIOR", [], segment,
                    "derived from the closed outline of the source room union"))
        else:
            unresolved.append({
                "classification": "MISSING_CANONICAL_EVIDENCE",
                "code": "NO_SOURCE_ROOM_GEOMETRY",
                "detail": "no room polygon could be realized",
            })
        return walls, unresolved

    @staticmethod
    def _wall_record(wall_id: str, role: str, between: list[str],
                     segment: list[list[float]], derivation: str) -> dict[str, Any]:
        return {
            "wall_id": wall_id,
            "wall_role": role,
            "between": between,
            "centerline": segment,
            "wall_band": {
                "wall_band_type": "SYMBOLIC_RELATIVE",
                "metric_thickness": "UNKNOWN",
                "construction_claim": False,
            },
            "thickness_status": WALL_THICKNESS_METRIC_UNRESOLVED,
            "construction_claim": False,
            "derivation": derivation,
            "provenance": {"source": "ARCHITECTOS_DERIVED", "geometry_invented": False},
        }

    def _openings(self, candidate: Mapping[str, Any],
                  spaces: Sequence[Mapping[str, Any]],
                  walls: Sequence[Mapping[str, Any]],
                  gap: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Preserve ONLY source-provided doors; host binding is derived geometrically."""
        known = {item["space_id"] for item in spaces}
        tolerance = (gap * 2.0) if gap else 1e-6
        records: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []

        for door in candidate.get("doors") or []:
            if not isinstance(door, Mapping):
                continue
            opening_id = str(door.get("door_id") or "")
            if not opening_id:
                continue
            segment = _ring(door.get("opening_segment"))
            if len(segment) < 2:
                unresolved.append({
                    "classification": "MISSING_CANONICAL_EVIDENCE",
                    "code": "OPENING_SEGMENT_UNRESOLVED",
                    "detail": f"door {opening_id} has no usable opening segment",
                    "opening_id": opening_id,
                })
                continue
            line = LineString(segment)

            sides = [str(s) for s in (door.get("between_identities") or [])
                     if str(s) in known]
            if str(door.get("door_type")).upper() == "FRONT":
                side_a, side_b = sides[0] if sides else None, EXTERIOR
            else:
                side_a = sides[0] if len(sides) > 0 else None
                side_b = sides[1] if len(sides) > 1 else None

            host_wall_id, host_distance = None, None
            for wall in walls:
                wall_line = LineString(wall["centerline"])
                distance = float(line.distance(wall_line))
                if host_distance is None or distance < host_distance:
                    host_distance, host_wall_id = distance, wall["wall_id"]
            if host_distance is not None and host_distance <= tolerance:
                host_status = "RESOLVED"
            else:
                host_wall_id = None
                host_status = "UNRESOLVED"
                unresolved.append({
                    "classification": "MISSING_CANONICAL_EVIDENCE",
                    "code": "OPENING_HOST_UNRESOLVED",
                    "detail": (f"door {opening_id} could not be bound to a derived wall "
                               f"within tolerance {tolerance}"),
                    "opening_id": opening_id,
                })

            native_type = str(door.get("native_type") or "")
            records.append({
                "opening_id": opening_id,
                "kind": "DOOR",
                "opening_class": NATIVE_DOOR_TYPES.get(native_type, "NATIVE_DOOR"),
                "native_type": native_type,
                "door_type": door.get("door_type"),
                "side_a": side_a,
                "side_b": side_b,
                "opening_segment": segment,
                "span": _round(line.length),
                "host_wall_id": host_wall_id,
                "host_status": host_status,
                "host_distance": _round(host_distance) if host_distance is not None else None,
                "construction_claim": False,
                "provenance": {
                    "source": "house_diffusion_source_door",
                    "door_invented": False,
                    "host_derived_geometrically": host_status == "RESOLVED",
                },
            })
        return records, unresolved

    @staticmethod
    def _windows(candidate: Mapping[str, Any]) -> tuple[list[Any], str]:
        supplied = candidate.get("windows")
        if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes)) and supplied:
            return deepcopy(list(supplied)), "PROVIDED_BY_SOURCE_CANDIDATE"
        return [], WINDOW_STATUS_NOT_PROVIDED

    @staticmethod
    def _circulation(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Preserve only EXPLICIT circulation evidence."""
        raw = candidate.get("circulation")
        records: list[dict[str, Any]] = []
        for item in (raw if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) else []):
            if not isinstance(item, Mapping):
                continue
            if item.get("geometry") in (None, [], {}):
                continue
            records.append(deepcopy(dict(item)))
        return records

    @staticmethod
    def _access_graph(spaces: Sequence[Mapping[str, Any]],
                      openings: Sequence[Mapping[str, Any]],
                      walls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Access is derived ONLY from explicit source doors. No proximity inference."""
        identities = [item["space_id"] for item in spaces]
        edges: list[dict[str, Any]] = []
        for opening in sorted(openings, key=lambda o: str(o["opening_id"])):
            side_a, side_b = opening.get("side_a"), opening.get("side_b")
            if not side_a or not side_b or side_a == side_b:
                continue
            edges.append({
                "edge_id": f"AE-{opening['opening_id']}",
                "a": side_a,
                "b": side_b,
                "opening_id": opening["opening_id"],
                "evidence": "EXPLICIT_SOURCE_DOOR",
                "host_wall_id": opening.get("host_wall_id"),
            })

        nodes = sorted(set(identities) | {EXTERIOR})
        adjacency: dict[str, set[str]] = {node: set() for node in nodes}
        for edge in edges:
            adjacency.setdefault(edge["a"], set()).add(edge["b"])
            adjacency.setdefault(edge["b"], set()).add(edge["a"])

        reachable: set[str] = set()
        stack = [EXTERIOR]
        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)
            stack.extend(adjacency.get(node, ()))

        unreachable = sorted(set(identities) - reachable)
        unresolved: list[dict[str, Any]] = []
        for identity in unreachable:
            unresolved.append({
                "classification": "MISSING_CANONICAL_EVIDENCE",
                "code": "SPACE_WITHOUT_EXPLICIT_ACCESS",
                "detail": (f"{identity} is not reachable from {EXTERIOR} through explicit "
                           f"source doors; no door was invented to connect it"),
                "space_id": identity,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "status": "RESOLVED" if not unreachable else "PARTIAL",
            "method": ("BFS over EXPLICIT source-candidate doors only. Geometric proximity "
                       "without a source door is NOT access and is never used as an edge."),
            "unresolved": unresolved,
            "provenance": {
                "source": "house_diffusion_source_candidate_doors",
                "proximity_inference_used": False,
                "doors_invented": False,
            },
        }


generated_baseline_realization = GeneratedBaselineRealizationV1()


def realize_generated_baseline(candidate: Mapping[str, Any], *,
                               candidate_path: str | None = None) -> dict[str, Any]:
    """Module-level convenience wrapper."""
    return GeneratedBaselineRealizationV1().realize(candidate, candidate_path=candidate_path)


__all__ = [
    "CONTRACT_NAME", "REALIZATION_VERSION", "EXTERIOR",
    "NATIVE_DOOR_TYPES", "GeneratedBaselineRealizationV1",
    "generated_baseline_realization", "realize_generated_baseline",
]
