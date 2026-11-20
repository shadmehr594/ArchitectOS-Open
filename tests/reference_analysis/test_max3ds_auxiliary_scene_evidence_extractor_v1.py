import struct

from core.reference_analysis.max3ds_auxiliary_scene_evidence_extractor_v1 import extract_3ds_scene


def _chunk(chunk_id, payload=b""):
    return struct.pack("<HI", chunk_id, len(payload) + 6) + payload


def test_reads_mesh_object_without_exporting_asset(tmp_path):
    vertices = struct.pack("<H9f", 3, 0, 0, 0, 1, 0, 0, 0, 2, 0)
    mesh = _chunk(0x4100, _chunk(0x4110, vertices))
    editor = _chunk(0x3D3D, _chunk(0x4000, b"Gate\0" + mesh))
    source = tmp_path / "scene.3ds"
    source.write_bytes(_chunk(0x4D4D, editor))
    result = extract_3ds_scene(source)
    assert result["objects"][0]["object_id"] == "Gate"
    assert result["objects"][0]["local_vertex_bbox"]["max"] == [1.0, 2.0, 0.0]
    assert result["extraction_mode"] == "READ_ONLY_CHUNK_METADATA_NO_ASSET_EXPORT"


def test_reads_gate_keyframe_node_name(tmp_path):
    node = _chunk(0xB002, _chunk(0xB010, b"Gates 2\0" + b"\0" * 6))
    source = tmp_path / "scene.3ds"
    source.write_bytes(_chunk(0x4D4D, _chunk(0xB000, node)))
    result = extract_3ds_scene(source)
    assert result["keyframe_nodes"] == [{"name": "Gates 2"}]
