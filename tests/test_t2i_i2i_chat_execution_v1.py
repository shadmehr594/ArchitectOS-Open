# ==========================================================
# ArchitectOS — T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
#
# End-to-end acceptance tests for the chat -> image execution paths.
#
# NO GPU. NO COMFYUI SUBMISSION. NO MODEL INSTALLATION.
# Every render result below is a MOCK. The real bounded smoke test is
# run separately (see runs/t2i_i2i_chat_execution_v1/).
#
# What is proven here:
#   A. single-turn T2I intent recognition (Persian)
#   B. multi-turn T2I: the specification answer completes the request
#   C. English T2I intent recognition
#   D. I2I: the uploaded source image really reaches the render call
#   E. non-rendering control: a question is not a render
#   F. failure handling: no false success is reported
# ==========================================================

import os
import tempfile

import pytest

from core.intent_router import (
    IntentRouter,
    is_pending_image_answer,
    merge_pending_image_prompt,
)
from core.chat.conversation_state import ConversationState
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry


@pytest.fixture(autouse=True)
def _isolate_session_registry_binding():
    """Standalone handler tests must never inherit another module's binding."""
    session_registry.end()
    yield
    session_registry.end()


# ==========================================================
# MOCK COLLABORATORS
# ==========================================================

class RecordingRenderRuntime:
    """Records every render call. Never talks to ComfyUI."""

    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else {
            "status": "success",
            "execution": {
                "status": "success",
                "prompt_id": "mock-prompt-1",
                "images": [
                    {"filename": "mock_out.png", "subfolder": "", "type": "output"}
                ],
            },
        }

    def render(self, project_id, payload, engine, image_asset=None, **kwargs):
        self.calls.append(
            {
                "project_id": project_id,
                "payload": payload,
                "engine": engine,
                "image_asset": image_asset,
                "kwargs": kwargs,
            }
        )
        return self.result


class MockResultBridge:
    def __init__(self, final):
        self.final = final

    def resolve(self, render_result):
        return self.final


class MockSemanticIntent:
    def __init__(self):
        self.seen = []

    def extract(self, text):
        self.seen.append(text)
        return {}


class MockImageResponse:
    def __init__(self, attachment):
        self.attachment = attachment

    def adapt(self, render_result):
        if not isinstance(render_result, dict):
            return {"status": "error", "attachments": []}
        if render_result.get("status") != "success":
            return render_result
        return {
            "type": "image",
            "status": "success",
            "attachments": [self.attachment],
        }


class MockWriteback:
    def __init__(self):
        self.stored = []

    def store(self, text, value):
        self.stored.append((text, value))


class MockImageBridge:
    """Minimal stand-in for the upload -> asset bridge."""

    def __init__(self):
        self.uploads = []

    def process_upload(self, project_id, image_path, preview=None):
        self.uploads.append((project_id, image_path, preview))
        return {
            "type": "image_asset",
            "asset": {
                "path": image_path,
                "filename": os.path.basename(str(image_path)),
                "status": "ready",
            },
        }


def _real_png(path):
    """A tiny real PNG so any isfile() check is honest."""
    with open(path, "wb") as handle:
        handle.write(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                "1f15c4890000000d4944415478da63f8ffff3f0005fe02fea735c40f"
                "0000000049454e44ae426082"
            )
        )
    return path


@pytest.fixture()
def rendered_png():
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    _real_png(handle.name)
    yield handle.name
    try:
        os.unlink(handle.name)
    except OSError:
        pass


def build_handler(
    state,
    render_runtime,
    final_render,
    attachment,
):
    return ImageHandler(
        render_runtime=render_runtime,
        result_bridge=MockResultBridge(final_render),
        semantic_intent=MockSemanticIntent(),
        image_bridge=MockImageBridge(),
        image_response=MockImageResponse(attachment),
        writeback=MockWriteback(),
        state=state,
        prompt_builder=None,
    )


# ==========================================================
# A / C / E — INTENT RECOGNITION
# ==========================================================

def test_a_single_turn_persian_t2i_is_recognised():
    router = IntentRouter()
    result = router.route("یک مکعب سفید ساده بساز", None, {"conversation_state": {}})
    assert result["intent"] == "image"
    assert result["mode"] == "generate"


def test_c_english_t2i_is_recognised():
    router = IntentRouter()
    result = router.route("Generate a simple white cube.", None, {"conversation_state": {}})
    assert result["intent"] == "image"
    assert result["mode"] == "generate"


def test_e_question_is_not_a_render():
    router = IntentRouter()
    for text in ("مکعب چیست؟", "What is a cube?", "چرا آسمان آبی است؟"):
        result = router.route(text, None, {"conversation_state": {}})
        assert result["intent"] == "chat", text
        assert result["mode"] == "conversation", text


def test_architectural_design_intent_is_not_hijacked():
    """The generic creation fallback must never capture a design request."""
    router = IntentRouter()
    for text, expected in (
        ("یک ساختمان بساز", "design"),
        ("یک ویلای ۲۰۰ متری بساز", "design"),
        ("یک برج بساز", "design"),
    ):
        result = router.route(text, None, {"conversation_state": {}})
        assert result["intent"] == expected, (text, result)


def test_non_visual_artifact_request_is_not_a_render():
    router = IntentRouter()
    for text in ("یک متن بساز", "یک جدول بساز", "Create a report", "یک فایل بساز"):
        result = router.route(text, None, {"conversation_state": {}})
        assert result["intent"] == "chat", (text, result)


# ==========================================================
# B — MULTI-TURN
# ==========================================================

def test_b_multi_turn_specification_answer_continues_the_request():
    router = IntentRouter()
    state = {
        "pending_image_generate": {
            "prompt": "یک مکعب سفید ساده بساز",
            "created_turn": 1,
        },
        "turn_index": 2,
    }
    result = router.route("5*5*5 سانتیمتر", None, {"conversation_state": state})
    assert result["intent"] == "image"
    assert result["mode"] == "generate"
    assert result.get("continuation") is True


def test_b_multi_turn_does_not_capture_architectural_or_unrelated_turns():
    router = IntentRouter()
    state = {
        "pending_image_generate": {
            "prompt": "یک مکعب سفید ساده بساز",
            "created_turn": 1,
        },
        "turn_index": 2,
    }
    for text in ("۳ طبقه", "مکعب چیست؟", "سلام خوبی؟", "یک متن بساز"):
        result = router.route(text, None, {"conversation_state": state})
        assert result["intent"] == "chat", (text, result)


def test_b_pending_request_expires():
    router = IntentRouter()
    state = {
        "pending_image_generate": {
            "prompt": "یک مکعب سفید ساده بساز",
            "created_turn": 0,
        },
        "turn_index": 99,
    }
    result = router.route("5*5*5 سانتیمتر", None, {"conversation_state": state})
    assert result["intent"] == "chat"


def test_b_merge_accumulates_object_appearance_and_dimensions():
    pending = {"prompt": "یک مکعب سفید ساده بساز"}
    merged = merge_pending_image_prompt(pending, "5*5*5 سانتیمتر")
    assert "مکعب" in merged
    assert "سفید" in merged
    assert "5*5*5" in merged


def test_b_handler_renders_the_merged_prompt(rendered_png):
    state = ConversationState()
    state.update(
        {
            "pending_image_generate": {
                "prompt": "یک مکعب سفید ساده بساز",
                "created_turn": 1,
            },
            "turn_index": 2,
        }
    )

    runtime = RecordingRenderRuntime()
    attachment = {"kind": "image", "path": rendered_png, "display_name": "mock_out.png"}
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "mock_out.png", "path": rendered_png}},
        attachment,
    )

    response = handler.handle_image_generate("5*5*5 سانتیمتر")

    assert len(runtime.calls) == 1
    sent_prompt = runtime.calls[0]["payload"]["original_prompt"]
    assert "مکعب" in sent_prompt
    assert "سفید" in sent_prompt
    assert "5*5*5" in sent_prompt
    assert response["type"] == "image_render"
    assert response["status"] == "success"
    assert response["result"]["attachments"]


def test_b_handler_remembers_the_request_for_the_next_turn(rendered_png):
    state = ConversationState()
    state.next_turn()

    runtime = RecordingRenderRuntime()
    attachment = {"kind": "image", "path": rendered_png, "display_name": "mock_out.png"}
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "mock_out.png", "path": rendered_png}},
        attachment,
    )

    handler.handle_image_generate("یک مکعب سفید ساده بساز")

    pending = state.get().get("pending_image_generate")
    assert isinstance(pending, dict)
    assert "مکعب" in pending["prompt"]


# ==========================================================
# D — IMAGE EDIT / I2I
# ==========================================================

def test_d_edit_request_with_image_routes_to_edit_and_uses_the_source(rendered_png):
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    attachment = {"kind": "image", "path": rendered_png, "display_name": "edited.png"}
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "edited.png", "path": rendered_png}},
        attachment,
    )

    source = {"path": rendered_png, "filename": "source.png"}

    response = handler.handle_image_edit("این تصویر را مدرن کن", source)

    assert len(runtime.calls) == 1
    call = runtime.calls[0]
    # the SOURCE image is what reaches the renderer, in img2img mode
    assert call["image_asset"] is not None
    assert call["image_asset"].get("path") == rendered_png
    assert call["payload"]["mode"] == "img2img"
    assert response.get("type") in ("image_render", "image_edit")


def test_d_ordinary_analysis_is_not_routed_to_edit():
    """A visual question must not be treated as an edit."""
    state = ConversationState()
    handler = build_handler(
        state,
        RecordingRenderRuntime(),
        {"status": "success"},
        {"kind": "image", "path": "x.png"},
    )
    assert handler.is_image_edit_request("این ساختمان چند طبقه دارد؟") is False


# ==========================================================
# F — FAILURE HANDLING
# ==========================================================

def test_f_no_image_result_is_not_reported_as_success():
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    handler = build_handler(
        state,
        runtime,
        {"status": "completed_no_image", "prompt_id": "mock-prompt-1"},
        {"kind": "image", "path": "never_used.png"},
    )

    response = handler.handle_image_generate("یک مکعب سفید ساده بساز")

    assert response["type"] == "image_render"
    assert response["status"] != "success"
    assert response["status"] == "completed_no_image"
    assert response["error"]
    assert not response["result"].get("attachments")


def test_f_error_result_is_surfaced():
    state = ConversationState()
    handler = build_handler(
        state,
        RecordingRenderRuntime(),
        {"status": "error", "error": "comfy_unreachable"},
        {"kind": "image", "path": "never_used.png"},
    )

    response = handler.handle_image_generate("یک مکعب سفید ساده بساز")

    assert response["status"] == "error"
    assert "comfy_unreachable" in str(response["error"])


def test_f_response_adapter_reports_failure_honestly():
    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()
    failed = adapter.build_message(
        {
            "type": "image_render",
            "status": "completed_no_image",
            "error": "render_output_missing",
        }
    )
    assert "رندر آماده شد" not in failed
    assert "render_output_missing" in failed

    ok = adapter.build_message({"type": "image_render", "status": "success"})
    assert "رندر آماده شد" in ok


# ==========================================================
# GUARD — the shared predicate used by BOTH router and handler
# ==========================================================

def test_shared_predicate_is_consistent():
    assert is_pending_image_answer("5*5*5 سانتیمتر") is True
    assert is_pending_image_answer("سفید باشد") is True
    assert is_pending_image_answer("چوبی باشه") is True
    assert is_pending_image_answer("۳ طبقه") is False
    assert is_pending_image_answer("مکعب چیست؟") is False
    assert is_pending_image_answer("یک متن بساز") is False
    assert is_pending_image_answer("") is False
