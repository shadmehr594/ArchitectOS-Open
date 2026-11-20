"""V8 evidence-dependent architectural design decisions (CPU only)."""

from copy import deepcopy
from types import SimpleNamespace

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.chat.handlers.image_handler import ImageHandler


def _element(name, kinds, quote, *, context=(), basis="subject_explicit"):
    return {
        "element": name,
        "kind": list(kinds),
        "context_kinds": list(context),
        "kind_basis": basis,
        "source_quote": quote,
        "evidence_class": "MODEL_REPORTED",
        "verification_status": "UNVERIFIED",
        "confidence": None,
        "position": None,
        "relations": [],
    }


def _facade_understanding(*elements, image_id="facade-1"):
    return {
        "contract": "ImageUnderstandingV1",
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "image_type": "facade_or_elevation",
        "element_evidence": {
            "contract": "ArchitecturalElementEvidenceV1",
            "source_image": {"image_id": image_id, "sha256": "a" * 64},
            "elements": list(elements),
        },
    }


CLASSICAL = _facade_understanding(
    _element("facade wall", ("wall",), "A pale facade wall plane."),
    _element("windows", ("window", "opening"), "Regular window openings."),
    _element("columns", ("column",), "Columns frame the entrance."),
    _element("entrance", ("entrance", "door"), "A central entrance door."),
    _element(
        "lanterns",
        ("light_fixture",),
        "Lantern fixtures mounted on the wall.",
        context=("wall",),
    ),
)

MODERN = _facade_understanding(
    _element("rendered wall", ("wall",), "A plain rendered wall plane."),
    _element("strip windows", ("window", "opening"), "Horizontal strip windows."),
    image_id="modern-1",
)

PLAN = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "floor_plan_or_sketch",
    "local_plan_reading": {
        "status": "grounded",
        "provider_independent": True,
        "wall_reading": {"partition": {"room_count": None}},
        "furniture_evidence": [
            {
                "class": "bed",
                "bbox_pixels": [20, 30, 80, 120],
                "confidence": "MEDIUM",
                "source": "local_raster_symbol_topology",
                "provider_independent": True,
                "corroboration": ["outline", "internal lines", "enclosure"],
                "raster_patch_sha256": "b" * 64,
            }
        ],
    },
}


def _decision(text, understanding, *, knowledge=True):
    delta = compile_edit_delta(text, image_edit=True)
    resolved = None
    if knowledge:
        resolved = SharedFacadeKnowledgeResolverV1().resolve({
            "style": delta.get("style"),
            "materials": [delta["material"]] if delta.get("material") else [],
            "normalized_prompt": text,
        })
    return resolve_design_decision(
        user_text=text,
        edit_delta=delta,
        image_understanding=understanding,
        resolved_facade_knowledge=resolved,
        preserve_geometry=True,
        preserve_constraints=(
            "number_of_floors", "overall_massing", "building_silhouette",
            "main_window_positions", "main_door_positions", "roofline",
        ),
    )


def test_classical_style_request_uses_evidence_knowledge_and_fixed_domains():
    decision = _decision(
        "Change the facade to neoclassical while keeping the building mass, "
        "openings and number of floors unchanged.",
        CLASSICAL,
    )

    assert decision["requested_operation"]["edit_class"] == "style_change"
    assert decision["applicable_knowledge"]["canonical_style"] == "neoclassical"
    assert {"massing", "opening", "roof"} <= set(decision["fixed_constraints"]["domains"])
    assert decision["editable_elements"] == ["facade_surface_expression"]
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert all(item["verification_status"] == "UNVERIFIED"
               for item in decision["image_supported_context"])


def test_material_request_edits_supported_wall_surface_and_preserves_named_elements():
    decision = _decision(
        "Replace the facade finish with light travertine, but preserve the "
        "columns, windows and entrance.",
        CLASSICAL,
    )

    assert decision["requested_operation"]["material"] == "travertine"
    assert decision["editable_elements"] == ["facade_wall_surface"]
    assert {"columns", "windows", "entrance"} <= set(
        decision["fixed_constraints"]["elements"]
    )
    assert "material appearance in the source image" in decision["remaining_uncertainty"]


def test_lantern_removal_is_evidence_grounded_but_requires_spatial_targeting():
    decision = _decision(
        "Remove the wall-mounted lanterns and keep everything else unchanged.",
        CLASSICAL,
    )

    assert decision["requested_operation"]["operation"] == "remove"
    assert decision["editable_elements"] == ["lanterns"]
    lantern = next(item for item in decision["image_supported_context"]
                   if item["element"] == "lanterns")
    assert lantern["kinds"] == ["light_fixture"]
    assert lantern["context_kinds"] == ["wall"]
    assert decision["execution_status"] == "NEEDS_SPATIAL_TARGETING"
    assert decision["workflow_recommendation"]["capability"] == "Kontext masked edit"
    assert "verified caller-supplied mask" in decision["workflow_recommendation"]["conditions"]


def test_persian_night_request_changes_lighting_not_architecture():
    decision = _decision(
        "این ساختمان را به یک رندر شب واقعی تبدیل کن و معماری، بازشوها و "
        "تعداد طبقات را بدون تغییر حفظ کن.",
        MODERN,
    )

    assert decision["requested_operation"]["edit_class"] == "time_of_day_change"
    assert decision["editable_elements"] == ["lighting", "atmosphere"]
    assert {"massing", "opening", "roof"} <= set(decision["fixed_constraints"]["domains"])
    assert decision["workflow_recommendation"]["capability"] == "Kontext global appearance edit"


def test_floor_plan_evidence_does_not_turn_into_a_facade_decision():
    decision = _decision(
        "Change the furniture layout but preserve all walls and openings.",
        PLAN,
        knowledge=False,
    )

    assert decision["image_type"] == "floor_plan_or_sketch"
    assert decision["editable_elements"] == ["furniture"]
    assert decision["execution_status"] == "INSUFFICIENT_SPATIAL_EVIDENCE"
    assert decision["workflow_recommendation"]["capability"] == "none"
    assert not decision["applicable_knowledge"]


def test_counterfactual_same_request_changes_with_image_evidence():
    text = "Replace the facade finish with light travertine."
    facade = _decision(text, MODERN)
    plan = _decision(text, PLAN)

    assert facade["editable_elements"] == ["facade_wall_surface"]
    assert plan["editable_elements"] == []
    assert plan["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"


def test_counterfactual_new_fixed_constraint_changes_preservation_decision():
    base = _decision("Change this facade to neoclassical.", CLASSICAL)
    fixed = _decision(
        "Change this facade to neoclassical but preserve the columns exactly.",
        CLASSICAL,
    )

    assert "columns" not in base["fixed_constraints"]["elements"]
    assert "columns" in fixed["fixed_constraints"]["elements"]


def test_unsupported_visual_target_is_not_invented():
    decision = _decision(
        "Remove the gargoyles and keep everything else unchanged.",
        CLASSICAL,
    )

    assert decision["editable_elements"] == []
    assert decision["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"
    assert "requested element is not supported by image evidence" in decision["conflicts"]


def test_contradictory_constraints_block_instead_of_choosing_arbitrarily():
    decision = _decision(
        "Redesign the roof but preserve its original shape.",
        CLASSICAL,
    )

    assert decision["execution_status"] == "BLOCKED_CONFLICT"
    assert decision["geometry_authority"]["conflicts"]


def test_removing_knowledge_context_removes_knowledge_claims():
    with_knowledge = _decision("Change this facade to neoclassical.", CLASSICAL)
    without_knowledge = _decision(
        "Change this facade to neoclassical.", CLASSICAL, knowledge=False
    )

    assert with_knowledge["applicable_knowledge"]["canonical_style"] == "neoclassical"
    assert without_knowledge["applicable_knowledge"] is None
    assert without_knowledge["knowledge_derived_decisions"] == []


def test_decision_is_pure_and_keeps_source_evidence_unchanged():
    before = deepcopy(CLASSICAL)
    decision = _decision("Make this a convincing night render.", CLASSICAL)

    assert CLASSICAL == before
    assert decision["render_executed"] is False
    assert decision["comfy_invoked"] is False
    assert decision["post_execution_verification"]


def test_real_image_handler_blocks_unlocalized_element_removal_before_render():
    class _State:
        def __init__(self):
            self.value = {}

        def get(self):
            return deepcopy(self.value)

        def update(self, values):
            self.value.update(values)

    class _Runtime:
        def __init__(self):
            self.render_called = False
            self.resolver = SharedFacadeKnowledgeResolverV1()

        def resolve_shared_facade_knowledge(self, intent):
            resolved = self.resolver.resolve(intent)
            intent["resolved_facade_knowledge"] = resolved
            return resolved

        def render(self, *args, **kwargs):
            self.render_called = True
            raise AssertionError("render must not run for an unlocalized removal")

    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": "recorded-source.png"}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _Runtime()

    text = "Remove the wall-mounted lanterns and keep everything else unchanged."
    result = handler.handle_image_edit(
        text=text,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=CLASSICAL,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "needs_spatial_targeting"
    assert result["architectural_design_decision"]["editable_elements"] == ["lanterns"]
    assert handler.render_runtime.render_called is False


def test_ready_decision_reaches_the_existing_render_handoff_without_execution():
    class _State:
        def __init__(self):
            self.value = {}

        def get(self):
            return deepcopy(self.value)

        def update(self, values):
            self.value.update(values)

    class _Runtime:
        def __init__(self):
            self.payloads = []
            self.resolver = SharedFacadeKnowledgeResolverV1()

        def resolve_shared_facade_knowledge(self, intent):
            resolved = self.resolver.resolve(intent)
            intent["resolved_facade_knowledge"] = resolved
            return resolved

        def render(self, project, payload, engine, asset, **kwargs):
            self.payloads.append(deepcopy(payload))
            return {"status": "recorded_no_execution"}

    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": "recorded-source.png"}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _Runtime()
    handler.result_bridge = SimpleNamespace(
        resolve=lambda result: {"status": result["status"], "engine": "recorded"}
    )
    handler.image_response = SimpleNamespace(adapt=lambda result: deepcopy(result))

    text = "Replace the facade finish with light travertine and preserve the windows."
    result = handler.handle_image_edit(
        text=text,
        image={"path": "recorded-source.png"},
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=MODERN,
    )

    assert result["status"] == "recorded_no_execution"
    assert len(handler.render_runtime.payloads) == 1
    decision = handler.render_runtime.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["editable_elements"] == ["facade_wall_surface"]
    assert decision["render_executed"] is False
    assert decision["comfy_invoked"] is False


def test_offline_flask_api_returns_evidence_based_decision_without_render(monkeypatch):
    """Real Flask route; every provider seam fails if unexpectedly reached."""
    import contextlib
    import io

    from PIL import Image as PILImage

    import app as application
    import core.chat.chat_architect as chat_module
    import core.vision.vision_provider_ollama_v1 as provider_module
    from core.llm.llm_gateway import LLMGateway

    def _forbidden(*args, **kwargs):
        raise AssertionError("unexpected model/provider/render call")

    monkeypatch.setattr(provider_module.OllamaVisionProvider, "analyze", _forbidden)
    monkeypatch.setattr(provider_module.OllamaVisualObserver, "observe", _forbidden)
    monkeypatch.setattr(provider_module.OllamaTextNormalizer, "normalize", _forbidden)
    monkeypatch.setattr(LLMGateway, "generate", lambda self, *a, **k: "recorded reply")
    monkeypatch.setattr(
        chat_module,
        "analyze_session_image",
        lambda *a, **k: deepcopy(CLASSICAL),
    )
    monkeypatch.setattr(
        chat_module.reference_image_understanding,
        "analyze",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        application.chat.image_handler.render_runtime,
        "render",
        _forbidden,
    )

    image = io.BytesIO()
    PILImage.new("RGB", (32, 32), "white").save(image, format="PNG")
    image.seek(0)

    with contextlib.redirect_stdout(io.StringIO()):
        response = application.app.test_client().post(
            "/api/chat",
            data={
                "text": "Remove the wall-mounted lanterns and keep everything else unchanged.",
                "mode": "image_to_image",
                "image": (image, "recorded.png"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    result = payload.get("response") or {}
    decision = result.get("architectural_design_decision") or {}
    assert result.get("status") == "blocked"
    assert result.get("reason") == "needs_spatial_targeting"
    assert decision.get("editable_elements") == ["lanterns"]
    assert decision.get("render_executed") is False
    assert decision.get("comfy_invoked") is False
    vision = result.get("vision") or {}
    assert (vision.get("element_evidence") or {}).get("elements")
