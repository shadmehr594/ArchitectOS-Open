# ==========================================================
# ArchitectOS Persian / Language Normalization Boundary v1.0
#
# PHASE 2D-1 — PERSIAN / LANGUAGE NORMALIZATION FOUNDATION
#
# Deterministic. Local. Non-LLM. Provider-independent.
#
# Responsibilities:
#   - Unicode normalization
#   - Arabic -> Persian letter normalization (ي -> ی, ك -> ک)
#   - ZWNJ / zero-width control normalization
#   - Persian / Arabic-Indic digit normalization (-> ASCII)
#   - whitespace normalization
#   - invisible bidi/format control removal
#   - deterministic language detection (fa / en / mixed / unknown)
#
# Explicit NON-responsibilities (later phases):
#   - no semantic interpretation
#   - no colloquial rewriting
#   - no spelling correction
#   - no translation
#   - no LLM / provider calls
#
# RAW TEXT IS NEVER DESTROYED. It is carried on NormalizedRequest.raw_text.
# ==========================================================


from __future__ import annotations

import re
import unicodedata


NORMALIZATION_VERSION = "1.0"


# ==========================================================
# CHARACTER TABLES
# ==========================================================

# Arabic letter forms that have a distinct canonical Persian letter.
# Deliberately minimal and conservative: only the two unambiguous pairs
# required by PHASE 2D-1.  (ة / ى / ه variants are NOT rewritten.)
_ARABIC_TO_PERSIAN = {
    ord("\u064A"): "\u06CC",  # ARABIC YEH        ي  ->  PERSIAN YEH  ی
    ord("\u0643"): "\u06A9",  # ARABIC KAF        ك  ->  PERSIAN KAF  ک
}


# Zero-width / join controls.
ZWNJ = "\u200C"  # ZERO WIDTH NON-JOINER (canonical Persian)
_ZWSP = "\u200B"  # ZERO WIDTH SPACE
_BOM = "\uFEFF"   # ZERO WIDTH NO-BREAK SPACE / BOM

# Invisible bidi / directional formatting controls (pure noise for text
# processing).  These are removed, not replaced.
_BIDI_CONTROL_CODEPOINTS = (
    [0x200E, 0x200F, 0x061C]          # LRM, RLM, ALM
    + list(range(0x202A, 0x202F))     # LRE, RLE, PDF, LRO, RLO
    + list(range(0x2066, 0x206A))     # LRI, RLI, FSI, PDI
)
_BIDI_CONTROL_MAP = dict.fromkeys(_BIDI_CONTROL_CODEPOINTS, None)


# Digit normalization -> ASCII 0-9.
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"        # U+06F0..U+06F9
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"    # U+0660..U+0669

_DIGIT_MAP = {ord(ch): str(i) for i, ch in enumerate(_PERSIAN_DIGITS)}
_DIGIT_MAP.update({ord(ch): str(i) for i, ch in enumerate(_ARABIC_INDIC_DIGITS)})


# ==========================================================
# REGEX
# ==========================================================

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_ZWNJ_RUN_RE = re.compile("\u200C+")
_ZWNJ_EDGE_LEFT_RE = re.compile("(^|\\s)\u200C+")
_ZWNJ_EDGE_RIGHT_RE = re.compile("\u200C+(\\s|$)")

_LATIN_RE = re.compile(r"[A-Za-z]")

# Script ranges considered "Persian/Arabic" for language detection.
_PERSIAN_RANGES = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)


def _is_persian_char(ch: str) -> bool:
    code = ord(ch)
    for start, end in _PERSIAN_RANGES:
        if start <= code <= end:
            return True
    return False


def has_persian_chars(text) -> bool:
    """True if the text contains at least one Persian/Arabic script character."""
    if not text:
        return False
    return any(_is_persian_char(ch) for ch in str(text))


# ==========================================================
# DETERMINISTIC LANGUAGE DETECTION
# ==========================================================

def detect_language(text) -> str:
    """Canonical deterministic language detector.

    Returns one of: "fa" | "en" | "mixed" | "unknown".

    Purely script-based; never uses an LLM or a provider.
    """
    if not text:
        return "unknown"

    value = str(text)
    persian = 0
    latin = 0

    for ch in value:
        if _is_persian_char(ch):
            persian += 1
        elif _LATIN_RE.match(ch):
            latin += 1

    if persian and latin:
        return "mixed"
    if persian:
        return "fa"
    if latin:
        return "en"
    return "unknown"


# ==========================================================
# NORMALIZED REQUEST CONTRACT
# ==========================================================

class NormalizedRequest(dict):
    """Versioned, dict-compatible request representation.

    Dictionary-compatible so existing callers that read ``payload["text"]``
    keep working.  ``raw_text`` is always the untouched original input.
    """

    CONTRACT = "NormalizedRequest"
    VERSION = NORMALIZATION_VERSION


# ==========================================================
# NORMALIZER
# ==========================================================

class PersianNormalizer:

    VERSION = NORMALIZATION_VERSION

    def __init__(self):

        # Ordered deterministic pipeline: (step_name, callable).
        self._pipeline = (
            ("unicode_normalization", lambda t: unicodedata.normalize("NFC", t)),
            ("invisible_control_removal", lambda t: t.translate(_BIDI_CONTROL_MAP)),
            ("arabic_to_persian_letters", lambda t: t.translate(_ARABIC_TO_PERSIAN)),
            ("zwnj_normalization", self._normalize_zwnj),
            ("digit_normalization", lambda t: t.translate(_DIGIT_MAP)),
            ("whitespace_normalization", self._normalize_whitespace),
        )

        print("🔤 PERSIAN NORMALIZER v1.0 ONLINE (deterministic)")

    # ======================================================
    # STEP: ZWNJ
    # ======================================================

    def _normalize_zwnj(self, text):
        """Conservative zero-width normalization.

        - BOM / ZWNBSP removed
        - ZWSP (U+200B) -> canonical ZWNJ (U+200C)   [orthographic variant]
        - consecutive ZWNJ collapsed to one
        - ZWNJ adjacent to whitespace or string edges removed

        A plain space is NEVER converted into a ZWNJ (no linguistic rewriting).
        """
        result = text.replace(_BOM, "")
        result = result.replace(_ZWSP, ZWNJ)
        result = _ZWNJ_RUN_RE.sub(ZWNJ, result)
        result = _ZWNJ_EDGE_LEFT_RE.sub(lambda m: m.group(1), result)
        result = _ZWNJ_EDGE_RIGHT_RE.sub(lambda m: m.group(1), result)
        return result

    # ======================================================
    # STEP: WHITESPACE
    # ======================================================

    def _normalize_whitespace(self, text):
        """Collapse every whitespace run to a single ASCII space and strip."""
        return _WHITESPACE_RE.sub(" ", text).strip()

    # ======================================================
    # LANGUAGE DETECTION (instance API)
    # ======================================================

    def detect_language(self, text):
        """Canonical deterministic detector: "fa" | "en" | "mixed" | "unknown"."""
        return detect_language(text)

    def has_persian_chars(self, text):
        """True if the text contains Persian/Arabic script characters."""
        return has_persian_chars(text)

    # ======================================================
    # NORMALIZE
    # ======================================================

    def normalize(self, text):
        """Return a NormalizedRequest for ``text``.

        Deterministic: identical input always yields identical output.
        The original string is preserved verbatim in ``raw_text``.
        """

        raw_text = "" if text is None else str(text)

        working = raw_text
        steps = []

        for name, transform in self._pipeline:
            updated = transform(working)
            if updated != working:
                steps.append(name)
                working = updated

        language = detect_language(raw_text)

        request = NormalizedRequest({
            "contract": NormalizedRequest.CONTRACT,
            "version": NORMALIZATION_VERSION,

            # --- preservation ---
            "raw_text": raw_text,

            # --- canonical processing form ---
            "normalized_text": working,

            # backward-compatible alias: "text" == normalized form
            "text": working,

            # --- language / flags ---
            "detected_language": language,
            "had_persian_chars": has_persian_chars(raw_text),
            "normalization_applied": working != raw_text,

            # --- audit ---
            "normalization_steps": steps,
            "normalization_metadata": {
                "version": NORMALIZATION_VERSION,
                "steps": list(steps),
                "detected_language": language,
                "had_persian_chars": has_persian_chars(raw_text),
                "normalization_applied": working != raw_text,
            },
        })

        return request


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

persian_normalizer = PersianNormalizer()


def normalize(text):
    """Module-level convenience wrapper over the canonical normalizer."""
    return persian_normalizer.normalize(text)
