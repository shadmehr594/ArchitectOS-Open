# ==========================================================
# ArchitectOS — TWO-TURN EDIT CONTINUITY V1
#
# Regression tests for the S2/S3 contract of the conversational
# image-edit path:
#
#   S2 — the previous turn's material / style intent and fixed
#        architectural constraints survive a follow-up revision.
#   S3 — the deterministic edit delta of the CURRENT turn is
#        authoritative over that continuity.
#
# These tests also pin the D1 callable contract of
# ImageHandler.handle_image_generate (T2I must work with no mask,
# and optional precise-edit parameters must be accepted).
#
# NO GPU. NO COMFYUI. Every render result is a mock.
# ==========================================================

import os
import tempfile

import pytest

from core.chat.conversation_state import ConversationState
from core.chat.handlers.image_handler import ImageHandler
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


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
    def __init__(self, extracted=None):
        self.seen = []
        self.extracted = extracted if isinstance(extracted, dict) else {}

    def extract(self, text):
        self.seen.append(text)
        return dict(self.extracted)


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


def build_handler(state, render_runtime, final_render, attachment, extracted=None):
    return ImageHandler(
        render_runtime=render_runtime,
        result_bridge=MockResultBridge(final_render),
        semantic_intent=MockSemanticIntent(extracted),
        image_bridge=MockImageBridge(),
        image_response=MockImageResponse(attachment),
        writeback=MockWriteback(),
        state=state,
        prompt_builder=None,
    )


# A previous turn that produced the source image: light travertine,
# neoclassical, with fixed architectural constraints.
PREVIOUS_INTENT = {
    "building_type": "villa",
    "style": "neoclassical",
    "materials": ["light_travertine_stone"],
    "facade": {"details": ["stone window surrounds"]},
    "preserve_constraints": ["number_of_floors", "opening_positions"],
    "request_type": "facade_material_edit",
}


# ==========================================================
# D1 — CALLABLE CONTRACT
# ==========================================================

def test_d1_generate_is_callable_without_mask(rendered_png):
    """T2I must work with no mask and no precise-edit opt-in."""
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "t2i.png", "path": rendered_png}},
        {"kind": "image", "path": rendered_png},
    )

    handler.handle_image_generate("یک مکعب سفید ساده بساز")

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["kwargs"].get("mask_asset") is None
    assert runtime.calls[0]["kwargs"].get("kontext_edit") is False


def test_d1_generate_forwards_precise_edit_parameters(rendered_png):
    """The optional precise-edit parameters must reach the renderer."""
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "t2i.png", "path": rendered_png}},
        {"kind": "image", "path": rendered_png},
    )

    mask = {"path": "wall_mask.png"}
    handler.handle_image_generate(
        "make the wall lighter",
        mask_asset=mask,
        kontext_edit=True,
    )

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["kwargs"].get("mask_asset") == mask
    assert runtime.calls[0]["kwargs"].get("kontext_edit") is True


# ==========================================================
# S2 / S3 — NORMALISED EDIT INTENT
# ==========================================================

def test_normalize_accepts_previous_intent_and_delta():
    """The S2/S3 call contract must exist (it previously raised TypeError)."""
    handler = ImageHandler.__new__(ImageHandler)

    result = handler.normalize_edit_intent(
        {"prompt": "make the brick a little lighter"},
        previous_intent=PREVIOUS_INTENT,
        edit_delta=compile_edit_delta("make the brick a little lighter"),
    )

    assert isinstance(result, dict)
    assert result["preserve_geometry"] is True


def test_normalize_is_backwards_compatible():
    """A pre-existing single-argument caller keeps its exact behaviour."""
    handler = ImageHandler.__new__(ImageHandler)

    raw = {"style": "modern", "materials": ["brick"], "prompt": "modern brick"}
    legacy = handler.normalize_edit_intent(raw)

    assert legacy["style"] == "modern"
    assert legacy["materials"] == ["brick"]
    assert legacy["request_type"] == "facade_material_edit"
    assert legacy["normalized_prompt"] == "modern brick"


def test_s2_previous_style_and_constraints_survive():
    """A follow-up that states no style keeps the previous architectural one."""
    handler = ImageHandler.__new__(ImageHandler)

    result = handler.normalize_edit_intent(
        {"prompt": "make it a little lighter"},
        previous_intent=PREVIOUS_INTENT,
        edit_delta=compile_edit_delta("make it a little lighter"),
    )

    assert result["style"] == "neoclassical"
    assert result["building_type"] == "villa"
    assert result["preserve_constraints"] == [
        "number_of_floors",
        "opening_positions",
    ]
    assert result["facade_details"] == ["stone window surrounds"]


def test_s3_delta_material_supersedes_previous_material():
    """The new finish must not be masked by the previous one."""
    handler = ImageHandler.__new__(ImageHandler)

    delta = compile_edit_delta("حالا رنگ آجرهای همان نما را کمی روشن‌تر کن.")

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "brick"

    result = handler.normalize_edit_intent(
        {"prompt": "حالا رنگ آجرهای همان نما را کمی روشن‌تر کن."},
        previous_intent=PREVIOUS_INTENT,
        edit_delta=delta,
    )

    assert result["materials"] == ["brick"]
    assert "light_travertine_stone" not in result["materials"]


def test_s3_explicit_current_material_wins_over_previous():
    handler = ImageHandler.__new__(ImageHandler)

    result = handler.normalize_edit_intent(
        {"materials": ["natural stone"], "prompt": "natural stone"},
        previous_intent=PREVIOUS_INTENT,
        edit_delta={},
    )

    assert result["materials"] == ["natural stone"]


def test_s3_colour_change_is_not_a_material_change():
    """A COLOUR delta must not be written into the MATERIAL-TYPE slot.

    `materials` is consumed verbatim by PromptBuilder as a facade feature
    and the material ontology identifies substances (travertine,
    red_brick), never hues. The former contract put the colour there, so
    "make the facade red" became a material replacement called "red" and
    the previous finish was discarded. A recolour must preserve the
    material type and carry the colour through the delta prompt only.
    """
    handler = ImageHandler.__new__(ImageHandler)

    delta = compile_edit_delta("make the facade red")

    assert delta["edit_class"] == "color_change"
    assert delta["color"] == "red"

    result = handler.normalize_edit_intent(
        {"prompt": "make the facade red"},
        previous_intent=PREVIOUS_INTENT,
        edit_delta=delta,
    )

    assert result["materials"] == ["light_travertine_stone"]
    assert "red" not in result["materials"]
    # the colour itself stays authoritative in the compiled delta
    assert "red" in delta["delta_prompt"]


def test_s3_colour_change_without_previous_material_stays_unspecified():
    """With no known finish, a recolour must not invent one from the hue."""
    handler = ImageHandler.__new__(ImageHandler)

    delta = compile_edit_delta("make the facade blue")

    result = handler.normalize_edit_intent(
        {"prompt": "make the facade blue"},
        previous_intent=None,
        edit_delta=delta,
    )

    assert result["materials"] == ["preserve existing facade materials"]
    assert "blue" not in result["materials"]


def test_s3_tone_change_preserves_the_named_material():
    """A tone modifier on an existing material keeps that material."""
    handler = ImageHandler.__new__(ImageHandler)

    delta = compile_edit_delta("make the travertine a little lighter")

    assert delta["material"] == "travertine"
    assert delta["material_tone"] == "light"

    result = handler.normalize_edit_intent(
        {"prompt": "make the travertine a little lighter"},
        previous_intent=PREVIOUS_INTENT,
        edit_delta=delta,
    )

    assert result["materials"] == ["travertine"]


# ==========================================================
# END-TO-END — THE SECOND TURN REACHES THE RENDERER
# ==========================================================

def test_second_turn_edit_reaches_renderer_with_the_new_material(rendered_png):
    """The measured D1 -> D2 flow, with mocks only.

    Turn 1 was light travertine; turn 2 asks for lighter brick. The render
    call must carry the delta prompt and the NEW material, while the
    previous fixed constraints survive.
    """
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "turn2.png", "path": rendered_png}},
        {"kind": "image", "path": rendered_png},
    )

    text = "حالا رنگ آجرهای همان نما را کمی روشن‌تر کن."
    delta = compile_edit_delta(text)

    response = handler.handle_image_edit(
        text,
        {"path": rendered_png, "filename": "source.png"},
        compiled_render_prompt=delta["delta_prompt"],
        previous_architectural_intent=PREVIOUS_INTENT,
        edit_delta=delta,
    )

    assert response.get("status") != "error", response
    assert len(runtime.calls) == 1

    call = runtime.calls[0]
    intent = call["payload"]["architectural_intent"]

    assert intent["materials"] == ["brick"]
    assert intent["style"] == "neoclassical"
    assert intent["preserve_constraints"] == [
        "number_of_floors",
        "opening_positions",
    ]
    # The delta is the authoritative render instruction; `prompt` keeps the
    # user's own words.
    assert "light fired clay brick" in call["payload"]["compiled_render_prompt"].lower()
    assert call["payload"]["prompt"] == text


def test_second_turn_precise_edit_parameters_reach_renderer(rendered_png):
    """Mask + Kontext opt-in must survive into the render call (S1 carrier)."""
    state = ConversationState()
    runtime = RecordingRenderRuntime()
    handler = build_handler(
        state,
        runtime,
        {"status": "success", "image": {"filename": "turn2.png", "path": rendered_png}},
        {"kind": "image", "path": rendered_png},
    )

    mask = {"path": "wall_mask.png"}

    handler.handle_image_edit(
        "make the brick a little lighter",
        {"path": rendered_png, "filename": "source.png"},
        mask_asset=mask,
        kontext_edit=True,
    )

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["kwargs"].get("mask_asset") == mask
    assert runtime.calls[0]["kwargs"].get("kontext_edit") is True
