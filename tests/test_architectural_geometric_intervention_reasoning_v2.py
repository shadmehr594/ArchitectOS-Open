from copy import deepcopy
import inspect
import json
from pathlib import Path

from core.architecture.reasoning.architectural_geometric_intervention_reasoning_v2 import ArchitecturalGeometricInterventionReasoningV2


def scenario(kind="orthogonal", hierarchy=False):
    boundary = [[0, 0], [14, 0], [14, 10], [0, 10]]
    if kind == "oblique":
        boundary = [[0, 0], [14, 2], [12.6, 11.8], [-1.4, 9.8]]
    spaces = [
        {"id": "ENTRY", "use": "unresolved" if hierarchy else "foyer", "boundary": [[0, 0], [3, 0], [3, 2], [0, 2]], "privacy": "public"},
        {"id": "LIVING", "use": "living", "boundary": [[3, 0], [14, 0], [14, 5], [3, 5]], "privacy": "public"},
        {"id": "BED", "use": "bedroom", "boundary": [[0, 6], [5, 6], [4, 10], [0, 10]], "privacy": "private"},
        {"id": "CORE", "use": "core", "boundary": [[7, 6], [10, 6], [10, 10], [7, 10]], "privacy": "neutral"},
    ]
    return dict(plan_boundary=boundary, spaces=spaces,
                connections=[["ENTRY", "LIVING"], ["LIVING", "BED"], ["CORE", "ENTRY"]],
                exterior_edges=[[boundary[i], boundary[(i+1) % len(boundary)]] for i in range(len(boundary))],
                entrances=[[1, 0]])


def test_pipeline_determinism_and_no_mutation():
    data = scenario(); before = deepcopy(data); engine = ArchitecturalGeometricInterventionReasoningV2()
    assert engine.analyze(**data) == engine.analyze(**data)
    assert data == before and engine.analyze(**data)["input_mutated"] is False
    assert engine.analyze(**data)["pipeline"] == ["spatial_problem_detection", "dominant_geometry_detection", "intervention_scope", "geometric_operation_generation", "spatial_reallocation", "multi_criteria_evaluation"]


def test_no_shape_or_parcel_hardcode():
    text = inspect.getsource(ArchitecturalGeometricInterventionReasoningV2).lower()
    for forbidden in ("parcel2", "parcel 2", "pentagon", "five-sided", "fixed_radius", "fixed_angle"):
        assert forbidden not in text
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario())
    assert result["policy"]["shape_catalog_selection"] is False
    assert result["policy"]["fixed_vertex_count"] is False


def test_dominant_geometry_is_context_derived_and_oblique_envelope_is_respected():
    engine = ArchitecturalGeometricInterventionReasoningV2()
    normal = engine.analyze(**scenario())
    oblique = engine.analyze(**scenario("oblique"))
    assert normal["dominant_geometry"]["global"]["family"] == "context_orthogonal"
    assert oblique["dominant_geometry"]["global"]["axes"] != [[1.0, 0.0], [-0.0, 1.0]]
    assert oblique["dominant_geometry"]["global"]["source"] == "context_edges_weighted_by_length"


def test_scope_is_explicit_and_local_exception_does_not_change_global_language():
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario())
    assert {s["scope"] for s in result["intervention_scopes"]} <= {"local", "zone", "global"}
    assert result["policy"]["local_exception_may_remain_local"] is True
    assert result["dominant_geometry"]["global"]["family"] == "context_orthogonal"


def test_exception_gate_requires_justification_and_multi_problem_benefit():
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario(hierarchy=True))
    exceptional = [h for h in result["intervention_hypotheses"] if h["non_orthogonal_or_curved_exception"]]
    assert exceptional
    for h in exceptional:
        assert h["justification"]["not_style_or_named_shape"] is True
        assert h["justification_gate_passed"] == h["multi_problem_benefit"]
        assert h["eligible_for_human_review"] == h["justification_gate_passed"]


def test_spatial_reallocation_is_explicit_for_every_hypothesis():
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario())
    assert result["intervention_hypotheses"]
    assert all(h["spatial_reallocation"]["boundary_change_status"] == "hypothesis_only" for h in result["intervention_hypotheses"])
    assert all("delta_geometry" in h["spatial_reallocation"] for h in result["intervention_hypotheses"])


def test_topology_reorganization_can_be_generated_without_becoming_winner():
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario(hierarchy=True), max_hypotheses=30)
    topology = [h for h in result["intervention_hypotheses"] if h["operation"] == "reorganize_around_core"]
    assert topology and topology[0]["spatial_reallocation"]["topology_change"] is True
    assert topology[0]["spatial_reallocation"]["requires_whole_plan_revalidation"] is True
    assert result["selection"] == {"winner": None, "authoritative_ranking": False, "final_selection_performed": False}


def test_operation_vocabulary_and_precedent_authority():
    result = ArchitecturalGeometricInterventionReasoningV2().analyze(**scenario())
    required = {"shift_boundary", "rotate_boundary", "chamfer_corner", "widen_node", "bend_circulation", "curve_transition", "radial_distribute", "merge_residual_pocket", "align_neighboring_spaces", "relocate_doorway", "reshape_service_cluster", "reorganize_around_core"}
    assert required <= set(result["supported_operations"])
    path = Path(__file__).resolve().parents[1] / "core/architecture/contracts/architectural_geometric_intervention_precedent_v2.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence["authority_class"] == "PRECEDENT_NON_REGULATORY"
    assert evidence["may_resolve_regulatory_requirement"] is False
    assert evidence["may_select_a_shape"] is False
    assert len(evidence["observed_patterns"]) == 5
