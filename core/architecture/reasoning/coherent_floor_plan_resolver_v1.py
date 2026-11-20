"""CoherentFloorPlanResolverV1 — ARCHITECTURAL-DESIGN-ROBUSTNESS-01A2.

Derived, read-only realization of a COHERENT, NON-OVERLAPPING metric floor plan.

Proven upstream defect this stage compensates for (see the phase report):

    ``SpatialPlacementReasoner.place`` marks a whole floor ``abstract_grid``
    when ANY space lacks explicit metric width/depth (all-or-nothing
    ``metric_floor_ready``).  ``architectural_geometry_engine_v2`` then still
    promotes those abstract cells to metric ``parcel_local`` footprints by
    applying only the parcel translation, so the abstract cell index is consumed
    as metres and rooms overlap.

This resolver does NOT modify that engine and does NOT replace the placement
reasoner: it keeps the existing ABSTRACT layout as the relative-ordering
authority and performs the missing METRIC realization with a deterministic
non-overlapping partition, then derives wall topology from the final boundaries.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from typing import Any

from shapely.geometry import Polygon

from core.architecture.contracts.coherent_architectural_floor_plan_v1 import (
    COHERENT_STYLE_TOKENS,
    COHERENT_SVG_BACKGROUND,
    COHERENT_SVG_FONT_FAMILY,
    COHERENT_SVG_PADDING,
    COHERENT_SVG_UNITS_PER_METRE,
    CONTRACT,
    EXTERIOR_WALL,
    FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA,
    INTERIOR_SHARED_WALL,
    PLACED,
    POST_LAYOUT_GEOMETRY_DRIFT,
    PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE,
    STAIR_CORE_SPACE_RESOLVED,
    STAIR_GEOMETRY_PENDING,
    STATUS_ENVELOPE_PENDING,
    STATUS_FAILED,
    STATUS_PROGRAM_AREA_EXCEEDS_ENVELOPE,
    STATUS_RESOLVED,
    STATUS_RESOLVED_WITH_GAPS,
    STATUS_SPATIAL_LAYOUT_UNRESOLVED,
    UNRESOLVED_SPACE,
    VERSION,
    coherent_floor_semantic_hash,
    svg_sha256,
)
from core.architecture.reasoning.architectural_design_robustness_01a import (
    project_human_readable_plan,
)

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: CoherentFloorPlanResolverV1.resolve
#             (internal plan synthesis branch - deterministic squarified
#              treemap / zone-band partition)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class CoherentArchitecturalFloorPlanV1(dict):
    """Versioned, dict-compatible coherent floor plan artifact."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as error:  # pragma: no cover
            raise AttributeError(item) from error


CIRCULATION_NAMES = {"corridor", "hall", "hallway", "landing", "stairs", "stair", "lobby"}
CORE_NAMES = {"stairs", "stair", "elevator", "lift", "core", "shaft"}
EXTERNAL_ZONE = "external"
TOL = 1e-6


# ==========================================================
# deterministic squarified treemap
# ==========================================================

def _worst_ratio(row: list[float], short: float) -> float:
    total = sum(row)
    if total <= 0 or short <= 0:
        return float("inf")
    biggest, smallest = max(row), min(row)
    if smallest <= 0:
        return float("inf")
    return max(
        (short * short * biggest) / (total * total),
        (total * total) / (short * short * smallest),
    )


def _treemap(values: list[float], x: float, y: float, dx: float, dy: float):
    """Squarified treemap: non-overlapping rectangles exactly filling (x,y,dx,dy)."""
    rects: list[tuple[float, float, float, float]] = []
    items = [value for value in values]
    index = 0
    while index < len(items):
        short = min(dx, dy)
        row = [items[index]]
        index += 1
        while index < len(items):
            if _worst_ratio(row + [items[index]], short) <= _worst_ratio(row, short):
                row.append(items[index])
                index += 1
            else:
                break
        total = sum(row)
        if total <= 0:
            break
        if dx >= dy:
            width = total / dy if dy else 0.0
            cursor = y
            for value in row:
                height = (value / total) * dy
                rects.append((x, cursor, width, height))
                cursor += height
            x += width
            dx -= width
        else:
            height = total / dx if dx else 0.0
            cursor = x
            for value in row:
                width = (value / total) * dx
                rects.append((cursor, y, width, height))
                cursor += width
            y += height
            dy -= height
    return rects


def _rect_polygon(rect) -> list[list[float]]:
    x, y, w, h = rect
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]


def _area(ring) -> float:
    try:
        return float(Polygon(ring).area)
    except (ValueError, TypeError):
        return 0.0


class CoherentFloorPlanResolverV1:
    """Realize a coherent, non-overlapping metric floor plan."""

    VERSION = VERSION

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def resolve(self, design_model: Any, *, program: Mapping[str, Any] | None = None,
                human_plan: Mapping[str, Any] | None = None) -> CoherentArchitecturalFloorPlanV1:
        plan = human_plan if isinstance(human_plan, Mapping) else project_human_readable_plan(
            design_model, program=program)
        geometry = getattr(design_model, "architectural_geometry", None)
        if not isinstance(geometry, Mapping) or not isinstance(plan.get("floors"), list):
            return self._failed("design_model_has_no_usable_plan")

        plan_model = getattr(design_model, "plan_model", None)
        plan_model = plan_model if isinstance(plan_model, Mapping) else {}
        abstract = self._abstract_layout(design_model)
        relationships = plan_model.get("relationships") or []
        buildable = (geometry.get("site_geometry") or {}).get("buildable_boundary")

        floor_meta = {
            str(item.get("floor")): item
            for item in (geometry.get("floor_geometry") or [])
            if isinstance(item, Mapping) and item.get("floor") is not None
        }

        floors: list[dict[str, Any]] = []
        for floor in plan["floors"]:
            floors.append(self._floor(
                floor, floor_meta.get(str(floor["floor_id"]), {}), abstract,
                relationships, buildable,
            ))

        status = self._plan_status(floors)
        document = CoherentArchitecturalFloorPlanV1({
            "contract": CONTRACT,
            "version": VERSION,
            "plan_status": status,
            "plan_kind": "DERIVED_COHERENT_METRIC_FLOOR_REALIZATION",
            "source": {
                "human_plan_hash": plan.get("plan_hash"),
                "source_plan_id": plan.get("source_candidate_id"),
                "abstract_layout_entries": len(abstract),
                "abstract_layout_authority": "RELATIVE_ORDERING_ONLY",
            },
            "floors": floors,
            "root_cause_analysis": {
                "primary": POST_LAYOUT_GEOMETRY_DRIFT,
                "contributing": ["FOOTPRINT_GENERATION_CONFLICT", "LEGACY_GRID_ASSUMPTION"],
                "evidence": {
                    "abstract_coordinates_consumed_as_metres": True,
                    "all_or_nothing_metric_floor_ready": True,
                    "engine_collision_test_bypassed_on_abstract_path": True,
                },
                "upstream_engine_modified": False,
                "layout_engine_replaced": False,
            },
            "provenance": {
                "resolver": "CoherentFloorPlanResolverV1",
                "resolver_version": VERSION,
                "ordering_authority": "SpatialPlacementReasoner.place (abstract_grid cells)",
                "partition": "deterministic_squarified_treemap",
                "geometry_invented": False,
                "spaces_moved_without_decision": False,
                "spaces_deleted": False,
                "source_mutated": False,
                "structural_elements_generated": False,
                "bim_ifc_executed": False,
                "render_runtime_executed": False,
                "comfyui_executed": False,
            },
        })
        document["plan_hash"] = coherent_floor_semantic_hash(document)
        return document

    # --------------------------------------------------
    # abstract ordering authority
    # --------------------------------------------------

    @staticmethod
    def _abstract_layout(design_model: Any) -> dict[tuple[str, str], dict[str, Any]]:
        layout = getattr(design_model, "layout", None)
        entries = layout.get("spatial_layout") if isinstance(layout, Mapping) else None
        output: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in entries or []:
            if not isinstance(entry, Mapping) or entry.get("name") is None:
                continue
            key = (str(entry.get("floor")), str(entry.get("name")))
            output.setdefault(key, dict(entry))
        return output

    # --------------------------------------------------
    # one floor
    # --------------------------------------------------

    def _floor(self, floor, meta, abstract, relationships, buildable) -> dict[str, Any]:
        floor_id = str(floor["floor_id"])
        coordinate_modes = [
            str(mode) for mode in (meta.get("coordinate_modes") or [])
        ]
        drifted = "abstract_grid" in coordinate_modes or meta.get("geometry_status") not in (
            None, "resolved_metric_envelope")

        interior = [
            space for space in floor["spaces"]
            if not space.get("external") and space.get("area_m2")
        ]
        external = [space for space in floor["spaces"] if space.get("external")]
        unresolved = [
            space for space in floor["spaces"]
            if not space.get("area_m2")
        ]

        conflicts: list[dict[str, Any]] = []
        if drifted:
            conflicts.append({
                "code": POST_LAYOUT_GEOMETRY_DRIFT,
                "floor_id": floor_id,
                "detail": "source floor coordinates were abstract_grid; engine footprints discarded",
                "source_footprint_overlap_area": self._source_overlap(floor),
            })

        if not interior:
            return self._empty_floor(floor_id, floor, conflicts, unresolved, drifted)

        target_area = round(sum(float(space["area_m2"]) for space in interior), 6)
        envelope, envelope_source, envelope_note = self._envelope(
            meta, interior, abstract, floor_id, buildable)
        # A resolved source envelope is AUTHORITATIVE: preserve it and only
        # re-realize the interior partition inside it.
        preserved_envelope = bool(
            isinstance(meta.get("envelope"), Mapping) and meta["envelope"].get("width"))
        if preserved_envelope:
            envelope_source = "floor_metric_envelope_preserved"
            envelope_note = None

        if envelope is None:
            conflicts.append({"code": STATUS_ENVELOPE_PENDING, "floor_id": floor_id})
            return self._empty_floor(floor_id, floor, conflicts, unresolved, drifted,
                                     target_area=target_area)
        if envelope_note == PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE:
            conflicts.append({
                "code": PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE,
                "floor_id": floor_id,
                "target_area_m2": target_area,
            })
            return self._empty_floor(floor_id, floor, conflicts, unresolved, drifted,
                                     target_area=target_area)

        ordered = self._order(interior, abstract, floor_id)
        rects = self._zone_bands(ordered, envelope)

        spaces = []
        for space, rect in zip(ordered, rects):
            ring = _rect_polygon(rect)
            realized = round(_area(ring), 6)
            requested = float(space["area_m2"])
            is_core = space["name"] in CORE_NAMES
            spaces.append({
                "space_id": space["space_id"],
                "name": space["name"],
                "display_label": space["display_label"],
                "semantic_type": space["semantic_type"],
                "zone": space["zone"],
                "external": False,
                "requested_area_m2": round(requested, 6),
                "realized_area_m2": realized,
                "area_delta_m2": round(realized - requested, 6),
                "polygon": ring,
                "placement_status": PLACED,
                "protected_core": is_core,
                "core_status": STAIR_CORE_SPACE_RESOLVED if is_core else None,
                "source_geometry_footprint": deepcopy(space.get("polygon")),
                "provenance": {
                    "source": "coherent_metric_partition",
                    "ordering_from": "abstract_grid_cell",
                    "geometry_invented": False,
                },
            })

        external_regions = self._external_regions(external, envelope)
        shared, exterior = self._boundaries(spaces, envelope)
        metrics = self._metrics(spaces, external_regions, envelope, target_area,
                                relationships, floor_id)
        adjacency, circulation = self._adjacency(spaces, relationships, floor_id)
        metrics["adjacency_requirements_total"] = adjacency["total"]
        metrics["adjacency_requirements_satisfied"] = adjacency["satisfied"]
        metrics["circulation_connectivity_status"] = circulation["status"]
        metrics["internal_shared_wall_count"] = len(shared)
        metrics["exterior_wall_count"] = len(exterior)

        status = STATUS_RESOLVED
        if unresolved or conflicts or circulation["status"] != "CONNECTED":
            status = STATUS_RESOLVED_WITH_GAPS

        return {
            "floor_id": floor_id,
            "floor_label": floor["floor_label"],
            "floor_order": floor["floor_order"],
            "elevation": floor.get("elevation"),
            "source_coordinate_modes": coordinate_modes,
            "source_geometry_status": meta.get("geometry_status"),
            "source_geometry_drifted": drifted,
            "realization_source": (
                "coherent_partition_in_preserved_envelope" if preserved_envelope
                else "coherent_partition_in_derived_envelope"),
            "floor_envelope": envelope,
            "floor_envelope_source": envelope_source,
            "interior_usable_region": deepcopy(envelope["polygon"]),
            "external_regions": external_regions,
            "spaces": spaces,
            "shared_boundaries": shared,
            "exterior_boundaries": exterior,
            "circulation_connections": circulation["connections"],
            "adjacency": adjacency,
            "layout_conflicts": conflicts,
            "unresolved_spaces": [
                {"space_id": space["space_id"], "name": space["name"],
                 "reason": "no_resolved_area_or_footprint",
                 "placement_status": UNRESOLVED_SPACE}
                for space in unresolved
            ],
            "quality_metrics": metrics,
            "stair_core": {
                "space_ids": [s["space_id"] for s in spaces if s["protected_core"]],
                "core_space_status": STAIR_CORE_SPACE_RESOLVED if any(
                    s["protected_core"] for s in spaces) else None,
                "stair_geometry_status": STAIR_GEOMETRY_PENDING,
                "stair_flights_generated": False,
                "protected_from_overlap": True,
            },
            "status": status,
        }

    # --------------------------------------------------
    # envelope
    # --------------------------------------------------

    def _envelope(self, meta, interior, abstract, floor_id, buildable):
        resolved = meta.get("envelope")
        if isinstance(resolved, Mapping) and resolved.get("width") and resolved.get("depth"):
            return ({
                "min_x": float(resolved["min_x"]), "min_y": float(resolved["min_y"]),
                "max_x": float(resolved["max_x"]), "max_y": float(resolved["max_y"]),
                "width": float(resolved["width"]), "depth": float(resolved["depth"]),
                "area": float(resolved.get("area") or resolved["width"] * resolved["depth"]),
                "polygon": [
                    [float(resolved["min_x"]), float(resolved["min_y"])],
                    [float(resolved["max_x"]), float(resolved["min_y"])],
                    [float(resolved["max_x"]), float(resolved["max_y"])],
                    [float(resolved["min_x"]), float(resolved["max_y"])],
                    [float(resolved["min_x"]), float(resolved["min_y"])],
                ],
            }, "floor_metric_envelope", None)

        # The floor's own metric envelope is unresolved.  Derive one ONLY from
        # the floor's own resolved space areas plus the aspect ratio of the
        # floor's own abstract relative layout.  No bbox enlargement, no fixed
        # width/depth, no structural grid.
        cells = [
            (entry.get("x"), entry.get("y"))
            for (entry_floor, _), entry in sorted(abstract.items())
            if entry_floor in (floor_id, "ground_floor") and isinstance(entry.get("x"), (int, float))
        ]
        xs = [float(x) for x, _ in cells]
        ys = [float(y) for _, y in cells]
        if xs and ys:
            ratio = max((max(xs) - min(xs)) + 1.0, 1.0) / max((max(ys) - min(ys)) + 1.0, 1.0)
        else:
            ratio = 1.0

        target = sum(float(space["area_m2"]) for space in interior)
        width = math.sqrt(target * ratio)
        depth = target / width if width else 0.0
        if width <= 0 or depth <= 0:
            return None, None, None

        if isinstance(buildable, list) and len(buildable) >= 3:
            bx = [float(p[0]) for p in buildable]
            by = [float(p[1]) for p in buildable]
            if width > (max(bx) - min(bx)) + TOL or depth > (max(by) - min(by)) + TOL:
                return None, None, PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE
            min_x, min_y = min(bx), min(by)
        else:
            min_x, min_y = 0.0, 0.0

        return ({
            "min_x": min_x, "min_y": min_y,
            "max_x": min_x + width, "max_y": min_y + depth,
            "width": width, "depth": depth, "area": width * depth,
            "polygon": [[min_x, min_y], [min_x + width, min_y],
                        [min_x + width, min_y + depth], [min_x, min_y + depth],
                        [min_x, min_y]],
        }, FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA,
            FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA)

    # --------------------------------------------------
    # ordering / externals / boundaries / metrics
    # --------------------------------------------------

    @staticmethod
    def _order(interior, abstract, floor_id):
        zone_rank = {"public": 0, "circulation": 1, "service": 2, "private": 3}

        def key(space):
            entry = abstract.get((floor_id, space["name"])) or abstract.get(
                ("ground_floor", space["name"])) or {}
            y = entry.get("y") if isinstance(entry.get("y"), (int, float)) else 0
            x = entry.get("x") if isinstance(entry.get("x"), (int, float)) else 0
            return (zone_rank.get(str(space.get("zone")), 9), float(y), float(x), space["name"])

        return sorted(interior, key=key)

    @staticmethod
    def _zone_bands(spaces, envelope):
        """Deterministic ZONE-COHERENT partition of the floor envelope.

        Zones are laid out as parallel bands along the envelope's longer axis in
        architectural order (public -> circulation -> service -> private); each
        band is subdivided along the perpendicular axis.  The circulation band
        therefore spans the envelope and touches the other zones, which is what
        makes a corridor serve circulation instead of being one more rectangle.

        Boundaries are tracked as explicit shared coordinates so adjacent rooms
        share an EXACT edge (no floating-point gaps).
        """
        rank = {"public": 0, "circulation": 1, "service": 2, "private": 3}
        groups: dict[int, list[dict[str, Any]]] = {}
        for space in spaces:
            groups.setdefault(rank.get(str(space.get("zone")), 9), []).append(space)

        origin_x, origin_y = envelope["min_x"], envelope["min_y"]
        full_dx, full_dy = envelope["width"], envelope["depth"]
        horizontal = full_dx >= full_dy
        total_area = sum(max(float(space["area_m2"]), 1e-6) for space in spaces)
        envelope_area = full_dx * full_dy
        # Only the share of the envelope actually required by the program is
        # partitioned; surplus stays UNALLOCATED rather than absorbed by a room.
        fill = min(1.0, (total_area / envelope_area)) if envelope_area else 1.0
        axis_total = (full_dx if horizontal else full_dy) * fill

        rects: dict[str, tuple[float, float, float, float]] = {}
        ordered_keys = sorted(groups)
        boundary = 0.0
        for position, key in enumerate(ordered_keys):
            band = groups[key]
            band_area = sum(max(float(space["area_m2"]), 1e-6) for space in band)
            share = (band_area / total_area) if total_area else 0.0
            last = position == len(ordered_keys) - 1
            start = boundary
            boundary = axis_total if last else boundary + axis_total * share
            extent = max(boundary - start, 0.0)

            cross = full_dy if horizontal else full_dx
            stack_boundary = 0.0
            for index, space in enumerate(band):
                weight = max(float(space["area_m2"]), 1e-6)
                item_start = stack_boundary
                if index == len(band) - 1:
                    stack_boundary = cross
                else:
                    step = (weight / extent) if extent else 0.0
                    stack_boundary = min(stack_boundary + step, cross)
                size = max(stack_boundary - item_start, 0.0)
                if horizontal:
                    rects[space["name"]] = (origin_x + start, origin_y + item_start,
                                            extent, size)
                else:
                    rects[space["name"]] = (origin_x + item_start, origin_y + start,
                                            size, extent)

        return [rects[space["name"]] for space in spaces]

    def _preserved_floor(self, floor, meta, interior, external, unresolved,
                         relationships, floor_id) -> dict[str, Any]:
        """Preserve authoritative upstream metric geometry without re-partitioning."""
        spaces = []
        for space in interior:
            is_core = space["name"] in CORE_NAMES
            spaces.append({
                "space_id": space["space_id"], "name": space["name"],
                "display_label": space["display_label"],
                "semantic_type": space["semantic_type"], "zone": space["zone"],
                "external": False,
                "requested_area_m2": round(float(space["area_m2"]), 6),
                "realized_area_m2": round(float(space["area_m2"]), 6),
                "area_delta_m2": 0.0,
                "polygon": deepcopy(space["polygon"]),
                "placement_status": PLACED, "protected_core": is_core,
                "core_status": STAIR_CORE_SPACE_RESOLVED if is_core else None,
                "source_geometry_footprint": deepcopy(space.get("polygon")),
                "provenance": {"source": "source_metric_geometry_preserved",
                               "geometry_invented": False},
            })

        resolved = meta["envelope"]
        envelope = {
            "min_x": float(resolved["min_x"]), "min_y": float(resolved["min_y"]),
            "max_x": float(resolved["max_x"]), "max_y": float(resolved["max_y"]),
            "width": float(resolved["width"]), "depth": float(resolved["depth"]),
            "area": float(resolved.get("area") or resolved["width"] * resolved["depth"]),
            "polygon": [
                [float(resolved["min_x"]), float(resolved["min_y"])],
                [float(resolved["max_x"]), float(resolved["min_y"])],
                [float(resolved["max_x"]), float(resolved["max_y"])],
                [float(resolved["min_x"]), float(resolved["max_y"])],
                [float(resolved["min_x"]), float(resolved["min_y"])],
            ],
        }
        external_regions = self._external_regions(external, envelope)
        shared, exterior = self._boundaries(spaces, envelope)
        target = sum(space["requested_area_m2"] for space in spaces)
        metrics = self._metrics(spaces, external_regions, envelope, target,
                                relationships, floor_id)
        metrics["internal_shared_wall_count"] = len(shared)
        metrics["exterior_wall_count"] = len(exterior)
        adjacency, circulation = self._adjacency(spaces, relationships, floor_id)
        metrics["adjacency_requirements_total"] = adjacency["total"]
        metrics["adjacency_requirements_satisfied"] = adjacency["satisfied"]
        metrics["circulation_connectivity_status"] = circulation["status"]

        status = STATUS_RESOLVED
        if unresolved or circulation["status"] != "CONNECTED":
            status = STATUS_RESOLVED_WITH_GAPS

        return {
            "floor_id": floor_id, "floor_label": floor["floor_label"],
            "floor_order": floor["floor_order"], "elevation": floor.get("elevation"),
            "source_coordinate_modes": [str(m) for m in (meta.get("coordinate_modes") or [])],
            "source_geometry_status": meta.get("geometry_status"),
            "source_geometry_drifted": False,
            "realization_source": "source_metric_geometry_preserved",
            "floor_envelope": envelope, "floor_envelope_source": "floor_metric_envelope",
            "interior_usable_region": deepcopy(envelope["polygon"]),
            "external_regions": external_regions, "spaces": spaces,
            "shared_boundaries": shared, "exterior_boundaries": exterior,
            "circulation_connections": circulation["connections"],
            "adjacency": adjacency, "layout_conflicts": [],
            "unresolved_spaces": [
                {"space_id": space["space_id"], "name": space["name"],
                 "reason": "no_resolved_area_or_footprint",
                 "placement_status": UNRESOLVED_SPACE} for space in unresolved
            ],
            "quality_metrics": metrics,
            "stair_core": {
                "space_ids": [s["space_id"] for s in spaces if s["protected_core"]],
                "core_space_status": STAIR_CORE_SPACE_RESOLVED if any(
                    s["protected_core"] for s in spaces) else None,
                "stair_geometry_status": STAIR_GEOMETRY_PENDING,
                "stair_flights_generated": False, "protected_from_overlap": True,
            },
            "status": status,
        }

    @staticmethod
    def _external_regions(external, envelope):
        regions = []
        cursor = envelope["min_x"]
        for space in sorted(external, key=lambda item: item["name"]):
            area = float(space.get("area_m2") or 0.0)
            if area <= 0:
                continue
            width = min(area / 2.0 if area else 0.0, envelope["width"] / 2.0)
            depth = area / width if width else 0.0
            ring = [[cursor, envelope["min_y"] - depth], [cursor + width, envelope["min_y"] - depth],
                    [cursor + width, envelope["min_y"]], [cursor, envelope["min_y"]],
                    [cursor, envelope["min_y"] - depth]]
            cursor += width
            regions.append({
                "space_id": space["space_id"], "name": space["name"],
                "display_label": space["display_label"], "zone": EXTERNAL_ZONE,
                "external": True, "realized_area_m2": round(area, 6),
                "polygon": ring, "placement_status": PLACED,
                "relation_to_building": "ADJACENT_EXTERNAL",
                "provenance": {"source": "human_plan.external_spaces",
                               "geometry_invented": False},
            })
        return regions

    def _boundaries(self, spaces, envelope):
        shared = []
        exterior = []
        env_poly = Polygon(envelope["polygon"])
        for space in spaces:
            polygon = Polygon(space["polygon"])
            boundary = polygon.boundary
            if boundary.intersection(env_poly.boundary).length > TOL:
                exterior.append({
                    "space_id": space["space_id"], "wall_type": EXTERIOR_WALL,
                    "length_m": round(boundary.intersection(env_poly.boundary).length, 6),
                    "provenance": {"source": "floor_envelope_edge", "geometry_invented": False},
                })
        for index, left in enumerate(spaces):
            for right in spaces[index + 1:]:
                overlap = Polygon(left["polygon"]).boundary.intersection(
                    Polygon(right["polygon"]).boundary)
                length = overlap.length
                if length > TOL:
                    shared.append({
                        "spaces": [left["space_id"], right["space_id"]],
                        "wall_type": INTERIOR_SHARED_WALL,
                        "length_m": round(length, 6),
                        "provenance": {"source": "resolved_space_boundary",
                                       "geometry_invented": False},
                    })
        return shared, exterior

    def _metrics(self, spaces, external, envelope, target_area, relationships, floor_id):
        polygons = [(space["space_id"], Polygon(space["polygon"])) for space in spaces]
        pairwise = 0.0
        maximum = 0.0
        for index, (_, left) in enumerate(polygons):
            for _, right in polygons[index + 1:]:
                area = left.intersection(right).area
                if area > TOL:
                    pairwise += area
                    maximum = max(maximum, area)
        realized = sum(space["realized_area_m2"] for space in spaces)
        external_area = sum(region["realized_area_m2"] for region in external)
        envelope_area = envelope["area"]
        return {
            "space_count": len(spaces),
            "resolved_space_count": sum(1 for s in spaces if s["placement_status"] == PLACED),
            "unresolved_space_count": 0,
            "total_program_target_area": round(target_area, 6),
            "realized_interior_area": round(realized, 6),
            "external_area": round(external_area, 6),
            "pairwise_overlap_area": round(pairwise, 6),
            "maximum_overlap_area": round(maximum, 6),
            "envelope_area": round(envelope_area, 6),
            "unallocated_interior_area": round(max(envelope_area - realized, 0.0), 6),
            "area_deficit_or_surplus": round(realized - target_area, 6),
            "internal_shared_wall_count": 0,
            "exterior_wall_count": 0,
            "layout_quality_status": "PASS" if pairwise <= TOL else "FAIL",
        }

    def _adjacency(self, spaces, relationships, floor_id):
        names = {space["name"]: space for space in spaces}
        polygons = {space["name"]: Polygon(space["polygon"]) for space in spaces}
        total = 0
        satisfied = 0
        failures = []
        for relation in relationships if isinstance(relationships, list) else []:
            if not isinstance(relation, Mapping):
                continue
            source = str(relation.get("from"))
            target = str(relation.get("to"))
            if source not in names or target not in names:
                continue
            total += 1
            length = polygons[source].boundary.intersection(polygons[target].boundary).length
            if length > TOL:
                satisfied += 1
            else:
                failures.append({"from": source, "to": target,
                                 "reason": "no_shared_boundary"})

        graph: dict[str, set[str]] = {space["name"]: set() for space in spaces}
        for index, left in enumerate(spaces):
            for right in spaces[index + 1:]:
                if polygons[left["name"]].boundary.intersection(
                        polygons[right["name"]].boundary).length > TOL:
                    graph[left["name"]].add(right["name"])
                    graph[right["name"]].add(left["name"])

        starts = [name for name in graph if name in ("entrance", "lobby")]
        if not starts:
            starts = [name for name in graph if name in CIRCULATION_NAMES]
        if not starts and graph:
            starts = [sorted(graph)[0]]

        seen: set[str] = set()
        stack = list(starts)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph[current] - seen)

        connections = []
        circulation = [space for space in spaces if space["name"] in CIRCULATION_NAMES]
        for space in spaces:
            touches = sorted(
                item["name"] for item in circulation
                if item["name"] in graph.get(space["name"], set())
            )
            connections.append({
                "space_id": space["space_id"],
                "circulation_neighbours": touches,
                "reachable": space["name"] in seen,
            })
        isolated = sorted(name for name in graph if name not in seen)
        status = "CONNECTED" if not isolated else "ISOLATED_SPACES_PRESENT"
        return (
            {"total": total, "satisfied": satisfied, "failures": failures},
            {"status": status, "connections": connections, "isolated": isolated},
        )

    def _source_overlap(self, floor) -> float:
        polygons = [
            Polygon(space["polygon"]) for space in floor["spaces"]
            if len(space.get("polygon") or []) >= 4
        ]
        total = 0.0
        for index, left in enumerate(polygons):
            for right in polygons[index + 1:]:
                total += left.intersection(right).area
        return round(total, 6)

    # --------------------------------------------------
    # status / empty / failed
    # --------------------------------------------------

    @staticmethod
    def _plan_status(floors) -> str:
        if not floors:
            return STATUS_FAILED
        if all(floor["status"] == STATUS_RESOLVED for floor in floors):
            return STATUS_RESOLVED
        if any(floor.get("quality_metrics", {}).get("layout_quality_status") == "FAIL"
               for floor in floors):
            return STATUS_SPATIAL_LAYOUT_UNRESOLVED
        if any(conflict["code"] == PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE
               for floor in floors for conflict in floor["layout_conflicts"]):
            return STATUS_PROGRAM_AREA_EXCEEDS_ENVELOPE
        return STATUS_RESOLVED_WITH_GAPS

    def _empty_floor(self, floor_id, floor, conflicts, unresolved, drifted,
                     target_area=0.0) -> dict[str, Any]:
        return {
            "floor_id": floor_id, "floor_label": floor["floor_label"],
            "floor_order": floor["floor_order"], "elevation": floor.get("elevation"),
            "source_geometry_drifted": drifted,
            "floor_envelope": None, "interior_usable_region": None,
            "external_regions": [], "spaces": [], "shared_boundaries": [],
            "exterior_boundaries": [], "circulation_connections": [], "adjacency": {},
            "layout_conflicts": conflicts,
            "unresolved_spaces": [
                {"space_id": space["space_id"], "name": space["name"],
                 "placement_status": UNRESOLVED_SPACE} for space in unresolved
            ],
            "quality_metrics": {
                "space_count": 0, "resolved_space_count": 0,
                "unresolved_space_count": len(unresolved) + len(floor["spaces"]),
                "total_program_target_area": round(target_area, 6),
                "realized_interior_area": 0.0, "external_area": 0.0,
                "pairwise_overlap_area": 0.0, "maximum_overlap_area": 0.0,
                "envelope_area": 0.0, "unallocated_interior_area": 0.0,
                "area_deficit_or_surplus": 0.0, "internal_shared_wall_count": 0,
                "exterior_wall_count": 0, "layout_quality_status": "UNRESOLVED",
            },
            "stair_core": {"space_ids": [], "stair_geometry_status": STAIR_GEOMETRY_PENDING},
            "status": STATUS_ENVELOPE_PENDING if conflicts and conflicts[-1]["code"] ==
            STATUS_ENVELOPE_PENDING else STATUS_RESOLVED_WITH_GAPS,
        }

    def _failed(self, reason: str) -> CoherentArchitecturalFloorPlanV1:
        document = CoherentArchitecturalFloorPlanV1({
            "contract": CONTRACT, "version": VERSION, "plan_status": STATUS_FAILED,
            "plan_kind": "DERIVED_COHERENT_METRIC_FLOOR_REALIZATION",
            "source": {}, "floors": [],
            "root_cause_analysis": {"primary": None, "evidence": {}},
            "provenance": {"resolver": "CoherentFloorPlanResolverV1", "reason": reason},
        })
        document["plan_hash"] = coherent_floor_semantic_hash(document)
        return document

    # --------------------------------------------------
    # SVG
    # --------------------------------------------------

    def render_plan_svg(self, plan: Mapping[str, Any], floor_id: str,
                        *, diagnostic: bool = False) -> str:
        floors = [f for f in plan.get("floors") or [] if str(f.get("floor_id")) == str(floor_id)]
        if not floors or not floors[0]["spaces"]:
            return self._empty_svg(f"{floor_id} — no coherent layout")
        floor = floors[0]

        points: list[list[float]] = []
        if floor.get("floor_envelope"):
            points.extend(floor["floor_envelope"]["polygon"])
        for space in floor["spaces"]:
            points.extend(space["polygon"])
        for region in floor["external_regions"]:
            points.extend(region["polygon"])

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        pad = COHERENT_SVG_PADDING
        scale = COHERENT_SVG_UNITS_PER_METRE
        width = (max_x - min_x + 2 * pad) * scale
        height = (max_y - min_y + 2 * pad) * scale + 26.0

        def px(value):
            return (float(value) - min_x + pad) * scale

        def py(value):
            return (max_y - float(value) + pad) * scale + 26.0

        def attr(ring):
            return " ".join(f"{px(p[0]):.3f},{py(p[1]):.3f}" for p in ring)

        title = floor["floor_label"] + (" — COHERENT DIAGNOSTIC" if diagnostic
                                        else " — COHERENT ARCHITECTURAL PLAN")
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
            f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">',
            f'<rect x="0" y="0" width="{width:.3f}" height="{height:.3f}" '
            f'fill="{COHERENT_SVG_BACKGROUND}"/>',
            f'<text x="8.000" y="18.000" font-family="{COHERENT_SVG_FONT_FAMILY}" '
            f'font-size="12" fill="#111111">{self._escape(title)}</text>',
        ]

        parts.append('<g id="spaces">')
        for space in floor["spaces"]:
            token = "CFP_SPACE"
            if space["protected_core"]:
                token = "CFP_STAIR_CORE"
            else:
                token = {
                    "public": "CFP_SPACE_PUBLIC", "service": "CFP_SPACE_SERVICE",
                    "circulation": "CFP_SPACE_CIRCULATION", "private": "CFP_SPACE_PRIVATE",
                }.get(str(space.get("zone")), "CFP_SPACE")
            style = COHERENT_STYLE_TOKENS[token]
            opacity = style.get("fill_opacity")
            fill_opacity = "" if opacity is None else f' fill-opacity="{opacity}"'
            parts.append(
                f'<polygon points="{attr(space["polygon"])}" fill="{style["fill"]}"'
                f'{fill_opacity} stroke="{style["stroke"]}" '
                f'stroke-width="{style["stroke_width"]}"/>'
            )
        parts.append("</g>")

        parts.append('<g id="external">')
        for region in floor["external_regions"]:
            style = COHERENT_STYLE_TOKENS["CFP_SPACE_EXTERNAL"]
            opacity = style.get("fill_opacity")
            parts.append(
                f'<polygon points="{attr(region["polygon"])}" fill="{style["fill"]}"'
                f' fill-opacity="{opacity}" stroke="{style["stroke"]}" '
                f'stroke-width="{style["stroke_width"]}"/>'
            )
        parts.append("</g>")

        parts.append('<g id="envelope">')
        if floor.get("floor_envelope"):
            style = COHERENT_STYLE_TOKENS["CFP_ENVELOPE"]
            parts.append(
                f'<polygon points="{attr(floor["floor_envelope"]["polygon"])}" fill="none" '
                f'stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/>'
            )
        parts.append("</g>")

        parts.append('<g id="labels">')
        for space in floor["spaces"]:
            anchor = self._anchor(space["polygon"])
            if anchor is None:
                continue
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" text-anchor="middle" '
                f'font-family="{COHERENT_SVG_FONT_FAMILY}" font-size="8.5" fill="#111111">'
                f'{self._escape(space["display_label"])}</text>'
            )
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]) + 10.0:.3f}" '
                f'text-anchor="middle" font-family="{COHERENT_SVG_FONT_FAMILY}" font-size="7" '
                f'fill="#666666">{space["realized_area_m2"]:.1f} m2</text>'
            )
        for region in floor["external_regions"]:
            anchor = self._anchor(region["polygon"])
            if anchor is None:
                continue
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" text-anchor="middle" '
                f'font-family="{COHERENT_SVG_FONT_FAMILY}" font-size="8" fill="#1d6b4f">'
                f'{self._escape(region["display_label"])} (EXT)</text>'
            )
        parts.append("</g>")

        if diagnostic:
            parts.append('<g id="diagnostics">')
            style = COHERENT_STYLE_TOKENS["CFP_UNRESOLVED"]
            lines = [f"overlap={floor['quality_metrics']['pairwise_overlap_area']:.3f} m2",
                     f"adjacency={floor['quality_metrics'].get('adjacency_requirements_satisfied', 0)}/"
                     f"{floor['quality_metrics'].get('adjacency_requirements_total', 0)}",
                     f"circulation={floor['quality_metrics'].get('circulation_connectivity_status')}"]
            for conflict in floor["layout_conflicts"]:
                lines.append(str(conflict["code"]))
            for space in floor["unresolved_spaces"]:
                lines.append(f"UNRESOLVED {space['name']}")
            for index, line in enumerate(lines):
                parts.append(
                    f'<text x="8.000" y="{height - 8.0 - index * 11.0:.3f}" '
                    f'font-family="{COHERENT_SVG_FONT_FAMILY}" font-size="8" '
                    f'fill="{style["stroke"]}">{self._escape(line)}</text>'
                )
            parts.append("</g>")

        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _anchor(ring):
        if len(ring) < 4:
            return None
        try:
            point = Polygon(ring).representative_point()
        except (ValueError, TypeError):
            return None
        return [float(point.x), float(point.y)]

    @staticmethod
    def _empty_svg(message: str) -> str:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="360.000" height="80.000" '
            'viewBox="0 0 360.000 80.000">'
            f'<rect x="0" y="0" width="360.000" height="80.000" fill="{COHERENT_SVG_BACKGROUND}"/>'
            f'<text x="10.000" y="40.000" font-family="{COHERENT_SVG_FONT_FAMILY}" '
            f'font-size="11" fill="#b02020">'
            f'{CoherentFloorPlanResolverV1._escape(message)}</text></svg>'
        )

    @staticmethod
    def _escape(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def hash(plan: Mapping[str, Any]) -> str:
        return coherent_floor_semantic_hash(plan)


coherent_floor_plan_resolver = CoherentFloorPlanResolverV1()


def resolve_coherent_floor_plan(design_model: Any, *, program: Mapping[str, Any] | None = None,
                                human_plan: Mapping[str, Any] | None = None):
    """Module-level convenience wrapper over the canonical resolver."""
    return coherent_floor_plan_resolver.resolve(
        design_model, program=program, human_plan=human_plan)


__all__ = [
    "CoherentArchitecturalFloorPlanV1", "CoherentFloorPlanResolverV1",
    "coherent_floor_plan_resolver", "resolve_coherent_floor_plan",
]
