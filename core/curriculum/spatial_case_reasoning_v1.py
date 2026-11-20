# ==========================================================
# ArchitectOS Spatial Case Reasoning v1
#
# PHASE 11 — PART 6 — CASE REASONING
#
# Answers "why" questions with MODEL EVIDENCE, never with a generic
# language-model opinion.
#
#   "چرا اتاق خواب کنار ورودی نیست؟"
#
# The answer is assembled from:
#   - the Phase 10 graded relation between the two spaces
#   - the relation's stated reason and provenance
#   - the privacy bands and the separation / open-connection verdicts
#   - the zones the two spaces belong to
#
# If any of that evidence is missing the module says so explicitly
# (`insufficient_evidence`) instead of inventing an explanation.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form, script_of

from core.curriculum.space_types_v1 import (
    space_types,
    category_display,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    relation_display,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
)

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.zone_model_v1 import zone_model, zone_display

from core.curriculum.space_query_v1 import scan_spaces


CONTRACT = "SpatialCaseReasoningV1"
VERSION = "1.0"


QUESTION_WHY_ADJACENT = "WHY_ADJACENT"
QUESTION_WHY_NOT_ADJACENT = "WHY_NOT_ADJACENT"
QUESTION_WHY_CATEGORY = "WHY_CATEGORY"
QUESTION_UNKNOWN = "UNKNOWN"


CONCLUSION_SUPPORTED = "supported"
CONCLUSION_NOT_SUPPORTED = "not_supported"
CONCLUSION_INSUFFICIENT = "insufficient_evidence"


WHY_MARKERS = (
    "\u0686\u0631\u0627",        # چرا
    "why",
)

NEGATION_MARKERS = (
    "\u0646\u06cc\u0633\u062a",              # نیست
    "\u0646\u0628\u0627\u06cc\u062f",        # نباید
    "\u0646\u0645\u06cc",                    # نمی
    "\u0646\u0627\u0645\u0646\u0627\u0633\u0628",  # نامناسب
    "\u0646\u062f\u0627\u0631\u062f",        # ندارد
    "not",
    "isn't",
    "shouldn't",
    "must not",
    "cannot",
)

ADJACENCY_MARKERS = (
    "\u06a9\u0646\u0627\u0631",              # کنار
    "\u0646\u0632\u062f\u06cc\u06a9",        # نزدیک
    "\u0645\u062c\u0627\u0648\u0631",        # مجاور
    "\u0645\u062a\u0635\u0644",              # متصل
    "\u062f\u0633\u062a\u0631\u0633\u06cc",  # دسترسی
    "\u0627\u0631\u062a\u0628\u0627\u0637",  # ارتباط
    "next to",
    "near",
    "adjacent",
    "connected",
    "access",
)

CATEGORY_WORDS = (
    "\u062e\u0635\u0648\u0635\u06cc",        # خصوصی
    "\u0639\u0645\u0648\u0645\u06cc",        # عمومی
    "\u062e\u062f\u0645\u0627\u062a\u06cc",  # خدماتی
    "\u0628\u06cc\u0631\u0648\u0646\u06cc",  # بیرونی
    "private",
    "public",
    "service",
    "external",
)


class SpatialCaseReasoningV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None, adjacency=None, privacy=None,
                 zones=None):

        self.registry = registry or space_types

        self.adjacency = adjacency or adjacency_model

        self.privacy = privacy or privacy_logic

        self.zones = zones or zone_model

        print(
            "\U0001f50d SPATIAL CASE REASONING v1.0 ONLINE "
            "(evidence only \u2014 no generic answers)"
        )

    # ======================================================

    def analyze(self, text, language=None):

        raw = str(text or "")

        form = match_form(raw)

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        spaces = scan_spaces(raw)

        why = any(marker in form for marker in WHY_MARKERS)

        negation = any(marker in form for marker in NEGATION_MARKERS)

        adjacency = any(marker in form for marker in ADJACENCY_MARKERS)

        category_word = any(
            marker in form for marker in CATEGORY_WORDS
        )

        if not why:

            question = QUESTION_UNKNOWN

        elif len(spaces) >= 2:

            question = (
                QUESTION_WHY_NOT_ADJACENT if negation
                else QUESTION_WHY_ADJACENT
            )

        elif len(spaces) == 1 and category_word:

            question = QUESTION_WHY_CATEGORY

        else:

            question = QUESTION_UNKNOWN

        result = {

            "contract": CONTRACT,
            "version": VERSION,

            "raw_text": raw,
            "language": lang,

            "question_type": question,

            "spaces": [s[0] for s in spaces],

            "markers": {
                "why": why,
                "negation": negation,
                "adjacency": adjacency,
                "category_word": category_word,
            },

            "deterministic": True,
            "llm_used": False,
            "network_used": False,
            "render_requested": False,
        }

        if question in (
            QUESTION_WHY_ADJACENT, QUESTION_WHY_NOT_ADJACENT
        ):

            result.update(
                self._adjacency_case(
                    spaces[0][0], spaces[1][0], question, lang
                )
            )

        elif question == QUESTION_WHY_CATEGORY:

            result.update(self._category_case(spaces[0][0], lang))

        else:

            result.update(
                {
                    "conclusion": CONCLUSION_INSUFFICIENT,
                    "evidence": {},
                    "answer": self._no_evidence_answer(lang),
                }
            )

        return result

    # ======================================================

    def _adjacency_case(self, source, target, question, lang):

        relation = self.adjacency.relation(source, target)

        if not relation:

            return {
                "conclusion": CONCLUSION_INSUFFICIENT,
                "evidence": {},
                "answer": self._no_relation_answer(
                    source, target, lang
                ),
            }

        evaluation = self.privacy.evaluate(source, target)

        relation_type = relation["relation_type"]

        record_a = self.registry.space(source) or {}

        record_b = self.registry.space(target) or {}

        name_a = (record_a.get("name") or {}).get(lang) or source

        name_b = (record_b.get("name") or {}).get(lang) or target

        separation = evaluation.get("separation") or {}

        open_connection = evaluation.get("direct_open_connection") or {}

        zone_a = self.zones.zone_of(source)

        zone_b = self.zones.zone_of(target)

        # ---- does the model support the user's claim? ----
        separation_required = separation.get("required") is True

        open_allowed = open_connection.get("allowed") is True

        if question == QUESTION_WHY_NOT_ADJACENT:

            supported = separation_required

        else:

            supported = open_allowed

        conclusion = (
            CONCLUSION_SUPPORTED if supported
            else CONCLUSION_NOT_SUPPORTED
        )

        evidence = {

            "relation": {
                "type": relation_type,
                "label": relation_display(relation_type, lang),
                "reason": (
                    relation.get("reason_fa")
                    if lang == "fa" and relation.get("reason_fa")
                    else relation.get("reason")
                ),
                "confidence": relation.get("confidence"),
                "provenance": relation.get("provenance"),
            },

            "source": {
                "space_id": source,
                "name": name_a,
                "category": record_a.get("category"),
                "category_label": category_display(
                    record_a.get("category"), lang
                ),
                "privacy_level": record_a.get("privacy_level"),
                "band": self.privacy.band(source),
                "zone": zone_a,
                "zone_label": zone_display(zone_a, lang),
            },

            "target": {
                "space_id": target,
                "name": name_b,
                "category": record_b.get("category"),
                "category_label": category_display(
                    record_b.get("category"), lang
                ),
                "privacy_level": record_b.get("privacy_level"),
                "band": self.privacy.band(target),
                "zone": zone_b,
                "zone_label": zone_display(zone_b, lang),
            },

            "privacy_relation": evaluation.get("privacy_relation"),

            "separation": separation,

            "direct_open_connection": open_connection,
        }

        return {
            "conclusion": conclusion,
            "relation_type": relation_type,
            "evidence": evidence,
            "answer": self._answer(
                name_a, name_b, evidence, conclusion, question, lang
            ),
        }

    # ------------------------------------------------------

    def _category_case(self, space_id, lang):

        record = self.registry.space(space_id) or {}

        category = record.get("category")

        zone = self.zones.zone_of(space_id)

        behaviour = self.zones.behaviour(zone, lang)

        control = self.privacy.requires_controlled_access(space_id)

        name = (record.get("name") or {}).get(lang) or space_id

        evidence = {
            "space_id": space_id,
            "category": category,
            "category_label": category_display(category, lang),
            "privacy_level": record.get("privacy_level"),
            "band": self.privacy.band(space_id),
            "zone": zone,
            "zone_label": zone_display(zone, lang),
            "zone_behaviour": behaviour,
            "controlled_access": control,
            "examples": record.get("examples") or [],
        }

        if lang == "fa":

            answer = (
                "%s \u062f\u0631 \u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc "
                "\u00ab%s\u00bb \u0648 \u062f\u0631 %s \u0627\u0633\u062a. %s"
                % (
                    name,
                    category_display(category, "fa"),
                    zone_display(zone, "fa"),
                    behaviour.get("reason") or "",
                )
            )

        else:

            answer = (
                "%s is %s and belongs to the %s. %s"
                % (
                    name,
                    category_display(category, "en"),
                    zone_display(zone, "en"),
                    behaviour.get("reason") or "",
                )
            )

        return {
            "conclusion": CONCLUSION_SUPPORTED,
            "evidence": evidence,
            "answer": answer,
        }

    # ======================================================

    def _answer(self, name_a, name_b, evidence, conclusion, question,
                lang):

        relation = evidence["relation"]

        reason = relation.get("reason") or ""

        privacy = evidence.get("privacy_relation")

        if lang == "fa":

            head = (
                "%s \u0627\u0632 %s\u060c \u0648 %s \u0627\u0632 %s \u0627\u0633\u062a."
                % (
                    name_a,
                    evidence["source"]["category_label"],
                    name_b,
                    evidence["target"]["category_label"],
                )
            )

            if question == QUESTION_WHY_NOT_ADJACENT:

                if conclusion == CONCLUSION_SUPPORTED:

                    body = (
                        "\u0627\u0631\u062a\u0628\u0627\u0637 \u0622\u0646\u200c\u0647\u0627 "
                        "\u00ab%s\u00bb \u0627\u0633\u062a%s. %s"
                        % (
                            relation["label"],
                            (
                                " \u0648 \u0639\u0631\u0635\u0647\u0654 "
                                "\u062e\u0635\u0648\u0635\u06cc \u062a\u0636\u0627\u062f "
                                "\u062f\u0627\u0631\u062f"
                                if privacy == "CONFLICT" else ""
                            ),
                            reason,
                        )
                    )

                else:

                    body = (
                        "\u062f\u0631 \u0648\u0627\u0642\u0639 \u0627\u0631\u062a\u0628\u0627\u0637 "
                        "\u0622\u0646\u200c\u0647\u0627 \u00ab%s\u00bb \u0627\u0633\u062a \u0648 "
                        "\u0645\u062f\u0644 \u0627\u06cc\u0646 \u0631\u0627 "
                        "\u0645\u0646\u0639 \u0646\u0645\u06cc\u200c\u06a9\u0646\u062f. %s"
                        % (relation["label"], reason)
                    )

            else:

                if conclusion == CONCLUSION_SUPPORTED:

                    body = (
                        "\u0627\u0631\u062a\u0628\u0627\u0637 \u0622\u0646\u200c\u0647\u0627 "
                        "\u00ab%s\u00bb \u0627\u0633\u062a. %s"
                        % (relation["label"], reason)
                    )

                else:

                    body = (
                        "\u062f\u0631 \u0648\u0627\u0642\u0639 \u0627\u0631\u062a\u0628\u0627\u0637 "
                        "\u0622\u0646\u200c\u0647\u0627 \u00ab%s\u00bb \u0627\u0633\u062a \u0648 "
                        "\u0628\u0627\u0632\u0634\u0648\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 "
                        "\u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a. %s"
                        % (relation["label"], reason)
                    )

            return head + " " + body

        head = "%s is %s and %s is %s." % (
            name_a, evidence["source"]["category_label"],
            name_b, evidence["target"]["category_label"],
        )

        if question == QUESTION_WHY_NOT_ADJACENT:

            if conclusion == CONCLUSION_SUPPORTED:

                body = "Their relation is a %s%s. %s" % (
                    relation["label"],
                    " and the privacy bands conflict"
                    if privacy == "CONFLICT" else "",
                    reason,
                )

            else:

                body = (
                    "In fact their relation is a %s, and the model does "
                    "not forbid it. %s" % (relation["label"], reason)
                )

        else:

            if conclusion == CONCLUSION_SUPPORTED:

                body = "Their relation is a %s. %s" % (
                    relation["label"], reason
                )

            else:

                body = (
                    "In fact their relation is a %s, and a direct opening "
                    "is not appropriate. %s" % (relation["label"], reason)
                )

        return head + " " + body

    # ------------------------------------------------------

    def _no_relation_answer(self, source, target, lang):

        if lang == "fa":

            return (
                "\u0628\u0631\u0627\u06cc \u0627\u0631\u062a\u0628\u0627\u0637 "
                "%s \u0648 %s \u062f\u0631 \u0645\u062f\u0644 \u0645\u062f\u0631\u06a9\u06cc "
                "\u062b\u0628\u062a \u0646\u0634\u062f\u0647 \u0627\u0633\u062a."
                % (source, target)
            )

        return (
            "No relation between %s and %s is recorded in the model."
            % (source, target)
        )

    def _no_evidence_answer(self, lang):

        if lang == "fa":

            return (
                "\u062f\u0631 \u0627\u06cc\u0646 \u062c\u0645\u0644\u0647 "
                "\u0641\u0636\u0627\u06cc \u0634\u0646\u0627\u062e\u062a\u0647\u200c\u0634\u062f\u0647\u200c\u0627\u06cc "
                "\u0646\u06cc\u0633\u062a\u060c \u067e\u0633 "
                "\u062f\u0644\u06cc\u0644\u06cc \u0646\u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u0645 "
                "\u0627\u0632 \u0645\u062f\u0644 \u0628\u06cc\u0627\u0648\u0631\u0645."
            )

        return (
            "No recognised space in that question, so no model evidence "
            "can be given."
        )

    # ------------------------------------------------------

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "question_types": [
                QUESTION_WHY_ADJACENT,
                QUESTION_WHY_NOT_ADJACENT,
                QUESTION_WHY_CATEGORY,
                QUESTION_UNKNOWN,
            ],

            "conclusions": [
                CONCLUSION_SUPPORTED,
                CONCLUSION_NOT_SUPPORTED,
                CONCLUSION_INSUFFICIENT,
            ],

            "evidence_only": True,
            "llm_used": False,
        }


spatial_case_reasoning = SpatialCaseReasoningV1()
