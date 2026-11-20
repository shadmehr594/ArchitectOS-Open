# ==========================================================
# ARCHITECTURAL_VISION_GROUNDING_V1 — CONTRACT / ACCEPTANCE TESTS
#
# THE REPORTED FAILURE (the teacher's own image)
#
#   "Expected absence: no window."
#   "False positive: window detected.
#    False negative: closet not detected, bathroom not detected."
#
# The provider payloads in core_api.log show the mechanism:
#   run A  observed: [... 'door symbols', 'window symbols' ...]
#   run B  observed: [... 'bed', 'wardrobe', 'desk', 'door symbols']
# and the interpreter hardcoded
#   "private bathroom connection is not visible"
#   "dressing or closet zone is not visible"
# for EVERY bedroom — so an observed wardrobe was announced as visible
# and as not visible in the same answer.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_architectural_vision_grounding_v1.py
#   .venv/Scripts/python.exe tests/test_architectural_vision_grounding_v1.py
# ==========================================================


import json
import sys
import os


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


from core.vision.architectural_vision_grounding_v1 import (  # noqa: E402
    CONTRACT,
    ground_vision_evidence,
    expected_elements,
    render_grounding,
    ELEMENTS,
)

from core.vision.architectural_vision_interpreter_v1 import (  # noqa: E402
    interpret_architectural_vision,
)

from core.vision.vision_report_v1 import (  # noqa: E402
    render_vision_evidence_report,
    render_vision_report,
)


# ---- the two payloads the provider actually returned, verbatim ----

RUN_A = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "furniture icons", "Persian text",
        "mirror-image layout", "door symbols", "window symbols",
        "watermark text",
    ],
    "inferred": [
        "parental suite", "alternative layout options", "bedroom layout",
    ],
    "unresolved": [
        "room dimensions", "material specifications",
        "unverified from image: bedroom layout",
    ],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "window"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین", "اتاق والدین"],
    "safety": {"supports_region_grounding": False},
}

RUN_B = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "mirrored layouts", "Persian text",
        "furniture icons", "bed", "wardrobe", "desk", "door symbols",
    ],
    "inferred": [
        "parental suite", "alternative layout options", "bedroom layout",
    ],
    "unresolved": [
        "exact dimensions", "material specifications", "actual scale",
        "unverified from image: bedroom layout",
    ],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "wall"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین", "اتاق والدین"],
    "safety": {"supports_region_grounding": False},
}

EMPTY = {
    "image_type": "unknown",
    "observed": [],
    "inferred": [],
    "unresolved": [],
    "architectural_elements": [],
    "confidence": "LOW",
}


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))


def _status(grounding, element_id):

    for entry in grounding.get("elements") or []:

        if entry.get("element") == element_id:

            return entry.get("status")

    return None


def _visible(interpretation, phrase):

    return phrase in (interpretation.get("observed_elements") or [])


# ==========================================================
# 1. THE REPORTED FALSE POSITIVE — THE WINDOW
# ==========================================================

def test_a_symbol_reading_is_not_visibility():

    grounding = ground_vision_evidence(RUN_A, space_type="master bedroom")

    return _check(
        "G1. 'window symbols' is a plan-symbol reading, NOT a visible window",
        _status(grounding, "window") == "symbol_reading"
        and "window" not in (grounding.get("visible_elements") or []),
        {"window_status": _status(grounding, "window")},
    )


def test_the_answer_never_claims_the_window_as_visible():

    interpretation = interpret_architectural_vision(RUN_A)

    return _check(
        "G2. the reported image's answer never publishes a visible window",
        not _visible(interpretation, "daylight opening visible"),
        {
            "observed_elements": interpretation.get("observed_elements"),
            "unverified": interpretation.get("unverified_claims"),
        },
    )


def test_the_window_claim_is_reported_as_unverified_not_dropped():

    interpretation = interpret_architectural_vision(RUN_A)

    return _check(
        "G3. the claim is still REPORTED — as unverified, with its reason",
        "daylight opening visible" in (interpretation.get("unverified_claims") or [])
        and any(
            entry.get("element") == "window"
            and "symbol" in (entry.get("reason") or "")
            for entry in (interpretation.get("grounding") or {}).get("rejected_claims") or []
        ),
        {
            "unverified": interpretation.get("unverified_claims"),
            "rejected": [
                entry for entry in
                (interpretation.get("grounding") or {}).get("rejected_claims") or []
                if entry.get("element") == "window"
            ],
        },
    )


def test_an_explicit_visibility_claim_is_still_grounded():

    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "window visible"],
            "architectural_elements": ["bed", "window"],
            "confidence": "MEDIUM",
        }
    )

    return _check(
        "G4. no over-correction: an explicit 'window visible' observation IS "
        "grounded",
        _visible(interpretation, "daylight opening visible")
        and _visible(interpretation, "sleeping element visible"),
        {"observed_elements": interpretation.get("observed_elements")},
    )


# ==========================================================
# 2. THE REPORTED FALSE NEGATIVES — CLOSET AND BATHROOM
# ==========================================================

def test_an_observed_closet_is_visible_and_not_contradicted():

    interpretation = interpret_architectural_vision(RUN_B)

    unknowns = " ".join(interpretation.get("unknowns") or []).lower()

    return _check(
        "G5. an observed wardrobe is VISIBLE, and no line says the closet is "
        "not visible (the contradiction is gone)",
        _visible(interpretation, "storage or dressing element visible")
        and "closet zone is not visible" not in unknowns
        and "dressing or closet zone is not visible" not in unknowns,
        {
            "observed_elements": interpretation.get("observed_elements"),
            "unknowns": interpretation.get("unknowns"),
        },
    )


def test_a_never_reported_zone_is_unknown_not_absent():

    interpretation = interpret_architectural_vision(RUN_B)

    unknowns = " ".join(interpretation.get("unknowns") or [])

    return _check(
        "G6. the bathroom was never reported -> 'not reported ... unknown, "
        "not absent' — never a claim that it is not visible",
        "private bathroom" in unknowns
        and "not reported in the visible evidence" in unknowns
        and "unknown, not absent" in unknowns,
        {"unknowns": interpretation.get("unknowns")},
    )


def test_expected_zones_are_surfaced_as_gaps():

    grounding = ground_vision_evidence(RUN_B, space_type="master bedroom")

    gaps = {entry.get("element") for entry in grounding.get("expected_gaps") or []}

    return _check(
        "G7. the zones that were EXPECTED but never reported are listed "
        "(the false negatives become visible gaps)",
        {"bathroom_or_ensuite", "wc", "circulation"}.issubset(gaps),
        {"gaps": sorted(gaps)},
    )


def test_expected_elements_come_from_the_frozen_corpus():

    expected = {element for element, _source in expected_elements("master bedroom")}

    sourced = {
        source for _element, source in expected_elements("master bedroom")
    }

    return _check(
        "G8. the expected set is DERIVED from the frozen corpus (the space's "
        "own role, its typical adjacency and its door requirement)",
        {"sleeping_element", "wardrobe_or_closet", "bathroom_or_ensuite",
         "circulation", "entrance"}.issubset(expected)
        and all(
            source.startswith("CORPUS:") or source.startswith("DERIVED:")
            for source in sourced
        ),
        {"expected": sorted(expected)},
    )


def test_a_generic_bedroom_does_not_expect_an_ensuite():

    expected = {element for element, _source in expected_elements("bedroom")}

    return _check(
        "G9. a generic bedroom does NOT expect an ensuite (the corpus "
        "discourages it) — expectations are not invented either",
        "bathroom_or_ensuite" not in expected
        and "sleeping_element" in expected,
        {"expected": sorted(expected)},
    )


# ==========================================================
# 3. EVIDENCE DISCIPLINE
# ==========================================================

def test_a_negated_mention_is_not_a_positive_claim():

    grounding = ground_vision_evidence(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["no window is visible", "پنجره ندارد", "bed visible"],
            "architectural_elements": [],
        },
        space_type="bedroom",
    )

    return _check(
        "G10. 'no window is visible' / 'پنجره ندارد' never becomes a visible "
        "window (negation-aware)",
        _status(grounding, "window") == "denied"
        and "window" not in (grounding.get("visible_elements") or []),
        {"window_status": _status(grounding, "window")},
    )


def test_an_inferred_element_is_never_evidence():

    grounding = ground_vision_evidence(
        {
            "image_type": "architectural_render_or_photo",
            "observed": [],
            "inferred": ["ensuite bathroom", "walk-in closet"],
            "architectural_elements": [],
        },
        space_type="bedroom",
    )

    rejected = grounding.get("rejected_claims") or []

    return _check(
        "G11. an INFERRED element is rejected as evidence, with the reason",
        "bathroom_or_ensuite" not in (grounding.get("visible_elements") or [])
        and "wardrobe_or_closet" not in (grounding.get("visible_elements") or [])
        and any(
            "inference" in (entry.get("reason") or "")
            for entry in rejected
        ),
        {"rejected": rejected},
    )


def test_a_bare_element_list_entry_is_not_visibility():

    grounding = ground_vision_evidence(
        {
            "image_type": "architectural_render_or_photo",
            "observed": [],
            "architectural_elements": ["bed", "window"],
        },
        space_type="bedroom",
    )

    return _check(
        "G12. an entry that exists ONLY in the provider's element list is "
        "unverified — it never establishes visibility",
        _status(grounding, "sleeping_element") == "unverified"
        and _status(grounding, "window") == "unverified"
        and not grounding.get("visible_elements"),
        {
            "bed": _status(grounding, "sleeping_element"),
            "window": _status(grounding, "window"),
        },
    )


def test_a_contradiction_is_resolved_and_recorded():

    grounding = ground_vision_evidence(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["closet visible"],
            "unresolved": ["closet not visible"],
            "architectural_elements": [],
        },
        space_type="bedroom",
    )

    conflicts = grounding.get("conflicts") or []

    return _check(
        "G13. a claim and its denial are RESOLVED (the observation wins) and "
        "recorded as a conflict, never printed twice",
        _status(grounding, "wardrobe_or_closet") == "visible"
        and any(
            entry.get("element") == "wardrobe_or_closet"
            for entry in conflicts
        ),
        {"conflicts": conflicts},
    )


def test_an_empty_payload_invents_nothing():

    grounding = ground_vision_evidence(EMPTY, space_type="unknown")

    return _check(
        "G14. an empty payload produces no visible element and no invented "
        "absence",
        grounding.get("visible_elements") == []
        and grounding.get("denied_elements") == []
        and grounding.get("space_type") == "unknown",
        {
            "visible": grounding.get("visible_elements"),
            "denied": grounding.get("denied_elements"),
        },
    )


def test_no_element_is_claimed_region_grounded():

    grounding = ground_vision_evidence(RUN_A, space_type="master bedroom")

    region = grounding.get("region_grounding") or {}

    return _check(
        "G15. the provider cannot ground pixel regions, and no element "
        "pretends otherwise",
        region.get("supported") is False
        and region.get("grounded_elements") == [],
        {"region_grounding": region},
    )


def test_every_element_carries_its_evidence():

    grounding = ground_vision_evidence(RUN_B, space_type="master bedroom")

    entries = grounding.get("elements") or []

    return _check(
        "G16. every element carries the field, the phrase and the class of "
        "every claim made about it",
        bool(entries)
        and all("status" in entry and "evidence" in entry for entry in entries)
        and any(
            claim.get("field") and claim.get("phrase") and claim.get("class")
            for entry in entries for claim in entry.get("evidence") or []
        ),
        {"elements": len(entries)},
    )


def test_the_layer_is_read_only():

    grounding = ground_vision_evidence(RUN_A, space_type="master bedroom")

    return _check(
        "G17. read-only: no LLM, no network, no storage, no render, no "
        "geometry, no ComfyUI",
        grounding.get("contract") == CONTRACT
        and grounding.get("llm_used") is False
        and grounding.get("network_used") is False
        and grounding.get("storage_used") is False
        and grounding.get("render_requested") is False
        and grounding.get("geometry_touched") is False
        and grounding.get("comfy_invoked") is False,
        {"contract": grounding.get("contract")},
    )


# ==========================================================
# 4. THE OLD PATH IS STILL REACHABLE, AND THE REPORT IS ADDITIVE
# ==========================================================

def test_the_historical_path_is_still_reachable():

    interpretation = interpret_architectural_vision(RUN_A, ground=False)

    return _check(
        "G18. ground=False keeps the historical behaviour byte for byte "
        "(the hardcoded lines are not deleted, only no longer the default)",
        "private bathroom connection is not visible"
        in (interpretation.get("unknowns") or [])
        and "grounding" not in interpretation,
        {"unknowns": interpretation.get("unknowns")},
    )


def test_the_historical_four_section_report_is_unchanged():

    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible"],
            "architectural_elements": ["bed"],
            "confidence": "MEDIUM",
        },
        ground=False,
    )

    rendered = render_vision_report(interpretation, "en")

    return _check(
        "G19. without a grounding the report is exactly the historical four "
        "sections (nothing added)",
        rendered.startswith("1. Possible architectural space:")
        and "2. Visible elements:" in rendered
        and "3. Possible spatial relations:" in rendered
        and "4. Uncertain or undetermined:" in rendered
        and "Visual evidence check" not in rendered,
        {"rendered": rendered[-200:]},
    )


def test_the_report_gains_the_grounded_section_when_grounded():

    interpretation = interpret_architectural_vision(RUN_A)

    # ARCHITECTURAL_VISION_REPORT_UX_V1 — the EVIDENCE report still ends
    # with the evidence check; the user-facing plan answer is now the
    # short architectural explanation (checked separately below).
    rendered = render_vision_evidence_report(interpretation, "fa")

    concise = render_vision_report(interpretation, "fa")

    return _check(
        "G20. the EVIDENCE report ends with the evidence check, in Persian, "
        "and lists the unverified claim and the expected gaps; the "
        "user-facing answer is the short architectural explanation",
        "بررسی شواهد تصویری" in rendered
        and "پنجره" in rendered
        and "حمام/سرویس" in rendered
        and "None" not in rendered
        and len(concise) < len(rendered) / 3
        and "بررسی شواهد تصویری" not in concise,
        {"tail": rendered[-320:], "concise": concise[:200]},
    )


def test_the_grounding_block_is_honest_in_both_languages():

    grounding = ground_vision_evidence(RUN_A, space_type="master bedroom")

    fa = render_grounding(grounding, "fa")

    en = render_grounding(grounding, "en")

    return _check(
        "G21. the block is rendered in both languages and never claims the "
        "window is visible",
        "پنجره" in fa and "window" in en
        and "تأییدنشده" in fa and "unverified" in en
        and "None" not in fa and "None" not in en,
        {"fa": fa[:200]},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("ARCHITECTURAL_VISION_GROUNDING_V1 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_a_symbol_reading_is_not_visibility,
        test_the_answer_never_claims_the_window_as_visible,
        test_the_window_claim_is_reported_as_unverified_not_dropped,
        test_an_explicit_visibility_claim_is_still_grounded,
        test_an_observed_closet_is_visible_and_not_contradicted,
        test_a_never_reported_zone_is_unknown_not_absent,
        test_expected_zones_are_surfaced_as_gaps,
        test_expected_elements_come_from_the_frozen_corpus,
        test_a_generic_bedroom_does_not_expect_an_ensuite,
        test_a_negated_mention_is_not_a_positive_claim,
        test_an_inferred_element_is_never_evidence,
        test_a_bare_element_list_entry_is_not_visibility,
        test_a_contradiction_is_resolved_and_recorded,
        test_an_empty_payload_invents_nothing,
        test_no_element_is_claimed_region_grounded,
        test_every_element_carries_its_evidence,
        test_the_layer_is_read_only,
        test_the_historical_path_is_still_reachable,
        test_the_historical_four_section_report_is_unchanged,
        test_the_report_gains_the_grounded_section_when_grounded,
        test_the_grounding_block_is_honest_in_both_languages,
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
