"""Publish fail-closed CoreSizing and Parcel-2 obstacle evidence contracts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox
from shapely.geometry import LineString, Point, Polygon, box

from core.cad.cad_import_engine import CADImportEngine
from core.site.separation_joint_engine import SeparationJointEngine


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "data" / "real_site" / "parcel_2_source.dxf"


def _local_bbox(entity, origin):
    try:
        extents = bbox.extents([entity])
        return [
            float(extents.extmin.x - origin[0]), float(extents.extmin.y - origin[1]),
            float(extents.extmax.x - origin[0]), float(extents.extmax.y - origin[1]),
        ]
    except Exception:
        return None


def _entity_geometry(entity, origin, bounds):
    result = {"bbox": bounds}
    kind = entity.dxftype()
    if kind == "LINE":
        result["segment"] = [
            [float(entity.dxf.start.x-origin[0]), float(entity.dxf.start.y-origin[1])],
            [float(entity.dxf.end.x-origin[0]), float(entity.dxf.end.y-origin[1])],
        ]
    elif kind == "LWPOLYLINE":
        result["polyline"] = [
            [float(point[0]-origin[0]), float(point[1]-origin[1])]
            for point in entity.get_points("xy")
        ]
        result["closed"] = bool(entity.closed)
    elif kind == "CIRCLE":
        result["center"] = [float(entity.dxf.center.x-origin[0]), float(entity.dxf.center.y-origin[1])]
        result["radius"] = float(entity.dxf.radius)
    elif kind in ("TEXT", "MTEXT"):
        insertion = entity.dxf.insert
        result["insertion"] = [float(insertion.x-origin[0]), float(insertion.y-origin[1])]
        result["text"] = entity.plain_text() if kind == "MTEXT" else entity.dxf.text
    elif kind == "INSERT":
        insertion = entity.dxf.insert
        result.update({
            "insertion": [float(insertion.x-origin[0]), float(insertion.y-origin[1])],
            "block_name": entity.dxf.name,
            "rotation": float(entity.dxf.rotation),
            "scale": [float(entity.dxf.xscale), float(entity.dxf.yscale)],
        })
    return result


def _classify(entity, geometry, selected_boundary):
    kind, layer, handle = entity.dxftype(), entity.dxf.layer, entity.dxf.handle
    if kind in ("MTEXT", "TEXT", "DIMENSION", "ARC_DIMENSION"):
        return "non_obstacle_reference", "annotation_or_dimension_entity"
    if layer == "CODE" and kind == "CIRCLE":
        return "non_obstacle_reference", "parcel_label_annotation_bubble"
    if layer == "base site" and kind == "LWPOLYLINE":
        return "non_obstacle_reference", "parcel_or_site_reference_polyline"
    if layer == "shabake_jadid":
        return "non_obstacle_reference", "confirmed_road_network_reference"
    if kind in ("HATCH", "LWPOLYLINE") and layer == "0":
        points = geometry.get("polyline")
        if handle in ("1175", "1176") or points == selected_boundary:
            return "non_obstacle_reference", "selected_parcel_boundary_or_presentation_hatch"
    if layer == "tirbarq":
        return "unresolved", "utility_network_semantics_without_fixed_obstacle_footprint"
    if kind == "INSERT":
        insertion = geometry.get("insertion")
        if (geometry.get("block_name", "").startswith("A$C") and insertion
                and not Polygon(selected_boundary).covers(Point(insertion))
                and layer in ("DOR KADR", "PLAN")):
            return "non_obstacle_reference", "repeated_external_drawing_reference_block"
        return "unresolved", "block_geometry_intersects_envelope_but_physical_semantics_unresolved"
    if kind == "LINE" and layer == "0" and geometry.get("segment"):
        line = LineString(geometry["segment"])
        boundary = Polygon(selected_boundary).boundary
        if line.distance(boundary) <= 1e-6 and line.intersects(boundary):
            return "non_obstacle_reference", "parcel_boundary_extension_reference"
    return "unresolved", "geometry_intersects_envelope_without_authoritative_physical_semantics"


def main():
    imported = CADImportEngine().load({"file_object": str(SOURCE)}, target_parcel=2)["site"]
    parcel = imported["points"]
    origin = (float(imported["origin"]["x"]), float(imported["origin"]["y"]))
    envelope = SeparationJointEngine().resolve_buildable_envelope(
        parcel, {"edge_offsets": [0.0, 0.10, 0.10, 0.10]}
    )
    target = Polygon(envelope["buildable_boundary"])
    document = ezdxf.readfile(str(SOURCE))
    classified, confirmed, references, unresolved = [], [], [], []
    for entity in document.modelspace():
        bounds = _local_bbox(entity, origin)
        if bounds is None or not target.intersects(box(*bounds)):
            continue
        geometry = _entity_geometry(entity, origin, bounds)
        exact_shape = None
        if geometry.get("segment"):
            exact_shape = LineString(geometry["segment"])
        elif geometry.get("polyline"):
            points = geometry["polyline"]
            exact_shape = Polygon(points) if geometry.get("closed") and len(points) >= 3 else LineString(points)
        elif geometry.get("center") and geometry.get("radius") is not None:
            exact_shape = Point(geometry["center"]).buffer(float(geometry["radius"]))
        if exact_shape is not None and not exact_shape.intersects(target):
            continue
        classification, reason = _classify(entity, geometry, parcel)
        intersection_geometry = None
        if exact_shape is not None:
            clipped = exact_shape.intersection(target)
            if clipped.geom_type == "LineString" and not clipped.is_empty:
                intersection_geometry = [list(point) for point in clipped.coords]
        item = {
            "handle": entity.dxf.handle,
            "entity_type": entity.dxftype(),
            "layer": entity.dxf.layer,
            "geometry": geometry,
            "inside_or_intersects_buildable_envelope": True,
            "intersection_geometry": intersection_geometry,
            "classification": classification,
            "semantic_evidence": reason,
            "fixed_physical_obstacle": classification == "confirmed_fixed_obstacle",
        }
        classified.append(item)
        if classification == "confirmed_fixed_obstacle":
            confirmed.append(item)
        elif classification == "non_obstacle_reference":
            references.append(item)
        else:
            unresolved.append(item)

    core = {
        "contract": "CoreSizingContractV1",
        "geometry_status": "unresolved",
        "maximum_width": 4.50,
        "maximum_depth": 5.50,
        "elevator_required": True,
        "lobby_reserved_zone": {"minimum_clear_width": 1.50, "minimum_clear_depth": 1.50},
        "minimum_width": None,
        "minimum_depth": None,
        "stair_reserved_zone": None,
        "elevator_reserved_zone": None,
        "wall_enclosure_allowance": None,
        "configurations": [],
        "evidence_used": [
            {"field": "maximum_core_envelope", "value": [4.5, 5.5], "classification": "USER_PROJECT_REQUIREMENT"},
            {"field": "elevator_required", "value": True, "classification": "USER_PROJECT_REQUIREMENT"},
            {"field": "elevator_front_lobby", "value": [1.5, 1.5], "classification": "USER_PROJECT_REQUIREMENT"},
            {"field": "stair_rule_categories", "value": ["minimum_clear_width", "landing_geometry"],
             "classification": "ARCHITECTURAL_KNOWLEDGE", "numeric_value": None},
            {"field": "elevator_rule_categories", "value": ["car_dimensions", "door_clear_width", "shaft_dimensions"],
             "classification": "ARCHITECTURAL_KNOWLEDGE", "numeric_value": None},
        ],
        "excluded_legacy_fixture_evidence": [
            "stair_clear_width_1.20", "landing_depth_1.20", "maximum_riser_0.18",
            "minimum_tread_0.28", "historical_stair_allowed_zone",
        ],
        "missing_dimensions": [
            "minimum_stair_clear_width", "minimum_stair_reserved_zone_width",
            "minimum_stair_reserved_zone_depth", "elevator_shaft_clear_width",
            "elevator_shaft_clear_depth", "core_internal_enclosure_wall_thickness",
            "minimum_stair_elevator_lobby_interface_clearance",
        ],
        "source": "repository_evidence_audit",
    }
    obstacle = {
        "contract": "Parcel2FixedObstacleInventoryContractV1",
        "source_file": str(SOURCE),
        "buildable_envelope": envelope["buildable_boundary"],
        "classified_entities": classified,
        "confirmed_fixed_obstacles": confirmed,
        "non_obstacle_reference_entities": references,
        "unresolved_entities": unresolved,
        "inventory_status": "unresolved" if unresolved else (
            "complete_with_obstacles" if confirmed else "complete_empty"
        ),
        "complete_empty_allowed": not unresolved and not confirmed,
        "evidence_summary": {
            "intersecting_entity_count": len(classified),
            "confirmed_fixed_obstacle_count": len(confirmed),
            "non_obstacle_reference_count": len(references),
            "unresolved_entity_count": len(unresolved),
        },
    }
    output = ROOT / "exports" / "DEFAULT" / (
        "parcel2_core_obstacle_audit_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    output.mkdir(parents=True, exist_ok=False)
    core_path = output / "CORE_SIZING_CONTRACT_V1.json"
    obstacle_path = output / "PARCEL2_FIXED_OBSTACLE_INVENTORY_CONTRACT_V1.json"
    core_path.write_text(json.dumps(core, ensure_ascii=False, indent=2), encoding="utf-8")
    obstacle_path.write_text(json.dumps(obstacle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "core_contract": str(core_path),
        "core_status": core["geometry_status"], "obstacle_contract": str(obstacle_path),
        "inventory_status": obstacle["inventory_status"],
        "summary": obstacle["evidence_summary"], "candidate_generation_started": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
