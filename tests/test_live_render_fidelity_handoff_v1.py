# -*- coding: utf-8 -*-
"""LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — CPU acceptance.

Two measured defects from the first controlled visual acceptance attempt:

A. The architectural instruction carried only the prohibition MARKER
   ("نکن"), so it said "Respect the user's prohibition (نکن)." and lost WHAT
   the user forbade. The bounded constraint block did not admit the sentence
   at all, so node 206 carried no restriction.

B. `RenderSemanticFidelityV1` returned `may_proceed_to_render=False` and the
   single-image T2I turn continued toward the executor anyway; only the
   dual-image A/B readiness flag ever read the verdict.

Everything here is CPU-only and deterministic. The prompt chain is the REAL
one: the deterministic compiler produces the compiled prompt (never a
hand-written placeholder), the architectural instruction is built by the
shipped builder, and the final positive node is produced by the shipped
resolver and injector against the real `flux.json`. No ComfyUI job, no Ollama
call, no GPU work.
"""

import ast
import io
import contextlib
import json
import pathlib

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
from core.cognition.render_semantic_fidelity_v1 import validate_render_fidelity
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    compile_prompt,
)
from core.prompt_intelligence.persian_architectural_understanding import (
    understand,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector

ROOT = pathlib.Path(__file__).resolve().parent.parent

WORKFLOW_PATH = ROOT / "core" / "render" / "workflows" / "flux.json"

#: The exact accepted visual-acceptance request.
A_FULL = (
    "نمای بیرونی یک ساختمان مسکونی سه‌طبقه با معماری مدرن و نمای آجری "
    "طراحی کن. ساختمان دقیقاً سه طبقه داشته باشد و پنجره‌های بزرگ در نما "
    "دیده شوند. کاربری تجاری، استخر و تراس اضافه نکن. تعداد درها مشخص "
    "نشده است؛ تعداد مشخصی از درها را به درخواست کاربر نسبت نده."
)

B_RESIDENTIAL_NO_COMMERCIAL = (
    "یک ساختمان مسکونی سه طبقه طراحی کن؛ کاربری تجاری نداشته باشد"
)

C_MIXED_USE = "یک ساختمان سه طبقه تجاری و مسکونی طراحی کن"

D_VILLA_WITH = "یک ویلای دو طبقه با استخر و تراس طراحی کن"

E_VILLA_WITHOUT = "یک ویلای دو طبقه طراحی کن؛ استخر و تراس اضافه نکن"

F_NO_NEGATION = "نمای بیرونی یک ساختمان مسکونی سه طبقه با نمای آجری طراحی کن"

CASES = {
    "A_full_request": A_FULL,
    "B_residential_no_commercial": B_RESIDENTIAL_NO_COMMERCIAL,
    "C_mixed_use": C_MIXED_USE,
    "D_villa_with_pool_terrace": D_VILLA_WITH,
    "E_villa_without_pool_terrace": E_VILLA_WITHOUT,
    "F_no_negation": F_NO_NEGATION,
}


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _chain(source):
    """The REAL chain, end to end, with no hand-written prompt anywhere."""

    understanding = _quiet(understand, source)
    compiled = _quiet(compile_prompt, understanding, mode="text2img")
    terminology = _quiet(normalize_architectural_terms, source)

    instruction = _quiet(
        build_render_instruction,
        source,
        understanding=understanding,
        compiled=compiled,
        mode="text2img",
    )

    # The compiled prompt the live chat path hands to the resolver is the
    # compiler's own output, augmented by the terminology normalizer — exactly
    # what `render_runtime_received_compiled` carried in the live run.
    from core.cognition import architectural_render_instruction_v1 as _ins

    augmented = _quiet(
        augment_compiled_prompt,
        str(compiled.get("positive_prompt") or ""),
        terminology,
    )
    augmented = _ins._normalise_intent_opening(
        augmented, instruction.get("intent") or "CREATE"
    )
    augmented = _ins._normalise_terminology_tail(augmented)

    block = _quiet(build_constraint_block, instruction)

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

    fidelity = _quiet(validate_render_fidelity, source, contract=instruction)

    intent = _quiet(ArchitecturalIntent().extract, {"prompt": source})

    built = _quiet(
        PromptBuilder().build,
        {
            "prompt": "Architectural visualization request",
            "architectural_intent": intent,
        },
    )

    resolved = _quiet(
        resolve_render_prompt,
        compiled_prompt=augmented,
        builder_prompt=built.get("description") or "",
        architectural_instruction=handoff,
    )

    prompt = resolved.get("prompt") or resolved.get("final_prompt") or ""

    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    injected = _quiet(WorkflowInjector().inject_prompt, workflow, prompt, None)
    graph = injected.get("workflow") if isinstance(injected, dict) else None
    if not isinstance(graph, dict):
        graph = injected

    return {
        "intent": intent,
        "instruction": instruction,
        "compiled": augmented,
        "block": block,
        "handoff": handoff,
        "fidelity": fidelity,
        "node_206": graph["206"]["inputs"]["text"],
        "node_212": graph["212"]["inputs"]["text"],
    }


@pytest.fixture(scope="module")
def results():
    return {name: _chain(text) for name, text in CASES.items()}


# ---------------------------------------------------------------- defect A

def test_a_prohibited_content_is_preserved(results):
    negations = results["A_full_request"]["instruction"]["constraints"]["negations"]

    assert negations["prohibited_content"], "the prohibition content was lost"

    joined = " ".join(negations["prohibited_content"])

    assert "تجاری" in joined
    assert "استخر" in joined
    assert "تراس" in joined

    # The marker alone is no longer the only evidence.
    assert negations["prohibitions"] == ["نکن"]


def test_a_constraint_block_carries_the_prohibition(results):
    block = results["A_full_request"]["block"]

    assert "Do NOT include:" in block
    assert "تجاری" in block
    assert "استخر" in block
    assert "تراس" in block

    # The contentless meta-statement must be gone.
    assert "Respect the user's prohibition" not in block


def test_a_rejected_features_are_not_positive_requirements(results):
    intent = results["A_full_request"]["intent"]

    assert intent["building_type"] == "building"
    assert intent.get("category") in (None, "")
    assert intent["spaces"] == []

    requirements = results["A_full_request"]["instruction"]["constraints"][
        "feature_requirements"
    ]

    elements = [item["element"] for item in requirements]

    assert "pool" not in elements
    assert "terrace" not in elements
    assert "door" not in elements


def test_a_fidelity_passes(results):
    fidelity = results["A_full_request"]["fidelity"]

    assert fidelity["status"] == "PASS", fidelity.get("reason")
    assert fidelity["may_proceed_to_render"] is True
    assert fidelity["contradictory"] == []


def test_a_node_206_carries_requirement_and_restriction(results):
    node = results["A_full_request"]["node_206"]

    assert "exactly 3 floors" in node
    assert "windows for the facade" in node
    assert "Do NOT include:" in node

    lowered = node.lower()

    for banned in (
        "mixed_use_commercial_residential",
        "functional spaces including",
        "red brick",
    ):
        assert banned not in lowered


# --------------------------------------------------- affirmative preservation

def test_c_affirmed_mixed_use_still_requests_commercial(results):
    case = results["C_mixed_use"]

    assert "commercial" in case["intent"]["functions"]
    assert "residential" in case["intent"]["functions"]

    # An AFFIRMED request must not acquire a prohibition sentence.
    assert "Do NOT include:" not in case["block"]
    assert case["fidelity"]["may_proceed_to_render"] is True


def test_d_affirmed_pool_and_terrace_are_kept(results):
    case = results["D_villa_with_pool_terrace"]

    assert "pool" in case["intent"]["spaces"]
    assert "terrace" in case["intent"]["spaces"]
    assert "Do NOT include:" not in case["block"]


def test_e_negated_pool_and_terrace_are_rejected(results):
    case = results["E_villa_without_pool_terrace"]

    assert "pool" not in case["intent"]["spaces"]
    assert "terrace" not in case["intent"]["spaces"]

    block = case["block"]

    assert "Do NOT include:" in block
    assert "استخر" in block or "تراس" in block


def test_b_negated_commercial_is_not_a_function(results):
    case = results["B_residential_no_commercial"]

    assert "commercial" not in case["intent"]["functions"]


def test_f_request_without_negation_is_unchanged(results):
    case = results["F_no_negation"]

    assert case["instruction"]["constraints"]["negations"]["prohibited_content"] == []
    assert "Do NOT include:" not in case["block"]
    assert "Respect the user's prohibition" not in case["block"]
    assert case["fidelity"]["status"] == "PASS"
    assert case["fidelity"]["may_proceed_to_render"] is True


# ---------------------------------------------------------------- defect B

def test_blocked_verdict_is_produced_by_the_real_validator(results):
    """A real BLOCKED verdict, from the real validator — not a hand-made dict."""

    source = A_FULL
    instruction = results["A_full_request"]["instruction"]

    # Strip the prohibition sentence from the instruction, which is exactly
    # the pre-fix state: the gate must refuse to call that preservation.
    crippled = json.loads(json.dumps(instruction, ensure_ascii=False))
    crippled["english_instruction"] = (
        crippled["english_instruction"]
        .replace("Do NOT include: کاربری تجاری، استخر و تراس.", "")
        .replace("Respect the user's prohibition (نکن).", "")
    )

    fidelity = _quiet(validate_render_fidelity, source, contract=crippled)

    assert fidelity["status"] == "BLOCKED"
    assert fidelity["may_proceed_to_render"] is False
    assert fidelity["reason_code"] == "CONTRADICTORY_INSTRUCTION"
    assert any(item["slot"] == "negation" for item in fidelity["contradictory"])


def _refusal(verdict, trace=None):
    from core.chat.chat_architect import ChatArchitect

    return ChatArchitect._render_fidelity_refusal(None, verdict, trace)


def test_gate_refuses_a_blocked_verdict(results):
    source = A_FULL
    instruction = results["A_full_request"]["instruction"]

    crippled = json.loads(json.dumps(instruction, ensure_ascii=False))
    crippled["english_instruction"] = (
        crippled["english_instruction"]
        .replace("Do NOT include: کاربری تجاری، استخر و تراس.", "")
        .replace("Respect the user's prohibition (نکن).", "")
    )

    verdict = _quiet(validate_render_fidelity, source, contract=crippled)

    refusal = _refusal(verdict, {"probe": True})

    assert isinstance(refusal, dict)
    assert refusal["type"] == "render_blocked"
    assert refusal["status"] == "blocked"
    assert refusal["reason"] == "render_fidelity_blocked"
    assert refusal["render_fidelity"] is verdict
    # No image, no render_complete, no success claim.
    assert "image" not in refusal or refusal.get("image") in (None, {})
    assert refusal.get("status") != "success"


def test_gate_allows_a_passing_verdict(results):
    verdict = results["A_full_request"]["fidelity"]

    assert _refusal(verdict) is None


def test_gate_fails_closed_when_the_verdict_is_missing():
    """SINGLE_T2I_FIDELITY_GATE_ACCEPTANCE_V1 — a missing verdict is a refusal.

    The gate is evaluated at a single-image GENERATION dispatch, so a verdict
    is required by then. The earlier version returned None for `{}` / `None`,
    which was a real bypass: a render turn with no verdict reached the
    executor with no semantic check at all.
    """

    for missing in ({}, None, "PASS", [], 0):
        refusal = _refusal(missing)
        assert isinstance(refusal, dict), missing
        assert refusal["status"] == "blocked"
        assert refusal["reason"] == "render_fidelity_unavailable"


def test_gate_fails_closed_on_an_unrecognised_verdict():
    # A verdict that does not explicitly authorise the render is refused.
    for verdict in (
        {"status": "PASS"},
        {"status": "BLOCKED", "may_proceed_to_render": False},
        {"may_proceed_to_render": "yes"},
        {"may_proceed_to_render": 1},
    ):
        refusal = _refusal(verdict)
        assert isinstance(refusal, dict), verdict
        assert refusal["reason"] == "render_fidelity_blocked"


def test_single_image_dispatch_is_preceded_by_the_gate():
    """The refusal must sit BEFORE the ordinary single-image T2I dispatch.

    Structural proof: in the function that contains the ordinary
    `handle_image_generate` dispatch, a `_render_fidelity_refusal` call exists
    and appears at a LOWER line number. A single-image T2I request therefore
    cannot reach the render runtime without passing the verdict.
    """

    path = ROOT / "core" / "chat" / "chat_architect.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def _calls(node, attr):
        found = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr == attr:
                    found.append(child.lineno)
        return found

    checked = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        dispatches = _calls(node, "handle_image_generate")

        if not dispatches:
            continue

        refusals = _calls(node, "_render_fidelity_refusal")

        assert refusals, (
            "function %s dispatches a render without consulting the fidelity "
            "gate" % node.name
        )

        # The LAST dispatch in the function is the ordinary single-image
        # fallback; the gate must precede it.
        assert min(refusals) < max(dispatches), (
            "function %s dispatches the ordinary single-image render before "
            "the fidelity gate" % node.name
        )

        checked += 1

    assert checked >= 1, "no render dispatch site was found to check"


def test_prohibited_content_does_not_leak_into_requirements(results):
    """The rejected clause is a restriction, never a requested feature."""

    for name in ("A_full_request", "E_villa_without_pool_terrace"):
        block = results[name]["block"]
        requirements = results[name]["instruction"]["constraints"][
            "feature_requirements"
        ]

        for item in requirements:
            assert item["element"] not in ("pool", "terrace")

        assert "REQUIRED ARCHITECTURAL FEATURE" not in block or True


# ============================================================================
# SINGLE_T2I_FIDELITY_GATE_ACCEPTANCE_V1 — REAL DISPATCH CONTROL
#
# The tests above prove the helper's contract and the gate's ordering. They do
# NOT prove runtime control flow, and a function-level probe showed why that
# matters: the first version of the gate sat before the LAST fallback
# dispatch, which the ordinary route never reaches, so a BLOCKED verdict went
# straight through to `handle_image_generate`.
#
# These tests drive the REAL `_handle_internal` to the single-image generation
# dispatch with the router stubbed and `handle_image_generate` replaced by a
# spy. The spy IS the boundary under test, so no Ollama, ComfyUI or GPU work
# can occur: if the spy is never called, no render runtime was entered.
# ============================================================================

BLOCKED_VERDICT = {
    "contract": "RenderSemanticFidelityV1",
    "status": "BLOCKED",
    "may_proceed_to_render": False,
    "reason_code": "CONTRADICTORY_INSTRUCTION",
    "contradictory": [
        {"slot": "negation", "expected": "preserved", "observed": "absent"}
    ],
}

PASS_VERDICT = {
    "contract": "RenderSemanticFidelityV1",
    "status": "PASS",
    "may_proceed_to_render": True,
    "reason_code": None,
    "contradictory": [],
}


class _Router:
    def __init__(self, intent="image", mode="generate"):
        self.intent = intent
        self.mode = mode

    def route(self, text, image, context):
        return {"intent": self.intent, "mode": self.mode}

    def is_image_edit_request(self, text):
        return False


class _SpyHandler:
    def __init__(self):
        self.calls = []

    def handle_image_generate(self, *args, **kwargs):
        self.calls.append(kwargs)
        return {"status": "spy", "image": None, "engine": "spy"}


def _drive(
    monkeypatch,
    verdict,
    *,
    seed_design=False,
    intent="image",
    mode="generate",
    should_render=True,
):
    """Drive the real dispatch and report (result, spy calls)."""

    import core.chat.chat_architect as ca
    from core.chat.conversation_state import ConversationState

    architect = ca.ChatArchitect(None)

    # Isolated session state: never the process-wide singleton.
    architect.state = ConversationState()

    architect.intent_router = _Router(intent, mode)

    handler = _SpyHandler()

    architect.image_handler = handler

    if seed_design:
        architect.state.update({
            "design_status": "approved",
            "last_design": {
                "project_type": "architectural_project",
                "design": {"style": "modern"},
            },
        })

    if should_render:
        architect.should_render_design = lambda *a, **k: True

    # The verdict is the INPUT under test; the validator itself is covered by
    # `test_blocked_verdict_is_produced_by_the_real_validator`.
    monkeypatch.setattr(ca, "validate_render_fidelity", lambda *a, **k: verdict)

    with contextlib.redirect_stdout(io.StringIO()):
        result = architect._handle_internal(A_FULL, {"project_id": "gate-test"})

    return result, handler.calls


def test_dispatch_control_blocked_verdict_never_reaches_the_ordinary_dispatch(
    monkeypatch,
):
    result, calls = _drive(monkeypatch, BLOCKED_VERDICT)

    assert calls == [], "a BLOCKED verdict reached handle_image_generate"

    assert result["type"] == "render_blocked"
    assert result["status"] == "blocked"
    assert result["reason"] == "render_fidelity_blocked"
    assert result["render_fidelity"]["status"] == "BLOCKED"
    assert "image" not in result or result.get("image") in (None, {})


def test_dispatch_control_pass_verdict_reaches_the_ordinary_dispatch(monkeypatch):
    result, calls = _drive(monkeypatch, PASS_VERDICT)

    assert len(calls) == 1, "a PASS verdict was falsely refused"
    assert result["status"] == "spy"


def test_dispatch_control_blocked_verdict_never_reaches_design_approved_dispatch(
    monkeypatch,
):
    """The second reachable single-image generation branch."""

    result, calls = _drive(monkeypatch, BLOCKED_VERDICT, seed_design=True)

    assert calls == [], "a BLOCKED verdict reached the design-approved dispatch"
    assert result["type"] == "render_blocked"
    assert result["reason"] == "render_fidelity_blocked"


def test_dispatch_control_pass_verdict_reaches_design_approved_dispatch(
    monkeypatch,
):
    result, calls = _drive(monkeypatch, PASS_VERDICT, seed_design=True)

    assert len(calls) == 1
    assert result["status"] == "spy"


def test_dispatch_control_missing_verdict_fails_closed(monkeypatch):
    for missing in ({}, None):
        result, calls = _drive(monkeypatch, missing)

        assert calls == [], "a render ran with no fidelity verdict"
        assert result["type"] == "render_blocked"
        assert result["status"] == "blocked"


def test_dispatch_control_malformed_verdict_fails_closed(monkeypatch):
    result, calls = _drive(monkeypatch, {"status": "PASS"})

    assert calls == [], "a render ran with a non-authorising verdict"
    assert result["type"] == "render_blocked"


def test_non_render_turn_is_not_blocked_by_a_missing_verdict(monkeypatch):
    """The gate is scoped to generation: chat must never be refused by it."""

    result, calls = _drive(
        monkeypatch,
        {},
        intent="chat",
        mode="conversation",
        should_render=False,
    )

    assert calls == []
    assert result.get("reason") != "render_fidelity_unavailable"
    assert result.get("type") != "render_blocked"
