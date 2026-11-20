import copy
import json
from pathlib import Path

import pytest

from core.pipeline.adapters.furniture_adapter import FurnitureAdapter


def test_diffuscene_json_to_furniture_contract(tmp_path):
    source = [
        {
            "slot": 7,
            "class_name": "single_bed",
            "center_xyz": [-0.2498, 0.6396, 0.2620],
            "full_dims_xyz": [2.7429, 1.2939, 2.5165],
            "angle_rad": -3.1398,
            "objfeat": [0.1, -0.2, 0.3],
        }
    ]
    scene_path = tmp_path / "bedroom_scene.json"
    scene_path.write_text(json.dumps(source), encoding="utf-8")

    result = FurnitureAdapter().load_diffuscene_json(scene_path)

    assert list(result) == ["furniture"]
    assert result["furniture"] == [
        {
            "source_engine": "DiffuScene",
            "slot": 7,
            "category": "single_bed",
            "center_xyz": [-0.2498, 0.6396, 0.2620],
            "full_dims_xyz": [2.7429, 1.2939, 2.5165],
            "rotation_y_rad": -3.1398,
            "objfeat": [0.1, -0.2, 0.3],
        }
    ]


def test_diffuscene_contract_rejects_missing_fields():
    with pytest.raises(ValueError, match="missing: objfeat"):
        FurnitureAdapter().convert_diffuscene(
            [
                {
                    "slot": 0,
                    "class_name": "chair",
                    "center_xyz": [0, 0, 0],
                    "full_dims_xyz": [1, 1, 1],
                    "angle_rad": 0,
                }
            ]
        )


def test_3d_future_matching_prioritizes_category_dimensions_then_objfeat():
    contract = FurnitureAdapter().convert_diffuscene(
        [
            {
                "slot": 7,
                "class_name": "single_bed",
                "center_xyz": [0, 0, 0],
                "full_dims_xyz": [2.0, 1.0, 0.6],
                "angle_rad": 0,
                "objfeat": [1.0, 0.0],
            }
        ]
    )
    registry_path = Path(__file__).parent / "fixtures" / "3d_future_registry.json"
    registry = FurnitureAdapter().load_3d_future_registry(registry_path)

    result = FurnitureAdapter().match_3d_future(contract, registry)
    match = result["furniture"][0]["asset_match"]

    assert match["model_id"] == "bed-best-feature"
    assert match["dimension_similarity"] == pytest.approx(1.0)
    assert match["objfeat_similarity"] == pytest.approx(1.0)


def test_3d_future_matching_leaves_unmatched_category_explicit():
    contract = {
        "furniture": [
            {
                "category": "wardrobe",
                "full_dims_xyz": [1.8, 0.6, 2.2],
                "objfeat": [],
            }
        ]
    }

    result = FurnitureAdapter().match_3d_future(contract, {"assets": []})

    assert result["furniture"][0]["asset_match"] is None


def test_3d_future_dimensions_rank_before_objfeat():
    contract = {
        "furniture": [
            {
                "category": "chair",
                "full_dims_xyz": [1.0, 1.0, 1.0],
                "objfeat": [1.0, 0.0],
            }
        ]
    }
    registry = {
        "assets": [
            {
                "model_id": "right-size",
                "category": "chair",
                "full_dims_xyz": [1.0, 1.0, 1.0],
                "objfeat": [0.0, 1.0],
            },
            {
                "model_id": "right-feature",
                "category": "chair",
                "full_dims_xyz": [2.0, 2.0, 2.0],
                "objfeat": [1.0, 0.0],
            },
        ]
    }

    result = FurnitureAdapter().match_3d_future(contract, registry)

    assert result["furniture"][0]["asset_match"]["model_id"] == "right-size"


# ---------------------------------------------------------------------------
# Phase 3D-H: transform-only placement candidates
# ---------------------------------------------------------------------------

def _raw_registry():
    return {
        "assets": [
            {
                "model_id": "bed-raw",
                "category": "bed",
                "full_dims_xyz": [2.0, 1.0, 0.6],
                "model_path": "3D-FUTURE-model/bed-raw/normalized_model.obj",
                "raw_model_path": "3D-FUTURE-model/bed-raw/raw_model.obj",
            },
            {
                "model_id": "bed-no-raw",
                "category": "bed",
                "full_dims_xyz": [2.0, 1.0, 0.6],
            },
        ]
    }


def _matched_contract(model_id="bed-raw"):
    return {
        "furniture": [
            {
                "source_engine": "DiffuScene",
                "slot": 7,
                "category": "single_bed",
                "center_xyz": [1.0, 2.0, 3.0],
                "full_dims_xyz": [2.7429, 1.2939, 2.5165],
                "rotation_y_rad": -3.1398,
                "objfeat": [],
                "asset_match": {
                    "source": "3D-FUTURE",
                    "model_id": model_id,
                    "category": "bed",
                    "full_dims_xyz": [2.0, 1.0, 0.6],
                    "model_path": "3D-FUTURE-model/bed-raw/normalized_model.obj",
                    "dimension_similarity": 1.0,
                    "objfeat_similarity": None,
                },
            }
        ]
    }


def test_placement_basis_maps_diffuscene_y_up_to_architectos_z_up():
    assert FurnitureAdapter().basis_position([1, 2, 3]) == [1, -3, 2]


def test_placement_basis_preserves_zero_position():
    assert FurnitureAdapter().basis_position([0, 0, 0]) == [0, 0, 0]


def test_placement_yaw_is_preserved_unchanged():
    adapter = FurnitureAdapter()

    assert adapter.map_yaw(-3.1398) == pytest.approx(-3.1398)
    assert adapter.map_yaw(0) == pytest.approx(0.0)
    assert adapter.map_yaw(1.5708) == pytest.approx(1.5708)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_placement_rejects_non_finite_values(bad):
    adapter = FurnitureAdapter()

    with pytest.raises(ValueError):
        adapter.basis_position([1.0, bad, 3.0])
    with pytest.raises(ValueError):
        adapter.map_yaw(bad)


def test_placement_rejects_bool_and_malformed_values():
    adapter = FurnitureAdapter()

    with pytest.raises(ValueError):
        adapter.basis_position([True, 0.0, 0.0])
    with pytest.raises(ValueError):
        adapter.map_yaw(True)
    with pytest.raises(ValueError):
        adapter.basis_position([1.0, 2.0])
    with pytest.raises(ValueError):
        adapter.basis_position("1,2,3")


def test_placement_marks_missing_asset_match_as_pending():
    contract = _matched_contract()
    contract["furniture"][0]["asset_match"] = None

    candidate = FurnitureAdapter().build_placement_candidates(
        contract, _raw_registry()
    )["placements"][0]

    assert candidate["status"]["state"] == "pending_asset_match"
    assert "no_compatible_asset" in candidate["status"]["reasons"]
    assert candidate["mesh_source"]["model_id"] is None
    assert candidate["mesh_source"]["raw_model_path"] is None
    # Basis mapping still happens; it does not depend on the asset match.
    assert candidate["position"]["room_local_xyz"] == [1.0, -3.0, 2.0]


def test_placement_resolves_raw_model_path_from_registry():
    candidate = FurnitureAdapter().build_placement_candidates(
        _matched_contract(), _raw_registry()
    )["placements"][0]

    assert candidate["status"]["state"] == "ready_transform_metadata"
    assert candidate["mesh_source"]["model_id"] == "bed-raw"
    assert candidate["mesh_source"]["raw_model_path"] == (
        "3D-FUTURE-model/bed-raw/raw_model.obj"
    )
    assert candidate["position"]["room_local_xyz"] == [1.0, -3.0, 2.0]
    assert candidate["rotation"]["yaw_rad"] == pytest.approx(-3.1398)


def test_placement_requires_raw_model_path_on_registry_record():
    candidate = FurnitureAdapter().build_placement_candidates(
        _matched_contract("bed-no-raw"), _raw_registry()
    )["placements"][0]

    assert candidate["status"]["state"] == "pending_raw_model_path"
    assert "raw_model_path_unavailable" in candidate["status"]["reasons"]


def test_placement_marks_unknown_model_id_as_pending():
    candidate = FurnitureAdapter().build_placement_candidates(
        _matched_contract("missing-model"), _raw_registry()
    )["placements"][0]

    assert candidate["status"]["state"] == "pending_raw_model_path"
    assert "asset_record_not_found" in candidate["status"]["reasons"]


def test_placement_reports_invalid_source_dimensions():
    contract = _matched_contract()
    contract["furniture"][0]["full_dims_xyz"] = [1.0, float("nan"), 1.0]

    candidate = FurnitureAdapter().build_placement_candidates(
        contract, _raw_registry()
    )["placements"][0]

    assert candidate["status"]["state"] == "invalid_source_dimensions"
    assert candidate["dimensions"]["target_diffuscene_xyz"] is None


def test_placement_retains_unresolved_statuses_explicitly():
    candidate = FurnitureAdapter().build_placement_candidates(
        _matched_contract(), _raw_registry()
    )["placements"][0]

    assert candidate["type"] == "furniture_asset_placement"
    assert candidate["rotation"]["mesh_forward_status"] == "unresolved"
    assert candidate["dimensions"]["axis_mapping_status"] == "unresolved"
    assert candidate["dimensions"]["fit_status"] == "fit_pending_axis_mapping"
    assert candidate["anchor"]["support_status"] == "unresolved"
    assert candidate["anchor"]["contact_z"] is None
    assert candidate["units"]["status"] == "assumed_meters"
    assert candidate["rotation"]["mapping_status"] == "resolved"
    assert candidate["rotation"]["axis"] == "+Z"
    assert candidate["scale"]["policy"] == "no_deformation"
    assert candidate["scale"]["scale_xyz"] == [1.0, 1.0, 1.0]
    assert candidate["scale"]["instance_scale_status"] == (
        "unresolved_training_data_convention"
    )
    # Dimensions are preserved verbatim: no reordering, no sorting.
    assert candidate["dimensions"]["source_asset_xyz"] == [2.0, 1.0, 0.6]
    assert candidate["dimensions"]["target_diffuscene_xyz"] == [
        2.7429,
        1.2939,
        2.5165,
    ]


def test_placement_does_not_load_mesh():
    registry = _raw_registry()
    registry["assets"][0]["raw_model_path"] = (
        "D:/does/not/exist/3D-FUTURE-model/bed-raw/raw_model.obj"
    )

    candidate = FurnitureAdapter().build_placement_candidates(
        _matched_contract(), registry
    )["placements"][0]

    # A nonexistent path is still returned verbatim as metadata, proving that
    # no mesh file is opened or parsed at this stage.
    assert candidate["status"]["state"] == "ready_transform_metadata"
    assert candidate["mesh_source"]["raw_model_path"] == (
        "D:/does/not/exist/3D-FUTURE-model/bed-raw/raw_model.obj"
    )
    assert not any(
        key in candidate for key in ("mesh", "mesh_data", "mesh_vertices")
    )


def test_placement_does_not_mutate_input_contract():
    contract = _matched_contract()
    before = copy.deepcopy(contract)

    FurnitureAdapter().build_placement_candidates(contract, _raw_registry())

    assert contract == before
    # asset_match.model_path is untouched by the raw path lookup.
    assert contract["furniture"][0]["asset_match"]["model_path"] == (
        "3D-FUTURE-model/bed-raw/normalized_model.obj"
    )


def test_placement_world_position_requires_room_origin():
    contract = _matched_contract()

    without_origin = FurnitureAdapter().build_placement_candidates(
        contract, _raw_registry()
    )["placements"][0]

    with_origin = FurnitureAdapter().build_placement_candidates(
        contract, _raw_registry(), room_origin_xyz=[10.0, 20.0, 0.0]
    )["placements"][0]

    assert without_origin["position"]["world_xyz"] is None
    assert with_origin["position"]["world_xyz"] == [11.0, 17.0, 2.0]
    assert with_origin["position"]["room_local_xyz"] == [1.0, -3.0, 2.0]


# ---------------------------------------------------------------------------
# Phase 3D-AH.1: deterministic PLACEMENT identity (never model_id / never slot)
# ---------------------------------------------------------------------------

def _multi_item_contract(count=2, model_id="bed-raw", slots=None):
    """``count`` furniture items sharing one asset model, in input order."""

    if slots is None:
        slots = list(range(count))

    return {
        "furniture": [
            {
                "source_engine": "DiffuScene",
                "slot": slots[index],
                "category": "single_bed",
                "center_xyz": [1.0, 2.0, 3.0],
                "full_dims_xyz": [2.7429, 1.2939, 2.5165],
                "rotation_y_rad": -3.1398,
                "objfeat": [],
                "asset_match": {
                    "source": "3D-FUTURE",
                    "model_id": model_id,
                    "category": "bed",
                    "full_dims_xyz": [2.0, 1.0, 0.6],
                    "model_path": "3D-FUTURE-model/bed-raw/normalized_model.obj",
                    "dimension_similarity": 1.0,
                    "objfeat_similarity": None,
                },
            }
            for index in range(count)
        ]
    }


def test_placement_identity_is_deterministic_from_scope_and_ordinal():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=2), _raw_registry(), placement_scope="scene-a"
    )["placements"]

    assert [p["placement_identity"]["instance_id"] for p in placements] == [
        "scene-a:placement:000000",
        "scene-a:placement:000001",
    ]
    assert [p["placement_identity"]["ordinal"] for p in placements] == [0, 1]
    assert all(
        p["placement_identity"]["status"] == "resolved" for p in placements
    )
    assert all(
        p["placement_identity"]["scope"] == "scene-a" for p in placements
    )


def test_one_candidate_per_source_item_in_stable_input_order():
    contract = _multi_item_contract(count=3, slots=[9, 1, 5])

    placements = FurnitureAdapter().build_placement_candidates(
        contract, _raw_registry(), placement_scope="scene-a"
    )["placements"]

    # No sorting, no deduplication, one candidate per source item.
    assert len(placements) == 3
    assert [p["slot"] for p in placements] == [9, 1, 5]
    assert [p["placement_identity"]["ordinal"] for p in placements] == [0, 1, 2]


def test_same_model_id_at_two_ordinals_gives_distinct_instance_ids():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=2, model_id="bed-raw"),
        _raw_registry(),
        placement_scope="scene-a",
    )["placements"]

    model_ids = {p["mesh_source"]["model_id"] for p in placements}
    instance_ids = [p["placement_identity"]["instance_id"] for p in placements]

    # Same ASSET MODEL, two distinct PLACEMENTS.
    assert model_ids == {"bed-raw"}
    assert len(set(instance_ids)) == 2


def test_duplicate_source_slot_still_gives_distinct_instance_ids():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=3, slots=[5, 5, 5]),
        _raw_registry(),
        placement_scope="scene-a",
    )["placements"]

    assert [p["slot"] for p in placements] == [5, 5, 5]
    assert [p["placement_identity"]["instance_id"] for p in placements] == [
        "scene-a:placement:000000",
        "scene-a:placement:000001",
        "scene-a:placement:000002",
    ]


def test_placement_identity_is_unresolved_without_scope():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=2), _raw_registry()
    )["placements"]

    for ordinal, placement in enumerate(placements):
        identity = placement["placement_identity"]
        assert identity["status"] == "unresolved"
        assert identity["instance_id"] is None
        assert identity["scope"] is None
        assert identity["ordinal"] == ordinal
        assert "placement_scope_missing" in identity["reasons"]

    # The candidates themselves are still built normally.
    assert all(
        p["status"]["state"] == "ready_transform_metadata" for p in placements
    )


def test_placement_identity_carries_source_provenance_only():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=1, slots=[7]),
        _raw_registry(),
        placement_scope="scene-a",
    )["placements"]

    identity = placements[0]["placement_identity"]

    assert identity["source_engine"] == "DiffuScene"
    assert identity["source_slot"] == 7
    # Provenance never leaks into the identity string.
    assert identity["instance_id"] == "scene-a:placement:000000"


def test_integer_diffuscene_slot_is_preserved_as_provenance():
    placements = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=1, slots=[12]),
        _raw_registry(),
        placement_scope="scene-a",
    )["placements"]

    assert placements[0]["slot"] == 12
    assert placements[0]["placement_identity"]["source_slot"] == 12
    assert isinstance(placements[0]["placement_identity"]["source_slot"], int)
    # The slot never becomes the identity.
    assert placements[0]["placement_identity"]["instance_id"] == (
        "scene-a:placement:000000"
    )


def test_placement_identity_is_repeatable_across_calls():
    first = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=3), _raw_registry(), placement_scope="scene-a"
    )
    second = FurnitureAdapter().build_placement_candidates(
        _multi_item_contract(count=3), _raw_registry(), placement_scope="scene-a"
    )

    assert first == second


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "scene a", "scene/a", "scene:a", "scene\na", "scene\u00e9",
     3, 1.5, [], {}],
    ids=[
        "empty", "whitespace", "space", "slash", "colon", "newline",
        "non-ascii", "int", "float", "list", "dict",
    ],
)
def test_malformed_placement_scope_is_rejected(bad):
    with pytest.raises(ValueError):
        FurnitureAdapter().build_placement_candidates(
            _matched_contract(), _raw_registry(), placement_scope=bad
        )


@pytest.mark.parametrize("bad", [True, False])
def test_bool_placement_scope_is_rejected(bad):
    with pytest.raises(ValueError, match="placement_scope"):
        FurnitureAdapter().build_placement_candidates(
            _matched_contract(), _raw_registry(), placement_scope=bad
        )


def test_placement_scope_is_keyword_only():
    import inspect

    signature = inspect.signature(FurnitureAdapter.build_placement_candidates)
    parameter = signature.parameters["placement_scope"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None
    # The established positional calling convention is preserved.
    assert list(signature.parameters)[:3] == [
        "self",
        "furniture_contract",
        "asset_registry",
    ]


@pytest.mark.parametrize("bad", [True, False, 1.0, "0", None, -1, [0]])
def test_validate_ordinal_rejects_bools_and_non_integers(bad):
    from core.asset.placement_identity import validate_ordinal

    with pytest.raises(ValueError):
        validate_ordinal(bad)


@pytest.mark.parametrize("ordinal", [0, 1, 42])
def test_validate_ordinal_accepts_non_negative_integers(ordinal):
    from core.asset.placement_identity import validate_ordinal

    assert validate_ordinal(ordinal) == ordinal


def test_placement_identity_helper_uses_no_nondeterministic_source():
    """No UUID / randomness / clock / global counter / geometry hash."""

    import core.asset.placement_identity as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    for token in (
        "import uuid",
        "import random",
        "import time",
        "import datetime",
        "from datetime",
        "import hashlib",
        "os.urandom",
        "getrandbits",
        "itertools.count",
    ):
        assert token not in source
