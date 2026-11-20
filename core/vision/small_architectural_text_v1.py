"""W3.5 — SMALL ARCHITECTURAL TEXT RECOVERY.

The W3 label layer can read a plan whose labels are legible, but a drawing whose
room text is only a few pixels high defeats every single-pass OCR strategy: the
historical passes ask the engine once per crop, on the already-resampled panel
raster, with one binarisation, and a 2-3 px glyph simply fuses into a blob.

This module adds a *bounded* recovery path for exactly that regime:

    visible small text -> localization -> native crop -> padding
    -> bounded preprocessing variants -> bounded upscale -> OCR
    -> consolidation -> readings only

Design constraints (from the W3.5 brief):

* **Text only.**  This module never creates a semantic label, never consults a
  space vocabulary to *produce* text, and never writes a room name.  It returns
  OCR *readings* in exactly the shape the reader's existing matchers consume, so
  the W3 lexical validation (`_architectural_label_matches`, `_label_matches`)
  and the W3 enclosure association stay the only gate that can name a space.
* **Bounded and deterministic.**  Candidate count, variant count, upscale range,
  page-segmentation modes and languages are all fixed small tuples.  There is no
  unbounded scale sweep and no full-panel brute force; candidates are chosen by
  spatial order, never by OCR result.
* **Provenance.**  Every retained reading carries its source crop box, the
  native scale it was taken at, the upscale factor, the preprocessing variant,
  the OCR language, the PSM mode, the raw text, the OCR confidence, the number of
  independent variants that agreed, and the recovery provenance id.
* **No regression.**  A lexical score is used ONLY to rank candidate strings; it
  can never turn noise into a reading.  Readings still have to exist as OCR
  output with visible glyph support.

Contract: ``SmallArchitecturalTextRecoveryV1``.
"""

from __future__ import annotations

import re

import numpy as np


CONTRACT = "SmallArchitecturalTextRecoveryV1"
VERSION = "1.0"
RECOVERY_ID = "small_architectural_text_v1"

# ---- runtime policy (W3R) --------------------------------------------------
# The recovery is DISABLED by default.  Measured on the real acceptance set:
# it costs 480 OCR calls per panel (960 on the two-panel sheet D, ~+26% on
# `read_local_plan`), and produced ZERO readings that any W3 matcher accepted.
# An eligibility gate on glyph resolution was investigated and rejected as
# dishonest: crisp synthetic labels recover at a 6-7 px glyph height, while D's
# ~7 px JPEG room text does not, and the two candidate populations are
# otherwise indistinguishable in glyph height, ink darkness, contrast and
# stroke structure.  Recoverability therefore cannot be predicted from
# candidate geometry, so the capability is kept behind an explicit opt-in
# instead of being run speculatively on every sheet.
SMALL_TEXT_RECOVERY_ENABLED = False

# The smallest glyph height proven recoverable by the synthetic fixtures.
# Candidates below it must never trigger OCR even when the recovery is enabled.
SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT = 6

# ---- bounded strategy ------------------------------------------------------
# Candidate localization.
SMALL_TEXT_INK_THRESHOLD = 205
SMALL_TEXT_MAX_CANDIDATES = 12
SMALL_TEXT_MIN_GLYPH_HEIGHT = SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT
SMALL_TEXT_MIN_GLYPH_WIDTH = 8
SMALL_TEXT_MIN_AREA = 20
SMALL_TEXT_MAX_GLYPH_HEIGHT_FRACTION = 0.05

# Preprocessing variants (all applied to the padded NATIVE crop, after upscale).
# The grayscale variants are new: the historical `_ocr_crop` only ever fed a
# hard binarisation, which fuses sub-pixel strokes.
VARIANT_GRAYSCALE = "grayscale"
VARIANT_CONTRAST = "contrast_normalized_grayscale"
VARIANT_BINARY_LIGHT = "binary_threshold_light"
VARIANT_BINARY_DARK = "binary_threshold_dark"
VARIANT_ADAPTIVE = "adaptive_local_threshold"
SMALL_TEXT_VARIANTS = (
    VARIANT_GRAYSCALE,
    VARIANT_CONTRAST,
    VARIANT_BINARY_LIGHT,
    VARIANT_BINARY_DARK,
    VARIANT_ADAPTIVE,
)
SMALL_TEXT_BINARY_LIGHT_THRESHOLD = 215
SMALL_TEXT_BINARY_DARK_THRESHOLD = 190
SMALL_TEXT_ADAPTIVE_BLOCK = 21
SMALL_TEXT_ADAPTIVE_C = 10

# Bounded upscale range (a small fixed set, never a sweep).
SMALL_TEXT_UPSCALES = (10, 14)

# Bounded segmentation modes (not every PSM).
PSM_SINGLE_WORD = "single_word"
PSM_SINGLE_LINE = "single_line"
SMALL_TEXT_PSM_MODES = (PSM_SINGLE_WORD, PSM_SINGLE_LINE)

# Bounded language strategy: `eng` is compared against `fas+eng` so a Latin
# architectural term is not decided by the Persian model's glyph priors, while
# Persian support is preserved (it is never removed, only gated for agreement).
SMALL_TEXT_LANGUAGES = ("eng", "fas+eng")

# Consolidation.
SMALL_TEXT_READINGS_PER_CANDIDATE = 1
SMALL_TEXT_PERSIAN_MIN_AGREEMENT = 2
SMALL_TEXT_PERSIAN_MIN_CHARS = 3
SMALL_TEXT_MAX_TEXT_LENGTH = 24

_PROVENANCE = "small_architectural_text_recovery"


def _reader():
    """The reader owns normalisation + the lexical windows; import lazily to
    keep the import graph acyclic (the reader imports this module lazily too)."""
    from core.vision import local_plan_reader_v1 as reader

    return reader


def _alnum_count(text):
    return sum(1 for ch in text if ch.isalnum())


# ---------------------------------------------------------------------------
# 1. Localization
# ---------------------------------------------------------------------------


def _plan_box_for(gray, plan_box=None):
    if plan_box is not None:
        return [float(v) for v in plan_box]
    return [float(v) for v in _reader()._plan_bbox(gray)]


def _suppress_plan_lines(cv2, ink, plan_width, plan_height):
    """Long horizontal/vertical strokes plus bounded diagonal strokes.

    A room label may sit inside a crossed-box void; the diagonals are long and
    straight, so they are removed here as *structure*, not as glyph cleanup.
    """
    horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, int(plan_width * 0.06)), 1)),
    )
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, int(plan_height * 0.06)))),
    )
    diagonal_length = max(9, int(min(plan_width, plan_height) * 0.08))
    diagonal = np.eye(diagonal_length, dtype=np.uint8)
    diagonal_a = cv2.morphologyEx(ink, cv2.MORPH_OPEN, diagonal)
    diagonal_b = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.fliplr(diagonal))
    lines = horizontal | vertical | diagonal_a | diagonal_b
    return cv2.dilate(lines, np.ones((3, 3), np.uint8))


def localize_small_text(gray, plan_box=None, *, limit=SMALL_TEXT_MAX_CANDIDATES):
    """Deterministic text-like candidate boxes on the NATIVE crop.

    Returns a list of ``{"bbox_pixels", "glyph_height_px", "candidate_id"}``
    sorted by a spatial key (top-to-bottom, left-to-right) and capped at
    ``limit``.  No OCR runs here and no target word is consulted.
    """
    import cv2

    box = _plan_box_for(gray, plan_box)
    px0, py0, px1, py1 = (int(round(v)) for v in box)
    px0 = max(0, px0); py0 = max(0, py0)
    px1 = min(gray.shape[1], px1); py1 = min(gray.shape[0], py1)
    plan_width = max(1, px1 - px0)
    plan_height = max(1, py1 - py0)

    ink = (gray < SMALL_TEXT_INK_THRESHOLD).astype(np.uint8)
    lines = _suppress_plan_lines(cv2, ink, plan_width, plan_height)
    residual = ink & (1 - lines)
    joined = cv2.dilate(residual, np.ones((3, 5), np.uint8))

    count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    max_height = max(18, int(plan_height * SMALL_TEXT_MAX_GLYPH_HEIGHT_FRACTION))
    proposals = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if not (SMALL_TEXT_MIN_GLYPH_WIDTH <= w <= plan_width * 0.5):
            continue
        if not (SMALL_TEXT_MIN_GLYPH_HEIGHT <= h <= max_height):
            continue
        if not (SMALL_TEXT_MIN_AREA <= area <= plan_width * plan_height * 0.01):
            continue
        if x < px0 - 4 or x + w > px1 + 4 or y < py0 - 4 or y + h > py1 + 4:
            continue
        proposals.append([x, y, x + w, y + h])

    # Merge same-baseline neighbours into words (a two-word label is often split
    # into two residual components).  Purely geometric, no OCR involved.
    proposals.sort(key=lambda b: (b[1], b[0]))
    merged = []
    for candidate in proposals:
        target = None
        for entry in merged:
            entry_centre = (entry[1] + entry[3]) / 2.0
            candidate_centre = (candidate[1] + candidate[3]) / 2.0
            gap = candidate[0] - entry[2]
            if abs(entry_centre - candidate_centre) <= max(4.0, (candidate[3] - candidate[1]) * 0.6) \
                    and -4 <= gap <= max(6.0, (candidate[3] - candidate[1]) * 1.4):
                target = entry
                break
        if target is None:
            merged.append(list(candidate))
        else:
            target[2] = max(target[2], candidate[2])
            target[1] = min(target[1], candidate[1])
            target[3] = max(target[3], candidate[3])

    merged = [b for b in merged if SMALL_TEXT_MIN_GLYPH_WIDTH <= (b[2] - b[0]) <= plan_width * 0.5]
    merged.sort(key=lambda b: (b[1], b[0]))
    merged = merged[:limit]

    output = []
    for index, b in enumerate(merged):
        output.append({
            "bbox_pixels": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
            "glyph_height_px": float(b[3] - b[1]),
            "candidate_id": "st%d" % index,
        })
    return output


# ---------------------------------------------------------------------------
# 2. Preprocessing variants (bounded)
# ---------------------------------------------------------------------------


def _variant_image(cv2, upscaled, variant):
    if variant == VARIANT_GRAYSCALE:
        return upscaled
    if variant == VARIANT_CONTRAST:
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(upscaled)
    if variant == VARIANT_BINARY_LIGHT:
        return np.where(upscaled < SMALL_TEXT_BINARY_LIGHT_THRESHOLD, 0, 255).astype(np.uint8)
    if variant == VARIANT_BINARY_DARK:
        return np.where(upscaled < SMALL_TEXT_BINARY_DARK_THRESHOLD, 0, 255).astype(np.uint8)
    if variant == VARIANT_ADAPTIVE:
        return cv2.adaptiveThreshold(
            upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
            SMALL_TEXT_ADAPTIVE_BLOCK, SMALL_TEXT_ADAPTIVE_C,
        )
    raise ValueError("unknown_small_text_variant:%s" % variant)


def _psm_value(psm_mode, PSM):
    return PSM.SINGLE_WORD if psm_mode == PSM_SINGLE_WORD else PSM.SINGLE_LINE


# ---------------------------------------------------------------------------
# 3. Consolidation
# ---------------------------------------------------------------------------


def _text_plausible(text):
    """Visible-glyph plausibility only.  No lexicon, no target word."""
    compact = re.sub(r"[^0-9A-Za-z\u0600-\u06ff]+", "", text or "")
    if len(compact) < 2 or len(compact) > SMALL_TEXT_MAX_TEXT_LENGTH:
        return False
    return _alnum_count(compact) >= 2


def _lexical_plausibility(text):
    """Best similarity to a known architectural surface — RANKING ONLY.

    This never gates emission and never rewrites a reading; it exists so that,
    when several independent variants disagree, the string that looks like an
    architectural term is preferred over one that does not.
    """
    reader = _reader()
    compact = re.sub(r"[^0-9A-Za-z]+", "", (text or "").upper())
    if not compact:
        return 0.0
    best = 0.0
    for surface, _semantic in reader.ARCHITECTURAL_LABEL_LEXICON:
        best = max(best, reader._windowed_match(compact, surface))
    return round(float(best), 3)


def _script_of(text):
    persian = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")
    latin = sum(1 for ch in text if "A" <= ch.upper() <= "Z")
    if persian >= 2 and persian >= latin:
        return "persian"
    if latin >= 2:
        return "latin"
    return "other"


def _consolidate(entries):
    """Deterministically reduce a candidate's raw OCR output to a few readings.

    ``entries`` is a list of dicts each carrying ``text_key``, ``raw_text``,
    ``ocr_confidence``, ``variant``, ``language``, ``psm_mode``, ``upscale``.
    Grouping is by normalised text, so the same string recovered by several
    independent variants becomes ONE reading with an agreement count.
    """
    groups = {}
    for entry in entries:
        key = entry["text_key"]
        groups.setdefault(key, []).append(entry)

    ranked = []
    for key, items in groups.items():
        variants = {item["variant"] for item in items}
        languages = {item["language"] for item in items}
        psms = {item["psm_mode"] for item in items}
        representative = max(
            items,
            key=lambda item: (item["ocr_confidence"], -item["upscale"]),
        )
        script = _script_of(representative["raw_text"])
        if script == "persian":
            persian_chars = sum(
                1 for ch in representative["raw_text"] if "\u0600" <= ch <= "\u06ff"
            )
            if (persian_chars < SMALL_TEXT_PERSIAN_MIN_CHARS
                    or len(variants) < SMALL_TEXT_PERSIAN_MIN_AGREEMENT):
                # Persian readings are already produced by the historical path;
                # the recovery only adds one when independent variants agree on
                # a real word, so it can never inject a lone Persian fragment.
                continue
        ranked.append({
            "text_key": key,
            "representative": representative,
            "agreement": len(variants),
            "language_agreement": len(languages),
            "psm_agreement": len(psms),
            "script": script,
            "lexical": _lexical_plausibility(representative["raw_text"]),
            "confidence": representative["ocr_confidence"],
        })

    # Deterministic ranking: architectural plausibility first (a ranking hint),
    # then independent-variant agreement, then OCR confidence, then the text.
    ranked.sort(key=lambda g: (
        -g["lexical"], -g["agreement"], -g["confidence"], g["text_key"],
    ))
    return ranked[:SMALL_TEXT_READINGS_PER_CANDIDATE]


# ---------------------------------------------------------------------------
# 4. Public recovery entry point
# ---------------------------------------------------------------------------


def recovery_disabled_audit():
    """The audit recorded when the recovery is not enabled (the default)."""

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "recovery": RECOVERY_ID,
        "status": "disabled",
        "reason": "small_text_recovery_disabled",
        "candidates": 0,
        "ocr_calls": 0,
        "readings": 0,
        "variants": list(SMALL_TEXT_VARIANTS),
        "upscales": list(SMALL_TEXT_UPSCALES),
        "psm_modes": list(SMALL_TEXT_PSM_MODES),
        "languages": list(SMALL_TEXT_LANGUAGES),
    }


def recover_small_architectural_readings(
    gray, plan_box, tessdata_path, *, bbox_scale=(1.0, 1.0), limit=SMALL_TEXT_MAX_CANDIDATES,
):
    """Recover small architectural TEXT from a plan raster.

    Returns ``(readings, audit)``.  ``readings`` are shaped exactly like the
    reader's own OCR readings plus provenance, so the existing W3 matchers and
    the existing enclosure association consume them unchanged.  ``bbox_scale``
    maps the recovered boxes from the frame OCR ran in to the caller's frame
    (used when the recovery runs on the native crop of an upscaled panel).
    """
    audit = {
        "contract": CONTRACT,
        "version": VERSION,
        "recovery": RECOVERY_ID,
        "status": "unavailable",
        "candidates": 0,
        "ocr_calls": 0,
        "readings": 0,
        "variants": list(SMALL_TEXT_VARIANTS),
        "upscales": list(SMALL_TEXT_UPSCALES),
        "psm_modes": list(SMALL_TEXT_PSM_MODES),
        "languages": list(SMALL_TEXT_LANGUAGES),
        "bbox_scale": [float(bbox_scale[0]), float(bbox_scale[1])],
    }
    if gray is None or getattr(gray, "size", 0) == 0:
        return [], audit

    try:
        from tesserocr import OEM, PSM, PyTessBaseAPI
    except Exception as exc:  # pragma: no cover - environment dependent
        audit["reason"] = "%s:%s" % (type(exc).__name__, exc)
        return [], audit

    import cv2

    reader = _reader()
    if tessdata_path is None:
        tessdata_path = reader._default_tessdata_path()
    try:
        box = _plan_box_for(gray, plan_box)
    except Exception as exc:
        audit["reason"] = "%s:%s" % (type(exc).__name__, exc)
        return [], audit
    candidates = localize_small_text(gray, box, limit=limit)
    audit["candidates"] = len(candidates)
    if not candidates:
        audit["status"] = "no_candidates"
        return [], audit

    try:
        apis = {
            language: PyTessBaseAPI(
                path=str(tessdata_path), lang=language,
                psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY,
            )
            for language in SMALL_TEXT_LANGUAGES
        }
    except Exception as exc:
        audit["reason"] = "%s:%s" % (type(exc).__name__, exc)
        return [], audit

    sx, sy = float(bbox_scale[0]), float(bbox_scale[1])
    readings = []
    calls = 0
    try:
        for candidate in candidates:
            x0, y0, x1, y1 = (int(round(v)) for v in candidate["bbox_pixels"])
            pad = max(2, int(round(0.35 * max(x1 - x0, y1 - y0))))
            nx0 = max(0, x0 - pad); ny0 = max(0, y0 - pad)
            nx1 = min(gray.shape[1], x1 + pad); ny1 = min(gray.shape[0], y1 + pad)
            crop = gray[ny0:ny1, nx0:nx1]
            if crop.size < 20:
                continue
            entries = []
            for upscale in SMALL_TEXT_UPSCALES:
                upscaled = cv2.resize(
                    crop, (crop.shape[1] * upscale, crop.shape[0] * upscale),
                    interpolation=cv2.INTER_CUBIC,
                )
                for variant in SMALL_TEXT_VARIANTS:
                    image = _variant_image(cv2, upscaled, variant)
                    for language, api in apis.items():
                        for psm_mode in SMALL_TEXT_PSM_MODES:
                            api.SetPageSegMode(_psm_value(psm_mode, PSM))
                            api.SetImageBytes(
                                image.tobytes(), image.shape[1], image.shape[0], 1, image.shape[1],
                            )
                            api.SetSourceResolution(300)
                            api.Recognize()
                            calls += 1
                            raw = " ".join((api.GetUTF8Text() or "").split())
                            if not raw or not _text_plausible(raw):
                                continue
                            compact = re.sub(r"[^0-9A-Za-z\u0600-\u06ff]+", "", raw)
                            entries.append({
                                "text_key": compact.upper(),
                                "raw_text": raw,
                                "ocr_confidence": round(max(0.0, min(100.0, float(api.MeanTextConf()))), 1),
                                "variant": variant,
                                "language": language,
                                "psm_mode": psm_mode,
                                "upscale": upscale,
                                "bbox_pixels": [float(nx0), float(ny0), float(nx1), float(ny1)],
                            })
            for group in _consolidate(entries):
                representative = group["representative"]
                native_box = representative["bbox_pixels"]
                mapped = [
                    round(native_box[0] * sx, 1), round(native_box[1] * sy, 1),
                    round(native_box[2] * sx, 1), round(native_box[3] * sy, 1),
                ]
                readings.append({
                    "raw_text": representative["raw_text"],
                    "ocr_confidence": representative["ocr_confidence"],
                    "bbox_pixels": mapped,
                    "pass": "smalltext_%s_%s_s%d_%s" % (
                        candidate["candidate_id"], representative["variant"],
                        representative["upscale"], representative["psm_mode"],
                    ),
                    # provenance
                    "source_crop_bbox": [float(v) for v in native_box],
                    "source_bbox_frame": "native_panel_pixels",
                    "native_glyph_height_px": round(candidate["glyph_height_px"], 1),
                    "upscale": representative["upscale"],
                    "preprocessing_variant": representative["variant"],
                    "ocr_language": representative["language"],
                    "psm_mode": representative["psm_mode"],
                    "independent_variants": group["agreement"],
                    "language_agreement": group["language_agreement"],
                    "psm_agreement": group["psm_agreement"],
                    "lexical_plausibility": group["lexical"],
                    "script": group["script"],
                    "recovery": RECOVERY_ID,
                    "recovery_provenance": _PROVENANCE,
                })
    finally:
        for api in apis.values():
            try:
                api.End()
            except Exception:
                pass

    audit["ocr_calls"] = calls
    audit["readings"] = len(readings)
    audit["status"] = "analyzed"
    return readings, audit


__all__ = [
    "CONTRACT",
    "VERSION",
    "RECOVERY_ID",
    "SMALL_TEXT_RECOVERY_ENABLED",
    "SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT",
    "SMALL_TEXT_VARIANTS",
    "SMALL_TEXT_UPSCALES",
    "SMALL_TEXT_PSM_MODES",
    "SMALL_TEXT_LANGUAGES",
    "localize_small_text",
    "recovery_disabled_audit",
    "recover_small_architectural_readings",
]
