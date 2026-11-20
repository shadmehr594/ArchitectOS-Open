from copy import deepcopy
import inspect

import pytest

from core.architecture.reasoning.architectural_precedent_experience_intelligence_v1 import (
    ArchitecturalExperienceMemoryV1,
    ArchitecturalPrecedentExperienceIntelligenceV1,
)


def project():
    return {
        "program": "residential",
        "climate": "hot_humid",
        "floor_count": 4,
        "unit_count": 8,
        "site": {"boundary": [[0, 0], [12, 0], [12, 20], [0, 20]], "access_types": ["street"]},
        "spatial_problems": ["residual_space", "weak_core_entry_relationship"],
        "design_goals": ["daylight", "circulation_hierarchy"],
        "requirements": [{"authority_class": "PROJECT_REQUIREMENT", "value": "eight_units"}],
        "regulations": [{"authority_class": "REGULATION", "value": "unresolved"}],
    }


def test_pipeline_is_deterministic_offline_and_does_not_mutate_input():
    data = project(); before = deepcopy(data); engine = ArchitecturalPrecedentExperienceIntelligenceV1()
    first = engine.run(project=data); second = engine.run(project=data)
    assert first == second
    assert data == before and first["input_mutated"] is False
    assert first["offline_first"] is True and first["similar_cases"]
    assert first["pipeline"] == list(engine.PIPELINE)


def test_precedent_is_abstract_and_never_regulatory_or_geometry_copying():
    result = ArchitecturalPrecedentExperienceIntelligenceV1().run(project=project())
    assert result["policy"]["geometric_copying"] is False
    assert result["policy"]["precedent_may_resolve_regulation"] is False
    assert all(p["authority_class"] == "PRECEDENT_NON_REGULATORY" for p in result["design_patterns"])
    assert all(h["geometry"] is None for h in result["design_hypotheses"])
    for analysis in result["precedent_analyses"]:
        assert {"problems", "design_moves", "reasoning", "outcomes", "trade_offs"} <= set(analysis)


def test_provenance_classes_remain_separate_and_feedback_is_explicit():
    result = ArchitecturalPrecedentExperienceIntelligenceV1().run(
        project=project(), feedback={"decision": "retain", "reason": "clearer_entry"}
    )
    assert set(result["policy"]["provenance_classes"]) == {
        "REGULATION", "PROJECT_REQUIREMENT", "HUMAN_FEEDBACK", "PRECEDENT_NON_REGULATORY"
    }
    assert result["human_feedback"]["authority_class"] == "HUMAN_FEEDBACK"
    assert any(p["authority_class"] == "HUMAN_FEEDBACK" for p in result["experience_memory"]["pattern_knowledge"])


def test_memory_is_audit_friendly_and_never_updates_opaque_weights():
    result = ArchitecturalPrecedentExperienceIntelligenceV1().run(
        project=project(), memory=ArchitecturalExperienceMemoryV1()
    )
    memory = result["experience_memory"]
    assert memory["learning_mechanism"] == ["case_memory", "pattern_knowledge", "performance_statistics"]
    assert memory["opaque_model_weight_update"] is False
    assert len(memory["case_memory"]) == len(memory["performance_statistics"]) == 1


def test_agi_adapter_receives_only_abstract_hypotheses_and_cannot_mutate_result():
    received = []
    def adapter(hypotheses):
        received.extend(deepcopy(hypotheses)); hypotheses.clear()
        return {"status": "ADAPTER_EXECUTED", "winner": None}
    result = ArchitecturalPrecedentExperienceIntelligenceV1().run(project=project(), agi_reasoner=adapter)
    assert received and result["design_hypotheses"]
    assert result["agi_spatial_reasoning"]["status"] == "ADAPTER_EXECUTED"


def test_no_project_or_named_shape_hardcode_in_engine():
    source = inspect.getsource(ArchitecturalPrecedentExperienceIntelligenceV1).lower()
    for forbidden in ("parcel2", "parcel 2", "pentagon", "octagon", "ellipse", "fixed_angle", "fixed_radius"):
        assert forbidden not in source


def test_invalid_authority_or_copyable_geometry_is_rejected():
    base = {"id": "X", "retrieval_tags": [], "problems": [], "design_moves": [], "reasoning": [], "outcomes": [], "trade_offs": []}
    with pytest.raises(ValueError):
        ArchitecturalPrecedentExperienceIntelligenceV1._validate_case(base | {"authority_class": "REGULATION"})
    with pytest.raises(ValueError):
        ArchitecturalPrecedentExperienceIntelligenceV1._validate_case(base | {"authority_class": "PRECEDENT_NON_REGULATORY", "geometry": {}})
