"""R4_PHOTO_FAST_PATH_CLOSURE_V1 - focused CPU acceptance.

The accepted PHOTO-02 photographic warmth edit is a deterministic per-pixel
operation on the ALREADY AUTHORITATIVE source. It needs no architectural
observation. This suite proves the V8 vision gate is skipped for exactly that
case, and that it is preserved for everything else.

CPU only and fail-loud: the vision boundary is replaced by a spy, and BOTH the
LLM gateway and `RenderRuntime` are replaced by stubs that raise on any
attribute access. If a turn ever reaches a model boundary the test fails
instead of calling one.
"""

import hashlib
import inspect
import os
from urllib.parse import unquote

import pytest
from PIL import Image

from core.chat import chat_architect as chat_architect_module
from core.chat.chat_architect import (
    ChatArchitect,
    _r4_architectural_edit_admission,
)
from core.chat.chat_attachment import chat_attachment_service
from core.chat.response_adapter import (
    PHOTOMETRIC_WARMTH_CONFIRMATION,
    ResponseAdapter,
)
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.render.photometric_warmth_adjustment_v1 import (
    PRESET_WARM_BLUE_RESTRAINED_V1,
    transform_image_blue_restrained,
)
from core.vision.image_registry_v1 import image_registry

FA = "\u062a\u0631\u0627\u0632 \u0631\u0646\u06af \u0627\u06cc\u0646 \u0639\u06a9\u0633 \u0631\u0627 \u06a9\u0645\u06cc \u06af\u0631\u0645\u200c\u062a\u0631 \u06a9\u0646."
# The accepted English sentence plus an explicit deictic, which is what binds
# the active image in the dispatcher (the bare sentence has no reference).
EN = ("Slightly warm the photographic colour balance of this image "
      "without changing the architecture.")

FA_OBSERVE = ("\u0641\u0642\u0637 \u0639\u0646\u0627\u0635\u0631 \u0642\u0627\u0628\u0644 "
              "\u0645\u0634\u0627\u0647\u062f\u0647 \u0627\u06cc\u0646 \u062a\u0635\u0648\u06cc\u0631 "
              "\u0631\u0627 \u0644\u06cc\u0633\u062a \u06a9\u0646")
FA_GEOMETRY = ("\u067e\u0646\u062c\u0631\u0647\u0654 \u0627\u06cc\u0646 \u0639\u06a9\u0633 "
               "\u0631\u0627 \u062c\u0627\u0628\u0647\u200c\u062c\u0627 \u06a9\u0646")
FA_STYLE = ("\u0627\u06cc\u0646 \u0639\u06a9\u0633 \u0631\u0627 \u0628\u0647 "
            "\u0633\u0628\u06a9 \u0645\u062f\u0631\u0646 \u0628\u0627\u0632\u0637\u0631\u0627\u062d\u06cc \u06a9\u0646")

# RE-BASELINED by FACADE_RENDERING_FIRST_I2I_ADMISSION_V1, which is explicitly
# authorized to change `_r4_architectural_edit_admission` so the closed gate can
# consult a server-side preservation-acceptance record. The fast path itself did
# not touch the guard; the fingerprint is re-pinned at the new checkpoint so
# future unintended drift is still detected.
#
# NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — re-pinned again, deliberately. The DEICTIC
# branch of `localization_required` used to consume a bare "this" unconditionally,
# so an explicitly GLOBAL facade design ("…for this unfinished building…") was
# refused as needing precise localization. The anchor is now suppressed only by
# a REAL STYLE with resolved global scope. The accepted rule for a named local
# target (`local_targets and not global_scope`) is UNCHANGED, so a localized
# element change keeps its refusal; the closed-by-default behaviour is still
# pinned behaviourally by `test_s_r4_guard_still_blocks_architectural_style_edit`.
#
# NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — re-pinned once more, deliberately.
# The suppression above was still too broad: "design ONLY THE LEFT facade
# SECTION in neoclassical style" carries a style and the word "facade", so its
# anchor was suppressed and a section-scoped request was admitted globally.
# EXCLUSIVE / REGIONAL markers now always localize. Demonstrated behaviourally
# by `test_neoclassical_live_evidence_handoff_v1.py::test_I_localized_requests_are_blocked`
# (window / left section / left side / localized material) and
# `::test_I_structural_requests_are_refused`, alongside the two companion
# guard tests in this file.
R4_ADMISSION_SOURCE_SHA256 = (
    "58575b9b4f65d02045fcf6444a7145aefae8c1496d0141f84cf1cca7bf95381f"
)


class _Exploding:
    """Any attribute access means a model / render boundary was reached."""

    def __init__(self, label):
        self._label = label

    def __getattr__(self, name):
        raise AssertionError("%s boundary touched: %s" % (self._label, name))


# ==========================================================
# FIXTURES
# ==========================================================

@pytest.fixture(scope="module")
def chat_instance():
    instance = ChatArchitect(None)
    # Fail loud instead of ever reaching Ollama or ComfyUI from a unit test.
    instance.llm = _Exploding("llm_gateway")
    instance.render_runtime = _Exploding("render_runtime")
    return instance


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("r4-photo-fast-path-v1")
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


@pytest.fixture
def chat(chat_instance, monkeypatch):
    """The shared instance, with the vision boundary replaced by a spy."""

    calls = []

    def spy(session_id, image_id, force=False):
        calls.append({"session_id": session_id, "image_id": image_id})
        return {
            "analysis_status": "STUBBED",
            "provider": "stub-provider",
            "model": "stub-model",
            "image_type": "architectural_photo",
            "confidence": "HIGH",
            "observed": [],
            "inferred": [],
            "unresolved": [],
            "architectural_elements": [],
            "text_labels_if_visible": [],
            "safety": {"status": "ok"},
            "runtime_status": [],
        }

    monkeypatch.setattr(chat_architect_module, "analyze_session_image", spy)
    return chat_instance, calls


def _synthetic(path, size=(48, 36), mode="RGB"):
    image = Image.new(mode, size, (150, 120, 96))
    if mode == "RGB":
        px = image.load()
        for x in range(size[0]):
            for y in range(size[1]):
                px[x, y] = ((150, 120, 96) if (x // 8 + y // 6) % 2 == 0
                            else (96, 128, 190))
    image.save(path)
    return path


def _register(tmp_path, manifest, name="source.png", mode="RGB"):
    path = _synthetic(tmp_path / name, mode=mode)
    return image_registry.register(
        manifest["session_id"], path=str(path), source_type="uploaded",
        make_active=True,
    )


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ==========================================================
# A / B / C / K / L / M / N / O / P / R - one end-to-end turn
# ==========================================================

def test_end_to_end_accepted_edit(chat, isolated_project, output_root, tmp_path):
    """A full accepted turn: routing, fidelity, lineage, UI contract."""

    instance, calls = chat
    record = _register(tmp_path, isolated_project)
    source_sha = _sha(record["path"])

    result = instance.handle(
        FA, context={"session_id": isolated_project["session_id"]}
    )

    # --- A: routed to PHOTO-02 with NO vision inference -------------------
    assert result.get("status") == "success", result
    assert result.get("engine") == "photometric_warmth_adjustment_v1"
    assert result.get("generative") is False
    assert calls == [], "the V8 vision boundary must not run for PHOTO-02"

    # --- R: no generative / render boundary -------------------------------
    assert "edit_preservation" not in result
    assert "render_metadata" not in result

    # --- C: the authoritative registered source was used ------------------
    assert result["source_image_id"] == record["image_id"]
    assert result["photometric"]["source_sha256"] == source_sha

    # --- K: pixel-identical to the accepted transform ---------------------
    with Image.open(record["path"]) as opened:
        source = opened.convert("RGB").copy()
    expected, _stats = transform_image_blue_restrained(
        source, PRESET_WARM_BLUE_RESTRAINED_V1
    )
    with Image.open(result["image"]["path"]) as opened:
        produced = opened.convert("RGB").copy()
    assert produced.size == expected.size
    assert produced.tobytes() == expected.tobytes()

    # --- L: the original is untouched -------------------------------------
    assert _sha(record["path"]) == source_sha
    assert result["photometric"]["source_unchanged"] is True
    assert result["image"]["path"] != record["path"]

    # --- M: secure creation + registration --------------------------------
    filename = result["image"]["filename"]
    assert filename.startswith("photo_warmth_") and filename.endswith(".png")
    assert len(filename) == len("photo_warmth_") + 32 + len(".png")
    assert os.path.dirname(result["image"]["path"]).lower() == str(output_root).lower()
    active = image_registry.active(isolated_project["session_id"])
    assert active["image_id"] == result["image_id"]
    assert active["source_type"] == "image_to_image"

    # --- N: lineage --------------------------------------------------------
    assert result["parent_image_id"] == record["image_id"]
    assert active["parent_image_id"] == record["image_id"]

    # --- O: the UI attachment resolves through the artifact endpoint ------
    attachment = result["attachments"][0]
    assert attachment["url"].startswith("/artifacts/architectos_output/")
    relative = unquote(attachment["url"][len("/artifacts/architectos_output/"):])
    resolved = chat_attachment_service.resolve_public_path(
        "architectos_output", relative
    )
    assert resolved is not None and resolved.is_file()

    # --- P: the confirmation message --------------------------------------
    response = ResponseAdapter().adapt(result)
    assert response["engine"] == "photometric_warmth_adjustment_v1"
    assert response["message"] == PHOTOMETRIC_WARMTH_CONFIRMATION
    for forbidden in ("\u0646\u0648\u0631\u067e\u0631\u062f\u0627\u0632\u06cc",   # relighting
                      "\u062a\u0639\u0648\u06cc\u0636 \u0645\u0635\u0627\u0644\u062d",  # material replacement
                      "\u0634\u0628"):                                        # night
        assert forbidden not in response["message"]


def test_b_english_request_also_skips_vision(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    _register(tmp_path, isolated_project)

    result = instance.handle(
        EN, context={"session_id": isolated_project["session_id"]}
    )

    assert result.get("engine") == "photometric_warmth_adjustment_v1"
    assert calls == []


# ==========================================================
# D - source authority
# ==========================================================

def test_d_cross_session_source_not_fast_pathed(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    foreign = _register(tmp_path, isolated_project, name="foreign.png")

    other = project_workspace.create("r4-photo-fast-path-other")
    project_registry_bridge.bind(other["project_id"])
    session_registry.begin(other["session_id"])
    image_registry.reset(other["session_id"])
    try:
        verdict = instance._photo_warmth_fast_path(FA, foreign)
        assert verdict["ready"] is False
        assert verdict["reason"] == "source_image_authority_mismatch"
    finally:
        session_registry.end()
        project_registry_bridge.unbind()
        project_registry_bridge.bind(isolated_project["project_id"])
        session_registry.begin(isolated_project["session_id"])


def test_d_unregistered_source_not_fast_pathed(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    forged = {
        "image_id": "img_not_registered",
        "session_id": isolated_project["session_id"],
        "path": str(_synthetic(tmp_path / "forged.png")),
    }
    verdict = instance._photo_warmth_fast_path(FA, forged)
    assert verdict["ready"] is False
    assert verdict["reason"] == "source_image_authority_mismatch"


def test_d_no_record_not_fast_pathed(chat, isolated_project, output_root):
    instance, calls = chat
    assert instance._photo_warmth_fast_path(FA, None)["reason"] == "no_registered_source"


# ==========================================================
# E / H / I - unsupported requests never take the fast path
# ==========================================================

@pytest.mark.parametrize(
    "text,expected_reason",
    [
        ("Make it warmer.", None),
        ("Change the brick to travertine.", None),
        ("Change the door colour only.", None),
        ("Convert this building to night.", None),
        ("Make the sun shine through the windows.", None),
        ("Relight the facade with evening sunlight.", None),
        ("Warm the sky in this photo.", None),
        ("What colour is the facade in this image?", "descriptive_question"),
    ],
    ids=["E_ambiguous", "E_material", "E_door", "H_night", "I_sun", "I_relight",
         "E_localized", "E_question"],
)
def test_ehi_unsupported_requests_do_not_take_fast_path(
    chat, isolated_project, output_root, tmp_path, text, expected_reason
):
    instance, calls = chat
    record = _register(tmp_path, isolated_project)

    verdict = instance._photo_warmth_fast_path(text, record)

    assert verdict["ready"] is False
    if expected_reason:
        assert verdict["reason"] == expected_reason


# ==========================================================
# F - Architectural Eye is preserved
# ==========================================================

def test_f_architectural_observation_still_invokes_vision(
    chat, isolated_project, output_root, tmp_path
):
    instance, calls = chat
    _register(tmp_path, isolated_project)

    result = instance.handle(
        FA_OBSERVE, context={"session_id": isolated_project["session_id"]}
    )

    assert len(calls) >= 1, "an observation request must still observe the image"
    assert result.get("engine") != "photometric_warmth_adjustment_v1"


def test_f_observation_request_is_not_fast_pathed(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    record = _register(tmp_path, isolated_project)
    assert instance._photo_warmth_fast_path(FA_OBSERVE, record)["ready"] is False


# ==========================================================
# G / S - guards remain intact
# ==========================================================

def test_g_geometry_edit_keeps_guard(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    _register(tmp_path, isolated_project)

    result = instance.handle(
        FA_GEOMETRY, context={"session_id": isolated_project["session_id"]}
    )

    assert result.get("type") == "image_edit"
    assert result.get("status") == "unsupported_edit"


def test_s_r4_guard_unchanged():
    source = inspect.getsource(_r4_architectural_edit_admission)
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == R4_ADMISSION_SOURCE_SHA256


def test_s_r4_guard_still_blocks_architectural_style_edit(
    chat, isolated_project, output_root, tmp_path
):
    instance, calls = chat
    _register(tmp_path, isolated_project)

    result = instance.handle(
        FA_STYLE, context={"session_id": isolated_project["session_id"]}
    )

    assert result.get("type") == "render_blocked"
    assert result.get("reason") == "preservation_capability_unverified"


# ==========================================================
# J - image mode validation
# ==========================================================

def test_j_rgba_source_does_not_take_fast_path(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    record = _register(tmp_path, isolated_project, name="rgba.png", mode="RGBA")

    verdict = instance._photo_warmth_fast_path(FA, record)

    assert verdict["ready"] is False
    assert verdict["reason"].startswith("unsupported_source_mode")


def test_j_rgb_source_takes_fast_path(chat, isolated_project, output_root, tmp_path):
    instance, calls = chat
    record = _register(tmp_path, isolated_project, name="rgb.png", mode="RGB")
    assert instance._photo_warmth_fast_path(FA, record)["ready"] is True


# ==========================================================
# Q - unrelated messages are unchanged
# ==========================================================

def test_q_other_messages_unchanged():
    adapter = ResponseAdapter()

    assert adapter.adapt({"type": "chat", "status": "success"})["message"] == (
        "\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0634\u0645\u0627 \u067e\u0631\u062f\u0627\u0632\u0634 \u0634\u062f."
    )
    assert adapter.adapt({"type": "chat", "result": "hello"})["message"] == "hello"
    other = adapter.adapt(
        {"type": "image", "engine": "render_runtime", "status": "success"}
    )
    assert other["message"] != PHOTOMETRIC_WARMTH_CONFIRMATION
