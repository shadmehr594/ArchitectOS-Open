# ==========================================================
# ArchitectOS Architectural Vision Grounding v1
#
# ARCHITECTURAL_VISION_GROUNDING_V1
#
# THE USER-REPORTED FAILURE (their own image as evidence)
#
#   "Expected visual evidence: sleeping area, double bed arrangement,
#    entrance, circulation zone, closet zone, ensuite bathroom zone,
#    WC zone.  Expected absence: no window."
#
#   "False positive: window detected.
#    False negative: closet not detected, bathroom not detected."
#
# WHAT THE EVIDENCE SHOWS (core_api.log, the same image, 4 runs):
#
#   run A  observed: [... 'door symbols', 'window symbols', ...]
#          architectural_elements: ['bed','wardrobe','desk','chair','door','window']
#   run B  observed: [... 'bed', 'wardrobe', 'desk', 'door symbols']
#          architectural_elements: ['bed','wardrobe','desk','chair','door','wall']
#
#   * the PROVIDER is inconsistent: it reports a `window` in one run and
#     not in another, for the SAME image
#   * the provider NEVER reports a bathroom, an ensuite or a WC
#   * `ArchitecturalVisionInterpreterV1` then HARDCODES
#       "private bathroom connection is not visible"
#       "dressing or closet zone is not visible"
#     for every bedroom — so a `wardrobe` that WAS observed is announced
#     as visible AND as not visible in the same answer, and the closet
#     reads as "not detected"
#
# THIS LAYER: evidence discipline, not a new vision model.
#
#   1. Every element claim is extracted WITH its evidence: which field,
#      which phrase, and what class of evidence it is.
#   2. A claim is only promoted to `visible` when the provider's own
#      OBSERVATION field states it as an object ("bed", "double bed
#      visible"). A plan SYMBOL reading ("window symbols") or a bare
#      entry in the provider's element list is NOT enough — the provider
#      itself declares that plan symbols "are read conservatively and
#      may be incomplete".
#   3. Absence is never invented: an element is `denied` only when the
#      provider states its absence, and `not_reported` otherwise —
#      unknown is better than hallucination.
#   4. Expected elements come from the FROZEN corpus (the space's own
#      function + its typical adjacency + its access requirements), so a
#      missing zone is surfaced explicitly instead of silently.
#   5. Contradictions are resolved and recorded, never printed twice.
#
# Read-only: no LLM, no network, no storage, no geometry, no render.
# ==========================================================


from __future__ import annotations


import re


CONTRACT = "ArchitecturalVisionGroundingV1"

VERSION = "1.0"


# ----------------------------------------------------------
# EVIDENCE SOURCE TAXONOMY
#
# ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — every claim carries the
# KIND of evidence it is, so a conclusion can never be stronger than its
# source. These are the sources, strongest first.
# ----------------------------------------------------------

SOURCE_LABEL = "label"            # readable text in the image (OCR)
SOURCE_GEOMETRY = "geometry"      # walls / openings / enclosure
SOURCE_SYMBOL = "symbol"          # a plan symbol reading
SOURCE_FURNITURE = "furniture"    # a furniture / fixture cue
SOURCE_RELATION = "relation"      # a stated relation between spaces
SOURCE_PROVIDER_ONLY = "provider_only"   # a claim with NO corroboration

EVIDENCE_SOURCES = (
    SOURCE_LABEL,
    SOURCE_GEOMETRY,
    SOURCE_SYMBOL,
    SOURCE_FURNITURE,
    SOURCE_RELATION,
    SOURCE_PROVIDER_ONLY,
)

# An image_type that is a DRAWING rather than a photograph. On a drawing
# everything the provider "sees" is a SYMBOL, never an object.
DRAWING_IMAGE_TYPES = (
    "floor_plan_or_sketch",
    "plan",
    "site_diagram",
    "diagram",
)

# ==========================================================
# VISION_END_TO_END_RETENTION_FIX_V1 — SCOPE-LEVEL CONFLICT
#
# A provider claim that negates the DOCUMENT SCOPE ("… not an architectural
# interior", "not a building floor plan") disagrees with any local claim that
# asserts an INTERIOR architectural space. This is a SCOPE-level conflict: it
# does NOT decide which source is correct, it only makes the disagreement
# visible, so a local space claim can never be published as undisputed fact.
#
# The term lists are bounded SCOPE and SPACE vocabulary, not per-room phrase
# rules and not per-image special cases.
# ==========================================================
SCOPE_ABSENCE_TERMS = (
    "architectural interior", "building interior", "interior space",
    "interior", "floor plan", "building floor plan", "building plan",
    "architectural plan",
)

INTERIOR_SPACE_KINDS = (
    "bathroom", "balcony", "kitchen", "bedroom", "master bedroom",
    "living room", "corridor", "entrance", "storage", "dining", "study",
    "private room", "circulation",
)


def _trusted_local_labels(local, independent_texts):
    """The local OCR labels that passed the TRUST gate (Fix V2).

    A local OCR token may only act as a trusted LOCAL PRESENT when it is
    INDEPENDENTLY verified. Same-engine multi-pass agreement is a stability
    signal and never qualifies, and a lexicon substitution never qualifies.
    """

    from core.vision.local_evidence_trust_v1 import (
        INDEPENDENTLY_VERIFIED_OCR, ocr_trust_state,
    )

    return [label for label in (local or {}).get("labels") or []
            if isinstance(label, dict)
            and ocr_trust_state(label, independent_texts) == INDEPENDENTLY_VERIFIED_OCR]


def _trusted_local_elements(local):
    """The local raster elements that may act as a trusted LOCAL PRESENT.

    An element whose own detector declares an UNSATISFIED requirement stays a
    CLUE and must not create presence (Fix V2).
    """

    trusted = []

    for element in (local or {}).get("element_evidence") or []:

        if not isinstance(element, dict) or not element.get("type"):

            continue

        if element.get("status") != "visible":

            continue

        if not _local_requirement_met(element):

            continue

        trusted.append(element)

    return trusted


def _local_present_kinds(local, independent_texts=()):
    """The architectural kinds the TRUSTED LOCAL evidence asserts as PRESENT.

    VISION_RETENTION_FIX_V2 — every OCR-derived kind must pass the same trust
    discipline as a downstream architectural fact, and every raster element
    must satisfy its own declared requirement. Low-trust OCR therefore cannot
    create a LOCAL PRESENT kind, and with it no scope or kind conflict.
    """

    kinds = set()

    if not isinstance(local, dict):

        return kinds

    for label in _trusted_local_labels(local, independent_texts):

        if label.get("semantic_function"):

            kinds.add(str(label["semantic_function"]).strip().casefold())

    for element in _trusted_local_elements(local):

        kinds.add(str(element["type"]).strip().casefold())

    try:

        from core.vision.local_plan_symbols_v1 import grounded_plan_items

        for item in grounded_plan_items(local):

            if item.get("class"):

                kinds.add(str(item["class"]).strip().casefold())

    except Exception:

        pass

    return kinds


def _scope_conflicts(raw):
    """Provider-ABSENT vs local-PRESENT disagreements, at both levels.

    SCOPE level — a provider claim that negates the DOCUMENT SCOPE
    ("… not an architectural interior") against any local interior space.

    KIND level — a provider ABSENT claim about a kind the local evidence
    asserts as PRESENT.

    Neither level decides which source is correct: the disagreement is simply
    made visible, so a local space claim can never be published as undisputed
    fact.
    """

    from core.vision.provider_candidate_verification_v1 import claim_polarity
    from core.vision.local_evidence_trust_v1 import independently_verified_ocr_texts

    candidates = [claim for claim in (raw.get("provider_candidates") or [])
                  if isinstance(claim, dict)]

    local = raw.get("local_plan_reading")

    # VISION_RETENTION_FIX_V2 — only INDEPENDENTLY verified OCR may act as a
    # trusted LOCAL PRESENT. Same-engine multi-pass agreement is stability, not
    # independence, so it never qualifies here.
    independent_texts = independently_verified_ocr_texts(raw)

    out = []

    # ---- SCOPE level -------------------------------------------------
    absent_scopes = []

    for claim in candidates:

        if claim.get("category") not in ("interpretations", "drawing_type", "unknowns"):

            continue

        if (claim.get("polarity") or claim_polarity(claim)) != "ABSENT":

            continue

        haystack = (
            str(claim.get("text") or "") + " " + str(claim.get("source_quote") or "")
        ).casefold()

        hits = [term for term in SCOPE_ABSENCE_TERMS if term in haystack]

        if hits:

            absent_scopes.append({"claim": claim.get("text"), "terms": hits,
                                  "candidate_id": claim.get("candidate_id")})

    if absent_scopes:

        present = []

        for label in _trusted_local_labels(local, independent_texts):

            if label.get("semantic_function") in INTERIOR_SPACE_KINDS:

                present.append({"kind": label.get("semantic_function"),
                                "text": label.get("text"), "source": "LOCAL_OCR",
                                "trust_state": "INDEPENDENTLY_VERIFIED_OCR"})

        for element in _trusted_local_elements(local):

            if element.get("type") in INTERIOR_SPACE_KINDS:

                present.append({"kind": element.get("type"),
                                "text": element.get("evidence"), "source": "LOCAL_RASTER",
                                "trust_state": "REQUIREMENT_MET"})

        if present:

            out.append({
                "element": None,
                "kind": "document_scope",
                "resolved": "CONFLICTING",
                "positive": present,
                "negative": absent_scopes,
                "reason_code": "provider_scope_absence_conflicts_with_local_interior_space",
                "reason": (
                    "the provider states the image is NOT an architectural interior "
                    "while TRUSTED local evidence asserts interior architectural "
                    "space(s); neither source is treated as correct here"
                ),
            })

    # ---- KIND level ---------------------------------------------------
    absent_kinds = {}

    for claim in candidates:

        if (claim.get("polarity") or claim_polarity(claim)) != "ABSENT":

            continue

        kind = claim.get("kind")

        if isinstance(kind, str) and kind.strip():

            absent_kinds.setdefault(kind.strip().casefold(), []).append(claim.get("text"))

    present_kinds = _local_present_kinds(local, independent_texts)

    for kind, texts in sorted(absent_kinds.items()):

        if kind not in present_kinds:

            continue

        out.append({
            "element": kind,
            "kind": kind,
            "resolved": "CONFLICTING",
            "positive": [{"kind": kind, "source": "LOCAL_EVIDENCE"}],
            "negative": [{"claim": text} for text in texts],
            "reason_code": "provider_absence_conflicts_with_local_presence",
            "reason": (
                "the provider states this kind is ABSENT while the local "
                "evidence reports it PRESENT; neither source is treated as "
                "correct here"
            ),
        })

    return out


# ----------------------------------------------------------
# EVIDENCE CLASSES
# ----------------------------------------------------------

CLASS_OBJECT = "object"        # "bed", "double bed visible"

CLASS_SYMBOL = "symbol"        # "window symbols"  (a plan symbol reading)

CLASS_MENTION = "mention"      # listed in the provider's element list only

CLASS_LABEL = "label"          # only inside a visible text label

CLASS_NEGATED = "negated"      # "no window", "پنجره ندارد"

CLASS_INFERRED = "inferred"    # from the provider's `inferred` list

# ARCHITECTURAL_VISION_OBSERVATION_V2 — a provider-observed RELATION
# between two spaces ("bedroom adjacent to corridor"). The provider was
# asked for these separately from `observed` and they were never read, so
# every visible adjacency was discarded before this filter ran.
CLASS_CLUE = "clue"


# ----------------------------------------------------------
# ELEMENT STATUSES
# ----------------------------------------------------------

STATUS_VISIBLE = "visible"

STATUS_UNVERIFIED = "unverified"

STATUS_SYMBOL = "symbol_reading"

STATUS_DENIED = "denied"

STATUS_NOT_REPORTED = "not_reported"

# ARCHITECTURAL_VISION_OBSERVATION_V2 — the LIKELY tier.
#
# A readable room LABEL on a plan ("آشپزخانه", "حمام") or a visible
# RELATION ("bedroom adjacent to corridor") NAMES the element. On a
# labelled floor plan that is the strongest evidence there is, but it is
# not the same claim as "the provider observed this object", so it is
# neither promoted to `visible` nor collapsed into `unverified` (which
# reads as "reported but unsupported"). It gets its own honest tier.
STATUS_LIKELY = "likely"

# ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — a claim that is NOT
# corroborated anywhere else in the provider payload. It is kept and
# reported, but it can never become an architectural fact.
STATUS_PROVIDER_ONLY = "provider_only"


# ----------------------------------------------------------
# THE CLOSED ELEMENT TABLE
#
# `phrase` is the architectural phrase the interpreter publishes, so the
# display vocabulary keeps ONE owner (the vision report renderer).
# ----------------------------------------------------------

ELEMENTS = {

    "sleeping_element": {
        "phrase": "sleeping element visible",
        "terms": ("bed", "تخت", "تخت خواب", "sleeping element", "double bed",
                  "تخت دونفره", "larger bed", "large bed"),
    },

    "double_bed": {
        "phrase": "double bed arrangement visible",
        "terms": ("double bed", "تخت دونفره", "larger bed", "large bed"),
    },

    "wardrobe_or_closet": {
        "phrase": "storage or dressing element visible",
        "terms": ("wardrobe", "closet", "closet room", "dressing", "کمد",
                  "کلوزت", "رختکن", "اتاق لباس", "کمد دیواری"),
    },

    "bathroom_or_ensuite": {
        "phrase": "sanitary zone visible",
        "terms": ("bathroom", "ensuite", "en-suite", "shower", "bathtub",
                  "sink", "حمام", "حموم", "سرویس", "دوش", "وان"),
    },

    "wc": {
        "phrase": "sanitary fixture visible",
        "terms": ("wc", "toilet", "water closet", "سرویس فرنگی", "توالت",
                  "دستشویی", "فرنگی"),
    },

    "entrance": {
        "phrase": "entrance threshold visible",
        # "doors" is what the provider's element list actually contains;
        # the singular-only terms could never match the plural.
        "terms": ("entrance", "entry", "door", "doors", "doorway", "ورودی",
                  "درب", "درها", "در", "آستانه"),
    },

    "circulation": {
        "phrase": "circulation passage visible",
        # "corridors" (plural) is the provider's own wording.
        "terms": ("corridor", "corridors", "hallway", "hall", "passage",
                  "راهرو", "راهروها", "دالان", "کریدور", "هال"),
    },

    "window": {
        "phrase": "daylight opening visible",
        # "windows" (plural) is the provider's own wording.
        "terms": ("window", "windows", "glazing", "glass", "پنجره", "پنجره‌ها",
                  "شیشه", "نورگیر"),
    },

    "stair": {"phrase": "stair run visible", "terms": ("stair", "staircase", "stairs", "steps", "پله", "راهپله")},
    "duct": {"phrase": "service shaft candidate", "terms": ("duct", "shaft", "داکت", "شفت")},
    "shaft": {"phrase": "core shaft candidate", "terms": ("elevator", "lift", "elevator shaft", "آسانسور", "چاهک")},
    "column": {"phrase": "structural column candidate", "terms": ("column", "columns", "pillar", "ستون")},
    "axis": {"phrase": "grid axis marker visible", "terms": ("grid", "axis", "axes", "محور", "آکس")},
    "level": {"phrase": "elevation marker visible", "terms": ("level marker", "elevation marker", "کد ارتفاعی", "کد تراز")},
    "opening": {
        "phrase": "opening visible",
        "terms": ("opening", "openings", "بازشو", "بازشوها"),
    },

    "seating": {
        "phrase": "seating element visible",
        "terms": ("seating", "chair", "sofa", "صندلی", "مبل", "نشیمن"),
    },

    "kitchen": {
        "phrase": "kitchen work zone visible",
        "terms": ("kitchen", "آشپزخانه", "مطبخ"),
    },

    "wall": {
        "phrase": "vertical enclosure surface visible",
        "terms": ("wall", "walls", "partition", "دیوار", "سطح قائم"),
    },

    "floor": {
        "phrase": "horizontal floor plane visible",
        "terms": ("floor plane", "floor", "سطح کف", "کف اتاق"),
    },

    "balcony": {
        "phrase": "projecting outdoor platform visible",
        "terms": ("balcony", "terrace", "بالکن", "تراس", "ایوان"),
    },

    "facade": {
        "phrase": "facade plane visible",
        "terms": ("facade", "elevation", "نما", "پوسته بیرونی"),
    },

    "room": {
        "phrase": "enclosed room volume visible",
        # ARCHITECTURAL_VISION_OBSERVATION_V2 — the provider reports the
        # plural "rooms" / "labeled rooms", which the old terms ("room
        # volume", "enclosed room") could never match, so a plan's rooms
        # were never detected at all. "اتاق" is the label noun.
        "terms": ("room volume", "enclosed room", "rooms", "labeled rooms",
                  "فضای داخلی", "حجم اتاق", "اتاق", "اتاق‌ها"),
    },

    "bedroom": {
        "phrase": "private sleeping room visible",
        "terms": ("bedroom", "bed rooms", "اتاق خواب", "اتاق‌خواب",
                  "اتاق والدین", "اتاق مستر"),
    },

    "garden": {
        "phrase": "landscape area visible",
        "terms": ("garden", "landscape", "yard", "باغ", "محوطه", "حیاط"),
    },

    "desk": {
        "phrase": "work surface visible",
        "terms": ("desk", "میز", "میز کار"),
    },

    "storage": {
        "phrase": "storage volume visible",
        "terms": ("storage", "shelf", "انباری", "قفسه"),
    },
}


# ----------------------------------------------------------
# MARKERS
# ----------------------------------------------------------

NEGATION_MARKERS = (
    # Whole words only — the matcher is word-bounded, so a trailing space
    # would never match ("no window": the lookahead sees "w").
    "no", "not", "without", "absent", "missing", "none",
    "cannot", "can not", "unable", "unverified", "does not",
    "ندارد", "ندارند", "نیست", "نیستند", "بدون", "مشاهده نشد",
    "دیده نمی", "دیده نشد", "وجود ندارد", "ثبت نشده", "حذف",
)


SYMBOL_MARKERS = (
    "symbol", "symbols", "icon", "icons", "schematic", "diagram",
    "نماد", "نمادها", "علامت", "علائم", "شماتیک",
)


# A phrase that is only a container of the drawing, never an element.
CONTAINER_MARKERS = (
    "floor plan", "floor plans", "plan", "plans", "layout", "layouts",
    "drawing", "drawings", "sketch", "text", "watermark", "label",
    "labels", "نقشه", "پلان", "طرح", "متن", "واترمارک", "چیدمان",
)


# ----------------------------------------------------------
# EXPECTED ELEMENTS — DERIVED FROM THE FROZEN CORPUS
# ----------------------------------------------------------

SPACE_TYPE_TO_CORPUS = {

    "bedroom": "BEDROOM_DOUBLE",

    "master bedroom": "MASTER_BEDROOM_SLEEPING",

    "living room": "LIVING_RECEPTION",

    "kitchen": "CLOSED_KITCHEN",

    "bathroom": "FAMILY_BATHROOM",

    "corridor": "PRIVATE_HALL_CORRIDOR",

    "balcony": "TERRACE_BALCONY",

    "entrance": "UNIT_ENTRY",

    "garden": "COURTYARD",
}


# The corpus space the element belongs to. A corpus record's own element
# comes from its FUNCTIONAL ROLE, its neighbours from `typical_adjacent`.
SELF_ELEMENT_BY_ROLE = (
    ("خواب", "sleeping_element"),
    ("sleep", "sleeping_element"),
    ("نشستن", "seating"),
    ("زندگی", "seating"),
    ("پخت", "kitchen"),
    ("بهداشت", "bathroom_or_ensuite"),
    ("پوشاک", "wardrobe_or_closet"),
    ("اتصال", "circulation"),
    ("ورود", "entrance"),
)


ADJACENT_ELEMENT = {

    "DRESSING": "wardrobe_or_closet",

    "WALK_IN_CLOSET": "wardrobe_or_closet",

    "ENSUITE": "bathroom_or_ensuite",

    "FAMILY_BATHROOM": "bathroom_or_ensuite",

    "GUEST_WC": "wc",

    "PRIVATE_HALL_CORRIDOR": "circulation",

    "FAMILY_HALL": "circulation",

    "GENERAL_HALL": "circulation",

    "COMMON_CORRIDOR_GALLERY": "circulation",

    "UNIT_ENTRY": "entrance",

    "FOYER_SHOE_OFF": "entrance",

    "TERRACE_BALCONY": "balcony",

    "COURTYARD": "garden",

    "DINING": "seating",

    "OPEN_KITCHEN": "kitchen",

    "CLOSED_KITCHEN": "kitchen",

    "STORAGE": "storage",

    "PANTRY": "storage",
}


# A sanitary zone always contains a WC fixture — a LABELLED derivation,
# reported as such on every expected item it produces.
SANITARY_IMPLIES_WC = True


# ----------------------------------------------------------
# TEXT HELPERS
# ----------------------------------------------------------

_WORD = "\u0600-\u06FF\u200cA-Za-z0-9"


def _text(value):

    if value is None:

        return ""

    return " ".join(str(value).strip().split())


def _items(value):

    if isinstance(value, str):

        return [_text(value)] if _text(value) else []

    if not isinstance(value, (list, tuple)):

        return []

    result = []

    for item in value:

        text = _text(item)

        if text and text not in result:

            result.append(text)

    return result


def _lower(text):

    return (text or "").lower()


def _has_whole(text, term):

    """Whole-word (or whole-phrase) match, so 'در' never matches 'دور'."""

    needle = _lower(term)

    if not needle:

        return False

    return re.search(
        r"(?<![" + _WORD + r"])"
        + re.escape(needle)
        + r"(?![" + _WORD + r"])",
        _lower(text),
    ) is not None


def _has_any(text, terms):

    return any(_has_whole(text, term) for term in terms)


def _is_negated(phrase):

    return _has_any(phrase, NEGATION_MARKERS)


def _is_symbol(phrase):

    return _has_any(phrase, SYMBOL_MARKERS)


def _is_container(phrase):

    return _has_any(phrase, CONTAINER_MARKERS)


def _matches_element(phrase, element_id):

    return _has_any(phrase, ELEMENTS[element_id]["terms"])


def _element_ids(phrase):

    return [
        element_id for element_id in ELEMENTS
        if _matches_element(phrase, element_id)
    ]


#: Prepositions that introduce a LOCATION inside a claim.
#:
#: FACADE_NEGATION_TARGET_GROUNDING_V1 — deliberately a closed spatial set.
#: Instrument and accompaniment prepositions ("through the glass", "with a
#: stone surround") are NOT included: they do not make the following noun the
#: place where something was missing, and widening the set without evidence
#: would move claims this milestone has no measured defect for.
_LOCATIVE = re.compile(
    r"\b(?:on|in|inside|within|at|along|behind|beneath|under|above)\b",
    re.IGNORECASE,
)


def _negation_target_ids(phrase):

    """The elements a NEGATION actually targets.

    MEASURED DEFECT (facade C):

        "No stairs, lifts, or other vertical circulation elements are
         visible on the facade"

    `_element_ids()` matches every element NAMED anywhere in the phrase, so
    this statement produced claims for both `stair` and `facade`. Because the
    phrase contains a negation marker, `_claims()` gave both of them
    CLASS_NEGATED, `_status(["facade"])` saw nothing but a negated claim, and
    the reply told the user the facade was "stated as not visible".

    The observer never said that. "On the facade" is the PLACE where
    circulation was not seen; it is not the thing that was not seen. A
    location named in a prepositional phrase is context, and context does not
    inherit the negation.

    The target set is therefore the elements named BEFORE the first locative
    preposition. If that prefix names no element at all, the whole phrase is
    used instead — so a negation is never silently dropped when the location
    is fronted ("On the facade, no stairs are visible" keeps its stair claim).
    """

    match = _LOCATIVE.search(phrase)

    if not match:

        return _element_ids(phrase)

    scoped = _element_ids(phrase[:match.start()])

    return scoped or _element_ids(phrase)


# ----------------------------------------------------------
# CLAIM EXTRACTION
# ----------------------------------------------------------

def _local_requirement_met(item):
    """Has the local detector's OWN declared requirement been satisfied?

    VISION_END_TO_END_RETENTION_FIX_V1 — a local element may declare a
    requirement it needs before its reading is established (for example
    `localized_numeric_annotation_required` for a level/elevation marker).
    When that requirement is not satisfied, the element is a CLUE, never a
    visible object. Unknown requirements fail closed.
    """

    requirements = [value for value in (item.get("corroboration") or [])
                    if isinstance(value, str) and value.endswith("_required")]

    if not requirements:

        return True

    attributes = item.get("attributes") or {}

    for requirement in requirements:

        if requirement == "localized_numeric_annotation_required":

            if attributes.get("annotation_status") == "grounded_ocr":

                continue

        return False

    return True


def _claims(raw):

    """Every element claim in the provider payload, with its evidence.

    The FIELD decides what a claim is worth:

      observed               -> the provider's own observation field
      architectural_elements -> the provider's derived element list
      text_labels_if_visible -> visible TEXT, not the element
      unresolved             -> only a NEGATIVE statement is a claim here
      inferred               -> never evidence (an inference is not an
                                observation) — kept, and rejected
    """

    claims = []

    for field in ("observed", "architectural_elements",
                  "text_labels_if_visible", "unresolved", "inferred"):

        for phrase in _items(raw.get(field)):

            if not phrase:

                continue

            if _is_container(phrase) and not _is_symbol(phrase):

                continue

            # FACADE_NEGATION_TARGET_GROUNDING_V1 — a negated phrase is
            # attributed only to the element it negates. An `inferred` phrase
            # is never evidence, so it keeps whole-phrase matching and its
            # CLASS_INFERRED verdict is unchanged.
            if field != "inferred" and _is_negated(phrase):

                target_ids = _negation_target_ids(phrase)

            else:

                target_ids = _element_ids(phrase)

            for element_id in target_ids:

                if field == "inferred":

                    kind = CLASS_INFERRED

                    source = SOURCE_PROVIDER_ONLY

                elif _is_negated(phrase):

                    kind = CLASS_NEGATED

                    source = SOURCE_PROVIDER_ONLY

                elif _is_symbol(phrase):

                    kind = CLASS_SYMBOL

                    source = SOURCE_SYMBOL

                elif field == "observed":

                    kind = CLASS_OBJECT

                    source = SOURCE_GEOMETRY

                elif field == "architectural_elements":

                    kind = CLASS_MENTION

                    source = SOURCE_GEOMETRY

                elif field == "text_labels_if_visible":

                    kind = CLASS_LABEL

                    source = SOURCE_LABEL

                else:

                    # `unresolved`: a POSITIVE phrase here is not evidence.
                    continue

                claims.append({

                    "element": element_id,

                    "field": field,

                    "phrase": phrase,

                    "class": kind,

                    "source": source,

                })

    # ==================================================
    # ARCHITECTURAL_VISION_OBSERVATION_V2 — THE PROVIDER'S OWN v3 KEYS
    #
    # The provider is asked for TWO categories SEPARATELY from `observed`:
    # the furniture it can see, and the visible relationships between
    # spaces. Both are provider OBSERVATIONS, and neither was ever read
    # here — so every furniture item and every visible adjacency the model
    # reported was silently discarded before this filter ran.
    #
    # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — BUT the CLASS depends
    # on what the image IS:
    #
    #   * on a PHOTO / RENDER, furniture named here is a real object
    #     observation -> CLASS_OBJECT.
    #   * on a DRAWING (plan / diagram), furniture is a SYMBOL on the
    #     sheet. It is a plan-symbol reading, exactly like "window
    #     symbols", and the frozen rule already says a symbol reading is
    #     NOT visibility. Treating it as an object observation is what let
    #     a provider furniture guess ("bed", "sofa", "table") become
    #     `visible` and then invent a bedroom, a living room and a dining
    #     room on a plan that shows no reliable furniture at all.
    #
    # The provider may deliver them at the top level (raw output) or under
    # `observation_extras` (the understanding contract).
    # ==================================================

    extras = raw.get("observation_extras")

    if not isinstance(extras, dict):

        extras = {
            key: raw.get(key)
            for key in ("furniture_elements", "spatial_clues")
            if raw.get(key) not in (None, [], "", {})
        }

    is_drawing = str(raw.get("image_type") or "").lower() in DRAWING_IMAGE_TYPES

    furniture_class = CLASS_SYMBOL if is_drawing else CLASS_OBJECT

    furniture_source = SOURCE_SYMBOL if is_drawing else SOURCE_FURNITURE

    for field, kind, source in (
        ("furniture_elements", furniture_class, furniture_source),
        ("spatial_clues", CLASS_CLUE, SOURCE_RELATION),
    ):

        for phrase in _items(extras.get(field)):

            if not phrase or _is_container(phrase):

                continue

            if _is_negated(phrase):

                kind_for_phrase = CLASS_NEGATED

                source_for_phrase = SOURCE_PROVIDER_ONLY

            else:

                kind_for_phrase = kind

                source_for_phrase = source

            for element_id in _element_ids(phrase):

                claims.append({

                    "element": element_id,

                    "field": "observation_extras." + field,

                    "phrase": phrase,

                    "class": kind_for_phrase,

                    "source": source_for_phrase,

                })

    from core.vision.local_plan_symbols_v1 import grounded_plan_items

    local = raw.get("local_plan_reading")
    mapping = {
        "bed": "sleeping_element", "sofa": "seating", "seating": "seating", "chair": "seating",
        "dining_surface": None, "kitchen_counter": "kitchen",
        "kitchen_sink_arrangement": "kitchen",
        "sanitary_fixture": "wc", "storage_cabinet": "storage",
    }
    if isinstance(local, dict) and (local.get("status") == "grounded" or local.get("symbol_analysis_status") == "analyzed"):
        furniture_ids = set(mapping.values()) | {"double_bed", "wardrobe_or_closet", "bathroom_or_ensuite", "desk"}
        # LOCAL PLAN takes precedence: bare provider observations/labels cannot
        # resurrect a bed/sofa/table without independent localized support.
        claims = [claim for claim in claims if claim.get("element") not in furniture_ids]
    elif str(raw.get("image_type") or "").lower() in DRAWING_IMAGE_TYPES:
        furniture_ids = set(mapping.values()) | {"double_bed", "wardrobe_or_closet", "bathroom_or_ensuite", "desk"}
        for claim in claims:
            if claim.get("element") in furniture_ids and claim.get("class") in (CLASS_OBJECT, CLASS_MENTION):
                claim["class"] = CLASS_SYMBOL
                claim["source"] = SOURCE_PROVIDER_ONLY
    for item in grounded_plan_items(local):
        if mapping[item["class"]] is None:
            continue
        claims.append({
            "element": mapping[item["class"]], "field": "local_plan_reading.furniture_evidence",
            "phrase": item["name"], "class": CLASS_OBJECT,
            "source": item["source"], "confidence": item["confidence"],
            "bbox_pixels": item["bbox_pixels"], "corroboration": item["corroboration"],
            "item_id": item["item_id"],
            # W4.2A-8 — the LOCAL symbol class is preserved beside the coarse
            # element id so a presentation layer can say "kitchen counter /
            # sink arrangement" instead of over-promoting it to "kitchen".
            "element_type": item["class"],
        })

    # Drawn architectural elements require independently localized raster
    # evidence. Provider "visible" wording cannot establish these instances.
    from core.vision.local_plan_elements_v1 import grounded_plan_elements
    element_ids = {"window", "entrance", "opening", "stair", "duct", "column", "axis", "level", "shaft"}
    if (isinstance(local, dict) and local.get("element_analysis_status") == "analyzed") or str(raw.get("image_type") or "").lower() in DRAWING_IMAGE_TYPES:
        for claim in claims:
            if claim.get("element") in element_ids and claim.get("class") != CLASS_NEGATED:
                claim["class"] = CLASS_SYMBOL
                claim["source"] = SOURCE_PROVIDER_ONLY
    for item in grounded_plan_elements(local):
        claims.append({
            "element": "entrance" if item["type"] == "door" else item["type"],
            "field": "local_plan_reading.element_evidence", "phrase": item["evidence"],
            "class": (CLASS_CLUE
                      if item["status"] == "candidate" or not _local_requirement_met(item)
                      else CLASS_OBJECT),
            "source": item["source"], "confidence": item["confidence"],
            "bbox_pixels": item["bbox_pixels"], "geometry": item["geometry"],
            "attributes": item["attributes"], "corroboration": item["corroboration"],
            "element_id": item["element_id"],
            # W4.2A-8 — the LOCAL raster element type is preserved beside the
            # coarse element id, so a presentation layer can report a DOOR as a
            # door instead of silently promoting it to "entrance". The status
            # logic and the element-id mapping above are unchanged.
            "element_type": item["type"],
        })

    return claims


def _status(claims):

    """The grounded status of ONE element from its claims."""

    positives = [
        claim for claim in claims
        if claim["class"] in (CLASS_OBJECT, CLASS_MENTION, CLASS_LABEL,
                             CLASS_SYMBOL, CLASS_CLUE)
    ]

    object_claims = [
        claim for claim in positives if claim["class"] == CLASS_OBJECT
    ]

    symbol_claims = [
        claim for claim in positives if claim["class"] == CLASS_SYMBOL
    ]

    # ARCHITECTURAL_VISION_OBSERVATION_V2 — a readable LABEL on a plan, or
    # a visible RELATION between two spaces, NAMES the element.
    likely_claims = [
        claim for claim in positives
        if claim["class"] in (CLASS_LABEL, CLASS_CLUE)
    ]

    weak_claims = [
        claim for claim in positives
        if claim["class"] in (CLASS_MENTION, CLASS_LABEL)
    ]

    negated = [
        claim for claim in claims if claim["class"] == CLASS_NEGATED
    ]

    if positives and all(claim.get("source") == SOURCE_PROVIDER_ONLY for claim in positives) and any(
        claim.get("element") in {"window", "entrance", "opening", "stair", "duct", "column", "axis", "level", "shaft"}
        for claim in positives
    ):
        return STATUS_DENIED if negated else STATUS_PROVIDER_ONLY

    if object_claims:

        return STATUS_VISIBLE

    if symbol_claims and not weak_claims:

        return STATUS_SYMBOL

    if symbol_claims:

        return STATUS_SYMBOL

    # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — a LABEL that nothing
    # else in the payload corroborates is a provider-only claim. It is
    # kept and reported, but it can never become an architectural fact.
    if likely_claims:

        label_claims = [
            claim for claim in likely_claims
            if claim["class"] == CLASS_LABEL
        ]

        others = [
            claim for claim in positives
            if claim["class"] != CLASS_LABEL
        ]

        if label_claims and not others and not negated:

            return STATUS_PROVIDER_ONLY

        return STATUS_LIKELY

    if weak_claims:

        return STATUS_UNVERIFIED

    if negated:

        return STATUS_DENIED

    return STATUS_NOT_REPORTED


# ----------------------------------------------------------
# EXPECTED ELEMENTS
# ----------------------------------------------------------

def _corpus_record(space_id):

    try:

        from core.curriculum.space_types_v1 import space_types

        return space_types.space(space_id) or {}

    except Exception:

        return {}


def expected_elements(space_type):

    """(element_id, source) expected for a space type, from the CORPUS."""

    expected = []

    def add(element_id, source):

        if not element_id:

            return

        if any(entry[0] == element_id for entry in expected):

            return

        expected.append((element_id, source))

    space_id = SPACE_TYPE_TO_CORPUS.get(_lower(_text(space_type)))

    if not space_id:

        return expected

    record = _corpus_record(space_id)

    if not record:

        return expected

    role = _lower(_text(record.get("functional_role")))

    for marker, element_id in SELF_ELEMENT_BY_ROLE:

        if marker in role:

            add(element_id, "CORPUS:" + space_id + ".functional_role")

            break

    for adjacent in record.get("typical_adjacent") or []:

        add(
            ADJACENT_ELEMENT.get(str(adjacent).upper()),
            "CORPUS:" + space_id + ".typical_adjacent." + str(adjacent),
        )

    access = record.get("access_requirements") or {}

    if str(access.get("requires_door", "")).upper() == "REQUIRED":

        add("entrance", "CORPUS:" + space_id + ".access_requirements.requires_door")

    if SANITARY_IMPLIES_WC and any(
        element_id == "bathroom_or_ensuite" for element_id, _source in expected
    ):

        add("wc", "DERIVED:sanitary zone implies a WC fixture")

    return expected


# ==========================================================
# THE GROUNDING
# ==========================================================

def ground_vision_evidence(understanding, user_text="", space_type=None):

    """Ground a provider payload into evidence-backed element statuses.

    Read-only. Returns the `ArchitecturalVisionGroundingV1` contract.
    """

    raw = understanding if isinstance(understanding, dict) else {}

    claims = _claims(raw)

    by_element = {}

    for claim in claims:

        by_element.setdefault(claim["element"], []).append(claim)

    safety = raw.get("safety") if isinstance(raw.get("safety"), dict) else {}

    region_supported = bool(
        safety.get("supports_region_grounding", False)
    )

    elements = []

    visible = []

    likely = []

    provider_only = []

    unverified = []

    symbol_readings = []

    denied = []

    not_reported = []

    conflicts = []

    rejected = []

    for element_id in ELEMENTS:

        element_claims = by_element.get(element_id, [])

        status = _status(element_claims)

        positive = [
            claim for claim in element_claims
            if claim["class"] in (CLASS_OBJECT, CLASS_MENTION,
                                  CLASS_LABEL, CLASS_SYMBOL)
        ]

        negative = [
            claim for claim in element_claims
            if claim["class"] == CLASS_NEGATED
        ]

        if positive and negative:

            conflicts.append({

                "element": element_id,

                "resolved": status,

                "positive": [claim["phrase"] for claim in positive],

                "negative": [claim["phrase"] for claim in negative],

            })

        for claim in element_claims:

            if claim["class"] == CLASS_INFERRED:

                rejected.append({

                    "element": element_id,

                    "phrase": claim["phrase"],

                    "reason_code": "inference",

                    "reason": (
                        "inference, not observation — an inferred element "
                        "is never treated as visible evidence"
                    ),

                })

            elif status == STATUS_UNVERIFIED and claim["class"] == CLASS_MENTION:

                rejected.append({

                    "element": element_id,

                    "phrase": claim["phrase"],

                    "reason_code": "mention_only",

                    "reason": (
                        "listed in the provider's element list, but the "
                        "observation field does not state it"
                    ),

                })

            elif status == STATUS_SYMBOL and claim["class"] == CLASS_SYMBOL:

                rejected.append({

                    "element": element_id,

                    "phrase": claim["phrase"],

                    "reason_code": "symbol_reading",

                    "reason": (
                        "read as a plan symbol — the provider itself "
                        "declares that plan symbols are read conservatively "
                        "and may be incomplete"
                    ),

                })

        entry = {

            "element": element_id,

            "status": status,

            "phrase": ELEMENTS[element_id]["phrase"],

            "evidence": element_claims,

        }

        if status == STATUS_VISIBLE:

            visible.append(element_id)

        elif status == STATUS_SYMBOL:

            symbol_readings.append(element_id)

        elif status == STATUS_LIKELY:

            likely.append(element_id)

        elif status == STATUS_PROVIDER_ONLY:

            provider_only.append(element_id)

        elif status == STATUS_UNVERIFIED:

            unverified.append(element_id)

        elif status == STATUS_DENIED:

            denied.append(element_id)

        else:

            not_reported.append(element_id)

        elements.append(entry)

    # VISION_END_TO_END_RETENTION_FIX_V1 — SCOPE-level conflicts between a
    # provider ABSENCE and a local PRESENCE are appended to the same list.
    conflicts.extend(_scope_conflicts(raw))

    # ---- expected vs reported ----------------------------------------

    expected = expected_elements(space_type)

    gaps = []

    for element_id, source in expected:

        status = next(
            (
                entry["status"] for entry in elements
                if entry["element"] == element_id
            ),
            STATUS_NOT_REPORTED,
        )

        # ARCHITECTURAL_VISION_OBSERVATION_V2 — an element the provider
        # NAMED (a readable label, a visible relation) is REPORTED, so it
        # is not a gap. Only a genuinely missing element is surfaced.
        if status not in (STATUS_VISIBLE, STATUS_LIKELY):

            gaps.append({

                "element": element_id,

                "status": status,

                "source": source,

            })

    if not region_supported:

        rejected.append({

            "element": None,

            "phrase": None,

            "reason_code": "no_region_grounding",

            "reason": (
                "the provider cannot ground pixel regions (no bounding "
                "boxes), so no element claim is region-verified"
            ),

        })

    grounding = {

        "contract": CONTRACT,

        "version": VERSION,

        "space_type": space_type,

        "provider": raw.get("provider"),

        "model": raw.get("model"),

        "image_type": raw.get("image_type"),

        # General observer claims have already crossed the independent local
        # verifier. Retain all verdicts without promoting candidates via the
        # legacy provider confidence/phrase rules.
        "provider_candidates": raw.get("provider_candidates", []),
        "grounded_provider_evidence": raw.get("grounded_provider_evidence", []),

        "visible_elements": visible,

        "likely_elements": likely,

        "provider_only_elements": provider_only,

        "unverified_elements": unverified,

        "symbol_readings": symbol_readings,

        "denied_elements": denied,

        "not_reported_elements": not_reported,

        "expected_elements": [
            {"element": element_id, "source": source}
            for element_id, source in expected
        ],

        "expected_gaps": gaps,

        "rejected_claims": rejected,

        "conflicts": conflicts,

        "elements": elements,

        "region_grounding": {

            "supported": region_supported,

            "grounded_elements": [],

        },

        "rules": [
            "an element is visible only when the provider's observation "
            "field states it as an object",
            "a readable room LABEL on a plan, or a visible RELATION "
            "between two spaces, makes an element LIKELY — named by the "
            "provider, but not observed as an object",
            "a LABEL that NOTHING else in the payload corroborates is "
            "provider_only — reported, never a fact",
            "a plan symbol reading is not visibility",
            "an inferred element is never evidence",
            "absence is claimed only when the provider states it",
            "everything else is not_reported — unknown, never absent",
        ],

        "read_only": True,

        "llm_used": False,
        "network_used": False,
        "storage_used": False,
        "render_requested": False,
        "geometry_touched": False,
        "comfy_invoked": False,
    }

    return grounding


# ----------------------------------------------------------
# PROJECTION INTO THE INTERPRETER'S VOCABULARY
# ----------------------------------------------------------

def visible_phrases(grounding):

    """The architectural phrases of the GROUNDED visible elements."""

    if not isinstance(grounding, dict):

        return []

    phrases = []

    for element_id in grounding.get("visible_elements") or []:

        phrase = (ELEMENTS.get(element_id) or {}).get("phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    return phrases


def likely_phrases(grounding):

    """The architectural phrases of the LIKELY elements.

    ARCHITECTURAL_VISION_OBSERVATION_V2 — elements the provider NAMED (a
    readable plan label, or a visible relation between two spaces). They
    are evidence, but a weaker tier than an observed object, and they are
    published as their own list so the two are never confused.
    """

    if not isinstance(grounding, dict):

        return []

    phrases = []

    for element_id in grounding.get("likely_elements") or []:

        phrase = (ELEMENTS.get(element_id) or {}).get("phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    return phrases


def element_label(element_id, language="en"):

    """A short human label for an element id."""

    labels = {

        "sleeping_element": ("تخت/عنصر خواب", "sleeping element"),

        "double_bed": ("تخت دونفره", "double bed"),

        "wardrobe_or_closet": ("کمد/کلوزت", "wardrobe or closet"),

        "bathroom_or_ensuite": ("حمام/سرویس", "bathroom or ensuite"),

        "wc": ("سرویس فرنگی/WC", "WC"),

        "entrance": ("ورودی", "entrance"),

        "circulation": ("راهرو/گردش", "circulation"),

        "window": ("پنجره", "window"),
        # W4.2A-8 — a DOOR is its own observation. It is not an entrance.
        "door": ("در", "door"),
        "stair": ("پله", "stair run"),
        "duct": ("داکت احتمالی", "service shaft candidate"),
        "shaft": ("چاهک احتمالی", "core shaft candidate"),
        "column": ("ستون احتمالی", "column candidate"),
        "axis": ("محور شبکه", "grid axis"),
        "level": ("نشانه تراز", "level marker"),

        "opening": ("بازشو", "opening"),

        "seating": ("نشیمن", "seating"),

        "kitchen": ("آشپزخانه", "kitchen"),

        "wall": ("دیوار", "wall"),

        "floor": ("کف", "floor"),

        "balcony": ("بالکن", "balcony"),

        "facade": ("نما", "facade"),

        "room": ("حجم اتاق", "room volume"),

        "bedroom": ("اتاق خواب/فضای خصوصی", "bedroom / private room"),

        "garden": ("محوطه", "garden"),

        "desk": ("میز", "work surface"),

        "storage": ("انباری", "storage"),
    }

    pair = labels.get(element_id)

    if not pair:

        return str(element_id or "")

    return pair[0] if str(language).startswith("fa") else pair[1]


def render_grounding(grounding, language="fa"):

    """The grounding as a short, honest block, or "".

    Lists what is EVIDENCED, what was claimed without evidence, and which
    EXPECTED zones were never reported. Deterministic.
    """

    if not isinstance(grounding, dict):

        return ""

    lang = "fa" if str(language or "").startswith("fa") else "en"

    visible = grounding.get("visible_elements") or []

    likely = grounding.get("likely_elements") or []

    weak = (grounding.get("symbol_readings") or []) + (
        grounding.get("unverified_elements") or []
    )

    denied = grounding.get("denied_elements") or []

    gaps = grounding.get("expected_gaps") or []

    if lang == "fa":

        lines = ["بررسی شواهد تصویری:"]

        if visible:

            lines.append(
                "• با شاهد تصویری: "
                + "، ".join(element_label(item, lang) for item in visible)
            )

        else:

            lines.append("• هیچ عنصری با شاهد تصویری کافی تأیید نشد.")

        if likely:

            lines.append(
                "• احتمالی (نام‌برده‌شده با برچسب خوانده‌شده یا رابطهٔ "
                "دیده‌شده): "
                + "، ".join(element_label(item, lang) for item in likely)
            )

        if weak:

            lines.append(
                "• گزارش‌شده ولی بدون شاهد کافی (تأییدنشده): "
                + "، ".join(element_label(item, lang) for item in weak)
            )

        if denied:

            lines.append(
                "• با شاهد نبودن: "
                + "، ".join(element_label(item, lang) for item in denied)
            )

        if gaps:

            lines.append(
                "• انتظار می‌رفت دیده شود ولی گزارش نشده (نامشخص، نه غایب): "
                + "، ".join(
                    element_label(entry.get("element"), lang)
                    for entry in gaps
                )
            )

        return "\n".join(lines)

    lines = ["Visual evidence check:"]

    if visible:

        lines.append(
            "• With visual evidence: "
            + ", ".join(element_label(item, lang) for item in visible)
        )

    else:

        lines.append("• No element is confirmed by visual evidence.")

    if likely:

        lines.append(
            "• Likely (named by a readable label or a visible relation): "
            + ", ".join(element_label(item, lang) for item in likely)
        )

    if weak:

        lines.append(
            "• Reported without sufficient evidence (unverified): "
            + ", ".join(element_label(item, lang) for item in weak)
        )

    if denied:

        lines.append(
            "• Stated as not visible: "
            + ", ".join(element_label(item, lang) for item in denied)
        )

    if gaps:

        lines.append(
            "• Expected but never reported (unknown, not absent): "
            + ", ".join(
                element_label(entry.get("element"), lang) for entry in gaps
            )
        )

    return "\n".join(lines)

