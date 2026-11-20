"""Focused tests for the room volume contract and support-surface resolution (Phase 3D-AO)."""

import ast
import builtins
import copy
import inspect
import io
import tokenize
from pathlib import Path

import pytest

import core.asset.room_support_surface as room_module
from core.asset.room_support_surface import (
    build_room_volume,
    resolve_room_support_surface,
)

# Downstream / upstream producers are imported by the TEST only.
from core.asset.furniture_support_policy import (
    resolve_furniture_support_policy,
)
from core.asset.furniture_unit_contract import build_furniture_unit_contract
from core.asset.furniture_contact_state import resolve_furniture_contact_state


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _volume(**overrides):
    kwargs = {"space_id": "R-101"}
    kwargs.update(overrides)

    return build_room_volume(**kwargs)


def _level_contract(status="resolved", exact_levels=None, contract=None):
    result = {
        "contract": "ProjectLevelContractV1" if contract is None else contract,
        "status": status,
        "exact_levels": (
            {"F1": 3.2, "ground": 0.0}
            if exact_levels is None
            else exact_levels
        ),
    }

    return result


def _real_level_contract():
    from core.architecture.reasoning.project_level_contract_v1 import (
        ProjectLevelContractV1,
    )

    return ProjectLevelContractV1().resolve(
        level_contract={
            "levels": {
                "ground": {
                    "value": 0.0,
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                },
                "F1": {
                    "value": 3.2,
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                },
            }
        }
    )


def _conflicted_real_level_contract():
    from core.architecture.reasoning.project_level_contract_v1 import (
        ProjectLevelContractV1,
    )

    return ProjectLevelContractV1().resolve(
        level_contract={
            "levels": {
                "ground": {
                    "value": 0.0,
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                }
            }
        },
        confirmations=[
            {
                "kind": "level_elevation",
                "level": "ground",
                "value": 0.5,
                "authority_class": "HARD_REGULATION",
                "provenance": ["regulation_v1"],
            }
        ],
    )


def _unit_contract():
    return build_furniture_unit_contract(
        diffuscene_unit_evidence={
            "numeric_unit": "meters",
            "status": "supported",
            "source": "diffuscene_dataset_stats_and_processed_data",
        },
        raw_asset_unit_evidence={
            "numeric_unit": "meters",
            "status": "supported",
            "source": "3d_future_registry_raw_obj_measurement",
        },
        asset_dimensions_xyz=[0.51, 0.86, 0.51],
    )


def _bounds(bottom_z, top_z):
    return {"min_xyz": [0.0, 0.0, bottom_z], "max_xyz": [1.0, 1.0, top_z]}


def _imported_modules(module):
    """Top-level module names imported by ``module`` (parsed from the AST)."""

    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])

    return names


def _code_source(module):
    """Module source with comments and string literals removed."""

    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


# ---------------------------------------------------------------------------
# 1 - 8. room volume vertical extent
# ---------------------------------------------------------------------------

def test_explicit_floor_and_ceiling_resolve_both_planes():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    assert volume["type"] == "room_volume"
    assert volume["version"] == "room_volume_v1"
    assert volume["space_id"] == "R-101"
    assert volume["vertical_extent"]["floor"]["z"] == 0.0
    assert volume["vertical_extent"]["ceiling"]["z"] == 2.7
    assert volume["vertical_extent"]["floor"]["source"] == (
        "explicit_caller_elevation"
    )
    assert volume["vertical_extent"]["clear_height"] == pytest.approx(2.7)
    assert volume["vertical_extent"]["status"] == "resolved"
    assert volume["status"]["state"] == "room_volume_resolved"


def test_floor_plus_clear_height_derives_the_ceiling():
    volume = _volume(floor_elevation=3.2, clear_height=2.8)

    assert volume["vertical_extent"]["floor"]["z"] == 3.2
    assert volume["vertical_extent"]["ceiling"]["z"] == pytest.approx(6.0)
    assert volume["vertical_extent"]["ceiling"]["source"] == (
        "derived_from_floor_and_clear_height"
    )
    assert volume["vertical_extent"]["status"] == "resolved"


def test_floor_only_leaves_the_room_partial():
    volume = _volume(floor_elevation=0.0)

    assert volume["vertical_extent"]["floor"]["status"] == "resolved"
    assert volume["vertical_extent"]["ceiling"]["status"] == "unresolved"
    assert volume["vertical_extent"]["ceiling"]["z"] is None
    assert volume["vertical_extent"]["status"] == "unresolved"
    assert volume["status"]["state"] == "room_volume_partial"


def test_ceiling_only_leaves_the_room_partial():
    volume = _volume(ceiling_elevation=2.7)

    assert volume["vertical_extent"]["floor"]["status"] == "unresolved"
    assert volume["vertical_extent"]["ceiling"]["status"] == "resolved"
    assert volume["vertical_extent"]["clear_height"] is None
    assert volume["status"]["state"] == "room_volume_partial"


def test_no_vertical_information_is_unresolved():
    volume = _volume()

    assert volume["vertical_extent"]["floor"]["z"] is None
    assert volume["vertical_extent"]["ceiling"]["z"] is None
    assert volume["vertical_extent"]["clear_height"] is None
    assert volume["status"]["state"] == "room_volume_unresolved"
    assert "floor_elevation_not_supplied" in volume["status"]["reasons"]


def test_floor_elevation_from_a_resolved_level_contract():
    volume = _volume(floor="F1", level_contract=_level_contract())

    assert volume["vertical_extent"]["floor"]["z"] == 3.2
    assert volume["vertical_extent"]["floor"]["source"] == (
        "project_level_contract_exact_levels"
    )
    assert volume["vertical_extent"]["level_contract_status"] == "resolved"


def test_floor_name_absent_from_exact_levels_stays_unresolved():
    volume = _volume(floor="F9", level_contract=_level_contract())

    assert volume["vertical_extent"]["floor"]["z"] is None
    assert volume["vertical_extent"]["floor"]["status"] == "unresolved"
    assert "floor_name_absent_from_exact_levels" in (
        volume["vertical_extent"]["floor"]["reasons"]
    )


def test_floor_name_not_supplied_stays_unresolved():
    volume = _volume(level_contract=_level_contract())

    assert volume["vertical_extent"]["floor"]["z"] is None
    assert "floor_name_not_supplied_for_level_lookup" in (
        volume["vertical_extent"]["floor"]["reasons"]
    )


# ---------------------------------------------------------------------------
# 9 - 14. hypothesis gating: a range hypothesis is never an exact plane
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["conflicted", "unresolved"])
def test_non_resolved_level_contract_never_supplies_an_elevation(status):
    volume = _volume(
        floor="F1",
        level_contract=_level_contract(status=status, exact_levels={}),
    )

    assert volume["vertical_extent"]["floor"]["z"] is None
    assert volume["vertical_extent"]["floor"]["status"] == "unresolved"
    assert (
        f"level_contract_status_{status}_not_authoritative_for_elevation"
        in volume["vertical_extent"]["floor"]["reasons"]
    )
    assert volume["vertical_extent"]["level_contract_status"] == status


def test_conflicted_exact_levels_are_discarded_by_the_level_contract():
    contract = _level_contract(status="conflicted", exact_levels={})
    volume = _volume(floor="ground", level_contract=contract)

    assert contract["status"] == "conflicted"
    assert volume["vertical_extent"]["floor"]["z"] is None


def test_real_level_contract_hypothesis_is_refused():
    """A conflicted real ProjectLevelContractV1 must not yield a support plane."""

    contract = _conflicted_real_level_contract()
    assert contract["status"] == "conflicted"

    volume = _volume(floor="ground", level_contract=contract)

    assert volume["vertical_extent"]["floor"]["z"] is None
    assert volume["status"]["state"] == "room_volume_unresolved"


def test_real_level_contract_exact_levels_are_used():
    contract = _real_level_contract()
    assert contract["status"] == "resolved"

    volume = _volume(floor="F1", level_contract=contract)

    assert volume["vertical_extent"]["floor"]["z"] == pytest.approx(3.2)
    assert volume["vertical_extent"]["floor"]["source"] == (
        "project_level_contract_exact_levels"
    )


def test_explicit_elevation_overrides_the_level_contract():
    volume = _volume(
        floor="F1", floor_elevation=99.0, level_contract=_level_contract()
    )

    assert volume["vertical_extent"]["floor"]["z"] == 99.0
    assert volume["vertical_extent"]["floor"]["source"] == (
        "explicit_caller_elevation"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"contract": "SomethingElse", "status": "resolved", "exact_levels": {}},
        {"status": "maybe", "exact_levels": {}},
        {"status": "resolved"},
        {"status": "resolved", "exact_levels": []},
        {"status": "resolved", "exact_levels": {"F1": "x"}},
        "not-a-mapping",
    ],
    ids=["wrong-name", "bad-status", "no-levels", "list-levels", "bad-value", "str"],
)
def test_malformed_level_contract_is_rejected(bad):
    with pytest.raises(ValueError):
        _volume(floor="F1", level_contract=bad)


# ---------------------------------------------------------------------------
# 15 - 20. vertical cross-checks
# ---------------------------------------------------------------------------

def test_ceiling_below_floor_is_rejected():
    with pytest.raises(ValueError, match="ceiling_elevation must be >="):
        _volume(floor_elevation=3.0, ceiling_elevation=1.0)


def test_consistent_floor_ceiling_and_clear_height_is_accepted():
    volume = _volume(
        floor_elevation=0.0, ceiling_elevation=2.7, clear_height=2.7
    )

    assert volume["vertical_extent"]["clear_height"] == pytest.approx(2.7)


def test_inconsistent_clear_height_is_rejected():
    with pytest.raises(ValueError, match="clear_height must equal"):
        _volume(floor_elevation=0.0, ceiling_elevation=2.7, clear_height=2.5)


@pytest.mark.parametrize(
    "bad", [0.0, -1.0], ids=["zero", "negative"]
)
def test_non_positive_clear_height_is_rejected(bad):
    with pytest.raises(ValueError, match="clear_height must be strictly positive"):
        _volume(floor_elevation=0.0, clear_height=bad)


@pytest.mark.parametrize(
    "bad",
    ["x", [], {}, float("nan"), float("inf"), float("-inf"), True],
    ids=["str", "list", "dict", "nan", "inf", "-inf", "bool"],
)
def test_malformed_elevations_are_rejected(bad):
    with pytest.raises(ValueError, match="floor_elevation"):
        _volume(floor_elevation=bad)


def test_bool_clear_height_is_rejected():
    with pytest.raises(ValueError, match="clear_height"):
        _volume(floor_elevation=0.0, clear_height=True)


@pytest.mark.parametrize("bad", ["", "   ", None, 3, True, [], {}])
def test_malformed_space_id_is_rejected(bad):
    with pytest.raises(ValueError, match="space_id must be a non-empty string"):
        build_room_volume(space_id=bad)


def test_space_id_is_required():
    with pytest.raises(TypeError):
        build_room_volume()


@pytest.mark.parametrize("bad", ["", "   ", 3, True, [], {}])
def test_malformed_floor_label_is_rejected(bad):
    with pytest.raises(ValueError, match="floor must be a non-empty string"):
        _volume(floor=bad)


# ---------------------------------------------------------------------------
# 21 - 25. footprint
# ---------------------------------------------------------------------------

def test_polygon_is_preserved_verbatim():
    polygon = [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]]

    volume = _volume(polygon=polygon)

    assert volume["footprint"]["status"] == "resolved"
    assert volume["footprint"]["polygon"] == polygon
    assert volume["footprint"]["polygon"] is not polygon


def test_polygon_is_not_measured_or_modified():
    polygon = [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0]]
    before = copy.deepcopy(polygon)

    volume = _volume(polygon=polygon)

    assert polygon == before
    # No derived area or cubic volume is claimed in this phase.
    assert "area_m2" not in volume["footprint"]
    assert "volume_m3" not in volume


def test_absent_polygon_leaves_the_footprint_unresolved():
    volume = _volume()

    assert volume["footprint"]["status"] == "unresolved"
    assert volume["footprint"]["polygon"] is None


@pytest.mark.parametrize(
    "bad",
    [
        "x",
        [[0.0, 0.0], [1.0, 1.0]],
        [[0.0, 0.0], [1.0, 1.0], [2.0]],
        [[0.0, 0.0], [1.0, 1.0], ["x", 0.0]],
        [[0.0, 0.0], [1.0, 1.0], [float("nan"), 0.0]],
        [[0.0, 0.0], [1.0, 1.0], [True, 0.0]],
    ],
    ids=["str", "two-points", "short-point", "str-coord", "nan", "bool"],
)
def test_malformed_polygon_is_rejected(bad):
    with pytest.raises(ValueError, match="polygon"):
        _volume(polygon=bad)


# ---------------------------------------------------------------------------
# 26 - 34. support surface resolution
# ---------------------------------------------------------------------------

def test_floor_target_returns_the_floor_plane():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    surface = resolve_room_support_surface(volume, contact_target="floor")

    assert surface["type"] == "room_support_surface"
    assert surface["contact_target"] == "floor"
    assert surface["plane"]["expected_z"] == 0.0
    assert surface["plane"]["axis"] == "z"
    assert surface["plane"]["up_axis_index"] == 2
    assert surface["plane"]["status"] == "resolved"
    assert surface["status"]["state"] == "support_surface_resolved"


def test_ceiling_target_returns_the_ceiling_plane():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    surface = resolve_room_support_surface(volume, contact_target="ceiling")

    assert surface["plane"]["expected_z"] == 2.7
    assert surface["status"]["state"] == "support_surface_resolved"


def test_unresolved_plane_yields_no_elevation():
    volume = _volume(floor_elevation=0.0)

    surface = resolve_room_support_surface(volume, contact_target="ceiling")

    assert surface["plane"]["expected_z"] is None
    assert surface["plane"]["status"] == "unresolved"
    assert surface["status"]["state"] == "support_surface_unresolved"


def test_space_identity_is_echoed():
    volume = _volume(floor="F1", floor_elevation=3.2)

    surface = resolve_room_support_surface(volume, contact_target="floor")

    assert surface["space_id"] == "R-101"
    assert surface["floor"] == "F1"


@pytest.mark.parametrize(
    "bad",
    ["wall", "free", None, True, "", 3, [], {}],
    ids=["wall", "free", "none", "bool", "empty", "int", "list", "dict"],
)
def test_out_of_scope_contact_targets_are_rejected(bad):
    volume = _volume(floor_elevation=0.0)

    with pytest.raises(ValueError, match="contact_target must be one of"):
        resolve_room_support_surface(volume, contact_target=bad)


def test_contact_target_is_required():
    volume = _volume(floor_elevation=0.0)

    with pytest.raises(TypeError):
        resolve_room_support_surface(volume)


@pytest.mark.parametrize("bad", [None, "x", 3, [], object()])
def test_non_mapping_room_volume_is_rejected(bad):
    with pytest.raises(ValueError, match="room_volume must be a mapping"):
        resolve_room_support_surface(bad, contact_target="floor")


def test_wrong_room_volume_type_is_rejected():
    volume = _volume(floor_elevation=0.0)
    volume["type"] = "something_else"

    with pytest.raises(ValueError, match="room_volume.type must be"):
        resolve_room_support_surface(volume, contact_target="floor")


def test_resolved_plane_without_an_elevation_is_rejected():
    volume = _volume(floor_elevation=0.0)
    volume["vertical_extent"]["floor"] = {
        "status": "resolved",
        "z": None,
        "source": "explicit_caller_elevation",
        "reasons": [],
    }

    with pytest.raises(ValueError, match="requires an elevation"):
        resolve_room_support_surface(volume, contact_target="floor")


def test_invalid_plane_status_is_rejected():
    volume = _volume(floor_elevation=0.0)
    volume["vertical_extent"]["floor"]["status"] = "maybe"

    with pytest.raises(ValueError, match="status must be"):
        resolve_room_support_surface(volume, contact_target="floor")


def test_missing_vertical_extent_is_rejected():
    volume = _volume(floor_elevation=0.0)
    del volume["vertical_extent"]

    with pytest.raises(ValueError, match="vertical_extent must be a mapping"):
        resolve_room_support_surface(volume, contact_target="floor")


# ---------------------------------------------------------------------------
# 35 - 43. semantics, determinism, purity
# ---------------------------------------------------------------------------

def test_semantics_block_is_exact_for_both_outputs():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)
    surface = resolve_room_support_surface(volume, contact_target="floor")

    expected = {
        "metadata_only": True,
        "geometry_modified": False,
        "placement_modified": False,
        "snap_applied": False,
        "geometry_adjustment_authorized": False,
        "containment_validated": False,
    }
    assert volume["semantics"] == expected
    assert surface["semantics"] == expected


def test_room_volume_has_the_expected_shape():
    assert sorted(_volume(floor_elevation=0.0).keys()) == [
        "floor",
        "footprint",
        "semantics",
        "space_id",
        "status",
        "type",
        "version",
        "vertical_extent",
    ]


def test_support_surface_has_the_expected_shape():
    volume = _volume(floor_elevation=0.0)
    surface = resolve_room_support_surface(volume, contact_target="floor")

    assert sorted(surface.keys()) == [
        "contact_target",
        "floor",
        "plane",
        "semantics",
        "space_id",
        "status",
        "type",
        "version",
    ]


def test_repeated_resolution_is_deterministic():
    first = _volume(floor_elevation=0.0, ceiling_elevation=2.7)
    second = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    assert first == second
    assert first is not second

    surface_first = resolve_room_support_surface(first, contact_target="floor")
    surface_second = resolve_room_support_surface(second, contact_target="floor")
    assert surface_first == surface_second


def test_caller_inputs_are_not_mutated():
    polygon = [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0]]
    level_contract = _level_contract()
    before = copy.deepcopy((polygon, level_contract))

    build_room_volume(
        space_id="R-101",
        floor="F1",
        polygon=polygon,
        level_contract=level_contract,
    )

    assert (polygon, level_contract) == before


def test_mutating_a_result_does_not_corrupt_later_results():
    first = _volume(floor_elevation=0.0)
    first["vertical_extent"]["floor"]["z"] = 99.0
    first["semantics"]["snap_applied"] = True

    second = _volume(floor_elevation=0.0)

    assert second["vertical_extent"]["floor"]["z"] == 0.0
    assert second["semantics"]["snap_applied"] is False


def test_room_module_imports_only_pure_modules():
    assert _imported_modules(room_module) <= {"__future__", "math", "typing"}


def test_room_module_does_not_import_the_contract_set_or_runtime():
    imported = _imported_modules(room_module)

    for name in (
        "furniture_adapter",
        "placement_identity",
        "asset_scene_instance",
        "asset_scene_instance_collection",
        "furniture_unit_contract",
        "furniture_support_policy",
        "furniture_contact_state",
        "mesh_transform_spec",
        "mesh_transform_executor",
        "mesh_alignment_resolver",
        "raw_obj_loader",
        "asset_forward_resolver",
        "bim",
        "scene_builder",
        "scene_exporter",
        "runtime",
        "pipeline",
    ):
        assert name not in imported


def test_room_module_does_not_call_the_contract_set():
    code = _code_source(room_module)

    for call in (
        "FurnitureAdapter(",
        "build_placement_identity(",
        "build_furniture_unit_contract(",
        "resolve_furniture_support_policy(",
        "resolve_furniture_contact_state(",
        "build_mesh_transform_spec(",
        "execute_mesh_transform(",
        "load_raw_obj(",
    ):
        assert call not in code


def test_room_module_touches_no_filesystem():
    imported = _imported_modules(room_module)

    for name in ("os", "pathlib", "io", "json", "shutil", "tempfile"):
        assert name not in imported

    source = inspect.getsource(room_module)
    assert "open(" not in source
    assert "__file__" not in source
    assert "asset_registry" not in source


def test_room_module_does_not_mutate_geometry():
    code = _code_source(room_module)

    for token in ("vertices_xyz", "trimesh", "matrix", "math.cos", "math.sin"):
        assert token not in code

    for name in ("BASIS", "UP_ALIGNMENT_MATRIX", "R_UP", "IDENTITY_SCALE"):
        assert not hasattr(room_module, name)


def test_room_output_has_no_runtime_pipeline_wiring():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)
    surface = resolve_room_support_surface(volume, contact_target="floor")

    for key in (
        "scene",
        "scene_result",
        "bim",
        "renderer",
        "export",
        "export_result",
        "runtime",
        "pipeline",
        "collision",
    ):
        assert key not in volume
        assert key not in surface


def test_room_module_does_not_name_the_3dan_contact_module():
    """The Phase 3D-AN contract ships a substring wiring guard over production
    sources, so this module must not even mention its module name."""

    source = inspect.getsource(room_module)

    assert "furniture_contact_state" not in source


def test_room_module_is_not_referenced_by_any_production_module():
    """This phase adds no wiring: only the tests may reference the new module."""

    root = Path(__file__).resolve().parents[1]
    offenders = []

    for path in list((root / "core").rglob("*.py")) + list(
        (root / "scripts").rglob("*.py")
    ):
        if path.name == "room_support_surface.py":
            continue
        if "room_support_surface" in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []


def test_api_is_keyword_only():
    signature = inspect.signature(build_room_volume)
    assert list(signature.parameters) == [
        "space_id",
        "floor",
        "polygon",
        "floor_elevation",
        "ceiling_elevation",
        "clear_height",
        "level_contract",
    ]
    for parameter in signature.parameters.values():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    surface_signature = inspect.signature(resolve_room_support_surface)
    assert surface_signature.parameters["contact_target"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )


# ---------------------------------------------------------------------------
# 44 - 47. integration with Phase 3D-AN contact resolution
# ---------------------------------------------------------------------------

def _contact_state(volume, bounds, category="chair", target="floor"):
    surface = resolve_room_support_surface(volume, contact_target=target)

    return resolve_furniture_contact_state(
        unit_contract=_unit_contract(),
        support_policy=resolve_furniture_support_policy(category=category),
        bounds=bounds,
        support_plane_z=surface["plane"]["expected_z"],
    )


def test_floor_surface_closes_the_3dan_loop_when_the_asset_rests():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    contract = _contact_state(volume, _bounds(0.0, 0.86))

    assert contract["support"]["target"] == "floor"
    assert contract["contact_plane"]["expected_z"] == 0.0
    assert contract["contact"]["status"] == "resolved"


def test_floor_surface_reports_a_mismatch_when_the_asset_floats():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.7)

    contract = _contact_state(volume, _bounds(1.568, 2.432))

    assert contract["contact"]["status"] == "mismatch"
    assert contract["contact"]["offset"] == pytest.approx(1.568)
    assert contract["semantics"]["geometry_adjustment_authorized"] is False


def test_raised_floor_elevation_is_honoured():
    volume = _volume(floor_elevation=3.2, ceiling_elevation=5.9)

    contract = _contact_state(volume, _bounds(3.2, 4.06))

    assert contract["contact_plane"]["expected_z"] == 3.2
    assert contract["contact"]["status"] == "resolved"


def test_ceiling_surface_closes_the_3dan_loop():
    volume = _volume(floor_elevation=0.0, ceiling_elevation=2.6)

    contract = _contact_state(
        volume, _bounds(2.4, 2.6), category="pendant_lamp", target="ceiling"
    )

    assert contract["support"]["target"] == "ceiling"
    assert contract["contact"]["status"] == "resolved"


def test_unresolved_surface_leaves_3dan_unresolved():
    volume = _volume()

    contract = _contact_state(volume, _bounds(0.0, 0.86))

    assert contract["contact_plane"]["status"] == "unresolved"
    assert contract["contact"]["status"] == "unresolved"
    assert "expected_contact_plane_unresolved" in contract["contact"]["reasons"]


def test_hypothesis_level_contract_keeps_the_whole_chain_unresolved():
    """A conflicted level contract must not silently become a support plane."""

    volume = _volume(floor="ground", level_contract=_conflicted_real_level_contract())

    contract = _contact_state(volume, _bounds(0.0, 0.86))

    assert contract["contact"]["status"] == "unresolved"
    assert contract["contact"]["offset"] is None


# ---------------------------------------------------------------------------
# 48. real architecture level contract, end to end
# ---------------------------------------------------------------------------

def test_real_project_level_contract_feeds_the_contact_chain():
    contract = _real_level_contract()
    assert contract["status"] == "resolved"
    assert contract["exact_levels"]["F1"] == pytest.approx(3.2)

    volume = build_room_volume(
        space_id="R-101",
        floor="F1",
        polygon=[[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]],
        clear_height=2.7,
        level_contract=contract,
    )

    assert volume["vertical_extent"]["floor"]["z"] == pytest.approx(3.2)
    assert volume["vertical_extent"]["ceiling"]["z"] == pytest.approx(5.9)
    assert volume["footprint"]["polygon"] == [
        [0.0, 0.0],
        [4.0, 0.0],
        [4.0, 3.0],
        [0.0, 3.0],
    ]
    assert volume["status"]["state"] == "room_volume_resolved"

    surface = resolve_room_support_surface(volume, contact_target="floor")
    assert surface["plane"]["expected_z"] == pytest.approx(3.2)
    assert surface["plane"]["source"] == "project_level_contract_exact_levels"

    contact = resolve_furniture_contact_state(
        unit_contract=_unit_contract(),
        support_policy=resolve_furniture_support_policy(category="chair"),
        bounds=_bounds(3.2, 4.06),
        support_plane_z=surface["plane"]["expected_z"],
    )

    assert contact["contact"]["status"] == "resolved"
    assert contact["contact"]["offset"] == pytest.approx(0.0)
    assert contact["semantics"]["snap_applied"] is False
    assert contact["semantics"]["geometry_adjustment_authorized"] is False


def test_room_volume_contract_never_uses_a_hypothesis_range():
    """The level-height module emits ranges labelled as hypotheses; this contract
    only accepts a resolved exact level, so such a range can never become a
    plane."""

    hypothesis = {
        "contract": "ProjectLevelContractV1",
        "status": "unresolved",
        "exact_levels": {},
    }

    volume = _volume(floor="F1", level_contract=hypothesis)

    assert volume["vertical_extent"]["floor"]["z"] is None
    surface = resolve_room_support_surface(volume, contact_target="floor")
    assert surface["plane"]["expected_z"] is None
