"""Focused CPU regressions for architectural-knowledge runtime connection V2.

The tests use production semantic, delta, normalization and workflow-selection
entry points.  External image execution is stubbed at ImageHandler only.
"""

import os
from types import SimpleNamespace

import pytest
from PIL import Image

from core.chat.chat_architect import ChatArchitect
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.prompt_intelligence.persian_architectural_understanding import understand
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_intent_v1 import INTENT_EDIT, classify_image_intent
from core.vision.image_registry_v1 import image_registry


@pytest.mark.parametrize(
    "text, canonical, prompt_term",
    [
        ("Convert this facade to modern style", "modern", "contemporary"),
        ("Convert this facade to classic style", "classic", "classical"),
        ("Convert this facade to neoclassical style", "neoclassical", "neoclassical"),
        ("Convert this facade to Roman classic style", "roman_classic", "roman/classical"),
        ("این نما را به سبک سنتی ایرانی بازسازی کن", "iranian_traditional", "traditional iranian"),
        ("این نما را به معماری اسلامی بازسازی کن", "islamic_architecture", "islamic architectural language"),
    ],
)
def test_style_families_share_canonical_runtime_ids(text, canonical, prompt_term):
    understanding = understand(text)
    intent = ArchitecturalIntent().extract({"prompt": text})
    compiled = compile_prompt(
        understanding,
        mode="image_to_image",
        context={"mode": "image_to_image", "base_image": True},
    )["positive_prompt"].lower()

    assert understanding["style"]["target"] == canonical
    assert intent["style"] == canonical
    assert prompt_term in compiled
    assert "architectural architectural" not in compiled


def test_english_convert_with_existing_image_is_an_edit():
    decision = classify_image_intent(
        "Convert this facade to neoclassical style and use light travertine"
    )
    assert decision["intent"] == INTENT_EDIT


def test_style_is_part_of_authoritative_global_edit_delta():
    delta = compile_edit_delta(
        "Convert this facade to neoclassical style, keep the existing geometry and windows",
        image_edit=True,
    )

    assert delta["edit_class"] == "style_change"
    assert delta["style"] == "neoclassical"
    assert "neoclassical" in delta["prompt"].lower()
    assert "same geometry" in delta["prompt"].lower()
    assert "same windows" in delta["prompt"].lower()


def test_combined_style_material_delta_preserves_both_requested_domains():
    delta = compile_edit_delta(
        "Convert this facade to neoclassical style and use light travertine",
        image_edit=True,
    )

    assert delta["edit_class"] == "material_change"
    assert delta["style"] == "neoclassical"
    assert delta["material"] == "travertine"
    assert "neoclassical" in delta["prompt"].lower()
    # The delta's own material vocabulary describes travertine as
    # "natural travertine stone" and the tone is prefixed, so the compiled
    # phrase is "light natural travertine stone". Both requested properties
    # (light tone + travertine) must survive; the exact adjacency does not.
    assert "travertine" in delta["prompt"].lower()
    assert "light" in delta["prompt"].lower()


def test_preserved_material_is_not_reclassified_as_replacement_during_style_edit():
    delta = compile_edit_delta(
        "این نما را به سبک سنتی ایرانی بازسازی کن ولی مصالح آجر موجود را حفظ کن",
        image_edit=True,
    )

    assert delta["edit_class"] == "style_change"
    assert delta["style"] == "iranian_traditional"
    assert delta["material"] is None
    assert delta["evidence"]["material_preserved"]


def test_style_delta_updates_source_bound_intent_without_losing_fixed_facts():
    normalized = ImageHandler.__new__(ImageHandler).normalize_edit_intent(
        {},
        previous_intent={
            "building_type": "villa",
            "style": "modern",
            "materials": ["brick"],
            "windows": {"layout": "regular"},
            # NOTE (WorkBuddy takeover): the established floor representation
            # is the FloorCountV1 contract, not a bare int — a bare `floors`
            # key is treated as absent by `_trusted_floor_contract` and is
            # correctly NOT promoted into the edit contract.
            "floor_count": {
                "contract": "FloorCountV1",
                "value": 2,
                "source": "USER_EXPLICIT",
            },
        },
        edit_delta={"style": "neoclassical"},
    )

    assert normalized["style"] == "neoclassical"
    assert normalized["materials"] == ["brick"]
    assert normalized["windows"] == {"layout": "regular"}
    assert normalized["floors"] == 2


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("knowledge-runtime-connection-v2")
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


def test_style_only_architectural_edit_requires_accepted_preservation_route(
    isolated_project, tmp_path
):
    source_path = tmp_path / "source.png"
    Image.new("RGB", (96, 80), (130, 115, 100)).save(source_path)
    source = image_registry.register(
        isolated_project["session_id"],
        path=str(source_path),
        source_type="uploaded",
        make_active=True,
    )
    # NOTE (WorkBuddy takeover): `register()` has no `architectural_intent`
    # parameter — the registry stores image identity, not intent. Previous
    # architectural intent reaches `_route_image_edit` through the bound
    # project resolution / stored edit context, so this test asserts the
    # routing contract only and does not fabricate an intent field.
    handler = ImageHandler.__new__(ImageHandler)
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})
    captured = []

    def fake_edit(**kwargs):
        captured.append(kwargs)
        workflow = WorkflowSelector().select(
            {
                "engine": "flux",
                "mode": "img2img",
                "image": kwargs.get("image"),
                "kontext_edit": kwargs.get("kontext_edit"),
            }
        )
        chat.render_runtime.last_render_metadata = {"workflow_name": workflow}
        return {
            "status": "success",
            "architectural_intent": kwargs.get("previous_architectural_intent"),
        }

    handler.handle_image_edit = fake_edit
    result = chat._route_image_edit(
        "Convert this facade to Roman classic style and keep the geometry and windows",
        source,
        {"image_id": source["image_id"]},
        None,
        None,
        20261023,
        {},
    )

    assert result["edit_delta"]["edit_class"] == "style_change"
    assert result["edit_delta"]["style"] == "roman_classic"
    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["admission"]["selected_workflow"] is None
    assert captured == []
