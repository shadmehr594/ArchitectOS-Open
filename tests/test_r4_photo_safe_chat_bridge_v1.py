"""R4_PHOTO_SAFE_CHAT_BRIDGE_V1 - focused CPU acceptance.

The accepted PHOTO-02 photographic warmth operation
(`PRESET_WARM_BLUE_RESTRAINED_V1`) is connected to the REAL chat image-edit
owner (`ChatArchitect._route_image_edit`).

Every test here is CPU-only and synthetic: no ComfyUI submission, no Ollama
inference, no GPU admission, no diffusion sampler. `ImageHandler.handle_image_edit`
is replaced by a capture stub, so a captured call is positive proof that a
request crossed into the GENERATIVE path - which the bridge must prevent for an
accepted photographic adjustment.
"""

import hashlib
import inspect
import os
import sys
from urllib.parse import unquote

import pytest
from PIL import Image

from core.chat import chat_architect as chat_architect_module
from core.chat.chat_architect import (
    ChatArchitect,
    _photo_warmth_bridge_eligibility,
    _r4_architectural_edit_admission,
)
from core.chat.chat_attachment import chat_attachment_service
from core.chat.handlers.image_handler import ImageHandler
from core.chat.session_registry_v1 import session_registry
from core.intent_router import intent_router
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.render.photometric_warmth_adjustment_v1 import (
    PRESET_WARM_BLUE_RESTRAINED_V1,
    adjust_file_exclusive,
    path_identity_conflict,
    transform_image_blue_restrained,
)
from core.vision.image_intent_v1 import INTENT_EDIT, classify_image_intent
from core.vision.image_registry_v1 import image_registry


# The three positive requests from the handoff. These are the REAL user
# sentences; the classifier maps all three to `color_change` / `facade`.
FA_TARAZ = (
    "\u062a\u0631\u0627\u0632 \u0631\u0646\u06af \u0627\u06cc\u0646 \u0639\u06a9\u0633 "
    "\u0631\u0627 \u06a9\u0645\u06cc \u06af\u0631\u0645\u200c\u062a\u0631 \u06a9\u0646."
)
FA_RANG_KOLLI = (
    "\u0631\u0646\u06af \u06a9\u0644\u06cc \u0627\u06cc\u0646 \u0639\u06a9\u0633 "
    "\u0645\u0639\u0645\u0627\u0631\u06cc \u0631\u0627 \u06a9\u0645\u06cc "
    "\u06af\u0631\u0645\u200c\u062a\u0631 \u06a9\u0646\u060c \u0628\u062f\u0648\u0646 "
    "\u062a\u063a\u06cc\u06cc\u0631 \u0627\u062c\u0632\u0627\u06cc "
    "\u0633\u0627\u062e\u062a\u0645\u0627\u0646."
)
EN_PHOTO = (
    "Slightly warm the photographic colour balance without changing the "
    "architecture."
)
FA_NUR_ROOZ = (
    "\u0646\u0648\u0631 \u0631\u0648\u0632 \u0627\u06cc\u0646 \u062a\u0635\u0648\u06cc\u0631 "
    "\u0633\u0627\u062e\u062a\u0645\u0627\u0646 \u0631\u0627 \u06a9\u0645\u06cc "
    "\u06af\u0631\u0645\u200c\u062a\u0631 \u0648 \u0637\u0628\u06cc\u0639\u06cc\u200c\u062a\u0631 "
    "\u06a9\u0646\u061b \u0645\u0635\u0627\u0644\u062d\u060c "
    "\u0628\u0627\u0632\u0634\u0648\u0647\u0627 \u0648 \u062d\u062c\u0645 "
    "\u0633\u0627\u062e\u062a\u0645\u0627\u0646 \u062a\u063a\u06cc\u06cc\u0631 "
    "\u0646\u06a9\u0646\u0646\u062f."
)

# The R4 admission guard must stay byte-identical. This fingerprint was taken
# from the unmodified baseline BEFORE the bridge was added.
#
# RE-BASELINED by FACADE_RENDERING_FIRST_I2I_ADMISSION_V1. That milestone is
# explicitly authorized to change this owner (`core/chat/chat_architect.py`)
# so the closed gate can consult a server-side preservation-acceptance record.
# The historical claim above still holds: the PHOTO BRIDGE did not touch it.
# The fingerprint is re-pinned at the new checkpoint so any FUTURE unintended
# drift is still detected, and the closed-by-default behaviour stays pinned by
# `test_x_r4_guard_still_blocks_an_architectural_style_edit` below.
#
# NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — re-pinned again, deliberately. The DEICTIC
# branch of `localization_required` consumed a bare "this" unconditionally, so a
# GLOBAL facade design ("…for this unfinished building…") was refused as needing
# precise localization. It is now suppressed only by a REAL STYLE with resolved
# global scope; the accepted named-local-target rule is unchanged.
#
# NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — re-pinned once more: that suppression
# was still too broad, because "design only the LEFT facade SECTION in
# neoclassical style" carries a style and "facade" yet is section-scoped.
# EXCLUSIVE / REGIONAL markers now always localize. Demonstrated behaviourally
# by `test_neoclassical_live_evidence_handoff_v1.py::test_I_localized_requests_are_blocked`
# and the two companion guard tests in this file.
R4_ADMISSION_SOURCE_SHA256 = (
    "58575b9b4f65d02045fcf6444a7145aefae8c1496d0141f84cf1cca7bf95381f"
)


# ==========================================================
# FIXTURES
# ==========================================================

@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("r4-photo-safe-chat-bridge-v1")
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


@pytest.fixture
def output_root(tmp_path):
    """Redirect the approved `architectos_output` root into the test tree."""

    root = tmp_path / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    previous = chat_attachment_service.roots.get("architectos_output")
    chat_attachment_service.roots["architectos_output"] = root.resolve()
    try:
        yield root.resolve()
    finally:
        if previous is None:
            chat_attachment_service.roots.pop("architectos_output", None)
        else:
            chat_attachment_service.roots["architectos_output"] = previous


def _synthetic_source(path, size=(48, 36)):
    """A small image with both warm-dominant and blue-dominant pixels."""

    image = Image.new("RGB", size)
    pixels = image.load()
    for x in range(size[0]):
        for y in range(size[1]):
            if (x // 8 + y // 6) % 2 == 0:
                pixels[x, y] = (150, 120, 96)      # warm brick-ish
            else:
                pixels[x, y] = (96, 128, 190)      # blue-dominant sky-ish
    image.save(path)
    return path


def _source(tmp_path, manifest, name="source.png"):
    path = _synthetic_source(tmp_path / name)
    return image_registry.register(
        manifest["session_id"],
        path=str(path),
        source_type="uploaded",
        make_active=True,
    )


def _chat_capture():
    handler = ImageHandler.__new__(ImageHandler)
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = type("R", (), {"last_render_metadata": {}})()
    calls = []

    def fake_edit(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "source_bound_image_id": kwargs.get("parent_image_id")}

    handler.handle_image_edit = fake_edit
    return chat, calls


def _route(chat, record, text, context=None):
    return chat._route_image_edit(
        text,
        record,
        {"image_id": (record or {}).get("image_id")},
        None,
        None,
        20261028,
        context or {},
        image_understanding=None,
    )


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ==========================================================
# A / B / C - the three positive requests select PHOTO-02
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [FA_TARAZ, FA_RANG_KOLLI, EN_PHOTO],
    ids=["A_fa_taraz", "B_fa_rang_kolli", "C_en_photographic_balance"],
)
def test_abc_positive_request_selects_photometric_bridge(
    isolated_project, output_root, tmp_path, text
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, text)

    assert result.get("status") == "success", result
    assert result.get("engine") == "photometric_warmth_adjustment_v1"
    assert result.get("operation") == "photometric_warmth_blue_restrained_v1"
    assert result.get("generative") is False
    # The generative edit owner must never be reached.
    assert calls == []


def test_abc_intent_layer_routes_photographic_balance_to_edit():
    for text in (FA_TARAZ, FA_RANG_KOLLI, EN_PHOTO):
        assert classify_image_intent(text, intent_router)["intent"] == INTENT_EDIT


def test_abc_eligibility_reason_is_recorded():
    for text in (FA_TARAZ, FA_RANG_KOLLI, EN_PHOTO):
        verdict = _photo_warmth_bridge_eligibility(
            text, compile_edit_delta(text, image_edit=True)
        )
        assert verdict["eligible"] is True, (text, verdict)
        assert verdict["reason"] == "photographic_global_colour_balance_warmth"


# ==========================================================
# D - the existing lighting_change / warmer contract is intact
# ==========================================================

def test_d_lighting_change_warmer_contract_intact():
    delta = compile_edit_delta(FA_NUR_ROOZ, image_edit=True)
    assert delta["edit_class"] == "lighting_change"
    assert delta["lighting_quality"] == "warmer"


def test_d_daylight_warmth_is_not_eligible_for_photometric_bridge():
    verdict = _photo_warmth_bridge_eligibility(
        FA_NUR_ROOZ, compile_edit_delta(FA_NUR_ROOZ, image_edit=True)
    )
    assert verdict["eligible"] is False


# ==========================================================
# E - ambiguous daylight warmth does not silently become photographic
# ==========================================================

def test_e_ambiguous_daylight_warmth_is_not_photometric(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, FA_NUR_ROOZ)

    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert result.get("status") != "success"


# ==========================================================
# F / G / H - material, relighting and night never enter PHOTO-02
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "Change the brick to travertine.",
        "Make the brick itself redder.",
        "Change the door colour only.",
    ],
    ids=["F_brick_to_travertine", "F_brick_redder", "F_door_colour_only"],
)
def test_f_material_colour_edits_never_enter_photo_bridge(
    isolated_project, output_root, tmp_path, text
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, text)

    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert _photo_warmth_bridge_eligibility(
        text, compile_edit_delta(text, image_edit=True)
    )["eligible"] is False


@pytest.mark.parametrize(
    "text",
    [
        "Make the sun shine through the windows.",
        "Relight the facade with evening sunlight.",
    ],
    ids=["G_sun_through_windows", "G_relight_facade"],
)
def test_g_physical_relighting_never_enters_photo_bridge(
    isolated_project, output_root, tmp_path, text
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, text)

    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert _photo_warmth_bridge_eligibility(
        text, compile_edit_delta(text, image_edit=True)
    )["eligible"] is False


def test_h_night_conversion_never_enters_photo_bridge(
    isolated_project, output_root, tmp_path
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)
    text = "Convert this building to night."

    result = _route(chat, record, text)

    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert _photo_warmth_bridge_eligibility(
        text, compile_edit_delta(text, image_edit=True)
    )["eligible"] is False


# ==========================================================
# I - architectural geometry edits remain blocked
# ==========================================================

def test_i_geometry_edit_still_blocked(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, "Move the window two metres to the left.")

    # The pre-existing geometry guard owns this refusal and its contract is
    # unchanged: `image_edit` / `unsupported_edit`.
    assert result.get("type") == "image_edit"
    assert result.get("status") == "unsupported_edit"
    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert calls == []


# ==========================================================
# J - a descriptive question never creates an output
# ==========================================================

def test_j_analysis_question_never_creates_output(isolated_project, output_root, tmp_path):
    text = "What colour is the facade in this image?"

    # The intent layer keeps it out of the edit route entirely.
    assert classify_image_intent(text, intent_router)["intent"] != INTENT_EDIT

    # And even if it did reach the owner, the bridge fails closed.
    assert _photo_warmth_bridge_eligibility(
        text, compile_edit_delta(text, image_edit=True)
    )["eligible"] is False

    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)
    _route(chat, record, text)
    assert calls == []  # the stub was not called either: no edit output


def test_j_persian_question_about_colour_balance_fails_closed():
    text = "\u062a\u0631\u0627\u0632 \u0631\u0646\u06af \u0627\u06cc\u0646 \u0639\u06a9\u0633 \u0686\u06cc\u0633\u062a\u061f"
    assert _photo_warmth_bridge_eligibility(
        text, compile_edit_delta(text, image_edit=True)
    )["eligible"] is False


# ==========================================================
# K / L / M - source authority
# ==========================================================

def test_k_invalid_source_authority_rejected(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()

    forged = {
        "image_id": "img_does_not_exist",
        "session_id": isolated_project["session_id"],
        "path": str(_synthetic_source(tmp_path / "unregistered.png")),
        "source_type": "uploaded",
    }

    result = _route(chat, forged, FA_TARAZ)

    assert result.get("engine") != "photometric_warmth_adjustment_v1"
    assert result.get("status") != "success"
    assert calls == []


def test_l_cross_session_source_rejected(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    foreign = _source(tmp_path, isolated_project, name="foreign.png")

    # Move to a DIFFERENT session, then try to edit the first session's image.
    other = project_workspace.create("r4-photo-bridge-other-session")
    project_registry_bridge.bind(other["project_id"])
    session_registry.begin(other["session_id"])
    image_registry.reset(other["session_id"])
    try:
        result = _route(chat, foreign, FA_TARAZ)
        assert result.get("engine") != "photometric_warmth_adjustment_v1"
        assert result.get("status") != "success"
        assert calls == []
    finally:
        session_registry.end()
        project_registry_bridge.unbind()
        project_registry_bridge.bind(isolated_project["project_id"])
        session_registry.begin(isolated_project["session_id"])


def test_m_stale_context_cannot_redirect_the_source(
    isolated_project, output_root, tmp_path
):
    chat, calls = _chat_capture()
    real = _source(tmp_path, isolated_project, name="real.png")

    # A DIFFERENT image, with a different digest, standing in for whatever a
    # stale client context claims the source is.
    decoy_path = tmp_path / "decoy.png"
    Image.new("RGB", (24, 18), (10, 200, 30)).save(decoy_path)
    assert _sha256(decoy_path) != _sha256(real["path"])

    stale_context = {
        "source_image_id": "img_stale",
        "source_path": str(decoy_path),
        "path": str(decoy_path),
        "image_id": "img_stale",
    }

    result = _route(chat, real, FA_TARAZ, context=stale_context)

    assert result.get("status") == "success", result
    assert result["source_image_id"] == real["image_id"]
    # The output must be derived from the REAL registered source, not the decoy.
    assert result["photometric"]["source_sha256"] == _sha256(real["path"])
    assert result["photometric"]["source_sha256"] != _sha256(decoy_path)


# ==========================================================
# N - the per-pixel mathematical contract is preserved
# ==========================================================

def _reference_pixel(r, g, b):
    preset = PRESET_WARM_BLUE_RESTRAINED_V1
    gains = preset["gains"]
    threshold = preset["blue_excess_threshold"]
    attenuation = preset["max_blue_attenuation"]

    excess = b - r
    strength = (
        1.0 if excess <= 0
        else 1.0 - attenuation * min(1.0, float(excess) / threshold)
    )
    red = r * (1.0 + (gains["R"] - 1.0) * strength)
    green = g * gains["G"]
    blue = b * (1.0 - (1.0 - gains["B"]) * strength)

    def clip(value):
        value = int(round(value))
        return 255 if value > 255 else (0 if value < 0 else value)

    return clip(red), clip(green), clip(blue)


def test_n_output_preserves_per_pixel_contract(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, FA_TARAZ)
    assert result.get("status") == "success", result

    with Image.open(record["path"]) as opened:
        source = opened.convert("RGB").copy()
    with Image.open(result["image"]["path"]) as opened:
        produced = opened.convert("RGB").copy()

    assert produced.size == source.size

    source_px = source.load()
    produced_px = produced.load()
    mismatches = 0
    for x in range(source.size[0]):
        for y in range(source.size[1]):
            expected = _reference_pixel(*source_px[x, y])
            if expected != produced_px[x, y]:
                mismatches += 1
    assert mismatches == 0, "%d pixels violate the per-pixel contract" % mismatches


def test_n_transform_is_purely_per_pixel():
    """No output pixel depends on a neighbour: a 1-pixel change stays local."""

    base = Image.new("RGB", (8, 8), (140, 120, 100))
    perturbed = base.copy()
    perturbed.putpixel((4, 4), (90, 120, 200))

    out_a, _ = transform_image_blue_restrained(base, PRESET_WARM_BLUE_RESTRAINED_V1)
    out_b, _ = transform_image_blue_restrained(perturbed, PRESET_WARM_BLUE_RESTRAINED_V1)

    diffs = [
        (x, y)
        for x in range(8) for y in range(8)
        if out_a.getpixel((x, y)) != out_b.getpixel((x, y))
    ]
    assert diffs == [(4, 4)]


# ==========================================================
# O - the original image digest is unchanged
# ==========================================================

def test_o_source_digest_unchanged(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)
    before = _sha256(record["path"])

    result = _route(chat, record, FA_TARAZ)

    assert result.get("status") == "success"
    assert _sha256(record["path"]) == before
    assert result["photometric"]["source_sha256_before"] == before
    assert result["photometric"]["source_sha256_after"] == before
    assert result["photometric"]["source_unchanged"] is True
    # The output is a different file with a different digest.
    assert result["image"]["path"] != record["path"]
    assert _sha256(result["image"]["path"]) != before


# ==========================================================
# P / Q / R - exclusive output creation
# ==========================================================

def test_p_exclusive_creation_refuses_existing_destination(tmp_path):
    source = _synthetic_source(tmp_path / "src.png")
    root = tmp_path / "out"
    root.mkdir()
    name = "photo_warmth_abc123.png"
    (root / name).write_bytes(b"pre-existing")

    result = adjust_file_exclusive(source, root, filename=name)

    assert result["status"] == "output_exists"
    assert result["output_written"] is False
    assert (root / name).read_bytes() == b"pre-existing"


def test_q_destination_race_cannot_overwrite(tmp_path):
    source = _synthetic_source(tmp_path / "src.png")
    root = tmp_path / "out"
    root.mkdir()
    name = "photo_warmth_race.png"

    first = adjust_file_exclusive(source, root, filename=name)
    assert first["status"] == "ok"
    first_digest = _sha256(root / name)

    # A second creator arriving with the same destination must lose, and the
    # winner's bytes must be untouched. Atomicity comes from O_EXCL ('xb').
    second = adjust_file_exclusive(source, root, filename=name)
    assert second["status"] == "output_exists"
    assert _sha256(root / name) == first_digest


def test_r_hardlink_alias_cannot_overwrite_source(tmp_path):
    source = _synthetic_source(tmp_path / "src.png")
    root = tmp_path / "out"
    root.mkdir()
    alias = root / "alias.png"
    try:
        os.link(source, alias)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("hardlinks unavailable on this filesystem")

    before = _sha256(source)
    result = adjust_file_exclusive(source, root, filename="alias.png")

    assert result["status"] == "source_output_conflict"
    assert result["reason"] == "same_file"
    assert result["via"] == "filesystem_identity"
    assert _sha256(source) == before
    assert path_identity_conflict(source, alias) is not None


def test_r_rejects_unsafe_filename_and_root_escape(tmp_path):
    source = _synthetic_source(tmp_path / "src.png")
    root = tmp_path / "out"
    root.mkdir()

    for bad in ("../escape.png", "sub/dir.png", "..\\escape.png", ""):
        result = adjust_file_exclusive(source, root, filename=bad)
        assert result["status"] == "invalid_filename", bad
        assert result["output_written"] is False

    assert not (tmp_path / "escape.png").exists()


# ==========================================================
# S / T / U - lineage and activation
# ==========================================================

def test_s_registration_uses_image_to_image_lineage(
    isolated_project, output_root, tmp_path
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, FA_TARAZ)
    assert result.get("status") == "success"

    active = image_registry.active(isolated_project["session_id"])
    assert active is not None
    assert active["image_id"] == result["image_id"]
    assert active["source_type"] == "image_to_image"
    assert active["session_id"] == record["session_id"]


def test_t_parent_image_id_is_correct(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, FA_TARAZ)
    assert result.get("status") == "success"

    assert result["parent_image_id"] == record["image_id"]
    active = image_registry.active(isolated_project["session_id"])
    assert active["parent_image_id"] == record["image_id"]


def test_u_failed_registration_does_not_activate(
    isolated_project, output_root, tmp_path, monkeypatch
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)
    before_active = image_registry.active(isolated_project["session_id"])["image_id"]
    before_count = image_registry.count(isolated_project["session_id"])

    def boom(*args, **kwargs):
        raise RuntimeError("registration backend unavailable")

    monkeypatch.setattr(chat_architect_module, "register_session_asset", boom)

    result = _route(chat, record, FA_TARAZ)

    assert result.get("status") != "success"
    assert image_registry.active(isolated_project["session_id"])["image_id"] == before_active
    assert image_registry.count(isolated_project["session_id"]) == before_count


def test_u_failed_output_does_not_activate(isolated_project, output_root, tmp_path, monkeypatch):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)
    before_active = image_registry.active(isolated_project["session_id"])["image_id"]

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(chat_architect_module, "adjust_file_exclusive", boom)

    result = _route(chat, record, FA_TARAZ)

    assert result.get("status") != "success"
    assert image_registry.active(isolated_project["session_id"])["image_id"] == before_active


# ==========================================================
# V - the UI receives a valid, accessible attachment
# ==========================================================

def test_v_ui_receives_accessible_attachment(isolated_project, output_root, tmp_path):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, FA_TARAZ)
    assert result.get("status") == "success"

    assert result["type"] == "image"
    assert result["image"]["exists"] is True
    assert result["image"]["url"]

    attachments = result["attachments"]
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment["url"].startswith("/artifacts/architectos_output/")
    assert attachment["kind"] == "image"
    assert attachment["mime_type"] == "image/png"
    assert attachment["size_bytes"] > 0

    # The PUBLIC contract (what the UI actually receives) must resolve back
    # to a real file through the existing, validated artifact resolver.
    prefix = "/artifacts/architectos_output/"
    relative = unquote(attachment["url"][len(prefix):])
    resolved = chat_attachment_service.resolve_public_path(
        "architectos_output", relative
    )
    assert resolved is not None and resolved.is_file()
    assert str(resolved) == os.path.normcase(result["image"]["path"]) or (
        os.path.samefile(str(resolved), result["image"]["path"])
    )
    # No fabricated generative identifiers.
    assert "prompt_id" not in result
    assert result.get("generative") is False


# ==========================================================
# W - no generative engine is invoked
# ==========================================================

def test_w_no_generative_engine_invoked(isolated_project, output_root, tmp_path, monkeypatch):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    touched = []

    class Exploding:
        def __getattr__(self, name):
            touched.append(name)
            raise AssertionError("generative runtime touched: %s" % name)

    monkeypatch.setattr(chat, "render_runtime", Exploding(), raising=False)

    result = _route(chat, record, FA_TARAZ)

    assert result.get("status") == "success"
    assert calls == []          # ImageHandler.handle_image_edit never called
    assert touched == []        # RenderRuntime never touched
    assert result["generative"] is False


# ==========================================================
# X - the R4 generative admission guard is unchanged
# ==========================================================

def test_x_r4_generative_guard_unchanged():
    source = inspect.getsource(_r4_architectural_edit_admission)
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == R4_ADMISSION_SOURCE_SHA256


def test_x_r4_guard_still_blocks_an_architectural_style_edit(
    isolated_project, output_root, tmp_path
):
    chat, calls = _chat_capture()
    record = _source(tmp_path, isolated_project)

    result = _route(chat, record, "Redesign the facade in a modern style.")

    assert result.get("type") == "render_blocked"
    assert result.get("reason") == "preservation_capability_unverified"
    assert calls == []
