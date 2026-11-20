"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01A contract acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import inspect

import pytest

from core.architecture.contracts import architectural_change_contracts_v1 as module
from core.architecture.contracts.architectural_change_contracts_v1 import (
    CHANGE_CONTRACT_REGISTRY,
    ArchitecturalChangeIntent,
    DesignChangeImpact,
    DesignRevisionRecord,
    DesignVariant,
    dumps_contract,
    loads_contract,
    serialize_contract,
)


@pytest.fixture(
    params=(
        {
            "change_intent_id": "intent-kitchen-grow",
            "change_type": "resize_space",
            "targets": ("space:kitchen",),
            "direction": "increase",
            "preference": "larger_area",
            "priority": "high",
            "hard_constraints": ("program_complete",),
            "soft_objectives": ("kitchen_usability",),
            "preserve_constraints": ("external_footprint",),
            "user_text": "آشپزخانه رو بزرگ‌تر کن",
        },
        {
            "change_intent_id": "intent-master-near-bath",
            "change_type": "change_relation",
            "targets": ("space:master_bedroom", "space:bathroom"),
            "direction": "closer",
            "preference": "proximity",
            "priority": "normal",
            "hard_constraints": ("program_complete",),
            "soft_objectives": ("master_bathroom_proximity",),
            "preserve_constraints": ("private_zone",),
            "user_text": "مستر رو به حمام نزدیک‌تر کن",
        },
        {
            "change_intent_id": "intent-living-daylight",
            "change_type": "improve_quality",
            "targets": ("space:living",),
            "direction": "increase",
            "preference": "daylight",
            "priority": "normal",
            "hard_constraints": ("program_complete",),
            "soft_objectives": ("living_daylight",),
            "preserve_constraints": ("privacy",),
            "user_text": "پذیرایی نور بیشتری بگیره",
        },
    ),
    ids=("kitchen_larger", "master_closer_to_bathroom", "living_more_daylight"),
)
def intent(request):
    return ArchitecturalChangeIntent(
        **request.param,
        provenance={"source": "user", "language": "fa", "interpreted_by": "test"},
    )


def test_three_intents_construct_and_round_trip_stably(intent):
    first = dumps_contract(intent)
    restored = loads_contract(first)

    assert restored == intent
    assert dumps_contract(restored) == first
    assert serialize_contract(intent)["contract_type"] == "ArchitecturalChangeIntent"


def test_contracts_never_mutate_candidate_geometry(intent):
    geometry = {
        "candidate_id": "candidate-01",
        "spaces": [{"space_id": "space:kitchen", "polygon": [[0, 0], [2, 0], [2, 3]]}],
        "wall_graph": [{"edge": [[0, 0], [2, 0]]}],
    }
    before = deepcopy(geometry)

    impact = DesignChangeImpact(
        change_intent_id=intent.change_intent_id,
        affected_spaces=intent.targets,
        required_rechecks=("program_count", "topology", "quality_gate"),
        risk_flags=("impact_not_calculated",),
    )
    variant = DesignVariant(
        parent_candidate_id=geometry["candidate_id"],
        change_intent_id=intent.change_intent_id,
        variant_id=f"variant:{intent.change_intent_id}",
        preserved_constraints=intent.preserve_constraints,
        provenance={"phase": "01A", "geometry_created": False},
    )
    serialize_contract(impact)
    serialize_contract(variant)

    assert geometry == before
    assert not hasattr(variant, "geometry")
    assert not hasattr(impact, "geometry")


def test_module_has_only_standard_library_dependencies():
    tree = ast.parse(inspect.getsource(module))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots <= {"__future__", "copy", "dataclasses", "json", "typing"}
    source = inspect.getsource(module).lower()
    assert "housediffusion" not in source
    assert "gsdiff" not in source


def test_revision_lineage_and_nested_intent_round_trip(intent):
    parent = DesignRevisionRecord(
        revision_id="revision-01",
        parent_revision_id=None,
        child_revision_ids=("revision-02",),
        user_request="طرح اولیه را حفظ کن",
        interpreted_intent=intent,
        affected_entities=(),
        quality_result={"status": "baseline"},
        user_approval_status="approved",
    )
    child = DesignRevisionRecord(
        revision_id="revision-02",
        parent_revision_id=parent.revision_id,
        child_revision_ids=(),
        user_request=intent.user_text,
        interpreted_intent=intent,
        affected_entities=intent.targets,
        quality_result={"status": "not_evaluated", "geometry_changed": False},
        user_approval_status="pending",
    )

    restored_parent = loads_contract(dumps_contract(parent))
    restored_child = loads_contract(dumps_contract(child))

    assert restored_parent.child_revision_ids == (restored_child.revision_id,)
    assert restored_child.parent_revision_id == restored_parent.revision_id
    assert restored_child.interpreted_intent == intent


def test_registry_exposes_active_versioned_contract_set():
    assert CHANGE_CONTRACT_REGISTRY.contract_types == (
        "AdjacencyRealizationResult",
        "ArchitecturalChangeIntent",
        "ArchitecturalChangeStrategy",
        "DeclarativeChangePlan",
        "DesignChangeImpact",
        "DesignRevisionRecord",
        "DesignVariant",
        "ExecutionReadinessResult",
        "GeometryDelta",
        "GeometryRealizationResult",
        "MultiRealizerTransactionPlan",
        "MultiRealizerTransactionResult",
        "OpeningAccessDelta",
        "OpeningAccessRealizationResult",
        "StrategyGenerationResult",
        "TopologyDelta",
        "TransactionStepResult",
    )


def test_revision_rejects_self_parent_or_child(intent):
    with pytest.raises(ValueError, match="own parent"):
        DesignRevisionRecord(
            revision_id="revision-01",
            parent_revision_id="revision-01",
            child_revision_ids=(),
            user_request=intent.user_text,
            interpreted_intent=intent,
        )
    with pytest.raises(ValueError, match="own child"):
        DesignRevisionRecord(
            revision_id="revision-01",
            parent_revision_id=None,
            child_revision_ids=("revision-01",),
            user_request=intent.user_text,
            interpreted_intent=intent,
        )
