from io import BytesIO
from pathlib import Path

from werkzeug.datastructures import FileStorage

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.chat.chat_attachment import ChatAttachmentServiceV1
from core.chat.handlers.image_handler import ImageHandler
from core.chat.image_response_adapter import ImageResponseAdapter
from core.chat.response_adapter import ResponseAdapter
from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder
from core.render.prompt_builder import PromptBuilder
from core.render.render_result_bridge import RenderResultBridge
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector


def resolver():
    return SharedFacadeKnowledgeResolverV1()


def attachment_service(tmp_path):
    roots = {
        "user_media": tmp_path / "user_media",
        "comfy_output": tmp_path / "comfy_output",
        "architectos_output": tmp_path / "outputs",
        "architectos_export": tmp_path / "exports",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    return ChatAttachmentServiceV1(roots)


def test_a_raw_modern_brick_consumes_shared_knowledge_and_keeps_facade_details():
    raw_intent = {
        "style": "modern",
        "materials": ["brick"],
        "facade_details": ["projecting entrance frame"],
        "mode": "img2img",
        "preserve_geometry": True,
    }
    handler = ImageHandler.__new__(ImageHandler)
    intent = handler.normalize_edit_intent(raw_intent)
    resolved = resolver().resolve(intent)
    intent["resolved_facade_knowledge"] = resolved

    assert resolved["canonical_style"] == "modern"
    assert resolved["materials"]["compatible_options"]
    assert resolved["user_facade_details"] == ["projecting entrance frame"]
    assert resolved["geometry_authority"] == "SOURCE_IMAGE"
    assert "number_of_floors" in resolved["preserve_constraints"]
    assert "architectural_style_ontology.json" in resolved["provenance"]
    assert "material_ontology.json" in resolved["provenance"]

    prompt = ImageEditPromptBuilder().build(intent)
    assert "resolved ArchitectOS facade knowledge" in prompt
    assert "projecting entrance frame" in prompt
    assert "original building silhouette" in prompt
    assert WorkflowSelector().select({"engine": "flux", "mode": "img2img"}) == "flux_img2img.json"


def test_b_neoclassical_natural_stone_uses_ontology_not_travertine_special_case():
    intent = {
        "style": "neo-classical",
        "materials": ["natural stone"],
        "mode": "img2img",
        "preserve_geometry": True,
    }
    resolved = resolver().resolve(intent)
    intent["resolved_facade_knowledge"] = resolved
    prompt = ImageEditPromptBuilder().build(intent)

    assert resolved["canonical_style"] == "neoclassical"
    assert "architectural_style_ontology.json" in resolved["provenance"]
    assert resolved["materials"]["resolved"][0]["name"] == "natural_stone"
    assert "formal entry" in prompt
    assert "luxury classical travertine stone residence" not in prompt


def test_c_text_to_image_contemporary_brick_stays_separate_and_is_enriched():
    intent = {
        "style": "contemporary",
        "materials": ["brick"],
        "mode": "text2img",
    }
    resolved = resolver().resolve(intent)
    intent["resolved_facade_knowledge"] = resolved
    prompt = PromptBuilder().build({"architectural_intent": intent})["description"]

    assert resolved["requested_style"] == "contemporary"
    assert resolved["canonical_style"] == "modern"
    assert "approved facade design" in prompt
    assert "brick" in prompt
    assert WorkflowSelector().select({"engine": "flux", "mode": "text2img"}) == "flux.json"


def test_render_runtime_shared_integration_mutates_only_render_intent_contract():
    runtime = RenderRuntime.__new__(RenderRuntime)
    runtime.facade_knowledge_resolver = resolver()
    intent = {"style": "classical", "materials": ["stone"], "mode": "text2img"}

    resolved = runtime.resolve_shared_facade_knowledge(intent)

    assert intent["facade_knowledge_consumed"] is True
    assert intent["resolved_facade_knowledge"] is resolved
    assert intent["style"] == "classic"
    assert intent["mode"] == "text2img"


def test_d_approved_design_is_geometry_authority_and_does_not_become_img2img():
    intent = {
        "style": "modern",
        "materials": ["stone"],
        "facade_language": {"primary": "deep_frames"},
        "facade_composition": {"entrance": "strong hierarchy"},
        "render_source": {
            "type": "approved_bim_design",
            "approval_status": True,
        },
        "mode": "text2img",
    }
    resolved = resolver().resolve(intent)

    assert resolved["geometry_authority"] == "APPROVED_ARCHITECTOS_DESIGN"
    assert "approved_design_intent" in resolved["provenance"]
    assert WorkflowSelector().select({"engine": "flux", "mode": "text2img"}) == "flux.json"


def test_e_style_aliases_are_deterministic_and_distinct_variants_survive():
    canonicalize = SharedFacadeKnowledgeResolverV1.canonicalize_style
    assert canonicalize("classic")["canonical_style"] == "classic"
    assert canonicalize("classical")["canonical_style"] == "classic"
    assert canonicalize("roman_classic")["canonical_style"] == "roman_classic"
    assert canonicalize("roman_classical")["canonical_style"] == "roman_classic"
    assert canonicalize("neo_classical")["canonical_style"] == "neoclassical"
    assert canonicalize("neo-classical")["canonical_style"] == "neoclassical"
    assert canonicalize("contemporary_warm")["canonical_style"] == "contemporary_warm"
    assert canonicalize("contemporary_stone")["canonical_style"] == "contemporary_stone"


class FakeState:
    def __init__(self):
        self.data = {}
        self.messages = []

    def update(self, values):
        self.data.update(values)

    def add_message(self, role, text, attachments):
        self.messages.append({"role": role, "text": text, "attachments": attachments})


class FakeImageBridge:
    def __init__(self):
        self.paths = []

    def process_upload(self, project_id, path):
        self.paths.append(Path(path))
        return {
            "asset": {
                "filename": "comfy_source.png",
                "path": str(path),
                "status": "ready",
            }
        }


def test_f_user_image_upload_has_public_attachment_and_still_registers_for_edit(tmp_path):
    service = attachment_service(tmp_path)
    handler = ImageHandler.__new__(ImageHandler)
    handler.attachment_service = service
    handler.image_bridge = FakeImageBridge()
    # `state` is a read-only property resolving the session's state; the
    # backing attribute is the documented injection point.
    handler._state = FakeState()
    upload = FileStorage(stream=BytesIO(b"fake png"), filename="building.png", content_type="image/png")

    result = handler.handle_image_upload_only(upload)

    assert result["status"] == "waiting_for_instruction"
    assert result["attachments"][0]["source"] == "user_upload"
    assert result["attachments"][0]["url"].startswith("/artifacts/user_media/")
    assert "path" not in result["attachments"][0]
    assert handler.image_bridge.paths[0].is_file()
    assert handler.state.data["waiting_image_edit"] is True

    # CHAT_UPLOAD_SINGLE_OWNER_V1 — the request boundary owns the user-turn
    # transcript record; this handler must NOT write a second one. It used to,
    # which stored one user turn twice (two image bubbles after a refresh,
    # one without a URL).
    assert handler.state.messages == []


def test_g_mocked_comfy_metadata_becomes_assistant_image_attachment(tmp_path):
    service = attachment_service(tmp_path)
    output = service.roots["comfy_output"] / "render_01.png"
    output.write_bytes(b"mock image")

    bridge = RenderResultBridge.__new__(RenderResultBridge)
    bridge.output_dir = str(service.roots["comfy_output"])
    bridge.attachment_service = service
    image_asset = bridge.build_image_asset(
        {"filename": "render_01.png", "subfolder": "", "type": "output"}
    )

    adapter = ImageResponseAdapter.__new__(ImageResponseAdapter)
    adapter.output_prefix = str(service.roots["comfy_output"])
    adapter.attachment_service = service
    response = adapter.adapt({"status": "success", "prompt_id": "mock", "image": image_asset})

    assert response["status"] == "success"
    assert response["attachments"][0]["kind"] == "render"
    assert response["attachments"][0]["url"] == "/artifacts/comfy_output/render_01.png"
    assert "path" not in response["attachments"][0]


def test_h_real_generated_file_can_be_an_assistant_attachment(tmp_path):
    service = attachment_service(tmp_path)
    report = service.roots["architectos_output"] / "report.json"
    report.write_text('{"status":"ok"}', encoding="utf-8")

    attachment = service.attachment_for_path(
        report,
        root_key="architectos_output",
        source="assistant_generated",
        kind="file",
    )

    assert attachment["filename"] == "report.json"
    assert attachment["size_bytes"] > 0
    assert attachment["url"].startswith("/artifacts/architectos_output/")

    public = service.public_attachment(attachment)
    response = ResponseAdapter().adapt(
        {
            "type": "chat",
            "status": "success",
            "result": "گزارش آماده شد.",
            "attachments": [public],
        }
    )
    assert response["attachments"][0]["filename"] == "report.json"
    assert response["message"] == "گزارش آماده شد."


def test_i_missing_comfy_artifact_never_creates_fake_success_attachment(tmp_path):
    service = attachment_service(tmp_path)
    adapter = ImageResponseAdapter.__new__(ImageResponseAdapter)
    adapter.output_prefix = str(service.roots["comfy_output"])
    adapter.attachment_service = service

    response = adapter.adapt(
        {"status": "success", "image": {"filename": "missing.png", "type": "output"}}
    )

    assert response["status"] == "chat_artifact_exposure_failure"
    assert response["render_status"] == "success"
    assert response["attachments"] == []


def test_j_path_traversal_and_arbitrary_windows_paths_are_rejected(tmp_path):
    service = attachment_service(tmp_path)
    valid = service.roots["user_media"] / "safe.txt"
    valid.write_text("safe", encoding="utf-8")

    assert service.resolve_public_path("user_media", "safe.txt") == valid.resolve()
    assert service.resolve_public_path("user_media", "../safe.txt") is None
    assert service.resolve_public_path("user_media", "../../outside.txt") is None
    assert service.resolve_public_path("user_media", r"C:\Windows\win.ini") is None
    assert service.resolve_public_path("unknown_root", "safe.txt") is None


def test_k_text_only_response_remains_backward_compatible():
    response = ResponseAdapter().adapt(
        {"type": "chat", "status": "success", "result": "سلام"}
    )

    assert response["message"] == "سلام"
    assert response["result"] == "سلام"
    assert "attachments" not in response


def test_l_route_separation_does_not_depend_on_facade_style():
    selector = WorkflowSelector()

    assert selector.select({"engine": "flux", "mode": "img2img", "image": {"filename": "x.png"}}) == "flux_img2img.json"
    assert selector.select({"engine": "flux", "mode": "text2img"}) == "flux.json"
    assert selector.select({"engine": "wan", "mode": "i2v"}) == "wan_i2v.json"


def test_ui_keeps_one_functional_send_image_definition():
    """The UI must keep exactly ONE functional image-upload path.

    REPLACED ASSERTION — the previous version asserted
    `async function sendImage()`, `fetch("/api/image")` and
    `extractAttachments`. All three belong to a REMOVED frontend design and
    none of them exists in HEAD either, so the test could never pass. Dead
    frontend code must not be restored just to satisfy it.

    The INTENT is preserved: one image-send definition, real file bytes, the
    role-bearing fields the Core API validates, and URL-based attachment
    rendering for restored history.
    """

    source = (Path(__file__).resolve().parents[1] / "ui" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    # exactly one place builds the chat upload body from a selected file
    assert source.count('form.append("image", files[0]);') == 1

    # the role-bearing dual-image transport still originates in the UI
    assert 'form.append("image_a", files[0]);' in source
    assert 'form.append("image_b", files[1]);' in source

    # restored attachments are rendered from their stored URL
    assert "function attachmentImageUrl(attachment)" in source
