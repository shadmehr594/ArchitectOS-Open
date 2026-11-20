from core.chat.chat_architect import ChatArchitect
from core.render.prompt_builder import PromptBuilder


class FakeState:
    def __init__(self, data):
        self.data = data

    def get(self):
        return self.data

    def update(self, values):
        self.data.update(values)


class FakeInputAdapter:
    def normalize(self, text, _context):
        return {"text": text, "image": None}


class FakeRouter:
    def route(self, _text, _image, _context):
        return {"intent": "image", "mode": "generate"}

    def is_image_edit_request(self, _text):
        return False


class FakeImageHandler:
    def __init__(self):
        self.calls = []

    def handle_image_generate(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return {"type": "image", "status": "queued"}


class FakeRenderRuntime:
    def __init__(self):
        self.calls = []

    def render(self, *args):
        self.calls.append(args)
        return {"status": "queued"}


def chat_for_route(state):
    chat = ChatArchitect.__new__(ChatArchitect)
    chat.state = FakeState(state)
    chat.input_adapter = FakeInputAdapter()
    chat.intent_router = FakeRouter()
    chat.image_handler = FakeImageHandler()
    return chat


def approved_state():
    return {
        "design_status": "approved",
        "last_architectural_intent": {"style": "modern"},
        "last_design": {
            "facade_language": {"primary": "deep_frames"},
            "facade_assembly": {"materials": ["brick", "wood"]},
            "climate_facade_strategy": {"shading": "horizontal_louvers"},
        },
        "bim_result": {"exports": {"ifc": "exports/project.ifc"}},
        "cad_asset": "exports/project.dxf",
        "ifc_asset": "exports/project.ifc",
    }


def test_approved_render_intent_carries_design_and_bim_evidence():
    chat = ChatArchitect.__new__(ChatArchitect)

    intent = chat.build_approved_render_intent(approved_state())

    assert intent["style"] == "modern"
    assert intent["facade_language"]["primary"] == "deep_frames"
    assert intent["facade_assembly"]["materials"] == ["brick", "wood"]
    assert intent["climate_facade_strategy"]["shading"] == "horizontal_louvers"
    assert intent["render_source"]["type"] == "approved_bim_design"
    assert intent["render_source"]["approval_status"] is True
    assert intent["render_source"]["ifc_asset"] == "exports/project.ifc"


def test_prompt_contains_approved_facade_language_and_materials():
    chat = ChatArchitect.__new__(ChatArchitect)
    intent = chat.build_approved_render_intent(approved_state())

    prompt = PromptBuilder().build({"architectural_intent": intent})["description"]

    assert "approved facade design" in prompt
    assert "deep frames" in prompt
    assert "horizontal louvers" in prompt
    assert "brick" in prompt
    assert "wood" in prompt


def test_render_is_blocked_until_design_is_approved():
    state = approved_state()
    state["design_status"] = "WAITING_APPROVAL"
    chat = chat_for_route(state)

    result = chat.handle("رندر بگیر")

    assert result["status"] == "waiting_approval"
    assert chat.image_handler.calls == []


def test_approved_render_routes_facade_intent_to_image_handler():
    chat = chat_for_route(approved_state())

    result = chat.handle("رندر بگیر")

    assert result["status"] == "queued"
    assert len(chat.image_handler.calls) == 1
    kwargs = chat.image_handler.calls[0][1]
    assert kwargs["architectural_intent"]["facade_language"]["primary"] == "deep_frames"
    assert kwargs["design_state"]["previous_design"]


def test_animation_uses_last_approved_render_and_wan():
    state = approved_state()
    state["last_render_asset"] = {"filename": "approved_facade.png"}
    chat = chat_for_route(state)
    chat.render_runtime = FakeRenderRuntime()

    result = chat.handle("از نمای تاییدشده انیمیشن بساز")

    assert result["type"] == "video"
    project_id, payload, engine, asset = chat.render_runtime.calls[0]
    assert project_id == "chat_project"
    assert engine == "wan"
    assert payload["mode"] == "i2v"
    assert asset["filename"] == "approved_facade.png"
