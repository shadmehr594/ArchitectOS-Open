# ==========================================================
# ARCHITECTOS — FLOOR RESTRUCTURING EXECUTION GUARD V1 — TESTS
#
# Deterministic. CPU-only. No GPU, no ComfyUI, no live Ollama.
#
# Proves:
#   1. Explicit floor restructuring requests (English & Persian) are refused.
#   2. The refusal reason is 'floor_count_restructuring_not_supported'.
#   3. Negative controls (materials, night, preservation, floor locations) remain permitted.
#   4. Ambiguous restructuring requests are refused rather than executing structural edits.
#   5. Pre-dispatch refusal blocks RenderRuntime, Comfy submission, and ImageHandler.
#   6. Existing precise-geometry and masked-edit guard behaviors remain intact.
#   7. Valid text-to-image generations are not blocked.
# ==========================================================

import os
import sys
import types
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.vision.image_intent_v1 import (
    detect_unsupported_geometry_edit,
    classify_image_intent,
    is_floor_restructuring_edit,
    INTENT_EDIT,
)
from core.chat.chat_architect import ChatArchitect
from core.vision.image_registry_v1 import image_registry
from core.chat.session_registry_v1 import session_registry

SOURCE_IMAGE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"


# ----------------------------------------------------------
# 1. POSITIVE RESTRUCTURING EXAMPLES (MUST BE REFUSED)
# ----------------------------------------------------------

ENGLISH_POSITIVE_CASES = [
    "make it 3 floors",
    "change this two-storey building to three storeys",
    "add another floor to this building",
    "remove one floor",
    "make this building four-storey",
    "increase the floor count from 2 to 3",
    "convert this 2-storey villa into a 3-storey villa",
    "make it between two and four floors",
    "increase it to at most four storeys",
    "add a floor",
    "add two more floors to the building",
    "change to three floors",
    "remove a floor",
    "reduce the floor count to 2",
    "make this villa 3 storeys",
    "make the house two storeys",
    "change this to three floors",
    "remove 2 floors",
    "add 3 floors",
    "add another two floors",
]

PERSIAN_POSITIVE_CASES = [
    "تعداد طبقات را به سه طبقه تغییر بده",
    "این ساختمان را سه طبقه کن",
    "یک طبقه به ساختمان اضافه کن",
    "یک طبقه از ساختمان کم کن",
    "ساختمان دو طبقه را چهار طبقه کن",
    "تعداد طبقات را افزایش بده",
    "طبقه سوم را به ساختمان اضافه کن",
    "ساختمان را بین دو تا چهار طبقه کن",
    "سه طبقه کن",
    "۴ طبقه کن",
    "یک طبقه اضافه کن",
    "طبقه اضافه کن",
    "تعداد طبقات را کاهش بده",
    "تعداد طبقات را بیشتر کن",
    "این ویلا را چهار طبقه کن",
    "این عمارت را ۳ طبقه کن",
    "تعداد طبقاتش را سه طبقه کن",
    "دو طبقه به این ساختمان اضافه کن",
    "دو طبقه از این ساختمان کم کن",
    "طبقه چهارم را اضافه کن",
]


@pytest.mark.parametrize("phrase", ENGLISH_POSITIVE_CASES)
def test_english_floor_restructuring_refused(phrase):
    guard = detect_unsupported_geometry_edit(phrase)
    assert guard["unsupported"] is True, f"Expected '{phrase}' to be refused by guard"
    assert guard["reason"] == "floor_count_restructuring_not_supported", (
        f"Expected reason 'floor_count_restructuring_not_supported', got {guard.get('reason')}"
    )


@pytest.mark.parametrize("phrase", PERSIAN_POSITIVE_CASES)
def test_persian_floor_restructuring_refused(phrase):
    guard = detect_unsupported_geometry_edit(phrase)
    assert guard["unsupported"] is True, f"Expected '{phrase}' to be refused by guard"
    assert guard["reason"] == "floor_count_restructuring_not_supported", (
        f"Expected reason 'floor_count_restructuring_not_supported', got {guard.get('reason')}"
    )


# ----------------------------------------------------------
# 2. NEGATIVE CONTROLS (MUST NOT BE BLOCKED)
# ----------------------------------------------------------

NEGATIVE_CONTROLS = [
    # English controls
    "Make this two-storey villa look like night",
    "Keep the existing 2 floors unchanged",
    "Change the facade material, preserve all floors",
    "Do not add or remove floors",
    "Change the windows on the second floor",
    "Add lighting to the third-floor balcony",
    "Change the color of the ground-floor entrance",
    "Make the building brick, keep 3 storeys",
    "Preserve the 2 floors",
    "make it night",
    "use light stone on the facade",
    "On the second floor add a window",
    "Change the doors on the first floor",
    "Do not change the number of floors",

    # Persian controls
    "بدون تغییر تعداد طبقات نما را شب کن",
    "ساختمان سه طبقه را آجری کن",
    "تعداد طبقات را تغییر نده",
    "نما رو سنگ کن",
    "همینو شب کن",
    "پنجره‌های طبقه دوم را عوض کن",
    "به بالکن طبقه سوم نورپردازی اضافه کن",
    "بدون دست زدن به طبقات نما را مدرن کن",
    "نمای ساختمان دو طبقه را سنگ کن",
    "پنجره‌های ساختمان سه طبقه را عوض کن",
    "در طبقه دوم بالکن اضافه کن",
    "بدون تغییر در تعداد طبقات نما را بازطراحی کن",
    "بدون دست زدن به فرم و طبقات پنجره‌ها را عوض کن",
]


@pytest.mark.parametrize("phrase", NEGATIVE_CONTROLS)
def test_negative_controls_not_blocked_by_floor_guard(phrase):
    guard = detect_unsupported_geometry_edit(phrase)
    # The floor guard must not block these; if any are blocked, reason must NOT be floor restructuring
    if guard.get("unsupported"):
        assert guard.get("reason") != "floor_count_restructuring_not_supported", (
            f"Negative control '{phrase}' was wrongly refused as floor restructuring"
        )


# ----------------------------------------------------------
# 3. EXISTING PRECISE GEOMETRY EDITS PRESERVED
# ----------------------------------------------------------

def test_existing_geometry_guard_unaffected():
    # Tier 1: dimensioned opening edit
    g1 = detect_unsupported_geometry_edit("این پنجره رو 80 سانت ببر راست")
    assert g1["unsupported"] is True
    assert g1["reason"] == "dimensioned_geometry_edit_not_supported"

    # Tier 2: localized component operation (e.g. window delete)
    g2 = detect_unsupported_geometry_edit("این پنجره رو حذف کن")
    assert g2["unsupported"] is True
    assert g2["reason"] == "localized_geometry_edit_not_supported"

    # Tier 3: bare geometry verb
    g3 = detect_unsupported_geometry_edit("جابجا کن")
    assert g3["unsupported"] is True
    assert g3["reason"] == "geometry_edit_not_supported"


# ----------------------------------------------------------
# 4. PRE-DISPATCH REFUSAL IN CHAT ARCHITECT
# ----------------------------------------------------------

def _setup_chat_session(session_name="floor_guard_session"):
    chat = ChatArchitect(types.SimpleNamespace())
    image_registry.reset(session_name)
    image_registry.register(
        session_name,
        path=SOURCE_IMAGE,
        source_type="text_to_image",
    )
    return chat, session_name


def test_floor_restructuring_blocks_execution_in_handle():
    chat, session = _setup_chat_session("exec_test_handle")

    calls = {"edit": 0, "render": 0, "comfy": 0}

    def _mock_edit(*args, **kwargs):
        calls["edit"] += 1
        return {"type": "image_render", "status": "FAIL_CALLED_EDIT"}

    def _mock_render(*args, **kwargs):
        calls["render"] += 1
        return {"status": "FAIL_CALLED_RENDER"}

    class _MockComfy:
        def submit(self, workflow):
            calls["comfy"] += 1
            return {"status": "FAIL_SUBMITTED"}
        def wait_for_result(self, prompt_id):
            return {}
        def history(self, prompt_id):
            return {}

    orig_edit = chat.image_handler.handle_image_edit
    orig_render = chat.render_runtime.render
    orig_comfy = chat.render_runtime.executor.comfy

    chat.image_handler.handle_image_edit = _mock_edit
    chat.render_runtime.render = _mock_render
    chat.render_runtime.executor.comfy = _MockComfy()

    session_registry.begin(session)
    try:
        count_before = image_registry.count(session)
        result = chat.handle(
            "این ساختمان را سه طبقه کن",
            context={"session_id": session},
        )
        count_after = image_registry.count(session)
    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = orig_edit
        chat.render_runtime.render = orig_render
        chat.render_runtime.executor.comfy = orig_comfy

    # Execution boundary must NOT be touched
    assert calls == {"edit": 0, "render": 0, "comfy": 0}, f"Execution was called: {calls}"
    assert count_after == count_before, "A derived image was registered for an unsupported edit"

    # Status must be unsupported_edit
    assert result.get("status") == "unsupported_edit"
    assert result.get("engine") == "image_edit_guard"
    guard_res = result.get("unsupported_edit") or {}
    assert guard_res.get("unsupported") is True
    assert guard_res.get("reason") == "floor_count_restructuring_not_supported"


def test_floor_restructuring_blocks_in_route_image_edit():
    chat, session = _setup_chat_session("exec_test_route_i2i")

    session_registry.begin(session)
    try:
        active_record = image_registry.active(session)
        result = chat._route_image_edit(
            text="make it 3 floors",
            image_record=active_record,
            image_reference={},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
            context={"session_id": session},
        )
    finally:
        session_registry.end()

    assert result.get("status") == "unsupported_edit"
    assert result.get("engine") == "image_edit_guard"
    guard_res = result.get("unsupported_edit") or {}
    assert guard_res.get("unsupported") is True
    assert guard_res.get("reason") == "floor_count_restructuring_not_supported"


def test_floor_restructuring_blocks_in_router_edit_route():
    chat, session = _setup_chat_session("exec_test_router_route")

    session_registry.begin(session)
    try:
        active_record = image_registry.active(session)
        result = chat._router_edit_route(
            text="یک طبقه به ساختمان اضافه کن",
            image={"path": SOURCE_IMAGE},
            context={"session_id": session},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
        )
    finally:
        session_registry.end()

    assert result.get("status") == "unsupported_edit"
    assert result.get("engine") == "image_edit_guard"
    guard_res = result.get("unsupported_edit") or {}
    assert guard_res.get("unsupported") is True
    assert guard_res.get("reason") == "floor_count_restructuring_not_supported"


def test_supported_appearance_edit_not_blocked_in_route():
    chat, session = _setup_chat_session("exec_test_appearance_route")

    calls = {"edit": 0}

    def _mock_edit(*args, **kwargs):
        calls["edit"] += 1
        return {"type": "image_render", "status": "SUCCESS"}

    orig_edit = chat.image_handler.handle_image_edit
    chat.image_handler.handle_image_edit = _mock_edit

    session_registry.begin(session)
    try:
        active_record = image_registry.active(session)
        result = chat._route_image_edit(
            text="make it night",
            image_record=active_record,
            image_reference={},
            compiled_render_prompt="STUB",
            terminology={},
            render_seed=42,
            context={"session_id": session},
        )
    finally:
        session_registry.end()
        chat.image_handler.handle_image_edit = orig_edit

    # Must route to edit handler, NOT blocked by guard
    assert result.get("status") != "unsupported_edit"
    assert calls["edit"] == 1


def test_valid_t2i_with_floor_count_not_blocked_by_guard():
    # T2I generation descriptions must not be flagged by the guard
    g1 = detect_unsupported_geometry_edit("طراحی یک ساختمان سه طبقه مدرن")
    assert g1["unsupported"] is False

    g2 = detect_unsupported_geometry_edit("A modern 3-storey villa")
    assert g2["unsupported"] is False

    g3 = detect_unsupported_geometry_edit("Generate a four-storey residential building")
    assert g3["unsupported"] is False
