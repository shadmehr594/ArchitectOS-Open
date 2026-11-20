# ==========================================================
# ArchitectOS Image Understanding Contract v1
#
# VISION_IMAGE_REGISTRY_04
#
# One safe, structured image-understanding contract that any vision
# provider must feed. The validator is the gate: it decides what may
# be reported as OBSERVED versus INFERRED versus REJECTED.
#
# Safety doctrine
#   REFERENCE IMAGE IS NON-AUTHORITATIVE FOR BUILDING GEOMETRY.
#
#   Vision may describe/reference:
#     visible facade elements, visible materials, visible openings,
#     visible room labels / plan symbols when clear,
#     composition / style / lighting, approximate visual relationships
#
#   Vision must NOT silently:
#     mutate canonical geometry, infer unseen floors, invent
#     dimensions, relocate openings, overwrite design intent
#
# Enforcement
#   HARD REJECT (never reportable): dimensions / measurements,
#     compass orientation, unseen floors or hidden geometry,
#     absolute geographic location.
#   DEMOTE observed -> inferred (attributable but unverifiable):
#     material claims, structural claims, room-type claims,
#     building-type claims.
#
# The validator never invents content: it only keeps, demotes or
# rejects what the provider actually returned.
# ==========================================================


from __future__ import annotations


import copy
import os
import re


from core.vision.local_plan_reader_v1 import local_ocr_environment


CONTRACT = "ImageUnderstandingV1"
VERSION = "1.0"


# ==========================================================
# ENUMS
# ==========================================================

IMAGE_TYPES = (
    "architectural_render_or_photo",
    "facade_or_elevation",
    "floor_plan_or_sketch",
    "site_diagram",
    "unknown",
)


STATUS_ANALYZED = "ANALYZED"
STATUS_ANALYZED_WITH_UNCERTAINTY = "ANALYZED_WITH_UNCERTAINTY"
STATUS_PARTIAL = "PARTIAL"
STATUS_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
STATUS_UNSUPPORTED_IMAGE = "UNSUPPORTED_IMAGE"
STATUS_FAILED = "FAILED"


CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")


SOURCE_TYPES = (
    "uploaded",
    "text_to_image",
    "image_to_image",
    "render",
    "other",
)


# LOCAL_PLAN_READING_V1 — the evidence-pipeline version stamped on EVERY
# understanding. `image_session_v1.analyze_record` only reuses a cached
# analysis whose stamp matches, so an analysis produced by an OLDER
# evidence chain (e.g. before the local plan reader existed) can never be
# served to the UI. Bump this whenever the evidence chain changes.
EVIDENCE_PIPELINE_VERSION = "w4-2a-general-visual-observer-bridge-v1"

# VISION_RETENTION_FIX_V2 — the canonical image type is now gated on POSITIVE
# local plan-structure evidence (see `_image_type_evidence` and
# `local_evidence_trust_v1.local_plan_structure_evidence`). There is no longer
# a sheet-type shortcut here.


REQUIRED_PROVIDER_KEYS = (
    "image_type",
    "observed",
    "inferred",
    "unresolved",
    "confidence",
    "architectural_elements",
    "text_labels_if_visible",
)


# ==========================================================
# SAFETY RULES
# ==========================================================

# Invented measurement / dimension claims.
_DIMENSION_RE = re.compile(
    r"(\d+(\.\d+)?\s*(mm|cm|m|km|ft|feet|inch|in\b|meter|meters|metre|metres))"
    r"|(\d+(\.\d+)?\s*(متر|سانتی\s*متر|سانتیمتر|میلی\s*متر|میلیمتر))"
    r"|(\d+(\.\d+)?\s*[x×]\s*\d+(\.\d+)?)",
    re.IGNORECASE,
)

# Compass orientation can never be established from an arbitrary image.
_ORIENTATION_TERMS = (
    "north", "south", "east", "west",
    "northeast", "northwest", "southeast", "southwest",
    "شمالی", "جنوبی", "شرقی", "غربی",
    "شمال", "جنوب", "شرق", "غرب",
)

# Geometry / floors that cannot be seen.
_UNSEEN_GEOMETRY_TERMS = (
    "hidden floor", "unseen floor", "upper floors not visible",
    "floors not visible", "basement level", "underground level",
    "طبقات نامرئی", "طبقه پنهان", "طبقات پنهان", "زیرزمین دیده",
)

# Absolute location claims.
_LOCATION_TERMS = (
    "located in", "city of", "country of", "in tehran", "in dubai",
    "واقع در", "شهر ", "کشور ",
)

_HARD_REJECT_RULES = (
    ("invented_dimension", _DIMENSION_RE),
    ("unsupported_orientation", _ORIENTATION_TERMS),
    ("unseen_geometry", _UNSEEN_GEOMETRY_TERMS),
    ("absolute_location", _LOCATION_TERMS),
)

# Claims that must be demoted out of `observed` because visual
# support cannot be verified from the returned data alone.
_DEMOTE_TERMS = (
    "material", "materials", "concrete", "glass", "stone", "brick",
    "wood", "steel", "metal", "aluminium", "aluminum", "travertine",
    "مصالح", "متریال", "بتن", "شیشه", "سنگ", "آجر", "چوب", "فلز",
    "structural", "load-bearing", "load bearing", "beam", "column",
    "foundation", "slab", "سازه", "باربر", "تیر", "ستون", "فونداسیون",
    "bedroom", "living room", "kitchen", "bathroom", "office", "lobby",
    "اتاق خواب", "نشیمن", "آشپزخانه", "حمام", "اداری", "لابی",
    "residential", "commercial", "villa", "apartment", "office building",
    "مسکونی", "تجاری", "ویلا", "آپارتمان",
)


def _as_text(value):

    if value is None:

        return ""

    if isinstance(value, str):

        return " ".join(value.split())

    return " ".join(str(value).split())


def _as_list(value):

    if value is None:

        return []

    if isinstance(value, str):

        return [_as_text(value)] if _as_text(value) else []

    if isinstance(value, (list, tuple)):

        out = []

        for item in value:

            text = _as_text(item)

            if text and text not in out:

                out.append(text)

        return out

    text = _as_text(value)

    return [text] if text else []


def classify_claim(text):
    """Return (verdict, reason) for one provider claim.

    verdict: "keep" | "demote" | "reject"
    """

    lowered = text.lower()

    for reason, rule in _HARD_REJECT_RULES:

        if reason == "invented_dimension":

            if rule.search(text):

                return "reject", reason

        else:

            for term in rule:

                if term in lowered:

                    return "reject", reason

    for term in _DEMOTE_TERMS:

        if term in lowered:

            return "demote", "unverifiable_" + term.replace(" ", "_")

    return "keep", None



# ==========================================================
# VALIDATION
# ==========================================================

def _screen(items, sink_kept, sink_demoted, rejected, field):

    for text in _as_list(items):

        verdict, reason = classify_claim(text)

        if verdict == "reject":

            rejected.append({
                "field": field,
                "reason": reason,
                "value": text,
            })

            continue

        if verdict == "demote":

            sink_demoted.append(text)

            continue

        sink_kept.append(text)


def _local_diagnostics(local):
    """Runtime facts only; never feed these fields into visual classification."""
    if not isinstance(local, dict):
        return None
    fields = (
        "status", "reason", "image_size", "plan_bbox_pixels",
        "ocr_status", "ocr_reason", "symbol_analysis_status", "symbol_reason",
        "element_analysis_status", "element_reason", "symbol_pipeline_version",
        "element_pipeline_version", "ocr_candidate_count", "ocr_engine",
        "ocr_language", "geometry_engine", "limitations",
    )
    diagnostics = {key: copy.deepcopy(local[key]) for key in fields if key in local}
    capabilities = [local.get(key) for key in (
        "ocr_status", "symbol_analysis_status", "element_analysis_status"
    )]
    if local.get("status") == "grounded":
        state = "LOCAL_EVIDENCE_PARTIAL"
    elif local.get("status") == "unavailable" or "unavailable" in capabilities:
        state = "CAPABILITY_UNAVAILABLE"
    elif local.get("status") == "no_grounded_evidence" and all(
        status == "analyzed" for status in capabilities
    ):
        state = "IMAGE_EVIDENCE_INSUFFICIENT"
    else:
        state = "UNKNOWN"
    diagnostics["evidence_state"] = state
    diagnostics["evidence_type"] = "RUNTIME_STATUS"
    return diagnostics


def build_understanding(
    raw,
    *,
    provider="none",
    model="none",
    image_id=None,
    source_type="other",
    source_hash=None,
    supports_grounding=False,
    provider_error=None,
    local_plan_reading=None,
):
    """Validate a raw provider observation into the canonical contract."""

    from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
    if isinstance(raw, dict) and raw.get("contract") == BRIDGE_CONTRACT:
        return _build_bridge_understanding(
            raw, provider=provider, model=model, image_id=image_id,
            source_type=source_type, source_hash=source_hash,
            local_plan_reading=local_plan_reading,
        )

    if source_type not in SOURCE_TYPES:

        source_type = "other"


    rejected = []

    observed = []

    demoted = []

    inferred = []

    unresolved = []

    elements = []

    labels = []


    if isinstance(raw, dict) and isinstance(raw.get("local_plan_reading"), dict):
        local_plan_reading = raw["local_plan_reading"]
    local_diagnostics = _local_diagnostics(local_plan_reading)

    if not isinstance(raw, dict):

        result = _unavailable(
            STATUS_FAILED if provider_error is None else STATUS_PROVIDER_UNAVAILABLE,
            provider,
            model,
            image_id,
            source_type,
            source_hash,
            provider_error or "provider_non_structured_output",
            supports_grounding,
            local_diagnostics=local_diagnostics,
        )
        # A provider failure cannot erase independently obtained local evidence.
        result["local_plan_reading"] = copy.deepcopy(local_plan_reading)
        result["evidence_pipeline"] = EVIDENCE_PIPELINE_VERSION
        result["local_ocr_environment"] = local_ocr_environment()
        return result


    image_type = _as_text(raw.get("image_type")).lower().replace(" ", "_")

    if image_type not in IMAGE_TYPES:

        image_type = "unknown"


    confidence_raw = raw.get("confidence")

    # providers may return a level ("HIGH") or a numeric score (0.95)
    if isinstance(confidence_raw, (int, float)) and not isinstance(confidence_raw, bool):

        score = float(confidence_raw)

        if score >= 0.75:

            confidence = "HIGH"

        elif score >= 0.45:

            confidence = "MEDIUM"

        else:

            confidence = "LOW"

    else:

        confidence = _as_text(confidence_raw).upper()

        if confidence not in CONFIDENCE_LEVELS:

            confidence = "LOW"


    _screen(raw.get("observed"), observed, demoted, rejected, "observed")

    _screen(raw.get("inferred"), inferred, demoted, rejected, "inferred")

    _screen(
        raw.get("architectural_elements"),
        elements,
        demoted,
        rejected,
        "architectural_elements",
    )

    # text labels are reported verbatim (visible text is evidence),
    # but still screened for hard-reject content such as dimensions.
    for label in _as_list(raw.get("text_labels_if_visible")):

        verdict, reason = classify_claim(label)

        if verdict == "reject":

            rejected.append({
                "field": "text_labels_if_visible",
                "reason": reason,
                "value": label,
            })

            continue

        labels.append(label)


    unresolved.extend(_as_list(raw.get("unresolved")))

    # ARCHITECTURAL_OBSERVATION_V1 — the v3 provider categories are carried
    # through VERBATIM so the architectural observation contract can expose
    # them. They are observations, never geometry claims, and they are not
    # screened away: screening them is what hid visible evidence.
    observation_extras = {}

    for key in (
        "visible_floors",
        # ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 — the lower-trust storey
        # reading. It travels on the observational-metadata channel, NOT into
        # `observed`, so verified-evidence consumers are unaffected.
        "visible_floors_observation",
        "material_observations",
        "texture_color_observations",
        "style_indicators",
        "spatial_clues",
        "furniture_elements",
        "object_elements",
    ):

        value = raw.get(key)

        if value not in (None, [], "", {}):

            observation_extras[key] = value

    # LOCAL_PLAN_READING_V1 — provider-independent OCR/raster evidence is a
    # separate contract.  It is never folded into the provider's raw labels;
    # downstream consumers can therefore reconcile the two sources explicitly.
    if not isinstance(local_plan_reading, dict):

        local_plan_reading = None


    # demoted claims are attributable but unverifiable -> inferred
    #
    # ARCHITECTURAL_OBSERVATION_V1 — the `inferred` band is UNCHANGED for
    # every existing consumer. What changes is that a demoted claim is no
    # longer rewritten as "unverified from image: ..." and pushed into
    # `unresolved`: that phrasing hid VISIBLE evidence behind an unknown.
    # The claim is a visible observation that is merely non-authoritative
    # for geometry, so it is reported in its own band with its evidence.
    observed_attributed = []

    for text in demoted:

        if text not in inferred:

            inferred.append(text)

        if text not in observed_attributed:

            observed_attributed.append(text)


    if not observed and not inferred:

        status = STATUS_PARTIAL

    elif confidence == "LOW" or unresolved:

        status = STATUS_ANALYZED_WITH_UNCERTAINTY

    else:

        status = STATUS_ANALYZED


    # ARCHITECTURAL_FACADE_ELEMENT_EVIDENCE_V7.1 — carry validated grounded
    # element evidence through to consumers. Only real evidence is carried: an
    # absent or empty collection becomes None so nothing downstream can mistake
    # "no evidence" for "evidence of nothing", and no empty collection is ever
    # fabricated.
    _element_evidence = (
        copy.deepcopy(raw["element_evidence"])
        if isinstance(raw, dict)
        and isinstance(raw.get("element_evidence"), dict)
        and (raw["element_evidence"].get("elements") or [])
        else None
    )


    return {

        "contract": CONTRACT,
        "version": VERSION,

        "image_id": image_id,
        "source_type": source_type,
        "source_hash": source_hash,

        "analysis_status": status,

        "provider": provider,
        "model": model,

        "image_type": image_type,
        # VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1 — the SOURCE MEDIUM, kept
        # apart from the image type. `build_understanding` only sees the legacy
        # provider payload, so it can never establish a medium; the bridge
        # adapter overwrites this with the derived record. The key is always
        # present so no consumer has to handle two record shapes.
        "image_medium": _medium_record(None),

        "observed": observed,
        # ARCHITECTURAL_OBSERVATION_V1 — visible evidence that is
        # attributable but not verifiable for geometry. Kept VISIBLE here
        # instead of being hidden inside `unresolved`.
        "observed_attributed": observed_attributed,
        "inferred": inferred,
        "unresolved": unresolved,
        # ARCHITECTURAL_OBSERVATION_V1 — verbatim v3 provider categories.
        "observation_extras": observation_extras,

        "confidence": confidence,

        "architectural_elements": elements,
        # V7.1 — None unless real validated evidence is present.
        "element_evidence": _element_evidence,
        "text_labels_if_visible": labels,
        "local_plan_reading": local_plan_reading,
        "local_diagnostics": local_diagnostics,
        "runtime_status": copy.deepcopy(raw.get("runtime_status") or []),

        # Which evidence pipeline produced this understanding. A cache
        # entry without the CURRENT stamp is stale by definition.
        "evidence_pipeline": EVIDENCE_PIPELINE_VERSION,

        # LOCAL_PLAN_READING_V1 — the OCR environment this understanding was
        # produced under. An entry recorded while the local reader could not
        # run (no compiled backend / no Persian language data) is NOT a
        # current result once the environment is repaired, so the cache layer
        # compares this fingerprint before reusing anything.
        "local_ocr_environment": local_ocr_environment(),

        "safety": {

            # Non-negotiable: vision never becomes authoritative geometry.
            "geometry_authoritative": False,

            "analysis_only": True,

            "rejected_claims": rejected,

            "supports_region_grounding": bool(supports_grounding),
            "supports_local_region_grounding": bool(
                local_plan_reading
                and local_plan_reading.get("status") == "grounded"
            ),

            "limitations": _limitations(image_type, supports_grounding),

        },

    }



def _limitations(image_type, supports_grounding):

    limits = [

        "vision describes only what is visually present",
        "no dimensions or measurements are inferred",
        "no compass orientation is inferred",
        "no unseen floors or hidden geometry are inferred",
        "reference image is non-authoritative for building geometry",

    ]

    if image_type == "floor_plan_or_sketch":

        limits.append("plan symbols are read conservatively and may be incomplete")

    if not supports_grounding:

        limits.append("provider cannot ground pixel regions (no bounding boxes)")

    return limits



def _unavailable(
    status,
    provider,
    model,
    image_id,
    source_type,
    source_hash,
    reason,
    supports_grounding=False,
    local_diagnostics=None,
):
    """Truthful empty contract - never fabricated understanding."""

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "image_id": image_id,
        "source_type": source_type,
        "source_hash": source_hash,

        "analysis_status": status,

        "provider": provider,
        "model": model,

        "image_type": "unknown",
        # VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1 — no drawing-type observation
        # reached this contract, so the medium is unknown, not guessed.
        "image_medium": _medium_record(None),

        "observed": [],
        "observed_attributed": [],
        "inferred": [],
        "unresolved": [reason],

        "confidence": "LOW",

        "architectural_elements": [],
        "text_labels_if_visible": [],
        "local_plan_reading": None,
        "local_diagnostics": local_diagnostics,

        "safety": {

            "geometry_authoritative": False,
            "analysis_only": True,
            "rejected_claims": [],
            "supports_region_grounding": bool(supports_grounding),
            "supports_local_region_grounding": False,
            "limitations": _limitations("unknown", supports_grounding),
            "reason": reason,

        },

    }


def _image_type_evidence(local_plan_reading, provider_type=None):
    """(canonical image_type, auditable evidence record).

    VISION_RETENTION_FIX_V2 — the canonical type needs POSITIVE plan-structure
    evidence. A local reader reporting `grounded` means only that it found *some*
    OCR, opening, symbol or region, and its `single_plan` sheet type is the
    DEFAULT for any raster; neither may establish a plan. Equally, a model's
    drawing-type observation is only an observation and must never set the
    canonical type by itself.

    The gate therefore requires an EXISTING, positive, non-default local signal
    (see `local_evidence_trust_v1.local_plan_structure_evidence`). Provider
    agreement CORROBORATES but is never required, so ArchitectOS still works
    when provider semantics are unavailable.
    """

    from core.vision.local_evidence_trust_v1 import local_plan_structure_evidence

    structure = local_plan_structure_evidence(local_plan_reading)

    provider_canonical = None
    if isinstance(provider_type, dict):
        provider_canonical = provider_type.get("canonical")

    provider_agrees = provider_canonical == "floor_plan_or_sketch"

    # FACADE-03D — a WEAK local plan signal must not override a contradictory
    # facade/render observation. `PLAN_ELEMENT_TOPOLOGY` alone (a spurious
    # door / window / column symbol detected on a facade render) is weak: the
    # canonical type must not be forced to a plan by it. Only the STRONGER
    # families — grounded plan FURNITURE symbol topology, or a POSITIVE
    # multi-panel sheet — may still establish a plan against the model's
    # facade/render reading. The provider still never DEFINES a plan: it can
    # only withhold a plan claim that a weak local signal would otherwise make.
    strong_families = (
        "PLAN_FURNITURE_SYMBOL_TOPOLOGY",
        "MULTI_PANEL_STRUCTURE",
    )
    facade_contradiction = provider_canonical in (
        "facade_or_elevation",
        "architectural_render_or_photo",
    )
    local_strong_families = [
        family for family in structure["families"] if family in strong_families
    ]

    if structure["positive"] and facade_contradiction and not local_strong_families:
        # Report the model's own facade/render observation, but keep it a
        # NON-authoritative observation (see `provider_is_authoritative`).
        canonical = provider_canonical
        basis = "LOCAL_WEAK_PLAN_VETOED_BY_FACADE"
    elif structure["positive"]:
        canonical = "floor_plan_or_sketch"
        basis = "CORROBORATED" if provider_agrees else "LOCAL_STRUCTURAL"
    elif provider_type:
        canonical = "unknown"
        basis = "PROVIDER_OBSERVED"
    else:
        canonical = "unknown"
        basis = "UNKNOWN"

    evidence = {
        "canonical_image_type": canonical,
        "basis": basis,
        "local_positive": bool(structure["positive"]),
        "local_families": structure["families"],
        "local_signals": structure["signals"],
        "local_strong_families": local_strong_families,
        "weak_plan_vetoed_by_facade": bool(
            structure["positive"] and facade_contradiction and not local_strong_families
        ),
        "provider_drawing_type": copy.deepcopy(provider_type),
        "provider_canonical": provider_canonical,
        "provider_agrees": bool(provider_agrees),
        "provider_is_authoritative": False,
        "rule": ("floor_plan_or_sketch requires positive, non-default LOCAL "
                 "plan-structure evidence; a provider observation corroborates "
                 "but never defines it. FACADE-03D: a WEAK plan family "
                 "(PLAN_ELEMENT_TOPOLOGY alone) is additionally vetoed by a "
                 "contradictory facade/render observation; the stronger "
                 "families (furniture symbols, multi-panel sheet) are not."),
    }
    return canonical, evidence


# ==========================================================
# VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1
#
# WHAT KIND OF SOURCE IMAGE THIS IS and WHAT ARCHITECTURAL SCENE IT DEPICTS
# are separate facts and are published separately:
#
#   image_medium  photograph / rendering / drawing / unknown  <- this block
#   image_type    interior / exterior / mixed / plan / diagram / unknown
#                 (derived by `architectural_observation_v1._refine_image_type`)
#   provider_drawing_type.canonical
#                 architectural_render_or_photo / facade_or_elevation / ...
#
# `canonical_drawing_type` collapses a photograph and a 3D rendering into the
# single family `architectural_render_or_photo`, so before this record no
# consumer could tell them apart without re-parsing free text. The medium is
# derived from the provider's OWN stated drawing-type text — it is an
# observation, never verified, and it NEVER feeds `image_type`: a photograph is
# not evidence of an exterior, and a render is not evidence of one either.
# ==========================================================

_MEDIUM_NOTE = (
    "source medium of the image; NOT an architectural scene category, "
    "NOT the drawing family, and NOT an independently verified fact"
)


def _medium_record(provider_type):
    """The auditable source-medium record for the understanding contract."""

    from core.vision.drawing_type_v1 import canonical_medium

    text = None

    if isinstance(provider_type, dict):

        value = provider_type.get("text")

        text = value if isinstance(value, str) and value.strip() else None

    if text is None:

        return {
            "medium": "unknown",
            "basis": "NO_DRAWING_TYPE_OBSERVATION",
            "evidence_text": None,
            "evidence_clause": None,
            "source": "MODEL_OBSERVED",
            "verified": False,
            "note": _MEDIUM_NOTE,
        }

    derived = canonical_medium(text)

    return {
        "medium": derived["medium"],
        "basis": derived["basis"],
        "evidence_text": text,
        "evidence_clause": derived["evidence_clause"],
        "source": "MODEL_OBSERVED",
        "verified": False,
        "note": _MEDIUM_NOTE,
    }


def _floor_observation_from_structured(raw, *, provider, model):
    """An explicitly attributed, UNVERIFIED storey reading.

    ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1
    ------------------------------------------
    The observer states a storey count; the verifier cannot corroborate it
    (a photograph has no independent local evidence), so it must not become a
    verified fact. It must nonetheless SURVIVE.

    This builds a lower-trust carrier. It is deliberately NOT
    ``visible_floors``: two existing consumers treat that key as authoritative
    (``architectural_vision_interpreter_v1`` deletes floor unknowns when it is
    truthy, ``design_constraint_fidelity_v1`` reads its ``count`` for render
    verification). An unverified reading placed there would silently erase an
    honest uncertainty and could manufacture a render PASS.

    Rules enforced here:
      * confidence is capped at LOW; the provider's own claim is kept apart;
      * a self-contradictory reading is recorded as contradictory, never
        resolved by picking a number;
      * a count the observer attributed to ANOTHER building is not attributed
        to the subject;
      * nothing is promoted to geometry, dimensions or verified fact.
    """

    if not isinstance(raw, dict):
        return None

    if all(value is None for value in raw.values()):
        return None

    def _int(value):
        return None if isinstance(value, bool) or not isinstance(value, int) else value

    def _bool(value):
        return value if isinstance(value, bool) else None

    count = _int(raw.get("count"))
    upper_floors = _int(raw.get("upper_floors"))
    ground = _bool(raw.get("ground_floor_included"))
    whole = _bool(raw.get("whole_building_visible"))
    roof_excluded = _bool(raw.get("roof_band_excluded"))

    scope = raw.get("count_scope")
    scope = scope if scope in ("TOTAL", "UPPER_ONLY", "UNDETERMINED") else None

    subject = raw.get("subject")
    subject = subject if subject in ("subject", "other", "unattributed") else None

    uncertainty = raw.get("uncertainty")
    uncertainty = uncertainty.strip() if isinstance(uncertainty, str) and uncertainty.strip() else None

    quote = raw.get("evidence_quote")
    quote = quote.strip() if isinstance(quote, str) and quote.strip() else None

    reported = raw.get("provider_confidence")
    reported = reported if reported in ("HIGH", "MEDIUM", "LOW") else None

    # ---- do not attribute another building's count to the subject ----
    attributed_to = subject or "unattributed"
    if subject == "other":
        count = None
        upper_floors = None
        scope = "UNDETERMINED" if scope is None else scope

    # ---- contradictions are recorded, never resolved ----
    contradiction = None

    if count is not None:

        if scope == "TOTAL" and ground is False:
            contradiction = {"kind": "total_without_ground_floor",
                             "count": count, "ground_floor_included": False}

        elif (scope == "TOTAL" and upper_floors is not None and ground is True
                and count != upper_floors + 1):
            contradiction = {"kind": "total_disagrees_with_upper_floors",
                             "count": count, "upper_floors": upper_floors}

        elif scope == "UPPER_ONLY" and ground is True:
            contradiction = {"kind": "upper_only_but_ground_counted",
                             "count": count}

    if contradiction is not None:
        count = None

    # ---- countable is an OBSERVATIONAL property, not proof ----
    if count is None:
        countable = False
    elif whole is False:
        countable = False
    elif whole is True:
        countable = True
    else:
        countable = None

    return {
        "trust_tier": "PROVIDER_OBSERVATION",
        "verification": "UNVERIFIED",
        "authoritative": False,
        "provider": provider,
        "model": model,
        "attributed_to": attributed_to,
        "count": count,
        "count_scope": scope,
        "count_is_total": (scope == "TOTAL") if scope else None,
        "ground_floor_included": ground,
        "upper_floors": upper_floors,
        "roof_band_excluded": roof_excluded,
        "whole_building_visible": whole,
        "countable": countable,
        "uncertainty": uncertainty,
        "evidence_quote": quote,
        "provider_confidence_reported": reported,
        # The uncorroborated tier never exceeds LOW, whatever the model said.
        "confidence": "LOW",
        "contradiction": contradiction,
        "superseded_by_verified": False,
    }


def _build_bridge_understanding(bridge, *, provider, model, image_id, source_type,
                                source_hash, local_plan_reading):
    """Adapt verified evidence to legacy consumers; retain the full audit record.

    Candidate prose is never fed to legacy inference/grounding fields. Existing
    local consumers continue to read exactly their independent local contracts.
    """
    from core.vision.provider_candidate_verification_v1 import (
        provider_candidates, verify_candidates, local_ocr_evidence,
    )
    from core.vision.drawing_type_v1 import provider_drawing_type as _provider_type

    audit = copy.deepcopy(bridge)
    normalization = audit.get("normalization") or {}
    raw = audit.get("raw_observer") or {}
    candidates, verification_error = [], None
    try:
        candidates = provider_candidates(normalization, raw.get("raw_text", ""))
        candidates = verify_candidates(candidates, local_plan_reading)
    except Exception as exc:
        verification_error = type(exc).__name__ + ":" + str(exc)
        # Even a verifier defect must not leave an unverified candidate grounded.
        for candidate in candidates:
            candidate.update(state="UNVERIFIED", grounded=False)
            candidate["verification"] = {"reason": "verification_failed"}
    confirmed = [copy.deepcopy(c) for c in candidates if c["state"] == "CONFIRMED"]
    local = local_plan_reading if isinstance(local_plan_reading, dict) else {}
    local_grounded = local.get("status") == "grounded"
    # Only atomic object presence enters old semantic consumers. Typed numeric
    # and OCR evidence stays in its distinct structured category below.
    object_claims = [c["text"] for c in confirmed if c["verification"]["reason"]
                     == "independent_local_type_presence"]
    # VISION_RETENTION_FIX_V2 — the canonical type is evidence-gated and its
    # provenance is recorded beside it; the model's type stays an observation.
    provider_type = _provider_type({"provider_candidates": candidates})
    canonical_type, type_evidence = _image_type_evidence(local_plan_reading, provider_type)
    # ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 — the observer's storey
    # reading survives here, in its OWN lower-trust slot. It is never written
    # into `observed` (verified-only) and never into `visible_floors` (which
    # downstream consumers treat as authoritative).
    _structured = normalization.get("structured")
    _structured = _structured if isinstance(_structured, dict) else {}
    _floor_reading = _floor_observation_from_structured(
        _structured.get("visible_floors"), provider=provider, model=model,
    )

    legacy = {
        "image_type": canonical_type,
        "confidence": "LOW", "observed": object_claims,
        "inferred": [], "unresolved": [], "architectural_elements": [],
        "text_labels_if_visible": [], "local_plan_reading": local_plan_reading,
        "visible_floors_observation": _floor_reading,
    }
    result = build_understanding(
        legacy, provider=provider, model=model, image_id=image_id, source_type=source_type,
        source_hash=source_hash, local_plan_reading=local_plan_reading,
    )
    result.update(
        visual_observer_bridge=audit, provider_candidates=candidates,
        grounded_provider_evidence=confirmed,
        provider_verification_error=verification_error,
        vision_cache_identity=copy.deepcopy(bridge.get("cache_identity")),
        provider_drawing_type=provider_type,
        image_type_evidence=type_evidence,
        # VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1 — the medium the provider
        # stated, in its OWN field. Additive: `image_type` is not touched, and
        # the medium never becomes evidence for a scene category.
        image_medium=_medium_record(provider_type),
    )
    try:
        result["local_ocr"] = local_ocr_evidence(local)
    except Exception:
        result["local_ocr"] = []
    result["verified_ocr"] = [copy.deepcopy(c) for c in confirmed if c["verification"]["reason"]
                              in ("verbatim_independent_local_ocr", "verbatim_local_level_annotation")]

    # ==================================================
    # VISION_EVIDENCE_PROVENANCE_V1
    #
    # MEASURED DEFECT: this adapter used to report `observed: []`,
    # `observed_attributed: []`, `architectural_elements: []` and
    # `confidence: "LOW"` for EVERY bridge result, and then FORCED
    # `analysis_status = ANALYZED_WITH_UNCERTAINTY`. The observer's
    # ASSERTED claims were all present in `provider_candidates` — they
    # were simply never projected, because the only band that was filled
    # was the independently corroborated one.
    #
    # Consequence: a photograph whose observer asserted "curved concrete
    # balcony slab" was indistinguishable from a photograph where the
    # model saw nothing, and from a normalizer failure. Downstream could
    # not tell OBSERVED from INFERRED from UNKNOWN, and the vision
    # interpreter therefore projected an empty report.
    #
    # The bands are now DERIVED from the verifier's own states:
    #
    #   observed            -> independently corroborated only (unchanged)
    #   observed_attributed -> ASSERTED provider claims with no applicable
    #                          independent corroboration (attributable, not
    #                          authoritative). This is the band the contract
    #                          already documents for exactly this case.
    #   architectural_elements -> the architectural subset of the above
    #   AMBIGUOUS / UNKNOWN / interpretations are NEVER promoted; they are
    #   counted in `diagnostics` and stay out of every visible band.
    # ==================================================

    architectural_categories = (
        "observed_elements",
        "walls",
        "structural_elements",
        "vertical_circulation",
        "fixtures",
        "openings.doors",
        "openings.windows",
        "openings.other_openings",
    )

    attributed, attributed_rejected = [], []

    # ==================================================
    # DESCRIPTIVE_ARCHITECTURAL_CLAIM_RETENTION_V1
    #
    # MEASURED DEFECT: `_decision()` returns
    # `claim_properties_not_verified` for a claim whose `text` is not literally
    # the kind name — i.e. for every DESCRIPTIVE claim:
    #
    #     "top level has arched-top (round-headed) windows"   kind=window
    #
    # Such a claim has already passed every safety gate in the verifier: the
    # kind is a recognised architectural kind, the certainty is ASSERTED, the
    # enclosing quote carries no negation, and it carries no total count. It is
    # rejected only for describing instead of naming. The attributed band
    # admitted ONE reason, so those claims fell through both bands and never
    # reached `architectural_elements` — the field the architectural
    # observation consumes. On facade C that removed every window from the
    # pipeline and the report answered "not determinable from image".
    #
    # The band is therefore widened by EXACTLY ONE reason. This is evidence
    # RETENTION, not verification:
    #   * `state` stays UNVERIFIED and `grounded` stays False;
    #   * the verifier's recorded reason and empty `local_evidence` are kept;
    #   * CONFIRMED remains reserved for `independent_local_type_presence`;
    #   * AMBIGUOUS / UNKNOWN / interpretations / negated claims / rejected
    #     claims are still excluded by the gates below and above;
    #   * `classify_claim()` still rejects anything it rejected before.
    #
    # `no_applicable_independent_corroboration` is unchanged.
    # ==================================================

    attributable_reasons = (
        "no_applicable_independent_corroboration",
        "claim_properties_not_verified",
    )

    for candidate in candidates:

        if candidate.get("state") != "UNVERIFIED":
            continue

        if (candidate.get("verification") or {}).get("reason") not in (
            attributable_reasons
        ):
            continue

        if candidate.get("certainty") != "ASSERTED":
            continue

        verdict, reason = classify_claim(candidate["text"])

        if verdict == "reject":

            attributed_rejected.append({
                "field": "observed_attributed",
                "reason": reason,
                "value": candidate["text"],
            })

            continue

        attributed.append(candidate)

    # ==================================================
    # D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — MODEL-REPORTED ABSENCE
    #
    # MEASURED DEFECT: `_decision()` returns
    # `negative_claim_requires_explicit_local_absence` for a negative claim
    # whose `kind` is a RECOGNISED element kind (window, opening, door,
    # column, stair, furniture), and the attributed band above admits ONLY
    # `no_applicable_independent_corroboration`. Those absences therefore
    # vanished from the observation entirely — an architectural absence was
    # lost precisely BECAUSE its subject was a recognised element. The same
    # absence about `roof` or `terrace` survived, only because those are not
    # element kinds.
    #
    # This is a SEPARATE, lower-trust channel that admits a claim as
    # MODEL-REPORTED ABSENCE ONLY:
    #   * `state` stays UNVERIFIED and `grounded` is False, so nothing here
    #     can become independently corroborated fact;
    #   * only claims the verifier ITSELF marked negative are eligible, so the
    #     verification policy is not weakened and no rejected claim is
    #     promoted;
    #   * AMBIGUOUS / UNKNOWN / CONFIRMED claims are never admitted;
    #   * the original verifier reason and the verbatim quote are preserved.
    # Nothing is removed from the positive bands by this block.
    # ==================================================

    absence_attributed, absence_rejected = [], []

    for candidate in candidates:

        if candidate.get("state") != "UNVERIFIED":
            continue

        if (candidate.get("verification") or {}).get("reason") != (
            "negative_claim_requires_explicit_local_absence"
        ):
            continue

        if candidate.get("certainty") != "ASSERTED":
            continue

        if candidate.get("polarity") != "ABSENT":
            continue

        verdict, reason = classify_claim(candidate["text"])

        if verdict == "reject":

            absence_rejected.append({
                "field": "absence_attributed",
                "reason": reason,
                "value": candidate["text"],
            })

            continue

        absence_attributed.append({
            "text": candidate["text"],
            "source_quote": candidate["source_quote"],
            "category": candidate["category"],
            "kind": candidate.get("kind"),
            "certainty": candidate.get("certainty"),
            "state": candidate.get("state"),
            "grounded": False,
            "polarity": candidate.get("polarity"),
            "reason": (candidate.get("verification") or {}).get("reason"),
            "verification": copy.deepcopy(candidate.get("verification")),
        })

    def _texts(items):

        seen, out = set(), []

        for item in items:

            text = item["text"]

            if text not in seen:

                seen.add(text)
                out.append(text)

        return out

    confirmed_architectural = _texts(
        c for c in confirmed if c.get("category") in architectural_categories
    )

    attributed_architectural = _texts(
        c for c in attributed if c.get("category") in architectural_categories
    )

    result["observed_attributed"] = _texts(attributed)

    # D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — model-reported absence, lower trust.
    result["absence_attributed"] = absence_attributed
    if absence_rejected:
        result["absence_rejected"] = absence_rejected

    result["architectural_elements"] = confirmed_architectural + [
        text for text in attributed_architectural
        if text not in confirmed_architectural
    ]

    ambiguous = [c for c in candidates if c.get("state") == "AMBIGUOUS"]
    unknown_claims = [c for c in candidates if c.get("state") == "UNVERIFIED"
                      and (c.get("verification") or {}).get("reason") == "unknown_preserved"]

    observer_status = raw.get("generation_status")
    normalization_status = normalization.get("status")

    if normalization_status != "NORMALIZED":
        evidence_state = "NORMALIZATION_FAILED"
    elif observer_status == "FAILED" or (not raw.get("raw_text") and not candidates):
        evidence_state = "PROVIDER_FAILED"
    elif result["observed"]:
        evidence_state = "OBSERVED"
    elif result["observed_attributed"]:
        evidence_state = "INFERRED"
    else:
        evidence_state = "UNKNOWN"

    # A confidence LEVEL is a classification of the evidence that exists —
    # never a score invented for the model. The rule and its inputs are both
    # recorded in `confidence_basis`, so a reader can always recompute it.
    if len(result["observed"]) >= 3 and not ambiguous:
        confidence = "HIGH"
    elif result["observed"]:
        confidence = "MEDIUM"
    elif len(result["observed_attributed"]) >= 3 and not ambiguous:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    result["confidence"] = confidence

    result["evidence_state"] = evidence_state

    result["confidence_basis"] = (
        "confirmed=%d attributed=%d ambiguous=%d unknown=%d local_corroboration=%s"
        % (
            len(result["observed"]),
            len(result["observed_attributed"]),
            len(ambiguous),
            len(unknown_claims),
            "grounded" if local_grounded else "none",
        )
    )

    result["diagnostics"] = {
        "evidence_type": "RUNTIME_STATUS",
        "provider": provider,
        "model": model,
        "observer_generation_status": observer_status,
        "observer_error": raw.get("error"),
        "normalization_status": normalization_status,
        "normalization_error": normalization.get("error"),
        "verification_error": verification_error,
        "candidate_count": len(candidates),
        "confirmed_count": len(confirmed),
        "attributed_count": len(result["observed_attributed"]),
        "ambiguous_count": len(ambiguous),
        "unknown_count": len(unknown_claims),
        "local_corroboration_available": bool(local_grounded),
        "raw_observer_retained": bool(raw.get("raw_text")),
    }

    if attributed_rejected:

        result["safety"]["rejected_claims"] = (
            list(result["safety"].get("rejected_claims") or []) + attributed_rejected
        )

    # `analysis_status` follows the evidence instead of being forced. A forced
    # value made a normalizer failure, an empty observation and a low-confidence
    # observation all report the same status.
    if evidence_state == "PROVIDER_FAILED":
        result["analysis_status"] = STATUS_PROVIDER_UNAVAILABLE
    elif evidence_state == "NORMALIZATION_FAILED":
        result["analysis_status"] = (
            STATUS_PARTIAL if raw.get("raw_text") or local_grounded
            else STATUS_PROVIDER_UNAVAILABLE
        )
        result["unresolved"].append(
            "visual observer normalization or verification unavailable; "
            "retained raw and local evidence"
        )
    elif evidence_state == "UNKNOWN":
        result["analysis_status"] = STATUS_PARTIAL
    elif confidence == "LOW" or ambiguous:
        result["analysis_status"] = STATUS_ANALYZED_WITH_UNCERTAINTY
    else:
        result["analysis_status"] = STATUS_ANALYZED

    if observer_status != "COMPLETE" and raw.get("raw_text"):
        result["analysis_status"] = STATUS_PARTIAL
        result["unresolved"].append(
            "visual observer generation incomplete; raw output retained"
        )

    # ==================================================
    # ARCHITECTURAL_FACADE_ELEMENT_EVIDENCE_V7.2
    #
    # The PRODUCTION image-analysis path builds understanding from the bridge
    # contract, so it never passes through the main builder's element-evidence
    # carry. Without this block, `element_evidence` would never exist in a real
    # application turn no matter what the adapter could do.
    #
    # Claims come from the EXISTING normalizer output that is already in the
    # bridge; the source text is the observer's own retained raw output, so
    # every carried quote is anchored to what the model actually said. No model
    # call is made here and none is triggered by an ordinary chat turn.
    #
    # Fail-safe: any defect leaves `element_evidence` as None, which downstream
    # treats as "no evidence" rather than "evidence of nothing".
    # ==================================================
    try:

        from core.vision.architectural_observation_v1 import (
            element_evidence_from_claims,
            recovered_claims_from_failures,
        )
        from core.vision.observation_normalizer_v1 import iter_claims

        _structured = normalization.get("structured")

        if isinstance(_structured, dict):

            _diagnostics = raw.get("diagnostics") or {}

            _source_text = raw.get("raw_text") or ""

            # V7.3 — stage-C recovery. The normalizer drops a claim when its
            # concise element LABEL is not a verbatim substring of its own
            # descriptive quote ("lanterns" vs "Small black metal lantern
            # fixtures ..."). Those claims are recovered only when the quote
            # still resolves, is not negated, and supports the kind. The model's
            # own output is never rewritten.
            _failures = normalization.get("source_resolution_failures") or []

            _accepted_claims = [
                dict(claim, claim_category=category)
                for category, claim in iter_claims(_structured)
            ]

            _recovered = recovered_claims_from_failures(
                _failures,
                _source_text,
            )

            _anchored, _report = element_evidence_from_claims(
                {},
                _accepted_claims + _recovered,
                _source_text,
                source_image={
                    "sha256": _diagnostics.get("original_source_sha256"),
                    "width": (_diagnostics.get("observer_input_width")
                              or _diagnostics.get("original_width")),
                    "height": (_diagnostics.get("observer_input_height")
                               or _diagnostics.get("original_height")),
                    "crop_box": None,
                    "parent": None,
                },
                raw_claim_count=len(_accepted_claims) + len(_failures),
                normalizer_accepted_count=len(_accepted_claims),
            )

            _report["stage_c_recovered_claims"] = len(_recovered)

            _block = _anchored.get("element_evidence") or {}

            _report["stage_c_recovered_evidence_records"] = sum(
                1 for entry in (_block.get("elements") or [])
                if entry.get("recovered")
            )

            result["element_evidence"] = _block if _block.get("elements") else None
            result["element_evidence_report"] = _report

    except Exception as _element_error:  # noqa: BLE001 - never break analysis

        result["element_evidence"] = None
        result["element_evidence_report"] = {
            "contract": "SourceAnchoredElementEvidenceV1",
            "error": type(_element_error).__name__ + ":" + str(_element_error),
        }

    return result
