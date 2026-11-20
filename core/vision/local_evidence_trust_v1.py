"""Consumer-side trust rules for LOCAL evidence (VISION_RETENTION_FIX_V2).

Two independent disciplines live here.

1. LOCAL OCR TRUST TIERS
   A lexicon guess is not a reading, and repeated passes of ONE engine over ONE
   image are not independent verification. Three fail-closed tiers:

     LOW_TRUST_OCR               — a lexicon SUBSTITUTION, insufficient local
                                   stability, or malformed evidence. Audit only.
     STABLE_LOCAL_OCR            — no semantic substitution and multiple local
                                   preprocessing passes agree. Reportable AS OCR,
                                   never architectural truth.
     INDEPENDENTLY_VERIFIED_OCR  — corroborated by a genuinely independent
                                   evidence path that ArchitectOS already has:
                                   a provider OCR claim that EXACTLY matches the
                                   local text and was CONFIRMED by the existing
                                   verifier (`verbatim_independent_local_ocr`).

   Only INDEPENDENTLY_VERIFIED_OCR may create a named space, a semantic
   function, a zone or a possible function.

   The legacy `independent_passes` field is retained for compatibility but is
   re-read as LOCAL OCR STABILITY. Same engine, same trained data, same source
   pixels ⇒ correlated, not independent.

2. LOCAL PLAN-STRUCTURE EVIDENCE
   A local reader reporting `grounded` means only that it found *some* OCR,
   opening, symbol or region, and its `single_plan` sheet type is the DEFAULT
   for any raster. The positive, non-default signals below are what may
   establish that a raster really is a plan drawing.

No detector threshold and no OCR heuristic is changed here, and no
image-specific token appears anywhere in this module.
"""

PLAN_STRUCTURE_ELEMENT_TYPES = (
    "door", "window", "opening", "stair", "duct", "shaft", "column", "axis",
)

# `level` is deliberately excluded: an elevation marker appears on facades and
# elevations too, so it is not plan-structure-specific.

MIN_STABILITY_PASSES = 2

LOW_TRUST_OCR = "LOW_TRUST_OCR"
STABLE_LOCAL_OCR = "STABLE_LOCAL_OCR"
INDEPENDENTLY_VERIFIED_OCR = "INDEPENDENTLY_VERIFIED_OCR"

OCR_TRUST_STATES = (LOW_TRUST_OCR, STABLE_LOCAL_OCR, INDEPENDENTLY_VERIFIED_OCR)

VERBATIM_LOCAL_OCR_REASON = "verbatim_independent_local_ocr"


# ------------------------------------------------------------------ OCR trust

def is_exact_transcription(label):
    """No lexicon SUBSTITUTION was applied to the reading.

    A local reader may deterministically re-orient right-to-left glyph order,
    which legitimately leaves `raw_ocr` different from `text`; that is still an
    exact reading and must keep working. What this rejects is a LEXICON
    SUBSTITUTION — `correction` — where the reader replaced what it saw with a
    different word from an architectural vocabulary.
    """

    if not isinstance(label, dict):
        return False
    if label.get("correction") is not None:
        return False
    text = label.get("text")
    return isinstance(text, str) and bool(text)


def raw_matches_text(label):
    """Diagnostic only: the published text is byte-equal to the raw OCR."""

    if not isinstance(label, dict):
        return False
    return label.get("raw_ocr") == label.get("text")


def stability_passes(label):
    """The legacy multi-pass count, read as LOCAL OCR STABILITY."""

    if not isinstance(label, dict):
        return 0
    passes = label.get("independent_passes")
    if isinstance(passes, bool) or not isinstance(passes, int):
        return 0
    return max(0, passes)


def is_stable_local_ocr(label):
    """No substitution AND several local preprocessing passes agree."""

    return (is_exact_transcription(label)
            and label.get("status") == "grounded_ocr"
            and stability_passes(label) >= MIN_STABILITY_PASSES)


def ocr_trust_state(label, independent_texts=()):
    """The fail-closed trust tier of ONE local OCR label.

    `independent_texts` is the set of texts corroborated by an INDEPENDENT
    source (see `independently_verified_ocr_texts`).
    """

    if not isinstance(label, dict) or label.get("status") != "grounded_ocr":
        return LOW_TRUST_OCR
    if not is_exact_transcription(label):
        return LOW_TRUST_OCR
    text = label.get("text")
    if isinstance(text, str) and text in set(independent_texts or ()):
        return INDEPENDENTLY_VERIFIED_OCR
    if stability_passes(label) >= MIN_STABILITY_PASSES:
        return STABLE_LOCAL_OCR
    return LOW_TRUST_OCR


def label_promotion(label, independent_texts=()):
    """(promote: bool, reason: str) — may this label name an architectural space?

    Only an INDEPENDENTLY_VERIFIED_OCR label may. Fail-closed.
    """

    state = ocr_trust_state(label, independent_texts)
    if state == INDEPENDENTLY_VERIFIED_OCR:
        return True, "independently_verified_ocr"
    if state == STABLE_LOCAL_OCR:
        return False, "stable_local_ocr_is_not_independent"
    return False, "low_trust_ocr"


def independently_verified_ocr_texts(understanding):
    """Texts corroborated by a genuinely INDEPENDENT source.

    Reuses the EXISTING verification contract: a provider OCR candidate whose
    text exactly matches a local label and which the verifier CONFIRMED as
    `verbatim_independent_local_ocr`. Provider confidence alone never qualifies,
    and same-engine pass counts never qualify.
    """

    texts = set()
    if not isinstance(understanding, dict):
        return texts
    confirmed = list(understanding.get("verified_ocr") or [])
    confirmed += [c for c in (understanding.get("grounded_provider_evidence") or [])
                  if isinstance(c, dict)
                  and (c.get("verification") or {}).get("reason") == VERBATIM_LOCAL_OCR_REASON]
    for candidate in confirmed:
        if not isinstance(candidate, dict):
            continue
        verification = candidate.get("verification") or {}
        if verification.get("reason") != VERBATIM_LOCAL_OCR_REASON:
            continue
        for evidence in verification.get("local_evidence") or []:
            if isinstance(evidence, dict) and isinstance(evidence.get("text"), str):
                texts.add(evidence["text"])
    return texts


def trusted_labels(local_plan_reading, independent_texts=()):
    """The local labels that may act as GROUNDED architectural space labels."""

    if not isinstance(local_plan_reading, dict):
        return []
    return [label for label in local_plan_reading.get("labels") or []
            if label_promotion(label, independent_texts)[0]]


def low_trust_labels(local_plan_reading, independent_texts=()):
    """The local labels retained only as LOW-TRUST OCR candidates."""

    if not isinstance(local_plan_reading, dict):
        return []
    return [label for label in local_plan_reading.get("labels") or []
            if isinstance(label, dict)
            and ocr_trust_state(label, independent_texts) == LOW_TRUST_OCR]


def low_trust_record(label, independent_texts=()):
    """A preserved OCR candidate: raw OCR + provenance, meaning only when trusted."""

    state = ocr_trust_state(label, independent_texts)
    return {
        "text": label.get("text"),
        "raw_ocr": label.get("raw_ocr"),
        "raw_matches_text": raw_matches_text(label),
        "correction": label.get("correction"),
        "match_score": label.get("match_score"),
        "ocr_confidence": label.get("ocr_confidence"),
        "confidence": label.get("confidence"),
        # LEGACY NAME, STABILITY MEANING: same engine, same pixels, correlated.
        "independent_passes": label.get("independent_passes"),
        "stability_passes": stability_passes(label),
        "bbox_pixels": label.get("bbox_pixels"),
        "bbox_normalized": label.get("bbox_normalized"),
        "evidence_type": "local_ocr",
        "status": "low_trust_ocr",
        "trust_state": state,
        "semantic_function": None,
        "zone": None,
        "promotion_reason": label_promotion(label, independent_texts)[1],
        "reasoning_source": (
            "local OCR candidate — not independently verified; retained for "
            "audit, never a space label"
        ),
    }


def stable_local_record(label):
    """A STABLE_LOCAL_OCR record: reportable as OCR, never architectural truth."""

    return {
        "text": label.get("text"),
        "raw_ocr": label.get("raw_ocr"),
        "raw_matches_text": raw_matches_text(label),
        "correction": label.get("correction"),
        "match_score": label.get("match_score"),
        "ocr_confidence": label.get("ocr_confidence"),
        "confidence": label.get("confidence"),
        "independent_passes": label.get("independent_passes"),
        "stability_passes": stability_passes(label),
        "bbox_pixels": label.get("bbox_pixels"),
        "bbox_normalized": label.get("bbox_normalized"),
        "evidence_type": "local_ocr",
        "status": "stable_local_ocr",
        "trust_state": STABLE_LOCAL_OCR,
        "semantic_function": None,
        "zone": None,
        "promotion_reason": "stable_local_ocr_is_not_independent",
        "reasoning_source": (
            "multiple passes of ONE OCR engine over ONE image agree — a "
            "stability signal, not an independent source"
        ),
    }


# ------------------------------------------------- plan-structure evidence

def local_plan_structure_evidence(local_plan_reading):
    """POSITIVE, non-default local evidence that the raster is a plan drawing.

    Selected signals and why each is positive rather than a default/fallback:

    * `plan_elements` — grounded plan-symbol ELEMENTS (door / window / opening /
      stair / duct / shaft / column / axis) whose OWN detector requirement is
      satisfied (`_local_requirement_met`). A door-swing or window-plan symbol
      with a localized raster footprint is plan topology. `level` is excluded:
      an elevation marker also appears on facades. An element whose declared
      requirement is unmet is a clue, not structure.
    * `furniture_symbols` — grounded plan-symbol FURNITURE / fixture topology
      (`grounded_plan_items`: bed / sofa / kitchen counter / sink / sanitary /
      storage / dining), which requires a localized raster patch and
      corroboration. A plan-specific symbol library hit.
    * `multi_panel` — a POSITIVE multi-panel sheet detection
      (`sheet_type` in `multi_plan` / `plan_pair`); the reader's own default is
      `single_plan`, so this is a real detection, not a fallback.

    Deliberately NOT used: `local.status` (true for any evidence), the default
    `single_plan` value, raw OCR words, lexicon-substituted labels, and
    `enclosure_geometry.regions` (a facade render produced nine of them).
    """

    signals = {
        "plan_elements": 0, "plan_element_types": {}, "furniture_symbols": 0,
        "multi_panel": False, "sheet_type": None,
    }
    if not isinstance(local_plan_reading, dict):
        return {"positive": False, "signals": signals, "families": []}

    from core.vision.local_plan_symbols_v1 import grounded_plan_items
    from core.vision.local_plan_elements_v1 import grounded_plan_elements
    from core.vision.architectural_vision_grounding_v1 import _local_requirement_met

    sheet = local_plan_reading.get("sheet_structure")
    sheet_type = sheet.get("sheet_type") if isinstance(sheet, dict) else None
    signals["sheet_type"] = sheet_type
    signals["multi_panel"] = sheet_type in ("multi_plan", "plan_pair")

    types = {}
    for element in grounded_plan_elements(local_plan_reading):
        if element.get("type") not in PLAN_STRUCTURE_ELEMENT_TYPES:
            continue
        if not _local_requirement_met(element):
            continue
        types[element["type"]] = types.get(element["type"], 0) + 1
    signals["plan_elements"] = sum(types.values())
    signals["plan_element_types"] = types

    signals["furniture_symbols"] = len(grounded_plan_items(local_plan_reading))

    families = []
    if signals["plan_elements"]:
        families.append("PLAN_ELEMENT_TOPOLOGY")
    if signals["furniture_symbols"]:
        families.append("PLAN_FURNITURE_SYMBOL_TOPOLOGY")
    if signals["multi_panel"]:
        families.append("MULTI_PANEL_STRUCTURE")

    return {"positive": bool(families), "signals": signals, "families": families}


__all__ = [
    "MIN_STABILITY_PASSES", "PLAN_STRUCTURE_ELEMENT_TYPES", "OCR_TRUST_STATES",
    "LOW_TRUST_OCR", "STABLE_LOCAL_OCR", "INDEPENDENTLY_VERIFIED_OCR",
    "VERBATIM_LOCAL_OCR_REASON", "is_exact_transcription", "raw_matches_text",
    "stability_passes", "is_stable_local_ocr", "ocr_trust_state",
    "label_promotion", "independently_verified_ocr_texts", "trusted_labels",
    "low_trust_labels", "low_trust_record", "stable_local_record",
    "local_plan_structure_evidence",
]
