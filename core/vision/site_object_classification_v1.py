"""SITE_OBJECT_CLASSIFICATION_V1 — separate permanent architecture from site objects.

WHY THIS EXISTS
===============

The vision analysis already reports what stands in front of the building:

    occlusions : ["scaffolding", "debris on ground"]
    evidence   : "Scaffolding poles and supports visible on the facade"

Nothing consumed that evidence. `_reference_ab_section()` read floor count,
symmetry, window rhythm, balcony presence and roof features — and dropped
`occlusions` entirely. Measured consequence (V4 §6): a conditioned output kept
the scaffolding and signage while LOSING the curved balconies, because nothing
in the render instruction ever said which of the observed objects were
architecture and which were the worksite.

WHAT THIS IS, AND IS NOT
========================

This is NOT a detector. It opens no image, calls no model and adds no CV. It
is a lexical PROJECTION over strings the vision layer already reported, using
an explicit vocabulary. Anything it cannot classify is returned as
`uncertain` — never guessed into a category, never silently dropped.

The four-way split is the one the product needs:

    permanent_geometry  — massing, floors, slabs, balconies, openings, arches,
                          staircases, rooflines: the building itself
    permanent_details   — cladding, cornices, pilasters, balustrades, surrounds,
                          ornament: applied architecture
    temporary_objects   — scaffolding, platforms, debris, signage, equipment:
                          present only while the worksite exists
    site_context        — trees, walls, paths, ground: independent of the building

`uncertain` keeps everything else, so a caller can say "I do not know" instead
of inventing an answer.
"""

CONTRACT = "SiteObjectClassificationV1"
VERSION = "1.0"

PERMANENT_GEOMETRY = "permanent_geometry"
PERMANENT_DETAILS = "permanent_details"
TEMPORARY_OBJECTS = "temporary_objects"
SITE_CONTEXT = "site_context"
UNCERTAIN = "uncertain"

#: Longest-token-first matching keeps "temporary platform" from being read as
#: a structural slab. Every entry is a lowercase substring tested against the
#: reported phrase.
_VOCABULARY = (
    # ---- temporary worksite objects -------------------------------------
    (TEMPORARY_OBJECTS, (
        "scaffold", "temporary platform", "temporary stair", "temporary support",
        "formwork", "shoring", "debris", "rubble", "loose brick",
        "loose material", "construction sign", "signage", "banner", "hoarding",
        "barrier tape", "safety net", "crane", "mixer", "cement bag", "skip",
        "dumpster", "plastic sheeting", "worksite", "construction equipment",
        "scaffolding poles", "scaffolding",
    )),
    # ---- independent site context ---------------------------------------
    (SITE_CONTEXT, (
        "tree", "shrub", "hedge", "planting", "planter", "lawn", "grass",
        "garden", "ground level", "path", "pavement", "retaining wall",
        "boundary wall", "fence", "pole", "street", "adjacent building",
        "neighbouring", "neighboring", "car", "vehicle", "people", "person",
        "sky", "cloud",
    )),
    # ---- applied architectural detail ------------------------------------
    (PERMANENT_DETAILS, (
        "cladding", "cornice", "frieze", "pilaster", "balustrade", "surround",
        "moulding", "molding", "pediment", "ornament", "relief", "tilework",
        "tile work", "railing", "grille", "shutter", "awning", "dentil",
        "capital", "architrave", "plaster", "render finish", "window frame",
        "door frame", "gutter", "downpipe",
    )),
    # ---- the building itself ---------------------------------------------
    (PERMANENT_GEOMETRY, (
        "massing", "floor level", "floor", "storey", "story", "slab",
        "balcony", "opening", "window", "doorway", "door", "arch", "vault",
        "staircase", "stair", "roofline", "roof", "parapet", "column",
        "pillar", "beam", "wall", "facade contour", "cantilever", "projection",
        "curve", "curved", "wave", "dome", "chimney", "gable",
    )),
)


def _category_of(phrase):
    """The category for one reported phrase, or UNCERTAIN."""

    text = str(phrase or "").lower()

    if not text.strip():
        return UNCERTAIN

    for category, tokens in _VOCABULARY:

        for token in tokens:

            if token in text:
                return category

    return UNCERTAIN


def _as_list(value):

    if value in (None, "", [], {}):
        return []

    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()]


def classify_site_objects(analysis, extra_fields=()):
    """Classify what ONE analysis reported, without adding anything.

    `analysis` is an existing `ReferenceArchitecturalAnalysisV1` (or any
    contract carrying `occlusions` / `evidence`). `extra_fields` lets a caller
    include another reported list, e.g. `("uncertainties",)`.

    Returns `SiteObjectClassificationV1`. Every entry keeps the phrase it came
    from and the field it was reported in, so the classification is auditable.
    """

    analysis = analysis if isinstance(analysis, dict) else {}

    fields = ("occlusions", "evidence") + tuple(extra_fields or ())

    buckets = {
        PERMANENT_GEOMETRY: [],
        PERMANENT_DETAILS: [],
        TEMPORARY_OBJECTS: [],
        SITE_CONTEXT: [],
        UNCERTAIN: [],
    }

    seen = set()

    for field in fields:

        for phrase in _as_list(analysis.get(field)):

            key = (field, phrase.lower())

            if key in seen:
                continue

            seen.add(key)

            category = _category_of(phrase)

            buckets[category].append({
                "phrase": phrase,
                "category": category,
                "source_field": field,
            })

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "permanent_geometry": buckets[PERMANENT_GEOMETRY],
        "permanent_details": buckets[PERMANENT_DETAILS],
        "temporary_objects": buckets[TEMPORARY_OBJECTS],
        "site_context": buckets[SITE_CONTEXT],
        "uncertain": buckets[UNCERTAIN],
        "counts": {key: len(value) for key, value in buckets.items()},
        "classification_method": "lexical_projection_over_reported_strings",
        "detector_used": False,
        "provider_calls": 0,
        "image_opened": False,
    }


def temporary_object_phrases(classification):
    """The reported phrases that are temporary construction objects."""

    classification = classification if isinstance(classification, dict) else {}

    return [entry["phrase"] for entry in classification.get("temporary_objects") or []]


# ==========================================================
# INTENT — is this a request for the FINISHED building?
# ==========================================================

#: A request to visualise the completed building. Deliberately narrow: an
#: ambiguous request must NOT authorise removal, so only an explicit finish
#: word counts.
_FINISHED_MARKERS = (
    "finished", "complete", "completed", "final", "as built", "as-built",
    "after construction", "finished facade", "clean facade", "remove the scaffolding",
    "without scaffolding", "no scaffolding", "پایان کار", "تکمیل شده",
    "تکمیل‌شده", "نهایی", "بدون داربست",
)

#: A request that asks for the building AS IT IS. Removal is never allowed.
_AS_BUILT_MARKERS = (
    "as built", "as-built", "current state", "existing condition",
    "what is there now", "unfinished building", "construction stage",
    "وضعیت فعلی", "همان‌طور که هست", "در حال ساخت",
)


def request_wants_finished_building(text):
    """(bool, evidence) — did the request explicitly ask for the finished state?

    Ambiguity resolves to False: removing a construction object is only ever
    authorised by an explicit request.
    """

    lowered = str(text or "").lower()

    if not lowered.strip():
        return False, None

    for marker in _AS_BUILT_MARKERS:

        if marker in lowered:
            return False, "as_built_request:" + marker

    for marker in _FINISHED_MARKERS:

        if marker in lowered:
            return True, "finished_request:" + marker

    return False, None
