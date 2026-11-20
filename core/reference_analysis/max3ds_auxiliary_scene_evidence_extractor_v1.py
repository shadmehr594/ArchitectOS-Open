"""Minimal read-only 3DS chunk reader for object geometry evidence."""

import json
import struct
from pathlib import Path


CONTAINER_CHUNKS = {0x4D4D, 0x3D3D, 0x4100, 0xB000}


def extract_3ds_scene(source_path, output_path=None):
    data = Path(source_path).read_bytes()
    objects = []
    keyframe_nodes = []

    def walk(start, end, current=None):
        cursor = start
        while cursor + 6 <= end:
            chunk_id, size = struct.unpack_from("<HI", data, cursor)
            if size < 6 or cursor + size > end:
                break
            payload, chunk_end = cursor + 6, cursor + size
            if chunk_id == 0x4000:
                zero = data.find(b"\0", payload, chunk_end)
                if zero < 0:
                    cursor = chunk_end
                    continue
                item = {"object_id": data[payload:zero].decode("cp1252", errors="replace"), "vertices": [], "local_matrix": None}
                objects.append(item)
                walk(zero + 1, chunk_end, item)
            elif chunk_id == 0xB002:
                node = {"name": None}
                keyframe_nodes.append(node)
                walk(payload, chunk_end, node)
            elif chunk_id == 0xB010 and current is not None:
                zero = data.find(b"\0", payload, chunk_end)
                if zero >= 0:
                    current["name"] = data[payload:zero].decode("cp1252", errors="replace")
            elif chunk_id == 0x4110 and current is not None and payload + 2 <= chunk_end:
                count = struct.unpack_from("<H", data, payload)[0]
                values = struct.unpack_from(f"<{count * 3}f", data, payload + 2)
                current["vertices"] = [list(values[index:index + 3]) for index in range(0, len(values), 3)]
            elif chunk_id == 0x4160 and current is not None and payload + 48 <= chunk_end:
                current["local_matrix"] = list(struct.unpack_from("<12f", data, payload))
            elif chunk_id in CONTAINER_CHUNKS:
                walk(payload, chunk_end, current)
            cursor = chunk_end

    walk(0, len(data))
    result_objects = []
    for item in objects:
        vertices = item.pop("vertices")
        bbox = None
        if vertices:
            bbox = {"min": [min(v[i] for v in vertices) for i in range(3)], "max": [max(v[i] for v in vertices) for i in range(3)]}
        result_objects.append({**item, "vertex_count": len(vertices), "local_vertex_bbox": bbox})
    result = {"source": "3DS", "source_file": str(source_path), "extraction_mode": "READ_ONLY_CHUNK_METADATA_NO_ASSET_EXPORT",
              "object_count": len(result_objects), "objects": result_objects,
              "keyframe_nodes": [item for item in keyframe_nodes if item.get("name")],
              "evidence_status": "AUXILIARY_PRESENTATION_EVIDENCE"}
    if output_path:
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
