# -*- coding: utf-8 -*-
"""Persian -> English render instruction + semantic fidelity gate.

Scope: the chat LANGUAGE rule, the explicit-request register, the
ArchitecturalRenderInstructionV1 contract and the RenderSemanticFidelityV1
gate. No render, no ComfyUI, no vision, no BIM/IFC/Structure.

The Persian sentences below are TEST PAYLOADS. Production modules must not
name them — `test_production_never_names_the_test_sentences` proves it.
"""

from pathlib import Path

import ast

import pytest

from core.prompt_engine import PromptEngine
from core.chat.conversational_naturalness_v1 import resolve_turn_register
from core.chat.conversation_intent_boundary_v1 import classify_conversation_intent
from core.cognition.architectural_render_instruction_v1 import (
    CONTRACT as INSTRUCTION_CONTRACT,
    ROLE_FACADE_REFERENCE,
    ROLE_TARGET_BUILDING,
    build_render_instruction,
)
from core.cognition.render_semantic_fidelity_v1 import (
    CONTRACT as FIDELITY_CONTRACT,
    STATUS_BLOCKED,
    STATUS_PASS,
    MISSING_DIMENSION,
    MISSING_FLOOR_COUNT,
    MISSING_HARD_CONSTRAINT,
    NO_INSTRUCTION,
    REVERSED_INTENT,
    REVERSED_VALUE,
    UNVERIFIABLE_SOURCE,
    VALIDATOR_ERROR,
    validate_render_fidelity,
)


ROOT = Path(__file__).resolve().parents[1]

CHANGED_FILES = (
    "core/prompt_engine.py",
    "core/chat/conversational_naturalness_v1.py",
    "core/cognition/architectural_render_instruction_v1.py",
    "core/cognition/render_semantic_fidelity_v1.py",
)

# Payloads only.
CREATE_VILLA = "یک ویلای دو طبقه با نمای سنتی بساز"
DIMENSION_FIX = "اتاق ۱۲ متره، نه ۱۰ متر"
FACADE_REQUEST = "نمای جنوبی ویلا رو با آجر مدرن کن، سه طبقه، پنجره ها رو جابه جا نکن"
CAMERA_REQUEST = "نمای جنوبی رو از زاویه پایین رندر کن"
LIST_REQUEST = "کتاب معمایی چند تا انتخاب کن برام لیست کن هم اسم فارسی و هم اسم انگلیسیش رو"
CHAT_01 = "سلام، خودت رو معرفی کن و بگو چه کارهایی می‌تونی انجام بدی"


def _signals(text):
    return classify_conversation_intent(text)["signals"]


def _persian_chars(text):
    return [c for c in str(text) if "\u0600" <= c <= "\u06FF"]


# ==========================================================
# TASK 1 — LANGUAGE
# ==========================================================

def test_persian_rule_allows_requested_english_titles():
    """The Persian reply rule must no longer forbid English outright."""

    block = PromptEngine().build("کتاب معمایی چند تا انتخاب کن")
    rule = block.split("PERSIAN ORTHOGRAPHY")[0]

    assert "TARGET LANGUAGE:\nPersian" in rule
    assert "Do not use English words" not in rule
    assert "title" in rule.lower()
    assert "NEVER translate" in rule


def test_persian_reply_language_is_still_persian():
    rule = PromptEngine().build("سلام").split("PERSIAN ORTHOGRAPHY")[0]

    assert "Write the reply in Persian" in rule
    assert "Do NOT mix languages" in rule


def test_english_rule_states_internal_render_prompts_are_english():
    rule = PromptEngine().build("hello there").split("GENERAL RESPONSE")[0]

    assert "TARGET LANGUAGE:\nEnglish" in rule
    assert "RENDER INSTRUCTIONS ARE ALWAYS ENGLISH" in rule


def test_explicit_list_request_is_not_small_talk():
    assert resolve_turn_register(LIST_REQUEST, _signals(LIST_REQUEST)) == "detail_request"


def test_explicit_information_request_is_not_small_talk():
    text = "اسم فارسی و انگلیسیش رو بده"

    assert resolve_turn_register(text, _signals(text)) == "detail_request"


def test_explicit_design_request_is_not_small_talk():
    assert resolve_turn_register(CREATE_VILLA, _signals(CREATE_VILLA)) == "detail_request"


@pytest.mark.parametrize("text", ["سلام", "سلام خوبی؟", "چطوری؟"])
def test_greetings_are_still_greetings(text):
    assert resolve_turn_register(text, _signals(text)) == "greeting"


@pytest.mark.parametrize("text", ["امروز هوا خوبه", "من معماری دوست ندارم"])
def test_plain_statements_are_still_small_talk(text):
    assert resolve_turn_register(text, _signals(text)) == "casual_chat"


def test_chat01_invariant_is_preserved():
    """The same sentence flips register ONLY because its SIGNAL is present."""

    assert resolve_turn_register(CHAT_01) == "greeting"
    assert resolve_turn_register(CHAT_01, _signals(CHAT_01)) == "detail_request"


def test_correction_is_still_a_detail_request():
    text = "معمایی گفتم نه معماری"

    assert resolve_turn_register(text, _signals(text)) == "detail_request"


# ==========================================================
# TASK 2 — THE ENGLISH RENDER INSTRUCTION
# ==========================================================

def test_contract_identity_and_no_render():
    contract = build_render_instruction(CREATE_VILLA)

    assert contract["contract"] == INSTRUCTION_CONTRACT
    assert contract["comfy_invoked"] is False
    assert contract["render_executed"] is False


def test_floor_count_is_preserved_in_english():
    contract = build_render_instruction(CREATE_VILLA)

    assert contract["constraints"]["floor_count"]["value"] == 2
    assert "2 floors" in contract["english_instruction"]


def test_geometry_and_facade_reach_the_instruction():
    contract = build_render_instruction(FACADE_REQUEST)

    assert contract["constraints"]["floor_count"]["value"] == 3
    assert "3 floors" in contract["english_instruction"]
    assert "south facade" in contract["english_instruction"]
    assert "brick" in contract["english_instruction"].lower()


def test_opening_constraint_is_preserved():
    contract = build_render_instruction(FACADE_REQUEST)

    assert contract["constraints"]["openings"]["preserve_windows"] is True
    assert "window" in contract["english_instruction"].lower()


def test_camera_perspective_is_preserved():
    contract = build_render_instruction(CAMERA_REQUEST)

    assert "low camera angle" in contract["constraints"]["camera"]
    assert "Camera / view:" in contract["english_instruction"]


def test_a_rejected_dimension_is_never_a_requirement():
    contract = build_render_instruction(DIMENSION_FIX)

    required = [item["value"] for item in contract["constraints"]["dimensions"]]
    rejected = [item["value"] for item in contract["constraints"]["rejected_dimensions"]]

    assert required == [12]
    assert rejected == [10]
    assert "Required dimension: 12 m." in contract["english_instruction"]
    assert "Required dimension: 10 m." not in contract["english_instruction"]


def test_negation_is_preserved_as_a_prohibition():
    contract = build_render_instruction(DIMENSION_FIX)

    assert contract["constraints"]["negations"]["rejected_span"]
    assert "Do NOT use or repeat" in contract["english_instruction"]


def test_image_a_is_the_facade_reference_and_b_the_target():
    contract = build_render_instruction(CREATE_VILLA, references={"A": "a.png", "B": "b.png"})

    assert contract["references"]["A"]["role"] == ROLE_FACADE_REFERENCE
    assert contract["references"]["B"]["role"] == ROLE_TARGET_BUILDING
    assert contract["references"]["A"]["authority"] == "appearance_only"
    assert contract["references"]["B"]["authority"] == "geometry"
    assert contract["references"]["geometry_authority"] == ROLE_TARGET_BUILDING


def test_the_instruction_is_english_when_there_is_no_quoted_rejection():
    contract = build_render_instruction(CREATE_VILLA)

    assert not _persian_chars(contract["english_instruction"])


def test_the_contract_reuses_the_existing_modules():
    contract = build_render_instruction(FACADE_REQUEST)

    sources = contract["sources"]

    assert sources["understanding"] == "PersianArchitecturalUnderstandingV1"
    assert sources["compiled"] == "ArchitecturalCompiledPromptV1"
    assert sources["terminology"] == "ArchitecturalTerminologyV1"


def test_a_create_request_does_not_carry_the_refine_opener():
    contract = build_render_instruction(CREATE_VILLA)

    assert contract["intent"] == "CREATE"
    assert "Refine the architectural design" not in contract["english_instruction"]
    assert "Create a new architectural design" in contract["english_instruction"]


# ==========================================================
# TASK 3 — THE FIDELITY GATE
# ==========================================================

def test_a_faithful_instruction_passes():
    for source in (CREATE_VILLA, DIMENSION_FIX, FACADE_REQUEST, CAMERA_REQUEST):
        verdict = validate_render_fidelity(source)

        assert verdict["contract"] == FIDELITY_CONTRACT
        assert verdict["status"] == STATUS_PASS, (source, verdict["reason"])
        assert verdict["may_proceed_to_render"] is True


def test_missing_floor_count_blocks():
    verdict = validate_render_fidelity(
        CREATE_VILLA,
        "Create a new architectural design. Adopt a traditional architectural language.",
    )

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == MISSING_FLOOR_COUNT
    assert verdict["may_proceed_to_render"] is False


def test_wrong_floor_count_blocks():
    """Value comparison, not word presence: the word 'floors' is there."""

    verdict = validate_render_fidelity(
        CREATE_VILLA, "Create a new architectural design. The building has exactly 5 floors."
    )

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == "FLOOR_COUNT_MISMATCH"


def test_missing_dimension_blocks():
    verdict = validate_render_fidelity(DIMENSION_FIX, "Do NOT use or repeat the old value.")

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == MISSING_DIMENSION


def test_repeating_a_rejected_value_blocks():
    verdict = validate_render_fidelity(
        DIMENSION_FIX, "Required dimension: 12 m. Required dimension: 10 m."
    )

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == REVERSED_VALUE


def test_reversing_create_into_refine_blocks():
    verdict = validate_render_fidelity(
        CREATE_VILLA, "Refine the architectural design. The building has exactly 2 floors."
    )

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == REVERSED_INTENT


def test_missing_hard_constraint_blocks():
    verdict = validate_render_fidelity(
        FACADE_REQUEST, "The building has exactly 3 floors. south facade, brick"
    )

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] in (MISSING_HARD_CONSTRAINT, MISSING_DIMENSION)


def test_an_empty_instruction_blocks_fail_closed():
    verdict = validate_render_fidelity(CREATE_VILLA, "")

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == NO_INSTRUCTION


def test_an_empty_request_blocks_fail_closed():
    verdict = validate_render_fidelity("", "anything")

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == UNVERIFIABLE_SOURCE


def test_a_broken_contract_blocks_fail_closed():
    verdict = validate_render_fidelity(CREATE_VILLA, contract={"constraints": "not-a-dict"})

    assert verdict["status"] == STATUS_BLOCKED
    assert verdict["reason_code"] == VALIDATOR_ERROR


def test_the_gate_never_defaults_to_pass():
    """A verdict is always explicit, and BLOCKED always carries a reason."""

    for source, instruction in (
        (CREATE_VILLA, ""),
        (DIMENSION_FIX, "Required dimension: 10 m."),
        ("", ""),
    ):
        verdict = validate_render_fidelity(source, instruction)

        assert verdict["status"] in (STATUS_PASS, STATUS_BLOCKED)

        if verdict["status"] == STATUS_BLOCKED:
            assert verdict["reason_code"]
            assert verdict["reason"]


# ==========================================================
# SAFETY
# ==========================================================

def _runtime_strings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()

    for node in ast.walk(tree):

        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue

        body = getattr(node, "body", [])

        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):

            docstrings.add(id(body[0].value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_production_never_names_the_test_sentences():
    forbidden = ("معمایی", "mystery", "مهدی")

    for relative in CHANGED_FILES:

        for literal in _runtime_strings(ROOT / relative):

            for token in forbidden:

                assert token not in literal, (relative, token)


def test_no_render_or_comfy_import_in_the_new_modules():
    for relative in CHANGED_FILES:

        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))

        modules = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                modules.extend(alias.name for alias in node.names)

            elif isinstance(node, ast.ImportFrom):

                modules.append(node.module or "")

        joined = " ".join(modules)

        assert "comfy" not in joined.lower()
        assert "render_runtime" not in joined.lower()
