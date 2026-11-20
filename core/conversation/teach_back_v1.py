# ==========================================================
# ArchitectOS Teach-Back v1
#
# PHASE 08D — UNDERSTANDING / TEACH-BACK
#
# ArchitectOS explains WHAT IT UNDERSTOOD — without ever claiming it
# has permanently learned it.
#
#   "I understood ..."          <- implemented here
#   "I permanently learned ..." <- NOT implemented, and never claimed
#
# The reply is built ONLY from teaching CANDIDATES recorded in the
# current project.  Nothing is invented, nothing is upgraded to truth,
# and the permanent-learning disclaimer is part of every answer.
# ==========================================================


from __future__ import annotations


from core.conversation.teaching_candidate_v1 import (
    teaching_candidate_store,
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.teaching_meaning_v1 import (
    restate,
    domain_display,
    kind_display,
    status_display,
    entity_display,
    knowledge_class_display,
    scope_display,
    provenance_display,
)

# PHASE 09 — teaching intent / elicitation
from core.conversation.turn_semantics_v1 import teaching_aspects

# CLAUSE_ANALYSIS_01 — the display name of a clause role. Imported, never
# re-derived, so the role vocabulary has ONE owner.
from core.conversation.clause_analysis_v1 import (
    role_display,
    knowledge_clauses,
    ROLE_OBSERVATION,
)


CONTRACT = "TeachBackV1"
VERSION = "1.0"


DEFAULT_LIMIT = 12


# ----------------------------------------------------------
# PHRASES
# ----------------------------------------------------------

PHRASES = {

    "fa": {

        "header": (
            "\u0627\u06cc\u0646 \u0686\u06cc\u0632\u06cc \u0627\u0633\u062a "
            "\u06a9\u0647 \u0627\u0632 \u062d\u0631\u0641 \u0634\u0645\u0627 "
            "\u0641\u0647\u0645\u06cc\u062f\u0645:"
        ),

        "item": "\u2022 %s\n  \u0641\u0647\u0645\u06cc\u062f\u0645: %s\n  \u0646\u0648\u0639: %s \u2014 \u062d\u0648\u0632\u0647: %s \u2014 \u0648\u0636\u0639\u06cc\u062a: %s\n  \u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc: %s \u2014 \u062f\u0627\u0645\u0646\u0647: %s \u2014 \u0645\u0646\u0628\u0639: %s",

        # TEACHING SESSION STATE FIX — this branch is reached when the
        # user asked for a teach-back and NO teaching candidate exists.
        # It used to state only that, which read as if the assistant had
        # no architectural knowledge at all. It must now DISTINGUISH:
        #   (a) no statements recorded FROM THE USER, from
        #   (b) the EXISTING architectural knowledge in the corpus,
        # and point at the read-only reflection route for (b).
        "empty": (
            "\u062f\u0631 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698"
            "\u0647 \u0647\u0646\u0648\u0632 \u062c\u0645\u0644\u0647"
            "\u0654 \u0622\u0645\u0648\u0632\u0634\u06cc \u06cc\u0627"
            " \u0627\u0635\u0644\u0627\u062d\u06cc \u0627\u0632 "
            "\u0634\u0645\u0627 \u062b\u0628\u062a \u0646\u0634\u062f"
            "\u0647 \u0627\u0633\u062a\u060c \u067e\u0633 \u0686"
            "\u06cc\u0632\u06cc \u0627\u0632 \u062d\u0631\u0641\u200c"
            "\u0647\u0627\u06cc \u0634\u0645\u0627 \u0628\u0631\u0627"
            "\u06cc \u0628\u0627\u0632\u06af\u0641\u062a\u0646 \u0646"
            "\u062f\u0627\u0631\u0645.\n\u062a\u0648\u062c\u0647: "
            "\u0627\u06cc\u0646 \u067e\u0627\u0633\u062e \u062f\u0631"
            "\u0628\u0627\u0631\u0647\u0654 \u00ab\u062f\u0627\u0646"
            "\u0633\u062a\u0647\u0654 \u0634\u0645\u0627\u00bb \u0627"
            "\u0633\u062a\u060c \u0646\u0647 \u062f\u0631\u0628\u0627"
            "\u0631\u0647\u0654 \u062f\u0627\u0646\u0634 \u0645\u0639"
            "\u0645\u0627\u0631\u06cc \u0645\u0648\u062c\u0648\u062f."
            " \u0627\u06af\u0631 \u0645\u06cc\u200c\u062e\u0648\u0627"
            "\u0647\u06cc\u062f \u0628\u0631\u062f\u0627\u0634\u062a "
            "\u0641\u0639\u0644\u06cc \u0645\u0646 \u0627\u0632 "
            "\u06cc\u06a9 \u0641\u0636\u0627 \u0631\u0627 \u0628"
            "\u0628\u06cc\u0646\u06cc\u062f\u060c \u0628\u067e\u0631"
            "\u0633\u06cc\u062f: \u00ab\u0628\u0631\u062f\u0627\u0634"
            "\u062a \u0641\u0639\u0644\u06cc \u062a\u0648 \u0627"
            "\u0632 \u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628"
            " \u0686\u06cc\u0633\u062a\u061f\u00bb"
        ),

        "understood_heading": (
            "\u0641\u0647\u0645\u06cc\u062f\u0645 (I understood)"
        ),

        "learned_heading": (
            "\u06cc\u0627\u062f \u0646\u06af\u0631\u0641\u062a\u0647\u200c\u0627\u0645 "
            "(I have NOT permanently learned)"
        ),

        "disclaimer": (
            "\u0645\u0647\u0645: \u0645\u0646 \u0627\u06cc\u0646 \u0646\u06a9\u0627\u062a "
            "\u0631\u0627 \u0641\u0642\u0637 \u00ab\u0641\u0647\u0645\u06cc\u062f\u0645\u00bb\u061b "
            "\u0647\u0646\u0648\u0632 \u0628\u0647 \u062f\u0627\u0646\u0634 "
            "\u062f\u0627\u0626\u0645\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc "
            "\u062a\u0628\u062f\u06cc\u0644 \u0646\u0634\u062f\u0647\u200c\u0627\u0646\u062f "
            "\u0648 \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 \u062d\u0642\u06cc\u0642\u062a "
            "\u0630\u062e\u06cc\u0631\u0647 \u0646\u0634\u062f\u0647\u200c\u0627\u0646\u062f."
        ),

        "candidates_only": (
            "\u0627\u06cc\u0646\u0647\u0627 \u0641\u0642\u0637 \u06a9\u0627\u0646\u062f\u06cc\u062f\u0627\u062a "
            "\u0647\u0633\u062a\u0646\u062f\u060c \u0646\u0647 \u062f\u0627\u0646\u0634 "
            "\u062a\u0623\u06cc\u06cc\u062f\u0634\u062f\u0647."
        ),

        # CLAUSE_ANALYSIS_01 — the store grows faster now that one message
        # becomes several candidates, so say when the list is not the
        # whole story instead of silently showing only the newest ones.
        "truncated": (
            "\u2026 \u0648 %s \u0645\u0648\u0631\u062f \u0642\u062f\u06cc\u0645\u06cc\u200c\u062a\u0631 "
            "\u0647\u0645 \u062b\u0628\u062a \u0634\u062f\u0647 \u0627\u0633\u062a."
        ),
    },

    "en": {

        "header": "This is what I understood from what you said:",

        "item": "\u2022 %s\n  I understood: %s\n  Kind: %s \u2014 Domain: %s \u2014 Status: %s\n  Class: %s \u2014 Scope: %s \u2014 Provenance: %s",

        # TEACHING SESSION STATE FIX — distinguishes "nothing recorded
        # from YOU" from "no architectural knowledge at all".
        "empty": (
            "No teaching or correction statement from you has been "
            "recorded in this project yet, so I have nothing of YOURS "
            "to restate.\nNote: this answers what YOU have told me \u2014 "
            "it is not the existing architectural knowledge. To see my "
            "current understanding of a space, ask: \u201cWhat is your "
            "current understanding of the bedroom?\u201d"
        ),

        "understood_heading": "I understood",

        "learned_heading": "I have NOT permanently learned",

        "disclaimer": (
            "Important: I only UNDERSTOOD these points. They have not "
            "become permanent architectural knowledge and have not been "
            "stored as truth."
        ),

        "candidates_only": (
            "These are candidates only, not accepted knowledge."
        ),

        "truncated": "\u2026 and %s older items are recorded too.",
    },
}


def phrases(language):

    return PHRASES["fa" if str(language or "").startswith("fa") else "en"]


# ----------------------------------------------------------
# STATEMENT RENDERING
# ----------------------------------------------------------

def render_statement(candidate, language="en"):

    """Human-readable line for one candidate."""

    lang = "fa" if str(language or "").startswith("fa") else "en"

    meaning = {

        "candidate_kind": candidate.get("candidate_kind"),
        "subject": (candidate.get("entities") or [None])[0],
        "objects": (candidate.get("entities") or [None])[1:],
        "primary_relation": (candidate.get("relations") or [None])[0],
        "polarity": candidate.get("polarity"),
    }

    return {

        "candidate_id": candidate.get("candidate_id"),

        "raw_statement": candidate.get("raw_statement"),

        "normalized_meaning": candidate.get("normalized_meaning"),

        "understood_as": restate(meaning, lang),

        "domain": candidate.get("domain"),

        "candidate_kind": candidate.get("candidate_kind"),

        # PHASE 09 — learning taxonomy
        "knowledge_class": candidate.get("knowledge_class"),

        "scope": candidate.get("scope"),

        "provenance": candidate.get("provenance"),

        "domain_tags": candidate.get("domain_tags") or [],

        "status": candidate.get("status"),

        "confidence": candidate.get("confidence"),

        "confidence_kind": candidate.get("confidence_kind"),

        # explicit, machine-readable truth flags
        "is_learned_knowledge": False,
        "is_permanent": False,
    }


# ----------------------------------------------------------
# TEACH-BACK
# ----------------------------------------------------------

def build_teach_back(
    project_id=None,
    language="en",
    limit=DEFAULT_LIMIT,
    store=None,
):

    """Explain what was understood. Never claim permanent learning."""

    lang = "fa" if str(language or "").startswith("fa") else "en"

    text = phrases(lang)

    store = store or teaching_candidate_store

    candidates = []

    if project_id:

        candidates = store.candidates(project_id)

    # Only candidates that actually carry an observed meaning are worth
    # restating; rejected ones are reported separately as rejected.
    #
    # CLAUSE_ANALYSIS_01 — one message can now produce several
    # candidates, so the window is wider AND the reply says when older
    # items exist instead of silently hiding them.
    considered = candidates[-max(1, int(limit)):]

    hidden = len(candidates) - len(considered)

    statements = [render_statement(c, lang) for c in considered]

    understood = [
        s for s in statements if s.get("status") != "rejected"
    ]

    if not statements:

        result = text["empty"]

    else:

        lines = [text["header"]]

        for statement in statements:

            lines.append(
                text["item"]
                % (
                    statement.get("raw_statement") or "",
                    statement.get("understood_as") or "",
                    kind_display(
                        statement.get("candidate_kind"), lang
                    ),
                    domain_display(statement.get("domain"), lang),
                    status_display(statement.get("status"), lang),
                    knowledge_class_display(
                        statement.get("knowledge_class"), lang
                    ),
                    scope_display(statement.get("scope"), lang),
                    provenance_display(
                        statement.get("provenance"), lang
                    ),
                )
            )

        lines.append("")
        lines.append(text["candidates_only"])

        if hidden > 0:

            lines.append(
                text["truncated"] % _count_display(hidden, lang)
            )

        lines.append(text["disclaimer"])

        result = "\n".join(lines)

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "status": "success",

        "language": lang,

        "project_id": project_id,

        "result": result,

        # --- what was understood ---
        "understanding_statement": (
            text["understood_heading"] if understood
            else text["empty"]
        ),

        # --- what was NOT learned (explicit) ---
        "learning_statement": text["learned_heading"],

        "learned_anything": False,

        "permanent_learning_implemented": PERMANENT_LEARNING_IMPLEMENTED,

        "candidates_considered": len(statements),

        "candidates_with_meaning": len(understood),

        "statements": statements,

        "allowed_statuses": list(ALLOWED_STATUSES),

        "distinguishes_understanding_from_learning": True,

        "llm_used": False,
        "network_used": False,
        "render_requested": False,
    }


# ==========================================================
# PHASE 09 — TEACHING INTENT / ELICITATION
# ==========================================================

ELICITATION_PHRASES = {

    "fa": {

        # TEACHER ROLE RESPONSE FIX — the lead must state the ROLE
        # CONTRACT, not just the assistant's willingness. The previous
        # wording ("آماده‌ام یاد بگیرم" / "I am ready to learn") implied
        # the assistant's role but never acknowledged the USER as the
        # teacher, and the `request_lead` variant actively inverted it
        # ("thank you for wanting to learn") while the very next line
        # asked the user which aspect they wanted to TEACH.
        "offer_lead": (
            "\u0645\u062a\u0648\u062c\u0647 \u0634\u062f\u0645. "
            "\u0634\u0645\u0627 \u0645\u06cc\u200c\u062e\u0648\u0627"
            "\u0647\u06cc\u062f \u0628\u0647 \u0645\u0646 \u0622"
            "\u0645\u0648\u0632\u0634 \u062f\u0647\u06cc\u062f\u061b "
            "\u0634\u0645\u0627 \u0645\u062f\u0631\u0633 \u0647\u0633"
            "\u062a\u06cc\u062f \u0648 \u0645\u0646 \u06cc\u0627"
            "\u062f \u0645\u06cc\u200c\u06af\u06cc\u0631\u0645 \u0648"
            " \u0647\u06cc\u0686 \u0686\u06cc\u0632\u06cc \u0628"
            "\u0647\u200c\u0635\u0648\u0631\u062a \u062e\u0648\u062f"
            "\u06a9\u0627\u0631 \u06cc\u0627\u062f \u06af\u0631\u0641"
            "\u062a\u0647 \u0646\u0645\u06cc\u200c\u0634\u0648\u062f."
        ),

        # Used ONLY when the user explicitly asked to be taught
        # ("یاد بده" / "teach me"). In that case the user IS the learner,
        # so the lead must not claim the teacher role for them.
        "request_lead": (
            "\u0628\u0627\u0634\u062f\u060c \u0627\u0632 \u0627\u06cc\u0646 \u06a9\u0647 "
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u06cc\u062f \u06cc\u0627\u062f "
            "\u0628\u06af\u06cc\u0631\u06cc\u062f \u0645\u062a\u0634\u06a9\u0631\u0645."
        ),

        # The brief-defined question shape.
        "ask_topic": (
            "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634 %s \u0631\u0627 "
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u06cc\u062f "
            "\u0622\u0645\u0648\u0632\u0634 \u062f\u0647\u06cc\u062f\u061f"
        ),

        "ask_generic": (
            "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634 \u0631\u0627 "
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u06cc\u062f "
            "\u0622\u0645\u0648\u0632\u0634 \u062f\u0647\u06cc\u062f\u061f"
        ),

        "not_learned": (
            "\u0645\u0646 \u0641\u0642\u0637 \u06af\u0648\u0634 "
            "\u0645\u06cc\u200c\u062f\u0647\u0645 \u0648 "
            "\u06cc\u0627\u062f\u062f\u0627\u0634\u062a "
            "\u0645\u06cc\u200c\u06a9\u0646\u0645\u061b \u062a\u0627 "
            "\u062a\u0623\u06cc\u06cc\u062f \u0634\u0645\u0627 \u0647\u06cc\u0686 "
            "\u0686\u06cc\u0632\u06cc \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 "
            "\u062f\u0627\u0646\u0634 \u062f\u0627\u0626\u0645\u06cc "
            "\u062b\u0628\u062a \u0646\u0645\u06cc\u200c\u0634\u0648\u062f."
        ),
    },

    "en": {

        "offer_lead": (
            "Understood. You are the teacher and I am the learner, and "
            "nothing is learned automatically."
        ),

        "request_lead": "Thank you \u2014 I am glad to be taught.",

        "ask_topic": "Which aspect of %s would you like to teach?",

        "ask_generic": "Which aspect would you like to teach?",

        "not_learned": (
            "I will only listen and take notes; nothing becomes permanent "
            "knowledge without your explicit confirmation."
        ),
    },
}


def build_teaching_elicitation(
    topic=None,
    language="fa",
    direction="user_offers_to_teach",
    aspects=None,
):

    """Clarifying question for a teaching intent.

    `aspects` is an OPTIONAL aspect set. PHASE 10 passes the five
    space-specific aspects when the topic is a known architectural
    space; when it is None the generic architectural aspects are used,
    so Phase 09 behaviour is unchanged.

    ROLE CONTRACT (TEACHER ROLE RESPONSE FIX)

    `direction` selects the role the reply presents:

      user_offers_to_teach    -> the USER is the teacher,
                                 the assistant is the learner
      user_requests_teaching  -> the user explicitly asked to be taught,
                                 so the user is the learner

    The resolved role is exposed as `user_as_teacher` so a caller never
    has to re-derive it from the wording.

    Returns the same contract shape as the other conversation replies so
    the caller can treat it uniformly.
    """

    lang = "fa" if str(language or "").startswith("fa") else "en"

    text = ELICITATION_PHRASES[lang]

    aspects = aspects or teaching_aspects(lang)

    user_as_teacher = direction != "user_requests_teaching"

    lines = [
        text["offer_lead"]
        if user_as_teacher
        else text["request_lead"]
    ]

    if topic:

        lines.append(text["ask_topic"] % topic)

    else:

        lines.append(text["ask_generic"])

    lines.extend(
        "\u2022 " + aspect["label"] for aspect in aspects
    )

    lines.append(text["not_learned"])

    return {

        "contract": "TeachingElicitationV1",
        "version": "1.0",

        "status": "success",

        "language": lang,

        "direction": direction,

        # TEACHER ROLE RESPONSE FIX — explicit role contract.
        "user_as_teacher": user_as_teacher,

        "assistant_as_learner": user_as_teacher,

        "topic": topic,

        "aspects": aspects,

        "result": "\n".join(lines),

        # A teaching intent is NOT knowledge yet and NOT an action.
        "is_knowledge": False,
        "is_action": False,
        "routed_to_execute": False,
        "candidate_created": False,
        "learned_anything": False,
        "permanent_learning_implemented": False,

        "llm_used": False,
        "network_used": False,
        "render_requested": False,
    }


# ----------------------------------------------------------
# TEACHING_QUESTION_RETRIEVAL — ANSWER A QUESTION FROM THE TEACHING
#
# A QUESTION about a space that HAS teacher-recorded knowledge must be
# answered from that knowledge, never from the generic LLM. This builder
# lists exactly what was recorded, with provenance and uncertainty, and
# states plainly that anything outside the list was never taught.
#
# It returns None when the space has NO recorded teaching, so the caller
# keeps the existing behaviour unchanged.
# ----------------------------------------------------------

GROUNDED_PHRASES = {

    "fa": {

        "header": (
            "\u0627\u0632 \u0622\u0646\u0686\u0647 \u062f\u0631"
            "\u0628\u0627\u0631\u0647\u0654 \u00ab%s\u00bb \u0628"
            "\u0647 \u0645\u0646 \u06cc\u0627\u062f \u062f\u0627"
            "\u062f\u0647\u200c\u0627\u06cc\u062f\u060c \u0627"
            "\u06cc\u0646\u200c\u0647\u0627 \u062b\u0628\u062a "
            "\u0634\u062f\u0647 \u0627\u0633\u062a:"
        ),

        "item": (
            "\u2022 %s\n  \u0645\u0646\u0628\u0639: %s \u2014 "
            "\u0648\u0636\u0639\u06cc\u062a: %s"
        ),

        # CLAUSE_ANALYSIS_01 — a clause-level item names its own role, so
        # the teacher sees WHICH part of the message was taken.
        "item_role": (
            "\u2022 %s\n  \u0646\u0648\u0639: %s\n  \u0645\u0646\u0628\u0639: "
            "%s \u2014 \u0648\u0636\u0639\u06cc\u062a: %s"
        ),

        # CLAUSE_ANALYSIS_01 — a candidate recorded BEFORE the analyser
        # existed is one long message; say so and show its rules.
        "legacy_intro": (
            "\u2022 %s\n  \u0646\u0648\u0639: %s\n  "
            "(\u062b\u0628\u062a \u0634\u062f\u0647 \u0628\u0647\u200c"
            "\u0635\u0648\u0631\u062a \u06cc\u06a9 \u067e\u06cc\u0627\u0645 "
            "\u06a9\u0627\u0645\u0644\u061b \u0627\u06cc\u0646 "
            "\u0642\u0648\u0627\u0639\u062f \u0631\u0627 \u062f\u0631 "
            "\u0622\u0646 \u062f\u0627\u0631\u062f:)\n  \u0645\u0646\u0628\u0639: "
            "%s \u2014 \u0648\u0636\u0639\u06cc\u062a: %s"
        ),

        "legacy_rule": "    - %s  (%s)",

        "source_human": (
            "\u0645\u062f\u0631\u0633 \u0627\u0646\u0633\u0627"
            "\u0646\u06cc"
        ),

        "status_observed": (
            "\u062f\u0631\u06cc\u0627\u0641\u062a\u200c\u0634\u062f"
            "\u0647 (\u062a\u0623\u06cc\u06cc\u062f\u0646\u0634"
            "\u062f\u0647)"
        ),

        "status_pending": (
            "\u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631 "
            "\u062a\u0623\u06cc\u06cc\u062f"
        ),

        "legacy_label": "یک پیام کامل",

        # ==================================================
        # SUBJECT_SCOPE_01 — WHAT WAS LEFT OUT, SAID OUT LOUD
        #
        # A recorded message can name SEVERAL spaces. When part of it is
        # about a different space, that part is NOT listed as a rule for
        # the space that was asked about — and the omission is reported
        # rather than hidden. Nothing is deleted or rewritten.
        # ==================================================

        "omitted": (
            "• %d مورد ثبت‌شده دربارهٔ فضای دیگری است و در پاسخ به "
            "این پرسش نیامده است."
        ),

        "uncertainty": (
            "\u0627\u06cc\u0646\u200c\u0647\u0627 \u0641\u0642"
            "\u0637 \u00ab\u062f\u0631\u06cc\u0627\u0641\u062a"
            "\u200c\u0634\u062f\u0647\u00bb \u0647\u0633\u062a"
            "\u0646\u062f \u0648 \u0647\u0646\u0648\u0632 \u0628"
            "\u0647 \u062f\u0627\u0646\u0634 \u062f\u0627\u0626"
            "\u0645\u06cc \u062a\u0628\u062f\u06cc\u0644 \u0646"
            "\u0634\u062f\u0647\u200c\u0627\u0646\u062f."
        ),

        "not_taught": (
            "\u0627\u06af\u0631 \u067e\u0631\u0633\u0634 \u0634"
            "\u0645\u0627 \u0645\u0648\u0636\u0648\u0639\u06cc "
            "\u0628\u06cc\u0631\u0648\u0646 \u0627\u0632 \u0627"
            "\u06cc\u0646 \u0641\u0647\u0631\u0633\u062a \u0628"
            "\u0627\u0634\u062f\u060c \u0622\u0646 \u0631\u0627 "
            "\u06cc\u0627\u062f \u0646\u06af\u0631\u0641\u062a"
            "\u0647\u200c\u0627\u0645 \u0648 \u062d\u062f\u0633"
            "\u06cc \u0646\u0645\u06cc\u200c\u0632\u0646\u0645."
        ),
    },

    "en": {

        "header": (
            "From what you have taught me about \u201c%s\u201d, this "
            "is recorded:"
        ),

        "item": "\u2022 %s\n  Source: %s \u2014 Status: %s",

        "item_role": "\u2022 %s\n  Type: %s\n  Source: %s \u2014 Status: %s",

        "legacy_intro": (
            "\u2022 %s\n  Type: %s\n  (recorded as one whole message; "
            "these rules are inside it:)\n  Source: %s \u2014 Status: %s"
        ),

        "legacy_rule": "    - %s  (%s)",

        "source_human": "human teacher",

        "status_observed": "received (not confirmed)",

        "status_pending": "awaiting confirmation",

        "legacy_label": "one whole message",

        # SUBJECT_SCOPE_01 — an omission is reported, never hidden.
        "omitted": (
            "\u2022 %d recorded item(s) are about a DIFFERENT space and "
            "are not listed in this answer."
        ),

        "uncertainty": (
            "These are RECEIVED only; none of them has become permanent "
            "knowledge."
        ),

        "not_taught": (
            "If your question is about something outside this list, I "
            "was never taught it and I will not guess."
        ),
    },
}


# Statuses that are still teacher-sourced and not rejected.
_GROUNDABLE_STATUSES = ("observed", "needs_confirmation")


# ==========================================================
# SUBJECT_SCOPE_01 — ONLY THE RULES ABOUT THE SPACE THAT WAS ASKED
#
# The teacher's own messages mix spaces. "اتاق خواب ها باید دور از
# پذیرایی و فضاهای نشیمن باشن" is a BEDROOM rule that happens to name
# the living area, while "نشیمن هم باید پنجره داشته باشه" is a LIVING
# rule that has nothing to do with the master bedroom. A question about
# the master bedroom must answer with the first and never with the
# second.
#
# The rule below is deliberately one-sided and conservative:
#
#   * a clause that names NO space is kept — it inherits the subject of
#     the message it came from ("تخت دور از پنجره باشه بهتره").
#   * a clause is dropped ONLY when EVERY space it names sits on the
#     opposite side of the privacy axis from the space that was asked
#     about (private bedroom vs public seating / reception).
#
# The axis comes from the frozen space registry (`space_types`), never
# from a new vocabulary. Nothing is written; this is a display-time
# projection of records that stay untouched on disk.
# ==========================================================

_PUBLIC_BAND = "public"

_PRIVATE_BAND = "private"


def _space_band(space_id):

    """`public` / `private` / None for a corpus space id."""

    if not space_id:

        return None

    try:

        from core.curriculum.space_types_v1 import (
            space_types,
            CATEGORY_PUBLIC,
            CATEGORY_SEMI_PUBLIC,
            CATEGORY_PRIVATE,
        )

        record = space_types.space(space_id) or {}

        category = record.get("category")

    except Exception:

        return None

    if category in (CATEGORY_PUBLIC, CATEGORY_SEMI_PUBLIC):

        return _PUBLIC_BAND

    if category == CATEGORY_PRIVATE:

        return _PRIVATE_BAND

    # SERVICE / CIRCULATION / EXTERNAL / unknown — never used to drop.
    return None


def _named_spaces(text):

    """The corpus spaces a clause names, in position order."""

    try:

        from core.curriculum.space_query_v1 import scan_spaces

        mentions = scan_spaces(text)

    except Exception:

        return []

    return [mention[0] for mention in (mentions or [])]


def _in_subject_scope(text, space_topic):

    """Is this clause about the space that was asked about?"""

    mentions = _named_spaces(text)

    if not mentions:

        return True

    asked = _space_band(space_topic)

    if asked is None:

        return True

    opposite = (
        _PRIVATE_BAND if asked == _PUBLIC_BAND else _PUBLIC_BAND
    )

    for space_id in mentions:

        if _space_band(space_id) != opposite:

            return True

    return False


def _without(text, clauses):

    """The recorded message with the out-of-scope clauses removed.

    A projection of the teacher's OWN words: everything that stays is a
    verbatim substring of the record, so nothing is paraphrased and
    nothing is invented. The record on disk is not touched.
    """

    result = text or ""

    for clause in clauses:

        piece = (clause or {}).get("text") or ""

        if piece:

            result = result.replace(piece, "")

    result = result.replace("، ،", "،")

    result = " ".join(result.split())

    return result.strip(" ،,.")


def _space_label(space_topic, language):

    """Display name for a space id — reuses the corpus, never a copy."""

    try:

        label = entity_display(space_topic, language)

        if label:

            return label

    except Exception:

        pass

    return str(space_topic or "")


def build_grounded_answer(
    project_id=None,
    space_topic=None,
    language="fa",
    store=None,
):

    """Answer a QUESTION from the recorded teaching, or None.

    TEACHING_QUESTION_RETRIEVAL.

    Returns None when this space has NO teacher-recorded knowledge, so
    the caller keeps the existing behaviour. Never invents anything: it
    reports exactly what was recorded, with provenance and uncertainty.
    """

    if not project_id or not space_topic:

        return None

    store = store or teaching_candidate_store

    try:

        entries = store.candidates(project_id)

    except Exception:

        return None

    recorded = [

        entry for entry in (entries or [])

        if (entry or {}).get("space_topic") == space_topic

        and (entry or {}).get("provenance") == "HUMAN_TEACHER"

        and (entry or {}).get("status") in _GROUNDABLE_STATUSES
    ]

    if not recorded:

        return None

    lang = "fa" if str(language or "").startswith("fa") else "en"

    text = GROUNDED_PHRASES[lang]

    lines = [text["header"] % _space_label(space_topic, lang)]

    reported = []

    # SUBJECT_SCOPE_01 — how many recorded items this answer leaves out
    # because they are about a different space.
    omitted = 0

    for entry in recorded:

        statement = entry.get("raw_statement") or ""

        status = (
            text["status_pending"]
            if entry.get("status") == "needs_confirmation"
            else text["status_observed"]
        )

        role = entry.get("clause_role")

        # ==================================================
        # CLAUSE_ANALYSIS_01 — DO NOT DUMP A WHOLE MESSAGE
        #
        # A candidate recorded BEFORE the analyser existed is one long
        # message, and listing it verbatim is exactly the "کلی گویی" the
        # teacher reported. Re-analyse it READ-ONLY at display time and
        # show the rules it actually contains. Nothing is written, and
        # the original wording is still shown as the heading.
        # ==================================================

        nested = []

        if not role:

            try:

                nested = [
                    clause for clause in knowledge_clauses(statement)
                    if clause.get("role") != ROLE_OBSERVATION
                ]

            except Exception:

                nested = []

        # ==================================================
        # SUBJECT_SCOPE_01 — A CLAUSE ABOUT ANOTHER SPACE IS NOT A RULE
        # ABOUT THIS ONE
        #
        # Applied to every shape: a single clause candidate, a legacy
        # whole message (rule by rule), and a plain statement. When a
        # legacy message keeps at least one rule, the message is still
        # shown with its own wording and only the out-of-scope rules are
        # left out of the list. When it keeps none, the message itself
        # is left out. Either way the count is reported below.
        # ==================================================

        if role:

            if not _in_subject_scope(statement, space_topic):

                omitted += 1

                continue

        elif len(nested) >= 2:

            scoped = []

            dropped = []

            for clause in nested:

                if _in_subject_scope(clause.get("text") or "", space_topic):

                    scoped.append(clause)

                else:

                    dropped.append(clause)

            if not scoped:

                omitted += 1

                continue

            omitted += len(dropped)

            nested = scoped

            # The heading is the same message with only the other
            # space's wording taken out — never reworded.
            statement = _without(statement, dropped)

        elif not _in_subject_scope(statement, space_topic):

            omitted += 1

            continue

        if role:

            lines.append(
                text["item_role"]
                % (
                    statement,
                    role_display(role, lang),
                    text["source_human"],
                    status,
                )
            )

        elif len(nested) >= 2:

            lines.append(
                text["legacy_intro"]
                % (
                    statement,
                    text["legacy_label"],
                    text["source_human"],
                    status,
                )
            )

            for clause in nested:

                lines.append(
                    text["legacy_rule"]
                    % (
                        clause["text"],
                        role_display(clause["role"], lang),
                    )
                )

        else:

            lines.append(
                text["item"]
                % (statement, text["source_human"], status)
            )

        reported.append({

            "candidate_id": entry.get("candidate_id"),
            "statement": statement,
            "provenance": entry.get("provenance"),
            "status": entry.get("status"),
            "knowledge_class": entry.get("knowledge_class"),
            "clause_role": role,
            "rules": [clause["text"] for clause in nested],
        })

    # SUBJECT_SCOPE_01 — the scope of this answer is stated up front, so
    # an omission can never look like the whole story.
    if omitted:

        lines.insert(1, text["omitted"] % omitted)

    lines.append(text["uncertainty"])

    lines.append(text["not_taught"])

    return {

        "contract": "TeachingGroundedAnswerV1",
        "version": "1.0",

        "status": "success",

        "language": lang,

        "space_topic": space_topic,

        "source": "TEACHING_CANDIDATE_STORE",

        "provenance": "HUMAN_TEACHER",

        "recorded": reported,

        # SUBJECT_SCOPE_01 — additive: how many recorded items were left
        # out because they are about a different space.
        "subject_scope": "ASKED_SPACE_ONLY",
        "omitted_items": omitted,

        "result": "\n".join(lines),

        # A grounded answer is a READ. Nothing is created or learned.
        "is_knowledge": False,
        "is_action": False,
        "candidate_created": False,
        "learned_anything": False,
        "stored_teaching": False,
        "permanent_learning_implemented": False,
        "routed_to_execute": False,
        "llm_used": False,
        "network_used": False,
        "render_requested": False,
        "comfy_invoked": False,
    }


# ----------------------------------------------------------
# ACKNOWLEDGEMENT (after a teaching / correction statement)
# ----------------------------------------------------------
ACK_PHRASES = {

    "fa": {

        "understood": "\u0641\u0647\u0645\u06cc\u062f\u0645.",

        "recorded": (
            "\u0627\u06cc\u0646 \u0646\u06a9\u062a\u0647 \u0631\u0627 "
            "\u0641\u0642\u0637 \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 "
            "\u00ab\u062f\u0631\u06cc\u0627\u0641\u062a\u200c\u0634\u062f\u0647\u00bb "
            "\u062b\u0628\u062a \u06a9\u0631\u062f\u0645."
        ),

        "not_learned": (
            "\u062a\u0627 \u062a\u0623\u06cc\u06cc\u062f \u0634\u0645\u0627 "
            "\u0647\u0646\u0648\u0632 \u0628\u0647 \u062f\u0627\u0646\u0634 "
            "\u062f\u0627\u0626\u0645\u06cc \u062a\u0628\u062f\u06cc\u0644 "
            "\u0646\u0634\u062f\u0647 \u0627\u0633\u062a."
        ),

        "correction": (
            "\u0645\u062a\u0648\u062c\u0647 \u0634\u062f\u0645 \u06a9\u0647 "
            "\u0627\u06cc\u0646 \u06cc\u06a9 \u0627\u0635\u0644\u0627\u062d "
            "\u0627\u0633\u062a."
        ),

        "ask": (
            "\u0647\u0631 \u0648\u0642\u062a \u062e\u0648\u0627\u0633\u062a\u06cc\u062f "
            "\u0628\u067e\u0631\u0633\u06cc\u062f \u0686\u0647 "
            "\u0641\u0647\u0645\u06cc\u062f\u0645."
        ),

        # PHASE 09 — learning taxonomy line
        "taxonomy": (
            "\u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc: %s "
            "\u2014 \u062f\u0627\u0645\u0646\u0647: %s"
        ),

        "rejected": (
            "\u0627\u06cc\u0646 \u062c\u0645\u0644\u0647 \u0647\u06cc\u0686 "
            "\u0627\u0637\u0644\u0627\u0639\u0627\u062a "
            "\u0645\u0639\u0645\u0627\u0631\u06cc \u0634\u0646\u0627\u0633\u0627\u06cc\u06cc\u200c\u0634\u062f\u0647\u200c\u0627\u06cc "
            "\u0646\u062f\u0627\u0634\u062a\u060c \u067e\u0633 \u0686\u06cc\u0632\u06cc "
            "\u062b\u0628\u062a \u0646\u06a9\u0631\u062f\u0645."
        ),

        # CLAUSE_ANALYSIS_01 — a message that carried SEVERAL rules
        "clause_header": (
            "\u0627\u06cc\u0646 \u067e\u06cc\u0627\u0645 \u0631\u0627 "
            "\u0628\u0647 %s \u0646\u06a9\u062a\u0647\u0654 \u062c\u062f\u0627 "
            "\u062a\u0642\u0633\u06cc\u0645 \u06a9\u0631\u062f\u0645:"
        ),

        "clause_item": (
            "\u2022 %s\n  \u0646\u0648\u0639: %s"
        ),

        "clause_rationale": (
            "  \u062f\u0644\u06cc\u0644 \u0634\u0645\u0627: %s"
        ),

        "recorded_many": (
            "\u0627\u06cc\u0646 \u0646\u06a9\u062a\u0647\u200c\u0647\u0627 "
            "\u0631\u0627 \u0641\u0642\u0637 \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 "
            "\u00ab\u062f\u0631\u06cc\u0627\u0641\u062a\u200c\u0634\u062f\u0647\u00bb "
            "\u062b\u0628\u062a \u06a9\u0631\u062f\u0645."
        ),
    },

    "en": {

        "understood": "Understood.",

        "recorded": (
            "I recorded this only as an observation."
        ),

        "not_learned": (
            "It has NOT become permanent knowledge yet \u2014 that "
            "requires your confirmation."
        ),

        "correction": "I can see this is a correction.",

        "ask": "Ask me any time what I understood.",

        # PHASE 09 — learning taxonomy line
        "taxonomy": "Class: %s \u2014 Scope: %s",

        "rejected": (
            "That statement carried no recognisable architectural "
            "information, so I recorded nothing."
        ),

        # CLAUSE_ANALYSIS_01 — a message that carried SEVERAL rules
        "clause_header": (
            "I split this message into %s separate points:"
        ),

        "clause_item": "\u2022 %s\n  Type: %s",

        "clause_rationale": "  Your reason: %s",

        "recorded_many": (
            "I recorded these points as RECEIVED only."
        ),
    },
}


_PERSIAN_DIGITS = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"


def _count_display(value, language):

    """3 -> "۳" in Persian, "3" in English."""

    if not str(language).startswith("fa"):

        return str(value)

    return "".join(_PERSIAN_DIGITS[int(d)] for d in str(value))


def _as_candidate_dicts(candidates):

    """Normalise a mixed list of candidates/dicts, dropping the junk."""

    normalised = []

    for entry in candidates or []:

        if isinstance(entry, dict):

            normalised.append(entry)

            continue

        to_dict = getattr(entry, "to_dict", None)

        if callable(to_dict):

            normalised.append(to_dict())

    return normalised


def build_acknowledgement(
    turn_kind,
    meaning=None,
    language="en",
    candidate=None,
    candidates=None,
):

    """Short honest acknowledgement after a teaching/correction turn.

    CLAUSE_ANALYSIS_01 — when the message carried SEVERAL knowledge
    clauses, every one of them is listed with its role and the teacher's
    own reason, so the teacher can see exactly WHICH parts were taken
    (and that the explanations were kept as reasons, not as facts).
    """

    lang = "fa" if str(language or "").startswith("fa") else "en"

    text = ACK_PHRASES[lang]

    many = _as_candidate_dicts(candidates)

    if len(many) >= 2:

        lines = [text["understood"]]

        if turn_kind == "CORRECTION":

            lines.append(text["correction"])

        lines.append(
            text["clause_header"] % _count_display(len(many), lang)
        )

        for entry in many:

            if entry.get("status") == "rejected":

                continue

            lines.append(
                text["clause_item"]
                % (
                    entry.get("raw_statement") or "",
                    role_display(entry.get("clause_role"), lang),
                )
            )

            if entry.get("rationale"):

                lines.append(
                    text["clause_rationale"] % entry.get("rationale")
                )

        lines.append(text["recorded_many"])

        lines.append(text["not_learned"])

        lines.append(text["ask"])

        return "\n".join(lines)

    # TEACHING SESSION STATE FIX — the candidate is a `TeachingCandidate`
    # OBJECT whenever it was NOT persisted (a bare session id with no real
    # project on disk). Calling `.get()` on it raised:
    #   AttributeError: 'TeachingCandidate' object has no attribute 'get'
    # Production always uses a real project, so `store.record()` returns a
    # dict and this branch never ran — an invisible crash. Normalise once,
    # here, so every downstream `.get()` is safe.
    if candidate is not None and not isinstance(candidate, dict):

        _to_dict = getattr(candidate, "to_dict", None)

        candidate = _to_dict() if callable(_to_dict) else None

    lines = [text["understood"]]

    if turn_kind == "CORRECTION":

        lines.append(text["correction"])

    if candidate and candidate.get("status") == "rejected":

        lines.append(text["rejected"])

        return "\n".join(lines)

    if meaning:

        statement = restate(meaning, lang)

        if statement:

            lines.append(statement)

        # PHASE 09 — show the learning taxonomy so the user can see HOW
        # the statement was filed (and that it is not yet knowledge).
        knowledge_class = meaning.get("knowledge_class")

        scope = meaning.get("scope")

        if knowledge_class and scope:

            lines.append(
                text["taxonomy"]
                % (
                    knowledge_class_display(knowledge_class, lang),
                    scope_display(scope, lang),
                )
            )

    lines.append(text["recorded"])

    lines.append(text["not_learned"])

    lines.append(text["ask"])

    return "\n".join(lines)
