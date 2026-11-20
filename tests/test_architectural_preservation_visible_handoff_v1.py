"""CPU-only response handoff for ArchitecturalPreservationIntentV1.

All model and rendering seams are test doubles. No provider, ComfyUI, GPU,
network, production HTTP route or asset registration is invoked.
"""

from copy import deepcopy
from types import SimpleNamespace

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.chat.handlers.image_handler import ImageHandler
from core.chat.response_adapter import ResponseAdapter
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


REQUEST = (
    "Reject rustic block stone. Design a restrained neoclassical facade for "
    "this unfinished building with subtle texture in cream travertine. "
    "Preserve the existing structural frame, original floor count, opening "
    "positions, ground-floor openness, balcony and terrace boundaries, roof "
    "geometry, massing and camera perspective. Do not change the courtyard, "
    "foreground ground surfaces, retaining walls, neighbouring buildings or "
    "surrounding site layout."
)

UNDERSTANDING = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "source-image", "sha256": "8" * 64},
        "elements": [
            {
                "element": "facade wall",
                "kind": ["wall"],
                "context_kinds": [],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "An unfinished facade wall is reported.",
            },
            {
                "element": "windows",
                "kind": ["window", "opening"],
                "context_kinds": [],
                "evidence_class": "MODEL_REPORTED",
                "verification_status": "UNVERIFIED",
                "source_quote": "Window openings are reported.",
            },
        ],
    },
}


class _State:
    def __init__(self):
        self.value = {}

    def get(self):
        return deepcopy(self.value)

    def update(self, values):
        self.value.update(deepcopy(values))


class _NonExecutingRuntime:
    def __init__(self):
        self.calls = []
        self.resolver = SharedFacadeKnowledgeResolverV1()

    def resolve_shared_facade_knowledge(self, intent):
        resolved = self.resolver.resolve(intent)
        intent["resolved_facade_knowledge"] = resolved
        return resolved

    def render(self, project, payload, engine, asset, **kwargs):
        self.calls.append({
            "project": project,
            "payload": deepcopy(payload),
            "engine": engine,
            "asset": deepcopy(asset),
            "kwargs": deepcopy(kwargs),
        })
        return {
            "type": "image_render",
            "status": "recorded_no_execution",
            "engine": "nonexecuting_test_double",
        }


def _real_response_path():
    runtime = _NonExecutingRuntime()
    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": "recorded-source.png"}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {
        "preserve_geometry": True,
        "preserve_constraints": [
            "number_of_floors", "overall_massing", "building_silhouette",
            "main_window_positions", "main_door_positions", "roofline",
        ],
    })
    handler.render_runtime = runtime
    handler.result_bridge = SimpleNamespace(resolve=lambda result: deepcopy(result))
    handler.image_response = SimpleNamespace(adapt=lambda result: deepcopy(result))

    native = handler.handle_image_edit(
        text=REQUEST,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(REQUEST, image_edit=True),
        image_understanding=deepcopy(UNDERSTANDING),
    )
    public = ResponseAdapter().adapt(native)
    return native, public, runtime


def _ids(contract, scope):
    return {
        item["id"] for item in contract["scopes"][scope]
        if isinstance(item, dict) and item.get("id")
    }


def test_real_image_handler_to_response_adapter_exposes_complete_contract():
    native, public, runtime = _real_response_path()
    nested = native["architectural_intent"]["architectural_design_decision"][
        "architectural_preservation_intent"
    ]

    assert public["architectural_preservation_intent"] == nested
    assert public["architectural_preservation_intent"]["contract"] == (
        "ArchitecturalPreservationIntentV1"
    )
    assert public["architectural_preservation_intent"]["spatial_authority"] == {
        "status": "UNKNOWN", "mask": None,
        "pixel_coordinates": None, "segmentation": None,
    }
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["payload"]["architectural_intent"][
        "architectural_design_decision"
    ]["render_executed"] is False


def test_visible_summary_covers_target_architecture_context_and_material():
    _, public, _ = _real_response_path()
    contract = public["architectural_preservation_intent"]
    summary = public["architectural_preservation_summary"]

    assert _ids(contract, "design_target") == {"main_facade_surface_expression"}
    assert {
        "floor_count", "structural_grid", "windows_and_openings",
        "balcony_and_terrace_boundaries", "roof_geometry",
    } <= _ids(contract, "protected_architecture")
    assert {
        "courtyard", "retaining_walls", "adjacent_buildings",
        "foreground_ground_surfaces", "surrounding_site_layout",
    } <= _ids(contract, "protected_context")

    assert "هدف طراحی: مصالح و بیان معماری نمای اصلی" in summary
    assert "تعداد طبقات" in summary
    assert "شبکه و قاب سازه‌ای" in summary
    assert "حیاط" in summary
    assert "دیوارهای حائل" in summary
    assert "neoclassical" in summary
    assert "travertine" in summary
    assert "cream" in summary
    assert "rustic_block_stone" in summary


def test_unverified_evidence_and_capability_limitation_are_visible_and_truthful():
    _, public, _ = _real_response_path()
    contract = public["architectural_preservation_intent"]
    summary = public["architectural_preservation_summary"]

    assert all(
        item["grounding_category"] == "model_reported_but_unverified"
        and item["verification_status"] == "UNVERIFIED"
        for item in contract["evidence_register"]
    )
    assert "UNVERIFIED" in summary
    assert "PRESERVATION_CAPABILITY_INSUFFICIENT" in summary
    assert "dual-conditioned" in summary
    assert "هدایت نرم هندسی" in summary
    assert "تضمین نشده" in summary
    assert "پذیرش R4 را فعال نمی‌کند" in summary
    assert contract["automatic_r4_approval"] is False
    assert contract["render_executed"] is False
    assert contract["comfy_invoked"] is False


def test_ui_text_surface_contains_summary_not_a_python_object():
    _, public, _ = _real_response_path()

    assert isinstance(public["result"], str)
    assert public["result"] == public["message"]
    assert "تصمیم حفاظت معماری:" in public["result"]
    assert "[object Object]" not in public["result"]
    assert isinstance(public["result_structured"], dict)


def test_ordinary_chat_and_image_responses_remain_compatible():
    adapter = ResponseAdapter()
    chat = {"type": "chat", "status": "success", "result": "سلام"}
    image = {
        "type": "image_render",
        "status": "recorded_no_execution",
        "result": "no external execution",
    }

    chat_response = adapter.adapt(deepcopy(chat))
    image_response = adapter.adapt(deepcopy(image))

    assert chat_response["result"] == "سلام"
    assert "architectural_preservation_intent" not in chat_response
    assert image_response["result"] == "no external execution"
    assert "architectural_preservation_intent" not in image_response
    assert "architectural_preservation_summary" not in image_response
