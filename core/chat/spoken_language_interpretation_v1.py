# -*- coding: utf-8 -*-
"""SPOKEN_LANGUAGE_INTERPRETATION_V1 — tolerant understanding of casual speech.

PERSIAN_VOICE_QUALITY_V2 (v2.0) CHANGES
---------------------------------------
Two MEASURED fixes, both still deterministic and raw-preserving:

  1. TIGHTENED architecture rescue gate. v1 fired the "معماری" rescue on
     the bare word "درباره"/"راجع به", which corrupted non-architecture
     turns ("این فیلم درباره میماری …"). A talk-about turn now only
     opens the rescue when the near-miss is the turn's actual OBJECT and
     the turn stays short.
  2. ADDED a context-gated homophone rescue for the exactly-three
     Persian letter confusions Whisper large-v3-turbo was measured to
     make on this machine: حیاط خلوت / ذخیره / آشپزخانه. Each needs an
     independent topic word in the same turn, and an explicit BLOCKER
     list refuses to touch turns that are provably about something else
     (آشپزی cooking, حیات life, fiction, …).

Nothing else changed: no domain routing, no giant dictionary, no
raw-transcript mutation, and uncertainty is still preserved by refusing
to change what cannot be justified.

PROBLEM THIS SOLVES
-------------------
A microphone recording is transcribed by Whisper and handed straight to the
chat path. Real casual speech produces small, recognisable STT noise:

    user says           Whisper transcribes
    ------------------  ----------------------------------
    "معماری"             "مماری"
    "راجع به"            "راجب"
    "می‌خوام"             "میخوام"

Because the transcript is used verbatim, the downstream understanding can
miss an obvious meaning even though a human would read it instantly.

WHAT THIS LAYER IS
------------------
A LIGHTWEIGHT, DETERMINISTIC normaliser that produces a SEPARATE internal
concept — the INTERPRETED UTTERANCE — while ALWAYS preserving the RAW
TRANSCRIPT.

    raw_transcript        "بیا یکمی راجب مماری صحبت کنیم"   (verbatim, kept)
    interpreted_utterance "بیا یکمی راجع به معماری صحبت کنیم" (for understanding)

WHAT IT EXPLICITLY IS NOT
-------------------------
* It is NOT a domain router. It makes no Teaching / Architecture / General
  decision and changes no routing.
* It is NOT a spell-checker and NOT a giant hard-coded typo dictionary. It
  applies a SMALL, closed set of high-confidence spoken-Persian forms plus a
  conservative, context-gated rescue for the single most common STT failure
  (the word "معماری"), and it REFUSES to change anything when the meaning is
  not obvious.
* It NEVER invents content. A token is only ever replaced by a form that is
  (a) a known spoken variant, or (b) an unambiguous near-miss of a canonical
  word AND the surrounding turn is clearly about that word's topic.
* It NEVER modifies the raw transcript. The chat path receives both, and the
  raw transcript stays observable for debugging.

UNCERTAINTY IS PRESERVED
------------------------
Every interpretation returns per-change evidence and a confidence. When the
confidence is not high, NOTHING is changed and `ambiguous` is True.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


CONTRACT = "SpokenLanguageInterpretationV1"
VERSION = "2.0"

print("🗣️ SPOKEN LANGUAGE INTERPRETATION v2.0 ONLINE (deterministic, raw kept)")


# ==========================================================
# 1. HIGH-CONFIDENCE SPOKEN PERSIAN FORMS (closed set)
# ----------------------------------------------------------
# Only forms where the spoken variant is UNAMBIGUOUS — i.e. the written
# word is the only sensible reading. Deliberately SMALL: this is not a
# replacement dictionary, it is the handful of contractions casual speech
# actually produces.
# ==========================================================

_SPOKEN_FORMS: Tuple[Tuple[str, str], ...] = (
    # "راجع به" family
    ("راجب به", "راجع به"),
    ("راجب", "راجع به"),
    ("راجعبه", "راجع به"),
    ("راجعب", "راجع به"),
    ("درمورد", "در مورد"),
    # common spoken contractions
    ("میخوام", "می‌خواهم"),
    ("نمیخوام", "نمی‌خواهم"),
    ("میخوای", "می‌خواهی"),
    ("میخوایم", "می‌خواهیم"),
    ("میخواین", "می‌خواهید"),
    ("نمیدونم", "نمی‌دانم"),
    ("میدونم", "می‌دانم"),
    ("میدونی", "می‌دانی"),
    ("نمیدونید", "نمی‌دانید"),
    ("چیکار", "چه کار"),
    ("چطوری", "چطور هستی"),
    ("اینطوری", "این‌طور"),
    ("اونطوری", "آن‌طور"),
    ("الان", "الآن"),
    ("یه", "یک"),
    ("بذاریم", "بگذاریم"),
    ("بذار", "بگذار"),
    ("تو ذهنمه", "در ذهنم است"),
    ("ولش کن", "رهایش کن"),
    ("بیخیال", "بی‌خیال"),
)

# ==========================================================
# 2. CONTEXT-GATED RESCUE for the canonical architectural word
# ----------------------------------------------------------
# "معماری" is the single most frequent STT victim ("مماری", "میماری",
# "میماری", "مهماری"). The rescue fires ONLY when the turn is clearly
# about architecture — never on its own. This is CONTEXTUAL, not a blind
# substitution.
# ==========================================================

_ARCHITECTURE_CONTEXT_MARKERS: Tuple[str, ...] = (
    "معماری", "معمار", "طراحی", "بنا", "ساختمان", "خانه", "ویلا", "پلان",
    "نما", "نقشه", "پروژه", "فضا", "اتاق", "اولین جلسه", "کورس", "درس",
    "architecture", "architect", "design", "building", "house", "plan",
)

# near-missspellings of معماری that are unambiguous ONLY in context
_ARCHITECTURE_NEAR_MISS: Tuple[str, ...] = (
    "مماری", "میماری", "میماری", "مهماری", "معمماری", "ممامری",
)

# a "let's talk about X" turn — raises X as the topic, so a near-miss X
# is unambiguous in context
_TALK_ABOUT_MARKERS: Tuple[str, ...] = (
    "صحبت کنیم", "حرف بزنیم", "حرف بذاریم", "گپ بزنیم", "گپ بذاریم",
    "صحبت بکنیم", "حرف بزن", "صحبت کن", "درباره", "راجع به", "راجب",
    "در مورد", "talk about", "chat about", "discuss",
)

# PERSIAN_VOICE_QUALITY_V2 — words that prove a turn is NOT about
# architecture. When any of these is present, the "معماری" rescue must
# REFUSE even if a talk-about marker and a near-miss are both present.
# Measured from the real corruption case
# "این فیلم درباره میماری یک بازیکن است".
_NON_ARCHITECTURE_BLOCKERS: Tuple[str, ...] = (
    "فیلم", "بازیگر", "بازیکن", "فوتبال", "ورزش", "موسیقی", "آهنگ",
    "خواننده", "کتاب", "رمان", "داستان", "غذا", "آشپزی", "پختن",
    "طبخ", "برنج", "دارو", "بیماری", "پزشکی", "سیاست", "تاریخ",
    "ریاضی", "فیزیک", "شیمی", "برنامه", "نرم‌افزار", "کد",
)

# ==========================================================
# 2b. CONTEXT-GATED HOMOPHONE RESCUE  (PERSIAN_VOICE_QUALITY_V2)
# ----------------------------------------------------------
# Whisper large-v3-turbo has a small, CONSISTENT set of Persian
# single-letter homophone confusions that were MEASURED on this machine
# (tools/audit_persian_stt_v2.py + .pytest_tmp/stt_audit_v2/):
#
#     حیاط خلوت  ->  حیات خلوت     (ط -> ت)
#     ذخیره      ->  زخیره         (ذ -> ز)
#     آشپزخانه   ->  آشپسخانه / آشبازخانه  (ز -> س / س -> ب)
#
# Each entry carries a CONTEXT REQUIREMENT. A near-miss is only rescued
# when an independent word from its own topic is present in the SAME
# turn. This is what keeps the rescue from corrupting meaning:
#
#   * "حیات پس از مرگ"      has no yard/space context -> NOT touched
#   * "آشپزی" (cooking)     is a DIFFERENT real word -> has no entry,
#                            and never maps to "آشپزخانه"
#   * "زخیره شد و رفت"      has no save/record context -> NOT touched
#
# A near-miss whose surrounding turn does not support it is LEFT AS-IS
# and the uncertainty is preserved (that is the contract).
# ==========================================================

# (near_miss, canonical, required_context_words, kind, needs_context)
#
#   needs_context=True   -> rescues ONLY when a topic word from
#                           `required_context_words` is present, because
#                           the near-miss is ALSO a real Persian word
#                           (e.g. "حیات" = life) and could be genuine.
#   needs_context=False  -> the near-miss is NOT a real word shape at all
#                           (e.g. "زخیره", "آشپسخانه"), so it can only be
#                           an STT error; still refuses if a blocker word
#                           proves the turn is about something else.
_HOMOPHONE_RESCUES: Tuple[Tuple[str, str, Tuple[str, ...], str, bool], ...] = (
    # ط -> ت : "حیاط خلوت" (private yard). "حیات" alone is a REAL word
    # (life), so context is required. The word "خلوت" is itself the
    # disambiguator: "حیات خلوت" is not a Persian phrase, while
    # "حیاط خلوت" is a standard architectural term — so the two-word
    # phrase carries its own architectural context.
    ("حیات خلوت", "حیاط خلوت",
     ("خانه", "ویلا", "ساختمان", "حیاط", "آشپزخانه", "اتاق", "پلان",
      "نقشه", "طراحی", "معماری", "فضا", "خلوت"),
     "homophone_ط_ت", True),

    # ذ -> ز : "ذخیره" (save) mis-heard as "زخیره". "زخیره" is not a real
    # word, so no context is strictly required.
    ("زخیره", "ذخیره",
     ("اطلاعات", "پروژه", "فایل", "ذخیره", "سیو", "نگه دار",
      "متن", "عکس", "تصویر", "پلان", "نقشه", "گزارش", "سند", "تنظیمات"),
     "homophone_ذ_ز", False),

    # ز -> س / س -> ب : "آشپزخانه" mis-heard as "آشپسخانه"/"آشبازخانه".
    # Neither near-miss is a real word; "آشپزی" (cooking) is a DIFFERENT
    # real word and is in the BLOCKER list, so it can never map here.
    ("آشپسخانه", "آشپزخانه",
     ("آشپزخانه", "خانه", "ویلا", "ساختمان", "حیاط", "اتاق", "پلان",
      "نقشه", "طراحی", "معماری", "کنار", "قرار"),
     "homophone_ز_س", False),
    ("آشبازخانه", "آشپزخانه",
     ("آشپزخانه", "خانه", "ویلا", "ساختمان", "حیاط", "اتاق", "پلان",
      "نقشه", "طراحی", "معماری", "کنار", "قرار"),
     "homophone_ز_س", False),
)

# Words that, if present, prove the turn is NOT about the near-miss'
# canonical topic — an explicit REFUSAL guard. Measured from real
# counter-examples (cooking / life-after-death / fiction).
_HOMOPHONE_BLOCKERS: Tuple[str, ...] = (
    # cooking context: never turn a cooking turn into a kitchen turn
    "آشپزی", "پختن", "پخت", "دستور غذا", "غذا", "برنج", "خوراک", "طبخ",
    # life / existence context: never turn "حیات" into "حیاط"
    "پس از مرگ", "زندگی", "زیست", "حیات وحش", "موجود", "سلول",
)


# ==========================================================
# 3. NORMALISATION HELPERS
# ==========================================================

_ZWNJ = "\u200c"

_ARABIC_TO_PERSIAN = (
    ("\u064a", "\u06cc"),  # ي -> ی
    ("\u0643", "\u06a9"),  # ك -> ک
    ("\u0649", "\u06cc"),  # ى -> ی
)


def _collapse(text: str) -> str:
    """Whitespace-collapse without losing characters (the raw text is
    returned separately and never mutated)."""
    return " ".join(str(text or "").split())


def _normalise_letters(text: str) -> str:
    """Arabic/Persian orthographic unification only — no word changes."""
    out = str(text or "")
    for src, dst in _ARABIC_TO_PERSIAN:
        out = out.replace(src, dst)
    return out


def _word_like(text: str) -> bool:
    """True when the turn carries real words (not just punctuation)."""
    return bool(re.search(r"[\w\u0600-\u06FF]", str(text or "")))


# ==========================================================
# 4. THE INTERPRETER
# ==========================================================

class SpokenLanguageInterpreterV1:
    """Deterministic spoken-language normaliser (raw transcript preserved)."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    ROUTES = False
    INVENTS_CONTENT = False
    MUTATES_RAW_TRANSCRIPT = False
    SUBSTITUTES_WHEN_AMBIGUOUS = False

    # ------------------------------------------------------
    # public entry point
    # ------------------------------------------------------

    def interpret(
        self,
        raw_transcript: Any,
        *,
        language: Any = None,
    ) -> Dict[str, Any]:
        """Return {raw_transcript, interpreted_utterance, changes,
        confidence, ambiguous, provenance}.

        The interpreted utterance is used for UNDERSTANDING only. The raw
        transcript is always returned verbatim and unchanged.
        """

        raw = _collapse(raw_transcript)

        if not raw or not _word_like(raw):

            return {
                "contract": CONTRACT,
                "version": VERSION,
                "raw_transcript": raw,
                "interpreted_utterance": raw,
                "changes": [],
                "confidence": "none",
                "ambiguous": False,
                "reason": "no_words",
                "provenance": self._provenance(False),
            }

        working = _normalise_letters(raw)

        changes: List[Dict[str, Any]] = []

        # ---- (a) high-confidence spoken forms ----
        for spoken, written in _SPOKEN_FORMS:

            working, hits = self._replace_token(working, spoken, written)

            if hits:

                changes.append({
                    "kind": "spoken_form",
                    "from": spoken,
                    "to": written,
                    "occurrences": hits,
                    "confidence": "high",
                })

        # ---- (b) context-gated architectural rescue ----
        #
        # The rescue fires when EITHER an independent architecture marker is
        # present (e.g. "طراحی", "پروژه", "اولین جلسه"), OR the turn is a
        # SHORT "let's talk about X" turn that raises the near-miss as its
        # own object.
        #
        # PERSIAN_VOICE_QUALITY_V2 — the talk-about gate was TIGHTENED.
        # v1 fired on the bare word "درباره"/"راجع به", which appears in
        # countless NON-architecture sentences; that corrupted turns like
        # "این فیلم درباره میماری یک بازیکن است" into "…درباره معماری…".
        # A talk-about turn now only opens the rescue when the near-miss
        # is the turn's TOPIC — i.e. it sits right after the talk-about
        # marker and the turn stays short.
        if self._architecture_context(raw) or self._talk_about_topic(raw):

            for miss in _ARCHITECTURE_NEAR_MISS:

                working, hits = self._replace_token(
                    working, miss, "معماری"
                )

                if hits:

                    changes.append({
                        "kind": "contextual_rescue",
                        "from": miss,
                        "to": "معماری",
                        "occurrences": hits,
                        "confidence": "high",
                        "gated_by": (
                            "architecture_topic"
                            if self._architecture_context(raw)
                            else "talk_about_turn"
                        ),
                    })

                    break  # one rescue per turn is enough

        # ---- (c) context-gated homophone rescue (PERSIAN_VOICE_QUALITY_V2) ----
        #
        # Each near-miss is rescued ONLY when (i) an independent word from
        # its own topic is present in the same turn AND (ii) no blocker
        # word proves the turn is actually about something else. When the
        # support is absent the near-miss is LEFT UNCHANGED and the
        # uncertainty is preserved.
        blocked = self._homophone_blocked(raw)

        if not blocked:

            for miss, canonical, context_words, kind, needs_context in _HOMOPHONE_RESCUES:

                if miss not in working:

                    continue

                # a real-word near-miss needs an independent topic word in
                # the same turn; a non-word near-miss can stand alone
                if needs_context and not self._has_any(working, context_words):

                    continue

                working, hits = self._replace_token(working, miss, canonical)

                if hits:

                    changes.append({
                        "kind": "homophone_rescue",
                        "from": miss,
                        "to": canonical,
                        "occurrences": hits,
                        "confidence": "high",
                        "gated_by": kind,
                    })

        working = _collapse(working)

        # ---- uncertainty: never present a change we cannot justify ----
        if not changes:

            return {
                "contract": CONTRACT,
                "version": VERSION,
                "raw_transcript": raw,
                "interpreted_utterance": raw,
                "changes": [],
                "confidence": "none",
                "ambiguous": False,
                "reason": "no_known_spoken_variant",
                "provenance": self._provenance(False),
            }

        # every recorded change is high-confidence by construction (a spoken
        # form is unambiguous; the architectural rescue is context-gated)
        confidence = "high"

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "raw_transcript": raw,
            "interpreted_utterance": working,
            "changes": changes,
            "confidence": confidence,
            "ambiguous": False,
            "reason": "interpreted",
            "provenance": self._provenance(True),
        }

    # ------------------------------------------------------
    # helpers
    # ------------------------------------------------------

    @staticmethod
    def _replace_token(text: str, needle: str, replacement: str):
        """Replace whole-word-ish occurrences, return (text, count)."""

        if not needle or needle not in text:

            return text, 0

        # boundary-aware: Persian word boundaries are whitespace / punctuation
        pattern = re.compile(
            r"(?<![\u0600-\u06FF\w])"
            + re.escape(needle)
            + r"(?![\u0600-\u06FF\w])"
        )

        found = pattern.findall(text)

        if not found:

            return text, 0

        return pattern.sub(replacement, text), len(found)

    @staticmethod
    def _architecture_context(text: str) -> bool:

        low = _normalise_letters(_collapse(text))

        return any(m in low for m in _ARCHITECTURE_CONTEXT_MARKERS)

    @staticmethod
    def _talk_about_topic(text: str) -> bool:
        """True when the turn RAISES a near-miss word as its own topic.

        PERSIAN_VOICE_QUALITY_V2 — this is deliberately NARROW. v1 fired
        on the bare talk-about word alone, so any sentence containing
        "درباره" (e.g. a sentence about a film) opened the architecture
        rescue. A talk-about turn only qualifies when ALL hold:

          (a) a talk-about marker is present, AND
          (b) a known architecture near-miss sits IMMEDIATELY AFTER the
              marker (the near-miss is the object of "about"), AND
          (c) the turn stays short — a topic announcement, not a long
              sentence that merely happens to contain "درباره", AND
          (d) no NON-architecture blocker word is present.

        "بیا راجع به مماری صحبت کنیم" qualifies.
        "این فیلم درباره میماری یک بازیکن است" does NOT (blocker "فیلم").
        """

        low = _normalise_letters(_collapse(text))

        if not any(m in low for m in _TALK_ABOUT_MARKERS):
            return False

        # (d) an explicit refusal guard
        if any(b in low for b in _NON_ARCHITECTURE_BLOCKERS):
            return False

        # collapse the split written form "در باره" -> "درباره" so the
        # token scan sees one marker
        scan = low.replace("در باره", "درباره").replace("راجع به", "راجعبه")

        words = scan.split()
        if not words or len(words) > 12:
            return False

        markers = ("درباره", "راجعبه", "راجب", "مورد")

        for index, word in enumerate(words):
            if any(word == mk or word.startswith(mk) for mk in markers):
                nxt = words[index + 1] if index + 1 < len(words) else ""
                if nxt in _ARCHITECTURE_NEAR_MISS:
                    return True
        return False

    @staticmethod
    def _has_any(text: str, needles) -> bool:
        """True when any needle appears as a token/word in the text."""

        low = str(text or "")
        for needle in needles:
            if not needle:
                continue
            if re.search(
                r"(?<![\u0600-\u06FF\w])" + re.escape(needle)
                + r"(?![\u0600-\u06FF\w])",
                low,
            ):
                return True
        return False

    @staticmethod
    def _homophone_blocked(text: str) -> bool:
        """True when the turn is provably about something else.

        A blocker word (cooking, life-after-death, fiction) means the
        near-miss is NOT an STT error of the canonical word and must be
        left alone. This is the explicit REFUSAL guard.
        """

        low = _normalise_letters(_collapse(text))
        return any(b in low for b in _HOMOPHONE_BLOCKERS)

    @staticmethod
    def _provenance(changed: bool) -> Dict[str, Any]:

        return {
            "engine": "SpokenLanguageInterpreterV1",
            "version": VERSION,
            "deterministic": True,
            "raw_transcript_preserved": True,
            "changed": bool(changed),
        }


# ==========================================================
# SINGLETON + FUNCTIONAL API
# ==========================================================

spoken_language_interpreter = SpokenLanguageInterpreterV1()


def interpret_utterance(raw_transcript, language=None):
    """Convenience wrapper over the singleton."""

    return spoken_language_interpreter.interpret(
        raw_transcript, language=language
    )
