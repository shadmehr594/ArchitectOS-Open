# -*- coding: utf-8 -*-
"""CPU-only durable material-correction review carrier regressions."""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from core.chat.conversation_state import ConversationState
from core.project.conversation_store_v1 import ConversationStore
from core.vision.architectural_material_knowledge_connection_v1 import (
    build_architectural_material_knowledge_connection,
)


CORRECTION = "The material you identified as travertine is actually marble."
PROJECT = "isolated-project-a"
SESSION = "isolated-project-a"


def _connection(image_id="SYNTHETIC-IMAGE-A"):
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


@pytest.fixture
def store(tmp_path):
    value = ConversationStore()

    def path(project_id):
        folder = tmp_path / project_id / "conversations"
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder / "chat.json")

    value.path = path
    return value


def _record(store, *, project=PROJECT, session=SESSION, ref="seq:7", image="SYNTHETIC-IMAGE-A"):
    return store.build_material_correction_review_carrier(
        project_id=project,
        session_id=session,
        message_ref=ref,
        message_text=CORRECTION,
        connection=_connection(image),
        attachment_ids=[image],
    )


def _bind_message(state, ref, image):
    message = {
        "role": "user",
        "text": CORRECTION,
        "attachments": [{"id": image, "kind": "image"}],
    }
    if ref.startswith("seq:"):
        message["turn_seq"] = int(ref.split(":", 1)[1])
    state.state.setdefault("messages", []).append(message)


def _remember(store, state, *, project=PROJECT, session=SESSION, ref="seq:7", image="SYNTHETIC-IMAGE-A"):
    _bind_message(state, ref, image)
    record = _record(
        store, project=project, session=session, ref=ref, image=image
    )
    store.remember_material_correction_review(state, record)
    return record


def test_pending_review_saves_and_restores_exact_identity(store):
    state = ConversationState()
    record = _remember(store, state)
    store.save(PROJECT, state.state)

    recreated = ConversationState()
    assert store.hydrate(PROJECT, recreated) == 1
    restored = recreated.state["material_correction_reviews"]

    assert len(restored) == 1
    assert restored[0]["review_id"] == record["review_id"]
    assert restored[0]["knowledge_candidate"] == record["knowledge_candidate"]


def test_project_message_image_and_session_binding_survive_reload(store):
    state = ConversationState()
    record = _remember(
        store, state, ref="seq:19", image="SYNTHETIC-IMAGE-BOUND"
    )
    store.save(PROJECT, state.state)

    restored = store.material_correction_reviews(PROJECT)[0]
    origin = restored["origin"]
    assert origin["project_id"] == PROJECT
    assert origin["message_ref"] == "seq:19"
    assert origin["session_id"] == SESSION
    assert origin["conversation_identity_kind"] == "PROJECT_BOUND_SESSION"
    assert origin["separate_conversation_id"] is None
    assert origin["image_identity"]["image_id"] == "SYNTHETIC-IMAGE-BOUND"
    assert origin["image_identity"]["attachment_ids"] == ["SYNTHETIC-IMAGE-BOUND"]


def test_original_observation_provenance_and_correction_are_exact(store):
    record = _record(store)
    connection = _connection()
    correction = connection["material_correction"]

    assert record["original_correction_text"] == CORRECTION
    assert record["original_observation"] == connection["observed_facts"]
    assert record["observation_provenance"] == connection["observed_facts"]["provenance"]
    assert record["previous_observation"] == correction["previous_observation"]
    assert record["corrected_material"] == correction["corrected_material"]


def test_wrong_project_record_is_rejected_on_save_and_restore(store):
    state = ConversationState()
    _bind_message(state, "seq:7", "SYNTHETIC-IMAGE-A")
    state.state["material_correction_reviews"] = [
        _record(store, project="project-b", session="project-b")
    ]
    store.save(PROJECT, state.state)

    recreated = ConversationState()
    store.hydrate(PROJECT, recreated)
    assert recreated.state["material_correction_reviews"] == []
    assert recreated.state["material_correction_review_restore_errors"]


@pytest.mark.parametrize("mutation", ["missing_review_id", "candidate_mismatch", "image_rebind"])
def test_missing_or_malformed_records_fail_closed(store, mutation):
    record = _record(store)
    if mutation == "missing_review_id":
        record.pop("review_id")
    elif mutation == "candidate_mismatch":
        record["knowledge_candidate"] = {"forged": True}
    else:
        record["origin"]["image_identity"]["image_id"] = "DIFFERENT-IMAGE"

    state = ConversationState()
    _bind_message(state, "seq:7", "SYNTHETIC-IMAGE-A")
    state.state["material_correction_reviews"] = [record]
    store.save(PROJECT, state.state)
    recreated = ConversationState()
    store.hydrate(PROJECT, recreated)

    assert recreated.state["material_correction_reviews"] == []
    assert recreated.state["material_correction_review_restore_errors"]


def test_wrong_session_and_missing_message_reference_fail_closed(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state, session_id=SESSION)

    recreated = ConversationState()
    store.hydrate(PROJECT, recreated, session_id="different-session")
    assert recreated.state["material_correction_reviews"] == []
    assert recreated.state["material_correction_review_restore_errors"]

    missing_message_state = ConversationState()
    missing_message_state.state["material_correction_reviews"] = [
        _record(store, ref="seq:404")
    ]
    store.save(PROJECT, missing_message_state.state, session_id=SESSION)
    assert store.material_correction_reviews(PROJECT, session_id=SESSION) == []


def test_unauthenticated_confirmed_state_is_not_restored(store):
    state = ConversationState()
    record = _record(store)
    _bind_message(state, "seq:7", "SYNTHETIC-IMAGE-A")
    record["confirmation_review"]["state"] = "confirmed"
    record["confirmation_review"]["human_confirmed"] = True
    record["lifecycle"]["state"] = "confirmed"
    record["lifecycle"]["human_confirmed"] = True
    state.state["material_correction_reviews"] = [record]

    store.save(PROJECT, state.state, session_id=SESSION)
    assert store.material_correction_reviews(PROJECT, session_id=SESSION) == []

def test_multiple_pending_reviews_remain_independently_identifiable(store):
    state = ConversationState()
    first = _remember(
        store, state, ref="seq:3", image="SYNTHETIC-IMAGE-A"
    )
    second = _remember(
        store, state, ref="seq:9", image="SYNTHETIC-IMAGE-B"
    )
    store.save(PROJECT, state.state)

    restored = store.material_correction_reviews(PROJECT)
    assert len(restored) == 2
    assert len({item["review_id"] for item in restored}) == 2
    assert {item["origin"]["message_ref"] for item in restored} == {"seq:3", "seq:9"}


def test_rejected_lifecycle_is_preserved_but_not_returned_as_pending(store):
    record = _record(store)
    record["confirmation_review"]["state"] = "rejected"
    record["confirmation_review"]["note"] = "synthetic rejection"
    record["lifecycle"]["state"] = "rejected"
    state = ConversationState()
    _bind_message(state, "seq:7", "SYNTHETIC-IMAGE-A")
    store.remember_material_correction_review(state, record)
    store.save(PROJECT, state.state)

    all_records = store.material_correction_reviews(PROJECT)
    pending = store.material_correction_reviews(PROJECT, pending_only=True)
    assert all_records[0]["lifecycle"]["state"] == "rejected"
    assert pending == []


def test_identical_review_is_not_duplicated(store):
    state = ConversationState()
    record = _remember(store, state)
    store.remember_material_correction_review(state, copy.deepcopy(record))
    store.save(PROJECT, state.state)
    assert len(store.material_correction_reviews(PROJECT)) == 1


def test_existing_message_and_attachment_continuity_is_unchanged(store):
    state = ConversationState()
    attachment = {"id": "SYNTHETIC-IMAGE-A", "kind": "image", "url": "/artifacts/test/a.png"}
    state.add_message("user", CORRECTION, [attachment])
    state.add_message("assistant", "Pending review shown.")
    before = copy.deepcopy(state.state["messages"])
    message_ref = store.message_ref(state.state["messages"], 0)
    store.remember_material_correction_review(
        state, _record(store, ref=message_ref)
    )
    store.save(PROJECT, state.state)

    recreated = ConversationState()
    store.hydrate(PROJECT, recreated)
    assert recreated.state["messages"] == before


def test_legacy_conversation_without_carrier_remains_readable(store):
    path = store.path(PROJECT)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({
            "contract": "ConversationStoreV1",
            "version": "1.0",
            "project_id": PROJECT,
            "messages": [{"role": "user", "text": "legacy", "attachments": []}],
            "message_count": 1,
            "ui": {},
        }, handle)

    recreated = ConversationState()
    assert store.hydrate(PROJECT, recreated) == 1
    assert recreated.state["messages"][0]["text"] == "legacy"
    assert recreated.state["material_correction_reviews"] == []


def test_untrusted_actor_and_automatic_confirmation_are_not_carried(store):
    record = _record(store)
    assert "confirmed_by" not in record
    assert record["lifecycle"] == {
        "state": "pending_review",
        "human_confirmed": False,
        "admitted": False,
    }
    assert record["authentication"] == {
        "status": "AUTHENTICATED_CONFIRMATION_ACTOR_UNAVAILABLE",
        "confirmation_enabled": False,
    }


def test_production_capture_is_pending_only_and_uses_existing_autosave():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )
    start = source.index(
        "# DURABLE MATERIAL CORRECTION REVIEW CARRIER V1 — the adapted"
    )
    end = source.index("response_type = str(", start)
    block = source[start:end].lower()

    assert "material_correction_pending_confirmation" in block
    assert "build_material_correction_review_carrier" in block
    assert "remember_material_correction_review" in block
    for forbidden in (
        "admit_confirmed_material_correction",
        "append_accepted_rule",
        ".confirm(",
        "confirmed_by",
        "is_confirmation",
    ):
        assert forbidden not in block
    assert "project_session.autosave" in source[end:]

def test_carrier_has_no_ledger_render_mask_or_model_path():
    from core.project import conversation_store_v1 as owner

    source = "\n".join(
        inspect.getsource(item).lower()
        for item in (
            owner.ConversationStore.build_material_correction_review_carrier,
            owner.ConversationStore.remember_material_correction_review,
            owner.ConversationStore.material_correction_reviews,
        )
    )
    for forbidden in (
        "append_accepted_rule",
        "confirmed_by=",
        "render_runtime",
        "sam3",
        "comfyui",
        "inference",
        "model.generate",
    ):
        assert forbidden not in source
