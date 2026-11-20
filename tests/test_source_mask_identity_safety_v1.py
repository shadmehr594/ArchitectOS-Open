# ==========================================================
# ARCHITECTOS — SOURCE / MASK IDENTITY SAFETY V1 — TESTS
#
# CPU-only. Flask test client drives the REAL `app.chat_api` boundary; the
# REAL `ImageWorkflowInjector` is driven on the REAL canonical Kontext graph.
# `ChatArchitect._handle_internal` is replaced with a recorder so nothing
# downstream (and nothing GPU) runs.
#
# THE RECORDED INCIDENT (SOURCE_MASK_MISROUTING):
#   LoadImage(300) and LoadImageMask(310) both resolved to the mask file's
#   bytes. The model read the mask as the building and the run was invalid.
#
# The reachable path today, reproduced in
# `test_mask_registered_as_the_active_source_is_refused`:
#   1. a mask is uploaded with its source -> a provenance sidecar binds the
#      mask to that source digest;
#   2. a later turn makes the MASK the session's active image and names the
#      mask asset.
#   Every pre-existing guard then agrees: dimensions match, provenance binds,
#   the composite exists. Source and mask are the same bytes and nothing says
#   so. That is the incident, and it is reachable on CPU today.
# ==========================================================

import hashlib
import io
import json
import os

import pytest

import app as CORE
from config import runtime_config as RC


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(self, address, *a, **k):
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)


# ----------------------------------------------------------
# fixtures / helpers
# ----------------------------------------------------------

def _png_bytes(size=(384, 512), colour=128):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (colour, colour, colour)).save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _mask_png_bytes(size=(384, 512), colour=255):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("L", size, colour).save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _write_mask_asset(name, size=(384, 512), colour=255):
    """Stage a mask file in ComfyUI's input dir, as the server does."""

    from PIL import Image

    path = "%s/%s" % (RC.COMFYUI_INPUT_DIR.rstrip("/"), name)
    Image.new("L", size, colour).save(path)
    return name


def _capture(monkeypatch):
    import core.chat.chat_architect as ca

    captured = {}

    def _record(self, text, context=None):
        captured["text"] = text
        captured["context"] = context
        return {"type": "chat", "status": "success", "result": "recorded"}

    monkeypatch.setattr(ca.ChatArchitect, "_handle_internal", _record)

    return captured


def _post_multipart(client, session, message="این پنجره را حذف کن", **files):
    data = {
        "message": message,
        "session_id": session,
        "mode": "image_to_image",
        "kontext_edit": "1",
    }
    return client.post(
        "/chat",
        data={**data, **files},
        content_type="multipart/form-data",
    )


def _post_json(client, session, mask_payload):
    return client.post(
        "/chat",
        json={
            "message": "این پنجره را حذف کن",
            "session_id": session,
            "mode": "image_to_image",
            "mask": mask_payload,
            "kontext_edit": "1",
        },
    )


@pytest.fixture
def two_sources(tmp_path):
    """Two DIFFERENT images with IDENTICAL dimensions."""

    a = tmp_path / "source_A.png"
    b = tmp_path / "source_B.png"
    a.write_bytes(_png_bytes((384, 512), 10).read())
    b.write_bytes(_png_bytes((384, 512), 200).read())
    return a, b


def _posted_mask_name(captured):
    """The filename the SERVER chose for the mask it just staged."""

    mask = (captured.get("context") or {}).get("mask")

    assert isinstance(mask, dict), "the boundary staged no mask"

    name = mask.get("filename")

    assert name and name.startswith("architectos_mask_"), name

    return name


def _register_active(session, path):
    from core.vision.image_registry_v1 import image_registry

    image_registry.reset(session)
    image_registry.register(session, path=str(path), source_type="uploaded")


# ==========================================================
# 1 — VALID SOURCE + VALID BOUND MASK IS ACCEPTED
# ==========================================================

def test_valid_source_with_a_bound_mask_is_accepted(monkeypatch):
    captured = _capture(monkeypatch)

    client = CORE.app.test_client()

    response = _post_multipart(
        client,
        "identity_ok_1",
        image=(_png_bytes((384, 512), 40), "source.png"),
        mask=(_mask_png_bytes(), "mask.png"),
    )

    assert response.status_code == 200, response.get_json()

    mask = (captured.get("context") or {}).get("mask")

    assert isinstance(mask, dict), "the boundary produced no mask"

    assert len(mask.get("source_sha256") or "") == 64

    assert mask.get("filename", "").startswith("architectos_mask_")


# ==========================================================
# 2 — SAME CANONICAL FILE FOR SOURCE AND MASK
# ==========================================================

def test_collision_helper_flags_the_same_canonical_file(tmp_path):
    from app import source_mask_identity_collision

    one = str(tmp_path / "same.png")
    (tmp_path / "same.png").write_bytes(b"x")

    reason = source_mask_identity_collision(
        source_path=one,
        source_digest="a" * 64,
        mask_path=one,
        mask_digest="b" * 64,
    )

    assert reason == "same_canonical_path"


# ==========================================================
# 3 — SAME DIGEST UNDER DIFFERENT FILENAMES
# ==========================================================

def test_collision_helper_flags_identical_digests(tmp_path):
    from app import source_mask_identity_collision

    reason = source_mask_identity_collision(
        source_path=str(tmp_path / "source.png"),
        source_digest="c" * 64,
        mask_path=str(tmp_path / "mask.png"),
        mask_digest="c" * 64,
    )

    assert reason == "same_digest"


def test_identical_bytes_as_source_and_mask_are_refused(monkeypatch):
    """Two filenames, one content. This is the incident's byte shape."""

    captured = _capture(monkeypatch)

    client = CORE.app.test_client()

    shared = _png_bytes((384, 512), 77)

    response = _post_multipart(
        client,
        "identity_ok_3",
        image=(io.BytesIO(shared.getvalue()), "source.png"),
        mask=(io.BytesIO(shared.getvalue()), "mask.png"),
    )

    assert response.status_code == 400, (
        "identical source and mask bytes were accepted"
    )

    assert (response.get_json() or {}).get("error") == "mask_source_identity_collision"

    assert "mask" not in (captured.get("context") or {})


# ==========================================================
# 4 — MASK SUBMITTED AS THE SOURCE (THE RECORDED INCIDENT)
# ==========================================================

def test_mask_registered_as_the_active_source_is_refused(monkeypatch, tmp_path):
    """The incident shape, end to end, on CPU.

    Step 1 uploads a mask WITH its source, so a provenance sidecar binds the
    mask to that source digest. Step 2 makes the mask itself the session's
    active image and names the mask asset. Every pre-existing guard agrees;
    only an identity-collision check can refuse this.
    """

    from core.vision.image_registry_v1 import image_registry

    client = CORE.app.test_client()

    # ---- step 1: author the mask against a real source ----
    captured1 = _capture(monkeypatch)

    first = _post_multipart(
        client,
        "identity_incident_4",
        image=(_png_bytes((384, 512), 33), "source.png"),
        mask=(_mask_png_bytes(), "mask.png"),
    )

    assert first.status_code == 200, first.get_json()

    # the mask filename the SERVER chose for the mask it just staged
    mask_name = _posted_mask_name(captured1)

    # ---- step 2: the MASK becomes the active source ----
    mask_path = os.path.join(RC.COMFYUI_INPUT_DIR, mask_name)

    image_registry.reset("identity_incident_4")
    image_registry.register(
        "identity_incident_4", path=mask_path, source_type="uploaded"
    )

    captured2 = _capture(monkeypatch)

    second = _post_json(client, "identity_incident_4", {"filename": mask_name})

    # This route is ALREADY refused today, by the provenance contract: the
    # sidecar bound the mask to the ORIGINAL source digest, and the resolved
    # source digest is now the mask's own. Recorded here as a regression guard
    # so the identity check cannot be traded against it.
    assert second.status_code == 400, (
        "the mask was accepted as its own source — this is SOURCE_MASK_MISROUTING"
    )

    assert (second.get_json() or {}).get("error") in (
        "mask_source_identity_collision", "mask_provenance_unverified",
    )

    assert "mask" not in (captured2.get("context") or {})


def test_collision_helper_flags_a_source_in_the_mask_namespace(tmp_path):
    from app import source_mask_identity_collision

    reason = source_mask_identity_collision(
        source_path=str(tmp_path / "architectos_mask_deadbeef.png"),
        source_digest="d" * 64,
        mask_path=str(tmp_path / "architectos_mask_other.png"),
        mask_digest="e" * 64,
    )

    assert reason == "source_is_mask_namespace"


# ==========================================================
# 5 — STALE MASK PROVENANCE
# ==========================================================

def test_stale_mask_provenance_is_refused(monkeypatch, two_sources, tmp_path):
    from PIL import Image

    source_a, _ = two_sources

    name = _write_mask_asset("architectos_mask_identity_stale.png")

    path = "%s/%s" % (RC.COMFYUI_INPUT_DIR.rstrip("/"), name)

    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()

    with open(path + ".provenance.json", "w", encoding="utf-8") as f:
        json.dump({
            "contract": "MaskSourceProvenanceV1",
            "mask_filename": name,
            "mask_sha256": digest,
            "mask_size_bytes": 1,
            "source_sha256": hashlib.sha256(source_a.read_bytes()).hexdigest(),
            "source_size_bytes": source_a.stat().st_size,
            "source_image_id": None,
            "source_path": str(source_a),
            "validated_at": 0,
        }, f)

    # the mask file changes after validation
    Image.new("L", (384, 512), 0).save(path)

    _register_active("identity_stale_5", source_a)

    captured = _capture(monkeypatch)

    response = _post_json(CORE.app.test_client(), "identity_stale_5", {"filename": name})

    assert response.status_code == 400

    assert (response.get_json() or {}).get("error") == "mask_provenance_unverified"

    assert "mask" not in (captured.get("context") or {})


# ==========================================================
# 6 — MASK FROM A DIFFERENT PROJECT / SOURCE
# ==========================================================

def test_mask_bound_to_another_project_source_is_refused(
    monkeypatch, two_sources
):
    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = two_sources

    client = CORE.app.test_client()

    # authored in project A against source A
    captured1 = _capture(monkeypatch)

    first = _post_multipart(
        client,
        "identity_project_a",
        image=(io.BytesIO(source_a.read_bytes()), "source.png"),
        mask=(_mask_png_bytes(), "mask.png"),
    )

    assert first.status_code == 200

    mask_name = _posted_mask_name(captured1)

    # submitted in project B, whose source is a DIFFERENT image of the same size
    image_registry.reset("identity_project_b")
    image_registry.register(
        "identity_project_b", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    response = _post_json(
        client, "identity_project_b", {"filename": mask_name}
    )

    assert response.status_code == 400, (
        "a mask authored for another source was accepted"
    )

    assert (response.get_json() or {}).get("error") in (
        "mask_provenance_unverified", "mask_source_identity_collision",
    )

    assert "mask" not in (captured.get("context") or {})


# ==========================================================
# 7 — MISSING AUTHORITATIVE SOURCE IDENTITY
# ==========================================================

def test_missing_authoritative_source_is_refused(monkeypatch):
    from core.vision.image_registry_v1 import image_registry

    image_registry.reset("identity_unbound_7")

    captured = _capture(monkeypatch)

    name = _write_mask_asset("architectos_mask_identity_unbound.png")

    response = _post_json(
        CORE.app.test_client(), "identity_unbound_7", {"filename": name}
    )

    assert response.status_code == 400

    assert (response.get_json() or {}).get("error") in (
        "mask_source_unbound", "mask_provenance_unverified",
    )

    assert "mask" not in (captured.get("context") or {})


# ==========================================================
# 8 — CORRECT DIMENSIONS BUT WRONG SOURCE
# ==========================================================

def test_correct_dimensions_but_wrong_source_is_refused(
    monkeypatch, two_sources
):
    source_a, source_b = two_sources

    client = CORE.app.test_client()

    captured1 = _capture(monkeypatch)

    first = _post_multipart(
        client,
        "identity_dims_8",
        image=(io.BytesIO(source_a.read_bytes()), "source.png"),
        mask=(_mask_png_bytes(), "mask.png"),
    )

    assert first.status_code == 200

    mask_name = _posted_mask_name(captured1)

    # same dimensions, different pixels
    _register_active("identity_dims_8", source_b)

    captured = _capture(monkeypatch)

    response = _post_json(client, "identity_dims_8", {"filename": mask_name})

    assert response.status_code == 400

    assert (response.get_json() or {}).get("error") in (
        "mask_provenance_unverified", "mask_source_identity_collision",
    )

    assert "mask" not in (captured.get("context") or {})


# ==========================================================
# 9 — REUSED VERIFIED MASK WITH ITS ORIGINAL SOURCE
# ==========================================================

def test_reused_verified_mask_with_its_original_source_is_accepted(
    monkeypatch, tmp_path
):
    from core.vision.image_registry_v1 import image_registry

    client = CORE.app.test_client()

    source_bytes = _png_bytes((384, 512), 55).getvalue()

    captured1 = _capture(monkeypatch)

    first = _post_multipart(
        client,
        "identity_reuse_9",
        image=(io.BytesIO(source_bytes), "source.png"),
        mask=(_mask_png_bytes(), "mask.png"),
    )

    assert first.status_code == 200

    mask_name = _posted_mask_name(captured1)

    # the SAME source bytes, now as the session's active image
    active = tmp_path / "same_source.png"
    active.write_bytes(source_bytes)

    image_registry.reset("identity_reuse_9")
    image_registry.register(
        "identity_reuse_9", path=str(active), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    second = _post_json(client, "identity_reuse_9", {"filename": mask_name})

    assert second.status_code == 200, second.get_json()

    mask = (captured.get("context") or {}).get("mask")

    assert isinstance(mask, dict), "a verified reusable mask was refused"

    assert mask.get("filename") == mask_name

    assert mask.get("source") == "asset_verified"


# ==========================================================
# 10 — ORDINARY MASKLESS KONTEXT EDIT IS UNCHANGED
# ==========================================================

def test_maskless_kontext_edit_is_unchanged(monkeypatch):
    captured = _capture(monkeypatch)

    response = _post_multipart(
        CORE.app.test_client(),
        "identity_maskless_10",
        image=(_png_bytes((384, 512), 66), "source.png"),
    )

    assert response.status_code == 200

    context = captured.get("context") or {}

    assert not context.get("mask"), "a maskless turn carried a mask"

    assert context.get("kontext_edit") is True


# ==========================================================
# 11 / 12 — THE FINAL INJECTED GRAPH
# ==========================================================

def _inject(mask_asset):
    from core.render.image_workflow_injector import ImageWorkflowInjector

    workflow = json.load(
        open("core/render/workflows/flux_kontext_edit.json", encoding="utf-8")
    )

    return ImageWorkflowInjector().inject(
        workflow,
        "replace the finish on the facade walls",
        {"filename": "architectos_source.png", "working_dimensions": [768, 704]},
        {},
        mask_asset=mask_asset,
    )


def test_masked_graph_saves_through_the_composite():
    result = _inject({"filename": "architectos_mask_abc.png"})

    wf = result["workflow"]

    assert result["status"] == "injected"

    assert wf["300"]["inputs"]["image"] == "architectos_source.png"

    assert wf["310"]["inputs"]["image"] == "architectos_mask_abc.png"

    assert wf["312"]["inputs"]["destination"] == ["300", 0]

    assert wf["312"]["inputs"]["source"] == ["208", 0]

    assert wf["312"]["inputs"]["mask"] == ["310", 0]

    assert wf["9"]["inputs"]["images"] == ["312", 0], (
        "SaveImage is not wired to the composite"
    )

    assert result["reference_edit_contract"]["save_source_node"] == "312"


def test_unmasked_graph_saves_the_decoded_output():
    result = _inject(None)

    wf = result["workflow"]

    assert result["status"] == "injected"

    assert wf["9"]["inputs"]["images"] == ["208", 0], (
        "SaveImage is not wired to the decoder on the maskless route"
    )

    assert result["reference_edit_contract"]["save_source_node"] == "208"


def test_injector_blocks_when_source_and_mask_are_the_same_file():
    result = _inject({"filename": "architectos_source.png"})

    assert result["status"] == "blocked", (
        "the injector bound one asset as both source and mask"
    )

    assert "source_mask_identity_collision" in (
        result["reference_edit_contract"]["errors"]
    )
