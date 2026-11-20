"""CPU-only acceptance for IMAGE_EDIT_ENGINE_INTEGRATION_V1.

Uses the production delta compiler, geometry guard, ChatArchitect edit route,
workflow selector, Kontext workflow loader/injector, image registry and project
bridge.  External rendering is replaced only at ImageHandler.handle_image_edit;
no ComfyUI or GPU call is made.
"""

import hashlib
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from core.chat.chat_architect import ChatArchitect
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.render.image_workflow_injector import ImageWorkflowInjector
from core.render.render_runtime import RenderRuntime
from core.render.workflow_loader import WorkflowLoader
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_intent_v1 import source_image_digest
from core.vision.image_registry_v1 import image_registry


def _floor(value):
    return {
        "contract": "FloorCountV1",
        "value": value,
        "source": "user_explicit",
        "raw": str(value),
        "levels_above_ground": value,
        "levels_total": value,
    }


def _intent(material="travertine"):
    return {
        "building_type": "villa",
        "style": "modern",
        "materials": [material],
        "floors": 2,
        "floor_count": _floor(2),
        "levels": {"above_ground": 2, "total": 2},
        "roof_geometry": {"type": "pitched"},
        "massing": {"form": "compact"},
        "windows": {"layout": "regular"},
        "doors": {"count": 1},
        "balconies": {"layout": "stacked"},
        "camera": {"view": "eye_level", "lens": "35mm"},
    }


def _png(path, colour):
    Image.new("RGB", (768, 704), colour).save(path)
    return str(path)


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("image-edit-engine-integration-v1")
    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])
    try:
        yield manifest
    finally:
        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


def _chat_with_capture():
    handler = ImageHandler.__new__(ImageHandler)
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})
    captured = []

    def fake_edit(**kwargs):
        captured.append(kwargs)
        workflow = WorkflowSelector().select({
            "engine": "flux",
            "mode": "img2img",
            "image": kwargs.get("image"),
            "kontext_edit": kwargs.get("kontext_edit"),
        })
        chat.render_runtime.last_render_metadata = {"workflow_name": workflow}
        current = session_registry.current() or {}
        return {
            "status": "success",
            "architectural_intent": kwargs.get("previous_architectural_intent"),
            "source_bound_image_id": kwargs.get("parent_image_id"),
            "source_bound_session_id": current.get("session_id"),
            "source_bound_project_id": current.get("project_id"),
        }

    handler.handle_image_edit = fake_edit
    return chat, captured


def _route(chat, record, text, context=None):
    return chat._route_image_edit(
        text,
        record,
        {"image_id": record.get("image_id")},
        None,
        None,
        20261023,
        context or {},
    )


@pytest.mark.parametrize(
    "text, edit_class, target",
    [
        (
            "همین ساختمان را شب کن، فقط نورپردازی را تغییر بده و معماری ساختمان را ثابت نگه دار.",
            "time_of_day_change",
            "scene",
        ),
        (
            "make this same building daytime only and keep its architecture fixed",
            "time_of_day_change",
            "scene",
        ),
        (
            "change the facade material to brick only and keep the architecture fixed",
            "material_change",
            "facade",
        ),
    ],
)
def test_global_architectural_appearance_edits_fail_closed_without_accepted_route(
    isolated_project, tmp_path, text, edit_class, target
):
    handler = ImageHandler.__new__(ImageHandler)
    source_path = _png(tmp_path / (edit_class + ".png"), (120, 140, 160))
    source = handler._register_render_output(
        {"image_asset": {"path": source_path}},
        architectural_intent=_intent(),
    )
    chat, captured = _chat_with_capture()

    result = _route(chat, source, text)

    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["edit_delta"]["edit_class"] == edit_class
    assert result["edit_delta"]["edit_target"] == target
    assert result["admission"]["selected_workflow"] is None
    assert result["admission"]["rejected_workflows"] == {
        "flux_kontext_edit.json": "preservation_capability_unverified",
        "flux_img2img.json": "preservation_capability_unverified",
    }
    assert captured == []


def test_negated_twilight_true_night_request_respects_r3_fidelity_block(
    isolated_project, tmp_path
):
    text = (
        "همین ساختمان را به شب واقعی تبدیل کن. نور روز و روشنایی محیط را "
        "به نورپردازی طبیعی شب تغییر بده. آسمان باید واقعاً تاریک باشد، نه "
        "آبی روشن یا حالت گرگ‌ومیش. چراغ‌های موجود و روشنایی داخل ساختمان "
        "متناسب با شب دیده شوند. تعداد طبقات، شکل سقف، پنجره‌ها، دودکش‌ها، "
        "درها، ورودی، مصالح، بالکن‌ها، نرده‌ها، ابعاد و زاویه دوربین را تغییر "
        "نده و هیچ عنصر معماری جدیدی اضافه نکن."
    )
    handler = ImageHandler.__new__(ImageHandler)
    source_path = _png(tmp_path / "true-night-source.png", (120, 140, 160))
    source = handler._register_render_output(
        {"image_asset": {"path": source_path}},
        architectural_intent=_intent(),
    )
    chat, captured = _chat_with_capture()

    result = _route(chat, source, text)

    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["edit_delta"]["edit_class"] == "time_of_day_change"
    assert result["edit_delta"]["time_of_day"] == "night"
    assert result["edit_delta"]["evidence"] == {
        "time_of_day": ["شب"]
    }
    assert result["admission"]["selected_workflow"] is None
    assert captured == []


def test_global_kontext_graph_uses_source_resolution_and_no_composite(tmp_path):
    source_path = _png(tmp_path / "source.png", (100, 130, 170))
    workflow = WorkflowLoader().load("flux_kontext_edit.json")["workflow"]
    source = {
        "filename": "architectos_source_768x704.png",
        "path": source_path,
        "original_source_path": source_path,
        "original_dimensions": [768, 704],
        "working_dimensions": [768, 704],
    }

    injected = ImageWorkflowInjector().inject(
        workflow,
        "global appearance instruction",
        source,
        {"seed": 7, "denoise": None, "steps": None, "negative_prompt": ""},
    )
    graph = injected["workflow"]

    assert injected["status"] == "injected"
    assert injected["reference_edit_contract"]["scope"] == "global"
    assert graph["302"]["inputs"]["width"] == 768
    assert graph["302"]["inputs"]["height"] == 704
    assert graph["300"]["inputs"]["image"] == source["filename"]
    assert graph["9"]["inputs"]["images"] == ["208", 0]

    # FACADE_I2I_SUBMISSION_SAFETY_V1 — a maskless global edit no longer keeps
    # the graph's dead mask branch. The save path already bypassed the
    # composite; the nodes themselves named a `mask.png` that need not exist,
    # and ComfyUI validates every node in a submitted prompt. This assertion
    # used to pin the presence of those unreachable nodes.
    assert "312" not in graph
    assert "310" not in graph
    assert not [
        node for node in graph.values()
        if isinstance(node, dict)
        and node.get("class_type") in ("ImageCompositeMasked", "LoadImageMask")
    ]


def test_localized_edit_requires_mask_and_valid_mask_keeps_composite(
    isolated_project, tmp_path
):
    source_path = _png(tmp_path / "localized_source.png", (90, 120, 150))
    mask_path = tmp_path / "localized_mask.png"
    Image.new("L", (768, 704), 255).save(mask_path)
    source = image_registry.register(
        isolated_project["session_id"],
        path=source_path,
        source_type="uploaded",
        make_active=True,
    )
    chat, captured = _chat_with_capture()

    blocked = _route(chat, source, "remove the window")
    assert blocked["status"] == "unsupported_edit"
    assert blocked["unsupported_edit"]["reason"] == (
        "localized_geometry_edit_not_supported"
    )
    assert captured == []

    mask = {
        "filename": "architectos_localized_mask.png",
        "path": str(mask_path),
        "dimensions": [768, 704],
        "mode": "L",
        "source": "uploaded",
        "source_sha256": source_image_digest(source_path),
        "source_size_bytes": os.path.getsize(source_path),
        "source_image_id": source["image_id"],
        "mask_sha256": source_image_digest(str(mask_path)),
    }
    guarded = _route(
        chat,
        source,
        "remove the window",
        {
            "mask": mask,
            "kontext_edit": "1",
            "precision_controls_supplied": True,
        },
    )
    assert guarded["status"] == "blocked"
    assert guarded["reason"] == "preservation_capability_unverified"
    assert guarded["admission"]["verified_localization"] is True
    assert guarded["admission"]["selected_workflow"] is None
    assert captured == []

    workflow = WorkflowLoader().load("flux_kontext_edit.json")["workflow"]
    source_asset = {
        "filename": "architectos_localized_source.png",
        "path": source_path,
        "original_source_path": source_path,
        "original_dimensions": [768, 704],
        "working_dimensions": [768, 704],
    }
    injected = ImageWorkflowInjector().inject(
        workflow,
        "localized instruction",
        source_asset,
        {"seed": 8, "denoise": None, "steps": None, "negative_prompt": ""},
        mask_asset=mask,
    )
    graph = injected["workflow"]
    assert injected["reference_edit_contract"]["scope"] == "localized"
    assert graph["300"]["inputs"]["image"] == source_asset["filename"]
    assert graph["310"]["inputs"]["image"] == mask["filename"]
    assert graph["9"]["inputs"]["images"] == ["312", 0]
    assert graph["300"]["inputs"]["image"] != graph["310"]["inputs"]["image"]
    assert hashlib.sha256(open(source_path, "rb").read()).hexdigest() == mask[
        "source_sha256"
    ]
    assert hashlib.sha256(open(mask_path, "rb").read()).hexdigest() == mask[
        "mask_sha256"
    ]


def test_explicit_precise_kontext_without_mask_remains_blocked(
    isolated_project, tmp_path
):
    path = _png(tmp_path / "precise.png", (80, 110, 140))
    source = image_registry.register(
        isolated_project["session_id"], path=path, source_type="uploaded"
    )
    chat, captured = _chat_with_capture()
    result = _route(
        chat,
        source,
        "edit this architectural detail",
        {"kontext_edit": True, "precision_controls_supplied": True},
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "mask_required_for_precise_edit"
    assert captured == []


def test_stored_local_mask_is_restored_only_for_localized_followup(
    isolated_project, tmp_path
):
    source_path = _png(tmp_path / "followup_source.png", (95, 125, 155))
    mask_path = tmp_path / "followup_mask.png"
    Image.new("L", (768, 704), 255).save(mask_path)
    source = image_registry.register(
        isolated_project["session_id"],
        path=source_path,
        source_type="uploaded",
        make_active=True,
    )
    mask = {
        "filename": "architectos_followup_mask.png",
        "path": str(mask_path),
        "dimensions": [768, 704],
        "mode": "L",
        "source": "uploaded",
        "source_sha256": source_image_digest(source_path),
        "source_size_bytes": os.path.getsize(source_path),
        "source_image_id": source["image_id"],
        "mask_sha256": source_image_digest(str(mask_path)),
    }
    prior_local_context = {
        "mask": mask,
        "kontext_edit": True,
        "source_image_id": source["image_id"],
        "source_session_id": isolated_project["session_id"],
        "source_project_id": isolated_project["project_id"],
    }
    chat, captured = _chat_with_capture()

    session_registry.current_state().update({
        "last_image_edit_context": dict(prior_local_context)
    })
    global_result = _route(chat, source, "make this same building night")
    assert global_result["status"] == "blocked"
    assert global_result["reason"] == "preservation_capability_unverified"
    assert global_result["admission"]["verified_localization"] is False
    assert global_result["edit_delta"]["edit_target"] == "scene"
    assert captured == []

    session_registry.current_state().update({
        "last_image_edit_context": dict(prior_local_context)
    })
    local_result = _route(chat, source, "remove the window")
    assert local_result["status"] == "blocked"
    assert local_result["reason"] == "preservation_capability_unverified"
    assert local_result["admission"]["verified_localization"] is True
    assert captured == []

    session_registry.current_state().update({
        "last_image_edit_context": dict(prior_local_context)
    })
    captured_before_opt_out = len(captured)
    opted_out = _route(
        chat,
        source,
        "remove the window",
        {"precision_controls_supplied": False},
    )
    assert opted_out["status"] == "unsupported_edit"
    assert len(captured) == captured_before_opt_out


def test_unsupported_floor_restructuring_never_reaches_execution(
    isolated_project, tmp_path
):
    path = _png(tmp_path / "floor.png", (70, 100, 130))
    source = image_registry.register(
        isolated_project["session_id"], path=path, source_type="uploaded"
    )
    chat, captured = _chat_with_capture()
    result = _route(chat, source, "add a third floor")
    assert result["status"] == "unsupported_edit"
    assert result["unsupported_edit"]["reason"] == (
        "floor_count_restructuring_not_supported"
    )
    assert captured == []


def test_generation_and_unclassified_edit_keep_existing_routes():
    selector = WorkflowSelector()
    assert selector.select({"engine": "flux", "mode": "txt2img"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "img2img"}) == (
        "flux_img2img.json"
    )


def test_replacement_upload_and_legacy_source_do_not_inherit_facts(
    isolated_project, tmp_path
):
    handler = ImageHandler.__new__(ImageHandler)
    trusted = handler._register_render_output(
        {"image_asset": {"path": _png(tmp_path / "trusted.png", (60, 90, 120))}},
        architectural_intent=_intent(),
    )
    replacement_path = _png(tmp_path / "replacement.png", (140, 110, 80))
    replacement = image_registry.register(
        isolated_project["session_id"],
        path=replacement_path,
        source_type="uploaded",
        make_active=True,
    )
    session_registry.current_state().update({
        "last_image_edit_context": {
            "source_image_id": trusted["image_id"],
            "source_session_id": isolated_project["session_id"],
            "source_project_id": isolated_project["project_id"],
            "architectural_intent": _intent(),
        }
    })
    chat, captured = _chat_with_capture()
    result = _route(chat, replacement, "make this same building night")
    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["intent_ownership"]["status"] == "unknown"
    assert result["intent_ownership"]["session_fallback_used"] is False
    assert result["admission"]["source"]["image_id"] == replacement["image_id"]
    assert captured == []


def test_reference_edit_dimensions_fail_closed_instead_of_using_384x512():
    workflow = WorkflowLoader().load("flux_kontext_edit.json")["workflow"]
    injected = ImageWorkflowInjector().inject(
        workflow,
        "instruction",
        {"filename": "source.png", "working_dimensions": [769, 704]},
        {"seed": 9, "denoise": None, "steps": None, "negative_prompt": ""},
    )
    assert injected["status"] == "blocked"
    assert injected["reference_edit_contract"]["errors"] == [
        "source_dimensions_not_model_compatible"
    ]


def test_render_runtime_executes_selected_global_kontext_contract(
    tmp_path, monkeypatch
):
    """Real selector/loader/injector/runtime; only GPU/executor are stubs."""

    import core.runtime.gpu_handoff_v1 as gpu_handoff

    class Lease:
        def __init__(self):
            self.acquires = 0
            self.releases = 0

        def acquire(self):
            self.acquires += 1
            return True

        def release(self):
            self.releases += 1

    class Executor:
        def __init__(self):
            self.calls = []

        def execute(self, injected_workflow, engine, **kwargs):
            self.calls.append((injected_workflow, engine, kwargs))
            return {"status": "dry_run_capture", "engine": engine}

    lease = Lease()
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", lambda wait=None: lease)
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda **kwargs: {
            "status": "unloaded",
            "reason": None,
            "ownership": "exclusive",
            "loaded_before": [],
            "unloaded": [],
            "failed": [],
            "skipped_in_use": [],
            "vram_free_before": 16 * 1024 ** 3,
            "vram_free_after": 16 * 1024 ** 3,
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "release_comfyui_for_vision",
        lambda *args, **kwargs: {"status": "blocked", "reason": "not_needed"},
    )

    source_path = _png(tmp_path / "runtime_source.png", (110, 130, 150))
    runtime = RenderRuntime()
    executor = Executor()
    runtime.executor = executor
    design = {
        "prompt": "make this same building night",
        "original_prompt": "make this same building night",
        "mode": "img2img",
        "architectural_intent": _intent(),
        "compiled_render_prompt": (
            "REFERENCE: same building, DELTA: night lighting, "
            "PRESERVE: architecture, QUALITY: photorealistic"
        ),
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": ["natural lighting"],
        "seed": 20261023,
    }
    runtime.render(
        "isolated-test",
        design,
        "flux",
        {
            "path": source_path,
            "filename": "runtime_source.png",
            "original_source_path": source_path,
            "original_dimensions": [768, 704],
            "working_dimensions": [768, 704],
        },
        kontext_edit=True,
    )

    assert len(executor.calls) == 1
    graph, engine, _kwargs = executor.calls[0]
    assert engine == "comfyui"
    assert graph["202"]["inputs"]["unet_name"] == (
        "flux1-dev-kontext_fp8_scaled.safetensors"
    )
    assert graph["302"]["inputs"]["width"] == 768
    assert graph["302"]["inputs"]["height"] == 704
    assert graph["9"]["inputs"]["images"] == ["208", 0]
    assert runtime.last_render_metadata["workflow_name"] == (
        "flux_kontext_edit.json"
    )
    assert runtime.last_render_metadata["width"] == 768
    assert runtime.last_render_metadata["height"] == 704
    assert runtime.last_render_metadata["edit_capability"][
        "supports_instruction_edit"
    ] is True
    assert runtime.last_render_metadata["edit_capability"][
        "supports_local_edit"
    ] is True
    assert lease.acquires == 1
    assert lease.releases == 1
