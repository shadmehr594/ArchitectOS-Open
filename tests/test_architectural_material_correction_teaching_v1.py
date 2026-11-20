# -*- coding: utf-8 -*-
"""CPU-only material-correction to human-teaching regressions.

All persistence assertions use pytest's isolated temporary directory. No real
learning ledger, model, renderer, segmenter, mask, network, BIM or CAD path is
reachable from this file.
"""

from __future__ import annotations

import copy
import inspect

import pytest

from core.architecture.knowledge.human_learning_ledger_v1 import (
    accepted_rules,
    load_ledger,
)
from core.vision.architectural_material_knowledge_connection_v1 import (
    admit_confirmed_material_correction,
    build_architectural_material_knowledge_connection,
    open_material_correction_review,
)
from core.vision.vision_report_v1 import render_vision_report


CORRECTION = "The material you identified as travertine is actually marble."


def _observation(material="travertine"):
    return {
        "contract": "ArchitecturalObservationV1",
        "material_observations": [
            {
                "descriptor": "cream %s facade cladding" % material,
                "materials": [material],
                "evidence_phrase": "cream %s facade cladding" % material,
                "confidence": "MEDIUM",
            }
        ],
        "provenance": {
            "provider": "SYNTHETIC_TEST_FIXTURE",
            "model": "NONE",
            "image_id": "SYNTHETIC-TRAVERTINE-CORRECTION",
            "source_type": "test_fixture",
        },
    }


def _connection(text=CORRECTION, material="travertine"):
    return build_architectural_material_knowledge_connection(
        _observation(material), text
    )


def _report(connection):
    return render_vision_report(
        {
            "space_type": "facade",
            "confidence": "MEDIUM",
            "observed_elements": [],
            "spatial_relations": [],
            "interpretations": [],
            "unknowns": [],
            "architectural_material_knowledge_connection": connection,
        },
        "en",
    )


def test_explicit_material_correction_is_recognized_not_replacement():
    connection = _connection()
    correction = connection["material_correction"]

    assert connection["status"] == "MATERIAL_CORRECTION_PENDING_CONFIRMATION"
    assert connection["architectural_interpretation"] is None
    assert correction["status"] == "PENDING_CONFIRMATION"
    assert correction["previous_observation"]["ontology_id"] == "travertine"
    assert correction["corrected_material"]["ontology_id"] == "marble"


def test_original_observation_and_provenance_are_preserved_without_mutation():
    observation = _observation()
    before = copy.deepcopy(observation)

    connection = build_architectural_material_knowledge_connection(
        observation, CORRECTION
    )

    assert observation == before
    assert connection["observed_facts"]["provenance"] == before["provenance"]
    previous = connection["material_correction"]["previous_observation"]
    assert previous["descriptor"] == "cream travertine facade cladding"
    assert previous["observation_confidence"] == "MEDIUM"
    assert previous["verification"] == "UNVERIFIED"


def test_correction_is_user_supplied_and_not_visual_evidence():
    correction = _connection()["material_correction"]

    assert correction["user_correction"] == {
        "source": "USER_CORRECTION",
        "verbatim": CORRECTION,
        "previous_material_term": "travertine",
        "corrected_material_term": "marble",
        "visually_observed": False,
    }
    assert correction["corrected_material"]["source"] == "USER_CORRECTION"
    assert correction["corrected_material"]["visually_observed"] is False


def test_pending_candidate_uses_existing_teaching_and_validation_owners():
    correction = _connection()["material_correction"]

    assert correction["teaching_candidate"]["contract"] == (
        "ArchitecturalTeachingCandidateV1"
    )
    assert correction["teaching_candidate"]["persistent"] is False
    assert correction["teaching_record"]["contract"] == (
        "ArchitecturalTeachingRecordV1"
    )
    assert correction["knowledge_candidate"]["contract"] == (
        "ArchitecturalKnowledgeExtractionCandidateV1"
    )
    assert correction["knowledge_candidate"]["scope"] == "CURRENT_PROJECT"
    assert correction["confirmation_review"]["contract"] == (
        "ArchitecturalKnowledgeReviewV1"
    )
    assert correction["confirmation_review"]["state"] == "pending_review"


def test_pending_candidate_does_not_persist(tmp_path):
    ledger = tmp_path / "isolated-material-correction-ledger.json"
    connection = _connection()

    assert connection["learned"] is False
    assert connection["material_correction"]["permanent_learning"] == {
        "status": "UNCHANGED",
        "persistent": False,
        "written": False,
    }
    assert load_ledger(str(ledger))["items"] == []
    assert not ledger.exists()


def test_explicit_rejection_leaves_isolated_ledger_unchanged(tmp_path):
    ledger = tmp_path / "isolated-material-correction-rejection.json"
    connection = _connection()
    review = open_material_correction_review(connection, language="en")

    review.reject("The correction is withdrawn.")

    assert review.state == "rejected"
    assert review.to_confirmed_entry() is None
    with pytest.raises(ValueError, match="explicitly confirmed"):
        admit_confirmed_material_correction(
            connection,
            review,
            path=str(ledger),
            confirmed_by="TEST_HUMAN",
        )
    assert load_ledger(str(ledger))["items"] == []
    assert not ledger.exists()


def test_explicit_confirmation_uses_existing_isolated_ledger_admission(tmp_path):
    ledger = tmp_path / "isolated-material-correction-confirmation.json"
    connection = _connection()
    review = open_material_correction_review(connection, language="en")

    review.confirm("Yes, record this project-specific correction.")
    record = admit_confirmed_material_correction(
        connection,
        review,
        path=str(ledger),
        confirmed_by="TEST_HUMAN",
    )

    assert record["provenance"] == "HUMAN_ACCEPTED_RULE"
    assert record["confirmed_by"] == "TEST_HUMAN"
    assert record["scope"] == "CURRENT_PROJECT"
    assert record["knowledge_kind"] == "PROJECT_MATERIAL_CORRECTION"
    assert record["corrected_material"]["ontology_id"] == "marble"
    assert record["previous_observation"]["ontology_id"] == "travertine"
    assert len(accepted_rules(str(ledger))) == 1


def test_ordinary_material_question_creates_no_teaching_candidate():
    connection = _connection("What material is visible?")

    assert connection["status"] == "NO_MATERIAL_REPLACEMENT"
    assert "material_correction" not in connection


def test_unsupported_or_unobserved_identity_creates_no_candidate():
    unsupported = _connection(
        "The material you identified as travertine is actually unobtainium."
    )
    mismatch = _connection(CORRECTION, material="brick")

    assert unsupported["status"] == "MATERIAL_CORRECTION_UNRESOLVED"
    assert unsupported["material_correction"]["teaching_candidate"] is None
    assert unsupported["material_correction"]["corrected_material"] is None
    assert mismatch["status"] == "MATERIAL_CORRECTION_SOURCE_NOT_OBSERVED"
    assert mismatch["material_correction"]["teaching_candidate"] is None


def test_spatial_and_execution_boundaries_remain_non_executable():
    connection = _connection()
    correction = connection["material_correction"]

    assert correction["spatial_grounding"] == {
        "status": "UNKNOWN",
        "coordinates": None,
        "mask": None,
        "grounded": False,
    }
    assert connection["execution_capability"]["status"] == "NOT_YET_AVAILABLE"
    assert connection["execution_capability"][
        "precise_facade_material_transfer"
    ] is False
    assert connection["execution_capability"]["authorized"] is False


def test_pending_correction_is_reported_without_execution_or_inference():
    connection = _connection()
    report = _report(connection)

    assert "Material correction awaiting human confirmation" in report
    assert "travertine stone facade [travertine]" in report
    assert "natural marble finish [marble]" in report
    assert "USER_CORRECTION" in report
    assert "PENDING_CONFIRMATION" in report
    assert "Spatial grounding: UNKNOWN" in report
    assert "NOT_YET_AVAILABLE" in report
    assert "No permanent learning has occurred" in report

    from core.vision import architectural_material_knowledge_connection_v1 as owner

    source = "\n".join(
        inspect.getsource(item).lower()
        for item in (
            owner._material_correction,
            owner.open_material_correction_review,
            owner.admit_confirmed_material_correction,
        )
    )
    for forbidden in (
        "render_runtime",
        "sam3",
        "comfyui",
        "inference",
        "generate(",
        "mask_builder",
    ):
        assert forbidden not in source
