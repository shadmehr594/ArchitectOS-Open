"""ARCHITECTURAL-DESIGN-ROBUSTNESS-01A — full plan realization audit + plan contract.

Read-only projection of the REAL architectural design chain into:

1. ``ArchitecturalHumanReadablePlanV1`` — per-floor, human-readable plan records
2. ``ArchitecturalPlanCompletenessV1`` — honest realization completeness report
3. deterministic per-floor plan SVG + diagnostics SVG

It extends the existing plan lineage (``ArchitecturalPlanModel`` +
``architectural_geometry`` + the canonical ``PlanModelToSceneAdapterV1`` /
``PlanDrawingServiceV1`` drawing path).  It never creates a competing plan
architecture and never invents geometry: an element without realized geometry is
recorded as MISSING_REALIZATION instead of being drawn.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_human_readable_plan_v1 import (
    COMPLETENESS_CONTRACT,
    CONTRACT,
    CONTRACT_ONLY,
    DOOR_GEOMETRY_REALIZATION_MISSING,
    ENTRANCE_GEOMETRY_REALIZATION_MISSING,
    FLOOR_ENVELOPE_REALIZATION_MISSING,
    INTERNAL_WALL_REALIZATION_MISSING,
    LEGACY,
    MISSING_REALIZATION,
    PARKING_REALIZATION_MISSING,
    PARTIAL,
    PLAN_STYLE_TOKENS,
    PLAN_SVG_BACKGROUND,
    PLAN_SVG_FONT_FAMILY,
    PLAN_SVG_PADDING,
    PLAN_SVG_UNITS_PER_METRE,
    READY_FOR_PLAN_DISPLAY,
    REALIZED,
    ROOF_REALIZATION_MISSING,
    ROOM_FOOTPRINT_REALIZATION_MISSING,
    SEMANTIC_ONLY,
    STAIR_GEOMETRY_REALIZATION_MISSING,
    STATUS_COMPLETE,
    STATUS_COMPLETE_WITH_WARNINGS,
    STATUS_FAILED,
    STATUS_GEOMETRY_INCOMPLETE,
    STATUS_SEMANTIC_ONLY,
    VERSION,
    WINDOW_GEOMETRY_REALIZATION_MISSING,
    display_label,
    plan_semantic_hash,
    svg_sha256,
)


class ArchitecturalHumanReadablePlanV1(dict):
    """Versioned, dict-compatible human-readable plan artifact."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as error:  # pragma: no cover
            raise AttributeError(item) from error


def _ring(value: Any) -> list[list[float]]:
    if not isinstance(value, (list, tuple)):
        return []
    output: list[list[float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        try:
            output.append([float(point[0]), float(point[1])])
        except (TypeError, ValueError):
            return []
    return output


def _space_footprint(space: Mapping[str, Any]) -> list[list[float]]:
    footprint = space.get("footprint")
    if isinstance(footprint, Mapping):
        ring = _ring(footprint.get("points"))
        if ring:
            return ring
    return _ring(space.get("polygon"))


def _area(ring: list[list[float]]) -> float | None:
    if len(ring) < 4:
        return None
    try:
        return round(float(Polygon(ring).area), 6)
    except (ValueError, TypeError):
        return None


class ArchitecturalDesignRobustness01A:
    """Project a real design model into a plan contract + completeness report."""

    VERSION = VERSION

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def project(self, design_model: Any, *, program: Mapping[str, Any] | None = None) -> ArchitecturalHumanReadablePlanV1:
        plan_model = getattr(design_model, "plan_model", None)
        geometry = getattr(design_model, "architectural_geometry", None)

        if not isinstance(plan_model, Mapping) and not isinstance(geometry, Mapping):
            return self._failed("design_model_has_no_plan_model_or_geometry")

        plan_model = plan_model if isinstance(plan_model, Mapping) else {}
        geometry = geometry if isinstance(geometry, Mapping) else {}

        registry = {
            str(item.get("name")): item
            for item in (plan_model.get("space_registry") or [])
            if isinstance(item, Mapping) and item.get("name") is not None
        }
        zones = plan_model.get("zones") if isinstance(plan_model.get("zones"), Mapping) else {}
        requested = self._requested_spaces(plan_model, program)

        floors = self._floors(
            geometry, registry, zones, plan_model.get("floor_distribution")
        )
        completeness = self._completeness(geometry, floors, requested, zones)

        plan_status = self._plan_status(floors, completeness)

        document = ArchitecturalHumanReadablePlanV1({
            "contract": CONTRACT,
            "version": VERSION,
            "plan_status": plan_status,
            "plan_kind": "READ_ONLY_DERIVED_PLAN_PROJECTION",
            "source": {
                "plan_model_version": plan_model.get("space_registry") is not None,
                "floor_distribution": deepcopy(plan_model.get("floor_distribution") or {}),
                "zones": deepcopy(zones),
                "geometry_status": geometry.get("geometry_status"),
                "geometry_version": geometry.get("version"),
            },
            "floors": floors,
            "program_spaces_requested": requested,
            "unresolved_geometry": self._unresolved(geometry, floors),
            "completeness": completeness,
            "warnings": self._warnings(floors, completeness),
            "provenance": {
                "builder": "ArchitecturalDesignRobustness01A",
                "builder_version": VERSION,
                "source": "ArchitecturalBrain.design -> plan_model + architectural_geometry",
                "drawing_path_reused": "PlanModelToSceneAdapterV1/PlanDrawingServiceV1",
                "geometry_invented": False,
                "walls_invented": False,
                "doors_invented": False,
                "windows_invented": False,
                "structural_elements_generated": False,
                "bim_ifc_executed": False,
                "render_runtime_executed": False,
                "comfyui_executed": False,
                "source_mutated": False,
            },
        })
        document["plan_hash"] = plan_semantic_hash(document)
        return document

    # --------------------------------------------------
    # program
    # --------------------------------------------------

    @staticmethod
    def _requested_spaces(plan_model: Mapping[str, Any], program: Mapping[str, Any] | None) -> list[str]:
        names = set()
        for space in plan_model.get("spaces") or []:
            if isinstance(space, Mapping) and space.get("name") is not None:
                names.add(str(space["name"]))
        if isinstance(program, Mapping):
            for name in program.get("spaces") or []:
                names.add(str(name))
        return sorted(names)

    # --------------------------------------------------
    # floors
    # --------------------------------------------------

    def _floors(self, geometry, registry, zones, distribution=None) -> list[dict[str, Any]]:
        spaces = [s for s in (geometry.get("spaces") or []) if isinstance(s, Mapping)]
        walls = [w for w in (geometry.get("physical_walls") or []) if isinstance(w, Mapping)]
        openings = [o for o in (geometry.get("openings") or []) if isinstance(o, Mapping)]
        vertical = [v for v in (geometry.get("vertical_geometry") or []) if isinstance(v, Mapping)]
        floor_geometry = {
            str(item.get("floor")): item
            for item in (geometry.get("floor_geometry") or [])
            if isinstance(item, Mapping) and item.get("floor") is not None
        }

        distribution = distribution if isinstance(distribution, Mapping) else {}
        floor_of: dict[str, str] = {}
        for floor_id, names in distribution.items():
            for name in names or []:
                floor_of.setdefault(str(name), str(floor_id))

        def resolve(name: Any, geometry_floor: Any) -> tuple[str, str]:
            raw = "" if geometry_floor is None else str(geometry_floor)
            if raw and raw.upper() != "SITE":
                return raw, "geometry.floor"
            mapped = floor_of.get(str(name))
            if mapped:
                return mapped, "plan_model.floor_distribution"
            return raw or "UNASSIGNED", "unresolved"

        order = sorted(
            {resolve(s.get("name"), s.get("floor"))[0] for s in spaces}
            | set(floor_geometry)
        )
        order = [name for name in order if name and name.upper() != "SITE"]

        external_names = {str(name) for name in (zones.get("external") or [])}
        circulation_names = {str(name) for name in (zones.get("circulation") or [])}

        output: list[dict[str, Any]] = []
        for index, floor_id in enumerate(order):
            envelope = floor_geometry.get(floor_id, {})
            floor_spaces = [
                s for s in spaces if resolve(s.get("name"), s.get("floor"))[0] == floor_id
            ]
            floor_walls = [w for w in walls if str(w.get("floor")) == floor_id]
            floor_openings = []
            for opening in openings:
                opening_floor, _ = resolve(opening.get("space"), opening.get("floor"))
                if opening_floor == floor_id:
                    floor_openings.append(opening)
            floor_vertical = [
                v for v in vertical
                if floor_id in {str(level) for level in (v.get("served_levels") or [])}
                or floor_id in {str(level) for level in (v.get("served_floor_ids") or [])}
            ]

            space_records = [
                self._space_record(space, registry, external_names, circulation_names,
                                   *resolve(space.get("name"), space.get("floor")))
                for space in floor_spaces
            ]
            wall_records = [self._wall_record(wall, space_records) for wall in floor_walls]
            door_records = [
                self._opening_record(o, "door") for o in floor_openings if o.get("type") == "door"
            ]
            window_records = [
                self._opening_record(o, "window") for o in floor_openings if o.get("type") == "window"
            ]
            vertical_records = [self._vertical_record(v) for v in floor_vertical]

            external_records = [
                record for record in space_records
                if record["external"] is True or record["name"] in external_names
            ]
            circulation_records = [
                record for record in space_records if record["name"] in circulation_names
            ]
            entrance_records = [
                record for record in space_records
                if str(record["semantic_type"]) in ("entrance", "lobby")
                or record["name"] in ("entrance", "entry")
            ]
            parking_records = [
                record for record in space_records
                if "parking" in record["name"] or record["name"] in ("garage", "carport")
            ]

            unresolved = []
            if envelope.get("geometry_status") not in (None, "resolved_metric_envelope"):
                unresolved.append({
                    "code": FLOOR_ENVELOPE_REALIZATION_MISSING,
                    "floor_id": floor_id,
                    "observed_status": envelope.get("geometry_status"),
                    "stage": "architectural geometry -> aggregate floor envelope",
                })
            for record in door_records:
                if record["realization"] != READY_FOR_PLAN_DISPLAY:
                    unresolved.append({
                        "code": DOOR_GEOMETRY_REALIZATION_MISSING,
                        "floor_id": floor_id,
                        "element_id": record["door_id"],
                        "category": record.get("category"),
                        "host_resolution_status": record.get("host_resolution_status"),
                        "stage": "opening host resolution (wall/opening placement selector)",
                    })
            for record in window_records:
                if record["realization"] != READY_FOR_PLAN_DISPLAY:
                    unresolved.append({
                        "code": WINDOW_GEOMETRY_REALIZATION_MISSING,
                        "floor_id": floor_id,
                        "element_id": record["window_id"],
                        "category": record.get("category"),
                        "host_resolution_status": record.get("host_resolution_status"),
                        "stage": "opening host resolution (wall/opening placement selector)",
                    })
            for record in vertical_records:
                if record["geometry_realization"] != READY_FOR_PLAN_DISPLAY:
                    unresolved.append({
                        "code": STAIR_GEOMETRY_REALIZATION_MISSING
                        if "stair" in str(record.get("system_type"))
                        else STAIR_GEOMETRY_REALIZATION_MISSING,
                        "floor_id": floor_id,
                        "element_id": record.get("system_id"),
                        "observed_status": record.get("geometry_status"),
                        "missing_evidence": record.get("missing_evidence"),
                        "stage": "vertical circulation geometry realization",
                    })

            output.append({
                "floor_id": floor_id,
                "floor_label": display_label(floor_id),
                "floor_order": index,
                "elevation": envelope.get("elevation"),
                "height": envelope.get("height"),
                "envelope_status": envelope.get("geometry_status"),
                "spaces": space_records,
                "walls": wall_records,
                "doors": door_records,
                "windows": window_records,
                "circulation": circulation_records,
                "vertical_circulation": vertical_records,
                "external_spaces": external_records,
                "parking_spaces": parking_records,
                "entrances": entrance_records,
                "unresolved_geometry": unresolved,
            })
        return output

    @staticmethod
    def _space_record(space, registry, external_names, circulation_names,
                      resolved_floor, floor_source) -> dict[str, Any]:
        name = str(space.get("name"))
        ring = _space_footprint(space)
        footprint = space.get("footprint") if isinstance(space.get("footprint"), Mapping) else {}
        area = footprint.get("area")
        area = area if area is not None else _area(ring)
        status = space.get("geometry_status")
        realized = bool(ring) and status in (None, "resolved_room_footprint")
        registered = registry.get(name, {})
        return {
            "space_id": name,
            "name": name,
            "display_label": display_label(name),
            "semantic_type": registered.get("space_type") or space.get("type"),
            "canonical_name": registered.get("canonical_name"),
            "zone": registered.get("zone") or registered.get("planning_zone"),
            "floor": resolved_floor,
            "geometry_floor": space.get("floor"),
            "floor_source": floor_source,
            "polygon": ring,
            "area_m2": round(float(area), 6) if isinstance(area, (int, float)) else None,
            "external": name in external_names or bool(space.get("external")),
            "circulation": name in circulation_names,
            "geometry_status": status,
            "realization": READY_FOR_PLAN_DISPLAY if realized else MISSING_REALIZATION,
            "provenance": {
                "source": "architectural_geometry.spaces[].footprint",
                "coordinate_mode": space.get("coordinate_mode"),
                "floor_source": floor_source,
                "geometry_invented": False,
            },
        }

    @staticmethod
    def _wall_record(wall, space_records) -> dict[str, Any]:
        start = _ring([wall.get("start")])
        end = _ring([wall.get("end")])
        geometry = [start[0], end[0]] if start and end else []
        spaces = [str(item) for item in (wall.get("spaces") or [])]
        return {
            "wall_id": wall.get("wall_id"),
            "wall_type": wall.get("wall_type"),
            "external": bool(wall.get("is_exterior")),
            "geometry": geometry,
            "thickness": wall.get("thickness"),
            "floor": str(wall.get("floor")),
            "adjacent_spaces": spaces,
            "topology_status": wall.get("topology_status"),
            "realization": READY_FOR_PLAN_DISPLAY if geometry else MISSING_REALIZATION,
            "provenance": {
                "source": "architectural_geometry.physical_walls",
                "thickness_source": wall.get("thickness_source"),
                "geometry_invented": False,
            },
        }

    @staticmethod
    def _opening_record(opening, kind: str) -> dict[str, Any]:
        status = opening.get("geometry_status")
        host = opening.get("host_wall_id")
        realized = status == "resolved" and host is not None
        center = _ring([opening.get("opening_center")])
        record = {
            "opening_id": opening.get("id") or opening.get("opening_id"),
            "category": opening.get("category"),
            "floor": str(opening.get("floor")),
            "host_wall_id": host,
            "host_resolution_status": opening.get("host_resolution_status"),
            "host_resolution_reason": opening.get("host_resolution_reason"),
            "geometry_status": status,
            "geometry": [center[0]] if center else [],
            "width": opening.get("width"),
            "height": opening.get("height"),
            "space": opening.get("space"),
            "realization": READY_FOR_PLAN_DISPLAY if realized else MISSING_REALIZATION,
            "provenance": {
                "source": "architectural_geometry.openings",
                "geometry_invented": False,
            },
        }
        key = "door_id" if kind == "door" else "window_id"
        record[key] = record["opening_id"]
        return record

    @staticmethod
    def _vertical_record(vertical) -> dict[str, Any]:
        status = vertical.get("geometry_status")
        placement = vertical.get("placement_status")
        realized = status == "resolved"
        return {
            "system_id": vertical.get("stair_id") or vertical.get("elevator_id") or vertical.get("name"),
            "system_type": vertical.get("type"),
            "name": vertical.get("name"),
            "served_levels": deepcopy(vertical.get("served_levels") or []),
            "geometry_status": status,
            "placement_status": placement,
            "reserved_zone": vertical.get("reserved_zone"),
            "missing_evidence": deepcopy(vertical.get("missing_evidence") or []),
            "semantic_requirement": "PRESENT",
            "placement": "PRESENT" if placement == "resolved" else "PENDING",
            "geometry_realization": READY_FOR_PLAN_DISPLAY if realized else (
                PARTIAL if placement == "pending" else SEMANTIC_ONLY
            ),
            "provenance": {"source": "architectural_geometry.vertical_geometry",
                           "geometry_invented": False},
        }

    # --------------------------------------------------
    # completeness
    # --------------------------------------------------

    def _completeness(self, geometry, floors, requested, zones) -> dict[str, Any]:
        space_records = [space for floor in floors for space in floor["spaces"]]
        realized_spaces = [s for s in space_records if s["realization"] == READY_FOR_PLAN_DISPLAY]
        walls = [wall for floor in floors for wall in floor["walls"]]
        interior = [w for w in walls if not w["external"]]
        exterior = [w for w in walls if w["external"]]
        doors = [d for floor in floors for d in floor["doors"]]
        windows = [w for floor in floors for w in floor["windows"]]
        circulation = [c for floor in floors for c in floor["circulation"]]
        vertical = [v for floor in floors for v in floor["vertical_circulation"]]
        external = [e for floor in floors for e in floor["external_spaces"]]
        parking = [p for floor in floors for p in floor["parking_spaces"]]
        entrances = [e for floor in floors for e in floor["entrances"]]

        realized_doors = [d for d in doors if d["realization"] == READY_FOR_PLAN_DISPLAY]
        realized_windows = [w for w in windows if w["realization"] == READY_FOR_PLAN_DISPLAY]

        missing: list[str] = []
        if interior and all(w["realization"] != READY_FOR_PLAN_DISPLAY for w in interior):
            missing.append(INTERNAL_WALL_REALIZATION_MISSING)
        if doors and not realized_doors:
            missing.append(DOOR_GEOMETRY_REALIZATION_MISSING)
        if windows and not realized_windows:
            missing.append(WINDOW_GEOMETRY_REALIZATION_MISSING)
        if vertical and all(v["geometry_realization"] != READY_FOR_PLAN_DISPLAY for v in vertical):
            missing.append(STAIR_GEOMETRY_REALIZATION_MISSING)
        if entrances and not realized_doors and any(
            str(d.get("category")) == "main_entrance" for d in doors
        ):
            missing.append(ENTRANCE_GEOMETRY_REALIZATION_MISSING)
        if any(floor["envelope_status"] not in (None, "resolved_metric_envelope") for floor in floors):
            missing.append(FLOOR_ENVELOPE_REALIZATION_MISSING)
        roof = geometry.get("roof_geometry")
        if isinstance(roof, Mapping) and (
            roof.get("roof_type") in (None, "UNKNOWN") or roof.get("slope") is None
        ):
            missing.append(ROOF_REALIZATION_MISSING)
        if "parking" in {str(name).lower() for name in requested} and not parking:
            missing.append(PARKING_REALIZATION_MISSING)

        spaces_without_geometry = sorted({
            record["name"] for record in space_records
            if record["realization"] != READY_FOR_PLAN_DISPLAY
        })
        if spaces_without_geometry:
            missing.append(ROOM_FOOTPRINT_REALIZATION_MISSING)

        requested_realized = [
            name for name in requested
            if any(record["name"] == name for record in realized_spaces)
        ]
        if not realized_spaces:
            status = STATUS_SEMANTIC_ONLY
        elif missing:
            status = STATUS_GEOMETRY_INCOMPLETE
        elif spaces_without_geometry:
            status = STATUS_COMPLETE_WITH_WARNINGS
        else:
            status = STATUS_COMPLETE

        return {
            "contract": COMPLETENESS_CONTRACT,
            "version": VERSION,
            "completeness_status": status,
            "program_spaces_requested": list(requested),
            "program_spaces_realized": requested_realized,
            "spaces_with_geometry": len(realized_spaces),
            "spaces_without_geometry": spaces_without_geometry,
            "internal_walls_required": len(interior),
            "internal_walls_realized": sum(
                1 for w in interior if w["realization"] == READY_FOR_PLAN_DISPLAY),
            "exterior_walls_realized": sum(
                1 for w in exterior if w["realization"] == READY_FOR_PLAN_DISPLAY),
            "doors_required": len(doors),
            "doors_realized": len(realized_doors),
            "windows_required": len(windows),
            "windows_realized": len(realized_windows),
            "circulation_required": len(circulation),
            "circulation_realized": sum(
                1 for c in circulation if c["realization"] == READY_FOR_PLAN_DISPLAY),
            "vertical_circulation_required": len(vertical),
            "vertical_circulation_realized": sum(
                1 for v in vertical if v["geometry_realization"] == READY_FOR_PLAN_DISPLAY),
            "external_spaces_required": len(external),
            "external_spaces_realized": sum(
                1 for e in external if e["realization"] == READY_FOR_PLAN_DISPLAY),
            "parking_required": "parking" in {str(name).lower() for name in requested},
            "parking_realized": len(parking),
            "entrances_required": len(entrances),
            "entrances_realized": sum(
                1 for e in entrances if e["realization"] == READY_FOR_PLAN_DISPLAY),
            "missing_realization_stages": sorted(set(missing)),
            "zones": deepcopy(zones),
        }

    @staticmethod
    def _plan_status(floors, completeness) -> str:
        status = completeness["completeness_status"]
        if status == STATUS_SEMANTIC_ONLY:
            return STATUS_SEMANTIC_ONLY
        if status in (STATUS_COMPLETE, STATUS_COMPLETE_WITH_WARNINGS):
            return status
        return STATUS_GEOMETRY_INCOMPLETE

    @staticmethod
    def _unresolved(geometry, floors) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for floor in floors:
            items.extend(deepcopy(floor["unresolved_geometry"]))
        roof = geometry.get("roof_geometry")
        if isinstance(roof, Mapping) and (
            roof.get("roof_type") in (None, "UNKNOWN") or roof.get("slope") is None
        ):
            items.append({
                "code": ROOF_REALIZATION_MISSING,
                "roof_type": roof.get("roof_type"),
                "slope": roof.get("slope"),
                "stage": "roof geometry evidence (Design-04)",
            })
        return items

    @staticmethod
    def _warnings(floors, completeness) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for name in completeness["spaces_without_geometry"]:
            warnings.append({"code": "ROOM_FOOTPRINT_PENDING", "space": name})
        if completeness["completeness_status"] != STATUS_COMPLETE:
            warnings.append({
                "code": "PLAN_NOT_COMPLETE",
                "missing_realization_stages": completeness["missing_realization_stages"],
            })
        return warnings

    # --------------------------------------------------
    # SVG
    # --------------------------------------------------

    def render_plan_svg(self, plan: Mapping[str, Any], floor_id: str, *, diagnostic: bool = False) -> str:
        floors = [f for f in (plan.get("floors") or []) if str(f.get("floor_id")) == str(floor_id)]
        if not floors:
            return self._empty_svg(f"{floor_id} (no realized floor data)")
        floor = floors[0]

        points: list[list[float]] = []
        for space in floor["spaces"]:
            points.extend(space["polygon"])
        for wall in floor["walls"]:
            points.extend(wall["geometry"])
        if not points:
            return self._empty_svg(f"{floor['floor_label']} (no realized geometry)")

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        pad = PLAN_SVG_PADDING
        scale = PLAN_SVG_UNITS_PER_METRE
        width = (max_x - min_x + 2 * pad) * scale
        height = (max_y - min_y + 2 * pad) * scale + 26.0

        def px(x: float) -> float:
            return (float(x) - min_x + pad) * scale

        def py(y: float) -> float:
            return (max_y - float(y) + pad) * scale + 26.0

        def points_attr(ring) -> str:
            return " ".join(f"{px(p[0]):.3f},{py(p[1]):.3f}" for p in ring)

        title = floor["floor_label"] + (" — DIAGNOSTIC" if diagnostic else " — ARCHITECTURAL PLAN")
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" height="{height:.3f}" '
            f'viewBox="0 0 {width:.3f} {height:.3f}">',
            f'<rect x="0" y="0" width="{width:.3f}" height="{height:.3f}" fill="{PLAN_SVG_BACKGROUND}"/>',
            f'<text x="8.000" y="18.000" font-family="{PLAN_SVG_FONT_FAMILY}" font-size="12" '
            f'fill="#111111">{self._escape(title)}</text>',
        ]

        parts.append('<g id="spaces">')
        for space in floor["spaces"]:
            if space["realization"] != READY_FOR_PLAN_DISPLAY:
                continue
            token = "PLAN_SPACE"
            if space["external"]:
                token = "PLAN_SPACE_EXTERNAL"
            elif space["circulation"]:
                token = "PLAN_SPACE_CIRCULATION"
            style = PLAN_STYLE_TOKENS[token]
            opacity = style.get("fill_opacity")
            fill_opacity = "" if opacity is None else f' fill-opacity="{opacity}"'
            parts.append(
                f'<polygon points="{points_attr(space["polygon"])}" fill="{style["fill"]}"'
                f'{fill_opacity} stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/>'
            )
        parts.append("</g>")

        parts.append('<g id="walls">')
        for wall in floor["walls"]:
            if wall["realization"] != READY_FOR_PLAN_DISPLAY:
                continue
            style = PLAN_STYLE_TOKENS[
                "PLAN_WALL_EXTERIOR" if wall["external"] else "PLAN_WALL_INTERIOR"]
            (x1, y1), (x2, y2) = wall["geometry"]
            parts.append(
                f'<line x1="{px(x1):.3f}" y1="{py(y1):.3f}" x2="{px(x2):.3f}" y2="{py(y2):.3f}" '
                f'stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/>'
            )
        parts.append("</g>")

        # doors / windows are drawn ONLY where their geometry is realized
        for layer, records, token in (
            ("doors", floor["doors"], "PLAN_DOOR"),
            ("windows", floor["windows"], "PLAN_WINDOW"),
        ):
            parts.append(f'<g id="{layer}">')
            for record in records:
                if record["realization"] != READY_FOR_PLAN_DISPLAY or not record["geometry"]:
                    continue
                style = PLAN_STYLE_TOKENS[token]
                center = record["geometry"][0]
                parts.append(
                    f'<circle cx="{px(center[0]):.3f}" cy="{py(center[1]):.3f}" r="2.400" '
                    f'fill="none" stroke="{style["stroke"]}" stroke-width="{style["stroke_width"]}"/>'
                )
            parts.append("</g>")

        parts.append('<g id="labels">')
        for space in floor["spaces"]:
            if space["realization"] != READY_FOR_PLAN_DISPLAY:
                continue
            anchor = self._label_anchor(space["polygon"])
            if anchor is None:
                continue
            token = "PLAN_LABEL_EXTERNAL" if space["external"] else "PLAN_LABEL"
            style = PLAN_STYLE_TOKENS[token]
            parts.append(
                f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]):.3f}" text-anchor="middle" '
                f'font-family="{PLAN_SVG_FONT_FAMILY}" font-size="8.5" fill="{style["fill"]}">'
                f'{self._escape(space["display_label"])}</text>'
            )
            area = space.get("area_m2")
            if isinstance(area, (int, float)):
                parts.append(
                    f'<text x="{px(anchor[0]):.3f}" y="{py(anchor[1]) + 10.0:.3f}" text-anchor="middle" '
                    f'font-family="{PLAN_SVG_FONT_FAMILY}" font-size="7" fill="#666666">'
                    f'{area:.1f} m2</text>'
                )
        parts.append("</g>")

        if diagnostic:
            parts.append('<g id="diagnostics">')
            style = PLAN_STYLE_TOKENS["PLAN_UNRESOLVED"]
            for index, item in enumerate(floor["unresolved_geometry"]):
                parts.append(
                    f'<text x="8.000" y="{height - 8.0 - index * 11.0:.3f}" '
                    f'font-family="{PLAN_SVG_FONT_FAMILY}" font-size="8" fill="{style["stroke"]}">'
                    f'{self._escape(item["code"])} — {self._escape(item.get("element_id") or "")}'
                    f'</text>'
                )
            parts.append("</g>")

        parts.append(self._scale_bar(px, py, min_x, max_x, max_y))
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _label_anchor(ring):
        if len(ring) < 4:
            return None
        try:
            point = Polygon(ring).representative_point()
        except (ValueError, TypeError):
            return None
        return [float(point.x), float(point.y)]

    @staticmethod
    def _scale_bar(px, py, min_x, max_x, max_y) -> str:
        length = min(5.0, max(1.0, (max_x - min_x) / 4.0))
        x0 = px(min_x)
        y0 = py(max_y) + 14.0
        x1 = px(min_x + length)
        return (
            f'<g id="scale"><line x1="{x0:.3f}" y1="{y0:.3f}" x2="{x1:.3f}" y2="{y0:.3f}" '
            f'stroke="#111111" stroke-width="1.2"/>'
            f'<text x="{x0:.3f}" y="{y0 + 11.0:.3f}" font-family="{PLAN_SVG_FONT_FAMILY}" '
            f'font-size="8" fill="#333333">{length:.1f} m</text></g>'
        )

    @staticmethod
    def _empty_svg(message: str) -> str:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320.000" height="80.000" '
            'viewBox="0 0 320.000 80.000">'
            f'<rect x="0" y="0" width="320.000" height="80.000" fill="{PLAN_SVG_BACKGROUND}"/>'
            f'<text x="10.000" y="40.000" font-family="{PLAN_SVG_FONT_FAMILY}" font-size="11" '
            f'fill="#b02020">{ArchitecturalDesignRobustness01A._escape(message)}</text></svg>'
        )

    @staticmethod
    def _escape(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------

    @staticmethod
    def _failed(reason: str) -> ArchitecturalHumanReadablePlanV1:
        document = ArchitecturalHumanReadablePlanV1({
            "contract": CONTRACT,
            "version": VERSION,
            "plan_status": STATUS_FAILED,
            "plan_kind": "READ_ONLY_DERIVED_PLAN_PROJECTION",
            "source": {},
            "floors": [],
            "program_spaces_requested": [],
            "unresolved_geometry": [],
            "completeness": {
                "contract": COMPLETENESS_CONTRACT,
                "version": VERSION,
                "completeness_status": STATUS_FAILED,
                "missing_realization_stages": [],
            },
            "warnings": [{"code": "PLAN_PROJECTION_FAILED", "reason": reason}],
            "provenance": {"builder": "ArchitecturalDesignRobustness01A", "reason": reason},
        })
        document["plan_hash"] = plan_semantic_hash(document)
        return document

    @staticmethod
    def hash(plan: Mapping[str, Any]) -> str:
        return plan_semantic_hash(plan)


architectural_design_robustness_01a = ArchitecturalDesignRobustness01A()


def project_human_readable_plan(design_model: Any, *, program: Mapping[str, Any] | None = None):
    """Module-level convenience wrapper over the canonical projector."""
    return architectural_design_robustness_01a.project(design_model, program=program)


__all__ = [
    "ArchitecturalHumanReadablePlanV1", "ArchitecturalDesignRobustness01A",
    "project_human_readable_plan", "architectural_design_robustness_01a",
]
