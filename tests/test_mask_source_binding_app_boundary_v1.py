# ==========================================================
# ARCHITECTOS — MASK SOURCE BINDING AT THE APP BOUNDARY (V1)
#
# CPU-only. No server, no socket, no ComfyUI, no GPU. The Flask test client
# drives the REAL `app.chat_api` boundary; nothing downstream is executed
# because `ChatArchitect._handle_internal` is replaced with a recorder.
#
# What this proves that the unit tests cannot:
#
#   the digest a mask carries is COMPUTED BY THE SERVER, from the image bytes
#   it received — not accepted from the client. A request that supplies its
#   own `source_sha256` does not get to choose it.
#
# Run:  python -m pytest tests/test_mask_source_binding_app_boundary_v1.py -q
# ==========================================================

import io
import json

import pytest

import app as CORE
from core.vision.image_intent_v1 import source_image_digest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(self, address, *a, **k):
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _png_bytes(size=(384, 512), colour=128):
    """A real, readable PNG — the boundary opens and measures the file."""

    from PIL import Image

    buffer = io.BytesIO()

    Image.new("RGB", size, (colour, colour, colour)).save(buffer, "PNG")

    buffer.seek(0)

    return buffer


def _capture_context(monkeypatch):
    """Replace the private internals with a recorder; the boundary stays real."""

    import core.chat.chat_architect as ca

    captured = {}

    def _record(self, text, context=None):
        captured["text"] = text
        captured["context"] = context
        return {"type": "chat", "status": "success", "result": "recorded"}

    monkeypatch.setattr(
        ca.ChatArchitect, "_handle_internal", _record, raising=True
    )

    return captured


def _post(client, data, files):
    return client.post(
        "/chat",
        data={**data, **files},
        content_type="multipart/form-data",
    )


def test_server_computes_the_mask_binding_digest(monkeypatch):
    """A same-size mask uploaded WITH its source is bound by the server."""

    captured = _capture_context(monkeypatch)

    client = CORE.app.test_client()

    source_bytes = _png_bytes()
    # SOURCE / MASK IDENTITY SAFETY V1 — the mask must be a DIFFERENT asset
    # from the source. This fixture previously reused the source's bytes for
    # convenience, which is now refused at the boundary (a mask that is
    # byte-identical to its source is SOURCE_MASK_MISROUTING). The assertion
    # below is unchanged: it is about WHO computes the digest, not the bytes.
    mask_bytes = _png_bytes(colour=250)

    # the client tries to dictate the digest — it must be ignored
    forged = "f" * 64

    response = _post(
        client,
        {
            "message": "این پنجره را حذف کن",
            "session_id": "bind_app_1",
            "mode": "image_to_image",
            "mask": json.dumps({
                "filename": "architectos_mask_client_named.png",
                "source_sha256": forged,
            }),
            "kontext_edit": "1",
        },
        {
            "image": (source_bytes, "source.png"),
            "mask": (mask_bytes, "mask.png"),
        },
    )

    assert response.status_code == 200

    context = captured.get("context") or {}

    mask = context.get("mask")

    assert isinstance(mask, dict), "the boundary produced no mask"

    digest = mask.get("source_sha256")

    assert digest and digest != forged, (
        "the server accepted a client-supplied digest instead of computing one"
    )

    assert len(digest) == 64, "the digest must be a full SHA-256 hex string"

    assert mask.get("source_size_bytes", 0) > 0

    # the server also kept the path it digested, so the guard can re-hash
    bound_path = mask.get("source_path")

    if bound_path:

        assert source_image_digest(bound_path) == digest


def test_mask_dimension_mismatch_is_refused_at_the_boundary(monkeypatch):
    """An uploaded mask of the wrong size is refused before any dispatch."""

    captured = _capture_context(monkeypatch)

    client = CORE.app.test_client()

    response = _post(
        client,
        {
            "message": "این پنجره را حذف کن",
            "session_id": "bind_app_2",
            "mode": "image_to_image",
            "kontext_edit": "1",
        },
        {
            "image": (_png_bytes((384, 512)), "source.png"),
            "mask": (_png_bytes((100, 100)), "mask.png"),
        },
    )

    assert response.status_code == 400

    payload = response.get_json() or {}

    assert payload.get("error") == "mask_dimension_mismatch"

    assert "mask" not in (captured.get("context") or {})


def test_asset_name_mask_with_no_source_available_is_refused(monkeypatch):
    """A text-only turn naming a mask asset, with no source image anywhere,
    has nothing to bind to and is refused rather than guessed."""

    captured = _capture_context(monkeypatch)

    client = CORE.app.test_client()

    response = client.post(
        "/chat",
        json={
            "message": "این پنجره را حذف کن",
            "session_id": "bind_app_unbound_session",
            "mode": "image_to_image",
            "mask": {"filename": "architectos_mask_orphan.png"},
            "kontext_edit": "1",
        },
    )

    # refused with a clear reason; nothing reaches the chat layer
    assert response.status_code == 400

    payload = response.get_json() or {}

    assert payload.get("error") in (
        "mask_source_unbound", "mask_asset_not_found", "invalid_mask_asset",
    )

    assert "mask" not in (captured.get("context") or {})


def test_digest_helper_matches_the_boundary_computation(tmp_path):
    """The guard's digest helper and the boundary agree on the same bytes."""

    path = tmp_path / "x.png"

    path.write_bytes(b"boundary-parity" * 128)

    import hashlib

    assert source_image_digest(str(path)) == hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
