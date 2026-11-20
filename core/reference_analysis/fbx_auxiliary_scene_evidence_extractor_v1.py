"""Read-only Blender-side scene evidence extraction for reference analysis.

This module is executed by Blender in an empty process.  It serializes metadata,
world transforms and world bounding boxes only; it never exports scene assets.
"""

import json
import sys
from pathlib import Path


def _argv_value(flag):
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return args[args.index(flag) + 1]


def _vector(value):
    return [float(component) for component in value]


def extract_scene(source_path, output_path):
    import bpy
    from mathutils import Vector

    source_path = Path(source_path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = source_path.suffix.lower()
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source_path), use_custom_normals=True)
    elif suffix == ".3ds":
        result = bpy.ops.wm.read_homefile(use_empty=True)
        del result
        if not hasattr(bpy.ops.import_scene, "max3ds"):
            raise RuntimeError("Blender max3ds importer is unavailable")
        bpy.ops.import_scene.max3ds(filepath=str(source_path))
    else:
        raise ValueError(f"Unsupported reference source: {suffix}")

    objects = []
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box] if obj.type == "MESH" else []
        bbox = None
        if world_corners:
            bbox = {
                "min": [min(point[index] for point in world_corners) for index in range(3)],
                "max": [max(point[index] for point in world_corners) for index in range(3)],
            }
        mesh = obj.data if obj.type == "MESH" else None
        objects.append(
            {
                "object_id": obj.name_full,
                "name": obj.name,
                "type": obj.type,
                "parent": obj.parent.name_full if obj.parent else None,
                "world_matrix": [[float(value) for value in row] for row in obj.matrix_world],
                "location": _vector(obj.matrix_world.translation),
                "rotation_euler": _vector(obj.rotation_euler),
                "scale": _vector(obj.scale),
                "world_bbox": bbox,
                "mesh_statistics": {
                    "vertex_count": len(mesh.vertices),
                    "edge_count": len(mesh.edges),
                    "polygon_count": len(mesh.polygons),
                    "material_names": [slot.material.name if slot.material else None for slot in obj.material_slots],
                }
                if mesh else None,
                "custom_properties": {
                    str(key): str(value) for key, value in obj.items() if key != "cycles"
                },
            }
        )
    output = {
        "source": "FBX" if suffix == ".fbx" else "3DS",
        "source_file": str(source_path),
        "extraction_mode": "READ_ONLY_SCENE_METADATA_NO_ASSET_EXPORT",
        "unit_settings": {
            "system": bpy.context.scene.unit_settings.system,
            "scale_length": bpy.context.scene.unit_settings.scale_length,
            "length_unit": bpy.context.scene.unit_settings.length_unit,
        },
        "object_count": len(objects),
        "objects": objects,
        "evidence_status": "AUXILIARY_PRESENTATION_EVIDENCE",
    }
    Path(output_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    extract_scene(_argv_value("--source"), _argv_value("--output"))
