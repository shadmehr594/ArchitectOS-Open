"""VISION_STOREY_DISAMBIGUATION_V3 — focused CPU-only regressions.

No render, network, Ollama, or ComfyUI execution occurs here.  The tests pin
the existing Vision provider instruction contract and exercise the established
ChatArchitect -> ImageHandler -> RenderRuntime-result -> Vision -> fidelity
path with a recorded executor result that names a real existing output PNG.
"""

import contextlib
import io
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from core.chat.chat_architect import ChatArchitect
from core.chat.conversation_state import ConversationState
from core.chat.handlers import image_handler as image_handler_module
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.vision import design_constraint_fidelity_v1 as fidelity
from core.vision.facade_reference_vision_provider_v1 import (
    ROLE_TARGET_BUILDING,
    _ROLE_PROMPTS,
    map_to_contract,
)
from core.vision.image_registry_v1 import image_registry


REAL_KONTEXT_OUTPUT = (
    r"C:\ComfyUI-Zluda\output\architectos_kontext_edit_00004_.png"
)
REAL_KONTEXT_SOURCE = (
    r"<repo-root>\uploads\chat_media"
    r"\29cb524c0117_source_day_6819dd.png"
)


def _intent():
    return {
        "building_type": "villa",
        "floors": 2,
        "roof_geometry": {"type": "pitched"},
        "windows": {"layout": "regular"},
        "doors": {"count": 1},
    }


def test_target_prompt_distinguishes_principal_storeys_from_roof_openings():
    prompt = " ".join(_ROLE_PROMPTS[ROLE_TARGET_BUILDING].lower().split())

    for required in (
        "principal storey",
        "attic",
        "gable window",
        "dormer",
        "roof parapet",
        "roof terrace",
        "mezzanine",
        "roof window is not automatically",
        "habitable attic",
    ):
        assert required in prompt


def test_roof_opening_can_be_recorded_without_becoming_a_third_storey():
    mapped = map_to_contract({
        "building_type": "villa",
        "visible_floor_count": 2,
        "floor_observation": {
            "count": 2,
            "count_type": "TOTAL",
            "storey_divisions_legible": True,
            "evidence": (
                "two full principal storeys; the central opening is within "
                "the pitched-roof gable and is not a full storey"
            ),
        },
        "roof_features": ["pitched roof", "central gable window"],
    })

    result = fidelity.evaluate(
        _intent(),
        "keep the existing two-storey villa",
        mapped,
        requested_text="same two-storey villa at night",
    )

    assert mapped["visible_floor_count"] == 2
    assert any("gable window" in item for item in mapped["roof_features"])
    assert result["floor_status"] == fidelity.FLOOR_VERIFIED


def test_real_additional_principal_storey_is_not_discarded():
    mapped = map_to_contract({
        "visible_floor_count": 3,
        "floor_observation": {
            "count": 3,
            "count_type": "TOTAL",
            "storey_divisions_legible": True,
            "evidence": "three full-height facade bands with repeated openings",
        },
        "roof_features": ["pitched roof above the third principal storey"],
    })

    observed = fidelity.observed_constraints(mapped)
    assert observed["floors"] == 3
    assert observed["floor_count_type"] == "TOTAL"


@pytest.mark.parametrize("count_type", ["AMBIGUOUS", "VISIBLE_LEVELS"])
def test_uncertain_roof_level_remains_unverified(count_type):
    result = fidelity.evaluate(
        _intent(),
        "same villa",
        {
            "visible_floor_count": 3,
            "building_type": "villa",
            "floor_observation": {
                "count": 3,
                "count_type": count_type,
                "storey_divisions_legible": False,
                "evidence": "roof-level opening may be attic or a roof storey",
            },
        },
        requested_text="same two-storey villa",
    )

    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["design_accepted"] is False


def test_cropped_total_is_still_vetoed_as_a_lower_bound():
    observed = fidelity.observed_constraints({
        "visible_floor_count": 4,
        "floor_observation": {
            "count": 4,
            "count_type": "TOTAL",
            "storey_divisions_legible": True,
        },
        "perspective_limitations": ["building is cropped at the lower frame"],
    })

    assert observed["floors"] is None
    assert observed["visible_floor_count_lower_bound"] == 4


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("vision-storey-disambiguation-v3")
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


def _registered_source(tmp_path, manifest):
    source_path = tmp_path / "source-villa.png"
    Image.new("RGB", (768, 704), (150, 155, 160)).save(source_path)
    handler = ImageHandler.__new__(ImageHandler)
    return handler._register_render_output(
        {"image_asset": {"path": str(source_path)}},
        architectural_intent=_intent(),
    )


def _route_chat(handler):
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})
    return chat


def test_verify_render_flag_reaches_global_kontext_edit_handler(
    isolated_project, tmp_path
):
    source = _registered_source(tmp_path, isolated_project)
    handler = ImageHandler.__new__(ImageHandler)
    captured = []

    def fake_edit(**kwargs):
        captured.append(kwargs)
        return {"status": "success", "architectural_intent": _intent()}

    handler.handle_image_edit = fake_edit
    chat = _route_chat(handler)

    result = chat._route_image_edit(
        "make this same building night and preserve its architecture",
        source,
        {"image_id": source["image_id"]},
        None,
        None,
        20261024,
        {"verify_render": True},
    )

    assert result["status"] == "success"
    assert captured[-1]["kontext_edit"] is True
    assert captured[-1]["verify_render"] is True


class _RecordedRuntime:
    def __init__(self):
        self.calls = []
        self.last_render_metadata = {"workflow_name": "flux_kontext_edit.json"}

    def render(self, project_id, payload, engine, image_asset=None, **kwargs):
        self.calls.append({
            "project_id": project_id,
            "payload": payload,
            "engine": engine,
            "image_asset": image_asset,
            "kwargs": kwargs,
        })
        return {
            "status": "success",
            "execution": {
                "status": "completed",
                "prompt_id": "recorded-kontext-v3",
                "images": [{
                    "filename": os.path.basename(REAL_KONTEXT_OUTPUT),
                    "subfolder": "",
                    "type": "output",
                }],
            },
        }


class _Bridge:
    def resolve(self, result):
        return {
            "status": "success",
            "engine": "comfyui",
            "workflow": "flux_kontext_edit.json",
            "prompt_id": "recorded-kontext-v3",
            "image": {
                "filename": os.path.basename(REAL_KONTEXT_OUTPUT),
                "path": REAL_KONTEXT_OUTPUT,
            },
        }


class _Intent:
    def extract(self, text):
        return {"building_type": "villa", "floors": 2}


class _ImageBridge:
    def process_upload(self, project_id, image_path, preview=None):
        return {
            "asset": {
                "path": image_path,
                "filename": os.path.basename(str(image_path)),
                "original_source_path": image_path,
                "original_dimensions": [768, 704],
                "working_dimensions": [768, 704],
            }
        }


class _ImageResponse:
    def adapt(self, final_render):
        return {
            "type": "image",
            "status": final_render.get("status"),
            "attachments": [{"kind": "image", "path": REAL_KONTEXT_OUTPUT}],
            "design_observation": final_render.get("design_observation"),
            "design_fidelity": final_render.get("design_fidelity"),
        }


class _Writeback:
    def store(self, *args, **kwargs):
        return None


def test_recorded_kontext_result_reaches_vision_fidelity_and_response(
    monkeypatch, isolated_project, tmp_path
):
    assert os.path.isfile(REAL_KONTEXT_OUTPUT)
    source = _registered_source(tmp_path, isolated_project)
    runtime = _RecordedRuntime()
    state = ConversationState()
    handler = ImageHandler(
        render_runtime=runtime,
        result_bridge=_Bridge(),
        semantic_intent=_Intent(),
        image_bridge=_ImageBridge(),
        image_response=_ImageResponse(),
        writeback=_Writeback(),
        state=state,
        prompt_builder=None,
    )

    observed_paths = []

    monkeypatch.setattr(
        "core.runtime.gpu_handoff_v1.release_comfyui_for_vision",
        lambda *a, **k: {"status": "released", "reason": "cpu_test"},
    )

    def fake_observe(path, provider=None):
        observed_paths.append(os.path.normcase(os.path.abspath(path)))
        return {
            "available": True,
            "reason": None,
            "contract": {
                "visible_floor_count": 2,
                "building_type": "villa",
                "floor_observation": {
                    "count": 2,
                    "count_type": "TOTAL",
                    "storey_divisions_legible": True,
                    "evidence": (
                        "two principal storeys; central gable opening belongs "
                        "to the pitched roof"
                    ),
                },
                "roof_features": ["central gable window"],
            },
            "provider": "ollama_facade",
            "model": "qwen3.8:27b",
        }

    monkeypatch.setattr(fidelity, "observe_output", fake_observe)

    response = handler.handle_image_edit(
        "make this same two-storey villa night and preserve its architecture",
        {"path": source["path"]},
        compiled_render_prompt=(
            "DELTA: true night lighting. PRESERVE: existing architecture."
        ),
        parent_image_id=source["image_id"],
        kontext_edit=True,
        previous_architectural_intent=_intent(),
        verify_render=True,
    )

    assert runtime.calls[0]["payload"]["mode"] == "img2img"
    assert runtime.calls[0]["kwargs"]["kontext_edit"] is True
    assert observed_paths == [os.path.normcase(os.path.abspath(REAL_KONTEXT_OUTPUT))]

    structured = response["result"]
    observation = structured["design_observation"]
    design_fidelity = structured["design_fidelity"]
    assert observation["available"] is True
    assert os.path.normcase(os.path.abspath(observation["image"])) == (
        os.path.normcase(os.path.abspath(REAL_KONTEXT_OUTPUT))
    )
    assert observation["provider"] == "ollama_facade"
    assert design_fidelity["requested"]["floors"] == 2
    assert design_fidelity["observed"]["floors"] == 2
    assert design_fidelity["instruction_is_not_evidence_of_result"] is True
    assert design_fidelity["floor_status"] == fidelity.FLOOR_VERIFIED
    assert "geometry_preserved" not in structured
    assert "source_geometry_preserved" not in structured


def test_missing_kontext_observation_never_passes(
    monkeypatch, isolated_project, tmp_path
):
    source = _registered_source(tmp_path, isolated_project)
    runtime = _RecordedRuntime()
    handler = ImageHandler(
        render_runtime=runtime,
        result_bridge=_Bridge(),
        semantic_intent=_Intent(),
        image_bridge=_ImageBridge(),
        image_response=_ImageResponse(),
        writeback=_Writeback(),
        state=ConversationState(),
        prompt_builder=None,
    )
    monkeypatch.setattr(
        image_handler_module,
        "_observe_rendered_output",
        lambda result: {
            "available": False,
            "reason": "produced_image_missing",
            "contract": None,
            "image": None,
            "provider": None,
            "model": None,
        },
    )

    response = handler.handle_image_edit(
        "make this same two-storey villa night",
        {"path": source["path"]},
        parent_image_id=source["image_id"],
        kontext_edit=True,
        previous_architectural_intent=_intent(),
        verify_render=True,
    )

    design_fidelity = response["result"]["design_fidelity"]
    assert design_fidelity["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert design_fidelity["design_accepted"] is False
    assert "PASS" not in str(design_fidelity)


def test_flask_api_global_kontext_edit_returns_observation_and_fidelity(
    monkeypatch, isolated_project
):
    """Genuine app route; only the external executor and Vision are recorded."""
    import core.render.render_runtime as rr_module
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import app as application

    assert os.path.isfile(REAL_KONTEXT_SOURCE)
    assert os.path.isfile(REAL_KONTEXT_OUTPUT)

    monkeypatch.setattr(
        application.chat,
        "_default_state",
        session_registry.current_state(),
    )

    # Keep every semantic seam local/deterministic. The test is about the app
    # transport and edit-output verification contract, not another model call.
    deterministic_intent = _Intent()
    monkeypatch.setattr(application.chat, "semantic_intent", deterministic_intent)
    monkeypatch.setattr(
        application.chat.image_handler, "semantic_intent", deterministic_intent
    )
    monkeypatch.setattr(
        application.chat.render_runtime, "semantic_intent", deterministic_intent
    )

    observed = []

    def fake_observe(path, provider=None):
        observed.append(os.path.normcase(os.path.abspath(path)))
        return {
            "available": True,
            "reason": None,
            "contract": {
                "visible_floor_count": 2,
                "building_type": "villa",
                "floor_observation": {
                    "count": 2,
                    "count_type": "TOTAL",
                    "storey_divisions_legible": True,
                    "evidence": "two principal storeys; gable opening excluded",
                },
                "roof_features": ["central gable window"],
                "lighting": {"time_of_day": "night"},
            },
            "provider": "ollama_facade",
            "model": "qwen3.8:27b",
        }

    monkeypatch.setattr(fidelity, "observe_output", fake_observe)
    monkeypatch.setattr(
        gpu_handoff,
        "gpu_render_lease",
        lambda *a, **k: type(
            "Guard",
            (),
            {"acquire": lambda self: True, "release": lambda self: True},
        )(),
    )
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda *a, **k: {
            "status": "not_running",
            "reason": "cpu_test",
            "ownership": None,
            "unloaded": [],
            "skipped_in_use": [],
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "require_render_vram",
        lambda *a, **k: {
            "ok": True,
            "reason": "cpu_test",
            "free_mib": 16000,
            "min_free_mib": 11264,
            "measurement_source": "cpu_test",
        },
    )
    monkeypatch.setattr(
        gpu_handoff,
        "release_comfyui_for_vision",
        lambda *a, **k: {"status": "released", "reason": "cpu_test"},
    )
    monkeypatch.setattr(
        rr_module,
        "ComfyProgressListener",
        type(
            "Listener",
            (),
            {
                "__init__": lambda self, *a, **k: None,
                "start": lambda self: True,
                "stop": lambda self: True,
                "bind_prompt_id": lambda self, prompt_id: None,
                "stats": lambda self: {},
            },
        ),
    )

    class Executor:
        def __init__(self):
            self.comfy = type("Comfy", (), {"endpoint": "stub"})()
            self.calls = []

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            self.calls.append((workflow, engine))
            if on_submitted:
                on_submitted("recorded-kontext-api-v3")
            return {
                "status": "completed",
                "prompt_id": "recorded-kontext-api-v3",
                "images": [{
                    "filename": os.path.basename(REAL_KONTEXT_OUTPUT),
                    "subfolder": "",
                    "type": "output",
                }],
            }

    executor = Executor()
    monkeypatch.setattr(application.chat.render_runtime, "executor", executor)
    monkeypatch.setattr(
        application.chat.image_handler, "result_bridge", _Bridge()
    )

    request_text = (
        "Make this same villa night and keep its architecture fixed."
    )
    with open(REAL_KONTEXT_SOURCE, "rb") as source_handle:
        source_bytes = source_handle.read()
    with contextlib.redirect_stdout(io.StringIO()):
        http_response = application.app.test_client().post(
            "/api/chat",
            data={
                "text": request_text,
                "mode": "image_to_image",
                "verify_render": "true",
                "session_id": isolated_project["session_id"],
                "image": (
                    io.BytesIO(source_bytes),
                    os.path.basename(REAL_KONTEXT_SOURCE),
                ),
            },
            content_type="multipart/form-data",
        )

    assert http_response.status_code == 200
    payload = http_response.get_json() or {}
    api_response = payload.get("response") or {}
    structured = api_response.get("result_structured") or {}

    assert executor.calls, (
        "the established app route did not reach execution: %r" % (payload,)
    )
    assert application.chat.render_runtime.last_render_metadata[
        "workflow_name"
    ] == "flux_kontext_edit.json"
    assert observed == [os.path.normcase(os.path.abspath(REAL_KONTEXT_OUTPUT))]
    assert structured["design_observation"]["available"] is True
    # This uploaded legacy source has no trusted architectural-intent snapshot.
    # The observed two levels must not be backfilled into the request.
    assert structured["design_fidelity"]["requested"]["floors"] is None
    assert structured["design_fidelity"]["observed"]["floors"] == 2
    assert api_response["parent_image_id"]
    assert (api_response.get("vision") or {}).get("image_id") == (
        api_response["parent_image_id"]
    )
    assert "geometry_preserved" not in structured
    assert "source_geometry_preserved" not in structured
