# ==========================================================
# ARCHITECTOS — MASK ASSET PROVENANCE V1 — TESTS
#
# CPU-only. Flask test client only — no server, no socket, no ComfyUI, no GPU.
# `ChatArchitect._handle_internal` is replaced with a recorder, so the REAL
# `app.chat_api` ingestion runs and nothing downstream does.
#
# THE EDGE CASE:
#   a previously stored asset-name mask, authored for source image A, is
#   submitted while the session's active source is a DIFFERENT image B of the
#   SAME dimensions. A server-computed digest of B proves only that the mask
#   is bound to B NOW; it does not prove the mask was authored for B.
#
# Two ways this was reachable:
#   1. the asset branch stamped B's digest onto A's mask;
#   2. a client-supplied `source_sha256` skipped that branch altogether.
#
# The corrected rule: an asset mask may be re-used only when the server can
# VERIFY it was validated against that same source (its sidecar provenance
# record), or when the mask is uploaded fresh on this request. Otherwise it
# fails closed and a fresh upload is required.
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


def _png_bytes(size=(384, 512), colour=128):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (colour, colour, colour)).save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _mask_asset(name, size=(384, 512)):
    from PIL import Image

    path = "%s/%s" % (RC.COMFYUI_INPUT_DIR.rstrip("/"), name)
    Image.new("L", size, 255).save(path)
    return name


@pytest.fixture
def sources(tmp_path):
    """Two different images with IDENTICAL dimensions."""

    from core.vision.image_registry_v1 import image_registry

    a = tmp_path / "source_A.png"
    b = tmp_path / "source_B.png"

    a.write_bytes(_png_bytes((384, 512), 10).read())
    b.write_bytes(_png_bytes((384, 512), 200).read())

    assert a.stat().st_size > 0

    image_registry.reset("provenance_session")

    return a, b


def _capture(monkeypatch):
    import core.chat.chat_architect as ca

    captured = {}

    def _record(self, text, context=None):
        captured["context"] = context
        return {"type": "chat", "status": "success", "result": "recorded"}

    monkeypatch.setattr(ca.ChatArchitect, "_handle_internal", _record)

    return captured


def _post_mask(client, session, mask_payload):
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


# ==========================================================
# 1 — THE EDGE CASE: A'S MASK SUBMITTED FOR SAME-SIZE SOURCE B
# ==========================================================

def test_asset_mask_from_another_source_is_refused_despite_same_dimensions(
    monkeypatch, sources
):
    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    name = _mask_asset("architectos_mask_authored_for_A.png")

    response = _post_mask(
        CORE.app.test_client(), "provenance_session", {"filename": name}
    )

    assert response.status_code == 400, (
        "an asset mask with no verified provenance was accepted"
    )

    payload = response.get_json() or {}

    assert payload.get("error") in (
        "mask_source_unbound", "mask_provenance_unverified",
    )

    assert "mask" not in (captured.get("context") or {})


def test_client_supplied_digest_cannot_establish_provenance(
    monkeypatch, sources
):
    """A caller asserting a digest must not skip the provenance decision."""

    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    name = _mask_asset("architectos_mask_authored_for_A.png")

    forged = hashlib.sha256(source_b.read_bytes()).hexdigest()

    response = _post_mask(
        CORE.app.test_client(),
        "provenance_session",
        {"filename": name, "source_sha256": forged},
    )

    assert response.status_code == 400, (
        "a client-supplied digest bypassed the provenance check"
    )

    assert "mask" not in (captured.get("context") or {})


def test_client_claimed_source_marker_cannot_skip_provenance(
    monkeypatch, sources
):
    """`source: "uploaded"` in the request must not select the upload path.

    The asset branch used to skip provenance whenever that field said
    "uploaded" — a value the client supplies on the JSON path — which let an
    unvalidated asset name through with a copied digest.
    """

    from core.vision.image_registry_v1 import image_registry
    from core.vision.image_intent_v1 import source_image_digest

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    name = _mask_asset("architectos_mask_bypass_attempt.png")

    forged = source_image_digest(str(source_b))

    response = _post_mask(
        CORE.app.test_client(),
        "provenance_session",
        {
            "filename": name,
            "source": "uploaded",          # client-claimed, must be ignored
            "source_sha256": forged,
            "dimensions": [384, 512],
        },
    )

    assert response.status_code == 400, (
        "a client-claimed `source` marker skipped provenance verification"
    )

    assert (response.get_json() or {}).get("error") == (
        "mask_provenance_unverified"
    )

    assert "mask" not in (captured.get("context") or {})


def test_asset_mask_binds_without_a_local_session_id(
    monkeypatch, sources, tmp_path
):
    """Mask ingestion runs before the chat handler defines `session_id`.

    The registry lookup must use the resolved request/project key, not a
    variable from the handler's scope: reading it raised NameError, which the
    broad except swallowed, so a legitimate mask looked source-less and was
    refused with `mask_source_unbound`.
    """

    from config import runtime_config as RC
    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "defect1_session", path=str(source_b), source_type="uploaded"
    )

    # a mask the SERVER validated for this source (its provenance record)
    name = _mask_asset("architectos_mask_defect1.png")

    mask_path = "%s/%s" % (RC.COMFYUI_INPUT_DIR.rstrip("/"), name)

    from core.vision.image_intent_v1 import source_image_digest

    io.open(mask_path + ".provenance.json", "w", encoding="utf-8").write(
        json.dumps({
            "contract": "MaskSourceProvenanceV1",
            "mask_filename": name,
            "mask_sha256": source_image_digest(mask_path),
            "mask_size_bytes": os.path.getsize(mask_path),
            "source_sha256": source_image_digest(str(source_b)),
            "source_size_bytes": os.path.getsize(str(source_b)),
        })
    )

    captured = _capture(monkeypatch)

    response = _post_mask(
        CORE.app.test_client(), "defect1_session", {"filename": name}
    )

    assert response.status_code == 200, response.get_json()

    assert isinstance((captured.get("context") or {}).get("mask"), dict)


def test_a_context_digest_without_server_verification_is_not_identity(
    tmp_path
):
    """A caller may put `source_sha256` in the guard context; that is data.

    Only the chat layer's source resolver may mark an identity verified, and
    it does so after hashing the actual image. An unmarked digest must not
    satisfy the mask binding, or the binding becomes caller-controlled.
    """

    from core.vision.image_intent_v1 import precise_localized_route_available

    source = tmp_path / "source_A.png"

    source.write_bytes(b"REAL-SOURCE-BYTES" * 32)

    claimed = "a" * 64

    mask = {
        "filename": "architectos_mask_smuggled.png",
        "dimensions": [384, 512],
        "source_sha256": claimed,
    }

    route = precise_localized_route_available({
        "mask": mask,
        "kontext_edit": "1",
        "precision_controls_supplied": True,
        "source_sha256": claimed,          # caller-supplied, unverified
    })

    assert route["available"] is False
    assert route["reason"] == "source_image_unresolved"


# ==========================================================
# 2 — LEGITIMATE PATHS MUST KEEP WORKING
# ==========================================================

def test_fresh_upload_for_the_current_source_is_bound(monkeypatch, sources):
    """The documented path: upload the mask WITH its source, same request."""

    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    response = CORE.app.test_client().post(
        "/chat",
        data={
            "text": "این پنجره را حذف کن",
            "session_id": "provenance_session",
            "mode": "image_to_image",
            "kontext_edit": "1",
            "image": (_png_bytes((384, 512), 200), "source.png"),
            "mask": (_png_bytes((384, 512), 255), "mask.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    mask = (captured.get("context") or {}).get("mask")

    assert isinstance(mask, dict)

    digest = mask.get("source_sha256")

    assert digest

    bound_path = mask.get("source_path")

    if bound_path:
        from core.vision.image_intent_v1 import source_image_digest

        assert source_image_digest(bound_path) == digest


def test_previously_verified_asset_is_reused_when_provenance_matches(
    monkeypatch, sources
):
    """An asset the server itself validated for THIS source stays reusable."""

    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    name = _mask_asset("architectos_mask_authored_for_B.png")

    client = CORE.app.test_client()

    # first turn: upload the mask alongside B — the server records provenance
    first = client.post(
        "/chat",
        data={
            "text": "این پنجره را حذف کن",
            "session_id": "provenance_session",
            "mode": "image_to_image",
            "kontext_edit": "1",
            "image": (_png_bytes((384, 512), 200), "source.png"),
            "mask": (_png_bytes((384, 512), 255), "mask.png"),
        },
        content_type="multipart/form-data",
    )

    assert first.status_code == 200

    used_name = captured["context"]["mask"]["filename"]

    # second turn: text-only, re-using that stored asset for the same source
    captured.clear()

    second = _post_mask(
        CORE.app.test_client(), "provenance_session", {"filename": used_name}
    )

    assert second.status_code == 200, (
        "a mask this server already validated for this source must be reusable"
    )

    assert isinstance((captured.get("context") or {}).get("mask"), dict)


def test_verified_asset_is_refused_once_the_source_changes(
    monkeypatch, sources
):
    """Provenance is not a permanent pass: it is re-checked every turn."""

    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    client = CORE.app.test_client()

    first = client.post(
        "/chat",
        data={
            "text": "این پنجره را حذف کن",
            "session_id": "provenance_session",
            "mode": "image_to_image",
            "kontext_edit": "1",
            "image": (_png_bytes((384, 512), 200), "source.png"),
            "mask": (_png_bytes((384, 512), 255), "mask.png"),
        },
        content_type="multipart/form-data",
    )

    assert first.status_code == 200

    used_name = captured["context"]["mask"]["filename"]

    # the SESSION's source image is replaced by a different image
    image_registry.reset("provenance_session")

    image_registry.register(
        "provenance_session", path=str(source_a), source_type="uploaded"
    )

    captured.clear()

    second = _post_mask(
        CORE.app.test_client(), "provenance_session", {"filename": used_name}
    )

    assert second.status_code == 400

    assert (second.get_json() or {}).get("error") == "mask_provenance_unverified"

    assert "mask" not in (captured.get("context") or {})


def test_mask_file_edited_after_validation_is_refused(monkeypatch, sources):
    """A sidecar alone is not enough — the mask bytes must still match it."""

    from config import runtime_config as RC
    from core.vision.image_intent_v1 import source_image_digest
    from core.vision.image_registry_v1 import image_registry

    source_a, source_b = sources

    image_registry.register(
        "provenance_session", path=str(source_b), source_type="uploaded"
    )

    captured = _capture(monkeypatch)

    client = CORE.app.test_client()

    first = client.post(
        "/chat",
        data={
            "text": "این پنجره را حذف کن",
            "session_id": "provenance_session",
            "mode": "image_to_image",
            "kontext_edit": "1",
            "image": (_png_bytes((384, 512), 200), "source.png"),
            "mask": (_png_bytes((384, 512), 255), "mask.png"),
        },
        content_type="multipart/form-data",
    )

    assert first.status_code == 200

    used_name = captured["context"]["mask"]["filename"]

    mask_path = "%s/%s" % (RC.COMFYUI_INPUT_DIR.rstrip("/"), used_name)

    # the mask bytes change while its provenance record still claims the old
    # digest; the record is server-written, so only the mask can be tampered
    with io.open(mask_path, "rb") as handle:
        original = handle.read()

    io.open(mask_path, "wb").write(original + b"\x00")

    captured.clear()

    second = _post_mask(
        CORE.app.test_client(), "provenance_session", {"filename": used_name}
    )

    assert second.status_code == 400

    assert (second.get_json() or {}).get("error") == "mask_provenance_unverified"

    assert "mask" not in (captured.get("context") or {})
