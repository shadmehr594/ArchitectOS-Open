"""ActClassifier (V1) — deterministic, read-only act classification.

The classifier answers exactly ONE question: what kind of human act is this text?

It MAY say
    "This text appears to be an endorsement act."

It may NOT say
    "This claim is now approved."
    "This claim is true."
    "This claim becomes knowledge."

No LLM. No client subsystem. No claim, licence or event is created, and the
event layer is never called. Classification is deterministic: a closed marker
table, no learned weights, no model.

Ambiguity is resolved SAFELY: zero matches, or a tie between acts, yields
`unknown` — the classifier never guesses.
"""

from __future__ import annotations


import hashlib
import re
from typing import Dict, Optional, Set


from core.governance.act_classifier.act_classification_v1 import (
    ACT_TYPES,
    ActClassification,
    build_act_classification,
)


CONTRACT = "ActClassifierV1"

VERSION = "1.0"


LANGUAGES = ("fa", "en", "mixed", "unknown")


_TEXT_REFERENCE_PREFIX = "txt_"


_TOKEN_RE = re.compile(r"[a-z0-9]+")


# Closed marker table. Persian markers are matched as substrings (no reliable
# tokeniser for the ZWNJ forms); ASCII single words are matched as tokens so
# "yes" never matches "yesterday".
_MARKERS: Dict[str, tuple] = {

    "endorsement": (
        "yes", "correct", "agree", "agreed", "appropriate", "right",
        "confirm", "confirmed", "exactly", "valid", "accurate",
        "i agree", "that is right", "sounds right", "makes sense",
        "بله", "درست", "تایید", "تأیید", "موافقم", "مناسب", "صحیح",
        "قبول", "آفرین",
    ),

    "preference": (
        "i like", "i prefer", "i want", "i would like", "my favourite",
        "my favorite", "preference", "i'd like",
        "دوست دارم", "ترجیح", "میخواهم", "می‌خواهم", "سلیقه", "بپسندم",
    ),

    "judgement": (
        "better", "worse", "i think", "in my opinion", "i believe",
        "seems", "probably", "perhaps", "opinion",
        "بهتر", "بدتر", "به نظر", "فکر میکنم", "فکر می‌کنم", "گمان",
    ),

    "decision": (
        "change", "replace", "move", "choose", "decide", "make it",
        "set it", "put it",
        "تغییر", "استفاده", "انتخاب", "قرار بده", "تصمیم", "جابجا",
    ),

    "outcome": (
        "worked", "works well", "succeeded", "success", "failed",
        "failure", "performed", "result",
        "جواب داد", "موفق", "ناموفق", "نتیجه", "عملکرد",
    ),
}


def _normalize(text) -> str:

    return " ".join(str(text or "").lower().split())


def _tokens(form: str) -> Set[str]:

    return set(_TOKEN_RE.findall(form))


def _hit(form: str, tokens: Set[str], marker: str) -> bool:

    marker = marker.lower()

    if " " in marker or not marker.isascii():

        return marker in form

    return marker in tokens


def _detect_language(text) -> str:

    raw = str(text or "")

    has_persian = any("\u0600" <= char <= "\u06FF" for char in raw)

    has_latin = any(char.isascii() and char.isalpha() for char in raw)

    if has_persian and has_latin:

        return "mixed"

    if has_persian:

        return "fa"

    if has_latin:

        return "en"

    return "unknown"


def _text_reference(text) -> str:

    digest = hashlib.sha256(
        str(text or "").encode("utf-8")
    ).hexdigest()[:16]

    return _TEXT_REFERENCE_PREFIX + digest


class ActClassifier:

    """Stateless, deterministic, read-only act classifier."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    def classify(
        self,
        text,
        *,
        text_reference: Optional[str] = None,
        language: Optional[str] = None,
    ) -> ActClassification:

        """Classify the act. NEVER raises: any failure yields `unknown`."""

        try:

            return self._classify(
                text,
                text_reference=text_reference,
                language=language,
            )

        except Exception:

            return build_act_classification(
                act_type="unknown",
                raw_text_reference=text_reference or _text_reference(text),
                language=language if language in LANGUAGES else "unknown",
                confidence_descriptor="none",
            )

    # --------------------------------------------------

    def _classify(
        self,
        text,
        *,
        text_reference=None,
        language=None,
    ) -> ActClassification:

        form = _normalize(text)

        resolved_reference = text_reference or _text_reference(text)

        resolved_language = (
            language if language in LANGUAGES else _detect_language(text)
        )

        if not form:

            return build_act_classification(
                act_type="unknown",
                raw_text_reference=resolved_reference,
                language=resolved_language,
                confidence_descriptor="none",
            )

        tokens = _tokens(form)

        scores: Dict[str, int] = {}

        for act_type, markers in _MARKERS.items():

            hits = {marker for marker in markers if _hit(form, tokens, marker)}

            if hits:

                scores[act_type] = len(hits)

        act_type = "unknown"

        descriptor = "none"

        if scores:

            best = max(scores.values())

            winners = [
                candidate
                for candidate, score in scores.items()
                if score == best
            ]

            if len(winners) == 1:

                act_type = winners[0]

                descriptor = "explicit" if best >= 2 else "weak"

        return build_act_classification(
            act_type=act_type,
            raw_text_reference=resolved_reference,
            language=resolved_language,
            confidence_descriptor=descriptor,
        )

    def __repr__(self):

        return (
            "ActClassifier(decides_truth=False, creates_claims=False, "
            "creates_licences=False, creates_events=False)"
        )


act_classifier = ActClassifier()
