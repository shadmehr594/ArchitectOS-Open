import json
import math
import os
from pathlib import Path

import pytest

from scripts.build_3d_future_registry import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_OUTPUT_PATH,
    ObjDimensionError,
    RegistryBuildError,
    build_registry,
    normalize_category_for_adapter,
    parse_obj_dimensions,
    validate_adapter_matching,
    validate_registry_file,
)


UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
UUID_C = "33333333-3333-4333-8333-333333333333"


def write_obj(path: Path, vertices):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# sample OBJ\n"]
    lines.extend(f"v {x} {y} {z}\n" for x, y, z in vertices)
    lines.append("f 1 2 3\n")
    path.write_text("".join(lines), encoding="utf-8")


def write_metadata(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def create_asset(part_dir: Path, model_id: str, *, normalized: bool = True):
    asset_dir = part_dir / model_id
    write_obj(asset_dir / "raw_model.obj", [(-1, 0, -2), (3, 5, 4), (0, 2, 1)])
    if normalized:
        write_obj(asset_dir / "normalized_model.obj", [(-0.5, 0, -0.5), (0.5, 1, 0.5)])
    (asset_dir / "texture.png").write_bytes(b"texture")
    (asset_dir / "image.jpg").write_bytes(b"image")
    return asset_dir


def test_obj_dimension_parser_streams_xyz_bounds(tmp_path):
    obj_path = tmp_path / "sample.obj"
    write_obj(obj_path, [(-1.5, 0.0, 2.0), (2.5, 3.25, -4.0), (1.0, 1.0, 0.0)])

    dims = parse_obj_dimensions(obj_path)

    assert dims.vertex_count == 3
    assert dims.full_dims_xyz == [4.0, 3.25, 6.0]
    assert len(dims.full_dims_xyz) == 3
    assert all(math.isfinite(value) and value > 0 for value in dims.full_dims_xyz)


def test_obj_dimension_parser_rejects_no_vertices(tmp_path):
    obj_path = tmp_path / "empty.obj"
    obj_path.write_text("# no vertices\nf 1 2 3\n", encoding="utf-8")

    with pytest.raises(ObjDimensionError, match="no vertex"):
        parse_obj_dimensions(obj_path)


def test_obj_dimension_parser_rejects_zero_dimensions(tmp_path):
    obj_path = tmp_path / "flat.obj"
    write_obj(obj_path, [(1, 2, 3), (1, 5, 7)])

    with pytest.raises(ObjDimensionError, match="not positive"):
        parse_obj_dimensions(obj_path)


def test_category_normalization_matches_furniture_adapter_contract():
    assert normalize_category_for_adapter(" Single-Bed ") == "bed"
    assert normalize_category_for_adapter("Dining Table") == "table"
    assert normalize_category_for_adapter("Wardrobe") == "cabinet"
    assert normalize_category_for_adapter("Bookshelf") == "shelf"


def test_build_registry_maps_metadata_fallback_and_stable_output(tmp_path):
    dataset_root = tmp_path / "dataset"
    part1 = dataset_root / "3D-FUTURE-model-part1"
    part2 = dataset_root / "3D-FUTURE-model-part2"
    part3 = dataset_root / "3D-FUTURE-model-part3"
    part4 = dataset_root / "3D-FUTURE-model-part4"
    for part in (part1, part2, part3, part4):
        part.mkdir(parents=True, exist_ok=True)

    create_asset(part2, UUID_B, normalized=False)
    create_asset(part1, UUID_A, normalized=True)
    metadata_file = part1 / "model_info.json"
    write_metadata(
        metadata_file,
        [
            {
                "model_id": UUID_B,
                "super-category": "Bed",
                "category": "Single Bed",
                "style": "Modern",
                "theme": "Lines",
                "material": "Wood",
            },
            {
                "model_id": UUID_A,
                "super-category": "Table",
                "category": "Coffee Table",
                "style": "Minimalist",
                "theme": None,
                "material": "Metal",
            },
        ],
    )
    output_path = tmp_path / "registry.json"

    registry, summary = build_registry(
        dataset_root=dataset_root,
        metadata_file=metadata_file,
        output_path=output_path,
    )
    first_output = output_path.read_text(encoding="utf-8")
    _, second_summary = build_registry(
        dataset_root=dataset_root,
        metadata_file=metadata_file,
        output_path=output_path,
    )
    second_output = output_path.read_text(encoding="utf-8")

    assert [asset["model_id"] for asset in registry["assets"]] == [UUID_A, UUID_B]
    assert registry["assets"][0]["category"] == "table"
    assert registry["assets"][0]["source_category"] == "Coffee Table"
    assert registry["assets"][1]["category"] == "bed"
    assert registry["assets"][1]["normalized_model_path"] is None
    assert registry["assets"][1]["model_path"] == registry["assets"][1]["raw_model_path"]
    assert registry["assets"][1]["full_dims_xyz"] == [4.0, 5.0, 6.0]
    assert summary["asset_count"] == 2
    assert summary["normalized_fallback_count"] == 1
    assert second_summary["normalized_fallback_count"] == 1
    assert first_output == second_output


def test_build_registry_detects_duplicate_metadata_ids(tmp_path):
    dataset_root = tmp_path / "dataset"
    part1 = dataset_root / "3D-FUTURE-model-part1"
    for part_name in ("3D-FUTURE-model-part1", "3D-FUTURE-model-part2", "3D-FUTURE-model-part3", "3D-FUTURE-model-part4"):
        (dataset_root / part_name).mkdir(parents=True, exist_ok=True)
    create_asset(part1, UUID_A)
    metadata_file = part1 / "model_info.json"
    write_metadata(
        metadata_file,
        [
            {"model_id": UUID_A, "category": "armchair"},
            {"model_id": UUID_A, "category": "armchair"},
        ],
    )

    with pytest.raises(RegistryBuildError) as exc_info:
        build_registry(dataset_root=dataset_root, metadata_file=metadata_file, output_path=tmp_path / "out.json")

    assert any(issue["kind"] == "duplicate_metadata_id" for issue in exc_info.value.summary["issues"])


def test_build_registry_detects_duplicate_physical_ids(tmp_path):
    dataset_root = tmp_path / "dataset"
    part1 = dataset_root / "3D-FUTURE-model-part1"
    part2 = dataset_root / "3D-FUTURE-model-part2"
    for part_name in ("3D-FUTURE-model-part1", "3D-FUTURE-model-part2", "3D-FUTURE-model-part3", "3D-FUTURE-model-part4"):
        (dataset_root / part_name).mkdir(parents=True, exist_ok=True)
    create_asset(part1, UUID_A)
    create_asset(part2, UUID_A)
    metadata_file = part1 / "model_info.json"
    write_metadata(metadata_file, [{"model_id": UUID_A, "category": "armchair"}])

    with pytest.raises(RegistryBuildError) as exc_info:
        build_registry(dataset_root=dataset_root, metadata_file=metadata_file, output_path=tmp_path / "out.json")

    assert any(issue["kind"] == "duplicate_physical_id" for issue in exc_info.value.summary["issues"])


def test_build_registry_detects_malformed_obj(tmp_path):
    dataset_root = tmp_path / "dataset"
    part1 = dataset_root / "3D-FUTURE-model-part1"
    for part_name in ("3D-FUTURE-model-part1", "3D-FUTURE-model-part2", "3D-FUTURE-model-part3", "3D-FUTURE-model-part4"):
        (dataset_root / part_name).mkdir(parents=True, exist_ok=True)
    asset_dir = part1 / UUID_A
    asset_dir.mkdir(parents=True)
    (asset_dir / "raw_model.obj").write_text("v 0 0 0\nv bad 1 2\n", encoding="utf-8")
    (asset_dir / "normalized_model.obj").write_text("v 0 0 0\nv 1 1 1\n", encoding="utf-8")
    metadata_file = part1 / "model_info.json"
    write_metadata(metadata_file, [{"model_id": UUID_A, "category": "armchair"}])

    with pytest.raises(RegistryBuildError) as exc_info:
        build_registry(dataset_root=dataset_root, metadata_file=metadata_file, output_path=tmp_path / "out.json")

    assert any(issue["kind"] == "malformed_obj" for issue in exc_info.value.summary["issues"])


@pytest.mark.skipif(
    os.environ.get("ARCHITECTOS_VALIDATE_REAL_3D_FUTURE") != "1",
    reason="set ARCHITECTOS_VALIDATE_REAL_3D_FUTURE=1 to run the real 3D-FUTURE dataset validation",
)
def test_real_3d_future_dataset_registry_and_adapter_validation():
    registry, summary = build_registry(
        dataset_root=DEFAULT_DATASET_ROOT,
        output_path=DEFAULT_OUTPUT_PATH,
    )
    validation = validate_registry_file(DEFAULT_OUTPUT_PATH, DEFAULT_DATASET_ROOT)
    matching = validate_adapter_matching(DEFAULT_OUTPUT_PATH)

    assert summary["source_metadata_file"].endswith("3D-FUTURE-model-part1\\model_info.json") or summary[
        "source_metadata_file"
    ].endswith("3D-FUTURE-model-part1/model_info.json")
    assert summary["asset_count"] == 16563
    assert summary["unique_physical_ids"] == 16563
    assert summary["unique_metadata_ids"] == 16563
    assert summary["normalized_fallback_count"] == 3
    assert summary["missing_raw_count"] == 0
    assert summary["malformed_asset_count"] == 0
    assert len(registry["assets"]) == 16563

    assert validation["asset_count"] == 16563
    assert validation["unique_model_ids"] == 16563
    assert validation["metadata_physical_matching_count"] == 16563
    assert validation["metadata_without_physical_count"] == 0
    assert validation["physical_without_metadata_count"] == 0
    assert validation["missing_raw_count"] == 0
    assert validation["normalized_fallback_count"] == 3
    assert validation["required_fields_present"] is True
    assert validation["optional_metadata_preserved"] is True
    assert validation["all_model_paths_exist"] is True
    assert validation["finite_positive_dimensions"] is True

    assert matching
    for category, result in matching.items():
        assert result["tested"] is True, category
        assert result["matched"] is True, category
        assert result["matched_model_id"], category
