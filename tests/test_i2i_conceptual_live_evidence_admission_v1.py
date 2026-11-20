# -*- coding: utf-8 -*-
"""Replay the blocked I2I turn with its persisted live evidence.

CPU only: no Chat POST, provider call, ComfyUI POST, or GPU execution.
"""

import hashlib
import json
import os
from copy import deepcopy
from types import SimpleNamespace

import pytest

import core.chat.chat_architect as ca
from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.chat.handlers.image_handler import ImageHandler
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.render.image_asset_bridge import ImageAssetBridge
from core.render.render_runtime import RenderRuntime
from core.vision.image_intent_v1 import detect_unsupported_geometry_edit


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ID = "project_7b6016d9"
PHOTO = os.path.join(
    ROOT, "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)
ASSETS = os.path.join(ROOT, "data", "projects", PROJECT_ID, "assets.json")
CHAT = os.path.join(
    ROOT, "data", "projects", PROJECT_ID, "conversations", "chat.json"
)
EXPECTED_SHA = "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"


def _load_live_evidence():
    with open(ASSETS, encoding="utf-8") as fh:
        records = json.load(fh)["registry_records"]
    record = next(item for item in records if item["image_id"] == "img_8a223f0d7a38")
    return deepcopy(record["analysis"])


def _request():
    with open(CHAT, encoding="utf-8") as fh:
        return json.load(fh)["messages"][10]["text"]


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path=PHOTO):
    return {
        "path": path,
        "image_id": "attachment_a250b10126e4",
        "session_id": PROJECT_ID,
        "project_id": PROJECT_ID,
        "source_type": "uploaded",
    }


def _admit(monkeypatch, text=None, consent=True, path=PHOTO):
    text = text or _request()
    monkeypatch.setattr(
        ca.session_registry, "current",
        lambda: {"session_id": PROJECT_ID, "project_id": PROJECT_ID},
        raising=False,
    )
    monkeypatch.setattr(
        ca.image_registry, "get",
        lambda session_id, image_id: {"path": path, "source_type": "uploaded"},
        raising=False,
    )
    context = {"conceptual_edit": True} if consent else {}
    blocked = ca._r4_architectural_edit_admission(
        text,
        _record(path),
        compile_edit_delta(text, image_edit=True),
        context,
        None,
        _load_live_evidence(),
    )
    return blocked, context


class _State:
    def __init__(self):
        self.value = {}

    def get(self):
        return deepcopy(self.value)

    def update(self, values):
        self.value.update(values)


class _NoExecutionRuntime:
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


def _handler():
    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {
            "asset": {"path": PHOTO, "filename": "architectos_preview_replay.png"}
        }
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _NoExecutionRuntime()
    handler.result_bridge = SimpleNamespace(
        resolve=lambda result: {"status": result["status"], "engine": "recorded"}
    )
    handler.image_response = SimpleNamespace(adapt=lambda result: deepcopy(result))
    return handler


@pytest.fixture(scope="module", autouse=True)
def _fixtures_exist():
    if not os.path.isfile(PHOTO) or not os.path.isfile(ASSETS):
        pytest.skip("persisted live I2I evidence is unavailable")


def test_a_real_live_evidence_and_consent_reach_existing_render_handoff(monkeypatch):
    text = _request()
    evidence = _load_live_evidence()
    before = deepcopy(evidence)
    blocked, context = _admit(monkeypatch, text=text, consent=True)
    assert blocked is None

    admission = context["r4_admission"]
    assert admission["selected_workflow"] == "flux_img2img.json"
    assert admission["preservation_status"] == "conceptual_unverified"
    assert admission["preservation_contract"] is None

    # Admission used a realistic bound session; the lightweight handler below
    # intentionally uses its injected state fallback.
    monkeypatch.setattr(ca.session_registry, "current", lambda: None, raising=False)

    handler = _handler()
    result = handler.handle_image_edit(
        text=text,
        image={"path": PHOTO},
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=evidence,
        render_profile="PREVIEW",
        r4_admission=admission,
    )

    assert result["status"] == "recorded_no_execution"
    assert len(handler.render_runtime.payloads) == 1
    decision = handler.render_runtime.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["image_type"] == "unknown"
    assert decision["editable_elements"] == []
    assert decision["conceptual_global_edit"]["preservation_status"] == "conceptual_unverified"
    assert evidence == before


def test_b_without_consent_the_existing_r4_refusal_remains(monkeypatch):
    blocked, context = _admit(monkeypatch, consent=False)
    assert blocked["reason"] == "preservation_capability_unverified"
    assert "r4_admission" not in context


def test_c_d_live_provenance_and_unknown_type_are_not_promoted(monkeypatch):
    evidence = _load_live_evidence()
    classes_before = [
        item.get("evidence_class")
        for item in evidence["element_evidence"]["elements"]
    ]
    blocked, context = _admit(monkeypatch)
    assert blocked is None
    assert evidence["image_type"] == "unknown"
    assert "OBSERVED" not in classes_before
    assert all(value in ("MODEL_REPORTED", "UNVERIFIED") for value in classes_before)
    assert context["r4_admission"]["architectural_evidence"] == "observation_only"


@pytest.mark.parametrize(
    "text",
    (
        "Remove the balcony railing.",
        "Move a window two metres left.",
        "Add two floors.",
    ),
)
def test_e_structural_or_spatial_operations_remain_blocked(text):
    assert detect_unsupported_geometry_edit(text)["unsupported"] is True


def test_f_localized_material_patch_is_not_a_conceptual_global_facade_edit(monkeypatch):
    text = "Apply travertine only to this facade area; keep every other area unchanged."
    assert compile_edit_delta(text, image_edit=True)["edit_class"] == "material_change"
    blocked, context = _admit(monkeypatch, text=text, consent=True)
    assert isinstance(blocked, dict)
    assert blocked["status"] == "blocked"
    assert not (context.get("r4_admission") or {}).get("admitted")


def test_g_missing_image_is_blocked_before_render(monkeypatch, tmp_path):
    missing = str(tmp_path / "missing.jpg")
    blocked, context = _admit(monkeypatch, consent=True, path=missing)
    assert blocked["reason"] in (
        "source_image_authority_mismatch", "source_image_integrity_failed"
    )
    assert not (context.get("r4_admission") or {}).get("admitted")


def test_h_original_source_hash_is_unchanged():
    assert _sha(PHOTO) == EXPECTED_SHA
    assert _load_live_evidence()["element_evidence"]["source_image"]["sha256"] == EXPECTED_SHA


def test_i_j_k_l_preview_and_effective_graph_use_only_the_real_source(tmp_path):
    bridge = ImageAssetBridge(comfy_input=str(tmp_path))
    staged = bridge.register("replay", PHOTO, preview="PREVIEW")
    assert staged["status"] == "ready"
    assert staged["filename"].startswith("architectos_preview_")
    assert staged["filename"].endswith(".png")
    assert staged["working_dimensions"] == [336, 448]

    class _Capture:
        def __init__(self):
            self.workflows = []

        def execute(self, workflow, engine, **kwargs):
            self.workflows.append(deepcopy(workflow))
            return {"status": "dry_run_capture", "prompt_id": None}

    runtime = RenderRuntime()
    capture = _Capture()
    runtime.executor = capture
    runtime.result_bridge = SimpleNamespace(
        resolve=lambda context: {"status": "dry_run_capture", "image_asset": None}
    )
    runtime.render(
        "cpu-replay",
        {
            "prompt": _request(),
            "original_prompt": _request(),
            "mode": "img2img",
            "seed": 1,
            "render_profile": "PREVIEW",
        },
        "flux",
        image_asset=staged,
    )
    graph = capture.workflows[0]
    assert graph["300"]["inputs"]["image"] == staged["filename"]
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["210"]["inputs"]["latent_image"] == ["301", 0]
    assert graph["210"]["inputs"]["steps"] == 8
    assert graph["210"]["inputs"]["denoise"] == 0.3
    classes = [node["class_type"] for node in graph.values()]
    assert "LoadImageMask" not in classes
    assert "EmptyLatentImage" not in classes
    assert "render_005" not in graph["300"]["inputs"]["image"]
    assert graph["300"]["inputs"]["image"] != "input.png"


def test_m_n_nonconceptual_decision_and_evidence_contract_remain_unchanged():
    from core.prompt_intelligence.geometry_authority_handoff_v1 import resolve_design_decision

    evidence = _load_live_evidence()
    decision = resolve_design_decision(
        user_text=_request(),
        edit_delta=compile_edit_delta(_request(), image_edit=True),
        image_understanding=evidence,
    )
    assert decision["execution_status"] == "INSUFFICIENT_IMAGE_EVIDENCE"
    assert decision["editable_elements"] == []
    assert "conceptual_global_edit" not in decision
    assert evidence["image_type"] == "unknown"


def test_o_test_module_has_no_live_transport(monkeypatch):
    """The replay consumes persisted JSON and local files only."""
    import requests

    monkeypatch.setattr(
        requests.sessions.Session, "request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network forbidden")),
    )
    assert _load_live_evidence()["provider"] == "ollama"
    assert _sha(PHOTO) == EXPECTED_SHA
