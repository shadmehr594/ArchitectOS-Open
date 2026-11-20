# ==========================================================
# ArchitectOS TEXT_TO_IMAGE_COMFY_03 — Contract Tests
#
#  1. preset contract (6 presets, allowed fields only)
#  2. preset selection (explicit > inferred > default > none)
#  3. preset must NOT override user architectural content
#  4. prompt composition (compiled authoritative + preset tail)
#  5. workflow injection map (flux.json node/key mapping)
#  6. safe workflow mutation / cross-request isolation
#  7. truthful result contract (incl. output_missing)
#  8. request metadata
#  9. no secrets exposed
#
# NO REAL IMAGE GENERATION IS PERFORMED HERE.
# ==========================================================


import copy
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


from core.render.render_preset_v1 import (
    PRESETS,
    DEFAULT_PRESET,
    available_presets,
    get_preset,
    build_quality_tail,
    render_params,
    infer_preset,
    resolve_preset,
)

from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
    augment_compiled_prompt,
)

from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

from core.render.workflow_loader import WorkflowLoader
from core.render.workflow_injector import WorkflowInjector
from core.render.render_runtime import RenderRuntime

from core.render.comfy_http_runtime import ComfyHTTPRuntime



PASS = []

FLUX_PATH = os.path.join(
    ROOT,
    "core",
    "render",
    "workflows",
    "flux.json"
)



def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)



def has_persian(text):

    return any(
        "\u0600" <= ch <= "\u06FF"
        for ch in str(text or "")
    )



# ==========================================================
# 1. PRESET CONTRACT
# ==========================================================

REQUIRED_PRESETS = (
    "exterior_day",
    "exterior_sunset",
    "exterior_night",
    "exterior_night_tall",
    "interior_day",
    "interior_warm",
    "concept_architectural",
)

ALLOWED_KEYS = {
    "label",
    "width",
    "height",
    "steps",
    "seed_mode",
    "seed",
    "quality_tail",
    "tags",
}


def test_preset_contract():

    print("\n[1] Preset contract")

    for name in REQUIRED_PRESETS:

        assert name in PRESETS, "missing preset: " + name

        preset = PRESETS[name]

        # only allowed fields may be present
        for key in preset:

            assert key in ALLOWED_KEYS, (
                name + " has disallowed field: " + key
            )

        # dimensions must be latent-safe multiples of 8
        assert preset["width"] % 8 == 0, name
        assert preset["height"] % 8 == 0, name

        assert preset["width"] > 0 and preset["height"] > 0

        assert preset["steps"] > 0

        assert preset["seed_mode"] in ("random", "fixed")

        assert preset["quality_tail"].strip()

        assert isinstance(preset["tags"], dict)

    assert len(available_presets()) == len(REQUIRED_PRESETS)

    ok(
        str(len(REQUIRED_PRESETS))
        + " presets, allowed fields only, latent-safe dimensions"
    )


def test_no_per_preset_workflow_files():

    print("\n[2] One workflow file only")

    workflow_dir = os.path.join(
        ROOT, "core", "render", "workflows"
    )

    files = sorted(
        f for f in os.listdir(workflow_dir)
        if f.endswith(".json")
    )

    assert files == [
        "flux.json",
        "flux_img2img.json",
        "wan_i2v.json",
    ], files

    ok("no per-preset workflow JSON created (flux.json only)")


# ==========================================================
# 3. PRESET SELECTION
# ==========================================================

def _infer(text):

    return infer_preset(
        normalize_architectural_terms(text)
    )


def test_preset_selection():

    print("\n[3] Preset selection (deterministic)")

    expected = {

        "نمای شب": "exterior_night",

        "فضای داخلی با نور گرم": "interior_warm",

        "رندر نمای ویلا در روز": "exterior_day",

        "رندر فضای داخلی در روز": "interior_day",

        "رندر نمای ویلا در غروب": "exterior_sunset",

        "یک رندر از نمای ویلا در شب": "exterior_night",
    }

    for text, want in expected.items():

        name, reason = _infer(text)

        assert name == want, (
            text + " -> " + str(name) + " (expected " + want + ")"
        )

        print("     " + want.ljust(22) + text)

    ok("required Persian preset examples resolve correctly")

    # ambiguous -> safe default for exterior render requests
    name, reason = _infer("رندر نمای ویلا")

    assert name == DEFAULT_PRESET, (name, reason)

    ok("ambiguous exterior render -> safe default " + DEFAULT_PRESET)

    # non-architectural text -> no preset (generic behaviour kept)
    name, reason = _infer("سلام، حالت چطوره؟")

    assert name is None, (name, reason)

    ok("non-architectural text -> no preset")


def test_explicit_preset_wins():

    print("\n[4] Explicit preset beats inference")

    terminology = normalize_architectural_terms(
        "رندر نمای ویلا در شب"
    )

    inferred = resolve_preset(terminology=terminology)

    assert inferred["name"] == "exterior_night"

    explicit = resolve_preset(
        terminology=terminology,
        explicit="concept_architectural"
    )

    assert explicit["name"] == "concept_architectural"

    assert explicit["source"] == "explicit"

    ok("explicit preset parameter overrides inferred preset")

    # unknown explicit value falls back to inference, and is recorded
    fallback = resolve_preset(
        terminology=terminology,
        explicit="not_a_real_preset"
    )

    assert fallback["name"] == "exterior_night"

    assert fallback["rejected_explicit"] == "not_a_real_preset"

    ok("unknown explicit preset falls back and is reported")


# ==========================================================
# 5. PRESET MUST NOT OVERRIDE USER CONTENT
# ==========================================================

FORBIDDEN_IN_TAIL = (
    "villa",
    "apartment",
    "tower",
    "complex",
    "modern style",
    "classical",
    "minimal style",
    "traditional",
    "glass",
    "stone",
    "brick",
    "wood",
    "concrete",
    "metal",
    "travertine",
    "camera angle",
    "low angle",
    "high angle",
    "aerial",
    "perspective",
    "frontal",
)


# A preset tail may describe its OWN time-of-day / space, but it must
# never contradict the preset it belongs to (that is what would
# override an explicit user day/night/interior/exterior request).
_DAY_WORDS = ("daylit", "daylight", "day render")

_NIGHT_WORDS = ("night",)

_INTERIOR_WORDS = ("interior",)

_EXTERIOR_WORDS = ("exterior",)


def test_preset_tail_does_not_override():

    print("\n[5] Preset tail cannot override user content")

    for name in available_presets():

        tail = build_quality_tail(name).lower()

        # ---- never restate user-owned architectural content ----
        for forbidden in FORBIDDEN_IN_TAIL:

            assert forbidden not in tail, (
                name + " quality tail contains '" + forbidden + "'"
            )

        # ---- never contradict its own time-of-day / space ----
        preset = get_preset(name)

        time_of_day = (preset.get("tags") or {}).get("time_of_day")

        space = (preset.get("tags") or {}).get("space")

        if time_of_day == "night":

            for word in _DAY_WORDS:

                assert word not in tail, (
                    name + " (night) contradicts with '" + word + "'"
                )

        if time_of_day == "day":

            for word in _NIGHT_WORDS:

                assert word not in tail, (
                    name + " (day) contradicts with '" + word + "'"
                )

        if space == "exterior":

            for word in _INTERIOR_WORDS:

                assert word not in tail, (
                    name + " (exterior) contradicts with '" + word + "'"
                )

        if space == "interior":

            for word in _EXTERIOR_WORDS:

                assert word not in tail, (
                    name + " (interior) contradicts with '" + word + "'"
                )

    ok("no preset tail restates building type / style / material / camera")


def test_preset_tail_never_contradicts_selected_preset():

    print("\n[5b] Preset tail is always consistent with its own tags")

    for name in available_presets():

        preset = get_preset(name)

        assert preset.get("quality_tail")

        assert isinstance(preset.get("tags"), dict)

        assert preset["tags"].get("time_of_day")

        assert preset["tags"].get("space")

    ok("every preset carries self-consistent time_of_day / space tags")


def test_compiled_prompt_stays_authoritative():

    print("\n[6] Compiled prompt stays authoritative")

    compiled = "south facade of a villa with glass material"

    merged = resolve_render_prompt(
        compiled_prompt=compiled,
        builder_prompt="",
        preset_tail=build_quality_tail("exterior_night")
    )

    assert merged["prompt"].startswith(compiled), merged["prompt"]

    assert merged["compiled_consumed"] is True

    assert merged["source"] == "compiled_authoritative"

    assert "night scene" in merged["prompt"]

    ok("final prompt = compiled content first + preset quality tail")


def test_prompt_composition_deduplicates():

    print("\n[7] Prompt composition deduplicates")

    merged = resolve_render_prompt(
        compiled_prompt="photorealistic architectural exterior",
        builder_prompt="photorealistic architectural exterior, 35mm lens",
        preset_tail="photorealistic architectural exterior, clear sky"
    )

    text = merged["prompt"]

    assert text.lower().count("photorealistic architectural exterior") == 1, text

    assert "35mm lens" in text

    assert "clear sky" in text

    ok("duplicate segments across compiled / preset / builder are collapsed")


# ==========================================================
# 8. WORKFLOW INJECTION MAP
# ==========================================================

def test_injection_map():

    print("\n[8] flux.json injection map")

    loader = WorkflowLoader()

    loaded = loader.load("flux.json")

    assert loaded["status"] == "loaded"

    workflow = loaded["workflow"]

    # canonical mapping of the frozen flux.json
    assert workflow["206"]["class_type"] == "CLIPTextEncode"

    assert workflow["212"]["class_type"] == "CLIPTextEncode"

    assert workflow["211"]["class_type"] == "EmptyLatentImage"

    assert workflow["210"]["class_type"] == "KSampler"

    assert workflow["9"]["class_type"] == "SaveImage"

    # KSampler graph routing identifies 206 as positive, 212 as negative
    injector = WorkflowInjector()

    positive, negative = injector.detect_clip_routes(workflow)

    assert positive == {"206"}, positive

    assert negative == {"212"}, negative

    ok("prompt -> CLIPTextEncode 206 (positive) / 212 (negative)")

    ok("dimensions -> EmptyLatentImage 211 ; steps/seed -> KSampler 210")


def test_injection_values():

    print("\n[9] Injected values land on the right nodes")

    loader = WorkflowLoader()

    injector = WorkflowInjector()

    workflow = loader.load("flux.json")["workflow"]

    context = {

        "seed": 424242,
        "width": 704,
        "height": 768,
        "steps": 22,

    }

    result = injector.inject(
        workflow,
        "TEST POSITIVE PROMPT",
        context,
        negative_prompt="TEST NEGATIVE PROMPT"
    )

    injected = result["workflow"]

    assert injected["206"]["inputs"]["text"] == "TEST POSITIVE PROMPT"

    assert injected["212"]["inputs"]["text"] == "TEST NEGATIVE PROMPT"

    assert injected["211"]["inputs"]["width"] == 704

    assert injected["211"]["inputs"]["height"] == 768

    assert injected["210"]["inputs"]["steps"] == 22

    assert injected["210"]["inputs"]["seed"] == 424242

    ok("prompt / negative / dimensions / steps / seed all injected correctly")


def test_invalid_dimensions_refused():

    print("\n[10] Invalid dimensions are refused, not corrupted")

    loader = WorkflowLoader()

    injector = WorkflowInjector()

    workflow = loader.load("flux.json")["workflow"]

    original_w = workflow["211"]["inputs"]["width"]

    original_h = workflow["211"]["inputs"]["height"]

    injected = injector.inject(
        workflow,
        "p",
        {"width": 737, "height": -64, "steps": 0}
    )["workflow"]

    assert injected["211"]["inputs"]["width"] == original_w

    assert injected["211"]["inputs"]["height"] == original_h

    assert injected["210"]["inputs"]["steps"] == 20

    ok("non-multiple-of-8 / invalid dimensions and steps are refused")


# ==========================================================
# 11. SAFE WORKFLOW MUTATION / ISOLATION
# ==========================================================

def test_canonical_workflow_not_mutated():

    print("\n[11] Canonical workflow object is never mutated in place")

    loader = WorkflowLoader()

    injector = WorkflowInjector()

    workflow = loader.load("flux.json")["workflow"]

    before = copy.deepcopy(workflow)

    injector.inject(
        workflow,
        "MUTATION TEST PROMPT",
        {"seed": 999999, "width": 512, "height": 512, "steps": 40},
        negative_prompt="MUTATION NEGATIVE"
    )

    assert workflow == before, (
        "inject() mutated the caller's workflow object"
    )

    ok("inject() operates on a deep copy (caller object untouched)")

    # the on-disk canonical file must also be untouched
    with open(FLUX_PATH, "r", encoding="utf-8") as f:

        on_disk = json.load(f)

    assert on_disk["211"]["inputs"]["width"] == 736

    assert on_disk["211"]["inputs"]["height"] == 704

    assert on_disk["210"]["inputs"]["seed"] == 123456789

    assert on_disk["210"]["inputs"]["steps"] == 20

    assert on_disk["206"]["inputs"]["text"] == "a modern villa in a cinematic style"

    ok("flux.json on disk unchanged after injection")


def test_two_sequential_renders_do_not_leak():

    print("\n[12] Two sequential renders cannot leak state")

    loader = WorkflowLoader()

    injector = WorkflowInjector()

    workflow = loader.load("flux.json")["workflow"]

    first = injector.inject(
        workflow,
        "FIRST PROMPT",
        {"seed": 111, "width": 768, "height": 704, "steps": 20},
        negative_prompt="FIRST NEGATIVE"
    )["workflow"]

    second = injector.inject(
        workflow,
        "SECOND PROMPT",
        {"seed": 222, "width": 704, "height": 768, "steps": 24},
        negative_prompt="SECOND NEGATIVE"
    )["workflow"]

    # prompt
    assert first["206"]["inputs"]["text"] == "FIRST PROMPT"

    assert second["206"]["inputs"]["text"] == "SECOND PROMPT"

    assert first["212"]["inputs"]["text"] == "FIRST NEGATIVE"

    assert second["212"]["inputs"]["text"] == "SECOND NEGATIVE"

    # seed
    assert first["210"]["inputs"]["seed"] == 111

    assert second["210"]["inputs"]["seed"] == 222

    # dimensions
    assert (first["211"]["inputs"]["width"], first["211"]["inputs"]["height"]) == (768, 704)

    assert (second["211"]["inputs"]["width"], second["211"]["inputs"]["height"]) == (704, 768)

    # steps
    assert first["210"]["inputs"]["steps"] == 20

    assert second["210"]["inputs"]["steps"] == 24

    ok("prompt / seed / dimensions / steps isolated across two renders")


class CapturingComfy:
    """Records the exact workflow submitted, without any generation."""

    def __init__(self):

        self.submitted = []


    def submit(self, workflow):

        self.submitted.append(copy.deepcopy(workflow))

        return {
            "status": "submitted",
            "prompt_id": "TEST_" + str(len(self.submitted)),
        }


    def wait_for_result(self, prompt_id):

        return {
            "status": "execution_error",
            "error": ["execution_error", {"node": "test"}],
        }


    def history(self, prompt_id):

        return {}


def test_runtime_level_preset_isolation():

    print("\n[13] RenderRuntime-level preset isolation")

    runtime = RenderRuntime()

    capture = CapturingComfy()

    runtime.executor.comfy = capture

    runtime.result_bridge.comfy = capture

    runtime.render(
        "iso_a",
        {
            "prompt": "builder prompt A",
            "compiled_render_prompt": "COMPILED A",
            "preset": "exterior_night",
            "mode": "text2img",
        },
        "flux",
        None
    )

    runtime.render(
        "iso_b",
        {
            "prompt": "builder prompt B",
            "compiled_render_prompt": "COMPILED B",
            "preset": "interior_day",
            "mode": "text2img",
        },
        "flux",
        None
    )

    assert len(capture.submitted) == 2

    first, second = capture.submitted

    assert "COMPILED A" in first["206"]["inputs"]["text"]

    assert "COMPILED B" in second["206"]["inputs"]["text"]

    assert "COMPILED B" not in first["206"]["inputs"]["text"]

    assert "COMPILED A" not in second["206"]["inputs"]["text"]

    assert first["210"]["inputs"]["seed"] != second["210"]["inputs"]["seed"]

    # exterior_night 768x704 vs interior_day 704x768
    assert (first["211"]["inputs"]["width"], first["211"]["inputs"]["height"]) == (768, 704)

    assert (second["211"]["inputs"]["width"], second["211"]["inputs"]["height"]) == (704, 768)

    ok("two sequential RenderRuntime renders are fully isolated")


# ==========================================================
# 14. TRUTHFUL RESULT CONTRACT + METADATA
# ==========================================================

def test_truthful_statuses_preserved():

    print("\n[14] Truthful status contract")

    runtime = RenderRuntime()

    # output_missing: asset exists flag False
    assert runtime._resolve_render_status(
        {"status": "completed"},
        {"status": "success", "image_asset": {"filename": "x.png", "exists": False}}
    ) == "output_missing"

    # real asset present
    assert runtime._resolve_render_status(
        {"status": "completed"},
        {"status": "success", "image_asset": {"filename": "x.png", "exists": True}}
    ) == "success"

    # legacy asset without the flag -> unchanged behaviour
    assert runtime._resolve_render_status(
        {"status": "completed"},
        {"status": "success", "image_asset": {"filename": "x.png"}}
    ) == "success"

    for status in (
        "submit_error",
        "execution_error",
        "timeout",
        "completed_no_image",
    ):

        assert runtime._resolve_render_status(
            {"status": status}, {}
        ) == status

    ok("submit_error / execution_error / timeout / completed_no_image / output_missing preserved")


def test_request_metadata():

    print("\n[15] Request metadata")

    runtime = RenderRuntime()

    capture = CapturingComfy()

    runtime.executor.comfy = capture

    runtime.result_bridge.comfy = capture

    result = runtime.render(
        "meta_test",
        {
            "prompt": "builder tail",
            "compiled_render_prompt": "COMPILED META",
            "preset": "exterior_sunset",
            "mode": "text2img",
        },
        "flux",
        None
    )

    metadata = result.get("request_metadata")

    assert isinstance(metadata, dict), metadata

    for key in (
        "preset",
        "final_prompt",
        "workflow_name",
        "seed",
        "width",
        "height",
        "prompt_source",
        "output_asset",
        "execution_status",
    ):

        assert key in metadata, "metadata missing: " + key

    assert metadata["preset"] == "exterior_sunset"

    assert metadata["workflow_name"] == "flux.json"

    assert metadata["width"] == 768

    assert metadata["height"] == 704

    assert metadata["prompt_source"] == "compiled_authoritative"

    assert metadata["execution_status"] == "execution_error"

    assert "COMPILED META" in metadata["final_prompt"]

    assert not has_persian(metadata["final_prompt"])

    ok("metadata exposes preset/prompt/workflow/seed/size/source/status")


def test_no_secrets_in_metadata():

    print("\n[16] No secrets or credentials exposed")

    runtime = RenderRuntime()

    capture = CapturingComfy()

    runtime.executor.comfy = capture

    runtime.result_bridge.comfy = capture

    result = runtime.render(
        "secret_test",
        {
            "prompt": "b",
            "compiled_render_prompt": "C",
            "preset": "exterior_day",
            "mode": "text2img",
        },
        "flux",
        None
    )

    blob = json.dumps(
        result.get("request_metadata") or {},
        ensure_ascii=False,
        default=str
    ).lower()

    for needle in (
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "authorization",
        "bearer",
    ):

        assert needle not in blob, "metadata leaked: " + needle

    ok("metadata contains no credentials")


# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS TEXT_TO_IMAGE_COMFY_03 — TESTS")
    print("=" * 62)

    test_preset_contract()

    test_no_per_preset_workflow_files()

    test_preset_selection()

    test_explicit_preset_wins()

    test_preset_tail_does_not_override()

    test_preset_tail_never_contradicts_selected_preset()

    test_compiled_prompt_stays_authoritative()

    test_prompt_composition_deduplicates()

    test_injection_map()

    test_injection_values()

    test_invalid_dimensions_refused()

    test_canonical_workflow_not_mutated()

    test_two_sequential_renders_do_not_leak()

    test_runtime_level_preset_isolation()

    test_truthful_statuses_preserved()

    test_request_metadata()

    test_no_secrets_in_metadata()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")
    print("  RESULT: TEXT_TO_IMAGE_COMFY_03_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
