"""Focused tests for the declarative furniture support policy contract (Phase 3D-AM)."""

import builtins
import inspect
import io
import json
import tokenize
from pathlib import Path

import pytest

import core.asset.furniture_support_policy as policy_module
from core.asset.furniture_support_policy import (
    resolve_furniture_support_policy,
    validate_support_rules,
)


REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "3d_future"
    / "asset_registry.json"
)

FLOOR_CATEGORIES = tuple(
    sorted(
        {
            category
            for rule in policy_module.SUPPORT_RULES
            if rule["support_mode"] == "floor"
            for category in rule["categories"]
        }
    )
)

CEILING_CATEGORIES = tuple(
    sorted(
        {
            category
            for rule in policy_module.SUPPORT_RULES
            if rule["support_mode"] == "ceiling"
            for category in rule["categories"]
        }
    )
)

ALL_CATEGORIES = tuple(sorted(set(FLOOR_CATEGORIES) | set(CEILING_CATEGORIES)))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve(category):
    return resolve_furniture_support_policy(category=category)


def _mode(category):
    return _resolve(category)["support"]["mode"]


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

    Structural checks must inspect executable code: this module's docstring
    legitimately names the things it refuses to do.
    """

    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


def _rule(
    rule_id="rule-a",
    categories=("chair",),
    support_mode="floor",
    source="test_source",
    physical_contact_required=True,
):
    # ``categories`` is passed through untouched so malformed values reach the
    # validator instead of being coerced (or exploding) inside the helper.
    return {
        "rule_id": rule_id,
        "categories": categories,
        "support_mode": support_mode,
        "source": source,
        "physical_contact_required": physical_contact_required,
    }


# ---------------------------------------------------------------------------
# 1 - 5. known categories
# ---------------------------------------------------------------------------

def test_known_floor_category_resolves_floor():
    contract = _resolve("chair")

    assert contract["type"] == "furniture_support_policy"
    assert contract["version"] == "furniture_support_policy_v1"
    assert contract["support"]["status"] == "resolved"
    assert contract["support"]["mode"] == "floor"
    assert contract["status"]["state"] == "support_policy_resolved"


def test_second_known_floor_category_resolves_floor():
    assert _mode("wardrobe") == "floor"
    assert _mode("cabinet") == "floor"


def test_floor_lamp_resolves_floor():
    """``floor_lamp`` is an exact category present in the local registry."""

    assert _mode("floor_lamp") == "floor"


def test_pendant_lamp_resolves_ceiling():
    contract = _resolve("pendant_lamp")

    assert contract["support"]["status"] == "resolved"
    assert contract["support"]["mode"] == "ceiling"


def test_ceiling_lamp_resolves_ceiling():
    assert _mode("ceiling_lamp") == "ceiling"


@pytest.mark.parametrize("category", FLOOR_CATEGORIES)
def test_every_floor_rule_category_resolves_to_floor(category):
    contract = _resolve(category)

    assert contract["support"]["status"] == "resolved"
    assert contract["support"]["mode"] == "floor"
    assert contract["category"] == category
    assert contract["support"]["rule_id"]
    assert contract["support"]["source"]


@pytest.mark.parametrize("category", CEILING_CATEGORIES)
def test_every_ceiling_rule_category_resolves_to_ceiling(category):
    contract = _resolve(category)

    assert contract["support"]["status"] == "resolved"
    assert contract["support"]["mode"] == "ceiling"
    assert contract["category"] == category


def test_no_ceiling_category_is_treated_as_floor_supported():
    for category in CEILING_CATEGORIES:
        assert _mode(category) != "floor"


# ---------------------------------------------------------------------------
# 6 - 10. unknown / malformed input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "category",
    ["unknown_thing", "spaceship", "wall_lamp", "hanging_chair", "x", "0"],
)
def test_unknown_category_resolves_unresolved(category):
    contract = _resolve(category)

    assert contract["support"]["status"] == "unresolved"
    assert contract["support"]["mode"] is None
    assert contract["support"]["rule_id"] is None
    assert contract["support"]["source"] is None
    assert contract["status"]["state"] == "support_policy_unresolved"
    assert "no_support_rule_for_category" in contract["support"]["reasons"]


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "\t", "\n", " \t \n "],
    ids=["empty", "spaces", "tab", "newline", "mixed-whitespace"],
)
def test_empty_or_whitespace_category_is_rejected(bad):
    with pytest.raises(ValueError, match="category must be a non-empty string"):
        _resolve(bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_category_is_rejected(bad):
    with pytest.raises(ValueError, match="category must be a non-empty string"):
        _resolve(bad)


@pytest.mark.parametrize(
    "bad",
    [None, 3, 1.5, [], {}, (), object()],
    ids=["none", "int", "float", "list", "dict", "tuple", "object"],
)
def test_non_string_category_is_rejected(bad):
    with pytest.raises(ValueError, match="category must be a non-empty string"):
        _resolve(bad)


def test_category_is_required():
    with pytest.raises(TypeError):
        resolve_furniture_support_policy()


def test_api_is_keyword_only():
    signature = inspect.signature(resolve_furniture_support_policy)

    assert list(signature.parameters) == ["category"]
    assert (
        signature.parameters["category"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )


# ---------------------------------------------------------------------------
# 11 - 14. no fuzzy / substring / plural / case matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "category",
    [" chair", "chair ", "  chair  ", "chair\t", "\nchair"],
    ids=["leading", "trailing", "both", "tab", "newline"],
)
def test_no_fuzzy_matching_on_surrounding_whitespace(category):
    assert _mode(category) is None


@pytest.mark.parametrize(
    "category",
    ["chai", "ch", "hair", "chair_back", "chair_", "_chair", "cha", "air"],
)
def test_no_substring_matching(category):
    assert _mode(category) is None


@pytest.mark.parametrize(
    "category",
    ["chairs", "beds", "tables", "cabinets", "shelves", "sofas", "lamps"],
)
def test_no_plural_guessing(category):
    assert _mode(category) is None


@pytest.mark.parametrize(
    "category",
    ["Chair", "CHAIR", "Bed", "Cabinet", "PENDANT_LAMP", "Ceiling_Lamp"],
)
def test_no_case_guessing(category):
    assert _mode(category) is None


def test_no_alias_inference_inside_the_resolver():
    """Alias keys resolve on their own merits, never via their alias target."""

    # ``lounge_chair`` has its own rule; it must not resolve merely because the
    # adapter aliases it to ``chair``.
    assert _resolve("lounge_chair")["support"]["rule_id"] == (
        "floor_support_adapter_category_contract"
    )
    # And an alias that is deliberately not a rule stays unresolved.
    assert _mode("bedside_cabinet") is None


# ---------------------------------------------------------------------------
# 15. exact category preservation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_exact_category_is_preserved(category):
    assert _resolve(category)["category"] == category


@pytest.mark.parametrize(
    "category",
    ["Chair", "unknown_thing", "  chair  ", "Pendant_Lamp"],
)
def test_category_is_preserved_even_when_unresolved(category):
    assert _resolve(category)["category"] == category


# ---------------------------------------------------------------------------
# 16 - 20. rule provenance and physical validation boundary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_resolved_rule_has_rule_id_and_source(category):
    support = _resolve(category)["support"]

    assert isinstance(support["rule_id"], str)
    assert support["rule_id"].strip()
    assert isinstance(support["source"], str)
    assert support["source"].strip()
    assert support["reasons"] == [f"matched_support_rule:{support['rule_id']}"]


def test_rule_ids_are_the_expected_set():
    assert {rule["rule_id"] for rule in policy_module.SUPPORT_RULES} == {
        "floor_support_measured",
        "floor_support_3d_future_taxonomy",
        "floor_support_adapter_category_contract",
        "ceiling_support_3d_future_taxonomy",
    }


@pytest.mark.parametrize("category", FLOOR_CATEGORIES)
def test_floor_support_requires_future_physical_validation(category):
    assert _resolve(category)["physical_validation"] == {
        "required": True,
        "contact_target": "floor",
        "contact_check_status": "pending",
        "geometry_adjustment_authorized": False,
    }


@pytest.mark.parametrize("category", CEILING_CATEGORIES)
def test_ceiling_support_requires_future_physical_validation(category):
    assert _resolve(category)["physical_validation"] == {
        "required": True,
        "contact_target": "ceiling",
        "contact_check_status": "pending",
        "geometry_adjustment_authorized": False,
    }


def test_unresolved_category_does_not_claim_contact_validated():
    contract = _resolve("unknown_thing")
    validation = contract["physical_validation"]

    assert validation["required"] is False
    assert validation["contact_target"] is None
    assert validation["contact_check_status"] == "unresolved"
    assert validation["geometry_adjustment_authorized"] is False
    assert "contact_target_unresolved_until_support_mode_known" in (
        contract["status"]["reasons"]
    )
    # Nothing anywhere claims a completed check.
    assert "complete" not in json.dumps(contract)
    assert "validated_ok" not in json.dumps(contract)


def test_physical_validation_is_never_reported_complete():
    for category in ALL_CATEGORIES + ("unknown_thing",):
        status = _resolve(category)["physical_validation"]["contact_check_status"]

        assert status in ("pending", "unresolved")
        assert status != "complete"


# ---------------------------------------------------------------------------
# 21 - 27. no geometry action, ever
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", ALL_CATEGORIES + ("unknown_thing",))
def test_geometry_adjustment_is_never_authorized(category):
    assert (
        _resolve(category)["physical_validation"][
            "geometry_adjustment_authorized"
        ]
        is False
    )


def _semantics_of(category):
    return _resolve(category)["semantics"]


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_floor_snap_is_never_applied(category):
    assert _semantics_of(category)["floor_snap_applied"] is False


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_ceiling_snap_is_never_applied(category):
    assert _semantics_of(category)["ceiling_snap_applied"] is False


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_wall_snap_is_never_applied(category):
    assert _semantics_of(category)["wall_snap_applied"] is False


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_geometry_is_never_modified(category):
    semantics = _semantics_of(category)

    assert semantics["geometry_modified"] is False
    assert semantics["metadata_only"] is True


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_collision_is_never_validated(category):
    assert _semantics_of(category)["collision_validated"] is False


@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_containment_is_never_validated(category):
    assert _semantics_of(category)["containment_validated"] is False


def test_semantics_block_is_exact():
    assert _semantics_of("chair") == {
        "metadata_only": True,
        "geometry_modified": False,
        "floor_snap_applied": False,
        "ceiling_snap_applied": False,
        "wall_snap_applied": False,
        "collision_validated": False,
        "containment_validated": False,
    }


def test_contract_has_the_expected_top_level_shape():
    assert sorted(_resolve("chair").keys()) == [
        "category",
        "physical_validation",
        "semantics",
        "status",
        "support",
        "type",
        "version",
    ]


# ---------------------------------------------------------------------------
# 28 - 29. determinism and aliasing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", ["chair", "pendant_lamp", "unknown_thing"])
def test_repeated_resolution_is_deterministic(category):
    first = _resolve(category)
    second = _resolve(category)

    assert first == second
    assert first is not second
    assert first["support"] is not second["support"]


def test_mutating_a_result_does_not_corrupt_later_results():
    first = _resolve("chair")
    first["support"]["mode"] = "ceiling"
    first["support"]["reasons"].append("mutated")
    first["semantics"]["floor_snap_applied"] = True
    first["physical_validation"]["contact_target"] = "wall"

    second = _resolve("chair")

    assert second["support"]["mode"] == "floor"
    assert second["support"]["reasons"] == [
        "matched_support_rule:floor_support_measured"
    ]
    assert second["semantics"]["floor_snap_applied"] is False
    assert second["physical_validation"]["contact_target"] == "floor"


def test_caller_input_is_not_mutated():
    category = "chair"
    before = category

    _resolve(category)

    assert category == before


def test_support_rules_constant_is_immutable_in_shape():
    assert isinstance(policy_module.SUPPORT_RULES, tuple)
    for rule in policy_module.SUPPORT_RULES:
        assert isinstance(rule["categories"], tuple)


# ---------------------------------------------------------------------------
# 30 - 34. purity
# ---------------------------------------------------------------------------

def test_policy_module_imports_only_pure_modules():
    assert _imported_modules(policy_module) <= {"__future__", "typing"}


def test_policy_module_has_no_transform_imports():
    imported = _imported_modules(policy_module)

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


def test_policy_module_has_no_adapter_import():
    imported = _imported_modules(policy_module)

    assert "furniture_adapter" not in imported
    assert "FurnitureAdapter(" not in _code_source(policy_module)


def test_policy_module_has_no_unit_contract_import():
    imported = _imported_modules(policy_module)

    assert "furniture_unit_contract" not in imported
    assert "build_furniture_unit_contract(" not in _code_source(policy_module)


def test_policy_module_does_not_process_geometry_or_bounds():
    code = _code_source(policy_module)

    for token in (
        "center_xyz",
        "vertices_xyz",
        "min_xyz",
        "max_xyz",
        "half_extent",
        "half_size",
        "bbox",
        "trimesh",
        "math.",
    ):
        assert token not in code


def test_policy_module_does_not_reinterpret_center_or_extents():
    """No ``bottom = center - half_extent`` style arithmetic may exist."""

    code = _code_source(policy_module)

    for token in ("bottom", "top_z", "center", "extent", "offset"):
        assert token not in code


def test_policy_module_touches_no_filesystem_and_no_external_data():
    imported = _imported_modules(policy_module)

    for name in ("os", "pathlib", "io", "json", "shutil", "tempfile"):
        assert name not in imported

    source = inspect.getsource(policy_module)
    assert "open(" not in source
    assert "__file__" not in source
    assert "asset_registry" not in source


def test_policy_runs_with_the_filesystem_disabled(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError(
            "the production support policy must not touch the filesystem"
        )

    monkeypatch.setattr(builtins, "open", _explode)

    assert _mode("chair") == "floor"
    assert _mode("pendant_lamp") == "ceiling"
    assert _mode("unknown_thing") is None


def test_policy_output_has_no_runtime_pipeline_wiring():
    contract = _resolve("chair")

    for key in (
        "scene",
        "scene_result",
        "bim",
        "renderer",
        "export",
        "export_result",
        "runtime",
        "pipeline",
        "room",
        "collision",
    ):
        assert key not in contract

    imported = _imported_modules(policy_module)
    for name in ("bim", "scene_builder", "scene_exporter", "runtime", "pipeline"):
        assert name not in imported


# ---------------------------------------------------------------------------
# 35 - 36. rule registry integrity
# ---------------------------------------------------------------------------

def test_builtin_rule_set_is_valid():
    normalized = validate_support_rules(policy_module.SUPPORT_RULES)

    assert len(normalized) == 4
    assert all(isinstance(rule["categories"], list) for rule in normalized)


def test_rule_categories_are_disjoint():
    seen = set()
    for rule in policy_module.SUPPORT_RULES:
        for category in rule["categories"]:
            assert category not in seen, f"{category!r} appears in two rules"
            seen.add(category)


def test_rule_category_counts_are_locked():
    assert len(FLOOR_CATEGORIES) == 56
    assert len(CEILING_CATEGORIES) == 2
    assert len(ALL_CATEGORIES) == 58


def test_no_wall_or_free_rules_exist():
    modes = {rule["support_mode"] for rule in policy_module.SUPPORT_RULES}

    assert "wall" not in modes
    assert "free" not in modes
    # The vocabulary still admits both, so a future evidenced rule needs no
    # contract change.
    assert set(policy_module.SUPPORT_MODES) == {
        "floor",
        "ceiling",
        "wall",
        "free",
    }


def test_conflicting_duplicate_category_rules_are_rejected():
    rules = [
        _rule(rule_id="a", categories=("chair",), support_mode="floor"),
        _rule(rule_id="b", categories=("chair",), support_mode="ceiling"),
    ]

    with pytest.raises(ValueError, match="assigned exactly one support rule"):
        validate_support_rules(rules)


def test_same_category_cannot_map_to_two_rules_even_in_one_mode():
    rules = [
        _rule(rule_id="a", categories=("chair",), support_mode="floor"),
        _rule(rule_id="b", categories=("chair",), support_mode="floor"),
    ]

    with pytest.raises(ValueError, match="assigned exactly one support rule"):
        validate_support_rules(rules)


def test_duplicate_rule_id_is_rejected():
    rules = [
        _rule(rule_id="same", categories=("chair",)),
        _rule(rule_id="same", categories=("table",)),
    ]

    with pytest.raises(ValueError, match="duplicate support rule_id"):
        validate_support_rules(rules)


@pytest.mark.parametrize(
    "bad", ["", "   ", None, 3, True, [], {}], ids=["empty", "ws", "none", "int", "bool", "list", "dict"]
)
def test_malformed_rule_id_is_rejected(bad):
    with pytest.raises(ValueError, match="rule_id must be a non-empty string"):
        validate_support_rules([_rule(rule_id=bad)])


@pytest.mark.parametrize(
    "bad",
    ["", "FLOOR", "unknown", None, 3, True],
    ids=["empty", "upper", "unknown", "none", "int", "bool"],
)
def test_invalid_support_mode_is_rejected(bad):
    with pytest.raises(ValueError, match="support_mode must be one of"):
        validate_support_rules([_rule(support_mode=bad)])


@pytest.mark.parametrize(
    "bad", ["", "   ", None, 3, True, [], {}], ids=["empty", "ws", "none", "int", "bool", "list", "dict"]
)
def test_malformed_rule_source_is_rejected(bad):
    with pytest.raises(ValueError, match="source must be a non-empty string"):
        validate_support_rules([_rule(source=bad)])


@pytest.mark.parametrize("bad", [1, 0, "true", None], ids=["one", "zero", "str", "none"])
def test_non_boolean_contact_required_is_rejected(bad):
    with pytest.raises(ValueError, match="physical_contact_required must be"):
        validate_support_rules([_rule(physical_contact_required=bad)])


@pytest.mark.parametrize(
    "bad",
    ["chair", 3, {}, [""], ["   "], [3], [True], []],
    ids=["str", "int", "dict", "empty-str", "ws-str", "int-entry", "bool-entry", "empty-list"],
)
def test_malformed_rule_categories_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_support_rules([_rule(categories=bad)])


def test_unknown_rule_key_is_rejected():
    rule = _rule()
    rule["unit_scale"] = 100.0

    with pytest.raises(ValueError, match="unknown support rules\\[0\\] key"):
        validate_support_rules([rule])


def test_missing_rule_key_is_rejected():
    for key in ("rule_id", "categories", "support_mode", "source", "physical_contact_required"):
        rule = _rule()
        del rule[key]

        with pytest.raises(ValueError, match=f"missing: {key}"):
            validate_support_rules([rule])


@pytest.mark.parametrize("bad", [None, "x", 3, {}, ()], ids=["none", "str", "int", "dict", "tuple"])
def test_non_sequence_rules_container_is_rejected(bad):
    if bad == ():
        with pytest.raises(ValueError, match="must not be empty"):
            validate_support_rules(bad)
        return

    with pytest.raises(ValueError, match="must be a list or tuple"):
        validate_support_rules(bad)


def test_empty_rule_set_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        validate_support_rules([])


@pytest.mark.parametrize("bad", ["x", 3, None], ids=["str", "int", "none"])
def test_non_mapping_rule_is_rejected(bad):
    with pytest.raises(ValueError, match="must be a mapping"):
        validate_support_rules([bad])


def test_validator_returns_a_new_container():
    normalized = validate_support_rules(policy_module.SUPPORT_RULES)

    normalized[0]["categories"].append("injected")
    normalized[0]["support_mode"] = "ceiling"

    # The module constant and the live index are unaffected.
    assert _mode("chair") == "floor"
    assert "injected" not in dict(
        (rule["rule_id"], rule) for rule in policy_module.SUPPORT_RULES
    )["floor_support_measured"]["categories"]


# ---------------------------------------------------------------------------
# real-registry tests (the TEST reads the registry; production does not)
# ---------------------------------------------------------------------------

def _registry_categories():
    if not REGISTRY_PATH.is_file():
        pytest.skip(f"3D-FUTURE asset registry absent at {REGISTRY_PATH}")

    with REGISTRY_PATH.open("r", encoding="utf-8") as registry_file:
        assets = json.load(registry_file)["assets"]

    return sorted({asset.get("category") for asset in assets if isinstance(asset.get("category"), str)})


def test_real_registry_floor_rule_test():
    categories = [category for category in _registry_categories() if category.strip()]
    floor = [category for category in categories if _mode(category) == "floor"]

    assert floor, "no rule-backed floor category found in the real registry"
    assert {"chair", "cabinet", "table", "shelf"} <= set(floor)

    for category in floor:
        contract = _resolve(category)
        assert contract["support"]["status"] == "resolved"
        assert contract["physical_validation"]["contact_target"] == "floor"
        assert contract["semantics"]["floor_snap_applied"] is False


def test_real_registry_ceiling_rule_test():
    categories = [category for category in _registry_categories() if category.strip()]
    ceiling = [category for category in categories if _mode(category) == "ceiling"]

    if not ceiling:
        pytest.skip(
            "no ceiling-mounted category (pendant_lamp / ceiling_lamp) is "
            "present in the local 3D-FUTURE registry"
        )

    assert set(ceiling) == {"ceiling_lamp", "pendant_lamp"}

    for category in ceiling:
        contract = _resolve(category)
        assert contract["support"]["mode"] == "ceiling"
        assert contract["physical_validation"]["contact_target"] == "ceiling"
        assert contract["semantics"]["ceiling_snap_applied"] is False
        assert contract["semantics"]["floor_snap_applied"] is False


def test_real_registry_unclassified_categories_are_only_the_known_ones():
    """Every non-empty registry category is either rule-backed or deliberately
    unresolved - never silently misclassified."""

    categories = [category for category in _registry_categories() if category.strip()]
    unresolved = [
        category
        for category in categories
        if _resolve(category)["support"]["status"] == "unresolved"
    ]

    assert set(unresolved) <= {"wall_lamp", "hanging_chair"}
    assert len(categories) - len(unresolved) >= 40


def test_real_registry_empty_category_cannot_be_classified():
    """1751 real assets carry an empty category; the policy rejects it rather
    than inventing a support mode."""

    categories = _registry_categories()
    if "" not in categories:
        pytest.skip("no empty-category asset present in the local registry")

    with pytest.raises(ValueError, match="category must be a non-empty string"):
        _resolve("")
