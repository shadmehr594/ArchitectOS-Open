"""NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — CPU acceptance.

Drives the REAL Chat image-edit route with the REAL PERSISTED analysis of the
accepted source image. No model call, no Ollama, no GPU, no ComfyUI request.

The evidence used here is exactly what is stored in
`data/projects/project_7b6016d9/assets.json` for `img_967f09b9a599`. Nothing is
synthesised and `image_type` is never rewritten.
"""

import copy
import json
import os

import pytest
from PIL import Image
from types import SimpleNamespace

from core.chat.chat_architect import ChatArchitect
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.prompt_intelligence.image_edit_delta_v1 import (
    _explicit_preservation_clauses,
    compile_edit_delta,
    conflict_terms as edit_delta_conflict_terms,
    delta_prompt,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.vision.image_registry_v1 import image_registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE = os.path.join(
    ROOT, "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)

SOURCE_SHA256 = (
    "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"
)

ASSETS = os.path.join(
    ROOT, "data", "projects", "project_7b6016d9", "assets.json"
)

RECORD_ID = "img_967f09b9a599"

REQUEST = (
    "Design a restrained neoclassical facade for the EXISTING unfinished "
    "building. Use light cream travertine with subtle natural texture. "
    "Design appropriately proportioned non-structural pilasters, classical "
    "capitals, stone surrounds on existing windows, horizontal "
    "stringcourses, a formal architectural cornice, and stone balustrades on "
    "suitable existing terrace edges. Keep the existing floor count, "
    "original structural frame, main building massing, existing openings and "
    "their locations, open ground-floor structure, existing terrace "
    "positions, main roof geometry and camera perspective. Treat exposed "
    "slab soffits as plastered or painted surfaces, not travertine cladding. "
    "Do not automatically apply facade stone to the courtyard, retaining "
    "walls or neighbouring buildings. Do not invent new balconies, floors, "
    "structural columns or openings."
)

MATERIAL_REQUEST = "Change the unfinished facade material to cream travertine."


def _persisted_analysis():
    """The REAL stored analysis. Never synthesised."""

    if not os.path.isfile(ASSETS):
        pytest.skip("persisted project analysis is not present")

    with open(ASSETS, encoding="utf-8") as handle:
        payload = json.load(handle)

    for record in payload.get("registry_records") or []:

        if record.get("image_id") == RECORD_ID:

            return copy.deepcopy(record["analysis"])

    pytest.skip("persisted analysis record not found")


class _State:
    def __init__(self):
        self.data = {}

    def get(self):
        return self.data

    def update(self, values):
        self.data.update(values or {})

    def add_message(self, *args, **kwargs):
        return None


class _Recorder:
    def __init__(self):
        self.payloads = []
        self.assets = []
        self.masks = []

    def render(self, project, payload, engine, asset, **kwargs):
        self.payloads.append(copy.deepcopy(payload))
        self.assets.append(copy.deepcopy(asset))
        self.masks.append(kwargs.get("mask_asset"))
        return {"status": "recorded_no_execution"}


@pytest.fixture
def session(tmp_path):

    if not os.path.isfile(SOURCE):
        pytest.skip("accepted source photograph is not present")

    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("live-evidence-v1")

    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])

    try:

        generated = tmp_path / "architectos_img2img_edit_99999_.png"
        Image.new("RGB", (336, 448), (150, 140, 130)).save(generated)

        generated_record = image_registry.register(
            manifest["session_id"], path=str(generated),
            source_type="generated", make_active=True,
        )

        jpeg_record = image_registry.register(
            manifest["session_id"], path=SOURCE,
            source_type="uploaded", make_active=False,
        )

        yield SimpleNamespace(
            manifest=manifest,
            generated=generated_record,
            jpeg=jpeg_record,
            tmp=tmp_path,
        )

    finally:

        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


def _route(session, text, *, understanding, conceptual=True, mask=None):
    """Real route, recording transport."""

    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": SOURCE}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _t: {})
    handler.render_runtime = _Recorder()
    handler.result_bridge = SimpleNamespace(
        resolve=lambda r: {"status": r.get("status"), "engine": "recorded"}
    )
    handler.image_response = SimpleNamespace(adapt=lambda r: dict(r))

    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = handler.render_runtime
    chat.state = _State()
    chat.session_registry = session_registry
    chat.image_registry = image_registry

    context = {"project_id": session.manifest["project_id"]}
    if conceptual:
        context["conceptual_edit"] = True
    if mask:
        context["mask"] = mask
        context["kontext_edit"] = True

    result = chat._route_image_edit(
        text,
        session.jpeg,
        {"image_id": session.jpeg.get("image_id")},
        None,
        None,
        20261104,
        context,
        image_understanding=understanding,
    )

    return result, handler.render_runtime, context, chat


def _final(payload):

    delta = (payload.get("architectural_intent") or {}).get("edit_delta") or {}

    return resolve_render_prompt(
        compiled_prompt=payload.get("compiled_render_prompt"),
        builder_prompt="",
        user_text=payload.get("prompt"),
        conflict_terms=tuple(edit_delta_conflict_terms(delta)),
        architectural_instruction=payload.get("architectural_instruction"),
    )


# ==========================================================
# A / B — evidence stays truthful
# ==========================================================

def test_A_the_persisted_evidence_is_real_and_unaltered():

    understanding = _persisted_analysis()

    assert understanding.get("contract") == "ImageUnderstandingV1"
    assert understanding.get("analysis_status") == "ANALYZED_WITH_UNCERTAINTY"

    elements = (understanding.get("element_evidence") or {}).get("elements") or []

    assert len(elements) == 18

    for item in elements:

        assert item.get("evidence_class") in ("MODEL_REPORTED", "UNVERIFIED")


def test_B_image_type_stays_unknown_after_the_route(session):

    understanding = _persisted_analysis()

    before = understanding.get("image_type")

    assert before == "unknown"

    _route(session, REQUEST, understanding=understanding)

    # The route must not rewrite the persisted classification.
    assert _persisted_analysis().get("image_type") == "unknown"


def test_A_no_observed_provenance_is_invented(session):

    understanding = _persisted_analysis()

    _route(session, REQUEST, understanding=understanding)

    # The stored file is unchanged: no PIXEL_VERIFIED record was written.
    with open(ASSETS, encoding="utf-8") as handle:
        payload = json.load(handle)

    for record in payload["registry_records"]:

        if record.get("image_id") != RECORD_ID:
            continue

        elements = (
            (record.get("analysis") or {}).get("element_evidence") or {}
        ).get("elements") or []

        assert not any(
            item.get("evidence_class") == "PIXEL_VERIFIED" for item in elements
        )


# ==========================================================
# C / D / E — the decision now works on real evidence
# ==========================================================

def test_C_the_real_request_is_a_restyle(session):

    result, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    decision = recorder.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]

    assert decision["requested_operation"]["operation"] == "restyle"
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["editable_elements"] == ["facade_surface_expression"]


def test_D_global_conceptual_admission_works_with_consent(session):

    result, recorder, context, chat = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    admission = getattr(chat, "last_r4_admission", None) or {}

    assert admission.get("admitted") is True
    assert admission.get("reason") == "conceptual_appearance_edit_consented"
    assert admission.get("selected_workflow") == "flux_img2img.json"
    assert admission.get("preservation_status") == "conceptual_unverified"


def test_E_the_constraint_block_is_nonempty(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    block = recorder.payloads[0].get("architectural_instruction") or {}

    text = block.get("constraint_block") or ""

    assert len(text) > 1000

    # The semantic caveat survives: no pixel-localisation claim.
    assert "not measured regions" in text


# ==========================================================
# F / G — the ornament contract reaches the payload
# ==========================================================

def test_F_requested_ornament_reaches_the_render_payload(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    prompt = _final(recorder.payloads[0])["final_prompt"].lower()

    for element in ("pilaster", "capital", "stringcourse", "cornice",
                    "window surround", "balustrade"):
        assert element in prompt, element

    assert "restrained light cream travertine" in prompt
    assert "soffits in painted plaster" in prompt
    assert "separate site scope" in prompt
    assert "no exaggerated golden marble veining" in prompt
    assert "applied as relief" in prompt


def test_G_no_prompt_truncation(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    resolution = _final(recorder.payloads[0])

    assert resolution.get("instruction_truncated") is False


def test_G_the_authorised_addition_boundary_survives(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    prompt = _final(recorder.payloads[0])["final_prompt"].lower()

    # The sentence that would have been truncated away by the unbounded list.
    assert "no structural member or new volume is added" in prompt


# ==========================================================
# H — source precedence
# ==========================================================

def test_H_the_photograph_is_bound_over_the_active_generated_image(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    active = image_registry.active(session.manifest["session_id"])

    assert active.get("source_type") != "uploaded"

    bound = recorder.assets[0] if recorder.assets else {}

    assert os.path.abspath(str(bound.get("path") or "")) == os.path.abspath(SOURCE)


# ==========================================================
# I — localized and structural requests stay blocked
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "Design this window in neoclassical stone.",
        "Design only the left facade section in neoclassical style.",
        "Redesign the left side of the facade in neoclassical style.",
        "Change only this window's material on the facade to dark metal.",
    ],
)
def test_I_localized_requests_are_blocked(session, text):

    result, recorder, _, _ = _route(
        session, text, understanding=_persisted_analysis()
    )

    assert result.get("status") == "blocked"
    assert recorder.payloads == []


@pytest.mark.parametrize(
    "text",
    [
        "Move an existing opening to the left.",
        "Remove a floor from the building.",
        "Add a new structural column to the facade.",
    ],
)
def test_I_structural_requests_are_refused(session, text):

    result, recorder, _, _ = _route(
        session, text, understanding=_persisted_analysis()
    )

    assert result.get("status") in ("blocked", "unsupported_edit")
    assert recorder.payloads == []


def test_I_a_masked_request_is_still_refused(session):

    result, recorder, _, _ = _route(
        session,
        REQUEST,
        understanding=_persisted_analysis(),
        mask={"filename": "architectos_mask_CALLER.png"},
    )

    assert result.get("status") == "blocked"
    assert recorder.payloads == []


# ==========================================================
# J / K — ordinary behaviour is unchanged
# ==========================================================

def test_J_material_only_edit_is_unchanged(session):

    result, recorder, _, _ = _route(
        session, MATERIAL_REQUEST, understanding=_persisted_analysis()
    )

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    decision = recorder.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]

    assert decision["requested_operation"]["operation"] == "replace_finish"

    block = (recorder.payloads[0].get("architectural_instruction") or {}).get(
        "constraint_block", ""
    ).lower()

    for ornament in ("pilaster", "capital", "cornice", "balustrade"):
        assert ornament not in block, ornament


def test_J_material_delta_keeps_its_own_material_wording():

    delta = compile_edit_delta(MATERIAL_REQUEST, image_edit=True)

    prompt = delta_prompt(delta).lower()

    assert "visible veining" in prompt
    assert "restrained light cream travertine" not in prompt
    assert "do not redesign the building" in prompt


def test_K_text_to_image_is_unchanged():

    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    instruction = build_render_instruction(
        "a modern villa in a cinematic style",
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )

    text = instruction["english_instruction"]

    assert "EXISTING building" not in text
    assert "Design a new facade treatment" not in text


# ==========================================================
# Evidence guard — still refuses when there is nothing to build on
# ==========================================================

def test_the_guard_refuses_a_design_without_understanding(session):

    result, recorder, _, _ = _route(session, REQUEST, understanding=None)

    assert result.get("status") == "blocked"
    assert result.get("reason") == "architectural_evidence_required"
    assert recorder.payloads == []


def test_the_guard_refuses_a_plan(session):

    plan = _persisted_analysis()
    plan["image_type"] = "floor_plan_or_sketch"

    result, recorder, _, _ = _route(session, REQUEST, understanding=plan)

    assert result.get("status") in ("blocked", "unsupported_edit")
    assert recorder.payloads == []


def test_the_guard_refuses_evidence_with_no_elements(session):

    empty = _persisted_analysis()
    empty["element_evidence"] = {
        "contract": "ArchitecturalElementEvidenceV1", "elements": [],
    }

    result, recorder, _, _ = _route(session, REQUEST, understanding=empty)

    assert result.get("status") == "blocked"
    assert result.get("reason") == "architectural_evidence_required"
    assert recorder.payloads == []


# ==========================================================
# Prompt integrity — the negated-clause fragment
# ==========================================================

def test_the_retaining_wall_fragment_is_not_a_preservation_clause():

    prohibition = (
        "Do not automatically apply facade stone to the courtyard, retaining "
        "walls or neighbouring buildings."
    )

    assert _explicit_preservation_clauses(prohibition) == []


def test_a_real_preservation_of_a_retaining_wall_still_works():

    assert _explicit_preservation_clauses(
        "Preserve the existing structural frame and the retaining walls."
    )


def test_the_fragment_is_absent_from_the_real_prompt(session):

    _, recorder, _, _ = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    prompt = _final(recorder.payloads[0])["final_prompt"].lower()

    assert "retaining walls or neighbouring buildings" not in prompt


def test_L_no_unsupported_localization_guarantee(session):

    _, recorder, context, chat = _route(
        session, REQUEST, understanding=_persisted_analysis()
    )

    admission = getattr(chat, "last_r4_admission", None) or {}

    assert admission.get("preservation_status") == "conceptual_unverified"
    assert admission.get("preservation_contract") is None

    block = (recorder.payloads[0].get("architectural_instruction") or {}).get(
        "constraint_block", ""
    ).lower()

    for token in ("polygon", "bounding box", "coordinates", "pixel"):
        assert token not in block, token


def test_M_the_source_photograph_is_unmodified():

    import hashlib

    with open(SOURCE, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()

    assert digest == SOURCE_SHA256


def test_an_invalid_source_image_is_refused(tmp_path):

    """A registered record whose file is missing cannot authorise a design."""

    base = tmp_path / "invalid"
    base.mkdir()

    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(base / "projects")
    project_workspace.trash_root = str(base / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("live-evidence-invalid-source")

    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])

    try:

        missing = image_registry.register(
            manifest["session_id"],
            path=str(base / "missing.jpg"),
            source_type="uploaded",
            make_active=True,
        )

        session = SimpleNamespace(
            manifest=manifest, generated={}, jpeg=missing, tmp=base,
        )

        result, recorder, _, _ = _route(
            session, REQUEST, understanding=_persisted_analysis()
        )

        assert result.get("status") == "blocked"
        assert result.get("reason") == "source_image_authority_mismatch"
        assert recorder.payloads == []

    finally:

        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


# ==========================================================
# NEOCLASSICAL_FIRST_RENDER_FIX_V1 — the authorised submission text
# ==========================================================

SUBMISSION_TEXT = (
    "Redesign the facade of this existing unfinished building in a "
    "neoclassical style while preserving the existing building geometry, "
    "massing, floor count, structural frame, wall positions, roof shape, "
    "opening layout, and camera perspective. Replace the visible facade "
    "finish on the main facade surfaces with restrained light cream "
    "travertine stone cladding. Apply neoclassical architectural design "
    "elements as surface relief within the existing wall planes only: "
    "pilasters with capitals, stringcourses, a clear cornice/parapet "
    "treatment, window surrounds, a more formal entrance frame, and stone "
    "balustrades where appropriate at terrace or balcony fronts. Keep the "
    "soffits as painted plaster, not facade stone. Keep glazing as "
    "glass-and-metal, and do not carry brick/block coursing into the new "
    "stone finish. Do not add extra floors, do not change the geometry, and "
    "do not redesign or reconstruct the primary building structure. Do not "
    "add arches, domes, sculptural ornament, or unrelated classical forms. "
    "Do not automatically apply facade stone to the courtyard, retaining "
    "walls, neighbouring buildings, or unrelated site surfaces."
)


def _submission(session):
    result, recorder, _, chat = _route(
        session, SUBMISSION_TEXT, understanding=_persisted_analysis()
    )
    payload = recorder.payloads[0] if recorder.payloads else {}
    return result, recorder, chat, payload, (
        _final(payload) if payload else {}
    )


def test_A_the_six_requested_ornaments_are_present(session):

    _, _, _, payload, _ = _submission(session)

    elements = (
        payload["architectural_intent"]["architectural_design_decision"]
        .get("requested_ornament") or {}
    ).get("elements")

    assert elements == [
        "pilasters", "capitals", "stringcourses", "window surrounds",
        "cornices", "balustrades",
    ]


def test_B_surface_relief_does_not_request_sculptural_relief(session):

    _, _, _, payload, _ = _submission(session)

    elements = (
        payload["architectural_intent"]["architectural_design_decision"]
        .get("requested_ornament") or {}
    ).get("elements") or []

    assert "sculptural relief" not in elements


def test_B_an_explicit_sculptural_request_is_still_detected():

    from core.cognition.architectural_render_instruction_v1 import understand

    for phrase in ("sculptural relief", "relief carving",
                   "ornamental carving"):
        assert "sculptural relief" in understand(
            "Add %s to the entrance." % phrase
        ).get("elements"), phrase


def test_C_no_affirmative_carving_request(session):

    _, _, _, _, resolution = _submission(session)

    prompt = resolution["final_prompt"].lower()

    assert "relief carving" not in prompt
    assert "sculptural architectural relief" not in prompt

    # "sculptural" may appear ONLY inside the user's own prohibition.
    for sentence in prompt.split("."):

        if "sculptural" in sentence:

            assert "do not include" in sentence, sentence


def test_D_the_prohibition_is_preserved(session):

    _, _, _, _, resolution = _submission(session)

    prompt = resolution["final_prompt"].lower()

    assert "do not include: arches, domes, sculptural ornament" in prompt


def test_E_architectural_relief_remains_authorised(session):

    _, _, _, _, resolution = _submission(session)

    prompt = resolution["final_prompt"].lower()

    assert "applied as relief only on the existing wall planes" in prompt
    assert "pilasters applied as relief" in prompt


def test_F_the_operation_remains_restyle(session):

    _, _, _, payload, _ = _submission(session)

    decision = payload["architectural_intent"]["architectural_design_decision"]

    assert decision["requested_operation"]["operation"] == "restyle"
    assert decision["editable_elements"] == ["facade_surface_expression"]


def test_G_the_source_is_the_original_photograph(session):

    _, recorder, _, _, _ = _submission(session)

    bound = recorder.assets[0] if recorder.assets else {}

    assert os.path.abspath(str(bound.get("path") or "")) == os.path.abspath(SOURCE)


def test_H_the_block_is_nonempty_and_not_truncated(session):

    _, _, _, payload, resolution = _submission(session)

    block = (payload.get("architectural_instruction") or {}).get(
        "constraint_block"
    ) or ""

    assert len(block) > 1000
    assert resolution.get("instruction_truncated") is False


def test_I_conceptual_admission_is_valid(session):

    _, _, chat, _, _ = _submission(session)

    admission = getattr(chat, "last_r4_admission", None) or {}

    assert admission.get("admitted") is True
    assert admission.get("reason") == "conceptual_appearance_edit_consented"
    assert admission.get("selected_workflow") == "flux_img2img.json"
    assert admission.get("preservation_status") == "conceptual_unverified"


@pytest.mark.parametrize(
    "text",
    [
        "Design this window in neoclassical stone.",
        "Design only the left facade section in neoclassical style.",
        "Add a new structural column to the facade.",
    ],
)
def test_J_localized_and_structural_requests_stay_blocked(session, text):

    result, recorder, _, _ = _route(
        session, text, understanding=_persisted_analysis()
    )

    assert result.get("status") in ("blocked", "unsupported_edit")
    assert recorder.payloads == []


def test_K_material_only_edit_is_unchanged(session):

    result, recorder, _, _ = _route(
        session, MATERIAL_REQUEST, understanding=_persisted_analysis()
    )

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    decision = recorder.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]

    assert decision["requested_operation"]["operation"] == "replace_finish"
    assert decision.get("requested_ornament") == {"elements": [], "source": "USER_TEXT"}
    assert decision.get("user_prohibitions") == []


def test_L_text_to_image_is_unchanged():

    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    text = build_render_instruction(
        "a modern villa in a cinematic style",
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )["english_instruction"]

    assert "EXISTING building" not in text
