# ==========================================================
# ArchitectOS — RENDER_INSTRUCTION_HANDOFF_V1 (contract tests)
#
# The measured defect (V4.1 §3.2): `render_instruction.english_instruction`
# is produced by chat_architect and then discarded. The canonical prompt
# assembly (`resolve_render_prompt`) never receives it, so no A/B
# constraint — floor anchor, geometry, curved form, temporary objects —
# reaches the sampler.
#
# These tests are written BEFORE the production edit. They pin:
#
#   1. no instruction  -> byte-identical prompt (regression)
#   2. instruction     -> placed AFTER compiled, BEFORE the quality tail
#   3. a bounded, whole-sentence block (never cut mid-sentence)
#   4. de-duplication against the compiled prompt
#   5. an auditable trace
#   6. priority: user constraints > geometry > temporary objects
#
# NO GPU. NO COMFYUI. NO NETWORK.
# ==========================================================

import json
import os

import pytest

from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIVE_RESPONSE = os.path.join(
    ROOT, "runs", "architectos_architectural_intelligence_v4_1", "q1_response.json"
)

COMPILED = (
    "Refine the existing architectural image. Use light travertine stone. "
    "Adopt a restrained neoclassical architectural language."
)

PRESET = "photorealistic, balanced daylight"
BUILDER = "architectural photography, 35mm lens"


def _resolve(**kwargs):
    return resolve_render_prompt(
        compiled_prompt=kwargs.get("compiled", COMPILED),
        builder_prompt=kwargs.get("builder", BUILDER),
        user_text="transfer the facade style",
        preset_tail=kwargs.get("preset", PRESET),
        preset_name="facade",
        architectural_instruction=kwargs.get("instruction"),
        max_instruction_chars=kwargs.get("max_instruction_chars", 700),
    )


def _live_instruction():
    payload = json.load(open(LIVE_RESPONSE, encoding="utf-8"))

    return payload["response"]["response"]["render_handoff"]["render_instruction"]


# ==========================================================
# 1 — REGRESSION: NO INSTRUCTION MEANS NO CHANGE
# ==========================================================

def test_without_an_instruction_the_prompt_is_unchanged():
    baseline = resolve_render_prompt(
        compiled_prompt=COMPILED,
        builder_prompt=BUILDER,
        user_text="transfer the facade style",
        preset_tail=PRESET,
        preset_name="facade",
    )

    with_none = _resolve(instruction=None)

    assert with_none["prompt"] == baseline["prompt"]
    assert with_none["instruction_block"] == ""
    assert with_none["instruction_chars"] == 0
    assert with_none["instruction_truncated"] is False


def test_an_empty_instruction_is_treated_as_absent():
    baseline = _resolve(instruction=None)

    assert _resolve(instruction="")["prompt"] == baseline["prompt"]
    assert _resolve(instruction="   ")["prompt"] == baseline["prompt"]


# ==========================================================
# 2 — PLACEMENT AND ORDER
# ==========================================================

def test_the_instruction_follows_the_compiled_prompt_and_precedes_the_tail():
    result = _resolve(
        instruction={"constraint_block": "Keep the curved balcony slabs exactly."}
    )

    prompt = result["prompt"]

    assert prompt.startswith(COMPILED)

    compiled_at = prompt.index("Use light travertine stone")
    instruction_at = prompt.index("Keep the curved balcony slabs exactly")
    preset_at = prompt.index("balanced daylight")

    assert compiled_at < instruction_at < preset_at


def test_the_trace_reports_the_block_and_its_size():
    block = "Keep the curved balcony slabs exactly."

    result = _resolve(instruction={"constraint_block": block})

    assert result["instruction_block"] == block
    assert result["instruction_chars"] == len(block)
    assert result["instruction_truncated"] is False


# ==========================================================
# 3 — BOUNDING AND WHOLE SENTENCES
# ==========================================================

def test_an_oversized_block_is_capped_without_cutting_a_sentence():
    sentences = ["Preserve opening %d exactly." % index for index in range(60)]

    result = _resolve(
        instruction={"constraint_block": " ".join(sentences)},
        max_instruction_chars=200,
    )

    block = result["instruction_block"]

    assert len(block) <= 200
    assert block.endswith(".")
    assert result["instruction_truncated"] is True

    # every kept sentence is complete
    for sentence in block.split(". "):
        assert sentence.rstrip(".") in " ".join(sentences).replace(". ", ".")


def test_a_block_within_budget_is_not_truncated():
    block = "Keep the curved balcony slabs exactly. Do not straighten them."

    result = _resolve(instruction={"constraint_block": block}, max_instruction_chars=2000)

    assert result["instruction_block"] == block
    assert result["instruction_truncated"] is False


# ==========================================================
# 4 — DE-DUPLICATION
# ==========================================================

def test_a_sentence_already_in_the_compiled_prompt_is_not_repeated():
    result = _resolve(
        instruction={"constraint_block": "Use light travertine stone."}
    )

    assert result["prompt"].count("Use light travertine stone") == 1


# ==========================================================
# 5 — THE CONSTRAINT BLOCK BUILDER
# ==========================================================

def test_the_live_instruction_yields_the_safety_constraints():
    from core.cognition.architectural_render_instruction_v1 import (
        build_constraint_block,
    )

    block = build_constraint_block(_live_instruction())

    assert "curved" in block.lower()
    assert "temporary construction objects" in block.lower()
    assert "never architectural features" in block.lower()


def test_the_block_prefers_constraints_over_description():
    from core.cognition.architectural_render_instruction_v1 import (
        build_constraint_block,
    )

    block = build_constraint_block(_live_instruction())

    # The IMAGE-A appearance narrative is descriptive, not a constraint.
    assert "Take the facade APPEARANCE from IMAGE A" not in block


def test_the_block_is_bounded_and_complete():
    from core.cognition.architectural_render_instruction_v1 import (
        CONSTRAINT_BLOCK_BUDGET,
        build_constraint_block,
    )

    block = build_constraint_block(_live_instruction())

    assert 0 < len(block) <= CONSTRAINT_BLOCK_BUDGET
    assert block.endswith(".")

    # All four constraint groups must survive the budget.
    lowered = block.lower()
    assert "curved" in lowered
    assert "never architectural features" in lowered
    assert "preserve the target building" in lowered
    assert "do not remove them" in lowered


def test_an_empty_instruction_yields_an_empty_block():
    from core.cognition.architectural_render_instruction_v1 import (
        build_constraint_block,
    )

    assert build_constraint_block({}) == ""
    assert build_constraint_block(None) == ""


# ==========================================================
# 6 — THE WIRING (the runtime must actually pass it)
# ==========================================================

def test_the_render_runtime_passes_the_architectural_instruction():
    """`resolve_render_prompt` must receive it from the render design."""

    import ast

    path = os.path.join(ROOT, "core", "render", "render_runtime.py")

    tree = ast.parse(open(path, encoding="utf-8").read())

    found = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)

        if name != "resolve_render_prompt":
            continue

        for keyword in node.keywords:

            if keyword.arg == "architectural_instruction":
                found.append(keyword.value)

    assert found, "resolve_render_prompt is never given architectural_instruction"

    value = found[0]

    assert isinstance(value, ast.Call), ast.dump(value)
    assert getattr(value.func, "attr", None) == "get"
    assert isinstance(value.args[0], ast.Constant)
    assert value.args[0].value == "architectural_instruction"


def test_the_chat_payload_carries_the_instruction_on_the_dual_path():
    """The render payload must use an EXPLICIT parameter.

    `attach_render()` never receives the routing context, so an ambient
    `context.get(...)` there is a NameError waiting to happen — and an
    unresolved one silently delivers nothing to the sampler.
    """

    import ast

    from core.chat.chat_architect import ChatArchitect

    signature = ChatArchitect.attach_render.__code__.co_varnames

    assert "architectural_instruction" in signature

    # no ambient context lookup survives in the method
    assert "context" not in ChatArchitect.attach_render.__code__.co_names

    path = os.path.join(ROOT, "core", "chat", "chat_architect.py")

    tree = ast.parse(open(path, encoding="utf-8").read())

    payload_keys = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Dict):

            for key, value in zip(node.keys, node.values):

                if (
                    isinstance(key, ast.Constant)
                    and key.value == "architectural_instruction"
                ):
                    payload_keys.append(value)

    assert payload_keys, "no render payload carries the instruction"

    assert any(
        isinstance(value, ast.Name) and value.id == "architectural_instruction"
        for value in payload_keys
    ), "the payload does not use the explicit parameter"
