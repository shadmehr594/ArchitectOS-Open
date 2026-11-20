# ==========================================================
# VISION_REPORT_LANGUAGE_01 — CONTRACT / ACCEPTANCE TESTS
#
# The user analysed a photo in a Persian conversation and the assistant
# answered in ENGLISH, while the SAME response declared
# `output_language: "persian"`. They then asked, in Persian, for the
# analysis in Persian ("میشه تحلیل عکستو فارسی برام بگی") and the
# assistant did not understand it as a language request at all — it
# reached the generic LLM, which treated "عکستو فارسی" as an
# ARCHITECTURAL TERM and invented a discussion of it.
#
# Three bounded corrections:
#   1. the image analysis is rendered in the language the response
#      itself declares (the English output is unchanged byte for byte)
#   2. an explicit language request is answered deterministically, and
#      the project's last interpretation is RE-RENDERED
#   3. a terminator no longer splits a predicate that continues
#      ("تخت خواب هم بهتره دور از پنجره ..." is ONE rule)
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_vision_report_language_01.py
#   .venv/Scripts/python.exe tests/test_vision_report_language_01.py
# ==========================================================


import json
import os
import sys
import tempfile


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


_TEMP_ROOT = os.path.join(
    tempfile.gettempdir(), "architectos_vision_report_language_01"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault(
    "ARCHITECTOS_PROJECTS_ROOT", os.path.join(_TEMP_ROOT, "projects")
)

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_TRASH_ROOT", os.path.join(_TEMP_ROOT, "trash")
)

os.environ["ARCHITECTOS_COMFY_PORT"] = "9"


from core.project.project_workspace_v1 import project_workspace  # noqa: E402

project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.vision.vision_report_v1 import (  # noqa: E402
    render_vision_report,
    display_phrase,
    display_space_type,
)

from core.vision.vision_analysis_store_v1 import (  # noqa: E402
    vision_analysis_store,
)

from core.conversation.language_switch_v1 import (  # noqa: E402
    detect_language_request,
    build_language_switch,
)

from core.conversation.clause_analysis_v1 import (  # noqa: E402
    knowledge_clauses,
)

from core.conversation.teach_back_v1 import (  # noqa: E402
    build_grounded_answer,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    teaching_candidate_store,
)

from core.chat.response_adapter import (  # noqa: E402
    ResponseAdapter,
)


# ----------------------------------------------------------
# THE USER'S OWN CASE
# ----------------------------------------------------------

# The interpretation the assistant actually produced for the bedroom
# photo (from their session).
INTERPRETATION = {
    "space_type": "master bedroom",
    "confidence": "HIGH",
    "observed_elements": [
        "entrance threshold visible",
        "daylight opening visible",
        "sleeping element visible",
        "storage or dressing element visible",
        "seating element visible",
    ],
    "spatial_relations": [
        "The daylight opening is associated with the enclosed sleeping space.",
        "The seating element is located within the same visible room zone.",
    ],
    "unknowns": [
        "private bathroom connection is not visible",
        "dressing or closet zone is not visible",
        "some provider observations remain unresolved",
    ],
}

# The EXACT historical English rendering — pinned byte for byte, so an
# English conversation cannot regress.
HISTORICAL_ENGLISH = (
    "1. Possible architectural space:\n"
    "master bedroom (confidence: HIGH)\n\n"
    "2. Visible elements:\n"
    "- entrance threshold visible\n"
    "- daylight opening visible\n"
    "- sleeping element visible\n"
    "- storage or dressing element visible\n"
    "- seating element visible\n\n"
    "3. Possible spatial relations:\n"
    "- The daylight opening is associated with the enclosed sleeping space.\n"
    "- The seating element is located within the same visible room zone.\n\n"
    "4. Uncertain or undetermined:\n"
    "- private bathroom connection is not visible\n"
    "- dressing or closet zone is not visible\n"
    "- some provider observations remain unresolved"
)

LANGUAGE_REQUEST = "میشه تحلیل عکستو فارسی برام بگی"

CONTINUATION_MESSAGE = "تخت خواب هم بهتره دور از پنجره اتاق خواب قرار بگیره"

TWO_RULES_MESSAGE = (
    "تخت دور از پنجره باشه بهتره تو برای اتاق خواب حتما پنجره داشته باشه"
)

LEGACY_MESSAGE = (
    "یسری چیزها باید در نظر گرفت روی تخت محل معاشقه والدین هست پس تخت "
    "باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه ، تخت "
    "دور از پنجره باشه بهتره"
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Vision Report")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


# ==========================================================
# 1. THE IMAGE ANALYSIS ANSWERS IN THE CONVERSATION'S LANGUAGE
# ==========================================================

def test_the_english_rendering_is_unchanged():

    return _check(
        "V1. the English rendering is byte-for-byte the historical "
        "output (no regression for an English conversation)",
        render_vision_report(INTERPRETATION, "en") == HISTORICAL_ENGLISH,
        {"text": render_vision_report(INTERPRETATION, "en")[:120]},
    )


def test_the_persian_rendering_is_persian():

    text = render_vision_report(INTERPRETATION, "fa")

    english_headers = (
        "Possible architectural space",
        "Visible elements",
        "Possible spatial relations",
        "Uncertain or undetermined",
    )

    english_items = (
        "sleeping element visible",
        "daylight opening visible",
        "private bathroom connection is not visible",
    )

    return _check(
        "V2. the Persian rendering has Persian headers AND Persian "
        "findings (no English left in it)",
        "فضای معماری احتمالی" in text
        and "عناصر قابل مشاهده" in text
        and "اتاق خواب مستر" in text
        and "میزان اطمینان: زیاد" in text
        and not any(h in text for h in english_headers)
        and not any(i in text for i in english_items),
        {"text": text[:200]},
    )


def test_the_declared_language_drives_the_rendering():

    adapter = ResponseAdapter()

    persian = adapter.build_architectural_vision_message(
        INTERPRETATION, language="persian"
    )

    english = adapter.build_architectural_vision_message(
        INTERPRETATION, language="english"
    )

    default = adapter.build_architectural_vision_message(INTERPRETATION)

    return _check(
        "V3. the adapter renders in the DECLARED language, and the "
        "default stays English",
        "اتاق خواب مستر" in persian
        and english == HISTORICAL_ENGLISH
        and default == HISTORICAL_ENGLISH,
        {"persian": persian[:80]},
    )


def test_an_unmapped_phrase_is_never_dropped():

    return _check(
        "V4. a phrase with no translation is passed through, never "
        "dropped (a translation gap must not remove a finding)",
        display_phrase("a brand new provider phrase", "fa")
        == "a brand new provider phrase"
        and display_space_type("some new space", "fa") == "some new space",
        {},
    )


# ==========================================================
# 2. THE LANGUAGE REQUEST
# ==========================================================

def test_the_language_request_is_detected():

    cases = [
        (LANGUAGE_REQUEST, "fa"),
        ("به فارسی جواب بده", "fa"),
        ("پاسخ را انگلیسی بده", "en"),
        ("can you answer in English please", "en"),
    ]

    wrong = [
        (text, expected)
        for text, expected in cases
        if detect_language_request(text) != expected
    ]

    return _check(
        "L1. an explicit language request is detected in both "
        "languages",
        not wrong,
        {"wrong": wrong},
    )


def test_a_language_name_alone_is_not_a_request():

    negatives = [
        "فارسی سخته",
        "اتاق خواب مستر باید دور از نشیمن باشه",
        "سلام",
        "دانش دائمی اش کن",
    ]

    captured = [
        text for text in negatives
        if detect_language_request(text) is not None
    ]

    return _check(
        "L2. merely mentioning a language is NOT a switch request "
        "(two-part test)",
        not captured,
        {"captured": captured},
    )


def test_the_switch_re_renders_the_last_analysis():

    switch = build_language_switch("fa", INTERPRETATION)

    text = switch.get("result") or ""

    return _check(
        "L3. the switch RE-RENDERS the last analysis in the requested "
        "language, without the LLM",
        switch.get("re_rendered_analysis") is True
        and "اتاق خواب مستر" in text
        and "عناصر قابل مشاهده" in text
        and switch.get("llm_used") is False
        and switch.get("render_requested") is False,
        {"text": text[:160]},
    )


def test_the_switch_is_honest_when_there_is_no_analysis():

    switch = build_language_switch(
        "fa", None, image_analysis_available=False
    )

    text = switch.get("result") or ""

    return _check(
        "L4. with no stored analysis the reply says so and asks for the "
        "image again — it never invents one",
        switch.get("re_rendered_analysis") is False
        and "ثبت نشده" in text
        and switch.get("candidate") is None,
        {"text": text[:160]},
    )


# ==========================================================
# 3. THE INTERPRETATION IS KEPT, PER PROJECT
# ==========================================================

def test_the_interpretation_round_trips():

    project_id = _project()

    saved = vision_analysis_store.save(
        project_id, INTERPRETATION, source_text="تحلیل عکس"
    )

    loaded = vision_analysis_store.load(project_id)

    return _check(
        "S1. the last interpretation round-trips, project-scoped",
        saved is True
        and isinstance(loaded, dict)
        and loaded.get("space_type") == "master bedroom"
        and loaded.get("observed_elements")
        == INTERPRETATION["observed_elements"],
        {"loaded": loaded},
    )


def test_the_store_is_project_scoped():

    project_a = _project()

    project_b = _project()

    vision_analysis_store.save(project_a, INTERPRETATION)

    return _check(
        "S2. another project does not see it (no leakage)",
        vision_analysis_store.load(project_b) is None,
        {},
    )


def test_the_store_does_not_materialise_a_project():

    return _check(
        "S3. a READ for an unknown project creates no folder and "
        "returns None",
        vision_analysis_store.load("project_does_not_exist_at_all") is None
        and not os.path.isdir(
            os.path.join(
                project_workspace.projects_root,
                "project_does_not_exist_at_all",
            )
        ),
        {},
    )


# ==========================================================
# 4. THE OVER-SPLIT
# ==========================================================

def test_a_continuing_predicate_is_not_split():

    clauses = knowledge_clauses(CONTINUATION_MESSAGE)

    return _check(
        "C1. 'تخت خواب هم بهتره دور از پنجره اتاق خواب قرار بگیره' is "
        "ONE rule (the terminator does not split a continuing predicate)",
        len(clauses) == 1
        and clauses[0]["text"] == CONTINUATION_MESSAGE,
        {"clauses": [c["text"] for c in clauses]},
    )


def test_a_real_second_rule_is_still_split():

    clauses = knowledge_clauses(TWO_RULES_MESSAGE)

    return _check(
        "C2. a real second rule is still split (the guard did not "
        "disable segmentation)",
        len(clauses) == 2
        and clauses[0]["text"].endswith("بهتره")
        and clauses[1]["text"].startswith("تو برای"),
        {"clauses": [c["text"] for c in clauses]},
    )


# ==========================================================
# 5. THE GROUNDED ANSWER STOPS DUMPING WHOLE MESSAGES
# ==========================================================

def test_a_legacy_whole_message_is_shown_as_its_rules():

    project_id = _project()

    teaching_candidate_store.record(
        project_id,
        {
            "raw_statement": LEGACY_MESSAGE,
            "domain": "space",
            "status": "observed",
            "provenance": "HUMAN_TEACHER",
            "space_topic": "MASTER_BEDROOM_SLEEPING",
            "entities": ["bed", "window"],
            "relations": ["far"],
            "polarity": "require",
            "knowledge_class": "DESIGN_RULE",
            "scope": "GENERAL",
        },
    )

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "G1. a candidate recorded as one whole message is shown as the "
        "rules inside it, not dumped verbatim",
        "قواعد را در آن دارد" in text
        and "تخت دور از پنجره باشه بهتره" in text
        and "تخت باید جایی گذاشته شود" in text,
        {"text": text[:320]},
    )


def test_a_clause_candidate_names_its_role():

    project_id = _project()

    teaching_candidate_store.record(
        project_id,
        {
            "raw_statement": "تخت دور از پنجره باشه بهتره",
            "domain": "space",
            "status": "observed",
            "provenance": "HUMAN_TEACHER",
            "space_topic": "MASTER_BEDROOM_SLEEPING",
            "entities": ["bed", "window"],
            "relations": ["far"],
            "polarity": "require",
            "knowledge_class": "DESIGN_RULE",
            "scope": "GENERAL",
            "clause_role": "RULE",
            "clause_index": 0,
            "clause_count": 2,
        },
    )

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "G2. a clause candidate names its own role, and no 'None' is "
        "ever rendered",
        "قاعدهٔ طراحی" in text and "None" not in text,
        {"text": text[:260]},
    )


def test_no_turn_asks_for_a_render():

    switch = build_language_switch("fa", INTERPRETATION)

    return _check(
        "F1. nothing on these paths asks for a render or a promotion",
        switch.get("render_requested") is False
        and switch.get("permanent_learning") is False
        and switch.get("routed_to_execute") is False,
        {},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("VISION_REPORT_LANGUAGE_01 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_the_english_rendering_is_unchanged,
        test_the_persian_rendering_is_persian,
        test_the_declared_language_drives_the_rendering,
        test_an_unmapped_phrase_is_never_dropped,
        test_the_language_request_is_detected,
        test_a_language_name_alone_is_not_a_request,
        test_the_switch_re_renders_the_last_analysis,
        test_the_switch_is_honest_when_there_is_no_analysis,
        test_the_interpretation_round_trips,
        test_the_store_is_project_scoped,
        test_the_store_does_not_materialise_a_project,
        test_a_continuing_predicate_is_not_split,
        test_a_real_second_rule_is_still_split,
        test_a_legacy_whole_message_is_shown_as_its_rules,
        test_a_clause_candidate_names_its_role,
        test_no_turn_asks_for_a_render,
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
                json.dumps(detail, ensure_ascii=False, default=str)[:500],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
