"""Focused tests for the declarative furniture unit contract (Phase 3D-AL)."""

import builtins
import copy
import inspect
import io
import json
import tokenize
from pathlib import Path

import pytest

import core.asset.furniture_unit_contract as contract_module
from core.asset.furniture_unit_contract import build_furniture_unit_contract


_UNSET = object()


REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "3d_future"
    / "asset_registry.json"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _evidence(
    numeric_unit="meters",
    status="supported",
    source="diffuscene_dataset_stats_and_processed_data",
    notes=None,
    **overrides,
):
    evidence = {
        "numeric_unit": numeric_unit,
        "status": status,
        "source": source,
    }
    if notes is not None:
        evidence["notes"] = notes
    evidence.update(overrides)

    return evidence


def _raw_evidence(**overrides):
    overrides.setdefault(
        "source", "3d_future_registry_raw_obj_measurement"
    )

    return _evidence(**overrides)


def _build(diffuscene=_UNSET, raw_asset=_UNSET, dimensions=None):
    """Build a contract, defaulting evidence only when it is NOT supplied.

    ``_UNSET`` matters: an explicit ``None`` must reach the contract so that
    malformed-evidence handling can be tested.
    """

    return build_furniture_unit_contract(
        diffuscene_unit_evidence=(
            _evidence() if diffuscene is _UNSET else diffuscene
        ),
        raw_asset_unit_evidence=(
            _raw_evidence() if raw_asset is _UNSET else raw_asset
        ),
        asset_dimensions_xyz=dimensions,
    )


def _imported_modules(module):
    """Top-level module names imported by ``module`` (no substring guessing)."""

    names = set()
    for line in inspect.getsource(module).splitlines():
        line = line.strip()
        if line.startswith("from "):
            names.add(line[len("from "):].split()[0].split(".")[0])
        elif line.startswith("import "):
            for part in line[len("import "):].split(","):
                names.add(part.strip().split()[0].split(".")[0])

    return names


def _code_source(module):
    """Module source with comments and string literals removed.

    Structural checks must inspect executable code, not prose: the module
    docstring legitimately names the things it refuses to do.
    """

    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


# ---------------------------------------------------------------------------
# 1 - 5. confidence model
# ---------------------------------------------------------------------------

def test_supported_meters_with_plausible_dimensions_is_supported():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert contract["type"] == "furniture_unit_contract"
    assert contract["version"] == "furniture_unit_contract_v1"
    assert contract["compatibility"]["status"] == "supported"
    assert contract["compatibility"]["same_nominal_unit"] is True
    assert contract["asset_dimension_check"]["status"] == "plausible"
    assert contract["status"]["state"] == "unit_contract_supported"


def test_supported_inputs_never_become_proven():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert contract["diffuscene"]["proven"] is False
    assert contract["raw_asset"]["proven"] is False
    assert contract["compatibility"]["status"] != "proven"
    assert contract["status"]["state"] != "unit_contract_proven"
    assert "diffuscene_unit_supported_not_proven" in (
        contract["compatibility"]["reasons"]
    )
    assert "raw_asset_unit_supported_not_proven" in (
        contract["compatibility"]["reasons"]
    )


def test_current_known_evidence_stays_supported_not_proven():
    """The Phase 3D-AK verdict must survive the contract unchanged."""

    contract = _build(dimensions=[0.26566, 1.90102, 0.26566])

    assert contract["diffuscene"]["numeric_unit"] == "meters"
    assert contract["diffuscene"]["status"] == "supported"
    assert contract["diffuscene"]["proven"] is False
    assert contract["raw_asset"]["numeric_unit"] == "meters"
    assert contract["raw_asset"]["status"] == "supported"
    assert contract["raw_asset"]["proven"] is False
    assert contract["compatibility"]["status"] == "supported"


def test_both_proven_and_same_unit_may_be_proven():
    contract = _build(
        diffuscene=_evidence(status="proven"),
        raw_asset=_raw_evidence(status="proven"),
        dimensions=[0.51, 0.86, 0.51],
    )

    assert contract["diffuscene"]["proven"] is True
    assert contract["raw_asset"]["proven"] is True
    assert contract["compatibility"]["status"] == "proven"
    assert contract["status"]["state"] == "unit_contract_proven"


def test_proven_plus_supported_stays_supported():
    contract = _build(
        diffuscene=_evidence(status="proven"),
        raw_asset=_raw_evidence(status="supported"),
    )

    assert contract["compatibility"]["status"] == "supported"


def test_one_unresolved_side_forces_unresolved():
    contract = _build(
        diffuscene=_evidence(status="unresolved"),
        raw_asset=_raw_evidence(status="supported"),
    )

    assert contract["compatibility"]["status"] == "unresolved"
    assert contract["status"]["state"] == "unit_contract_unresolved"
    assert "diffuscene_unit_unresolved" in contract["compatibility"]["reasons"]


def test_both_unresolved_stays_unresolved():
    contract = _build(
        diffuscene=_evidence(status="unresolved"),
        raw_asset=_raw_evidence(status="unresolved"),
    )

    assert contract["compatibility"]["status"] == "unresolved"


def test_different_nominal_units_are_unresolved():
    contract = _build(
        diffuscene=_evidence(numeric_unit="meters", status="proven"),
        raw_asset=_raw_evidence(numeric_unit="centimeters", status="proven"),
    )

    assert contract["compatibility"]["same_nominal_unit"] is False
    assert contract["compatibility"]["status"] == "unresolved"
    assert "nominal_unit_mismatch" in contract["compatibility"]["reasons"]


def test_missing_nominal_unit_is_unresolved():
    contract = _build(
        diffuscene=_evidence(numeric_unit=None, status="proven"),
        raw_asset=_raw_evidence(numeric_unit="meters", status="proven"),
    )

    assert contract["compatibility"]["same_nominal_unit"] is None
    assert contract["compatibility"]["status"] == "unresolved"
    assert "nominal_unit_missing" in contract["compatibility"]["reasons"]


def test_supplied_proven_flag_cannot_contradict_status():
    """No evidence object may silently promote SUPPORTED to PROVEN."""

    with pytest.raises(ValueError, match="can never be reported as PROVEN"):
        _build(diffuscene=_evidence(status="supported", proven=True))


def test_supplied_proven_flag_must_be_boolean():
    with pytest.raises(ValueError, match="proven must be a boolean"):
        _build(diffuscene=_evidence(status="proven", proven="yes"))


def test_supplied_proven_flag_agreeing_with_status_is_accepted():
    contract = _build(
        diffuscene=_evidence(status="proven", proven=True),
        raw_asset=_raw_evidence(status="proven", proven=True),
    )

    assert contract["compatibility"]["status"] == "proven"


# ---------------------------------------------------------------------------
# 6 - 8. dimension outlier diagnostics
# ---------------------------------------------------------------------------

def test_oversize_dimension_downgrades_to_unresolved():
    contract = _build(dimensions=[6.0, 0.6, 0.6])

    assert contract["asset_dimension_check"]["status"] == "suspicious"
    assert contract["asset_dimension_check"]["severe_oversize"] is False
    assert contract["compatibility"]["status"] == "unresolved"
    assert "asset_dimension_suspicious" in contract["compatibility"]["reasons"]
    assert contract["asset_dimension_check"]["reasons"][0] == (
        "asset_dimension_exceeds_expected_furniture_range"
    )


def test_severely_oversize_dimension_stays_unresolved():
    contract = _build(dimensions=[48.2572, 52.1568, 49.9912])

    assert contract["asset_dimension_check"]["status"] == "suspicious"
    assert contract["asset_dimension_check"]["severe_oversize"] is True
    assert contract["asset_dimension_check"]["max_dimension"] == pytest.approx(
        52.1568
    )
    assert contract["compatibility"]["status"] == "unresolved"


def test_dimension_suspicion_never_upgrades_confidence():
    """Suspicion is a one-way downgrade, even from PROVEN evidence."""

    contract = _build(
        diffuscene=_evidence(status="proven"),
        raw_asset=_raw_evidence(status="proven"),
        dimensions=[60.0, 60.0, 60.0],
    )

    assert contract["compatibility"]["status"] == "unresolved"
    assert contract["asset_dimension_check"]["severe_oversize"] is True


def test_absent_dimensions_are_not_evaluated_and_do_not_downgrade():
    contract = _build()

    assert contract["asset_dimension_check"]["status"] == "not_evaluated"
    assert contract["asset_dimension_check"]["max_dimension"] is None
    assert contract["asset_dimension_check"]["reasons"] == [
        "asset_dimensions_not_supplied"
    ]
    assert contract["compatibility"]["status"] == "supported"


def test_dimension_thresholds_are_declared_as_diagnostic_heuristics():
    check = _build(dimensions=[1.0, 1.0, 1.0])["asset_dimension_check"]

    assert check["thresholds"]["plausible_max_dimension"] == 5.0
    assert check["thresholds"]["severe_max_dimension"] == 50.0
    assert check["thresholds"]["basis"] == (
        "diagnostic_heuristic_not_unit_detection"
    )


def test_suspicious_dimensions_are_not_rescaled():
    dimensions = [48.2572, 52.1568, 49.9912]

    contract = _build(dimensions=dimensions)

    check = contract["asset_dimension_check"]
    # Reported verbatim: no /100, no *100, no cm->m conversion.
    assert check["max_dimension"] == max(dimensions)
    assert check["min_dimension"] == min(dimensions)
    assert check["max_dimension"] != max(dimensions) / 100.0
    assert contract["compatibility"]["scale_xyz"] == [1.0, 1.0, 1.0]
    assert contract["semantics"]["unit_conversion_applied"] is False


def test_dimension_reasons_never_assert_centimeters():
    check = _build(dimensions=[80.0, 80.0, 80.0])["asset_dimension_check"]

    joined = " ".join(check["reasons"]).lower()
    for forbidden in ("centimeter", "centimetre", "cm", "convert"):
        assert forbidden not in joined


# ---------------------------------------------------------------------------
# 9 - 10. identity scale / no scaling authorization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "diffuscene_status,raw_status,dimensions",
    [
        ("proven", "proven", [0.5, 0.9, 0.5]),
        ("supported", "supported", [0.5, 0.9, 0.5]),
        ("supported", "supported", [60.0, 60.0, 60.0]),
        ("unresolved", "supported", None),
        ("proven", "proven", None),
    ],
)
def test_identity_scale_always_preserved(
    diffuscene_status, raw_status, dimensions
):
    contract = _build(
        diffuscene=_evidence(status=diffuscene_status),
        raw_asset=_raw_evidence(status=raw_status),
        dimensions=dimensions,
    )

    assert contract["compatibility"]["scale_xyz"] == [1.0, 1.0, 1.0]
    assert contract["compatibility"]["geometry_scaling_authorized"] is False
    assert contract["semantics"]["non_identity_scale_authorized"] is False


def test_geometry_scaling_is_never_authorized():
    for dimensions in (None, [0.5, 0.9, 0.5], [80.0, 80.0, 80.0]):
        contract = _build(dimensions=dimensions)

        assert contract["compatibility"]["geometry_scaling_authorized"] is False


# ---------------------------------------------------------------------------
# 11 - 14. malformed dimensions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["x", 3, 1.5, [], {}, [1.0, 2.0], [1.0, 2.0, 3.0, 4.0], object()],
    ids=[
        "str",
        "int",
        "float",
        "empty-list",
        "dict",
        "too-short",
        "too-long",
        "object",
    ],
)
def test_malformed_dimensions_are_rejected(bad):
    with pytest.raises(ValueError, match="asset_dimensions_xyz"):
        _build(dimensions=bad)


@pytest.mark.parametrize(
    "bad",
    [[0.0, 1.0, 1.0], [-1.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, -0.5]],
    ids=["zero-x", "negative-x", "zero-y", "negative-z"],
)
def test_zero_or_negative_dimensions_are_rejected(bad):
    with pytest.raises(ValueError, match="strictly positive"):
        _build(dimensions=bad)


@pytest.mark.parametrize(
    "bad",
    [
        [float("nan"), 1.0, 1.0],
        [1.0, float("inf"), 1.0],
        [1.0, 1.0, float("-inf")],
    ],
    ids=["nan", "inf", "-inf"],
)
def test_non_finite_dimensions_are_rejected(bad):
    with pytest.raises(ValueError, match="finite"):
        _build(dimensions=bad)


@pytest.mark.parametrize(
    "bad",
    [[True, 1.0, 1.0], [1.0, False, 1.0], [1.0, 1.0, True]],
    ids=["x", "y", "z"],
)
def test_bool_dimensions_are_rejected(bad):
    with pytest.raises(ValueError, match="real numbers"):
        _build(dimensions=bad)


def test_dimension_strings_that_look_numeric_are_rejected():
    with pytest.raises(ValueError):
        _build(dimensions=["0.5", "0.9", "0.5"])


# ---------------------------------------------------------------------------
# 15 - 18. evidence validation
# ---------------------------------------------------------------------------

def test_evidence_mappings_are_required():
    with pytest.raises(TypeError):
        build_furniture_unit_contract()


@pytest.mark.parametrize("bad", [None, "x", 3, [], object()])
def test_non_mapping_evidence_is_rejected(bad):
    with pytest.raises(ValueError, match="diffuscene evidence must be a mapping"):
        _build(diffuscene=bad)

    with pytest.raises(ValueError, match="raw_asset evidence must be a mapping"):
        _build(raw_asset=bad)


@pytest.mark.parametrize(
    "bad",
    ["", "PROVEN", "assumed", "unknown", 1, True, None, [], {}],
    ids=[
        "empty",
        "upper",
        "assumed",
        "unknown",
        "int",
        "bool",
        "none",
        "list",
        "dict",
    ],
)
def test_malformed_status_is_rejected(bad):
    with pytest.raises(ValueError, match="status must be one of"):
        _build(diffuscene=_evidence(status=bad))


@pytest.mark.parametrize(
    "bad",
    ["", "   ", 3, 1.5, True, [], {}],
    ids=["empty", "whitespace", "int", "float", "bool", "list", "dict"],
)
def test_malformed_numeric_unit_is_rejected(bad):
    with pytest.raises(ValueError, match="numeric_unit"):
        _build(diffuscene=_evidence(numeric_unit=bad))


@pytest.mark.parametrize(
    "bad",
    ["", "   ", None, 3, True, [], {}],
    ids=["empty", "whitespace", "none", "int", "bool", "list", "dict"],
)
def test_malformed_source_is_rejected(bad):
    with pytest.raises(ValueError, match="source"):
        _build(diffuscene=_evidence(source=bad))


def test_missing_evidence_keys_are_rejected():
    for key in ("numeric_unit", "status", "source"):
        evidence = _evidence()
        del evidence[key]

        with pytest.raises(ValueError, match=f"missing: {key}"):
            _build(diffuscene=evidence)


def test_unknown_evidence_keys_are_rejected():
    with pytest.raises(ValueError, match="unknown diffuscene evidence key"):
        _build(diffuscene={**_evidence(), "unit_scale": 100.0})


@pytest.mark.parametrize(
    "bad",
    ["not-a-list", ("a", "b"), {"a": 1}, 3],
    ids=["str", "tuple", "dict", "int"],
)
def test_malformed_notes_are_rejected(bad):
    with pytest.raises(ValueError, match="notes must be a list"):
        _build(diffuscene=_evidence(notes=bad))


def test_non_string_notes_are_rejected():
    with pytest.raises(ValueError, match="notes must be strings"):
        _build(diffuscene=_evidence(notes=["ok", 3]))


# ---------------------------------------------------------------------------
# 19 - 21. copy / immutability / determinism
# ---------------------------------------------------------------------------

def test_evidence_notes_are_deep_copied():
    notes = ["center_is_bbox_center", "floor_plane_at_y_zero"]

    contract = _build(diffuscene=_evidence(notes=notes))

    assert contract["diffuscene"]["notes"] == [
        "center_is_bbox_center",
        "floor_plane_at_y_zero",
    ]
    assert contract["diffuscene"]["notes"] is not notes

    notes.append("mutated")
    assert contract["diffuscene"]["notes"] == [
        "center_is_bbox_center",
        "floor_plane_at_y_zero",
    ]


def test_dimension_input_is_not_aliased_or_mutated():
    dimensions = [0.51, 0.86, 0.51]
    before = list(dimensions)

    contract = _build(dimensions=dimensions)

    assert dimensions == before
    assert contract["asset_dimension_check"]["max_dimension"] == 0.86


def test_caller_inputs_are_not_mutated():
    diffuscene = _evidence(notes=["a"])
    raw_asset = _raw_evidence(notes=["b"])
    dimensions = [0.5, 0.9, 0.5]
    before = copy.deepcopy((diffuscene, raw_asset, dimensions))

    build_furniture_unit_contract(
        diffuscene_unit_evidence=diffuscene,
        raw_asset_unit_evidence=raw_asset,
        asset_dimensions_xyz=dimensions,
    )

    assert (diffuscene, raw_asset, dimensions) == before


def test_repeated_calls_are_deterministic():
    first = _build(dimensions=[0.51, 0.86, 0.51])
    second = _build(dimensions=[0.51, 0.86, 0.51])

    assert first == second
    assert first is not second
    assert first["diffuscene"] is not second["diffuscene"]


def test_output_evidence_does_not_alias_the_input():
    diffuscene = _evidence(notes=["a"])

    contract = _build(diffuscene=diffuscene)

    assert contract["diffuscene"] is not diffuscene
    assert contract["diffuscene"]["notes"] is not diffuscene["notes"]


# ---------------------------------------------------------------------------
# 22 - 26. purity
# ---------------------------------------------------------------------------

def test_contract_module_imports_only_pure_modules():
    assert _imported_modules(contract_module) <= {
        "__future__",
        "copy",
        "math",
        "typing",
    }


def test_contract_module_does_not_touch_the_filesystem():
    imported = _imported_modules(contract_module)

    for name in ("os", "pathlib", "io", "shutil", "tempfile", "glob", "json"):
        assert name not in imported

    source = inspect.getsource(contract_module)
    assert "open(" not in source
    assert "__file__" not in source
    assert "Path(" not in source


def test_contract_performs_no_filesystem_access_at_runtime(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError(
            "the production unit contract must not touch the filesystem"
        )

    monkeypatch.setattr(builtins, "open", _explode)

    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert contract["type"] == "furniture_unit_contract"
    assert contract["compatibility"]["status"] == "supported"


def test_contract_module_does_not_import_the_transform_stage():
    imported = _imported_modules(contract_module)

    for name in (
        "raw_obj_loader",
        "mesh_transform_spec",
        "mesh_transform_executor",
        "mesh_alignment_resolver",
        "asset_forward_resolver",
        "asset_scene_instance",
        "asset_scene_instance_collection",
        "furniture_adapter",
        "placement_identity",
    ):
        assert name not in imported


def test_contract_module_does_not_call_the_transform_stage():
    source = inspect.getsource(contract_module)

    for call in (
        "FurnitureAdapter(",
        "build_mesh_transform_spec(",
        "execute_mesh_transform(",
        "load_raw_obj(",
        "build_asset_scene_instance(",
        "build_placement_identity(",
    ):
        assert call not in source


def test_contract_module_does_not_load_or_process_geometry():
    code = _code_source(contract_module)

    for token in ("vertices_xyz", "min_xyz", "max_xyz", "trimesh", "face_count"):
        assert token not in code


def test_contract_module_has_no_transform_or_bim_machinery():
    code = _code_source(contract_module)

    for token in (
        "math.cos",
        "math.sin",
        "math.tan",
        "math.radians",
        "math.degrees",
        "matrix",
        "trimesh",
    ):
        assert token not in code

    for name in (
        "BASIS",
        "BASIS_B",
        "UP_ALIGNMENT_MATRIX",
        "R_UP",
        "PHI_BY_RAW_FORWARD",
        "IDENTITY_MATRIX",
    ):
        assert not hasattr(contract_module, name)

    imported = _imported_modules(contract_module)
    for name in (
        "bim",
        "scene_builder",
        "scene_exporter",
        "runtime",
        "pipeline",
        "renderer",
        "collision",
        "clearance",
    ):
        assert name not in imported


def test_contract_output_has_no_scene_or_bim_wiring():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    for key in (
        "scene",
        "scene_result",
        "bim",
        "renderer",
        "export",
        "export_result",
        "runtime",
        "pipeline",
    ):
        assert key not in contract


# ---------------------------------------------------------------------------
# 27 - 30. semantics flags / no automatic conversion
# ---------------------------------------------------------------------------

def test_semantics_block_is_exact():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert contract["semantics"] == {
        "metadata_only": True,
        "geometry_modified": False,
        "unit_conversion_applied": False,
        "non_identity_scale_authorized": False,
    }


def test_contract_is_metadata_only():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert contract["semantics"]["metadata_only"] is True
    assert contract["semantics"]["geometry_modified"] is False


def test_no_automatic_centimeter_conversion_constant_exists():
    """No cm->m (or any) conversion constant may exist in executable code."""

    code = _code_source(contract_module)

    for token in ("/ 100", "* 100", "100.0", "0.01", "0.001", "/ 1000", "* 1000"):
        assert token not in code

    # The only dimension thresholds are the documented diagnostic heuristics.
    assert contract_module.PLAUSIBLE_MAX_DIMENSION_M == 5.0
    assert contract_module.SEVERE_MAX_DIMENSION_M == 50.0


def test_contract_has_the_expected_top_level_shape():
    contract = _build(dimensions=[0.51, 0.86, 0.51])

    assert sorted(contract.keys()) == [
        "asset_dimension_check",
        "compatibility",
        "diffuscene",
        "raw_asset",
        "semantics",
        "status",
        "type",
        "version",
    ]


def test_status_block_is_consistent_with_compatibility():
    for diffuscene_status, raw_status in (
        ("proven", "proven"),
        ("supported", "supported"),
        ("unresolved", "supported"),
    ):
        contract = _build(
            diffuscene=_evidence(status=diffuscene_status),
            raw_asset=_raw_evidence(status=raw_status),
        )

        assert contract["status"]["state"] == (
            "unit_contract_" + contract["compatibility"]["status"]
        )
        assert contract["status"]["reasons"] == (
            contract["compatibility"]["reasons"]
        )


def test_api_is_keyword_only():
    signature = inspect.signature(build_furniture_unit_contract)

    assert list(signature.parameters) == [
        "diffuscene_unit_evidence",
        "raw_asset_unit_evidence",
        "asset_dimensions_xyz",
    ]
    for name, parameter in signature.parameters.items():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["asset_dimensions_xyz"].default is None


# ---------------------------------------------------------------------------
# guarded real-registry tests (the TEST reads the registry; production does not)
# ---------------------------------------------------------------------------

def _registry_assets():
    if not REGISTRY_PATH.is_file():
        pytest.skip(f"3D-FUTURE asset registry absent at {REGISTRY_PATH}")

    with REGISTRY_PATH.open("r", encoding="utf-8") as registry_file:
        return json.load(registry_file)["assets"]


def _first(assets, predicate):
    for asset in assets:
        dimensions = asset.get("full_dims_xyz")
        if (
            isinstance(dimensions, list)
            and len(dimensions) == 3
            and all(isinstance(value, (int, float)) for value in dimensions)
            and predicate(dimensions)
        ):
            return asset

    return None


def test_real_registry_normal_asset_is_plausible():
    assets = _registry_assets()
    normal = _first(
        assets,
        lambda dims: max(dims) <= 3.0 and min(dims) > 0.05,
    )
    if normal is None:
        pytest.skip("no normally-scaled real asset found in the local registry")

    contract = _build(dimensions=normal["full_dims_xyz"])

    assert contract["asset_dimension_check"]["status"] == "plausible"
    assert contract["asset_dimension_check"]["max_dimension"] == pytest.approx(
        max(normal["full_dims_xyz"])
    )
    assert contract["compatibility"]["status"] == "supported"
    assert contract["compatibility"]["geometry_scaling_authorized"] is False
    assert contract["compatibility"]["scale_xyz"] == [1.0, 1.0, 1.0]


def test_real_registry_suspicious_asset_is_suspicious():
    assets = _registry_assets()
    oversize = _first(assets, lambda dims: max(dims) > 5.0)
    if oversize is None:
        pytest.skip(
            "no asset with a maximum dimension above 5 m exists in the local "
            "registry, so the oversize diagnostic cannot be exercised"
        )

    dimensions = oversize["full_dims_xyz"]
    contract = _build(dimensions=dimensions)

    assert contract["asset_dimension_check"]["status"] == "suspicious"
    assert contract["asset_dimension_check"]["severe_oversize"] is (
        max(dimensions) > 50.0
    )
    # Verbatim: never rescaled, never converted.
    assert contract["asset_dimension_check"]["max_dimension"] == pytest.approx(
        max(dimensions)
    )
    assert contract["compatibility"]["status"] == "unresolved"
    assert contract["compatibility"]["scale_xyz"] == [1.0, 1.0, 1.0]
    assert contract["semantics"]["unit_conversion_applied"] is False
