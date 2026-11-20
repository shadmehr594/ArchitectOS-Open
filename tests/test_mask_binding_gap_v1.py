# ==========================================================
# ARCHITECTOS — MASK SOURCE BINDING V1 — TESTS
#
# CPU-only. No GPU, no ComfyUI, no live socket. Every render entry is mocked.
#
# These began as the six RED reproductions of a confirmed defect: the masked
# Kontext route accepted any structurally plausible mask dict, never checking
# that the mask belonged to the image being edited. They now encode the
# REQUIRED behaviour after the MASK_SOURCE_BINDING_V1 correction and must be
# GREEN.
#
# The binding evidence is a SERVER-COMPUTED SHA-256 of the source image
# bytes, re-verified at guard time. A caller cannot forge it: the guard
# re-hashes the source this turn will actually edit and compares.
# ==========================================================

import hashlib
import types

import pytest

from core.vision.image_intent_v1 import (
    detect_unsupported_geometry_edit,
    precise_localized_route_available,
    source_image_digest,
)

LOCALIZED_FA = "این پنجره را حذف کن"      # remove this window


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(self, address, *a, **k):
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _write_image(path, payload=b"SOURCE-A-BYTES" * 64):
    path.write_bytes(payload)
    return path


def _mask_for(source_path, **overrides):
    """A mask dict as the corrected ingestion boundary would produce it."""

    mask = {
        "filename": "architectos_mask_0123456789abcdef.png",
        "dimensions": [384, 512],
        "source": "uploaded",
        "source_sha256": source_image_digest(str(source_path)),
        "source_size_bytes": source_path.stat().st_size,
    }
    mask.update(overrides)
    return mask


def _ctx(mask, source_path, kontext="1", fresh=True, **extra):
    context = {
        "mask": mask,
        "kontext_edit": kontext,
        "source_image_path": str(source_path),
        "source_sha256": source_image_digest(str(source_path)),
    }
    if fresh:
        context["precision_controls_supplied"] = True
    context.update(extra)
    return context


# ==========================================================
# THE SIX ORIGINAL REPRODUCTIONS — NOW GREEN
# ==========================================================

def test_unvalidated_but_structurally_plausible_mask_is_refused(tmp_path):
    """A hand-built mask carries no server digest, so it cannot bind."""

    source = _write_image(tmp_path / "source_A.png")

    invented = {
        "filename": "architectos_mask_never_validated.png",
        "dimensions": [384, 512],
        "source": "uploaded",
    }

    route = precise_localized_route_available(_ctx(invented, source))

    assert route["available"] is False
    assert route["reason"] == "mask_source_digest_missing"

    guard = detect_unsupported_geometry_edit(
        LOCALIZED_FA, context=_ctx(invented, source)
    )

    assert guard["unsupported"] is True


def test_mask_for_a_different_source_image_is_refused(tmp_path):
    """A mask whose digest is a DIFFERENT image's is refused."""

    source_a = _write_image(tmp_path / "source_A.png")
    source_b = _write_image(tmp_path / "source_B.png", b"SOURCE-B-BYTES" * 64)

    foreign = _mask_for(source_b)          # bound to B, presented for A

    route = precise_localized_route_available(_ctx(foreign, source_a))

    assert route["available"] is False
    assert route["reason"] == "mask_bound_to_a_different_source"


def test_mask_with_identical_dimensions_but_another_source_is_refused(tmp_path):
    """Same size is NOT proof of identity — the digest decides."""

    source_a = _write_image(tmp_path / "source_A.png", b"A" * 512)
    # different bytes, identical byte length
    source_b = _write_image(tmp_path / "source_B.png", b"B" * 512)

    assert source_a.stat().st_size == source_b.stat().st_size

    foreign = _mask_for(source_b)

    route = precise_localized_route_available(_ctx(foreign, source_a))

    assert route["available"] is False
    assert route["reason"] == "mask_bound_to_a_different_source"


def test_stale_mask_after_the_source_image_changed_is_refused(tmp_path):
    """The source file changed on disk after the mask was bound."""

    source = _write_image(tmp_path / "source_A.png")

    mask = _mask_for(source)

    assert precise_localized_route_available(_ctx(mask, source))["available"] is True

    # the source image is replaced
    source.write_bytes(b"REPLACED-SOURCE-BYTES" * 64)

    route = precise_localized_route_available(_ctx(mask, source))

    assert route["available"] is False
    assert route["reason"] in (
        "mask_bound_to_a_different_source", "source_image_unreadable",
    )


def test_direct_internal_invocation_cannot_bypass_the_binding(tmp_path):
    """`handle()` is not a validation boundary, so a mask that never passed
    ingestion must not pass here either."""

    source = _write_image(tmp_path / "source_A.png")

    forged = {
        "filename": "architectos_mask_smuggled_in.png",
        "dimensions": [384, 512],
        # a caller trying to forge the digest cannot: the guard re-hashes
        "source_sha256": "0" * 64,
    }

    route = precise_localized_route_available(_ctx(forged, source))

    assert route["available"] is False
    assert route["reason"] == "mask_bound_to_a_different_source"


def test_text_only_followup_with_a_foreign_mask_does_not_reach_the_edit_handler(
    tmp_path,
):
    import core.chat.chat_architect as ca
    from core.chat.session_registry_v1 import session_registry
    from core.vision.image_registry_v1 import image_registry

    chat = ca.ChatArchitect(types.SimpleNamespace())

    session = "mask_binding_gap"

    image_registry.reset(session)

    source_a = _write_image(tmp_path / "source_A.png")
    source_b = _write_image(tmp_path / "source_B.png", b"B" * 4096)

    image_registry.register(
        session, path=str(source_a), source_type="uploaded"
    )

    reached = {"edit": 0}

    original = chat.image_handler.handle_image_edit
    chat.image_handler.handle_image_edit = (
        lambda *a, **k: reached.__setitem__("edit", reached["edit"] + 1)
        or {"type": "image_render", "status": "MOCKED_NO_RENDER"}
    )

    session_registry.begin(session)

    try:
        result = chat.handle(
            LOCALIZED_FA,
            context={
                "session_id": session,
                "mode": "image_to_image",
                "mask": _mask_for(source_b),      # bound to a DIFFERENT image
                "kontext_edit": "1",
                "precision_controls_supplied": True,
            },
        )
    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = original

    assert reached["edit"] == 0, (
        "a mask never bound to the current source image reached the edit handler"
    )
    assert result.get("status") == "unsupported_edit"


# ==========================================================
# LEGITIMATE MASKED EDITS MUST STILL WORK
# ==========================================================

def test_legitimate_same_source_mask_passes_the_guard(tmp_path):
    source = _write_image(tmp_path / "source_A.png")

    mask = _mask_for(source)

    route = precise_localized_route_available(_ctx(mask, source))

    assert route["available"] is True

    guard = detect_unsupported_geometry_edit(
        LOCALIZED_FA, context=_ctx(mask, source)
    )

    assert guard["unsupported"] is False
    assert guard["routed_to"] == "flux_kontext_edit.json"


def test_legitimate_text_only_followup_binds_to_the_session_source(tmp_path):
    """A follow-up that carries no image may still bind, because the session's
    active source image is resolvable and hashed."""

    import core.chat.chat_architect as ca
    from core.chat.session_registry_v1 import session_registry
    from core.vision.image_registry_v1 import image_registry

    chat = ca.ChatArchitect(types.SimpleNamespace())

    session = "mask_binding_ok"

    image_registry.reset(session)

    source_a = _write_image(tmp_path / "source_A.png")

    image_registry.register(session, path=str(source_a), source_type="uploaded")

    reached = {"edit": 0}

    original = chat.image_handler.handle_image_edit
    chat.image_handler.handle_image_edit = (
        lambda *a, **k: reached.__setitem__("edit", reached["edit"] + 1)
        or {"type": "image_render", "status": "MOCKED_NO_RENDER"}
    )

    session_registry.begin(session)

    try:
        result = chat.handle(
            LOCALIZED_FA,
            context={
                "session_id": session,
                "mode": "image_to_image",
                "mask": _mask_for(source_a),      # the SAME image
                "kontext_edit": "1",
                "precision_controls_supplied": True,
            },
        )
    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = original

    assert result.get("status") != "unsupported_edit"
    assert reached["edit"] == 1, "a correctly bound mask must still reach the edit handler"


def test_stale_reuse_without_fresh_flags_is_still_refused(tmp_path):
    import core.chat.chat_architect as ca
    from core.chat.session_registry_v1 import session_registry
    from core.vision.image_registry_v1 import image_registry

    chat = ca.ChatArchitect(types.SimpleNamespace())

    session = "mask_binding_stale"

    image_registry.reset(session)

    source_a = _write_image(tmp_path / "source_A.png")

    image_registry.register(session, path=str(source_a), source_type="uploaded")

    reached = {"edit": 0}

    original = chat.image_handler.handle_image_edit
    chat.image_handler.handle_image_edit = (
        lambda *a, **k: reached.__setitem__("edit", reached["edit"] + 1)
        or {"type": "image_render", "status": "MOCKED"}
    )

    session_registry.begin(session)

    try:
        chat.state.update({
            "last_image_edit_context": {"mask": _mask_for(source_a)},
        })

        result = chat.handle(LOCALIZED_FA, context={"session_id": session})
    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = original

    assert result.get("status") == "unsupported_edit"
    assert reached["edit"] == 0


def test_dimensioned_and_bare_verb_still_refused_with_a_bound_mask(tmp_path):
    source = _write_image(tmp_path / "source_A.png")

    context = _ctx(_mask_for(source), source)

    dimensioned = detect_unsupported_geometry_edit(
        "این پنجره را ۸۰ سانت ببر راست", context=context
    )

    bare = detect_unsupported_geometry_edit("move", context=context)

    assert dimensioned["unsupported"] is True
    assert dimensioned["reason"] == "dimensioned_geometry_edit_not_supported"
    assert bare["unsupported"] is True
    assert bare["reason"] == "geometry_edit_not_supported"
