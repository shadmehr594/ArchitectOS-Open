"""FLOOR_GUARD_MIXED_CLAUSE_ORDINAL_FIX_V1 — focused regression suite.

WHY THIS FILE EXISTS
====================
`ARCHITECTOS_DAY_TO_NIGHT_VISUAL_ACCEPTANCE_V1.md` blocked before GPU
execution because two floor-restructuring guard bypasses were reproduced
against the real dispatch layer:

  * **mixed clause** — `طبقات را حفظ کن ولی یک طبقه اضافه کن` passed,
    because `is_floor_restructuring_edit()` treated ANY preservation match
    anywhere in the message as a veto over the whole message, discarding an
    affirmative restructuring clause it had already found.
  * **English ordinals** — `add a third floor` passed even standalone,
    because the addition family accepted cardinals only.

WHAT THIS SUITE PINS
====================
1. The nine required RED cases are refused with
   `floor_count_restructuring_not_supported`.
2. Mixed-clause behaviour is clause-scoped and order-independent, in both
   languages (rules A, C, E, F).
3. Negated additions are never read as affirmative (rule B).
4. Ordinals are covered by the bounded vocabulary — no general parser
   (rule D).
5. Lighting / facade requests that merely mention a numbered floor are not
   blocked (rule G).
6. The refusal holds at the REAL production entry points, with zero calls to
   `handle_image_edit`, zero `render()`, zero ComfyUI submissions and zero
   derived-image registrations.
7. Ordinary appearance edits keep their existing route.

CPU ONLY. NO GPU. NO ComfyUI. NO OLLAMA. NO NETWORK. NO PRODUCTION EDIT.
"""

import contextlib
import io
import os
import socket
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.vision.image_intent_v1 import (
    detect_unsupported_geometry_edit,
    is_floor_restructuring_edit,
)
from core.vision.image_registry_v1 import image_registry

REASON = "floor_count_restructuring_not_supported"

# Verified daytime villa — read only, never modified.
SOURCE_IMAGE = os.path.join(
    ROOT, "data", "projects", "project_09884e3a", "renders", "render_001_6819dd.png"
)


# ==========================================================
# 1. REQUIRED RED CASES
# ==========================================================

REQUIRED_RED_CASES = [
    "طبقات را حفظ کن ولی یک طبقه اضافه کن",
    "Keep two floors, but add a third floor",
    "add a third floor",
    "add a fourth floor",
    "add the third floor",
    "add a 3rd floor",
    "بدون تغییر طبقات، یک طبقه اضافه کن",
    "یک طبقه اضافه کن ولی طبقات را حفظ کن",
    "تعداد طبقات را تغییر نده ولی یک طبقه اضافه کن",
]


@pytest.mark.parametrize("phrase", REQUIRED_RED_CASES)
def test_required_red_case_is_refused(phrase):
    guard = detect_unsupported_geometry_edit(phrase)

    assert guard["unsupported"] is True, (
        "Bypass not closed: %r was permitted" % (phrase,)
    )
    assert guard["reason"] == REASON
    assert is_floor_restructuring_edit(phrase) is True


# ==========================================================
# 2. MIXED-CLAUSE MATRIX (rules A, C, E, F)
# ==========================================================

MIXED_CLAUSE_REFUSED = [
    # preservation first, addition second
    "طبقات را حفظ کن ولی یک طبقه اضافه کن",
    "طبقات را حفظ کن و یک طبقه اضافه کن",
    "بدون تغییر طبقات، یک طبقه اضافه کن",
    "تعداد طبقات را تغییر نده ولی یک طبقه اضافه کن",
    "Keep two floors, but add a third floor",
    "Keep the existing 2 floors, but add a third floor",
    "Do not change the number of floors, but add a fourth floor",
    # addition first, preservation second (rule E — order must not matter)
    "یک طبقه اضافه کن ولی طبقات را حفظ کن",
    "یک طبقه اضافه کن، طبقات را حفظ کن",
    "Add a third floor, but keep two floors",
    "add a third floor and do not change the rest of the floors",
    # removal under preservation
    "طبقات را حفظ کن ولی یک طبقه کم کن",
    "Keep two floors, but remove one floor",
]


@pytest.mark.parametrize("phrase", MIXED_CLAUSE_REFUSED)
def test_mixed_clause_restructuring_refused(phrase):
    guard = detect_unsupported_geometry_edit(phrase)

    assert guard["unsupported"] is True, (
        "Mixed-clause restructuring permitted: %r" % (phrase,)
    )
    assert guard["reason"] == REASON


# ==========================================================
# 3. ENGLISH ORDINAL MATRIX (rule D)
# ==========================================================

ORDINAL_ADDITIONS = [
    "add a third floor",
    "add a fourth floor",
    "add a fifth floor",
    "add the third floor",
    "add the fourth floor",
    "add a 3rd floor",
    "add a 4th floor",
    "add a third storey",
    "add a fourth story",
    "add a third floor to this building",
    "introduce a third floor",
    "remove the third floor",
    "remove a 3rd floor",
]


@pytest.mark.parametrize("phrase", ORDINAL_ADDITIONS)
def test_ordinal_floor_restructuring_refused(phrase):
    guard = detect_unsupported_geometry_edit(phrase)

    assert guard["unsupported"] is True, (
        "Ordinal floor change permitted: %r" % (phrase,)
    )
    assert guard["reason"] == REASON


# ==========================================================
# 4. NEGATION (rule B) — must never be read as affirmative
# ==========================================================

NEGATED_ADDITIONS = [
    "Do not add a third floor",
    "Do not add another floor",
    "Do not add a floor",
    "Don't add a third floor",
    "Never add a third floor",
    "Do not add or remove floors",
    "Do not remove any floors",
    "Do not add another floor; make it night",
    "طبقه سوم را اضافه نکن",
    "یک طبقه اضافه نکن، نما را شب کن",
    "یک طبقه اضافه نکن",
    "طبقه چهارم را اضافه نکنید",
]


@pytest.mark.parametrize("phrase", NEGATED_ADDITIONS)
def test_negated_addition_is_not_floor_restructuring(phrase):
    assert is_floor_restructuring_edit(phrase) is False, (
        "Negated addition read as affirmative: %r" % (phrase,)
    )


# ==========================================================
# 5. REQUIRED NEGATIVE CONTROLS (rule G)
# ==========================================================

REQUIRED_NEGATIVE_CONTROLS = [
    "Do not add a third floor",
    "Do not remove any floors",
    "Keep the building two-storey",
    "Make this two-storey villa look like night",
    "Keep two floors and change the lighting",
    "Add lighting to the third-floor balcony",
    "Change the second-floor window color",
    "Do not add another floor; make it night",
    "طبقه سوم را اضافه نکن",
    "یک طبقه اضافه نکن، نما را شب کن",
    "بدون تغییر طبقات نما را شب کن",
    "ساختمان سه طبقه را آجری کن",
    "نورپردازی بالکن طبقه سوم را تغییر بده",
]


@pytest.mark.parametrize("phrase", REQUIRED_NEGATIVE_CONTROLS)
def test_required_negative_control_not_floor_restructuring(phrase):
    guard = detect_unsupported_geometry_edit(phrase)

    assert guard.get("reason") != REASON, (
        "Negative control refused as floor restructuring: %r" % (phrase,)
    )


# ==========================================================
# 6. OTHER GEOMETRY TIERS REMAIN AUTHORITATIVE
# ==========================================================

def test_existing_geometry_tiers_unchanged():
    g1 = detect_unsupported_geometry_edit("این پنجره رو 80 سانت ببر راست")
    assert g1["reason"] == "dimensioned_geometry_edit_not_supported"

    g2 = detect_unsupported_geometry_edit("این پنجره رو حذف کن")
    assert g2["reason"] == "localized_geometry_edit_not_supported"

    g3 = detect_unsupported_geometry_edit("جابجا کن")
    assert g3["reason"] == "geometry_edit_not_supported"


# ==========================================================
# 7. PRODUCTION ROUTING — real entry points, zero execution
# ==========================================================

@pytest.fixture(scope="module")
def chat():
    with contextlib.redirect_stdout(io.StringIO()):
        return ChatArchitect(types.SimpleNamespace())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("outbound connection refused")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


class ExecutionProbe:
    """Records every execution boundary the guard is supposed to protect."""

    def __init__(self):
        self.edit_calls = []
        self.render_calls = 0
        self.comfy_submissions = 0


@pytest.fixture
def armed(chat):
    """Install recording stubs on the real collaborator objects."""
    probe = ExecutionProbe()

    original_edit = chat.image_handler.handle_image_edit
    original_render = chat.render_runtime.render

    def _edit(*args, **kwargs):
        probe.edit_calls.append(kwargs.get("text"))
        return {"type": "image_render", "status": "EDIT_DISPATCHED"}

    def _render(*args, **kwargs):
        probe.render_calls += 1
        return {"status": "RENDER_CALLED"}

    class _Comfy:
        def submit(self, workflow):
            probe.comfy_submissions += 1
            return {"status": "SUBMITTED"}

    chat.image_handler.handle_image_edit = _edit
    chat.render_runtime.render = _render
    chat.render_runtime.executor.comfy = _Comfy()

    try:
        yield probe
    finally:
        chat.image_handler.handle_image_edit = original_edit
        chat.render_runtime.render = original_render


def _register(session_name):
    image_registry.reset(session_name)
    image_registry.register(session_name, path=SOURCE_IMAGE, source_type="text_to_image")


def _classify(result, probe):
    """Name the outcome instead of flattening every non-dispatch into 'refused'."""

    if probe.edit_calls:
        return "ordinary_edit_dispatch"

    result = result if isinstance(result, dict) else {}
    reason = (result.get("unsupported_edit") or {}).get("reason")

    if result.get("status") == "unsupported_edit" and reason == REASON:
        return "floor_guard_refusal"

    if result.get("status") == "unsupported_edit":
        return "other_geometry_guard_refusal"

    return "general_conversation_or_degraded"


@pytest.mark.parametrize("phrase", REQUIRED_RED_CASES)
def test_route_image_edit_refuses_without_execution(chat, armed, phrase):
    session = "fgfix_route_%d" % abs(hash(phrase) % 100000)
    _register(session)

    session_registry.begin(session)
    try:
        before = image_registry.count(session)
        result = chat._route_image_edit(
            text=phrase,
            image_record=image_registry.active(session),
            image_reference={},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
            context={"session_id": session},
        )
        after = image_registry.count(session)
    finally:
        session_registry.end()

    assert _classify(result, armed) == "floor_guard_refusal"
    assert armed.edit_calls == []
    assert armed.render_calls == 0
    assert armed.comfy_submissions == 0
    assert after == before


@pytest.mark.parametrize("phrase", REQUIRED_RED_CASES)
def test_router_edit_route_refuses_without_execution(chat, armed, phrase):
    session = "fgfix_router_%d" % abs(hash(phrase) % 100000)
    _register(session)

    session_registry.begin(session)
    try:
        before = image_registry.count(session)
        result = chat._router_edit_route(
            text=phrase,
            image=None,
            context={"session_id": session},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
        )
        after = image_registry.count(session)
    finally:
        session_registry.end()

    assert _classify(result, armed) == "floor_guard_refusal"
    assert armed.edit_calls == []
    assert armed.render_calls == 0
    assert armed.comfy_submissions == 0
    assert after == before


@pytest.mark.parametrize("phrase", REQUIRED_RED_CASES)
def test_handle_never_executes_a_refused_floor_change(chat, armed, phrase):
    """Safety property only.

    `handle()` performs full dispatch and, for some inputs, needs an LLM that
    this CPU-only suite refuses. A `degraded` outcome is therefore NOT a guard
    refusal and is never reported as one — the assertion is the safety
    property: the edit boundary is never reached.
    """

    session = "fgfix_handle_%d" % abs(hash(phrase) % 100000)
    _register(session)

    session_registry.begin(session)
    try:
        before = image_registry.count(session)
        with contextlib.redirect_stdout(io.StringIO()):
            result = chat.handle(phrase, context={"session_id": session})
        after = image_registry.count(session)
    finally:
        session_registry.end()

    outcome = _classify(result, armed)

    assert outcome != "ordinary_edit_dispatch", (
        "Refused floor change reached the edit boundary: %r (%s)" % (phrase, outcome)
    )
    assert armed.edit_calls == []
    assert armed.render_calls == 0
    assert armed.comfy_submissions == 0
    assert after == before


# ----------------------------------------------------------
# 8. Permitted appearance edits keep their existing route
# ----------------------------------------------------------

PERMITTED_EDITS = [
    "بدون تغییر طبقات نما را شب کن",
    "همین ساختمان را شب کن. فقط نورپردازی روز را به نورپردازی واقعی شب تبدیل کن.",
    "Add lighting to the third-floor balcony",
    "Keep two floors and change the lighting",
]


@pytest.mark.parametrize("phrase", PERMITTED_EDITS)
def test_permitted_edit_still_dispatches(chat, armed, phrase):
    session = "fgfix_perm_%d" % abs(hash(phrase) % 100000)
    _register(session)

    session_registry.begin(session)
    try:
        result = chat._route_image_edit(
            text=phrase,
            image_record=image_registry.active(session),
            image_reference={},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
            context={"session_id": session},
        )
    finally:
        session_registry.end()

    assert _classify(result, armed) == "ordinary_edit_dispatch", (
        "Permitted appearance edit lost its route: %r" % (phrase,)
    )
    assert len(armed.edit_calls) == 1
