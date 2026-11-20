"""Evidence-only DXF adapter used by architectural reference acceptance.

This module deliberately does not import or call ArchitectOS design engines.  It
records what a DXF says, where it says it, and how confidently it can be used.
It does not turn generic lines into walls or attach architectural meaning to
unlabelled geometry.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import ezdxf
from ezdxf import bbox


EVIDENCE_STATUSES = {"AUTHORITATIVE", "INFERRED", "UNRESOLVED"}


def _number(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    try:
        result = float(value)
    except (TypeError, ValueError):
        return value
    return result if math.isfinite(result) else None


def _point(value: Any, dimensions: int = 3) -> list[float] | None:
    if value is None:
        return None
    try:
        values = list(value)
    except TypeError:
        return None
    values += [0.0] * max(0, dimensions - len(values))
    return [float(values[index]) for index in range(dimensions)]


def _provenance(
    source_file: Path,
    *,
    layer: str | None = None,
    entity_type: str | None = None,
    handle: str | None = None,
    evidence: str,
) -> dict[str, Any]:
    return {
        "source_file": str(source_file.resolve()),
        "source_layer": layer,
        "source_entity": entity_type,
        "handle": handle,
        "evidence": evidence,
    }


def _fact(
    value: Any,
    status: str,
    provenance: dict[str, Any],
    confidence: float,
    fact_type: str,
) -> dict[str, Any]:
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"Unsupported evidence status: {status}")
    return {
        "fact_type": fact_type,
        "status": status,
        "value": value,
        "provenance": provenance,
        "confidence": float(confidence),
    }


class ReferenceDXFEvidenceAdapter:
    """Extract a provenance-rich, read-only contract from a DXF file."""

    SCHEMA = "architectos.reference_dxf_evidence/1.0"
    UNIT_NAMES = {
        0: "unitless",
        1: "inches",
        2: "feet",
        3: "miles",
        4: "millimeters",
        5: "centimeters",
        6: "meters",
        7: "kilometers",
        8: "microinches",
        9: "mils",
        10: "yards",
        14: "decimeters",
    }
    VIEW_TITLES = {
        "FLOOR PLAN": "floor_plan",
        "MEZZANINE PLAN": "mezzanine_plan",
        "SPLIT-LEVEL FLOOR": "mezzanine_plan",
        "ROOF PLAN": "roof_plan",
        "SITE PLAN": "site_plan",
        "SOUTH ELEVATION": "elevation",
        "NORTH ELEVATION": "elevation",
        "EAST ELEVATION": "elevation",
        "WEST ELEVATION": "elevation",
        "SECTION 1-1": "section",
        "SECTION 2-2": "section",
    }

    def extract(
        self,
        source: str | Path,
        *,
        user_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        document = ezdxf.readfile(path)
        modelspace = document.modelspace()
        model_entities = [
            self._entity_record(entity, path, "Model") for entity in modelspace
        ]
        extents = self._extents(modelspace)
        declared_unit_code = int(document.header.get("$INSUNITS", 0) or 0)
        declared_unit_name = self.UNIT_NAMES.get(
            declared_unit_code, f"dxf_unit_code_{declared_unit_code}"
        )

        identity_provenance = _provenance(
            path, entity_type="FILE", evidence="filesystem and SHA-256 digest"
        )
        header_provenance = _provenance(
            path, entity_type="DXF_HEADER", evidence="DXF header variable"
        )

        layers = []
        for layer in document.layers:
            layers.append(
                {
                    "name": layer.dxf.name,
                    "color": int(layer.dxf.color),
                    "linetype": layer.dxf.linetype,
                    "is_off": bool(layer.is_off()),
                    "is_frozen": bool(layer.is_frozen()),
                    "provenance": _provenance(
                        path,
                        layer=layer.dxf.name,
                        entity_type="LAYER",
                        handle=getattr(layer.dxf, "handle", None),
                        evidence="DXF layer table record",
                    ),
                }
            )

        layouts = []
        for layout in document.layouts:
            layouts.append(
                {
                    "name": layout.name,
                    "entity_count": len(layout),
                    "is_modelspace": layout.name == "Model",
                    "provenance": _provenance(
                        path,
                        entity_type="LAYOUT",
                        handle=getattr(layout.dxf, "handle", None),
                        evidence="DXF layout table record",
                    ),
                }
            )

        blocks = []
        for block in document.blocks:
            flags = int(getattr(block.block.dxf, "flags", 0) or 0)
            blocks.append(
                {
                    "name": block.name,
                    "handle": getattr(block.block.dxf, "handle", None),
                    "base_point": _point(getattr(block.block.dxf, "base_point", None)),
                    "flags": flags,
                    "is_xref": bool(flags & (4 | 8)),
                    "entity_count": len(block),
                    "entities": [
                        self._entity_record(entity, path, f"BLOCK:{block.name}")
                        for entity in block
                    ],
                    "provenance": _provenance(
                        path,
                        entity_type="BLOCK",
                        handle=getattr(block.block.dxf, "handle", None),
                        evidence="DXF block definition",
                    ),
                }
            )

        inserts = [
            entity for entity in model_entities if entity["entity_type"] == "INSERT"
        ]
        text_records = [
            entity
            for entity in model_entities
            if entity["entity_type"] in {"TEXT", "MTEXT"}
        ]
        dimensions = [
            entity for entity in model_entities if entity["entity_type"] == "DIMENSION"
        ]
        hatches = [
            entity for entity in model_entities if entity["entity_type"] == "HATCH"
        ]
        clusters = self._detect_views(model_entities, path, extents, declared_unit_name)
        view_relationships = self._view_relationships(clusters, dimensions, path)

        metadata_facts = []
        for key, value in (user_metadata or {}).items():
            metadata_facts.append(
                _fact(
                    value,
                    "AUTHORITATIVE",
                    _provenance(
                        path,
                        entity_type="USER_METADATA",
                        evidence=f"user-provided benchmark metadata: {key}",
                    ),
                    1.0,
                    key,
                )
            )

        extracted_facts = list(metadata_facts)
        for record in text_records:
            encoding = record.get("encoding", {})
            status = (
                "AUTHORITATIVE"
                if encoding.get("status") == "valid_unicode"
                else "UNRESOLVED"
            )
            extracted_facts.append(
                _fact(
                    record["geometry"].get("plain_text"),
                    status,
                    record["provenance"],
                    1.0 if status == "AUTHORITATIVE" else 0.0,
                    "drawing_text",
                )
            )
        for record in dimensions:
            extracted_facts.append(
                _fact(
                    record["geometry"].get("measurement"),
                    "AUTHORITATIVE",
                    record["provenance"],
                    1.0,
                    "dimension_measurement",
                )
            )

        effective_unit_status = "AUTHORITATIVE" if declared_unit_code else "UNRESOLVED"
        contract = {
            "schema": self.SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "read_only_evidence_extraction",
            "file_identity": {
                "path": str(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "provenance": identity_provenance,
            },
            "dxf": {
                "version": _fact(
                    document.dxfversion, "AUTHORITATIVE", header_provenance, 1.0, "dxf_version"
                ),
                "acad_release": _fact(
                    document.acad_release, "AUTHORITATIVE", header_provenance, 1.0, "acad_release"
                ),
                "declared_units": _fact(
                    {"code": declared_unit_code, "name": declared_unit_name},
                    effective_unit_status,
                    header_provenance,
                    1.0 if declared_unit_code else 0.0,
                    "declared_units",
                ),
                "measurement_system": int(document.header.get("$MEASUREMENT", 0) or 0),
                "extents": _fact(
                    extents, "AUTHORITATIVE", header_provenance, 1.0, "computed_modelspace_extents"
                ),
            },
            "layouts": layouts,
            "layers": layers,
            "blocks": blocks,
            "xrefs": [block["name"] for block in blocks if block["is_xref"]],
            "modelspace": {
                "entity_count": len(model_entities),
                "entity_counts": dict(Counter(item["entity_type"] for item in model_entities)),
                "entities": model_entities,
                "inserts": inserts,
                "texts": text_records,
                "dimensions": dimensions,
                "hatches": hatches,
            },
            "views": clusters,
            "view_relationships": view_relationships,
            "facts": extracted_facts,
            "evidence_policy": {
                "hard_assertion_status": "AUTHORITATIVE",
                "soft_score_status": "INFERRED",
                "excluded_from_acceptance_status": "UNRESOLVED",
            },
        }
        return contract

    def write_contract(self, contract: dict[str, Any], destination: str | Path) -> Path:
        output = Path(destination).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return output

    def _entity_record(self, entity: Any, path: Path, container: str) -> dict[str, Any]:
        entity_type = entity.dxftype()
        layer = getattr(entity.dxf, "layer", None)
        handle = getattr(entity.dxf, "handle", None)
        geometry, geometry_status, geometry_reason = self._geometry(entity)
        record = {
            "entity_type": entity_type,
            "handle": handle,
            "layer": layer,
            "container": container,
            "geometry_status": geometry_status,
            "geometry_reason": geometry_reason,
            "geometry": geometry,
            "provenance": _provenance(
                path,
                layer=layer,
                entity_type=entity_type,
                handle=handle,
                evidence=f"DXF entity in {container}",
            ),
        }
        if entity_type in {"TEXT", "MTEXT"}:
            value = geometry.get("plain_text") or ""
            suspicious = "\ufffd" in value or any(ord(char) < 32 and char not in "\n\t" for char in value)
            record["encoding"] = {
                "status": "unresolved_encoding" if suspicious else "valid_unicode",
                "raw_text": geometry.get("raw_text"),
            }
        return record

    def _geometry(self, entity: Any) -> tuple[dict[str, Any], str, str]:
        kind = entity.dxftype()
        try:
            if kind == "LINE":
                return {
                    "start": _point(entity.dxf.start), "end": _point(entity.dxf.end)
                }, "AUTHORITATIVE", "explicit LINE endpoints"
            if kind == "LWPOLYLINE":
                return {
                    "points": [list(map(float, point)) for point in entity.get_points("xyseb")],
                    "closed": bool(entity.closed),
                    "elevation": _number(entity.dxf.elevation),
                }, "AUTHORITATIVE", "explicit LWPOLYLINE vertices"
            if kind == "POLYLINE":
                return {
                    "points": [_point(vertex.dxf.location) for vertex in entity.vertices],
                    "closed": bool(entity.is_closed),
                }, "AUTHORITATIVE", "explicit POLYLINE vertices"
            if kind == "ARC":
                return {
                    "center": _point(entity.dxf.center), "radius": float(entity.dxf.radius),
                    "start_angle": float(entity.dxf.start_angle),
                    "end_angle": float(entity.dxf.end_angle),
                    "extrusion": _point(entity.dxf.extrusion),
                }, "AUTHORITATIVE", "explicit ARC parameters"
            if kind == "CIRCLE":
                return {
                    "center": _point(entity.dxf.center), "radius": float(entity.dxf.radius),
                    "extrusion": _point(entity.dxf.extrusion),
                }, "AUTHORITATIVE", "explicit CIRCLE parameters"
            if kind == "SPLINE":
                return {
                    "degree": int(entity.dxf.degree),
                    "control_points": [_point(point) for point in entity.control_points],
                    "fit_points": [_point(point) for point in entity.fit_points],
                    "knots": [float(value) for value in entity.knots()],
                    "weights": [float(value) for value in entity.weights()],
                    "flags": int(entity.dxf.flags),
                }, "AUTHORITATIVE", "explicit SPLINE definition"
            if kind == "ELLIPSE":
                return {
                    "center": _point(entity.dxf.center),
                    "major_axis": _point(entity.dxf.major_axis),
                    "ratio": float(entity.dxf.ratio),
                    "start_param": float(entity.dxf.start_param),
                    "end_param": float(entity.dxf.end_param),
                }, "AUTHORITATIVE", "explicit ELLIPSE parameters"
            if kind == "REGION":
                return {
                    "acis_data": list(entity.acis_data),
                }, "AUTHORITATIVE", "raw ACIS REGION data; semantic boundary unresolved"
            if kind in {"TEXT", "MTEXT"}:
                raw = entity.dxf.text if kind == "TEXT" else entity.text
                plain = raw if kind == "TEXT" else entity.plain_text()
                return {
                    "raw_text": raw, "plain_text": plain,
                    "insert": _point(entity.dxf.insert),
                    "rotation": _number(getattr(entity.dxf, "rotation", 0.0)),
                    "height": _number(
                        getattr(entity.dxf, "height", getattr(entity.dxf, "char_height", None))
                    ),
                }, "AUTHORITATIVE", f"explicit {kind} content"
            if kind == "DIMENSION":
                try:
                    measurement = _number(entity.get_measurement())
                except Exception:
                    measurement = None
                return {
                    "dimension_type": int(entity.dxf.dimtype),
                    "measurement": measurement,
                    "text_override": getattr(entity.dxf, "text", ""),
                    "defpoint": _point(getattr(entity.dxf, "defpoint", None)),
                    "defpoint2": _point(getattr(entity.dxf, "defpoint2", None)),
                    "defpoint3": _point(getattr(entity.dxf, "defpoint3", None)),
                    "angle": _number(getattr(entity.dxf, "angle", None)),
                }, "AUTHORITATIVE", "DIMENSION definition and ezdxf measurement"
            if kind == "INSERT":
                matrix = [list(map(float, row)) for row in entity.matrix44().rows()]
                return {
                    "block_name": entity.dxf.name,
                    "insert": _point(entity.dxf.insert),
                    "scale": [
                        float(getattr(entity.dxf, "xscale", 1.0)),
                        float(getattr(entity.dxf, "yscale", 1.0)),
                        float(getattr(entity.dxf, "zscale", 1.0)),
                    ],
                    "rotation_degrees": float(getattr(entity.dxf, "rotation", 0.0)),
                    "extrusion": _point(getattr(entity.dxf, "extrusion", None)),
                    "transform_matrix": matrix,
                    "attributes": [
                        {
                            "tag": attrib.dxf.tag,
                            "text": attrib.dxf.text,
                            "handle": getattr(attrib.dxf, "handle", None),
                        }
                        for attrib in entity.attribs
                    ],
                }, "AUTHORITATIVE", "INSERT placement and transformation matrix"
            if kind == "HATCH":
                return {
                    "pattern_name": entity.dxf.pattern_name,
                    "solid_fill": bool(entity.dxf.solid_fill),
                    "associative": bool(entity.dxf.associative),
                    "paths": [self._hatch_path(path) for path in entity.paths],
                }, "AUTHORITATIVE", "HATCH pattern and boundary paths"
            if kind == "SOLID":
                return {
                    f"vtx{index}": _point(getattr(entity.dxf, f"vtx{index}"))
                    for index in range(4)
                }, "AUTHORITATIVE", "explicit SOLID vertices"
        except Exception as error:
            return {}, "UNRESOLVED", f"geometry extraction failed: {error}"
        return {}, "UNRESOLVED", f"no geometry adapter for {kind}"

    def _hatch_path(self, path: Any) -> dict[str, Any]:
        if hasattr(path, "vertices"):
            return {
                "path_type": "polyline",
                "vertices": [list(map(float, vertex)) for vertex in path.vertices],
                "closed": bool(path.is_closed),
            }
        edges = []
        for edge in getattr(path, "edges", []):
            item = {"edge_type": edge.__class__.__name__}
            for name in (
                "start", "end", "center", "radius", "start_angle", "end_angle",
                "major_axis", "ratio", "start_param", "end_param", "degree",
            ):
                if hasattr(edge, name):
                    value = getattr(edge, name)
                    item[name] = _point(value) if name in {"start", "end", "center", "major_axis"} else _number(value)
            if hasattr(edge, "control_points"):
                item["control_points"] = [_point(point) for point in edge.control_points]
            if hasattr(edge, "fit_points"):
                item["fit_points"] = [_point(point) for point in edge.fit_points]
            edges.append(item)
        return {"path_type": "edge_path", "edges": edges}

    def _extents(self, entities: Iterable[Any]) -> dict[str, list[float] | None]:
        try:
            box = bbox.extents(entities, fast=True)
            if not box.has_data:
                raise ValueError("empty bbox")
            return {"min": _point(box.extmin), "max": _point(box.extmax)}
        except Exception:
            return {"min": None, "max": None}

    def _anchor(self, record: dict[str, Any]) -> list[float] | None:
        geometry = record.get("geometry", {})
        for key in ("insert", "center", "defpoint", "start"):
            point = geometry.get(key)
            if point:
                return [float(point[0]), float(point[1])]
        points = geometry.get("points") or geometry.get("control_points")
        if points:
            usable = [point for point in points if point]
            if usable:
                return [
                    sum(float(point[0]) for point in usable) / len(usable),
                    sum(float(point[1]) for point in usable) / len(usable),
                ]
        end = geometry.get("end")
        start = geometry.get("start")
        if start and end:
            return [(start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0]
        return None

    def _detect_views(
        self,
        entities: list[dict[str, Any]],
        path: Path,
        drawing_extents: dict[str, Any],
        declared_unit: str,
    ) -> list[dict[str, Any]]:
        titles = []
        for record in entities:
            if record["entity_type"] not in {"TEXT", "MTEXT"}:
                continue
            text = (record["geometry"].get("plain_text") or "").strip().upper()
            if text in self.VIEW_TITLES:
                anchor = self._anchor(record)
                if anchor:
                    titles.append((anchor[0], text, record))
        titles.sort(key=lambda item: item[0])
        if not titles:
            return [
                {
                    "cluster_id": "view_001",
                    "probable_view_type": "unknown",
                    "status": "UNRESOLVED",
                    "title_text": None,
                    "bbox": drawing_extents,
                    "entity_handles": [record["handle"] for record in entities],
                    "normalized_frame": self._normalized_frame(drawing_extents, declared_unit),
                    "provenance": _provenance(
                        path,
                        entity_type="SPATIAL_CLUSTER",
                        evidence="single cluster fallback; no readable view title",
                    ),
                    "confidence": 0.0,
                }
            ]

        boundaries = [
            (titles[index][0] + titles[index + 1][0]) / 2.0
            for index in range(len(titles) - 1)
        ]
        assigned: list[list[dict[str, Any]]] = [[] for _ in titles]
        for record in entities:
            anchor = self._anchor(record)
            if not anchor:
                continue
            index = 0
            while index < len(boundaries) and anchor[0] >= boundaries[index]:
                index += 1
            assigned[index].append(record)

        clusters = []
        for index, ((_, title, title_record), records) in enumerate(zip(titles, assigned), 1):
            anchors = [self._anchor(record) for record in records]
            anchors = [point for point in anchors if point]
            cluster_bbox = {
                "min": [min(point[0] for point in anchors), min(point[1] for point in anchors), 0.0],
                "max": [max(point[0] for point in anchors), max(point[1] for point in anchors), 0.0],
            }
            clusters.append(
                {
                    "cluster_id": f"view_{index:03d}",
                    "probable_view_type": self.VIEW_TITLES[title],
                    "status": "AUTHORITATIVE",
                    "title_text": title_record["geometry"].get("plain_text"),
                    "title_handle": title_record["handle"],
                    "bbox": cluster_bbox,
                    "entity_count": len(records),
                    "entity_counts": dict(Counter(record["entity_type"] for record in records)),
                    "entity_handles": [record["handle"] for record in records],
                    "normalized_frame": self._normalized_frame(cluster_bbox, declared_unit),
                    "provenance": title_record["provenance"],
                    "confidence": 1.0,
                }
            )
        return clusters

    def _normalized_frame(self, extents: dict[str, Any], declared_unit: str) -> dict[str, Any]:
        minimum = extents.get("min") or [0.0, 0.0, 0.0]
        maximum = extents.get("max") or minimum
        return {
            "origin": [minimum[0], minimum[1], 0.0],
            "translation": [-minimum[0], -minimum[1], 0.0],
            "rotation_degrees": 0.0,
            "rotation_status": "UNRESOLVED",
            "scale": 1.0,
            "scale_status": "AUTHORITATIVE" if declared_unit != "unitless" else "UNRESOLVED",
            "declared_unit": declared_unit,
            "width": maximum[0] - minimum[0],
            "height": maximum[1] - minimum[1],
            "allowed_alignment": ["translation", "rotation"],
            "deformation_allowed": False,
        }

    def _view_relationships(
        self,
        clusters: list[dict[str, Any]],
        dimensions: list[dict[str, Any]],
        path: Path,
    ) -> list[dict[str, Any]]:
        plans = [view for view in clusters if view["probable_view_type"] == "floor_plan"]
        if len(plans) < 2:
            return []
        dimension_values = sorted(
            round(float(record["geometry"]["measurement"]), 6)
            for record in dimensions
            if record["geometry"].get("measurement") is not None
        )
        return [
            {
                "relationship_type": "plan_view_identity",
                "views": [view["cluster_id"] for view in plans],
                "classification": "duplicated_view_or_presentation_variant_or_distinct_plan",
                "status": "UNRESOLVED",
                "evidence": {
                    "same_readable_title": True,
                    "document_dimension_signature": dimension_values,
                    "user_authoritative_storeys": 1,
                    "reason": "Two FLOOR PLAN titles do not prove two architectural storeys.",
                },
                "provenance": _provenance(
                    path,
                    entity_type="VIEW_RELATIONSHIP",
                    evidence="title clustering plus user-authoritative one-storey metadata",
                ),
                "confidence": 0.0,
            }
        ]
