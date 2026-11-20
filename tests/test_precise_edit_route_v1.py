# ==========================================================
# ARCHITECTOS — PRECISE_EDIT_ROUTE_V1 — TESTS
#
# Deterministic. CPU-only. No GPU, no ComfyUI, no live socket.
#
# Scope: the localized-geometry guard now refuses a localized opening/railing
# edit ONLY while no validated masked-Kontext route exists. These tests prove
# the guard is not weakened by any unvalidated mask value, and that a genuinely
# validated route is what lets an explicitly authorized request through.
#
# Capability boundary (from the existing audit, asserted below):
#   supports_local_edit      = true    (a caller-supplied mask is honoured)
#   supports_region_grounding= false   (ArchitectOS derives NO mask)
#   supports_geometry_edit   = false
# Nothing here claims the model can create, remove or dimension an opening.
# ==========================================================

import types

import pytest

from core.vision.image_intent_v1 import (
    detect_unsupported_geometry_edit,
    precise_localized_route_available,
    source_image_digest,
)

# A localized opening/railing request — tier 2 of the guard.
LOCALIZED_FA = "این پنجره را حذف کن"                 # remove this window
LOCALIZED_RAILING_FA = "یک نرده جدید به بالکن اضافه کن"  # add a railing
DIMENSIONED = "این پنجره را ۸۰ سانت ببر راست"          # dimensioned: tier 1

#: MASK_SOURCE_BINDING_V1 — a mask is accepted only when it carries the
#: SERVER-COMPUTED digest of the source image this turn will edit. The fixture
#: writes a real source file so the guard can re-hash it, exactly as ingestion
#: would have done after reading and measuring the mask.
_SOURCE_BYTES = b"ARCHITECTOS-SOURCE-A" * 64


@pytest.fixture
def source_image(tmp_path):
    path = tmp_path / "source_A.png"
    path.write_bytes(_SOURCE_BYTES)
    return path


def _bound_mask(source_path):
    return {
        "filename": "architectos_mask_0123456789abcdef.png",
        "dimensions": [384, 512],
        "mode": "L",
        "source": "uploaded",
        "source_sha256": source_image_digest(str(source_path)),
        "source_size_bytes": source_path.stat().st_size,
    }


def _ctx(mask=None, kontext="1", fresh=True, source_path=None):
    """A guard context. `mask=None` means "no mask bound to the source".

    When `source_path` is given the context carries its real digest, so the
    binding check can verify against the source this turn edits.
    """

    context = {"kontext_edit": kontext}

    if mask is not None:
        context["mask"] = mask

    if source_path is not None:
        context["source_image_path"] = str(source_path)
        context["source_sha256"] = source_image_digest(str(source_path))

    if fresh:
        context["precision_controls_supplied"] = True

    return context


# ==========================================================
# 10 — NO NETWORK, ANYWHERE IN THIS MODULE
# ==========================================================

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """A live connection in any test here is a hard failure, not a warning."""

    import socket

    attempts = []

    def _blocked(self, address, *a, **k):
        attempts.append(address)
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)

    return attempts


# ==========================================================
# 1 — LOCALIZED EDIT WITHOUT A MASK IS STILL REFUSED
# ==========================================================

@pytest.mark.parametrize("text", [LOCALIZED_FA, LOCALIZED_RAILING_FA])
def test_localized_edit_without_a_mask_is_refused(text):
    for context in (None, {}):
        guard = detect_unsupported_geometry_edit(text, context=context)

        assert guard["unsupported"] is True
        assert guard["reason"] == "localized_geometry_edit_not_supported"


def test_guard_default_argument_is_unchanged_for_existing_callers():
    """Every pre-existing caller passes only `text`, so that must not change."""

    guard = detect_unsupported_geometry_edit(LOCALIZED_FA)

    assert guard["unsupported"] is True


# ==========================================================
# 2 — INVALID / EMPTY / MISMATCHED MASKS CANNOT BYPASS
# ==========================================================

@pytest.mark.parametrize(
    "mask",
    [
        None,
        "",
        "architectos_mask_abc.png",              # truthy string is NOT a mask
        "false",                                  # bool("false") is True
        0,
        [],
        {},
        {"filename": "m.png"},                    # no measured dimensions
        {"filename": "", "dimensions": [384, 512], "source": "uploaded"},
        {"dimensions": [384, 512], "source": "uploaded"},   # no filename
        {"filename": "m.png", "dimensions": [0, 0], "source": "uploaded"},
        {"filename": "m.png", "dimensions": [-1, 512], "source": "uploaded"},
        {"filename": "m.png", "dimensions": ["x", "y"], "source": "uploaded"},
        {"filename": "m.png", "dimensions": [384], "source": "uploaded"},
        {"filename": "m.png", "dimensions": [384, 512, 1], "source": "uploaded"},
        {"filename": "m.png", "dimensions": None, "source": "uploaded"},
        {"filename": "m.png", "dimensions": "384x512", "source": "uploaded"},
        {"filename": "a/b.png", "dimensions": [384, 512], "source": "uploaded"},
        {"filename": "..\\..\\x.png", "dimensions": [384, 512], "source": "uploaded"},
        {"filename": "..", "dimensions": [384, 512], "source": "uploaded"},
    ],
)
def test_invalid_masks_cannot_bypass_the_guard(mask):
    guard = detect_unsupported_geometry_edit(LOCALIZED_FA, context=_ctx(mask=mask))

    assert guard["unsupported"] is True
    assert guard["reason"] == "localized_geometry_edit_not_supported"

    route = precise_localized_route_available(_ctx(mask=mask))

    assert route["available"] is False


def test_asset_name_mask_bound_to_the_source_is_accepted(source_image):
    """The asset-name path writes no `source` marker but IS bound by the
    server digest, so a legitimately validated asset mask still works."""

    asset_mask = {
        "filename": "architectos_mask_existing.png",
        "dimensions": [384, 512],
        "source_sha256": source_image_digest(str(source_image)),
    }

    route = precise_localized_route_available(
        _ctx(mask=asset_mask, source_path=source_image)
    )

    assert route["available"] is True

    guard = detect_unsupported_geometry_edit(
        LOCALIZED_FA, context=_ctx(mask=asset_mask, source_path=source_image)
    )

    assert guard["unsupported"] is False


def test_an_unmeasured_filename_dict_is_still_refused():
    """A filename alone proves nothing was opened or measured."""

    route = precise_localized_route_available(_ctx(mask={"filename": "m.png"}))

    assert route["available"] is False
    assert route["reason"] == "no_validated_mask"


# ==========================================================
# 3 — A MASK NOT BOUND TO THIS SOURCE CANNOT BYPASS
# ==========================================================

def test_mask_without_a_fresh_binding_is_refused(source_image):
    """A structurally valid mask with no fresh validation is refused
    before binding is even consulted."""

    context = _ctx(
        mask=_bound_mask(source_image), source_path=source_image, fresh=False
    )

    guard = detect_unsupported_geometry_edit(LOCALIZED_FA, context=context)

    assert guard["unsupported"] is True

    route = precise_localized_route_available(context)

    assert route["available"] is False
    assert route["reason"] == "mask_not_bound_to_this_source"


def test_mask_without_a_server_digest_is_refused(source_image):
    """MASK_SOURCE_BINDING_V1 — structural plausibility is not binding."""

    unbound = {
        "filename": "architectos_mask_0123456789abcdef.png",
        "dimensions": [384, 512],
        "source": "uploaded",
    }

    route = precise_localized_route_available(
        _ctx(mask=unbound, source_path=source_image)
    )

    assert route["available"] is False
    assert route["reason"] == "mask_source_digest_missing"


# ==========================================================
# 4 — KONTEXT DISABLED OR UNAVAILABLE KEEPS THE REFUSAL
# ==========================================================

@pytest.mark.parametrize("kontext", ["", "0", "false", "no", "off", None, False])
def test_kontext_not_selected_keeps_the_refusal(kontext, source_image):
    context = _ctx(
        mask=_bound_mask(source_image),
        kontext=kontext,
        source_path=source_image,
    )

    guard = detect_unsupported_geometry_edit(LOCALIZED_FA, context=context)

    assert guard["unsupported"] is True

    route = precise_localized_route_available(context)

    assert route["available"] is False
    assert route["reason"] == "kontext_edit_not_selected"


def test_kontext_workflow_without_local_edit_keeps_the_refusal(
    monkeypatch, source_image
):
    """If the graph genuinely lacked a mask route, the guard must refuse."""

    import core.vision.image_intent_v1 as ii

    monkeypatch.setattr(ii, "_kontext_local_edit_available", lambda: False)

    context = _ctx(mask=_bound_mask(source_image), source_path=source_image)

    guard = detect_unsupported_geometry_edit(LOCALIZED_FA, context=context)

    assert guard["unsupported"] is True

    route = precise_localized_route_available(context)

    assert route["available"] is False
    assert route["reason"] == "local_edit_unavailable_in_workflow"


# ==========================================================
# 5 — DIMENSIONED EDITS REMAIN REFUSED (even with a valid mask)
# ==========================================================

def test_dimensioned_edits_remain_refused_with_and_without_a_valid_mask(
    source_image,
):
    without = detect_unsupported_geometry_edit(DIMENSIONED)

    with_mask = detect_unsupported_geometry_edit(
        DIMENSIONED,
        context=_ctx(mask=_bound_mask(source_image), source_path=source_image),
    )

    assert without["unsupported"] is True
    assert with_mask["unsupported"] is True
    assert with_mask["reason"] == "dimensioned_geometry_edit_not_supported"


def test_bare_geometry_verb_remains_refused_with_a_valid_mask(source_image):
    """Tier 3 is unchanged: no named component means no localized route."""

    guard = detect_unsupported_geometry_edit(
        "move",
        context=_ctx(mask=_bound_mask(source_image), source_path=source_image),
    )

    assert guard["unsupported"] is True
    assert guard["reason"] == "geometry_edit_not_supported"


# ==========================================================
# 6 — A VALID MASKED LOCALIZED REQUEST CAN PASS
# ==========================================================

@pytest.mark.parametrize("text", [LOCALIZED_FA, LOCALIZED_RAILING_FA])
def test_valid_masked_localized_request_passes_the_guard(text, source_image):
    guard = detect_unsupported_geometry_edit(
        text,
        context=_ctx(mask=_bound_mask(source_image), source_path=source_image),
    )

    assert guard["unsupported"] is False
    assert guard["reason"] is None
    assert guard["routed_to"] == "flux_kontext_edit.json"


def test_appearance_edits_are_unaffected_by_the_route():
    for phrase in ("همینو شب کن", "نما رو سنگ کن", "make it night"):
        guard = detect_unsupported_geometry_edit(phrase)
        assert guard["unsupported"] is False, phrase


# ==========================================================
# 7 — BOTH GUARD CALL SITES BEHAVE CONSISTENTLY
# ==========================================================

def _chat():
    import core.chat.chat_architect as ca
    return ca.ChatArchitect(types.SimpleNamespace())


def _run_turn(text, with_mask, source_path):
    import core.chat.chat_architect as ca
    from core.chat.session_registry_v1 import session_registry
    from core.vision.image_registry_v1 import image_registry

    chat = _chat()

    session = "precise_route_test"

    image_registry.reset(session)

    image_registry.register(
        session, path=str(source_path), source_type="uploaded"
    )

    seen = []

    real = ca.detect_unsupported_geometry_edit

    def _spy(text_arg, context=None):
        decision = real(text_arg, context=context)
        seen.append((context, decision))
        return decision

    ca.detect_unsupported_geometry_edit = _spy

    reached = {"edit": 0}

    def _record_edit(*_a, **_k):
        reached["edit"] += 1
        return {"type": "image_render", "status": "MOCKED_NO_RENDER"}

    original = chat.image_handler.handle_image_edit
    chat.image_handler.handle_image_edit = _record_edit

    session_registry.begin(session)

    try:
        context = {
            "session_id": session,
            "image": str(source_path),
            "mode": "image_to_image",
        }

        if with_mask:
            context["mask"] = _bound_mask(source_path)
            context["kontext_edit"] = "1"
            context["precision_controls_supplied"] = True

        result = chat.handle(text, context=context)

    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = original
        ca.detect_unsupported_geometry_edit = real

    return seen, reached, result


def test_both_guard_call_sites_carry_the_mask_and_agree_to_pass(source_image):
    seen, reached, result = _run_turn(
        LOCALIZED_FA, with_mask=True, source_path=source_image
    )

    assert len(seen) >= 2, "both guard call sites must run"

    for context, decision in seen:
        assert isinstance(context, dict) and context.get("mask")
        assert decision["unsupported"] is False, (
            "every call site must agree a validated route exists"
        )
        assert decision["routed_to"] == "flux_kontext_edit.json"

    assert result.get("status") != "unsupported_edit"
    assert reached["edit"] == 1, "the validated route must reach the edit handler"


def test_both_guard_call_sites_agree_to_refuse_without_a_mask(source_image):
    seen, reached, result = _run_turn(
        LOCALIZED_FA, with_mask=False, source_path=source_image
    )

    # The pre-routing guard refuses and returns, so the later call site is
    # never reached. One call carrying no mask is the correct refusal path.
    assert len(seen) >= 1

    for context, decision in seen:
        assert not (isinstance(context, dict) and context.get("mask"))
        assert decision["unsupported"] is True
        assert decision["reason"] == "localized_geometry_edit_not_supported"

    assert result.get("status") == "unsupported_edit"
    assert result.get("engine") == "image_edit_guard"
    assert reached["edit"] == 0, "no execution may occur"


def test_every_guard_call_site_forwards_the_mask_context():
    """No guard call site may silently drop `context`.

    A site that omitted it would refuse a request every other site allows,
    which is exactly the inconsistency this change removes. Checked
    structurally so a future call site cannot reintroduce the gap.
    """

    import re
    from pathlib import Path

    source = Path("core/chat/chat_architect.py").read_text(encoding="utf-8")

    calls = re.findall(
        r"detect_unsupported_geometry_edit\(([^)]*)\)", source
    )

    assert len(calls) >= 3, "the guard call sites must still be present"

    for arguments in calls:
        assert "context=" in arguments, (
            "a guard call site does not forward context: %r" % (arguments,)
        )


def test_both_guard_call_sites_refuse_a_mask_not_bound_to_this_source(
    source_image,
):
    """A mask dict present in context WITHOUT fresh validation is refused."""

    seen, reached, result = _run_turn(
        LOCALIZED_FA, with_mask=True, source_path=source_image
    )

    # sanity: the bound case passes, so the refusal below is about binding
    assert result.get("status") != "unsupported_edit"

    guard = detect_unsupported_geometry_edit(
        LOCALIZED_FA,
        context=_ctx(
            mask=_bound_mask(source_image),
            source_path=source_image,
            fresh=False,
        ),
    )

    assert guard["unsupported"] is True


# ==========================================================
# 8 — THE WORKFLOW SELECTOR CHOOSES THE MASKED KONTEXT PATH
# ==========================================================

def test_workflow_selector_chooses_the_masked_kontext_path():
    from core.render.workflow_selector import WorkflowSelector

    selector = WorkflowSelector()

    assert selector.select(
        {"engine": "flux", "mode": "img2img", "kontext_edit": True}
    ) == "flux_kontext_edit.json"

    # a supplied mask implies the precise route even without the flag
    assert selector.select(
        {"engine": "flux", "mode": "img2img", "mask": {"filename": "m.png"}}
    ) == "flux_kontext_edit.json"

    # and the ordinary path is untouched
    assert selector.select(
        {"engine": "flux", "mode": "img2img"}
    ) == "flux_img2img.json"


def test_capability_boundary_is_unchanged():
    """Local edit yes; region grounding and geometric editing no."""

    from core.render.image_edit_capability_v1 import capability_flags

    flags = capability_flags(
        "core/render/workflows/flux_kontext_edit.json"
    )

    assert flags["supports_local_edit"] is True
    assert flags["supports_instruction_edit"] is True
    assert flags["supports_region_grounding"] is False
    assert flags["supports_geometry_edit"] is False


# ==========================================================
# 9 — RESOLVER EXCEPTIONS REMAIN FAIL-CLOSED BEFORE THE LEASE
# ==========================================================

class _FakeLease:
    def __init__(self):
        self.acquires = 0

    def acquire(self):
        self.acquires += 1
        return True

    def release(self):
        pass


class _CaptureExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, injected_workflow, engine):
        self.calls.append(engine)
        return {"status": "dry_run_capture", "engine": engine}


def _gpu_isolated(monkeypatch, tmp_path):
    import core.runtime.gpu_handoff_v1 as gh

    target = tmp_path / "gpu_handoff"

    target.mkdir()

    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    monkeypatch.delenv("ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB", raising=False)

    lease = _FakeLease()

    monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)
    monkeypatch.setattr(gh, "unload_ollama_models_for_render", lambda **k: {
        "status": "not_loaded", "reason": None, "ownership": "exclusive",
        "loaded_before": [], "unloaded": [], "failed": [], "skipped_in_use": [],
        "vram_free_before": 16 * 1024 ** 3, "vram_free_after": 16 * 1024 ** 3,
    })
    monkeypatch.setattr(gh, "require_render_vram", lambda h2=None, *a, **k: {
        "ok": True, "reason": "ok", "free_mib": 16000.0, "min_free_mib": 11264.0,
        "measurement_source": "h2.vram_free_after", "raw_bytes": 16 * 1024 ** 3,
    })
    monkeypatch.setattr(gh, "release_comfyui_for_vision",
                        lambda *a, **k: {"status": "blocked"})

    return lease


def test_resolver_exception_remains_fail_closed_before_the_lease(
    monkeypatch, tmp_path, _no_network
):
    import core.prompt_intelligence.geometry_authority_handoff_v1 as authority_module
    from core.render.render_runtime import RenderRuntime

    lease = _gpu_isolated(monkeypatch, tmp_path)

    def _raise(*_a, **_k):
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(authority_module, "resolve_geometry_authority", _raise)

    runtime = RenderRuntime()

    executor = _CaptureExecutor()

    runtime.executor = executor

    design = {
        "prompt": "این پنجره را حذف کن",
        "mode": "img2img",
        "architectural_intent": {
            "normalized_prompt": "این پنجره را حذف کن",
            "preserve_geometry": True,
            "preserve_constraints": ["main_window_positions", "camera"],
        },
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "seed": 7,
    }

    result = runtime.render(
        "precise-route-test", design, "flux",
        {"path": "uploads/up.png", "filename": "base.png"},
    )

    assert result["status"] == "geometry_authority_blocked"
    assert result["reason"] == "authority_resolver_failed"
    assert lease.acquires == 0, "no lease may be taken"
    assert executor.calls == [], "nothing may be submitted"
    assert _no_network == [], "no socket may be opened"
