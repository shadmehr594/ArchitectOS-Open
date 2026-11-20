"""Focused tests for the minimal raw 3D-FUTURE OBJ loader (Phase 3D-J)."""

import os
from pathlib import Path

import pytest

from core.asset.raw_obj_loader import (
    DEFAULT_ROOT_ENV_VAR,
    load_raw_obj,
)

TRIANGLE = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"


def _make_obj(root, model_id="m1", name="raw_model.obj", text=TRIANGLE):
    folder = Path(root) / model_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def _source(path, model_id="m1"):
    return {
        "source": "3D-FUTURE",
        "model_id": model_id,
        "raw_model_path": str(path),
    }


def _load(root, path, model_id="m1", **kwargs):
    kwargs.setdefault("allowed_roots", [root])
    return load_raw_obj(_source(path, model_id), **kwargs)


# ---------------------------------------------------------------------------
# 1. minimal triangle
# ---------------------------------------------------------------------------

def test_loads_minimal_triangle(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_loaded_valid"
    assert result["status"]["reasons"] == []
    assert result["geometry"]["index_base"] == 0
    assert result["geometry"]["vertices_xyz"] == [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
    assert result["geometry"]["faces"] == [[0, 1, 2]]
    assert result["counts"] == {
        "vertices": 3,
        "faces": 1,
        "face_degree_max": 3,
        "ignored_lines": 0,
    }
    assert result["mesh_frame"] == "raw_mesh_local_frame"
    assert result["format_version"] == "raw_obj_mesh_v1"


# ---------------------------------------------------------------------------
# 2. v/vt/vn face forms
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "face",
    ["f 1/1/1 2/2/2 3/3/3", "f 1//1 2//2 3//3", "f 1/1 2/2 3/3", "f 1 2 3"],
)
def test_face_index_forms_store_vertex_indices_only(tmp_path, face):
    text = "v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvn 0 0 1\n" + face + "\n"
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert result["geometry"]["faces"] == [[0, 1, 2]]


def test_vt_vn_are_ignored_but_reported(tmp_path):
    text = "v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvn 0 0 1\nf 1/1/1 2/2/2 3/3/3\n"
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert "mesh_vn_vt_ignored" in result["warnings"]
    assert "vt" not in result["geometry"]
    assert "vn" not in result["geometry"]


# ---------------------------------------------------------------------------
# 3. negative indices
# ---------------------------------------------------------------------------

def test_negative_indices_resolve_relative_to_current_vertex_count(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n")

    result = _load(tmp_path, obj)

    assert result["geometry"]["faces"] == [[0, 1, 2]]


def test_negative_indices_may_mix_with_positive(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 -2 -1\n")

    result = _load(tmp_path, obj)

    assert result["geometry"]["faces"] == [[0, 1, 2]]


# ---------------------------------------------------------------------------
# 4 + 5. index validation
# ---------------------------------------------------------------------------

def test_index_zero_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nv 0 1 0\nf 0 1 2\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_invalid_faces"
    assert result["status"]["reasons"] == ["face_index_zero"]
    assert result["geometry"] is None


@pytest.mark.parametrize("face", ["f 1 2 9", "f -1 -2 -9"])
def test_out_of_range_index_is_rejected(tmp_path, face):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nv 0 1 0\n" + face + "\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_invalid_faces"
    assert result["status"]["reasons"] == ["face_index_out_of_range"]


def test_non_integer_face_index_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 x\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_invalid_faces"


def test_face_degree_below_three_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 1 0 0\nf 1 2\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_invalid_faces"
    assert result["status"]["reasons"] == ["face_degree_below_3"]


# ---------------------------------------------------------------------------
# 6. non-finite / malformed vertices
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "NaN", "Infinity"])
def test_nonfinite_vertex_is_rejected(tmp_path, bad):
    obj = _make_obj(tmp_path, text=f"v {bad} 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_nonfinite_vertices"
    assert result["geometry"] is None


def test_non_numeric_vertex_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, text="v a b c\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_parse_failed"
    assert result["status"]["reasons"] == ["vertex_record_non_numeric"]


def test_vertex_with_too_few_components_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, text="v 1 2\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_parse_failed"


# ---------------------------------------------------------------------------
# 7. empty mesh
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "\n\n", "# only a comment\n"])
def test_empty_mesh_is_rejected(tmp_path, text):
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_empty"
    assert result["geometry"] is None


# ---------------------------------------------------------------------------
# 8 + 9. bounds and pivot
# ---------------------------------------------------------------------------

def test_bounds_are_computed_from_vertex_extremes(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 2 4 6\n")

    result = _load(tmp_path, obj)

    assert result["bounds"]["min_xyz"] == [0.0, 0.0, 0.0]
    assert result["bounds"]["max_xyz"] == [2.0, 4.0, 6.0]
    assert result["bounds"]["dims_xyz"] == [2.0, 4.0, 6.0]
    assert result["bounds"]["center_xyz"] == [1.0, 2.0, 3.0]


def test_vertices_are_not_recentered_or_remapped(tmp_path):
    # The Phase 3D-G basis would map [1, 2, 3] to [1, -3, 2]; the loader must not.
    obj = _make_obj(tmp_path, text="v 1 2 3\nv -4 5 -6\n")

    result = _load(tmp_path, obj)

    assert result["geometry"]["vertices_xyz"] == [[1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]]
    assert result["pivot"]["mesh_origin_xyz"] == [0.0, 0.0, 0.0]
    assert result["pivot"]["bbox_center_xyz"] == [-1.5, 3.5, -1.5]
    assert "basis" not in result
    assert result["mesh_frame"] == "raw_mesh_local_frame"


def test_flat_axis_produces_zero_dimension_warning(tmp_path):
    obj = _make_obj(tmp_path, text="v 0 0 0\nv 2 0 6\n")

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_loaded_valid"
    assert "mesh_zero_dimension" in result["warnings"]


# ---------------------------------------------------------------------------
# 10, 11, 12. path security
# ---------------------------------------------------------------------------

def test_model_id_parent_mismatch_is_rejected(tmp_path):
    obj = _make_obj(tmp_path, model_id="m1")

    result = _load(tmp_path, obj, model_id="something-else")

    assert result["status"]["state"] == "mesh_path_model_id_mismatch"
    assert result["status"]["reasons"] == [
        "parent_directory_does_not_match_model_id"
    ]


def test_missing_model_id_is_rejected(tmp_path):
    obj = _make_obj(tmp_path)

    result = load_raw_obj(
        {"raw_model_path": str(obj)}, allowed_roots=[tmp_path]
    )

    assert result["status"]["state"] == "mesh_path_model_id_mismatch"
    assert result["status"]["reasons"] == ["model_id_missing"]


@pytest.mark.parametrize("name", ["normalized_model.obj", "raw_model.txt", "model.obj"])
def test_wrong_filename_or_extension_is_rejected(tmp_path, name):
    obj = _make_obj(tmp_path, name=name)

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_invalid_extension"


def test_path_outside_allowed_root_is_rejected(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    obj = _make_obj(outside)

    result = load_raw_obj(_source(obj), allowed_roots=[allowed])

    assert result["status"]["state"] == "mesh_path_outside_allowed_root"
    assert result["status"]["reasons"] == ["lexical_path_outside_allowed_root"]


def test_parent_traversal_is_rejected(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    obj = _make_obj(outside)

    traversing = allowed / ".." / "outside" / "m1" / "raw_model.obj"

    result = load_raw_obj(_source(traversing), allowed_roots=[allowed])

    assert result["status"]["state"] == "mesh_path_outside_allowed_root"
    assert result["geometry"] is None


def test_sibling_prefix_root_is_not_treated_as_inside(tmp_path):
    # "allowed" vs "allowed_evil" must not pass a naive prefix comparison.
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    evil = tmp_path / "allowed_evil"
    obj = _make_obj(evil)

    result = load_raw_obj(_source(obj), allowed_roots=[allowed])

    assert result["status"]["state"] == "mesh_path_outside_allowed_root"


def test_symlink_escape_is_rejected(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    real = _make_obj(outside)

    link_dir = allowed / "m1"
    try:
        os.symlink(outside / "m1", link_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this platform")

    # Some Windows configurations accept the call without creating a usable
    # link; only assert the guard when the link actually resolves.
    if not link_dir.is_symlink() or not (link_dir / "raw_model.obj").exists():
        pytest.skip("symlink created but not usable in this environment")

    result = load_raw_obj(
        _source(link_dir / "raw_model.obj"), allowed_roots=[allowed]
    )

    assert result["status"]["state"] == "mesh_path_outside_allowed_root"
    assert result["status"]["reasons"] == ["resolved_path_escapes_allowed_root"]
    assert real.exists()


def test_post_canonicalization_guard_rejects_reparse_point_escape(
    tmp_path, monkeypatch
):
    """A lexically-inside path that canonicalizes outside the root is rejected.

    This deterministically exercises step 6-8 of the path contract (the guard
    that defeats symlink / junction / reparse-point escapes) without depending
    on whether the host permits creating links.
    """

    import core.asset.raw_obj_loader as loader_module

    allowed = tmp_path / "allowed"
    obj = _make_obj(allowed)
    escaped = tmp_path / "outside" / "m1" / "raw_model.obj"

    def fake_realpath(path):
        if os.path.basename(os.path.normpath(os.fspath(path))) == "raw_model.obj":
            return str(escaped)
        return os.path.realpath(path)

    monkeypatch.setattr(loader_module, "_realpath", fake_realpath)

    result = load_raw_obj(_source(obj), allowed_roots=[allowed])

    assert result["status"]["state"] == "mesh_path_outside_allowed_root"
    assert result["status"]["reasons"] == ["resolved_path_escapes_allowed_root"]
    assert result["geometry"] is None


def test_missing_file_is_rejected(tmp_path):
    missing = tmp_path / "m1" / "raw_model.obj"

    result = load_raw_obj(_source(missing), allowed_roots=[tmp_path])

    assert result["status"]["state"] == "mesh_file_not_found"


@pytest.mark.parametrize("bad", [None, 123, True, b"C:/x/raw_model.obj"])
def test_invalid_path_type_is_rejected(tmp_path, bad):
    result = load_raw_obj(
        {"model_id": "m1", "raw_model_path": bad}, allowed_roots=[tmp_path]
    )

    assert result["status"]["state"] == "mesh_path_invalid_type"
    assert result["geometry"] is None


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_path_is_rejected(tmp_path, bad):
    result = load_raw_obj(
        {"model_id": "m1", "raw_model_path": bad}, allowed_roots=[tmp_path]
    )

    assert result["status"]["state"] == "mesh_path_missing"


def test_directory_path_is_rejected(tmp_path):
    folder = tmp_path / "m1"
    folder.mkdir()

    result = load_raw_obj(_source(folder), allowed_roots=[tmp_path])

    assert result["status"]["state"] == "mesh_invalid_extension"


def test_allowed_roots_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv(DEFAULT_ROOT_ENV_VAR, raising=False)
    obj = _make_obj(tmp_path)

    with pytest.raises(ValueError, match="allowed_roots is required"):
        load_raw_obj(_source(obj))


def test_allowed_roots_may_come_from_environment(tmp_path, monkeypatch):
    obj = _make_obj(tmp_path)
    monkeypatch.setenv(DEFAULT_ROOT_ENV_VAR, str(tmp_path))

    result = load_raw_obj(_source(obj))

    assert result["status"]["state"] == "mesh_loaded_valid"


# ---------------------------------------------------------------------------
# 13, 14, 15. registry validation
# ---------------------------------------------------------------------------

def _matching_reference(**overrides):
    reference = {
        "raw_bounds_min_xyz": [0.0, 0.0, 0.0],
        "raw_bounds_max_xyz": [1.0, 1.0, 0.0],
        "full_dims_xyz": [1.0, 1.0, 0.0],
        "vertex_count": 3,
    }
    reference.update(overrides)
    return reference


def test_registry_reference_match_is_recorded(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(tmp_path, obj, expected=_matching_reference())

    assert result["status"]["state"] == "mesh_loaded_valid"
    assert result["validation"]["reference"] == "present"
    assert result["validation"]["bounds_status"] == "match"
    assert result["validation"]["dims_status"] == "match"
    assert result["validation"]["vertex_count_status"] == "match"
    assert result["validation"]["abs_tol"] == pytest.approx(1e-6)
    assert result["validation"]["rel_tol"] == pytest.approx(1e-6)
    assert "mesh_bounds_unvalidated" not in result["warnings"]


def test_registry_bounds_mismatch_blocks_the_mesh(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(
        tmp_path,
        obj,
        expected=_matching_reference(raw_bounds_max_xyz=[9.0, 1.0, 0.0]),
    )

    assert result["status"]["state"] == "mesh_registry_dims_mismatch"
    assert result["status"]["reasons"] == ["raw_bounds_mismatch"]
    assert result["geometry"] is None


def test_registry_dims_mismatch_blocks_the_mesh(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(
        tmp_path, obj, expected=_matching_reference(full_dims_xyz=[5.0, 1.0, 0.0])
    )

    assert result["status"]["state"] == "mesh_registry_dims_mismatch"
    assert result["status"]["reasons"] == ["full_dims_mismatch"]


def test_vertex_count_mismatch_blocks_the_mesh(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(tmp_path, obj, expected=_matching_reference(vertex_count=99))

    assert result["status"]["state"] == "mesh_registry_dims_mismatch"
    assert result["status"]["reasons"] == ["vertex_count_mismatch"]
    assert result["validation"]["vertex_count_status"] == "mismatch"


def test_tolerance_is_configurable(tmp_path):
    obj = _make_obj(tmp_path)

    strict = _load(
        tmp_path,
        obj,
        expected=_matching_reference(raw_bounds_max_xyz=[1.001, 1.0, 0.0]),
        abs_tol=1e-9,
        rel_tol=0.0,
    )
    relaxed = _load(
        tmp_path,
        obj,
        expected=_matching_reference(raw_bounds_max_xyz=[1.001, 1.0, 0.0]),
        abs_tol=1e-2,
        rel_tol=0.0,
    )

    assert strict["status"]["state"] == "mesh_registry_dims_mismatch"
    assert relaxed["status"]["state"] == "mesh_loaded_valid"
    assert relaxed["validation"]["abs_tol"] == pytest.approx(1e-2)


def test_absent_reference_still_loads_with_warning(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_loaded_valid"
    assert result["validation"]["reference"] == "absent"
    assert result["validation"]["bounds_status"] == "not_checked"
    assert "mesh_bounds_unvalidated" in result["warnings"]


def test_partial_reference_checks_only_what_is_provided(tmp_path):
    obj = _make_obj(tmp_path)

    result = _load(tmp_path, obj, expected={"vertex_count": 3})

    assert result["validation"]["vertex_count_status"] == "match"
    assert result["validation"]["bounds_status"] == "not_checked"
    assert result["validation"]["dims_status"] == "not_checked"


def test_full_registry_record_may_be_passed_as_reference(tmp_path):
    obj = _make_obj(tmp_path)
    record = _matching_reference()
    record.update({"category": "chair", "image_path": "x.jpg", "theme": "Modern"})

    result = _load(tmp_path, obj, expected=record)

    assert result["status"]["state"] == "mesh_loaded_valid"


# ---------------------------------------------------------------------------
# 16, 17. materials
# ---------------------------------------------------------------------------

def test_mtllib_is_recorded_but_never_opened(tmp_path):
    text = "mtllib model.mtl\nusemtl chair_wire\ng CHAIR\n" + TRIANGLE
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert result["materials"]["mtllib"] == "model.mtl"
    assert result["materials"]["usemtl"] == ["chair_wire"]
    assert result["materials"]["groups"] == ["CHAIR"]
    assert "mesh_material_unresolved" in result["warnings"]
    assert result["status"]["state"] == "mesh_loaded_valid"


def test_external_mtllib_path_is_metadata_only(tmp_path):
    external = "C:\\outside\\does_not_exist\\secret.mtl"
    text = f"mtllib {external}\n" + TRIANGLE
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    # Recorded verbatim, never resolved, never opened, never followed.
    assert result["materials"]["mtllib"] == external
    assert result["status"]["state"] == "mesh_loaded_valid"


def test_missing_mtllib_is_harmless(tmp_path):
    text = "mtllib definitely_not_here.mtl\n" + TRIANGLE
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert not (tmp_path / "m1" / "definitely_not_here.mtl").exists()
    assert result["status"]["state"] == "mesh_loaded_valid"


# ---------------------------------------------------------------------------
# 18. n-gons preserved
# ---------------------------------------------------------------------------

def test_ngon_faces_are_preserved_with_warning(tmp_path):
    text = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n"
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert result["geometry"]["faces"] == [[0, 1, 2, 3]]
    assert result["counts"]["face_degree_max"] == 4
    assert "mesh_ngon_faces_present" in result["warnings"]
    assert result["status"]["state"] == "mesh_loaded_valid"


# ---------------------------------------------------------------------------
# 19. resource guards
# ---------------------------------------------------------------------------

TWO_FACES = "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 1 1 0\nf 1 2 3\nf 2 4 3\n"


@pytest.mark.parametrize(
    "limits, text, reason",
    [
        ({"max_file_bytes": 1}, TRIANGLE, "guard_exceeded:max_file_bytes"),
        ({"max_vertices": 2}, TRIANGLE, "guard_exceeded:max_vertices"),
        ({"max_faces": 1}, TWO_FACES, "guard_exceeded:max_faces"),
        ({"max_face_degree": 2}, TRIANGLE, "guard_exceeded:max_face_degree"),
        ({"max_line_bytes": 2}, TRIANGLE, "guard_exceeded:max_line_bytes"),
    ],
)
def test_guards_are_enforced_when_configured(tmp_path, limits, text, reason):
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj, limits=limits)

    assert result["status"]["state"] == "mesh_parse_failed"
    assert result["status"]["reasons"] == [reason]
    assert result["geometry"] is None


def test_guards_default_to_disabled(tmp_path):
    obj = _make_obj(tmp_path, text=TRIANGLE)

    result = _load(tmp_path, obj)

    assert result["status"]["state"] == "mesh_loaded_valid"


def test_unknown_limit_name_is_rejected(tmp_path):
    obj = _make_obj(tmp_path)

    with pytest.raises(ValueError, match="unknown limit"):
        _load(tmp_path, obj, limits={"max_triangles": 1})


# ---------------------------------------------------------------------------
# 20. no transform, no basis application
# ---------------------------------------------------------------------------

def test_loader_does_not_import_or_apply_the_placement_basis():
    import core.asset.raw_obj_loader as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "FurnitureAdapter" not in source
    assert "basis_position" not in source
    assert "diffuscene_y_up_to_architectos_z_up_v1" not in source


def test_loader_does_not_triangulate_or_reorder(tmp_path):
    text = "v 5 0 0\nv 0 5 0\nv 0 0 5\nv 1 1 1\nf 1 2 3 4\n"
    obj = _make_obj(tmp_path, text=text)

    result = _load(tmp_path, obj)

    assert result["geometry"]["vertices_xyz"] == [
        [5.0, 0.0, 0.0],
        [0.0, 5.0, 0.0],
        [0.0, 0.0, 5.0],
        [1.0, 1.0, 1.0],
    ]
    assert result["geometry"]["faces"] == [[0, 1, 2, 3]]


# ---------------------------------------------------------------------------
# ONE real 3D-FUTURE asset integration test
# ---------------------------------------------------------------------------

REAL_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_MODEL_ID = "27059911-89f4-3e78-a511-4c9b8cf51fb3"
REAL_OBJ = REAL_ROOT / "3D-FUTURE-model-part1" / REAL_MODEL_ID / "raw_model.obj"

REAL_EXPECTED = {
    "raw_bounds_min_xyz": [-0.252954, 0.000247, -0.246412],
    "raw_bounds_max_xyz": [0.257616, 0.864153, 0.265119],
    "full_dims_xyz": [0.51057, 0.863906, 0.511531],
    "vertex_count": 475,
}


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_real_3d_future_raw_model_validates_against_registry():
    result = load_raw_obj(
        {
            "source": "3D-FUTURE",
            "model_id": REAL_MODEL_ID,
            "raw_model_path": str(REAL_OBJ),
        },
        expected=REAL_EXPECTED,
        allowed_roots=[REAL_ROOT],
    )

    assert result["status"]["state"] == "mesh_loaded_valid"
    assert result["status"]["reasons"] == []

    assert result["counts"]["vertices"] == 475
    assert result["counts"]["faces"] == 884
    assert result["counts"]["face_degree_max"] == 3

    assert result["validation"]["reference"] == "present"
    assert result["validation"]["bounds_status"] == "match"
    assert result["validation"]["dims_status"] == "match"
    assert result["validation"]["vertex_count_status"] == "match"

    assert result["bounds"]["dims_xyz"] == pytest.approx(
        [0.51057, 0.863906, 0.511531], abs=1e-6
    )
    assert result["bounds"]["min_xyz"] == pytest.approx(
        [-0.252954, 0.000247, -0.246412], abs=1e-6
    )
    assert result["bounds"]["max_xyz"] == pytest.approx(
        [0.257616, 0.864153, 0.265119], abs=1e-6
    )

    assert result["materials"]["mtllib"] == "model.mtl"
    assert "mesh_material_unresolved" in result["warnings"]
    assert "mesh_vn_vt_ignored" in result["warnings"]

    # Raw local frame preserved: origin untouched, bbox center reported apart.
    assert result["mesh_frame"] == "raw_mesh_local_frame"
    assert result["pivot"]["mesh_origin_xyz"] == [0.0, 0.0, 0.0]
    assert result["pivot"]["bbox_center_xyz"] == pytest.approx(
        [0.002331, 0.4322, 0.0093535], abs=1e-6
    )
