# -*- coding: utf-8 -*-
"""EXISTING_CAMERA_INSTRUCTION_HANDOFF_FIX_V1 — CPU acceptance.

Measured defect: the instruction builder has always produced
``Camera / view: frontal view.`` for an explicit camera request, but
``build_constraint_block()`` had no admission rule for that prefix, so the
sentence was dropped before node 206. The user's camera choice never reached
the sampler.

The correction is one admission entry plus a negation guard taken from the
shared negation layer. No camera vocabulary, engine or workflow is added.
"""

import contextlib
import io
import json
import pathlib

import pytest

import core.cognition.architectural_render_instruction_v1 as instruction_module
from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
from core.cognition.render_semantic_fidelity_v1 import validate_render_fidelity
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    compile_prompt,
)
from core.prompt_intelligence.persian_architectural_understanding import (
    understand,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.workflow_injector import WorkflowInjector

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "core" / "render" / "workflows" / "flux.json"

CAMERA_PREFIX = "Camera / view:"
FRAMING_PREFIX = "Frame the complete building in one view"

FRONTAL_THREE = (
    "نمای روبرو از ساختمان سه طبقه با نمای آجری طراحی کن. "
    "ساختمان دقیقاً سه طبقه داشته باشد."
)

NO_CAMERA = "نمای بیرونی یک ساختمان مسکونی سه طبقه با نمای آجری طراحی کن"

CLOSEUP = "کلوزآپ از نمای آجری ساختمان سه طبقه"

EDIT_PRESERVE = "هندسه ساختمان را حفظ کن و فقط نمای آجری را تغییر بده"

NEGATED_KON = "نمای روبرو نکن؛ نمای ساختمان سه طبقه را طراحی کن"

NEGATED_DASHTE = "نمای روبرو نداشته باشد؛ ساختمان سه طبقه با نمای آجری"

WHOLE_BUILDING = "نمای کل ساختمان را با همه طبقات نشان بده"


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _chain(text, mode="text_to_image"):
    understanding = _quiet(understand, text)
    compiled = _quiet(compile_prompt, understanding, mode=mode)
    terminology = _quiet(normalize_architectural_terms, text)

    instruction = _quiet(
        build_render_instruction,
        text,
        understanding=understanding,
        compiled=compiled,
        mode=mode,
    )

    block = _quiet(build_constraint_block, instruction)
    fidelity = _quiet(validate_render_fidelity, text, contract=instruction)

    augmented = _quiet(
        augment_compiled_prompt,
        str(compiled.get("positive_prompt") or ""),
        terminology,
    )
    augmented = instruction_module._normalise_intent_opening(
        augmented, instruction.get("intent") or "CREATE"
    )
    augmented = instruction_module._normalise_terminology_tail(augmented)

    provenance = (instruction.get("constraints") or {}).get(
        "floor_count_provenance"
    ) or {}

    handoff = {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": block,
        "source": "render_instruction.english_instruction",
        "floor_count": (
            provenance.get("value")
            if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
            else None
        ),
    }

    resolved = _quiet(
        resolve_render_prompt,
        compiled_prompt=augmented,
        builder_prompt="",
        architectural_instruction=handoff,
    )

    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    injected = _quiet(
        WorkflowInjector().inject_prompt,
        workflow,
        resolved.get("prompt") or "",
        None,
    )

    graph = injected

    if isinstance(injected, dict) and isinstance(injected.get("workflow"), dict):
        graph = injected["workflow"]

    return {
        "instruction": instruction,
        "constraints": instruction.get("constraints") or {},
        "block": block,
        "fidelity": fidelity,
        "node_206": graph["206"]["inputs"]["text"],
        "node_212": graph["212"]["inputs"]["text"],
    }


@pytest.fixture(scope="module")
def frontal():
    return _chain(FRONTAL_THREE)


# ------------------------------------------------------------------ case 1

def test_explicit_camera_reaches_the_block(frontal):
    assert CAMERA_PREFIX in frontal["block"]
    assert "frontal view" in frontal["block"]


def test_explicit_camera_reaches_the_final_node(frontal):
    assert "Camera / view: frontal view." in frontal["node_206"]


def test_floor_count_survives_alongside_the_camera(frontal):
    assert "The building has exactly 3 floors." in frontal["node_206"]
    assert frontal["constraints"]["floor_count"]["value"] == 3


def test_framing_survives_alongside_the_camera(frontal):
    assert FRAMING_PREFIX in frontal["node_206"]


def test_camera_and_floor_count_do_not_overwrite_each_other(frontal):
    node = frontal["node_206"]

    assert node.index("exactly 3 floors") < node.index("Camera / view:")
    assert node.count("Camera / view:") == 1


def test_negative_node_is_untouched(frontal):
    assert frontal["node_212"] == (
        "low quality, blurry, distorted, bad geometry, deformed, unrealistic, "
        "bad architecture"
    )


def test_fidelity_still_passes(frontal):
    assert frontal["fidelity"]["status"] == "PASS"
    assert frontal["fidelity"]["may_proceed_to_render"] is True


# ------------------------------------------------------------------ case 2

def test_request_without_camera_gains_none():
    case = _chain(NO_CAMERA)

    assert CAMERA_PREFIX not in case["block"]
    assert CAMERA_PREFIX not in case["node_206"]


# ------------------------------------------------------------------ case 3

def test_closeup_is_not_substituted_with_a_distant_view():
    case = _chain(CLOSEUP)

    assert FRAMING_PREFIX not in case["block"]
    assert CAMERA_PREFIX not in case["block"]
    assert "The building has exactly 3 floors." in case["block"]


# ------------------------------------------------------------------ case 4

def test_geometry_preserving_edit_gains_no_camera():
    case = _chain(EDIT_PRESERVE, mode="image_to_image")

    assert CAMERA_PREFIX not in case["block"]
    assert FRAMING_PREFIX not in case["block"]


# ------------------------------------------------------------------ case 6

def test_negated_camera_is_not_a_positive_requirement():
    for text in (NEGATED_KON, NEGATED_DASHTE):
        case = _chain(text)

        assert CAMERA_PREFIX not in case["block"], text
        assert "Camera / view:" not in case["node_206"], text


# ------------------------------------------------ hallucination boundary

def test_camera_change_introduces_no_balcony_or_entrance(frontal):
    """The camera sentence must not smuggle in elements the user never asked for."""

    lowered = frontal["block"].lower()

    assert "balcony" not in lowered
    assert "entrance" not in lowered


def test_old_framing_sentence_still_names_balcony_and_entrance():
    """DOCUMENTED boundary, not caused by the camera change.

    `WHOLE_BUILDING_FRAMING_SENTENCE` names "the entrance, the balcony". It is
    reached ONLY when the user explicitly asks for a whole-building view, and
    it reaches the block because of the earlier prefix-slicing admission fix,
    not because of the camera admission. Recorded here so the boundary is
    provable; rewording the accepted sentence is a separate decision.
    """

    case = _chain(WHOLE_BUILDING)

    assert case["constraints"]["whole_building_visibility"] is True
    assert "balcony" in case["block"].lower()
    assert "entrance" in case["block"].lower()

    # And it is NOT reachable for a request that never asked for it.
    assert "balcony" not in _chain(NO_CAMERA)["block"].lower()


def test_camera_admission_does_not_change_the_whole_building_sentence():
    """With and without a camera term, the sentence is byte-identical."""

    without = _chain(WHOLE_BUILDING)["block"]
    with_camera = _chain(
        "نمای روبرو از کل ساختمان با همه طبقات"
    )["block"]

    old_sentence = (
        "Frame the complete building: show the whole exterior elevation with "
        "all its floors, the entrance, the balcony and the roof visible in one "
        "view."
    )

    assert old_sentence in without
    assert old_sentence in with_camera
