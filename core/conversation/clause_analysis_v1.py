# ==========================================================
# ArchitectOS Clause Analysis v1
#
# CLAUSE_ANALYSIS_01
#
# THE PROBLEM (user-reported, with their own session as evidence)
#
# The teacher writes one long Persian message that contains SEVERAL
# rules, their REASONS, and some conversational meta:
#
#   "یسری چیزها باید در نظر گرفت روی تخت محل معاشقه والدین هست پس تخت
#    باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه ، تخت
#    دور از پنجره باشه بهتره ، اتاق خواب ها باید دور از پذیرایی و
#    فضاهای نشیمن باشن چون اون فضاها فضاهای عمومی هستن ..."
#
# The teaching layer treated that WHOLE message as ONE statement and
# reduced it to a single (wrong) triple — "پنجره باید دور از اتاق خواب و
# نشیمن باشد" — losing three of the four rules and inverting the subject.
# The teacher's own words: "کل جملات رو میگیره ... کلی میگیره همه چیز
# رو" (it takes whole sentences; it takes everything coarsely).
#
# THIS MODULE is the missing analysis step. Deterministic: no LLM, no
# network, no storage, no candidate.
#
#   segment(text) -> [
#       {index, text, role, reason, connector, knowledge, rationale}
#   ]
#
# ROLES
#   RULE        a design rule ("تخت باید دور از پنجره باشد")
#   DEFINITION  a copular definition ("اتاق خواب مستر اتاق والدین است")
#   OBSERVATION an architectural statement with a subject but no rule
#   EXPLANATION a REASON ("چون ...", or the premise before a "پس ...")
#               — never knowledge on its own, but KEPT as the rationale
#               of the rule it explains
#   META        talk about the conversation, not about architecture
#               ("اشتباه فهمیدی", "متوجه شدی؟", a quote of the assistant)
#   LEAD_IN     a preamble with no architectural content
#
# RULE / DEFINITION / OBSERVATION become candidates. EXPLANATION clauses
# are ATTACHED to the rule they explain — the teacher's reasoning is
# neither thrown away nor stored as a fact. META and LEAD_IN are dropped.
#
# IMPORTANT: `match_form` STRIPS punctuation, so the hard boundaries are
# applied to the RAW text and `match_form` is applied per piece.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import (
    match_form,
    NORMATIVE_TOKENS,
    PERSIAN_COPULA_TOKENS,
)


CONTRACT = "ClauseAnalysisV1"
VERSION = "1.0"


# ----------------------------------------------------------
# ROLES
# ----------------------------------------------------------

ROLE_RULE = "RULE"
ROLE_DEFINITION = "DEFINITION"
ROLE_OBSERVATION = "OBSERVATION"
ROLE_EXPLANATION = "EXPLANATION"
ROLE_META = "META"
ROLE_LEAD_IN = "LEAD_IN"

ALL_CLAUSE_ROLES = (
    ROLE_RULE,
    ROLE_DEFINITION,
    ROLE_OBSERVATION,
    ROLE_EXPLANATION,
    ROLE_META,
    ROLE_LEAD_IN,
)

# Roles that may become teaching knowledge.
KNOWLEDGE_ROLES = (
    ROLE_RULE,
    ROLE_DEFINITION,
    ROLE_OBSERVATION,
)

# An internal connector label: the premise that PRECEDES a conclusion.
PREMISE_FOR_CONCLUSION = "premise_for_conclusion"


# ----------------------------------------------------------
# 1. HARD BOUNDARIES — applied to the RAW text, before match_form
# ----------------------------------------------------------

HARD_BOUNDARIES = (
    "\u060c",   # ،
    "\u061b",   # ؛
    ";",
    ".",
    "!",
    "?",
    "\u061f",   # ؟
    "\n",
    ":",
    "\u2022",   # •
    "\u2026",   # …
)


# ----------------------------------------------------------
# 2. CONNECTORS (match form) — the EARLIEST one in a piece wins
# ----------------------------------------------------------

REASON_CONNECTORS = (
    "\u0686\u0648\u0646\u06a9\u0647",  # چونکه
    "\u0686\u0648\u0646",              # چون
    "\u0632\u06cc\u0631\u0627",        # زیرا
    "\u0686\u0631\u0627 \u06a9\u0647",  # چرا که
    "\u0628\u0647 \u062f\u0644\u06cc\u0644",      # به دلیل
    "\u0628\u0647 \u062e\u0627\u0637\u0631",      # به خاطر
    "\u062f\u0644\u06cc\u0644\u0634",  # دلیلش
    "because",
    "since",
)

CONCLUSION_CONNECTORS = (
    "\u0628\u0646\u0627\u0628\u0631\u0627\u06cc\u0646",  # بنابراین
    "\u062f\u0631 \u0646\u062a\u06cc\u062c\u0647",       # در نتیجه
    "\u0628\u0647 \u0647\u0645\u06cc\u0646 \u062f\u0644\u06cc\u0644",  # به همین دلیل
    "\u067e\u0633",                    # پس
    "therefore",
    "so",
)

CONTRAST_CONNECTORS = (
    "\u0648\u0644\u06cc",              # ولی
    "\u0627\u0645\u0627",              # اما
    "\u0628\u0644\u06a9\u0647",        # بلکه
    "but",
)

# class -> label, used by `_classify`
CONNECTOR_CLASSES = (
    (REASON_CONNECTORS, "reason"),
    (CONCLUSION_CONNECTORS, "conclusion"),
    (CONTRAST_CONNECTORS, "contrast"),
)


# ----------------------------------------------------------
# 3. CLAUSE TERMINATORS — a Persian instruction very often ends with
#    one of these and then continues WITHOUT punctuation
# ----------------------------------------------------------

CLAUSE_TERMINATORS = (
    "\u0628\u0647\u062a\u0631\u0647",              # بهتره
    "\u0628\u0647\u062a\u0631 \u0627\u0633\u062a",  # بهتر است
    "\u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u0647",  # نیاز داره
    "\u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f",  # نیاز دارد
    "\u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u0646\u062f",  # نیاز دارند
    "\u0644\u0627\u0632\u0645\u0647",              # لازمه
    "\u0644\u0627\u0632\u0645 \u0627\u0633\u062a",  # لازم است
    "\u0636\u0631\u0648\u0631\u06cc\u0647",        # ضروریه
    "\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u0647",  # داشته باشه
    "\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u06cc",  # داشته باشی
    "\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",  # داشته باشد
)


# 3b. CONTINUATION OPENERS — when a terminator is followed by one of
#     these, the sentence CONTINUES the same predicate and must NOT be
#     split:
#       "تخت خواب هم بهتره دور از پنجره اتاق خواب قرار بگیره"
#     is ONE rule. Splitting after "بهتره" produced the useless fragment
#     "تخت خواب هم بهتره" plus a subject-less "دور از پنجره …".
CONTINUATION_OPENERS = (
    "\u062f\u0648\u0631",              # دور
    "\u0646\u0632\u062f\u06cc\u06a9",  # نزدیک
    "\u06a9\u0646\u0627\u0631",        # کنار
    "\u0645\u062c\u0627\u0648\u0631",  # مجاور
    "\u0686\u0633\u0628\u06cc\u062f\u0647",  # چسبیده
    "\u062c\u062f\u0627",              # جدا
    "\u0631\u0648 \u0628\u0647",        # رو به
    "\u0645\u0634\u0631\u0641",        # مشرف
    "\u062f\u0627\u062e\u0644",        # داخل
    "\u062e\u0627\u0631\u062c",        # خارج
    "\u0628\u06cc\u0646",              # بین
    "\u0648\u0633\u0637",              # وسط
    "\u0632\u06cc\u0631",              # زیر
    "\u067e\u0634\u062a",              # پشت
    "\u062c\u0644\u0648\u06cc",        # جلوی
    "\u0628\u0627\u0644\u0627\u06cc",  # بالای
)


# ----------------------------------------------------------
# 4. TAXONOMY OPENERS — a classification starts a new clause
# ----------------------------------------------------------

TAXONOMY_OPENERS = (
    "\u0627\u0646\u0648\u0627\u0639",                # انواع
    "\u06a9\u0644\u0627",                            # کلا
    "\u06a9\u0644\u0627\u064b",                      # کلاً
    "\u0628\u0647 \u0637\u0648\u0631 \u06a9\u0644\u06cc",  # به طور کلی
)


# ----------------------------------------------------------
# 5. META — talk about the conversation, never architectural knowledge
# ----------------------------------------------------------

META_MARKERS = (
    "\u0627\u0634\u062a\u0628\u0627\u0647 \u0641\u0647\u0645\u06cc\u062f\u06cc",  # اشتباه فهمیدی
    "\u0627\u0634\u062a\u0628\u0627\u0647 \u0641\u0647\u0645\u06cc\u062f\u0647",  # اشتباه فهمیده
    "\u0645\u062a\u0648\u062c\u0647 \u0634\u062f\u06cc",  # متوجه شدی
    # The whole recall phrase, so no filler is left behind when it is
    # stripped ("دلایلش رو هم که فهمیدی" -> "" not "هم که").
    "\u062f\u0644\u0627\u06cc\u0644\u0634 \u0631\u0648 \u0647\u0645 \u06a9\u0647 \u0641\u0647\u0645\u06cc\u062f\u06cc",  # دلایلش رو هم که فهمیدی
    "\u062f\u0644\u0627\u06cc\u0644\u0634 \u0631\u0648 \u0647\u0645 \u06a9\u0647",  # دلایلش رو هم که
    "\u062f\u0644\u0627\u06cc\u0644\u0634 \u0631\u0648",  # دلایلش رو
    "\u062f\u0644\u06cc\u0644\u0634 \u0631\u0648",        # دلیلش رو
    "\u062d\u0627\u0644\u0627 \u062f\u0631\u0633\u062a \u0634\u062f",  # حالا درست شد
    "\u0641\u0647\u0645\u06cc\u062f\u06cc",              # فهمیدی
    "\u0645\u0646\u0637\u0648\u0631\u0645",              # منظورم
    "you misunderstood",
    "did you understand",
)

# Longest first, so "دلایلش رو هم که فهمیدی" is removed as ONE phrase
# instead of leaving "هم که" behind.
META_MARKERS_BY_LENGTH = tuple(
    sorted(META_MARKERS, key=lambda marker: -len(marker))
)

# An assistant-quote introducer: the clause AFTER it is the assistant's
# own words being quoted back — never the teacher's knowledge.
QUOTE_INTRODUCERS = (
    "\u0641\u0647\u0645\u06cc\u062f\u0645",  # فهمیدم
)

# A first-person recall prefix — strip it, KEEP what follows.
RECALL_PREFIXES = (
    "\u0645\u0646 \u06af\u0641\u062a\u0645 \u06a9\u0647",  # من گفتم که
    "\u0645\u0646 \u06af\u0641\u062a\u0645",                # من گفتم
    "\u06af\u0641\u062a\u0645 \u06a9\u0647",                # گفتم که
    "i said",
)

# Normative words the shared classifier does not carry yet. Kept LOCAL
# so `turn_semantics_v1` is not modified.
CLAUSE_NORMATIVE_EXTRA = (
    "\u062d\u062a\u0645\u0627",        # حتما
    "\u062d\u062a\u0645\u0627\u064b",  # حتماً
    "\u0628\u0647\u062a\u0631\u0647",  # بهتره
    "\u0646\u0628\u0627\u06cc\u062f",  # نباید
    "\u062f\u0631 \u0646\u0638\u0631 \u06af\u0631\u0641\u062a",  # در نظر گرفت
)


# A single message never becomes an unbounded pile of candidates.
MAX_CLAUSES = 8


def _has_any(form, markers):

    return any(marker in form for marker in markers)


def _split_hard(raw):

    """Split the RAW text on punctuation, in order."""

    pieces = [raw]

    for separator in HARD_BOUNDARIES:

        next_pieces = []

        for piece in pieces:

            next_pieces.extend(piece.split(separator))

        pieces = next_pieces

    return pieces


def _earliest_connector(form):

    """(index, connector, label) of the earliest connector, or None.

    The connector must stand as its own word, so "پس" inside "پسر" and
    "so" inside "some" can never split a sentence.
    """

    best = None

    for connectors, label in CONNECTOR_CLASSES:

        for connector in connectors:

            index = form.find(connector)

            while index != -1:

                before = form[:index]

                after = form[index + len(connector):]

                before_ok = (not before) or before.endswith(" ")

                after_ok = (not after) or after.startswith(" ")

                if before_ok and after_ok:

                    if best is None or index < best[0]:

                        best = (index, connector, label)

                    break

                index = form.find(connector, index + 1)

    return best


def _split_terminator(form):

    """Split AFTER a clause terminator ("... بهتره <new clause>").

    The terminator must stand as its own words, so "داشته باشه" inside
    "نداشته باشه" can never split a clause — and the text that FOLLOWS
    it must not simply continue the same predicate, or
    "تخت خواب هم بهتره دور از پنجره اتاق خواب قرار بگیره" would become
    the fragment "تخت خواب هم بهتره" plus a subject-less remainder.
    """

    best = None

    for terminator in CLAUSE_TERMINATORS:

        index = form.find(terminator)

        while index != -1:

            starts_a_word = index == 0 or form[index - 1] == " "

            if starts_a_word:

                cut = index + len(terminator)

                tail = form[cut:].strip()

                if tail and not _continues_predicate(tail):

                    if best is None or index < best[0]:

                        best = (index, cut)

                break

            index = form.find(terminator, index + 1)

    if best is None:

        return form, ""

    return form[:best[1]], form[best[1]:]


def _continues_predicate(tail):

    """True when `tail` continues the predicate instead of starting one."""

    return any(
        tail == opener or tail.startswith(opener + " ")
        for opener in CONTINUATION_OPENERS
    )


def _split_taxonomy(form):

    """Split BEFORE a taxonomy opener that is not already the start."""

    for opener in TAXONOMY_OPENERS:

        index = form.find(opener)

        while index > 0:

            if form[index - 1] == " ":

                return form[:index].strip(), form[index:].strip()

            index = form.find(opener, index + 1)

    return form, ""


def _resolve_piece(form, connector=None, out=None):

    """Split one piece at connectors and terminators, recursively."""

    if out is None:

        out = []

    found = _earliest_connector(form)

    if found:

        index, connector_word, label = found

        left = form[:index].strip()

        right = form[index + len(connector_word):].strip()

        if left:

            # the premise BEFORE a conclusion is that conclusion's reason
            left_connector = (
                PREMISE_FOR_CONCLUSION
                if label == "conclusion"
                else connector
            )

            _resolve_piece(left, left_connector, out)

        if right:

            _resolve_piece(right, connector_word, out)

        return out

    head, tail = _split_terminator(form)

    if tail:

        _resolve_piece(head, connector, out)

        _resolve_piece(tail, None, out)

        return out

    before, after = _split_taxonomy(form)

    if after:

        out.append((before, connector))

        _resolve_piece(after, None, out)

        return out

    out.append((form.strip(), connector))

    return out


def segment(text):

    """Split a message into clauses with a role each.

    Deterministic. Never raises. Returns [] for empty input.
    """

    raw = str(text or "")

    if not raw.strip():

        return []

    pieces = []

    for raw_piece in _split_hard(raw):

        if not raw_piece.strip():

            continue

        form = match_form(raw_piece)

        if not form.strip():

            continue

        # ---- strip a first-person recall prefix, keep the rest ----
        for prefix in RECALL_PREFIXES:

            if form.startswith(prefix):

                form = form[len(prefix):].strip()

                break

        if not form:

            continue

        pieces.extend(_resolve_piece(form))

    # ---- roles ----
    clauses = []

    quote_next = False

    for piece, connector in pieces:

        piece = piece.strip()

        if not piece:

            continue

        clause = _classify(
            piece,
            index=len(clauses),
            connector=connector,
            quoted=quote_next,
        )

        quote_next = bool(
            clause["role"] == ROLE_META
            and _is_quote_introducer(piece)
        )

        clauses.append(clause)

    clauses = _attach_rationales(clauses)

    return clauses[:MAX_CLAUSES]


def _is_quote_introducer(form):

    return any(
        form == introducer or form.endswith(" " + introducer)
        for introducer in QUOTE_INTRODUCERS
    )


def _strip_meta(form):

    """Remove conversational meta phrases and keep the real content.

    A clause is very often BOTH ("اشتباه فهمیدی اتاق خواب دو نمونه
    داریم ..."). Dropping the whole clause because it mentions the
    conversation throws away a real statement — so the meta is removed
    and what remains is classified.
    """

    stripped = form

    for marker in META_MARKERS_BY_LENGTH:

        if marker in stripped:

            stripped = stripped.replace(marker, " ")

    return " ".join(stripped.split())


def _make(index, piece, role, reason, connector, knowledge):

    return {
        "index": index,
        "text": piece,
        "role": role,
        "reason": reason,
        "connector": connector,
        "knowledge": knowledge,
        "rationale": None,
    }


def _classify(piece, index=0, connector=None, quoted=False):

    """Role for one clause. A pure function of the clause's own words."""

    # ---- META: quoted back from the assistant ----
    if quoted:

        return _make(
            index, piece, ROLE_META, "quoted_from_assistant",
            connector, False,
        )

    if _is_quote_introducer(piece):

        return _make(
            index, piece, ROLE_META, "assistant_quote_introducer",
            connector, False,
        )

    # ---- strip conversational meta, classify what is left ----
    content = _strip_meta(piece)

    if content != piece:

        if len(content.split()) < 3:

            return _make(
                index, piece, ROLE_META, "conversation_meta",
                connector, False,
            )

        piece = content

    tokens = [token for token in piece.split(" ") if token]

    has_normative = bool(set(tokens) & NORMATIVE_TOKENS) or _has_any(
        piece, CLAUSE_NORMATIVE_EXTRA
    )

    # ---- EXPLANATION ----
    if connector == PREMISE_FOR_CONCLUSION:

        return _make(
            index, piece, ROLE_EXPLANATION, "conclusion_premise",
            connector, False,
        )

    if connector in REASON_CONNECTORS:

        return _make(
            index, piece, ROLE_EXPLANATION, "reason_connector",
            connector, False,
        )

    # ---- DEFINITION ----
    if tokens and len(tokens) >= 4 and tokens[-1] in PERSIAN_COPULA_TOKENS:

        return _make(
            index, piece, ROLE_DEFINITION, "copular_definition",
            connector, True,
        )

    # ---- RULE ----
    if has_normative:

        return _make(
            index, piece, ROLE_RULE, "normative", connector, True
        )

    # ---- OBSERVATION ----
    if len(tokens) >= 3:

        return _make(
            index, piece, ROLE_OBSERVATION, "statement", connector, True
        )

    # ---- LEAD_IN ----
    return _make(
        index, piece, ROLE_LEAD_IN, "no_content", connector, False
    )


def _attach_rationales(clauses):

    """Give every knowledge clause the reason that explains it.

    A reason either FOLLOWS a "چون" connector (attach backwards, to the
    nearest earlier knowledge clause) or PRECEDES a "پس" conclusion
    (attach forwards, to the nearest later knowledge clause).
    """

    attached = [dict(clause) for clause in clauses]

    for position, clause in enumerate(attached):

        if clause["role"] != ROLE_EXPLANATION:

            continue

        backwards = clause.get("reason") == "reason_connector"

        order = (
            range(position - 1, -1, -1)
            if backwards
            else range(position + 1, len(attached))
        )

        for index in order:

            candidate = attached[index]

            if candidate["role"] not in KNOWLEDGE_ROLES:

                continue

            existing = candidate.get("rationale")

            candidate["rationale"] = (
                (existing + " " + clause["text"]).strip()
                if existing
                else clause["text"]
            )

            candidate["rationale_role"] = clause.get("reason")

            clause["consumed_as_rationale"] = True

            break

    return attached


def knowledge_clauses(text):

    """Only the clauses that may become teaching knowledge."""

    return [
        clause for clause in segment(text)
        if clause["role"] in KNOWLEDGE_ROLES
    ]


def role_display(role, language="fa"):

    labels = {

        "fa": {
            ROLE_RULE: "قاعدهٔ طراحی",
            ROLE_DEFINITION: "تعریف",
            ROLE_OBSERVATION: "مشاهده",
            ROLE_EXPLANATION: "توضیح (دلیل)",
            ROLE_META: "گفت‌وگوی متنی",
            ROLE_LEAD_IN: "مقدمه",
        },

        "en": {
            ROLE_RULE: "design rule",
            ROLE_DEFINITION: "definition",
            ROLE_OBSERVATION: "observation",
            ROLE_EXPLANATION: "explanation (reason)",
            ROLE_META: "conversation meta",
            ROLE_LEAD_IN: "lead-in",
        },
    }

    table = labels["fa" if str(language).startswith("fa") else "en"]

    return table.get(role, str(role or ""))


clause_analysis = {

    "contract": CONTRACT,
    "version": VERSION,

    "segment": segment,
    "knowledge_clauses": knowledge_clauses,
    "role_display": role_display,

    "ALL_CLAUSE_ROLES": ALL_CLAUSE_ROLES,
    "KNOWLEDGE_ROLES": KNOWLEDGE_ROLES,
    "MAX_CLAUSES": MAX_CLAUSES,
}


print(
    "CLAUSE ANALYSIS v1.0 ONLINE "
    "(rule vs reason vs meta, deterministic, no storage)"
)
