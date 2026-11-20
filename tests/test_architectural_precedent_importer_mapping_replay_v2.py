from copy import deepcopy
import inspect

import pytest

from core.architecture.reasoning.architectural_precedent_importer_mapping_replay_v2 import (
    ContextualDesignMoveMapperV2, PrecedentReplayGateV2, ValidatedPrecedentImporterV2,
)


def raw(reference="case-a", authority="PRECEDENT_NON_REGULATORY"):
    return {
        "source": {"reference": reference, "content_digest": "abc"},
        "authority_class": authority,
        "context": {"context_id": "ctx-a", "scope": "entry_distribution",
                    "dominant_geometry": ["context_axis_conforming"]},
        "knowledge": {
            "problem": ["residual_space", "door_distribution_conflict"],
            "constraints": ["rooms_cannot_shift", "preserve_usable_area"],
            "design_move": ["reshape_local_distribution_zone"],
            "reasoning": ["one local intervention can coordinate several thresholds"],
            "outcome": ["residual_space", "door_access", "circulation_legibility"],
            "trade_off": ["local_dimensional_revalidation"],
            "applicability": ["context_axis_conforming", "local_exception_only"],
        },
    }


def test_all_source_kinds_normalize_deterministically_without_mutation():
    importer = ValidatedPrecedentImporterV2()
    for kind in ("local", "manual", "online", "image_plan_analysis"):
        data = raw(kind); before = deepcopy(data)
        assert importer.import_case(data, source_kind=kind) == importer.import_case(data, source_kind=kind)
        assert data == before
        assert importer.import_case(data, source_kind=kind)["source"]["kind"] == kind


def test_binding_authority_and_transferable_geometry_fail_closed():
    importer = ValidatedPrecedentImporterV2()
    with pytest.raises(ValueError): importer.import_case(raw(authority="REGULATION"), source_kind="local")
    data = raw(); data["knowledge"]["geometry"] = [[0, 0]]
    with pytest.raises(ValueError): importer.import_case(data, source_kind="image_plan_analysis")


def test_source_geometry_is_discarded_not_transferred():
    data = raw(); data["geometry"] = {"vertices": [[0, 0], [1, 0]]}
    case = ValidatedPrecedentImporterV2().import_case(data, source_kind="image_plan_analysis")
    assert case["contains_transferable_geometry"] is False
    assert "geometry" not in case and case["normalization_audit"]["discarded_source_geometry"] is True


def test_human_feedback_remains_context_specific():
    case = ValidatedPrecedentImporterV2().import_case(raw(authority="HUMAN_FEEDBACK"), source_kind="manual")
    assert case["human_feedback_policy"] == {"context_specific": True, "general_rule": False,
                                               "context_id": "ctx-a", "scope": "entry_distribution"}


def test_mapping_uses_context_and_is_non_authoritative_with_defensive_adapter():
    pattern = ValidatedPrecedentImporterV2().import_case(raw(), source_kind="local")
    received = []
    def adapter(payload):
        received.append(deepcopy(payload)); payload["candidates"].clear(); return {"status": "RECEIVED", "winner": None}
    context = {"problems": ["residual_space", "door_distribution_conflict"],
               "constraints": ["rooms_cannot_shift"], "dominant_geometry": ["context_axis_conforming"],
               "goals": ["door_access", "circulation_legibility"]}
    result = ContextualDesignMoveMapperV2().map(project_context=context, patterns=[pattern], agi_adapter=adapter)
    assert result["candidates"] and received and result["winner"] is None
    evidence = result["candidates"][0]["applicability_evidence"]
    assert evidence["matched_constraints"] and evidence["dominant_geometry_compatibility"]
    assert len(evidence["multi_problem_benefit"]) >= 2


def test_replay_hides_geometry_and_recovers_appropriate_move():
    importer = ValidatedPrecedentImporterV2()
    learned = importer.import_case(raw("training"), source_kind="local")
    held = importer.import_case(raw("held-out"), source_kind="image_plan_analysis")
    result = PrecedentReplayGateV2().run(held_out_case=held, learned_patterns=[learned])
    assert result["status"] == "PASS"
    assert result["geometry_visible_to_reasoning"] is False
    assert result["exact_geometry_reconstruction_attempted"] is False
    assert result["expected_overlap"] == ["reshape_local_distribution_zone"]


def test_offline_no_hardcode_and_provenance_isolation():
    source = inspect.getsource(ValidatedPrecedentImporterV2).lower() + inspect.getsource(ContextualDesignMoveMapperV2).lower()
    for forbidden in ("parcel2", "dead_space\u2192angled_wall", "pentagon", "fixed_radius", "fixed_angle"):
        assert forbidden not in source
    case = ValidatedPrecedentImporterV2().import_case(raw(), source_kind="online")
    assert case["source"]["online_optional_enrichment"] is True
    assert case["authority_class"] == "PRECEDENT_NON_REGULATORY"
