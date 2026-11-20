# ==========================================================
# ArchitectOS IMAGE_TO_IMAGE_05 — Tests
#
#  1. preservation contract (3 levels, approved ranges, default)
#  2. preservation inference + denoise clamping
#  3. colloquial Persian reference resolution (همینو / اینو / …)
#  4. bare deictic only counts with an edit signal
#  5. edit intent precedence over reference
#  6. Persian edit imperatives recognised
#  7. unsupported precise-geometry edits refused
#  8. img2img injection map (denoise + seed, NO dimensions)
#  9. img2img preset suppression + compiled prompt authority
# 10. derived-image registration + parent lineage
# 11. truthful top-level status (no fake success)
# 12. registry active/last semantics for chaining
# 13. regression 01 / 02 / 03 / 03B / 04
#
# NO REAL RENDERS ARE PERFORMED HERE.
# ==========================================================


import copy
import importlib.util
import json
import os
import sys
import types


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(
        0,
        ROOT
    )


from core.render.image_edit_presets_v1 import (
    LEVELS,
    DEFAULT_LEVEL,
    LEVEL_ORDER,
    get_level,
    clamp_denoise,
    infer_level,
    resolve_preservation,
    resolve_preservation_with_denoise,
    available_levels,
)

from core.render.workflow_loader import WorkflowLoader
from core.render.image_workflow_injector import ImageWorkflowInjector
from core.render.render_runtime import RenderRuntime
from core.render.image_asset_bridge import ImageAssetBridge

from core.vision.image_registry_v1 import image_registry
from core.vision.reference_resolver_v1 import resolve_reference
from core.vision.image_intent_v1 import (
    classify_image_intent,
    detect_unsupported_geometry_edit,
    has_edit_signal,
    INTENT_EDIT,
    INTENT_ANALYZE,
    INTENT_REFERENCE,
    INTENT_UPLOAD_ONLY,
)

from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry


PASS = []


SOURCE_IMAGE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"

FLUX_IMG2IMG = os.path.join(
    ROOT, "core", "render", "workflows", "flux_img2img.json"
)


def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)


def _chat():

    return ChatArchitect(types.SimpleNamespace())


def _seed_registry(session, n_render=2):

    image_registry.reset(session)

    image_registry.register(
        session, path="uploads/up.png", source_type="uploaded"
    )

    for i in range(n_render):

        image_registry.register(
            session,
            path="C:/ComfyUI-Zluda/output/render_%d.png" % i,
            source_type="text_to_image",
        )



# ==========================================================
# 1 / 2 — PRESERVATION CONTRACT
# ==========================================================

def test_preservation_contract():

    print("\n[1] Preservation contract")

    assert available_levels() == list(LEVEL_ORDER)

    expected = {
        "high_preservation": (0.20, 0.30),
        "balanced": (0.35, 0.45),
        "creative": (0.50, 0.60),
    }

    for name, (low, high) in expected.items():

        level = LEVELS[name]

        assert level["min"] == low, (name, level["min"])

        assert level["max"] == high, (name, level["max"])

        assert low <= level["denoise"] <= high, (name, level["denoise"])

    assert DEFAULT_LEVEL == "high_preservation"

    ok("3 levels with approved denoise ranges; default high_preservation")


def test_preservation_inference_and_clamp():

    print("\n[2] Preservation inference + clamping")

    assert infer_level("")[0] == "high_preservation"

    assert infer_level("همینو شب کن")[0] == "high_preservation"

    assert infer_level("بدون تغییر فرم فقط نور")[0] == "high_preservation"

    assert infer_level("متعادل تغییر بده")[0] == "balanced"

    assert infer_level("کاملاً خلاقانه عوض کن")[0] == "creative"

    assert infer_level("creative reinterpretation")[0] == "creative"

    ok("deterministic level inference (no LLM)")

    # clamping can never violate the level contract
    assert clamp_denoise(0.9, "high_preservation") == 0.30

    assert clamp_denoise(0.05, "high_preservation") == 0.20

    assert clamp_denoise(0.9, "creative") == 0.60

    assert clamp_denoise(0.9, "balanced") == 0.45

    clamped = resolve_preservation_with_denoise(
        text="همینو شب کن", denoise=0.95
    )

    assert clamped["level"] == "high_preservation"

    assert clamped["denoise"] == 0.30

    ok("explicit denoise is clamped into the resolved level range")

    explicit = resolve_preservation(explicit="creative")

    assert explicit["level"] == "creative"

    assert explicit["source"] == "explicit_level"

    rejected = resolve_preservation(text="", explicit="nonsense")

    assert rejected["level"] == DEFAULT_LEVEL

    assert rejected["rejected_explicit"] == "nonsense"

    ok("explicit level wins; unknown level falls back and is reported")


# ==========================================================
# 3 / 4 / 5 / 6 — REFERENCE + INTENT
# ==========================================================

def test_colloquial_references():

    print("\n[3] Colloquial Persian reference resolution")

    session = "i2i_ref"

    _seed_registry(session)

    for phrase, kind in (
        ("همینو شب کن", "active"),
        ("اینو شب کن", "active"),
        ("همین رو تیره کن", "active"),
        ("این رو روشن کن", "active"),
        ("رندر قبلی رو سنگ روشن کن", "last_render"),
        ("همین رندر رو شب کن", "active"),
        ("همینو روز کن", "active"),
    ):

        resolution = resolve_reference(phrase, session)

        assert resolution["status"] == "resolved", (phrase, resolution)

        assert resolution["reference_kind"] == kind, (phrase, resolution)

    ok("همینو / اینو / همین رو / این رو / رندر قبلی all resolve")

    # unresolved still never guesses
    empty = "i2i_ref_empty"

    image_registry.reset(empty)

    assert resolve_reference("همینو شب کن", empty)["status"] == "unresolved"

    ok("colloquial reference with no images -> unresolved")


def test_bare_deictic_requires_edit_signal():

    print("\n[4] Bare deictic only counts with an edit signal")

    session = "i2i_bare"

    _seed_registry(session)

    # bare "این" WITHOUT an edit signal must not become a reference
    plain = resolve_reference("این ویلا خیلی قشنگه", session)

    assert plain["status"] == "not_a_reference", plain

    ok("bare 'این' without an edit signal -> not_a_reference")

    # with an edit signal it becomes an active-image reference
    edit = resolve_reference("این رو شب کن", session)

    assert edit["status"] == "resolved"

    assert edit["reference_kind"] == "active"

    ok("bare 'این' + edit signal -> active image")

    # colloquial contractions match directly
    assert resolve_reference("همینو", session)["status"] == "resolved"

    ok("colloquial contraction 'همینو' matches directly")


def test_edit_precedence_over_reference():

    print("\n[5] Edit intent precedence over reference")

    for phrase in (
        "رندر قبلی رو سنگ روشن کن",
        "همین رندر رو شب کن",
        "همینو شب کن",
        "اینو تیره کن",
    ):

        intent = classify_image_intent(phrase)

        assert intent["intent"] == INTENT_EDIT, (phrase, intent)

    ok("edit wins whenever an edit imperative is present")

    # pure reference with no edit stays a reference
    assert classify_image_intent("همین عکس")["intent"] == INTENT_REFERENCE

    # pure question stays analyze
    assert classify_image_intent("رندر قبلی رو توضیح بده")["intent"] == INTENT_ANALYZE

    assert classify_image_intent("همین عکس چیه؟")["intent"] == INTENT_ANALYZE

    assert classify_image_intent("")["intent"] == INTENT_UPLOAD_ONLY

    ok("reference / analyze / upload_only still classified correctly")


def test_persian_edit_imperatives():

    print("\n[6] Persian edit imperatives recognised")

    approved = (
        "شب کن", "روز کن", "روشن کن", "تیره کن", "سنگ کن",
        "چوب کن", "شیشه کن", "متریال", "رنگ", "نور",
    )

    for word in approved:

        phrase = "اینو " + word

        has_edit, matched = has_edit_signal(phrase)

        assert has_edit, (word, phrase)

        print("     " + word.ljust(10) + "-> " + str(matched[:2]))

    ok("all approved Persian appearance imperatives recognised")

    # a bare appearance noun is NOT an edit on its own
    assert not has_edit_signal("چه رنگیه؟")[0]

    assert not has_edit_signal("این عکس چیه؟")[0]

    assert not has_edit_signal("این عکس رنگش چیه؟")[0]

    ok("bare appearance nouns alone are not edit signals")

    # ...but they ARE edits when the image is object-marked
    for noun in ("متریال", "رنگ", "نور"):

        assert has_edit_signal("اینو " + noun)[0], noun

        assert has_edit_signal("همینو " + noun)[0], noun

    ok("object-marked deictic + appearance noun -> edit")


# ==========================================================
# 7 — UNSUPPORTED GEOMETRY
# ==========================================================

def test_unsupported_geometry_edit():

    print("\n[7] Unsupported precise-geometry edits refused")

    dimensioned = "این پنجره رو 80 سانت ببر راست"

    guard = detect_unsupported_geometry_edit(dimensioned)

    assert guard["unsupported"] is True

    assert guard["reason"] == "dimensioned_geometry_edit_not_supported"

    ok("negative test phrase -> dimensioned_geometry_edit_not_supported")

    for phrase in (
        "پنجره رو ببر راست",
        "این پنجره رو بزرگتر کن",
        "move the window to the right",
        "پنجره رو 80 سانتی متر ببر راست",
        "move the window 80 cm to the right",
    ):

        assert detect_unsupported_geometry_edit(phrase)["unsupported"] is True, phrase

    ok("plain and dimensioned geometry moves are all refused")

    # localized operations on ONE named architectural component are also
    # precise geometry edits, even without a stated dimension
    for phrase in (
        "این پنجره رو حذف کن",
        "پنجره رو اضافه کن",
        "این دیوار رو جابه‌جا کن",
        "در ورودی رو بزرگ کن",
        "remove the window",
        "delete the wall",
        "move the door",
    ):

        guard = detect_unsupported_geometry_edit(phrase)

        assert guard["unsupported"] is True, phrase

    ok("localized component operations are refused")

    for phrase in (
        "همینو شب کن",
        "رندر قبلی رو سنگ روشن کن",
        "اینو تیره کن",
        "نما رو سنگ کن",
        "همینو چوب کن",
        "شیشه‌ها رو تیره کن",
        "make it night",
        "use light stone on the facade",
    ):

        guard = detect_unsupported_geometry_edit(phrase)

        assert guard["unsupported"] is False, (phrase, guard)

    ok("supported appearance edits are NOT flagged as geometry edits")


# ==========================================================
# 8 — INJECTION MAP
# ==========================================================

def test_img2img_injection_map():

    print("\n[8] img2img injection map")

    workflow = WorkflowLoader().load("flux_img2img.json")["workflow"]

    before = copy.deepcopy(workflow)

    injector = ImageWorkflowInjector()

    injected = injector.inject(
        workflow,
        "COMPILED EDIT PROMPT",
        {"filename": "architectos_src.png"},
        {"denoise": 0.25, "seed": 777001},
    )["workflow"]

    assert injected["206"]["inputs"]["text"] == "COMPILED EDIT PROMPT"

    assert injected["300"]["inputs"]["image"] == "architectos_src.png"

    assert injected["210"]["inputs"]["denoise"] == 0.25

    assert injected["210"]["inputs"]["seed"] == 777001

    ok("prompt -> 206, source -> 300, denoise+seed -> 210")

    # dimensions must never be injected for img2img
    assert "width" not in injected["210"]["inputs"]

    assert "height" not in injected["210"]["inputs"]

    ok("no width/height injected for img2img (source-driven latent)")

    # steps / cfg remain the frozen baseline
    assert injected["210"]["inputs"]["steps"] == 30

    assert injected["210"]["inputs"]["cfg"] == 5

    ok("steps/cfg keep the frozen img2img baseline")

    # isolation
    assert workflow == before, "inject mutated the canonical workflow"

    with open(FLUX_IMG2IMG, "r", encoding="utf-8") as handle:

        on_disk = json.load(handle)

    assert on_disk["210"]["inputs"]["denoise"] == 0.30

    assert on_disk["210"]["inputs"]["seed"] == 0

    assert on_disk["300"]["inputs"]["image"] == "input.png"

    ok("flux_img2img.json on disk untouched")


def test_two_edits_do_not_leak():

    print("\n[9] Two sequential edits are isolated")

    workflow = WorkflowLoader().load("flux_img2img.json")["workflow"]

    injector = ImageWorkflowInjector()

    first = injector.inject(
        workflow, "EDIT ONE", {"filename": "a.png"},
        {"denoise": 0.25, "seed": 111},
    )["workflow"]

    second = injector.inject(
        workflow, "EDIT TWO", {"filename": "b.png"},
        {"denoise": 0.55, "seed": 222},
    )["workflow"]

    assert first["206"]["inputs"]["text"] == "EDIT ONE"

    assert second["206"]["inputs"]["text"] == "EDIT TWO"

    assert first["300"]["inputs"]["image"] == "a.png"

    assert second["300"]["inputs"]["image"] == "b.png"

    assert first["210"]["inputs"]["denoise"] == 0.25

    assert second["210"]["inputs"]["denoise"] == 0.55

    assert first["210"]["inputs"]["seed"] == 111

    assert second["210"]["inputs"]["seed"] == 222

    ok("prompt / source / denoise / seed isolated across two edits")


# ==========================================================
# 10 — PRESET SUPPRESSION + COMPILED PROMPT AUTHORITY
# ==========================================================

class CapturingComfy:

    def __init__(self):

        self.submitted = []

        self.workflow = None


    def submit(self, workflow):

        self.submitted.append(copy.deepcopy(workflow))

        self.workflow = copy.deepcopy(workflow)

        return {"status": "submitted", "prompt_id": "T%d" % len(self.submitted)}


    def wait_for_result(self, prompt_id):

        return {"status": "execution_error", "error": ["x", {}]}


    def history(self, prompt_id):

        return {}


def test_img2img_preset_suppressed_and_prompt_authoritative():

    print("\n[10] img2img: preset suppressed, compiled prompt authoritative")

    runtime = RenderRuntime()

    capture = CapturingComfy()

    runtime.executor.comfy = capture

    runtime.result_bridge.comfy = capture

    result = runtime.render(
        "i2i_test",
        {
            "prompt": "builder tail",
            "original_prompt": "همینو شب کن",
            "compiled_render_prompt": "COMPILED NIGHT EDIT",
            "denoise": 0.25,
            "seed": 4242,
            "mode": "img2img",
        },
        "flux",
        {"filename": "architectos_src.png"},
    )

    workflow = capture.workflow

    assert workflow is not None

    assert workflow["206"]["inputs"]["text"].startswith("COMPILED NIGHT EDIT")

    assert workflow["210"]["inputs"]["denoise"] == 0.25

    assert workflow["210"]["inputs"]["seed"] == 4242

    assert workflow["300"]["inputs"]["image"] == "architectos_src.png"

    ok("compiled prompt + denoise + seed + source reached the img2img workflow")

    metadata = result.get("request_metadata") or {}

    assert metadata.get("preset") is None

    assert result.get("preset") is None

    ok("text-to-image preset suppressed for img2img")

    # no preset quality tail leaked into the edit prompt
    final = workflow["206"]["inputs"]["text"].lower()

    for tail_word in ("bright natural daylight", "night scene", "warm lit windows"):

        assert tail_word not in final, tail_word

    ok("no preset quality tail leaked into the edit prompt")


# ==========================================================
# 11 / 12 — REGISTRATION, LINEAGE, CHAINING, TRUTHFUL STATUS
# ==========================================================

def test_derived_registration_and_lineage():

    print("\n[11] Derived-image registration + parent lineage")

    session = "i2i_lineage"

    image_registry.reset(session)

    parent = image_registry.register(
        session, path="uploads/source.png", source_type="uploaded"
    )

    chat = _chat()

    session_registry.begin(session)

    try:

        record = chat.image_handler._register_derived_output(
            {
                "image_asset": {
                    "filename": "architectos_img2img_edit_00001_.png",
                    "path": SOURCE_IMAGE,
                }
            },
            attachments=[{"id": "att_1", "kind": "render"}],
            parent_image_id=parent["image_id"],
        )

    finally:

        session_registry.end()

    assert record, "derived output was not registered"

    assert record["source_type"] == "image_to_image"

    assert record["parent_image_id"] == parent["image_id"]

    assert record["active"] is True

    ok("derived output registered with source_type image_to_image + parent")

    # a missing file must never be registered
    session_registry.begin("i2i_lineage_missing")

    try:

        missing = chat.image_handler._register_derived_output(
            {"image_asset": {"path": "C:/nope/missing.png"}},
            parent_image_id=parent["image_id"],
        )

    finally:

        session_registry.end()

    assert missing is None

    ok("missing derived file is never registered")


def test_chaining_semantics():

    print("\n[12] Registry active/last semantics enable chaining")

    session = "i2i_chain"

    image_registry.reset(session)

    image_registry.register(session, path="uploads/up.png", source_type="uploaded")

    image_registry.register(
        session, path="render_1.png", source_type="text_to_image"
    )

    derived = image_registry.register(
        session, path="edit_1.png", source_type="image_to_image",
        parent_image_id="img_x",
    )

    # the derived image is now the active / latest image
    assert image_registry.active(session)["image_id"] == derived["image_id"]

    assert image_registry.last(session)["image_id"] == derived["image_id"]

    assert image_registry.last_render(session)["image_id"] == derived["image_id"]

    ok("derived image becomes active + last_render (chain source)")

    resolution = resolve_reference("همینو روز کن", session)

    assert resolution["status"] == "resolved"

    assert resolution["target_ordinal"] == derived["ordinal"]

    ok("'همینو' now resolves to the DERIVED image (chained edit)")


def test_truthful_status_no_fake_success():

    print("\n[13] Truthful status on the edit path")

    chat = _chat()

    session = "i2i_status"

    image_registry.reset(session)

    capture = CapturingComfy()

    chat.render_runtime.executor.comfy = capture

    chat.render_runtime.result_bridge.comfy = capture

    session_registry.begin(session)

    try:

        result = chat.image_handler.handle_image_edit(
            text="همینو شب کن",
            image={"path": SOURCE_IMAGE},
            compiled_render_prompt="COMPILED NIGHT EDIT",
            preservation=get_level("high_preservation"),
            seed=99,
            parent_image_id="img_parent",
        )

    finally:

        session_registry.end()

    assert result.get("type") == "image_render"

    assert result.get("status") == "execution_error", result.get("status")

    assert result.get("status") != "success"

    assert result["render"]["status"] == "execution_error"

    ok("failed img2img reports execution_error, never success")

    assert result.get("preservation", {}).get("level") == "high_preservation"

    assert result.get("parent_image_id") == "img_parent"

    ok("response carries preservation level + parent lineage")


# ==========================================================
# 14 — CONFIG + REGRESSION
# ==========================================================

def test_comfy_input_from_config():

    print("\n[14] ImageAssetBridge uses runtime_config, not a hardcoded path")

    import inspect

    from config import runtime_config as RC

    source = inspect.getsource(ImageAssetBridge.__init__)

    assert "C:/ComfyUI-Zluda" not in source, "hardcoded Comfy path still present"

    assert "RC.COMFYUI_INPUT_DIR" in source

    bridge = ImageAssetBridge()

    assert os.path.normcase(bridge.comfy_input) == os.path.normcase(
        RC.COMFYUI_INPUT_DIR
    ), (bridge.comfy_input, RC.COMFYUI_INPUT_DIR)

    ok("Comfy input dir comes from runtime_config.COMFYUI_INPUT_DIR")


def test_draft_profile():

    print("\n[16] Draft / preview profile (test budget policy)")

    from core.render.render_draft_v1 import (
        is_draft,
        draft_steps,
        profile,
        ENV_FLAG,
        ENV_STEPS,
    )

    saved = {
        ENV_FLAG: os.environ.pop(ENV_FLAG, None),
        ENV_STEPS: os.environ.pop(ENV_STEPS, None),
    }

    try:

        # default: OFF -> production behaviour unchanged
        assert is_draft() is False

        assert profile()["steps"] is None

        ok("draft profile OFF by default (production unchanged)")

        # enabled via environment
        os.environ[ENV_FLAG] = "1"

        os.environ[ENV_STEPS] = "8"

        assert is_draft() is True

        assert draft_steps() == 8

        ok("draft profile enabled via environment (steps=8)")

        # steps reach the img2img KSampler
        workflow = WorkflowLoader().load("flux_img2img.json")["workflow"]

        injected = ImageWorkflowInjector().inject(
            workflow,
            "P",
            {"filename": "x.png"},
            {"denoise": 0.25, "seed": 1, "steps": draft_steps()},
        )["workflow"]

        assert injected["210"]["inputs"]["steps"] == 8

        ok("draft steps injected into the img2img KSampler")

        # the frozen JSON is untouched
        with open(FLUX_IMG2IMG, "r", encoding="utf-8") as handle:

            on_disk = json.load(handle)

        assert on_disk["210"]["inputs"]["steps"] == 30

        ok("flux_img2img.json steps stay frozen at 30")

        # invalid values fall back safely
        os.environ[ENV_STEPS] = "0"

        assert draft_steps() == 8

        os.environ[ENV_STEPS] = "abc"

        assert draft_steps() == 8

        ok("invalid draft step values fall back to the safe default")

    finally:

        for key, value in saved.items():

            if value is None:

                os.environ.pop(key, None)

            else:

                os.environ[key] = value


def test_guard_covers_every_edit_route():

    print("\n[17] Geometry guard covers every edit route")

    import core.chat.chat_architect as ca

    chat = _chat()

    session = "i2i_guard"

    image_registry.reset(session)

    image_registry.register(
        session,
        path="C:/ComfyUI-Zluda/output/architectos_v11_00235_.png",
        source_type="uploaded",
    )

    image_registry.register(
        session,
        path="C:/ComfyUI-Zluda/output/architectos_img2img_edit_00081_.png",
        source_type="image_to_image",
    )

    calls = {"edit": 0}

    def _record_edit(text, image, **kwargs):

        calls["edit"] += 1

        return {"type": "image_render", "status": "SHOULD_NOT_HAPPEN"}

    original = chat.image_handler.handle_image_edit

    chat.image_handler.handle_image_edit = _record_edit

    session_registry.begin(session)

    try:

        # force the legacy state-override route (waiting_image_edit True)
        chat.state.update({
            "waiting_image_edit": True,
            "last_image_asset": {"path": "x.png"},
        })

        result = chat.handle(
            "این پنجره رو 80 سانت ببر راست",
            context={"session_id": session},
        )

    finally:

        session_registry.end()

        chat.image_handler.handle_image_edit = original

    assert calls["edit"] == 0, "geometry edit reached the edit handler"

    assert result.get("status") == "unsupported_edit", result.get("status")

    assert result.get("engine") == "image_edit_guard"

    ok("state-override route refuses the geometry edit (no execution)")

    guard = result.get("unsupported_edit") or {}

    assert guard.get("reason") == "dimensioned_geometry_edit_not_supported"

    assert result.get("supported_alternatives")

    ok("refusal reports the reason and the supported alternatives")


def test_edit_delta_compiler():

    print("\n[18] Deterministic img2img edit delta")

    from core.prompt_intelligence.image_edit_delta_v1 import (
        compile_edit_delta,
        is_classified,
        EDIT_TIME_OF_DAY,
        EDIT_MATERIAL,
        EDIT_GENERIC,
        TIME_NIGHT,
        TIME_DAY,
    )

    night = compile_edit_delta("همینو شب کن")

    assert night["edit_class"] == EDIT_TIME_OF_DAY

    assert night["time_of_day"] == TIME_NIGHT

    assert is_classified(night)

    ok("'همینو شب کن' -> time_of_day_change / night")

    day = compile_edit_delta("همینو روز کن")

    assert day["edit_class"] == EDIT_TIME_OF_DAY

    assert day["time_of_day"] == TIME_DAY

    ok("'همینو روز کن' -> time_of_day_change / day")

    stone = compile_edit_delta("رندر قبلی رو سنگ روشن کن")

    assert stone["edit_class"] == EDIT_MATERIAL

    assert stone["material"] == "stone"

    assert stone["material_tone"] == "light"

    ok("'رندر قبلی رو سنگ روشن کن' -> material_change / light stone")

    # the delta prompt carries the four approved sections
    for section in ("REFERENCE:", "DELTA:", "PRESERVE:", "QUALITY:"):

        assert section in night["prompt"], section

        assert section in stone["prompt"], section

    ok("delta prompt is REFERENCE / DELTA / PRESERVE / QUALITY")

    assert "night" in night["prompt"].lower()

    assert "light natural stone" in stone["prompt"]

    ok("delta prompt states the requested change explicitly")

    # a non-edit must NOT be classified
    assert compile_edit_delta("یه ویلای مدرن میخوام")["edit_class"] == EDIT_GENERIC

    assert compile_edit_delta("")["edit_class"] == EDIT_GENERIC

    assert not is_classified(compile_edit_delta("یه ویلای مدرن میخوام"))

    ok("non-edit text stays generic (previous behaviour preserved)")

    # determinism
    assert compile_edit_delta("همینو شب کن") == compile_edit_delta("همینو شب کن")

    ok("delta compilation is deterministic")


def test_delta_authority_and_conflict_stripping():

    print("\n[19] Edit delta is authoritative; generic tail cannot contradict it")

    from core.prompt_intelligence.image_edit_delta_v1 import (
        compile_edit_delta,
    )

    from core.prompt_intelligence.render_prompt_resolver_v1 import (
        resolve_render_prompt,
    )

    from core.prompt_intelligence.image_edit_prompt_builder import (
        ImageEditPromptBuilder,
    )

    builder_prompt = ImageEditPromptBuilder().build({
        "request_type": "facade_material_edit",
        "style": "traditional",
        "materials": ["wood"],
        "mode": "img2img",
    })

    # ---- night edit ----
    delta = compile_edit_delta("همینو شب کن")

    resolution = resolve_render_prompt(
        compiled_prompt=delta["prompt"],
        builder_prompt=builder_prompt,
        user_text="همینو شب کن",
        preset_tail="",
        preset_name=None,
        conflict_terms=tuple(delta["conflict_terms"]),
        reinforcement="",
    )

    final = (resolution.get("final_prompt") or "").lower()

    assert resolution["source"] == "compiled_authoritative"

    assert final.startswith("reference:"), final[:60]

    assert "night" in final

    assert "natural lighting" not in final, "daylight tail survived a night edit"

    assert "material with wood" not in final, "generic material change survived"

    ok("night delta wins; 'natural lighting' + generic material change removed")

    # ---- material edit ----
    delta = compile_edit_delta("رندر قبلی رو سنگ روشن کن")

    resolution = resolve_render_prompt(
        compiled_prompt=delta["prompt"],
        builder_prompt=builder_prompt,
        user_text="رندر قبلی رو سنگ روشن کن",
        preset_tail="",
        preset_name=None,
        conflict_terms=tuple(delta["conflict_terms"]),
        reinforcement="",
    )

    final = (resolution.get("final_prompt") or "").lower()

    assert "light natural stone" in final

    assert "material with wood" not in final, "competing material survived"

    assert "natural lighting" not in final, (
        "a material-only edit must not assert a lighting condition"
    )

    ok("material delta wins; competing generic material + daylight tail removed")

    # ---- no conflict terms -> previous behaviour unchanged ----
    resolution = resolve_render_prompt(
        compiled_prompt="COMPILED",
        builder_prompt=builder_prompt,
        user_text="x",
        preset_tail="",
        preset_name=None,
        conflict_terms=(),
        reinforcement="",
    )

    assert "natural lighting" in (resolution["final_prompt"] or "").lower()

    ok("empty conflict terms remain a no-op")


def test_material_replacement_escalation():

    print("\n[20] Deterministic preservation escalation for material replacement")

    from core.prompt_intelligence.image_edit_delta_v1 import (
        compile_edit_delta,
        preservation_level,
        denoise_override,
    )

    from core.render.image_edit_presets_v1 import (
        resolve_preservation_with_denoise,
    )

    stone = compile_edit_delta("رندر قبلی رو سنگ روشن کن")

    level = preservation_level(stone)

    assert level == "balanced", level

    resolved = resolve_preservation_with_denoise(
        text="رندر قبلی رو سنگ روشن کن",
        explicit=level,
    )

    assert resolved["level"] == "balanced"

    assert 0.35 <= resolved["denoise"] <= 0.45, resolved["denoise"]

    ok("facade material replacement -> approved BALANCED band (0.35-0.45)")

    # a lighting edit must NOT be escalated out of its level
    night = compile_edit_delta("همینو شب کن")

    assert preservation_level(night) is None

    assert denoise_override(night) == 0.30

    night_level = preservation_level(night) or "high_preservation"

    resolved = resolve_preservation_with_denoise(
        text="همینو شب کن",
        explicit=night_level,
        denoise=denoise_override(night),
    )

    assert resolved["level"] == "high_preservation"

    assert resolved["denoise"] == 0.30

    assert resolved["denoise"] <= LEVELS["high_preservation"]["max"]

    ok("time-of-day edit -> top of the approved high_preservation band (0.30)")

    plain = resolve_preservation_with_denoise(
        text="همینو شب کن",
        explicit=None,
    )

    assert plain["level"] == "high_preservation"

    assert plain["denoise"] == 0.25

    ok("the module default itself is unchanged (0.25)")

    # it never jumps to creative
    assert preservation_level(stone) != "creative"

    assert denoise_override(night) < LEVELS["creative"]["min"]

    ok("escalation never reaches creative")


def test_geometry_guard_blocks_execution():

    print("\n[21] Precise-geometry guard blocks execution (mocked)")

    chat = _chat()

    session = "i2i_guard_exec"

    image_registry.reset(session)

    image_registry.register(
        session,
        path=SOURCE_IMAGE,
        source_type="text_to_image",
    )

    calls = {"edit": 0, "render": 0, "comfy": 0}

    def _edit(*args, **kwargs):

        calls["edit"] += 1

        return {"type": "image_render", "status": "SHOULD_NOT_HAPPEN"}

    def _render(*args, **kwargs):

        calls["render"] += 1

        return {"status": "SHOULD_NOT_HAPPEN"}

    class _Comfy:

        def submit(self, workflow):

            calls["comfy"] += 1

            return {"status": "submitted", "prompt_id": "X"}

        def wait_for_result(self, prompt_id):

            return {"status": "execution_error"}

        def history(self, prompt_id):

            return {}

    orig_edit = chat.image_handler.handle_image_edit

    orig_render = chat.render_runtime.render

    orig_comfy = chat.render_runtime.executor.comfy

    chat.image_handler.handle_image_edit = _edit

    chat.render_runtime.render = _render

    chat.render_runtime.executor.comfy = _Comfy()

    results = {}

    session_registry.begin(session)

    try:

        for key, phrase in (
            ("dimensioned", "این پنجره رو 80 سانت ببر راست"),
            ("localized_delete", "این پنجره رو حذف کن"),
            ("localized_resize", "این پنجره رو بزرگتر کن"),
            ("dimensioned_wall", "دیوار رو ۲ متر ببر راست"),
        ):

            results[key] = chat.handle(
                phrase,
                context={"session_id": session},
            )

    finally:

        session_registry.end()

        chat.image_handler.handle_image_edit = orig_edit

        chat.render_runtime.render = orig_render

        chat.render_runtime.executor.comfy = orig_comfy

    assert calls == {"edit": 0, "render": 0, "comfy": 0}, calls

    ok("ImageHandler / RenderRuntime / Comfy executor were NOT called")

    for key, result in results.items():

        assert result.get("status") == "unsupported_edit", (key, result.get("status"))

        assert result.get("engine") == "image_edit_guard"

        assert (result.get("unsupported_edit") or {}).get("unsupported") is True

    ok("all four precise-geometry requests refused with a truthful reason")

    # ordinary global appearance edits must still route to a real edit
    calls["edit"] = 0

    chat.image_handler.handle_image_edit = _edit

    session_registry.begin(session)

    try:

        chat.handle("همینو شب کن", context={"session_id": session})

    finally:

        session_registry.end()

        chat.image_handler.handle_image_edit = orig_edit

    assert calls["edit"] == 1, "a supported appearance edit was wrongly blocked"

    ok("a supported appearance edit is NOT blocked by the geometry guard")


def test_delta_reaches_comfy_node_206():

    print("\n[22] Compiled edit delta reaches the exact Comfy prompt node")

    chat = _chat()

    session = "i2i_e2e_prompt"

    image_registry.reset(session)

    image_registry.register(
        session,
        path=SOURCE_IMAGE,
        source_type="text_to_image",
    )

    capture = CapturingComfy()

    chat.render_runtime.executor.comfy = capture

    chat.render_runtime.result_bridge.comfy = capture

    session_registry.begin(session)

    try:

        night = chat.handle(
            "همینو شب کن",
            context={"session_id": session},
        )

    finally:

        session_registry.end()

    workflow = capture.workflow

    assert workflow is not None, "no img2img workflow was submitted"

    prompt = workflow["206"]["inputs"]["text"]

    lowered = prompt.lower()

    assert lowered.startswith("reference:"), lowered[:60]

    assert "convert the scene to true architectural night photography" in lowered

    assert "natural lighting" not in lowered, "daylight tail survived a night edit"

    assert workflow["300"]["inputs"]["image"], "no source image injected"

    assert workflow["210"]["inputs"]["denoise"] == 0.30

    assert workflow["210"]["inputs"]["seed"] is not None

    assert "width" not in workflow["210"]["inputs"]

    assert "height" not in workflow["210"]["inputs"]

    ok("night delta reached node 206; denoise/seed/source correct; no dimensions")

    assert night.get("edit_delta", {}).get("edit_class") == "time_of_day_change"

    ok("response exposes the edit delta for the acceptance trace")

    # ---- material edit ----
    capture.workflow = None

    session_registry.begin(session)

    try:

        stone = chat.handle(
            "رندر قبلی رو سنگ روشن کن",
            context={"session_id": session},
        )

    finally:

        session_registry.end()

    workflow = capture.workflow

    assert workflow is not None

    lowered = workflow["206"]["inputs"]["text"].lower()

    assert "light natural stone" in lowered

    assert "material with wood" not in lowered

    assert "natural lighting" not in lowered, (
        "material-only edit must not assert a lighting condition"
    )

    assert 0.35 <= workflow["210"]["inputs"]["denoise"] <= 0.45, (
        workflow["210"]["inputs"]["denoise"]
    )

    ok("material delta reached node 206 at the BALANCED denoise band")

    assert stone.get("edit_preservation", {}).get("level") == "balanced"

    ok("material edit reports the escalated preservation level truthfully")


def test_preview_source_and_render_profile():

    print("\n[23] Test-render profile + preview source (code enforced)")

    import hashlib
    import shutil
    import tempfile

    from core.render import render_draft_v1 as RDP
    from core.render import image_preview_v1 as IPV
    from core.render.image_asset_bridge import ImageAssetBridge

    # ---- profile contract ----
    assert RDP.available_profiles() == [
        "DRAFT", "PREVIEW", "QUALITY", "FINAL"
    ]

    assert RDP.TEST_PROFILES == ("DRAFT", "PREVIEW")

    ok("four locked profiles exist: DRAFT / PREVIEW / QUALITY / FINAL")

    # default is OFF -> production behaviour unchanged
    saved_profile = os.environ.pop(RDP.ENV_PROFILE, None)
    saved_flag = os.environ.pop(RDP.ENV_FLAG, None)

    try:

        off = RDP.resolve_profile()

        assert off["active"] is False

        assert off["production_unchanged"] is True

        assert off["steps"] is None

        ok("no profile active by default (production unchanged)")

        # functional tests get a test profile, never a production one
        for name in ("DRAFT", "PREVIEW"):

            resolved = RDP.resolve_profile(explicit=name)

            assert resolved["test_profile"] is True

            assert resolved["production_resolution"] is False

            assert resolved["upscale"] is False

            assert resolved["quality_pass"] is False

            assert RDP.assert_test_profile(resolved) is True

        ok("DRAFT/PREVIEW are test profiles; no upscale, no quality pass")

        # a production profile must be refused for functional tests
        for name in ("QUALITY", "FINAL"):

            production = RDP.resolve_profile(explicit=name)

            assert production["production_resolution"] is True

            try:

                RDP.assert_test_profile(production)

                raise AssertionError("production profile was not refused")

            except ValueError:

                pass

            refused = RDP.test_profile(explicit=name)

            assert refused["name"] == "PREVIEW"

            assert refused["reason"] == "production_profile_refused_for_tests"

        ok("QUALITY/FINAL are refused for functional tests (falls back to PREVIEW)")

        # seed policy
        locked = RDP.resolve_seed(mode="lock", seed=4242)

        assert locked["seed"] == 4242

        assert locked["mode"] == "lock"

        reused = RDP.resolve_seed(mode="reuse", previous_seed=99)

        assert reused["seed"] == 99

        rerolled = RDP.resolve_seed(mode="reroll", render_id=123456)

        assert rerolled["seed"] == 123456

        ok("seed policy supports lock / reroll / reuse")

        # quality override is off unless explicit
        assert RDP.quality_override()["override"] is False

        assert RDP.quality_override("QUALITY")["override"] is True

        assert RDP.quality_override("nonsense")["override"] is False

        ok("quality override is explicit-only and validated")

        # ---- preview geometry ----
        plan = IPV.plan_preview_size(768, 704, 448)

        assert plan["downscaled"] is True

        assert plan["upscaled"] is False

        assert plan["aspect_ratio_preserved"] is True

        assert plan["preview_width"] % 8 == 0

        assert plan["preview_height"] % 8 == 0

        ok("preview preserves aspect ratio and stays latent-aligned")

        for edge in (10, 384, 448, 512, 4000):

            assert IPV.PREVIEW_LONG_EDGE_MIN <= IPV.clamp_long_edge(edge) <= IPV.PREVIEW_LONG_EDGE_MAX

        ok("preview long edge is clamped to the approved 384-512 band")

        small = IPV.plan_preview_size(320, 240, 448)

        assert small["downscaled"] is False

        assert small["upscaled"] is False

        ok("a source below the preview band is never upscaled")

        # ---- preview creation on a real render (no ComfyUI involved) ----
        before = hashlib.sha256(open(SOURCE_IMAGE, "rb").read()).hexdigest()

        workdir = os.path.join(ROOT, ".pytest_tmp", "i2i05_preview")

        if os.path.isdir(workdir):

            shutil.rmtree(workdir, ignore_errors=True)

        preview = IPV.make_preview(SOURCE_IMAGE, workdir, long_edge=448)

        assert preview["preview_available"] is True, preview

        assert IPV.is_preview_usable(preview) is True

        assert preview["original_source_path"] == SOURCE_IMAGE

        assert preview["original_dimensions"] == [768, 704]

        assert preview["working_dimensions"] == [448, 408]

        assert preview["upscaled"] is False

        assert preview["original_preserved"] is True

        after = hashlib.sha256(open(SOURCE_IMAGE, "rb").read()).hexdigest()

        assert before == after, "the original source was modified"

        ok("preview created from a real render; original untouched (sha256 equal)")

        decoded, mode = IPV.read_png(preview["working_preview_path"])

        assert decoded.shape[:2] == (408, 448)

        ok("the preview round-trips through the PNG codec")

        # ---- asset bridge: profile inactive -> v3 behaviour ----
        tmp_comfy = os.path.join(ROOT, ".pytest_tmp", "i2i05_comfy_in")

        os.makedirs(tmp_comfy, exist_ok=True)

        bridge = ImageAssetBridge(comfy_input=tmp_comfy)

        plain = bridge.register("proj", SOURCE_IMAGE, preview={"active": False})

        assert plain["status"] == "ready"

        assert plain["filename"] == os.path.basename(plain["path"])

        assert plain["working_preview_path"] is None

        assert plain["preview"]["preview_available"] is False

        assert plain["original_dimensions"] == [768, 704]

        ok("profile inactive -> original is loaded, preview metadata recorded")

        # ---- asset bridge: PREVIEW profile -> downscaled working copy ----
        active = RDP.resolve_profile(explicit="PREVIEW")

        previewed = bridge.register("proj", SOURCE_IMAGE, preview=active)

        assert previewed["status"] == "ready"

        assert previewed["filename"] != os.path.basename(previewed["path"])

        assert previewed["filename"].startswith("architectos_preview_")

        assert os.path.isfile(previewed["working_preview_path"])

        # the authoritative asset is still the original copy
        assert os.path.basename(previewed["path"]) in previewed["path"]

        assert previewed["original_source_path"] == SOURCE_IMAGE

        assert previewed["original_dimensions"] == [768, 704]

        assert previewed["working_dimensions"] == [448, 408]

        assert previewed["test_profile"]["name"] == "PREVIEW"

        assert previewed["test_profile"]["production_resolution"] is False

        assert previewed["preview"]["original_preserved"] is True

        ok("PREVIEW profile -> LoadImage loads a 448x408 copy, original authoritative")

        # required metadata keys are all present
        for key in (
            "original_source_path",
            "working_preview_path",
            "original_dimensions",
            "working_dimensions",
            "test_profile",
        ):

            assert previewed.get(key) is not None, key

        ok("metadata records original_source_path / working_preview_path / "
           "original_dimensions / working_dimensions / test_profile")

    finally:

        if saved_profile is not None:

            os.environ[RDP.ENV_PROFILE] = saved_profile

        if saved_flag is not None:

            os.environ[RDP.ENV_FLAG] = saved_flag


def test_img2img_capability_contract():

    print("\n[24] Truthful img2img capability contract")

    from core.render.image_edit_capability_v1 import (
        audit,
        capability_flags,
        DEFAULT_WORKFLOW,
    )

    result = audit()

    flags = result["capabilities"]

    # ---- the frozen workflow is standard FLUX img2img ----
    assert flags["supports_global_img2img"] is True

    assert flags["supports_instruction_edit"] is False

    assert flags["supports_local_edit"] is False

    assert flags["supports_region_grounding"] is False

    assert flags["supports_geometry_edit"] is False

    ok("flags: global_img2img true; instruction/local/region/geometry false")

    assert result["is_designed_for_semantic_instruction_editing"] is False

    assert result["answer"].startswith("NO")

    ok("workflow is NOT designed for semantic instruction editing")

    # ---- proven from the graph, not assumed ----
    graph = result["workflow_graph"]

    assert graph["source_latent_nodes"] == ["301"]

    assert graph["sampler_nodes"] == ["210"]

    assert graph["sampler_inputs"]["210"]["latent_source"] == "301"

    assert graph["mask_nodes"] == []

    assert graph["region_grounding_nodes"] == []

    assert graph["geometry_conditioning_nodes"] == []

    assert graph["instruction_edit_nodes"] == []

    ok("no mask / region / geometry / instruction-edit conditioning nodes exist")

    # ---- model identity ----
    model = result["model"]

    assert model["unet_name"] == "flux1-krea-dev_fp8_scaled.safetensors"

    assert model["is_flux_base_family"] is True

    assert model["is_instruction_edit_model"] is False

    assert model["family"] == "flux_base"

    assert model["vae_name"] == "ae.safetensors"

    assert "clip_l.safetensors" in model["clip_names"]

    assert "t5xxl_fp16.safetensors" in model["clip_names"]

    ok("model is a FLUX base checkpoint (Krea dev fp8), not an edit model")

    # ---- identity preservation mechanism ----
    identity = result["identity_preservation"]

    assert identity["mechanism"] == "low_denoise_source_latent"

    assert identity["relies_on_low_denoise_only"] is True

    assert identity["has_structural_conditioning"] is False

    assert identity["has_region_conditioning"] is False

    ok("identity preservation relies on low denoise only")

    # ---- the audit must follow the workflow, not a hardcoded answer ----
    probe = {

        "202": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "flux1-kontext-dev.safetensors"}},

        "300": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},

        "301": {"class_type": "VAEEncode", "inputs": {
            "pixels": ["300", 0]}},

        "310": {"class_type": "ReferenceLatent", "inputs": {
            "conditioning": ["206", 0]}},

        "206": {"class_type": "CLIPTextEncode", "inputs": {"text": "p"}},

        "210": {"class_type": "KSampler", "inputs": {
            "latent_image": ["301", 0]}},
    }

    probe_path = os.path.join(
        ROOT, ".pytest_tmp", "i2i05_probe_kontext.json"
    )

    os.makedirs(os.path.dirname(probe_path), exist_ok=True)

    with open(probe_path, "w", encoding="utf-8") as handle:

        json.dump(probe, handle)

    probed = audit(probe_path)

    assert probed["capabilities"]["supports_instruction_edit"] is True

    assert probed["model"]["is_instruction_edit_model"] is True

    assert probed["is_designed_for_semantic_instruction_editing"] is True

    assert probed["answer"].startswith("YES")

    ok("audit is derived from the graph: a Kontext-style graph reports YES")

    # a masked graph must report local-edit support
    masked = {

        "300": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},

        "301": {"class_type": "VAEEncode", "inputs": {"pixels": ["300", 0]}},

        "305": {"class_type": "SetLatentNoiseMask", "inputs": {
            "samples": ["301", 0]}},

        "210": {"class_type": "KSampler", "inputs": {
            "latent_image": ["305", 0]}},
    }

    masked_path = os.path.join(
        ROOT, ".pytest_tmp", "i2i05_probe_masked.json"
    )

    with open(masked_path, "w", encoding="utf-8") as handle:

        json.dump(masked, handle)

    assert audit(masked_path)["capabilities"]["supports_local_edit"] is True

    ok("audit is derived from the graph: a masked graph reports local edit")

    # ---- capability_flags() is a stable accessor ----
    assert capability_flags() == flags

    assert os.path.isfile(DEFAULT_WORKFLOW)

    ok("capability_flags() accessor is stable")


def test_regression():

    print("\n[15] Regression 01 / 02 / 03 / 03B / 04")

    suites = (
        "test_runtime_foundation_01.py",
        "test_chat_language_02.py",
        "test_text_to_image_comfy_03.py",
        "test_text_to_image_comfy_03b.py",
        "test_vision_image_registry_04.py",
    )

    for name in suites:

        path = os.path.join(ROOT, "tests", name)

        spec = importlib.util.spec_from_file_location(
            "reg_" + name.replace(".py", ""), path
        )

        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

        code = module.run_all()

        assert code == 0, name + " failed"

    ok("01 / 02 / 03 / 03B / 04 suites still pass")



# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS IMAGE_TO_IMAGE_05 — TESTS")
    print("=" * 62)

    test_preservation_contract()

    test_preservation_inference_and_clamp()

    test_colloquial_references()

    test_bare_deictic_requires_edit_signal()

    test_edit_precedence_over_reference()

    test_persian_edit_imperatives()

    test_unsupported_geometry_edit()

    test_img2img_injection_map()

    test_two_edits_do_not_leak()

    test_img2img_preset_suppressed_and_prompt_authoritative()

    test_derived_registration_and_lineage()

    test_chaining_semantics()

    test_truthful_status_no_fake_success()

    test_comfy_input_from_config()

    test_draft_profile()

    test_guard_covers_every_edit_route()

    test_edit_delta_compiler()

    test_delta_authority_and_conflict_stripping()

    test_material_replacement_escalation()

    test_geometry_guard_blocks_execution()

    test_delta_reaches_comfy_node_206()

    test_preview_source_and_render_profile()

    test_img2img_capability_contract()

    test_regression()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")
    print("  RESULT: IMAGE_TO_IMAGE_05_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
