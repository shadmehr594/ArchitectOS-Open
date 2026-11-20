"""NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — CPU acceptance on the REAL Chat route.

Drives `ChatArchitect._route_image_edit` — the production image-edit routing
owner — with the real `ImageHandler` and a RECORDING render transport. Nothing
is submitted, no model runs, no ComfyUI request is made.

ACCEPTANCE CASE
    The accepted user photograph
    `uploads/chat_media/c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg`
    (1792x2400, sha256 8052c743...64c872) is registered as the ACTIVE image,
    after a generated output has been registered active first, so source
    precedence is a real question rather than an assumption.

    `IMAGE_EVIDENCE` is a FIXTURE standing in for the production vision report.
    It asserts nothing about the photograph's pixels.
"""

import copy
import hashlib
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

REQUEST = (
    "Design a restrained neoclassical facade for this unfinished building "
    "using cream travertine. Add proportioned pilasters and capitals, carved "
    "stone surrounds around existing openings, horizontal stringcourses, a "
    "formal cornice and stone balustrades on suitable existing terrace edges. "
    "Preserve the existing structural frame, original floor count, opening "
    "positions, ground-floor openness, massing and camera perspective."
)

MATERIAL_REQUEST = "Change the unfinished facade material to cream travertine."

IMAGE_EVIDENCE = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "accepted-building", "sha256": SOURCE_SHA256},
        "elements": [
            {"element": "facade wall", "kind": ["wall"], "context_kinds": [],
             "evidence_class": "MODEL_REPORTED",
             "verification_status": "UNVERIFIED"},
            {"element": "windows", "kind": ["window", "opening"],
             "context_kinds": [], "evidence_class": "MODEL_REPORTED",
             "verification_status": "UNVERIFIED"},
        ],
    },
}


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
    """Records the payload. Never submits, never executes."""

    def __init__(self):
        self.payloads = []
        self.masks = []
        self.assets = []

    def render(self, project, payload, engine, asset, **kwargs):
        self.payloads.append(copy.deepcopy(payload))
        self.masks.append(kwargs.get("mask_asset"))
        self.assets.append(copy.deepcopy(asset))
        return {"status": "recorded_no_execution"}


@pytest.fixture
def route(tmp_path):

    if not os.path.isfile(SOURCE):
        pytest.skip("accepted source photograph is not present")

    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("neoclassical-chat-route-v1")

    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])

    try:

        # A generated output is registered ACTIVE first.
        generated = tmp_path / "architectos_img2img_edit_99999_.png"
        Image.new("RGB", (336, 448), (150, 140, 130)).save(generated)

        generated_record = image_registry.register(
            manifest["session_id"], path=str(generated),
            source_type="generated", make_active=True,
        )

        # The original photograph is uploaded and becomes active.
        source_record = image_registry.register(
            manifest["session_id"], path=SOURCE,
            source_type="uploaded", make_active=True,
        )

        yield SimpleNamespace(
            manifest=manifest,
            generated=generated_record,
            source=source_record,
            tmp=tmp_path,
        )

    finally:

        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


def _run_route(route, text, *, conceptual=True, understanding=True,
               image_record=None):
    """Drive the REAL routing owner. Returns (result, recorder, context)."""

    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": SOURCE}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _Recorder()
    handler.result_bridge = SimpleNamespace(
        resolve=lambda result: {"status": result.get("status"), "engine": "recorded"}
    )
    handler.image_response = SimpleNamespace(adapt=lambda result: dict(result))

    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = handler.render_runtime
    chat.state = _State()
    chat.session_registry = session_registry
    chat.image_registry = image_registry

    context = {"project_id": route.manifest["project_id"]}
    if conceptual:
        context["conceptual_edit"] = True

    # The caller may name the edit source explicitly; otherwise the session's
    # active image is used, exactly as the production route does.
    active = image_record or image_registry.active(route.manifest["session_id"])

    result = chat._route_image_edit(
        text,
        active,
        {"image_id": (active or {}).get("image_id")},
        None,
        None,
        20261104,
        context,
        image_understanding=IMAGE_EVIDENCE if understanding else None,
    )

    return result, handler.render_runtime, context, chat, active


def _final_prompt(payload):
    """The exact prompt the render path resolves, via the real composer."""

    delta = (payload.get("architectural_intent") or {}).get("edit_delta") or {}

    resolution = resolve_render_prompt(
        compiled_prompt=payload.get("compiled_render_prompt"),
        builder_prompt="",
        user_text=payload.get("prompt"),
        conflict_terms=tuple(edit_delta_conflict_terms(delta)),
        architectural_instruction=payload.get("architectural_instruction"),
    )

    return resolution


@pytest.fixture(scope="module")
def design_route(tmp_path_factory):

    """One real route execution shared by the read-only assertions."""

    base = tmp_path_factory.mktemp("ndcr")

    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(base / "projects")
    project_workspace.trash_root = str(base / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("neoclassical-chat-route-shared")
    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])

    try:

        generated = base / "generated.png"
        Image.new("RGB", (336, 448), (150, 140, 130)).save(generated)
        image_registry.register(
            manifest["session_id"], path=str(generated),
            source_type="generated", make_active=True,
        )
        image_registry.register(
            manifest["session_id"], path=SOURCE,
            source_type="uploaded", make_active=True,
        )

        ns = SimpleNamespace(
            manifest=manifest, tmp=base,
            generated={"image_id": "generated"},
            source={"image_id": "source"},
        )

        result, recorder, context, chat, active = _run_route(ns, REQUEST)

        payload = recorder.payloads[0] if recorder.payloads else {}

        yield SimpleNamespace(
            result=result,
            recorder=recorder,
            context=context,
            chat=chat,
            active=active,
            payload=payload,
            resolution=_final_prompt(payload) if payload else {},
        )

    finally:

        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


# ==========================================================
# A — the real request reaches the design path
# ==========================================================

def test_A_the_route_produces_exactly_one_payload(design_route):

    assert design_route.result.get("status") == "recorded_no_execution"
    assert len(design_route.recorder.payloads) == 1
    assert design_route.payload.get("mode") == "img2img"


def test_A_the_edit_is_an_architectural_design_not_a_material_swap(design_route):

    intent = design_route.payload["architectural_intent"]
    delta = intent["edit_delta"]

    assert delta["style"] == "neoclassical"
    assert delta["material"] == "travertine"

    decision = intent["architectural_design_decision"]

    assert decision["requested_operation"]["operation"] == "restyle"
    assert decision["execution_status"] == "READY_FOR_EXISTING_WORKFLOW"
    assert decision["editable_elements"] == ["facade_surface_expression"]


# ==========================================================
# B — R4 and the conceptual consent contract are intact
# ==========================================================

def test_B_conceptual_consent_admits_the_existing_whole_image_route(design_route):

    admission = (
        design_route.context.get("r4_admission")
        or getattr(design_route.chat, "last_r4_admission", None)
        or {}
    )

    assert admission.get("admitted") is True
    assert admission.get("reason") == "conceptual_appearance_edit_consented"
    assert admission.get("selected_workflow") == "flux_img2img.json"
    assert admission.get("preservation_status") == "conceptual_unverified"
    # No exact-preservation claim is made anywhere.
    assert admission.get("preservation_contract") is None


def test_B_without_conceptual_consent_the_route_is_refused(route):

    result, recorder, _, _, _ = _run_route(route, REQUEST, conceptual=False)

    assert result.get("status") == "blocked"
    assert result.get("reason") == "preservation_capability_unverified"
    assert recorder.payloads == [], "nothing may reach the renderer"


def test_B_a_masked_architectural_edit_is_still_refused(route):

    """A caller mask stays outside the accepted envelope — R4 is not bypassed."""

    handler = ImageHandler.__new__(ImageHandler)
    handler._state = _State()
    handler.image_bridge = SimpleNamespace(
        process_upload=lambda *a, **k: {"asset": {"path": SOURCE}}
    )
    handler.semantic_intent = SimpleNamespace(extract=lambda _text: {})
    handler.render_runtime = _Recorder()
    handler.result_bridge = SimpleNamespace(resolve=lambda r: dict(r))
    handler.image_response = SimpleNamespace(adapt=lambda r: dict(r))

    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = handler.render_runtime
    chat.state = _State()
    chat.session_registry = session_registry
    chat.image_registry = image_registry

    active = image_registry.active(route.manifest["session_id"])

    result = chat._route_image_edit(
        REQUEST,
        active,
        {"image_id": (active or {}).get("image_id")},
        None,
        None,
        20261104,
        {
            "project_id": route.manifest["project_id"],
            "conceptual_edit": True,
            "mask": {"filename": "architectos_mask_CALLER.png"},
            "kontext_edit": True,
        },
        image_understanding=IMAGE_EVIDENCE,
    )

    assert result.get("status") == "blocked"
    assert handler.render_runtime.payloads == []


# ==========================================================
# RISK A — the global gate must not swallow localized edits
# ==========================================================

LOCAL_MATERIAL = (
    "Change only this window's material on the facade to dark metal."
)

LOCAL_WINDOW = "Change only this window on the facade."

STRUCTURAL_MUTATION = "Remove the facade wall and replace it with a new volume."


def test_RISK_A_localized_material_change_is_not_globally_admissible(route):

    """'facade' appears, but the target is ONE window: still localization."""

    result, recorder, _, chat, _ = _run_route(route, LOCAL_MATERIAL)

    assert result.get("status") == "blocked"
    assert result.get("reason") == "preservation_capability_unverified"
    assert recorder.payloads == [], "a localized edit must not reach the renderer"


def test_RISK_A_localized_window_change_is_not_globally_admissible(route):

    result, recorder, _, _, _ = _run_route(route, LOCAL_WINDOW)

    assert result.get("status") == "blocked"
    assert recorder.payloads == []


def test_RISK_A_structural_mutation_is_refused(route):

    result, recorder, _, _, _ = _run_route(route, STRUCTURAL_MUTATION)

    assert result.get("status") in ("blocked", "unsupported_edit")
    assert recorder.payloads == []


def test_RISK_A_the_design_and_the_localized_edit_differ_in_style_presence():

    """The discriminator is a real style, not the word "facade"."""

    design = compile_edit_delta(REQUEST, image_edit=True)
    localized = compile_edit_delta(LOCAL_MATERIAL, image_edit=True)

    assert design.get("style") == "neoclassical"
    assert localized.get("style") is None


# ==========================================================
# RISK B — the generated image stays ACTIVE, the JPEG is the edit source
# ==========================================================

@pytest.fixture
def precedence_session(tmp_path):

    """Generated output ACTIVE; the photograph supplied explicitly."""

    if not os.path.isfile(SOURCE):
        pytest.skip("accepted source photograph is not present")

    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("neoclassical-precedence-v1")

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

        # Registered but deliberately NOT made active.
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


def test_RISK_B_the_generated_image_stays_active(precedence_session):

    active = image_registry.active(precedence_session.manifest["session_id"])

    assert active.get("image_id") == precedence_session.generated["image_id"]
    # The registry normalises a generated asset to "other"; what matters is
    # that the ACTIVE asset is not the uploaded photograph.
    assert active.get("source_type") != "uploaded"
    assert "architectos_img2img_edit_99999" in str(active.get("path") or "")


def test_RISK_B_the_explicit_jpeg_wins_over_the_active_generated_image(
    precedence_session,
):

    result, recorder, _, _, _ = _run_route(
        precedence_session,
        REQUEST,
        image_record=precedence_session.jpeg,
    )

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    bound = recorder.assets[0] if recorder.assets else {}

    assert os.path.abspath(str(bound.get("path") or "")) == os.path.abspath(SOURCE)

    # …and the generated asset was never substituted.
    assert "architectos_img2img_edit_99999" not in str(bound.get("path") or "")


# ==========================================================
# C — the effective prompt carries the design elements
# ==========================================================

def test_C_the_effective_prompt_contains_the_requested_elements(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    for element in ("pilaster", "capital", "stringcourse", "cornice",
                    "balustrade", "window surround"):
        assert element in prompt, element


def test_C_the_instruction_block_is_not_truncated(design_route):

    assert design_route.resolution.get("instruction_truncated") is False


# ==========================================================
# D — the prompt does not ask for a new building
# ==========================================================

def test_D_no_new_building_instruction(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "create a new architectural design (not a refinement)" not in prompt
    assert "overall building composition" not in prompt


def test_D_the_same_building_is_kept(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    # The prompt must say the SAME building stays, not that a new one is made.
    assert "keep the same building" in prompt

    # NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — the bare "do not redesign the
    # building" was ambiguous for a facade redesign and is now replaced by the
    # precise distinction: redesign the EXPRESSION, not the structure.
    assert "redesign the architectural expression of the existing facade only" in prompt
    assert "do not redesign or reconstruct the primary building structure" in prompt
    assert "do not redesign the building" not in prompt


# ==========================================================
# E — protection and authorised decoration are distinguished
# ==========================================================

def test_E_preservation_and_authorised_decoration_are_both_stated(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    # Primary geometry is protected…
    assert "preserve the existing structural frame" in prompt
    assert "the same geometry" in prompt
    # …while the requested decoration is authorised as relief.
    assert "requested decorative additions, applied as relief only" in prompt
    assert "no structural member or new volume is added" in prompt


def test_E_decoration_is_never_described_as_structure(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "structurally supported" not in prompt
    assert "applied as relief only on the existing wall planes" in prompt


# ==========================================================
# F — nothing unrequested
# ==========================================================

def test_F_no_unrequested_ornament(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    # Specific words, not a substring scrub: "archviz" and "architectural"
    # contain "arch" and are not arches.
    for unrequested in ("arches", "arched", "arcade", "dome", "domes",
                        "sculptural", "sculpture", "pediment"):
        assert unrequested not in prompt, unrequested


# ==========================================================
# G — surfaces stay distinct
# ==========================================================

def test_G_wall_soffit_glazing_and_site_stay_distinct(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "the wall field in travertine" in prompt
    assert "the soffits in painted plaster, not facade stone" in prompt
    assert "glazing and frames as glass and metal, not stone" in prompt
    assert "separate site scope" in prompt


# ==========================================================
# H — the source photograph is bound, not the generated output
# ==========================================================

def test_H_the_active_image_is_the_uploaded_photograph(design_route):

    active = design_route.active or {}

    assert active.get("source_type") == "uploaded"
    assert os.path.abspath(str(active.get("path"))) == os.path.abspath(SOURCE)


def test_H_the_payload_binds_the_photograph(design_route):

    assets = design_route.recorder.assets

    assert assets, "the renderer must have received a source asset"

    bound = assets[0] if isinstance(assets[0], dict) else {}

    assert os.path.abspath(str(bound.get("path") or "")) == os.path.abspath(SOURCE)


# ==========================================================
# I — material-only I2I is unchanged
# ==========================================================

def test_I_material_only_request_is_still_a_finish_replacement(route):

    result, recorder, _, _, _ = _run_route(route, MATERIAL_REQUEST)

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    payload = recorder.payloads[0]
    decision = payload["architectural_intent"]["architectural_design_decision"]

    assert decision["requested_operation"]["operation"] == "replace_finish"
    assert decision["editable_elements"] == ["facade_wall_surface"]

    block = (payload.get("architectural_instruction") or {}).get(
        "constraint_block", ""
    ).lower()

    for ornament in ("pilaster", "capital", "cornice", "balustrade",
                     "stringcourse"):
        assert ornament not in block, ornament


# ==========================================================
# J — text-to-image is unchanged
# ==========================================================

def test_J_t2i_instruction_is_unchanged():

    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    instruction = build_render_instruction(
        "a modern villa in a cinematic style",
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )

    text = instruction["english_instruction"]

    # A new-build request is never captured by the existing-building gate.
    assert "EXISTING building" not in text
    assert "do not replace the building" not in text
    assert "Design a new facade treatment" not in text


# ==========================================================
# K — no localization claim
# ==========================================================

def test_K_no_unsupported_localization_claim(design_route):

    decision = design_route.payload["architectural_intent"][
        "architectural_design_decision"
    ]

    admission = (
        design_route.context.get("r4_admission")
        or getattr(design_route.chat, "last_r4_admission", None)
        or {}
    )

    # The route is the GLOBAL conceptual one; nothing claims a localized edit.
    assert admission.get("preservation_status") == "conceptual_unverified"
    assert decision["geometry_authority"]["authorized_domains"] in ([], None)

    block = (design_route.payload.get("architectural_instruction") or {}).get(
        "constraint_block", ""
    ).lower()

    assert "not measured regions" in block

    for token in ("polygon", "bounding box", "coordinates", "pixel"):
        assert token not in block, token


# ==========================================================
# L — nothing executed
# ==========================================================

def test_L_no_submission_and_canonical_workflow_unchanged(design_route):

    assert design_route.payload.get("render_executed") in (None, False)
    assert design_route.payload.get("comfy_invoked") in (None, False)

    path = os.path.join(
        ROOT, "core", "render", "workflows", "flux_img2img.json"
    )

    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()

    assert digest == (
        "3e6656efe1d9eacac7d903502d4adf389eb49d18a05a9d6f1055e9265d6948ca"
    )


def test_L_source_photograph_is_unmodified():

    with open(SOURCE, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()

    assert digest == SOURCE_SHA256


# ==========================================================
# NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1
# PROBLEM A — protected geometry vs authorised facade design
# ==========================================================

def test_PROBLEM_A_the_protected_set_is_primary_structure(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "structural element unchanged" in prompt
    # The old blanket clause forbade the decoration the request authorises.
    assert "architectural element unchanged" not in prompt


def test_PROBLEM_A_the_authorised_additions_are_stated_as_relief(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert (
        "requested decorative stone elements are additions applied as relief "
        "on the existing wall planes" in prompt
    )
    assert "not replacements of those elements" in prompt


def test_PROBLEM_A_protection_is_not_removed(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    for protected in ("massing", "floor count", "structural frame",
                      "wall positions", "roof shape", "opening layout",
                      "camera perspective"):
        assert protected in prompt, protected


def test_PROBLEM_A_decorative_additions_are_not_prohibited(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    for authorised in ("pilaster", "capital", "stringcourse", "cornice",
                       "window surround", "balustrade"):
        assert authorised in prompt, authorised


# ==========================================================
# PROBLEM C — restrained travertine, not veined marble
# ==========================================================

def test_PROBLEM_C_the_design_asks_for_restrained_travertine(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "restrained light cream travertine" in prompt
    assert "natural subtle porosity" in prompt
    assert "no exaggerated golden marble veining" in prompt
    assert "no brick or block coursing carried through the stone" in prompt


def test_PROBLEM_C_the_veined_marble_wording_is_gone(design_route):

    prompt = design_route.resolution["final_prompt"].lower()

    assert "visible veining" not in prompt


def test_PROBLEM_C_a_plain_material_request_keeps_its_own_wording():

    """The restrained variant is gated on a style; a material swap is not."""

    delta = compile_edit_delta(MATERIAL_REQUEST, image_edit=True)
    prompt = delta_prompt(delta).lower()

    assert "visible veining" in prompt
    assert "restrained light cream travertine" not in prompt
    assert "do not redesign the building" in prompt


# ==========================================================
# PROBLEM D — no silent render without architectural evidence
# ==========================================================

def test_PROBLEM_D_a_design_without_evidence_is_refused(route):

    result, recorder, _, _, _ = _run_route(
        route, REQUEST, understanding=False,
    )

    assert result.get("status") == "blocked"
    assert result.get("reason") == "architectural_evidence_required"
    assert recorder.payloads == [], "nothing may reach the renderer"

    gap = result.get("capability_gap") or {}
    assert gap.get("missing") == "source_architectural_evidence"


def test_PROBLEM_D_the_same_design_with_evidence_still_renders(route):

    result, recorder, _, _, _ = _run_route(route, REQUEST, understanding=True)

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1


def test_PROBLEM_D_a_material_request_is_not_affected_by_the_guard(route):

    """The guard is scoped to `restyle`; a finish replacement still runs."""

    result, recorder, _, _, _ = _run_route(
        route, MATERIAL_REQUEST, understanding=False,
    )

    assert result.get("status") == "recorded_no_execution"
    assert len(recorder.payloads) == 1

    decision = recorder.payloads[0]["architectural_intent"][
        "architectural_design_decision"
    ]

    assert decision["requested_operation"]["operation"] == "replace_finish"


# ==========================================================
# PROBLEM E — the remaining R4 localization cases
# ==========================================================

def test_PROBLEM_E_a_named_region_is_not_globally_admissible(route):

    result, recorder, _, _, _ = _run_route(
        route, "Change this particular region to neoclassical.",
    )

    assert result.get("status") == "blocked"
    assert recorder.payloads == []


def test_PROBLEM_E_a_named_facade_section_is_not_globally_admissible(route):

    result, recorder, _, _, _ = _run_route(
        route, "Change only the left facade section.",
    )

    assert result.get("status") == "blocked"
    assert recorder.payloads == []


def test_PROBLEM_E_a_new_structural_column_is_refused(route):

    result, recorder, _, _, _ = _run_route(
        route, "Add a new structural column to the facade.",
    )

    assert result.get("status") in ("blocked", "unsupported_edit")
    assert recorder.payloads == []


def test_PROBLEM_E_style_presence_alone_does_not_suppress_localization():

    """A style word must not turn a localized request into a global one."""

    region = compile_edit_delta(
        "Change this particular region to neoclassical.", image_edit=True
    )

    assert region.get("style") == "neoclassical"

    import core.chat.chat_architect as ca

    scope = (ca.detect_unsupported_geometry_edit(
        "Change this particular region to neoclassical."
    ) or {}).get("scope_evidence") or {}

    # Global facade scope is NOT resolved, so the anchor still localizes.
    assert scope.get("global_scope") is False
