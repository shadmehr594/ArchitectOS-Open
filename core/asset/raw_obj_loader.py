"""Minimal raw 3D-FUTURE OBJ loader (Phase 3D-J).

Reads a single ``raw_model.obj`` and returns validated in-memory geometry in
``RAW_MESH_LOCAL_FRAME``.

This module deliberately does NOT:

- remap axes, rotate, scale, recenter or normalize geometry
- apply the DiffuScene -> ArchitectOS placement basis
- place, transform or insert anything into a scene
- open ``.mtl`` files, resolve ``mtllib`` paths, or load textures
- triangulate faces or compute/validate normals
- infer mesh forward/up axes or dimension-axis correspondence

Every unresolved item from Phase 3D-A..3D-I is preserved as an explicit status
or warning; nothing is silently resolved.
"""

from __future__ import annotations

import codecs
import math
import os
from typing import Any, Iterable, Mapping, Sequence


FORMAT_VERSION = "raw_obj_mesh_v1"
MESH_FRAME = "raw_mesh_local_frame"

EXPECTED_FILENAME = "raw_model.obj"
EXPECTED_SUFFIX = ".obj"

# PROVISIONAL VALIDATION TOLERANCE (Phase 3D-I / 3D-J).
# These are NOT verified permanent thresholds. They are exposed as arguments and
# echoed into the result's ``validation`` metadata so a caller can calibrate
# them on real data before relying on them.
PROVISIONAL_ABS_TOL = 1e-6
PROVISIONAL_REL_TOL = 1e-6

DEFAULT_ROOT_ENV_VAR = "ARCHITECTOS_3D_FUTURE_ROOT"

_GUARD_NAMES = (
    "max_file_bytes",
    "max_vertices",
    "max_faces",
    "max_face_degree",
    "max_line_bytes",
)

# Records recognized but never consumed as geometry.
_IGNORED_KEYWORDS = frozenset({"vt", "vn", "mtllib", "usemtl", "g", "o", "s"})

_REFERENCE_KEYS = (
    "raw_bounds_min_xyz",
    "raw_bounds_max_xyz",
    "full_dims_xyz",
    "vertex_count",
)


# ---------------------------------------------------------------------------
# result assembly
# ---------------------------------------------------------------------------

def _result_stub(source, model_id, raw_model_path):
    return {
        "format_version": FORMAT_VERSION,
        "source": source,
        "model_id": model_id,
        "raw_model_path": raw_model_path,
        "mesh_frame": MESH_FRAME,
        "geometry": None,
        "bounds": None,
        "counts": {
            "vertices": 0,
            "faces": 0,
            "face_degree_max": 0,
            "ignored_lines": 0,
        },
        "pivot": None,
        "materials": {"mtllib": None, "usemtl": [], "groups": []},
        "validation": {
            "reference": "absent",
            "bounds_status": "not_checked",
            "dims_status": "not_checked",
            "vertex_count_status": "not_checked",
            "abs_tol": None,
            "rel_tol": None,
        },
        "warnings": [],
        "status": {"state": None, "reasons": []},
    }


def _fail(result, state, reason=None):
    """Fatal result: geometry/bounds/pivot stay null, no partial mesh leaks."""

    result["geometry"] = None
    result["bounds"] = None
    result["pivot"] = None
    result["counts"] = {
        "vertices": 0,
        "faces": 0,
        "face_degree_max": 0,
        "ignored_lines": 0,
    }
    result["status"] = {
        "state": state,
        "reasons": [reason] if reason else [],
    }

    return result


# ---------------------------------------------------------------------------
# argument normalization
# ---------------------------------------------------------------------------

def _normalize_roots(allowed_roots):
    if allowed_roots is None:
        env_root = os.environ.get(DEFAULT_ROOT_ENV_VAR)
        allowed_roots = [env_root] if env_root else None

    if allowed_roots is None:
        raise ValueError(
            "allowed_roots is required: pass the 3D-FUTURE dataset root(s) or "
            f"set {DEFAULT_ROOT_ENV_VAR}"
        )
    if isinstance(allowed_roots, (str, bytes, os.PathLike)):
        allowed_roots = [allowed_roots]

    roots = []
    for root in allowed_roots:
        if isinstance(root, bytes):
            raise ValueError("allowed_roots entries must be text paths")
        text = os.fspath(root)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("allowed_roots entries must be non-empty paths")
        roots.append(os.path.normpath(os.path.abspath(text)))

    if not roots:
        raise ValueError("allowed_roots must contain at least one root")

    return roots


def _normalize_limits(limits):
    if limits is None:
        limits = {}
    if not isinstance(limits, Mapping):
        raise ValueError("limits must be a mapping")

    unknown = [key for key in limits if key not in _GUARD_NAMES]
    if unknown:
        raise ValueError("unknown limit(s): " + ", ".join(sorted(unknown)))

    normalized = {}
    for name in _GUARD_NAMES:
        value = limits.get(name)
        if value is None:
            normalized[name] = None
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"limit {name} must be a positive int or None")
        normalized[name] = value

    return normalized


def _normalize_expected(expected):
    if expected is None:
        return None
    if not isinstance(expected, Mapping):
        raise ValueError("expected must be a mapping or None")

    normalized = {}
    for key in _REFERENCE_KEYS:
        if key not in expected:
            continue
        value = expected[key]
        if key == "vertex_count":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("expected vertex_count must be an int")
            normalized[key] = value
            continue
        if isinstance(value, (str, bytes)) or not isinstance(
            value, Sequence
        ) or len(value) != 3:
            raise ValueError(f"expected {key} must contain three values")
        numbers = []
        for item in value:
            if isinstance(item, bool):
                raise ValueError(f"expected {key} must be numeric")
            number = float(item)
            if not math.isfinite(number):
                raise ValueError(f"expected {key} must be finite")
            numbers.append(number)
        normalized[key] = numbers

    return normalized or None


def _normalize_tolerance(abs_tol, rel_tol):
    def one(value, default, label):
        if value is None:
            return default
        if isinstance(value, bool):
            raise ValueError(f"{label} must be a non-negative number")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{label} must be a non-negative finite number")
        return number

    return one(abs_tol, PROVISIONAL_ABS_TOL, "abs_tol"), one(
        rel_tol, PROVISIONAL_REL_TOL, "rel_tol"
    )


# ---------------------------------------------------------------------------
# path security
# ---------------------------------------------------------------------------

def _is_inside(target, roots):
    """Containment via commonpath, never a naive string prefix check."""

    target_key = os.path.normcase(os.path.normpath(target))
    for root in roots:
        root_key = os.path.normcase(os.path.normpath(root))
        try:
            if os.path.commonpath([target_key, root_key]) == root_key:
                return True
        except ValueError:
            # Different drives, or mixed absolute/relative paths.
            continue

    return False


def _realpath(path):
    """Canonicalize to the real target path.

    Resolves symlinks, junctions and Windows reparse points. Kept as a module
    level indirection so the post-canonicalization containment guard is
    directly testable.
    """

    return os.path.realpath(path)


def _validate_path(raw_path, model_id, roots):
    """Twelve-step validation. Returns (state, reason, resolved_path)."""

    # 1. type
    if isinstance(raw_path, bool) or not isinstance(
        raw_path, (str, os.PathLike)
    ):
        return "mesh_path_invalid_type", "raw_model_path_must_be_a_text_path", None
    try:
        text = os.fspath(raw_path)
    except TypeError:
        return "mesh_path_invalid_type", "raw_model_path_must_be_a_text_path", None
    if isinstance(text, bytes):
        return "mesh_path_invalid_type", "raw_model_path_must_be_text_not_bytes", None

    # 2. empty / NUL
    if not text.strip():
        return "mesh_path_missing", "raw_model_path_is_empty", None
    if "\x00" in text:
        return "mesh_path_missing", "raw_model_path_contains_nul", None

    # 3. lexical absolute normalization (collapses '..' and '.')
    lexical = os.path.normpath(os.path.abspath(text))

    # 4. lexical containment, before any filesystem probe
    if not _is_inside(lexical, roots):
        return (
            "mesh_path_outside_allowed_root",
            "lexical_path_outside_allowed_root",
            None,
        )

    # 5. existence
    if not os.path.exists(lexical):
        return "mesh_file_not_found", "target_does_not_exist", None

    # 6 + 7 + 8. canonicalize the real target and the real root, then re-check
    # containment. This defeats symlinks, junctions and reparse-point escapes.
    real_target = _realpath(lexical)
    real_roots = [_realpath(root) for root in roots]
    if not _is_inside(real_target, real_roots):
        return (
            "mesh_path_outside_allowed_root",
            "resolved_path_escapes_allowed_root",
            None,
        )

    # 9. expected filename
    if os.path.basename(real_target).lower() != EXPECTED_FILENAME:
        return (
            "mesh_invalid_extension",
            f"basename_must_be_{EXPECTED_FILENAME}",
            None,
        )

    # 10. expected extension
    if os.path.splitext(real_target)[1].lower() != EXPECTED_SUFFIX:
        return "mesh_invalid_extension", "suffix_must_be_.obj", None

    # 11. parent directory must match model_id exactly
    if not isinstance(model_id, str) or not model_id.strip():
        return "mesh_path_model_id_mismatch", "model_id_missing", None
    if os.path.basename(os.path.dirname(real_target)) != model_id:
        return (
            "mesh_path_model_id_mismatch",
            "parent_directory_does_not_match_model_id",
            None,
        )

    # 12. regular file
    if not os.path.isfile(real_target):
        return "mesh_file_not_found", "target_is_not_a_regular_file", None

    return None, None, real_target


# ---------------------------------------------------------------------------
# OBJ parsing
# ---------------------------------------------------------------------------

def _parse_obj(path, limits, result):
    """Parse geometry only. Returns a fatal state name, or None on success."""

    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    usemtl: list[str] = []
    groups: list[str] = []
    mtllib = None
    ignored_lines = 0
    unknown_keywords: set[str] = set()
    vt_lines = 0
    vn_lines = 0

    def guard(name):
        limit = limits[name]
        return limit is not None and limit

    try:
        handle = open(path, "rb")
    except OSError:
        return _fail(result, "mesh_file_not_found", "open_failed")

    with handle:
        if guard("max_file_bytes"):
            size = os.fstat(handle.fileno()).st_size
            if size > limits["max_file_bytes"]:
                return _fail(
                    result, "mesh_parse_failed", "guard_exceeded:max_file_bytes"
                )

        for index, raw in enumerate(handle):
            if index == 0 and raw.startswith(codecs.BOM_UTF8):
                raw = raw[len(codecs.BOM_UTF8):]

            if guard("max_line_bytes") and len(raw) > limits["max_line_bytes"]:
                return _fail(
                    result, "mesh_parse_failed", "guard_exceeded:max_line_bytes"
                )

            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                return _fail(result, "mesh_parse_failed", "line_decode_failed")

            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split()
            keyword = parts[0]

            if keyword == "v":
                if len(parts) < 4:
                    return _fail(
                        result,
                        "mesh_parse_failed",
                        "vertex_record_missing_components",
                    )
                try:
                    coords = [
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                    ]
                except ValueError:
                    return _fail(
                        result, "mesh_parse_failed", "vertex_record_non_numeric"
                    )
                if not all(math.isfinite(value) for value in coords):
                    return _fail(
                        result,
                        "mesh_nonfinite_vertices",
                        "vertex_coordinate_not_finite",
                    )
                if guard("max_vertices") and len(vertices) + 1 > limits["max_vertices"]:
                    return _fail(
                        result, "mesh_parse_failed", "guard_exceeded:max_vertices"
                    )
                vertices.append(coords)
                continue

            if keyword == "f":
                tokens = parts[1:]
                if len(tokens) < 3:
                    return _fail(
                        result, "mesh_invalid_faces", "face_degree_below_3"
                    )
                indices: list[int] = []
                for token in tokens:
                    head = token.split("/", 1)[0]
                    if not head:
                        return _fail(
                            result,
                            "mesh_invalid_faces",
                            "face_index_missing",
                        )
                    try:
                        value = int(head)
                    except ValueError:
                        return _fail(
                            result,
                            "mesh_invalid_faces",
                            "face_index_non_integer",
                        )
                    if value == 0:
                        return _fail(
                            result, "mesh_invalid_faces", "face_index_zero"
                        )
                    # OBJ is 1-based; negative indices are relative to the
                    # vertices defined so far (-1 is the most recent vertex).
                    resolved = len(vertices) + value if value < 0 else value - 1
                    if resolved < 0 or resolved >= len(vertices):
                        return _fail(
                            result,
                            "mesh_invalid_faces",
                            "face_index_out_of_range",
                        )
                    indices.append(resolved)

                degree = len(indices)
                if guard("max_face_degree") and degree > limits["max_face_degree"]:
                    return _fail(
                        result,
                        "mesh_parse_failed",
                        "guard_exceeded:max_face_degree",
                    )
                if guard("max_faces") and len(faces) + 1 > limits["max_faces"]:
                    return _fail(
                        result, "mesh_parse_failed", "guard_exceeded:max_faces"
                    )
                faces.append(indices)
                continue

            if keyword in _IGNORED_KEYWORDS:
                if keyword == "vt":
                    vt_lines += 1
                elif keyword == "vn":
                    vn_lines += 1
                elif keyword == "mtllib":
                    # Recorded verbatim only. Never resolved, never opened.
                    if mtllib is None and len(parts) > 1:
                        mtllib = parts[1]
                elif keyword == "usemtl":
                    if len(parts) > 1:
                        usemtl.append(parts[1])
                elif keyword in ("g", "o"):
                    if len(parts) > 1:
                        groups.append(parts[1])
                continue

            ignored_lines += 1
            unknown_keywords.add(keyword)

    if not vertices:
        return _fail(result, "mesh_empty", "no_vertex_records")

    result["geometry"] = {
        "index_base": 0,
        "vertices_xyz": vertices,
        "faces": faces,
    }
    result["counts"] = {
        "vertices": len(vertices),
        "faces": len(faces),
        "face_degree_max": max((len(face) for face in faces), default=0),
        "ignored_lines": ignored_lines,
    }
    result["materials"] = {
        "mtllib": mtllib,
        "usemtl": usemtl,
        "groups": groups,
    }

    if result["counts"]["face_degree_max"] > 3:
        result["warnings"].append("mesh_ngon_faces_present")
    if mtllib is not None:
        result["warnings"].append("mesh_material_unresolved")
    if vt_lines or vn_lines:
        result["warnings"].append("mesh_vn_vt_ignored")
    if unknown_keywords:
        result["warnings"].append("mesh_unknown_keyword_ignored")

    return None


# ---------------------------------------------------------------------------
# bounds + registry validation
# ---------------------------------------------------------------------------

def _compute_bounds(vertices):
    minimum = [min(vertex[i] for vertex in vertices) for i in range(3)]
    maximum = [max(vertex[i] for vertex in vertices) for i in range(3)]

    return minimum, maximum


def _within(computed, expected, abs_tol, rel_tol):
    return abs(computed - expected) <= abs_tol + rel_tol * abs(expected)


def _triple_within(computed, expected, abs_tol, rel_tol):
    return all(
        _within(computed[i], expected[i], abs_tol, rel_tol) for i in range(3)
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def load_raw_obj(
    mesh_source: Mapping[str, Any],
    expected: Mapping[str, Any] | None = None,
    allowed_roots: Iterable[Any] | None = None,
    limits: Mapping[str, Any] | None = None,
    abs_tol: float | None = None,
    rel_tol: float | None = None,
) -> dict[str, Any]:
    """Load one raw 3D-FUTURE OBJ into validated RAW_MESH_LOCAL_FRAME geometry.

    ``mesh_source`` requires ``model_id`` and ``raw_model_path``.
    ``expected`` is an optional registry validation reference; a full registry
    record may be passed (only the four known keys are read).
    ``allowed_roots`` is required unless ``ARCHITECTOS_3D_FUTURE_ROOT`` is set.
    ``limits`` guards default to ``None`` (disabled / uncalibrated).
    """

    if not isinstance(mesh_source, Mapping):
        raise ValueError("mesh_source must be a mapping")

    roots = _normalize_roots(allowed_roots)
    guard_limits = _normalize_limits(limits)
    reference = _normalize_expected(expected)
    abs_tol, rel_tol = _normalize_tolerance(abs_tol, rel_tol)

    model_id = mesh_source.get("model_id")
    raw_model_path = mesh_source.get("raw_model_path")
    source = mesh_source.get("source") or "3D-FUTURE"

    result = _result_stub(source, model_id, raw_model_path)

    state, reason, resolved = _validate_path(raw_model_path, model_id, roots)
    if state is not None:
        return _fail(result, state, reason)

    result["raw_model_path"] = resolved

    failure = _parse_obj(resolved, guard_limits, result)
    if failure is not None:
        return failure

    vertices = result["geometry"]["vertices_xyz"]
    minimum, maximum = _compute_bounds(vertices)
    dims = [maximum[i] - minimum[i] for i in range(3)]
    center = [(minimum[i] + maximum[i]) / 2.0 for i in range(3)]

    result["bounds"] = {
        "min_xyz": minimum,
        "max_xyz": maximum,
        "dims_xyz": dims,
        "center_xyz": center,
    }
    # The loader never recenters: the OBJ origin is reported as-is and the
    # computed bbox center is reported separately.
    result["pivot"] = {
        "mesh_origin_xyz": [0.0, 0.0, 0.0],
        "bbox_center_xyz": center,
    }

    if not all(math.isfinite(value) for value in dims) or any(
        value < 0 for value in dims
    ):
        return _fail(result, "mesh_bounds_invalid", "dimension_not_positive_finite")

    if any(value == 0 for value in dims):
        result["warnings"].append("mesh_zero_dimension")

    validation = result["validation"]
    validation["abs_tol"] = abs_tol
    validation["rel_tol"] = rel_tol

    if reference is None:
        result["warnings"].append("mesh_bounds_unvalidated")
        result["status"] = {"state": "mesh_loaded_valid", "reasons": []}
        return result

    validation["reference"] = "present"
    mismatches = []

    if "vertex_count" in reference:
        if len(vertices) == reference["vertex_count"]:
            validation["vertex_count_status"] = "match"
        else:
            validation["vertex_count_status"] = "mismatch"
            mismatches.append("vertex_count_mismatch")

    if "raw_bounds_min_xyz" in reference and "raw_bounds_max_xyz" in reference:
        if _triple_within(
            minimum, reference["raw_bounds_min_xyz"], abs_tol, rel_tol
        ) and _triple_within(
            maximum, reference["raw_bounds_max_xyz"], abs_tol, rel_tol
        ):
            validation["bounds_status"] = "match"
        else:
            validation["bounds_status"] = "mismatch"
            mismatches.append("raw_bounds_mismatch")

    if "full_dims_xyz" in reference:
        if _triple_within(dims, reference["full_dims_xyz"], abs_tol, rel_tol):
            validation["dims_status"] = "match"
        else:
            validation["dims_status"] = "mismatch"
            mismatches.append("full_dims_mismatch")

    if mismatches:
        # Blocking for this loader: never emit geometry that disagrees with the
        # registry as valid.
        return _fail(result, "mesh_registry_dims_mismatch", ",".join(mismatches))

    result["status"] = {"state": "mesh_loaded_valid", "reasons": []}

    return result
