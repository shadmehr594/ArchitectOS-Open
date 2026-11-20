# -*- coding: utf-8 -*-
"""ARCHITECTOS — NEGATION SCOPE V1.

GENERAL_CONVERSATION_CORRECTION_V1 — "is this word AFFIRMED, or is it inside a
negation?"

WHY THIS EXISTS
---------------
Two shared interpretation layers decided the SUBJECT of a turn by looking for a
subject word anywhere in the text:

* ``ConversationIntentBoundaryV1._subject()``  -> architecture vs general
* ``ConversationDomainV1.classify_domain()``   -> the conversation domain

Neither consulted negation, so a turn that REJECTS a subject was classified AS
that subject:

    "معمایی گفتم نه معماری"   ->  domain = architecture

The user said "mystery, NOT architecture" and the system answered as if
architecture had been requested — the inversion this module prevents.

WHAT IT IS
----------
A tiny, dependency-free predicate over text. It knows nothing about
architecture, mystery, or any particular vocabulary: callers pass their own
marker list, and the helper reports whether at least one occurrence sits
OUTSIDE a negation.

It never rewrites the user's text, stores anything, or classifies an intent.

NEGATION SCOPE
--------------
A marker is treated as NEGATED when

* a standalone negation word appears earlier in the same SENTENCE
  ("... گفتم نه معماری"),
* a negated copula immediately follows it ("معماری نبود"), or
* a DISCOURSE rejection ("نه، …" / "no, …") precedes it AND the clause's own
  predicate is negated ("نه، معماری رو نمی‌خوام" — architecture is unwanted).

Sentence boundaries are punctuation (. ؟ ! ؛ , and newline). The comma matters:
Persian "نه، معماری رو توضیح بده" means "no, explain architecture" — a discourse
"نه", not a rejection of the term that follows it — so it counts as a rejection
only when the following clause negates its own predicate. Negation words are
matched as WHOLE TOKENS, so "نه" inside "خانه" is not a negation.
"""

from __future__ import annotations

import re

from typing import Any, Iterable


CONTRACT = "NegationScopeV1"
VERSION = "1.0"


#: Contrastive markers that introduce the user's AFFIRMED replacement
#: ("not X, but Y" / "نه X بلکه Y"). The negated requirement ends here, so a
#: prohibition and a material rejection both stop naming the replacement.
#: These are DISCOURSE connectors, not domain vocabulary.
REPLACEMENT_MARKERS = (
    "but", "rather",
    "\u0627\u0645\u0627",          # اما
    "\u0648\u0644\u06cc",          # ولی
    "\u0628\u0644\u06a9\u0647",    # بلکه
)

_REPLACEMENT_MARKER_RE = re.compile(
    r"\b(?:but|rather)\b"
    + "|"
    + "|".join(
        marker for marker in REPLACEMENT_MARKERS if not marker.isascii()
    ),
    re.IGNORECASE,
)


def trim_replacement_span(span: Any) -> str:
    """Cut an extracted rejected span at the affirmed replacement.

    ``rejected_span()`` returns the whole sentence tail after the last
    negation word, so "not a three-storey building, but a four-storey one"
    yields "a three-storey building, but a four-storey one". Everything from
    the contrastive marker onwards is what the user ASKED FOR, so it must not
    be carried as a prohibition or as a rejected material.

    The input is a span this module already produced; no text is re-parsed.
    """

    text = str(span or "")

    match = _REPLACEMENT_MARKER_RE.search(text)

    if match:

        head = text[:match.start()].strip(" \u060c,;:\u061b")

        if head:

            return head

    return text


def negated_requirement(text: Any) -> str:
    """The negated requirement of ``text``, without the affirmed replacement."""

    return trim_replacement_span(rejected_span(text))


#: Persian TRAILING prohibition verbs. Persian is subject-object-verb, so
#: "کاربری تجاری، استخر و تراس اضافه نکن" puts the prohibition AFTER the
#: objects it rejects. `_negated_at` only looks at tokens BEFORE a marker (plus
#: a negated copula after it), so this shape was invisible to the shared layer:
#: a negated commercial use, pool and terrace were read as AFFIRMED requests.
#:
#: VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — this is an ADDITIVE definition. No
#: existing function changes behaviour, so no unrelated consumer is affected.
#:
#: IMPERATIVE prohibitions ("اضافه نکن" = do not add) take an object LIST, and
#: Persian joins that list with commas: «تجاری، استخر و تراس اضافه نکن». Their
#: span therefore runs back to the previous STRONG separator only.
_IMPERATIVE_PROHIBITION_MARKERS = (
    "نکن", "نکنید", "نکنیم", "نکنه", "نکنن", "نکنند",
    "نخواه", "نخواهید",
)

#: NEGATIVE-COPULA prohibitions ("نداشته باشد" = must not have) take a CLAUSE,
#: and there the comma separates clauses: «ساختمان سه طبقه مسکونی، کاربری
#: تجاری نداشته باشد» prohibits the commercial use only, not the residential
#: subject in front of the comma. Their span keeps the comma boundary.
_COPULA_PROHIBITION_MARKERS = (
    "نداشته باشد", "نداشته باشه", "نداشته باشید",
    "نباشد", "نباشه", "نباشند",
    "نشود", "نشه",
)

TRAILING_PROHIBITION_MARKERS = (
    _IMPERATIVE_PROHIBITION_MARKERS + _COPULA_PROHIBITION_MARKERS
)

#: Hard separators only — the comma is NOT one of them here, because inside an
#: imperative prohibition it separates the rejected objects.
_STRONG_SEPARATORS = ".\u061f!\u061b?;\n"

# English puts the prohibition BEFORE its comma-separated object list.  These
# are grammar markers, not architectural vocabulary.  Keeping their spans in
# the shared negation owner lets terminology extraction and render constraints
# consume the same evidence instead of interpreting ``Avoid A, B, C`` twice.
_LEADING_PROHIBITION_RE = re.compile(
    r"\b(?:avoid|exclude|do\s+not\s+include)\b",
    re.IGNORECASE,
)

# In Persian purpose/result clauses, the negative copula applies only after
# ``تا``: «دوربین ... قرار بگیرد تا ساختمان خارج نشود».  Without this boundary
# the positive camera instruction was swallowed by the trailing prohibition.
_PURPOSE_BOUNDARY_RE = re.compile(r"(?<!\w)تا(?!\w)")

#: A REQUEST verb opens a new instruction. When one appears between the strong
#: separator and the prohibition verb, the prohibition's object list starts
#: AFTER it: «نمای آجری طراحی کن، نمای سنگی نکن» asks for brick and prohibits
#: stone — the brick must not be swallowed by the wide span. This is a BOUNDARY
#: vocabulary only (the same handful of imperative request forms the project
#: already uses elsewhere), not a parser and not a second intent engine.
_REQUEST_MARKERS = (
    "طراحی کن", "طراحی کنید", "بساز", "بسازید", "ایجاد کن", "ایجاد کنید",
    "درست کن", "درست کنید", "بزن", "اضافه کن", "اضافه کنید",
    "design", "build", "create", "generate", "add",
)


def _request_boundary(text: str, start: int, end: int) -> int:
    """The offset after the last REQUEST verb inside ``[start, end)``."""

    lowered = text.lower()

    boundary = start

    for marker in _REQUEST_MARKERS:

        position = lowered.rfind(marker.lower(), start, end)

        if position >= 0 and position + len(marker) > boundary:

            boundary = position + len(marker)

    return boundary


def _strong_clause_bounds(text: str, index: int) -> tuple:
    """The (start, end) of the strong-separator clause containing ``index``."""

    start = 0

    for separator in _STRONG_SEPARATORS:

        found = text.rfind(separator, 0, index)

        if found + 1 > start:

            start = found + 1

    end = len(text)

    for separator in _STRONG_SEPARATORS:

        found = text.find(separator, index)

        if found >= 0 and found < end:

            end = found

    return start, end


def trailing_prohibition_spans(text: Any) -> list:
    """The clause spans governed by a TRAILING Persian prohibition verb.

    Returns a list of ``(start, end)`` offsets. An IMPERATIVE prohibition
    ("اضافه نکن") spans back to the previous strong separator so its
    comma-separated object list is fully covered; a NEGATIVE-COPULA prohibition
    ("نداشته باشد") keeps the comma boundary so the subject in front of the
    comma is not swallowed.
    """

    if not isinstance(text, str) or not text:

        return []

    lowered = text.lower()

    spans = []

    for markers, comma_is_boundary in (
        (_IMPERATIVE_PROHIBITION_MARKERS, False),
        (_COPULA_PROHIBITION_MARKERS, True),
    ):

        for marker in markers:

            position = lowered.find(marker)

            while position >= 0:

                start, end = _strong_clause_bounds(text, position)

                if comma_is_boundary:

                    start = _sentence_start(text, position)

                    # A final negative result after «تا» does not negate the
                    # affirmative action before it.  Keep only the result
                    # clause inside the prohibition span.
                    purpose = None

                    for match in _PURPOSE_BOUNDARY_RE.finditer(
                        text, start, position
                    ):

                        purpose = match

                    if purpose is not None:

                        start = purpose.end()

                else:

                    start = _request_boundary(text, start, position)

                spans.append((start, end))

                position = lowered.find(marker, position + len(marker))

    return spans


def leading_prohibition_spans(text: Any) -> list:
    """Object-list spans governed by a leading English prohibition.

    ``Avoid brick, daylight and cropped towers.`` returns the span after
    ``Avoid`` through the sentence boundary.  An affirmative replacement
    introduced by ``but`` / ``rather`` is outside the span.
    """

    if not isinstance(text, str) or not text:

        return []

    spans = []

    for match in _LEADING_PROHIBITION_RE.finditer(text):

        _clause_start, end = _strong_clause_bounds(text, match.end())

        replacement = _REPLACEMENT_MARKER_RE.search(
            text, match.end(), end
        )

        if replacement:

            end = replacement.start()

        start = match.end()

        while start < end and text[start] in " \t:\u060c,;\u061b":

            start += 1

        if start < end:

            spans.append((start, end))

    return spans


def prohibition_spans(text: Any) -> list:
    """All shared leading-English and trailing-Persian prohibition spans."""

    return trailing_prohibition_spans(text) + leading_prohibition_spans(text)


def is_prohibited(text: Any, marker: Any) -> bool:
    """True when EVERY occurrence of ``marker`` sits in a prohibition clause.

    An occurrence outside a prohibition clause means the term is still the
    user's requirement ("ویلا با استخر و تراس طراحی کن، استخر اضافه نکن"
    keeps the affirmed mention), so only a fully-prohibited term is reported.
    """

    if not isinstance(text, str) or not marker:

        return False

    spans = trailing_prohibition_spans(text)

    if not spans:

        return False

    lowered = text.lower()

    needle = str(marker).lower()

    position = lowered.find(needle)

    if position < 0:

        return False

    seen = False

    while position >= 0:

        seen = True

        if not any(low <= position < high for low, high in spans):

            return False

        position = lowered.find(needle, position + len(needle))

    return seen


# Standalone negation words (Persian + English). Matched as whole tokens.
NEGATION_TOKENS = frozenset((
    "\u0646\u0647",          # نه   (no / not)
    "\u0646\u06cc\u0633\u062a",   # نیست (is not)
    "\u0646\u0628\u0648\u062f",   # نبود (was not)
    "\u0628\u062f\u0648\u0646",   # بدون (without)
    "\u0647\u06cc\u0686",    # هیچ (none/any)
    # R1_FLOOR_COUNT_SEMANTICS_NEGATION_V1 — the PRE-positional prohibitive
    # "must not". It sits BEFORE the term it forbids ("ساختمان نباید چهار
    # طبقه باشد"), so it belongs in this lexicon rather than NEGATED_AFTER.
    # Without it the forbidden count was published as a hard requirement.
    "\u0646\u0628\u0627\u06cc\u062f",   # نباید (must not)
    "not", "no", "without", "isn't", "isnt", "aren't", "arent",
))

# Negated copulas that FOLLOW the term they negate ("معماری نبود").
NEGATED_AFTER = (
    "\u0646\u0628\u0648\u062f",        # نبود
    "\u0646\u06cc\u0633\u062a",        # نیست
    "\u0646\u06cc\u0633\u062a\u0646\u062f",  # نیستند
    "\u0646\u06cc\u0633\u062a\u0645",  # نیستم
    # R1_FLOOR_COUNT_SEMANTICS_NEGATION_V1 — negative SUBJUNCTIVE, colloquial
    # and "must not have" copulas. "چهار طبقه نباشد" = "it should NOT be four
    # storeys". These are the Persian prohibitive forms that follow their
    # subject, and they were absent from THIS surface, so `is_affirmed()`
    # returned True and the forbidden count became an exact positive
    # floor-count hard constraint — the user's instruction was inverted.
    #
    # The same owner already lists every one of these in
    # `_COPULA_PROHIBITION_MARKERS` (the trailing-prohibition SPAN surface).
    # The two surfaces disagreed: a prohibition the span detector could see
    # was invisible to `is_affirmed()`. This block makes them agree; it names
    # no domain vocabulary.
    "\u0646\u0628\u0627\u0634\u062f",        # نباشد   (should not be)
    "\u0646\u0628\u0627\u0634\u0647",        # نباشه   (colloquial)
    "\u0646\u0628\u0627\u0634\u0646\u062f",  # نباشند  (should not be, pl.)
    "\u0646\u0634\u0648\u062f",              # نشود    (should not become)
    "\u0646\u0634\u0647",                    # نشه     (colloquial)
    "\u0646\u0645\u06cc\u200c\u0634\u0648\u062f",  # نمی‌شود (does not become)
    "\u0646\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",    # نداشته باشد
    "\u0646\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u0647",    # نداشته باشه
    "\u0646\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u06cc\u062f",  # نداشته باشید
    "\u0646\u062e\u0648\u0627\u0647\u062f \u0628\u0648\u062f",  # نخواهد بود
)

# Negated PREDICATE forms — "I do not want / do not like <X>".
#
# This is a GRAMMATICAL lexicon (negation morphology), never a domain
# vocabulary: it names no subject, so a caller can use it for any topic.
# It exists so that a DISCOURSE rejection ("نه، معماری رو نمی‌خوام" = "no, I
# don't want architecture") is recognised as a rejection, while a plain
# preference statement without that rejection opener ("من معماری دوست
# ندارم") still keeps its subject mention.
NEGATED_PREDICATES = (
    "نمی‌خوام", "نمیخوام",           # I don't want
    "نمی‌خواهم", "نمیخواهم",         # I don't want (formal)
    "نمی‌خوایم", "نمیخوایم",         # we don't want
    "نمی‌خواهیم", "نمیخواهیم",       # we don't want (formal)
    "نمی‌خواستم", "نمیخواستم",       # I did not want
    "نمی‌خواد", "نمیخواد",           # he/she doesn't want
    "نمی‌خوان", "نمیخوان",           # they don't want
    "نمی‌پسندم", "نمیپسندم",         # I don't like
    "دوست ندارم", "دوست نداریم",     # I/we don't like
    "علاقه ندارم",                   # I'm not interested
    "no thanks", "do not want", "don't want",
)

# Hard sentence boundaries. The comma IS one: in Persian "نه، معماری رو توضیح
# بده" means "no, explain architecture" — the "نه" is a discourse marker, not a
# rejection of the term that follows it. Only an unseparated "نه معماری" is a
# contrastive rejection, which is the shape this module must catch.
_SENTENCE_SEPARATORS = ".\u061f!\u061b,?;:\u060c\n"   # . ؟ ! ؛ , ? ; : ، newline

# How far after a marker to look for a negated copula.
#
# R1_FLOOR_COUNT_SEMANTICS_NEGATION_V1 — widened from 8 to 16 so the window
# can actually contain the longest entry in NEGATED_AFTER ("نداشته باشید",
# 13 characters) plus the separating space. A window shorter than the longest
# lexicon entry silently disables that entry, which is how "چهار طبقه نخواهد
# بود" and "چهار طبقه نداشته باشد" escaped the gate. This constant must always
# be >= the longest entry in NEGATED_AFTER plus one separator; the invariant
# is asserted by tests/test_r1_floor_count_semantics_negation_v1.py.
_AFTER_WINDOW = 16


def _sentence_start(text: str, index: int) -> int:
    start = 0
    for sep in _SENTENCE_SEPARATORS:
        pos = text.rfind(sep, 0, index)
        if pos + 1 > start:
            start = pos + 1
    return start


def _clean_token(token: str) -> str:
    """Strip surrounding punctuation so a token can be compared to a marker."""

    return token.strip().strip("\u060c\u061b,;:.\u061f!?\u00ab\u00bb")


def _comma_follows(text: str, token: str, end: int) -> bool:
    """True when the token is immediately followed by a comma.

    The comma may be glued to the token ("نه،") or stand as its own character
    after whitespace ("نه ،"). Either way it marks a DISCOURSE "no", not a
    contrastive rejection of the next term.
    """

    word = _clean_token(token)

    offset = token.find(word)

    remainder = token[offset + len(word):] if offset >= 0 else ""

    following = (remainder + text[end:]).lstrip()

    return following[:1] in ("\u060c", ",")


def _discourse_rejection_before(text: str, index: int) -> bool:
    """True when the text before ``index`` opens with a rejection + comma."""

    for token, _start, end in _tokens_with_spans(text[:index]):

        word = _clean_token(token)

        if word.lower() not in NEGATION_TOKENS:

            continue

        if _comma_follows(text, token, end):

            return True

    return False


def _has_negated_predicate(text: str, from_index: int) -> bool:
    """True when the clause starting at ``from_index`` negates its predicate.

    Spaces and ZWNJ are removed before matching, because the same clause can
    arrive folded ("نمی خوام" after a ZWNJ fold) or glued ("نمی‌خوام").
    """

    tail = text[from_index:]

    for separator in _SENTENCE_SEPARATORS:

        position = tail.find(separator)

        if position >= 0:

            tail = tail[:position]

    flat = tail.replace("\u200c", "").replace(" ", "")

    for predicate in NEGATED_PREDICATES:

        if predicate.replace("\u200c", "").replace(" ", "") in flat:

            return True

    return False


def _negated_at(text: str, index: int, length: int) -> bool:
    """Is the token at ``index`` inside a negation?"""

    before = text[_sentence_start(text, index):index]

    if before:

        tokens = before.replace("\u060c", " ").split()

        for token in tokens:

            # English negation words are stored lower-case, so the comparison
            # must fold case: "Not architecture" is a rejection too.
            if _clean_token(token).lower() in NEGATION_TOKENS:

                return True

    after = text[index + length:index + length + _AFTER_WINDOW]

    for negated in NEGATED_AFTER:

        if negated in after:

            return True

    # A DISCOURSE rejection ("نه، …" / "no, …") scopes over the clause that
    # follows it, and that clause's own predicate decides the polarity: a
    # negated predicate rejects the subject, a positive request keeps it.
    if _discourse_rejection_before(text, index) and _has_negated_predicate(
        text, index + length
    ):

        return True

    return False


def is_affirmed(text: Any, marker: str) -> bool:
    """True when ``marker`` occurs at least once OUTSIDE a negation."""

    if not isinstance(text, str) or not marker:

        return False

    start = 0

    while True:

        index = text.find(marker, start)

        if index < 0:

            return False

        if not _negated_at(text, index, len(marker)):

            return True

        start = index + len(marker)


def affirmed_hit(text: Any, markers: Iterable[str]) -> bool:
    """True when at least one marker is AFFIRMED (not negated).

    This is the drop-in replacement for a plain "does the text contain any of
    these words" test. A marker that appears ONLY inside a negation does not
    count, which is exactly what makes a contrastive correction work in both
    directions:

        "معمایی گفتم نه معماری"  -> architecture is NOT affirmed
        "معماری گفتم نه معمایی"  -> architecture IS affirmed
    """

    if not isinstance(text, str):

        return False

    for marker in markers or ():

        if is_affirmed(text, marker):

            return True

    return False


class NegationScopeV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    REWRITES_USER_TEXT = False
    STORES_ANYTHING = False
    CLASSIFIES_INTENT = False

    def affirmed(self, text: Any, markers: Iterable[str]) -> bool:
        return affirmed_hit(text, markers)

    def is_affirmed(self, text: Any, marker: str) -> bool:
        return is_affirmed(text, marker)

    def rejected(self, text: Any) -> str:
        return rejected_span(text)

    def is_contrastive(self, text: Any) -> bool:
        return has_contrastive_negation(text)


def _tokens_with_spans(text: str):
    """Yield (token, start, end) for the whole-token scan."""

    start = None

    for index, char in enumerate(text):

        if char.isspace():

            if start is not None:

                yield text[start:index], start, index

                start = None

        else:

            if start is None:

                start = index

    if start is not None:

        yield text[start:], start, len(text)


def _last_negation(text: str):
    """(start, end) of the LAST standalone negation word, or None.

    A negation word immediately followed by a comma is a DISCOURSE marker
    ("نه، …" = "no, …"): it answers the previous statement instead of rejecting
    the term after it, so it is not a contrastive negation and is skipped here.
    """

    found = None

    for token, start, end in _tokens_with_spans(text):

        cleaned = _clean_token(token)

        if cleaned.lower() not in NEGATION_TOKENS:

            continue

        if _comma_follows(text, token, end):

            continue

        found = (start, end)

    return found


def has_contrastive_negation(text: Any) -> bool:
    """True when a negation word is followed by the term it rejects.

    This is the "X, not Y" shape — the user is naming what they do NOT want.
    A bare "نه" with nothing after it is not contrastive.
    """

    if not isinstance(text, str) or not text:

        return False

    found = _last_negation(text)

    if found is None:

        return False

    return bool(rejected_span(text))


def rejected_span(text: Any, max_chars: int = 48) -> str:
    """The term the user is rejecting — the text AFTER the last negation word.

    The vocabulary-free extraction is what makes the correction reportable to
    the model without naming any domain word in production:

        "معمایی گفتم نه معماری"      -> "معماری"
        "نه، معماری رو نمی‌خوام"     -> "معماری رو نمی‌خوام"
        "معماری گفتم نه معمایی"      -> "معمایی"
        "I said mystery, not architecture" -> "architecture"
    """

    if not isinstance(text, str) or not text:

        return ""

    found = _last_negation(text)

    if found is None:

        return ""

    tail = text[found[1]:]

    tail = tail.lstrip(" \u060c\u061b,;:.\u061f!?\u00ab\u00bb")

    for separator in (".", "\u061f", "!", "\u061b", "?", ";", "\n"):

        position = tail.find(separator)

        if position > 0:

            tail = tail[:position]

    return tail.strip()[:max_chars]


negation_scope = NegationScopeV1()
