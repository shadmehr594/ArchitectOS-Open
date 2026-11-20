# ==========================================================
# ArchitectOS Vision Observation Mode v1
#
# VISION_OBSERVATION_MODE_SEPARATION_V1
#
# THE AUDIT (see the report for the full trace)
#
#   ImageUnderstandingV1
#           |
#   ArchitecturalVisionGroundingV1      (what the evidence supports)
#           |
#   ArchitecturalVisionInterpreterV1    (what space this could be)
#           |
#   ResponseAdapter                     (one message shape for all of it)
#
# The image path had exactly ONE output shape for EVERY image turn: the
# architectural interpretation, which always carries `space_type`,
# `architectural_interpretation`, `spatial_relations` and
# `possible_function`. So
#
#   "فقط عناصر قابل مشاهده تصویر را لیست کن"
#
# was answered with "1. Possible architectural space: master bedroom …" —
# the observation layer and the interpretation layer were fused into one
# contract and one message.
#
# THIS MODULE is the observation layer, on its own:
#
#   * it answers ONLY "what is visibly present in the image?"
#   * it never classifies a space, never names a function, never reasons
#     about privacy, zoning, circulation or design intent
#   * it reuses the grounded evidence of the previous phase, so it cannot
#     resurrect a claim the grounding rejected
#   * it is READ-ONLY and adds no provider call, no render and no network
#
# Observation  ->  Interpretation  ->  Architectural reasoning  ->  Design
# ==========================================================


from __future__ import annotations


CONTRACT = "VisionObservationV1"

VERSION = "1.0"

MODE = "OBSERVATION"


# ----------------------------------------------------------
# THE REQUEST  (two-part detection, like the language switch)
#
# An observation request needs BOTH a "list / only" marker AND an
# explicit visible-evidence phrase. "این تصویر را فقط تحلیل کن" is an
# ANALYZE request — "فقط" alone must never turn it into observation mode.
# ----------------------------------------------------------

LIST_MARKERS = (
    "لیست", "فهرست", "بشمار", "شمارش", "چه چیزهایی", "چی میبینی",
    "چی می‌بینی", "enumerate", "list", "itemise", "itemize",
)


VISIBLE_EVIDENCE = (
    "قابل مشاهده", "قابل دیدن", "دیده می‌شود", "دیده میشه", "دیده شده",
    "مشهود", "عینی", "شواهد تصویری", "شواهد", "عناصر تصویر",
    # W4.2A-8 — ordinary Persian phrasings of an observation request.
    # "مشاهدات معماری را کامل گزارش بده / مشاهده را از تفسیر جدا کن" is an
    # observation request, but neither "مشاهده" nor "مشاهدات" was a marker, so
    # the whole turn fell through to the interpretation path and the
    # observation layer was never reached.
    "مشاهدات", "مشاهده", "شاهد تصویری", "مشاهدات معماری",
    "visible", "visibly", "observed", "visually present",
    "visible evidence", "visible elements",
)


# W4.2A-8 — the user may ask for observation AND interpretation in one turn.
# The observation layer must still answer observation-only; the interpretation
# section is a SEPARATE, hedged block, and only when explicitly requested.
INTERPRETATION_MARKERS = (
    "تفسیر", "تفسیر معماری", "interpretation", "interpret",
)

INTERPRETATION_NEGATIONS = (
    "تفسیر نکن", "تفسیر نکنید", "بدون تفسیر", "تفسیر نمی‌خوام",
    "no interpretation", "without interpretation", "don't interpret",
)


def detect_interpretation_request(text):

    """Is the user ALSO asking for an architectural interpretation?

    Deterministic and negation-aware: "تفسیر نکن" / "بدون تفسیر" must never
    turn an observation-only turn into an interpretation turn.
    """

    form = " ".join(str(text or "").lower().split())

    if not form:

        return False

    if any(marker in form for marker in INTERPRETATION_NEGATIONS):

        return False

    return any(marker in form for marker in INTERPRETATION_MARKERS)


ONLY_MARKERS = (
    "فقط", "تنها", "صرفا", "صرفاً",
    "بدون تفسیر", "بدون تحلیل", "بدون دسته‌بندی", "بدون استدلال",
    "تفسیر نکن", "تحلیل نکن", "فقط مشاهده",
    "only", "just", "without interpretation", "no interpretation",
    "observation only",
)


EXPLICIT_MODE_MARKERS = (
    "حالت مشاهده", "مشاهده محض", "فقط مشاهده",
    "observation mode", "observation only", "observe only",
)


def _language(value):

    """The canonical reply language: "fa" or "en".

    VISION_OBSERVATION_MODE_SEPARATION_V1 — the response declares
    `output_language: "persian"`, and the PREVIOUS phase's renderer
    (`vision_report_v1._language`) already accepts `persian` / `farsi` /
    `ir` next to `fa`. This module must use the same normaliser, or a
    Persian observation request is answered in English — which is exactly
    the defect VISION_REPORT_LANGUAGE_01 fixed for the interpretation
    path. One owner for the decision, and it accepts every spelling the
    pipeline actually emits.
    """

    text = str(value or "").strip().lower()

    if (
        text.startswith("fa")
        or text.startswith("persian")
        or text in ("ir", "farsi")
    ):

        return "fa"

    return "en"


def detect_observation_request(text):

    """Is this message asking for OBSERVATION ONLY?

    Deterministic, two-part: an explicit mode marker, or a
    visible-evidence phrase combined with a list / only marker.
    """

    form = " ".join(str(text or "").lower().split())

    if not form:

        return False

    if any(marker in form for marker in EXPLICIT_MODE_MARKERS):

        return True

    if not any(marker in form for marker in VISIBLE_EVIDENCE):

        return False

    return any(
        marker in form for marker in LIST_MARKERS
    ) or any(
        marker in form for marker in ONLY_MARKERS
    )


# ----------------------------------------------------------
# CONFIDENCE — the evidence hierarchy of the brief
#
#   highest : a visible object in the image
#   medium  : a clear spatial symbol
#   low     : an inference  (never evidence, never listed as an element)
# ----------------------------------------------------------

CONFIDENCE_HIGH = "high"

CONFIDENCE_MEDIUM = "medium"

CONFIDENCE_NOT_CONFIRMED = "not confirmed"

CONFIDENCE_UNKNOWN = "unknown"


# ----------------------------------------------------------
# CHAT_OBSERVATION_ATTRIBUTION_PARITY_V1
#
# The attributed band publishes a provider claim that nothing independently
# corroborated. The verifier records WHY a claim stayed UNVERIFIED, and two of
# those reasons mean the same thing for this band: the claim passed every
# safety gate and was never corroborated. `claim_properties_not_verified` is
# the descriptive wording case — "top level has arched-top windows" is rejected
# only for DESCRIBING the kind instead of naming it.
#
# `image_understanding_v1` already admits both reasons into the architectural
# evidence the report layer reads. Admitting only the first here made the same
# claim visible in the report and invisible to the chat observation contract.
# The set is deliberately TWO reasons, not "any UNVERIFIED claim": AMBIGUOUS,
# negated, interpretive, unknown and rejected claims stay excluded by the gates
# around this set.
# ----------------------------------------------------------

ATTRIBUTABLE_REASONS = (
    "no_applicable_independent_corroboration",
    "claim_properties_not_verified",
)


ASSERTION_MARKERS = (
    "visible", "visibly", "seen", "shown", "present",
    "دیده می‌شود", "دیده میشه", "دیده شده", "مشهود", "قابل مشاهده",
)


def _asserted(phrase):

    form = " ".join(str(phrase or "").lower().split())

    return any(marker in form for marker in ASSERTION_MARKERS)


def _confidence_for(status, evidence):

    """`high` / `medium` / `not confirmed` for one grounded element.

    The brief's hierarchy grades by EVIDENCE CLASS, not by the provider's
    spelling: a visible object in the image is highest, a clear spatial
    symbol is MEDIUM, and an inference is never evidence.

    The class is already decided by the grounding layer — `visible` means
    the provider's own OBSERVATION field stated the element as an object.
    Grading the PHRASE again (so `bed visible` scored high while a bare
    `bed` scored medium) made the confidence depend on whether the model
    happened to write the word "visible": a spelling artefact, not
    evidence strength. The raw signal is still recorded per element as
    `explicit_assertion`, so nothing is lost.
    """

    if status == "visible":

        local = [claim for claim in evidence
                 if claim.get("source") in ("local_raster_symbol_topology", "local_raster_geometry")]
        if local and any(claim.get("confidence") != "HIGH" for claim in local):
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_HIGH

    if status == "symbol_reading":

        return CONFIDENCE_MEDIUM

    return CONFIDENCE_NOT_CONFIRMED


SUPPORTING_CLASSES = ("object", "symbol", "mention")


def _supporting_claims(evidence):

    """The claims that actually SUPPORT the element's reported status.

    The grounding layer's own contract says a `label` is "only inside a
    visible text label" — visible TEXT, not the element — so a text label
    inside the image is not evidence that the element is present. A
    `negated` phrase is a contradiction, and it is already reported as
    such in `unknowns`. An `inferred` claim is never evidence.

    This is not a cosmetic filter: surfacing the label put the image's
    own wording ("حریم خصوصی در اتاق والدین") into an OBSERVATION answer,
    which the brief forbids — the observation layer must not emit privacy
    vocabulary. (The label had also been attached to `entrance` by a
    homograph: the preposition "در" inside the label matched the element
    alias "در" = door.)
    """

    supported = [
        claim for claim in evidence
        if claim.get("class") in SUPPORTING_CLASSES
        and claim.get("source") != "provider_only"
    ]
    local = [claim for claim in supported
             if claim.get("source") in ("local_raster_geometry", "local_raster_symbol_topology")]
    return local or supported


# ==========================================================
# W4.2A-8 — PRESENTATION LAYER
#
# The machine-readable evidence IDs stay EXACTLY as they are inside the
# structured contract (`elements[].evidence`); nothing is renamed or
# destroyed. This layer only decides how a tag is SHOWN to a human, so that
# an internal identifier never reaches normal UI prose, and a door is never
# shown as an entrance.
# ==========================================================

GENERIC_TAG_FA = "شاهد هندسی محلی"
GENERIC_TAG_EN = "local geometric evidence"

TAG_TRANSLATIONS = {

    # ---- door / opening raster cues ----
    "localized_swing_arc": ("قوس بازشدن در", "localized swing arc"),
    "leaf_segment": ("لنگه‌ی در", "door leaf segment"),
    "two_wall_jambs": ("دو لبه‌ی بازشو در دیوار", "two wall jambs"),
    "opening_gap_repair": ("ترمیم شکاف بازشو در دیوار", "opening gap repair"),

    # ---- window / glazing raster cues ----
    "parallel_glazing_rails": ("خطوط موازی شیشه", "parallel glazing rails"),
    "thick_wall_flanks": ("دیوار ضخیم دو طرف بازشو", "thick wall flanks"),
    "perimeter_wall_band": ("نوار دیوار محیطی", "perimeter wall band"),
    "thin_nonempty_perimeter_interruption": (
        "وقفه‌ی باریک در دیوار محیطی", "thin perimeter interruption"),
    "historical_local_raster_window": (
        "پنجره‌ی خوانده‌شده از تصویر", "raster window reading"),

    # ---- walls / enclosure ----
    "thick_wall_boundaries": ("مرزهای دیوار ضخیم", "thick wall boundaries"),
    "bounded_free_raster_region": (
        "ناحیه‌ی محصور در تصویر", "bounded free raster region"),

    # ---- furniture / fixtures ----
    "kitchen sink arrangement": ("چیدمان سینک آشپزخانه", "kitchen sink arrangement"),
    "kitchen counter": ("کانتر آشپزخانه", "kitchen counter"),
    "localized_sink_arrangement": ("چیدمان سینک", "localized sink arrangement"),
    "paired_rectangular_bowls": ("دو حوضچه‌ی مستطیلی", "paired rectangular bowls"),
    "aligned_bowl_rims": ("لبه‌های هم‌راستای حوضچه‌ها", "aligned bowl rims"),
    "surrounding_counter_runs": ("کانترهای پیرامون", "surrounding counter runs"),
    "horizontal_counter_run": ("کانتر افقی", "horizontal counter run"),
    "vertical_counter_run": ("کانتر عمودی", "vertical counter run"),
    "closed_mattress_outline": ("خط بسته‌ی تشک", "closed mattress outline"),
    "closed_upholstered_outline": ("خط بسته‌ی مبلمان", "closed upholstered outline"),
    "aligned_seat_row": ("ردیف صندلی هم‌راستا", "aligned seat row"),
    "terminal_pillow_compartment": ("محفظه‌ی بالش", "terminal pillow compartment"),
    "repeated_mattress_cells": ("سلول‌های تکرارشده‌ی تشک", "repeated mattress cells"),

    # ---- stair / vertical circulation ----
    "regular_parallel_riser_lines": (
        "خطوط موازی و منظم پله", "regular parallel riser lines"),
    "bounded_stair_run": ("مسیر پله‌ی محدودشده", "bounded stair run"),
    "localized_direction_arrow": ("فلش جهت حرکت", "localized direction arrow"),
    "two_outer_stringers": ("دو تیر کناری پله", "two outer stringers"),
    "intermediate_flight_separator": (
        "جداکننده‌ی میان‌پله", "intermediate flight separator"),
    "core_shaft_or_void": ("چاهک یا فضای خالی مرکزی", "core shaft or void"),
    "compact_enclosed_core_void": (
        "فضای خالی محصور مرکزی", "compact enclosed core void"),
    "crossed_diagonal_void_symbol": (
        "نماد ضربدری فضای خالی", "crossed diagonal void symbol"),

    # ---- drawing / sheet ----
    "independent_long_line_cluster": (
        "خوشه‌ی خطوط بلند مستقل", "independent long line cluster"),
    "substantial_drawing_extent": ("گستره‌ی قابل‌توجه ترسیم", "substantial drawing extent"),
    "interior_partition_activity": ("فعالیت تیغه‌های داخلی", "interior partition activity"),
    "whitespace_gutter": ("فاصله‌ی سفید میان دو نقشه", "whitespace gutter"),
    "normalized_footprint": ("ردپای نرمال‌شده", "normalized footprint"),
    "bidirectional_major_partition_match": (
        "تطابق دوطرفه‌ی تیغه‌های اصلی", "bidirectional major partition match"),
    "stable_at_two_thresholds": ("پایدار در دو آستانه", "stable at two thresholds"),
    "stable_across_gap_scales": ("پایدار در مقیاس‌های شکاف", "stable across gap scales"),
    "independent_thresholds": ("آستانه‌های مستقل", "independent thresholds"),
    "paired_flight_context": ("زمینه‌ی پله‌ی جفتی", "paired flight context"),
}


# A local symbol/element class that is NOT a room function. Used so the
# observation says what was SEEN, never what the room "is".
KIND_LABELS = {

    "door": ("در", "door"),
    "window": ("پنجره", "window"),
    "opening": ("بازشو", "opening"),
    "stair": ("پله / عنصر گردش عمودی", "stair / vertical circulation"),
    "duct": ("داکت / شفت", "duct / shaft"),
    "shaft": ("چاهک / آسانسور", "shaft / elevator"),
    "column": ("ستون", "column"),
    "axis": ("محور شبکه", "grid axis"),
    "level": ("نشانه‌ی تراز", "level marker"),

    "bed": ("تخت", "bed"),
    "sofa": ("مبل", "sofa"),
    "seating": ("نشیمن", "seating"),
    "chair": ("صندلی", "chair"),
    "dining_surface": ("میز ناهارخوری", "dining surface"),

    "kitchen_counter": ("کانتر آشپزخانه", "kitchen counter"),
    "kitchen_sink_arrangement": (
        "تجهیز آشپزخانه (سینک/کانتر)", "kitchen sink / counter arrangement"),
    "sanitary_fixture": ("تجهیز بهداشتی", "sanitary fixture"),
    "storage_cabinet": ("کابینت/قفسه", "storage cabinet"),
}


def _translate_tag(tag, language):

    """One internal evidence tag as human prose (never the raw tag)."""

    form = " ".join(str(tag or "").strip().split())

    if not form:

        return ""

    pair = TAG_TRANSLATIONS.get(form)

    if not pair:

        pair = TAG_TRANSLATIONS.get(form.lower())

    if not pair:

        return GENERIC_TAG_FA if str(language).startswith("fa") else GENERIC_TAG_EN

    return pair[0] if str(language).startswith("fa") else pair[1]


def _translate_evidence(phrases, language):

    """Translate a list of raw evidence phrases, preserving the ORDER.

    The raw phrases are never mutated — they stay in the structured
    contract. Untranslated tags degrade to a generic phrase, never to the
    raw identifier.
    """

    out = []

    for phrase in phrases or []:

        for part in str(phrase or "").replace(" · ", "; ").split(";"):

            part = part.strip()

            if not part:

                continue

            text = _translate_tag(part, language)

            if text and text not in out:

                out.append(text)

    return out


def _presentation(element_id, evidence):

    """(observed_kind, label_fa, label_en) for one grounded element.

    W4.2A-8 — the grounding vocabulary is deliberately coarse: a locally
    read DOOR is folded into `entrance`, and a locally read counter/sink is
    folded into `kitchen`. The observation must present what was actually
    seen, so the LOCAL element subtype carried on the claims wins over the
    coarse element id. Nothing is promoted: this only ever makes the label
    MORE specific and LESS certain.
    """

    kinds = [
        claim.get("element_type")
        for claim in evidence or []
        if claim.get("element_type")
    ]

    order = ("door", "stair", "duct", "shaft", "column", "axis", "level",
             "window", "opening",
             "kitchen_sink_arrangement", "kitchen_counter",
             "sanitary_fixture", "storage_cabinet",
             "dining_surface", "bed", "sofa", "seating", "chair")

    for kind in order:

        if kind in kinds:

            pair = KIND_LABELS.get(kind)

            if pair:

                return kind, pair[0], pair[1]

    return element_id, None, None


def _display_label(entry, language):

    """The presentation label for a rendered element, or None."""

    if str(language).startswith("fa"):

        return entry.get("display_label_fa")

    return entry.get("display_label_en")


def _evidence_for(evidence, language):

    """The provider's own phrases, verbatim — the observation's evidence."""

    phrases = []

    for claim in _supporting_claims(evidence):

        phrase = claim.get("phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    return phrases


def _label(element_id, language):

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            element_label,
        )

        return element_label(element_id, language)

    except Exception:

        return str(element_id or "")


def _grounding_for(understanding, space_type=None):

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            ground_vision_evidence,
        )

        return ground_vision_evidence(
            understanding, space_type=space_type
        )

    except Exception:

        return None


def _reason(code, fallback, language):

    """A localised reason for a claim that was not promoted."""

    table = {

        "inference": (
            "استنباط است، نه مشاهده — عنصر استنباط‌شده شاهد تصویری نیست",
            "inference, not observation — never visible evidence",
        ),

        "mention_only": (
            "فقط در فهرست عناصر آمده و در مشاهدهٔ مدل تأیید نشده است",
            "listed in the element list, but not stated in the observation",
        ),

        "symbol_reading": (
            "به‌عنوان نماد نقشه خوانده شده — نمادها ممکن است ناقص باشند",
            "read as a plan symbol — plan symbols may be incomplete",
        ),

        "no_region_grounding": (
            "مدل بینایی نمی‌تواند ناحیهٔ تصویر را مشخص کند",
            "the provider cannot ground pixel regions",
        ),

    }

    pair = table.get(code)

    if not pair:

        return fallback or ""

    return pair[0] if str(language).startswith("fa") else pair[1]


# ==========================================================
# THE OBSERVATION
# ==========================================================

# ==========================================================
# W4.2A-8 — GROUNDED CATEGORY COVERAGE
#
# Observation-only must not mean "three strongest objects". Every category
# that the LOCAL, provider-independent raster evidence genuinely established
# is eligible for the report. Nothing is invented here: each category is
# built only from the already-validated local contracts, and an empty
# category is omitted (never shown as an empty claim).
# ==========================================================

CATEGORY_ORDER = (
    "geometry", "openings", "vertical_circulation", "structure",
    "furniture", "text", "stable_local_ocr", "low_trust_ocr",
)


def _grounded_categories(understanding):

    """Grounded local categories, by evidence class. Read-only."""

    local = (understanding or {}).get("local_plan_reading")

    if not isinstance(local, dict):

        return {}

    try:

        from core.vision.local_plan_elements_v1 import grounded_plan_elements
        from core.vision.local_plan_symbols_v1 import grounded_plan_items

    except Exception:

        return {}

    by_type = {}

    try:

        from core.vision.architectural_vision_grounding_v1 import _local_requirement_met

    except Exception:

        _local_requirement_met = lambda _item: True

    for entry in grounded_plan_elements(local):

        # VISION_END_TO_END_RETENTION_FIX_V1 — a local element whose own
        # detector declares an UNSATISFIED requirement is a clue, never a
        # grounded category member.
        if not _local_requirement_met(entry):

            continue

        key = entry.get("type")

        if key:

            by_type[key] = by_type.get(key, 0) + 1

    by_class = {}

    for item in grounded_plan_items(local):

        key = item.get("class")

        if key:

            by_class[key] = by_class.get(key, 0) + 1

    categories = {}

    # ---- geometry / enclosed regions (distinct from semantic rooms) ----
    enclosure = local.get("enclosure_geometry") or {}

    regions = enclosure.get("regions") or []

    if regions:

        categories["geometry"] = {
            "region_count": len(regions),
            "count_status": enclosure.get("count_status"),
            "multiple_spaces": enclosure.get("multiple_spaces"),
            "provenance": "LOCAL_RASTER",
        }

    # ---- openings ----
    openings = {k: v for k, v in by_type.items() if k in ("window", "door", "opening")}

    if openings:

        categories["openings"] = {"counts": openings, "provenance": "LOCAL_RASTER"}

    # ---- vertical circulation ----
    vertical = {k: v for k, v in by_type.items() if k in ("stair", "duct", "shaft")}

    if vertical:

        categories["vertical_circulation"] = {
            "counts": vertical, "provenance": "LOCAL_RASTER",
        }

    # ---- structural-looking elements / axes / levels ----
    structure = {k: v for k, v in by_type.items() if k in ("column", "axis", "level")}

    if structure:

        categories["structure"] = {"counts": structure, "provenance": "LOCAL_RASTER"}

    # ---- furniture / fixtures (evidence in its own right) ----
    if by_class:

        categories["furniture"] = {
            "counts": by_class, "provenance": "LOCAL_SYMBOL_READER",
        }

    # ---- grounded OCR text / labels ----
    from core.vision.local_evidence_trust_v1 import (
        INDEPENDENTLY_VERIFIED_OCR, STABLE_LOCAL_OCR,
        independently_verified_ocr_texts, ocr_trust_state, stability_passes,
    )

    independent_texts = independently_verified_ocr_texts(understanding)

    labels = []

    stable = []

    low_trust = []

    for label in local.get("labels") or []:

        if not isinstance(label, dict):

            continue

        # VISION_RETENTION_FIX_V2 — only an INDEPENDENTLY verified reading is
        # presented as grounded text. A stable multi-pass reading of ONE engine
        # over ONE image is reported separately as OCR only, and a lexicon
        # substitution is an unverified OCR candidate.
        state = ocr_trust_state(label, independent_texts)

        if state == INDEPENDENTLY_VERIFIED_OCR:

            labels.append({
                "text": label.get("text"),
                "semantic_function": label.get("semantic_function"),
                "confidence": label.get("confidence"),
                "ocr_confidence": label.get("ocr_confidence"),
                "trust_state": state,
            })

        elif state == STABLE_LOCAL_OCR:

            stable.append({
                "text": label.get("text"),
                "raw_ocr": label.get("raw_ocr"),
                "correction": label.get("correction"),
                "match_score": label.get("match_score"),
                "ocr_confidence": label.get("ocr_confidence"),
                "stability_passes": stability_passes(label),
                "bbox_pixels": label.get("bbox_pixels"),
                "trust_state": state,
            })

        elif label.get("status") == "grounded_ocr":

            low_trust.append({
                "text": label.get("text"),
                "raw_ocr": label.get("raw_ocr"),
                "correction": label.get("correction"),
                "match_score": label.get("match_score"),
                "ocr_confidence": label.get("ocr_confidence"),
                "stability_passes": stability_passes(label),
                "bbox_pixels": label.get("bbox_pixels"),
                "trust_state": state,
            })

    if labels:

        categories["text"] = {"labels": labels, "provenance": "LOCAL_OCR"}

    if stable:

        categories["stable_local_ocr"] = {
            "labels": stable, "provenance": "LOCAL_OCR",
        }

    if low_trust:

        categories["low_trust_ocr"] = {
            "labels": low_trust, "provenance": "LOCAL_OCR",
        }

    return categories


# W4.2A-8 — interpretation vocabulary. A Persian request must get Persian
# interpretation prose; a phrase with no Persian name is DROPPED rather than
# leaked in English.
SPACE_NAME_FA = {
    "bedroom": "اتاق خواب",
    "master bedroom": "اتاق خواب مستر",
    "living room": "نشیمن/پذیرایی",
    "kitchen": "آشپزخانه",
    "bathroom": "سرویس بهداشتی",
    "corridor": "راهرو",
    "entrance": "ورودی",
    "balcony": "بالکن",
    "dining": "ناهارخوری",
    "garden": "محوطه",
    "storage": "انباری",
    "study": "اتاق کار",
    "enclosed region": "فضای محصور",
    "private room": "فضای شخصی‌تر",
    "circulation": "مسیر گردش",
}


def _possible_phrase(value, lang):

    """One interpretation phrase as a HEDGED, localised possibility."""

    text = " ".join(str(value or "").strip().split())

    if not text:

        return None

    lowered = text.lower()

    # The interpreter spells possibilities as "possible <space> function".
    for prefix in ("possible ", "probable ", "likely "):

        if lowered.startswith(prefix):

            text = text[len(prefix):]

            lowered = text.lower()

            break

    for suffix in (" function", " space", " room"):

        if lowered.endswith(suffix):

            text = text[: -len(suffix)]

            lowered = text.lower()

            break

    text = text.strip()

    if not str(lang).startswith("fa"):

        return "possible %s" % text if text else None

    name = SPACE_NAME_FA.get(lowered) or SPACE_NAME_FA.get(text)

    if not name:

        return None

    return "احتمالاً %s" % name


def build_interpretation_section(understanding, language="fa"):

    """A SEPARATE, hedged interpretation block — only when asked for.

    W4.2A-8 — observation and interpretation stay two distinct sections.
    Every line is a possibility, never a fact.
    """

    try:

        from core.vision.architectural_vision_interpreter_v1 import (
            interpret_architectural_vision,
        )

        interpretation = interpret_architectural_vision(understanding)

    except Exception:

        return None

    if not isinstance(interpretation, dict):

        return None

    lang = _language(language)

    items = []

    space_type = interpretation.get("space_type")

    if space_type and str(space_type).lower() not in ("plan", "unknown", "none"):

        items.append(_possible_phrase(space_type, lang))

    for value in interpretation.get("possible_function") or []:

        phrase = _possible_phrase(value, lang)

        if phrase and phrase not in items:

            items.append(phrase)

    items = [item for item in items if item]

    if not items:

        return None

    return {
        "requested": True,
        "items": items[:12],
        "certainty": "possibility",
        "source": "ARCHITECTURAL_INTERPRETATION",
        "separate_from": "observation",
    }


def build_observation(understanding, grounding=None, language="fa",
                      include_interpretation=False):

    """The OBSERVATION contract: visible evidence only, or None.

    No space type, no function, no interpretation, no relations, no
    design reasoning. Nothing is invented: an element that was never
    reported is not listed, and an unconfirmed claim keeps its evidence
    and says so.
    """

    if not isinstance(understanding, dict):

        return None

    lang = _language(language)

    evidence_available = True

    if not isinstance(grounding, dict):

        grounding = _grounding_for(understanding)

    if not isinstance(grounding, dict):

        grounding = {}

        evidence_available = False

    elements = []

    unknowns = []

    for entry in grounding.get("elements") or []:

        element_id = entry.get("element")

        status = entry.get("status")

        evidence = entry.get("evidence") or []

        if status in ("visible", "symbol_reading"):

            supporting = _supporting_claims(evidence)

            # W4.2A-8 — present what was SEEN. A locally read door is shown
            # as a door (never as an entrance) and a counter/sink as kitchen
            # equipment (never as a certain kitchen). The coarse element id
            # and the raw evidence stay untouched in the contract.
            observed_kind, display_fa, display_en = _presentation(
                element_id, evidence
            )

            elements.append({

                "name": element_id,

                "label": _label(element_id, lang),

                "observed_kind": observed_kind,

                "display_label_fa": display_fa,

                "display_label_en": display_en,

                "evidence": _evidence_for(evidence, lang),

                "confidence": _confidence_for(status, evidence),

                "evidence_class": (
                    "visible object" if status == "visible"
                    else "spatial symbol"
                ),

                "status": status,

                # The raw signal, kept beside the graded confidence: did
                # the provider's own phrase say the word "visible"?
                "explicit_assertion": any(
                    _asserted(claim.get("phrase")) for claim in evidence
                ),

                "source_field": (
                    supporting[0].get("field") if supporting else None
                ),

            })

        elif status == "denied":

            unknowns.append({

                "name": element_id,

                "label": _label(element_id, lang),

                "status": "stated as not visible",

                "confidence": CONFIDENCE_NOT_CONFIRMED,

            })

    # A claim that was never promoted is reported as NOT CONFIRMED, with
    # the reason — never silently dropped, never upgraded. An element that
    # DID make the element list (a symbol reading) is not repeated here.
    listed = {entry.get("name") for entry in elements}

    rejected = []

    for claim in grounding.get("rejected_claims") or []:

        if not claim.get("element") or claim.get("element") in listed:

            continue

        rejected.append({

            "name": claim.get("element"),

            "label": _label(claim.get("element"), lang),

            "phrase": claim.get("phrase"),

            "reason": _reason(
                claim.get("reason_code"), claim.get("reason"), lang
            ),

            "reason_code": claim.get("reason_code"),

        })

    # ==================================================
    # VISION_EVIDENCE_PROVENANCE_V1 — THE ATTRIBUTED BAND
    #
    # `elements` stays strict: only locally grounded visible evidence may
    # enter it. The provider's ASSERTED observations are NOT promoted into
    # it — they are published here, with their own verbatim quote and a
    # `not confirmed` confidence.
    #
    # Before this band existed, a photograph whose vision model asserted
    # "curved concrete balcony slab" produced `elements: []` and the reply
    # "no visible element was reported" — which was FALSE. Three different
    # situations (model saw nothing / model asserted but nothing
    # corroborated it / model never ran) all rendered as that one sentence.
    # ==================================================

    attributed = []

    seen_attributed = set()

    for candidate in understanding.get("provider_candidates") or []:

        if not isinstance(candidate, dict):

            continue

        if candidate.get("state") != "UNVERIFIED":

            continue

        reason = (candidate.get("verification") or {}).get("reason")

        if reason not in ATTRIBUTABLE_REASONS:

            continue

        if candidate.get("certainty") != "ASSERTED":

            continue

        # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — a POSITIVE attributed
        # observation must be an affirmative presence. The band admitted any
        # claim that cleared the state/reason/certainty gates, so a claim the
        # verifier recorded as ABSENT ("no parapet", "No stairs, lifts, or
        # other vertical circulation elements are visible") was published as a
        # reported observation. ABSENT is evidence of absence and belongs in
        # its own band; UNKNOWN is not presence either. Both are withheld here
        # and republished below, never discarded.
        if candidate.get("polarity") != "PRESENT":

            continue

        text = str(candidate.get("text") or "").strip()

        if not text or text.lower() in seen_attributed:

            continue

        seen_attributed.add(text.lower())

        attributed.append({

            "name": text,
            "label": text,

            "kind": candidate.get("kind"),
            "category": candidate.get("category"),

            "evidence": candidate.get("source_quote") or text,

            "evidence_class": "provider observation (unconfirmed)",

            "confidence": CONFIDENCE_NOT_CONFIRMED,

            "status": "reported, not independently confirmed",

            "source": "provider",

            # the verifier's OWN reason for this claim, not a constant: the
            # band now admits two reasons and must not relabel one as the other
            "verification_reason": reason,

            # the polarity the band admitted on — always PRESENT here, and
            # recorded so a reader never has to infer it
            "polarity": candidate.get("polarity"),

        })

    # ==================================================
    # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — WHAT THE MODEL REPORTED
    # THAT IS NOT A POSITIVE OBSERVATION
    #
    # Withholding a negated or uncertain claim from the positive band is not
    # permission to drop it. "Absent is not present" cuts both ways: a stated
    # absence must still reach the user, labelled as a model-reported absence
    # and never as proven absence, and a claim the model itself left ambiguous
    # must be shown as uncertain rather than silently discarded.
    #
    # Neither list is evidence. Both are the provider's own wording, verbatim,
    # at `not confirmed` confidence. A text already published in the positive
    # band is never repeated here.
    # ==================================================

    reported_absences = []

    uncertain_claims = []

    withheld_claims = []

    seen_absence = set()

    seen_uncertain = set()

    seen_withheld = set()

    for candidate in understanding.get("provider_candidates") or []:

        if not isinstance(candidate, dict):

            continue

        # The contract already withholds `interpretations` from the published
        # candidate list — an interpretation is not an observation. The bands
        # below must apply the SAME rule, or a withheld interpretation would
        # re-enter through a curated band.
        if candidate.get("category") == "interpretations":

            continue

        text = str(candidate.get("text") or "").strip()

        if not text:

            continue

        key = text.lower()

        if key in seen_attributed:

            continue

        reason = (candidate.get("verification") or {}).get("reason")

        if candidate.get("polarity") == "ABSENT":

            if key in seen_absence:

                continue

            seen_absence.add(key)

            reported_absences.append({

                "name": text,
                "label": text,

                "kind": candidate.get("kind"),
                "category": candidate.get("category"),

                "evidence": candidate.get("source_quote") or text,

                "evidence_class": "provider absence report (unconfirmed)",

                "confidence": CONFIDENCE_NOT_CONFIRMED,

                "status": "reported, not independently confirmed",

                "source": "provider",

                "verification_reason": reason,

                "polarity": candidate.get("polarity"),

            })

            continue

        if (candidate.get("state") == "AMBIGUOUS"
                or candidate.get("certainty") == "AMBIGUOUS"
                or reason == "unknown_preserved"):

            if key in seen_uncertain:

                continue

            seen_uncertain.add(key)

            uncertain_claims.append({

                "name": text,
                "label": text,

                "kind": candidate.get("kind"),
                "category": candidate.get("category"),

                "evidence": candidate.get("source_quote") or text,

                "evidence_class": "provider claim (uncertain)",

                "confidence": CONFIDENCE_UNKNOWN,

                "status": "not determinable from the image",

                "source": "provider",

                "verification_reason": reason,

                "polarity": candidate.get("polarity"),

            })

            continue

        # ==================================================
        # ... AND WHAT THE VERIFIER WITHHELD
        #
        # A positive claim can clear the state, certainty and polarity gates
        # and still not be attributable, because the verifier recorded a
        # reason outside ATTRIBUTABLE_REASONS — for example a positive
        # description it filed under
        # `negative_claim_requires_explicit_local_absence`, or a numeric
        # mismatch. Those claims were visible in the old raw dump, so dropping
        # them would silently lose architectural content. They are published
        # here, labelled as reported-but-withheld, and never as evidence.
        # ==================================================

        if (candidate.get("state") == "UNVERIFIED"
                and candidate.get("polarity") == "PRESENT"
                and reason not in ATTRIBUTABLE_REASONS
                and reason is not None):

            if key in seen_withheld:

                continue

            seen_withheld.add(key)

            withheld_claims.append({

                "name": text,
                "label": text,

                "kind": candidate.get("kind"),
                "category": candidate.get("category"),

                "evidence": candidate.get("source_quote") or text,

                "evidence_class": "provider claim (withheld by the verifier)",

                "confidence": CONFIDENCE_NOT_CONFIRMED,

                "status": "reported, not admitted as observation evidence",

                "source": "provider",

                "verification_reason": reason,

                "polarity": candidate.get("polarity"),

            })

    if not evidence_available:

        unknowns.append({

            "name": None,

            "label": (
                "شواهد تصویری در دسترس نبود"
                if lang == "fa" else "no visual evidence was available"
            ),

            "status": "no evidence available",

            "confidence": CONFIDENCE_UNKNOWN,

        })

    elif not elements and not unknowns and not attributed:

        unknowns.append({

            "name": None,

            "label": (
                "هیچ عنصر قابل مشاهده‌ای گزارش نشده است"
                if lang == "fa" else "no visible element was reported"
            ),

            "status": "no visible element reported",

            "confidence": CONFIDENCE_UNKNOWN,

        })

    from core.vision.local_plan_symbols_v1 import grounded_plan_items
    from core.vision.local_plan_elements_v1 import grounded_plan_elements

    local_items = [
        {key: value for key, value in item.items() if key != "supported_function"}
        for item in grounded_plan_items(understanding.get("local_plan_reading"))
    ]

    observation = {

        "contract": CONTRACT,

        "version": VERSION,

        "mode": MODE,

        "language": lang,

        "elements": elements,

        # The brief's own name for this list. `elements` stays canonical
        # (the renderer and the tests read it); `visible_elements` mirrors
        # it so the contract reads exactly as the brief specifies.
        "visible_elements": elements,
        "grounded_furniture_evidence": local_items,
        "grounded_element_evidence": grounded_plan_elements(understanding.get("local_plan_reading")),

        # W4.2A-8 — every grounded local category, so observation-only does
        # not collapse to a handful of objects.
        "grounded_categories": _grounded_categories(understanding),

        # Provider candidates are audit evidence, never merged into the local
        # element list or used as interpretations. Raw remains in understanding.
        "provider_candidates": [
            dict(item) for item in understanding.get("provider_candidates", [])
            if item.get("category") != "interpretations"
        ],
        "grounded_provider_evidence": understanding.get("grounded_provider_evidence", []),
        "local_ocr": understanding.get("local_ocr", []),
        "verified_ocr": understanding.get("verified_ocr", []),

        # VISION_END_TO_END_RETENTION_FIX_V1 — provider/local disagreements are
        # published beside the evidence, never resolved by preference.
        "conflicts": grounding.get("conflicts") or [],
        "provider_drawing_type": understanding.get("provider_drawing_type"),

        # W4.2A-8 — interpretation is a SEPARATE section, and only when the
        # turn explicitly asked for it. Observation never promotes itself.
        "interpretation_section": (
            build_interpretation_section(understanding, lang)
            if include_interpretation else None
        ),

        "unknowns": unknowns,

        "not_confirmed": rejected,

        # VISION_EVIDENCE_PROVENANCE_V1 — provider-asserted observations that
        # nothing independently corroborated. Never mixed into `elements`.
        # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — affirmative presence only.
        "attributed_elements": attributed,

        # the two bands that are NOT positive observations, kept so the human
        # view can show them without ever promoting them
        "reported_absences": reported_absences,

        "uncertain_claims": uncertain_claims,

        "withheld_claims": withheld_claims,

        "counts": {

            "elements": len(elements),

            "unknowns": len(unknowns),

            "not_confirmed": len(rejected),

            "attributed": len(attributed),

            "reported_absences": len(reported_absences),

            "uncertain_claims": len(uncertain_claims),

            "withheld_claims": len(withheld_claims),

        },

        # ---- the separation, stated in the contract itself ----
        "space_type": None,
        "architectural_interpretation": [],
        "spatial_relations": [],
        "possible_function": [],
        "design_reasoning": [],

        "excludes": [
            "space classification",
            "privacy / public-private zoning",
            "design intent",
            "circulation reasoning",
            "architectural function",
        ],

        "evidence_hierarchy": [
            "visible object in the image",
            "clear spatial symbol",
            "inference (never evidence)",
        ],

        "feeds": "ArchitecturalVisionInterpreterV1",

        # ---- read-only, and provably so ----
        "read_only": True,
        "provider_calls": 0,
        "llm_used": False,
        "network_used": False,
        "storage_used": False,
        "render_requested": False,
        "geometry_touched": False,
        "comfy_invoked": False,
        "teaching_used": False,
    }

    return observation


# ----------------------------------------------------------
# RENDERING
# ----------------------------------------------------------

OBSERVATION_PHRASES = {

    "fa": {

        "header": "عناصر قابل مشاهده در تصویر:",

        "item": "• %s — شاهد: %s — اطمینان: %s",

        "symbol_note": " (خوانده‌شده به‌عنوان نماد نقشه)",

        "no_elements": (
            "• هیچ عنصر قابل مشاهده‌ای با شاهد کافی گزارش نشده است."
        ),

        # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — "nothing corroborated" is
        # NOT "the model reported nothing". Two different sentences.
        "no_corroborated": (
            "• هیچ عنصری به‌طور مستقل تأیید نشد. گزارش‌های مدل بینایی در ادامه "
            "به‌صورت تأییدنشده آمده است."
        ),

        "attributed_header": "گزارش مدل بینایی — تأییدنشده:",

        "attributed_item": "• «%s» — %s",

        "attributed_status": "تأییدنشده",

        "absence_header": "نبودِ گزارش‌شده توسط مدل — تأییدنشده:",

        "absence_item": "• «%s» — %s",

        "absence_status": "ادعای نبود، تأییدنشده",

        "uncertain_header": "ادعاهایی که مدل نامشخص گذاشته — شاهد نیست:",

        "uncertain_item": "• «%s» — %s",

        "uncertain_status": "مبهم یا قابل تعیین نیست",

        "withheld_header": "گزارش‌شده توسط مدل ولی پذیرفته‌نشده به‌عنوان شاهد:",

        "withheld_item": "• «%s» — %s",

        "withheld_status": "گزارش مدل، شاهد نیست",

        "unknown_header": "نامشخص یا تأییدنشده:",

        "unknown_item": "• %s — %s — اطمینان: %s",

        "not_confirmed_header": "گزارش‌شده ولی تأییدنشده:",

        "not_confirmed_item": "• %s — دلیل: %s",

        "scope_note": (
            "این پاسخ فقط «مشاهده» است: بدون تفسیر فضا، بدون دسته‌بندی، "
            "بدون حریم و بدون استدلال طراحی."
        ),

        "confidence": {
            "high": "زیاد",
            "medium": "متوسط",
            "not confirmed": "تأییدنشده",
            "unknown": "نامشخص",
        },

        # W4.2A-8 — grounded category coverage
        "category_headers": {
            "geometry": "هندسه و فضاهای محصور:",
            "openings": "بازشوها:",
            "vertical_circulation": "گردش عمودی:",
            "structure": "عناصر سازه‌ای و محورها:",
            "furniture": "مبلمان و تجهیزات:",
            "text": "متن، ابعاد و کدها:",
            "stable_local_ocr": "خوانش OCR پایدار ولی تأییدنشدهٔ مستقل (فقط OCR، نه واقعیت معماری):",
            "low_trust_ocr": "خوانش OCR تأییدنشده (حدس، نه متن اثبات‌شده):",
        },

        "category_geometry": (
            "• حدود %s ناحیه/فضای هندسی محصور تشخیص داده شد — منبع: %s"
        ),

        "category_item": "• %s: %s مورد — منبع: %s",

        "category_text": "• «%s» — خوانده‌شده با OCR محلی — اطمینان: %s",

        "category_stable_local": (
            "• «%s» — پایدار (%s پاس، همان موتور) — تأییدنشدهٔ مستقل — منبع: %s"
        ),

        "category_low_trust": (
            "• «%s» — تأییدنشده؛ خام OCR: «%s» — منبع: %s"
        ),

        "provenance": {
            "LOCAL_RASTER": "خوانش محلی تصویر",
            "LOCAL_SYMBOL_READER": "خوانش نمادی محلی",
            "LOCAL_OCR": "OCR محلی",
        },

        "interpretation_header": "تفسیر معماری (احتمالی، جدا از مشاهده):",

        "interpretation_item": "• %s",

        "interpretation_note": (
            "بخش تفسیر جداست و قطعی نیست؛ فقط مشاهدهٔ بالا شاهد تصویری دارد."
        ),

        "scope_note_with_interpretation": (
            "بخش «مشاهده» فقط شاهد تصویری دارد؛ بخش «تفسیر» احتمالی و جداست."
        ),

        "status": {
            "stated as not visible": "گزارش‌شده به‌عنوان دیده‌نشده",
            "no evidence available": "شواهدی در دسترس نبود",
            "no visible element reported": "گزارشی ثبت نشده",
        },
    },

    "en": {

        "header": "Elements visible in the image:",

        "item": "• %s — evidence: %s — confidence: %s",

        "symbol_note": " (read as a plan symbol)",

        "no_elements": "• No visible element is reported with evidence.",

        # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — "nothing corroborated" is
        # NOT "the model reported nothing". Two different sentences.
        "no_corroborated": (
            "• No element was independently corroborated. The vision model's "
            "reports follow as unverified observations."
        ),

        "attributed_header": "Reported by the vision model — not independently confirmed:",

        "attributed_item": "• «%s» — %s",

        "attributed_status": "unverified",

        "absence_header": "Model-reported absences — not independently confirmed:",

        "absence_item": "• «%s» — %s",

        "absence_status": "absence claim, unverified",

        "uncertain_header": "Claims the model left uncertain — not evidence:",

        "uncertain_item": "• «%s» — %s",

        "uncertain_status": "ambiguous or not determinable",

        "withheld_header": "Reported by the model but not admitted as observation evidence:",

        "withheld_item": "• «%s» — %s",

        "withheld_status": "model report, not evidence",

        "unknown_header": "Unknown or unconfirmed:",

        "unknown_item": "• %s — %s — confidence: %s",

        "not_confirmed_header": "Reported but not confirmed:",

        "not_confirmed_item": "• %s — reason: %s",

        "scope_note": (
            "This answer is OBSERVATION only: no space interpretation, no "
            "classification, no privacy or zoning, no design reasoning."
        ),

        "confidence": {
            "high": "high",
            "medium": "medium",
            "not confirmed": "not confirmed",
            "unknown": "unknown",
        },

        # W4.2A-8 — grounded category coverage
        "category_headers": {
            "geometry": "Geometry and enclosed spaces:",
            "openings": "Openings:",
            "vertical_circulation": "Vertical movement:",
            "structure": "Structural elements and axes:",
            "furniture": "Furniture and equipment:",
            "text": "Text, dimensions and codes:",
            "stable_local_ocr": "Stable but NOT independently verified OCR (OCR only, not architectural fact):",
            "low_trust_ocr": "Unverified OCR reading (a guess, not proven text):",
        },

        "category_geometry": (
            "• about %s enclosed geometric region(s) were detected — source: %s"
        ),

        "category_item": "• %s: %s instance(s) — source: %s",

        "category_text": "• \"%s\" — read by local OCR — confidence: %s",

        "category_stable_local": (
            "• \"%s\" — stable (%s pass(es), same engine) — NOT independently "
            "verified — source: %s"
        ),

        "category_low_trust": (
            "• \"%s\" — UNVERIFIED; raw OCR: \"%s\" — source: %s"
        ),

        "provenance": {
            "LOCAL_RASTER": "local raster reading",
            "LOCAL_SYMBOL_READER": "local symbol reading",
            "LOCAL_OCR": "local OCR",
        },

        "interpretation_header": (
            "Architectural interpretation (possible, separate from observation):"
        ),

        "interpretation_item": "• %s",

        "interpretation_note": (
            "The block above is interpretation, not observation; it is not certain."
        ),

        "scope_note_with_interpretation": (
            "The OBSERVATION section carries visual evidence only; the "
            "INTERPRETATION section is separate and possible."
        ),

        "status": {
            "stated as not visible": "stated as not visible",
            "no evidence available": "no evidence available",
            "no visible element reported": "no visible element reported",
        },
    },
}


def render_observation(observation, language=None):

    """The observation as the answer text, or ""."""

    if not isinstance(observation, dict):

        return ""

    lang = _language(language or observation.get("language"))

    text = OBSERVATION_PHRASES[lang]

    lines = [text["header"]]

    elements = observation.get("elements") or []

    if elements:

        for entry in elements:

            # W4.2A-8 — the raw evidence IDs stay in the structured
            # contract; the UI shows human prose, never the identifier.
            translated = _translate_evidence(entry.get("evidence"), lang)

            evidence = " · ".join(translated) or "-"

            confidence = text["confidence"].get(
                entry.get("confidence"), entry.get("confidence") or ""
            )

            note = (
                text["symbol_note"]
                if entry.get("status") == "symbol_reading"
                else ""
            )

            # The label follows the RENDERED language, not the language
            # the observation happened to be built in. A door is shown as
            # a door, never as an entrance.
            label = (
                _display_label(entry, lang)
                or _label(entry.get("name"), lang)
                or entry.get("label")
            )

            lines.append(
                text["item"] % (label, evidence, confidence) + note
            )

    else:

        # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — the empty `elements` band
        # means "nothing was INDEPENDENTLY CORROBORATED", not "the model saw
        # nothing". Printing the second when the first is true was the defect:
        # four facades opened with "No visible element is reported with
        # evidence" and then listed 16-45 model claims.
        reported = (
            (observation.get("attributed_elements") or [])
            or (observation.get("reported_absences") or [])
            or (observation.get("uncertain_claims") or [])
        )

        lines.append(text["no_corroborated"] if reported else text["no_elements"])

    # ---- W4.2A-8 — grounded category coverage ----
    categories = observation.get("grounded_categories") or {}

    headers = text.get("category_headers") or {}

    provenance = text.get("provenance") or {}

    for key in CATEGORY_ORDER:

        entry = categories.get(key)

        if not entry or not headers.get(key):

            continue

        lines.append(headers[key])

        source = provenance.get(
            entry.get("provenance"), entry.get("provenance") or ""
        )

        if key == "geometry":

            lines.append(
                text["category_geometry"] % (entry.get("region_count"), source)
            )

        elif key == "text":

            for label in entry.get("labels") or []:

                confidence = text["confidence"].get(
                    str(label.get("confidence") or "").lower(),
                    label.get("confidence") or "",
                )

                lines.append(
                    text["category_text"] % (label.get("text"), confidence)
                )

        elif key == "stable_local_ocr":

            # VISION_RETENTION_FIX_V2 — a stable multi-pass reading of ONE
            # engine over ONE image is reported as OCR ONLY, with its pass
            # count, and never as architectural truth.
            for label in entry.get("labels") or []:

                lines.append(
                    text["category_stable_local"] % (
                        label.get("text"), label.get("stability_passes"), source
                    )
                )

        elif key == "low_trust_ocr":

            # VISION_END_TO_END_RETENTION_FIX_V1 — an unverified OCR guess is
            # reported as a GUESS, with its raw OCR, and never as read text.
            for label in entry.get("labels") or []:

                lines.append(
                    text["category_low_trust"] % (
                        label.get("text"), label.get("raw_ocr"), source
                    )
                )

        else:

            for kind, count in sorted((entry.get("counts") or {}).items()):

                pair = KIND_LABELS.get(kind)

                label = (
                    (pair[0] if lang == "fa" else pair[1]) if pair else kind
                )

                lines.append(
                    text["category_item"] % (label, count, source)
                )

    # ==================================================
    # CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — CURATED PROVIDER EVIDENCE
    #
    # This used to be one flat dump of every `provider_candidates` entry under
    # a single heading. That dump printed the same claim twice when the model
    # reached it by two paths, printed a stated ABSENCE in the same list as a
    # positive description, and gave a drawing-type statement and an
    # architectural window the same weight.
    #
    # The three curated bands replace it. Each claim appears in exactly one of
    # them, the provider's own wording is quoted verbatim, and every band says
    # in its own heading that it is NOT independently confirmed.
    #
    # The complete `provider_candidates` list is untouched in the structured
    # contract, so nothing is lost for audit — only the human view is ordered.
    # ==================================================

    attributed = observation.get("attributed_elements") or []

    if attributed:

        lines.append(text["attributed_header"])

        for entry in attributed:

            # Quote the claim verbatim; no inferred translation, units, room
            # identity, axis continuation or compass direction is added.
            lines.append(
                text["attributed_item"] % (
                    entry.get("name", ""), text["attributed_status"]
                )
            )

    absences = observation.get("reported_absences") or []

    if absences:

        lines.append(text["absence_header"])

        for entry in absences:

            lines.append(
                text["absence_item"] % (
                    entry.get("name", ""), text["absence_status"]
                )
            )

    uncertain = observation.get("uncertain_claims") or []

    if uncertain:

        lines.append(text["uncertain_header"])

        for entry in uncertain:

            lines.append(
                text["uncertain_item"] % (
                    entry.get("name", ""), text["uncertain_status"]
                )
            )

    withheld = observation.get("withheld_claims") or []

    if withheld:

        lines.append(text["withheld_header"])

        for entry in withheld:

            lines.append(
                text["withheld_item"] % (
                    entry.get("name", ""), text["withheld_status"]
                )
            )

    unknowns = observation.get("unknowns") or []

    if unknowns:

        lines.append(text["unknown_header"])

        for entry in unknowns:

            status = text["status"].get(
                entry.get("status"), entry.get("status") or ""
            )

            confidence = text["confidence"].get(
                entry.get("confidence"), entry.get("confidence") or ""
            )

            label = _label(entry.get("name"), lang) or entry.get("label")

            lines.append(
                text["unknown_item"] % (label, status, confidence)
            )

    not_confirmed = observation.get("not_confirmed") or []

    if not_confirmed:

        lines.append(text["not_confirmed_header"])

        for entry in not_confirmed:

            label = _label(entry.get("name"), lang) or entry.get("label")

            reason = _reason(
                entry.get("reason_code"), entry.get("reason"), lang
            )

            lines.append(text["not_confirmed_item"] % (label, reason))

    # ---- W4.2A-8 — interpretation stays a SEPARATE, hedged section ----
    section = observation.get("interpretation_section")

    has_section = isinstance(section, dict) and bool(section.get("items"))

    if has_section:

        lines.append(text["interpretation_header"])

        for item in section["items"]:

            lines.append(text["interpretation_item"] % item)

        lines.append(text["interpretation_note"])

    lines.append(
        text.get("scope_note_with_interpretation")
        if has_section else text["scope_note"]
    )

    return "\n".join(line for line in lines if line)

