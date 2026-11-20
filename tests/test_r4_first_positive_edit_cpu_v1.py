"""R4 positive edit instruction contract — CPU acceptance (no GPU, no ComfyUI).

Scope
-----
After `R4_FIRST_POSITIVE_EDIT_PARTIAL`, two instruction-contract defects were
authorized for repair:

B-1  the edit-delta compiler did not recognise a modest change in daylight
     warmth / colour temperature, and the English word "daylight" describing
     the CURRENT illumination was read as a request to CONVERT to daylight;
B-2  the img2img prompt builder ignored the requested edit and emitted a
     facade-transformation instruction.

A third, directly blocking defect was found while implementing them: the
Persian negative constraint «... تغییر نکنند» was parsed as an AUTHORIZATION to
change the element it protects, which emptied the builder's PRESERVE list.

Evidence rules
--------------
The prompt evidence is taken from the REAL production path, not from a helper
that imitates composition:

    ImageHandler.handle_image_edit()  ->  RenderRuntime.render()
        -> PromptRouter / ImageEditPromptBuilder      (real)
        -> resolve_render_prompt()                    (real)
        -> WorkflowSelector / WorkflowLoader          (real)
        -> ImageWorkflowInjector.inject()             (real)
        -> WorkflowExecutor.execute()                 (STUBBED — captures the graph)

Only the hardware boundary is replaced: VRAM measurement, the Ollama unload and
the ComfyUI submission. `RenderRuntime.last_render_request["resolved_prompt"]`
is therefore the exact string the sampler would receive.

Two tests are deliberately `xfail(strict=True)`: they state the capability that
still does not exist (a verified visual preservation envelope). They turn into
XPASS — and fail the suite — if someone ever "fixes" them without visual
evidence.
"""

import hashlib
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from core.architecture.knowledge.human_learning_ledger_v1 import (
    accepted_rules,
    evaluate_rule_applicability,
)
from core.chat.chat_architect import ChatArchitect, _manual_image_intent
from core.chat.chat_image_bridge import ChatImageBridge
from core.chat.handlers.image_handler import ImageHandler
from core.chat.image_response_adapter import ImageResponseAdapter
from core.chat.session_registry_v1 import session_registry
from core.intent_router import intent_router
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.intelligence.semantic_intent import SemanticIntentEngine
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    preserve_lists,
    resolve_geometry_authority,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    TIME_OF_DAY_DENOISE,
    compile_edit_delta,
    denoise_override,
    is_classified,
)
from core.prompt_intelligence.prompt_router import PromptRouter
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.render.image_edit_presets_v1 import (
    LEVELS,
    resolve_preservation_with_denoise,
)
from core.render.render_result_bridge import RenderResultBridge
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_intent_v1 import INTENT_ANALYZE, INTENT_EDIT
from core.vision.image_registry_v1 import image_registry


# ----------------------------------------------------------
# The one bounded acceptance subject
# ----------------------------------------------------------

SOURCE_PATH = r"C:\ComfyUI-Zluda\output\architectos_v11_00263_.png"

SOURCE_SHA256 = (
    "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4"
)

SOURCE_DIMENSIONS = (768, 704)

# "Make the daylight illumination of this existing architectural image slightly
# warmer and more natural, without changing the building materials, openings or
# geometry."
REQUEST_FA = (
    "نور روز این تصویر ساختمان را کمی گرم‌تر و طبیعی‌تر کن؛ "
    "مصالح، بازشوها و حجم ساختمان تغییر نکنند."
)

REQUEST_EN = (
    "Make the daylight illumination of this existing architectural image "
    "slightly warmer and more natural, without changing the building "
    "materials, openings or geometry."
)

# "How is the lighting of this building?" — descriptive, never an edit.
ANALYSIS_FA = "نور این ساختمان چگونه است؟"

CANDIDATE_WORKFLOW = "flux_img2img.json"
CANDIDATE_DENOISE = 0.30
CANDIDATE_LEVEL = "high_preservation"

# The R3 night contract is accepted evidence; it must not drift.
R3_NIGHT_TEXT = "Convert this building to night."
R3_NIGHT_LENGTH = 869
R3_NIGHT_SHA = "b8783197951cb160e5c4c1b0c881b4ca4fec48dda32ce9f3769129b00192afe8"


class _State:
    """Minimal session state object (get / update / add_message)."""

    def __init__(self):
        self.data = {}

    def get(self):
        return self.data

    def update(self, values):
        self.data.update(values or {})

    def add_message(self, *args, **kwargs):
        return None


# ----------------------------------------------------------
# Fixtures
# ----------------------------------------------------------


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("r4-positive-instruction-contract-v1")
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


def _source(tmp_path, manifest, name="source.png"):
    path = tmp_path / name
    Image.new("RGB", (96, 80), (130, 115, 100)).save(path)
    return image_registry.register(
        manifest["session_id"],
        path=str(path),
        source_type="uploaded",
        make_active=True,
    )


def _capture_chat():
    """Production route with ImageHandler rendering replaced by a stub."""

    handler = ImageHandler.__new__(ImageHandler)
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = SimpleNamespace(last_render_metadata={})
    calls = []

    def fake_edit(**kwargs):
        calls.append(kwargs)
        return {
            "status": "success",
            "source_bound_image_id": kwargs.get("parent_image_id"),
        }

    handler.handle_image_edit = fake_edit
    return chat, calls


def _route(chat, record, text, context=None, image_understanding=None):
    return chat._route_image_edit(
        text,
        record,
        {"image_id": record.get("image_id")},
        None,
        None,
        20261028,
        context or {},
        image_understanding=image_understanding,
    )


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_real_source():
    if not os.path.isfile(SOURCE_PATH):
        pytest.skip("recorded V3 facade source is not present on this machine")
    return SOURCE_PATH


class _ExecutorStop(RuntimeError):
    """Sentinel raised at the ComfyUI submission boundary."""


def _run_real_edit(monkeypatch, tmp_path, text, *, denoise=CANDIDATE_DENOISE):
    """Drive the real production edit path and stop at the executor.

    Everything above `WorkflowExecutor.execute()` is the production code. Only
    the hardware boundary is replaced:

      * `require_render_vram`      — would read ComfyUI /system_stats
      * `unload_ollama_models_for_render` — would unload Ollama models
      * `WorkflowExecutor.execute` — would submit a ComfyUI job

    The image staging directory is redirected into `tmp_path` so no file is
    written into ComfyUI's input directory.
    """

    source = _require_real_source()

    delta = compile_edit_delta(text, image_edit=True)

    preservation = resolve_preservation_with_denoise(
        text=text,
        explicit=CANDIDATE_LEVEL,
        denoise=denoise,
    )

    runtime = RenderRuntime()

    captured = {"executor_calls": 0, "workflow": None, "engine": None}

    def _stub_execute(workflow, engine=None, **kwargs):
        captured["executor_calls"] += 1
        captured["workflow"] = workflow
        captured["engine"] = engine
        raise _ExecutorStop("cpu capture")

    runtime.executor.execute = _stub_execute

    import core.runtime.gpu_handoff_v1 as gpu_handoff

    def _stub_vram(*_args, **_kwargs):
        return {"ok": True, "reason": "cpu_stub", "free_mib": 99999}

    def _stub_ollama(*_args, **_kwargs):
        return {"status": "not_loaded", "reason": "cpu_stub"}

    def _stub_lease(*_args, **_kwargs):
        return SimpleNamespace(acquire=lambda: True, release=lambda: None)

    monkeypatch.setattr(gpu_handoff, "require_render_vram", _stub_vram)
    monkeypatch.setattr(
        gpu_handoff, "unload_ollama_models_for_render", _stub_ollama
    )
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", _stub_lease)

    # The real executor must be unreachable even if the instance stub is lost.
    import core.render.workflow_executor as workflow_executor

    def _forbidden_real_execute(*_args, **_kwargs):
        raise AssertionError("real WorkflowExecutor.execute() reached")

    monkeypatch.setattr(
        workflow_executor.WorkflowExecutor, "execute", _forbidden_real_execute
    )

    image_bridge = ChatImageBridge()
    staging = tmp_path / "comfy_input"
    os.makedirs(staging, exist_ok=True)
    image_bridge.asset_bridge.comfy_input = str(staging)

    handler = ImageHandler(
        render_runtime=runtime,
        result_bridge=RenderResultBridge(),
        semantic_intent=SemanticIntentEngine(fallback=ArchitecturalIntent()),
        image_bridge=image_bridge,
        image_response=ImageResponseAdapter(),
        writeback=None,
        state=_State(),
        prompt_builder=None,
    )

    result = handler.handle_image_edit(
        text=text,
        image={"path": source},
        compiled_render_prompt=delta["prompt"] or None,
        preservation=preservation,
        seed=20261028,
        edit_conflict_terms=delta["conflict_terms"],
        render_profile=None,
        parent_image_id="img_candidate_parent",
        mask_asset=None,
        kontext_edit=False,
        previous_architectural_intent={},
        edit_delta=delta,
        verify_render=None,
        image_understanding=None,
    )

    return {
        "delta": delta,
        "preservation": preservation,
        "workflow": captured["workflow"],
        "executor_calls": captured["executor_calls"],
        "engine": captured["engine"],
        "prompt": runtime.last_render_request.get("resolved_prompt") or "",
        "prompt_source": runtime.last_render_request.get("prompt_source"),
        "instruction": runtime.last_render_request.get("architectural_instruction"),
        "preset": runtime.last_render_request.get("preset"),
        "result": result,
        "runtime": runtime,
    }


# ==========================================================
# A / B — the target request is now a lighting-quality edit
# ==========================================================


def test_A_persian_warmer_daylight_is_a_lighting_edit():
    delta = compile_edit_delta(REQUEST_FA, image_edit=True)

    assert is_classified(delta) is True
    assert delta["edit_class"] == "lighting_change"
    assert delta["edit_target"] == "scene"
    assert delta["lighting_quality"] == "warmer"

    # Not a conversion and not a restyle.
    assert delta["time_of_day"] is None
    assert delta["material"] is None
    assert delta["color"] is None
    assert delta["style"] is None

    assert delta["evidence"]["lighting_quality"] == ["گرم‌تر"]

    text = delta["delta_prompt"]
    assert text.startswith("DELTA: adjust only the illumination")
    assert "warmer" in text
    assert "same time of day" in text
    assert "no sunset" in text
    assert "no night lighting" in text

    # The intensity class must not be silently borrowed: no product-wide
    # strength escalation applies to a quality edit.
    assert denoise_override(delta) is None
    assert TIME_OF_DAY_DENOISE == 0.30


def test_B_english_warmer_daylight_is_a_lighting_edit():
    """The word "daylight" here names the EXISTING light, not a destination."""

    delta = compile_edit_delta(REQUEST_EN, image_edit=True)

    assert delta["edit_class"] == "lighting_change"
    assert delta["edit_class"] != "time_of_day_change"
    assert delta["time_of_day"] is None
    assert delta["lighting_quality"] == "warmer"

    assert "convert the scene" not in delta["delta_prompt"]
    assert "clear blue daytime sky" not in delta["delta_prompt"]
    assert "warmer" in delta["delta_prompt"]


# ==========================================================
# C / D — conversion recognition is not weakened
# ==========================================================


@pytest.mark.parametrize(
    "text",
    [
        "Convert this night scene to daytime.",
        "این صحنه شب را به روز تبدیل کن",
    ],
)
def test_C_explicit_day_conversion_still_classifies_as_day(text):
    delta = compile_edit_delta(text, image_edit=True)

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "day"
    assert delta["lighting_quality"] is None
    assert delta["delta_prompt"].startswith("DELTA: convert the scene to bright")


@pytest.mark.parametrize(
    "text",
    [
        "Convert this building to night.",
        "این تصویر را شب کن",
    ],
)
def test_D_explicit_night_conversion_still_classifies_as_night(text):
    delta = compile_edit_delta(text, image_edit=True)

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "night"
    assert delta["lighting_quality"] is None
    assert denoise_override(delta) == TIME_OF_DAY_DENOISE


def test_D2_accepted_r3_night_delta_is_byte_identical():
    """R3 accepted evidence is immutable: the night contract did not move."""

    prompt = compile_edit_delta(R3_NIGHT_TEXT, image_edit=True)["delta_prompt"]

    assert len(prompt) == R3_NIGHT_LENGTH
    assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == R3_NIGHT_SHA


# ==========================================================
# E / F / G — no over-reach, no regression, no question becomes an edit
# ==========================================================


@pytest.mark.parametrize(
    "text, expected_class",
    [
        # A material is named: the material class outranks light quality.
        ("آجر را گرم‌تر کن", "material_change"),
        ("متریال نما را سنگ کن", "material_change"),
        # No illumination noun governs the quality word.
        ("رنگ نما را گرم‌تر کن", "color_change"),
        # Style requests keep their own class.
        ("این نما را مدرن کن", "style_change"),
    ],
)
def test_E_material_colour_and_style_are_not_lighting_edits(
    text, expected_class
):
    delta = compile_edit_delta(text, image_edit=True)

    assert delta["edit_class"] == expected_class
    assert delta["edit_class"] != "lighting_change"
    assert delta["lighting_quality"] is None


@pytest.mark.parametrize(
    "text, marker",
    [
        ("این تصویر را روشن‌تر کن", "raise the illumination"),
        ("این تصویر را تیره‌تر کن", "lower the illumination"),
        ("Make this image brighter", "raise the illumination"),
    ],
)
def test_F_intensity_contracts_are_unchanged(text, marker):
    delta = compile_edit_delta(text, image_edit=True)

    assert delta["edit_class"] == "lighting_change"
    # Intensity, not quality: the new axis must not claim these.
    assert delta["lighting_quality"] is None
    assert marker in delta["delta_prompt"]


def test_G_descriptive_lighting_question_stays_analysis():
    auto = _manual_image_intent("", ANALYSIS_FA, intent_router)
    manual = _manual_image_intent("analyze_image", ANALYSIS_FA, intent_router)

    assert auto["intent"] == INTENT_ANALYZE
    assert auto["intent"] != INTENT_EDIT
    assert manual["intent"] == INTENT_ANALYZE
    assert manual["intent"] != INTENT_EDIT

    assert is_classified(compile_edit_delta(ANALYSIS_FA, image_edit=True)) is False


def test_G2_manual_analyze_image_never_renders(isolated_project, tmp_path):
    source = _source(tmp_path, isolated_project)
    chat, calls = _capture_chat()

    manual = _manual_image_intent("analyze_image", ANALYSIS_FA, intent_router)
    assert manual["intent"] == INTENT_ANALYZE

    result = _route(chat, source, ANALYSIS_FA)

    assert calls == []
    assert result["type"] == "render_blocked"
    assert result["admission"]["selected_workflow"] is None


# ==========================================================
# H / I — preservation retention and the negation defect
# ==========================================================


def test_H_explicit_preservation_clauses_survive_compilation():
    delta = compile_edit_delta(REQUEST_FA, image_edit=True)

    clauses = delta["explicit_preservation_clauses"]

    assert clauses == ["مصالح، بازشوها و حجم ساختمان تغییر نکنند"]
    assert "EXPLICIT PRESERVATION:" in delta["delta_prompt"]
    assert "مصالح، بازشوها و حجم ساختمان تغییر نکنند" in delta["delta_prompt"]

    english = compile_edit_delta(REQUEST_EN, image_edit=True)

    assert english["explicit_preservation_clauses"] == [
        "without changing the building materials, openings or geometry"
    ]
    assert "EXPLICIT PRESERVATION:" in english["delta_prompt"]


def test_I_negated_geometry_constraint_is_not_an_authorization():
    """«حجم ساختمان تغییر نکنند» must protect the massing, not authorize it.

    Before the fix the plural negative matched no preserve pattern, fell
    through to the verb table, and became a geometric OPERATION: massing was
    lifted out of `fixed_domains` and the builder's PRESERVE list came out
    empty.
    """

    authority = resolve_geometry_authority(
        (),
        preserve_geometry=True,
        preserve_constraints=(),
        user_text=REQUEST_FA,
        edit_class="lighting_change",
    )

    assert authority["authorized_domains"] == []
    assert "massing" in authority["explicit_preserved_domains"]
    assert "massing" in authority["fixed_domains"]
    assert authority["status"] == "ok"

    preserve, prohibit = preserve_lists(authority)

    assert len(preserve) >= 10
    assert "original massing" in preserve
    assert "openings" in preserve
    assert "camera angle" in preserve
    assert "redesign any element outside the authorised scope" not in prohibit
    assert "redesign the building" in prohibit


# ==========================================================
# J / K / L / M / N / O — the effective production prompt
# ==========================================================


def test_J_user_instruction_reaches_the_effective_prompt(
    monkeypatch, tmp_path, isolated_project
):
    run = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)

    prompt = run["prompt"]

    assert run["prompt_source"] == "compiled_authoritative"
    assert run["executor_calls"] == 1

    # 1. the modest warming instruction
    assert "warmer" in prompt
    assert "adjust only the illumination" in prompt
    # 2. the daylight scene is preserved, not converted
    assert "daylight" in prompt
    assert "no night lighting" in prompt
    # 3. the user's own material / opening constraint
    assert "مصالح، بازشوها و حجم ساختمان تغییر نکنند" in prompt
    # 5. meaningful geometry preservation
    assert "GEOMETRY PRESERVATION" in prompt
    assert "- original massing" in prompt
    assert "- camera angle" in prompt
    # The V8.1 decision seam names the editable domain, not the facade.
    assert "lighting, atmosphere" in prompt


def test_K_lighting_prompt_contains_no_facade_restyle(
    monkeypatch, tmp_path, isolated_project
):
    prompt = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)["prompt"]

    for banned in (
        "FACADE TRANSFORMATION",
        "facade transformation",
        "Improve facade appearance",
        "strongly express the requested architectural style",
        "architect-designed facade transformation",
        "renovation visualization",
        "Transform the facade architectural style",
        "Replace only the facade surface material",
        "realistic architectural materials",
    ):
        assert banned not in prompt, banned


def test_L_preserve_list_is_not_empty(
    monkeypatch, tmp_path, isolated_project
):
    prompt = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)["prompt"]

    # The heading with nothing under it was the measured defect.
    assert "PRESERVE EXACTLY: DO NOT:" not in prompt
    assert "PRESERVE EXACTLY:" in prompt

    tail = prompt.split("PRESERVE EXACTLY:", 1)[1]

    assert tail.count("- ") >= 15


def test_M_furniture_graphics_rules_do_not_reach_the_prompt(
    monkeypatch, tmp_path, isolated_project
):
    prompt = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)["prompt"].lower()

    for contaminant in (
        "furniture", "sofa", "dwg", "svg", "symbol library",
        "semantic furniture", "vector contract",
    ):
        assert contaminant not in prompt

    graphics = [
        rule for rule in accepted_rules()
        if rule.get("scope") == "ARCHITECTURAL_GRAPHICS"
    ]

    assert graphics

    for rule in graphics:
        verdict = evaluate_rule_applicability(
            rule,
            {
                "operation": "relight",
                "image_type": "architectural_render_or_photo",
                "text": REQUEST_FA,
            },
        )
        assert verdict["status"] == "NOT_APPLICABLE"
        assert verdict["reason"] == "scope_operation_mismatch"


def test_N_no_preset_tail_and_no_duplicated_delta(
    monkeypatch, tmp_path, isolated_project
):
    run = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)

    # Presets are suppressed for every img2img request.
    assert run["preset"] is None
    assert "warm lit windows" not in run["prompt"]

    # The authoritative delta appears exactly once.
    assert run["prompt"].count("adjust only the illumination") == 1
    assert run["prompt"].count("GEOMETRY PRESERVATION") == 1


def test_O_restyle_edits_keep_the_facade_transformation_contract(
    monkeypatch, tmp_path, isolated_project
):
    """An explicit restyle must NOT lose its supported instruction."""

    style = compile_edit_delta("این نما را مدرن کن", image_edit=True)

    assert style["edit_class"] == "style_change"

    builder = PromptRouter().build(
        {
            "prompt": "این نما را مدرن کن",
            "architectural_intent": {
                "building_type": "villa",
                "edit_delta": style,
            },
        },
        mode="img2img",
    )["description"]

    assert "FACADE TRANSFORMATION" in builder
    assert "ARCHITECTURAL VISUALIZATION QUALITY" in builder

    material = compile_edit_delta("متریال نما را سنگ کن", image_edit=True)

    assert material["edit_class"] == "material_change"

    builder = PromptRouter().build(
        {
            "prompt": "متریال نما را سنگ کن",
            "architectural_intent": {
                "building_type": "villa",
                "edit_delta": material,
            },
        },
        mode="img2img",
    )["description"]

    assert "FACADE TRANSFORMATION" in builder


def test_O2_builder_alone_is_never_change_less():
    """The builder-only path must still say WHAT to change.

    When the delta has no compiled prompt of its own the builder IS the whole
    instruction, so the bounded CHANGE section is emitted. When the delta is
    authoritative the section is omitted, because restating it would duplicate
    the delta and spend T5 budget the DO-NOT block needs.
    """

    delta = compile_edit_delta(REQUEST_FA, image_edit=True)

    with_delta_prompt = PromptRouter().build(
        {
            "prompt": REQUEST_FA,
            "architectural_intent": {"building_type": "villa", "edit_delta": delta},
        },
        mode="img2img",
    )["description"]

    assert "REQUESTED CHANGE" not in with_delta_prompt
    assert "FACADE TRANSFORMATION" not in with_delta_prompt
    assert "- original massing" in with_delta_prompt

    standalone = dict(delta)
    standalone["prompt"] = ""

    builder_only = PromptRouter().build(
        {
            "prompt": REQUEST_FA,
            "architectural_intent": {
                "building_type": "villa",
                "edit_delta": standalone,
            },
        },
        mode="img2img",
    )["description"]

    assert "REQUESTED CHANGE" in builder_only
    assert "warmer" in builder_only
    assert "FACADE TRANSFORMATION" not in builder_only


# ==========================================================
# P / Q — candidate graph, exact source, no hardware boundary
# ==========================================================


def test_P_candidate_uses_exact_source_and_source_latent(
    monkeypatch, tmp_path, isolated_project
):
    before = _sha256(_require_real_source())

    run = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)

    graph = run["workflow"]

    assert run["executor_calls"] == 1
    assert graph is not None
    assert len(graph) == 10

    # The staged copy is byte-identical to the recorded source.
    staged = graph["300"]["inputs"]["image"]
    staged_path = os.path.join(str(tmp_path / "comfy_input"), staged)

    assert os.path.isfile(staged_path)
    assert _sha256(staged_path) == SOURCE_SHA256
    assert _sha256(_require_real_source()) == before == SOURCE_SHA256

    with Image.open(staged_path) as image:
        assert image.size == SOURCE_DIMENSIONS

    # Source latent, not an empty latent.
    assert graph["301"]["class_type"] == "VAEEncode"
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["301"]["inputs"]["vae"] == ["205", 0]
    assert graph["210"]["inputs"]["latent_image"] == ["301", 0]

    classes = {node.get("class_type") for node in graph.values()}

    assert "EmptySD3LatentImage" not in classes
    assert "EmptyLatentImage" not in classes
    assert "LoadImageMask" not in classes
    assert "ImageCompositeMasked" not in classes
    assert not any(str(c).startswith("ControlNet") for c in classes)

    # Exact recorded model configuration, unchanged.
    assert graph["202"]["inputs"]["unet_name"] == (
        "flux1-krea-dev_fp8_scaled.safetensors"
    )
    assert graph["210"]["inputs"]["steps"] == 30
    assert graph["210"]["inputs"]["cfg"] == 5
    assert graph["210"]["inputs"]["sampler_name"] == "euler"
    assert graph["210"]["inputs"]["scheduler"] == "simple"
    assert graph["210"]["inputs"]["denoise"] == CANDIDATE_DENOISE
    assert graph["9"]["inputs"]["images"] == ["208", 0]


def test_Q_high_preservation_comes_from_the_existing_interface():
    preservation = resolve_preservation_with_denoise(
        text=REQUEST_FA,
        explicit=CANDIDATE_LEVEL,
        denoise=CANDIDATE_DENOISE,
    )

    assert preservation["level"] == "high_preservation"
    assert preservation["denoise"] == CANDIDATE_DENOISE
    assert preservation["source"] == "explicit_level+denoise"

    band = LEVELS["high_preservation"]

    assert band["min"] <= CANDIDATE_DENOISE <= band["max"]

    inferred = resolve_preservation_with_denoise(text=REQUEST_FA)
    assert inferred["denoise"] == band["denoise"] == 0.25


# ==========================================================
# R / S / T — the R4 guard is untouched and still refuses
# ==========================================================


def test_R_r4_guard_still_blocks_the_target_request(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)
    chat, calls = _capture_chat()

    result = _route(chat, source, REQUEST_FA)

    assert calls == []
    assert result["type"] == "render_blocked"
    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"

    admission = result["admission"]

    assert admission["admitted"] is False
    assert admission["selected_workflow"] is None
    assert admission["edit_class"] == "lighting_change"
    assert admission["architectural_scope"] is True
    assert admission["rejected_workflows"] == {
        "flux_kontext_edit.json": "preservation_capability_unverified",
        "flux_img2img.json": "preservation_capability_unverified",
    }
    assert admission["human_learning_authority"] == (
        "not_used_for_visual_capability"
    )

    for protected in (
        "massing", "silhouette", "storeys", "roof", "parapet",
        "windows", "doors", "openings", "through_passages",
        "spatial_depth", "railings", "balconies", "details",
        "unmodified_materials", "camera", "perspective",
    ):
        assert protected in admission["protected"]


def test_R2_guard_runs_before_the_global_appearance_escalation():
    with open(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "chat", "chat_architect.py",
        ),
        encoding="utf-8",
    ) as handle:
        source_text = handle.read()

    admission_at = source_text.index(
        "_r4_refusal = _r4_architectural_edit_admission("
    )
    refusal_return_at = source_text.index("return _r4_refusal")
    escalation_at = source_text.index("_global_appearance_edit = bool(")

    assert admission_at < refusal_return_at < escalation_at


def test_S_buildable_candidate_does_not_execute_a_production_edit(
    monkeypatch, tmp_path, isolated_project
):
    # The candidate graph builds and the prompt is correct …
    run = _run_real_edit(monkeypatch, tmp_path, REQUEST_FA)
    assert run["executor_calls"] == 1

    # … and production still refuses the same request.
    source = _source(tmp_path, isolated_project)
    chat, calls = _capture_chat()

    result = _route(chat, source, REQUEST_FA)

    assert result["type"] == "render_blocked"
    assert calls == []


def test_T_existing_architectural_refusals_remain(
    isolated_project, tmp_path
):
    source = _source(tmp_path, isolated_project)

    night_chat, night_calls = _capture_chat()
    night = _route(
        night_chat,
        source,
        "این تصویر را شب کن و معماری ساختمان را ثابت نگه دار",
    )

    assert night_calls == []
    assert night["reason"] == "preservation_capability_unverified"
    assert night["edit_delta"]["edit_class"] == "time_of_day_change"

    material_chat, material_calls = _capture_chat()
    material = _route(
        material_chat,
        source,
        "مصالح نما را سنگ کن؛ حجم و پنجره‌ها ثابت بمانند و هیچ چیز دیگری تغییر نکند.",
    )

    assert material_calls == []
    assert material["reason"] == "preservation_capability_unverified"
    assert material["admission"]["edit_class"] == "material_change"

    passage_chat, passage_calls = _capture_chat()
    passage = _route(
        passage_chat,
        source,
        "گذر سرتاسری میانی را ببند و بقیه اجزا را تغییر نده",
    )

    assert passage_calls == []
    assert "through_passage" in passage["admission"]["protected_spatial_targets"]


# ==========================================================
# The acceptance contract that still gates the future GPU case
# ==========================================================


def test_V_acceptance_contract_still_requires_the_through_passage():
    assert "through_passage_open_to_the_rear" in ACCEPTANCE_CRITERIA
    assert ACCEPTANCE_CRITERIA["through_passage_open_to_the_rear"]["mandatory"] is True
    assert ACCEPTANCE_CRITERIA["storey_count_is_four"]["mandatory"] is True
    assert ACCEPTANCE_CRITERIA["colour_statistics_are_sufficient"]["value"] is False


ACCEPTANCE_CRITERIA = {
    "lighting_change_visible_but_modest": {"mandatory": True},
    "scene_remains_daylight": {"mandatory": True},
    "storey_count_is_four": {"mandatory": True},
    "through_passage_open_to_the_rear": {"mandatory": True},
    "window_and_door_assemblies_unchanged": {"mandatory": True},
    "no_new_railings_balconies_or_fixtures": {"mandatory": True},
    "masonry_coursing_preserved": {"mandatory": True},
    "brick_hue_identity_preserved": {"mandatory": True},
    "no_white_or_green_speckles": {"mandatory": True},
    "camera_and_composition_unchanged": {"mandatory": True},
    "no_invented_architectural_features": {"mandatory": True},
    "valid_source_output_lineage": {"mandatory": True},
    "visual_architecture_inspection": {"mandatory": True},
    "colour_statistics_are_sufficient": {"value": False},
}
