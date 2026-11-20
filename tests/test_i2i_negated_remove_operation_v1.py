"""I2I_NEGATED_REMOVE_FIX_V1 — focused regression.

The operation classifier used a whole-text substring scan, so the prohibition
"Do not add floors, remove floors, or change the geometry" set
`operation = "remove"`, overrode the request's own `material_change`
classification, and pushed the design decision to NEEDS_SPATIAL_TARGETING.

No GPU, no ComfyUI POST, no model inference.
"""

import hashlib
import json
import os
from copy import deepcopy

import pytest

from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    _affirmative_remove_clause,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.vision.image_intent_v1 import detect_unsupported_geometry_edit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHAT = os.path.join(ROOT, "data", "projects", "project_7b6016d9",
                    "conversations", "chat.json")

PHOTO = os.path.join(
    ROOT, "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)

EVIDENCE = {
    "image_type": "architectural_render_or_photo",
    "element_evidence": {"elements": [
        {"element": "facade wall", "kind": ["wall"],
         "evidence_class": "OBSERVED"},
        {"element": "balcony railing", "kind": ["railing"],
         "evidence_class": "OBSERVED"},
        {"element": "window", "kind": ["opening"],
         "evidence_class": "OBSERVED"},
    ]},
}

REAL_REQUEST = (
    "Do not add floors, remove floors, or change the geometry. "
    "Only change the exterior facade treatment to light cream travertine."
)


def _decision(text, evidence=EVIDENCE):
    return resolve_design_decision(
        user_text=text,
        edit_delta=compile_edit_delta(text, image_edit=True),
        image_understanding=evidence,
    )


def _persisted_request():
    with open(CHAT, encoding="utf-8") as fh:
        return json.load(fh)["messages"][10]["text"]


# ------------------------------------------------------------------ A / E / F / G

def test_a_prohibited_list_is_not_a_removal():
    decision = _decision(REAL_REQUEST)

    assert _affirmative_remove_clause(REAL_REQUEST) is None
    assert decision["requested_operation"]["operation"] != "remove"
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["conflicts"] == []


def test_a_prohibited_list_keeps_the_material_classification():
    decision = _decision(REAL_REQUEST)

    # The classifier's own vocabulary for a material change.
    assert decision["requested_operation"]["operation"] == "replace_finish"
    assert decision["requested_operation"]["edit_class"] == "material_change"


def test_e_prohibition_only_is_not_a_removal():
    decision = _decision("Do not remove any floors.")

    assert _affirmative_remove_clause("Do not remove any floors.") is None
    assert decision["requested_operation"]["operation"] != "remove"


def test_f_prohibition_does_not_suppress_a_later_material_edit():
    text = "Do not remove any floors. Change the facade to cream travertine."
    decision = _decision(text)

    assert decision["requested_operation"]["operation"] != "remove"
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"


def test_g_ordinary_words_are_not_matched():
    assert _affirmative_remove_clause("Improve the facade.") is None
    assert _decision("Improve the facade.")["requested_operation"]["operation"] == "change"


# ------------------------------------------------------------------ B / C / I

def test_b_genuine_removal_still_removes():
    decision = _decision("Remove the balcony railing.")

    assert decision["requested_operation"]["operation"] == "remove"
    assert decision["execution_status"] == "NEEDS_SPATIAL_TARGETING"


def test_b_localized_geometry_restriction_still_applies():
    guard = detect_unsupported_geometry_edit("Remove the balcony railing.")

    assert guard["unsupported"] is True
    assert guard["reason"] == "localized_geometry_edit_not_supported"


def test_c_affirmative_removal_survives_a_previous_sentence_prohibition():
    text = "Do not touch the roof. Remove the balcony railing."

    assert _affirmative_remove_clause(text) == "Remove the balcony railing"
    assert _decision(text)["requested_operation"]["operation"] == "remove"


def test_i_persian_affirmative_removal_still_removes():
    text = "این پنجره را حذف کن."

    assert _decision(text)["requested_operation"]["operation"] == "remove"
    assert detect_unsupported_geometry_edit(text)["unsupported"] is True


# ------------------------------------------------------------------ D / H

def test_d_floor_addition_is_still_blocked():
    guard = detect_unsupported_geometry_edit("Add two floors.")

    assert guard["unsupported"] is True
    assert guard["reason"] == "floor_count_restructuring_not_supported"


def test_h_persian_prohibition_is_not_a_removal():
    text = "طبقات را حذف نکن، فقط متریال نما را به تراورتن کرم تغییر بده."
    decision = _decision(text)

    assert _affirmative_remove_clause(text) is None
    assert decision["requested_operation"]["operation"] != "remove"


# ------------------------------------------------------------------ J

def test_j_route_facing_real_request_is_admitted(monkeypatch):
    import core.chat.chat_architect as ca

    text = _persisted_request()
    delta = compile_edit_delta(text, image_edit=True)

    # 1. The design decision no longer demands spatial targeting.
    decision = _decision(text)
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"

    # 2. The R4 admission still admits the conceptual edit.
    monkeypatch.setattr(
        ca.session_registry, "current",
        lambda: {"session_id": "project_7b6016d9",
                 "project_id": "project_7b6016d9"},
        raising=False,
    )
    monkeypatch.setattr(
        ca.image_registry, "get",
        lambda session_id, image_id: {"path": PHOTO, "source_type": "uploaded"},
        raising=False,
    )

    record = {"path": PHOTO, "image_id": "attachment_a250b10126e4",
              "session_id": "project_7b6016d9", "project_id": "project_7b6016d9"}

    consented = {"conceptual_edit": True}
    blocked = ca._r4_architectural_edit_admission(
        text, record, delta, consented, None, {})

    admission = consented.get("r4_admission") or {}

    assert blocked is None
    assert admission.get("selected_workflow") == "flux_img2img.json"
    assert admission.get("preservation_status") == "conceptual_unverified"


# ------------------------------------------------------------------ L

def test_l_no_consent_keeps_the_r4_restriction(monkeypatch):
    import core.chat.chat_architect as ca

    text = _persisted_request()
    delta = compile_edit_delta(text, image_edit=True)

    monkeypatch.setattr(
        ca.session_registry, "current",
        lambda: {"session_id": "project_7b6016d9",
                 "project_id": "project_7b6016d9"},
        raising=False,
    )
    monkeypatch.setattr(
        ca.image_registry, "get",
        lambda session_id, image_id: {"path": PHOTO, "source_type": "uploaded"},
        raising=False,
    )

    record = {"path": PHOTO, "image_id": "attachment_a250b10126e4",
              "session_id": "project_7b6016d9", "project_id": "project_7b6016d9"}

    plain = {}
    blocked = ca._r4_architectural_edit_admission(
        text, record, delta, plain, None, {})

    assert isinstance(blocked, dict)
    assert blocked.get("reason") == "preservation_capability_unverified"


# ------------------------------------------------------------------ K

pytestmark_photo = pytest.mark.skipif(
    not os.path.isfile(PHOTO), reason="uploaded JPEG fixture not present")


@pytest.mark.skipif(not os.path.isfile(PHOTO),
                    reason="uploaded JPEG fixture not present")
def test_k_preview_staging_still_binds_a_336x448_png(tmp_path):
    from PIL import Image

    from core.render.image_asset_bridge import ImageAssetBridge
    from core.render.render_runtime import RenderRuntime

    with open(PHOTO, "rb") as fh:
        before = hashlib.sha256(fh.read()).hexdigest()

    staged = ImageAssetBridge(comfy_input=str(tmp_path)).register(
        "project_7b6016d9", PHOTO, preview="PREVIEW")

    assert staged["status"] == "ready"
    assert staged["filename"].endswith(".png")
    assert staged["working_dimensions"] == [336, 448]
    assert staged["original_dimensions"] == [1792, 2400]

    with Image.open(os.path.join(str(tmp_path), staged["filename"])) as image:
        assert image.size == (336, 448)
        assert image.format == "PNG"

    class Capture:
        def __init__(self):
            self.workflows = []

        def execute(self, workflow, engine, **kwargs):
            self.workflows.append(deepcopy(workflow))
            return {"status": "dry_run_capture", "prompt_id": None}

    class Bridge:
        def resolve(self, context):
            return {"status": "dry_run_capture", "image_asset": None}

    runtime = RenderRuntime()
    capture = Capture()
    runtime.executor = capture
    runtime.result_bridge = Bridge()

    text = _persisted_request()

    runtime.render(
        "negated-remove-test",
        {"prompt": text, "original_prompt": text, "mode": "img2img",
         "seed": 1793714778, "render_profile": "PREVIEW"},
        "flux",
        image_asset={"filename": staged["filename"],
                     "path": staged["path"],
                     "type": "source_image"},
    )

    workflow = capture.workflows[0]

    assert workflow["300"]["inputs"]["image"] == staged["filename"]
    assert workflow["301"]["inputs"]["pixels"] == ["300", 0]
    assert workflow["210"]["inputs"]["latent_image"] == ["301", 0]

    with open(PHOTO, "rb") as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == before
