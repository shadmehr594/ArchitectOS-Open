# ==========================================================
# CORRECTION_LOOP_01 — CONTRACT / ACCEPTANCE TESTS
#
# The user reported that the assistant could not LEARN: they corrected
# it, it acknowledged, and then it gave the same wrong answer again.
# Their own session (`data/projects/project_e89fe613`) is the evidence.
#
# Five root causes were proven from that session:
#
#   1. ALIAS GAP — the question "اتاق خواب مستر ..." resolved to
#      MASTER_BEDROOM_SLEEPING through the corpus scanner, but the
#      STATEMENTS the user taught resolved to the flat entity `bedroom`
#      (which is not a space id) or to nothing at all. Every recorded
#      candidate carried `space_topic = null`, so the retrieval path
#      could never match it and the question fell to the generic LLM.
#      The user's own short forms ("اتاق مستر", "اتاق والدین") were not
#      aliases at all.
#
#   2. AUTO-REJECTION — "برای میهمانان نیست فقط برای زوجین هست" names no
#      space of its own, so `domain` was `unknown` and
#      `build_candidate` stored it as `rejected`. The correction was
#      thrown away. The domain ladder ran BEFORE the subject was
#      resolved, so the inherited topic could not help it.
#
#   3. TURN GATE — "نه فقط و فقط برای زوجین هست ..." opened with a
#      denial but carried no error word, so it classified
#      NORMAL_CONVERSATION and fell through to the LLM, which INVENTED
#      the opposite of what the teacher had said.
#
#   4. PROMOTION FABRICATION — "به دانش عمومی تبدیلش کن" classified as
#      INSTRUCTION, reached the LLM, and the LLM fabricated a completed
#      promotion out of an unrelated memory.
#
#   5. NO LOOP CLOSURE — as a consequence of 1-4 the same question was
#      answered wrongly, corrected, and answered wrongly again.
#
# SCOPE: no new space ids, no curriculum change, no lesson, no
# promotion, no global memory, no render, no LLM on these paths.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_correction_loop_01.py
#   .venv/Scripts/python.exe tests/test_correction_loop_01.py
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
    tempfile.gettempdir(), "architectos_correction_loop_01"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault(
    "ARCHITECTOS_PROJECTS_ROOT", os.path.join(_TEMP_ROOT, "projects")
)

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_TRASH_ROOT", os.path.join(_TEMP_ROOT, "trash")
)

# Render-stop guard: acceptance must never reach ComfyUI.
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"


from core.project.project_workspace_v1 import project_workspace  # noqa: E402

project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.conversation.teaching_foundation_v1 import (  # noqa: E402
    teaching_foundation,
)

from core.conversation.teaching_meaning_v1 import (  # noqa: E402
    extract_meaning,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    build_candidate,
    teaching_candidate_store,
)

from core.conversation.turn_semantics_v1 import (  # noqa: E402
    classify_turn,
)

from core.conversation.promotion_boundary_v1 import (  # noqa: E402
    is_promotion_request,
    build_promotion_refusal,
)

from core.conversation.knowledge_promotion_bridge_v1 import (  # noqa: E402
    PROMOTION_IMPLEMENTED,
)

from core.curriculum.space_query_v1 import (  # noqa: E402
    scan_spaces,
)

from core.curriculum.space_types_v1 import (  # noqa: E402
    PREFERRED_TERM,
)

from core.curriculum.curriculum_sequencer_v1 import (  # noqa: E402
    LESSONS,
)

from core.conversation.clause_analysis_v1 import (  # noqa: E402
    segment,
    knowledge_clauses,
)


# ----------------------------------------------------------
# CLAUSE_ANALYSIS_01 — the teacher's long messages, verbatim
# ----------------------------------------------------------

LONG_RULES = (
    "یسری چیزها باید در نظر گرفت روی تخت محل معاشقه والدین هست پس "
    "تخت باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه "
    "، تخت دور از پنجره باشه بهتره ، اتاق خواب ها باید دور از پذیرایی "
    "و فضاهای نشیمن باشن چون اون فضاها فضاهای عمومی هستن و مهمان میاد "
    "ولی اتاق خواب فضای خصوصی است و حریمش باید حفظ شود"
)

QUOTED_META = (
    "اینم باز اشتباه فهمیدی : فهمیدم: پنجره باید دور از اتاق خواب و "
    "نشیمن باشد. ، من گفتم تخت دور از پنجره باشه بهتره تو برای اتاق "
    "خواب حتما پنجره داشته باشی اتاق خواب به نور طبیعی و تهویه نیاز "
    "داره ، نشیمن هم باید پنجره داشته باشه"
)

TAXONOMY_MESSAGE = (
    "اشتباه فهمیدی اتاق خواب دو نمونه داریم اتاق خواب معمولی که برای "
    "بچه هاست و اتاق خواب والیدن که اتاق خواب مستر هست دلایلش رو هم "
    "که فهمیدی کلا اتاق خواب ها فضای خصوصی هستن و باید دور از نشیمن و "
    "فضاهای عمومی قرار بگیرند متوجه شدی؟"
)


# ----------------------------------------------------------
# THE USER'S OWN MESSAGES, VERBATIM
# ----------------------------------------------------------

TEACH_DEFINITION = (
    "اتاق خواب مستر اتاق والدین هست اونی که تو گفتی اتاق خواب "
    "میهمانه که تو بعضی از خونه ها در نظر میگیرن"
)

CORRECTION_WRONG = (
    "خوب پس تعریف قبلت که گفتی برای یک نفر می خواهد اشتباهه ، "
    "اتاق خواب والدین هم فقط برای دو نفر هست یعنی زن و شوهر نه کل "
    "خانواده اینم اشتباهه ، حالا درست شد؟"
)

QUESTION_SHORT_FORM = "اتاق مستر برای چه افرادی تو خونه استفاده میشه؟"

CORRECTION_DENIAL = (
    "نه فقط و فقط برای زوجین هست ، حتی برای مسن ها و میهمانان هم "
    "استفاده نمیشود"
)

TEACH_SHORT_DEFINITION = "اتاق مستر فقط اتاق والدین هست"

PROMOTION_REQUEST = "به دانش عمومی تبدیلش کن"

# the phrase the user actually used in the reported session
PROMOTION_REQUEST_DOOMI = "دانش دائمی اش کن"

CORRECTION_GUESTS = "برای میهمانان نیست فقط برای زوجین هست"

QUESTION_FINAL = "اتاق خواب مستر برای چه افرادی در خانه استفاده میشه؟"

# ---- negatives that must NOT be captured ----

BARE_DENIAL = "نه"

POLITE_NO = "نه ممنون، خودم انجام میدم"

KNOWLEDGE_QUESTION = "دانش عمومی یعنی چه؟"

TEACHING_OFFER = "من میخوام طراحی معماری رو یادت بدم"

NON_ARCHITECTURAL = "من امروز حالم خوب نیست"

# A mid-sentence copula that names NO space — the recovery must not fire.
MID_COPULA_NON_ARCHITECTURAL = "امروز هوا سرد است و باران می بارد"

PLAIN_BEDROOM = "اتاق خواب فضای خصوصی است"


MASTER = "MASTER_BEDROOM_SLEEPING"

BEDROOM = "BEDROOM_DOUBLE"

ZWNJ = "\u200c"


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Correction Loop")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _turn(text, project_id):

    observation = teaching_foundation.observe_turn(
        session_id=project_id,
        text=text,
        context={"session_id": project_id},
        input_type="typed",
    )

    response = observation.get("response") or {}

    return observation, response, (response.get("teaching") or {})


def _meaning(text, context=None):

    return extract_meaning(
        text, turn_kind="TEACHING_STATEMENT", context=context
    )


# ==========================================================
# 1. ALIAS COVERAGE — write path and read path must agree
# ==========================================================

def test_the_users_short_forms_resolve_to_the_master_bedroom():

    short_form = scan_spaces("اتاق مستر برای چه افرادی استفاده میشه")

    parents_form = scan_spaces("اتاق والدین برای چه کسانی است")

    return _check(
        "A1. the user's short forms resolve to MASTER_BEDROOM_SLEEPING",
        [space for space, _alias in short_form] == [MASTER]
        and [space for space, _alias in parents_form] == [MASTER],
        {"short": short_form, "parents": parents_form},
    )


def test_a_bare_bedroom_keeps_its_own_space():

    mentions = scan_spaces("اتاق خواب فضای خصوصی است")

    return _check(
        "A2. a bare 'اتاق خواب' still resolves to BEDROOM_DOUBLE "
        "(no over-capture)",
        [space for space, _alias in mentions] == [BEDROOM],
        {"mentions": mentions},
    )


def test_every_teaching_statement_attaches_to_the_master_bedroom():

    results = {}

    for label, text in (
        ("definition", TEACH_DEFINITION),
        ("correction_wrong", CORRECTION_WRONG),
        ("short_definition", TEACH_SHORT_DEFINITION),
    ):

        meaning = _meaning(text)

        results[label] = meaning.get("space_topic")

    return _check(
        "A3. every one of the user's teaching statements carries "
        "space_topic = MASTER_BEDROOM_SLEEPING",
        set(results.values()) == {MASTER},
        results,
    )


def test_the_alias_table_is_the_single_source():

    # The corpus scanner must resolve the new terms, i.e. the aliases
    # really live in PREFERRED_TERM rather than in a private copy.
    entries = [
        term for term in PREFERRED_TERM
        if PREFERRED_TERM[term] == MASTER
    ]

    return _check(
        "A4. the master-bedroom terms come from the shared PREFERRED_TERM "
        "table (no private alias copy)",
        len(entries) >= 5
        and len(scan_spaces("اتاق خواب مستر")) == 1,
        {"preferred_terms": entries},
    )


def test_a_definition_with_a_trailing_clause_is_recorded():

    project_id = _project()

    observation, _response, teaching = _turn(
        TEACH_DEFINITION, project_id
    )

    candidate = teaching.get("candidate") or {}

    return _check(
        "A5. a copular definition with a TRAILING CLAUSE is recovered and "
        "recorded (the classifier is not modified)",
        observation.get("recovered_turn_kind") == "TEACHING_STATEMENT"
        and observation.get("classifier_turn_kind") == "NORMAL_CONVERSATION"
        and (observation.get("semantics") or {}).get("turn_kind")
        == "NORMAL_CONVERSATION"
        and candidate.get("space_topic") == MASTER
        and candidate.get("status") == "observed",
        {
            "recovered": observation.get("recovered_turn_kind"),
            "classifier": observation.get("classifier_turn_kind"),
            "candidate": candidate,
        },
    )


def test_a_copula_about_nothing_architectural_is_not_recovered():

    project_id = _project()

    observation, _response, teaching = _turn(
        MID_COPULA_NON_ARCHITECTURAL, project_id
    )

    return _check(
        "A6. a mid-sentence copula that names no space is NOT recovered "
        "(no over-capture)",
        observation.get("recovered_turn_kind") is None
        and observation.get("candidate") is None
        and teaching.get("action") is None,
        {
            "recovered": observation.get("recovered_turn_kind"),
            "turn_kind": observation.get("turn_kind"),
        },
    )


# ==========================================================
# 2. AUTO-REJECTION — the correction must survive
# ==========================================================

def test_a_space_less_statement_alone_is_still_unknown():

    meaning = _meaning(CORRECTION_GUESTS, context=None)

    return _check(
        "B1. with NO topic context a space-less statement is still "
        "'unknown' (historical behaviour kept)",
        meaning.get("domain") == "unknown"
        and meaning.get("space_topic") is None,
        {"domain": meaning.get("domain")},
    )


def test_an_inherited_topic_makes_the_statement_about_that_space():

    meaning = _meaning(
        CORRECTION_GUESTS, context={"active_topic": MASTER}
    )

    return _check(
        "B2. with the inherited topic the same statement resolves to the "
        "space and stops being 'unknown'",
        meaning.get("domain") == "space"
        and meaning.get("space_topic") == MASTER
        and meaning.get("subject_source") == "inherited_active_topic",
        {
            "domain": meaning.get("domain"),
            "space_topic": meaning.get("space_topic"),
            "source": meaning.get("subject_source"),
        },
    )


def test_the_correction_is_recorded_not_rejected():

    candidate = build_candidate(
        CORRECTION_GUESTS,
        project_id=None,
        turn_kind="TEACHING_STATEMENT",
        context={"active_topic": MASTER},
    )

    return _check(
        "B3. the user's last correction is `observed`, NOT `rejected`",
        candidate is not None and candidate.status == "observed",
        {
            "status": getattr(candidate, "status", None),
            "domain": getattr(candidate, "domain", None),
        },
    )


def test_a_non_architectural_statement_is_still_rejected():

    candidate = build_candidate(
        NON_ARCHITECTURAL,
        project_id=None,
        turn_kind="TEACHING_STATEMENT",
        context={"active_topic": MASTER},
    )

    return _check(
        "B4. a genuinely non-architectural statement is still rejected "
        "(the rejection policy was not deleted)",
        candidate is not None and candidate.status == "rejected",
        {"status": getattr(candidate, "status", None)},
    )


# ==========================================================
# 3. TURN GATE — a denial must reach the teaching layer
# ==========================================================

def test_a_denial_opener_is_a_correction():

    result = classify_turn(CORRECTION_DENIAL, language="fa")

    features = result.get("features") or {}

    return _check(
        "C1. 'نه ... هست' is a CORRECTION (was NORMAL_CONVERSATION -> LLM)",
        result.get("turn_kind") == "CORRECTION"
        and features.get("disagreement_opener") is True,
        {"turn_kind": result.get("turn_kind")},
    )


def test_a_bare_denial_is_not_a_correction():

    bare = classify_turn(BARE_DENIAL, language="fa")

    polite = classify_turn(POLITE_NO, language="fa")

    return _check(
        "C2. a bare 'نه' and a polite 'نه ممنون...' are NOT corrections "
        "(the opener alone is never enough)",
        bare.get("turn_kind") != "CORRECTION"
        and polite.get("turn_kind") != "CORRECTION",
        {
            "bare": bare.get("turn_kind"),
            "polite": polite.get("turn_kind"),
        },
    )


def test_the_original_correction_path_is_unchanged():

    lexical = classify_turn(CORRECTION_WRONG, language="fa")

    statement = classify_turn(TEACH_SHORT_DEFINITION, language="fa")

    return _check(
        "C3. the error-marked correction is still a CORRECTION and the "
        "plain definition is still a TEACHING_STATEMENT",
        lexical.get("turn_kind") == "CORRECTION"
        and statement.get("turn_kind") == "TEACHING_STATEMENT",
        {
            "lexical": lexical.get("turn_kind"),
            "statement": statement.get("turn_kind"),
        },
    )


def test_the_denial_is_recorded_against_the_space():

    project_id = _project()

    _turn(TEACH_DEFINITION, project_id)

    _observation, _response, teaching = _turn(
        CORRECTION_DENIAL, project_id
    )

    candidate = teaching.get("candidate") or {}

    return _check(
        "C4. the denial is recorded against MASTER_BEDROOM_SLEEPING",
        candidate.get("space_topic") == MASTER
        and candidate.get("status") == "observed",
        {"candidate": candidate},
    )


# ==========================================================
# 4. PROMOTION BOUNDARY — say it, do not invent it
# ==========================================================

def test_the_promotion_request_is_detected():

    with_zwnj = "به دانش عمومی تبدیل" + ZWNJ + "ش کن"

    return _check(
        "D1. an explicit two-part promotion request is detected "
        "(the user's own 'دانش دائمی اش کن' included)",
        is_promotion_request(PROMOTION_REQUEST)
        and is_promotion_request(with_zwnj)
        and is_promotion_request(PROMOTION_REQUEST_DOOMI),
        {
            "plain": is_promotion_request(PROMOTION_REQUEST),
            "daemi": is_promotion_request(PROMOTION_REQUEST_DOOMI),
        },
    )


def test_the_negatives_are_not_promotion_requests():

    return _check(
        "D2. a question ABOUT knowledge and a teaching offer are NOT "
        "promotion requests",
        not is_promotion_request(KNOWLEDGE_QUESTION)
        and not is_promotion_request(TEACHING_OFFER),
        {
            "knowledge_question": is_promotion_request(KNOWLEDGE_QUESTION),
            "teaching_offer": is_promotion_request(TEACHING_OFFER),
        },
    )


def test_the_refusal_reports_the_bridge_truth():

    refusal = build_promotion_refusal("fa")

    return _check(
        "D3. the refusal READS 'promotion not implemented' from the "
        "Phase 09 bridge instead of re-deriving it",
        refusal.get("promotion_implemented") is PROMOTION_IMPLEMENTED
        and PROMOTION_IMPLEMENTED is False
        and refusal.get("promoted") is False
        and refusal.get("candidate_created") is False,
        {
            "promotion_implemented": refusal.get("promotion_implemented"),
            "bridge": PROMOTION_IMPLEMENTED,
        },
    )


def test_the_promotion_turn_never_reaches_the_llm():

    project_id = _project()

    _turn(TEACH_SHORT_DEFINITION, project_id)

    observation, response, teaching = _turn(
        PROMOTION_REQUEST, project_id
    )

    text = response.get("result") or ""

    return _check(
        "D4. the promotion turn is short-circuited by the teaching layer "
        "and claims no conversion",
        observation.get("short_circuit") is True
        and response.get("engine") == "architectos_turn_semantics"
        and teaching.get("action") == "refuse_knowledge_promotion"
        and teaching.get("llm_used") is False
        and "پیاده‌سازی نشده" in text,
        {
            "engine": response.get("engine"),
            "action": teaching.get("action"),
            "text": text[:120],
        },
    )


def test_the_promotion_turn_creates_nothing():

    project_id = _project()

    before = len(teaching_candidate_store.candidates(project_id))

    observation, _response, _teaching = _turn(
        PROMOTION_REQUEST, project_id
    )

    after = len(teaching_candidate_store.candidates(project_id))

    return _check(
        "D5. a promotion request creates no candidate and learns nothing",
        observation.get("candidate") is None and before == after,
        {"before": before, "after": after},
    )


# ==========================================================
# 5. LOOP CLOSURE — the user's exact sequence
# ==========================================================

def test_the_full_user_session_closes_the_loop():

    project_id = _project()

    _turn(TEACH_DEFINITION, project_id)
    _turn(CORRECTION_WRONG, project_id)

    # the question in the SHORT form the user actually typed
    short_observation, short_response, short_teaching = _turn(
        QUESTION_SHORT_FORM, project_id
    )

    _turn(CORRECTION_DENIAL, project_id)
    _turn(TEACH_SHORT_DEFINITION, project_id)
    _turn(PROMOTION_REQUEST, project_id)
    _turn(CORRECTION_GUESTS, project_id)

    # the question that used to loop for ever
    observation, response, teaching = _turn(
        QUESTION_FINAL, project_id
    )

    grounded = teaching.get("grounded_answer") or {}

    text = grounded.get("result") or ""

    candidates = teaching_candidate_store.candidates(project_id)

    observed = [
        entry for entry in candidates if entry.get("status") != "rejected"
    ]

    # CLAUSE_ANALYSIS_01 — a long message is now split into clauses, so a
    # fragment that carries no architectural domain signal of its own can
    # legitimately be `rejected`. What must NOT be rejected is a clause
    # that carries the teacher's own rule.
    rules_rejected = [
        entry for entry in candidates
        if entry.get("status") == "rejected"
        and "زوجین" in (entry.get("raw_statement") or "")
    ]

    return _check(
        "E1. after the corrections the repeated question is answered from "
        "the teaching store (not the LLM), quotes the taught definition, "
        "and no RULE clause was rejected",
        response.get("engine") == "architectos_turn_semantics"
        and teaching.get("action") == "answer_from_teaching_memory"
        and "والدین" in text
        and len(candidates) >= 5
        and len(observed) >= 5
        and not rules_rejected,
        {
            "engine": response.get("engine"),
            "action": teaching.get("action"),
            "candidates": len(candidates),
            "observed": len(observed),
            "statuses": [e.get("status") for e in candidates],
            "topics": [e.get("space_topic") for e in candidates],
            "rules_rejected": [e.get("raw_statement") for e in rules_rejected],
            "text": text[:160],
        },
    )


def test_the_short_form_question_is_grounded_too():

    project_id = _project()

    _turn(TEACH_DEFINITION, project_id)

    observation, response, teaching = _turn(
        QUESTION_SHORT_FORM, project_id
    )

    return _check(
        "E2. the question phrased with the user's own shorthand "
        "('اتاق مستر') is grounded as well",
        observation.get("short_circuit") is True
        and response.get("engine") == "architectos_turn_semantics"
        and teaching.get("action") == "answer_from_teaching_memory",
        {
            "engine": response.get("engine"),
            "action": teaching.get("action"),
        },
    )


# ==========================================================
# 6. SCOPE / SAFETY
# ==========================================================

def test_nothing_is_silently_promoted():

    project_id = _project()

    _turn(TEACH_DEFINITION, project_id)
    _turn(TEACH_SHORT_DEFINITION, project_id)
    _turn(PROMOTION_REQUEST, project_id)

    candidates = teaching_candidate_store.candidates(project_id)

    return _check(
        "F1. every candidate stays unlearned and non-permanent, and no "
        "lesson was created",
        bool(candidates)
        and all(
            entry.get("is_learned_knowledge") is False
            and entry.get("is_permanent") is False
            for entry in candidates
        )
        and LESSONS == (),
        {
            "count": len(candidates),
            "lessons": len(LESSONS),
        },
    )


def test_the_retrieval_stays_project_scoped():

    project_a = _project()

    project_b = _project()

    _turn(TEACH_DEFINITION, project_a)

    observation, _response, teaching = _turn(
        QUESTION_FINAL, project_b
    )

    return _check(
        "F2. no cross-project leakage: an untaught project keeps the "
        "existing path",
        observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {"short_circuit": observation.get("short_circuit")},
    )


def test_a_plain_statement_is_unchanged():

    project_id = _project()

    observation, _response, teaching = _turn(
        PLAIN_BEDROOM, project_id
    )

    candidate = teaching.get("candidate") or {}

    return _check(
        "F3. a plain 'اتاق خواب فضای خصوصی است' is still a teaching "
        "statement about the plain bedroom (unchanged)",
        candidate.get("space_topic") is None
        and candidate.get("status") == "observed"
        and teaching.get("action") == "record_teaching_statement",
        {"candidate": candidate, "action": teaching.get("action")},
    )


def test_no_render_is_ever_requested():

    project_id = _project()

    observation, _response, _teaching = _turn(
        QUESTION_FINAL, project_id
    )

    return _check(
        "F4. no turn requests a render (render-stop guard is not needed "
        "on these paths)",
        observation.get("render_requested") is False,
        {"render_requested": observation.get("render_requested")},
    )


# ==========================================================
# 7. CLAUSE ANALYSIS — a long message is not one statement
# ==========================================================

def test_the_long_message_yields_every_rule():

    clauses = knowledge_clauses(LONG_RULES)

    rules = [c for c in clauses if c["role"] == "RULE"]

    texts = " || ".join(c["text"] for c in clauses)

    return _check(
        "G1. the long message yields 4 RULES (was: ONE wrong triple)",
        len(rules) == 4
        and "تخت باید جایی گذاشته شود" in texts
        and "تخت دور از پنجره باشه بهتره" in texts
        and "اتاق خواب ها باید دور از پذیرایی" in texts
        and "حریمش باید حفظ شود" in texts,
        {"rules": [c["text"] for c in rules]},
    )


def test_the_reason_is_kept_as_a_rationale_not_as_knowledge():

    clauses = knowledge_clauses(LONG_RULES)

    by_text = {c["text"]: c for c in clauses}

    rule = next(
        (
            c for c in clauses
            if c["text"].startswith("اتاق خواب ها باید دور از پذیرایی")
        ),
        {},
    )

    every_text = " || ".join(by_text)

    return _check(
        "G2. the 'چون ...' reason is NOT knowledge but IS the rule's "
        "rationale",
        rule.get("rationale") == "اون فضاها فضاهای عمومی هستن و مهمان میاد"
        and "چون اون فضاها" not in every_text,
        {"rationale": rule.get("rationale")},
    )


def test_the_premise_before_a_conclusion_becomes_the_rationale():

    clauses = knowledge_clauses(LONG_RULES)

    rule = next(
        (
            c for c in clauses
            if c["text"].startswith("تخت باید جایی گذاشته شود")
        ),
        {},
    )

    return _check(
        "G3. the premise before 'پس' is the rule's rationale, not a "
        "statement of its own",
        bool(rule.get("rationale"))
        and "محل معاشقه" in (rule.get("rationale") or ""),
        {"rationale": rule.get("rationale")},
    )


def test_meta_and_the_quoted_assistant_are_not_knowledge():

    clauses = knowledge_clauses(QUOTED_META)

    texts = " || ".join(c["text"] for c in clauses)

    return _check(
        "G4. 'اشتباه فهمیدی' and the quoted assistant restatement are "
        "dropped, and the real rules are kept",
        "اشتباه فهمیدی" not in texts
        and "پنجره باید دور از اتاق خواب و نشیمن" not in texts
        and "تخت دور از پنجره باشه بهتره" in texts
        and "نشیمن هم باید پنجره داشته باشه" in texts,
        {"clauses": [c["text"] for c in clauses]},
    )


def test_a_single_clause_message_keeps_the_old_behaviour():

    project_id = _project()

    observation, _response, teaching = _turn(
        PLAIN_BEDROOM, project_id
    )

    candidate = teaching.get("candidate") or {}

    return _check(
        "G5. a one-clause message keeps the EXACT previous behaviour "
        "(one candidate, clause_count None)",
        observation.get("clause_count") is None
        and len(teaching.get("candidates") or []) == 1
        and candidate.get("raw_statement") == PLAIN_BEDROOM
        and candidate.get("clause_role") is None,
        {
            "clause_count": observation.get("clause_count"),
            "candidates": len(teaching.get("candidates") or []),
        },
    )


def test_a_multi_clause_message_is_stored_as_several_candidates():

    project_id = _project()

    observation, response, teaching = _turn(LONG_RULES, project_id)

    stored = teaching_candidate_store.candidates(project_id)

    text = response.get("result") or ""

    return _check(
        "G6. the message is stored as 4 separate candidates, each with "
        "its clause role and the full source statement",
        observation.get("clause_count") == 4
        and len(stored) == 4
        and all(c.get("clause_role") == "RULE" for c in stored)
        and all(c.get("source_statement") == LONG_RULES for c in stored)
        and all(c.get("clause_index") is not None for c in stored)
        and "تقسیم کردم" in text,
        {
            "clause_count": observation.get("clause_count"),
            "stored": len(stored),
            "roles": [c.get("clause_role") for c in stored],
        },
    )


def test_the_bed_is_a_subject_of_its_own():

    meaning = _meaning("تخت دور از پنجره باشه بهتره")

    entities = meaning.get("entities") or []

    return _check(
        "G7. 'تخت' is an entity, so the bed rule has the bed as its "
        "subject (was: subject inverted to پنجره)",
        entities and entities[0] == "bed" and "window" in entities,
        {"entities": entities},
    )


def test_a_plain_message_is_not_split_into_noise():

    clauses = knowledge_clauses("آشپزخانه باید کنار نشیمن باشد")

    return _check(
        "G8. an ordinary one-rule message stays one clause (no "
        "over-segmentation)",
        len(clauses) == 1 and clauses[0]["role"] == "RULE",
        {"clauses": [c["text"] for c in clauses]},
    )


def test_a_taxonomy_message_keeps_its_definition_and_its_rule():

    clauses = knowledge_clauses(TAXONOMY_MESSAGE)

    roles = [c["role"] for c in clauses]

    texts = " || ".join(c["text"] for c in clauses)

    return _check(
        "G10. the taxonomy message yields a DEFINITION (two kinds of "
        "bedroom) and a RULE — not 'this is a correction'",
        len(clauses) == 2
        and "DEFINITION" in roles
        and "RULE" in roles
        and "دو نمونه داریم" in texts
        and "دور از نشیمن" in texts
        and "اشتباه فهمیدی" not in texts
        and "دلایلش رو" not in texts,
        {"roles": roles, "texts": [c["text"] for c in clauses]},
    )


def test_the_clause_analysis_stores_nothing():
    before = os.environ.get("ARCHITECTOS_PROJECT_DATA_ROOT")

    clauses = segment(LONG_RULES)

    return _check(
        "G9. the analyser is pure: it only returns clauses",
        bool(clauses)
        and os.environ.get("ARCHITECTOS_PROJECT_DATA_ROOT") == before
        and all(set(c) >= {"role", "text", "knowledge"} for c in clauses),
        {"count": len(clauses)},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("CORRECTION_LOOP_01 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_the_users_short_forms_resolve_to_the_master_bedroom,
        test_a_bare_bedroom_keeps_its_own_space,
        test_every_teaching_statement_attaches_to_the_master_bedroom,
        test_the_alias_table_is_the_single_source,
        test_a_definition_with_a_trailing_clause_is_recorded,
        test_a_copula_about_nothing_architectural_is_not_recovered,
        test_a_space_less_statement_alone_is_still_unknown,
        test_an_inherited_topic_makes_the_statement_about_that_space,
        test_the_correction_is_recorded_not_rejected,
        test_a_non_architectural_statement_is_still_rejected,
        test_a_denial_opener_is_a_correction,
        test_a_bare_denial_is_not_a_correction,
        test_the_original_correction_path_is_unchanged,
        test_the_denial_is_recorded_against_the_space,
        test_the_promotion_request_is_detected,
        test_the_negatives_are_not_promotion_requests,
        test_the_refusal_reports_the_bridge_truth,
        test_the_promotion_turn_never_reaches_the_llm,
        test_the_promotion_turn_creates_nothing,
        test_the_full_user_session_closes_the_loop,
        test_the_short_form_question_is_grounded_too,
        test_nothing_is_silently_promoted,
        test_the_retrieval_stays_project_scoped,
        test_a_plain_statement_is_unchanged,
        test_no_render_is_ever_requested,
        test_the_long_message_yields_every_rule,
        test_the_reason_is_kept_as_a_rationale_not_as_knowledge,
        test_the_premise_before_a_conclusion_becomes_the_rationale,
        test_meta_and_the_quoted_assistant_are_not_knowledge,
        test_a_single_clause_message_keeps_the_old_behaviour,
        test_a_multi_clause_message_is_stored_as_several_candidates,
        test_the_bed_is_a_subject_of_its_own,
        test_a_plain_message_is_not_split_into_noise,
        test_a_taxonomy_message_keeps_its_definition_and_its_rule,
        test_the_clause_analysis_stores_nothing,
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
