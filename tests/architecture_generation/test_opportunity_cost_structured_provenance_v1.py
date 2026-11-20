from copy import deepcopy

from core.architecture.reasoning.opportunity_cost_evaluator_v1 import OpportunityCostEvaluatorV1


def _plan(evidence):
    return {"hypotheses": [{
        "hypothesis_id": "allocation-1",
        "assignments": [
            {"function_id": "a", "resource_id": "resource", "utility": 2.0, "evidence": evidence},
            {"function_id": "b", "resource_id": "resource", "utility": 1.0, "evidence": evidence},
        ],
        "unresolved_demands": [],
        "resource_consumption": {"resource": 2.0},
    }]}


def test_structured_provenance_is_preserved_deduplicated_and_deterministic():
    records = [
        "scalar",
        {"contract": "EvidenceV1", "nested": {"paths": ["a", {"index": 1}]}},
        {"nested": {"paths": ["a", {"index": 1}]}, "contract": "EvidenceV1"},
        {"contract": "EvidenceV1", "nested": {"paths": ["a", {"index": 2}]}},
        "scalar",
    ]
    before = deepcopy(records)
    evaluator = OpportunityCostEvaluatorV1()
    first = evaluator.evaluate(_plan(records), {"functions": []})
    second = evaluator.evaluate(_plan(records), {"functions": []})
    expected = [records[0], records[1], records[3]]
    assert first["alternatives"][0]["evidence"] == expected
    assert second["alternatives"][0]["evidence"] == expected
    assert isinstance(first["alternatives"][0]["evidence"][1], dict)
    assert records == before
    first["alternatives"][0]["evidence"][1]["nested"]["paths"].append("changed")
    assert records == before
