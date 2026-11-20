# -*- coding: utf-8 -*-
"""PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — response-side Persian orthography safety net.

WHY THIS EXISTS
---------------
PERSIAN_OUTPUT_ORTHOGRAPHY_V1 traced the malformed Persian the user saw in
the REAL browser UI. The measured root cause (tools/audit_persian_orthography_
source_v1.py, real llama3):

  * llama3 does NOT invent the malformed spelling from clean input,
  * it ECHOES the malformed word that arrives in the user turn / context,
  * and the prompt had NO Persian orthography contract.

The prompt was then strengthened (core/prompt_engine.py). That removed most
but not all cases (measured residual ≈1/12 turns). This module is the small,
deterministic SAFETY NET the brief explicitly allows for "a very small set of
proven, unambiguous contextual errors".

WHAT IT IS
----------
A deterministic, CONTEXT-AWARE normaliser for EXACTLY the measured failures:

    حیات خلوت   ->  حیاط خلوت      (ONLY this architectural collocation)
    زخیره       ->  ذخیره
    (optional) Arabic codepoints -> Persian codepoints (ي->ی, ك->ک)

WHAT IT IS NOT — and must never become
---------------------------------------
  * NOT a global replacement dictionary.
  * It NEVER replaces the bare word «حیات». «حیات انسان» and «حیات وحش»
    are untouched. Only the two-word architectural collocation
    «حیات خلوت» is corrected — «خلوت» is the disambiguator, because
    «حیات خلوت» is not a Persian phrase while «حیاط خلوت» is a standard
    architectural term.
  * It NEVER changes letters globally.
  * It NEVER touches the user's typed text, the raw transcript, or memory.

WHERE IT APPLIES
----------------
The ASSISTANT RESPONSE TEXT only (the visible reply). It does not touch STT,
the dictation path, routing, or any architectural layer.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


CONTRACT = "PersianOutputOrthographyV1"
VERSION = "1.0"

print("🔤 PERSIAN OUTPUT ORTHOGRAPHY v1.0 ONLINE (context-aware, tiny, raw-safe)")


# ==========================================================
# 1. CONTEXT-AWARE COLLOCATION FIXES (closed set, measured)
# ----------------------------------------------------------
# Each entry is (pattern, replacement, description). The pattern is
# boundary-aware so a substring inside a longer word is never hit.
# ==========================================================

_COLLOCATION_FIXES: Tuple[Tuple[str, str, str], ...] = (
    # Only the two-word architectural collocation — never the bare word.
    ("حیات خلوت", "حیاط خلوت", "architectural_collocation_ط_ت"),
    # "زخیره" is not a Persian word; the only reading is "ذخیره".
    ("زخیره", "ذخیره", "non_word_ذ_ز"),
)


# ==========================================================
# 2. ARABIC -> PERSIAN CODEPOINT UNIFICATION
# ----------------------------------------------------------
# Presentation-only; same letters, correct Persian codepoints. This is
# what a standard Persian keyboard produces.
# ==========================================================

_CODEPOINT_MAP = (
    ("\u064a", "\u06cc"),  # ARABIC YEH        -> FARSI YEH
    ("\u0643", "\u06a9"),  # ARABIC KAF        -> KEHEH
    ("\u0649", "\u06cc"),  # ALEF MAKSURA      -> FARSI YEH
    ("\u06d2", "\u06cc"),  # YEH BARREE        -> FARSI YEH
)


def _boundary_pattern(needle: str) -> "re.Pattern":
    return re.compile(
        r"(?<![\u0600-\u06FF\w])" + re.escape(needle) + r"(?![\u0600-\u06FF\w])"
    )


def normalize_response_orthography(text: Any) -> Dict[str, Any]:
    """Return {text, changes, changed, contract, version}.

    The input text is NEVER mutated in place; a new string is returned.
    When nothing applies, the original string is returned unchanged.
    """

    original = str(text if text is not None else "")

    if not original.strip():
        return {
            "contract": CONTRACT,
            "version": VERSION,
            "text": original,
            "changes": [],
            "changed": False,
        }

    working = original
    changes: List[Dict[str, Any]] = []

    # ---- (a) Arabic -> Persian codepoints ----
    for src, dst in _CODEPOINT_MAP:
        if src in working:
            count = working.count(src)
            working = working.replace(src, dst)
            changes.append({
                "kind": "codepoint_unification",
                "from": src,
                "to": dst,
                "occurrences": count,
            })

    # ---- (b) context-aware collocation fixes ----
    for needle, replacement, kind in _COLLOCATION_FIXES:
        if needle not in working:
            continue
        pattern = _boundary_pattern(needle)
        found = pattern.findall(working)
        if found:
            working = pattern.sub(replacement, working)
            changes.append({
                "kind": kind,
                "from": needle,
                "to": replacement,
                "occurrences": len(found),
            })

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "text": working,
        "changes": changes,
        "changed": bool(changes),
    }


# ==========================================================
# SINGLETON + FUNCTIONAL API
# ==========================================================

class PersianOutputOrthographyV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    # truthful contract flags
    TOUCHES_STT = False
    TOUCHES_DICTATION = False
    TOUCHES_ROUTING = False
    TOUCHES_RAW_TRANSCRIPT = False
    IS_GLOBAL_DICTIONARY = False
    ONLY_CONTEXT_AWARE = True

    def normalize(self, text, **kwargs):
        return normalize_response_orthography(text, **kwargs)

    def describe(self):
        return {
            "contract": CONTRACT,
            "version": VERSION,
            "fixes": [
                {"from": a, "to": b, "kind": k}
                for a, b, k in _COLLOCATION_FIXES
            ],
            "codepoint_unification": [
                {"from": a, "to": b} for a, b in _CODEPOINT_MAP
            ],
        }


persian_output_orthography = PersianOutputOrthographyV1()
