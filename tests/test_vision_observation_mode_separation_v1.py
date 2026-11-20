# ==========================================================
# VISION_OBSERVATION_MODE_SEPARATION_V1 — CONTRACT / ACCEPTANCE TESTS
#
# The image path had ONE output shape for EVERY image turn: the
# architectural interpretation (space_type + function + relations). So
#
#   "فقط عناصر قابل مشاهده تصویر را لیست کن"
#
# was answered with "1. Possible architectural space: master bedroom …".
# Observation and interpretation were fused into one contract.
#
# This phase separates them: the observation layer answers "what is
# visibly present?" and nothing else, and the interpretation layer keeps
# its existing path.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_vision_observation_mode_separation_v1.py
#   .venv/Scripts/python.exe tests/test_vision_observation_mode_separation_v1.py
# ==========================================================


import json
import os
import sys


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


from core.vision.vision_observation_mode_v1 import (  # noqa: E402
    CONTRACT,
    MODE,
    detect_observation_request,
    build_observation,
    render_observation,
)

from core.vision.image_intent_v1 import (  # noqa: E402
    classify_image_intent,
    build_mode_contract,
    INTENT_OBSERVE,
    INTENT_ANALYZE,
    MODE_IMAGE_OBSERVATION,
    MODE_IMAGE_ANALYSIS,
)

from core.vision.architectural_vision_interpreter_v1 import (  # noqa: E402
    interpret_architectural_vision,
)

from core.chat.response_adapter import ResponseAdapter  # noqa: E402


OBSERVATION_REQUEST = "فقط عناصر قابل مشاهده تصویر را لیست کن"

# ---- TEST 1 — an image with bedroom furniture ----

BEDROOM_FURNITURE = {
    "image_type": "architectural_render_or_photo",
    "confidence": "HIGH",
    "observed": ["bed visible", "wardrobe visible", "desk visible"],
    "inferred": [],
    "unresolved": [],
    "architectural_elements": ["bed", "wardrobe", "desk"],
    "safety": {"supports_region_grounding": False},
}

# ---- TEST 2 — bed + ensuite + dressing ----

MASTER_SUITE = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "bed visible",
        "dressing room visible",
        "ensuite bathroom visible",
    ],
    "inferred": [],
    "unresolved": [],
    "architectural_elements": ["bed", "wardrobe", "bathroom"],
    "safety": {"supports_region_grounding": False},
}

# ---- the provider's own payload for the reported image ----

RUN_B = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "mirrored layouts", "Persian text",
        "furniture icons", "bed", "wardrobe", "desk", "door symbols",
    ],
    "inferred": ["parental suite", "alternative layout options"],
    "unresolved": ["exact dimensions"],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "wall"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین"],
    "safety": {"supports_region_grounding": False},
}


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))


def _observation_text(understanding, language="fa"):

    observation = build_observation(understanding, language=language)

    return observation, render_observation(observation, language)


# ==========================================================
# TEST 1 — BEDROOM FURNITURE + "list the visible elements"
# ==========================================================

def test_1_the_request_is_detected_as_observation():

    intent = classify_image_intent(OBSERVATION_REQUEST)

    return _check(
        "T1a. 'فقط عناصر قابل مشاهده تصویر را لیست کن' is its own intent "
        "(observe), not analyze",
        intent["intent"] == INTENT_OBSERVE,
        {"intent": intent},
    )


def test_1_the_observation_lists_the_bed():

    observation, text = _observation_text(BEDROOM_FURNITURE)

    names = [entry.get("name") for entry in observation.get("elements") or []]

    return _check(
        "T1b. PASS — the bed is detected (as a sleeping element, not a room)",
        "sleeping_element" in names
        and "تخت" in text,
        {"names": names},
    )


def test_1_the_observation_never_classifies_the_space():

    observation, text = _observation_text(BEDROOM_FURNITURE)

    lowered = text.lower()

    return _check(
        "T1c. NEGATIVE CONTROL — the observation carries no master-bedroom "
        "classification (the brief's expected failure mode is absent)",
        observation.get("space_type") is None
        and "master" not in lowered
        and "اتاق خواب مستر" not in text
        and observation.get("possible_function") == []
        and observation.get("architectural_interpretation") == [],
        {"space_type": observation.get("space_type"), "text": text},
    )


def test_1_the_observation_contains_no_reasoning_vocabulary():

    _observation, text = _observation_text(BEDROOM_FURNITURE)

    # The last line is the scope note, which NAMES what is excluded — so
    # the check runs on the body only.
    body = "\n".join(text.splitlines()[:-1]).lower()

    forbidden = (
        "privacy", "public", "private zone", "zoning", "circulation",
        "design intent", "function",
        "حریم", "عمومی", "خصوصی", "استدلال طراحی", "کاربری",
    )

    hits = [word for word in forbidden if word in body]

    return _check(
        "T1d. the observation body carries no privacy / zoning / design-intent "
        "/ function vocabulary (and the scope note says what is excluded)",
        not hits and "مشاهده" in text,
        {"hits": hits, "body": body},
    )


def test_1_the_observation_contract_shape():

    observation, _text = _observation_text(BEDROOM_FURNITURE)

    elements = observation.get("elements") or []

    return _check(
        "T1e. the contract is mode/elements/unknowns with "
        "name/evidence/confidence per element",
        observation.get("contract") == CONTRACT
        and observation.get("mode") == MODE
        and isinstance(observation.get("elements"), list)
        and isinstance(observation.get("unknowns"), list)
        and all(
            entry.get("name")
            and isinstance(entry.get("evidence"), list)
            and entry.get("confidence")
            for entry in elements
        ),
        {"observation": observation},
    )


# ==========================================================
# TEST 2 — bed + ensuite + dressing
# ==========================================================

def test_2_the_interpretation_may_say_master_bedroom():

    interpretation = interpret_architectural_vision(MASTER_SUITE)

    return _check(
        "T2a. bed + ensuite + dressing -> the INTERPRETATION layer may say "
        "'possible master bedroom' (multiple evidence sources)",
        interpretation["space_type"] == "master bedroom"
        and "possible private couple bedroom"
        in (interpretation.get("possible_function") or [])
        and len(interpretation.get("classification_basis") or []) >= 3,
        {
            "space_type": interpretation["space_type"],
            "basis": interpretation.get("classification_basis"),
        },
    )


def test_2_the_observation_may_not():

    observation, _fa = _observation_text(MASTER_SUITE, language="fa")

    _observation_en, text = _observation_text(MASTER_SUITE, language="en")

    return _check(
        "T2b. the OBSERVATION layer says nothing about a master bedroom — "
        "only the elements",
        observation.get("space_type") is None
        and "master" not in text.lower()
        and "bathroom or ensuite" in text.lower()
        and "wardrobe or closet" in text.lower(),
        {"text": text},
    )


def test_2_a_single_bed_is_never_a_master_bedroom():

    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible"],
            "architectural_elements": ["bed"],
            "confidence": "MEDIUM",
        }
    )

    return _check(
        "T2c. brief rule 1: bed -> sleeping element, NEVER 'master bedroom' "
        "from a single bed",
        interpretation["space_type"] == "bedroom"
        and interpretation.get("classification_basis") == ["sleeping element"],
        {
            "space_type": interpretation["space_type"],
            "basis": interpretation.get("classification_basis"),
        },
    )


def test_2_the_master_label_is_hedged_as_possible():

    interpretation = interpret_architectural_vision(MASTER_SUITE)

    return _check(
        "T2d. even with multiple sources the master label stays a "
        "POSSIBILITY, never a fact",
        all(
            "possible" in value
            for value in interpretation.get("possible_function") or []
        ),
        {"possible_function": interpretation.get("possible_function")},
    )


# ==========================================================
# TEST 3 — EXISTING BEHAVIOUR IS PRESERVED
# ==========================================================

def test_3_ordinary_image_questions_keep_their_intent():

    cases = (
        "تحلیلت از این عکس چیه؟",
        "این تصویر را فقط تحلیل کن",
        "این عکس چیه؟",
        "what is in this image?",
        "analyze this image",
    )

    intents = {
        text: classify_image_intent(text)["intent"] for text in cases
    }

    return _check(
        "T3a. ordinary analysis questions are still ANALYZE (only a "
        "visible-evidence + list/only request becomes observation)",
        all(intent == INTENT_ANALYZE for intent in intents.values()),
        {"intents": intents},
    )


def test_3_the_only_marker_alone_is_not_enough():

    return _check(
        "T3b. 'این تصویر را فقط تحلیل کن' is NOT observation (two-part "
        "detection: 'فقط' alone must not switch the mode)",
        detect_observation_request("این تصویر را فقط تحلیل کن") is False
        and detect_observation_request("فقط بگو چه چیزی میبینی") is False
        and detect_observation_request(OBSERVATION_REQUEST) is True
        and detect_observation_request(
            "list only the visible elements"
        ) is True,
        {},
    )


def test_3_the_interpretation_message_is_unchanged():

    interpretation = interpret_architectural_vision(RUN_B)

    response = ResponseAdapter().adapt(
        {
            "type": "image_analysis",
            "status": "success",
            "result": interpretation,
            "architectural_interpretation": interpretation,
            "language": {"output_language": "english"},
        }
    )

    return _check(
        "T3c. the interpretation path still renders its four sections",
        response["message"].startswith("1. Possible architectural space:")
        and "2. Visible elements:" in response["message"]
        and "4. Uncertain or undetermined:" in response["message"],
        {"message": response["message"][:200]},
    )


def test_3_the_mode_contract_adds_observation_without_changing_the_rest():

    observe_contract = build_mode_contract(
        {
            "type": "image_observation",
            "vision": {"intent": INTENT_OBSERVE},
        },
        has_image=True,
    )

    analyze_contract = build_mode_contract(
        {
            "type": "image_analysis",
            "vision": {"intent": INTENT_ANALYZE},
        },
        has_image=True,
    )

    return _check(
        "T3d. the mode contract gains IMAGE_OBSERVATION, never renders, and "
        "IMAGE_ANALYSIS is untouched",
        observe_contract["mode"] == MODE_IMAGE_OBSERVATION
        and observe_contract["render"] is False
        and analyze_contract["mode"] == MODE_IMAGE_ANALYSIS
        and analyze_contract["render"] is False,
        {"observe": observe_contract, "analyze": analyze_contract},
    )


def test_3_the_observation_message_renders_through_the_adapter():

    observation = build_observation(RUN_B, language="en")

    response = ResponseAdapter().adapt(
        {
            "type": "image_observation",
            "status": "success",
            "result": observation,
            "observation": observation,
            "language": {"output_language": "english"},
        }
    )

    return _check(
        "T3e. the observation has its OWN message, with no space section",
        response["message"].startswith("Elements visible in the image:")
        and "Possible architectural space" not in response["message"],
        {"message": response["message"][:200]},
    )


# ==========================================================
# TEST 4 — NO RENDER, NO EXTRA INFERENCE, NO NETWORK
# ==========================================================

def test_4_the_observation_adds_no_provider_call():

    observation = build_observation(RUN_B, language="fa")

    return _check(
        "T4a. the observation makes no provider call of its own (it consumes "
        "the understanding the turn already has)",
        observation.get("provider_calls") == 0
        and observation.get("llm_used") is False
        and observation.get("network_used") is False,
        {
            "provider_calls": observation.get("provider_calls"),
            "llm": observation.get("llm_used"),
        },
    )


def test_4_no_render_and_no_side_effects():

    observation = build_observation(RUN_B, language="fa")

    return _check(
        "T4b. no render, no geometry, no ComfyUI, no storage, no teaching",
        observation.get("render_requested") is False
        and observation.get("geometry_touched") is False
        and observation.get("comfy_invoked") is False
        and observation.get("storage_used") is False
        and observation.get("teaching_used") is False
        and observation.get("read_only") is True,
        {},
    )


def test_4_the_observation_is_deterministic():

    first = json.dumps(
        build_observation(RUN_B, language="fa"),
        ensure_ascii=False, sort_keys=True,
    )

    second = json.dumps(
        build_observation(RUN_B, language="fa"),
        ensure_ascii=False, sort_keys=True,
    )

    return _check(
        "T4c. the observation is deterministic (no sampling, no clock, no "
        "network)",
        first == second,
        {},
    )


# ==========================================================
# THE RULES
# ==========================================================

def test_rule_4_uncertainty_is_stated_never_invented():

    observation, text = _observation_text(
        {
            "image_type": "floor_plan_or_sketch",
            "observed": ["window symbols", "bed"],
            "inferred": ["ensuite bathroom"],
            "architectural_elements": ["window", "bed", "bathroom"],
            "confidence": "MEDIUM",
        }
    )

    names = [entry.get("name") for entry in observation.get("elements") or []]

    return _check(
        "R4. an inference is never an element, an unconfirmed claim says so, "
        "and nothing is invented",
        "bathroom_or_ensuite" not in names
        and any(
            entry.get("reason_code") == "inference"
            for entry in observation.get("not_confirmed") or []
        )
        and "تأییدنشده" in text,
        {"elements": names, "not_confirmed": observation.get("not_confirmed")},
    )


def test_rule_5_the_evidence_hierarchy_is_encoded():

    observation = build_observation(
        {
            "image_type": "floor_plan_or_sketch",
            "observed": ["bed visible", "window symbols"],
            "architectural_elements": ["bed", "window", "wall"],
            "confidence": "HIGH",
        },
        language="fa",
    )

    by_name = {entry.get("name"): entry for entry in observation.get("elements") or []}

    return _check(
        "R5. a visible object is high/medium, a spatial symbol is medium and "
        "flagged, an element-list-only entry is not an element",
        by_name.get("sleeping_element", {}).get("confidence") == "high"
        and by_name.get("window", {}).get("confidence") == "medium"
        and by_name.get("window", {}).get("status") == "symbol_reading"
        and "wall" not in by_name,
        {"elements": by_name},
    )


def test_rule_6_the_observation_is_reusable_by_later_layers():

    observation = build_observation(RUN_B, language="fa")

    interpretation = interpret_architectural_vision(RUN_B)

    return _check(
        "R6. the observation is a machine contract a later layer can consume "
        "(and the interpretation layer still runs on the same evidence)",
        observation.get("feeds") == "ArchitecturalVisionInterpreterV1"
        and isinstance(observation.get("elements"), list)
        and interpretation.get("space_type") in ("bedroom", "master bedroom"),
        {
            "feeds": observation.get("feeds"),
            "space_type": interpretation.get("space_type"),
        },
    )


def test_an_empty_understanding_is_honest():

    observation = build_observation(
        {"image_type": "unknown", "observed": [], "architectural_elements": []},
        language="fa",
    )

    return _check(
        "R7. with no evidence the observation lists nothing and says why",
        observation.get("elements") == []
        and bool(observation.get("unknowns")),
        {"observation": observation},
    )


# ==========================================================
# TEST 5 — THE OBSERVATION IS NOT DISCARDED BEFORE IT REACHES
#          THE USER  (VISION_OBSERVATION_MODE_SEPARATION_V1)
#
# The inherited implementation produced the observation and then threw
# it away at the adapter boundary: `response.result` stayed the
# observation DICT, while the UI does `response.result || response.message`
# (ui/static/app.js) and app.py's autosave reads
# `formatted_response["result"] or ["message"]`. So the user saw
# "[object Object]" and the conversation history stored a dict repr.
# ==========================================================

def test_5_the_adapter_hands_the_observation_to_the_ui_as_text():

    observation = build_observation(BEDROOM_FURNITURE, language="fa")

    response = ResponseAdapter().adapt(
        {
            "type": "image_observation",
            "status": "success",
            "result": observation,
            "observation": observation,
            "language": {"output_language": "persian"},
        }
    )

    return _check(
        "T5a. response.result is the RENDERED TEXT (the UI shows "
        "`result || message`, so a dict renders '[object Object]')",
        isinstance(response.get("result"), str)
        and response["result"].startswith("عناصر قابل مشاهده"),
        {"result_type": type(response.get("result")).__name__},
    )


def test_5_the_structured_observation_survives_the_adapter():

    observation = build_observation(BEDROOM_FURNITURE, language="fa")

    response = ResponseAdapter().adapt(
        {
            "type": "image_observation",
            "status": "success",
            "result": observation,
            "observation": observation,
            "language": {"output_language": "persian"},
        }
    )

    return _check(
        "T5b. the structured observation is exposed at the API boundary "
        "under `observation` (beside `architectural_interpretation`)",
        isinstance(response.get("observation"), dict)
        and response["observation"].get("mode") == MODE
        and response["observation"].get("space_type") is None,
        {"keys": sorted(response.keys())},
    )


def test_5_a_persian_response_renders_persian():

    observation = build_observation(BEDROOM_FURNITURE, language="fa")

    response = ResponseAdapter().adapt(
        {
            "type": "image_observation",
            "status": "success",
            "result": observation,
            "observation": observation,
            # The pipeline declares "persian", not "fa".
            "language": {"output_language": "persian"},
        }
    )

    text = response.get("message") or ""

    return _check(
        "T5c. a response declaring 'persian' renders PERSIAN — the reply "
        "must not contradict its own language contract",
        "عناصر قابل مشاهده" in text
        and "Elements visible" not in text
        and "اتاق خواب مستر" not in text,
        {"message": text[:160]},
    )


def test_5_confidence_follows_the_evidence_class_not_the_spelling():

    # The provider's own payload writes a bare "bed" — the brief's
    # hierarchy grades a visible OBJECT as highest, so the confidence
    # must not depend on whether the model typed the word "visible".
    bare = build_observation(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed"],
            "architectural_elements": ["bed"],
            "confidence": "HIGH",
        },
        language="fa",
    )

    by_name = {entry["name"]: entry for entry in bare["elements"]}

    return _check(
        "T5d. a visible object is HIGH whether or not the phrase says "
        "'visible'; provider-only plan symbols remain unconfirmed",
        by_name.get("sleeping_element", {}).get("confidence") == "high"
        and by_name.get("sleeping_element", {}).get("explicit_assertion")
        is False
        and build_observation(
            {
                "image_type": "floor_plan_or_sketch",
                "observed": ["window symbols"],
                "architectural_elements": ["window"],
            },
            language="fa",
        )["elements"] == [],
        {"elements": by_name},
    )


def test_5_a_text_label_is_not_evidence_for_an_element():

    """The reported image carries the visible text label
    "حریم خصوصی در اتاق والدین". The grounding layer's own contract says a
    label is "only inside a visible text label" — visible TEXT, not the
    element — so it must never be listed as an element's evidence, or an
    OBSERVATION answer ends up emitting privacy vocabulary the brief
    forbids. (It had also been attached to `entrance` by a homograph: the
    preposition "در" matched the element alias "در" = door.)
    """

    observation = build_observation(RUN_B, language="fa")

    blob = json.dumps(observation, ensure_ascii=False)

    return _check(
        "T5f. the image's visible TEXT label never becomes element evidence, "
        "and the observation emits no privacy wording",
        "حریم خصوصی" not in blob
        and "حریم" not in blob
        and "خصوصی" not in blob
        and all(
            "حریم" not in phrase and "خصوصی" not in phrase
            for entry in observation.get("elements") or []
            for phrase in entry.get("evidence") or []
        ),
        {"elements": observation.get("elements")},
    )


def test_5_the_contract_uses_the_briefs_element_list_name():

    observation = build_observation(BEDROOM_FURNITURE, language="en")

    return _check(
        "T5e. the contract exposes `visible_elements` (the brief's name) "
        "mirroring the canonical `elements` list",
        observation.get("visible_elements") == observation.get("elements")
        and isinstance(observation.get("visible_elements"), list)
        and observation.get("mode") == "OBSERVATION"
        and observation.get("unknowns") == [],
        {"counts": observation.get("counts")},
    )


# ==========================================================
# TEST 6 — THE BRIEF'S TWO ACCEPTANCE CASES, SIDE BY SIDE
# ==========================================================

def test_6_the_briefs_acceptance_pair():

    """Case 1: a bedroom image + "list only the visible elements".

    PASS = the bed is detected. FAIL = a master-bedroom classification.
    Case 2: bed + closet + bathroom — observation = elements only,
    interpretation = a POSSIBLE master bedroom.
    """

    observation, text = _observation_text(BEDROOM_FURNITURE, language="fa")

    names = [entry.get("name") for entry in observation.get("elements") or []]

    case_1 = (
        "sleeping_element" in names
        and observation.get("space_type") is None
        and "مستر" not in text
        and all(
            entry.get("evidence") and entry.get("confidence")
            for entry in observation["elements"]
        )
    )

    suite_observation, suite_text = _observation_text(MASTER_SUITE, language="fa")

    suite_names = [
        entry.get("name") for entry in suite_observation.get("elements") or []
    ]

    interpretation = interpret_architectural_vision(MASTER_SUITE)

    case_2 = (
        set(suite_names) == {"sleeping_element", "wardrobe_or_closet",
                             "bathroom_or_ensuite"}
        and "مستر" not in suite_text
        and interpretation["space_type"] == "master bedroom"
        and all(
            "possible" in value
            for value in interpretation.get("possible_function") or []
        )
    )

    return _check(
        "T6. brief acceptance: observation lists elements only (bed "
        "detected, never 'master bedroom'); the INTERPRETATION layer may "
        "say 'possible master bedroom' from bed + closet + bathroom",
        case_1 and case_2,
        {
            "case_1_names": names,
            "case_2_names": suite_names,
            "space_type": interpretation["space_type"],
        },
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("VISION_OBSERVATION_MODE_SEPARATION_V1 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_1_the_request_is_detected_as_observation,
        test_1_the_observation_lists_the_bed,
        test_1_the_observation_never_classifies_the_space,
        test_1_the_observation_contains_no_reasoning_vocabulary,
        test_1_the_observation_contract_shape,
        test_2_the_interpretation_may_say_master_bedroom,
        test_2_the_observation_may_not,
        test_2_a_single_bed_is_never_a_master_bedroom,
        test_2_the_master_label_is_hedged_as_possible,
        test_3_ordinary_image_questions_keep_their_intent,
        test_3_the_only_marker_alone_is_not_enough,
        test_3_the_interpretation_message_is_unchanged,
        test_3_the_mode_contract_adds_observation_without_changing_the_rest,
        test_3_the_observation_message_renders_through_the_adapter,
        test_4_the_observation_adds_no_provider_call,
        test_4_no_render_and_no_side_effects,
        test_4_the_observation_is_deterministic,
        test_rule_4_uncertainty_is_stated_never_invented,
        test_rule_5_the_evidence_hierarchy_is_encoded,
        test_rule_6_the_observation_is_reusable_by_later_layers,
        test_an_empty_understanding_is_honest,
        test_5_the_adapter_hands_the_observation_to_the_ui_as_text,
        test_5_the_structured_observation_survives_the_adapter,
        test_5_a_persian_response_renders_persian,
        test_5_confidence_follows_the_evidence_class_not_the_spelling,
        test_5_a_text_label_is_not_evidence_for_an_element,
        test_5_the_contract_uses_the_briefs_element_list_name,
        test_6_the_briefs_acceptance_pair,
    ]

    for test in tests:

        try:

            test()

        except Exception as error:

            _check(
                test.__name__ + " (raised)",
                False,
                "%s: %s" % (type(error).__name__, error),
            )

    failed = [item for item in _RESULTS if not item[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print(
                "        ",
                json.dumps(detail, ensure_ascii=False, default=str)[:700],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())

