"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01I baseline adapter acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from core.architecture.contracts.architectural_change_window_daylight_contracts_v1 import (
    WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
)
from core.architecture.reasoning import architectural_change_baseline_adapter_v1 as adapter_module
from core.architecture.reasoning.architectural_change_baseline_adapter_v1 import (
    adapt_accepted_baseline_for_architectural_change,
)
from core.architecture.reasoning.architectural_change_adjacency_topology_realizer_v1 import (
    realize_selected_adjacency_topology_strategy,
)
from core.architecture.reasoning.architectural_change_multi_realizer_transaction_coordinator_v1 import (
    execute_multi_realizer_transaction,
)
from core.architecture.reasoning.architectural_change_opening_access_realizer_v1 import (
    realize_selected_opening_access_strategy,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)
from core.architecture.geometry.space_boundary_opening_host_graph_engine_v1 import (
    BoundaryExtractionResult,
)


HERE = Path(__file__).resolve().parent
GRAPH_KEYS = (
    "space_boundary_graphs",
    "wall_face_graphs",
    "wall_solid_graphs",
    "opening_host_graphs",
    "access_graph",
)


def _support(filename: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, HERE / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multi = _support(
    "test_architectural_change_multi_realizer_transaction_coordinator_v1.py",
    "_01i_multi_support",
)
end_to_end = _support(
    "test_architectural_change_end_to_end_acceptance_v1.py",
    "_01i_semantic_support",
)
daylight = _support(
    "test_architectural_change_window_daylight_realizer_v1.py",
    "_01i_daylight_support",
)


def _canonical_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _accepted_envelope(*, daylight_complete: bool = False):
    source = daylight._candidate() if daylight_complete else multi._candidate()
    source.pop("candidate_hash", None)
    extraction = {"source_semantic_hash": "geometry-kernel-controlled-fixture"}
    for key in GRAPH_KEYS:
        if key in source:
            extraction[key] = source.pop(key)
    source["boundary_extraction"] = extraction
    source["acceptance_evidence"] = {
        "status": "ACCEPTED",
        "source": "controlled_01i_contract_fixture",
    }
    source["candidate_hash"] = candidate_semantic_hash(source)
    return source


def _adapt(*, daylight_complete: bool = False):
    baseline = _accepted_envelope(daylight_complete=daylight_complete)
    result = adapt_accepted_baseline_for_architectural_change(baseline)
    assert result["parent_candidate"] is not None
    return baseline, result, result["parent_candidate"]


def test_a_valid_accepted_baseline_envelope_adapts_successfully():
    baseline, result, parent = _adapt()
    assert result["schema_version"] == adapter_module.ADAPTER_VERSION
    assert result["baseline_identity"]["stored_hash_verified"] is True
    assert parent["candidate_id"] == baseline["candidate_id"]
    assert parent["candidate_version"] == baseline["candidate_version"]


def test_b_raw_boundary_extraction_without_accepted_envelope_is_rejected_structurally():
    raw = deepcopy(_accepted_envelope()["boundary_extraction"])
    result = adapt_accepted_baseline_for_architectural_change(raw)
    assert result["parent_candidate"] is None
    assert {gap["classification"] for gap in result["readiness_gaps"]} == {"BASELINE_CONTRACT_GAP"}
    assert {gap["code"] for gap in result["readiness_gaps"]} == {"ACCEPTED_BASELINE_ENVELOPE_REQUIRED"}

    raw_object = BoundaryExtractionResult(
        source_file="fixture.dxf",
        source_sha256="source-hash",
        semantic_length_unit="METER",
        geometry_scale_applied=False,
        tolerance_audit={},
        wall_face_graphs={},
        wall_solid_graphs={},
        opening_host_graphs={},
        space_boundary_graphs={},
        access_graph={},
        label_bindings=[],
        unresolved=[],
    )
    object_result = adapt_accepted_baseline_for_architectural_change(raw_object)
    assert object_result["parent_candidate"] is None
    assert object_result["readiness_gaps"] == [{
        "classification": "BASELINE_CONTRACT_GAP",
        "code": "ACCEPTED_BASELINE_ENVELOPE_REQUIRED",
        "received_type": "BoundaryExtractionResult",
    }]


def test_c_stale_stored_hash_is_rejected_without_adaptation():
    baseline = _accepted_envelope()
    baseline["candidate_hash"] = "0" * 64
    result = adapt_accepted_baseline_for_architectural_change(baseline)
    assert result["parent_candidate"] is None
    gap = result["readiness_gaps"][0]
    assert gap["code"] == "accepted_baseline_hash_mismatch"
    assert gap["classification"] == "TRUE_BLOCKER"


def test_d_accepted_identity_version_and_hash_are_preserved_and_verified_in_lineage():
    baseline, result, parent = _adapt()
    identity = result["baseline_identity"]
    assert identity["candidate_id"] == baseline["candidate_id"] == parent["candidate_id"]
    assert identity["candidate_version"] == baseline["candidate_version"] == parent["candidate_version"]
    assert identity["accepted_baseline_hash"] == baseline["candidate_hash"]
    assert parent["baseline_lineage"]["accepted_baseline_hash"] == baseline["candidate_hash"]
    assert parent["candidate_hash"] == identity["change_parent_hash"] == candidate_semantic_hash(parent)


def test_e_graphs_are_lifted_once_without_geometry_invention_or_id_rewriting():
    baseline, _, parent = _adapt()
    extraction = baseline["boundary_extraction"]
    assert "boundary_extraction" not in parent
    for key in GRAPH_KEYS:
        if key in extraction:
            assert parent[key] == extraction[key]
    source_ids = {item["space_id"] for item in extraction["space_boundary_graphs"]["R1"]["spaces"]}
    parent_ids = {item["space_id"] for item in parent["space_boundary_graphs"]["R1"]["spaces"]}
    assert parent_ids == source_ids


def test_f_semantic_snapshot_contains_only_present_evidence_and_no_orientation_guess():
    _, result, _ = _adapt()
    snapshot = result["semantic_snapshot"]
    assert snapshot["spaces"] and snapshot["relations"] and snapshot["openings"]
    assert "orientation" not in snapshot and "site_orientation" not in snapshot
    assert snapshot["daylight_evidence_available"] is False
    assert "site_orientation_evidence" in snapshot["unresolved_dependencies"]


def test_g_readiness_gaps_classify_caller_and_missing_baseline_evidence():
    _, result, _ = _adapt()
    pairs = {(item["classification"], item["code"]) for item in result["readiness_gaps"]}
    assert ("EXPECTED_CALLER_EVIDENCE", "explicit_strategy_selection_required") in pairs
    assert ("EXPECTED_CALLER_EVIDENCE", "realizer_specific_execution_binding_required") in pairs
    assert ("BASELINE_CONTRACT_GAP", "canonical_graph_missing:wall_face_graphs") in pairs
    assert ("BASELINE_CONTRACT_GAP", "canonical_graph_missing:wall_solid_graphs") in pairs


def test_h_original_baseline_remains_byte_and_semantically_equivalent():
    baseline = _accepted_envelope()
    before = deepcopy(baseline)
    before_bytes = _canonical_bytes(baseline)
    before_hash = candidate_semantic_hash(baseline)
    adapt_accepted_baseline_for_architectural_change(baseline)
    assert baseline == before
    assert _canonical_bytes(baseline) == before_bytes
    assert candidate_semantic_hash(baseline) == before_hash


def test_i_same_input_produces_same_result_and_change_parent_hash():
    baseline = _accepted_envelope()
    first = adapt_accepted_baseline_for_architectural_change(baseline)
    second = adapt_accepted_baseline_for_architectural_change(deepcopy(baseline))
    assert first == second
    assert first["parent_candidate"]["candidate_hash"] == second["parent_candidate"]["candidate_hash"]


def test_j_json_round_trip_is_stable():
    result = adapt_accepted_baseline_for_architectural_change(_accepted_envelope())
    document = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    loaded = json.loads(document)
    assert loaded == result
    assert json.dumps(loaded, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == document


def test_k_snapshot_is_consumed_read_only_by_01b_through_01e():
    _, result, _ = _adapt()
    snapshot = result["semantic_snapshot"]
    before = deepcopy(snapshot)
    intent = end_to_end._kitchen_intent()
    impact, plan, readiness, generation = end_to_end._run_semantic_chain(intent, snapshot)
    assert impact.change_intent_id == intent.change_intent_id
    assert plan.intent_id == intent.change_intent_id
    assert readiness.plan_id == plan.plan_id
    assert generation.plan_id == plan.plan_id
    assert snapshot == before


def test_l_simple_01f_a_path_commits_derived_candidate_without_parent_mutation():
    _, _, parent = _adapt()
    before = deepcopy(parent)
    strategies = (multi._bundle()[0],)
    plan = multi._plan(parent, strategies, steps=("SPACE_BOUNDARY_REALIZATION",), dependencies=())
    final, result = execute_multi_realizer_transaction(plan, strategies, multi._readiness(strategies), parent)
    assert final is not None and result.commit_status == "COMMITTED"
    assert parent == before
    assert final["baseline_lineage"] == parent["baseline_lineage"]


def test_m_01f_b_contract_succeeds_with_explicit_caller_execution_evidence():
    _, _, parent = _adapt()
    strategy = multi._bundle()[1]
    readiness = multi._readiness((strategy,))[strategy.strategy_id]
    derived, result = realize_selected_adjacency_topology_strategy(
        strategy,
        readiness,
        parent,
        expected_parent_id=parent["candidate_id"],
        expected_parent_version=parent["candidate_version"],
        expected_parent_hash=parent["candidate_hash"],
    )
    assert derived is not None and result.status == "REALIZED"


def test_n_01f_c_contract_succeeds_after_explicit_01f_b_evidence():
    _, _, parent = _adapt()
    topology, opening = multi._bundle()[1:]
    topology_ready = multi._readiness((topology,))[topology.strategy_id]
    topology_parent, topology_result = realize_selected_adjacency_topology_strategy(
        topology,
        topology_ready,
        parent,
        expected_parent_id=parent["candidate_id"],
        expected_parent_version=parent["candidate_version"],
        expected_parent_hash=parent["candidate_hash"],
    )
    assert topology_parent is not None and topology_result.status == "REALIZED"
    opening_ready = multi._readiness((opening,))[opening.strategy_id]
    derived, result = realize_selected_opening_access_strategy(
        opening,
        opening_ready,
        topology_parent,
        expected_parent_id=topology_parent["candidate_id"],
        expected_parent_version=topology_parent["candidate_version"],
        expected_parent_hash=topology_parent["candidate_hash"],
    )
    assert derived is not None and result.status == "REALIZED"


def test_o_01f_d_commits_once_and_later_failure_rolls_back_all_or_nothing():
    _, _, parent = _adapt()
    before = deepcopy(parent)
    success_strategies = multi._bundle()
    success_plan = multi._plan(parent, success_strategies)
    final, committed = execute_multi_realizer_transaction(
        success_plan, success_strategies, multi._readiness(success_strategies), parent
    )
    assert final is not None and committed.commit_status == "COMMITTED"
    assert final["derivation"]["single_final_commit"] is True
    assert final["derivation"]["intermediate_candidates_committed"] is False
    assert parent == before

    failing_strategies = multi._bundle(fail_c=True)
    failing_plan = multi._plan(parent, failing_strategies)
    rejected, rolled_back = execute_multi_realizer_transaction(
        failing_plan, failing_strategies, multi._readiness(failing_strategies), parent
    )
    assert rejected is None and rolled_back.commit_status == "REJECTED_STEP_FAILURE"
    assert parent == before


def test_p_01h_missing_orientation_is_not_guessed_and_rejects_existing_way():
    _, result, parent = _adapt(daylight_complete=True)
    assert "site_orientation" not in result["semantic_snapshot"]
    evidence = daylight._evidence(
        orientation_required=True,
        daylight_goal={"goal": "improve_solar_daylight_performance", "requires_orientation": True},
    )
    derived, daylight_result = daylight._run(parent, daylight._strategy(evidence=evidence))
    assert derived is None
    assert daylight_result.status == WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE
    assert daylight_result.failures == ("site_orientation_evidence_required_but_missing",)
    assert daylight_result.provenance["orientation_inferred"] is False


def test_q_final_derived_lineage_points_to_original_accepted_baseline():
    baseline, _, parent = _adapt()
    strategies = (multi._bundle()[0],)
    plan = multi._plan(parent, strategies, steps=("SPACE_BOUNDARY_REALIZATION",), dependencies=())
    final, result = execute_multi_realizer_transaction(plan, strategies, multi._readiness(strategies), parent)
    assert final is not None and result.commit_status == "COMMITTED"
    assert final["baseline_lineage"]["accepted_baseline_candidate_id"] == baseline["candidate_id"]
    assert final["baseline_lineage"]["accepted_baseline_hash"] == baseline["candidate_hash"]


def test_r_missing_or_unresolved_evidence_never_becomes_fake_success():
    baseline = _accepted_envelope()
    baseline["boundary_extraction"]["access_graph"]["status"] = "UNRESOLVED"
    baseline["candidate_hash"] = candidate_semantic_hash(baseline)
    result = adapt_accepted_baseline_for_architectural_change(baseline)
    snapshot = result["semantic_snapshot"]
    assert snapshot["adjacency_available"] is False
    assert snapshot["topology_available"] is False
    assert snapshot["evidence_status"] == "partial"
    assert any(
        gap["code"] == "canonical_access_graph_not_verified_resolved"
        for gap in result["readiness_gaps"]
    )


def test_s_adapter_has_no_forbidden_dependencies_or_hidden_fixture_imports():
    source = Path(adapter_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = (
        "tests", "fixture", "chat", "llm", "memory", "voice", "provider",
        "render", "comfy", "bim", "ifc", "structure",
    )
    assert not any(token in document for token in forbidden)


def test_conflicting_envelope_aliases_and_duplicate_graph_sources_are_rejected():
    baseline = _accepted_envelope()
    baseline["id"] = "different-id"
    baseline["candidate_hash"] = candidate_semantic_hash(baseline)
    result = adapt_accepted_baseline_for_architectural_change(baseline)
    assert result["parent_candidate"] is None
    assert any(gap["code"] == "accepted_baseline_identity_alias_conflict" for gap in result["readiness_gaps"])

    baseline = _accepted_envelope()
    baseline["space_boundary_graphs"] = {"R1": {"floor": "R1", "spaces": []}}
    baseline["candidate_hash"] = candidate_semantic_hash(baseline)
    result = adapt_accepted_baseline_for_architectural_change(baseline)
    assert result["parent_candidate"] is None
    assert result["readiness_gaps"][0]["code"] == "ambiguous_root_and_boundary_extraction_graphs"
