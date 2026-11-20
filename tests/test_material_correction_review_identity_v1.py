# -*- coding: utf-8 -*-
"""CPU-only exact-identity and replay guards for material corrections.

Every persistence assertion uses pytest's isolated temporary directory. This
suite never resolves or writes the production human-learning ledger.
"""

from __future__ import annotations

import copy
import inspect

import pytest

from core.architecture.knowledge.human_learning_ledger_v1 import load_ledger
from core.knowledge.human_knowledge_validation_loop_v1 import (
    ArchitecturalKnowledgeReview,
)
from core.vision.architectural_material_knowledge_connection_v1 import (
    admit_confirmed_material_correction,
    build_architectural_material_knowledge_connection,
    open_material_correction_review,
)


CORRECTION = "The material you identified as travertine is actually marble."


def _connection(image_id="SYNTHETIC-TRAVERTINE-CORRECTION"):
    observation = {
        "contract": "ArchitecturalObservationV1",
        "material_observations": [{
            "descriptor": "cream travertine facade cladding",
            "materials": ["travertine"],
            "evidence_phrase": "cream travertine facade cladding",
            "confidence": "MEDIUM",
        }],
        "provenance": {
            "provider": "SYNTHETIC_TEST_FIXTURE",
            "model": "NONE",
            "image_id": image_id,
            "source_type": "test_fixture",
        },
    }
    return build_architectural_material_knowledge_connection(
        observation, CORRECTION
    )


def _ledger(tmp_path, name="ledger.json"):
    return str(tmp_path / name)


def test_exact_pending_review_id_and_candidate_are_recovered():
    connection = _connection()
    serialized = connection["material_correction"]["confirmation_review"]
    review = open_material_correction_review(connection, language="en")

    assert review.review_id == serialized["review_id"]
    assert review.candidate == serialized["candidate"]
    assert review.state == "pending_review"


@pytest.mark.parametrize("bad_id", [None, "", 7])
def test_missing_or_malformed_saved_review_identity_fails_closed(bad_id):
    connection = _connection()
    connection["material_correction"]["confirmation_review"]["review_id"] = bad_id

    with pytest.raises(ValueError, match="no pending confirmation candidate"):
        open_material_correction_review(connection, language="en")


def test_forged_review_id_is_rejected_with_zero_writes(tmp_path):
    connection = _connection()
    candidate = connection["material_correction"]["knowledge_candidate"]
    forged = ArchitecturalKnowledgeReview(
        candidate, review_id="review_forged_identity", language="en"
    ).confirm("explicit synthetic confirmation")
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="explicitly confirmed"):
        admit_confirmed_material_correction(
            connection,
            forged,
            path=ledger,
            confirmed_by="SYNTHETIC_TEST_ACTOR",
        )

    assert load_ledger(ledger)["items"] == []
    assert not (tmp_path / "ledger.json").exists()


def test_matching_id_with_mismatched_candidate_is_rejected(tmp_path):
    connection = _connection()
    review = open_material_correction_review(connection, language="en")
    review.candidate = copy.deepcopy(review.candidate)
    review.candidate["scope"] = "GLOBAL"
    review.confirm("explicit synthetic confirmation")
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="explicitly confirmed"):
        admit_confirmed_material_correction(
            connection,
            review,
            path=ledger,
            confirmed_by="SYNTHETIC_TEST_ACTOR",
        )

    assert load_ledger(ledger)["items"] == []


def test_two_pending_corrections_cannot_be_cross_confirmed(tmp_path):
    first = _connection("SYNTHETIC-IMAGE-A")
    second = _connection("SYNTHETIC-IMAGE-B")
    first_review = open_material_correction_review(first, language="en")
    first_review.confirm("explicit synthetic confirmation")
    ledger = _ledger(tmp_path)

    assert (
        first["material_correction"]["confirmation_review"]["review_id"]
        != second["material_correction"]["confirmation_review"]["review_id"]
    )
    with pytest.raises(ValueError, match="explicitly confirmed"):
        admit_confirmed_material_correction(
            second,
            first_review,
            path=ledger,
            confirmed_by="SYNTHETIC_TEST_ACTOR",
        )

    assert load_ledger(ledger)["items"] == []


def test_rejected_review_cannot_be_admitted(tmp_path):
    connection = _connection()
    review = open_material_correction_review(connection, language="en")
    review.reject("synthetic rejection")
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="explicitly confirmed"):
        admit_confirmed_material_correction(
            connection,
            review,
            path=ledger,
            confirmed_by="SYNTHETIC_TEST_ACTOR",
        )

    assert load_ledger(ledger)["items"] == []


def test_replayed_confirmation_cannot_append_twice(tmp_path):
    connection = _connection()
    review = open_material_correction_review(connection, language="en")
    review.confirm("explicit synthetic confirmation")
    ledger = _ledger(tmp_path)

    first = admit_confirmed_material_correction(
        connection,
        review,
        path=ledger,
        confirmed_by="SYNTHETIC_TEST_ACTOR",
    )
    with pytest.raises(ValueError, match="already exists"):
        admit_confirmed_material_correction(
            connection,
            review,
            path=ledger,
            confirmed_by="SYNTHETIC_TEST_ACTOR",
        )

    items = load_ledger(ledger)["items"]
    expected_review_id = connection["material_correction"][
        "confirmation_review"
    ]["review_id"]
    assert first["id"] == "material_correction_%s" % expected_review_id
    assert len(items) == 1


def test_valid_admission_preserves_observation_and_current_project_scope(tmp_path):
    connection = _connection()
    review = open_material_correction_review(connection, language="en")
    review.confirm("explicit synthetic confirmation")

    record = admit_confirmed_material_correction(
        connection,
        review,
        path=_ledger(tmp_path),
        confirmed_by="SYNTHETIC_TEST_ACTOR",
    )

    assert record["scope"] == "CURRENT_PROJECT"
    assert record["previous_observation"]["ontology_id"] == "travertine"
    assert record["corrected_material"]["ontology_id"] == "marble"
    assert record["user_correction"]["source"] == "USER_CORRECTION"
    assert record["spatial_grounding"]["status"] == "UNKNOWN"
    assert record["execution_capability"]["status"] == "NOT_YET_AVAILABLE"


def test_identity_guard_has_no_render_mask_or_inference_path():
    from core.vision import architectural_material_knowledge_connection_v1 as owner

    source = "\n".join(
        inspect.getsource(item).lower()
        for item in (
            owner.open_material_correction_review,
            owner.admit_confirmed_material_correction,
        )
    )
    for forbidden in (
        "render_runtime",
        "sam3",
        "comfyui",
        "inference",
        "mask_builder",
    ):
        assert forbidden not in source
