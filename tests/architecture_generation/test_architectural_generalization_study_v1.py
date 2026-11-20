from copy import deepcopy

from core.architecture.reasoning.architectural_generalization_study_v1 import (
    CleanParcel2ResolveV1, IndependentGeneralizationStudyV1,
)
from core.architecture.reasoning.architectural_brain_orchestrator_v1 import (
    ArchitecturalBrainOrchestratorV1,
)


def test_independent_case_passes_every_acceptance_gate():
    result = IndependentGeneralizationStudyV1().run()
    assert result["phase_1_passed"]
    assert all(result["acceptance_assertions"].values())
    assert result["context"]["case_id"] == "SYNTHETIC-CORNER-MIXED-USE-01"
    assert len(result["context"]["site"]["frontages"]) == 2


def test_topology_change_regenerates_without_geometry_seed():
    result = IndependentGeneralizationStudyV1().run()
    before = {c["geometry_fingerprint"] for c in result["baseline_candidates"]}
    after = {c["geometry_fingerprint"] for c in result["regenerated_candidates"]}
    assert before.isdisjoint(after)
    for candidate in result["regenerated_candidates"]:
        brain = candidate["brain"]
        assert brain["topology_invalidation"]["dependency_scope"] == "WHOLE_BUILDING"
        assert brain["regeneration"]["mode"] == "from_requirements"
        assert not brain["regeneration_provenance"]["prior_geometry_used_as_seed"]


def test_daylight_zoning_critic_memory_and_capabilities_are_pre_geometry():
    result = IndependentGeneralizationStudyV1().run()
    assert result["early_daylight_deficit"]["new_daylight_source_required"]
    assert len(result["daylight_source_alternatives"]) >= 2
    assert result["critic_rejection_probe"]["architectural_critic"]["status"] == "revise"
    for candidate in result["regenerated_candidates"]:
        brain = candidate["brain"]
        assert set(("PUBLIC", "TRANSITION", "PRIVATE", "SERVICE")).issubset(brain["zoning"]["canonical_zones"])
        assert [x["capability"] for x in brain["execution_trace"]] == list(brain["reasoner_evidence"])
        assert not brain["stable_knowledge_mutated"]


def test_clean_parcel_gate_and_no_legacy_geometry_seed():
    study = IndependentGeneralizationStudyV1().run()
    site = deepcopy(study["context"]["site"])
    site["local_parcel_polygon"] = [[0, 0], [12, 0], [12, 26], [0, 26]]
    result = CleanParcel2ResolveV1().run(site, study["context"]["requirements"], study["phase_1_passed"])
    assert 1 <= len(result["shortlist"]) <= 3
    assert len({c["topology_family"] for c in result["shortlist"]}) == len(result["shortlist"])
    assert result["clean_context_source"] == "site_rules_program_only"
    assert not result["final_selection_performed"] and not result["room_layout_generated"]
    assert not result["final_windows_generated"] and not result["structure_executed"]
    assert all("spatial_reservation" in c for c in result["candidates"])
    assert all(c["spatial_reservation"]["gate_position"]=="before_scoring" for c in result["candidates"])
    assert all(c["hard_validation_status"]=="hard_valid" for c in result["shortlist"])
    assert not result["final_selection_performed"] and not result["room_layout_generated"]


def test_main_reasoner_trace_ignores_contextual_entries_but_is_exact():
    reasoners = list(ArchitecturalBrainOrchestratorV1.CAPABILITY_ORDER)
    contextual = [{"capability": "site_resource_map", "executed": True}]
    valid = contextual + [{"capability": name, "executed": True} for name in reasoners]
    predicate = IndependentGeneralizationStudyV1.all_main_reasoners_executed
    assert predicate(valid)
    assert not predicate(valid[:-1])
    assert not predicate(valid + [{"capability": reasoners[-1], "executed": True}])
    assert not predicate(contextual + [{"capability": name, "executed": True}
                                       for name in reversed(reasoners)])
