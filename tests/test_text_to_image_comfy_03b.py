# ==========================================================
# ArchitectOS TEXT_TO_IMAGE_COMFY_03B — Preset Quality Closure Tests
#
# Closes the two confirmed quality issues:
#   (2) exterior_day produced dusk/golden-hour instead of clear day
#   (3) interior_warm produced an exterior facade composition
#
# Verifies PRESET-AWARE TAIL FILTERING:
#   - only conflicting GENERIC builder filler is removed
#   - compiled_render_prompt is NEVER filtered (user content safe)
#   - preset's own tail / reinforcement is never filtered
#   - required trace fields are recorded
#
# NO REAL IMAGE GENERATION IS PERFORMED HERE.
# ==========================================================


import json
import os
import sys


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


from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
    filter_tail_segments,
)

from core.render.render_preset_v1 import (
    build_quality_tail,
    tail_conflicts,
    tail_reinforcement,
    available_presets,
)

from core.render.render_runtime import RenderRuntime



PASS = []



def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)



# The REAL generic builder tail observed in the 03 acceptance run.
REAL_BUILDER_TAIL = (
    "modern villa architectural visualization, single floor building, "
    "approved facade design: modern, simple geometry, clean lines, "
    "horizontal composition, functional expression, material contrast, "
    "minimal expression, simple volumes, flat roof, open plan, "
    "large openings, glass surfaces, minimal details, controlled asymmetry, "
    "horizontal lines, vertical fins, clean vertical planes, "
    "solid void contrast, UNKNOWN, recessed openings, large glazing, "
    "large windows, minimal parapet, deep frames, minimal modern architecture, "
    "glass facade, natural stone materials, architectural photography, "
    "35mm lens, golden hour natural lighting, cinematic realistic render, "
    "physically accurate materials, 8k ultra realistic"
)


def compose(preset_name, compiled="USER COMPILED ARCHITECTURAL CONTENT"):

    return resolve_render_prompt(
        compiled_prompt=compiled,
        builder_prompt=REAL_BUILDER_TAIL,
        preset_tail=build_quality_tail(preset_name),
        preset_name=preset_name,
        conflict_terms=tail_conflicts(preset_name),
        reinforcement=tail_reinforcement(preset_name),
    )



# ==========================================================
# 1. CONFLICT TABLES
# ==========================================================

def test_conflict_tables_exist():

    print("\n[1] Preset conflict tables")

    for name in (
        "exterior_day",
        "exterior_sunset",
        "exterior_night",
        "interior_day",
        "interior_warm",
    ):

        assert tail_conflicts(name), name + " has no conflict terms"

    # neutral studio preset must not filter architectural framing
    assert tail_conflicts("concept_architectural") == ("unknown",)

    # interior presets reinforce the interior viewpoint
    for name in ("interior_day", "interior_warm"):

        reinforcement = tail_reinforcement(name)

        assert "interior viewpoint" in reinforcement

        assert "camera inside the room" in reinforcement

    # exterior presets need no reinforcement (their tail is explicit)
    for name in ("exterior_day", "exterior_sunset", "exterior_night"):

        assert tail_reinforcement(name) == ()

    ok("conflict + reinforcement tables defined for the 5 named presets")


# ==========================================================
# 2. ISSUE 2 — exterior_day must not inherit dusk/golden hour
# ==========================================================

def test_exterior_day_no_dusk():

    print("\n[2] exterior_day no longer inherits dusk/golden-hour")

    result = compose("exterior_day")

    final = result["final_prompt"].lower()

    for forbidden in ("golden hour", "sunset", "dusk", "twilight", "night"):

        assert forbidden not in final, (
            "exterior_day final prompt still contains '" + forbidden + "'"
        )

    assert "golden hour" in result["removed_conflicting_tail_terms"]

    # preset daytime intent is present and unopposed
    assert "bright natural daylight" in final

    assert "clear sky" in final

    ok("exterior_day: golden hour / dusk / night language removed")


def test_exterior_night_no_daylight():

    print("\n[3] exterior_night must not inherit daylight/golden-hour")

    final = compose("exterior_night")["final_prompt"].lower()

    for forbidden in ("daylight", "golden hour", "bright day", "sunset", "dusk"):

        assert forbidden not in final, (
            "exterior_night final prompt still contains '" + forbidden + "'"
        )

    assert "night scene" in final

    assert "architectural night photography" in final

    ok("exterior_night: daylight / golden hour / sunset language removed")


def test_exterior_sunset_keeps_golden_hour():

    print("\n[4] exterior_sunset keeps golden hour (compatible)")

    final = compose("exterior_sunset")["final_prompt"].lower()

    # sunset is a golden-hour condition -> must NOT be stripped
    assert "golden hour" in final

    assert "sunset" in final

    # but bright-day and night language must go
    for forbidden in ("bright day", "daylight", "night"):

        assert forbidden not in final, (
            "exterior_sunset still contains '" + forbidden + "'"
        )

    ok("exterior_sunset: keeps golden hour, drops bright-day/night")


# ==========================================================
# 3. ISSUE 3 — interior must drop facade framing, reinforce interior
# ==========================================================

def test_interior_drops_facade_framing():

    print("\n[5] interior_* no longer inherits facade/exterior framing")

    for name in ("interior_day", "interior_warm"):

        result = compose(name)

        final = result["final_prompt"].lower()

        for forbidden in ("facade", "exterior", "golden hour", "night"):

            assert forbidden not in final, (
                name + " final prompt still contains '" + forbidden + "'"
            )

        removed_segments = [
            record["segment"]
            for record in result["removed_conflicting_tail_segments"]
        ]

        assert "approved facade design: modern" in removed_segments

        assert "golden hour natural lighting" in removed_segments

        print("     " + name + " removed:", removed_segments)

    ok("interior_*: 'approved facade design' + facade/golden-hour filler removed")


def test_interior_reinforces_viewpoint():

    print("\n[6] interior_* explicitly reinforces the interior viewpoint")

    for name in ("interior_day", "interior_warm"):

        result = compose(name)

        final = result["final_prompt"].lower()

        for required in (
            "interior architectural photography",
            "interior viewpoint",
            "camera inside the room",
            "interior composition",
        ):

            assert required in final, (
                name + " missing reinforcement: " + required
            )

    ok("interior_*: interior viewpoint reinforcement present in final prompt")


# ==========================================================
# 4. USER CONTENT IS NEVER SUPPRESSED
# ==========================================================

def test_compiled_prompt_never_filtered():

    print("\n[7] compiled_render_prompt is never filtered")

    compiled = (
        "south facade of a modern villa, glass facade, "
        "golden hour natural lighting, exterior facade view"
    )

    for name in available_presets():

        result = compose(name, compiled=compiled)

        # the compiled prompt must appear verbatim at the start
        assert result["final_prompt"].startswith(compiled), name

        assert result["compiled_consumed"] is True

        assert result["compiled_prompt"] == compiled

    ok("user-requested facade/golden-hour content survives in every preset")


def test_preset_tail_never_filtered():

    print("\n[8] the preset's own tail is never filtered")

    # exterior_night's own tail legitimately contains "night"
    result = compose("exterior_night")

    assert "night scene" in result["final_prompt"]

    assert "night" not in result["removed_conflicting_tail_terms"]

    # interior_warm's own tail legitimately contains "interior"
    interior = compose("interior_warm")

    assert "warm interior lighting" in interior["final_prompt"]

    ok("preset-owned tail phrases survive their own conflict filters")


def test_no_preset_no_filtering():

    print("\n[9] no preset -> no filtering (backward compatible)")

    result = resolve_render_prompt(
        compiled_prompt="COMPILED",
        builder_prompt=REAL_BUILDER_TAIL,
    )

    assert result["removed_conflicting_tail_terms"] == []

    assert result["preset"] is None

    assert "golden hour natural lighting" in result["final_prompt"]

    ok("absent preset -> generic tail passed through unchanged")


# ==========================================================
# 5. ORDERING + TRACE
# ==========================================================

def test_composition_order():

    print("\n[10] preset intent precedes generic filler")

    final = compose("interior_warm")["final_prompt"]

    low = final.lower()

    assert low.index("warm interior lighting") < low.index("simple geometry"), (
        "preset tail must come before the generic builder tail"
    )

    assert low.index("camera inside the room") < low.index("simple geometry")

    assert low.index("interior viewpoint") < low.index("35mm lens")

    ok("order: compiled -> preset tail -> reinforcement -> generic filler")


def test_required_trace_fields():

    print("\n[11] required trace fields recorded")

    result = compose("exterior_day")

    for key in (
        "preset",
        "removed_conflicting_tail_terms",
        "retained_builder_tail",
        "final_prompt",
    ):

        assert key in result, "trace missing: " + key

    assert result["preset"] == "exterior_day"

    assert isinstance(result["removed_conflicting_tail_terms"], list)

    assert isinstance(result["retained_builder_tail"], list)

    assert result["final_prompt"] == result["prompt"]

    # removed segment must NOT be in the retained tail
    assert "golden hour natural lighting" not in result["retained_builder_tail"]

    # retained tail still carries the non-conflicting generic filler
    assert "35mm lens" in result["retained_builder_tail"]

    ok("trace: preset / removed_conflicting_tail_terms / retained_builder_tail / final_prompt")


def test_runtime_metadata_carries_trace():

    print("\n[12] RenderRuntime request metadata carries the 03B trace")

    runtime = RenderRuntime()

    class Stub:

        def submit(self, workflow):

            return {"status": "submitted", "prompt_id": "T1"}

        def wait_for_result(self, prompt_id):

            return {"status": "execution_error", "error": ["execution_error", {}]}

        def history(self, prompt_id):

            return {}

    stub = Stub()

    runtime.executor.comfy = stub

    runtime.result_bridge.comfy = stub

    result = runtime.render(
        "trace_03b",
        {
            "prompt": REAL_BUILDER_TAIL,
            "compiled_render_prompt": "COMPILED USER CONTENT",
            "preset": "interior_warm",
            "mode": "text2img",
        },
        "flux",
        None
    )

    metadata = result["request_metadata"]

    assert metadata["preset"] == "interior_warm"

    # NOTE: RenderRuntime rebuilds the generic tail via PromptBuilder, so the
    # removed segments are that engine's output - assert on shape, not on a
    # literal string captured from a different run.
    removed_segments = [
        record["segment"]
        for record in (metadata["removed_conflicting_tail_segments"] or [])
    ]

    assert any(
        "approved facade design" in segment
        for segment in removed_segments
    ), removed_segments

    assert any(
        "golden hour" in segment
        for segment in removed_segments
    ), removed_segments

    assert "golden hour" in metadata["removed_conflicting_tail_terms"]

    assert "facade" in metadata["removed_conflicting_tail_terms"]

    assert "interior viewpoint" in metadata["final_prompt"]

    assert "golden hour" not in metadata["final_prompt"].lower()

    assert "facade" not in metadata["final_prompt"].lower()

    ok("runtime metadata exposes removed terms + retained tail + final prompt")


# ==========================================================
# 6. EXPLICIT SEED (preset isolation for acceptance A/B)
# ==========================================================

def test_explicit_seed_precedence():

    print("\n[13] explicit request seed precedence")

    runtime = RenderRuntime()

    captured = {}

    class Stub:

        def submit(self, workflow):

            captured["workflow"] = json.loads(
                json.dumps(workflow)
            )

            return {"status": "submitted", "prompt_id": "T1"}

        def wait_for_result(self, prompt_id):

            return {"status": "execution_error", "error": ["x", {}]}

        def history(self, prompt_id):

            return {}

    stub = Stub()

    runtime.executor.comfy = stub

    runtime.result_bridge.comfy = stub

    runtime.render(
        "seed_test",
        {
            "prompt": "p",
            "compiled_render_prompt": "C",
            "preset": "exterior_day",
            "seed": 777001,
            "mode": "text2img",
        },
        "flux",
        None
    )

    assert captured["workflow"]["210"]["inputs"]["seed"] == 777001

    ok("explicit request seed reaches the KSampler")


def test_seed_absent_keeps_time_behaviour():

    print("\n[14] no explicit seed -> time-derived behaviour preserved")

    runtime = RenderRuntime()

    captured = {}

    class Stub:

        def submit(self, workflow):

            captured["seed"] = workflow["210"]["inputs"]["seed"]

            return {"status": "submitted", "prompt_id": "T1"}

        def wait_for_result(self, prompt_id):

            return {"status": "execution_error", "error": ["x", {}]}

        def history(self, prompt_id):

            return {}

    stub = Stub()

    runtime.executor.comfy = stub

    runtime.result_bridge.comfy = stub

    runtime.render(
        "seed_test2",
        {
            "prompt": "p",
            "compiled_render_prompt": "C",
            "preset": "exterior_day",
            "mode": "text2img",
        },
        "flux",
        None
    )

    assert captured["seed"] > 1_000_000_000

    ok("absent seed -> unchanged time-derived seed")


# ==========================================================
# 7. FILTER UNIT BEHAVIOUR
# ==========================================================

def test_filter_is_segment_level():

    print("\n[15] filtering is segment-level and case-insensitive")

    kept, removed = filter_tail_segments(
        "Golden Hour lighting, keep me, NIGHT scene",
        ("golden hour", "night")
    )

    assert kept == ["keep me"], kept

    assert [r["matched"] for r in removed] == ["golden hour", "night"]

    # no conflicts -> nothing removed
    kept2, removed2 = filter_tail_segments("a, b, c", ())

    assert kept2 == ["a", "b", "c"]

    assert removed2 == []

    ok("segment-level, case-insensitive filtering; empty conflicts = no-op")


# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS TEXT_TO_IMAGE_COMFY_03B — TESTS")
    print("=" * 62)

    test_conflict_tables_exist()

    test_exterior_day_no_dusk()

    test_exterior_night_no_daylight()

    test_exterior_sunset_keeps_golden_hour()

    test_interior_drops_facade_framing()

    test_interior_reinforces_viewpoint()

    test_compiled_prompt_never_filtered()

    test_preset_tail_never_filtered()

    test_no_preset_no_filtering()

    test_composition_order()

    test_required_trace_fields()

    test_runtime_metadata_carries_trace()

    test_explicit_seed_precedence()

    test_seed_absent_keeps_time_behaviour()

    test_filter_is_segment_level()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")
    print("  RESULT: TEXT_TO_IMAGE_COMFY_03B_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
