# -*- coding: utf-8 -*-
"""I2I_CONCEPTUAL_ADMISSION_V1 — CPU-only acceptance.

Drives the REAL R4 admission owner (`_r4_admission_verdict`), the real edit-delta
compiler, the real workflow selector and the real RenderRuntime with a
non-executing executor.

No GPU, no ComfyUI POST, no model inference, no image generation.
"""

import json
import os
from copy import deepcopy

import pytest

from core.chat.chat_architect import (
    _R4_CONCEPTUAL_PRESERVATION_STATUS,
    _R4_CONCEPTUAL_REASON,
    _R4_CONCEPTUAL_WORKFLOW,
    _r4_admission_verdict,
    _r4_conceptual_consent,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    is_classified,
)
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The real user-uploaded photograph. Read-only; never modified.
PHOTO = os.path.join(
    ROOT, "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)

EDIT = (
    "Edit the attached building photo.\r\n\r\nPreserve exactly:\r\n"
    "- building massing\r\n- floor count\r\n- structural frame\r\n"
    "- openings and window positions\r\n- camera angle and perspective\r\n"
    "- site layout and composition\r\n\r\n"
    "Do not add floors, remove floors, or change the geometry.\r\n\r\n"
    "Only change the exterior facade treatment:\r\n"
    "convert the unfinished facade into a clean finished facade with light "
    "cream travertine-style cladding and a realistic completed architectural "
    "appearance.\r\n\r\nKeep the building as the same building.\r\n"
    "Photorealistic result."
)

GEOMETRY_EDIT = "Remove the balcony railing and move the entrance two metres left."


def _source():
    return {
        "valid": True,
        "session_id": "project_7b6016d9",
        "project_id": "project_7b6016d9",
        "image_id": "attachment_a250b10126e4",
        "path": PHOTO,
        "source_type": "uploaded",
    }


def _verdict(text=EDIT, context=None, delta=None, spatial=False):
    delta = delta if delta is not None else compile_edit_delta(text, image_edit=True)
    return _r4_admission_verdict(
        text=text,
        source=_source(),
        edit_delta=delta,
        context=context or {},
        image_understanding={},
        edit_class=delta.get("edit_class"),
        localization_required=False,
        verified_localization=False,
        spatial_change=spatial,
    )


class _CaptureExecutor:
    def __init__(self):
        self.workflows = []

    def execute(self, workflow, engine, **kwargs):
        self.workflows.append(deepcopy(workflow))
        return {"status": "dry_run_capture", "engine": engine, "prompt_id": None}


class _ResultBridge:
    def resolve(self, context):
        return {"status": "dry_run_capture", "image_asset": None}


def _capture(image_asset):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()
    runtime.render(
        "i2i-conceptual-v1",
        {
            "prompt": EDIT,
            "original_prompt": EDIT,
            "mode": "img2img",
            "seed": 1793714778,
        },
        "flux",
        image_asset=image_asset,
    )
    assert executor.workflows
    return executor.workflows[0]


@pytest.fixture(scope="module", autouse=True)
def _require_photo():
    if not os.path.isfile(PHOTO):
        pytest.skip("the user-uploaded photograph is not present")


# ---------------------------------------------------------------- 1

def test_1_exact_preservation_without_consent_is_still_blocked():
    """The default policy is unchanged: no consent, no admission."""

    verdict = _verdict(context={})

    assert verdict["admitted"] is False
    assert verdict["reason"] == "preservation_capability_unverified"
    assert verdict["workflow"] is None
    assert verdict["contract"] is None


# ---------------------------------------------------------------- 2

def test_2_consented_conceptual_edit_is_admitted_on_the_i2i_graph():
    verdict = _verdict(context={"conceptual_edit": True})

    assert verdict["admitted"] is True
    assert verdict["reason"] == _R4_CONCEPTUAL_REASON
    assert verdict["workflow"] == "flux_img2img.json"
    assert _R4_CONCEPTUAL_WORKFLOW == "flux_img2img.json"


# ---------------------------------------------------------------- 3

def test_3_geometry_mutation_is_never_admitted_as_conceptual():
    """A spatial mutation stays closed even WITH consent."""

    verdict = _verdict(context={"conceptual_edit": True}, spatial=True)

    assert verdict["admitted"] is False
    assert verdict["reason"] == "preservation_capability_unverified"


def test_3b_genuine_geometry_request_is_blocked_upstream():
    """The unsupported-operation gate still refuses real geometry edits."""

    from core.vision.image_intent_v1 import detect_unsupported_geometry_edit

    guard = detect_unsupported_geometry_edit(GEOMETRY_EDIT)

    assert guard["unsupported"] is True


# ---------------------------------------------------------------- 4

def test_4_unreadable_source_fails_safely():
    bad = _source()
    bad["path"] = os.path.join(ROOT, "uploads", "chat_media", "does_not_exist.jpg")

    verdict = _r4_admission_verdict(
        text=EDIT,
        source=bad,
        edit_delta=compile_edit_delta(EDIT, image_edit=True),
        context={"conceptual_edit": True},
        image_understanding={},
        edit_class="material_change",
        localization_required=False,
        verified_localization=False,
        spatial_change=False,
    )

    assert verdict["admitted"] is False
    assert verdict["reason"] == "source_image_integrity_failed"


# ---------------------------------------------------------------- consent contract

def test_consent_must_be_an_explicit_boolean():
    """A string, a number or a truthy object is never consent."""

    for value in ("1", "true", 1, {"a": 1}, [1], None):
        assert _r4_conceptual_consent({"conceptual_edit": value}) is False

    assert _r4_conceptual_consent({"conceptual_edit": True}) is True
    assert _r4_conceptual_consent({}) is False
    assert _r4_conceptual_consent(None) is False


def test_wording_alone_never_enables_consent():
    """"modern"/"travertine"/"facade"/"Preserve exactly" cannot opt in."""

    delta = compile_edit_delta(EDIT, image_edit=True)

    assert is_classified(delta) is True
    assert "travertine" in json.dumps(delta, ensure_ascii=False).lower()
    # …and yet, without the request field, the verdict is still closed.
    assert _verdict(context={}, delta=delta)["admitted"] is False


def test_unclassified_delta_is_not_admitted_even_with_consent():
    verdict = _verdict(
        text="Change it.",
        delta={"contract": "ImageEditDeltaV1", "edit_class": None},
        context={"conceptual_edit": True},
    )

    assert verdict["admitted"] is False


# ---------------------------------------------------------------- 8 / 9

def test_no_preservation_contract_is_claimed():
    """A conceptual admission asserts NO preservation capability."""

    verdict = _verdict(context={"conceptual_edit": True})

    assert verdict["contract"] is None
    assert verdict["preservation_status"] == _R4_CONCEPTUAL_PRESERVATION_STATUS
    assert _R4_CONCEPTUAL_PRESERVATION_STATUS == "conceptual_unverified"


# ---------------------------------------------------------------- 5 / 6 / 7

def test_5_the_real_photo_is_bound_into_node_300():
    workflow = _capture({"filename": "architectos_test01.jpg", "path": PHOTO})

    assert workflow["300"]["inputs"]["image"] == "architectos_test01.jpg"
    assert workflow["301"]["inputs"]["pixels"] == ["300", 0]
    assert workflow["210"]["inputs"]["latent_image"] == ["301", 0]


def test_6_no_unrelated_render_or_placeholder_is_substituted():
    workflow = _capture({"filename": "architectos_test02.jpg", "path": PHOTO})
    types = [n.get("class_type") for n in workflow.values()]
    bound = workflow["300"]["inputs"]["image"]

    assert bound != "input.png"
    assert "render_005" not in bound
    assert "LoadImageMask" not in types
    assert "EmptyLatentImage" not in types


def test_7_preservation_instructions_remain_best_effort_in_node_206():
    workflow = _capture({"filename": "architectos_test03.jpg", "path": PHOTO})
    positive = workflow["206"]["inputs"]["text"].lower()

    assert "geometry preservation" in positive
    assert "preserve exactly" in positive
    assert "floor count" in positive


# ---------------------------------------------------------------- 10

def test_10_text_to_image_and_normal_i2i_are_unchanged():
    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "text_to_image"}) == "flux.json"
    assert selector.select(
        {"engine": "flux", "image": "x.jpg", "kontext_edit": False}
    ) == "flux_img2img.json"
    assert selector.select(
        {"engine": "flux", "image": "x.jpg", "kontext_edit": True}
    ) == "flux_kontext_edit.json"


# ---------------------------------------------------------------- 11 / 12

def test_11_12_one_capture_no_execution_no_retry():
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    runtime.result_bridge = _ResultBridge()

    runtime.render(
        "i2i-no-exec-v1",
        {"prompt": EDIT, "mode": "img2img", "seed": 1},
        "flux",
        image_asset={"filename": "architectos_test04.jpg", "path": PHOTO},
    )

    # Exactly one graph captured: no hidden second generation.
    assert len(executor.workflows) == 1


# ---------------------------------------------------------------- route-facing wrapper

def test_route_facing_admission_admits_only_with_consent(monkeypatch):
    """Exercise `_r4_architectural_edit_admission` — the function the Chat
    route actually calls — with the session/image registries stubbed to a
    realistic single-project session.
    """

    import core.chat.chat_architect as ca

    monkeypatch.setattr(
        ca.session_registry, "current",
        lambda: {"session_id": "project_7b6016d9", "project_id": "project_7b6016d9"},
        raising=False,
    )
    monkeypatch.setattr(
        ca.image_registry, "get",
        lambda session_id, image_id: {"path": PHOTO, "source_type": "uploaded"},
        raising=False,
    )

    record = {
        "path": PHOTO,
        "image_id": "attachment_a250b10126e4",
        "session_id": "project_7b6016d9",
        "project_id": "project_7b6016d9",
    }

    delta = compile_edit_delta(EDIT, image_edit=True)

    # 1. No consent -> the pre-existing refusal stands.
    plain = {}
    blocked = ca._r4_architectural_edit_admission(
        EDIT, record, delta, plain, None, {}
    )
    assert isinstance(blocked, dict)
    assert blocked.get("reason") == "preservation_capability_unverified"

    # 2. Consent -> admitted on the existing img2img graph.
    consented = {"conceptual_edit": True}
    admitted = ca._r4_architectural_edit_admission(
        EDIT, record, delta, consented, None, {}
    )

    assert admitted is None

    admission = consented.get("r4_admission") or {}

    assert admission.get("admitted") is True
    assert admission.get("selected_workflow") == "flux_img2img.json"
    assert admission.get("preservation_status") == "conceptual_unverified"
    # Nothing about preservation is asserted.
    assert admission.get("preservation_contract") is None
    assert consented.get("r4_preservation_contract") is None

    notice = (admission.get("conceptual_edit") or {}).get("notice") or ""
    assert "best-effort" in notice
    assert "conceptual" in notice
