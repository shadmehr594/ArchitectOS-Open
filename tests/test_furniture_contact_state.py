"""Focused tests for semantic floor / ceiling contact resolution (Phase 3D-AN)."""

import ast
import builtins
import copy
import inspect
import io
import json
import tokenize
from pathlib import Path

import pytest

import core.asset.furniture_contact_state as contact_module
from core.asset.furniture_contact_state import (
    resolve_furniture_contact_state,
)

# Upstream producers are imported by the TEST only. The production module must
# never import them.
from core.asset.furniture_support_policy import (
    resolve_furniture_support_policy,
)
from core.asset.furniture_unit_contract import build_furniture_unit_contract


REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "3d_future"
    / "asset_registry.json"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _unit_contract(compatibility="supported"):
    return {
        "type": "furniture_unit_contract",
        "version": "furniture_unit_contract_v1",
        "diffuscene": {
            "numeric_unit": "meters",
            "status": "supported",
            "proven": False,
            "source": "test",
            "notes": [],
        },
        "raw_asset": {
            "numeric_unit": "meters",
            "status": "supported",
            "proven": False,
            "source": "test",
            "notes": [],
        },
        "compatibility": {
            "status": compatibility,
            "same_nominal_unit": True,
            "geometry_scaling_authorized": False,
            "scale_xyz": [1.0, 1.0, 1.0],
            "reasons": ["compatibility_confidence_bounded_by_evidence_confidence"],
        },
        "asset_dimension_check": {
            "status": "plausible",
            "max_dimension": 1.0,
            "min_dimension": 0.5,
            "severe_oversize": False,
            "thresholds": {},
            "reasons": [],
        },
        "semantics": {
            "metadata_only": True,
            "geometry_modified": False,
            "unit_conversion_applied": False,
            "non_identity_scale_authorized": False,
        },
        "status": {"state": "unit_contract_supported", "reasons": []},
    }


def _support_policy(mode="floor", status="resolved"):
    return {
        "type": "furniture_support_policy",
        "version": "furniture_support_policy_v1",
        "category": "chair" if mode == "floor" else "pendant_lamp",
        "support": {
            "status": status,
            "mode": mode if status == "resolved" else None,
            "rule_id": "floor_support_measured" if status == "resolved" else None,
            "source": "test" if status == "resolved" else None,
            "reasons": [],
        },
        "physical_validation": {
            "required": status == "resolved",
            "contact_target": mode if status == "resolved" else None,
            "contact_check_status": "pending" if status == "resolved" else "unresolved",
            "geometry_adjustment_authorized": False,
        },
        "semantics": {
            "metadata_only": True,
            "geometry_modified": False,
            "floor_snap_applied": False,
            "ceiling_snap_applied": False,
            "wall_snap_applied": False,
            "collision_validated": False,
            "containment_validated": False,
        },
        "status": {"state": "support_policy_resolved", "reasons": []},
    }


def _bounds(bottom_z, top_z, x=(0.0, 1.0), y=(0.0, 1.0)):
    return {
        "min_xyz": [x[0], y[0], bottom_z],
        "max_xyz": [x[1], y[1], top_z],
    }


def _resolve(
    support_policy=None,
    unit_contract=None,
    bounds=None,
    support_plane_z=None,
    tolerance=None,
):
    return resolve_furniture_contact_state(
        unit_contract=(
            _unit_contract() if unit_contract is None else unit_contract
        ),
        support_policy=(
            _support_policy() if support_policy is None else support_policy
        ),
        bounds=bounds,
        support_plane_z=support_plane_z,
        tolerance=tolerance,
    )


def _imported_modules(module):
    """Top-level module names imported by ``module``.

    Parsed from the AST, not from raw lines: a wrapped docstring line that
    happens to begin with "from " must never be mistaken for an import.
    """

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
# 1 - 3. floor contact state
# ---------------------------------------------------------------------------

def test_floor_supported_asset_resting_on_floor_is_resolved():
    contract = _resolve(
        bounds=_bounds(0.0, 0.9), support_plane_z=0.0
    )

    assert contract["type"] == "furniture_contact_state"
    assert contract["version"] == "furniture_contact_state_v1"
    assert contract["support"]["target"] == "floor"
    assert contract["support"]["status"] == "resolved"
    assert contract["contact_plane"]["expected_z"] == 0.0
    assert contract["contact_plane"]["status"] == "resolved"
    assert contract["contact"]["status"] == "resolved"
    assert contract["contact"]["within_tolerance"] is True
    assert contract["contact"]["offset"] == pytest.approx(0.0)
    assert contract["status"]["state"] == "contact_resolved"


def test_floor_contact_coordinate_is_the_asset_bottom():
    contract = _resolve(bounds=_bounds(0.25, 1.4), support_plane_z=0.0)

    assert contract["contact"]["asset_bottom_z"] == pytest.approx(0.25)
    assert contract["contact"]["asset_top_z"] == pytest.approx(1.4)
    assert contract["contact"]["contact_coordinate_z"] == pytest.approx(0.25)
    # Bottom is above the floor, so the asset floats.
    assert contract["contact"]["offset"] == pytest.approx(0.25)


def test_floor_supported_asset_floating_above_floor_is_mismatch():
    contract = _resolve(bounds=_bounds(0.4, 1.3), support_plane_z=0.0)

    assert contract["contact"]["status"] == "mismatch"
    assert contract["contact"]["within_tolerance"] is False
    assert contract["contact"]["offset"] == pytest.approx(0.4)
    assert contract["status"]["state"] == "contact_mismatch"
    assert "contact_coordinate_outside_tolerance" in contract["contact"]["reasons"]


def test_floor_supported_asset_sunk_below_floor_is_mismatch():
    contract = _resolve(bounds=_bounds(-0.2, 0.7), support_plane_z=0.0)

    assert contract["contact"]["status"] == "mismatch"
    assert contract["contact"]["offset"] == pytest.approx(-0.2)


def test_floor_plane_may_be_negative_or_raised():
    raised = _resolve(bounds=_bounds(0.35, 1.25), support_plane_z=0.35)
    assert raised["contact"]["status"] == "resolved"
    assert raised["contact_plane"]["expected_z"] == pytest.approx(0.35)

    sunk = _resolve(bounds=_bounds(-1.5, -0.6), support_plane_z=-1.5)
    assert sunk["contact"]["status"] == "resolved"


# ---------------------------------------------------------------------------
# 2. ceiling contact state
# ---------------------------------------------------------------------------

def test_ceiling_supported_asset_touching_ceiling_is_resolved():
    contract = _resolve(
        support_policy=_support_policy(mode="ceiling"),
        bounds=_bounds(2.2, 2.6),
        support_plane_z=2.6,
    )

    assert contract["support"]["target"] == "ceiling"
    assert contract["support"]["status"] == "resolved"
    assert contract["contact"]["status"] == "resolved"
    assert contract["contact"]["offset"] == pytest.approx(0.0)


def test_ceiling_contact_coordinate_is_the_asset_top():
    contract = _resolve(
        support_policy=_support_policy(mode="ceiling"),
        bounds=_bounds(2.2, 2.6),
        support_plane_z=2.6,
    )

    assert contract["contact"]["contact_coordinate_z"] == pytest.approx(2.6)
    assert contract["contact"]["asset_top_z"] == pytest.approx(2.6)
    assert contract["contact"]["asset_bottom_z"] == pytest.approx(2.2)


def test_ceiling_supported_asset_hanging_below_ceiling_is_mismatch():
    contract = _resolve(
        support_policy=_support_policy(mode="ceiling"),
        bounds=_bounds(1.9, 2.3),
        support_plane_z=2.6,
    )

    assert contract["contact"]["status"] == "mismatch"
    assert contract["contact"]["offset"] == pytest.approx(-0.3)


def test_ceiling_supported_asset_poking_through_ceiling_is_mismatch():
    contract = _resolve(
        support_policy=_support_policy(mode="ceiling"),
        bounds=_bounds(2.3, 2.9),
        support_plane_z=2.6,
    )

    assert contract["contact"]["status"] == "mismatch"
    assert contract["contact"]["offset"] == pytest.approx(0.3)


def test_floor_and_ceiling_use_opposite_contact_coordinates():
    box = _bounds(2.2, 2.6)

    floor_like = _resolve(bounds=box, support_plane_z=2.2)
    ceiling_like = _resolve(
        support_policy=_support_policy(mode="ceiling"),
        bounds=box,
        support_plane_z=2.6,
    )

    assert floor_like["contact"]["contact_coordinate_z"] == pytest.approx(2.2)
    assert ceiling_like["contact"]["contact_coordinate_z"] == pytest.approx(2.6)
    assert floor_like["contact"]["status"] == "resolved"
    assert ceiling_like["contact"]["status"] == "resolved"


# ---------------------------------------------------------------------------
# 3. unresolved categories stay unresolved
# ---------------------------------------------------------------------------

def test_unresolved_support_policy_keeps_contact_unresolved():
    contract = _resolve(
        support_policy=_support_policy(status="unresolved"),
        bounds=_bounds(0.0, 0.9),
        support_plane_z=0.0,
    )

    assert contract["support"]["status"] == "unresolved"
    assert contract["support"]["target"] is None
    assert contract["support"]["mode"] is None
    assert contract["contact_plane"]["status"] == "unresolved"
    assert contract["contact_plane"]["expected_z"] is None
    assert contract["contact"]["status"] == "unresolved"
    assert contract["contact"]["contact_coordinate_z"] is None
    assert contract["contact"]["offset"] is None
    assert contract["contact"]["within_tolerance"] is None
    assert contract["status"]["state"] == "contact_unresolved"


@pytest.mark.parametrize("mode", ["wall", "free"])
def test_out_of_scope_support_targets_stay_unresolved(mode):
    contract = _resolve(
        support_policy=_support_policy(mode=mode),
        bounds=_bounds(0.0, 0.9),
        support_plane_z=0.0,
    )

    assert contract["support"]["mode"] == mode
    assert contract["support"]["target"] is None
    assert contract["contact"]["status"] == "unresolved"
    assert "support_target_out_of_scope_for_contact" in (
        contract["contact"]["reasons"]
    )


def test_unresolved_support_never_claims_a_contact_verdict():
    contract = _resolve(
        support_policy=_support_policy(status="unresolved"),
        bounds=_bounds(0.0, 0.9),
        support_plane_z=0.0,
    )

    assert contract["contact"]["status"] != "resolved"
    assert contract["contact"]["status"] != "mismatch"
    assert contract["semantics"]["snap_applied"] is False
    assert contract["semantics"]["geometry_adjustment_authorized"] is False


# ---------------------------------------------------------------------------
# 4 - 5. unit contract consumption
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("compatibility", ["proven", "supported"])
def test_usable_unit_contract_allows_contact_resolution(compatibility):
    contract = _resolve(
        unit_contract=_unit_contract(compatibility),
        bounds=_bounds(0.0, 0.9),
        support_plane_z=0.0,
    )

    assert contract["unit"]["compatibility_status"] == compatibility
    assert contract["unit"]["usable_for_contact"] is True
    assert contract["contact"]["status"] == "resolved"


def test_unresolved_unit_contract_forces_contact_unresolved():
    contract = _resolve(
        unit_contract=_unit_contract("unresolved"),
        bounds=_bounds(0.4, 1.3),
        support_plane_z=0.0,
    )

    assert contract["unit"]["usable_for_contact"] is False
    assert contract["contact"]["status"] == "unresolved"
    assert "unit_contract_not_usable_for_length_comparison" in (
        contract["contact"]["reasons"]
    )
    # Crucially, it does NOT emit a confident mismatch from untrusted units.
    assert contract["contact"]["offset"] is None


def test_unit_contract_is_not_modified():
    unit_contract = _unit_contract()
    before = copy.deepcopy(unit_contract)

    _resolve(unit_contract=unit_contract, bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

    assert unit_contract == before


def test_support_policy_is_not_modified():
    support_policy = _support_policy()
    before = copy.deepcopy(support_policy)

    _resolve(support_policy=support_policy, bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

    assert support_policy == before


# ---------------------------------------------------------------------------
# 6 - 8. missing / malformed inputs
# ---------------------------------------------------------------------------

def test_missing_bounds_keeps_contact_unresolved():
    contract = _resolve(support_plane_z=0.0)

    assert contract["contact"]["status"] == "unresolved"
    assert contract["contact"]["asset_bottom_z"] is None
    assert contract["contact"]["asset_top_z"] is None
    assert "asset_bounds_not_supplied" in contract["contact"]["reasons"]
    # The support target and plane are still resolved.
    assert contract["support"]["target"] == "floor"
    assert contract["contact_plane"]["expected_z"] == 0.0


def test_missing_support_plane_keeps_contact_unresolved():
    contract = _resolve(bounds=_bounds(0.0, 0.9))

    assert contract["contact_plane"]["status"] == "unresolved"
    assert contract["contact_plane"]["expected_z"] is None
    assert contract["contact"]["status"] == "unresolved"
    assert "support_plane_elevation_not_supplied" in (
        contract["contact_plane"]["reasons"]
    )


@pytest.mark.parametrize(
    "bad",
    ["x", 3, 1.5, [], object()],
    ids=["str", "int", "float", "list", "object"],
)
def test_non_mapping_bounds_are_rejected(bad):
    with pytest.raises(ValueError, match="bounds must be a mapping"):
        _resolve(bounds=bad, support_plane_z=0.0)


@pytest.mark.parametrize(
    "bad",
    [
        {"max_xyz": [1.0, 1.0, 1.0]},
        {"min_xyz": [0.0, 0.0, 0.0]},
        {"min_xyz": [0.0, 0.0], "max_xyz": [1.0, 1.0, 1.0]},
        {"min_xyz": "x", "max_xyz": [1.0, 1.0, 1.0]},
        {"min_xyz": [0.0, 0.0, 0.0], "max_xyz": [1.0, 1.0]},
    ],
    ids=["no-min", "no-max", "short-min", "str-min", "short-max"],
)
def test_malformed_bounds_are_rejected(bad):
    with pytest.raises(ValueError):
        _resolve(bounds=bad, support_plane_z=0.0)


@pytest.mark.parametrize(
    "bad",
    [[float("nan"), 0.0, 0.0], [0.0, float("inf"), 0.0]],
    ids=["nan", "inf"],
)
def test_non_finite_bounds_are_rejected(bad):
    with pytest.raises(ValueError, match="finite"):
        _resolve(bounds={"min_xyz": bad, "max_xyz": [1.0, 1.0, 1.0]})


def test_inverted_bounds_are_rejected():
    with pytest.raises(ValueError, match="max_xyz must be >="):
        _resolve(
            bounds={"min_xyz": [0.0, 0.0, 2.0], "max_xyz": [1.0, 1.0, 1.0]},
            support_plane_z=0.0,
        )


def test_bool_bound_entry_is_rejected():
    with pytest.raises(ValueError, match="real number"):
        _resolve(
            bounds={"min_xyz": [True, 0.0, 0.0], "max_xyz": [1.0, 1.0, 1.0]},
            support_plane_z=0.0,
        )


@pytest.mark.parametrize(
    "bad",
    ["x", [], {}, object(), float("nan"), float("inf")],
    ids=["str", "list", "dict", "object", "nan", "inf"],
)
def test_malformed_support_plane_is_rejected(bad):
    with pytest.raises(ValueError, match="support_plane_z"):
        _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=bad)


def test_bool_support_plane_is_rejected():
    with pytest.raises(ValueError, match="support_plane_z must be a real number"):
        _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=True)


@pytest.mark.parametrize(
    "bad",
    ["x", [], {}, object(), float("nan")],
    ids=["str", "list", "dict", "object", "nan"],
)
def test_malformed_tolerance_is_rejected(bad):
    with pytest.raises(ValueError, match="tolerance"):
        _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0, tolerance=bad)


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValueError, match="tolerance must be non-negative"):
        _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0, tolerance=-0.001)


def test_bool_tolerance_is_rejected():
    with pytest.raises(ValueError, match="tolerance must be a real number"):
        _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0, tolerance=True)


def test_zero_tolerance_is_accepted():
    contract = _resolve(
        bounds=_bounds(0.0, 0.9), support_plane_z=0.0, tolerance=0.0
    )

    assert contract["contact"]["tolerance"] == 0.0
    assert contract["contact"]["status"] == "resolved"


# ---------------------------------------------------------------------------
# 9. tolerance boundaries
# ---------------------------------------------------------------------------

def test_contact_exactly_at_tolerance_is_resolved():
    contract = _resolve(
        bounds=_bounds(0.01, 0.9), support_plane_z=0.0, tolerance=0.01
    )

    assert contract["contact"]["within_tolerance"] is True
    assert contract["contact"]["status"] == "resolved"


def test_contact_just_outside_tolerance_is_mismatch():
    contract = _resolve(
        bounds=_bounds(0.0100001, 0.9), support_plane_z=0.0, tolerance=0.01
    )

    assert contract["contact"]["within_tolerance"] is False
    assert contract["contact"]["status"] == "mismatch"


def test_default_tolerance_is_the_documented_diagnostic_value():
    contract = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

    assert contract["contact"]["tolerance"] == pytest.approx(
        contact_module.DEFAULT_CONTACT_TOLERANCE_M
    )
    assert contact_module.DEFAULT_CONTACT_TOLERANCE_M == 0.005


def test_tolerance_is_symmetric_about_the_plane():
    above = _resolve(
        bounds=_bounds(0.02, 0.9), support_plane_z=0.0, tolerance=0.02
    )
    below = _resolve(
        bounds=_bounds(-0.02, 0.9), support_plane_z=0.0, tolerance=0.02
    )

    assert above["contact"]["status"] == "resolved"
    assert below["contact"]["status"] == "resolved"
    assert above["contact"]["offset"] == pytest.approx(0.02)
    assert below["contact"]["offset"] == pytest.approx(-0.02)


def test_offset_beyond_the_default_tolerance_is_a_mismatch():
    """The default resting tolerance is a few millimetres, so a 20 mm gap is a
    genuine mismatch - the module reports it rather than hiding it."""

    contract = _resolve(bounds=_bounds(0.02, 0.9), support_plane_z=0.0)

    assert contract["contact"]["tolerance"] == pytest.approx(0.005)
    assert contract["contact"]["status"] == "mismatch"


# ---------------------------------------------------------------------------
# 10 - 13. contract shape, axis, semantics
# ---------------------------------------------------------------------------

def test_contract_has_the_expected_top_level_shape():
    assert sorted(_resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0).keys()) == [
        "contact",
        "contact_plane",
        "semantics",
        "status",
        "support",
        "type",
        "unit",
        "version",
    ]


def test_contact_plane_declares_the_canonical_up_axis():
    plane = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)["contact_plane"]

    assert plane["axis"] == "z"
    assert plane["up_axis_index"] == 2


def test_semantics_block_is_exact():
    assert _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)["semantics"] == {
        "metadata_only": True,
        "geometry_modified": False,
        "transform_modified": False,
        "geometry_adjustment_authorized": False,
        "snap_applied": False,
    }


@pytest.mark.parametrize(
    "support_policy,bounds,plane",
    [
        (_support_policy(), _bounds(0.0, 0.9), 0.0),
        (_support_policy(), _bounds(0.4, 1.3), 0.0),
        (_support_policy(mode="ceiling"), _bounds(2.2, 2.6), 2.6),
        (_support_policy(mode="ceiling"), _bounds(1.9, 2.3), 2.6),
        (_support_policy(status="unresolved"), _bounds(0.0, 0.9), 0.0),
        (_support_policy(), None, 0.0),
        (_support_policy(), _bounds(0.0, 0.9), None),
        (_support_policy(mode="wall"), _bounds(0.0, 0.9), 0.0),
    ],
    ids=[
        "floor-resolved",
        "floor-mismatch",
        "ceiling-resolved",
        "ceiling-mismatch",
        "unresolved-support",
        "no-bounds",
        "no-plane",
        "wall-out-of-scope",
    ],
)
def test_geometry_is_never_modified_and_never_authorized(
    support_policy, bounds, plane
):
    contract = _resolve(
        support_policy=support_policy, bounds=bounds, support_plane_z=plane
    )
    semantics = contract["semantics"]

    assert semantics["metadata_only"] is True
    assert semantics["geometry_modified"] is False
    assert semantics["transform_modified"] is False
    assert semantics["geometry_adjustment_authorized"] is False
    assert semantics["snap_applied"] is False


def test_no_snap_or_adjustment_field_is_emitted():
    contract = _resolve(bounds=_bounds(0.4, 1.3), support_plane_z=0.0)

    for key in (
        "translation",
        "adjustment",
        "snap",
        "corrected_center_xyz",
        "suggested_offset",
        "recommended_translation",
    ):
        assert key not in contract
        assert key not in contract["contact"]


def test_status_block_state_matches_contact_status():
    for support_policy, bounds, plane in (
        (_support_policy(), _bounds(0.0, 0.9), 0.0),
        (_support_policy(), _bounds(0.4, 1.3), 0.0),
        (_support_policy(status="unresolved"), _bounds(0.0, 0.9), 0.0),
    ):
        contract = _resolve(
            support_policy=support_policy, bounds=bounds, support_plane_z=plane
        )

        assert contract["status"]["state"] == (
            "contact_" + contract["contact"]["status"]
        )


# ---------------------------------------------------------------------------
# 14 - 15. determinism, aliasing, immutability
# ---------------------------------------------------------------------------

def test_repeated_resolution_is_deterministic():
    first = _resolve(bounds=_bounds(0.4, 1.3), support_plane_z=0.0)
    second = _resolve(bounds=_bounds(0.4, 1.3), support_plane_z=0.0)

    assert first == second
    assert first is not second
    assert first["contact"] is not second["contact"]


def test_mutating_a_result_does_not_corrupt_later_results():
    first = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)
    first["contact"]["status"] = "mismatch"
    first["semantics"]["snap_applied"] = True
    first["contact_plane"]["expected_z"] = 99.0

    second = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

    assert second["contact"]["status"] == "resolved"
    assert second["semantics"]["snap_applied"] is False
    assert second["contact_plane"]["expected_z"] == 0.0


def test_bounds_input_is_not_aliased_or_mutated():
    bounds = _bounds(0.0, 0.9)
    before = copy.deepcopy(bounds)

    contract = _resolve(bounds=bounds, support_plane_z=0.0)

    assert bounds == before
    assert contract["contact"]["asset_bottom_z"] == 0.0
    # Mutating the caller's bounds afterwards must not change anything already
    # computed, and the result holds no reference to it.
    bounds["min_xyz"][2] = 42.0
    assert contract["contact"]["asset_bottom_z"] == 0.0


def test_api_is_keyword_only():
    signature = inspect.signature(resolve_furniture_contact_state)

    assert list(signature.parameters) == [
        "unit_contract",
        "support_policy",
        "bounds",
        "support_plane_z",
        "tolerance",
    ]
    for name, parameter in signature.parameters.items():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    for name in ("bounds", "support_plane_z", "tolerance"):
        assert signature.parameters[name].default is None


def test_required_contracts_are_mandatory():
    with pytest.raises(TypeError):
        resolve_furniture_contact_state()


# ---------------------------------------------------------------------------
# 16. purity
# ---------------------------------------------------------------------------

def test_contact_module_imports_only_pure_modules():
    assert _imported_modules(contact_module) <= {"__future__", "math", "typing"}


def test_contact_module_does_not_import_the_upstream_producers():
    imported = _imported_modules(contact_module)

    for name in (
        "furniture_unit_contract",
        "furniture_support_policy",
        "furniture_adapter",
    ):
        assert name not in imported

    code = _code_source(contact_module)
    for call in (
        "build_furniture_unit_contract(",
        "resolve_furniture_support_policy(",
        "FurnitureAdapter(",
    ):
        assert call not in code


def test_contact_module_does_not_import_the_transform_stage():
    imported = _imported_modules(contact_module)

    for name in (
        "mesh_transform_spec",
        "mesh_transform_executor",
        "mesh_alignment_resolver",
        "raw_obj_loader",
        "asset_forward_resolver",
        "asset_scene_instance",
        "asset_scene_instance_collection",
        "placement_identity",
    ):
        assert name not in imported


def test_contact_module_does_not_touch_the_filesystem():
    imported = _imported_modules(contact_module)

    for name in ("os", "pathlib", "io", "json", "shutil", "tempfile"):
        assert name not in imported

    source = inspect.getsource(contact_module)
    assert "open(" not in source
    assert "__file__" not in source
    assert "asset_registry" not in source


def test_resolution_runs_with_the_filesystem_disabled(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError(
            "the production contact resolver must not touch the filesystem"
        )

    monkeypatch.setattr(builtins, "open", _explode)

    contract = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

    assert contract["contact"]["status"] == "resolved"


def test_contact_module_does_not_mutate_geometry():
    code = _code_source(contact_module)

    for token in ("vertices_xyz", "trimesh", "faces", "matrix", "math.cos", "math.sin"):
        assert token not in code

    for name in ("BASIS", "UP_ALIGNMENT_MATRIX", "R_UP", "IDENTITY_SCALE"):
        assert not hasattr(contact_module, name)


def test_contact_output_has_no_runtime_pipeline_wiring():
    contract = _resolve(bounds=_bounds(0.0, 0.9), support_plane_z=0.0)

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
        assert key not in contract

    imported = _imported_modules(contact_module)
    for name in ("bim", "scene_builder", "scene_exporter", "runtime", "pipeline"):
        assert name not in imported


def test_contact_module_is_not_imported_by_any_production_module():
    """This phase adds no wiring: nothing outside the asset contract set and the
    tests may reference the new module."""

    root = Path(__file__).resolve().parents[1]
    offenders = []

    for path in list((root / "core").rglob("*.py")) + list((root / "scripts").rglob("*.py")):
        if path.name == "furniture_contact_state.py":
            continue
        if "furniture_contact_state" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []


# ---------------------------------------------------------------------------
# 17. upstream integration (real 3D-AL / 3D-AM outputs)
# ---------------------------------------------------------------------------

def _real_unit_contract():
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


def test_real_upstream_contracts_drive_floor_contact():
    contract = resolve_furniture_contact_state(
        unit_contract=_real_unit_contract(),
        support_policy=resolve_furniture_support_policy(category="chair"),
        bounds=_bounds(0.0, 0.86),
        support_plane_z=0.0,
    )

    assert contract["unit"]["compatibility_status"] == "supported"
    assert contract["unit"]["usable_for_contact"] is True
    assert contract["support"]["target"] == "floor"
    assert contract["support"]["rule_id"] == "floor_support_measured"
    assert contract["support"]["category"] == "chair"
    assert contract["contact"]["status"] == "resolved"


def test_real_upstream_contracts_drive_ceiling_contact():
    contract = resolve_furniture_contact_state(
        unit_contract=_real_unit_contract(),
        support_policy=resolve_furniture_support_policy(category="pendant_lamp"),
        bounds=_bounds(2.4, 2.6),
        support_plane_z=2.6,
    )

    assert contract["support"]["target"] == "ceiling"
    assert contract["contact"]["status"] == "resolved"


def test_real_unresolved_category_stays_unresolved_end_to_end():
    contract = resolve_furniture_contact_state(
        unit_contract=_real_unit_contract(),
        support_policy=resolve_furniture_support_policy(category="wall_lamp"),
        bounds=_bounds(1.2, 1.4),
        support_plane_z=0.0,
    )

    assert contract["support"]["status"] == "unresolved"
    assert contract["support"]["target"] is None
    assert contract["contact"]["status"] == "unresolved"


def test_real_suspicious_asset_units_block_contact_resolution():
    """An oversize/implausible asset makes the unit contract unresolved, so no
    length comparison is claimed."""

    unit_contract = build_furniture_unit_contract(
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
        asset_dimensions_xyz=[48.2572, 52.1568, 49.9912],
    )
    assert unit_contract["compatibility"]["status"] == "unresolved"

    contract = resolve_furniture_contact_state(
        unit_contract=unit_contract,
        support_policy=resolve_furniture_support_policy(category="chair"),
        bounds=_bounds(0.0, 52.1568),
        support_plane_z=0.0,
    )

    assert contract["contact"]["status"] == "unresolved"
    assert contract["contact"]["offset"] is None


def test_every_real_registry_category_resolves_to_a_defined_contact_state():
    if not REGISTRY_PATH.is_file():
        pytest.skip(f"3D-FUTURE asset registry absent at {REGISTRY_PATH}")

    with REGISTRY_PATH.open("r", encoding="utf-8") as registry_file:
        assets = json.load(registry_file)["assets"]

    categories = sorted(
        {
            asset["category"]
            for asset in assets
            if isinstance(asset.get("category"), str) and asset["category"].strip()
        }
    )

    floor_seen = 0
    ceiling_seen = 0

    for category in categories:
        contract = resolve_furniture_contact_state(
            unit_contract=_real_unit_contract(),
            support_policy=resolve_furniture_support_policy(category=category),
            bounds=_bounds(0.0, 1.0),
            support_plane_z=0.0,
        )

        assert contract["contact"]["status"] in (
            "resolved",
            "mismatch",
            "unresolved",
        )
        assert contract["semantics"]["geometry_adjustment_authorized"] is False

        if contract["support"]["target"] == "floor":
            floor_seen += 1
        elif contract["support"]["target"] == "ceiling":
            ceiling_seen += 1

    assert floor_seen >= 40
    assert ceiling_seen == 2


# ---------------------------------------------------------------------------
# 18. real 3D-FUTURE world-space geometry (guarded)
# ---------------------------------------------------------------------------

REAL_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_MODEL_ID = "27059911-89f4-3e78-a511-4c9b8cf51fb3"
REAL_OBJ = REAL_ROOT / "3D-FUTURE-model-part1" / REAL_MODEL_ID / "raw_model.obj"

SUPPORTED_FORWARD = {
    "status": "supported",
    "axis": "+Z",
    "axis_frame": "raw_mesh_local_frame",
    "source": "family_rule",
    "family": "seating_and_adult_beds",
    "evidence": {
        "rule_id": "forward_family_rule_v1",
        "geometry_gate": "agreed",
        "agreement": 0.95,
        "notes": ["seating_and_adult_beds_only"],
    },
}


def _phi():
    import math

    return {
        "phi_status": "resolved",
        "phi_rad": math.pi / 2.0,
        "forward_status": "supported",
        "forward_axis": "+Z",
        "forward_axis_frame": "raw_mesh_local_frame",
        "world_zero_facing_axis": "+X",
        "world_zero_facing_axis_frame": "architectos_world_frame",
        "reasons": [],
    }


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_real_world_space_geometry_contact_state():
    """The most valuable acceptance evidence: real world-space bounds.

    Builds a genuine asset_scene_instance through the existing chain, then
    resolves its floor contact state against a floor plane at z = 0. Because the
    chain applies no deformation, the asset height need not match the predicted
    height, so this is EXPECTED to report a mismatch rather than hide it - which
    is exactly the Phase 3D-AK finding.
    """

    from core.pipeline.adapters.furniture_adapter import FurnitureAdapter
    from core.asset.raw_obj_loader import load_raw_obj
    from core.asset.mesh_transform_spec import build_mesh_transform_spec
    from core.asset.mesh_transform_executor import execute_mesh_transform
    from core.asset.asset_scene_instance import build_asset_scene_instance

    mesh_source = {
        "source": "3D-FUTURE",
        "model_id": REAL_MODEL_ID,
        "raw_model_path": str(REAL_OBJ),
    }
    mesh = load_raw_obj(mesh_source, allowed_roots=[REAL_ROOT])
    assert mesh["status"]["state"] == "mesh_loaded_valid"

    adapter = FurnitureAdapter()
    scene = [
        {
            "slot": 3,
            "class_name": "chair",
            "center_xyz": [0.0, 2.0, 3.0],
            "full_dims_xyz": [0.5, 0.5, 0.5],
            "angle_rad": 0.4,
            "objfeat": [1.0, 0.0],
        }
    ]
    registry = {
        "assets": [
            {
                "model_id": REAL_MODEL_ID,
                "category": "chair",
                "full_dims_xyz": [0.5, 0.5, 0.5],
                "raw_model_path": str(REAL_OBJ),
            }
        ]
    }

    matched = adapter.match_3d_future(adapter.convert_diffuscene(scene), registry)
    candidates = adapter.build_placement_candidates(
        matched, registry, placement_scope="scene-contact"
    )["placements"]

    spec = build_mesh_transform_spec(
        mesh, candidates[0], forward_contract=SUPPORTED_FORWARD, phi_result=_phi()
    )
    transformed = execute_mesh_transform(mesh, spec)
    assert transformed["status"]["state"] == "transformed_vertices_ready"

    instance = build_asset_scene_instance(
        transformed, category="chair", slot=candidates[0]["slot"]
    )
    bounds_before = copy.deepcopy(instance["bounds"])
    vertices_before = copy.deepcopy(instance["geometry"]["vertices_xyz"])

    contract = resolve_furniture_contact_state(
        unit_contract=_real_unit_contract(),
        support_policy=resolve_furniture_support_policy(category="chair"),
        bounds=instance["bounds"],
        support_plane_z=0.0,
    )

    # Real world-space bounds drive a real contact verdict.
    assert contract["support"]["target"] == "floor"
    assert contract["contact"]["status"] in ("resolved", "mismatch")
    assert contract["contact"]["asset_bottom_z"] == pytest.approx(
        bounds_before["min_xyz"][2]
    )
    assert contract["contact"]["asset_top_z"] == pytest.approx(
        bounds_before["max_xyz"][2]
    )
    assert contract["contact"]["contact_coordinate_z"] == pytest.approx(
        bounds_before["min_xyz"][2]
    )
    assert contract["contact"]["offset"] == pytest.approx(
        bounds_before["min_xyz"][2] - 0.0
    )

    # No geometry mutation, and nothing was snapped.
    assert instance["bounds"] == bounds_before
    assert instance["geometry"]["vertices_xyz"] == vertices_before
    assert contract["semantics"]["snap_applied"] is False
    assert contract["semantics"]["geometry_adjustment_authorized"] is False
    assert contract["semantics"]["geometry_modified"] is False
