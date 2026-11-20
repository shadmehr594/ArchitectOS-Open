"""VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 - CPU-only acceptance.

BLOCKER A: a NEGATED architectural requirement (Persian trailing prohibition
«… اضافه نکن» / «… نداشته باشد») must not become a positive requirement.
BLOCKER B: a meta-statement about missing information («تعداد درها مشخص نشده
است») must not become a door requirement.

Real deterministic chain only, ending at the REAL `flux.json` positive node 206:

    ArchitecturalIntent.extract() -> build_render_instruction()
      -> build_constraint_block() -> PromptBuilder -> resolve_render_prompt()
      -> WorkflowInjector.inject_prompt(real flux.json)

No LLM, Ollama, ComfyUI, GPU, renderer or network call.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _feature_requirements,
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector

FULL_REQUEST = (
    "نمای بیرونی یک ساختمان مسکونی سه‌طبقه با معماری مدرن و نمای آجری طراحی کن. "
    "ساختمان دقیقاً سه طبقه داشته باشد و پنجره‌های بزرگ در نما دیده شوند. "
    "کاربری تجاری، استخر و تراس اضافه نکن. تعداد درها مشخص نشده است؛ "
    "تعداد مشخصی از درها را به درخواست کاربر نسبت نده."
)

WORKFLOW_PATH = "core/render/workflows/flux.json"


@lru_cache(maxsize=None)
def _intent(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return ArchitecturalIntent().extract({"prompt": text})


def _requirements(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return _feature_requirements(text)


def _instruction(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return build_render_instruction(text, mode="text2img")


def _resolved(text):
    intent = _intent(text)
    instruction = _instruction(text)
    provenance = (instruction.get("constraints") or {}).get(
        "floor_count_provenance"
    ) or {}
    handoff = {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": build_constraint_block(instruction),
        "source": "render_instruction.english_instruction",
        "floor_count": (
            provenance.get("value")
            if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
            else None
        ),
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        built = PromptBuilder().build(
            {"prompt": "Architectural visualization request",
             "architectural_intent": intent}
        )
        resolved = resolve_render_prompt(
            compiled_prompt="Architectural visualization of the requested building.",
            builder_prompt=built.get("description") or "",
            architectural_instruction=handoff,
        )
    return (
        intent,
        resolved.get("prompt") or resolved.get("final_prompt") or "",
    )


def _node_206(text):
    _intent_row, prompt = _resolved(text)
    workflow = json.load(open(WORKFLOW_PATH, encoding="utf-8"))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        injected = WorkflowInjector().inject_prompt(workflow, prompt, None)
    graph = injected.get("workflow") if isinstance(injected, dict) else None
    if not isinstance(graph, dict):
        graph = injected
    return graph["206"]["inputs"]["text"]


# ===========================================================================
# A. Full original visual-acceptance request
# ===========================================================================


def test_full_request_classification_is_residential():
    intent = _intent(FULL_REQUEST)

    assert intent.get("building_type") != "mixed_use_commercial_residential"
    assert intent.get("category") != "commercial"
    assert intent.get("building_type") != "commercial"


def test_full_request_has_no_commercial_pool_or_terrace_spaces():
    spaces = _intent(FULL_REQUEST).get("spaces") or []

    assert "retail" not in spaces
    assert "lobby" not in spaces
    assert "pool" not in spaces
    assert "terrace" not in spaces


def test_full_request_keeps_its_real_requirements():
    intent = _intent(FULL_REQUEST)

    assert intent.get("floors") == 3
    assert intent.get("style") == "modern"
    assert intent.get("materials") == ["brick facade"]

    provenance = (_instruction(FULL_REQUEST).get("constraints") or {}).get(
        "floor_count_provenance"
    ) or {}
    assert provenance.get("value") == 3
    assert provenance.get("source") == "USER_TEXT"
    assert provenance.get("hard_constraint") is True


def test_full_request_emits_no_door_requirement():
    elements = [r["element"] for r in _requirements(FULL_REQUEST)]
    assert "door" not in elements
    assert "window" in elements


def test_full_request_node_206_is_clean():
    node = _node_206(FULL_REQUEST).lower()

    assert "exactly 3 floors" in node
    assert "brick facade" in node
    assert "include windows" in node

    assert "retail" not in node
    assert "lobby" not in node
    assert "pool" not in node
    assert "terrace" not in node
    assert "mixed_use" not in node
    assert "commercial" not in node
    assert "door" not in node


def test_full_request_keeps_requested_and_rejected_evidence_separate():
    intent = _intent(FULL_REQUEST)
    instruction = _instruction(FULL_REQUEST)
    negations = (instruction.get("constraints") or {}).get("negations") or {}

    assert intent.get("materials") == ["brick facade"]
    assert intent.get("floors") == 3
    assert negations.get("is_negated") is True


# ===========================================================================
# B. Negated commercial use (Persian negative copula)
# ===========================================================================


def test_negated_commercial_is_not_mixed_use():
    text = "ساختمان سه طبقه مسکونی، کاربری تجاری نداشته باشد"
    intent = _intent(text)

    assert intent.get("building_type") != "mixed_use_commercial_residential"
    assert "commercial" not in (intent.get("functions") or [])
    assert intent.get("floors") == 3

    node = _node_206(text).lower()
    assert "retail" not in node
    assert "commercial" not in node


# ===========================================================================
# C. Affirmed mixed use must keep working
# ===========================================================================


def test_affirmed_mixed_use_still_works():
    text = "ساختمان سه طبقه تجاری و مسکونی"
    intent = _intent(text)

    assert intent.get("building_type") in (
        "mixed_use", "mixed_use_commercial_residential",
    )
    assert "commercial" in (intent.get("functions") or [])
    assert "residential" in (intent.get("functions") or [])


# ===========================================================================
# D. Affirmed pool and terrace must keep working
# ===========================================================================


def test_affirmed_pool_and_terrace_still_work():
    text = "ویلا با استخر و تراس طراحی کن"
    spaces = _intent(text).get("spaces") or []

    assert "pool" in spaces
    assert "terrace" in spaces

    node = _node_206(text).lower()
    assert "pool" in node
    assert "terrace" in node


# ===========================================================================
# E. Negated pool and terrace
# ===========================================================================


def test_negated_pool_and_terrace_are_not_requested():
    text = "ویلا طراحی کن، استخر و تراس اضافه نکن"
    spaces = _intent(text).get("spaces") or []

    assert "pool" not in spaces
    assert "terrace" not in spaces

    node = _node_206(text).lower()
    assert "pool" not in node
    assert "terrace" not in node
    assert "villa" in node


# ===========================================================================
# F. Meta-statement about a missing count
# ===========================================================================


def test_unspecified_door_count_is_not_a_door_requirement():
    text = "تعداد درها مشخص نشده است"

    assert _requirements(text) == []

    node = _node_206(text).lower()
    assert "door" not in node


def test_unspecified_door_count_is_not_a_prohibition_either():
    text = "تعداد درها مشخص نشده است"
    negations = (_instruction(text).get("constraints") or {}).get(
        "negations"
    ) or {}

    assert negations.get("rejected_span") in ("", None)


def test_meta_statement_after_an_authorised_clause_still_adds_no_door():
    """The real shape: a feature clause opens the enumeration, then a
    meta-statement about the door count must NOT inherit that authorisation."""

    text = (
        "ساختمان سه طبقه با پنجره‌های بزرگ داشته باشد. "
        "تعداد درها مشخص نشده است."
    )
    elements = [r["element"] for r in _requirements(text)]

    assert "window" in elements
    assert "door" not in elements


# ===========================================================================
# G. Genuine door request must still work
# ===========================================================================


def test_explicit_door_request_still_works():
    text = "دو در ورودی برای نما طراحی کن"
    requirements = _requirements(text)

    doors = [r for r in requirements if r["element"] == "door"]
    assert len(doors) == 1

    node = _node_206(text).lower()
    assert "door" in node


# ===========================================================================
# H. Window presence (size adjective is a known, unfixed gap)
# ===========================================================================


def test_window_presence_remains_correct():
    text = "نمای ساختمان دارای پنجره‌های بزرگ باشد"
    requirements = _requirements(text)

    assert [r["element"] for r in requirements] == ["window"]
    assert requirements[0]["locations"] == ["facade"]
    # DOCUMENTED GAP: the Persian size adjective «بزرگ» is not in the shape
    # vocabulary, so no size claim is made here (and none is asserted).
    assert requirements[0]["shapes"] == []

    node = _node_206(text).lower()
    assert "include windows" in node
