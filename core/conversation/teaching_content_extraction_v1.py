# ==========================================================
# ArchitectOS Teaching Content Extraction v1
#
# TEACHING CONTENT CAPTURE V1
#
# THE DEFECT (real manual browser test, verified from the pipeline)
#
# The teacher announces the teaching intent AND supplies the actual
# content in the SAME turn:
#
#   "میخوام یه نکته آموزشی رو بهت بگم اگه آشپزخونه به حیاط خلوت
#    نزدیکتر باشه برای طراحیمون بهتره"
#   ("I want to tell you a teaching note: if the kitchen is closer to
#    the lightwell, it is better for our design.")
#
# `turn_semantics_v1` classifies it OFFER_TO_TEACH — rung 0 of the
# precedence ladder — and returns EARLY, before the TEACHING_STATEMENT
# rung that this sentence ALSO satisfies (measured: `normative=True`).
# OFFER_TO_TEACH therefore carries `may_produce_candidate=False`, the
# candidate block in `teaching_foundation_v1.observe_turn` is skipped
# entirely, and the assistant asks for content the user has ALREADY
# given.
#
# THIS MODULE separates the two shapes the brief distinguishes:
#
#   A) PURE TEACHING OFFER
#      "میخوام یه نکته بهت یاد بدم"
#      -> no proposition; the elicitation question is correct.
#
#   B) TEACHING OFFER + ACTUAL CONTENT
#      "میخوام یه نکته بهت یاد بدم: آشپزخونه بهتره نزدیک حیاط خلوت باشه"
#      -> the content IS a proposition and must be captured immediately.
#
# It does NOT change the classifier, the boundary or the precedence
# ladder. It only answers one question, deterministically:
#
#   "Given a turn the classifier ALREADY called a teaching offer, does
#    the SAME turn also carry a real proposition — and if so, what is
#    the remaining content?"
#
# Deterministic: no LLM, no network, no storage, no candidate.
#
# `match_form` STRIPS punctuation, so the preamble markers below are
# written in MATCH FORM and the raw text is folded before matching.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form


CONTRACT = "TeachingContentExtractionV1"
VERSION = "1.0"


# ----------------------------------------------------------
# 1. TEACHING PREAMBLES (match form)
#
#    Each entry is a PREFIX the speaker uses to announce the
#    teaching. The content, when present, follows it directly —
#    with or without a colon, because natural Persian often joins
#    both clauses with no punctuation at all.
#
#    WRITTEN IN MATCH FORM — and MEASURED, not assumed.
#    `turn_semantics_v1.match_form` folds the ZWNJ to a space but
#    PRESERVES the alef-madda (`آ`). A marker written with `ا` in place
#    of `آ` can therefore NEVER match: `"اموزشی" in "یه نکته آموزشی دارم"`
#    is False. Every marker below was printed through `match_form`
#    first and copied from that output.
# ----------------------------------------------------------

TEACHING_PREAMBLES_MATCH_FORM = (
    # "I want to tell you a teaching note / a note"
    "میخوام یه نکته آموزشی رو بهت بگم",
    "میخوام یه نکته آموزشی بهت بگم",
    "میخوام یه نکته اموزشی رو بهت بگم",
    "میخوام یه نکته رو بهت بگم",
    "میخوام یه نکته بهت بگم",
    "میخوام یه نکته آموزشی رو بگم",
    "میخوام یه نکته بگم",
    # "I want to teach you a note / something"
    "میخوام یه نکته آموزشی رو بهت یاد بدم",
    "میخوام یه نکته بهت یاد بدم",
    "میخوام یه نکته رو بهت یاد بدم",
    "میخوام یه چیزی بهت یاد بدم",
    "میخوام یه نکته یادت بدم",
    "میخوام یه نکته آموزشت بدم",
    # "I have a teaching note"
    "یه نکته آموزشی دارم",
    "یه نکته اموزشی دارم",
    "یه نکته دارم",
    "یه چیزی دارم که بهت بگم",
    # "learn this" / "remember this"
    "این رو یاد بگیر",
    "اینو یاد بگیر",
    "این رو یادت باشه",
    "اینو یادت باشه",
    # "I want to teach you something"
    "یه چیزی میخوام بهت آموزش بدم",
    "یه چیزی میخوام بهت اموزش بدم",
    "میخوام بهت آموزش بدم",
    "میخوام بهت اموزش بدم",
    "میخوام بهت یاد بدم",
    # "for future designs, remember ..."
    "برای طراحی های بعدی یادت باشه",
    "برای طراحی های بعدی یادت باسه",
    "برای طراحی بعدی یادت باشه",
    "برای پروژه های بعدی یادت باشه",
    "برای طراحی های بعدی یاد بگیر",
    # "remember ..."
    "یادت باشه",
    # English
    "i want to tell you a note",
    "i want to teach you a note",
    "i have a teaching note",
    "let me teach you",
    "remember this",
)

# Longest first, so the LONGEST matching preamble is removed as ONE
# phrase instead of leaving a fragment behind.
TEACHING_PREAMBLES_BY_LENGTH = tuple(
    sorted(TEACHING_PREAMBLES_MATCH_FORM, key=lambda marker: -len(marker))
)


# ----------------------------------------------------------
# 2. SEPARATORS a preamble may be followed by
# ----------------------------------------------------------

SEPARATORS = (":", "،", ",", "؛", ";", "-", "—", "که")


# ----------------------------------------------------------
# 3. THE PROPOSITION TEST
#
#    After the preamble is removed, the remainder must be a REAL
#    proposition — not an echo of the offer itself.
#
#    A remainder is a proposition when it is at least
#    `MIN_CONTENT_TOKENS` tokens AND carries at least one
#    architectural / normative signal. This is what keeps the PURE
#    offers out: their remainder is empty or a bare object phrase
#    ("یه نکته بهت یاد بدم" -> nothing left).
# ----------------------------------------------------------

MIN_CONTENT_TOKENS = 3

# A proposition either states a relationship / requirement or names a
# space. These are the SAME families the frozen classifier already
# uses; duplicated here as a LOCAL list so no frozen module is edited.
PROPOSITION_MARKERS_MATCH_FORM = (
    # normative / preference
    "بهتره", "بهتر است", "بهتر باشد", "باید", "نباید", "لازمه",
    "لازم است", "لازم داره", "لازم دارد", "نیاز داره", "نیاز دارد",
    "ضروریه", "حتما", "مناسب تره",
    # relations
    "نزدیک", "دور", "کنار", "مجاور", "چسبیده", "جدا", "رو به",
    "مشرف", "داخل", "خارج", "بین", "وسط", "زیر", "پشت", "جلوی",
    "بالای", "قرار داره", "قرار دارد", "قرار بگیره", "باشه",
    # negative existence
    "نباشه", "نباشد", "نداشته باشه", "نداشته باشد",
    # english
    "should", "must", "better", "near", "close to", "away from",
    "next to", "adjacent",
)


# ----------------------------------------------------------
# 4. CONTENT EXTRACTION
# ----------------------------------------------------------


def _strip_leading_separators(text):

    """Drop leading separators/whitespace from a remainder."""

    remaining = text.strip()

    changed = True

    while changed and remaining:

        changed = False

        for separator in SEPARATORS:

            if remaining.startswith(separator):

                remaining = remaining[len(separator):].strip()

                changed = True

                break

    return remaining


def _match_offset(form, marker):

    """Character offset of `marker` inside `form`, or -1.

    `match_form` preserves length for the transformations that matter
    here (ZWNJ -> space is 1:1; the leading alef-normalisations the
    classifier applies are length-preserving too), so an index into
    the folded string is also a valid index into the raw string. This
    helper exists so the offset is derived ONCE and never guessed by
    re-searching a truncated fragment.
    """

    return form.find(marker)


def content_after_preamble(text):

    """The teaching content that FOLLOWS a teaching preamble, or None.

    Returns the remaining proposition text (in its ORIGINAL spelling,
    so the candidate keeps the teacher's own words) when the turn
    carries real content; None when it is a PURE OFFER.

    The classifier is never consulted and never modified.
    """

    raw = str(text or "").strip()

    if not raw:

        return None

    form = match_form(raw)

    if len(form) != len(raw):

        # A fold changed the length. Extraction still works (the
        # folded remainder is the teacher's wording modulo the fold),
        # but the raw-offset optimisation below is skipped.
        length_preserving = False

    else:

        length_preserving = True

    # ---- locate the preamble ----
    #
    # The preamble is a PREFIX of the utterance. The LONGEST match
    # wins, so "میخوام یه نکته اموزشی رو بهت بگم" is removed whole and
    # "رو بهت بگم" is never left behind.

    matched = None
    matched_index = -1

    for marker in TEACHING_PREAMBLES_BY_LENGTH:

        if form.startswith(marker):

            matched = marker
            matched_index = 0

            break

    if matched is None:

        # A preamble may follow a SHORT lead-in ("خب"، "راستش").
        # Only the FIRST few characters are searched, so a preamble
        # mentioned LATER in a sentence can never swallow the
        # sentence's start.
        for marker in TEACHING_PREAMBLES_BY_LENGTH:

            index = _match_offset(form, marker)

            if 0 <= index <= 24:

                matched = marker
                matched_index = index

                break

        if matched is None:

            return None

    # ---- the remainder, in the teacher's OWN spelling ----

    tail_form = form[matched_index + len(matched):]

    if not _is_proposition(tail_form):

        return None

    if length_preserving and matched_index >= 0:

        raw_tail = raw[matched_index + len(matched):]

    else:

        raw_tail = tail_form

    raw_tail = _strip_leading_separators(raw_tail)

    if not raw_tail:

        # The fold shifted the boundary; use the folded remainder.
        raw_tail = _strip_leading_separators(tail_form)

    return raw_tail or None


def _is_proposition(form):

    """True when a remainder is a real proposition, not an echo."""

    if not form:

        return False

    tokens = [token for token in form.split(" ") if token]

    if len(tokens) < MIN_CONTENT_TOKENS:

        return False

    return any(
        marker in form for marker in PROPOSITION_MARKERS_MATCH_FORM
    )


def has_embedded_content(text):

    """True when the teaching offer carries actual content."""

    return content_after_preamble(text) is not None


# ----------------------------------------------------------
# 5. DIAGNOSTIC SURFACE (used by the acceptance runner)
# ----------------------------------------------------------


def describe(text):

    content = content_after_preamble(text)

    return {

        "contract": CONTRACT,

        "version": VERSION,

        "has_content": content is not None,

        "content": content,

        "preamble_found": any(
            match_form(text).startswith(marker)
            or 0 <= match_form(text).find(marker) <= 24
            for marker in TEACHING_PREAMBLES_MATCH_FORM
        ),

        "fold_length_preserved": len(match_form(text)) == len(str(text or "").strip()),

    }
