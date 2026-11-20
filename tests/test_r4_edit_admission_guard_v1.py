"""R4 edit-admission guard acceptance (CPU only).

The production dispatch boundary is exercised directly.  ImageHandler rendering
is replaced with a capture stub, so any captured call is proof that the request
crossed the admission boundary; no RenderRuntime, GPU or ComfyUI code runs.
"""

import os
from types import SimpleNamespace

import pytest
from PIL import Image

from core.chat.chat_architect import ChatArchitect, _manual_image_intent
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.intent_router import intent_router
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.vision.image_intent_v1 import INTENT_ANALYZE, INTENT_EDIT
from core.vision.image_registry_v1 import image_registry


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("r4-edit-admission-guard-v1")
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


def _source(tmp_path, manifest, name="source.png", *, source_type="uploaded"):
    path = tmp_path / name
    Image.new("RGB", (96, 80), (130, 115, 100)).save(path)
    return image_registry.register(
        manifest["session_id"],
        path=str(path),
        source_type=source_type,
        make_active=True,
    )


def _chat_capture():
    handler = ImageHandler.__new__(ImageHandler)
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})
    calls = []

    def fake_edit(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "source_bound_image_id": kwargs.get("parent_image_id")}

    handler.handle_image_edit = fake_edit
    return chat, calls


def _route(chat, record, text, context=None, image_understanding=None):
    return chat._route_image_edit(
        text,
        record,
        {"image_id": record.get("image_id")},
        None,
        None,
        20261028,
        context or {},
        image_understanding=image_understanding,
    )


def _assert_capability_block(result, calls):
    assert result["type"] == "render_blocked"
    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["admission"]["selected_workflow"] is None
    assert calls == []


def test_A_material_edit_with_strict_preservation_is_blocked(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _chat_capture()
    result = _route(
        chat,
        source,
        "مصالح نما را سنگ کن؛ حجم و پنجره‌ها ثابت بمانند و هیچ چیز دیگری تغییر نکند.",
    )
    _assert_capability_block(result, calls)
    assert result["admission"]["edit_class"] == "material_change"
    assert result["admission"]["strict_preservation"] is True
    assert "رندر اجرا نشد" in result["message"]


def test_B_localized_door_colour_without_verified_localization_is_blocked(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _chat_capture()
    result = _route(chat, source, "فقط رنگ در ورودی را آبی کن")
    _assert_capability_block(result, calls)
    assert result["admission"]["localization_required"] is True
    assert result["admission"]["verified_localization"] is False


def test_C_closing_a_protected_through_passage_is_blocked(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _chat_capture()
    result = _route(
        chat,
        source,
        "گذر سرتاسری میانی را ببند و همه اجزای دیگر را بدون تغییر نگه دار",
    )
    _assert_capability_block(result, calls)
    assert "through_passage" in result["admission"]["protected_spatial_targets"]


def test_D_E_exact_preservation_selects_neither_kontext_nor_img2img(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _chat_capture()
    result = _route(
        chat,
        source,
        "preserve exactly this building and only change the facade material to stone",
    )
    _assert_capability_block(result, calls)
    rejected = result["admission"]["rejected_workflows"]
    assert rejected["flux_kontext_edit.json"] == "preservation_capability_unverified"
    assert rejected["flux_img2img.json"] == "preservation_capability_unverified"


def test_F_G_H_persian_question_stays_analysis_in_auto_and_manual_modes():
    question = "این ساختمان چند طبقه دارد و گذر ورودی آن چگونه دیده می‌شود؟"
    auto = _manual_image_intent("", question, intent_router)
    manual = _manual_image_intent("analyze_image", question, intent_router)
    assert auto["intent"] == INTENT_ANALYZE
    assert auto["intent"] != INTENT_EDIT
    assert manual["intent"] == INTENT_ANALYZE
    assert manual["intent"] != INTENT_EDIT


def test_I_stale_waiting_state_and_active_derived_image_cannot_bypass_guard(
    isolated_project, tmp_path
):
    parent = _source(tmp_path, isolated_project, "parent.png")
    derived = _source(
        tmp_path,
        isolated_project,
        "derived.png",
        source_type="image_to_image",
    )
    session_registry.current_state().update(
        {
            "waiting_image_edit": True,
            "last_render_asset": {"path": parent["path"]},
            "last_image_asset": {"path": derived["path"]},
        }
    )
    before_count = image_registry.count(isolated_project["session_id"])
    before_active = image_registry.active(isolated_project["session_id"])
    chat, calls = _chat_capture()
    result = _route(
        chat,
        derived,
        "فقط مصالح نما را عوض کن و هیچ چیز دیگری تغییر نکند",
        {"waiting_image_edit": True},
    )
    _assert_capability_block(result, calls)
    assert image_registry.count(isolated_project["session_id"]) == before_count
    assert image_registry.active(isolated_project["session_id"])["image_id"] == before_active["image_id"]


def test_J_cross_session_source_is_blocked_before_image_handler(
    isolated_project, tmp_path
):
    foreign_path = tmp_path / "foreign.png"
    Image.new("RGB", (96, 80), (90, 90, 90)).save(foreign_path)
    foreign = image_registry.register(
        "foreign-session",
        path=str(foreign_path),
        source_type="uploaded",
        make_active=True,
    )
    chat, calls = _chat_capture()
    result = _route(
        chat,
        foreign,
        "only change the facade material to stone and preserve everything else exactly",
    )
    assert result["type"] == "render_blocked"
    assert result["reason"] == "source_image_authority_mismatch"
    assert calls == []


def test_K_L_M_blocked_edit_creates_no_asset_submission_or_active_change(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    before_count = image_registry.count(isolated_project["session_id"])
    before_active = image_registry.active(isolated_project["session_id"])
    chat, calls = _chat_capture()
    result = _route(
        chat,
        source,
        "only change the facade colour to blue; do not alter any opening or material",
    )
    _assert_capability_block(result, calls)
    assert image_registry.count(isolated_project["session_id"]) == before_count
    assert image_registry.active(isolated_project["session_id"])["image_id"] == before_active["image_id"]


def test_N_unverified_observation_is_never_promoted_to_verified_geometry(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _chat_capture()
    result = _route(
        chat,
        source,
        "دقیقاً همین ساختمان را حفظ کن و فقط رنگ نما را آبی کن",
        image_understanding={
            "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
            "observations": {"openings": ["possible through-passage"]},
        },
    )
    _assert_capability_block(result, calls)
    assert result["admission"]["architectural_evidence"] == "observation_only"
    assert "verified_geometry" not in result["admission"]


def test_O_P_non_architectural_edit_remains_on_its_existing_route(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project, "ordinary-photo.png")
    chat, calls = _chat_capture()
    result = _route(chat, source, "change the image colour to blue")
    assert result["status"] == "success"
    assert len(calls) == 1
    assert calls[0]["parent_image_id"] == source["image_id"]
    assert calls[0]["kontext_edit"] is True
