"""Evidence-gated comparison of generated architecture with a DXF contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ReferenceAcceptanceComparator:
    """Compare four independent acceptance dimensions without reference guessing."""

    CATEGORIES = ("Semantic", "Topological", "Geometric", "Representational")

    def compare(
        self,
        reference: dict[str, Any],
        generated: dict[str, Any],
    ) -> dict[str, Any]:
        facts = reference.get("facts", [])
        metadata = {
            fact.get("fact_type"): fact
            for fact in facts
            if fact.get("provenance", {}).get("source_entity") == "USER_METADATA"
        }
        entities = reference.get("modelspace", {}).get("entities", [])
        views = reference.get("views", [])
        intent = generated.get("architectural_intent", {}) or {}
        geometry = generated.get("geometry", {}) or {}
        exports = generated.get("exports", {}) or {}

        sections: dict[str, dict[str, Any]] = {
            name: {"checks": [], "hard_failures": 0, "warnings": 0}
            for name in self.CATEGORIES
        }
        divergences: list[dict[str, Any]] = []

        self._check(
            sections,
            divergences,
            category="Semantic",
            name="building_type",
            reference_fact=metadata.get("building_type"),
            generated_value=intent.get("building_type"),
            passed=intent.get("building_type") == metadata.get("building_type", {}).get("value"),
            severity="critical",
            responsible="INTENT",
            module="core/prompt_intelligence/architectural_intent.py",
            recommendation="Preserve user-explicit building type through the production context.",
        )
        generated_storeys = self._storey_count(intent, generated)
        self._check(
            sections,
            divergences,
            category="Semantic",
            name="storey_count",
            reference_fact=metadata.get("storeys"),
            generated_value=generated_storeys,
            passed=generated_storeys == metadata.get("storeys", {}).get("value"),
            severity="critical",
            responsible="VERTICAL",
            module="core/prompt_intelligence/architectural_intent.py",
            recommendation="Carry the parsed one-storey level contract into architecture-first geometry.",
        )

        reference_relationships = [
            fact for fact in facts
            if fact.get("fact_type") == "space_relationship"
            and fact.get("status") == "AUTHORITATIVE"
        ]
        if reference_relationships:
            generated_relationships = intent.get("relationships", [])
            self._check(
                sections, divergences, category="Topological", name="space_relationships",
                reference_fact={"status": "AUTHORITATIVE", "value": reference_relationships,
                                "provenance": reference_relationships[0]["provenance"]},
                generated_value=generated_relationships,
                passed=bool(generated_relationships), severity="high", responsible="TOPOLOGY",
                module="core/architecture/reasoning/architectural_layout_reasoner_v1.py",
                recommendation="Preserve evidenced adjacency and connectivity in the spatial graph.",
            )
        else:
            sections["Topological"]["checks"].append({
                "name": "space_relationships",
                "result": "NOT_ASSERTED",
                "reference_status": "UNRESOLVED",
                "reason": "The DXF has no authoritative room-boundary/adjacency binding yet.",
            })

        dimensions = [
            entity for entity in entities if entity.get("entity_type") == "DIMENSION"
        ]
        measured = [
            entity.get("geometry", {}).get("measurement") for entity in dimensions
            if entity.get("geometry", {}).get("measurement") is not None
        ]
        sections["Geometric"]["checks"].append({
            "name": "dimension_chain_agreement",
            "result": "NOT_ASSERTED",
            "reference_status": "AUTHORITATIVE_MEASUREMENT_UNRESOLVED_SEMANTIC_ROLE",
            "reference_measurements": measured,
            "generated_value": self._geometry_spans(geometry),
            "reason": "Measurements are authoritative, but their binding to footprint/rooms is unresolved.",
        })
        sections["Geometric"]["checks"].append({
            "name": "normalized_alignment",
            "result": "READY",
            "reference_status": "AUTHORITATIVE",
            "allowed": ["translation", "rotation"],
            "deformation_allowed": False,
            "scale": 1.0,
        })
        authoritative_geometry = bool(
            generated.get("architecture_first")
            and any(geometry.get(key) for key in (
                "physical_walls", "openings", "slabs", "floor_geometry"
            ))
        )
        geometry_fact = {
            "status": "AUTHORITATIVE",
            "value": "DXF contains explicit wall/opening/floor geometry",
            "provenance": next(
                (entity["provenance"] for entity in entities if entity["entity_type"] == "LINE"),
                reference["file_identity"]["provenance"],
            ),
        }
        self._check(
            sections, divergences, category="Geometric", name="authoritative_architectural_geometry",
            reference_fact=geometry_fact,
            generated_value={
                "architecture_first": generated.get("architecture_first"),
                "geometry_counts": self._geometry_counts(geometry),
            },
            passed=authoritative_geometry,
            severity="critical", responsible="GEOMETRY",
            module="core/intelligence/architectos_design_execution_bridge_v100.py",
            recommendation=(
                "Keep ArchitecturalGeometryEngineV2 output authoritative through execution; "
                "do not replace it with the legacy room-only DesignGeometryAdapter result."
            ),
        )

        reference_representation = {
            "floor_plan_views": sum(view.get("probable_view_type") == "floor_plan" for view in views),
            "elevation_views": sum(view.get("probable_view_type") == "elevation" for view in views),
            "dimensions": len(dimensions),
            "door_evidence": self._has_named_block(reference, "Door"),
            "window_evidence": self._has_named_block(reference, "Window"),
        }
        export_files = generated.get("export_files", {}) or {}
        inspection = generated.get("artifact_inspection", {}) or {}
        real_outputs = {
            key: str(value) if value else None for key, value in export_files.items()
        }
        files_exist = {
            key: bool(value and Path(value).is_file()) for key, value in export_files.items()
        }
        export_passed = exports.get("status") == "completed" and all(
            files_exist.get(key) for key in ("ifc", "dxf")
        )
        representation_fact = {
            "status": "AUTHORITATIVE",
            "value": reference_representation,
            "provenance": reference["file_identity"]["provenance"],
        }
        self._check(
            sections, divergences, category="Representational", name="real_production_exports",
            reference_fact=representation_fact,
            generated_value={
                "export_status": exports.get("status"),
                "export_error": exports.get("error"),
                "paths": real_outputs,
                "files_exist": files_exist,
            },
            passed=export_passed,
            severity="critical", responsible="IFC",
            module="core/export/ifc_export_engine.py:6068",
            recommendation=(
                "Guard the post-containment IFC debug/storey inspection against an empty "
                "storeys mapping instead of reading the loop variable level after a zero-iteration loop."
            ),
        )

        generated_dxf = inspection.get("dxf", {}) or {}
        generated_entity_counts = generated_dxf.get("entity_counts", {}) or {}
        if dimensions:
            self._check(
                sections, divergences, category="Representational",
                name="dimension_entities_present",
                reference_fact={
                    "status": "AUTHORITATIVE",
                    "value": len(dimensions),
                    "provenance": dimensions[0].get("provenance"),
                },
                generated_value=generated_entity_counts.get("DIMENSION", 0),
                passed=generated_entity_counts.get("DIMENSION", 0) > 0,
                severity="high", responsible="CAD",
                module="core/export/dwg/dwg_writer.py",
                recommendation=(
                    "Emit evidence-backed architectural dimension entities from the "
                    "resolved geometry contract; do not copy reference dimensions."
                ),
            )
        reference_elevations = sum(
            view.get("probable_view_type") == "elevation" for view in views
        )
        if reference_elevations:
            generated_elevations = generated_dxf.get("elevation_view_count", 0)
            self._check(
                sections, divergences, category="Representational",
                name="elevation_views_present",
                reference_fact={
                    "status": "AUTHORITATIVE",
                    "value": reference_elevations,
                    "provenance": reference["file_identity"]["provenance"],
                },
                generated_value=generated_elevations,
                passed=generated_elevations > 0,
                severity="high", responsible="CAD",
                module="core/export/dwg/dwg_writer.py",
                recommendation=(
                    "Generate north/south elevation views from authoritative walls, "
                    "openings, roof and level geometry."
                ),
            )

        return {
            "schema": "architectos.reference_acceptance_comparison/1.0",
            "benchmark": reference.get("file_identity", {}),
            "generated_run": {
                "prompt": generated.get("prompt"),
                "output_dir": generated.get("output_dir"),
                "production_status": exports.get("status"),
                "production_error": exports.get("error"),
            },
            "policy": reference.get("evidence_policy", {}),
            "sections": sections,
            "divergences": divergences,
            "summary": {
                "hard_failures": sum(section["hard_failures"] for section in sections.values()),
                "warnings": sum(section["warnings"] for section in sections.values()),
                "acceptance_status": "FAILED" if divergences else "PASSED",
            },
        }

    def _check(
        self, sections: dict[str, Any], divergences: list[dict[str, Any]], *,
        category: str, name: str, reference_fact: dict[str, Any] | None,
        generated_value: Any, passed: bool, severity: str, responsible: str,
        module: str, recommendation: str,
    ) -> None:
        status = (reference_fact or {}).get("status", "UNRESOLVED")
        hard = status == "AUTHORITATIVE"
        result = "PASS" if passed else ("FAIL" if hard else "WARNING")
        check = {
            "name": name,
            "result": result,
            "reference_fact": (reference_fact or {}).get("value"),
            "generated_fact": generated_value,
            "evidence_status": status,
            "source_evidence": (reference_fact or {}).get("provenance"),
        }
        sections[category]["checks"].append(check)
        if passed:
            return
        if hard:
            sections[category]["hard_failures"] += 1
        else:
            sections[category]["warnings"] += 1
        divergences.append({
            "category": responsible,
            "comparison_section": category,
            "reference_fact": check["reference_fact"],
            "generated_fact": generated_value,
            "difference": f"{name} did not satisfy the evidence-gated comparison",
            "evidence_status": status,
            "severity": severity if hard else "warning",
            "source_evidence": check["source_evidence"],
            "likely_responsible_subsystem": responsible,
            "likely_responsible_module": module,
            "recommended_fix": recommendation,
        })

    def _storey_count(self, intent: dict[str, Any], generated: dict[str, Any]) -> int | None:
        vertical = generated.get("vertical_section", {}).get("levels", [])
        if vertical:
            return len([
                level for level in vertical
                if isinstance(level, dict)
                and str(level.get("name", "")).upper() != "SITE"
            ])
        levels = intent.get("levels", {})
        if isinstance(levels, dict) and levels.get("total") is not None:
            return int(levels["total"])
        program_levels = intent.get("building_program", {}).get("levels", [])
        if isinstance(program_levels, list) and program_levels:
            return len(program_levels)
        return None

    def _geometry_counts(self, geometry: dict[str, Any]) -> dict[str, int]:
        return {
            key: len(value) for key, value in geometry.items() if isinstance(value, list)
        }

    def _geometry_spans(self, geometry: dict[str, Any]) -> dict[str, float] | None:
        points = []
        for collection in ("rooms", "spaces", "physical_walls", "walls"):
            for item in geometry.get(collection, []) or []:
                nested = item.get("geometry", {}) if isinstance(item.get("geometry"), dict) else {}
                x = item.get("x", nested.get("x"))
                y = item.get("y", nested.get("y"))
                width = item.get("w", item.get("width", nested.get("w", nested.get("width"))))
                height = item.get("h", item.get("depth", nested.get("h", nested.get("depth"))))
                if None not in (x, y, width, height):
                    points.extend([
                        [float(x), float(y)],
                        [float(x) + float(width), float(y) + float(height)],
                    ])
                for key in ("polygon", "points", "centerline"):
                    value = item.get(key)
                    if isinstance(value, list):
                        points.extend(point for point in value if isinstance(point, (list, tuple)) and len(point) >= 2)
                for key in ("start", "end"):
                    point = item.get(key)
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        points.append(point)
        if not points:
            return None
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return {"width": max(xs) - min(xs), "height": max(ys) - min(ys)}

    def _has_named_block(self, reference: dict[str, Any], token: str) -> bool:
        lowered = token.lower()
        return any(lowered in block.get("name", "").lower() for block in reference.get("blocks", []))
