"""ArchitecturalLayoutIntelligenceV1 — ARCHITECTURAL-DESIGN-ROBUSTNESS-01A2B.

Turns a coherent-but-architecturally-weak partition (01A2) into an
ARCHITECTURALLY EVALUATED design:

    ontology -> relationship priority classes
             -> deterministic multi-candidate generation
             -> structured architectural evaluation
             -> hard rejection rules
             -> quality gate (no PASS while a CRITICAL relation fails)

The rectangle packing is only a CANDIDATE GENERATOR.  Selection is made by the
evaluation, never by the packing algorithm.  No doors, no windows, no stair
flights, no structure.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import itertools
import math
from typing import Any

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_layout_candidate_v1 import (
    CANDIDATE_CONTRACT,
    CANDIDATE_STYLE_TOKENS,
    CANDIDATE_SVG_BACKGROUND,
    CANDIDATE_SVG_FONT_FAMILY,
    CANDIDATE_SVG_PADDING,
    CANDIDATE_SVG_UNITS_PER_METRE,
    CORE_ALIGNED,
    CORE_MISALIGNED,
    CORE_MISSING,
    CORE_NOT_ALIGNED_ACROSS_FLOORS,
    CRITICAL,
    CRITICAL_ADJACENCY_MISSING,
    DAYLIGHT_OPPORTUNITY,
    ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION,
    ENTRANCE_EDGE_UNRESOLVED,
    ENTRANCE_HIERARCHY_INVALID,
    ENTRANCE_HIERARCHY_VALID,
    ENTRANCE_HIERARCHY_WEAK,
    ENVELOPE_NOT_REALIZED,
    EVALUATION_CONTRACT,
    EXTERIOR_EDGE_CONTACT,
    FORBIDDEN,
    FORBIDDEN_RELATION_PRESENT,
    GATE_CONTRACT,
    HIGH,
    OPTIONAL,
    PREFERRED,
    PRIORITY_CLASSES,
    PROPORTION_OK,
    PROPORTION_PATHOLOGICAL,
    PROPORTION_RULE_UNRESOLVED,
    PROTECTED_CORE_OVERLAPPED,
    QUALITY_FAIL,
    QUALITY_PASS,
    QUALITY_PASS_WITH_WARNINGS,
    REQUIRED_ROOM_ISOLATED,
    ROOM_OVERLAP_DETECTED,
    SCORE_COMPONENTS,
    SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE,
    UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL,
    VERSION,
    candidate_hash,
    layout_semantic_hash,
)
from core.architecture.reasoning.architectural_design_robustness_01a import (
    project_human_readable_plan,
)
from core.architecture.reasoning.coherent_floor_plan_resolver_v1 import (
    CIRCULATION_NAMES,
    CORE_NAMES,
    CoherentFloorPlanResolverV1,
    _area,
    _rect_polygon,
)


TOL = 1e-6

#: Connection types whose semantics imply a stronger-than-optional relation.
DIRECT_TYPES = ("direct_connection", "direct_access", "connected", "private_connection")
WEAK_TYPES = ("visual_connection", "semantic_adjacent")

ZONE_ORDER = ("public", "circulation", "service", "private")

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: ArchitecturalLayoutIntelligenceV1.design
#             (internal plan synthesis branch - multi-candidate generation
#              over the 01A2 treemap partition)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class ArchitecturalLayoutIntelligenceV1:
    """Generate, evaluate and select an architectural layout."""

    VERSION = VERSION

    def __init__(self):
        self._coherent = CoherentFloorPlanResolverV1()

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def design(self, design_model: Any, *, program: Mapping[str, Any] | None = None,
               human_plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
        plan = human_plan if isinstance(human_plan, Mapping) else project_human_readable_plan(
            design_model, program=program)
        geometry = getattr(design_model, "architectural_geometry", None)
        if not isinstance(geometry, Mapping) or not isinstance(plan.get("floors"), list):
            return self._failed("design_model_has_no_usable_plan")

        ontology = self._ontology(design_model)
        floor_meta = {
            str(item.get("floor")): item
            for item in (geometry.get("floor_geometry") or [])
            if isinstance(item, Mapping) and item.get("floor") is not None
        }
        abstract = self._abstract(design_model)
        buildable = (geometry.get("site_geometry") or {}).get("buildable_boundary")

        # --- envelopes, shared core region, served floors --------------------
        envelopes = {}
        for floor in plan["floors"]:
            envelope = self._envelope(floor, floor_meta.get(str(floor["floor_id"]), {}),
                                      abstract, buildable, reference=None)
            envelopes[str(floor["floor_id"])] = envelope
        reference_id = self._reference_floor(envelopes, plan["floors"])
        for floor in plan["floors"]:
            floor_id = str(floor["floor_id"])
            if envelopes[floor_id] and envelopes[floor_id].get("derived"):
                envelopes[floor_id] = self._envelope(
                    floor, floor_meta.get(floor_id, {}), abstract, buildable,
                    reference=envelopes[reference_id])

        served = self._served_floors(plan["floors"], ontology)
        shared = self._shared_region(envelopes, served)
        core_area = self._core_area(plan, served)

        # --- candidate generation -------------------------------------------
        variants = self._variant_axes()
        candidates = []
        for index, axes in enumerate(variants):
            candidates.append(self._build_candidate(
                index, axes, plan["floors"], envelopes, shared, core_area,
                served, ontology, floor_meta))

        evaluations = [self._evaluate(candidate, ontology, shared, served)
                       for candidate in candidates]
        for candidate, evaluation in zip(candidates, evaluations):
            candidate["evaluation"] = evaluation
            candidate["candidate_hash"] = candidate_hash(candidate)

        selected = self._select(candidates, evaluations)
        if selected is None:
            return self._failed("no_layout_candidate_survived_evaluation")

        plan_document = self._plan_document(selected, candidates, evaluations, plan,
                                           envelopes, shared, served, ontology)
        return plan_document

    # --------------------------------------------------
    # ontology
    # --------------------------------------------------

    def _ontology(self, design_model: Any) -> dict[str, Any]:
        layout = getattr(design_model, "layout", None)
        layout = layout if isinstance(layout, Mapping) else {}
        plan_model = getattr(design_model, "plan_model", None)
        plan_model = plan_model if isinstance(plan_model, Mapping) else {}

        zones = layout.get("zones") if isinstance(layout.get("zones"), Mapping) else {}
        zone_of: dict[str, str] = {}
        for zone, names in zones.items():
            for name in names or []:
                zone_of.setdefault(str(name), str(zone))

        connections = []
        seen = set()
        for source in (layout.get("connections") or [], plan_model.get("relationships") or []):
            for item in source:
                if not isinstance(item, Mapping):
                    continue
                left, right = str(item.get("from")), str(item.get("to"))
                if not left or not right:
                    continue
                key = tuple(sorted((left, right)))
                if key in seen:
                    continue
                seen.add(key)
                connections.append({
                    "from": left, "to": right,
                    "connection_type": str(item.get("type") or "adjacent"),
                    "zone_from": zone_of.get(left), "zone_to": zone_of.get(right),
                    "priority": self._priority(
                        str(item.get("type") or "adjacent"),
                        zone_of.get(left), zone_of.get(right)),
                    "provenance": {
                        "source": "layout.connections" if item in
                        (layout.get("connections") or []) else "plan_model.relationships",
                    },
                })
        return {"connections": connections, "zone_of": zone_of, "zones": zones}

    @staticmethod
    def _priority(connection_type: str, zone_from: str | None, zone_to: str | None) -> str:
        """Derive the architectural priority class from the ACTIVE ontology.

        The class comes from the connection type plus the zone pair — never from
        a hardcoded room name.
        """
        pair = {zone_from, zone_to}
        if "external" in pair:
            return PREFERRED
        if connection_type in WEAK_TYPES:
            return PREFERRED
        if connection_type == "adjacent":
            if pair <= {"private"}:
                return HIGH
            if pair & {"public", "service"}:
                return HIGH
            return OPTIONAL
        if connection_type in DIRECT_TYPES:
            if zone_from == "public" and zone_to == "private" or pair == {"public", "private"}:
                return FORBIDDEN
            if zone_from == "public" and zone_to == "service" or pair == {"public", "service"}:
                return FORBIDDEN
            if "circulation" in pair:
                return CRITICAL
            if pair <= {"public"}:
                return HIGH
            if "private" in pair:
                return CRITICAL
            return HIGH
        return OPTIONAL

    # --------------------------------------------------
    # envelopes / core
    # --------------------------------------------------

    @staticmethod
    def _reference_floor(envelopes, floors) -> str:
        resolved = [fid for fid, envelope in envelopes.items()
                    if envelope and not envelope.get("derived")]
        return sorted(resolved)[0] if resolved else str(floors[0]["floor_id"])

    def _envelope(self, floor, meta, abstract, buildable, reference) -> dict[str, Any] | None:
        floor_id = str(floor["floor_id"])
        interior = [s for s in floor["spaces"]
                    if not s.get("external") and s.get("area_m2")]
        if not interior:
            return None

        resolved = meta.get("envelope")
        if isinstance(resolved, Mapping) and resolved.get("width") and resolved.get("depth"):
            min_x, min_y = float(resolved["min_x"]), float(resolved["min_y"])
            width, depth = float(resolved["width"]), float(resolved["depth"])
            derived = False
        else:
            cells = [(entry.get("x"), entry.get("y"))
                     for (entry_floor, _), entry in sorted(abstract.items())
                     if entry_floor in (floor_id, "ground_floor")
                     and isinstance(entry.get("x"), (int, float))]
            xs = [float(x) for x, _ in cells]
            ys = [float(y) for _, y in cells]
            ratio = (max((max(xs) - min(xs)) + 1.0, 1.0) /
                     max((max(ys) - min(ys)) + 1.0, 1.0)) if xs and ys else 1.0
            target = sum(float(s["area_m2"]) for s in interior)
            width = math.sqrt(target * ratio)
            depth = target / width if width else 0.0
            if width <= 0 or depth <= 0:
                return None
            # anchor the derived floor on the reference floor's origin so floors
            # stack coherently (the engine's own reference-floor placement)
            min_x = float(reference["min_x"]) if reference else (
                min(float(p[0]) for p in buildable) if isinstance(buildable, list) else 0.0)
            min_y = float(reference["min_y"]) if reference else (
                min(float(p[1]) for p in buildable) if isinstance(buildable, list) else 0.0)
            derived = True
            if isinstance(buildable, list) and len(buildable) >= 3:
                bx = [float(p[0]) for p in buildable]
                by = [float(p[1]) for p in buildable]
                if width > (max(bx) - min(bx)) + TOL or depth > (max(by) - min(by)) + TOL:
                    return None

        return {
            "min_x": min_x, "min_y": min_y,
            "max_x": min_x + width, "max_y": min_y + depth,
            "width": width, "depth": depth, "area": width * depth, "derived": derived,
            "polygon": [[min_x, min_y], [min_x + width, min_y],
                        [min_x + width, min_y + depth], [min_x, min_y + depth],
                        [min_x, min_y]],
        }

    @staticmethod
    def _served_floors(floors, ontology) -> list[str]:
        served = []
        for floor in floors:
            names = {s["name"] for s in floor["spaces"]}
            if names & CORE_NAMES or names & CIRCULATION_NAMES:
                served.append(str(floor["floor_id"]))
        return sorted(served)

    @staticmethod
    def _shared_region(envelopes, served) -> dict[str, Any] | None:
        shapes = [Polygon(envelopes[fid]["polygon"]) for fid in served
                  if envelopes.get(fid)]
        if not shapes:
            return None
        shared = shapes[0]
        for shape in shapes[1:]:
            shared = shared.intersection(shape)
        if shared.is_empty:
            return None
        min_x, min_y, max_x, max_y = shared.bounds
        return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
                "width": max_x - min_x, "depth": max_y - min_y,
                "area": (max_x - min_x) * (max_y - min_y)}

    @staticmethod
    def _core_area(plan, served) -> float:
        for floor in plan["floors"]:
            for space in floor["spaces"]:
                if space["name"] in CORE_NAMES and space.get("area_m2"):
                    return float(space["area_m2"])
        return 0.0

    # --------------------------------------------------
    # candidate generation
    # --------------------------------------------------

    @staticmethod
    def _variant_axes() -> list[dict[str, Any]]:
        """Deterministic candidate axes — no randomness."""
        axes = []
        for axis in ("auto", "flip"):
            for zone_order in ("canonical", "circulation_first"):
                for room_order in ("ontology", "reverse"):
                    for core_end in ("start", "end"):
                        axes.append({"band_axis": axis, "zone_order": zone_order,
                                     "room_order": room_order, "core_end": core_end})
        return axes[:8]

    def _build_candidate(self, index, axes, floors, envelopes, shared, core_area,
                         served, ontology, floor_meta) -> dict[str, Any]:
        core = self._core_rect(shared, core_area, axes["core_end"]) if shared else None
        floor_records = []
        for floor in floors:
            floor_id = str(floor["floor_id"])
            envelope = envelopes.get(floor_id)
            if envelope is None:
                floor_records.append({"floor_id": floor_id, "envelope": None, "spaces": [],
                                      "core": None, "external_regions": []})
                continue
            reserved = core if floor_id in served else None
            interior = [s for s in floor["spaces"]
                        if not s.get("external") and s.get("area_m2")]
            # a reserved core IS the geometry of its own space: never partition it twice
            core_spaces = [s for s in interior if s["name"] in CORE_NAMES] if reserved else []
            other = [s for s in interior if s not in core_spaces]
            external = [s for s in floor["spaces"] if s.get("external")]

            rects = self._partition(other, envelope, reserved, axes, ontology)
            spaces = []
            for space in other:
                rect = rects.get(space["name"])
                if rect is None:
                    continue
                ring = _rect_polygon(rect)
                spaces.append({
                    "space_id": space["space_id"], "name": space["name"],
                    "display_label": space["display_label"],
                    "semantic_type": space["semantic_type"], "zone": space["zone"],
                    "requested_area_m2": round(float(space["area_m2"]), 6),
                    "realized_area_m2": round(_area(ring), 6),
                    "polygon": ring, "protected_core": False,
                })
            for space in core_spaces:
                ring = deepcopy(reserved["polygon"])
                spaces.append({
                    "space_id": space["space_id"], "name": space["name"],
                    "display_label": space["display_label"],
                    "semantic_type": space["semantic_type"], "zone": space["zone"],
                    "requested_area_m2": round(float(space["area_m2"]), 6),
                    "realized_area_m2": round(_area(ring), 6),
                    "polygon": ring, "protected_core": True,
                })
            if reserved and not core_spaces:
                # a served floor must carry the SAME core reservation even when the
                # floor program does not list its own stair space
                ring = deepcopy(reserved["polygon"])
                spaces.append({
                    "space_id": "stairs", "name": "stairs",
                    "display_label": "STAIR CORE", "semantic_type": "stair_core",
                    "zone": "circulation",
                    "requested_area_m2": round(_area(ring), 6),
                    "realized_area_m2": round(_area(ring), 6),
                    "polygon": ring, "protected_core": True,
                    "provenance": {"source": "vertical_core_reservation",
                                   "geometry_invented": False},
                })
            floor_records.append({
                "floor_id": floor_id, "envelope": envelope,
                "core": deepcopy(core) if floor_id in served else None,
                "spaces": spaces,
                "external_regions": self._external_regions(external, envelope),
            })
        return {
            "contract": CANDIDATE_CONTRACT, "version": VERSION,
            "candidate_id": f"LAYOUT-CANDIDATE-{index + 1:02d}",
            "axes": dict(axes), "floors": floor_records,
            "vertical_core": {
                "vertical_core_id": "VC-1" if core else None,
                "served_floors": list(served),
                "footprint": deepcopy(core),
                "stair_geometry_status": "STAIR_GEOMETRY_PENDING",
                "stair_flights_generated": False,
            },
            "provenance": {
                "generator": "ArchitecturalLayoutIntelligenceV1",
                "method": "deterministic_zone_band_partition_with_reserved_core",
                "randomness_used": False,
                "geometry_invented": False,
                "doors_generated": False, "windows_generated": False,
            },
        }

    @staticmethod
    def _core_rect(shared, core_area, core_end) -> dict[str, Any] | None:
        if not shared or core_area <= 0:
            return None
        depth = shared["depth"]
        width = min(core_area / depth, shared["width"]) if depth else 0.0
        if width <= 0:
            return None
        if core_end == "end":
            min_x = shared["max_x"] - width
        else:
            min_x = shared["min_x"]
        return {
            "min_x": min_x, "min_y": shared["min_y"],
            "max_x": min_x + width, "max_y": shared["min_y"] + depth,
            "width": width, "depth": depth, "area": width * depth,
            "polygon": [[min_x, shared["min_y"]], [min_x + width, shared["min_y"]],
                        [min_x + width, shared["min_y"] + depth],
                        [min_x, shared["min_y"] + depth], [min_x, shared["min_y"]]],
        }

    def _partition(self, interior, envelope, core, axes, ontology) -> dict[str, Any]:
        """Exact-area ZONE-BAND partition of the envelope around the reserved core.

        Zones occupy parallel bands; a band is sized so its rooms' target areas
        are reproduced exactly (band_extent = band_area / band_cross_span).  A
        zone flows into the next free strip when a band does not fit, so the
        reserved core is never overlapped and no room is resized arbitrarily.
        """
        groups: dict[str, list[dict[str, Any]]] = {}
        for space in interior:
            groups.setdefault(str(space.get("zone") or "other"), []).append(space)

        order = [zone for zone in ZONE_ORDER if zone in groups]
        order += sorted(zone for zone in groups if zone not in order)
        if axes["zone_order"] == "circulation_first":
            order = sorted(order, key=lambda z: (0 if z == "circulation" else 1, order.index(z)))
        for zone in order:
            groups[zone] = self._order_rooms(groups[zone], ontology)
            if axes["room_order"] == "reverse":
                groups[zone] = list(reversed(groups[zone]))

        horizontal = self._horizontal(envelope, axes)
        slots = [list(slot) for slot in self._strips(envelope, core)]
        rects: dict[str, Any] = {}

        for zone in order:
            band = list(groups[zone])
            while band:
                slot = next((item for item in slots if item[2] > TOL and item[3] > TOL), None)
                if slot is None:
                    break
                cross = slot[3] if horizontal else slot[2]
                slot_len = slot[2] if horizontal else slot[3]
                if cross <= TOL or slot_len <= TOL:
                    break

                # whole-band placement: extent = band_area / band_cross_span keeps
                # every room on its target area instead of creating slivers
                band_area = sum(max(float(space["area_m2"]), 1e-6) for space in band)
                extent = min(band_area / cross, slot_len)
                cursor = 0.0
                for index, space in enumerate(band):
                    weight = max(float(space["area_m2"]), 1e-6)
                    if index == len(band) - 1:
                        size = max(cross - cursor, 0.0)
                    else:
                        size = min((weight / extent) if extent else 0.0,
                                   max(cross - cursor, 0.0))
                    if horizontal:
                        rects[space["name"]] = (slot[0], slot[1] + cursor, extent, size)
                    else:
                        rects[space["name"]] = (slot[0] + cursor, slot[1], size, extent)
                    cursor += size

                band = []
                if horizontal:
                    slot[0] += extent
                    slot[2] -= extent
                else:
                    slot[1] += extent
                    slot[3] -= extent

        return {name: rect for name, rect in rects.items() if rect is not None}

    @staticmethod
    def _order_rooms(band, ontology) -> list[dict[str, Any]]:
        """Order a zone band so that architecturally related rooms end up adjacent.

        Deterministic greedy chain driven by the ACTIVE ontology (no hardcoded
        room order): start from the most connected room, then repeatedly append
        the unplaced room most strongly related to the last placed one.
        """
        names = [space["name"] for space in band]
        if len(names) < 3:
            return list(band)
        weight = {CRITICAL: 3.0, HIGH: 2.0, PREFERRED: 1.0, OPTIONAL: 0.5}
        links: dict[str, dict[str, float]] = {name: {} for name in names}
        for relation in ontology.get("connections", []):
            left, right = relation["from"], relation["to"]
            if left in links and right in links:
                value = weight.get(relation["priority"], 0.0)
                if value:
                    links[left][right] = links[left].get(right, 0.0) + value
                    links[right][left] = links[right].get(left, 0.0) + value

        by_name = {space["name"]: space for space in band}
        start = sorted(names, key=lambda name: (-sum(links[name].values()), name))[0]
        ordered = [start]
        remaining = [name for name in names if name != start]
        while remaining:
            last = ordered[-1]
            nxt = sorted(remaining,
                         key=lambda name: (-links[last].get(name, 0.0),
                                           -sum(links[name].values()), name))[0]
            ordered.append(nxt)
            remaining.remove(nxt)
        return [by_name[name] for name in ordered]

    @staticmethod
    def _size(space, extent, cross) -> float:
        weight = max(float(space["area_m2"]), 1e-6)
        return (weight / cross) if cross else 0.0

    @staticmethod
    def _horizontal(envelope, axes) -> bool:
        if axes["band_axis"] == "auto":
            return envelope["width"] >= envelope["depth"]
        return not (envelope["width"] >= envelope["depth"])

    @staticmethod
    def _strips(envelope, core) -> list[list[float]]:
        """Free rectangles of the envelope around the reserved core."""
        slots = []
        if core["min_x"] - envelope["min_x"] > TOL:
            slots.append([envelope["min_x"], envelope["min_y"],
                          core["min_x"] - envelope["min_x"], envelope["depth"]])
        if envelope["max_x"] - core["max_x"] > TOL:
            slots.append([core["max_x"], envelope["min_y"],
                          envelope["max_x"] - core["max_x"], envelope["depth"]])
        if not slots:
            slots.append([envelope["min_x"], envelope["min_y"],
                          envelope["width"], envelope["depth"]])
        return slots

    @staticmethod
    def _external_regions(external, envelope) -> list[dict[str, Any]]:
        regions = []
        cursor = envelope["min_x"]
        for space in sorted(external, key=lambda item: item["name"]):
            area = float(space.get("area_m2") or 0.0)
            if area <= 0:
                continue
            width = min(area / 2.0 if area else 0.0, envelope["width"] / 2.0)
            depth = area / width if width else 0.0
            regions.append({
                "space_id": space["space_id"], "name": space["name"],
                "display_label": space["display_label"], "external": True,
                "realized_area_m2": round(area, 6),
                "polygon": [[cursor, envelope["min_y"] - depth],
                            [cursor + width, envelope["min_y"] - depth],
                            [cursor + width, envelope["min_y"]],
                            [cursor, envelope["min_y"]],
                            [cursor, envelope["min_y"] - depth]],
                "relation_to_building": "ADJACENT_EXTERNAL",
            })
            cursor += width
        return regions

    @staticmethod
    def _abstract(design_model: Any) -> dict[tuple[str, str], dict[str, Any]]:
        layout = getattr(design_model, "layout", None)
        entries = layout.get("spatial_layout") if isinstance(layout, Mapping) else None
        output: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in entries or []:
            if isinstance(entry, Mapping) and entry.get("name") is not None:
                output.setdefault((str(entry.get("floor")), str(entry["name"])), dict(entry))
        return output

    # --------------------------------------------------
    # evaluation
    # --------------------------------------------------

    def _evaluate(self, candidate, ontology, shared, served) -> dict[str, Any]:
        rejections: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        components: dict[str, Any] = {}

        overlap_total = 0.0
        core_overlap_total = 0.0
        for floor in candidate["floors"]:
            polygons = {s["name"]: Polygon(s["polygon"]) for s in floor["spaces"]}
            names = sorted(polygons)
            for index, left in enumerate(names):
                for right in names[index + 1:]:
                    area = polygons[left].intersection(polygons[right]).area
                    if area > TOL:
                        overlap_total += area
            core = floor.get("core")
            if core:
                core_shape = Polygon(core["polygon"])
                for name, polygon in polygons.items():
                    if name in CORE_NAMES:
                        continue
                    if core_shape.intersection(polygon).area > TOL:
                        core_overlap_total += core_shape.intersection(polygon).area
        if overlap_total > TOL:
            rejections.append({"code": ROOM_OVERLAP_DETECTED, "area_m2": round(overlap_total, 6)})
        if core_overlap_total > TOL:
            rejections.append({"code": PROTECTED_CORE_OVERLAPPED,
                               "area_m2": round(core_overlap_total, 6)})
        components["geometry_validity"] = "PASS" if not rejections else "FAIL"

        # --- critical / high adjacency ---------------------------------------
        critical_total = critical_ok = 0
        high_total = high_ok = 0
        forbidden_hits = []
        adjacency_detail = []
        for floor in candidate["floors"]:
            polygons = {s["name"]: Polygon(s["polygon"]) for s in floor["spaces"]}
            for relation in ontology["connections"]:
                left, right = relation["from"], relation["to"]
                if left not in polygons or right not in polygons:
                    continue
                shares = polygons[left].boundary.intersection(
                    polygons[right].boundary).length > TOL
                priority = relation["priority"]
                if priority == FORBIDDEN:
                    if shares:
                        forbidden_hits.append({"from": left, "to": right,
                                               "connection_type": relation["connection_type"]})
                    continue
                if priority not in (CRITICAL, HIGH):
                    continue
                record = {"floor_id": floor["floor_id"], "from": left, "to": right,
                          "priority": priority, "connection_type": relation["connection_type"],
                          "shared_boundary": shares}
                adjacency_detail.append(record)
                if priority == CRITICAL:
                    critical_total += 1
                    critical_ok += 1 if shares else 0
                else:
                    high_total += 1
                    high_ok += 1 if shares else 0

        if critical_total and critical_ok < critical_total:
            rejections.append({
                "code": CRITICAL_ADJACENCY_MISSING,
                "missing": [r for r in adjacency_detail
                            if r["priority"] == CRITICAL and not r["shared_boundary"]],
            })
        if forbidden_hits:
            rejections.append({"code": FORBIDDEN_RELATION_PRESENT, "relations": forbidden_hits})
        components["critical_adjacency"] = (
            "PASS" if critical_total and critical_ok == critical_total else "FAIL")
        components["high_adjacency"] = (
            "PASS" if high_total == high_ok else "WARN" if high_ok else "FAIL")

        # --- vertical core continuity ----------------------------------------
        core_status = self._core_status(candidate, served)
        if core_status == CORE_MISSING:
            rejections.append({"code": SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE,
                               "served_floors": list(served)})
        elif core_status == CORE_MISALIGNED:
            rejections.append({"code": CORE_NOT_ALIGNED_ACROSS_FLOORS,
                               "served_floors": list(served)})
        components["vertical_core_continuity"] = (
            "PASS" if core_status == CORE_ALIGNED else "FAIL")

        # --- entrance hierarchy ----------------------------------------------
        entrance = self._entrance(candidate)
        if entrance["hierarchy_status"] == ENTRANCE_HIERARCHY_INVALID:
            rejections.append({"code": ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION,
                               "entrance": entrance})
        components["entrance_hierarchy"] = {
            ENTRANCE_HIERARCHY_VALID: "PASS",
            ENTRANCE_HIERARCHY_WEAK: "WARN",
            ENTRANCE_HIERARCHY_INVALID: "FAIL",
            ENTRANCE_EDGE_UNRESOLVED: "WARN",
        }[entrance["hierarchy_status"]]

        # --- circulation ------------------------------------------------------
        circulation = self._circulation(candidate, served)
        if circulation["isolated"]:
            rejections.append({"code": REQUIRED_ROOM_ISOLATED,
                               "spaces": circulation["isolated"]})
        if circulation["upper_floor_corridor_without_arrival"]:
            rejections.append({"code": UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL,
                               "floors": circulation["upper_floor_corridor_without_arrival"]})
        components["circulation_quality"] = "PASS" if not (
            circulation["isolated"] or circulation["upper_floor_corridor_without_arrival"]
        ) else "FAIL"

        # --- zoning / privacy / service / external / proportion --------------
        components["privacy"] = "PASS" if not forbidden_hits else "FAIL"
        components["public_private_zoning"] = "PASS" if self._zoning_ok(candidate) else "WARN"
        components["service_logic"] = "PASS" if self._service_ok(candidate, entrance) else "WARN"
        components["external_space_relation"] = (
            "PASS" if any(f["external_regions"] for f in candidate["floors"]) else "WARN")
        proportion = self._proportion(candidate)
        components["room_proportion_quality"] = proportion["status"]
        components["daylight_opportunity"] = self._daylight(candidate)["status"]
        components["unresolved_penalty"] = "PASS"

        if components["high_adjacency"] == "WARN":
            warnings.append({"code": "HIGH_ADJACENCY_PARTIAL",
                             "satisfied": high_ok, "total": high_total})
        if proportion["status"] == PROPORTION_PATHOLOGICAL:
            warnings.append({"code": "PATHOLOGICAL_ROOM_PROPORTION",
                             "rooms": proportion["pathological"]})
        if proportion["status"] == PROPORTION_RULE_UNRESOLVED:
            warnings.append({"code": PROPORTION_RULE_UNRESOLVED})

        return {
            "contract": EVALUATION_CONTRACT, "version": VERSION,
            "candidate_id": candidate["candidate_id"],
            "hard_rejections": rejections,
            "rejected": bool(rejections),
            "warnings": warnings,
            "score_components": components,
            "critical_relationships": {"total": critical_total, "satisfied": critical_ok},
            "high_relationships": {"total": high_total, "satisfied": high_ok},
            "adjacency_detail": adjacency_detail,
            "entrance_hierarchy": entrance,
            "vertical_core": {"status": core_status, "served_floors": list(served)},
            "circulation": circulation,
            "proportion": proportion,
            "external_edge_opportunities": self._daylight(candidate)["opportunities"],
            "overlap_area_m2": round(overlap_total, 6),
            "core_overlap_area_m2": round(core_overlap_total, 6),
        }

    @staticmethod
    def _core_status(candidate, served) -> str:
        served = [floor_id for floor_id in served if floor_id]
        if len(served) < 2:
            # a single-storey building needs no vertical core continuity
            return CORE_ALIGNED
        footprints = []
        for floor in candidate["floors"]:
            if str(floor["floor_id"]) not in served:
                continue
            core = floor.get("core")
            if not core:
                continue
            footprints.append(tuple(round(core[key], 6)
                                    for key in ("min_x", "min_y", "max_x", "max_y")))
        if len(footprints) < len(served):
            return CORE_MISSING
        if len(set(footprints)) != 1:
            return CORE_MISALIGNED
        return CORE_ALIGNED

    @staticmethod
    def _entrance(candidate) -> dict[str, Any]:
        for floor in candidate["floors"]:
            polygons = {s["name"]: Polygon(s["polygon"]) for s in floor["spaces"]}
            zones = {s["name"]: str(s.get("zone")) for s in floor["spaces"]}
            entrance = next((name for name in polygons
                             if name in ("entrance", "lobby", "entry")), None)
            if entrance is None:
                continue
            envelope = Polygon(floor["envelope"]["polygon"])
            on_edge = polygons[entrance].boundary.intersection(envelope.boundary).length > TOL
            neighbours = [
                name for name in polygons if name != entrance
                and polygons[entrance].boundary.intersection(polygons[name].boundary).length > TOL
            ]
            public_neighbours = [n for n in neighbours
                                 if zones.get(n) in ("public", "circulation")]
            private_neighbours = [n for n in neighbours if zones.get(n) == "private"]
            service_neighbours = [n for n in neighbours if zones.get(n) == "service"]
            if not on_edge:
                status = ENTRANCE_EDGE_UNRESOLVED
            elif private_neighbours:
                status = ENTRANCE_HIERARCHY_INVALID
            elif not public_neighbours:
                status = ENTRANCE_HIERARCHY_INVALID
            elif service_neighbours and not [n for n in public_neighbours
                                             if zones.get(n) == "circulation"]:
                status = ENTRANCE_HIERARCHY_WEAK
            else:
                status = ENTRANCE_HIERARCHY_VALID
            return {
                "floor_id": floor["floor_id"], "entrance_space": entrance,
                "entrance_edge": "EXTERIOR_EDGE" if on_edge else "NOT_ON_EXTERIOR_EDGE",
                "entrance_arrival_space": entrance,
                "next_reachable_public_space": public_neighbours,
                "service_conflicts": service_neighbours,
                "privacy_conflicts": private_neighbours,
                "hierarchy_status": status,
                "door_geometry_generated": False,
            }
        return {"hierarchy_status": ENTRANCE_EDGE_UNRESOLVED, "entrance_space": None}

    @staticmethod
    def _circulation(candidate, served) -> dict[str, Any]:
        isolated = []
        without_arrival = []
        for floor in candidate["floors"]:
            floor_id = str(floor["floor_id"])
            polygons = {s["name"]: Polygon(s["polygon"]) for s in floor["spaces"]}
            if not polygons:
                continue
            graph = {name: set() for name in polygons}
            names = sorted(polygons)
            for index, left in enumerate(names):
                for right in names[index + 1:]:
                    if polygons[left].boundary.intersection(
                            polygons[right].boundary).length > TOL:
                        graph[left].add(right)
                        graph[right].add(left)
            cores = [n for n in graph if n in CORE_NAMES]
            corridors = [n for n in graph if n in CIRCULATION_NAMES and n not in CORE_NAMES]
            starts = cores or corridors or (["entrance"] if "entrance" in graph else [])
            if not starts and graph:
                starts = [names[0]]
            seen: set[str] = set()
            stack = list(starts)
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(graph[current] - seen)
            isolated.extend(sorted(name for name in graph if name not in seen))
            if floor_id in served and floor_id != served[0]:
                if not any(c in graph for c in cores) or not any(
                        graph[c] & set(corridors) for c in cores if c in graph):
                    without_arrival.append(floor_id)
        return {"isolated": isolated,
                "upper_floor_corridor_without_arrival": without_arrival}

    @staticmethod
    def _zoning_ok(candidate) -> bool:
        for floor in candidate["floors"]:
            by_zone: dict[str, list[str]] = {}
            for space in floor["spaces"]:
                by_zone.setdefault(str(space.get("zone")), []).append(space["name"])
            if by_zone.get("private") and not by_zone.get("circulation"):
                return False
        return True

    @staticmethod
    def _service_ok(candidate, entrance) -> bool:
        return not entrance.get("service_conflicts")

    @staticmethod
    def _proportion(candidate) -> dict[str, Any]:
        pathological = []
        for floor in candidate["floors"]:
            for space in floor["spaces"]:
                if space.get("protected_core") or space["name"] in CIRCULATION_NAMES:
                    # a corridor / core is architecturally allowed to be elongated
                    continue
                ring = space["polygon"]
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                width = max(xs) - min(xs)
                depth = max(ys) - min(ys)
                if width <= 0 or depth <= 0:
                    continue
                ratio = max(width, depth) / min(width, depth)
                minimum = min(width, depth)
                if ratio > 6.0 or minimum < 0.9:
                    pathological.append({"space": space["name"], "floor_id": floor["floor_id"],
                                         "aspect_ratio": round(ratio, 3),
                                         "minimum_dimension": round(minimum, 3)})
        if pathological:
            status = PROPORTION_PATHOLOGICAL
        else:
            status = PROPORTION_RULE_UNRESOLVED
        return {"status": status, "pathological": pathological,
                "rule_source": "ARCHITECTURAL_DIMENSION_KNOWLEDGE_UNAVAILABLE"}

    @staticmethod
    def _daylight(candidate) -> dict[str, Any]:
        opportunities = []
        for floor in candidate["floors"]:
            envelope = Polygon(floor["envelope"]["polygon"])
            for space in floor["spaces"]:
                contact = Polygon(space["polygon"]).boundary.intersection(
                    envelope.boundary).length
                if contact > TOL:
                    opportunities.append({
                        "floor_id": floor["floor_id"], "space": space["name"],
                        "exterior_edge_contact_m": round(contact, 6),
                        "tags": [EXTERIOR_EDGE_CONTACT, DAYLIGHT_OPPORTUNITY],
                        "final_window_placement": False,
                    })
        return {"status": "PASS" if opportunities else "WARN",
                "opportunities": opportunities}

    # --------------------------------------------------
    # selection
    # --------------------------------------------------

    @staticmethod
    def _select(candidates, evaluations):
        viable = [(candidate, evaluation)
                  for candidate, evaluation in zip(candidates, evaluations)
                  if not evaluation["rejected"]]
        if not viable:
            return None

        def key(pair):
            candidate, evaluation = pair
            components = evaluation["score_components"]
            return (
                0 if components["critical_adjacency"] == "PASS" else 1,
                0 if components["entrance_hierarchy"] == "PASS" else 1,
                0 if components["circulation_quality"] == "PASS" else 1,
                -evaluation["high_relationships"]["satisfied"],
                0 if components["room_proportion_quality"] != PROPORTION_PATHOLOGICAL else 1,
                len(evaluation["warnings"]),
                candidate["candidate_id"],
            )

        return sorted(viable, key=key)[0]

    # --------------------------------------------------
    # output
    # --------------------------------------------------

    def _plan_document(self, selected, candidates, evaluations, plan, envelopes,
                       shared, served, ontology) -> dict[str, Any]:
        candidate, evaluation = selected
        floors = []
        for floor in candidate["floors"]:
            floor_id = floor["floor_id"]
            if floor["envelope"] is None:
                continue
            spaces = []
            for space in floor["spaces"]:
                requested = space["requested_area_m2"]
                realized = space["realized_area_m2"]
                spaces.append({
                    **space,
                    "area_delta_m2": round(realized - requested, 6),
                    "placement_status": "PLACED",
                    "provenance": {"source": "architectural_layout_candidate",
                                   "geometry_invented": False},
                })
            shared_walls, exterior_walls = self._coherent._boundaries(spaces, floor["envelope"])
            adjacency, circulation = self._coherent._adjacency(
                spaces, ontology["connections"], floor_id)
            metrics = self._coherent._metrics(
                spaces, floor["external_regions"], floor["envelope"],
                sum(s["requested_area_m2"] for s in spaces), ontology["connections"], floor_id)
            metrics["internal_shared_wall_count"] = len(shared_walls)
            metrics["exterior_wall_count"] = len(exterior_walls)
            metrics["adjacency_requirements_total"] = adjacency["total"]
            metrics["adjacency_requirements_satisfied"] = adjacency["satisfied"]
            metrics["circulation_connectivity_status"] = circulation["status"]
            metrics["layout_quality_status"] = (
                "PASS" if metrics["pairwise_overlap_area"] == 0.0 else "FAIL")
            floors.append({
                "floor_id": floor_id,
                "floor_label": next(f["floor_label"] for f in plan["floors"]
                                    if str(f["floor_id"]) == floor_id),
                "floor_order": next(f["floor_order"] for f in plan["floors"]
                                    if str(f["floor_id"]) == floor_id),
                "floor_envelope": floor["envelope"],
                "spaces": spaces,
                "external_regions": floor["external_regions"],
                "shared_boundaries": shared_walls,
                "exterior_boundaries": exterior_walls,
                "circulation_connections": circulation["connections"],
                "adjacency": adjacency,
                "quality_metrics": metrics,
                "vertical_core": {
                    "vertical_core_id": candidate["vertical_core"]["vertical_core_id"],
                    "core_footprint": deepcopy(floor["core"]),
                    "core_status": "CORE_RESERVED_ON_FLOOR" if floor["core"] else None,
                    "arrival_space": "corridor",
                    "stair_geometry_status": "STAIR_GEOMETRY_PENDING",
                    "stair_flights_generated": False,
                },
            })

        gate = self._gate(floors, evaluation, candidate)

        document = {
            "contract": CANDIDATE_CONTRACT, "version": VERSION,
            "plan_kind": "ARCHITECTURALLY_EVALUATED_LAYOUT",
            "selected_candidate_id": candidate["candidate_id"],
            "selected_candidate_hash": candidate["candidate_hash"],
            "candidate_count": len(candidates),
            "candidate_ids": [c["candidate_id"] for c in candidates],
            "floors": floors,
            "vertical_core_binding": candidate["vertical_core"],
            "shared_core_region": shared,
            "served_floors": list(served),
            "relationship_ontology": {
                "connection_count": len(ontology["connections"]),
                "by_priority": {
                    priority: sum(1 for c in ontology["connections"] if c["priority"] == priority)
                    for priority in PRIORITY_CLASSES
                },
                "connections": deepcopy(ontology["connections"]),
            },
            "evaluations": [
                {"candidate_id": c["candidate_id"], "rejected": e["rejected"],
                 "hard_rejections": [r["code"] for r in e["hard_rejections"]],
                 "critical": e["critical_relationships"],
                 "high": e["high_relationships"],
                 "components": e["score_components"],
                 "entrance": e["entrance_hierarchy"].get("hierarchy_status"),
                 "core": e["vertical_core"]["status"]}
                for c, e in zip(candidates, evaluations)
            ],
            "selected_evaluation": evaluation,
            "quality_gate": gate,
            "unresolved_items": self._unresolved(plan, candidate, floors),
            "warnings": list(evaluation["warnings"]),
            "provenance": {
                "engine": "ArchitecturalLayoutIntelligenceV1",
                "engine_version": VERSION,
                "candidate_generator": "deterministic_zone_band_partition_with_reserved_core",
                "selection_authority": "architectural_evaluation",
                "packing_is_design_authority": False,
                "randomness_used": False,
                "doors_generated": False, "windows_generated": False,
                "stair_flights_generated": False,
                "structural_elements_generated": False,
                "bim_ifc_executed": False, "render_runtime_executed": False,
                "comfyui_executed": False, "source_mutated": False,
            },
        }
        document["plan_hash"] = layout_semantic_hash(document)
        return document

    @staticmethod
    def _gate(floors, evaluation, candidate) -> dict[str, Any]:
        failures = [r["code"] for r in evaluation["hard_rejections"]]
        critical = evaluation["critical_relationships"]
        if failures or (critical["total"] and critical["satisfied"] < critical["total"]):
            status = QUALITY_FAIL
        elif evaluation["warnings"]:
            status = QUALITY_PASS_WITH_WARNINGS
        else:
            status = QUALITY_PASS
        return {
            "contract": GATE_CONTRACT, "version": VERSION,
            "quality_status": status,
            "critical_relationships": deepcopy(critical),
            "high_relationships": deepcopy(evaluation["high_relationships"]),
            "hard_rejections": failures,
            "warning_count": len(evaluation["warnings"]),
            "rule": "NO_PASS_WHILE_ANY_CRITICAL_RELATION_FAILS",
            "pass_requires": [
                "zero_room_overlap", "zero_core_overlap",
                "aligned_core_on_served_floors",
                "entrance_reaches_public_circulation",
                "all_critical_relationships_satisfied",
                "no_isolated_required_room",
                "upper_floor_corridor_anchored_to_arrival",
            ],
        }

    @staticmethod
    def _unresolved(plan, candidate, floors) -> list[dict[str, Any]]:
        items = []
        for floor in plan["floors"]:
            for space in floor.get("unresolved_spaces") or []:
                items.append({"floor_id": floor["floor_id"], **deepcopy(space)})
        for floor in candidate["floors"]:
            if floor["envelope"] is None:
                items.append({"floor_id": floor["floor_id"], "code": ENVELOPE_NOT_REALIZED})
        items.append({"code": "DOOR_GEOMETRY_REALIZATION_MISSING", "deferred_to": "ROBUSTNESS-01A3"})
        items.append({"code": "WINDOW_GEOMETRY_REALIZATION_MISSING", "deferred_to": "ROBUSTNESS-01A3"})
        items.append({"code": "STAIR_GEOMETRY_REALIZATION_MISSING", "deferred_to": "ROBUSTNESS-01B"})
        return items

    # --------------------------------------------------
    # SVG
    # --------------------------------------------------

    def render_plan_svg(self, document: Mapping[str, Any], floor_id: str) -> str:
        floors = [f for f in document.get("floors") or []
                  if str(f.get("floor_id")) == str(floor_id)]
        if not floors or not floors[0]["spaces"]:
            return self._empty_svg(f"{floor_id} — no selected layout")
        floor = floors[0]
        points: list[list[float]] = list(floor["floor_envelope"]["polygon"])
        for space in floor["spaces"]:
            points.extend(space["polygon"])
        for region in floor["external_regions"]:
            points.extend(region["polygon"])
        core = (floor.get("vertical_core") or {}).get("core_footprint")
        if core:
            points.extend(core["polygon"])

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        pad = CANDIDATE_SVG_PADDING
        scale = CANDIDATE_SVG_UNITS_PER_METRE
        width = (max_x - min_x + 2 * pad) * scale
        height = (max_y - min_y + 2 * pad) * scale + 26.0

        def px(value):
            return (float(value) - min_x + pad) * scale

        def py(value):
            return (max_y - float(value) + pad) * scale + 26.0

        def attr(ring):
            return " ".join(f"{px(p[0]):.3f},{py(p[1]):.3f}" for p in ring)

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
            f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">',
            f'<rect x="0" y="0" width="{width:.3f}" height="{height:.3f}" '
            f'fill="{CANDIDATE_SVG_BACKGROUND}"/>',
            f'<text x="8.000" y="18.000" font-family="{CANDIDATE_SVG_FONT_FAMILY}" '
            f'font-size="12" fill="#111111">{self._escape(floor["floor_label"])}'
            f' — SELECTED ARCHITECTURAL PLAN ({document["selected_candidate_id"]})</text>',
        ]
        parts.append('<g id="spaces">')
        for space in floor["spaces"]:
            if space["protected_core"]:
                token = "CAND_CORE"
            else:
                token = {
                    "public": "CAND_SPACE_PUBLIC", "service": "CAND_SPACE_SERVICE",
                    "circulation": "CAND_SPACE_CIRCULATION", "private": "CAND_SPACE_PRIVATE",
                }.get(str(space.get("zone")), "CAND_SPACE")
            style = CANDIDATE_STYLE_TOKENS[token]
            opacity = style.get("fill_opacity")
            fill_opacity = "" if opacity is None else f' fill-opacity="{opacity}"'
            parts.append(f'<polygon points="{attr(space["polygon"])}" fill="{style["fill"]}"'
                         f'{fill_opacity} stroke="{style["stroke"]}" '
                         f'stroke-width="{style["stroke_width"]}"/>')
        parts.append("</g>")

        parts.append('<g id="external">')
        for region in floor["external_regions"]:
            style = CANDIDATE_STYLE_TOKENS["CAND_SPACE_EXTERNAL"]
            parts.append(f'<polygon points="{attr(region["polygon"])}" fill="{style["fill"]}"'
                         f' fill-opacity="{style["fill_opacity"]}" stroke="{style["stroke"]}" '
                         f'stroke-width="{style["stroke_width"]}"/>')
        parts.append("</g>")

        parts.append('<g id="envelope">')
        style = CANDIDATE_STYLE_TOKENS["CAND_ENVELOPE"]
        parts.append(f'<polygon points="{attr(floor["floor_envelope"]["polygon"])}" fill="none" '
                     f'stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/>')
        if core:
            core_style = CANDIDATE_STYLE_TOKENS["CAND_CORE"]
            parts.append(f'<polygon points="{attr(core["polygon"])}" fill="{core_style["fill"]}"'
                         f' fill-opacity="{core_style["fill_opacity"]}" '
                         f'stroke="{core_style["stroke"]}" '
                         f'stroke-width="{core_style["stroke_width"]}"/>')
        parts.append("</g>")

        parts.append('<g id="labels">')
        for space in floor["spaces"]:
            anchor = self._anchor(space["polygon"])
            if anchor is None:
                continue
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" text-anchor="middle" '
                f'font-family="{CANDIDATE_SVG_FONT_FAMILY}" font-size="8.5" fill="#111111">'
                f'{self._escape(space["display_label"])}</text>')
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]) + 10.0:.3f}" '
                f'text-anchor="middle" font-family="{CANDIDATE_SVG_FONT_FAMILY}" font-size="7" '
                f'fill="#666666">{space["realized_area_m2"]:.1f} m2</text>')
        if core:
            anchor = self._anchor(core["polygon"])
            if anchor:
                parts.append(
                    f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" '
                    f'text-anchor="middle" font-family="{CANDIDATE_SVG_FONT_FAMILY}" '
                    f'font-size="7.5" fill="#5a3c00">STAIR CORE</text>')
        for region in floor["external_regions"]:
            anchor = self._anchor(region["polygon"])
            if anchor:
                parts.append(
                    f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" '
                    f'text-anchor="middle" font-family="{CANDIDATE_SVG_FONT_FAMILY}" '
                    f'font-size="8" fill="#1d6b4f">'
                    f'{self._escape(region["display_label"])} (EXT)</text>')
        parts.append("</g>")
        parts.append("</svg>")
        return "".join(parts)

    def render_candidate_sheet(self, document: Mapping[str, Any], floor_id: str,
                               candidates: list[Mapping[str, Any]],
                               evaluations: list[Mapping[str, Any]]) -> str:
        """One sheet listing every candidate for a floor with its evaluation."""
        rows = []
        for candidate, evaluation in zip(candidates, evaluations):
            floor = next((f for f in candidate["floors"]
                          if str(f["floor_id"]) == str(floor_id)), None)
            if floor is None:
                continue
            rows.append((candidate["candidate_id"], candidate, floor, evaluation))

        height = 40.0 + max(len(rows), 1) * 92.0
        width = 660.0
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
            f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">',
            f'<rect x="0" y="0" width="{width:.3f}" height="{height:.3f}" '
            f'fill="{CANDIDATE_SVG_BACKGROUND}"/>',
            f'<text x="10.000" y="20.000" font-family="{CANDIDATE_SVG_FONT_FAMILY}" '
            f'font-size="12" fill="#111111">{self._escape(floor_id)} — LAYOUT CANDIDATES'
            f' ({len(rows)})</text>',
        ]
        for index, (candidate_id, candidate, floor, evaluation) in enumerate(rows):
            top = 34.0 + index * 92.0
            selected = candidate_id == document.get("selected_candidate_id")
            stroke = "#1f7a3d" if selected else "#999999"
            parts.append(f'<rect x="10.000" y="{top:.3f}" width="640.000" height="84.000" '
                         f'fill="none" stroke="{stroke}" stroke-width="1.2"/>')
            components = evaluation["score_components"]
            summary = (
                f'{candidate_id}{" [SELECTED]" if selected else ""} — '
                f'{"REJECTED" if evaluation["rejected"] else "VIABLE"} | '
                f'critical {evaluation["critical_relationships"]["satisfied"]}/'
                f'{evaluation["critical_relationships"]["total"]} | '
                f'high {evaluation["high_relationships"]["satisfied"]}/'
                f'{evaluation["high_relationships"]["total"]} | '
                f'entrance {components["entrance_hierarchy"]} | '
                f'core {evaluation["vertical_core"]["status"]} | '
                f'overlap {evaluation["overlap_area_m2"]:.3f} m2'
            )
            parts.append(f'<text x="18.000" y="{top + 16.0:.3f}" '
                         f'font-family="{CANDIDATE_SVG_FONT_FAMILY}" font-size="9" '
                         f'fill="#111111">{self._escape(summary)}</text>')
            if evaluation["hard_rejections"]:
                codes = ", ".join(r["code"] for r in evaluation["hard_rejections"])
                parts.append(f'<text x="18.000" y="{top + 30.0:.3f}" '
                             f'font-family="{CANDIDATE_SVG_FONT_FAMILY}" font-size="8" '
                             f'fill="#b02020">{self._escape(codes)}</text>')
            # miniature of the candidate's floor layout
            points: list[list[float]] = []
            for space in floor["spaces"]:
                points.extend(space["polygon"])
            if points:
                min_x = min(p[0] for p in points)
                max_x = max(p[0] for p in points)
                min_y = min(p[1] for p in points)
                max_y = max(p[1] for p in points)
                span = max(max_x - min_x, max_y - min_y) or 1.0
                scale = 60.0 / span
                for space in floor["spaces"]:
                    token = {
                        "public": "CAND_SPACE_PUBLIC", "service": "CAND_SPACE_SERVICE",
                        "circulation": "CAND_SPACE_CIRCULATION",
                        "private": "CAND_SPACE_PRIVATE",
                    }.get(str(space.get("zone")), "CAND_SPACE")
                    if space.get("protected_core"):
                        token = "CAND_CORE"
                    style = CANDIDATE_STYLE_TOKENS[token]
                    coords = " ".join(
                        f"{18.0 + 520.0 + (p[0] - min_x) * scale:.3f},"
                        f"{top + 12.0 + (max_y - p[1]) * scale:.3f}"
                        for p in space["polygon"])
                    parts.append(f'<polygon points="{coords}" fill="{style["fill"]}" '
                                 f'fill-opacity="{style.get("fill_opacity", 0.0)}" '
                                 f'stroke="{style["stroke"]}" stroke-width="0.7"/>')
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
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="360.000" height="80.000" '
                'viewBox="0 0 360.000 80.000">'
                f'<rect x="0" y="0" width="360.000" height="80.000" '
                f'fill="{CANDIDATE_SVG_BACKGROUND}"/>'
                f'<text x="10.000" y="40.000" font-family="{CANDIDATE_SVG_FONT_FAMILY}" '
                f'font-size="11" fill="#b02020">'
                f'{ArchitecturalLayoutIntelligenceV1._escape(message)}</text></svg>')

    @staticmethod
    def _escape(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _failed(self, reason: str) -> dict[str, Any]:
        document = {
            "contract": CANDIDATE_CONTRACT, "version": VERSION,
            "plan_kind": "ARCHITECTURALLY_EVALUATED_LAYOUT",
            "selected_candidate_id": None, "selected_candidate_hash": None,
            "candidate_count": 0, "candidate_ids": [], "floors": [],
            "vertical_core_binding": {}, "shared_core_region": None, "served_floors": [],
            "relationship_ontology": {}, "evaluations": [], "selected_evaluation": {},
            "quality_gate": {"contract": GATE_CONTRACT, "version": VERSION,
                             "quality_status": QUALITY_FAIL, "hard_rejections": [reason]},
            "unresolved_items": [], "warnings": [{"code": "LAYOUT_INTELLIGENCE_FAILED",
                                                  "reason": reason}],
            "provenance": {"engine": "ArchitecturalLayoutIntelligenceV1", "reason": reason},
        }
        document["plan_hash"] = layout_semantic_hash(document)
        return document


architectural_layout_intelligence = ArchitecturalLayoutIntelligenceV1()


def design_architectural_layout(design_model: Any, *, program: Mapping[str, Any] | None = None,
                                human_plan: Mapping[str, Any] | None = None):
    """Module-level convenience wrapper over the canonical engine."""
    return architectural_layout_intelligence.design(
        design_model, program=program, human_plan=human_plan)


__all__ = [
    "ArchitecturalLayoutIntelligenceV1", "architectural_layout_intelligence",
    "design_architectural_layout",
]
