# -*- coding: utf-8 -*-
"""CPU-only tests for MATERIAL_REVIEW_READONLY_UI_V1 and its
MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 access gate.

Two layers are covered:

1. The projection helper (`_public_material_reviews`) — field
   minimization, lifecycle filtering, fail-closed behaviour.
2. The real Core route (`GET /api/projects/<id>`) — unauthenticated and
   forged-signature requests must NOT receive review data; only a valid
   trusted-local gateway signature may.

Isolated: every test uses a temporary projects root. No production
project, conversation store, or learning ledger is read or written.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os

import pytest

from core.chat.conversation_state import ConversationState
from core.project.conversation_store_v1 import ConversationStore
from core.vision.architectural_material_knowledge_connection_v1 import (
    build_architectural_material_knowledge_connection,
)


CORRECTION = "The material you identified as travertine is actually marble."
PROJECT = "isolated-mr-project-a"
SESSION = "isolated-mr-project-a"
IMAGE = "SYNTHETIC-IMAGE-MR-A"

TEST_SECRET = "unit-test-local-proxy-secret-0123456789abcdef"


def _connection(image_id=IMAGE):
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


def _record(store, *, project=PROJECT, session=SESSION, ref="seq:7",
            image=IMAGE):
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


def _remember(store, state, *, project=PROJECT, session=SESSION,
              ref="seq:7", image=IMAGE):
    _bind_message(state, ref, image)
    record = _record(
        store, project=project, session=session, ref=ref, image=image
    )
    store.remember_material_correction_review(state, record)
    return record


def _project_reviews(project_id, store, authorized=True):
    """Call the projection helper against an isolated store."""

    import core.project.project_api_v1 as api_module

    original = api_module.conversation_store
    api_module.conversation_store = store
    try:
        return api_module._public_material_reviews(
            project_id, authorized=authorized
        )
    finally:
        api_module.conversation_store = original


# ==========================================================
# A. PROJECTION CONTENT
# ==========================================================

def test_01_pending_review_visible_after_creation(store):
    state = ConversationState()
    record = _remember(store, state)
    store.save(PROJECT, state.state)

    reviews = _project_reviews(PROJECT, store)
    assert len(reviews) == 1
    assert reviews[0]["review_id"] == record["review_id"]


def test_02_pending_review_visible_after_project_reload(store):
    state = ConversationState()
    record = _remember(store, state)
    store.save(PROJECT, state.state)

    recreated = ConversationState()
    store.hydrate(PROJECT, recreated)
    store.save(PROJECT, recreated.state)

    reviews = _project_reviews(PROJECT, store)
    assert len(reviews) == 1
    assert reviews[0]["review_id"] == record["review_id"]


def test_03_exact_review_id_preserved(store):
    state = ConversationState()
    record = _remember(store, state)
    store.save(PROJECT, state.state)

    reviews = _project_reviews(PROJECT, store)
    assert reviews[0]["review_id"] == record["review_id"]


def test_04_exact_corrected_material_label_preserved(store):
    state = ConversationState()
    record = _remember(store, state)
    store.save(PROJECT, state.state)

    corrected = record["corrected_material"]
    expected = (
        corrected.get("material_label")
        or corrected.get("label")
        or corrected.get("ontology_normalized")
        or corrected.get("identity")
        or corrected.get("ontology_id")
    )
    reviews = _project_reviews(PROJECT, store)
    assert reviews[0]["corrected_material_label"] == expected


def test_05_previous_material_label_distinct_from_corrected(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["previous_material_label"]
    assert review["corrected_material_label"]
    assert review["previous_material_label"] != review["corrected_material_label"]


def test_06_observation_confidence_retained(store):
    """Observation uncertainty must survive the minimization."""
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["observation_confidence"] == "MEDIUM"


def test_07_image_and_attachment_provenance_retained(store):
    state = ConversationState()
    _remember(store, state, ref="seq:19", image="SYNTHETIC-MR-BOUND")
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["image_id"] == "SYNTHETIC-MR-BOUND"
    assert review["observation_provenance"]["image_id"] == "SYNTHETIC-MR-BOUND"
    assert review["observation_provenance"]["provider"] == "SYNTHETIC_TEST_FIXTURE"


def test_08_multiple_pending_reviews_remain_distinct(store):
    state = ConversationState()
    first = _remember(store, state, ref="seq:3", image="SYNTHETIC-MR-A")
    second = _remember(store, state, ref="seq:9", image="SYNTHETIC-MR-B")
    store.save(PROJECT, state.state)

    reviews = _project_reviews(PROJECT, store)
    assert len(reviews) == 2
    assert {r["review_id"] for r in reviews} == {
        first["review_id"], second["review_id"]
    }


def test_09_wrong_project_access_rejected(store):
    state = ConversationState()
    _remember(store, state, project="project-a", session="project-a")
    store.save("project-a", state.state)

    assert _project_reviews("project-b", store) == []


def test_10_malformed_carrier_not_displayed_as_valid(store):
    state = ConversationState()
    record = _record(store)
    record.pop("review_id")
    _bind_message(state, "seq:7", IMAGE)
    state.state["material_correction_reviews"] = [record]
    store.save(PROJECT, state.state)

    assert _project_reviews(PROJECT, store) == []


def test_11_rejected_records_not_displayed_as_pending(store):
    record = _record(store)
    record["confirmation_review"]["state"] = "rejected"
    record["lifecycle"]["state"] = "rejected"
    state = ConversationState()
    _bind_message(state, "seq:7", IMAGE)
    store.remember_material_correction_review(state, record)
    store.save(PROJECT, state.state)

    assert _project_reviews(PROJECT, store) == []


def test_12_correction_text_exact(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    assert _project_reviews(PROJECT, store)[0][
        "original_correction_text"
    ] == CORRECTION


def test_13_pending_status_and_no_confirmation(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["state"] == "pending_review"
    assert review["human_confirmed"] is False
    assert review["confirmation_enabled"] is False


def test_14_spatial_grounding_unknown(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["spatial_grounding_status"] in (None, "UNKNOWN", "")


def test_15_execution_capability_not_yet_available(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert review["execution_capability_status"] == "NOT_YET_AVAILABLE"


def test_16_legacy_project_without_reviews_returns_empty(store):
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

    assert _project_reviews(PROJECT, store) == []


def test_17_existing_chat_and_attachment_rendering_unchanged(store):
    state = ConversationState()
    attachment = {"id": IMAGE, "kind": "image", "url": "/artifacts/test/a.png"}
    state.add_message("user", CORRECTION, [attachment])
    state.add_message("assistant", "Pending review shown.")
    before_messages = copy.deepcopy(state.state["messages"])
    message_ref = store.message_ref(state.state["messages"], 0)
    store.remember_material_correction_review(
        state, _record(store, ref=message_ref)
    )
    store.save(PROJECT, state.state)

    recreated = ConversationState()
    store.hydrate(PROJECT, recreated)
    assert recreated.state["messages"] == before_messages


# ==========================================================
# B. FIELD MINIMIZATION
# ==========================================================

def test_18_projection_has_no_whole_carrier_subobjects(store):
    """The minimized contract must not echo full carrier objects."""
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    for forbidden in (
        "knowledge_candidate",
        "confirmation_review",
        "original_observation",
        "previous_observation",
        "corrected_material",
        "origin",
        "lifecycle",
        "authentication",
        "captured_at",
        "confirmed_by",
        "ledger_path",
        "approval_capability",
    ):
        assert forbidden not in review, (
            "non-minimized field '%s' present in projection" % forbidden
        )


def test_19_projection_field_set_is_exactly_the_display_contract(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    review = _project_reviews(PROJECT, store)[0]
    assert set(review) == {
        "review_id",
        "original_correction_text",
        "previous_material_label",
        "corrected_material_label",
        "observation_confidence",
        "observation_provenance",
        "project_id",
        "image_id",
        "spatial_grounding_status",
        "execution_capability_status",
        "state",
        "human_confirmed",
        "confirmation_enabled",
    }


def test_20_provenance_is_trimmed_to_three_fields(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    provenance = _project_reviews(PROJECT, store)[0]["observation_provenance"]
    assert set(provenance) == {"provider", "model", "image_id"}


def test_21_no_token_like_values_in_projection(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    serialized = json.dumps(_project_reviews(PROJECT, store))
    for marker in ("exc_", "conf_", "dv_", "nonce_", "lsa_", "lss_"):
        assert marker not in serialized, (
            "token-like marker '%s' in projection" % marker
        )


def test_22_projection_source_has_no_render_inference_or_ledger():
    import core.project.project_api_v1 as api_module

    source = inspect.getsource(
        api_module._public_material_reviews
    ).lower()
    for forbidden in (
        "comfyui",
        "render_runtime",
        "sam3",
        "inference",
        "model.generate",
        "append_accepted_rule",
        "confirmed_by=",
        ".confirm(",
    ):
        assert forbidden not in source


def test_23_no_new_confirmation_or_ledger_route_exists():
    import core.project.project_api_v1 as api_module

    source = inspect.getsource(api_module)
    for forbidden in (
        "/api/material-reviews",
        "/api/material_reviews",
        "/api/reviews/material",
        "/api/confirm",
        "/api/reject",
        "/api/approve",
    ):
        assert forbidden not in source


# ==========================================================
# C. ACCESS GATE — helper level
# ==========================================================

def test_24_unauthorized_helper_call_returns_empty(store):
    """Even with a real pending review, authorized=False yields nothing."""
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    assert _project_reviews(PROJECT, store, authorized=False) == []


def test_25_authorized_helper_call_returns_review(store):
    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)

    assert len(_project_reviews(PROJECT, store, authorized=True)) == 1


def test_26_helper_gate_is_default_deny(store):
    """The parameter defaults to False, so a forgetful caller is safe."""
    import core.project.project_api_v1 as api_module

    signature = inspect.signature(api_module._public_material_reviews)
    assert signature.parameters["authorized"].default is False


# ==========================================================
# D. ACCESS GATE — real Core HTTP route
# ==========================================================

@pytest.fixture
def core_client(tmp_path, monkeypatch):
    """The real Core Flask app over an isolated projects root."""

    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()

    from core.project.project_workspace_v1 import project_workspace

    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))

    import app as application

    return application.app.test_client(), project_workspace


def _seed_core_project(workspace, name="core project"):
    """Create one project holding one pending review; return (pid, sid)."""

    from core.project.conversation_store_v1 import conversation_store

    manifest = workspace.create(name)
    pid = manifest["project_id"]
    sid = manifest.get("session_id") or pid

    state = ConversationState()
    state.add_message("user", CORRECTION, [{"id": IMAGE, "kind": "image"}])
    ref = conversation_store.message_ref(state.state["messages"], 0)
    carrier = conversation_store.build_material_correction_review_carrier(
        project_id=pid, session_id=sid, message_ref=ref,
        message_text=CORRECTION, connection=_connection(IMAGE),
        attachment_ids=[IMAGE],
    )
    conversation_store.remember_material_correction_review(state, carrier)
    conversation_store.save(pid, state.state, session_id=sid)
    return pid, sid, carrier["review_id"]


def _signed_headers(path, secret=TEST_SECRET, actor="lsa_test_actor",
                    session="lss_test_session"):
    from core.runtime.local_authorization_v1 import sign_proxy_request

    return sign_proxy_request(
        secret, actor_id=actor, session_id=session, payload={}, path=path
    )


def test_27_unauthenticated_direct_core_exposes_no_review(
    core_client, monkeypatch
):
    """THE security gate: no signature => no review data."""
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, review_id = _seed_core_project(workspace)

    response = client.get(
        "/api/projects/" + pid, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["material_reviews"] == []
    assert review_id not in json.dumps(body)


def test_28_forged_signature_headers_expose_no_review(
    core_client, monkeypatch
):
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, review_id = _seed_core_project(workspace)

    response = client.get(
        "/api/projects/" + pid,
        headers={
            "X-ArchitectOS-Actor": "lsa_attacker",
            "X-ArchitectOS-Local-Session": "lss_attacker",
            "X-ArchitectOS-Timestamp": "1",
            "X-ArchitectOS-Nonce": "nonce_attacker",
            "X-ArchitectOS-Signature": "deadbeef",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200
    assert response.get_json()["material_reviews"] == []
    assert review_id not in json.dumps(response.get_json())


def test_29_signature_with_wrong_secret_exposes_no_review(
    core_client, monkeypatch
):
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, _review_id = _seed_core_project(workspace)

    path = "/api/projects/" + pid
    headers = _signed_headers(
        path, secret="a-different-secret-0123456789abcdefghij"
    )
    response = client.get(
        path, headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert response.get_json()["material_reviews"] == []


def test_30_missing_secret_fails_closed(core_client, monkeypatch):
    client, workspace = core_client
    monkeypatch.delenv("ARCHITECTOS_LOCAL_PROXY_SECRET", raising=False)
    pid, _sid, _review_id = _seed_core_project(workspace)

    path = "/api/projects/" + pid
    headers = _signed_headers(path)
    response = client.get(
        path, headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert response.get_json()["material_reviews"] == []


def test_31_valid_trusted_local_signature_exposes_the_review(
    core_client, monkeypatch
):
    """The legitimate UI path still works."""
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, review_id = _seed_core_project(workspace)

    path = "/api/projects/" + pid
    headers = _signed_headers(path)
    response = client.get(
        path, headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert response.status_code == 200
    reviews = response.get_json()["material_reviews"]
    assert len(reviews) == 1
    assert reviews[0]["review_id"] == review_id


def test_32_signature_is_path_bound_across_projects(
    core_client, monkeypatch
):
    """A signature for project A cannot read project B."""
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid_a, _sa, _ra = _seed_core_project(workspace, "project A")
    pid_b, _sb, review_b = _seed_core_project(workspace, "project B")

    headers_for_a = _signed_headers("/api/projects/" + pid_a)
    response = client.get(
        "/api/projects/" + pid_b,
        headers=headers_for_a,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.get_json()["material_reviews"] == []
    assert review_b not in json.dumps(response.get_json())


def test_33_forged_project_id_with_valid_signature_returns_404(
    core_client, monkeypatch
):
    client, _workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)

    path = "/api/projects/does-not-exist-xyz"
    headers = _signed_headers(path)
    response = client.get(
        path, headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert response.status_code == 404


def test_34_client_supplied_actor_metadata_grants_nothing(
    core_client, monkeypatch
):
    """An arbitrary actor/session pair cannot self-authorize."""
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, _review_id = _seed_core_project(workspace)

    path = "/api/projects/" + pid
    response = client.get(
        path,
        headers={
            "X-ArchitectOS-Actor": "lsa_admin",
            "X-ArchitectOS-Local-Session": "lss_admin",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.get_json()["material_reviews"] == []


def test_35_core_route_returns_no_confirmation_capability(
    core_client, monkeypatch
):
    client, workspace = core_client
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", TEST_SECRET)
    pid, _sid, _review_id = _seed_core_project(workspace)

    path = "/api/projects/" + pid
    body = client.get(
        path, headers=_signed_headers(path),
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ).get_json()

    serialized = json.dumps(body).lower()
    for forbidden in (
        "approval_capability",
        "confirm_token",
        "ledger_path",
        "confirmed_by",
        "admit_confirmed",
    ):
        assert forbidden not in serialized


# ==========================================================
# E. LEDGER SAFETY
# ==========================================================

def test_36_production_ledger_hash_unchanged(store):
    ledger_rel = (
        "core/architecture/knowledge/"
        "human_architectural_learning_registry_v1.json"
    )
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ledger_path = os.path.join(project_root, ledger_rel)

    if not os.path.isfile(ledger_path):
        pytest.skip("production ledger not found")

    before = hashlib.sha256(
        open(ledger_path, "rb").read()
    ).hexdigest().upper()

    state = ConversationState()
    _remember(store, state)
    store.save(PROJECT, state.state)
    _project_reviews(PROJECT, store)
    _project_reviews(PROJECT, store, authorized=False)

    after = hashlib.sha256(
        open(ledger_path, "rb").read()
    ).hexdigest().upper()

    assert before == after, (
        "production learning ledger was modified: %s -> %s" % (before, after)
    )
