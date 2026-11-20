# ==========================================================
# ArchitectOS Space Query v1
#
# PHASE 10 — SPACE + RELATIONSHIP REASONING SURFACE
#
# Answers the curriculum questions a teacher asks:
#
#   "اتاق خواب فضای خصوصی است"            -> space classification
#   "آشپزخانه کنار نشیمن مناسب است"        -> positive adjacency
#   "ورودی مستقیم به اتاق خواب مناسب نیست" -> negative relationship
#
# Deterministic. No LLM. No network. Persian + English.
#
# This is NOT a chatbot: it reasons over the space-type model and the
# graded adjacency model built in Parts 1-3 and returns a verdict with
# a reason.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form, script_of

from core.curriculum.space_types_v1 import (
    space_types,
    ALL_CATEGORIES,
    CATEGORY_PUBLIC,
    CATEGORY_SEMI_PUBLIC,
    CATEGORY_PRIVATE,
    CATEGORY_SERVICE,
    CATEGORY_CIRCULATION,
    CATEGORY_EXTERNAL,
    category_display,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
    relation_display,
)

from core.curriculum.privacy_logic_v1 import privacy_logic


CONTRACT = "SpaceQueryV1"
VERSION = "1.0"


# ----------------------------------------------------------
# QUERY TYPES
# ----------------------------------------------------------

QUERY_CLASSIFICATION = "SPACE_CLASSIFICATION"
QUERY_POSITIVE_RELATION = "POSITIVE_RELATION"
QUERY_NEGATIVE_RELATION = "NEGATIVE_RELATION"
QUERY_SPACE_LOOKUP = "SPACE_LOOKUP"
QUERY_UNKNOWN = "UNKNOWN"


# ----------------------------------------------------------
# VERDICTS
# ----------------------------------------------------------

VERDICT_CORRECT = "CORRECT"
VERDICT_INCORRECT = "INCORRECT"
VERDICT_ACCEPTABLE = "ACCEPTABLE"
VERDICT_PARTIALLY_ACCEPTABLE = "PARTIALLY_ACCEPTABLE"
VERDICT_NOT_ACCEPTABLE = "NOT_ACCEPTABLE"
VERDICT_CONFIRMED = "CONFIRMED"
VERDICT_DISPUTED = "DISPUTED"
VERDICT_UNKNOWN = "UNKNOWN"

# Added in Phase 11: "the model records NO relation for this pair" is not
# the same claim as "this pair is not acceptable". Reporting the first as
# the second is a false negative claim, and it also leaked the literal
# string "None" into the answer text via relation_display(None).
VERDICT_NO_EVIDENCE = "NO_EVIDENCE"


# ----------------------------------------------------------
# CATEGORY CLAIM VOCABULARY (longest first matters)
# ----------------------------------------------------------

CATEGORY_CLAIM_WORDS = (
    ("\u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc", CATEGORY_SEMI_PUBLIC),
    ("\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc", CATEGORY_SEMI_PUBLIC),
    ("\u0646\u06cc\u0645\u0647\u200c\u0639\u0645\u0648\u0645\u06cc", CATEGORY_SEMI_PUBLIC),
    ("\u0639\u0645\u0648\u0645\u06cc", CATEGORY_PUBLIC),
    ("\u062e\u0635\u0648\u0635\u06cc", CATEGORY_PRIVATE),
    ("\u062e\u062f\u0645\u0627\u062a\u06cc", CATEGORY_SERVICE),
    ("\u0633\u0631\u0648\u06cc\u0633\u06cc", CATEGORY_SERVICE),
    ("\u06af\u0631\u062f\u0634", CATEGORY_CIRCULATION),
    ("\u0627\u0631\u062a\u0628\u0627\u0637\u06cc", CATEGORY_CIRCULATION),
    ("\u0628\u06cc\u0631\u0648\u0646\u06cc", CATEGORY_EXTERNAL),
    ("\u062e\u0627\u0631\u062c\u06cc", CATEGORY_EXTERNAL),
    ("semi-public", CATEGORY_SEMI_PUBLIC),
    ("semipublic", CATEGORY_SEMI_PUBLIC),
    ("semi public", CATEGORY_SEMI_PUBLIC),
    ("public", CATEGORY_PUBLIC),
    ("private", CATEGORY_PRIVATE),
    ("service", CATEGORY_SERVICE),
    ("circulation", CATEGORY_CIRCULATION),
    ("external", CATEGORY_EXTERNAL),
    ("outdoor", CATEGORY_EXTERNAL),
)


# ----------------------------------------------------------
# RELATION / JUDGEMENT MARKERS
# ----------------------------------------------------------

RELATION_MARKERS = (
    # Persian
    "\u06a9\u0646\u0627\u0631",              # کنار
    "\u0646\u0632\u062f\u06cc\u06a9",        # نزدیک
    "\u0645\u062c\u0627\u0648\u0631",        # مجاور
    "\u0645\u062a\u0635\u0644",              # متصل
    "\u0686\u0633\u0628\u06cc\u062f\u0647",  # چسبیده
    "\u0647\u0645\u062c\u0648\u0627\u0631",  # همجوار
    "\u0628\u0627\u0632 \u0634\u0648\u062f",  # باز شود
    "\u062f\u0633\u062a\u0631\u0633\u06cc",  # دسترسی
    "\u0627\u0631\u062a\u0628\u0627\u0637",  # ارتباط
    # English
    "next to",
    "near",
    "adjacent",
    "connected to",
    "beside",
    "open to",
    "opens to",
    "access to",
)


DIRECTNESS_MARKERS = (
    "\u0645\u0633\u062a\u0642\u06cc\u0645",  # مستقیم
    "\u0628\u062f\u0648\u0646 \u0648\u0627\u0633\u0637\u0647",  # بدون واسطه
    "directly",
    "direct",
)


NEGATION_MARKERS = (
    "\u0646\u06cc\u0633\u062a",              # نیست
    "\u0646\u0628\u0627\u06cc\u062f",        # نباید
    "\u0646\u0645\u06cc",                    # نمی
    "\u0646\u0627\u0645\u0646\u0627\u0633\u0628",  # نامناسب
    "\u063a\u0644\u0637",                    # غلط
    "\u0627\u0634\u062a\u0628\u0627\u0647",  # اشتباه
    "\u0646\u0627\u062f\u0631\u0633\u062a",  # نادرست
    "not ",
    "should not",
    "must not",
    "cannot",
    "can not",
    "isn't",
    "is not",
    "wrong",
    "incorrect",
)


POSITIVE_JUDGEMENT_MARKERS = (
    "\u0645\u0646\u0627\u0633\u0628",        # مناسب
    "\u062f\u0631\u0633\u062a",              # درست
    "\u0628\u0647\u062a\u0631",              # بهتر
    "\u062e\u0648\u0628",                    # خوب
    "\u0635\u062d\u06cc\u062d",              # صحیح
    "appropriate",
    "suitable",
    "correct",
    "good",
    "fine",
    "acceptable",
)


def _any_in(text, markers):

    return any(marker in text for marker in markers)


# ----------------------------------------------------------
# SPACE MENTION SCANNING
# ----------------------------------------------------------

def _build_alias_table(registry):

    """alias -> space_id, PREFERRED_TERM wins, longest alias first.

    Both existing models contain a "kitchen"/"bedroom"/"entrance". The
    preferred-term table decides which record owns the bare term, so a
    scan and `registry.find()` always agree.
    """

    from core.curriculum.space_types_v1 import PREFERRED_TERM

    table = {}

    for space_id, record in registry.spaces().items():

        names = record.get("name") or {}

        candidates = set(record.get("aliases") or [])

        for value in names.values():

            if value:

                candidates.add(value)

        for alias in candidates:

            normalized = match_form(alias)

            if len(normalized) < 3:

                continue

            table.setdefault(normalized, space_id)

    # ---- preferred terms WIN ----
    for term, space_id in PREFERRED_TERM.items():

        normalized = match_form(term)

        if len(normalized) >= 3 and registry.space(space_id):

            table[normalized] = space_id

    # longest alias first so "اتاق خواب مستر" beats "اتاق خواب"
    return sorted(table.items(), key=lambda item: -len(item[0]))


_ALIAS_TABLE = None


def _alias_table():

    global _ALIAS_TABLE

    if _ALIAS_TABLE is None:

        _ALIAS_TABLE = _build_alias_table(space_types)

    return _ALIAS_TABLE


def scan_spaces(text):

    """Find space mentions, longest-match, non-overlapping, ordered."""

    form = match_form(text)

    taken = [False] * (len(form) + 1)

    found = []

    for alias, space_id in _alias_table():

        start = form.find(alias)

        while start != -1:

            end = start + len(alias)

            if not any(taken[start:end]):

                for index in range(start, end):

                    taken[index] = True

                found.append((start, space_id, alias))

                break

            start = form.find(alias, start + 1)

    found.sort(key=lambda item: item[0])

    # de-duplicate consecutive identical spaces
    ordered = []

    for _position, space_id, alias in found:

        if ordered and ordered[-1][0] == space_id:

            continue

        ordered.append((space_id, alias))

    return ordered


# ----------------------------------------------------------
# QUERY
# ----------------------------------------------------------

class SpaceQueryV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, adjacency=None, privacy=None):

        self.registry = registry or space_types

        self.adjacency = adjacency or adjacency_model

        self.privacy = privacy or privacy_logic

        print(
            "\U0001f9ed SPACE QUERY v1.0 ONLINE "
            "(space + relationship reasoning)"
        )

    # ======================================================

    def analyze(self, text, language=None):

        raw = str(text or "")

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        form = match_form(raw)

        spaces = scan_spaces(raw)

        relation_marker = _any_in(form, RELATION_MARKERS)

        directness = _any_in(form, DIRECTNESS_MARKERS)

        negation = _any_in(form, NEGATION_MARKERS)

        judgement = _any_in(form, POSITIVE_JUDGEMENT_MARKERS)

        category_claim = self._category_claim(form)

        # ---- decide the query type ----
        if len(spaces) >= 2 and (relation_marker or directness or negation):

            query_type = (
                QUERY_NEGATIVE_RELATION if negation
                else QUERY_POSITIVE_RELATION
            )

        elif len(spaces) >= 1 and category_claim:

            query_type = QUERY_CLASSIFICATION

        elif len(spaces) >= 1:

            query_type = QUERY_SPACE_LOOKUP

        else:

            query_type = QUERY_UNKNOWN

        result = {

            "contract": CONTRACT,
            "version": VERSION,

            "raw_text": raw,
            "language": lang,

            "query_type": query_type,

            "spaces": [
                {
                    "space_id": space_id,
                    "alias": alias,
                    "name": (
                        self.registry.space(space_id) or {}
                    ).get("name"),
                    "category": (
                        self.registry.space(space_id) or {}
                    ).get("category"),
                }
                for space_id, alias in spaces
            ],

            "markers": {
                "relation": relation_marker,
                "directness": directness,
                "negation": negation,
                "judgement": judgement,
            },

            "claimed_category": category_claim,

            "deterministic": True,
            "llm_used": False,
            "network_used": False,
            "render_requested": False,
        }

        if query_type == QUERY_CLASSIFICATION:

            result.update(
                self._classification(spaces[0][0], category_claim, lang)
            )

        elif query_type in (
            QUERY_POSITIVE_RELATION, QUERY_NEGATIVE_RELATION
        ):

            result.update(
                self._relation(
                    spaces[0][0],
                    spaces[1][0],
                    query_type,
                    directness,
                    lang,
                )
            )

        elif query_type == QUERY_SPACE_LOOKUP:

            result.update(self._lookup(spaces[0][0], lang))

        else:

            result.update(
                {
                    "verdict": VERDICT_UNKNOWN,
                    "answer": self._unknown_answer(lang),
                    "reason": "no space or relationship recognised",
                }
            )

        return result

    # ------------------------------------------------------

    def _category_claim(self, form):

        for word, category in CATEGORY_CLAIM_WORDS:

            if word in form:

                return category

        return None

    # ------------------------------------------------------

    def _classification(self, space_id, claimed, lang):

        record = self.registry.space(space_id) or {}

        actual = record.get("category")

        correct = claimed == actual

        name = (record.get("name") or {}).get(lang) or space_id

        if lang == "fa":

            if correct:

                answer = (
                    "\u062f\u0631\u0633\u062a \u0627\u0633\u062a\u061b "
                    "%s \u062f\u0631 \u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc "
                    "\u00ab%s\u00bb \u0642\u0631\u0627\u0631 \u0645\u06cc\u200c\u06af\u06cc\u0631\u062f."
                    % (name, category_display(actual, "fa"))
                )
            else:

                answer = (
                    "\u062f\u0631\u0633\u062a \u0646\u06cc\u0633\u062a\u061b "
                    "%s \u062f\u0631 \u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc "
                    "\u00ab%s\u00bb \u0627\u0633\u062a\u060c \u0646\u0647 \u00ab%s\u00bb."
                    % (
                        name,
                        category_display(actual, "fa"),
                        category_display(claimed, "fa"),
                    )
                )

        else:

            if correct:

                answer = (
                    "Correct \u2014 %s is classified as %s."
                    % (name, category_display(actual, "en"))
                )

            else:

                answer = (
                    "Not correct \u2014 %s is %s, not %s."
                    % (
                        name,
                        category_display(actual, "en"),
                        category_display(claimed, "en"),
                    )
                )

        return {

            "space_id": space_id,
            "space_name": name,
            "claimed_category": claimed,
            "actual_category": actual,
            "actual_privacy_level": record.get("privacy_level"),
            "privacy_band": self.privacy.band(space_id),

            "verdict": VERDICT_CORRECT if correct else VERDICT_INCORRECT,

            "answer": answer,

            "reason": "space registry category is %s" % actual,

            "examples": record.get("examples") or [],
        }

    # ------------------------------------------------------

    def _relation(self, source, target, query_type, directness, lang):

        evaluation = self.privacy.evaluate(source, target)

        relation_type = evaluation.get("relation_type")

        name_a = (
            self.registry.space(source) or {}
        ).get("name", {}).get(lang) or source

        name_b = (
            self.registry.space(target) or {}
        ).get("name", {}).get(lang) or target

        separation = evaluation.get("separation") or {}

        open_connection = evaluation.get("direct_open_connection") or {}

        if query_type == QUERY_NEGATIVE_RELATION:

            acceptable = separation.get("required") is True

            verdict = VERDICT_CONFIRMED if acceptable else VERDICT_DISPUTED

        elif not relation_type:

            # no relation is RECORDED for this pair: say so instead of
            # asserting the pair is unacceptable
            verdict = VERDICT_NO_EVIDENCE

        else:

            allowed = open_connection.get("allowed")

            if allowed is True:

                verdict = VERDICT_ACCEPTABLE

            elif relation_type == REL_WEAK:

                verdict = VERDICT_PARTIALLY_ACCEPTABLE

            else:

                verdict = VERDICT_NOT_ACCEPTABLE

        reason = self._relation_reason(
            source, target, relation_type, separation, lang
        )

        answer = self._relation_answer(
            name_a,
            name_b,
            relation_type,
            verdict,
            directness,
            lang,
        )

        return {

            "source_space": source,
            "target_space": target,

            "has_relation": bool(relation_type),

            "relation_type": relation_type,
            "relation_label": (
                relation_display(relation_type, lang)
                if relation_type else None
            ),

            "privacy_relation": evaluation.get("privacy_relation"),

            "source_category": evaluation.get("source_category"),
            "target_category": evaluation.get("target_category"),

            "direct_open_connection": open_connection,
            "separation": separation,

            "verdict": verdict,

            "answer": answer,

            "reason": reason,

            "confidence": (
                self.adjacency.relation(source, target) or {}
            ).get("confidence"),

            "provenance": (
                self.adjacency.relation(source, target) or {}
            ).get("provenance"),
        }

    # ------------------------------------------------------

    def _relation_reason(self, source, target, relation_type, separation,
                         lang):

        record = self.adjacency.relation(source, target) or {}

        if lang == "fa":

            reason = record.get("reason_fa") or record.get("reason") or ""

        else:

            reason = record.get("reason") or ""

        parts = [reason] if reason else []

        if separation.get("privacy_relation") == "CONFLICT":

            parts.append(
                "\u062a\u0636\u0627\u062f \u0639\u0631\u0635\u0647\u0654 "
                "\u062e\u0635\u0648\u0635\u06cc"
                if lang == "fa"
                else "privacy band conflict"
            )

        return " \u2014 ".join(parts)

    # ------------------------------------------------------

    def _relation_answer(self, name_a, name_b, relation_type, verdict,
                         directness, lang):

        if verdict == VERDICT_NO_EVIDENCE:

            if lang == "fa":

                return (
                    "\u0628\u0631\u0627\u06cc \u0627\u0631\u062a\u0628\u0627\u0637 "
                    "%s \u0648 %s \u062f\u0631 \u0645\u062f\u0644 \u0645\u062f\u0631\u06a9\u06cc "
                    "\u062b\u0628\u062a \u0646\u0634\u062f\u0647 \u0627\u0633\u062a\u061b "
                    "\u067e\u0633 \u0646\u0647 \u062a\u0623\u06cc\u06cc\u062f \u0645\u06cc\u200c\u06a9\u0646\u0645 "
                    "\u0648 \u0646\u0647 \u0631\u062f."
                    % (name_a, name_b)
                )

            return (
                "No relation between %s and %s is recorded in the model, "
                "so this can be neither confirmed nor refused."
                % (name_a, name_b)
            )

        label = relation_display(relation_type, lang)

        if lang == "fa":

            if verdict == VERDICT_CONFIRMED:

                return (
                    "\u0628\u0644\u0647\u060c \u062f\u0631\u0633\u062a "
                    "\u0627\u0633\u062a. \u0627\u0631\u062a\u0628\u0627\u0637 "
                    "%s \u0648 %s \u00ab%s\u00bb \u0627\u0633\u062a."
                    % (name_a, name_b, label)
                )

            if verdict == VERDICT_DISPUTED:

                return (
                    "\u062e\u06cc\u0631\u060c \u0627\u0631\u062a\u0628\u0627\u0637 "
                    "%s \u0648 %s \u00ab%s\u00bb \u0627\u0633\u062a."
                    % (name_a, name_b, label)
                )

            if verdict == VERDICT_ACCEPTABLE:

                return (
                    "\u0628\u0644\u0647\u060c \u0645\u0646\u0627\u0633\u0628 "
                    "\u0627\u0633\u062a. \u0627\u0631\u062a\u0628\u0627\u0637 "
                    "%s \u0648 %s \u00ab%s\u00bb \u0627\u0633\u062a."
                    % (name_a, name_b, label)
                )

            if verdict == VERDICT_PARTIALLY_ACCEPTABLE:

                return (
                    "\u0641\u0642\u0637 \u0628\u0627 \u0648\u0627\u0633\u0637\u0647 "
                    "\u0648 \u0645\u0633\u06cc\u0631 \u0628\u0627\u0641\u0631. "
                    "\u0627\u0631\u062a\u0628\u0627\u0637 %s \u0648 %s "
                    "\u00ab%s\u00bb \u0627\u0633\u062a."
                    % (name_a, name_b, label)
                )

            return (
                "\u0646\u0647\u060c \u0645\u0646\u0627\u0633\u0628 "
                "\u0646\u06cc\u0633\u062a. \u0627\u0631\u062a\u0628\u0627\u0637 "
                "%s \u0648 %s \u00ab%s\u00bb \u0627\u0633\u062a."
                % (name_a, name_b, label)
            )

        if verdict == VERDICT_CONFIRMED:

            return "Yes, that is right. %s and %s are a %s." % (
                name_a, name_b, label
            )

        if verdict == VERDICT_DISPUTED:

            return "No \u2014 %s and %s are a %s." % (
                name_a, name_b, label
            )

        if verdict == VERDICT_ACCEPTABLE:

            return "Yes, that is appropriate. %s and %s are a %s." % (
                name_a, name_b, label
            )

        if verdict == VERDICT_PARTIALLY_ACCEPTABLE:

            return (
                "Only with a buffer. %s and %s are a %s."
                % (name_a, name_b, label)
            )

        return "No, that is not appropriate. %s and %s are a %s." % (
            name_a, name_b, label
        )

    # ------------------------------------------------------

    def _lookup(self, space_id, lang):

        record = self.registry.space(space_id) or {}

        name = (record.get("name") or {}).get(lang) or space_id

        category = record.get("category")

        if lang == "fa":

            answer = (
                "%s \u062f\u0631 \u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc "
                "\u00ab%s\u00bb \u0627\u0633\u062a." % (
                    name, category_display(category, "fa")
                )
            )

        else:

            answer = "%s is %s." % (
                name, category_display(category, "en")
            )

        return {

            "space_id": space_id,
            "space_name": name,
            "actual_category": category,
            "actual_privacy_level": record.get("privacy_level"),
            "privacy_band": self.privacy.band(space_id),
            "typical_adjacent": record.get("typical_adjacent") or [],
            "discouraged_adjacent": record.get("discouraged_adjacent") or [],
            "examples": record.get("examples") or [],
            "verdict": VERDICT_UNKNOWN,
            "answer": answer,
            "reason": "space lookup",
        }

    # ------------------------------------------------------

    def _unknown_answer(self, lang):

        if lang == "fa":

            return (
                "\u0641\u0636\u0627\u06cc \u0634\u0646\u0627\u062e\u062a\u0647\u200c\u0634\u062f\u0647\u200c\u0627\u06cc "
                "\u062f\u0631 \u0627\u06cc\u0646 \u062c\u0645\u0644\u0647 \u0646\u06cc\u0633\u062a."
            )

        return "No recognised space in that statement."

    # ------------------------------------------------------

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "query_types": [
                QUERY_CLASSIFICATION,
                QUERY_POSITIVE_RELATION,
                QUERY_NEGATIVE_RELATION,
                QUERY_SPACE_LOOKUP,
                QUERY_UNKNOWN,
            ],

            "verdicts": [
                VERDICT_CORRECT,
                VERDICT_INCORRECT,
                VERDICT_ACCEPTABLE,
                VERDICT_PARTIALLY_ACCEPTABLE,
                VERDICT_NOT_ACCEPTABLE,
                VERDICT_CONFIRMED,
                VERDICT_DISPUTED,
                VERDICT_NO_EVIDENCE,
                VERDICT_UNKNOWN,
            ],

            "alias_count": len(_alias_table()),

            "categories": list(ALL_CATEGORIES),

            "relation_types": [
                REL_STRONG, REL_NORMAL, REL_WEAK, REL_AVOID, REL_FORBIDDEN,
            ],

            "deterministic": True,
            "llm_used": False,
        }


space_query = SpaceQueryV1()
