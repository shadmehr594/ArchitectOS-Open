"""Focused tests for the explicit level-name bridge and elevation provenance."""

import ast
import builtins
import copy
import inspect
import io
import tokenize
from pathlib import Path

import pytest

import core.asset.level_elevation_bridge as bridge_module
from core.asset.level_elevation_bridge import resolve_level_elevation


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolved_contract(exact_levels=None, level_evidence=None):
    if exact_levels is None:
        exact_levels = {"F1": 3.2, "ground": 0.0}
    if level_evidence is None:
        level_evidence = {
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                }
            ],
            "ground": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                }
            ],
        }

    return {
        "contract": "ProjectLevelContractV1",
        "status": "resolved",
        "exact_levels": exact_levels,
        "level_evidence": level_evidence,
        "range_hypotheses": [],
        "range_hypotheses_authoritative": False,
    }


def _resolve(
    level_contract=None,
    level_name=None,
    floor=None,
    bridge=None,
):
    return resolve_level_elevation(
        level_contract=(
            _resolved_contract() if level_contract is None else level_contract
        ),
        level_name=level_name,
        floor=floor,
        level_name_by_floor=bridge,
    )


def _real_contract(**kwargs):
    from core.architecture.reasoning.project_level_contract_v1 import (
        ProjectLevelContractV1,
    )

    return ProjectLevelContractV1().resolve(**kwargs)


def _imported_modules(module):
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
    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


# ---------------------------------------------------------------------------
# 1 - 3. precedence
# ---------------------------------------------------------------------------

def test_explicit_level_name_resolves_the_elevation():
    result = _resolve(level_name="F1")

    assert result["type"] == "level_elevation_resolution"
    assert result["version"] == "level_elevation_resolution_v1"
    assert result["elevation"]["status"] == "resolved"
    assert result["elevation"]["value_m"] == pytest.approx(3.2)
    assert result["status"]["state"] == "level_elevation_resolved"


def test_bridge_mapping_resolves_the_elevation():
    result = _resolve(floor="R1", bridge={"G": "ground", "R1": "F1"})

    assert result["elevation"]["status"] == "resolved"
    assert result["elevation"]["value_m"] == pytest.approx(3.2)
    assert result["bridge_resolution"]["level_name"] == "F1"


def test_explicit_level_name_takes_precedence_over_the_bridge():
    result = _resolve(
        level_name="ground", floor="R1", bridge={"R1": "F1"}
    )

    assert result["bridge_resolution"]["source"] == "explicit_level_name"
    assert result["bridge_resolution"]["level_name"] == "ground"
    assert result["elevation"]["value_m"] == pytest.approx(0.0)


def test_neither_name_nor_bridge_is_unresolved():
    result = _resolve()

    assert result["elevation"]["status"] == "unresolved"
    assert result["elevation"]["value_m"] is None
    assert result["status"]["state"] == "level_elevation_unresolved"
    assert "neither_level_name_nor_bridge_mapping_supplied" in (
        result["status"]["reasons"]
    )


def test_floor_label_alone_is_never_used_as_a_level_name():
    """The whole point of the bridge: no implicit floor -> level inference."""

    result = _resolve(floor="F1")

    assert result["elevation"]["status"] == "unresolved"
    assert result["bridge_resolution"]["level_name"] is None
    assert result["bridge_resolution"]["used"] is False
    assert result["bridge_resolution"]["mapping_verified"] is None
    assert "neither_level_name_nor_bridge_mapping_supplied" in (
        result["bridge_resolution"]["reasons"]
    )


def test_bridge_supplied_without_a_floor_label_cannot_be_consulted():
    result = _resolve(bridge={"R1": "F1"})

    assert result["elevation"]["status"] == "unresolved"
    assert result["bridge_resolution"]["mapping_verified"] is None
    assert result["bridge_resolution"]["used"] is False
    assert "floor_label_not_supplied_for_bridge_lookup" in (
        result["bridge_resolution"]["reasons"]
    )


def test_floor_label_absent_from_the_bridge_is_unresolved():
    result = _resolve(floor="ROOF", bridge={"G": "ground", "R1": "F1"})

    assert result["elevation"]["status"] == "unresolved"
    assert "floor_label_absent_from_bridge_mapping" in (
        result["bridge_resolution"]["reasons"]
    )


# ---------------------------------------------------------------------------
# 4 - 6. bridge_resolution metadata
# ---------------------------------------------------------------------------

def test_bridge_metadata_for_the_explicit_route():
    metadata = _resolve(level_name="F1")["bridge_resolution"]

    assert metadata["used"] is False
    assert metadata["source"] == "explicit_level_name"
    assert metadata["mapping_verified"] is None
    assert metadata["space_floor_label"] is None


def test_bridge_metadata_for_the_bridge_route():
    metadata = _resolve(floor="R1", bridge={"R1": "F1"})["bridge_resolution"]

    assert metadata["used"] is True
    assert metadata["source"] == "floor_bridge_mapping"
    assert metadata["mapping_verified"] is True
    assert metadata["space_floor_label"] == "R1"


def test_bridge_metadata_when_a_mapping_is_supplied_but_not_consulted():
    """A mapping without a floor label cannot be consulted."""

    metadata = _resolve(level_name="F1", bridge={"R1": "F1"})[
        "bridge_resolution"
    ]

    assert metadata["used"] is False
    assert metadata["source"] == "explicit_level_name"
    assert metadata["mapping_verified"] is None


def test_bridge_metadata_verifies_a_mapping_that_would_have_worked():
    metadata = _resolve(level_name="F1", floor="R1", bridge={"R1": "F1"})[
        "bridge_resolution"
    ]

    assert metadata["used"] is False
    assert metadata["source"] == "explicit_level_name"
    assert metadata["mapping_verified"] is True
    assert "bridge_mapping_would_also_have_resolved" in metadata["reasons"]


def test_bridge_metadata_records_a_failed_mapping_lookup():
    metadata = _resolve(floor="ROOF", bridge={"R1": "F1"})[
        "bridge_resolution"
    ]

    assert metadata["used"] is False
    assert metadata["source"] is None
    assert metadata["mapping_verified"] is False


def test_floor_label_equals_level_name_diagnostic():
    same = _resolve(floor="F1", bridge={"F1": "F1"})["bridge_resolution"]
    different = _resolve(floor="R1", bridge={"R1": "F1"})["bridge_resolution"]
    unknown = _resolve(level_name="F1")["bridge_resolution"]

    assert same["floor_label_equals_level_name"] is True
    assert different["floor_label_equals_level_name"] is False
    assert unknown["floor_label_equals_level_name"] is None


def test_bridge_metadata_has_the_expected_keys():
    metadata = _resolve(level_name="F1")["bridge_resolution"]

    assert sorted(metadata.keys()) == [
        "floor_label_equals_level_name",
        "level_name",
        "mapping_verified",
        "reasons",
        "source",
        "space_floor_label",
        "used",
    ]


# ---------------------------------------------------------------------------
# 7 - 8. contract gating (approved D2)
# ---------------------------------------------------------------------------

def test_absent_contract_is_unresolved_not_accepted():
    result = resolve_level_elevation(
        level_contract=None, level_name="F1"
    )

    assert result["elevation"]["status"] == "unresolved"
    assert result["level_contract"]["contract"] is None
    assert result["level_contract"]["authoritative"] is False
    assert result["level_contract"]["reasons"] == [
        "level_contract_not_supplied"
    ]


def test_unnamed_contract_is_unresolved_not_silently_accepted():
    contract = _resolved_contract()
    del contract["contract"]

    result = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )

    assert result["elevation"]["status"] == "unresolved"
    assert result["level_contract"]["reasons"] == [
        "level_contract_name_missing"
    ]


@pytest.mark.parametrize(
    "bad_name",
    ["SomethingElse", "project_level_contract_v1", "", 3],
    ids=["other-name", "wrong-case", "empty", "int"],
)
def test_wrongly_named_contract_is_rejected(bad_name):
    contract = _resolved_contract()
    contract["contract"] = bad_name

    with pytest.raises(ValueError, match="level_contract.contract must be"):
        resolve_level_elevation(level_contract=contract, level_name="F1")


@pytest.mark.parametrize("status", ["conflicted", "unresolved"])
def test_non_resolved_contract_status_is_unresolved(status):
    contract = _resolved_contract()
    contract["status"] = status

    result = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )

    assert result["elevation"]["status"] == "unresolved"
    assert result["level_contract"]["status"] == status
    assert result["level_contract"]["authoritative"] is False
    assert (
        f"level_contract_status_{status}_not_authoritative_for_elevation"
        in result["level_contract"]["reasons"]
    )


def test_conflicted_contract_discards_its_exact_levels():
    """A conflicted contract carries {} levels, so nothing can resolve."""

    contract = _resolved_contract(exact_levels={}, level_evidence={})
    contract["status"] = "conflicted"

    result = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )

    assert result["elevation"]["value_m"] is None


def test_resolved_contract_is_authoritative():
    result = _resolve(level_name="F1")

    assert result["level_contract"] == {
        "contract": "ProjectLevelContractV1",
        "status": "resolved",
        "authoritative": True,
        "reasons": ["level_contract_resolved_and_authoritative"],
    }


def test_malformed_contract_status_is_rejected():
    contract = _resolved_contract()
    contract["status"] = "maybe"

    with pytest.raises(ValueError, match="level_contract.status must be"):
        resolve_level_elevation(level_contract=contract, level_name="F1")


def test_resolved_contract_without_exact_levels_is_rejected():
    contract = _resolved_contract()
    del contract["exact_levels"]

    with pytest.raises(ValueError, match="requires an exact_levels mapping"):
        resolve_level_elevation(level_contract=contract, level_name="F1")


def test_non_mapping_contract_is_rejected():
    with pytest.raises(ValueError, match="level_contract must be a mapping"):
        resolve_level_elevation(level_contract="x", level_name="F1")


# ---------------------------------------------------------------------------
# 9 - 10. elevation and derivation provenance
# ---------------------------------------------------------------------------

def test_level_absent_from_exact_levels_is_unresolved():
    result = _resolve(level_name="F9")

    assert result["elevation"]["status"] == "unresolved"
    assert result["elevation"]["reasons"] == [
        "level_name_absent_from_exact_levels"
    ]


def test_directly_stated_elevation_is_labelled():
    elevation = _resolve(level_name="F1")["elevation"]

    assert elevation["derivation"] == "directly_stated"
    assert elevation["authority_class"] == "PROJECT_REQUIREMENT"
    assert elevation["provenance"] == ["project_brief_v1"]


def test_span_derived_elevation_is_labelled():
    contract = _resolved_contract(
        exact_levels={"ground": 0.0, "F1": 3.2},
        level_evidence={
            "ground": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                }
            ],
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["project_brief_v1"],
                },
                {
                    "kind": "floor_to_floor_span",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["span_evidence_v1"],
                },
            ],
        },
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "resolved"
    assert elevation["derivation"] == "derived_from_floor_to_floor_span"
    assert elevation["provenance"] == ["project_brief_v1", "span_evidence_v1"]
    assert [record["kind"] for record in elevation["evidence"]] == [
        "level_elevation",
        "floor_to_floor_span",
    ]


def test_provenance_is_deduplicated_in_order():
    contract = _resolved_contract(
        level_evidence={
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["a", "b"],
                },
                {
                    "kind": "floor_to_floor_span",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["b", "c"],
                },
            ]
        }
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["provenance"] == ["a", "b", "c"]


def test_elevation_value_comes_from_exact_levels():
    contract = _resolved_contract(exact_levels={"F1": 7.5})

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["value_m"] == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# 11 - 13. authority refusal (approved D3 - never pick a winner)
# ---------------------------------------------------------------------------

def test_mixed_authority_classes_are_unresolved():
    contract = _resolved_contract(
        level_evidence={
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": ["a"],
                },
                {
                    "kind": "floor_to_floor_span",
                    "authority_class": "HARD_REGULATION",
                    "provenance": ["b"],
                },
            ]
        }
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "unresolved"
    assert elevation["authority_class"] is None
    assert elevation["reasons"] == ["mixed_authority_classes"]


@pytest.mark.parametrize(
    "authority",
    ["DESIGN_HEURISTIC", "SEMANTIC_INFERENCE", "ASSUMED", "unknown"],
)
def test_non_exact_authority_is_unresolved(authority):
    contract = _resolved_contract(
        level_evidence={
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": authority,
                    "provenance": ["a"],
                }
            ]
        }
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "unresolved"
    assert elevation["reasons"] == ["evidence_authority_not_exact"]


def test_missing_authority_class_is_unresolved():
    contract = _resolved_contract(
        level_evidence={
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": None,
                    "provenance": ["a"],
                }
            ]
        }
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "unresolved"


def test_absent_evidence_is_unresolved():
    contract = _resolved_contract(level_evidence={})

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "unresolved"
    assert elevation["reasons"] == ["level_evidence_absent"]


def test_absent_provenance_is_unresolved():
    contract = _resolved_contract(
        level_evidence={
            "F1": [
                {
                    "kind": "level_elevation",
                    "authority_class": "PROJECT_REQUIREMENT",
                    "provenance": [],
                }
            ]
        }
    )

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "unresolved"
    assert elevation["reasons"] == ["evidence_provenance_absent"]


def test_both_exact_authorities_are_accepted():
    for authority in ("HARD_REGULATION", "PROJECT_REQUIREMENT"):
        contract = _resolved_contract(
            level_evidence={
                "F1": [
                    {
                        "kind": "level_elevation",
                        "authority_class": authority,
                        "provenance": ["a"],
                    }
                ]
            }
        )

        elevation = resolve_level_elevation(
            level_contract=contract, level_name="F1"
        )["elevation"]

        assert elevation["status"] == "resolved"
        assert elevation["authority_class"] == authority


# ---------------------------------------------------------------------------
# 14. input validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad", ["", "   ", 3, True, [], {}], ids=["empty", "ws", "int", "bool", "list", "dict"]
)
def test_malformed_level_name_is_rejected(bad):
    with pytest.raises(ValueError, match="level_name must be a non-empty string"):
        resolve_level_elevation(level_contract=_resolved_contract(), level_name=bad)


@pytest.mark.parametrize(
    "bad", ["", "   ", 3, True, [], {}], ids=["empty", "ws", "int", "bool", "list", "dict"]
)
def test_malformed_floor_is_rejected(bad):
    with pytest.raises(ValueError, match="floor must be a non-empty string"):
        resolve_level_elevation(level_contract=_resolved_contract(), floor=bad)


@pytest.mark.parametrize(
    "bad",
    ["x", 3, [], [("R1", "F1")], {"": "F1"}, {"R1": ""}, {"R1": 3}, {"R1": True}],
    ids=["str", "int", "list", "pair-list", "empty-key", "empty-value", "int-value", "bool-value"],
)
def test_malformed_bridge_mapping_is_rejected(bad):
    with pytest.raises(ValueError, match="level_name_by_floor"):
        resolve_level_elevation(
            level_contract=_resolved_contract(),
            floor="R1",
            level_name_by_floor=bad,
        )


def test_empty_bridge_mapping_is_allowed_but_unverified():
    result = resolve_level_elevation(
        level_contract=_resolved_contract(),
        floor="R1",
        level_name_by_floor={},
    )

    assert result["bridge_resolution"]["mapping_verified"] is False
    assert result["elevation"]["status"] == "unresolved"


@pytest.mark.parametrize(
    "bad",
    [{"F1": "x"}, {"F1": float("nan")}, {"F1": True}, {"": 3.2}, "x"],
    ids=["str", "nan", "bool", "empty-key", "container-str"],
)
def test_malformed_exact_levels_are_rejected(bad):
    contract = _resolved_contract()
    contract["exact_levels"] = bad

    with pytest.raises(ValueError):
        resolve_level_elevation(level_contract=contract, level_name="F1")


@pytest.mark.parametrize(
    "bad",
    [
        "x",
        {"F1": "not-a-list"},
        {"F1": ["x"]},
        {"F1": [{"kind": "unknown_kind"}]},
        {"F1": [{"kind": "level_elevation", "provenance": "x"}]},
        {"F1": [{"kind": "level_elevation", "provenance": [3]}]},
        {"F1": [{"kind": "level_elevation", "authority_class": 3}]},
    ],
    ids=[
        "container-str",
        "not-a-list",
        "record-str",
        "bad-kind",
        "provenance-str",
        "provenance-int",
        "authority-int",
    ],
)
def test_malformed_level_evidence_is_rejected(bad):
    contract = _resolved_contract()
    contract["level_evidence"] = bad

    with pytest.raises(ValueError):
        resolve_level_elevation(level_contract=contract, level_name="F1")


def test_api_is_keyword_only():
    signature = inspect.signature(resolve_level_elevation)

    assert list(signature.parameters) == [
        "level_contract",
        "level_name",
        "floor",
        "level_name_by_floor",
    ]
    for name, parameter in signature.parameters.items():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["level_contract"].default is inspect.Parameter.empty
    for name in ("level_name", "floor", "level_name_by_floor"):
        assert signature.parameters[name].default is None


def test_level_contract_is_required():
    with pytest.raises(TypeError):
        resolve_level_elevation()


# ---------------------------------------------------------------------------
# 15 - 19. shape, semantics, determinism, purity
# ---------------------------------------------------------------------------

def test_output_shape():
    result = _resolve(level_name="F1")

    assert sorted(result.keys()) == [
        "bridge_resolution",
        "elevation",
        "level_contract",
        "semantics",
        "status",
        "type",
        "version",
    ]
    assert sorted(result["elevation"].keys()) == [
        "authority_class",
        "derivation",
        "evidence",
        "provenance",
        "reasons",
        "status",
        "value_m",
    ]


def test_semantics_block_is_exact():
    assert _resolve(level_name="F1")["semantics"] == {
        "metadata_only": True,
        "geometry_modified": False,
        "placement_modified": False,
        "snap_applied": False,
        "geometry_adjustment_authorized": False,
    }


def test_state_mirrors_the_elevation_status():
    resolved = _resolve(level_name="F1")
    unresolved = _resolve(level_name="F9")

    assert resolved["status"]["state"] == "level_elevation_resolved"
    assert unresolved["status"]["state"] == "level_elevation_unresolved"


def test_repeated_resolution_is_deterministic():
    first = _resolve(level_name="F1", floor="R1", bridge={"R1": "F1"})
    second = _resolve(level_name="F1", floor="R1", bridge={"R1": "F1"})

    assert first == second
    assert first is not second
    assert first["elevation"] is not second["elevation"]


def test_caller_inputs_are_not_mutated():
    contract = _resolved_contract()
    mapping = {"R1": "F1"}
    before = copy.deepcopy((contract, mapping))

    resolve_level_elevation(
        level_contract=contract,
        floor="R1",
        level_name_by_floor=mapping,
    )

    assert (contract, mapping) == before


def test_mutating_a_result_does_not_corrupt_later_results():
    first = _resolve(level_name="F1")
    first["elevation"]["value_m"] = 99.0
    first["elevation"]["provenance"].append("injected")
    first["semantics"]["snap_applied"] = True

    second = _resolve(level_name="F1")

    assert second["elevation"]["value_m"] == pytest.approx(3.2)
    assert second["elevation"]["provenance"] == ["project_brief_v1"]
    assert second["semantics"]["snap_applied"] is False


def test_bridge_module_imports_only_pure_modules():
    assert _imported_modules(bridge_module) <= {"__future__", "math", "typing"}


def test_bridge_module_does_not_import_the_contract_set_or_runtime():
    imported = _imported_modules(bridge_module)

    for name in (
        "furniture_adapter",
        "placement_identity",
        "asset_scene_instance",
        "asset_scene_instance_collection",
        "furniture_unit_contract",
        "furniture_support_policy",
        "mesh_transform_spec",
        "mesh_transform_executor",
        "mesh_alignment_resolver",
        "raw_obj_loader",
        "asset_forward_resolver",
        "project_level_contract_v1",
        "bim",
        "scene_builder",
        "scene_exporter",
        "runtime",
        "pipeline",
    ):
        assert name not in imported


def test_bridge_module_does_not_call_the_contract_set():
    code = _code_source(bridge_module)

    for call in (
        "FurnitureAdapter(",
        "build_placement_identity(",
        "build_furniture_unit_contract(",
        "resolve_furniture_support_policy(",
        "build_mesh_transform_spec(",
        "execute_mesh_transform(",
        "load_raw_obj(",
        "ProjectLevelContractV1(",
    ):
        assert call not in code


def test_bridge_module_touches_no_filesystem():
    imported = _imported_modules(bridge_module)

    for name in ("os", "pathlib", "io", "json", "shutil", "tempfile"):
        assert name not in imported

    source = inspect.getsource(bridge_module)
    assert "open(" not in source
    assert "__file__" not in source


def test_bridge_module_does_not_mutate_geometry():
    code = _code_source(bridge_module)

    for token in ("vertices_xyz", "trimesh", "matrix", "math.cos", "math.sin"):
        assert token not in code

    for name in ("BASIS", "UP_ALIGNMENT_MATRIX", "R_UP", "IDENTITY_SCALE"):
        assert not hasattr(bridge_module, name)


def test_bridge_module_respects_the_existing_wiring_guards():
    """Both the Phase 3D-AN and Phase 3D-AO guards scan production sources for
    their own module names as plain substrings, so this module must not name
    either of them."""

    source = inspect.getsource(bridge_module)

    assert "furniture_contact_state" not in source
    assert "room_support_surface" not in source


def test_bridge_module_is_not_referenced_by_any_production_module():
    root = Path(__file__).resolve().parents[1]
    offenders = []

    for path in list((root / "core").rglob("*.py")) + list(
        (root / "scripts").rglob("*.py")
    ):
        if path.name == "level_elevation_bridge.py":
            continue
        if "level_elevation_bridge" in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []


def test_bridge_output_has_no_runtime_pipeline_wiring():
    result = _resolve(level_name="F1")

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
        assert key not in result


# ---------------------------------------------------------------------------
# 20 - 22. real ProjectLevelContractV1 integration
# ---------------------------------------------------------------------------

def _brief_contract():
    return _real_contract(
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


def test_real_contract_bridges_the_space_floor_vocabulary():
    """The space boundary engine uses ("G", "R1", "R2", "ROOF") while level
    contracts use names like "ground"/"F1". The bridge is what connects them."""

    contract = _brief_contract()
    assert contract["status"] == "resolved"

    bridge = {"G": "ground", "R1": "F1", "R2": "F2", "ROOF": "roof"}

    ground = resolve_level_elevation(
        level_contract=contract, floor="G", level_name_by_floor=bridge
    )
    first = resolve_level_elevation(
        level_contract=contract, floor="R1", level_name_by_floor=bridge
    )

    assert ground["elevation"]["value_m"] == pytest.approx(0.0)
    assert ground["bridge_resolution"]["level_name"] == "ground"
    assert first["elevation"]["value_m"] == pytest.approx(3.2)
    assert first["bridge_resolution"]["source"] == "floor_bridge_mapping"


def test_real_contract_without_a_bridge_cannot_resolve_a_space_floor_label():
    """Without the bridge the raw space label is not a level name - the exact
    gap this refinement closes."""

    contract = _brief_contract()

    result = resolve_level_elevation(
        level_contract=contract, floor="R1"
    )

    assert result["elevation"]["status"] == "unresolved"
    assert result["bridge_resolution"]["level_name"] is None


def test_real_conflicted_contract_never_resolves():
    contract = _real_contract(
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
    assert contract["status"] == "conflicted"
    assert contract["exact_levels"] == {}

    result = resolve_level_elevation(
        level_contract=contract, level_name="ground"
    )

    assert result["elevation"]["status"] == "unresolved"
    assert result["level_contract"]["status"] == "conflicted"


def test_real_span_derived_level_is_labelled_as_derived():
    contract = _real_contract(
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
                "kind": "floor_to_floor_span",
                "from_level": "ground",
                "to_level": "F1",
                "value": 3.2,
                "authority_class": "PROJECT_REQUIREMENT",
                "provenance": ["span_evidence_v1"],
            }
        ],
    )

    assert contract["exact_levels"]["F1"] == pytest.approx(3.2)

    elevation = resolve_level_elevation(
        level_contract=contract, level_name="F1"
    )["elevation"]

    assert elevation["status"] == "resolved"
    assert elevation["derivation"] == "derived_from_floor_to_floor_span"
    assert "span_evidence_v1" in elevation["provenance"]
