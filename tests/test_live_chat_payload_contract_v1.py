"""LIVE_CHAT_PAYLOAD_CONTRACT_V1 focused CPU acceptance.

The tests cross the real Flask multipart boundary.  External model and render
execution is replaced with local recorders; no Ollama or ComfyUI call is
allowed.
"""

import copy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import app as application
from core.project.project_workspace_v1 import project_workspace
from core.render.image_asset_bridge import ImageAssetBridge
from core.render.render_runtime import RenderRuntime


REQUEST = (
    "Redesign the facade of this existing unfinished building in a "
    "neoclassical style.\n"
    "Apply a restrained light cream travertine stone finish to the facade "
    "surfaces only.\n"
    "Add neoclassical design elements as surface relief within the existing "
    "wall planes only, including:\n"
    "- pilasters\n"
    "- capitals\n"
    "- stringcourses\n"
    "- cornices\n"
    "- window surrounds\n"
    "- stone balustrades / balustrade-style terrace guards where appropriate\n\n"
    "Important preservation / scope rules:\n"
    "- Preserve the exact building geometry, massing, floor count, structural "
    "frame, wall positions, opening layout, roof shape, and camera perspective.\n"
    "- Do not add floors, remove floors, or change the geometry.\n"
    "- Do not automatically apply facade stone to the courtyard, retaining "
    "walls, site walls, neighboring buildings, or unrelated surfaces.\n"
    "- Soffits should read as painted plaster, not facade stone.\n"
    "- Glazing and metal elements should remain distinct from the stone "
    "treatment.\n"
    "- Keep the intervention conceptual and facade-focused.\n"
    "- Do NOT add arches, domes, sculptural ornament, or unrelated classical "
    "forms."
)


NEOCLASSICAL_SERIALIZATION_REQUEST = (
    "Redesign the facade of this existing unfinished building in a "
    "neoclassical style while preserving the existing building geometry, "
    "massing, floor count, structural frame, wall positions, roof shape, "
    "opening layout, and camera perspective.\n\n"
    "Apply restrained light cream travertine stone cladding to the main "
    "facade surfaces.\n\n"
    "Create a genuine neoclassical architectural facade composition using "
    "surface-applied elements within the existing wall planes: pilasters, "
    "capitals, stringcourses, cornices, window surrounds, and stone "
    "balustrades only at suitable existing terrace edges.\n\n"
    "This is an architectural style redesign, not merely a material or color "
    "replacement.\n\n"
    "Keep soffits as painted plaster, not travertine. Keep glazing and metal "
    "elements distinct from facade stone.\n\n"
    "Do not add or remove floors. Do not modify structural geometry, roof "
    "shape, or existing openings.\n\n"
    "Do not add arches, domes, sculptural ornament, or unrelated classical "
    "forms.\n\n"
    "Do not automatically redesign the courtyard, retaining walls, "
    "neighboring buildings, or unrelated site surfaces."
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "uploads" / "chat_media" / (
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg"
)
SOURCE_SHA256 = (
    "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"
)


def _persisted_analysis():
    path = ROOT / "data" / "projects" / "project_7b6016d9" / "assets.json"
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    for record in reversed(payload.get("registry_records") or []):
        analysis = record.get("analysis") if isinstance(record, dict) else None
        if (
            isinstance(analysis, dict)
            and analysis.get("source_hash") == SOURCE_SHA256
            and len(
                ((analysis.get("element_evidence") or {}).get("elements") or [])
            ) == 18
        ):
            return copy.deepcopy(analysis)
    raise AssertionError("accepted persisted 18-element analysis not found")


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        self.workflows.append(copy.deepcopy(workflow))
        return {
            "status": "dry_run_capture",
            "engine": engine,
            "prompt_id": None,
        }


class _DryResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


class _CpuLease:
    def acquire(self):
        return True

    def release(self):
        return None


def _upload():
    return io.BytesIO(b"accepted-original-jpeg-placeholder")


def test_red_real_multipart_message_field_reaches_chat(monkeypatch, tmp_path):
    """The field used by the failed live submission must not be discarded."""

    captured = {}
    source = tmp_path / "original.jpg"
    source.write_bytes(b"accepted-original-jpeg-placeholder")

    monkeypatch.setattr(
        application.chat_attachment_service,
        "save_upload",
        lambda *args, **kwargs: {
            "status": "ready",
            "path": str(source),
            "attachment": {
                "id": "attachment_cpu",
                "kind": "image",
                "mime_type": "image/jpeg",
                "filename": "original.jpg",
                "display_name": "original.jpg",
                "url": "/artifacts/user_media/original.jpg",
                "thumbnail_url": "/artifacts/user_media/original.jpg",
                "size_bytes": source.stat().st_size,
                "source": "user_upload",
                "status": "ready",
                "metadata": {},
            },
        },
    )
    monkeypatch.setattr(
        application.chat_attachment_service,
        "public_attachment",
        lambda attachment: dict(attachment),
    )

    def _handle(text, context=None):
        captured["text"] = text
        captured["context"] = dict(context or {})
        return {
            "type": "chat",
            "status": "success",
            "message": "recorded without execution",
            "result": "recorded without execution",
        }

    monkeypatch.setattr(application.chat, "handle", _handle)

    response = application.app.test_client().post(
        "/api/chat",
        data={
            "message": REQUEST,
            "mode": "image_to_image",
            "quality": "PREVIEW",
            "seed_mode": "lock",
            "seed_value": "20261104",
            "conceptual_edit": "1",
            "image": (_upload(), "original.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured["text"] == REQUEST
    assert (response.get_json() or {})["input"]["text"] == REQUEST


def test_empty_manual_i2i_is_refused_before_chat_or_render(monkeypatch, tmp_path):
    calls = []
    source = tmp_path / "original.jpg"
    source.write_bytes(b"accepted-original-jpeg-placeholder")

    monkeypatch.setattr(
        application.chat_attachment_service,
        "save_upload",
        lambda *args, **kwargs: {
            "status": "ready",
            "path": str(source),
            "attachment": {
                "id": "attachment_cpu_empty",
                "kind": "image",
                "mime_type": "image/jpeg",
                "filename": "original.jpg",
                "url": "/artifacts/user_media/original.jpg",
                "thumbnail_url": "/artifacts/user_media/original.jpg",
                "status": "ready",
            },
        },
    )
    monkeypatch.setattr(
        application.chat_attachment_service,
        "public_attachment",
        lambda attachment: dict(attachment),
    )
    monkeypatch.setattr(
        application.chat,
        "handle",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    response = application.app.test_client().post(
        "/api/chat",
        data={
            "message": "",
            "mode": "image_to_image",
            "quality": "PREVIEW",
            "conceptual_edit": "1",
            "image": (_upload(), "original.jpg"),
        },
        content_type="multipart/form-data",
    )

    payload = response.get_json() or {}
    assert response.status_code == 400
    assert payload["error"] == "missing_image_edit_instruction"
    assert payload["response"]["generative"] is False
    assert calls == []


def test_ordinary_chat_response_contract_remains_json(monkeypatch, tmp_path):
    projects = tmp_path / "ordinary_projects"
    trash = tmp_path / "ordinary_trash"
    projects.mkdir(parents=True, exist_ok=True)
    trash.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))
    manifest = project_workspace.create("ordinary-chat-json-contract")

    monkeypatch.setattr(
        application.chat,
        "handle",
        lambda text, context=None: {
            "type": "chat",
            "status": "success",
            "message": "پاسخ عادی",
            "result": "پاسخ عادی",
        },
    )

    response = application.app.test_client().post(
        "/api/chat",
        json={
            "message": "یک پرسش عادی معماری",
            "mode": "chat",
            "project_id": manifest["project_id"],
        },
    )

    payload = response.get_json() or {}
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["input"]["text"] == "یک پرسش عادی معماری"
    assert payload["response"]["message"] == "پاسخ عادی"


@pytest.mark.parametrize(
    "request_text",
    (REQUEST, NEOCLASSICAL_SERIALIZATION_REQUEST),
)
def test_real_http_boundary_builds_one_correct_nonexecuting_graph(
    monkeypatch, tmp_path, request_text
):
    """Multipart -> app -> real ChatArchitect -> real graph, zero execution."""

    if not SOURCE.is_file():
        raise AssertionError("accepted original JPEG is missing")

    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    user_media = tmp_path / "user_media"
    comfy_input = tmp_path / "comfy_input"
    for path in (projects, trash, user_media, comfy_input):
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))
    monkeypatch.setitem(
        application.chat_attachment_service.roots, "user_media", user_media
    )
    monkeypatch.setitem(
        application.chat_attachment_service.roots, "project_media", projects
    )

    manifest = project_workspace.create("live-chat-payload-contract-v1")

    analysis = _persisted_analysis()
    assert analysis["source_hash"] == SOURCE_SHA256
    assert len(analysis["element_evidence"]["elements"]) == 18
    assert analysis.get("reused_source_hash") == SOURCE_SHA256
    assert analysis.get("reused_from_image_id")

    # The route receives the accepted persisted evidence without touching a
    # provider. This is the same analysis contract that the live source hash
    # previously reused; it is not regenerated or rewritten here.
    import core.chat.chat_architect as chat_module
    import core.prompt_intelligence.geometry_authority_handoff_v1 as authority_module

    analysis_calls = []
    decision_capture = {}

    def _analysis_replay(*args, **kwargs):
        analysis_calls.append((args, kwargs))
        return copy.deepcopy(analysis)

    monkeypatch.setattr(chat_module, "analyze_session_image", _analysis_replay)

    _real_design_decision = authority_module.resolve_design_decision
    _real_instruction_block = authority_module.decision_instruction_block

    def _capture_design_decision(*args, **kwargs):
        decision = _real_design_decision(*args, **kwargs)
        decision_capture["decision"] = decision
        return decision

    def _capture_instruction_block(*args, **kwargs):
        block = _real_instruction_block(*args, **kwargs)
        decision_capture["block"] = block
        return block

    monkeypatch.setattr(
        authority_module, "resolve_design_decision", _capture_design_decision
    )
    monkeypatch.setattr(
        authority_module, "decision_instruction_block", _capture_instruction_block
    )

    # Fail loudly if any model/provider path is reached. The prompt proof is
    # deterministic and consumes the already persisted analysis only.
    monkeypatch.setattr(
        application.chat.image_handler.semantic_intent,
        "extract",
        lambda text: {},
    )
    from core.llm.llm_gateway import LLMGateway
    import core.vision.vision_provider_ollama_v1 as vision_provider

    def _model_forbidden(*args, **kwargs):
        raise AssertionError("model/provider inference is forbidden")

    monkeypatch.setattr(LLMGateway, "generate", _model_forbidden)
    monkeypatch.setattr(
        vision_provider.OllamaVisionProvider, "analyze", _model_forbidden
    )
    monkeypatch.setattr(
        vision_provider.OllamaVisualObserver, "observe", _model_forbidden
    )
    monkeypatch.setattr(
        vision_provider.OllamaTextNormalizer, "normalize", _model_forbidden
    )

    import core.runtime.gpu_handoff_v1 as gpu_handoff

    monkeypatch.setattr(
        gpu_handoff, "gpu_render_lease", lambda *args, **kwargs: _CpuLease()
    )
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda *args, **kwargs: {
            "status": "not_loaded",
            "reason": "cpu_contract_test",
            "ownership": None,
            "unloaded": [],
            "skipped_in_use": [],
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "require_render_vram",
        lambda *args, **kwargs: {
            "ok": True,
            "reason": "cpu_contract_test",
            "free_mib": 16384,
            "min_free_mib": 11264,
            "measurement_source": "cpu_test_stub",
        },
    )

    capture = _CaptureExecutor()
    runtime = RenderRuntime()
    runtime.executor = capture
    runtime.result_bridge = _DryResultBridge()

    monkeypatch.setattr(application.chat, "render_runtime", runtime)
    monkeypatch.setattr(application.chat.image_handler, "render_runtime", runtime)
    monkeypatch.setattr(
        application.chat.image_handler.image_bridge,
        "asset_bridge",
        ImageAssetBridge(comfy_input=str(comfy_input)),
    )

    with SOURCE.open("rb") as source_handle:
        response = application.app.test_client().post(
            "/api/chat",
            data={
                "message": request_text,
                "project_id": manifest["project_id"],
                "mode": "image_to_image",
                "quality": "PREVIEW",
                "seed_mode": "lock",
                "seed_value": "20261104",
                "conceptual_edit": "1",
                "image": (source_handle, SOURCE.name),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    envelope = response.get_json() or {}
    assert envelope["input"]["text"] == request_text
    assert envelope["project_id"] == manifest["project_id"]
    assert len(capture.workflows) == 1
    assert analysis_calls, "the persisted analysis contract was not consumed"

    admission = application.chat.last_r4_admission or {}
    assert admission.get("admitted") is True
    assert admission.get("reason") == "conceptual_appearance_edit_consented"
    assert admission.get("preservation_status") == "conceptual_unverified"
    assert admission.get("selected_workflow") == "flux_img2img.json"

    decision = decision_capture.get("decision") or {}
    requested = decision.get("requested_operation") or {}
    assert requested.get("style") == "neoclassical"
    assert requested.get("operation") == "restyle"
    assert "facade_surface_expression" in (decision.get("editable_elements") or [])
    assert decision.get("execution_status") == "READY_FOR_EXISTING_WORKFLOW"
    instruction_block = decision_capture.get("block") or {}
    assert len(instruction_block.get("constraint_block") or "") > 0
    assert instruction_block.get("instruction_truncated") is not True

    graph = capture.workflows[0]
    positive = graph["206"]["inputs"]["text"].lower()
    negative = graph["212"]["inputs"]["text"].lower()
    sampler = graph["210"]["inputs"]
    staged_name = graph["300"]["inputs"]["image"]
    staged_path = comfy_input / staged_name

    assert staged_name.startswith("architectos_preview_")
    assert staged_name.endswith(".png")
    assert staged_path.is_file()

    from PIL import Image

    with Image.open(staged_path) as staged:
        assert staged.size == (336, 448)
        assert staged.format == "PNG"

    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert sampler["latent_image"] == ["301", 0]
    assert sampler["denoise"] == 0.40
    assert sampler["steps"] == 8
    assert sampler["cfg"] == 5.0
    assert sampler["seed"] == 20261104

    injected = (
        envelope["response"]["result_structured"]["render"]["injected"]
    )
    prompt_injection = injected["prompt_injection"]
    assert prompt_injection["positive"] == ["206"]
    assert prompt_injection["negative"] == ["212"]

    for required in (
        "pilasters", "capitals", "stringcourses", "cornices",
        "window surrounds", "stone balustrades", "cream travertine",
    ):
        assert required in positive

    combined_conditioning = positive + " " + negative
    for alternatives in (
        ("extra floors", "add floors", "add or remove floors"),
        ("change the geometry", "modify structural geometry"),
        ("arches",), ("domes",), ("sculptural ornament",),
        ("unrelated classical forms",), ("courtyard",),
        ("retaining walls",), ("site walls", "site surfaces", "boundary walls"),
        ("neighboring buildings",),
    ):
        assert any(term in combined_conditioning for term in alternatives)
    assert "structural frame" in combined_conditioning
    assert "sculptural architectural relief" not in positive
    assert "relief carving" not in positive

    chat_path = (
        projects / manifest["project_id"] / "conversations" / "chat.json"
    )
    with chat_path.open(encoding="utf-8") as handle:
        transcript = json.load(handle)
    user_turns = [
        item for item in transcript.get("messages") or []
        if item.get("role") == "user"
    ]
    assert user_turns[-1]["text"] == request_text

    with (projects / manifest["project_id"] / "project.json").open(
        encoding="utf-8"
    ) as handle:
        project_state = json.load(handle)
    assert project_state["counters"]["render"] == 0
    assert project_state["counters"]["edit"] == 0
    assert project_state["last_derived_asset_id"] is None

    # No executor side effect, no prompt id and no generated output/asset.
    assert graph["300"]["inputs"]["image"] != SOURCE.name
    assert "render_005" not in graph["300"]["inputs"]["image"]
    source_preview = runtime.last_render_metadata["source_preview"]
    staged_from = Path(source_preview["original_source_path"])
    import hashlib
    assert hashlib.sha256(staged_from.read_bytes()).hexdigest() == SOURCE_SHA256
    assert "render_005" not in staged_from.name
