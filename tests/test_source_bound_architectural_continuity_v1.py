import json
import os
from types import SimpleNamespace

import pytest

from core.chat.handlers.image_handler import ImageHandler
from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.vision.image_registry_v1 import image_registry


def _floor(value, source="user_explicit"):
    return {
        "contract": "FloorCountV1",
        "value": value,
        "source": source,
        "raw": str(value) if value is not None else "",
        "levels_above_ground": value,
        "levels_total": value,
    }


def _intent(floors=2, material="travertine"):
    intent = {
        "building_type": "villa",
        "style": "modern",
        "materials": [material],
        "roof_geometry": {"type": "pitched"},
        "massing": {"form": "compact"},
        "windows": {"layout": "regular"},
        "doors": {"count": 1},
        "balconies": {"layout": "stacked"},
        "dimensions": {"source": "user_text", "width": "12 m"},
        "proportions": {"width_to_height": "2:1"},
        "camera": {"view": "eye_level", "lens": "35mm"},
    }
    if floors is not None:
        intent.update({
            "floors": floors,
            "floor_count": _floor(floors),
            "levels": {"above_ground": floors, "total": floors},
        })
    return intent


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("source-bound-test")
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


def _image_file(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"not-rendered-test-asset")
    return str(path)


def _handler():
    return ImageHandler.__new__(ImageHandler)


def test_A_generated_two_storey_snapshot_and_night_continuity(
    isolated_project, tmp_path
):
    handler = _handler()
    source = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "a.png")}},
        architectural_intent=_intent(2),
    )
    snapshot = source["architectural_intent_snapshot"]
    assert snapshot["source_image_id"] == source["image_id"]
    assert snapshot["source_project_id"] == isolated_project["project_id"]
    assert snapshot["intent"]["floor_count"]["value"] == 2

    current = ArchitecturalIntent().extract("make it night")
    normalized = handler.normalize_edit_intent(
        current, snapshot["intent"], {"time_of_day": "night"}
    )
    assert normalized["floors"] == 2
    assert normalized["floor_count"]["source"] == "user_explicit"
    assert normalized["roof_geometry"] == {"type": "pitched"}
    assert normalized["camera"]["view"] == "eye_level"


def test_B_material_change_preserves_four_floors(isolated_project):
    handler = _handler()
    normalized = handler.normalize_edit_intent(
        ArchitecturalIntent().extract("replace the facade with brick"),
        _intent(4),
        {"material": "brick"},
    )
    assert normalized["materials"] == ["brick"]
    assert normalized["floors"] == 4
    assert normalized["windows"] == {"layout": "regular"}


def test_C_explicit_three_storey_correction_is_preserved_but_prompt_gap_remains(
    isolated_project,
):
    handler = _handler()
    current = ArchitecturalIntent().extract(
        "make this a three-storey building"
    )
    assert current["floor_count"]["value"] == 3
    normalized = handler.normalize_edit_intent(current, _intent(2), {})
    assert normalized["floors"] == 3
    assert normalized["floor_count"]["value"] == 3
    assert normalized["floor_count"]["source"] == "user_explicit"


def test_D_style_change_preserves_openings_balconies(isolated_project):
    handler = _handler()
    current = ArchitecturalIntent().extract("change the style to modern")
    current["style"] = "modern"
    normalized = handler.normalize_edit_intent(current, _intent(4), {})
    assert normalized["style"] == "modern"
    assert normalized["windows"] == {"layout": "regular"}
    assert normalized["doors"] == {"count": 1}
    assert normalized["balconies"] == {"layout": "stacked"}


def test_E_unknown_floor_stays_unknown(isolated_project):
    handler = _handler()
    normalized = handler.normalize_edit_intent(
        ArchitecturalIntent().extract("make it night"),
        _intent(None),
        {"time_of_day": "night"},
    )
    assert "floors" not in normalized
    assert "floor_count" not in normalized
    assert "levels" not in normalized


def test_F_confirmed_floor_beats_uncertain_observation(isolated_project):
    handler = _handler()
    current = {
        "floor_count": {
            "contract": "FloorCountV1",
            "value": 3,
            "source": "vision",
            "confidence": 0.42,
        },
        "prompt": "make it night",
    }
    normalized = handler.normalize_edit_intent(current, _intent(4), {})
    assert normalized["floors"] == 4
    assert normalized["floor_count"]["source"] == "user_explicit"
    observed = normalized["architectural_observations"]["floor_count"]
    assert observed == {
        "contract": "FloorCountObservationV1",
        "value": 3,
        "source": "vision",
        "confidence": 0.42,
    }


def test_G_t2i_parser_contract_survives_normalization(isolated_project):
    handler = _handler()
    parsed = ArchitecturalIntent().extract("create a two-storey villa")
    normalized = handler.normalize_intent(parsed)
    assert normalized["floors"] == 2
    assert normalized["floor_count"]["value"] == 2
    assert normalized["floor_count"]["source"] == "user_explicit"


def test_H_new_upload_has_no_old_snapshot_and_cross_project_is_rejected(
    isolated_project, tmp_path
):
    handler = _handler()
    first = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "old.png")}},
        architectural_intent=_intent(4),
    )
    old_snapshot = first["architectural_intent_snapshot"]
    uploaded = image_registry.register(
        isolated_project["session_id"],
        path=_image_file(tmp_path, "new.png"),
        source_type="uploaded",
        make_active=True,
    )
    resolution = handler.resolve_source_bound_intent(uploaded)
    assert resolution["status"] == "unknown"
    assert resolution["intent"] == {}
    assert "architectural_intent_snapshot" not in uploaded

    session_registry.end()
    project_registry_bridge.unbind()
    second = project_workspace.create("other-project")
    project_registry_bridge.bind(second["project_id"])
    session_registry.begin(second["session_id"])
    forged = dict(first)
    forged["architectural_intent_snapshot"] = old_snapshot
    rejected = handler.resolve_source_bound_intent(forged)
    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "snapshot_ownership_mismatch"


def test_I_generate_edit_edit_and_project_reopen(isolated_project, tmp_path):
    handler = _handler()
    source = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "source.png")}},
        architectural_intent=_intent(2),
    )
    night = handler.normalize_edit_intent(
        ArchitecturalIntent().extract("make it night"),
        source["architectural_intent_snapshot"]["intent"],
        {"time_of_day": "night"},
    )
    derived_1 = handler._register_derived_output(
        {"image_asset": {"path": _image_file(tmp_path, "night.png")}},
        parent_image_id=source["image_id"],
        architectural_intent=night,
    )
    material = handler.normalize_edit_intent(
        ArchitecturalIntent().extract("replace the facade with brick"),
        derived_1["architectural_intent_snapshot"]["intent"],
        {"material": "brick"},
    )
    derived_2 = handler._register_derived_output(
        {"image_asset": {"path": _image_file(tmp_path, "brick.png")}},
        parent_image_id=derived_1["image_id"],
        architectural_intent=material,
    )
    assert derived_2["parent_image_id"] == derived_1["image_id"]
    assert image_registry.active(isolated_project["session_id"])["image_id"] == derived_2["image_id"]
    assert derived_2["architectural_intent_snapshot"]["intent"]["floors"] == 2
    assert derived_2["architectural_intent_snapshot"]["intent"]["materials"] == ["brick"]

    project_registry_bridge.save(isolated_project["project_id"])
    assets_path = os.path.join(
        project_workspace.project_dir(isolated_project["project_id"]),
        "assets.json",
    )
    persisted = json.loads(open(assets_path, encoding="utf-8").read())
    assert persisted["registry_records"][-1][
        "architectural_intent_snapshot"
    ]["intent"]["floors"] == 2

    session_registry.end()
    project_registry_bridge.unbind()
    image_registry.reset(isolated_project["session_id"])
    project_registry_bridge.bind(isolated_project["project_id"])
    session_registry.begin(isolated_project["session_id"])
    restored = image_registry.active(isolated_project["session_id"])
    resolved = handler.resolve_source_bound_intent(restored)
    assert resolved["status"] == "trusted"
    assert resolved["intent"]["floors"] == 2
    assert resolved["intent"]["materials"] == ["brick"]


def test_invalid_conflicting_and_nonserializable_snapshots_fail_closed(
    isolated_project, tmp_path
):
    handler = _handler()
    conflict = _intent(2)
    conflict["floors"] = 3
    rejected = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "conflict.png")}},
        architectural_intent=conflict,
    )
    assert "architectural_intent_snapshot" not in rejected

    unsafe = _intent(2)
    unsafe["roof_geometry"] = {"raw": b"bytes-are-not-json"}
    rejected = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "unsafe.png")}},
        architectural_intent=unsafe,
    )
    assert "architectural_intent_snapshot" not in rejected

    safe = _intent(2)
    safe["prompt"] = "do not persist me"
    safe["conversation_history"] = ["do not persist me"]
    accepted = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "safe.png")}},
        architectural_intent=safe,
    )
    stored = accepted["architectural_intent_snapshot"]["intent"]
    assert "prompt" not in stored
    assert "conversation_history" not in stored


def test_route_uses_selected_record_and_rejects_mismatched_session_fallback(
    isolated_project, tmp_path
):
    handler = _handler()
    source = handler._register_render_output(
        {"image_asset": {"path": _image_file(tmp_path, "bound.png")}},
        architectural_intent=_intent(4),
    )
    upload = image_registry.register(
        isolated_project["session_id"],
        path=_image_file(tmp_path, "replacement.png"),
        source_type="uploaded",
        make_active=True,
    )
    session_registry.current_state().update({
        "last_architectural_intent": _intent(4),
        "last_image_edit_context": {
            "source_image_id": source["image_id"],
            "source_session_id": isolated_project["session_id"],
            "source_project_id": isolated_project["project_id"],
            "architectural_intent": _intent(4),
        },
    })

    captured = []

    def fake_edit(**kwargs):
        captured.append(kwargs["previous_architectural_intent"])
        return {
            "status": "success",
            "architectural_intent": kwargs["previous_architectural_intent"],
            "source_bound_image_id": kwargs["parent_image_id"],
            "source_bound_session_id": isolated_project["session_id"],
            "source_bound_project_id": isolated_project["project_id"],
        }

    handler.handle_image_edit = fake_edit
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})

    replacement_result = chat._route_image_edit(
        "make it night", upload, {}, None, None, 1, {}
    )
    assert captured[-1] == {}
    assert replacement_result["intent_ownership"]["status"] == "unknown"
    assert replacement_result["intent_ownership"]["session_fallback_used"] is False

    bound_result = chat._route_image_edit(
        "make it night", source, {}, None, None, 1, {}
    )
    assert bound_result["status"] == "blocked"
    assert bound_result["reason"] == "preservation_capability_unverified"
    assert len(captured) == 1
    assert bound_result["admission"]["source"]["image_id"] == source["image_id"]
    assert bound_result["intent_ownership"]["status"] == "trusted"
