"""ArchitecturalDesignVisualValidationV1.

Deterministic, READ-ONLY visual inspection of the current architectural design
chain:

    AcceptedArchitecturalBaselineEnvelopeV1
      -> Design-02 derived candidate
      -> Design-03 enriched candidate
      -> Design-04 floor / slab / roof geometry candidate
      -> Design-05 structural readiness candidate
      -> Structural-Synthesis-01 support candidate analysis

Produces ``ArchitecturalVisualValidationArtifactV1``: deterministic vector
records + deterministic SVG per floor, with the required logical views.

Pure projection.  No mutation, no geometry invention, no BIM/IFC/render, no
structural engine execution, no image generation.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from shapely.geometry import Point, Polygon

from core.architecture.contracts.architectural_visual_validation_v1 import (
    CONTRACT,
    STATUS_FAILED,
    STATUS_INSUFFICIENT_VISUAL_SOURCE,
    STATUS_READY,
    STATUS_READY_WITH_UNRESOLVED,
    STYLE_TOKENS,
    SVG_BACKGROUND,
    SVG_FONT_FAMILY,
    SVG_PADDING,
    SVG_UNITS_PER_METRE,
    VALIDATION_LAYERS,
    VERSION,
    VIEW_ARCHITECTURAL_PLAN,
    VIEW_OPENING_ACCESS,
    VIEW_STRUCTURAL_READINESS,
    VIEW_SUPPORT_CANDIDATE_SUMMARY,
    VIEW_VOIDS_PROTECTED_ZONES,
    canonical_visual_validation_document,
    svg_sha256,
    visual_validation_semantic_hash,
)


class ArchitecturalVisualValidationV1(dict):
    """Versioned, dict-compatible visual validation artifact."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as error:  # pragma: no cover - attribute convenience
            raise AttributeError(item) from error


# Layer -> view membership (deterministic order).
VIEW_LAYERS: dict[str, tuple[str, ...]] = {
    VIEW_ARCHITECTURAL_PLAN: ("floor_envelope", "spaces", "walls", "external_spaces"),
    VIEW_OPENING_ACCESS: ("floor_envelope", "walls", "openings", "access"),
    VIEW_VOIDS_PROTECTED_ZONES: (
        "floor_envelope", "vertical_voids", "protected_zones", "exclusion_regions",
    ),
    VIEW_STRUCTURAL_READINESS: (
        "floor_envelope", "eligibility_regions", "exclusion_regions",
        "support_candidates", "rejected_support_regions",
    ),
    VIEW_SUPPORT_CANDIDATE_SUMMARY: ("support_candidates", "rejected_support_regions"),
}

ALL_LAYERS = (
    "floor_envelope", "spaces", "walls", "external_spaces", "openings", "access",
    "vertical_voids", "protected_zones", "eligibility_regions", "exclusion_regions",
    "support_candidates", "rejected_support_regions",
)


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


def _surface_ring(value: Any) -> list[list[float]]:
    """Accept either a raw ring or a Design-05 ``{"exterior": ...}`` surface."""
    if isinstance(value, Mapping):
        return _ring(value.get("exterior"))
    return _ring(value)


def _record(
    geometry_type: str,
    coordinates: Any,
    style_token: str,
    source_path: str,
    source_record_id: Any,
    **extra: Any,
) -> dict[str, Any]:
    record = {
        "geometry_type": geometry_type,
        "coordinates": coordinates,
        "style_token": style_token,
        "source_path": source_path,
        "source_record_id": source_record_id,
        "provenance": {"projection": "read_only", "geometry_invented": False},
    }
    record.update(extra)
    return record


class ArchitecturalDesignVisualValidationV1:
    """Build a deterministic visual validation artifact from a candidate chain."""

    VERSION = VERSION

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def build(self, chain: Mapping[str, Any]) -> ArchitecturalVisualValidationV1:
        if not isinstance(chain, Mapping):
            return self._failed([{"code": "CHAIN_MUST_BE_A_MAPPING"}])

        design_04 = chain.get("design_04") if isinstance(chain.get("design_04"), Mapping) else None
        if not design_04 or not isinstance(design_04.get("floor_geometries"), list) \
                or not design_04["floor_geometries"]:
            return self._failed([{"code": "DESIGN_04_FLOOR_GEOMETRY_REQUIRED"}], chain)

        boundary, boundary_source = self._boundary_source(chain)
        design_05 = chain.get("design_05") if isinstance(chain.get("design_05"), Mapping) else None
        support = chain.get("support_analysis") if isinstance(chain.get("support_analysis"), Mapping) else None
        accepted = chain.get("accepted_baseline") if isinstance(chain.get("accepted_baseline"), Mapping) else None

        unresolved: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if boundary_source is None:
            unresolved.append({
                "code": "CANONICAL_BOUNDARY_EXTRACTION_NOT_SUPPLIED",
                "layer": "spaces/walls/openings/access",
                "detail": "accepted_baseline or design_02/design_03 boundary_extraction missing",
            })
        if design_05 is None:
            unresolved.append({
                "code": "DESIGN_05_READINESS_NOT_SUPPLIED",
                "layer": "eligibility_regions/exclusion_regions",
            })
        if support is None:
            unresolved.append({
                "code": "SUPPORT_CANDIDATE_ANALYSIS_NOT_SUPPLIED",
                "layer": "support_candidates/rejected_support_regions",
            })

        floors = self._floor_artifacts(design_04, boundary, boundary_source, design_05, support, unresolved)
        floors.sort(key=lambda item: (item["floor_order"], item["floor_id"]))

        for roof in design_04.get("roof_geometries", []) or []:
            if isinstance(roof, Mapping) and (
                roof.get("roof_type") in (None, "UNKNOWN") or roof.get("slope") is None
            ):
                warnings.append({
                    "code": "ROOF_EVIDENCE_UNRESOLVED",
                    "roof_geometry_ref": roof.get("geometry_id"),
                    "roof_type": roof.get("roof_type"),
                    "slope": roof.get("slope"),
                    "roof_geometry_invented": False,
                })

        status = STATUS_READY_WITH_UNRESOLVED if (unresolved or warnings) else STATUS_READY

        artifact = ArchitecturalVisualValidationV1({
            "contract": CONTRACT,
            "version": VERSION,
            "artifact_status": status,
            "artifact_kind": "READ_ONLY_INSPECTION_OUTPUT",
            "source_candidate_id": design_04.get("candidate_id"),
            "source_candidate_version": design_04.get("candidate_version"),
            "source_candidate_hash": design_04.get("candidate_hash"),
            "accepted_baseline_id": None if accepted is None else accepted.get("candidate_id"),
            "accepted_baseline_hash": None if accepted is None else accepted.get("candidate_hash"),
            "floor_artifacts": floors,
            "validation_layers": list(VALIDATION_LAYERS),
            "layer_sources": self._layer_sources(boundary_source, design_05, support),
            "summary": self._summary(floors, unresolved),
            "warnings": warnings,
            "unresolved_visual_evidence": unresolved,
            "visualization_policy": {
                "inspection_output_only": True,
                "geometry_invented": False,
                "geometry_smoothed": False,
                "geometry_snapped": False,
                "geometry_repaired": False,
                "envelope_enlarged": False,
                "missing_polygons_inferred": False,
                "automatic_merge": False,
                "layout_beautification": False,
                "random_colour_used": False,
                "runtime_theme_used": False,
            },
            "provenance": {
                "builder": "ArchitecturalDesignVisualValidationV1",
                "builder_version": VERSION,
                "output": "deterministic_svg_and_vector_records",
                "render_runtime_executed": False,
                "comfyui_executed": False,
                "bim_ifc_executed": False,
                "image_generation_executed": False,
                "structural_engine_executed": False,
                "source_mutated": False,
            },
        })
        artifact["artifact_hash"] = visual_validation_semantic_hash(artifact)
        return artifact

    # --------------------------------------------------
    # source resolution
    # --------------------------------------------------

    @staticmethod
    def _boundary_source(chain: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
        for key in ("accepted_baseline", "design_03", "design_02"):
            candidate = chain.get(key)
            if isinstance(candidate, Mapping) and isinstance(candidate.get("boundary_extraction"), Mapping):
                return dict(candidate["boundary_extraction"]), key
        return {}, None

    @staticmethod
    def _layer_sources(boundary_source: str | None, design_05: Mapping[str, Any] | None,
                       support: Mapping[str, Any] | None) -> dict[str, str]:
        return {
            "floor_envelope": "design_04.floor_geometries[*].polygon",
            "spaces": f"{boundary_source}.boundary_extraction.space_boundary_graphs" if boundary_source else "MISSING",
            "walls": f"{boundary_source}.boundary_extraction.wall_face_graphs" if boundary_source else "MISSING",
            "openings": f"{boundary_source}.boundary_extraction.opening_host_graphs" if boundary_source else "MISSING",
            "access": f"{boundary_source}.boundary_extraction.access_graph" if boundary_source else "MISSING",
            "external_spaces": "design_04.floor_geometries[*].external_spaces",
            "vertical_voids": "design_04.vertical_voids / design_05.vertical_void_constraints",
            "protected_zones": "design_04.protected_zones / design_05.protected_zones",
            "eligibility_regions": "design_05.eligible_support_regions" if design_05 else "MISSING",
            "exclusion_regions": "design_05.exclusion_zones" if design_05 else "MISSING",
            "support_candidates": "support_analysis.floors[*].candidate_support_regions" if support else "MISSING",
            "rejected_support_regions": "support_analysis.floors[*].rejected_support_regions" if support else "MISSING",
        }

    # --------------------------------------------------
    # floors
    # --------------------------------------------------

    def _floor_artifacts(self, design_04, boundary, boundary_source, design_05, support, unresolved):
        floors: list[dict[str, Any]] = []
        for index, floor in enumerate(design_04.get("floor_geometries", []) or []):
            if not isinstance(floor, Mapping):
                continue
            floor_id = str(floor.get("floor_id"))
            envelope = _ring(floor.get("polygon"))
            if not envelope:
                unresolved.append({"code": "FLOOR_ENVELOPE_GEOMETRY_MISSING", "floor_id": floor_id})
                continue

            layers = {name: [] for name in ALL_LAYERS}
            layers["floor_envelope"].append(_record(
                "POLYGON", deepcopy(envelope), "FLOOR_ENVELOPE",
                "design_04.floor_geometries[].polygon", floor.get("geometry_id"),
                area_m2=floor.get("area_m2"), elevation=floor.get("elevation"),
            ))

            self._plan_layers(layers, floor, floor_id, boundary, boundary_source)
            self._opening_access_layers(layers, floor_id, boundary, unresolved)
            self._void_layers(layers, floor_id, design_04, design_05)
            self._structural_layers(layers, floor_id, design_05, support)

            checks = self._geometry_checks(floor, envelope, layers)
            bounds = self._bounds(envelope, layers)
            views = {view: list(names) for view, names in VIEW_LAYERS.items()}
            svg = self._render(envelope, layers, list(VIEW_LAYERS), bounds,
                               f"{floor_id} ALL VIEWS")
            view_svgs = {
                view: self._render(envelope, layers, [view], bounds, f"{floor_id} {view}")
                for view in VIEW_LAYERS
            }

            floors.append({
                "floor_id": floor_id,
                "floor_label": f"FLOOR {floor_id}",
                "floor_order": int(floor.get("deterministic_order", index)),
                "elevation": floor.get("elevation"),
                "bounds": bounds,
                "viewbox": {
                    "min_x": bounds["min_x"] - SVG_PADDING, "min_y": bounds["min_y"] - SVG_PADDING,
                    "width": bounds["width"] + 2 * SVG_PADDING, "depth": bounds["depth"] + 2 * SVG_PADDING,
                },
                "layers": layers,
                "views": views,
                "geometry_checks": checks,
                "support_summary": self._support_summary(floor_id, support),
                "unresolved_items": [
                    item for item in unresolved
                    if item.get("floor_id") in (None, floor_id)
                ],
                "svg": svg,
                "svg_sha256": svg_sha256(svg),
                "view_svgs": view_svgs,
            })
        return floors

    def _plan_layers(self, layers, floor, floor_id, boundary, boundary_source):
        graphs = boundary.get("space_boundary_graphs", {})
        record = graphs.get(floor_id) if isinstance(graphs, Mapping) else None
        spaces = record.get("spaces", []) if isinstance(record, Mapping) else []
        for space in spaces if isinstance(spaces, list) else []:
            if not isinstance(space, Mapping):
                continue
            ring = _ring(space.get("polygon"))
            if not ring:
                continue
            layers["spaces"].append(_record(
                "POLYGON", ring, "SPACE_BOUNDARY",
                f"{boundary_source}.boundary_extraction.space_boundary_graphs.{floor_id}.spaces",
                space.get("space_id"), semantic_class=space.get("semantic_class"),
                external=space.get("external"),
            ))

        faces = boundary.get("wall_face_graphs", {})
        record = faces.get(floor_id) if isinstance(faces, Mapping) else None
        for face in (record.get("faces", []) if isinstance(record, Mapping) else []) or []:
            if not isinstance(face, Mapping):
                continue
            start, end = _ring([face.get("start")]), _ring([face.get("end")])
            if not start or not end:
                continue
            layers["walls"].append(_record(
                "POLYLINE", [start[0], end[0]], "WALL",
                f"{boundary_source}.boundary_extraction.wall_face_graphs.{floor_id}.faces",
                face.get("face_id"),
            ))

        for external in floor.get("external_spaces", []) or []:
            if not isinstance(external, Mapping):
                continue
            ring = _ring(external.get("polygon"))
            if not ring:
                continue
            layers["external_spaces"].append(_record(
                "POLYGON", ring, "EXTERNAL_SPACE",
                "design_04.floor_geometries[].external_spaces",
                external.get("space_id") or external.get("terrace_id"),
                semantic_class=external.get("semantic_class"),
            ))

    def _opening_access_layers(self, layers, floor_id, boundary, unresolved):
        faces = boundary.get("wall_face_graphs", {})
        record = faces.get(floor_id) if isinstance(faces, Mapping) else None
        face_index: dict[str, list[list[float]]] = {}
        for face in (record.get("faces", []) if isinstance(record, Mapping) else []) or []:
            if not isinstance(face, Mapping):
                continue
            start, end = _ring([face.get("start")]), _ring([face.get("end")])
            if start and end:
                face_index[str(face.get("face_id"))] = [start[0], end[0]]

        hosts = boundary.get("opening_host_graphs", {})
        record = hosts.get(floor_id) if isinstance(hosts, Mapping) else None
        for opening in (record.get("openings", []) if isinstance(record, Mapping) else []) or []:
            if not isinstance(opening, Mapping):
                continue
            segment = face_index.get(str(opening.get("host_face_a")))
            if not segment:
                unresolved.append({
                    "code": "OPENING_HOST_GEOMETRY_UNRESOLVED",
                    "floor_id": floor_id, "opening_id": opening.get("opening_id"),
                })
                continue
            layers["openings"].append(_record(
                "POLYLINE", deepcopy(segment), "OPENING",
                f"boundary_extraction.opening_host_graphs.{floor_id}.openings",
                opening.get("opening_id"), kind=opening.get("kind"),
                host_face_id=opening.get("host_face_a"),
            ))

        graph = boundary.get("access_graph", {})
        for edge in (graph.get("edges", []) if isinstance(graph, Mapping) else []) or []:
            if not isinstance(edge, Mapping):
                continue
            layers["access"].append(_record(
                "RELATION_MARKER", [], "ACCESS",
                "boundary_extraction.access_graph.edges", edge.get("id"),
                from_node=edge.get("from"), to_node=edge.get("to"), kind=edge.get("kind"),
                representable=False,
                representation_reason="access_graph_nodes_carry_no_coordinates",
            ))

    @staticmethod
    def _append_unique(records: list[dict[str, Any]], record: dict[str, Any]) -> None:
        """Append unless the same canonical record identity is already present.

        Design-04 and Design-05 both republish the same protected/void records;
        displaying them twice would misrepresent the architecture.  This is an
        identity de-duplication only — never a geometry merge.
        """
        key = (record["style_token"], str(record["source_record_id"]))
        if any((item["style_token"], str(item["source_record_id"])) == key for item in records):
            return
        records.append(record)

    def _void_layers(self, layers, floor_id, design_04, design_05):
        for void in design_04.get("vertical_voids", []) or []:
            if not isinstance(void, Mapping):
                continue
            if not self._on_floor(void, floor_id):
                continue
            ring = _ring(void.get("polygon"))
            if not ring:
                continue
            self._append_unique(layers["vertical_voids"], _record(
                "POLYGON", ring, "VERTICAL_VOID",
                "design_04.vertical_voids", void.get("void_id") or void.get("id"),
                void_type=void.get("type") or void.get("void_type"),
            ))

        for zone in design_04.get("protected_zones", []) or []:
            if not isinstance(zone, Mapping) or not self._on_floor(zone, floor_id):
                continue
            ring = _ring(zone.get("polygon"))
            if not ring:
                continue
            self._append_unique(layers["protected_zones"], _record(
                "POLYGON", ring, "PROTECTED_ZONE",
                "design_04.protected_zones", zone.get("zone_id") or zone.get("void_id"),
                zone_type=zone.get("zone_type"),
            ))

        if isinstance(design_05, Mapping):
            for void in design_05.get("vertical_void_constraints", []) or []:
                if not isinstance(void, Mapping) or not self._on_floor(void, floor_id):
                    continue
                ring = _ring(void.get("polygon"))
                if not ring:
                    continue
                self._append_unique(layers["vertical_voids"], _record(
                    "POLYGON", ring, "VERTICAL_VOID",
                    "design_05.vertical_void_constraints", void.get("void_id") or void.get("zone_id"),
                    zone_type=void.get("zone_type"),
                ))
            for zone in design_05.get("protected_zones", []) or []:
                if not isinstance(zone, Mapping) or not self._on_floor(zone, floor_id):
                    continue
                ring = _ring(zone.get("polygon"))
                if not ring:
                    continue
                self._append_unique(layers["protected_zones"], _record(
                    "POLYGON", ring, "PROTECTED_ZONE",
                    "design_05.protected_zones", zone.get("zone_id") or zone.get("void_id"),
                    zone_type=zone.get("zone_type"),
                ))
            for zone in design_05.get("exclusion_zones", []) or []:
                if not isinstance(zone, Mapping) or not self._on_floor(zone, floor_id):
                    continue
                ring = _ring(zone.get("polygon"))
                if not ring:
                    continue
                layers["exclusion_regions"].append(_record(
                    "POLYGON", ring, "EXCLUSION_REGION",
                    "design_05.exclusion_zones",
                    zone.get("constraint_id") or zone.get("zone_id"),
                    constraint_type=zone.get("constraint_type") or zone.get("zone_type"),
                ))
            for item in design_05.get("external_space_constraints", []) or []:
                if not isinstance(item, Mapping) or not self._on_floor(item, floor_id):
                    continue
                ring = _ring(item.get("polygon"))
                if not ring:
                    continue
                layers["external_spaces"].append(_record(
                    "POLYGON", ring, "EXTERNAL_SPACE",
                    "design_05.external_space_constraints",
                    item.get("constraint_id") or item.get("space_id") or item.get("terrace_id"),
                    constraint_type=item.get("constraint_type"),
                    structural_policy=item.get("structural_policy"),
                ))

    def _structural_layers(self, layers, floor_id, design_05, support):
        if isinstance(design_05, Mapping):
            for region in design_05.get("eligible_support_regions", []) or []:
                if not isinstance(region, Mapping) or str(region.get("floor_id")) != floor_id:
                    continue
                for surface in region.get("polygons", []) or []:
                    ring = _surface_ring(surface)
                    if not ring:
                        continue
                    layers["eligibility_regions"].append(_record(
                        "POLYGON", ring, "ELIGIBILITY_REGION",
                        "design_05.eligible_support_regions[].polygons",
                        region.get("region_id"),
                        area_m2=region.get("area_m2"),
                        eligibility_status=region.get("eligibility_status"),
                    ))

        if not isinstance(support, Mapping):
            return
        for floor in support.get("floors", []) or []:
            if not isinstance(floor, Mapping) or str(floor.get("floor_id")) != floor_id:
                continue
            for order, candidate in enumerate(floor.get("candidate_support_regions", []) or [], start=1):
                if not isinstance(candidate, Mapping):
                    continue
                point = _ring([candidate.get("point")])
                if not point:
                    continue
                layers["support_candidates"].append(_record(
                    "POINT", point[0], "SUPPORT_CANDIDATE",
                    "support_analysis.floors[].candidate_support_regions",
                    candidate.get("point"),
                    label=f"SUP-{floor_id}-{order:02d}",
                    kind=candidate.get("kind"),
                    committed=candidate.get("committed", False),
                    is_column=candidate.get("is_column", False),
                ))
            for order, rejected in enumerate(floor.get("rejected_support_regions", []) or [], start=1):
                if not isinstance(rejected, Mapping):
                    continue
                point = _ring([rejected.get("point")])
                if not point:
                    continue
                layers["rejected_support_regions"].append(_record(
                    "POINT", point[0], "REJECTED_SUPPORT_REGION",
                    "support_analysis.floors[].rejected_support_regions",
                    rejected.get("point"),
                    label=f"REJ-{floor_id}-{order:02d}",
                    reason=rejected.get("reason"),
                    excluded_by=rejected.get("excluded_by"),
                    committed=False,
                ))

    @staticmethod
    def _on_floor(item: Mapping[str, Any], floor_id: str) -> bool:
        values = item.get("floor_ids")
        if isinstance(values, (list, tuple)):
            return floor_id in {str(value) for value in values}
        value = item.get("floor_id")
        return value is None or str(value) == floor_id

    # --------------------------------------------------
    # checks / bounds / summary
    # --------------------------------------------------

    def _geometry_checks(self, floor, envelope, layers) -> dict[str, Any]:
        shape = Polygon(envelope) if len(envelope) >= 4 else None
        exclusions = [
            Polygon(record["coordinates"]) for record in layers["exclusion_regions"]
            if len(record["coordinates"]) >= 4
        ]
        inside = 0
        for record in layers["support_candidates"]:
            point = Point(record["coordinates"][0], record["coordinates"][1])
            if any(polygon.contains(point) for polygon in exclusions):
                inside += 1

        min_x = min(point[0] for point in envelope)
        max_x = max(point[0] for point in envelope)
        min_y = min(point[1] for point in envelope)
        max_y = max(point[1] for point in envelope)
        bounding_area = (max_x - min_x) * (max_y - min_y)
        envelope_area = float(shape.area) if shape is not None else 0.0

        return {
            "envelope_polygon": deepcopy(envelope),
            "envelope_area_m2": round(envelope_area, 6),
            "envelope_bounds": {
                "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
                "width": round(max_x - min_x, 6), "depth": round(max_y - min_y, 6),
            },
            "bounding_box_area_m2": round(bounding_area, 6),
            "rectangularisation_detected": bool(
                envelope_area > 0 and abs(envelope_area - bounding_area) <= 1e-9
                and len(envelope) > 5
            ),
            "envelope_matches_source": deepcopy(envelope) == _ring(floor.get("polygon")),
            "space_count": len(layers["spaces"]),
            "wall_count": len(layers["walls"]),
            "opening_count": len(layers["openings"]),
            "access_relation_count": len(layers["access"]),
            "external_space_count": len(layers["external_spaces"]),
            "vertical_void_count": len(layers["vertical_voids"]),
            "protected_zone_count": len(layers["protected_zones"]),
            "eligibility_region_count": len(layers["eligibility_regions"]),
            "exclusion_region_count": len(layers["exclusion_regions"]),
            "support_candidate_count": len(layers["support_candidates"]),
            "rejected_support_region_count": len(layers["rejected_support_regions"]),
            "support_candidates_inside_exclusions": inside,
        }

    @staticmethod
    def _bounds(envelope, layers) -> dict[str, float]:
        points = list(envelope)
        for name in ALL_LAYERS:
            for record in layers.get(name, []):
                coordinates = record.get("coordinates")
                if record.get("geometry_type") == "POINT" and coordinates:
                    points.append(coordinates)
                elif record.get("geometry_type") in ("POLYGON", "POLYLINE"):
                    points.extend(coordinates)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return {
            "min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys),
            "width": max(xs) - min(xs), "depth": max(ys) - min(ys),
        }

    @staticmethod
    def _support_summary(floor_id, support) -> dict[str, Any]:
        if not isinstance(support, Mapping):
            return {"available": False}
        for floor in support.get("floors", []) or []:
            if isinstance(floor, Mapping) and str(floor.get("floor_id")) == floor_id:
                return {
                    "available": True,
                    "eligible_area_m2": floor.get("eligible_area_m2"),
                    "candidate_count": len(floor.get("candidate_support_regions", []) or []),
                    "rejected_count": len(floor.get("rejected_support_regions", []) or []),
                    "axis_opportunities": deepcopy(floor.get("candidate_axis_opportunities", {})),
                    "analysis_status": support.get("status"),
                    "committed_columns": floor.get("committed_columns", []),
                    "committed_beams": floor.get("committed_beams", []),
                }
        return {"available": False}

    @staticmethod
    def _summary(floors, unresolved) -> dict[str, Any]:
        def total(key: str) -> int:
            return sum(int(floor["geometry_checks"].get(key, 0)) for floor in floors)

        return {
            "floor_count": len(floors),
            "floors": [
                {"floor_id": floor["floor_id"], "order": floor["floor_order"],
                 "area_m2": floor["geometry_checks"]["envelope_area_m2"]}
                for floor in floors
            ],
            "total_floor_area_m2": round(sum(
                floor["geometry_checks"]["envelope_area_m2"] for floor in floors), 6),
            "space_count": total("space_count"),
            "opening_count": total("opening_count"),
            "protected_zone_count": total("protected_zone_count"),
            "support_candidate_count": total("support_candidate_count"),
            "rejected_region_count": total("rejected_support_region_count"),
            "unresolved_count": len(unresolved),
        }

    # --------------------------------------------------
    # deterministic SVG
    # --------------------------------------------------

    def _render(self, envelope, layers, views, bounds, title) -> str:
        min_x, min_y = bounds["min_x"], bounds["min_y"]
        max_y = bounds["max_y"]
        pad = SVG_PADDING
        scale = SVG_UNITS_PER_METRE
        width = (bounds["width"] + 2 * pad) * scale
        height = (bounds["depth"] + 2 * pad) * scale

        def point(value):
            x = (float(value[0]) - min_x + pad) * scale
            y = (max_y - float(value[1]) + pad) * scale
            return f"{x:.3f},{y:.3f}"

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
            f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">',
            f'<rect x="0" y="0" width="{width:.3f}" height="{height:.3f}" fill="{SVG_BACKGROUND}"/>',
            f'<text x="6.000" y="14.000" font-family="{SVG_FONT_FAMILY}" font-size="11" '
            f'fill="#333333">{self._escape(title)}</text>',
        ]
        for view in views:
            parts.append(f'<g id="view-{view}">')
            for layer in VIEW_LAYERS.get(view, ()):
                parts.append(f'<g id="layer-{layer}">')
                for record in layers.get(layer, []):
                    parts.extend(self._draw(record, point))
                parts.append("</g>")
            parts.append("</g>")
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _draw(record, point) -> list[str]:
        style = STYLE_TOKENS[record["style_token"]]
        stroke = style["stroke"]
        stroke_width = style["stroke_width"]
        dash = "" if style.get("dash") is None else f' stroke-dasharray="{style["dash"]}"'
        fill = style.get("fill", "none")
        opacity = style.get("fill_opacity")
        fill_opacity = "" if opacity is None else f' fill-opacity="{opacity}"'
        coordinates = record.get("coordinates")
        kind = record.get("geometry_type")

        if kind == "POLYGON":
            points = " ".join(point(item) for item in coordinates)
            return [f'<polygon points="{points}" fill="{fill}"{fill_opacity} '
                    f'stroke="{stroke}" stroke-width="{stroke_width}"{dash}/>']
        if kind == "POLYLINE":
            points = " ".join(point(item) for item in coordinates)
            return [f'<polyline points="{points}" fill="none" stroke="{stroke}" '
                    f'stroke-width="{stroke_width}"{dash}/>']
        if kind == "POINT":
            radius = style.get("radius") or 0.15
            return [f'<circle cx="{point(coordinates).split(",")[0]}" '
                    f'cy="{point(coordinates).split(",")[1]}" r="{radius * SVG_UNITS_PER_METRE:.3f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"{dash}/>']
        # RELATION_MARKER without coordinates carries no drawable geometry.
        return []

    @staticmethod
    def _escape(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    # --------------------------------------------------
    # blocked artifact
    # --------------------------------------------------

    def _failed(self, conflicts, chain: Mapping[str, Any] | None = None) -> ArchitecturalVisualValidationV1:
        source = chain if isinstance(chain, Mapping) else {}
        artifact = ArchitecturalVisualValidationV1({
            "contract": CONTRACT,
            "version": VERSION,
            "artifact_status": STATUS_INSUFFICIENT_VISUAL_SOURCE if chain is not None else STATUS_FAILED,
            "artifact_kind": "READ_ONLY_INSPECTION_OUTPUT",
            "source_candidate_id": (source.get("design_04") or {}).get("candidate_id")
            if isinstance(source.get("design_04"), Mapping) else None,
            "source_candidate_version": None,
            "source_candidate_hash": None,
            "accepted_baseline_id": (source.get("accepted_baseline") or {}).get("candidate_id")
            if isinstance(source.get("accepted_baseline"), Mapping) else None,
            "accepted_baseline_hash": None,
            "floor_artifacts": [],
            "validation_layers": list(VALIDATION_LAYERS),
            "layer_sources": {},
            "summary": {"floor_count": 0, "floors": [], "total_floor_area_m2": 0.0,
                        "space_count": 0, "opening_count": 0, "protected_zone_count": 0,
                        "support_candidate_count": 0, "rejected_region_count": 0,
                        "unresolved_count": len(conflicts)},
            "warnings": [{"code": "NO_VISUAL_ARTIFACT", "conflicts": deepcopy(conflicts)}],
            "unresolved_visual_evidence": deepcopy(conflicts),
            "visualization_policy": {"inspection_output_only": True, "geometry_invented": False},
            "provenance": {
                "builder": "ArchitecturalDesignVisualValidationV1",
                "builder_version": VERSION,
                "render_runtime_executed": False,
                "comfyui_executed": False,
                "bim_ifc_executed": False,
                "image_generation_executed": False,
                "structural_engine_executed": False,
                "source_mutated": False,
            },
        })
        artifact["artifact_hash"] = visual_validation_semantic_hash(artifact)
        return artifact

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------

    @staticmethod
    def hash(artifact: Mapping[str, Any]) -> str:
        return visual_validation_semantic_hash(artifact)

    @staticmethod
    def canonical(artifact: Mapping[str, Any]) -> str:
        return canonical_visual_validation_document(artifact)


architectural_design_visual_validation = ArchitecturalDesignVisualValidationV1()


def build_architectural_visual_validation(chain: Mapping[str, Any]) -> ArchitecturalVisualValidationV1:
    """Module-level convenience wrapper over the canonical builder."""
    return architectural_design_visual_validation.build(chain)


__all__ = [
    "ArchitecturalVisualValidationV1", "ArchitecturalDesignVisualValidationV1",
    "build_architectural_visual_validation", "architectural_design_visual_validation",
    "VIEW_LAYERS", "ALL_LAYERS",
]
