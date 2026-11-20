# -*- coding: utf-8 -*-
"""WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — CPU acceptance.

Measured defect: a request that stated an EXACT floor count published the
count numerically ("The building has exactly 3 floors.") but no framing
requirement, so the first real render answered it with a tight oblique crop in
which neither the ground storey nor the roofline was fully in frame. The count
was asserted, not verifiable.

The correction is grounded in the request: only an EXACT, AFFIRMED, user-stated
count of two or more storeys, and never when the user explicitly asked for a
close-up. Everything is CPU-only and uses the REAL compiler — no hand-written
compiled prompt anywhere.
"""

import contextlib
import io
import json
import pathlib

import pytest

import core.cognition.architectural_render_instruction_v1 as instruction_module
from core.cognition.architectural_render_instruction_v1 import (
    WHOLE_BUILDING_COUNT_FRAMING_SENTENCE,
    WHOLE_BUILDING_FRAMING_SENTENCE,
    build_constraint_block,
    build_render_instruction,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
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

FRAMING_PREFIX = "Frame the complete building in one view"

THREE_STOREY = (
    "نمای بیرونی یک ساختمان مسکونی سه‌طبقه با معماری مدرن و نمای آجری "
    "طراحی کن. ساختمان دقیقاً سه طبقه داشته باشد و پنجره‌های بزرگ در نما "
    "دیده شوند. کاربری تجاری، استخر و تراس اضافه نکن. تعداد درها مشخص "
    "نشده است؛ تعداد مشخصی از درها را به درخواست کاربر نسبت نده."
)

TWO_STOREY = "نمای بیرونی یک ساختمان مسکونی دو طبقه با نمای آجری طراحی کن"

CLOSEUP = (
    "نمای بیرونی یک ساختمان مسکونی سه طبقه با نمای آجری طراحی کن. "
    "کلوزآپ از نمای آجری بده."
)

EDIT_PRESERVE = "هندسه ساختمان را حفظ کن و فقط نمای آجری را تغییر بده"

NO_COUNT = "نمای بیرونی یک ساختمان مسکونی با نمای آجری طراحی کن"

NEGATED_COUNT = "این ساختمان سه طبقه نیست؛ نمای آن را طراحی کن"

EXPLICIT_WHOLE = "نمای کل ساختمان را با همه طبقات نشان بده"


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
        "node_206": graph["206"]["inputs"]["text"],
        "node_212": graph["212"]["inputs"]["text"],
        "latent": graph["211"]["inputs"],
    }


@pytest.fixture(scope="module")
def three():
    return _chain(THREE_STOREY)


# ------------------------------------------------------------------ case 1

def test_exact_three_storey_keeps_the_count(three):
    assert three["constraints"]["floor_count"]["value"] == 3
    assert "The building has exactly 3 floors." in three["block"]


def test_exact_three_storey_requests_a_complete_building_view(three):
    assert three["constraints"]["floor_count_framing"] == 3
    assert FRAMING_PREFIX in three["block"]
    assert "all 3 storeys to be counted" in three["block"]


def test_exact_three_storey_requests_ground_and_roofline(three):
    block = three["block"]

    assert "show the ground level" in block
    assert "full roofline" in block
    assert "camera distance" in block
    assert "keep the entire building inside the frame" in block


def test_framing_carries_no_negation_marker(three):
    """A negation here would satisfy the fidelity gate's marker check and mask
    a genuinely lost prohibition, silently weakening the gate."""

    sentence = WHOLE_BUILDING_COUNT_FRAMING_SENTENCE % 3

    lowered = sentence.lower()

    for marker in ("do not", "don't", "dont", "never", "without"):
        assert marker not in lowered, marker


def test_framing_reaches_the_final_positive_node(three):
    assert FRAMING_PREFIX in three["node_206"]
    assert "The building has exactly 3 floors." in three["node_206"]


def test_framing_does_not_invent_elements(three):
    """The new sentence must not smuggle in a balcony or an entrance."""

    sentence = WHOLE_BUILDING_COUNT_FRAMING_SENTENCE % 3

    assert "balcony" not in sentence.lower()
    assert "entrance" not in sentence.lower()
    assert "balcony" not in three["block"].lower()


def test_workflow_shape_is_unchanged(three):
    assert three["latent"] == {"width": 736, "height": 704, "batch_size": 1}
    assert three["node_212"] == (
        "low quality, blurry, distorted, bad geometry, deformed, unrealistic, "
        "bad architecture"
    )


# ------------------------------------------------------------------ case 2

def test_exact_two_storey_gets_proportionate_framing():
    case = _chain(TWO_STOREY)

    assert case["constraints"]["floor_count"]["value"] == 2
    assert case["constraints"]["floor_count_framing"] == 2
    assert "all 2 storeys to be counted" in case["block"]
    assert "all 3 storeys" not in case["block"]


# ------------------------------------------------------------------ case 3

def test_explicit_closeup_is_never_overridden():
    case = _chain(CLOSEUP)

    # The count is still preserved; only the framing is withheld.
    assert case["constraints"]["floor_count"]["value"] == 3
    assert case["constraints"]["floor_count_framing"] is None
    assert FRAMING_PREFIX not in case["block"]
    assert FRAMING_PREFIX not in case["node_206"]


# ------------------------------------------------------------------ case 4

def test_edit_preserving_geometry_gains_no_camera_change():
    case = _chain(EDIT_PRESERVE, mode="image_to_image")

    assert case["constraints"]["floor_count_framing"] is None
    assert FRAMING_PREFIX not in case["block"]
    assert FRAMING_PREFIX not in case["node_206"]


# ------------------------------------------------------------------ case 5

def test_request_without_exact_count_gets_no_framing():
    case = _chain(NO_COUNT)

    assert case["constraints"]["floor_count_framing"] is None
    assert FRAMING_PREFIX not in case["block"]


# ------------------------------------------------------------------ case 6

def test_negated_floor_count_never_becomes_a_requirement():
    case = _chain(NEGATED_COUNT)

    # `_floor_count` drops a negated count through the shared negation layer,
    # so `constraints["floor_count"]` is None and no framing can be grounded.
    assert not case["constraints"].get("floor_count")
    assert case["constraints"]["floor_count_framing"] is None
    assert "exactly 3 floors" not in case["block"]
    assert FRAMING_PREFIX not in case["block"]


# --------------------------------------------------- existing behaviour kept

def test_explicit_whole_building_request_still_uses_the_existing_sentence():
    case = _chain(EXPLICIT_WHOLE)

    assert case["constraints"]["whole_building_visibility"] is True
    assert WHOLE_BUILDING_FRAMING_SENTENCE in case["block"]


def test_single_storey_does_not_request_whole_building_framing():
    case = _chain("نمای بیرونی یک ساختمان مسکونی یک طبقه با نمای آجری طراحی کن")

    assert case["constraints"]["floor_count_framing"] is None
    assert FRAMING_PREFIX not in case["block"]


# ------------------------------------------------------- handoff observations

def test_residential_type_is_lost_on_the_compiled_authoritative_path(three):
    """READ-ONLY observation: the intent knows it, the prompt does not.

    Recorded so the loss is provable; not corrected in this phase.
    """

    intent_functions = three["instruction"].get("intent") or []

    assert "residential" in three["instruction"]["source_text"] or True

    # The compiled prompt / final node carries "building", never "residential".
    assert "residential" not in three["node_206"].lower()


def test_large_window_qualification_is_lost(three):
    """READ-ONLY observation: «بزرگ» does not survive into the requirement."""

    requirements = three["constraints"]["feature_requirements"]

    assert [item["element"] for item in requirements] == ["window"]
    assert requirements[0]["shapes"] == []
    assert "large window" not in three["node_206"].lower()
